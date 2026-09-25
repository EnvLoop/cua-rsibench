"""Independent saved-OOXML oracle for mixed-unit EPS/capital-return cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Return Review", "Filing Selection", "EPS Bridge", "Capital Returns",
          "Repurchase Scenario", "Audit", "Source 10-K", "Filing Map"]
METRICS = ("net_income", "basic_shares", "diluted_shares", "eps_basic",
           "eps_diluted", "repurchases", "dividends")
UNITS = {"net_income": "USD", "basic_shares": "shares", "diluted_shares": "shares",
         "eps_basic": "USD/shares", "eps_diluted": "USD/shares",
         "repurchases": "USD", "dividends": "USD"}
TARGETS = {
    *(("Filing Selection", f"{col}{row}") for col in "BC" for row in range(5, 12)),
    *(("EPS Bridge", f"B{row}") for row in range(5, 13)),
    *(("Capital Returns", f"{col}{row}") for col in "BC" for row in range(5, 11)),
    *(("Repurchase Scenario", f"C{row}") for row in range(5, 11)),
    *(("Return Review", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("eps_excerpt_hash_changed")
    source = json.loads(raw)
    if source["cik"] != case["cik"] or source["filing_accession"] != case["filing_accession"]:
        raise ValueError("source_filing_identity_changed")
    if source["source_raw_json_sha256"] != case["source_raw_json_sha256"]:
        raise ValueError("source_raw_pin_changed")
    earlier = json.loads((ROOT / "sec_excel_factory/candidate_audit_fetched_2026-09-24.json").read_text())
    prior = next(row for row in earlier["results"] if row["ticker"] == case["ticker"])
    if prior["sha256_raw_json"] != case["source_raw_json_sha256"]:
        raise ValueError("prior_direct_sec_hash_not_matching")
    out = {}
    for year in ("prior", "current"):
        end = case["prior_end"] if year == "prior" else case["annual_end"]
        starts = set()
        for metric in METRICS:
            key = f"{year}:{metric}"
            record = case["canonical"][key]
            if record not in source["records"]:
                raise ValueError(f"canonical_not_in_pinned_excerpt:{key}")
            if (record["unit"] != UNITS[metric] or record["accession"] != case["filing_accession"]
                    or record["form"] != "10-K" or record["end"] != end):
                raise ValueError(f"wrong_source_lineage_or_unit:{key}")
            if not 330 <= (date.fromisoformat(end) - date.fromisoformat(record["start"])).days + 1 <= 381:
                raise ValueError(f"not_annual_fact:{key}")
            starts.add(record["start"])
            convert = 1 if metric.startswith("eps_") else 1_000_000
            out[key] = float(record["value"]) / convert + deltas.get(key, 0)
        if len(starts) != 1:
            raise ValueError(f"source_year_flow_starts_disagree:{year}")
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    price = case["scenario"]["synthetic_repurchase_price_usd"] + scenario_deltas.get("price", 0)
    fraction = case["scenario"]["synthetic_buyback_budget_fraction"] + scenario_deltas.get("fraction", 0)
    if price <= 0 or not 0 < fraction < 1:
        raise ValueError("scenario_out_of_range")
    out = {}
    for year, col in (("prior", "B"), ("current", "C")):
        for row, metric in zip(range(5, 12), METRICS):
            out[("Filing Selection", f"{col}{row}")] = f[f"{year}:{metric}"]
    basic, diluted = f["current:basic_shares"], f["current:diluted_shares"]
    ni = f["current:net_income"]
    spread = diluted - basic
    simple_diluted = ni / diluted
    bridge = (basic, diluted, spread, spread / basic,
              f["current:eps_basic"] - f["current:eps_diluted"],
              ni / basic, simple_diluted,
              f["current:eps_diluted"] - simple_diluted)
    for row, value in zip(range(5, 13), bridge):
        out[("EPS Bridge", f"B{row}")] = value
    for year, col in (("prior", "B"), ("current", "C")):
        rep = f[f"{year}:repurchases"]
        div = f[f"{year}:dividends"]
        income = f[f"{year}:net_income"]
        cash_returns = rep + div
        for row, value in zip(range(5, 11), (rep, div, cash_returns,
                                             cash_returns / income, rep / cash_returns,
                                             income - cash_returns)):
            out[("Capital Returns", f"{col}{row}")] = value
    spend = f["current:repurchases"] * fraction
    retired_m = spend / price
    modeled_shares = diluted - retired_m
    if modeled_shares <= 0:
        raise ValueError("modeled_share_count_nonpositive")
    modeled_eps = ni / modeled_shares
    modeled_lift = modeled_eps - simple_diluted
    modeled_payout = (f["current:dividends"] + spend) / ni
    for row, value in zip(range(5, 11), (spend, retired_m, modeled_shares,
                                         modeled_eps, modeled_lift, modeled_payout)):
        out[("Repurchase Scenario", f"C{row}")] = value
    review = (ni, f["current:eps_diluted"], spread,
              f["current:repurchases"] + f["current:dividends"],
              out[("Capital Returns", "C8")], modeled_eps, modeled_lift)
    for row, value in zip(range(5, 12), review):
        out[("Return Review", f"B{row}")] = value
    out[("Audit", "B5")] = out[("Capital Returns", "C5")] + out[("Capital Returns", "C6")] - out[("Capital Returns", "C7")]
    out[("Audit", "B6")] = basic + spread - diluted
    out[("Audit", "B7")] = retired_m * price - spend
    if set(out) != TARGETS:
        raise ValueError(f"eps_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
    return out


def raw_address(cells: dict[str, dict[str, Cell]], record: dict) -> tuple[str, str]:
    raw = cells["Source 10-K"]
    matches = []
    for addr in raw:
        if not addr.startswith("A") or not addr[1:].isdigit() or int(addr[1:]) < 5:
            continue
        row = addr[1:]
        actual = tuple((raw.get(f"{col}{row}") or Cell(None, None, None)).value or ""
                       for col in "ABCDEFG")
        expected = (record["id"], record["concept"], record["unit"], record["start"],
                    record["end"], record["filed"], record["accession"])
        if actual == expected:
            matches.append(("Source 10-K", f"H{row}"))
    if len(matches) != 1:
        raise ValueError(f"raw_source_lineage_ambiguous:{record['id']}:{len(matches)}")
    return matches[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    overrides, deltas = {}, {}
    for i, (key, record) in enumerate(sorted(case["canonical"].items())):
        if record["unit"] == "USD/shares":
            delta = (i + 1) * 0.013 * (1 if profile == 1 else -1)
            raw_delta = delta
        else:
            delta = (43 + 23 * i) * (1 if profile == 1 else (-1 if i % 2 else 1))
            raw_delta = delta * 1_000_000
        deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + raw_delta
    assumptions = {"price": 17.0 * profile, "fraction": 0.035 * profile}
    overrides[("Repurchase Scenario", "B5")] = case["scenario"]["synthetic_repurchase_price_usd"] + assumptions["price"]
    overrides[("Repurchase Scenario", "B6")] = case["scenario"]["synthetic_buyback_budget_fraction"] + assumptions["fraction"]
    return overrides, deltas, assumptions


def verify(candidate_path: Path, seed_path: Path, case: dict) -> dict:
    errors = []
    try:
        candidate, order, tables, structure = load_xlsx(candidate_path)
        seed, seed_order, seed_tables, seed_structure = load_xlsx(seed_path)
        if order != SHEETS or seed_order != SHEETS:
            errors.append("sheet_identity_or_order_changed")
        if tables != seed_tables or structure != seed_structure:
            errors.append("table_or_sheet_structure_changed")
        for sheet in seed_order:
            for addr in set(seed[sheet]) | set(candidate.get(sheet, {})):
                key = (sheet, addr)
                old, new = seed[sheet].get(addr), candidate.get(sheet, {}).get(addr)
                if key not in TARGETS:
                    if old is None or new is None or not unchanged_cell(old, new):
                        errors.append(f"non_target_cell_changed:{sheet}!{addr}")
                elif new is None or not new.formula:
                    errors.append(f"target_formula_missing:{sheet}!{addr}")
        for sheet, addr, value in (("Repurchase Scenario", "B5", case["scenario"]["synthetic_repurchase_price_usd"]),
                                    ("Repurchase Scenario", "B6", case["scenario"]["synthetic_buyback_budget_fraction"])):
            cell = seed[sheet][addr]
            if cell.formula or not close(float(cell.value), value):
                errors.append(f"seed_scenario_input_changed:{sheet}!{addr}")
        if errors:
            return {"pass": False, "errors": errors[:30], "checked_targets": len(TARGETS),
                    "counterfactual_profiles": 0}
        for profile in (0, 1, 2):
            overrides, deltas, assumptions = ({}, {}, {}) if profile == 0 else replay(case, candidate, profile)
            expected = expected_values(case, source_deltas=deltas, scenario_deltas=assumptions)
            calc = Evaluator(candidate, overrides)
            for sheet, addr in sorted(TARGETS):
                try:
                    actual = calc.cell(sheet, addr)
                    if not close(actual, expected[(sheet, addr)]):
                        errors.append(f"numeric_or_dependency_error_p{profile}:{sheet}!{addr}")
                    if profile == 0:
                        cache = candidate[sheet][addr].value
                        if cache is not None and not close(float(cache), actual):
                            errors.append(f"stale_formula_cache:{sheet}!{addr}")
                except Exception as exc:
                    errors.append(f"formula_error_p{profile}:{sheet}!{addr}:{type(exc).__name__}")
        return {"pass": not errors, "errors": errors[:30], "checked_targets": len(TARGETS),
                "counterfactual_profiles": 2}
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
    chosen = [c for c in cases if c["case_id"] == args.case_id]
    if len(chosen) != 1:
        raise SystemExit("case identity missing or ambiguous")
    result = verify(args.candidate, args.seed, chosen[0])
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
