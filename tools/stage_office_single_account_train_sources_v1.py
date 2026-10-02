"""Offline stage one active v13 PPT and SEC integrated Excel train source.

Only source-equal actor/reset upload copies are created. Task specifications,
known positives and reference answers remain in a separate evaluator subtree.
This script makes no Microsoft, browser, Graph, E2B or model request and never
prints a task ID or answer. The resulting private stage is not an admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from ppt_wdi_factory import plan as ppt_plan, verify as ppt_verify
from tools import sec_excel_web_train_oracle_v1 as excel_oracle


SCHEMA = 'cua-office-single-account-first-train-stage-v1'
_SAFE = re.compile(r'[A-Za-z0-9_.:-]{4,160}\Z')


class StageError(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise StageError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else
                           raw.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _write(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require(not path.exists() and not path.is_symlink(),
             'office_train_stage_output_already_exists')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(raw)


def _copy(path: Path, target: Path) -> str:
    _require(path.is_file() and not path.is_symlink() and
             path.stat().st_size > 0,
             'office_train_stage_source_missing')
    return _write(target, path.read_bytes())


def _ppt_source(root: Path) -> dict:
    _require(root.name == 'ppt-revised-seven-reserves-v13',
             'office_train_ppt_active_v13_required')
    plan_path = root / 'candidate-plan.private.json'
    receipt_path = root / 'seventh-reserve-receipt.private.json'
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    receipt = json.loads(receipt_path.read_bytes())
    _require(plan.get('schema') == ppt_plan.SCHEMA and
             type(plan.get('sets')) is dict and
             type(plan['sets'].get('train')) is list and
             len(plan['sets']['train']) == 20 and
             receipt.get('schema') ==
                 'envloop-ppt-wdi-seventh-reserve-private-v1' and
             receipt.get('revised_plan_sha256') == _sha(plan_raw) and
             receipt.get('final_candidate_count') == 100 and
             receipt.get('model_calls') == 0 and
             receipt.get('official_final_admitted') == 0,
             'office_train_ppt_v13_plan_or_receipt_changed')
    task = plan['sets']['train'][0]
    task_id = task.get('task_id')
    _require(type(task_id) is str and _SAFE.fullmatch(task_id) and
             task.get('split') == 'train' and
             task.get('official_final_credit') == 0 and
             task.get('target_keys') == ['summary'],
             'office_train_ppt_task_split_changed')
    package = root / 'packages' / 'train' / task_id
    task_path = package / 'task.private.json'
    source = package / 'source.pptx'
    positive = package / 'controls' / 'positive.pptx'
    _require(task_path.read_bytes() == ppt_plan.canonical(task),
             'office_train_ppt_task_bytes_changed')
    oracle = ppt_verify.freeze(source, task)
    baseline_score = ppt_verify.verify(source, source, oracle)
    positive_score = ppt_verify.verify(source, positive, oracle)
    _require(baseline_score.get('status') == 'scored' and
             baseline_score.get('score') == 0 and
             positive_score.get('status') == 'scored' and
             positive_score.get('score') == 1 and
             positive_score.get('preservation_pass') is True,
             'office_train_ppt_source_positive_control_failed')
    return {'task_id': task_id, 'task_path': task_path,
            'source_path': source, 'positive_path': positive,
            'plan_sha256': _sha(plan_raw),
            'ratified_train_split': True}


def _excel_source(root: Path) -> dict:
    _require(root.name == 'sec-integrated',
             'office_train_excel_integrated_root_required')
    cases_path = root / 'cases.json'
    raw = cases_path.read_bytes()
    cases = json.loads(raw)
    _require(type(cases) is list and len(cases) == 140 and
             {split: sum(row.get('split') == split for row in cases)
              for split in ('train_candidate', 'selection_candidate',
                            'final_candidate')} == {
                 'train_candidate': 20,
                 'selection_candidate': 20,
                 'final_candidate': 100},
             'office_train_excel_integrated_split_changed')
    case = next(row for row in cases if
                row.get('split') == 'train_candidate')
    case_id = case.get('case_id')
    _require(type(case_id) is str and _SAFE.fullmatch(case_id) and
             type(case.get('source_package')) is dict and
             case['source_package'].get('schema') ==
                 'sec-integrated-source-package-v1',
             'office_train_excel_source_case_invalid')
    package = root / 'workbooks' / 'train_candidate' / case_id
    source = package / 'actor.xlsx'
    positive = package / 'reference.xlsx'
    _require(source.is_file() and positive.is_file() and
             (package / 'task.md').is_file(),
             'office_train_excel_workbook_or_instruction_missing')
    negative_score = excel_oracle.sec_verify(source, source, case)
    positive_score = excel_oracle.sec_verify(positive, source, case)
    _require(negative_score.get('pass') is False and
             positive_score.get('pass') is True and
             positive_score.get('checked_targets', 0) >= 20 and
             positive_score.get('counterfactual_profiles') == 2 and
             positive_score.get('errors') == [],
             'office_train_excel_source_positive_control_failed')
    instruction = (package / 'task.md').read_text().strip()
    _require(0 < len(instruction.encode()) <= 8192,
             'office_train_excel_instruction_invalid')
    task_id = 'xl-train-' + _sha(case_id + _sha(source.read_bytes()))[:16]
    task = {
        'schema': 'excel-web-original-train-package-v1',
        'split': 'train', 'official_final_credit': 0,
        'task_id': task_id, 'actor_task': instruction,
        'actor_xlsx_sha256': _sha(source.read_bytes()),
    }
    return {'task_id': task_id, 'task': task,
            'source_path': source, 'positive_path': positive,
            'case': case, 'case_manifest_sha256': _sha(raw),
            'ratified_train_split': True}


def stage(*, ppt_root: Path, excel_root: Path,
          output: Path) -> dict:
    """Write one private source-bound pair per cell, or fail before output."""
    ppt = _ppt_source(Path(ppt_root))
    excel = _excel_source(Path(excel_root))
    output = Path(output).absolute()
    _require(not output.exists() and not output.is_symlink(),
             'office_train_stage_fresh_output_required')
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    ppt_base = output / 'powerpoint-web'
    ppt_eval = (ppt_base / 'evaluator' / 'packages' / 'train' /
                ppt['task_id'])
    ppt_actor = ppt_base / 'upload-actor' / 'EL-PPT-Train-Actor.pptx'
    ppt_reset = ppt_base / 'upload-reset' / 'EL-PPT-Train-Reset.pptx'
    ppt_sha = _copy(ppt['source_path'], ppt_actor)
    _require(_copy(ppt['source_path'], ppt_reset) == ppt_sha,
             'office_train_ppt_actor_reset_bytes_differ')
    _copy(ppt['task_path'], ppt_eval / 'task.private.json')
    _copy(ppt['source_path'], ppt_eval / 'source.pptx')
    _copy(ppt['positive_path'], ppt_eval / 'controls' /
          'positive.private.pptx')
    excel_base = output / 'excel-web'
    excel_eval = (excel_base / 'evaluator' / 'packages' / 'train' /
                  excel['task_id'])
    excel_actor = (excel_base / 'upload-actor' /
                   'EL-Excel-Train-Actor.xlsx')
    excel_reset = (excel_base / 'upload-reset' /
                   'EL-Excel-Train-Reset.xlsx')
    excel_sha = _copy(excel['source_path'], excel_actor)
    _require(_copy(excel['source_path'], excel_reset) == excel_sha,
             'office_train_excel_actor_reset_bytes_differ')
    _write(excel_eval / 'task.private.json',
           _canonical(excel['task']))
    _copy(excel['source_path'], excel_eval / 'actor.xlsx')
    _copy(excel['positive_path'], excel_base /
          'evaluator' / 'reference.private.xlsx')
    _write(excel_base / 'evaluator' /
           'one-case.private.json',
           _canonical([excel['case']]))
    receipt = {
        'schema': SCHEMA,
        'status': 'staged_private_train_sources_no_cloud_calls',
        'powerpoint': {
            'task_id': ppt['task_id'],
            'source_plan_sha256': ppt['plan_sha256'],
            'actor_sha256': ppt_sha,
            'reset_sha256': _sha(ppt_reset.read_bytes()),
            'evaluator_task_sha256':
                _sha((ppt_eval / 'task.private.json').read_bytes()),
            'evaluator_positive_sha256':
                _sha((ppt_eval / 'controls' /
                      'positive.private.pptx').read_bytes()),
            'active_v13': True,
        },
        'excel': {
            'task_id': excel['task_id'],
            'source_case_manifest_sha256':
                excel['case_manifest_sha256'],
            'actor_sha256': excel_sha,
            'reset_sha256': _sha(excel_reset.read_bytes()),
            'evaluator_task_sha256':
                _sha((excel_eval / 'task.private.json').read_bytes()),
            'evaluator_reference_sha256':
                _sha((excel_base / 'evaluator' /
                      'reference.private.xlsx').read_bytes()),
            'train_candidate_split': True,
        },
        'cloud_calls': 0, 'model_calls': 0,
        'official_selection_credit': 0,
        'official_final_credit': 0,
    }
    _write(output / 'stage-receipt.private.json',
           _canonical(receipt))
    return {
        'status': 'two_private_train_pairs_staged',
        'cell_count': 2,
        'actor_reset_byte_identical_per_cell': True,
        'receipt_sha256': _sha(
            (output / 'stage-receipt.private.json').read_bytes()),
        'cloud_calls': 0, 'model_calls': 0,
        'official_final_credit': 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ppt-v13-root', type=Path, required=True)
    parser.add_argument('--excel-integrated-root', type=Path,
                        required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = stage(ppt_root=args.ppt_v13_root,
                       excel_root=args.excel_integrated_root,
                       output=args.out)
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'refused',
                          'reason_type': type(exc).__name__,
                          'reason_code': str(exc) if isinstance(
                              exc, StageError) else None,
                          'cloud_calls': 0,
                          'official_final_credit': 0},
                         sort_keys=True))
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
