"""Independent saved-OOXML oracle for public cash/debt capacity cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Debt Review", "Filing Selection", "Debt Mix", "Cash Capacity",
          "Refinance Stress", "Audit", "Source 10-K", "Filing Map"]
TARGETS = {
    *(("Filing Selection", f"B{row}") for row in range(5, 12)),
    *(("Debt Mix", f"B{row}") for row in range(5, 9)),
    *(("Cash Capacity", f"B{row}") for row in range(5, 10)),
    *(("Refinance Stress", f"C{row}") for row in range(5, 12)),
    *(("Debt Review", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}
METRICS = ("current_long_term_debt", "noncurrent_long_term_debt", "cash",
           "operating_cash_flow", "capital_expenditures", "current_liabilities",
           "current_assets")


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("source_excerpt_hash_changed")
    data = json.loads(raw)
    if data["cik"] != case["cik"] or data["filing_accession"] != case["filing_accession"]:
        raise ValueError("source_filing_identity_changed")
    if data["source_raw_json_sha256"] != case["source_raw_json_sha256"]:
        raise ValueError("source_raw_hash_changed")
    earlier = json.loads((ROOT / "sec_excel_factory/candidate_audit_fetched_2026-09-24.json").read_text())
    prior = next(row for row in earlier["results"] if row["ticker"] == case["ticker"])
    if prior["sha256_raw_json"] != case["source_raw_json_sha256"]:
        raise ValueError("prior_direct_sec_hash_not_matching")
    out = {}
    for key in METRICS:
        record = case["canonical"][key]
        if record not in data["records"]:
            raise ValueError(f"canonical_not_in_pinned_excerpt:{key}")
        if (record["accession"] != case["filing_accession"] or record["end"] != case["annual_end"]
                or record["form"] != "10-K"):
            raise ValueError(f"wrong_original_filing:{key}")
        if key in {"operating_cash_flow", "capital_expenditures"}:
            if record["start"] != case["annual_start"]:
                raise ValueError(f"wrong_flow_duration:{key}")
        elif record["start"]:
            raise ValueError(f"stock_fact_has_duration:{key}")
        out[key] = float(record["value"]) / 1_000_000 + deltas.get(key, 0)
    days = (date.fromisoformat(case["annual_end"]) - date.fromisoformat(case["annual_start"])).days + 1
    if not 330 <= days <= 381:
        raise ValueError("not_annual_period")
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    share = case["scenario"]["refinance_share"] + scenario_deltas.get("refinance_share", 0)
    rate = case["scenario"]["incremental_interest_rate"] + scenario_deltas.get("incremental_interest_rate", 0)
    if not 0 < share < 1 or not 0 < rate < 1:
        raise ValueError("scenario_out_of_range")
    out = {}
    for row, key in zip(range(5, 12), METRICS):
        out[("Filing Selection", f"B{row}")] = f[key]
    tracked = f["current_long_term_debt"] + f["noncurrent_long_term_debt"]
    mix = (tracked, f["current_long_term_debt"] / tracked,
           tracked - f["cash"], f["cash"] / tracked)
    for row, value in zip(range(5, 9), mix):
        out[("Debt Mix", f"B{row}")] = value
    fcf = f["operating_cash_flow"] - f["capital_expenditures"]
    available = f["cash"] + fcf
    capacity = (fcf, fcf / f["current_long_term_debt"], available,
                available / f["current_long_term_debt"],
                f["current_assets"] - f["current_liabilities"])
    for row, value in zip(range(5, 10), capacity):
        out[("Cash Capacity", f"B{row}")] = value
    maturing = f["current_long_term_debt"]
    refinanced = maturing * share
    due = maturing - refinanced
    interest = refinanced * rate
    post_interest_fcf = fcf - interest
    end_cash = f["cash"] + post_interest_fcf - due
    coverage = (f["cash"] + post_interest_fcf) / due
    for row, value in zip(range(5, 12), (maturing, refinanced, due, interest,
                                         post_interest_fcf, end_cash, coverage)):
        out[("Refinance Stress", f"C{row}")] = value
    review = (maturing, tracked, fcf, end_cash, coverage,
              f["current_assets"] / f["current_liabilities"], tracked - f["cash"])
    for row, value in zip(range(5, 12), review):
        out[("Debt Review", f"B{row}")] = value
    out[("Audit", "B5")] = tracked - maturing - f["noncurrent_long_term_debt"]
    out[("Audit", "B6")] = fcf - f["operating_cash_flow"] + f["capital_expenditures"]
    out[("Audit", "B7")] = refinanced + due - maturing
    if set(out) != TARGETS:
        raise ValueError(f"debt_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
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
        expected = (record["id"], record["concept"], record["start"], record["end"],
                    record["filed"], record["form"], record["accession"])
        if actual == expected:
            matches.append(("Source 10-K", f"H{row}"))
    if len(matches) != 1:
        raise ValueError(f"raw_source_lineage_ambiguous:{record['id']}:{len(matches)}")
    return matches[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    overrides, source_deltas = {}, {}
    for i, key in enumerate(METRICS):
        record = case["canonical"][key]
        delta = (37 + i * 19) * (1 if profile == 1 else (-1 if i % 2 else 1))
        source_deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    assumptions = {"refinance_share": 0.05 * profile,
                   "incremental_interest_rate": 0.003 * profile}
    overrides[("Refinance Stress", "B5")] = case["scenario"]["refinance_share"] + assumptions["refinance_share"]
    overrides[("Refinance Stress", "B6")] = case["scenario"]["incremental_interest_rate"] + assumptions["incremental_interest_rate"]
    return overrides, source_deltas, assumptions


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
        for sheet, addr, value in (("Refinance Stress", "B5", case["scenario"]["refinance_share"]),
                                    ("Refinance Stress", "B6", case["scenario"]["incremental_interest_rate"])):
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
