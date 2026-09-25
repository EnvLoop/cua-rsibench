"""Independent saved-OOXML oracle for goodwill/intangible development cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Asset Review", "Filing Selection", "Goodwill Movement", "Intangible Carrying",
          "Earnings Burden", "WriteDown Stress", "Audit", "Source 10-K", "Filing Map"]
STOCK = ("goodwill", "intangibles", "assets")
FLOW = ("acquired_goodwill", "amortization", "net_income")
TARGETS = {
    *(("Filing Selection", f"{col}{row}") for col in "BC" for row in range(5, 8)),
    *(("Filing Selection", f"C{row}") for row in range(8, 11)),
    *(("Goodwill Movement", f"B{row}") for row in range(5, 12)),
    *(("Intangible Carrying", f"B{row}") for row in range(5, 13)),
    *(("Earnings Burden", f"B{row}") for row in range(5, 10)),
    *(("WriteDown Stress", f"C{row}") for row in range(5, 11)),
    *(("Asset Review", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("goodwill_excerpt_hash_changed")
    source = json.loads(raw)
    if source["cik"] != case["cik"] or source["filing_accession"] != case["filing_accession"]:
        raise ValueError("source_filing_identity_changed")
    if source["source_raw_json_sha256"] != case["source_raw_json_sha256"]:
        raise ValueError("source_raw_hash_changed")
    earlier = json.loads((ROOT / "sec_excel_factory/candidate_audit_fetched_2026-09-24.json").read_text())
    prior = next(r for r in earlier["results"] if r["ticker"] == case["ticker"])
    if prior["sha256_raw_json"] != case["source_raw_json_sha256"]:
        raise ValueError("prior_direct_sec_hash_not_matching")
    out = {}
    for year in ("prior", "current"):
        end = case["prior_end"] if year == "prior" else case["annual_end"]
        for metric in STOCK:
            key = f"{year}:{metric}"
            r = case["canonical"][key]
            if r not in source["records"] or r["start"]:
                raise ValueError(f"stock_fact_invalid:{key}")
            if r["accession"] != case["filing_accession"] or r["form"] != "10-K" or r["end"] != end:
                raise ValueError(f"wrong_source_lineage:{key}")
            out[key] = float(r["value"]) / 1_000_000 + deltas.get(key, 0)
    starts = set()
    for metric in FLOW:
        r = case["canonical"][metric]
        if r not in source["records"] or not r["start"]:
            raise ValueError(f"flow_fact_invalid:{metric}")
        if r["accession"] != case["filing_accession"] or r["form"] != "10-K" or r["end"] != case["annual_end"]:
            raise ValueError(f"wrong_annual_flow_source:{metric}")
        starts.add(r["start"])
        out[metric] = float(r["value"]) / 1_000_000 + deltas.get(metric, 0)
    if starts != {case["annual_start"]}:
        raise ValueError("annual_flow_start_mismatch")
    days = (date.fromisoformat(case["annual_end"]) - date.fromisoformat(case["annual_start"])).days + 1
    if not 330 <= days <= 381:
        raise ValueError("not_annual_period")
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    impairment = case["scenario"]["goodwill_write_down_fraction"] + scenario_deltas.get("impairment", 0)
    extra_amort = case["scenario"]["incremental_amortization_m"] + scenario_deltas.get("extra_amort", 0)
    if not 0 <= impairment < 1 or extra_amort < 0:
        raise ValueError("scenario_out_of_range")
    out = {}
    for year, col in (("prior", "B"), ("current", "C")):
        for row, metric in zip(range(5, 8), STOCK):
            out[("Filing Selection", f"{col}{row}")] = f[f"{year}:{metric}"]
    for row, metric in zip(range(8, 11), FLOW):
        out[("Filing Selection", f"C{row}")] = f[metric]
    opening, closing, acquired = f["prior:goodwill"], f["current:goodwill"], f["acquired_goodwill"]
    movement = closing - opening
    goodwill_residual = movement - acquired
    for row, value in zip(range(5, 12), (opening, acquired, closing, movement,
                                         goodwill_residual, goodwill_residual / closing,
                                         closing / f["current:assets"])):
        out[("Goodwill Movement", f"B{row}")] = value
    int_open, int_close = f["prior:intangibles"], f["current:intangibles"]
    int_change = int_close - int_open
    combined_current = (closing + int_close) / f["current:assets"]
    combined_prior = (opening + int_open) / f["prior:assets"]
    for row, value in zip(range(5, 13), (int_open, int_close, int_change,
                                         f["amortization"], int_change + f["amortization"],
                                         combined_current, combined_prior,
                                         combined_current - combined_prior)):
        out[("Intangible Carrying", f"B{row}")] = value
    for row, value in zip(range(5, 10), (f["net_income"], f["amortization"],
                                         f["net_income"] / f["amortization"],
                                         f["amortization"] / int_close,
                                         f["amortization"] / f["current:assets"])):
        out[("Earnings Burden", f"B{row}")] = value
    write_down = closing * impairment
    goodwill_after = closing - write_down
    intangible_after = int_close - extra_amort
    assets_after = f["current:assets"] - write_down - extra_amort
    income_after = f["net_income"] - write_down - extra_amort
    for row, value in zip(range(5, 11), (write_down, intangible_after, goodwill_after,
                                         assets_after, income_after,
                                         (goodwill_after + intangible_after) / assets_after)):
        out[("WriteDown Stress", f"C{row}")] = value
    for row, value in zip(range(5, 12), (closing, acquired, goodwill_residual,
                                         combined_current, f["amortization"] / int_close,
                                         assets_after, income_after)):
        out[("Asset Review", f"B{row}")] = value
    out[("Audit", "B5")] = movement - acquired - goodwill_residual
    out[("Audit", "B6")] = closing + int_close - combined_current * f["current:assets"]
    out[("Audit", "B7")] = goodwill_after + intangible_after - ((goodwill_after + intangible_after) / assets_after) * assets_after
    if set(out) != TARGETS:
        raise ValueError(f"goodwill_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
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
        wanted = (record["id"], record["concept"], record["unit"], record["start"],
                  record["end"], record["filed"], record["accession"])
        if actual == wanted:
            matches.append(("Source 10-K", f"H{row}"))
    if len(matches) != 1:
        raise ValueError(f"raw_lineage_ambiguous:{record['id']}:{len(matches)}")
    return matches[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    overrides, deltas = {}, {}
    for i, (key, record) in enumerate(sorted(case["canonical"].items())):
        delta = (37 + 17 * i) * (1 if profile == 1 else (-1 if i % 2 else 1))
        deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    assumptions = {"impairment": 0.025 * profile, "extra_amort": 45.0 * profile}
    overrides[("WriteDown Stress", "B5")] = case["scenario"]["goodwill_write_down_fraction"] + assumptions["impairment"]
    overrides[("WriteDown Stress", "B6")] = case["scenario"]["incremental_amortization_m"] + assumptions["extra_amort"]
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
        for sheet, addr, value in (("WriteDown Stress", "B5", case["scenario"]["goodwill_write_down_fraction"]),
                                    ("WriteDown Stress", "B6", case["scenario"]["incremental_amortization_m"])):
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
