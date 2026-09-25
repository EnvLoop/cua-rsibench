"""Independent saved-state OOXML oracle for public RPO development cases."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from verify_ooxml import Cell, Evaluator, close, load_xlsx, unchanged_cell


ROOT = Path(__file__).resolve().parent.parent
SHEETS = ["Executive", "Filing Selection", "Liability Rollforward", "RPO Scenario",
          "Liquidity Review", "Audit", "Source 10-K", "Filing Map"]
TARGETS = {
    *(("Filing Selection", f"B{row}") for row in range(5, 18)),
    *(("Liability Rollforward", f"B{row}") for row in range(5, 14)),
    *(("RPO Scenario", f"C{row}") for row in range(5, 11)),
    *(("Liquidity Review", f"B{row}") for row in range(5, 10)),
    *(("Executive", f"B{row}") for row in range(5, 12)),
    *(("Audit", f"B{row}") for row in range(5, 8)),
}


def source(case: dict) -> dict:
    path = ROOT / case["source_excerpt_path"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != case["source_excerpt_sha256"]:
        raise ValueError("source_excerpt_hash_changed")
    parsed = json.loads(raw)
    if parsed["cik"] != case["cik"] or parsed["filing_accession"] != case["filing_accession"]:
        raise ValueError("source_cik_or_accession_changed")
    if parsed["source_raw_json_sha256"] != case["source_raw_json_sha256"]:
        raise ValueError("source_raw_pin_changed")
    for key, record in case["canonical"].items():
        if record is not None and record not in parsed["records"]:
            raise ValueError(f"canonical_not_in_exact_pinned_excerpt:{key}")
    return parsed


def facts(case: dict, deltas: dict[str, float]) -> dict[str, float | None]:
    source(case)
    out = {}
    for key, record in case["canonical"].items():
        if record is not None:
            if record["accession"] != case["filing_accession"] or record["form"] != "10-K":
                raise ValueError(f"wrong_source_lineage:{key}")
            out[key] = float(record["value"]) / 1_000_000 + deltas.get(key, 0)
        else:
            out[key] = None
    for prefix in ("", "prior_"):
        total = out[prefix + "total"]
        current = out[prefix + "current"]
        noncurrent = out[prefix + "noncurrent"]
        if current is None or (total is None and noncurrent is None):
            raise ValueError(f"classification_source_insufficient:{prefix}")
        if total is None:
            total = current + noncurrent
        if noncurrent is None:
            noncurrent = total - current
        out[prefix + "total"] = total
        out[prefix + "noncurrent"] = noncurrent
    return out


def expected_values(case: dict, *, source_deltas: dict[str, float] | None = None,
                    scenario_deltas: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    f = facts(case, source_deltas or {})
    scenario_deltas = scenario_deltas or {}
    haircut = case["scenario"]["rpo_haircut"] + scenario_deltas.get("rpo_haircut", 0)
    next_share = case["scenario"]["next12_recognition_share"] + scenario_deltas.get("next12_recognition_share", 0)
    out = {}
    selection = (f["revenue"], f["revenue_prior"], f["prior_total"],
                 f["prior_current"], f["prior_noncurrent"], f["total"],
                 f["current"], f["noncurrent"], f["rpo"], f["recognized"],
                 f["assets_current"], f["liabilities_current"], f["cash"])
    for row, value in zip(range(5, 18), selection):
        out[("Filing Selection", f"B{row}")] = value
    opening, recognized, closing = f["prior_total"], f["recognized"], f["total"]
    net_change = closing - opening
    residual = net_change + recognized
    opening_recognized_share = recognized / opening
    closing_current_share = f["current"] / closing
    opening_current_share = f["prior_current"] / opening
    for row, value in zip(range(5, 14), (opening, recognized, closing, net_change, residual,
                                         opening_recognized_share, closing_current_share,
                                         opening_current_share,
                                         closing_current_share - opening_current_share)):
        out[("Liability Rollforward", f"B{row}")] = value
    modeled_rpo = f["rpo"] * (1 - haircut)
    modeled_next12 = modeled_rpo * next_share
    for row, value in zip(range(5, 11), (modeled_rpo, modeled_next12, modeled_rpo - modeled_next12,
                                         f["rpo"] / f["revenue"], modeled_next12 / f["revenue"],
                                         closing / f["rpo"])):
        out[("RPO Scenario", f"C{row}")] = value
    current_ratio = f["assets_current"] / f["liabilities_current"]
    for row, value in zip(range(5, 10), (current_ratio, f["cash"] / f["liabilities_current"],
                                         f["liabilities_current"] - f["cash"],
                                         f["current"] / f["liabilities_current"],
                                         f["cash"] / f["current"])):
        out[("Liquidity Review", f"B{row}")] = value
    for row, value in zip(range(5, 12), (f["revenue"], f["rpo"], opening_recognized_share,
                                          closing_current_share - opening_current_share,
                                          modeled_next12, current_ratio, residual)):
        out[("Executive", f"B{row}")] = value
    out[("Audit", "B5")] = closing - f["current"] - f["noncurrent"]
    out[("Audit", "B6")] = opening - f["prior_current"] - f["prior_noncurrent"]
    out[("Audit", "B7")] = modeled_next12 + (modeled_rpo - modeled_next12) - modeled_rpo
    if set(out) != TARGETS:
        raise ValueError(f"rpo_oracle_target_coverage:{len(out)}:{len(TARGETS)}")
    return out


def raw_address(cells: dict[str, dict[str, Cell]], record: dict) -> tuple[str, str]:
    raw = cells["Source 10-K"]
    hits = []
    for addr, cell in raw.items():
        if not addr.startswith("A") or not addr[1:].isdigit() or int(addr[1:]) < 5:
            continue
        row = addr[1:]
        props = tuple((raw.get(f"{col}{row}") or Cell(None, None, None)).value or ""
                      for col in "ABCDEFG")
        expected = (record["id"], record["concept"], record["start"], record["end"],
                    record["filed"], record["form"], record["accession"])
        if props == expected:
            hits.append(("Source 10-K", f"H{row}"))
    if len(hits) != 1:
        raise ValueError(f"raw_record_lineage_ambiguous:{record['id']}:{len(hits)}")
    return hits[0]


def replay(case: dict, cells: dict[str, dict[str, Cell]], profile: int) -> tuple[dict, dict, dict]:
    source_deltas, overrides = {}, {}
    for i, (key, record) in enumerate(sorted(case["canonical"].items())):
        if record is None:
            continue
        delta = (29 + 17 * i) * (1 if profile == 1 else (-1 if i % 2 else 1))
        source_deltas[key] = delta
        addr = raw_address(cells, record)
        overrides[addr] = float(cells[addr[0]][addr[1]].value) + delta * 1_000_000
    scenario_deltas = {"rpo_haircut": 0.037 * profile,
                       "next12_recognition_share": -0.041 * profile}
    overrides[("RPO Scenario", "B5")] = case["scenario"]["rpo_haircut"] + scenario_deltas["rpo_haircut"]
    overrides[("RPO Scenario", "B6")] = case["scenario"]["next12_recognition_share"] + scenario_deltas["next12_recognition_share"]
    return overrides, source_deltas, scenario_deltas


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
        for sheet, addr, value in (("RPO Scenario", "B5", case["scenario"]["rpo_haircut"]),
                                    ("RPO Scenario", "B6", case["scenario"]["next12_recognition_share"])):
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
