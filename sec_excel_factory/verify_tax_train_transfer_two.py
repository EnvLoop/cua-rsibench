"""Independent saved-OOXML scorer for two TRAIN-only SEC tax analogues.

The oracle recomputes signed balances from reviewed case facts, not builder
formulas, reference workbook values, cached cells, or a final task. An isolated
formula evaluator replays edited source and scenario inputs in memory.
"""

from __future__ import annotations

import argparse
import json
import math
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_ooxml import Evaluator, load_xlsx, unchanged_cell  # noqa: E402
from verify_train_transfer_four import _package_structure_unchanged  # noqa: E402


SHEETS = ["Tax summary", "Tax scenario", "Gross bridge", "Interest scope",
          "Source facts", "Source lineage", "Checks"]
METRICS = [
    ("opening", "Opening gross uncertain tax positions"),
    ("current_year_additions", "Current-year position additions"),
    ("prior_year_additions", "Prior-year position additions"),
    ("prior_year_reductions", "Prior-year position reductions, signed"),
    ("settlements", "Settlements, signed"),
    ("lapse", "Statute lapse, signed"),
    ("translation", "Currency translation, signed"),
    ("other", "Other disclosed signed activity"),
    ("closing", "Filed closing gross uncertain tax positions"),
    ("accrued_interest_penalties", "Separately accrued interest and penalties"),
    ("interest_flow", "Filed interest-related expense/(benefit)"),
]
SOURCE_ROW = {key: row for row, (key, _) in enumerate(METRICS, 5)}
ACTIVITY = ("current_year_additions", "prior_year_additions",
            "prior_year_reductions", "settlements", "lapse", "translation", "other")
TARGETS = {
    ("Gross bridge", "B5"), ("Gross bridge", "C5"),
    ("Gross bridge", "C6"), ("Gross bridge", "C8"),
    ("Gross bridge", "C9"), ("Gross bridge", "C13"),
    ("Gross bridge", "C14"), ("Gross bridge", "C16"),
    ("Interest scope", "C5"), ("Tax scenario", "C5"),
    ("Tax scenario", "C6"), ("Tax summary", "B8"),
}
assert len(TARGETS) == 12


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def _num(cell) -> float:
    if cell is None or cell.value is None or cell.formula is not None:
        raise ValueError("numeric_reviewed_source_cell_missing")
    return float(cell.value)


def _same_number(cell, expected: int | float) -> bool:
    try:
        return math.isfinite(_num(cell)) and _num(cell).hex() == float(expected).hex()
    except (ValueError, TypeError):
        return False


def _text(cell) -> str:
    return cell.value if cell is not None and cell.value is not None else ""


def _fact(case: dict, period: int, key: str,
          changes: dict[tuple[int, str], float]) -> float:
    fact = case["periods"][period]["fields"][key]
    if fact["presence"] == "not_separately_reported":
        if fact["value"] is not None or (period, key) in changes:
            raise ValueError("unreported_category_misrepresented_as_filed_zero")
        return 0.0  # Explicit bridge-only convention, never a filed source fact.
    value = changes.get((period, key), fact["value"])
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("reviewed_filed_number_missing")
    return float(value)


def expected_values(case: dict, *,
                    source_changes: dict[tuple[int, str], float] | None = None,
                    driver_changes: dict[str, float] | None = None) -> dict[tuple[str, str], float]:
    """Recompute 12 target results from independent signed arithmetic."""
    changes = source_changes or {}
    drivers = {**case["scenario"], **(driver_changes or {})}
    prior_opening = _fact(case, 0, "opening", changes)
    current_opening = _fact(case, 1, "opening", changes)
    current_additions = _fact(case, 1, "current_year_additions", changes)
    current_reductions = _fact(case, 1, "prior_year_reductions", changes)
    current_settlements = _fact(case, 1, "settlements", changes)
    activity = sum(_fact(case, 1, key, changes) for key in ACTIVITY)
    rebuilt = current_opening + activity
    filed_closing = _fact(case, 1, "closing", changes)
    accrued = _fact(case, 1, "accrued_interest_penalties", changes)
    new_gross = filed_closing + drivers["additions"]
    settled_gross = new_gross + drivers["settlements"]
    modeled_separate_accrual = accrued * (1 + drivers["accrual_change"])
    return {
        ("Gross bridge", "B5"): prior_opening,
        ("Gross bridge", "C5"): current_opening,
        ("Gross bridge", "C6"): current_additions,
        ("Gross bridge", "C8"): current_reductions,
        ("Gross bridge", "C9"): current_settlements,
        ("Gross bridge", "C13"): activity,
        ("Gross bridge", "C14"): rebuilt,
        ("Gross bridge", "C16"): rebuilt - filed_closing,
        ("Interest scope", "C5"): accrued,
        ("Tax scenario", "C5"): new_gross,
        ("Tax scenario", "C6"): settled_gross,
        ("Tax summary", "B8"): settled_gross + modeled_separate_accrual,
    }


def _case_scope(case: dict) -> None:
    if (case.get("schema") != "envloop.sec_tax_train_analogue_case.private.v1" or
            case.get("scope") !=
            "TRAIN-only offline analogue; no final workbook or GUI admission" or
            len(case.get("periods", [])) != 2 or
            case.get("skill", {}).get("signature_sha256") !=
            "ff413ae00b002631deefbccab6a6392405c63e6f31a968efbb5ef67aaa5506e8"):
        raise ValueError("wrong_private_train_case_scope")
    for period in case["periods"]:
        if set(period["fields"]) != set(SOURCE_ROW):
            raise ValueError("reviewed_source_field_set_changed")
        for key, item in period["fields"].items():
            if item["presence"] == "not_separately_reported":
                if item["value"] is not None or item.get("ixbrl_tag") is not None:
                    raise ValueError("unreported_category_misrepresented_as_filed_zero")
            elif (item["presence"] not in {"reported", "disclosed_dash"} or
                  not isinstance(item["value"], (int, float)) or
                  item.get("document") not in case["source"]["raw_sha256"] or
                  not item.get("ixbrl_tag") or not item.get("ixbrl_context_ref")):
                raise ValueError(f"filed_fact_without_reviewed_origin:{key}")
        expected = (_fact(case, case["periods"].index(period), "opening", {}) +
                    sum(_fact(case, case["periods"].index(period), key, {})
                        for key in ACTIVITY))
        if not _close(expected, _fact(case, case["periods"].index(period), "closing", {})):
            raise ValueError("filed_gross_rollforward_not_reconciled")
    if case["source"].get("interest_flow_label") not in {
            "Net interest expense",
            "Combined interest and penalties expense/(benefit)"}:
        raise ValueError("interest_expense_scope_label_invalid")


def _source_facts_match(case: dict, seed: dict) -> bool:
    facts = seed["Source facts"]
    if (_text(facts.get("A1")) != "Original SEC filing tax note facts (USD millions)" or
            _text(facts.get("A2")) !=
            "Original filing: " + case["source"]["original_sec_url"] or
            _text(facts.get("A15")) != case["source"]["interest_flow_label"] or
            _text(seed["Interest scope"].get("A6")) !=
            case["source"]["interest_flow_label"]):
        return False
    for key, row in SOURCE_ROW.items():
        absent = any(p["fields"][key]["presence"] == "not_separately_reported"
                     for p in case["periods"])
        note = ("Separate liability; excluded from the gross position rollforward"
                if key == "accrued_interest_penalties" else
                "Signed annual flow; scope follows the original source, outside the gross bridge"
                if key == "interest_flow" else
                "n.r. is not separately reported; zero is a bridge convention"
                if absent else "")
        if _text(facts.get(f"D{row}")) != note:
            return False
        if row in range(6, 13):
            bridge_note = ("n.r. uses zero only as a bridge convention; not a filed zero"
                           if absent else "")
            if _text(seed["Gross bridge"].get(f"D{row}")) != bridge_note:
                return False
    for period, col in ((0, "B"), (1, "C")):
        for key, row in SOURCE_ROW.items():
            item = case["periods"][period]["fields"][key]
            cell = facts.get(f"{col}{row}")
            if item["presence"] == "not_separately_reported":
                if _text(cell) != "n.r." or (cell and cell.formula):
                    return False
            elif not _same_number(cell, item["value"]):
                return False
    for row, key in enumerate(("additions", "settlements", "accrual_change"), 5):
        if not _same_number(seed["Tax scenario"].get(f"B{row}"), case["scenario"][key]):
            return False
    lineage = seed["Source lineage"]
    row = 5
    for period in (0, 1):
        for key, fallback in METRICS:
            fact = case["periods"][period]["fields"][key]
            label = case["source"]["interest_flow_label"] if key == "interest_flow" else fallback
            expected = [label, case["periods"][period]["period_end"],
                        fact["presence"], fact.get("document") or "",
                        fact.get("ixbrl_tag") or "",
                        fact.get("ixbrl_context_ref") or fact.get("row_locator") or "",
                        case["source"]["original_sec_url"], case["source"]["accession"]]
            if [_text(lineage.get(f"{col}{row}")) for col in "ABCDEFGH"] != expected:
                return False
            row += 1
    return len([x for x in lineage if x.startswith("H") and x[1:].isdigit()
                and int(x[1:]) >= 5]) == row - 5


def _check_targets(candidate: dict, case: dict,
                   source_changes: dict[tuple[int, str], float] | None = None,
                   driver_changes: dict[str, float] | None = None,
                   *, cache: bool = False) -> list[str]:
    source_changes = source_changes or {}
    driver_changes = driver_changes or {}
    overrides = {("Source facts", f"{'B' if p == 0 else 'C'}{SOURCE_ROW[key]}"): value
                 for (p, key), value in source_changes.items()}
    overrides.update({("Tax scenario", f"B{row}"): value
                      for row, key in enumerate(("additions", "settlements", "accrual_change"), 5)
                      if (value := driver_changes.get(key)) is not None})
    oracle = expected_values(case, source_changes=source_changes,
                             driver_changes=driver_changes)
    errors = []
    evaluator = Evaluator(candidate, overrides)
    for sheet, address in sorted(TARGETS):
        cell = candidate.get(sheet, {}).get(address)
        if cell is None or not cell.formula:
            errors.append(f"missing_target_formula:{sheet}!{address}")
            continue
        try:
            observed = evaluator.cell(sheet, address)
            if not _close(observed, oracle[(sheet, address)]):
                errors.append(f"wrong_target_result:{sheet}!{address}")
            if cache:
                if cell.value is None or not math.isfinite(float(cell.value)):
                    errors.append(f"missing_target_saved_numeric_cache:{sheet}!{address}")
                elif not _close(float(cell.value), observed):
                    errors.append(f"stale_target_cache:{sheet}!{address}")
        except Exception as error:
            errors.append(f"target_evaluation_error:{sheet}!{address}:{type(error).__name__}")
    return errors


def _counterfactuals(case: dict) -> list[tuple[dict, dict]]:
    keys = ((0, "opening", 17.0), (1, "opening", 19.0),
            (1, "current_year_additions", 11.0),
            (1, "prior_year_reductions", -7.0),
            (1, "settlements", -5.0), (1, "closing", 13.0),
            (1, "accrued_interest_penalties", 4.0))
    source = [({(p, key): case["periods"][p]["fields"][key]["value"] + delta}, {})
              for p, key, delta in keys]
    drivers = [({}, {key: case["scenario"][key] + delta})
               for key, delta in (("additions", 3.0), ("settlements", -2.0),
                                  ("accrual_change", 0.02))]
    # The joint replay catches an additive impostor that matches each separate
    # factor while omitting the accrued-balance × rate interaction term.
    joint = ({(1, "accrued_interest_penalties"):
              case["periods"][1]["fields"]["accrued_interest_penalties"]["value"] + 4.0},
             {"accrual_change": case["scenario"]["accrual_change"] + 0.02})
    return source + drivers + [joint]


def _manifest_case_bound(case_path: Path, case: dict) -> None:
    manifest_path = case_path.parent.parent / "cases-manifest.private.json"
    manifest = json.loads(manifest_path.read_bytes())
    index = case["case_index"]
    if (manifest.get("schema") != "envloop.sec_tax_train_case_manifest.private.v1" or
            manifest.get("case_count") != 2 or index not in (0, 1) or
            case_path.name != f"case-{index:02d}.private.json" or
            sha256(case_path.read_bytes()).hexdigest() != manifest["case_sha256"][index] or
            case["source"]["semantic_review_sha256"] != manifest["semantic_review_sha256"] or
            manifest.get("official_excel_web_admitted") != 0):
        raise ValueError("private_case_not_bound_to_source_manifest")


def verify(candidate_path: Path, seed_path: Path, case_path: Path) -> dict:
    errors: list[str] = []
    try:
        case = json.loads(case_path.read_bytes())
        _case_scope(case)
        _manifest_case_bound(case_path, case)
        candidate, names, tables, structure = load_xlsx(candidate_path)
        seed, seed_names, seed_tables, seed_structure = load_xlsx(seed_path)
        if names != SHEETS or seed_names != SHEETS:
            errors.append("sheet_order_or_names_changed")
        if tables != seed_tables or structure != seed_structure:
            errors.append("sheet_table_or_structure_changed")
        if not _package_structure_unchanged(candidate_path, seed_path, TARGETS):
            errors.append("workbook_non_target_or_style_structure_changed")
        if not _source_facts_match(case, seed):
            errors.append("seed_facts_or_drivers_not_reviewed_source")
        for sheet in seed_names:
            for address in set(seed[sheet]) | set(candidate.get(sheet, {})):
                if (sheet, address) in TARGETS:
                    continue
                old, new = seed[sheet].get(address), candidate.get(sheet, {}).get(address)
                if old is None or new is None or old.formula != new.formula:
                    errors.append(f"non_target_cell_changed:{sheet}!{address}")
                elif old.formula is None and not unchanged_cell(old, new):
                    errors.append(f"non_target_cell_changed:{sheet}!{address}")
        saved_evaluator = Evaluator(candidate)
        for sheet, cells in candidate.items():
            for address, cell in cells.items():
                if cell.formula:
                    try:
                        if cell.value is None or not math.isfinite(float(cell.value)):
                            errors.append(f"missing_saved_numeric_formula_cache:{sheet}!{address}")
                        elif not _close(float(cell.value), saved_evaluator.cell(sheet, address)):
                            errors.append(f"stale_saved_display_cache:{sheet}!{address}")
                    except (ValueError, ZeroDivisionError):
                        errors.append(f"invalid_saved_display_formula_or_cache:{sheet}!{address}")
        if errors:
            return {"pass": False, "errors": errors[:30], "checked_targets": 0}
        errors.extend(_check_targets(candidate, case, cache=True))
        baseline = expected_values(case)
        witnesses = set()
        counterfactuals = _counterfactuals(case)
        for source, drivers in counterfactuals:
            changed = expected_values(case, source_changes=source,
                                      driver_changes=drivers)
            witnesses.update(key for key in TARGETS if not _close(changed[key], baseline[key]))
            errors.extend(_check_targets(candidate, case, source, drivers))
        if witnesses != TARGETS:
            errors.append("counterfactual_target_dependency_coverage_incomplete")
        if not errors:
            evaluator = Evaluator(candidate)
            for row in range(5, 9):
                if not _close(evaluator.cell("Checks", f"B{row}"), 0):
                    errors.append(f"historical_or_scenario_reconciliation_failed:{row}")
    except Exception as error:
        errors.append(f"verification_error:{type(error).__name__}:{error}")
    return {"pass": not errors, "errors": errors[:30],
            "checked_targets": len(TARGETS),
            "counterfactual_replays": len(_counterfactuals(case)) if not errors else 0,
            "source_only_offline_train": True, "official_excel_web_admission": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=Path)
    ap.add_argument("seed", type=Path)
    ap.add_argument("case", type=Path)
    args = ap.parse_args()
    result = verify(args.candidate, args.seed, args.case)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
