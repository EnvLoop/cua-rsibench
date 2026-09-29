"""Independent saved-OOXML scorer for pension and AFS TRAIN analogues."""

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
    'pension_full': ['Pension summary', 'Plan scenario', 'Asset build',
                     'Source facts', 'Source lineage', 'Checks'],
    'afs': ['AFS summary', 'Rate scenario', 'Fair bridge', 'Loss aging',
            'Maturity ladder', 'Source facts', 'Source lineage', 'Checks'],
}
PENSION_KEYS = [
    'opening_assets', 'acquisition', 'return', 'employer', 'participant',
    'fx_or_other', 'benefits', 'settlements_or_other', 'closing_assets',
    'obligation', 'reported_funded',
]
PENSION_LABELS = [
    'Opening international-plan assets',
    'Acquisition or divestiture asset change',
    'Actual return on plan assets', 'Employer contributions',
    'Participant contributions', 'Currency and other filed asset activity',
    'Benefits paid, signed', 'Settlements and related items, signed',
    'Filed closing plan assets', 'Projected benefit obligation',
    'Filed funded status',
]
AFS_KEYS = [
    'amortized_cost', 'acl_signed', 'unrealized_gains',
    'unrealized_losses_signed', 'fair_value',
    'loss_age_lt_fair', 'loss_age_lt_loss',
    'loss_age_ge_fair', 'loss_age_ge_loss',
    'loss_position_fair', 'loss_position_loss',
]
AFS_LABELS = [
    'AFS amortized cost before allowance',
    'Allowance for credit losses, signed',
    'Gross unrealized gains', 'Gross unrealized losses, signed',
    'Filed AFS fair value',
    'Loss-position fair value, under 12 months',
    'Loss-position gross losses, under 12 months',
    'Loss-position fair value, 12 months or more',
    'Loss-position gross losses, 12 months or more',
    'Filed fair value of loss-position subset',
    'Filed gross losses of loss-position subset',
]
PENSION_TARGETS = {
    ('Asset build', 'C5'), ('Asset build', 'C7'),
    ('Asset build', 'C8'), ('Asset build', 'C9'),
    ('Asset build', 'C10'), ('Asset build', 'C11'),
    ('Asset build', 'C12'), ('Asset build', 'C13'),
    ('Asset build', 'C15'), ('Asset build', 'C17'),
    ('Plan scenario', 'C11'), ('Pension summary', 'B9'),
}
AFS_TARGETS = {
    ('Fair bridge', 'C5'), ('Fair bridge', 'C6'),
    ('Fair bridge', 'C7'), ('Fair bridge', 'C8'),
    ('Fair bridge', 'C9'), ('Fair bridge', 'C11'),
    ('Loss aging', 'C9'), ('Loss aging', 'C12'),
    ('Maturity ladder', 'C16'), ('Maturity ladder', 'C19'),
    ('Rate scenario', 'C9'), ('AFS summary', 'B9'),
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
            raise ValueError('unreported_source_fact_cannot_be_replayed')
        return 0.0
    return changes.get((period, key), float(item['value']))


def _maturity(case: dict, key: str,
              changes: dict[str, float]) -> float:
    if key == 'filed_total_fair':
        base = case['maturity']['filed_total_fair']['value']
    elif key == 'filed_total_cost':
        base = case['maturity']['filed_total_cost']['value']
    else:
        kind, number = key.rsplit('_', 1)
        base = case['maturity']['buckets'][int(number) - 1][kind]['value']
    return changes.get(key, float(base))


def expected_values(case: dict, *,
                    source_changes: dict[tuple[int, str], float] | None = None,
                    maturity_changes: dict[str, float] | None = None,
                    driver_changes: dict[str, float] | None = None) -> dict:
    source_changes = source_changes or {}
    maturity_changes = maturity_changes or {}
    drivers = {**case['scenario'], **(driver_changes or {})}
    f = lambda period, key: _fact(case, period, key, source_changes)
    if case['profile'] == 'pension_full':
        rebuilt = sum(f(1, key) for key in PENSION_KEYS[:8])
        closing = f(1, 'closing_assets')
        obligation = f(1, 'obligation')
        funded = closing - obligation
        modeled_assets = (closing + drivers['sponsor_contribution'] +
                          f(1, 'opening_assets') * drivers['return_change'] +
                          drivers['fx_shift'])
        modeled_obligation = obligation * (1 + drivers['obligation_change'])
        out = {
            ('Asset build', 'C5'): f(1, 'opening_assets'),
            ('Asset build', 'C7'): f(1, 'return'),
            ('Asset build', 'C8'): f(1, 'employer'),
            ('Asset build', 'C9'): f(1, 'participant'),
            ('Asset build', 'C10'): f(1, 'fx_or_other'),
            ('Asset build', 'C11'): f(1, 'benefits'),
            ('Asset build', 'C12'): f(1, 'settlements_or_other'),
            ('Asset build', 'C13'): rebuilt,
            ('Asset build', 'C15'): rebuilt - closing,
            ('Asset build', 'C17'): funded,
            ('Plan scenario', 'C11'): modeled_assets - modeled_obligation,
            ('Pension summary', 'B9'): modeled_assets - modeled_obligation,
        }
        if set(out) != PENSION_TARGETS:
            raise ValueError('pension_target_contract_changed')
        return out
    if case['profile'] == 'afs':
        cost = f(1, 'amortized_cost')
        acl = f(1, 'acl_signed')
        gain = f(1, 'unrealized_gains')
        loss = f(1, 'unrealized_losses_signed')
        fair = cost + acl + gain + loss
        age_fair = f(1, 'loss_age_lt_fair') + f(1, 'loss_age_ge_fair')
        age_loss = f(1, 'loss_age_lt_loss') + f(1, 'loss_age_ge_loss')
        maturity_cost = sum(_maturity(case, f'cost_{i}', maturity_changes)
                            for i in range(1, 6))
        maturity_fair = sum(_maturity(case, f'fair_{i}', maturity_changes)
                            for i in range(1, 6))
        stressed = (_maturity(case, 'filed_total_fair', maturity_changes)
                    - _maturity(case, 'fair_2', maturity_changes)
                    * drivers['years_two_five_haircut']
                    - _maturity(case, 'fair_4', maturity_changes)
                    * drivers['after_ten_haircut']
                    - _maturity(case, 'fair_5', maturity_changes)
                    * drivers['no_single_date_haircut'])
        out = {
            ('Fair bridge', 'C5'): cost,
            ('Fair bridge', 'C6'): acl,
            ('Fair bridge', 'C7'): gain,
            ('Fair bridge', 'C8'): loss,
            ('Fair bridge', 'C9'): fair,
            ('Fair bridge', 'C11'): fair - f(1, 'fair_value'),
            ('Loss aging', 'C9'): age_fair,
            ('Loss aging', 'C12'): age_loss,
            ('Maturity ladder', 'C16'): maturity_cost,
            ('Maturity ladder', 'C19'): maturity_fair,
            ('Rate scenario', 'C9'): stressed,
            ('AFS summary', 'B9'): stressed,
        }
        if set(out) != AFS_TARGETS:
            raise ValueError('afs_target_contract_changed')
        return out
    raise ValueError('unknown_private_train_profile')


def _source_cells_match(case: dict, seed: dict) -> bool:
    keys = PENSION_KEYS if case['profile'] == 'pension_full' else AFS_KEYS
    labels = PENSION_LABELS if case['profile'] == 'pension_full' else AFS_LABELS
    source = seed['Source facts']
    if _text(source.get('A2')) != \
            'Original filing: ' + case['source']['original_sec_url']:
        return False
    lineage = seed['Source lineage']
    row = 5
    for period, col in ((0, 'B'), (1, 'C')):
        for i, key in enumerate(keys):
            fact = case['periods'][period]['fields'][key]
            srow = i + 5
            if _text(source.get(f'A{srow}')) != labels[i]:
                return False
            cell = source.get(f'{col}{srow}')
            if fact['value'] is None:
                if _text(cell) != 'n.r.' or cell.formula:
                    return False
            else:
                try:
                    if _num(cell).hex() != float(fact['value']).hex():
                        return False
                except (ValueError, TypeError):
                    return False
            observed = [_text(lineage.get(f'{letter}{row}'))
                        for letter in 'ABCDEF']
            expected = [labels[i], case['periods'][period]['period_end'],
                        fact['presence'], fact.get('ixbrl_tag') or '',
                        fact.get('context_ref') or fact.get('row_sha256') or '',
                        case['source']['original_sec_url']]
            if observed != expected:
                return False
            row += 1
    if case['profile'] == 'afs':
        if _text(source.get('A16')) != 'Current maturity buckets, filed basis':
            return False
        for i, bucket in enumerate(case['maturity']['buckets']):
            for kind, srow in (('cost', 17 + i), ('fair', 22 + i)):
                fact = bucket[kind]
                display = (f'{bucket["label"]} fair value' if kind == 'fair'
                           else f'{bucket["label"]} cost')
                if (_text(source.get(f'A{srow}')) !=
                        display or
                        _num(source.get(f'C{srow}')).hex() !=
                        float(fact['value']).hex()):
                    return False
                actual = [_text(lineage.get(f'{letter}{row}'))
                          for letter in 'ABCDEF']
                expected = [f'{bucket["label"]} {kind}',
                            case['maturity']['period_end'], fact['presence'],
                            fact.get('ixbrl_tag') or '',
                            fact.get('context_ref') or
                            fact.get('row_sha256') or '',
                            case['source']['original_sec_url']]
                if actual != expected:
                    return False
                row += 1
        for key, srow, label in (
                ('filed_total_cost', 27, 'Filed maturity total cost'),
                ('filed_total_fair', 28, 'Filed maturity total fair value')):
            fact = case['maturity'][key]
            if (_text(source.get(f'A{srow}')) != label or
                    _num(source.get(f'C{srow}')).hex() !=
                    float(fact['value']).hex()):
                return False
            actual = [_text(lineage.get(f'{letter}{row}'))
                      for letter in 'ABCDEF']
            expected = [label, case['maturity']['period_end'],
                        fact['presence'], fact.get('ixbrl_tag') or '',
                        fact.get('context_ref') or
                        fact.get('row_sha256') or '',
                        case['source']['original_sec_url']]
            if actual != expected:
                return False
            row += 1
    driver_sheet = ('Plan scenario' if case['profile'] == 'pension_full'
                    else 'Rate scenario')
    driver_keys = (['sponsor_contribution', 'return_change',
                    'fx_shift', 'obligation_change']
                   if case['profile'] == 'pension_full' else
                   ['years_two_five_haircut', 'after_ten_haircut',
                    'no_single_date_haircut'])
    return all(_num(seed[driver_sheet].get(f'B{row}')).hex() ==
               float(case['scenario'][key]).hex()
               for row, key in enumerate(driver_keys, 5))


def _counterfactuals(case: dict) -> list[tuple[dict, dict, dict]]:
    f = lambda period, key: _fact(case, period, key, {})
    if case['profile'] == 'pension_full':
        return [
            ({(1, 'opening_assets'): f(1, 'opening_assets') + 17}, {}, {}),
            ({(1, 'return'): f(1, 'return') + 19}, {}, {}),
            ({(1, 'employer'): f(1, 'employer') + 23}, {}, {}),
            ({(1, 'participant'): f(1, 'participant') + 29}, {}, {}),
            ({(1, 'fx_or_other'): f(1, 'fx_or_other') + 31}, {}, {}),
            ({(1, 'benefits'): f(1, 'benefits') + 37}, {}, {}),
            ({(1, 'settlements_or_other'):
              f(1, 'settlements_or_other') + 41}, {}, {}),
            ({(1, 'closing_assets'): f(1, 'closing_assets') + 43}, {}, {}),
            ({(1, 'obligation'): f(1, 'obligation') + 47}, {}, {}),
            ({}, {}, {'sponsor_contribution':
                      case['scenario']['sponsor_contribution'] + 53}),
            ({}, {}, {'return_change':
                      case['scenario']['return_change'] + .003}),
            ({}, {}, {'fx_shift': case['scenario']['fx_shift'] + 13}),
            ({}, {}, {'obligation_change':
                      case['scenario']['obligation_change'] + .005}),
        ]
    return [
        ({(1, 'amortized_cost'): f(1, 'amortized_cost') + 17}, {}, {}),
        ({(1, 'acl_signed'): f(1, 'acl_signed') + 3}, {}, {}),
        ({(1, 'unrealized_gains'):
          f(1, 'unrealized_gains') + 19}, {}, {}),
        ({(1, 'unrealized_losses_signed'):
          f(1, 'unrealized_losses_signed') + 23}, {}, {}),
        ({(1, 'fair_value'): f(1, 'fair_value') + 29}, {}, {}),
        ({(1, 'loss_age_lt_fair'):
          f(1, 'loss_age_lt_fair') + 31}, {}, {}),
        ({(1, 'loss_age_ge_fair'):
          f(1, 'loss_age_ge_fair') + 37}, {}, {}),
        ({(1, 'loss_age_lt_loss'):
          f(1, 'loss_age_lt_loss') + 41}, {}, {}),
        ({(1, 'loss_age_ge_loss'):
          f(1, 'loss_age_ge_loss') + 43}, {}, {}),
        ({}, {'cost_1': _maturity(case, 'cost_1', {}) + 47}, {}),
        ({}, {'fair_1': _maturity(case, 'fair_1', {}) + 53}, {}),
        ({}, {'filed_total_fair':
              _maturity(case, 'filed_total_fair', {}) + 59}, {}),
        ({}, {}, {'years_two_five_haircut':
                  case['scenario']['years_two_five_haircut'] + .01}),
        ({}, {}, {'after_ten_haircut':
                  case['scenario']['after_ten_haircut'] + .01}),
        ({}, {}, {'no_single_date_haircut':
                  case['scenario']['no_single_date_haircut'] + .01}),
    ]


def _target_values(candidate: dict, case: dict, *,
                   source_changes: dict, maturity_changes: dict,
                   driver_changes: dict) -> list[str]:
    expected = expected_values(case,
                               source_changes=source_changes,
                               maturity_changes=maturity_changes,
                               driver_changes=driver_changes)
    overrides = {}
    keys = PENSION_KEYS if case['profile'] == 'pension_full' else AFS_KEYS
    for (period, key), value in source_changes.items():
        row = keys.index(key) + 5
        overrides[('Source facts',
                   f'{"B" if period == 0 else "C"}{row}')] = value
    for key, value in maturity_changes.items():
        if key == 'filed_total_cost':
            row = 27
        elif key == 'filed_total_fair':
            row = 28
        else:
            kind, number = key.rsplit('_', 1)
            row = (16 if kind == 'cost' else 21) + int(number)
        overrides[('Source facts', f'C{row}')] = value
    sheet = 'Plan scenario' if case['profile'] == 'pension_full' else 'Rate scenario'
    drivers = (['sponsor_contribution', 'return_change',
                'fx_shift', 'obligation_change']
               if case['profile'] == 'pension_full' else
               ['years_two_five_haircut', 'after_ten_haircut',
                'no_single_date_haircut'])
    for row, key in enumerate(drivers, 5):
        if key in driver_changes:
            overrides[(sheet, f'B{row}')] = driver_changes[key]
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
    targets = PENSION_TARGETS if profile == 'pension_full' else AFS_TARGETS
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
        errors += _target_values(current, case, source_changes={},
                                 maturity_changes={}, driver_changes={})
        baseline = expected_values(case)
        witnesses = set()
        replays = _counterfactuals(case)
        for source_changes, maturity_changes, driver_changes in replays:
            changed = expected_values(case,
                                      source_changes=source_changes,
                                      maturity_changes=maturity_changes,
                                      driver_changes=driver_changes)
            witnesses.update(key for key in targets
                             if not _close(changed[key], baseline[key]))
            errors += _target_values(current, case,
                                     source_changes=source_changes,
                                     maturity_changes=maturity_changes,
                                     driver_changes=driver_changes)
        if witnesses != targets:
            errors.append('counterfactual_target_dependency_coverage_incomplete')
        count = 3 if profile == 'pension_full' else 6
        for row in range(5, 5 + count):
            if not _close(saved.cell('Checks', f'B{row}'), 0):
                errors.append(f'source_or_scenario_reconciliation_failed:{row}')
    except Exception as exc:
        errors.append(f'verification_error:{type(exc).__name__}:{exc}')
    return {'pass': not errors, 'errors': errors[:30],
            'checked_targets': len(targets),
            'counterfactual_replays': len(_counterfactuals(case)),
            'source_only_offline_train': True,
            'excel_web_gui_admissions': 0,
            'official_final_admissions': 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('candidate', type=Path)
    ap.add_argument('seed', type=Path)
    ap.add_argument('review', type=Path)
    ap.add_argument('--case-index', type=int, required=True)
    args = ap.parse_args()
    review = json.loads(args.review.read_bytes())
    if review.get('schema') != \
            'envloop.sec_excel_train_remaining_four_review.private.v1':
        raise ValueError('private_review_schema_changed')
    cases = [c for c in review['cases'] if c['case_index'] == args.case_index]
    if len(cases) != 1:
        raise ValueError('private_train_case_not_unique')
    result = verify(args.candidate, args.seed, cases[0])
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
