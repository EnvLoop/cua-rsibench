"""Independent OOXML oracle for the retail working-capital audit prototype.

The workbook builder is never imported. Expected outputs are recomputed from a
hash-pinned SEC excerpt, and candidate formulas are replayed with public
development source/scenario perturbations rather than trusting Excel's cached
values. The legacy result field ``private_replay_profiles`` is retained so
previously hashed development receipts remain reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "sources/retail_excerpt.json"
SOURCE_SHA256 = "df9f56387b2c30bc521d8a4eb13c6e437a065d3b921ed4ae3a5fab1e1f20f64a"
SHEETS = ["Review", "History", "Year Delta", "Scenario", "Raw SEC"]
FLOW = {"Revenue", "Cost of sales"}
SPECS = {
    "COST": {"cik": 909832, "old": "0000909832-23-000042", "new": "0000909832-24-000049",
             "ends": {"2022": "2022-08-28", "2023": "2023-09-03", "2024": "2024-09-01"},
             "concepts": {"Revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
                          "Cost of sales": "CostOfGoodsAndServicesSold", "Inventory": "InventoryNet",
                          "Trade payables": "AccountsPayableCurrent"}},
    "WMT": {"cik": 104169, "old": "0000104169-23-000020", "new": "0000104169-24-000056",
            "ends": {"2022": "2022-01-31", "2023": "2023-01-31", "2024": "2024-01-31"},
            "concepts": {"Revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
                         "Cost of sales": "CostOfRevenue", "Inventory": "InventoryNet",
                         "Trade payables": "AccountsPayableCurrent"}},
}
TARGETS = {
    *(("History", f"{col}{row}") for row in range(5, 9) for col in "DEFGHIJKLMNO"),
    *(("Year Delta", f"{col}{row}") for row in (5, 6) for col in "BCDEFG"),
    *(("Scenario", f"{col}{row}") for row in (5, 6) for col in "DEFGHIJK"),
    *(("Review", f"{col}{row}") for row in (5, 6) for col in "BCDEFGHI"),
}


@lru_cache(maxsize=1)
def source_rows() -> list[dict]:
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("frozen_source_excerpt_hash_changed")
    data = json.loads(raw)
    if data.get("schema") != "sec-retail-working-capital-source-v1":
        raise ValueError("frozen_source_excerpt_schema_changed")
    if {r["cik"] for r in data["source_meta"]} != {909832, 104169}:
        raise ValueError("frozen_source_excerpt_issuers_changed")
    return data["records"]


def _fact(issuer: str, year: str, metric: str) -> dict:
    spec = SPECS[issuer]
    accession = spec["old"] if year == "2022" else spec["new"]
    matches = [row for row in source_rows() if
               row.get("issuer") == issuer and row.get("metric") == metric
               and row.get("concept") == spec["concepts"][metric]
               and row.get("end") == spec["ends"][year]
               and row.get("accession") == accession
               and row.get("form") == "10-K" and row.get("unit") == "USD"
               and bool(row.get("start")) == (metric in FLOW)]
    if len(matches) != 1:
        raise ValueError(f"canonical_source_ambiguity:{issuer}:{year}:{metric}:{len(matches)}")
    return matches[0]


def _source_value(issuer: str, year: str, metric: str, deltas: dict[tuple[str, str, str], float]) -> float:
    return float(_fact(issuer, year, metric)["value"]) / 1_000_000 + deltas.get((issuer, year, metric), 0)


def _scenario(seed: dict[str, dict[str, Cell]], issuer: str, col: str, deltas: dict[tuple[str, str], float]) -> float:
    addr = f"{col}{5 if issuer == 'COST' else 6}"
    cell = seed["Scenario"].get(addr)
    if cell is None or cell.value is None or cell.formula is not None:
        raise ValueError(f"scenario_input_missing:{addr}")
    return float(cell.value) + deltas.get((issuer, col), 0)


def expected_values(seed: dict[str, dict[str, Cell]], *, source_deltas_m: dict[tuple[str, str, str], float] | None = None,
                    scenario_deltas_m: dict[tuple[str, str], float] | None = None) -> dict[tuple[str, str], float]:
    source_deltas_m = source_deltas_m or {}
    scenario_deltas_m = scenario_deltas_m or {}
    out: dict[tuple[str, str], float] = {}
    history: dict[tuple[str, str], dict[str, float]] = {}
    for issuer, year, row in (("COST", "2023", 5), ("COST", "2024", 6),
                              ("WMT", "2023", 7), ("WMT", "2024", 8)):
        previous = str(int(year) - 1)
        revenue = _source_value(issuer, year, "Revenue", source_deltas_m)
        cost = _source_value(issuer, year, "Cost of sales", source_deltas_m)
        opening_inv = _source_value(issuer, previous, "Inventory", source_deltas_m)
        closing_inv = _source_value(issuer, year, "Inventory", source_deltas_m)
        opening_ap = _source_value(issuer, previous, "Trade payables", source_deltas_m)
        closing_ap = _source_value(issuer, year, "Trade payables", source_deltas_m)
        flow = _fact(issuer, year, "Revenue")
        days = (date.fromisoformat(flow["end"]) - date.fromisoformat(flow["start"])).days + 1
        if float(seed["History"][f"C{row}"].value or 0) != days:
            raise ValueError(f"fiscal_days_seed_mismatch:{issuer}:{year}")
        avg_inv = (opening_inv + closing_inv) / 2
        avg_ap = (opening_ap + closing_ap) / 2
        values = (revenue, cost, opening_inv, closing_inv, opening_ap, closing_ap,
                  avg_inv, avg_ap, avg_inv / cost * days, avg_ap / cost * days,
                  closing_inv - closing_ap, (revenue - cost) / revenue)
        history[(issuer, year)] = dict(zip(("revenue", "cost", "opening_inv", "closing_inv", "opening_ap", "closing_ap",
                                           "avg_inv", "avg_ap", "dio", "dpo", "net", "margin"), values))
        for col, value in zip("DEFGHIJKLMNO", values):
            out[("History", f"{col}{row}")] = value
    for issuer, row in (("COST", 5), ("WMT", 6)):
        old, current = history[(issuer, "2023")], history[(issuer, "2024")]
        delta = (current["dio"] - old["dio"], current["dpo"] - old["dpo"],
                 current["net"], old["net"], current["net"] - old["net"],
                 current["margin"] - old["margin"])
        for col, value in zip("BCDEFG", delta):
            out[("Year Delta", f"{col}{row}")] = value
        inv_shock = _scenario(seed, issuer, "B", scenario_deltas_m)
        ap_shock = _scenario(seed, issuer, "C", scenario_deltas_m)
        stressed_inv = current["closing_inv"] + inv_shock
        stressed_ap = current["closing_ap"] + ap_shock
        stressed_avg_inv = (current["opening_inv"] + stressed_inv) / 2
        stressed_avg_ap = (current["opening_ap"] + stressed_ap) / 2
        fiscal_days = (date.fromisoformat(_fact(issuer, "2024", "Revenue")["end"])
                       - date.fromisoformat(_fact(issuer, "2024", "Revenue")["start"])).days + 1
        stressed = (stressed_inv, stressed_ap, stressed_avg_inv, stressed_avg_ap,
                    stressed_avg_inv / current["cost"] * fiscal_days,
                    stressed_avg_ap / current["cost"] * fiscal_days,
                    stressed_inv - stressed_ap, stressed_inv - stressed_ap - current["net"])
        for col, value in zip("DEFGHIJK", stressed):
            out[("Scenario", f"{col}{row}")] = value
        review = (current["dio"], current["dpo"], current["net"], delta[0], delta[1],
                  stressed[-1], stressed[4], stressed[6])
        for col, value in zip("BCDEFGHI", review):
            out[("Review", f"{col}{row}")] = value
    if set(out) != TARGETS:
        raise ValueError(f"oracle_target_coverage:{len(out)}:{len(TARGETS)}")
    return out


def perturbation_profiles() -> list[tuple[dict[tuple[str, str, str], float], dict[tuple[str, str], float]]]:
    source_keys = []
    for ticker in SPECS:
        for year in ("2022", "2023", "2024"):
            metrics = ("Inventory", "Trade payables") if year == "2022" else ("Revenue", "Cost of sales", "Inventory", "Trade payables")
            source_keys.extend((ticker, year, metric) for metric in metrics)
    first = {key: float((i + 1) * 31) for i, key in enumerate(source_keys)}
    second = {key: float(((-1) ** i) * (i * 17 + 47)) for i, key in enumerate(source_keys)}
    return [(first, {("COST", "B"): 125, ("COST", "C"): -75, ("WMT", "B"): 260, ("WMT", "C"): -140}),
            (second, {("COST", "B"): -95, ("COST", "C"): 155, ("WMT", "B"): -340, ("WMT", "C"): 220})]


def _raw_address(candidate: dict[str, dict[str, Cell]], ticker: str, year: str, metric: str) -> tuple[str, str]:
    source = _fact(ticker, year, metric)
    raw = candidate["Raw SEC"]
    matches = []
    for addr, cell in raw.items():
        if not addr.startswith("A") or not addr[1:].isdigit() or int(addr[1:]) < 5:
            continue
        row = addr[1:]
        columns = ("A", "B", "C", "D", "E", "F", "H", "I", "M")
        actual = tuple(raw.get(f"{col}{row}", Cell(None, None, None)).value or "" for col in columns)
        expected = (source["id"], ticker, metric, source["concept"], source["start"], source["end"], "10-K", source["accession"], "USD")
        if actual == expected:
            matches.append(("Raw SEC", f"N{row}"))
    if len(matches) != 1:
        raise ValueError(f"raw_lineage_ambiguity:{ticker}:{year}:{metric}:{len(matches)}")
    return matches[0]


def _overrides(candidate: dict[str, dict[str, Cell]], seed: dict[str, dict[str, Cell]],
               source_deltas: dict[tuple[str, str, str], float], scenario_deltas: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    overrides = {}
    for (ticker, year, metric), delta_m in source_deltas.items():
        ref = _raw_address(candidate, ticker, year, metric)
        overrides[ref] = float(candidate[ref[0]][ref[1]].value) + delta_m * 1_000_000
    for (ticker, col), delta_m in scenario_deltas.items():
        ref = ("Scenario", f"{col}{5 if ticker == 'COST' else 6}")
        overrides[ref] = _scenario(seed, ticker, col, {(ticker, col): delta_m})
    return overrides


def verify(candidate_path: Path, seed_path: Path, reference_path: Path) -> dict:
    errors: list[str] = []
    try:
        candidate, order, tables, structure = load_xlsx(candidate_path)
        seed, seed_order, seed_tables, seed_structure = load_xlsx(seed_path)
        reference, reference_order, reference_tables, reference_structure = load_xlsx(reference_path)
    except Exception as exc:
        return {"pass": False, "errors": [f"invalid_xlsx:{exc}"]}
    if order != SHEETS or seed_order != SHEETS or reference_order != SHEETS:
        errors.append("sheet_order_or_identity_changed")
    if tables != seed_tables or tables != reference_tables or structure != seed_structure or structure != reference_structure:
        errors.append("table_or_sheet_structure_changed")
    allowed_repairs = {key for key in TARGETS if seed.get(key[0], {}).get(key[1], Cell(None, None, None)).formula
                       != reference.get(key[0], {}).get(key[1], Cell(None, None, None)).formula}
    if len(allowed_repairs) != 9:
        errors.append("private_repair_manifest_invalid")
    for sheet in seed_order:
        for addr in set(seed[sheet]) | set(candidate.get(sheet, {})):
            key = (sheet, addr)
            old, new = seed[sheet].get(addr), candidate.get(sheet, {}).get(addr)
            if key in TARGETS:
                if new is None or not new.formula:
                    errors.append(f"missing_formula:{sheet}!{addr}")
                elif key not in allowed_repairs and (old is None or old.formula != new.formula):
                    errors.append(f"previously_correct_formula_changed:{sheet}!{addr}")
                continue
            if old is None or new is None or not unchanged_cell(old, new):
                errors.append(f"non_target_cell_changed:{sheet}!{addr}")
    if errors:
        return {"pass": False, "errors": errors[:30], "checked_targets": len(TARGETS),
                "allowed_repairs": len(allowed_repairs), "repaired_faults": 0, "repair_score": 0.0}
    try:
        cases = [(expected_values(seed), {})]
        for source_deltas, scenarios in perturbation_profiles():
            cases.append((expected_values(seed, source_deltas_m=source_deltas, scenario_deltas_m=scenarios),
                          _overrides(candidate, seed, source_deltas, scenarios)))
        for index, (expected, overrides) in enumerate(cases):
            evaluator = Evaluator(candidate, overrides)
            for sheet, addr in sorted(TARGETS):
                try:
                    actual = evaluator.cell(sheet, addr)
                    if not close(actual, expected[(sheet, addr)]):
                        errors.append(f"{'wrong_result' if index == 0 else f'dependency_failure_p{index}'}:{sheet}!{addr}")
                    if index == 0:
                        cached = candidate[sheet][addr].value
                        if cached is not None and not close(float(cached), actual):
                            errors.append(f"stale_cache:{sheet}!{addr}")
                except Exception as exc:
                    errors.append(f"evaluation_error_p{index}:{sheet}!{addr}:{exc}")
        repaired = 0
        for key in allowed_repairs:
            if candidate[key[0]][key[1]].formula == seed[key[0]][key[1]].formula:
                continue
            correct = True
            for expected, overrides in cases:
                isolated = dict(overrides)
                isolated.update({other: value for other, value in expected.items() if other != key})
                try:
                    if not close(Evaluator(candidate, isolated).cell(*key), expected[key]):
                        correct = False
                        break
                except Exception:
                    correct = False
                    break
            repaired += int(correct)
    except Exception as exc:
        errors.append(f"verification_error:{exc}")
        repaired = 0
    return {"pass": not errors and repaired == len(allowed_repairs), "errors": errors[:30],
            "checked_targets": len(TARGETS), "allowed_repairs": len(allowed_repairs),
            "repaired_faults": repaired, "repair_score": repaired / len(allowed_repairs) if allowed_repairs else 0.0,
            "private_replay_profiles": len(cases) - 1 if "cases" in locals() else 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("seed", type=Path)
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.candidate, args.seed, args.reference), indent=2))
