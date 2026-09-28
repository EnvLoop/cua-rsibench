"""One real train-split GUI calibration before a clean Magento v3 final sweep.

The pilot uses the original application, two fresh app/search pairs, the new
release guard, independent saved-state scoring, and exact cold-reset checks.
It never accesses a final candidate or grants final admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from tools import magento_cron_runtime_contract_v1 as old_contract
from tools import magento_v3_runtime as runtime_gate
from tools import sweep_magento_original_gui_controls_v3 as sweep
from tools.freeze_magento_cron_runtime_v1 import PROBE_DIR, TRAIN_DIR


SCHEMA = 'envloop-magento-v3-release-guard-train-pilot-private-v1'
PUBLIC_SCHEMA = 'envloop-magento-v3-release-guard-train-pilot-public-v1'
RUN_DIR = ROOT / 'work/magento-original/v3-release-guard-train-pilot-20260928'
PRIVATE_RECEIPT = RUN_DIR / 'pilot.private.json'
PUBLIC_RECEIPT = ROOT / 'docs/evidence/magento-v3-release-guard-train-pilot-2026-09-28.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_new(path: Path, value: dict, mode: int) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def _train_case(plan: Path, plan_sha256: str) -> dict:
    require(sha(plan.read_bytes()) == plan_sha256, 'train pilot plan bytes changed')
    rows = json.loads(plan.read_bytes())['cases']['train_policy_development']
    require(len(rows) == 4 and len({row['task_id'] for row in rows}) == 4,
            'frozen train-only pilot source must have four distinct tasks')
    task = rows[0]
    require(task['split'] == 'train_policy_development' and
            load_case(plan, plan_sha256, task['task_id']) == task,
            'first train task changed or is not private train split')
    return task


def _case_dir() -> Path:
    return RUN_DIR / 'case-000'


def _audit_train_journal() -> dict:
    path = RUN_DIR / 'journal.private.jsonl'
    raw = path.read_bytes()
    require(raw.endswith(b'\n'), 'train pilot journal is incomplete')
    events = [json.loads(line) for line in raw.splitlines()]
    intents = [row.get('step') for row in events
               if row.get('event') == 'step_intent']
    finished = [row for row in events if row.get('event') == 'step_finished']
    cleanups = [row.get('pair') for row in events
                if row.get('event') == 'pair_cleanup_verified']
    calibrated = [row for row in events
                  if row.get('event') == 'task_gui_calibrated']
    require(intents == [row.get('step') for row in finished] ==
            list(old_contract.STEPS) and
            all(row.get('exit_code') == 0 for row in finished) and
            cleanups == ['positive', 'negative'] and
            len(calibrated) == 1 and
            not any(row.get('event') == 'step_timeout_uncertain'
                    for row in events),
            'train pilot lacks exact 1/0/reset process and cleanup sequence')
    return {'journal_sha256': sha(raw), 'completed_step_count': len(finished),
            'calibration_event': calibrated[0]}


def _read_controls(task: dict, plan_sha256: str,
                   runtime_sha256: str, source_sha256s: dict[str, str]) -> dict:
    journal = _audit_train_journal()
    base = _case_dir()
    calibration = json.loads((base / 'calibration.private.json').read_bytes())
    require(calibration.get('schema') ==
            'envloop-magento-original-gui-case-calibration-v3' and
            calibration.get('split') == 'train_policy_development' and
            calibration.get('task_id') == task['task_id'] and
            calibration.get('package_sha256') == task['package_sha256'] and
            calibration.get('positive_score') == 1.0 and
            calibration.get('wrong_variant_score') == 0.0 and
            calibration.get('fresh_reset_passed') is True and
            calibration.get('model_calls') == 0 and
            calibration.get('official_final_admitted') is False and
            journal['calibration_event'].get('task_id') == task['task_id'] and
            journal['calibration_event'].get('receipt_sha256') ==
            sha((base / 'calibration.private.json').read_bytes()),
            'train guard pilot lacks complete 1/0/fresh-reset control')
    journal.pop('calibration_event')
    views = []
    for pair, modes in (('positive', ('neutral', 'gui-positive')),
                        ('negative', ('neutral', 'gui-wrong-variant'))):
        for mode in modes:
            folder = base / pair / mode
            result_path = folder / 'result.json'
            raw = result_path.read_bytes()
            result = json.loads(raw)
            before = json.loads((folder / 'private-before.json').read_bytes())
            pre_edit = json.loads((folder / 'private-pre-edit.json').read_bytes())
            guard = result.get('quote', {}).get('release_modal_guard')
            require(result.get('task_id') == task['task_id'] and
                    result.get('mode') == ('wrong-variant' if mode == 'gui-wrong-variant'
                                           else 'positive' if mode == 'gui-positive'
                                           else 'neutral') and
                    result.get('pre_edit_sha256') ==
                    sha((folder / 'private-pre-edit.json').read_bytes()) and
                    pre_edit == before and
                    type(guard) is dict and
                    guard.get('obstruction_clear_before_business_edit') is True and
                    type(guard.get('release_mask_observed')) is bool and
                    type(guard.get('release_notification_modals_closed')) is int and
                    guard['release_notification_modals_closed'] >= 0 and
                    result.get('model_calls') ==
                    result.get('official_final_tasks_admitted') == 0,
                    'train GUI guard lacks exact no-regression pre-edit readback')
            views.append({'pair': pair, 'mode': mode,
                          'result_sha256': sha(raw),
                          'pre_edit_state_sha256': result['pre_edit_sha256'],
                          'release_mask_observed': guard['release_mask_observed'],
                          'release_notification_modals_closed':
                          guard['release_notification_modals_closed']})
    reset = json.loads((base / 'negative/fresh-reset.private.json').read_bytes())
    require(reset.get('fresh_clone_reset_passed') is True and
            reset.get('material_monitored_sql_and_search_state') is True and
            reset.get('different_container_ids') is True and
            reset.get('different_search_container_ids') is True and
            reset.get('official_final_tasks_admitted') == 0,
            'train pilot exact independent reset missing')
    return {'schema': SCHEMA,
            'status': 'one_train_original_gui_guard_and_saved_state_passed',
            'plan_sha256': plan_sha256,
            'train_task_id': task['task_id'],
            'package_sha256': task['package_sha256'],
            'runtime_receipt_sha256': runtime_sha256,
            'source_sha256s': source_sha256s,
            'calibration_sha256': sha((base / 'calibration.private.json').read_bytes()),
            'fresh_reset_sha256': sha((base / 'negative/fresh-reset.private.json').read_bytes()),
            **journal,
            'four_gui_views': views,
            'all_four_pre_edit_states_exact': True,
            'positive_saved_state_passed': True,
            'wrong_variant_rejected': True,
            'fresh_reset_passed': True,
            'release_obstruction_observed_in_train': any(
                row['release_mask_observed'] or
                row['release_notification_modals_closed'] > 0 for row in views),
            'model_calls': 0, 'official_final_admitted': 0}


def source_sha256s() -> dict[str, str]:
    names = ('tools/magento_v3_guard_train_pilot.py',
             'tools/sweep_magento_original_gui_controls_v3.py',
             'tools/qualify_magento_original_catalog_v3.py')
    return {name: sha((ROOT / name).read_bytes()) for name in names}


def run(*, plan: Path, plan_sha256: str, source: Path,
        parent_freeze: Path) -> dict:
    require(not RUN_DIR.exists() and not PRIVATE_RECEIPT.exists() and
            not PUBLIC_RECEIPT.exists(),
            'train guard pilot needs a fresh private run directory')
    _runtime, runtime_sha = runtime_gate.validate_receipt()
    old, parent_sha = old_contract.validate_freeze(
        parent_freeze, ROOT, PROBE_DIR, TRAIN_DIR)
    require(old['final_candidate_plan_sha256'] == plan_sha256,
            'train pilot parent runtime belongs to another frozen plan')
    task = _train_case(plan, plan_sha256)
    # All checks above, including a real local headless browser launch, occur
    # before the following first possible application clone creation.
    sweep.assert_absent()
    RUN_DIR.mkdir(mode=0o700)
    intent = {'schema': 'envloop-magento-v3-guard-train-pilot-intent-v1',
              'task_id': task['task_id'], 'package_sha256': task['package_sha256'],
              'plan_sha256': plan_sha256, 'parent_cron_freeze_sha256': parent_sha,
              'runtime_receipt_sha256': runtime_sha,
              'source_sha256s': source_sha256s(),
              'model_calls': 0, 'official_final_admitted': 0}
    intent_sha = _write_new(RUN_DIR / 'pilot-intent.private.json', intent, 0o600)
    journal = RUN_DIR / 'journal.private.jsonl'
    try:
        sweep.task(0, task, plan, plan_sha256, source, RUN_DIR, journal,
                   train_cron_never_autostart=True, cellwide_freeze=old)
        sweep.assert_absent()
        record = _read_controls(task, plan_sha256, runtime_sha,
                                intent['source_sha256s'])
        record['intent_sha256'] = intent_sha
        private_sha = _write_new(PRIVATE_RECEIPT, record, 0o600)
        public = {'schema': PUBLIC_SCHEMA,
                  'status': ('train_only_live_original_gui_guard_qualified_for_v3_freeze'
                             if record['release_obstruction_observed_in_train'] else
                             'train_gui_passed_without_release_obstruction_v3_freeze_closed'),
                  'private_pilot_sha256': private_sha,
                  'parent_cron_freeze_sha256': parent_sha,
                  'runtime_receipt_sha256': runtime_sha,
                  'source_sha256s': intent['source_sha256s'],
                  'gui_views': 4,
                  'all_four_pre_edit_states_exact': True,
                  'positive_saved_state_passed': True,
                  'wrong_variant_rejected': True,
                  'fresh_reset_passed': True,
                  'release_obstruction_observed_in_train':
                  record['release_obstruction_observed_in_train'],
                  'model_calls': 0, 'official_final_admitted': 0}
        _write_new(PUBLIC_RECEIPT, public, 0o644)
        return public
    except Exception:
        # A partially created pair stays for exact forensic reconciliation.
        # Never retry this train pilot or launch the final sweep automatically.
        raise


def validate_receipt(plan: Path, plan_sha256: str) -> tuple[dict, str]:
    require(PRIVATE_RECEIPT.is_file() and PUBLIC_RECEIPT.is_file(),
            'real_train_only_release_guard_pilot_required_before_v3_freeze')
    task = _train_case(plan, plan_sha256)
    raw = PRIVATE_RECEIPT.read_bytes()
    record = json.loads(raw)
    public = json.loads(PUBLIC_RECEIPT.read_bytes())
    runtime, runtime_sha = runtime_gate.validate_receipt()
    current = _read_controls(task, plan_sha256, runtime_sha, source_sha256s())
    intent, intent_sha = (json.loads((RUN_DIR / 'pilot-intent.private.json').read_bytes()),
                         sha((RUN_DIR / 'pilot-intent.private.json').read_bytes()))
    current['intent_sha256'] = intent_sha
    require(record == current and
            intent.get('source_sha256s') == current['source_sha256s'] and
            intent.get('runtime_receipt_sha256') == runtime_sha and
            public.get('schema') == PUBLIC_SCHEMA and
            public.get('private_pilot_sha256') == sha(raw) and
            public.get('gui_views') == 4 and
            public.get('all_four_pre_edit_states_exact') is True and
            public.get('positive_saved_state_passed') is True and
            public.get('wrong_variant_rejected') is True and
            public.get('fresh_reset_passed') is True and
            public.get('status') == (
                'train_only_live_original_gui_guard_qualified_for_v3_freeze'
                if record['release_obstruction_observed_in_train'] else
                'train_gui_passed_without_release_obstruction_v3_freeze_closed') and
            public.get('model_calls') == public.get('official_final_admitted') == 0,
            'train_guard_pilot_raw_gui_reset_or_source_changed')
    return record, sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'verify'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--parent-freeze', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action == 'run':
        require(args.execute and args.source is not None and
                args.parent_freeze is not None,
                'explicit_train_pilot_execute_and_frozen_inputs_required')
        result = run(plan=args.plan, plan_sha256=args.plan_sha256,
                     source=args.source, parent_freeze=args.parent_freeze)
    else:
        _record, digest = validate_receipt(args.plan, args.plan_sha256)
        result = {'status': 'train_only_original_gui_guard_receipt_revalidated',
                  'private_pilot_sha256': digest,
                  'model_calls': 0, 'official_final_admitted': 0}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
