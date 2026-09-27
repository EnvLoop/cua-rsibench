"""Independent SEC-integrated train workbook score and neutral-state check.

The private one-case manifest must be a `train_candidate`. The scorer imports
the filing-pinned evaluator, never a workbook builder or teacher transcript.
It checks formula dependencies under two counterfactual profiles and preserves
all non-target cells. Cached values are checked when present; this does not
claim that Excel's recalculation engine ran after the download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sec_excel_factory'
sys.path.insert(0, str(SOURCE))

from verify_integrated_candidate import verify as sec_verify  # noqa: E402
from verify_ooxml import load_xlsx, unchanged_cell  # noqa: E402


class ExcelOracleError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise ExcelOracleError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def one_train_case(path: Path, expected_case_id: str) -> dict:
    raw = path.read_bytes()
    _require(0 < len(raw) <= 8_000_000,
             'sec_train_case_manifest_size_invalid')
    try:
        rows = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ExcelOracleError('sec_train_case_manifest_invalid_json') from None
    _require(type(rows) is list and len(rows) == 1 and
             type(rows[0]) is dict and
             rows[0].get('split') == 'train_candidate' and
             rows[0].get('case_id') == expected_case_id and
             type(rows[0].get('source_package')) is dict and
             rows[0]['source_package'].get('schema') ==
             'sec-integrated-source-package-v1',
             'sec_train_case_not_exact_original_train_candidate')
    return rows[0]


def score(candidate: Path, seed: Path, case: dict) -> dict:
    result = sec_verify(candidate, seed, case)
    _require(type(result) is dict and type(result.get('pass')) is bool and
             type(result.get('checked_targets')) is int and
             type(result.get('counterfactual_profiles')) is int and
             type(result.get('errors')) is list,
             'sec_saved_oracle_result_invalid')
    return {
        'schema': 'cua-sec-integrated-train-saved-score-v1',
        'artifact_pass': result['pass'],
        'checked_formula_targets': result['checked_targets'],
        'source_counterfactual_profiles': result['counterfactual_profiles'],
        'error_count': len(result['errors']),
        'candidate_sha256': _sha(candidate.read_bytes()),
        'seed_sha256': _sha(seed.read_bytes()),
        'case_sha256': _sha(json.dumps(case, sort_keys=True,
                                        separators=(',', ':')).encode()),
        'native_recalculation_verified': False,
    }


def neutral(source: Path, candidate: Path) -> dict:
    initial, order, tables, structure = load_xlsx(source)
    restored, restored_order, restored_tables, restored_structure = load_xlsx(
        candidate)
    structure_pass = (order == restored_order and
                      tables == restored_tables and
                      structure == restored_structure)
    changed = 0
    cell_count = 0
    for sheet in order:
        before = initial.get(sheet, {})
        after = restored.get(sheet, {})
        for address in set(before) | set(after):
            cell_count += 1
            if (address not in before or address not in after or
                    not unchanged_cell(before[address], after[address])):
                changed += 1
    return {
        'schema': 'cua-sec-integrated-train-neutral-v1',
        'equivalent': structure_pass and changed == 0,
        'structure_pass': structure_pass,
        'cell_count': cell_count,
        'changed_cell_count': changed,
        'source_sha256': _sha(source.read_bytes()),
        'candidate_sha256': _sha(candidate.read_bytes()),
    }


def calibrate(seed: Path, reference: Path, case: dict) -> dict:
    unsolved = score(seed, seed, case)
    positive = score(reference, seed, case)
    _require(unsolved['artifact_pass'] is False and
             positive['artifact_pass'] is True and
             positive['checked_formula_targets'] >= 20 and
             positive['source_counterfactual_profiles'] == 2 and
             positive['error_count'] == 0,
             'sec_train_oracle_positive_negative_calibration_failed')
    return {'schema': 'cua-sec-integrated-train-oracle-calibration-v1',
            'unsolved_seed_rejected': True,
            'positive_reference_passed': True,
            'checked_formula_targets': positive['checked_formula_targets'],
            'source_counterfactual_profiles': 2,
            'seed_sha256': _sha(seed.read_bytes()),
            'reference_sha256': _sha(reference.read_bytes()),
            'case_sha256': positive['case_sha256']}


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
                     'neutral_candidate_required')
            result = neutral(args.seed, args.candidate)
        else:
            _require(args.cases is not None and args.case_id is not None,
                     'sec_train_case_required')
            case = one_train_case(args.cases, args.case_id)
            if args.mode == 'calibrate':
                _require(args.reference is not None,
                         'sec_train_reference_required')
                result = calibrate(args.seed, args.reference, case)
            else:
                _require(args.candidate is not None,
                         'sec_saved_candidate_required')
                result = score(args.candidate, args.seed, case)
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result.get('artifact_pass',
                                        result.get('equivalent', True)) else 1)
    except ExcelOracleError as exc:
        print(json.dumps({'status': 'refused', 'reason_code': str(exc)}))
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
