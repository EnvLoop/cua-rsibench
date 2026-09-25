"""Independent saved-OOXML oracle for operating-lease maturity cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Lease Review", "Filing Selection", "Maturity Ladder", "Liability Bridge",
          "Cash Burden", "Occupancy Stress", "Audit", "Source 10-K", "Filing Map"]
METRICS = ("current_liability", "noncurrent_liability", "rou_asset", "lease_cost",
           "lease_payments", "discount_rate", "operating_cash_flow", "due_next12",
           "due_year2", "due_year3", "due_year4", "due_year5", "due_after5", "due_total")
FLOW = {"lease_cost", "lease_payments", "operating_cash_flow"}
TARGETS = {
    *(("Filing Selection", f"B{row}") for row in range(5, 19)),
    *(("Maturity Ladder", f"B{row}") for row in range(5, 15)),
    *(("Liability Bridge", f"B{row}") for row in range(5, 12)),
    *(("Cash Burden", f"B{row}") for row in range(5, 11)),
    *(("Occupancy Stress", f"C{row}") for row in range(5, 10)),
    *(("Lease Review", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("lease_excerpt_hash_changed")
    source = json.loads(raw)
    if source["cik"] != case["cik"] or source["filing_accession"] != case["filing_accession"]:
        raise ValueError("source_filing_identity_changed")
    if source["source_raw_json_sha256"] != case["source_raw_json_sha256"]:
        raise ValueError("source_raw_hash_changed")
    earlier = json.loads((ROOT / "sec_excel_factory/candidate_audit_fetched_2026-09-24.json").read_text())
    prior = next(row for row in earlier["results"] if row["ticker"] == case["ticker"])
    if prior["sha256_raw_json"] != case["source_raw_json_sha256"]:
        raise ValueError("prior_direct_sec_hash_not_matching")
    out = {}
    for metric in METRICS:
        record = case["canonical"][metric]
        if record not in source["records"]:
            raise ValueError(f"canonical_not_in_exact_excerpt:{metric}")
        if (record["accession"] != case["filing_accession"] or record["form"] != "10-K"
                or record["end"] != case["annual_end"]):
            raise ValueError(f"wrong_original_filing:{metric}")
        if metric in FLOW:
            if record["start"] != case["annual_start"]:
                raise ValueError(f"wrong_annual_duration:{metric}")
        elif record["start"]:
            raise ValueError(f"instant_disclosure_has_start:{metric}")
        if metric == "discount_rate":
            if record["unit"] != "pure":
                raise ValueError("discount_rate_unit_not_pure")
            out[metric] = float(record["value"]) + deltas.get(metric, 0)
        else:
            if record["unit"] != "USD":
                raise ValueError(f"financial_unit_not_usd:{metric}")
            out[metric] = float(record["value"]) / 1_000_000 + deltas.get(metric, 0)
    days = (date.fromisoformat(case["annual_end"]) - date.fromisoformat(case["annual_start"])).days + 1
    if not 330 <= days <= 381:
        raise ValueError("not_annual_flow_period")
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    reduction = case["scenario"]["next12_payment_reduction"] + scenario_deltas.get("reduction", 0)
    escalation = case["scenario"]["next12_escalation"] + scenario_deltas.get("escalation", 0)
    if not 0 <= reduction < 1 or not 0 <= escalation < 1:
        raise ValueError("scenario_out_of_range")
    out = {}
    for row, metric in zip(range(5, 19), METRICS):
        out[("Filing Selection", f"B{row}")] = f[metric]
    due = [f[k] for k in ("due_next12", "due_year2", "due_year3", "due_year4",
                          "due_year5", "due_after5")]
    for row, value in zip(range(5, 11), due):
        out[("Maturity Ladder", f"B{row}")] = value
    first5, six = sum(due[:5]), sum(due)
    for row, value in zip(range(11, 15), (first5, six, f["due_total"], six - f["due_total"])):
        out[("Maturity Ladder", f"B{row}")] = value
    liability = f["current_liability"] + f["noncurrent_liability"]
    gap = f["due_total"] - liability
    for row, value in zip(range(5, 12), (f["current_liability"], f["noncurrent_liability"],
                                          liability, f["due_total"], gap,
                                          f["rou_asset"] / liability, f["discount_rate"])):
        out[("Liability Bridge", f"B{row}")] = value
    next12 = f["due_next12"]
    for row, value in zip(range(5, 11), (next12, f["lease_payments"],
                                          next12 - f["lease_payments"],
                                          next12 / f["operating_cash_flow"],
                                          f["current_liability"] / next12,
                                          f["lease_cost"] / f["lease_payments"])):
        out[("Cash Burden", f"B{row}")] = value
    modeled_next = next12 * (1 - reduction) * (1 + escalation)
    modeled_three = sum(due[:3]) * (1 - reduction) * (1 + escalation)
    savings = next12 - modeled_next
    for row, value in zip(range(5, 10), (modeled_next, modeled_three, savings,
                                         modeled_next / f["operating_cash_flow"],
                                         modeled_next / f["lease_payments"])):
        out[("Occupancy Stress", f"C{row}")] = value
    review = (f["due_total"], liability, gap, next12, f["discount_rate"],
              modeled_next, modeled_next / f["operating_cash_flow"])
    for row, value in zip(range(5, 12), review):
        out[("Lease Review", f"B{row}")] = value
    out[("Audit", "B5")] = six - f["due_total"]
    out[("Audit", "B6")] = f["current_liability"] + f["noncurrent_liability"] - liability
    out[("Audit", "B7")] = modeled_next + savings - next12
    if set(out) != TARGETS:
        raise ValueError(f"lease_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
    return out


def raw_address(cells: dict[str, dict[str, Cell]], record: dict) -> tuple[str, str]:
    raw = cells["Source 10-K"]
    found = []
    for addr in raw:
        if not addr.startswith("A") or not addr[1:].isdigit() or int(addr[1:]) < 5:
            continue
        row = addr[1:]
        actual = tuple((raw.get(f"{col}{row}") or Cell(None, None, None)).value or ""
                       for col in "ABCDEFG")
        wanted = (record["id"], record["concept"], record["unit"], record["start"],
                  record["end"], record["filed"], record["accession"])
        if actual == wanted:
            found.append(("Source 10-K", f"H{row}"))
    if len(found) != 1:
        raise ValueError(f"raw_source_lineage_ambiguous:{record['id']}:{len(found)}")
    return found[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    overrides, deltas = {}, {}
    for i, metric in enumerate(METRICS):
        record = case["canonical"][metric]
        if metric == "discount_rate":
            delta = 0.007 * profile
            raw_delta = delta
        else:
            delta = (19 + i * 13) * (1 if profile == 1 else (-1 if i % 2 else 1))
            raw_delta = delta * 1_000_000
        deltas[metric] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + raw_delta
    assumptions = {"reduction": 0.025 * profile, "escalation": 0.013 * profile}
    overrides[("Occupancy Stress", "B5")] = case["scenario"]["next12_payment_reduction"] + assumptions["reduction"]
    overrides[("Occupancy Stress", "B6")] = case["scenario"]["next12_escalation"] + assumptions["escalation"]
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
        for sheet, addr, value in (("Occupancy Stress", "B5", case["scenario"]["next12_payment_reduction"]),
                                    ("Occupancy Stress", "B6", case["scenario"]["next12_escalation"])):
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
