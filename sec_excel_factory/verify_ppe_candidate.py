"""Independent saved-OOXML oracle for PPE carrying-value cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["PPE Review", "Filing Selection", "Gross-to-Net", "Asset Movement",
          "Capital Intensity", "Asset Stress", "Audit", "Source 10-K", "Filing Map"]
METRICS = ("gross_ppe", "accumulated_depreciation", "net_ppe", "assets",
           "capex", "depreciation_amortization")
STOCK = set(METRICS[:4])
TARGETS = {
    *(("Filing Selection", f"{col}{row}") for col in "BC" for row in range(5, 11)),
    *(("Gross-to-Net", f"B{row}") for row in range(5, 13)),
    *(("Asset Movement", f"B{row}") for row in range(5, 16)),
    *(("Capital Intensity", f"B{row}") for row in range(5, 11)),
    *(("Asset Stress", f"C{row}") for row in range(5, 11)),
    *(("PPE Review", f"B{row}") for row in range(5, 13)),
    *(("Audit", f"B{row}") for row in range(5, 9)),
}


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float]:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("ppe_excerpt_hash_changed")
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
                raise ValueError(f"wrong_original_source:{key}")
            if metric in STOCK and r["start"]:
                raise ValueError(f"stock_fact_has_duration:{key}")
            if metric not in STOCK:
                if not r["start"] or not 330 <= (date.fromisoformat(end)
                        - date.fromisoformat(r["start"])).days + 1 <= 381:
                    raise ValueError(f"not_annual_flow:{key}")
                starts.add(r["start"])
            out[key] = float(r["value"]) / 1_000_000 + deltas.get(key, 0)
        if len(starts) != 1:
            raise ValueError(f"flow_start_mismatch:{year}")
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    write_down = case["scenario"]["modeled_write_down_fraction"] + scenario_deltas.get("write_down", 0)
    capex_up = case["scenario"]["maintenance_capex_increase_fraction"] + scenario_deltas.get("capex_up", 0)
    if not 0 <= write_down < 0.5 or not 0 <= capex_up < 1:
        raise ValueError("scenario_out_of_range")
    out = {}
    for year, col in (("prior", "B"), ("current", "C")):
        for row, metric in zip(range(5, 11), METRICS):
            out[("Filing Selection", f"{col}{row}")] = f[f"{year}:{metric}"]
    gross, accum, net, assets = (f[f"current:{k}"] for k in METRICS[:4])
    capex, da = f["current:capex"], f["current:depreciation_amortization"]
    computed_net = gross - accum
    gross_net_residual = computed_net - net
    if gross == 0 or net == 0 or assets == 0 or da == 0 or capex == 0:
        raise ValueError("zero_denominator_for_ppe_ratios")
    for row, value in zip(range(5, 13), (gross, accum, computed_net, net,
                                         gross_net_residual, accum / gross,
                                         net / gross, net / assets)):
        out[("Gross-to-Net", f"B{row}")] = value
    prior_gross, prior_accum, prior_net = (f[f"prior:{k}"] for k in METRICS[:3])
    gross_change, accum_change = gross - prior_gross, accum - prior_accum
    net_change = net - prior_net
    capex_less_da = capex - da
    movement_residual = net_change - capex_less_da
    for row, value in zip(range(5, 16), (prior_gross, gross, gross_change,
                                         prior_accum, accum, accum_change,
                                         prior_net, net, net_change,
                                         capex_less_da, movement_residual)):
        out[("Asset Movement", f"B{row}")] = value
    for row, value in zip(range(5, 11), (capex, da, capex / da, capex / net,
                                         da / net, net / assets)):
        out[("Capital Intensity", f"B{row}")] = value
    modeled_write_down = net * write_down
    modeled_capex = capex * (1 + capex_up)
    modeled_net, modeled_assets = net - modeled_write_down, assets - modeled_write_down
    if modeled_assets <= 0:
        raise ValueError("modeled_assets_nonpositive")
    modeled_ppe_ratio = modeled_net / modeled_assets
    modeled_capex_da = modeled_capex / da
    for row, value in zip(range(5, 11), (modeled_write_down, modeled_capex,
                                         modeled_net, modeled_assets,
                                         modeled_ppe_ratio, modeled_capex_da)):
        out[("Asset Stress", f"C{row}")] = value
    for row, value in zip(range(5, 13), (net, gross_net_residual, accum / gross,
                                         net_change, movement_residual, capex / da,
                                         modeled_ppe_ratio, modeled_capex_da)):
        out[("PPE Review", f"B{row}")] = value
    out[("Audit", "B5")] = gross_net_residual
    out[("Audit", "B6")] = gross - prior_gross - gross_change
    out[("Audit", "B7")] = net - prior_net - net_change
    out[("Audit", "B8")] = modeled_net + modeled_write_down - net
    if set(out) != TARGETS:
        raise ValueError(f"ppe_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
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
        raise ValueError(f"raw_lineage_ambiguous:{record['id']}:{len(matches)}")
    return matches[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    overrides, deltas = {}, {}
    for i, (key, record) in enumerate(sorted(case["canonical"].items())):
        delta = (17 + 11 * i) * (1 if profile == 1 else (-1 if i % 2 else 1))
        deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    assumptions = {"write_down": 0.012 * profile, "capex_up": 0.025 * profile}
    overrides[("Asset Stress", "B5")] = case["scenario"]["modeled_write_down_fraction"] + assumptions["write_down"]
    overrides[("Asset Stress", "B6")] = case["scenario"]["maintenance_capex_increase_fraction"] + assumptions["capex_up"]
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
        for sheet, addr, value in (("Asset Stress", "B5", case["scenario"]["modeled_write_down_fraction"]),
                                   ("Asset Stress", "B6", case["scenario"]["maintenance_capex_increase_fraction"])):
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
