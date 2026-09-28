"""Evaluator-only WDI PowerPoint selection scorer for saved Office PPTX bytes.

The three selected text targets come from the frozen WDI task specification.
The independent OOXML verifier derives numeric answers from pinned WDI facts,
checks seven slides and the native chart/workbook, and rejects unrelated edits.
An application-normalized baseline and private positive/near/collateral controls
are required before a model rollout. No oracle content enters model prompts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ppt_wdi_factory import plan, verify as ppt_verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


CALIBRATION_SCHEMA = 'cua-ppt-wdi-selection-calibration-v1'
SCORE_SCHEMA = 'cua-ppt-wdi-selection-saved-score-v1'
NEUTRAL_SCHEMA = 'cua-ppt-wdi-selection-neutral-v1'


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _require(value: bool, code: str) -> None:
    if not value:
        raise ValueError(code)


def exact_case(path: Path, task_id: str) -> dict:
    raw = Path(path).read_bytes()
    _require(0 < len(raw) <= 2_000_000,
             'ppt_selection_task_spec_size_invalid')
    try:
        task = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('ppt_selection_task_spec_invalid_json') from None
    _require(type(task) is dict and
             task.get('schema') == plan.SCHEMA and
             task.get('split') == 'selection' and
             task.get('task_id') == task_id and
             task.get('workflow') in plan.WORKFLOWS[:8] and
             task.get('target_keys') ==
                 ['summary', 'ledger', 'interpretation'] and
             task.get('official_final_credit') == 0,
             'ppt_selection_task_not_exact_three_target_wdi')
    return task


def _freeze(baseline: Path, case: dict) -> dict:
    oracle = ppt_verify.freeze(baseline, case,
                               office_web_normalized=True)
    _require(oracle.get('task_id') == case['task_id'] and
             oracle.get('office_web_normalized') is True and
             set(oracle.get('targets', {})) ==
                 {'summary', 'ledger', 'interpretation'} and
             oracle.get('source_sha256') == _sha(baseline.read_bytes()),
             'ppt_selection_normalized_baseline_oracle_changed')
    return oracle


def _scored(baseline: Path, candidate: Path, oracle: dict) -> dict:
    result = ppt_verify.verify(baseline, candidate, oracle)
    _require(type(result) is dict and
             result.get('status') in {'scored', 'infrastructure_error'},
             'ppt_selection_verifier_result_invalid')
    if result['status'] == 'infrastructure_error':
        return {'status': 'invalid_source_or_verifier',
                'score': None, 'verifier_result': result}
    _require(type(result.get('score')) in (int, float) and
             result['score'] in (0, 0.0, 1, 1.0) and
             type(result.get('target_correct')) is bool and
             type(result.get('preservation_pass')) is bool and
             type(result.get('per_target')) is dict and
             set(result['per_target']) == set(oracle['targets']) and
             type(result.get('unexpected_parts')) is list,
             'ppt_selection_verifier_result_invalid')
    return {'status': 'scored', 'score': int(result['score']),
            'verifier_result': result}


def score(candidate: Path, baseline: Path, case: dict) -> dict:
    oracle = _freeze(baseline, case)
    result = _scored(baseline, candidate, oracle)
    return {
        'schema': SCORE_SCHEMA,
        'status': result['status'],
        'score': result['score'],
        'task_id': case['task_id'],
        'workflow': case['workflow'],
        'target_count': 3,
        'baseline_sha256': _sha(baseline.read_bytes()),
        'candidate_sha256': _sha(candidate.read_bytes()),
        'oracle_sha256': _sha(_canonical(oracle)),
        'target_correct': result['verifier_result'].get('target_correct'),
        'preservation_pass': result['verifier_result'].get(
            'preservation_pass'),
        'unexpected_part_count': len(result['verifier_result'].get(
            'unexpected_parts', [])),
        'per_target': result['verifier_result'].get('per_target'),
        'native_chart_and_workbook_preserved': (
            result['status'] == 'scored' and
            result['verifier_result']['preservation_pass'] and
            result['verifier_result']['unexpected_parts'] == []),
    }


def neutral(baseline: Path, candidate: Path, case: dict) -> dict:
    scored = score(candidate, baseline, case)
    per_target = scored['per_target']
    equivalent = (scored['status'] == 'scored' and
                  scored['score'] == 0 and
                  scored['preservation_pass'] is True and
                  scored['unexpected_part_count'] == 0 and
                  type(per_target) is dict and len(per_target) == 3 and
                  all(row.get('changed') is False for row in
                      per_target.values()))
    return {'schema': NEUTRAL_SCHEMA,
            'equivalent': equivalent,
            'task_id': case['task_id'],
            'baseline_sha256': scored['baseline_sha256'],
            'candidate_sha256': scored['candidate_sha256'],
            'oracle_sha256': scored['oracle_sha256'],
            'target_count': 3,
            'preservation_pass': scored['preservation_pass'],
            'unexpected_part_count': scored['unexpected_part_count'],
            'changed_target_count': (
                sum(bool(row.get('changed')) for row in
                    per_target.values()) if type(per_target) is dict else None),
            'native_chart_and_workbook_preserved':
                scored['native_chart_and_workbook_preserved']}


def calibrate(baseline: Path, positive: Path, near_miss: Path,
              collateral: Path, case: dict, source: Path) -> dict:
    _require(_sha(source.read_bytes()) != _sha(baseline.read_bytes()),
             'ppt_selection_office_normalization_not_observed')
    source_semantics = semantic_source_equal(source, baseline)
    _require(source_semantics.get('slide_count') == 7 and
             source_semantics.get('slide_text_equal') is True and
             source_semantics.get('embedded_workbook_members_equal') is True and
             source_semantics.get('native_chart_cache_semantically_equal')
                 is True,
             'ppt_selection_source_to_office_baseline_changed')
    oracle = _freeze(baseline, case)
    baseline_result = _scored(baseline, baseline, oracle)
    good = _scored(baseline, positive, oracle)
    partial = _scored(baseline, near_miss, oracle)
    damaged = _scored(baseline, collateral, oracle)
    baseline_targets = baseline_result['verifier_result'].get('per_target')
    partial_targets = partial['verifier_result'].get('per_target')
    _require(baseline_result['status'] == good['status'] ==
             partial['status'] == damaged['status'] == 'scored' and
             baseline_result['score'] == 0 and
             baseline_result['verifier_result']['preservation_pass'] is True and
             type(baseline_targets) is dict and
             all(row.get('changed') is False for row in
                 baseline_targets.values()) and
             good['score'] == 1 and
             good['verifier_result']['target_correct'] is True and
             good['verifier_result']['preservation_pass'] is True and
             partial['score'] == 0 and
             partial['verifier_result']['preservation_pass'] is True and
             type(partial_targets) is dict and
             0 < sum(bool(row.get('changed')) for row in
                     partial_targets.values()) < 3 and
             damaged['score'] == 0 and
             damaged['verifier_result']['preservation_pass'] is False and
             damaged['verifier_result']['target_correct'] is True,
             'ppt_selection_positive_partial_collateral_calibration_failed')
    return {'schema': CALIBRATION_SCHEMA,
            'task_id': case['task_id'],
            'workflow': case['workflow'],
            'target_count': 3,
            'baseline_sha256': _sha(baseline.read_bytes()),
            'source_sha256': _sha(source.read_bytes()),
            'source_semantics_sha256': _sha(_canonical(source_semantics)),
            'positive_sha256': _sha(positive.read_bytes()),
            'near_miss_sha256': _sha(near_miss.read_bytes()),
            'collateral_sha256': _sha(collateral.read_bytes()),
            'oracle_sha256': _sha(_canonical(oracle)),
            'baseline_neutral': True,
            'positive_passed': True,
            'near_miss_rejected': True,
            'collateral_rejected': True,
            'native_chart_and_workbook_checked': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True,
                        choices=('calibrate', 'score', 'neutral'))
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--positive', type=Path)
    parser.add_argument('--near-miss', type=Path)
    parser.add_argument('--collateral', type=Path)
    args = parser.parse_args()
    try:
        case = exact_case(args.task, args.task_id)
        if args.mode == 'calibrate':
            _require(all(path is not None for path in (
                args.source, args.positive, args.near_miss,
                args.collateral)),
                'ppt_selection_calibration_controls_required')
            result = calibrate(args.baseline, args.positive,
                               args.near_miss, args.collateral, case,
                               args.source)
        else:
            _require(args.candidate is not None,
                     'ppt_selection_candidate_required')
            result = (score(args.candidate, args.baseline, case)
                      if args.mode == 'score' else
                      neutral(args.baseline, args.candidate, case))
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result.get('score', int(result.get(
            'equivalent', True))) in (1, True) else 1)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({'status': 'refused',
                          'reason_code': str(exc)[:256]}))
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
