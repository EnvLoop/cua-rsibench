"""Independent saved-OOXML oracle for filing-pinned Excel-web candidates.

Does not import either candidate generator or workbook builder, and never
accepts a formula string or cached value as the expected business result.
"""

from __future__ import annotations

import argparse
from datetime import date
from functools import lru_cache
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


HERE = Path(__file__).resolve().parent
PINS = {
    "AAPL": ("apple-companyfacts.json.gz", "73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43", 320193),
    "MSFT": ("microsoft-companyfacts.json.gz", "f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f", 789019),
}
TAGS = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "operating_income": "OperatingIncomeLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capital_expenditures": "PaymentsToAcquirePropertyPlantAndEquipment",
    "cost_of_sales": "CostOfGoodsAndServicesSold",
    "assets": "Assets", "liabilities": "Liabilities", "equity": "StockholdersEquity",
    "inventory": "InventoryNet", "trade_payables": "AccountsPayableCurrent",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
}
FLOW = set(list(TAGS)[:5])
ANNUAL_METRICS = tuple(TAGS)
Q3_METRICS = ANNUAL_METRICS[:5]


@lru_cache(maxsize=2)
def source(ticker: str) -> dict:
    filename, pin, cik = PINS[ticker]
    raw = gzip.decompress((HERE / "sources/raw" / filename).read_bytes())
    if sha256(raw).hexdigest() != pin:
        raise ValueError("raw_source_hash_changed")
    parsed = json.loads(raw)
    if parsed.get("cik") != cik:
        raise ValueError("source_cik_changed")
    return parsed


def read_number(cells: dict[str, dict[str, Cell]], sheet: str, addr: str) -> float:
    cell = cells.get(sheet, {}).get(addr)
    if cell is None or cell.value is None or cell.formula:
        raise ValueError(f"input_not_literal:{sheet}!{addr}")
    return float(cell.value)


def exact_source_record(sec: dict, record: dict) -> None:
    if record["concept"] != TAGS[record["metric"]] or record["unit"] != "USD":
        raise ValueError("source_concept_or_unit_invalid")
    rows = sec["facts"]["us-gaap"][record["concept"]]["units"]["USD"]
    matches = [r for r in rows if
               r.get("accn") == record["accession"] and r.get("filed") == record["filed"]
               and r.get("form") == record["form"] and r.get("start", "") == record["start"]
               and r.get("end") == record["end"] and r.get("fy") == record["fy"]
               and r.get("fp") == record["fp"] and r.get("frame", "") == record["frame"]
               and r.get("val") == record["value"]]
    if len({json.dumps(r, sort_keys=True) for r in matches}) != 1:
        raise ValueError(f"source_record_not_exactly_pinned:{record['metric']}:{record['accession']}")


def canonical_values(case: dict, source_delta: dict[str, float]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    pkg = case["source_package"]
    sec = source(pkg["ticker"])
    if pkg["cik"] != sec["cik"]:
        raise ValueError("case_cik_mismatch")
    for record in pkg["annual_rows"] + pkg["q3_rows"]:
        exact_source_record(sec, record)
    annual, q3 = {}, {}
    for metric in ANNUAL_METRICS:
        r = pkg["canonical"][f"annual:{metric}"]
        exact_source_record(sec, r)
        if r["accession"] != pkg["annual_accession"] or r["end"] != pkg["annual_end"]:
            raise ValueError("wrong_annual_filing_lineage")
        if (r["start"] == pkg["annual_start"]) != (metric in FLOW):
            raise ValueError("annual_duration_or_stock_mismatch")
        annual[metric] = float(r["value"]) / 1_000_000 + source_delta.get(f"annual:{metric}", 0.0)
    for metric in Q3_METRICS:
        r = pkg["canonical"][f"q3:{metric}"]
        exact_source_record(sec, r)
        if (r["accession"] != pkg["q3_accession"] or r["start"] != pkg["annual_start"]
                or r["end"] != pkg["q3_end"]):
            raise ValueError("wrong_q3_ytd_lineage")
        q3[metric] = float(r["value"]) / 1_000_000 + source_delta.get(f"q3:{metric}", 0.0)
    prior = {}
    for metric in ("inventory", "trade_payables"):
        rows = [r for r in pkg["annual_rows"] if
                r["metric"] == metric and r["end"] < pkg["annual_end"] and not r["start"]]
        latest = max(r["end"] for r in rows)
        matches = [r for r in rows if r["end"] == latest]
        if len(matches) != 1:
            raise ValueError(f"opening_balance_ambiguous:{metric}")
        prior[metric] = float(matches[0]["value"]) / 1_000_000 + source_delta.get(f"opening:{metric}", 0.0)
    return annual, q3, prior


def target_addresses(split: str) -> set[tuple[str, str]]:
    result = {("FY Selection", f"B{r}") for r in range(5, 16)}
    result |= {("Review", f"B{r}") for r in range(5, 12)}
    result.add(("Audit", "B5"))
    if split != "train_candidate":
        result |= {("Q3 Selection", f"B{r}") for r in range(5, 10)}
        result |= {("Q4 Bridge", f"B{r}") for r in range(5, 10)}
        result |= {("Q4 Bridge", f"C{r}") for r in range(10, 13)}
        result.add(("Audit", "B6"))
    if split == "final_candidate":
        result |= {("Working Capital", f"B{r}") for r in range(5, 14)}
    if split != "selection_candidate":
        result |= {("Scenario", f"C{r}") for r in range(5, 11)}
    return result


def expected_values(case: dict, *, source_delta: dict[str, float] | None = None,
                    scenario_delta: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    source_delta = source_delta or {}
    scenario_delta = scenario_delta or {}
    split, pkg = case["split"], case["source_package"]
    a, q, prior = canonical_values(case, source_delta)
    out = {("FY Selection", f"B{i + 5}"): a[metric] for i, metric in enumerate(ANNUAL_METRICS)}
    if split != "train_candidate":
        q4 = {m: a[m] - q[m] for m in Q3_METRICS}
        out.update({("Q3 Selection", f"B{i + 5}"): q[m] for i, m in enumerate(Q3_METRICS)})
        out.update({("Q4 Bridge", f"B{i + 5}"): q4[m] for i, m in enumerate(Q3_METRICS)})
        out[("Q4 Bridge", "C10")] = q4["operating_income"] / q4["revenue"]
        out[("Q4 Bridge", "C11")] = q4["operating_cash_flow"] - q4["capital_expenditures"]
        out[("Q4 Bridge", "C12")] = out[("Q4 Bridge", "C11")] / q4["revenue"]
        out[("Audit", "B6")] = q4["revenue"] + q["revenue"] - a["revenue"]
    if split == "final_candidate":
        days = (date.fromisoformat(pkg["annual_end"]) - date.fromisoformat(pkg["annual_start"])).days + 1
        wc = (a["inventory"], a["trade_payables"], a["cost_of_sales"], days,
              (a["inventory"] + prior["inventory"]) / 2 / a["cost_of_sales"] * days,
              (a["trade_payables"] + prior["trade_payables"]) / 2 / a["cost_of_sales"] * days,
              a["inventory"] - a["trade_payables"], prior["inventory"], prior["trade_payables"])
        for row, value in zip(range(5, 14), wc):
            out[("Working Capital", f"B{row}")] = value
    if split != "selection_candidate":
        inv_shock = case["scenario"]["inventory_shock_m"] + scenario_delta.get("inventory_shock_m", 0)
        ap_shock = case["scenario"]["payables_shock_m"] + scenario_delta.get("payables_shock_m", 0)
        multiplier = case["scenario"]["capex_multiplier"] + scenario_delta.get("capex_multiplier", 0)
        stressed_inv = a["inventory"] + inv_shock
        stressed_ap = a["trade_payables"] + ap_shock
        stressed_wc = stressed_inv - stressed_ap
        stressed_capex = a["capital_expenditures"] * multiplier
        stressed_fcf = a["operating_cash_flow"] - stressed_capex
        for row, value in zip(range(5, 11),
                              (stressed_inv, stressed_ap, stressed_capex,
                               stressed_wc, stressed_fcf, stressed_fcf / a["revenue"])):
            out[("Scenario", f"C{row}")] = value
    review = [a["revenue"], a["operating_income"] / a["revenue"],
              a["operating_cash_flow"] - a["capital_expenditures"]]
    if split == "train_candidate":
        review += [a["revenue"] - a["cost_of_sales"], a["cash"]]
    else:
        review += [q4["revenue"], out[("Q4 Bridge", "C10")]]
    if split == "selection_candidate":
        review += [out[("Q4 Bridge", "C11")], out[("Q4 Bridge", "C12")]]
    else:
        review += [out[("Scenario", "C9")], out[("Scenario", "C8")]]
    for row, value in zip(range(5, 12), review):
        out[("Review", f"B{row}")] = value
    out[("Audit", "B5")] = a["assets"] - a["liabilities"] - a["equity"]
    if set(out) != target_addresses(split):
        raise ValueError("oracle_target_coverage")
    return out


def raw_cell(cells: dict[str, dict[str, Cell]], record: dict, tab: str) -> tuple[str, str]:
    matches = []
    for addr, cell in cells[tab].items():
        if not addr.startswith("A") or not addr[1:].isdigit() or int(addr[1:]) < 5:
            continue
        r = addr[1:]
        actual = tuple((cells[tab].get(f"{col}{r}") or Cell(None, None, None)).value or ""
                       for col in "ACDEFGHI")
        wanted = (record["id"], record["metric"], record["concept"], record["start"],
                  record["end"], record["filed"], record["form"], record["accession"])
        if actual == wanted:
            matches.append((tab, f"N{r}"))
    if len(matches) != 1:
        raise ValueError(f"raw_provenance_lineage:{tab}:{record['id']}:{len(matches)}")
    return matches[0]


def override_inputs(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict[tuple[str, str], float], dict[str, float], dict[str, float]]:
    source_delta = {}
    overrides = {}
    records = case["source_package"]["canonical"]
    for i, (key, record) in enumerate(sorted(records.items())):
        if key.startswith("q3:") and case["split"] == "train_candidate":
            continue
        delta = (31 + i * 17) * (1 if profile == 1 else (-1 if i % 2 else 1))
        source_delta[key] = delta
        tab = "Annual 10-K" if key.startswith("annual:") else "Q3 10-Q"
        addr = raw_cell(cells, record, tab)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    if case["split"] == "final_candidate":
        pkg = case["source_package"]
        for i, metric in enumerate(("inventory", "trade_payables")):
            prior_rows = [r for r in pkg["annual_rows"] if r["metric"] == metric and not r["start"] and r["end"] < pkg["annual_end"]]
            record = max(prior_rows, key=lambda r: r["end"])
            delta = (71 + i * 43) * (1 if profile == 1 else -1)
            source_delta[f"opening:{metric}"] = delta
            addr = raw_cell(cells, record, "Annual 10-K")
            overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    scenario_delta = {}
    if case["split"] != "selection_candidate":
        scenario_delta = {"inventory_shock_m": 47 * profile,
                          "payables_shock_m": -37 * profile,
                          "capex_multiplier": 0.07 * profile}
        for key, row in (("inventory_shock_m", 5), ("payables_shock_m", 6), ("capex_multiplier", 7)):
            overrides[("Scenario", f"B{row}")] = case["scenario"][key] + scenario_delta[key]
    return overrides, source_delta, scenario_delta


def verify(candidate_path: Path, seed_path: Path, case: dict) -> dict:
    errors = []
    try:
        candidate, order, tables, structure = load_xlsx(candidate_path)
        seed, seed_order, seed_tables, seed_structure = load_xlsx(seed_path)
        targets = target_addresses(case["split"])
        expected_order = {
            "train_candidate": ["Review", "FY Selection", "Scenario", "Audit", "Annual 10-K", "Source Map"],
            "selection_candidate": ["Review", "FY Selection", "Q3 Selection", "Q4 Bridge", "Audit", "Annual 10-K", "Q3 10-Q", "Source Map"],
            "final_candidate": ["Review", "FY Selection", "Q3 Selection", "Q4 Bridge", "Working Capital", "Scenario", "Audit", "Annual 10-K", "Q3 10-Q", "Source Map"],
        }[case["split"]]
        if order != expected_order or seed_order != expected_order:
            errors.append("sheet_identity_or_order_changed")
        if tables != seed_tables or structure != seed_structure:
            errors.append("table_or_sheet_structure_changed")
        for sheet in seed_order:
            for addr in set(seed[sheet]) | set(candidate.get(sheet, {})):
                key = (sheet, addr)
                old, new = seed[sheet].get(addr), candidate.get(sheet, {}).get(addr)
                if key not in targets:
                    if old is None or new is None or not unchanged_cell(old, new):
                        errors.append(f"non_target_cell_changed:{sheet}!{addr}")
                elif new is None or not new.formula:
                    errors.append(f"target_formula_missing:{sheet}!{addr}")
        if errors:
            return {"pass": False, "errors": errors[:30], "checked_targets": len(targets), "counterfactual_profiles": 0}
        for profile in (0, 1, 2):
            if profile == 0:
                overrides, sd, sc = {}, {}, {}
            else:
                overrides, sd, sc = override_inputs(case, candidate, profile)
            expected = expected_values(case, source_delta=sd, scenario_delta=sc)
            evaluator = Evaluator(candidate, overrides)
            for sheet, addr in sorted(targets):
                try:
                    actual = evaluator.cell(sheet, addr)
                    if not close(actual, expected[(sheet, addr)]):
                        errors.append(f"numeric_or_dependency_error_p{profile}:{sheet}!{addr}")
                    if profile == 0:
                        cached = candidate[sheet][addr].value
                        if cached is not None and not close(float(cached), actual):
                            errors.append(f"stale_formula_cache:{sheet}!{addr}")
                except Exception as exc:
                    errors.append(f"formula_error_p{profile}:{sheet}!{addr}:{type(exc).__name__}")
        return {"pass": not errors, "errors": errors[:30],
                "checked_targets": len(targets), "counterfactual_profiles": 2}
    except Exception as exc:
        return {"pass": False, "errors": [f"oracle_setup:{type(exc).__name__}:{exc}"],
                "checked_targets": 0, "counterfactual_profiles": 0}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--seed", type=Path, required=True)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--case-id", required=True)
    args = p.parse_args()
    cases = json.loads(args.cases.read_text())
    matching = [case for case in cases if case["case_id"] == args.case_id]
    if len(matching) != 1:
        raise SystemExit("case identity missing or ambiguous")
    result = verify(args.candidate, args.seed, matching[0])
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
