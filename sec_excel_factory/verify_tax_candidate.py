"""Independent saved-OOXML oracle for tax-provision development cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Tax Review", "Filing Selection", "Provision Bridge", "Cash Taxes",
          "Deferred Assets", "Rate Stress", "Audit", "Source 10-K", "Filing Map"]
METRICS = ("pretax", "tax_expense", "current_tax", "deferred_tax", "cash_taxes", "dta")
FLOW = set(METRICS) - {"dta"}
TARGETS = {
    *(("Filing Selection", f"{col}{row}") for col in "BC" for row in range(5, 11)),
    *(("Provision Bridge", f"B{row}") for row in range(5, 13)),
    *(("Cash Taxes", f"B{row}") for row in range(5, 10)),
    *(("Deferred Assets", f"B{row}") for row in range(5, 10)),
    *(("Rate Stress", f"C{row}") for row in range(5, 11)),
    *(("Tax Review", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("tax_excerpt_hash_changed")
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
        starts = set()
        for metric in METRICS:
            key = f"{year}:{metric}"
            r = case["canonical"][key]
            if r not in source["records"]:
                raise ValueError(f"canonical_not_in_exact_excerpt:{key}")
            if (r["unit"] != "USD" or r["accession"] != case["filing_accession"]
                    or r["form"] != "10-K" or r["end"] != end):
                raise ValueError(f"wrong_original_source_or_unit:{key}")
            if metric in FLOW:
                if not 330 <= (date.fromisoformat(end) - date.fromisoformat(r["start"])).days + 1 <= 381:
                    raise ValueError(f"not_annual_flow:{key}")
                starts.add(r["start"])
            elif r["start"]:
                raise ValueError(f"stock_dta_has_duration:{key}")
            out[key] = float(r["value"]) / 1_000_000 + deltas.get(key, 0)
        if len(starts) != 1:
            raise ValueError(f"flow_start_mismatch:{year}")
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    income_change = case["scenario"]["pretax_delta_m"] + scenario_deltas.get("income_change", 0)
    rate_shift = case["scenario"]["effective_rate_shift"] + scenario_deltas.get("rate_shift", 0)
    if income_change <= 0 or not 0 <= rate_shift < 1:
        raise ValueError("scenario_out_of_range")
    out = {}
    for year, col in (("prior", "B"), ("current", "C")):
        for row, metric in zip(range(5, 11), METRICS):
            out[("Filing Selection", f"{col}{row}")] = f[f"{year}:{metric}"]
    current_tax, deferred_tax = f["current:current_tax"], f["current:deferred_tax"]
    reported = f["current:tax_expense"]
    computed = current_tax + deferred_tax
    current_rate = reported / f["current:pretax"]
    prior_rate = f["prior:tax_expense"] / f["prior:pretax"]
    bridge = (current_tax, deferred_tax, computed, reported, computed - reported,
              current_rate, prior_rate, current_rate - prior_rate)
    for row, value in zip(range(5, 13), bridge):
        out[("Provision Bridge", f"B{row}")] = value
    cash = f["current:cash_taxes"]
    for row, value in zip(range(5, 10), (cash, reported, cash - reported,
                                         cash / f["current:pretax"], cash - current_tax)):
        out[("Cash Taxes", f"B{row}")] = value
    opening_dta, closing_dta = f["prior:dta"], f["current:dta"]
    dta_change = closing_dta - opening_dta
    for row, value in zip(range(5, 10), (opening_dta, closing_dta, dta_change,
                                         closing_dta / f["current:pretax"],
                                         deferred_tax + dta_change)):
        out[("Deferred Assets", f"B{row}")] = value
    stressed_income = f["current:pretax"] + income_change
    stressed_rate = current_rate + rate_shift
    stressed_tax = stressed_income * stressed_rate
    stressed_after = stressed_income - stressed_tax
    historical_proxy = f["current:pretax"] - reported
    for row, value in zip(range(5, 11), (stressed_income, current_rate,
                                         stressed_rate, stressed_tax, stressed_after,
                                         stressed_after - historical_proxy)):
        out[("Rate Stress", f"C{row}")] = value
    for row, value in zip(range(5, 12), (f["current:pretax"], reported, current_rate,
                                          cash, dta_change, stressed_tax, stressed_after)):
        out[("Tax Review", f"B{row}")] = value
    out[("Audit", "B5")] = current_tax + deferred_tax - reported
    out[("Audit", "B6")] = computed - reported
    out[("Audit", "B7")] = stressed_tax - stressed_income * stressed_rate
    if set(out) != TARGETS:
        raise ValueError(f"tax_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
    return out


def raw_address(cells: dict[str, dict[str, Cell]], record: dict) -> tuple[str, str]:
    raw = cells["Source 10-K"]
    hits = []
    for addr in raw:
        if not addr.startswith("A") or not addr[1:].isdigit() or int(addr[1:]) < 5:
            continue
        row = addr[1:]
        actual = tuple((raw.get(f"{col}{row}") or Cell(None, None, None)).value or ""
                       for col in "ABCDEFG")
        expected = (record["id"], record["concept"], record["unit"], record["start"],
                    record["end"], record["filed"], record["accession"])
        if actual == expected:
            hits.append(("Source 10-K", f"H{row}"))
    if len(hits) != 1:
        raise ValueError(f"raw_lineage_ambiguity:{record['id']}:{len(hits)}")
    return hits[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    overrides, deltas = {}, {}
    for i, (key, record) in enumerate(sorted(case["canonical"].items())):
        delta = (31 + i * 19) * (1 if profile == 1 else (-1 if i % 2 else 1))
        deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    assumptions = {"income_change": 220.0 * profile, "rate_shift": 0.007 * profile}
    overrides[("Rate Stress", "B5")] = case["scenario"]["pretax_delta_m"] + assumptions["income_change"]
    overrides[("Rate Stress", "B6")] = case["scenario"]["effective_rate_shift"] + assumptions["rate_shift"]
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
        for sheet, addr, value in (("Rate Stress", "B5", case["scenario"]["pretax_delta_m"]),
                                    ("Rate Stress", "B6", case["scenario"]["effective_rate_shift"])):
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
