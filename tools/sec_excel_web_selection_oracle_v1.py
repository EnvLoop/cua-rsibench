"""Evaluator-only SEC integrated selection workbook scorer.

One original `selection_candidate` case, pinned SEC source facts and a separate
reference workbook calibrate this scorer before any Qwen rollout. A saved Excel
file earns 1 only when the independent verifier accepts formulas, numeric
dependencies under two counterfactual profiles, and no unrelated state edit.
Valid actor mistakes score 0; missing source/oracle evidence is invalid, not 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools import sec_excel_web_train_oracle_v1 as train_oracle


SCHEMA = 'cua-sec-integrated-selection-saved-score-v1'
CALIBRATION_SCHEMA = 'cua-sec-integrated-selection-oracle-calibration-v1'
NEUTRAL_SCHEMA = 'cua-sec-integrated-selection-neutral-v1'


def _require(value: bool, code: str) -> None:
    if not value:
        raise ValueError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def one_selection_case(path: Path, expected_case_id: str) -> dict:
    raw = path.read_bytes()
    _require(0 < len(raw) <= 8_000_000,
             'sec_selection_case_manifest_size_invalid')
    try:
        rows = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('sec_selection_case_manifest_invalid_json') from None
    _require(type(rows) is list and len(rows) == 1 and
             type(rows[0]) is dict and
             rows[0].get('split') == 'selection_candidate' and
             rows[0].get('case_id') == expected_case_id and
             type(rows[0].get('source_package')) is dict and
             rows[0]['source_package'].get('schema') ==
             'sec-integrated-source-package-v1',
             'sec_selection_case_not_exact_original_selection_candidate')
    return rows[0]


def score(candidate: Path, seed: Path, case: dict) -> dict:
    raw = train_oracle.sec_verify(candidate, seed, case)
    _require(type(raw) is dict and type(raw.get('pass')) is bool and
             type(raw.get('checked_targets')) is int and
             type(raw.get('counterfactual_profiles')) is int and
             type(raw.get('errors')) is list,
             'sec_selection_oracle_result_invalid')
    invalid_source = any(type(error) is str and
                         error.startswith('oracle_setup:')
                         for error in raw['errors'])
    preservation_errors = tuple(
        error for error in raw['errors'] if type(error) is str and
        (error.startswith('non_target_cell_changed:') or
         error in {'sheet_identity_or_order_changed',
                   'table_or_sheet_structure_changed'}))
    return {
        'schema': SCHEMA,
        'status': 'invalid_source_or_verifier' if invalid_source else 'scored',
        'score': None if invalid_source else int(raw['pass']),
        'checked_formula_targets': raw['checked_targets'],
        'source_counterfactual_profiles': raw['counterfactual_profiles'],
        'error_count': len(raw['errors']),
        'preservation_pass': None if invalid_source else not preservation_errors,
        'non_target_or_structure_error_count': len(preservation_errors),
        'candidate_sha256': _sha(candidate.read_bytes()),
        'seed_sha256': _sha(seed.read_bytes()),
        'case_sha256': _sha(json.dumps(case, sort_keys=True,
                                        separators=(',', ':')).encode()),
        'native_recalculation_verified': False,
    }


def calibrate(seed: Path, reference: Path, case: dict) -> dict:
    unsolved = score(seed, seed, case)
    positive = score(reference, seed, case)
    _require(unsolved['status'] == positive['status'] == 'scored' and
             unsolved['score'] == 0 and positive['score'] == 1 and
             positive['checked_formula_targets'] >= 30 and
             positive['source_counterfactual_profiles'] == 2 and
             positive['error_count'] == 0,
             'sec_selection_positive_negative_calibration_failed')
    return {'schema': CALIBRATION_SCHEMA,
            'unsolved_seed_rejected': True,
            'positive_reference_passed': True,
            'checked_formula_targets': positive['checked_formula_targets'],
            'source_counterfactual_profiles': 2,
            'seed_sha256': _sha(seed.read_bytes()),
            'reference_sha256': _sha(reference.read_bytes()),
            'case_sha256': positive['case_sha256']}


def neutral(seed: Path, candidate: Path) -> dict:
    result = train_oracle.neutral(seed, candidate)
    return {**result, 'schema': NEUTRAL_SCHEMA}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('calibrate', 'score', 'neutral'),
                        required=True)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--case-id')
    args = parser.parse_args()
    try:
        if args.mode == 'neutral':
            _require(args.candidate is not None,
                     'selection_neutral_candidate_required')
            result = neutral(args.seed, args.candidate)
        else:
            _require(args.cases is not None and args.case_id is not None,
                     'selection_case_required')
            case = one_selection_case(args.cases, args.case_id)
            if args.mode == 'calibrate':
                _require(args.reference is not None,
                         'selection_reference_required')
                result = calibrate(args.seed, args.reference, case)
            else:
                _require(args.candidate is not None,
                         'selection_candidate_required')
                result = score(args.candidate, args.seed, case)
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result.get('score',
                                        int(result.get('equivalent', True)))
                         in (1, True) else 1)
    except ValueError as exc:
        print(json.dumps({'status': 'refused', 'reason_code': str(exc)}))
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
