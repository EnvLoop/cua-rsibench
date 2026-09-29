"""Independent saved-OOXML oracle for four TRAIN-only SEC workbook pairs.

This imports the generic OOXML reader and arithmetic evaluator, not the
workbook builder. Expected values come from the reviewed original filing
facts and independent financial arithmetic. No Office GUI or final task runs.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_ooxml import Evaluator, load_xlsx, unchanged_cell  # noqa: E402
from verify_train_transfer_four import _package_structure_unchanged  # noqa: E402


SHEETS = {
    "pension": ["Benefit summary", "Asset scenario", "Asset bridge",
                "Source facts", "Source lineage", "Checks"],
    "bank": ["Interest summary", "Rate scenario", "Interest build",
             "Source facts", "Source lineage", "Checks"],
}
SOURCE_KEYS = {
    "pension": ["opening_assets", "actual_return", "employer_contributions",
                "participant_contributions", "benefits_paid", "settlements",
                "closing_assets", "obligation", "reported_funded", "other_disclosed"],
    "bank": ["interest_income", "interest_expense", "reported_net_interest",
             "interest_bearing_deposits", "total_deposits",
             "average_interest_bearing_deposits"],
}
SOURCE_LABELS = {
    "pension": ["Opening plan assets", "Actual return on plan assets",
                "Employer contributions", "Participant contributions",
                "Benefits paid, signed", "Plan settlements, signed",
                "Filed closing plan assets", "Projected benefit obligation",
                "Filed funded status", "Other disclosed plan-asset activity"],
    "bank": ["Filed interest income", "Filed interest expense",
             "Filed net interest income", "Interest-bearing deposits, closing",
             "Total deposits, closing", "Interest-bearing deposits, annual average"],
}
PENSION_TARGETS = {
    ("Asset bridge", "B5"), ("Asset bridge", "C5"),
    ("Asset bridge", "C6"), ("Asset bridge", "C9"),
    ("Asset bridge", "C11"), ("Asset bridge", "C13"),
    ("Asset bridge", "C15"), ("Asset bridge", "C17"),
    ("Asset bridge", "C18"), ("Asset scenario", "C6"),
    ("Asset scenario", "C11"), ("Benefit summary", "B9"),
}
BANK_TARGETS = {
    ("Interest build", "B5"), ("Interest build", "C5"),
    ("Interest build", "C6"), ("Interest build", "C7"),
    ("Interest build", "C9"), ("Interest build", "C10"),
    ("Interest build", "C11"), ("Interest build", "C12"),
    ("Interest build", "C13"), ("Rate scenario", "C6"),
    ("Rate scenario", "C7"), ("Interest summary", "B8"),
}


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def _num(cell) -> float:
    if cell is None or cell.formula is not None or cell.value is None:
        raise ValueError("reviewed_numeric_input_missing")
    value = float(cell.value)
    if not math.isfinite(value):
        raise ValueError("reviewed_numeric_input_nonfinite")
    return value


def _text(cell) -> str:
    return "" if cell is None or cell.value is None else cell.value


def _fact(case: dict, period: int, key: str,
          changes: dict[tuple[int, str], float]) -> float:
    item = case["periods"][period]["fields"][key]
    if item["value"] is None:
        if (period, key) in changes:
            raise ValueError("unreported_source_fact_cannot_be_replayed")
        return 0.0
    return changes.get((period, key), float(item["value"]))


def expected_values(case: dict, *,
                    source_changes: dict[tuple[int, str], float] | None = None,
                    driver_changes: dict[str, float] | None = None) -> dict:
    changes = source_changes or {}
    drivers = {**case["scenario"], **(driver_changes or {})}
    f = lambda period, key: _fact(case, period, key, changes)
    if case["profile"] == "pension":
        partial = sum(f(1, key) for key in (
            "opening_assets", "actual_return", "employer_contributions",
            "participant_contributions", "benefits_paid", "settlements"))
        closing = f(1, "closing_assets")
        obligation = f(1, "obligation")
        funded = closing - obligation
        return_effect = f(1, "opening_assets") * drivers["return_change"]
        modeled_assets = closing + return_effect + drivers["sponsor_contribution"]
        modeled_obligation = obligation * (1 + drivers["obligation_change"])
        out = {
            ("Asset bridge", "B5"): f(0, "opening_assets"),
            ("Asset bridge", "C5"): f(1, "opening_assets"),
            ("Asset bridge", "C6"): f(1, "actual_return"),
            ("Asset bridge", "C9"): f(1, "benefits_paid"),
            ("Asset bridge", "C11"): partial,
            ("Asset bridge", "C13"): closing - partial,
            ("Asset bridge", "C15"): funded,
            ("Asset bridge", "C17"): funded - f(1, "reported_funded"),
            ("Asset bridge", "C18"): obligation - closing,
            ("Asset scenario", "C6"): return_effect,
            ("Asset scenario", "C11"): modeled_assets - modeled_obligation,
            ("Benefit summary", "B9"): modeled_assets - modeled_obligation,
        }
        if set(out) != PENSION_TARGETS:
            raise ValueError("pension_target_contract_changed")
        return out
    if case["profile"] == "bank":
        current_income = f(1, "interest_income")
        current_expense = f(1, "interest_expense")
        reported = f(1, "reported_net_interest")
        rebuilt = current_income - current_expense
        stress_expense = (f(1, "average_interest_bearing_deposits")
                          * drivers["deposit_rate_change_bps"] / 10000)
        stressed = reported - stress_expense
        out = {
            ("Interest build", "B5"): f(0, "interest_income"),
            ("Interest build", "C5"): current_income,
            ("Interest build", "C6"): current_expense,
            ("Interest build", "C7"): rebuilt,
            ("Interest build", "C9"): rebuilt - reported,
            ("Interest build", "C10"): f(1, "average_interest_bearing_deposits"),
            ("Interest build", "C11"):
                f(1, "interest_bearing_deposits") / f(1, "total_deposits"),
            ("Interest build", "C12"): f(1, "total_deposits") - f(0, "total_deposits"),
            ("Interest build", "C13"): reported - f(0, "reported_net_interest"),
            ("Rate scenario", "C6"): stress_expense,
            ("Rate scenario", "C7"): stressed,
            ("Interest summary", "B8"): stressed,
        }
        if set(out) != BANK_TARGETS:
            raise ValueError("bank_target_contract_changed")
        return out
    raise ValueError("unknown_private_train_profile")


def _source_cells_match(case: dict, seed: dict) -> bool:
    fields = SOURCE_KEYS[case["profile"]]
    labels = SOURCE_LABELS[case["profile"]]
    source = seed["Source facts"]
    if _text(source.get("A2")) != "Original filing: " + case["source"]["original_sec_url"]:
        return False
    lineage = seed["Source lineage"]
    next_row = 5
    for period, col in ((0, "B"), (1, "C")):
        for i, key in enumerate(fields):
            fact = case["periods"][period]["fields"][key]
            row = i + 5
            if _text(source.get(f"A{row}")) != labels[i]:
                return False
            cell = source.get(f"{col}{row}")
            if fact["value"] is None:
                if _text(cell) != "n.r." or cell.formula:
                    return False
            else:
                try:
                    if _num(cell).hex() != float(fact["value"]).hex():
                        return False
                except (ValueError, TypeError):
                    return False
            observed = [_text(lineage.get(f"{letter}{next_row}"))
                        for letter in "ABCDEF"]
            expected = [labels[i], case["periods"][period]["period_end"],
                        fact["presence"], fact.get("ixbrl_tag") or "",
                        fact.get("context_ref") or fact.get("row_sha256") or "",
                        case["source"]["original_sec_url"]]
            if observed != expected:
                return False
            next_row += 1
    sheet = seed["Asset scenario" if case["profile"] == "pension"
                 else "Rate scenario"]
    drivers = (["sponsor_contribution", "return_change", "obligation_change"]
               if case["profile"] == "pension" else ["deposit_rate_change_bps"])
    return all(_num(sheet.get(f"B{row}")).hex() ==
               float(case["scenario"][key]).hex()
               for row, key in enumerate(drivers, 5))


def _counterfactuals(case: dict) -> list[tuple[dict, dict]]:
    if case["profile"] == "pension":
        return [
            ({(0, "opening_assets"): _fact(case, 0, "opening_assets", {}) + 17}, {}),
            ({(1, "opening_assets"): _fact(case, 1, "opening_assets", {}) + 13}, {}),
            ({(1, "actual_return"): _fact(case, 1, "actual_return", {}) + 19}, {}),
            ({(1, "benefits_paid"): _fact(case, 1, "benefits_paid", {}) + 23}, {}),
            ({(1, "closing_assets"): _fact(case, 1, "closing_assets", {}) + 31}, {}),
            ({(1, "obligation"): _fact(case, 1, "obligation", {}) + 37}, {}),
            ({}, {"sponsor_contribution": case["scenario"]["sponsor_contribution"] + 47}),
            ({}, {"return_change": case["scenario"]["return_change"] + .003}),
            ({}, {"obligation_change": case["scenario"]["obligation_change"] + .005}),
        ]
    return [
        ({(0, "interest_income"): _fact(case, 0, "interest_income", {}) + 11}, {}),
        ({(1, "interest_income"): _fact(case, 1, "interest_income", {}) + 17}, {}),
        ({(1, "interest_expense"): _fact(case, 1, "interest_expense", {}) + 13}, {}),
        ({(1, "reported_net_interest"):
          _fact(case, 1, "reported_net_interest", {}) + 19}, {}),
        ({(1, "average_interest_bearing_deposits"):
          _fact(case, 1, "average_interest_bearing_deposits", {}) + 1000}, {}),
        ({(1, "interest_bearing_deposits"):
          _fact(case, 1, "interest_bearing_deposits", {}) + 1100}, {}),
        ({(1, "total_deposits"):
          _fact(case, 1, "total_deposits", {}) + 1300}, {}),
        ({(0, "total_deposits"):
          _fact(case, 0, "total_deposits", {}) + 1700}, {}),
        ({(0, "reported_net_interest"):
          _fact(case, 0, "reported_net_interest", {}) + 23}, {}),
        ({}, {"deposit_rate_change_bps":
              case["scenario"]["deposit_rate_change_bps"] + 10}),
    ]


def _target_values(candidate: dict, case: dict, *, source_changes: dict,
                   driver_changes: dict) -> list[str]:
    expected = expected_values(case, source_changes=source_changes,
                               driver_changes=driver_changes)
    overrides = {}
    for (period, key), value in source_changes.items():
        row = SOURCE_KEYS[case["profile"]].index(key) + 5
        overrides[("Source facts", f"{'B' if period == 0 else 'C'}{row}")] = value
    driver_keys = (["sponsor_contribution", "return_change", "obligation_change"]
                   if case["profile"] == "pension" else
                   ["deposit_rate_change_bps"])
    driver_sheet = ("Asset scenario" if case["profile"] == "pension" else
                    "Rate scenario")
    for row, key in enumerate(driver_keys, 5):
        if key in driver_changes:
            overrides[(driver_sheet, f"B{row}")] = driver_changes[key]
    evaluator = Evaluator(candidate, overrides)
    errors = []
    for (sheet, address), answer in expected.items():
        cell = candidate[sheet].get(address)
        if cell is None or cell.formula is None:
            errors.append(f"missing_target_formula:{sheet}!{address}")
            continue
        actual = evaluator.cell(sheet, address)
        if not _close(actual, answer):
            errors.append(f"wrong_target_result:{sheet}!{address}")
    return errors


def verify(candidate_path: Path, seed_path: Path, case: dict) -> dict:
    errors = []
    profile = case.get("profile")
    if (profile not in SHEETS or case.get("review_status") !=
            "source_field_review_pass; independent_audit_pending" or
            case.get("excel_web_admitted") is not False or
            case.get("official_final_admitted") is not False):
        return {"pass": False, "errors": ["wrong_train_only_review_scope"]}
    targets = PENSION_TARGETS if profile == "pension" else BANK_TARGETS
    try:
        candidate, names, tables, structures = load_xlsx(candidate_path)
        seed, seed_names, seed_tables, seed_structures = load_xlsx(seed_path)
        if names != SHEETS[profile] or seed_names != SHEETS[profile]:
            errors.append("sheet_order_or_names_changed")
        if tables != seed_tables or structures != seed_structures:
            errors.append("sheet_table_or_structure_changed")
        if not _package_structure_unchanged(candidate_path, seed_path, targets):
            errors.append("workbook_non_target_or_style_structure_changed")
        if not _source_cells_match(case, seed):
            errors.append("seed_source_facts_or_lineage_not_reviewed")
        for sheet in seed_names:
            for address in set(seed[sheet]) | set(candidate.get(sheet, {})):
                if (sheet, address) in targets:
                    continue
                old = seed[sheet].get(address)
                new = candidate[sheet].get(address)
                if old is None or new is None or old.formula != new.formula:
                    errors.append(f"non_target_cell_changed:{sheet}!{address}")
                elif old.formula is None and not unchanged_cell(old, new):
                    errors.append(f"non_target_cell_changed:{sheet}!{address}")
        saved = Evaluator(candidate)
        for sheet, cells in candidate.items():
            for address, cell in cells.items():
                if not cell.formula:
                    continue
                if cell.value is None:
                    errors.append(f"missing_saved_numeric_formula_cache:{sheet}!{address}")
                    continue
                if not _close(float(cell.value), saved.cell(sheet, address)):
                    errors.append(f"stale_saved_display_cache:{sheet}!{address}")
        if errors:
            return {"pass": False, "errors": errors[:30], "checked_targets": 0}
        errors += _target_values(candidate, case, source_changes={},
                                 driver_changes={})
        baseline = expected_values(case)
        witnesses = set()
        replays = _counterfactuals(case)
        for source_changes, driver_changes in replays:
            changed = expected_values(case, source_changes=source_changes,
                                      driver_changes=driver_changes)
            witnesses.update(key for key in targets
                             if not _close(changed[key], baseline[key]))
            errors += _target_values(candidate, case, source_changes=source_changes,
                                     driver_changes=driver_changes)
        if witnesses != targets:
            errors.append("counterfactual_target_dependency_coverage_incomplete")
        check_count = 3 if profile == "pension" else 2
        for row in range(5, 5 + check_count):
            if not _close(saved.cell("Checks", f"B{row}"), 0):
                errors.append(f"source_or_scenario_reconciliation_failed:{row}")
    except Exception as exc:
        errors.append(f"verification_error:{type(exc).__name__}:{exc}")
    return {"pass": not errors, "errors": errors[:30],
            "checked_targets": len(targets),
            "counterfactual_replays": len(_counterfactuals(case)),
            "source_only_offline_train": True,
            "excel_web_gui_admissions": 0, "official_final_admissions": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=Path)
    ap.add_argument("seed", type=Path)
    ap.add_argument("review", type=Path)
    ap.add_argument("--case-index", type=int, required=True)
    args = ap.parse_args()
    review = json.loads(args.review.read_bytes())
    if review.get("schema") != "envloop.sec_excel_train_next_four_review.private.v1":
        raise ValueError("private_review_schema_changed")
    matches = [x for x in review["cases"] if x["case_index"] == args.case_index]
    if len(matches) != 1:
        raise ValueError("private_train_case_not_unique")
    result = verify(args.candidate, args.seed, matches[0])
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
