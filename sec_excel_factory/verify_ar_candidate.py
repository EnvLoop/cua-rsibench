"""Independent saved-OOXML oracle for receivables/allowance development cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Collection Review", "Filing Selection", "Reserve Bridge", "DSO Trend",
          "Cash Conversion", "Credit Stress", "Audit", "Source 10-K", "Filing Map"]
METRICS = ("net_ar", "allowance", "revenue", "ocf", "current_assets")
FLOW = {"revenue", "ocf"}
TARGETS = {
    *(("Filing Selection", f"{col}{row}") for col in "BC" for row in range(5, 10)),
    *(("Reserve Bridge", f"{col}{row}") for col in "BC" for row in range(5, 10)),
    *(("DSO Trend", f"B{row}") for row in range(5, 11)),
    *(("Cash Conversion", f"B{row}") for row in range(5, 11)),
    *(("Credit Stress", f"C{row}") for row in range(5, 12)),
    *(("Collection Review", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}


def facts(case: dict, deltas: dict[str, float]) -> tuple[dict[str, float], int, int]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("ar_excerpt_hash_changed")
    source = json.loads(raw)
    if (source["cik"] != case["cik"] or source["filing_accession"] != case["filing_accession"]
            or source["revenue_concept"] != case["revenue_concept"]):
        raise ValueError("source_filing_identity_changed")
    if source["source_raw_json_sha256"] != case["source_raw_json_sha256"]:
        raise ValueError("source_raw_hash_changed")
    earlier = json.loads((ROOT / "sec_excel_factory/candidate_audit_fetched_2026-09-24.json").read_text())
    prior = next(r for r in earlier["results"] if r["ticker"] == case["ticker"])
    if prior["sha256_raw_json"] != case["source_raw_json_sha256"]:
        raise ValueError("prior_direct_sec_hash_not_matching")
    out = {}
    days = {}
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
                raise ValueError(f"wrong_original_source:{key}")
            if metric in FLOW:
                if not 330 <= (date.fromisoformat(end) - date.fromisoformat(r["start"])).days + 1 <= 381:
                    raise ValueError(f"not_annual_flow:{key}")
                starts.add(r["start"])
            elif r["start"]:
                raise ValueError(f"stock_fact_has_duration:{key}")
            out[key] = float(r["value"]) / 1_000_000 + deltas.get(key, 0)
        if len(starts) != 1:
            raise ValueError(f"flow_start_mismatch:{year}")
        days[year] = (date.fromisoformat(end) - date.fromisoformat(next(iter(starts)))).days + 1
    if (days["prior"] != case["prior_fiscal_days"]
            or days["current"] != case["current_fiscal_days"]):
        raise ValueError("fiscal_days_case_not_source_derived")
    return out, days["prior"], days["current"]


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f, prior_days, current_days = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    reserve_rate = case["scenario"]["incremental_reserve_rate"] + scenario_deltas.get("reserve_rate", 0)
    cash_fraction = case["scenario"]["modeled_cash_realization_fraction"] + scenario_deltas.get("cash_fraction", 0)
    if not 0 < reserve_rate < 1 or not 0 < cash_fraction < 1:
        raise ValueError("scenario_out_of_range")
    out = {}
    for year, col in (("prior", "B"), ("current", "C")):
        for row, metric in zip(range(5, 10), METRICS):
            out[("Filing Selection", f"{col}{row}")] = f[f"{year}:{metric}"]
        net, allowance = f[f"{year}:net_ar"], f[f"{year}:allowance"]
        gross = net + allowance
        for row, value in zip(range(5, 10), (net, allowance, gross,
                                             allowance / gross,
                                             net / f[f"{year}:current_assets"])):
            out[("Reserve Bridge", f"{col}{row}")] = value
    avg_net = (f["prior:net_ar"] + f["current:net_ar"]) / 2
    dso = avg_net / f["current:revenue"] * current_days
    for row, value in zip(range(5, 11), (prior_days, current_days, avg_net, dso,
                                         f["current:revenue"] / f["prior:revenue"] - 1,
                                         f["current:net_ar"] / f["prior:net_ar"] - 1)):
        out[("DSO Trend", f"B{row}")] = value
    ar_change = f["current:net_ar"] - f["prior:net_ar"]
    for row, value in zip(range(5, 11), (f["current:ocf"] / f["current:revenue"],
                                         f["current:net_ar"] / f["current:revenue"],
                                         f["current:ocf"] / f["current:net_ar"],
                                         f["current:ocf"] / f["prior:ocf"] - 1,
                                         ar_change, f["current:ocf"] - ar_change)):
        out[("Cash Conversion", f"B{row}")] = value
    gross = f["current:net_ar"] + f["current:allowance"]
    extra = gross * reserve_rate
    modeled_net = f["current:net_ar"] - extra
    modeled_current_assets = f["current:current_assets"] - extra
    cash_shortfall = extra * cash_fraction
    for row, value in zip(range(5, 12), (extra, cash_shortfall, modeled_net,
                                         (f["current:allowance"] + extra) / gross,
                                         gross, modeled_current_assets,
                                         modeled_net / modeled_current_assets)):
        out[("Credit Stress", f"C{row}")] = value
    for row, value in zip(range(5, 12), (f["current:net_ar"], gross,
                                          f["current:allowance"] / gross, dso,
                                          f["current:ocf"] / f["current:revenue"],
                                          modeled_net, cash_shortfall)):
        out[("Collection Review", f"B{row}")] = value
    out[("Audit", "B5")] = gross - f["current:net_ar"] - f["current:allowance"]
    out[("Audit", "B6")] = modeled_net + f["current:allowance"] + extra - gross
    out[("Audit", "B7")] = dso - avg_net / f["current:revenue"] * current_days
    if set(out) != TARGETS:
        raise ValueError(f"ar_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
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
        delta = (29 + 17 * i) * (1 if profile == 1 else (-1 if i % 2 else 1))
        deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    assumptions = {"reserve_rate": 0.005 * profile,
                   "cash_fraction": 0.05 * profile}
    overrides[("Credit Stress", "B5")] = case["scenario"]["incremental_reserve_rate"] + assumptions["reserve_rate"]
    overrides[("Credit Stress", "B6")] = case["scenario"]["modeled_cash_realization_fraction"] + assumptions["cash_fraction"]
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
        for sheet, addr, value in (("Credit Stress", "B5", case["scenario"]["incremental_reserve_rate"]),
                                    ("Credit Stress", "B6", case["scenario"]["modeled_cash_realization_fraction"])):
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
