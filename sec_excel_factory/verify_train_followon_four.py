"""Independent saved-OOXML scorer for four TRAIN-only SEC workbook pairs."""

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
    'allowance': ['Loan summary', 'Loss scenario', 'Loan build',
                  'Source facts', 'Source lineage', 'Checks'],
    'segment': ['Segment summary', 'Segment scenario', 'Segment build',
                'Customer cut', 'Source facts', 'Source lineage', 'Checks'],
}
SOURCE_KEYS = {
    'allowance': ['gross_loans', 'allowance', 'net_loans',
                  'beginning_allowance', 'chargeoffs', 'recoveries',
                  'provision', 'other', 'ending_allowance'],
    'segment': [*(f'segment_sales_{i}' for i in range(1, 5)),
                *(f'segment_profit_{i}' for i in range(1, 5)),
                'sales_adjustment', 'profit_adjustment',
                'filed_sales', 'filed_profit',
                *(f'customer_{i}' for i in range(1, 5))],
}
ALLOWANCE_LABELS = [
    'Gross loans and leases', 'Allowance for loan losses, magnitude',
    'Filed net loans and leases', 'Beginning allowance',
    'Charge-offs, signed', 'Recoveries', 'Provision for credit losses',
    'Other allowance activity, signed', 'Filed ending allowance',
]
SEGMENT_FIXED_LABELS = {
    'sales_adjustment': 'Signed sales eliminations or corporate amount',
    'profit_adjustment': 'Signed profit eliminations and corporate items',
    'filed_sales': 'Filed consolidated sales',
    'filed_profit': 'Filed consolidated operating profit',
}
ALLOWANCE_TARGETS = {
    ('Loan build', 'B5'), ('Loan build', 'C5'),
    ('Loan build', 'C6'), ('Loan build', 'C7'),
    ('Loan build', 'C9'), ('Loan build', 'C11'),
    ('Loan build', 'C13'), ('Loan build', 'C15'),
    ('Loan build', 'C17'), ('Loan build', 'C18'),
    ('Loss scenario', 'C9'), ('Loan summary', 'B9'),
}
SEGMENT_TARGETS = {
    ('Segment build', 'C5'), ('Segment build', 'C6'),
    ('Segment build', 'C9'), ('Segment build', 'C10'),
    ('Segment build', 'C12'), ('Segment build', 'C13'),
    ('Segment build', 'C17'), ('Segment build', 'C18'),
    ('Segment build', 'C20'), ('Customer cut', 'C9'),
    ('Segment scenario', 'C8'), ('Segment summary', 'B9'),
}


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def _text(cell) -> str:
    return '' if cell is None or cell.value is None else cell.value


def _num(cell) -> float:
    if cell is None or cell.formula is not None or cell.value is None:
        raise ValueError('reviewed_numeric_input_missing')
    value = float(cell.value)
    if not math.isfinite(value):
        raise ValueError('reviewed_numeric_input_nonfinite')
    return value


def _fact(case: dict, period: int, key: str,
          changes: dict[tuple[int, str], float]) -> float:
    item = case['periods'][period]['fields'][key]
    if item['value'] is None:
        if (period, key) in changes:
            raise ValueError('unreported_customer_category_cannot_be_replayed')
        return 0.0
    return changes.get((period, key), float(item['value']))


def expected_values(case: dict, *,
                    source_changes: dict[tuple[int, str], float] | None = None,
                    driver_changes: dict[str, float] | None = None) -> dict:
    changes = source_changes or {}
    drivers = {**case['scenario'], **(driver_changes or {})}
    f = lambda period, key: _fact(case, period, key, changes)
    if case['profile'] == 'allowance':
        gross = f(1, 'gross_loans')
        allowance = f(1, 'allowance')
        net = f(1, 'net_loans')
        rebuilt = sum(f(1, key) for key in (
            'beginning_allowance', 'chargeoffs', 'recoveries',
            'provision', 'other'))
        ending = f(1, 'ending_allowance')
        stressed = gross * (1 + drivers['gross_loan_change']) - \
            (ending + drivers['additional_provision'])
        out = {
            ('Loan build', 'B5'): f(0, 'gross_loans'),
            ('Loan build', 'C5'): gross,
            ('Loan build', 'C6'): allowance,
            ('Loan build', 'C7'): gross - allowance,
            ('Loan build', 'C9'): gross - allowance - net,
            ('Loan build', 'C11'): f(1, 'chargeoffs'),
            ('Loan build', 'C13'): f(1, 'provision'),
            ('Loan build', 'C15'): rebuilt,
            ('Loan build', 'C17'): rebuilt - ending,
            ('Loan build', 'C18'): allowance / gross,
            ('Loss scenario', 'C9'): stressed,
            ('Loan summary', 'B9'): stressed,
        }
        if set(out) != ALLOWANCE_TARGETS:
            raise ValueError('allowance_target_contract_changed')
        return out
    if case['profile'] == 'segment':
        sales = sum(f(1, f'segment_sales_{i}') for i in range(1, 5))
        sales += f(1, 'sales_adjustment')
        profit = sum(f(1, f'segment_profit_{i}') for i in range(1, 5))
        profit += f(1, 'profit_adjustment')
        customer = sum(f(1, f'customer_{i}') for i in range(1, 5))
        filed_sales = f(1, 'filed_sales')
        filed_profit = f(1, 'filed_profit')
        added_sales = f(1, 'segment_sales_1') * \
            drivers['selected_segment_sales_change']
        modeled_sales = filed_sales + added_sales
        modeled_profit = filed_profit + added_sales * \
            drivers['incremental_profit_margin']
        out = {
            ('Segment build', 'C5'): f(1, 'segment_sales_1'),
            ('Segment build', 'C6'): f(1, 'segment_sales_2'),
            ('Segment build', 'C9'): f(1, 'sales_adjustment'),
            ('Segment build', 'C10'): sales,
            ('Segment build', 'C12'): sales - filed_sales,
            ('Segment build', 'C13'): f(1, 'segment_profit_1'),
            ('Segment build', 'C17'): f(1, 'profit_adjustment'),
            ('Segment build', 'C18'): profit,
            ('Segment build', 'C20'): profit - filed_profit,
            ('Customer cut', 'C9'): customer,
            ('Segment scenario', 'C8'): modeled_sales,
            ('Segment summary', 'B9'): modeled_profit,
        }
        if set(out) != SEGMENT_TARGETS:
            raise ValueError('segment_target_contract_changed')
        return out
    raise ValueError('unknown_private_train_profile')


def _labels(case: dict) -> list[str]:
    if case['profile'] == 'allowance':
        return ALLOWANCE_LABELS
    segment = case['source']['segment_labels']
    customer = case['source']['customer_labels']
    if len(segment) != 4 or len(customer) != 4:
        raise ValueError('segment_or_customer_labels_incomplete')
    return ([f'{x} sales' for x in segment] +
            [f'{x} operating profit' for x in segment] +
            [SEGMENT_FIXED_LABELS[x] for x in
             ('sales_adjustment', 'profit_adjustment',
              'filed_sales', 'filed_profit')] + customer)


def _source_cells_match(case: dict, seed: dict) -> bool:
    keys = SOURCE_KEYS[case['profile']]
    labels = _labels(case)
    source = seed['Source facts']
    if _text(source.get('A2')) != \
            'Original filing: ' + case['source']['original_sec_url']:
        return False
    lineage = seed['Source lineage']
    row = 5
    for period, col in ((0, 'B'), (1, 'C')):
        for i, key in enumerate(keys):
            fact = case['periods'][period]['fields'][key]
            source_row = i + 5
            if _text(source.get(f'A{source_row}')) != labels[i]:
                return False
            cell = source.get(f'{col}{source_row}')
            if fact['value'] is None:
                if _text(cell) != 'n.r.' or cell.formula:
                    return False
            else:
                try:
                    if _num(cell).hex() != float(fact['value']).hex():
                        return False
                except (ValueError, TypeError):
                    return False
            actual = [_text(lineage.get(f'{letter}{row}'))
                      for letter in 'ABCDEF']
            expected = [labels[i], case['periods'][period]['period_end'],
                        fact['presence'], fact.get('ixbrl_tag') or '',
                        fact.get('context_ref') or fact.get('row_sha256') or '',
                        case['source']['original_sec_url']]
            if actual != expected:
                return False
            row += 1
    sheet = seed['Loss scenario' if case['profile'] == 'allowance'
                 else 'Segment scenario']
    driver_keys = (['additional_provision', 'gross_loan_change']
                   if case['profile'] == 'allowance' else
                   ['selected_segment_sales_change',
                    'incremental_profit_margin'])
    return all(_num(sheet.get(f'B{row}')).hex() ==
               float(case['scenario'][key]).hex()
               for row, key in enumerate(driver_keys, 5))


def _counterfactuals(case: dict) -> list[tuple[dict, dict]]:
    f = lambda period, key: _fact(case, period, key, {})
    if case['profile'] == 'allowance':
        return [
            ({(0, 'gross_loans'): f(0, 'gross_loans') + 17}, {}),
            ({(1, 'gross_loans'): f(1, 'gross_loans') + 19}, {}),
            ({(1, 'allowance'): f(1, 'allowance') + 23}, {}),
            ({(1, 'chargeoffs'): f(1, 'chargeoffs') + 29}, {}),
            ({(1, 'provision'): f(1, 'provision') + 31}, {}),
            ({(1, 'beginning_allowance'):
              f(1, 'beginning_allowance') + 37}, {}),
            ({(1, 'ending_allowance'): f(1, 'ending_allowance') + 41}, {}),
            ({}, {'additional_provision':
                  case['scenario']['additional_provision'] + 47}),
            ({}, {'gross_loan_change':
                  case['scenario']['gross_loan_change'] + .003}),
        ]
    return [
        ({(1, 'segment_sales_1'): f(1, 'segment_sales_1') + 13}, {}),
        ({(1, 'segment_sales_2'): f(1, 'segment_sales_2') + 17}, {}),
        ({(1, 'sales_adjustment'): f(1, 'sales_adjustment') + 19}, {}),
        ({(1, 'filed_sales'): f(1, 'filed_sales') + 23}, {}),
        ({(1, 'segment_profit_1'): f(1, 'segment_profit_1') + 29}, {}),
        ({(1, 'profit_adjustment'): f(1, 'profit_adjustment') + 31}, {}),
        ({(1, 'filed_profit'): f(1, 'filed_profit') + 37}, {}),
        ({(1, 'customer_3'): f(1, 'customer_3') + 41}, {}),
        ({}, {'selected_segment_sales_change':
              case['scenario']['selected_segment_sales_change'] + .01}),
        ({}, {'incremental_profit_margin':
              case['scenario']['incremental_profit_margin'] + .02}),
    ]


def _check_targets(candidate: dict, case: dict, *,
                   source_changes: dict, driver_changes: dict) -> list[str]:
    expected = expected_values(case, source_changes=source_changes,
                               driver_changes=driver_changes)
    overrides = {}
    for (period, key), value in source_changes.items():
        row = SOURCE_KEYS[case['profile']].index(key) + 5
        overrides[('Source facts', f'{"B" if period == 0 else "C"}{row}')] = value
    driver_sheet = ('Loss scenario' if case['profile'] == 'allowance'
                    else 'Segment scenario')
    driver_keys = (['additional_provision', 'gross_loan_change']
                   if case['profile'] == 'allowance' else
                   ['selected_segment_sales_change',
                    'incremental_profit_margin'])
    for row, key in enumerate(driver_keys, 5):
        if key in driver_changes:
            overrides[(driver_sheet, f'B{row}')] = driver_changes[key]
    evaluator = Evaluator(candidate, overrides)
    errors = []
    for (sheet, address), answer in expected.items():
        cell = candidate[sheet].get(address)
        if cell is None or cell.formula is None:
            errors.append(f'missing_target_formula:{sheet}!{address}')
            continue
        if not _close(evaluator.cell(sheet, address), answer):
            errors.append(f'wrong_target_result:{sheet}!{address}')
    return errors


def verify(candidate_path: Path, seed_path: Path, case: dict) -> dict:
    profile = case.get('profile')
    if (profile not in SHEETS or case.get('review_status') !=
            'source_field_review_pass; independent_audit_pending' or
            case.get('excel_web_admitted') is not False or
            case.get('official_final_admitted') is not False):
        return {'pass': False, 'errors': ['wrong_private_train_case_scope']}
    targets = (ALLOWANCE_TARGETS if profile == 'allowance' else
               SEGMENT_TARGETS)
    errors = []
    try:
        current, names, tables, structure = load_xlsx(candidate_path)
        seed, seed_names, seed_tables, seed_structure = load_xlsx(seed_path)
        if names != SHEETS[profile] or seed_names != SHEETS[profile]:
            errors.append('sheet_order_or_names_changed')
        if tables != seed_tables or structure != seed_structure:
            errors.append('sheet_table_or_structure_changed')
        if not _package_structure_unchanged(candidate_path, seed_path, targets):
            errors.append('workbook_non_target_or_style_structure_changed')
        if not _source_cells_match(case, seed):
            errors.append('seed_source_facts_or_lineage_not_reviewed')
        for sheet in seed_names:
            for address in set(seed[sheet]) | set(current.get(sheet, {})):
                if (sheet, address) in targets:
                    continue
                old, new = seed[sheet].get(address), current.get(sheet, {}).get(address)
                if old is None or new is None or old.formula != new.formula:
                    errors.append(f'non_target_cell_changed:{sheet}!{address}')
                elif old.formula is None and not unchanged_cell(old, new):
                    errors.append(f'non_target_cell_changed:{sheet}!{address}')
        saved = Evaluator(current)
        for sheet, cells in current.items():
            for address, cell in cells.items():
                if not cell.formula:
                    continue
                if cell.value is None:
                    errors.append(f'missing_saved_numeric_formula_cache:{sheet}!{address}')
                    continue
                if not _close(float(cell.value), saved.cell(sheet, address)):
                    errors.append(f'stale_saved_display_cache:{sheet}!{address}')
        if errors:
            return {'pass': False, 'errors': errors[:30], 'checked_targets': 0}
        errors += _check_targets(current, case, source_changes={},
                                 driver_changes={})
        baseline = expected_values(case)
        witnesses = set()
        replays = _counterfactuals(case)
        for source_changes, driver_changes in replays:
            changed = expected_values(case, source_changes=source_changes,
                                      driver_changes=driver_changes)
            witnesses.update(key for key in targets
                             if not _close(changed[key], baseline[key]))
            errors += _check_targets(current, case,
                                     source_changes=source_changes,
                                     driver_changes=driver_changes)
        if witnesses != targets:
            errors.append('counterfactual_target_dependency_coverage_incomplete')
        count = 3 if profile == 'allowance' else 5
        for row in range(5, 5 + count):
            if not _close(saved.cell('Checks', f'B{row}'), 0):
                errors.append(f'source_or_scenario_reconciliation_failed:{row}')
    except Exception as exc:
        errors.append(f'verification_error:{type(exc).__name__}:{exc}')
    return {'pass': not errors, 'errors': errors[:30],
            'checked_targets': len(targets),
            'counterfactual_replays': len(_counterfactuals(case)),
            'source_only_offline_train': True,
            'excel_web_gui_admissions': 0, 'official_final_admissions': 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('candidate', type=Path)
    ap.add_argument('seed', type=Path)
    ap.add_argument('review', type=Path)
    ap.add_argument('--case-index', type=int, required=True)
    args = ap.parse_args()
    review = json.loads(args.review.read_bytes())
    if review.get('schema') != \
            'envloop.sec_excel_train_followon_four_review.private.v1':
        raise ValueError('private_review_schema_changed')
    cases = [c for c in review['cases'] if c['case_index'] == args.case_index]
    if len(cases) != 1:
        raise ValueError('private_train_case_not_unique')
    result = verify(args.candidate, args.seed, cases[0])
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
