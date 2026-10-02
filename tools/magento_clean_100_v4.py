"""Chunked, source-bound Magento v4 100-case evaluator GUI calibration.

This is a prospective pre-result amendment to the frozen v3 controller. It
uses the same v3 per-case original-GUI controls and starts at index zero in a
fresh v4 directory. Each invocation ends only after a complete case and a
verified cleanup; resume rechecks every completed case before a new one.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import IMAGE, load_case
from magento_catalog_factory.verify import (
    NATIVE_SEARCH_IMAGE, check_baseline, check_material_reset,
    read_snapshot,
)
from tools import magento_cron_runtime_contract_v1 as old_contract
from tools import sweep_magento_original_gui_controls_v3 as sweep_v3
from tools import magento_v3_runtime as runtime_gate
from tools import magento_v3_guard_train_pilot as guard_pilot
from tools import magento_clean_100_v3 as parent_v3
from tools import start_magento_native_sidecar_clone_v1 as clone
from tools.freeze_magento_cron_runtime_v1 import PROBE_DIR, TRAIN_DIR


SCHEMA = 'envloop-magento-clean-100-freeze-private-v4'
JOURNAL_SCHEMA = 'envloop-magento-clean-100-journal-private-v4'
RETRY_CAP = 20
PER_CASE_RETRY_CAP = 1
MAX_CHUNK_CASES = 5
CODE_FILES = ('tools/magento_clean_100_v3.py',
              'tools/magento_clean_100_v4.py',
              'tools/sweep_magento_original_gui_controls_v3.py',
              'tools/qualify_magento_original_catalog_v3.py',
              'tools/magento_v3_runtime.py',
              'tools/magento_v3_guard_train_pilot.py',
              'tools/audit_magento_cron_requalification_v1.py',
              'tools/start_magento_native_sidecar_clone_v1.py',
              'tools/finalize_magento_normalized_baseline_v1.py',
              'tools/capture_magento_native_runtime_v1.py',
              'tools/audit_magento_original_fresh_reset_v1.py',
              'magento_catalog_factory/seed.py',
              'magento_catalog_factory/verify.py')
LOCK = ROOT / 'work/magento-original/exclusive-worker.lock'
PUBLIC_FREEZE = ROOT / 'docs/evidence/magento-clean-100-v4-freeze-2026-09-29.json'
PRIVATE_FREEZE = ROOT / 'work/magento-original/clean-v4-freeze-20260929.private.json'
V3_FREEZE = ROOT / 'work/magento-original/clean-v3-freeze-20260928.private.json'
V4_RUN = ROOT / 'work/magento-original/clean-v4-100-20260929'
V2_RUN = ROOT / 'work/magento-original/cron-resumable-100-v2'
V2_RETIRED_PUBLIC = ROOT / 'docs/evidence/magento-v2-retry-runtime-retired-2026-09-28.json'
V2_RETIRED_PRIVATE = (V2_RUN / 'attempts/case-014-attempt-1/'
                      'operator-runtime-cleanup-receipt.private.json')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def private_new(path: Path, value: dict) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def read_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), sha(raw)


def read_journal(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    require(raw.endswith(b'\n'), 'truncated append-only journal')
    events = []
    prior = '0' * 64
    for number, line in enumerate(raw.splitlines()):
        event = json.loads(line)
        require(event.get('sequence') == number and
                event.get('previous_line_sha256') == prior and
                event.get('schema') == JOURNAL_SCHEMA,
                'Magento journal chain, schema, or sequence changed')
        events.append(event)
        prior = sha(line + b'\n')
    return events


def append_event(path: Path, event: dict) -> None:
    events = read_journal(path)
    prior = sha(encode(events[-1])) if events else '0' * 64
    row = {**event, 'schema': JOURNAL_SCHEMA,
           'sequence': len(events), 'previous_line_sha256': prior,
           'time': time.time()}
    raw = encode(row)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def case_identity_digest(cases: list[dict]) -> str:
    return sha(encode({'cases': [(case['task_id'], case['package_sha256'])
                                 for case in cases]}))


def validate_plan(plan: Path, digest: str) -> list[dict]:
    require(sha(plan.read_bytes()) == digest, 'final candidate plan bytes changed')
    cases = json.loads(plan.read_bytes())['cases']['official_candidate']
    require(len(cases) == 100 and
            len({row['task_id'] for row in cases}) == 100 and
            len({row['package_sha256'] for row in cases}) == 100 and
            all(load_case(plan, digest, row['task_id']) == row for row in cases),
            'exact 100 distinct frozen task packages required')
    return cases


def source_revision(source: Path) -> str:
    result = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                            check=True, capture_output=True, text=True, timeout=15)
    revision = result.stdout.strip()
    require(revision == sweep_v3.IMAGE_SOURCE_COMMIT,
            'Magento source revision changed')
    return revision


def retired_v2_binding(root: Path) -> dict:
    public_path = root / V2_RETIRED_PUBLIC.relative_to(ROOT)
    private_path = root / V2_RETIRED_PRIVATE.relative_to(ROOT)
    public_raw, private_raw = public_path.read_bytes(), private_path.read_bytes()
    public, private = json.loads(public_raw), json.loads(private_raw)
    require(public.get('schema') ==
            'envloop-magento-v2-retry-runtime-retired-public-v1' and
            public.get('status') ==
            'exhausted_v2_control_run_retired_before_new_full100' and
            public.get('completed_distinct_evaluator_controls') == 14 and
            public.get('failed_attempts_same_fifteenth_task') == 2 and
            public.get('all_disposable_pair_containers_absent') is True and
            public.get('third_same_id_retry_authorized') is False and
            public.get('new_full100_source_freeze_required') is True and
            public.get('private_cleanup_receipt_sha256') == sha(private_raw) and
            public.get('model_calls') == public.get('official_final_admitted') == 0 and
            private.get('schema') ==
            'envloop-magento-v2-attempt1-runtime-cleanup-receipt-v1' and
            private.get('both_containers_absent') is True and
            private.get('third_attempt_authorized') is False and
            private.get('model_calls') == private.get('official_final_admitted') == 0,
            'exhausted_v2_run_not_exactly_retired_before_clean_v3')
    return {'v2_retirement_public_sha256': sha(public_raw),
            'v2_retirement_private_sha256': sha(private_raw),
            'v2_stopped_journal_sha256': public['stopped_journal_sha256'],
            'v2_partial_controls_excluded': 14}


def build_freeze(root: Path, old_path: Path, plan: Path,
                 plan_sha256: str, source: Path) -> dict:
    prior, _, prior_sha = parent_v3.validate_freeze(
        root / V3_FREEZE.relative_to(ROOT), old_path, plan, plan_sha256,
        source, root=root)
    require(not (root / parent_v3.V3_RUN.relative_to(ROOT)).exists(),
            'v3 full100 dispatch exists; preserve it and write a new amendment')
    require(prior['ordered_case_count'] == 100 and
            prior['whole_case_retry_cap_per_id'] == PER_CASE_RETRY_CAP and
            prior['study_wide_infrastructure_retry_cap'] == RETRY_CAP and
            prior['model_calls'] == prior['official_final_admitted'] == 0,
            'parent v3 freeze is not the original pre-result 100-case contract')
    return {**prior, 'schema': SCHEMA,
            'status': 'pre_result_chunked_evaluator_controls_only',
            'parent_v3_freeze_sha256': prior_sha,
            'historical_v3_controls_reused': 0,
            'max_cases_per_dispatch': MAX_CHUNK_CASES,
            'code_sha256': {name: sha((root / name).read_bytes())
                            for name in CODE_FILES}}


def validate_freeze(path: Path, old_path: Path, plan: Path,
                    plan_sha256: str, source: Path,
                    *, root: Path = ROOT) -> tuple[dict, dict, str]:
    frozen, digest = read_json(path)
    require(frozen.get('schema') == SCHEMA and
            frozen.get('model_calls') == frozen.get('official_final_admitted') == 0 and
            frozen == build_freeze(root, old_path, plan, plan_sha256, source),
            'v4 pre-result freeze, parent runtime, plan, or code changed')
    public, _ = read_json(root / PUBLIC_FREEZE.relative_to(ROOT))
    require(public.get('schema') ==
            'envloop-magento-clean-100-freeze-public-v4' and
            public.get('private_freeze_sha256') == digest and
            public.get('parent_v3_freeze_sha256') ==
            frozen['parent_v3_freeze_sha256'] and
            public.get('max_cases_per_dispatch') == MAX_CHUNK_CASES and
            public.get('parent_cron_freeze_sha256') ==
            frozen['parent_cron_freeze_sha256'] and
            public.get('runtime_fingerprint_sha256') ==
            frozen['parent_runtime_fingerprint_sha256'] and
            public.get('plan_sha256') == plan_sha256 and
            public.get('ordered_task_identity_sha256') ==
            frozen['ordered_task_identity_sha256'] and
            public.get('pinned_python_runtime_sha256') ==
            frozen['pinned_python_runtime_sha256'] and
            public.get('train_only_release_guard_pilot_sha256') ==
            frozen['train_only_release_guard_pilot_sha256'] and
            public.get('v2_retirement_public_sha256') ==
            frozen['v2_retirement_public_sha256'] and
            public.get('historical_v2_controls_reused') == 0 and
            public.get('historical_v3_controls_reused') == 0 and
            public.get('study_wide_infrastructure_retry_cap') == RETRY_CAP and
            public.get('model_calls') ==
            public.get('official_final_admitted') == 0,
            'published pre-result v4 freeze receipt missing or changed')
    old, _ = old_contract.validate_freeze(
        old_path, root,
        root / PROBE_DIR.relative_to(ROOT),
        root / TRAIN_DIR.relative_to(ROOT))
    return frozen, old, digest


def attempt_dir(run_dir: Path, index: int, number: int) -> Path:
    return run_dir / 'attempts' / f'case-{index:03d}-attempt-{number}'


def case_events(events: list[dict], index: int) -> list[dict]:
    return [row for row in events if row.get('index') == index]


def start_events(events: list[dict], index: int) -> list[dict]:
    return [row for row in case_events(events, index)
            if row.get('event') == 'case_attempt_started']


def verify_finished_attempt(run_dir: Path, events: list[dict], index: int,
                            number: int, case: dict, runtime_fingerprint: str) -> str:
    starts = [row for row in start_events(events, index)
              if row.get('attempt') == number]
    require(len(starts) == 1 and
            starts[0].get('task_id') == case['task_id'] and
            starts[0].get('package_sha256') == case['package_sha256'],
            'attempt/task identity binding changed')
    scoped = [row for row in case_events(events, index)
              if row.get('attempt') == number]
    intents = [row.get('step') for row in scoped if row.get('event') ==
               'step_intent']
    finishes = [row for row in scoped if row.get('event') == 'step_finished']
    require(intents == [row.get('step') for row in finishes] ==
            list(old_contract.STEPS) and
            all(row.get('exit_code') == 0 for row in finishes) and
            not any(row.get('event') == 'step_timeout_uncertain'
                    for row in scoped),
            'successful case lacks the full frozen zero-exit process sequence')
    calibrated = [row for row in scoped if row.get('event') == 'task_gui_calibrated']
    cleanups = [row.get('pair') for row in scoped
                if row.get('event') == 'pair_cleanup_verified']
    require(len(calibrated) == 1 and cleanups == ['positive', 'negative'],
            'candidate lacks one complete two-pair GUI control')
    base = attempt_dir(run_dir, index, number) / f'case-{index:03d}'
    receipt, receipt_sha = read_json(base / 'calibration.private.json')
    require(calibrated[0].get('receipt_sha256') == receipt_sha and
            calibrated[0].get('task_id') == case['task_id'] and
            receipt.get('task_id') == case['task_id'] and
            receipt.get('package_sha256') == case['package_sha256'] and
            receipt.get('schema') ==
            'envloop-magento-original-gui-case-calibration-v3' and
            receipt.get('split') == 'official_candidate' and
            receipt.get('positive_score') == 1.0 and
            receipt.get('wrong_variant_score') == 0.0 and
            receipt.get('fresh_reset_passed') is True and
            receipt.get('cellwide_cron_runtime_fingerprint_sha256') ==
            runtime_fingerprint and
            receipt.get('model_calls') == 0 and
            receipt.get('official_final_admitted') is False,
            'calibration is not frozen positive 1 / negative 0 / reset')
    for pair, mode, score in (('positive', 'gui-positive', 1.0),
                              ('negative', 'gui-wrong-variant', 0.0)):
        result, _ = read_json(base / pair / mode / 'result.json')
        require(result.get('schema') ==
                'envloop-magento-original-gui-control-v3' and
                result.get('score', {}).get('score') == score and
                result['score'].get('independent_saved_state') is True and
                result['score'].get('task_id') == case['task_id'] and
                result.get('model_calls') ==
                result.get('official_final_tasks_admitted') == 0,
                'independent native saved-state score missing')
    for pair, mode in (('positive', 'neutral'),
                       ('positive', 'gui-positive'),
                       ('negative', 'neutral'),
                       ('negative', 'gui-wrong-variant')):
        folder = base / pair / mode
        result, _ = read_json(folder / 'result.json')
        before, before_sha = read_json(folder / 'private-before.json')
        pre_edit, pre_edit_sha = read_json(folder / 'private-pre-edit.json')
        guard = result.get('quote', {}).get('release_modal_guard')
        require(result.get('schema') ==
                'envloop-magento-original-gui-control-v3' and
                result.get('task_id') == case['task_id'] and
                result.get('before_sha256') == before_sha and
                result.get('pre_edit_sha256') == pre_edit_sha and
                before == pre_edit and
                type(guard) is dict and
                guard.get('obstruction_clear_before_business_edit') is True and
                type(guard.get('release_mask_observed')) is bool and
                type(guard.get('release_notification_modals_closed')) is int and
                guard['release_notification_modals_closed'] >= 0 and
                result.get('model_calls') ==
                result.get('official_final_tasks_admitted') == 0,
                'v3 GUI release guard changed business state before candidate edit')
    reset, _ = read_json(base / 'negative/fresh-reset.private.json')
    require(reset.get('fresh_clone_reset_passed') is True and
            reset.get('material_monitored_sql_and_search_state') is True and
            reset.get('different_container_ids') is True and
            reset.get('different_search_container_ids') is True and
            reset.get('official_final_tasks_admitted') == 0 and
            reset.get('allowed_volatile_fields', []) in
            ([], ['target_stock_low_stock_date_clock']),
            'fresh material reset proof missing')
    return receipt_sha


def validate_run_header(events: list[dict], freeze_sha: str,
                        frozen: dict) -> None:
    require(events and events[0].get('event') == 'run_started' and
            events[0].get('freeze_v4_sha256') == freeze_sha and
            events[0].get('parent_v3_freeze_sha256') ==
            frozen['parent_v3_freeze_sha256'] and
            events[0].get('max_cases_per_dispatch') == MAX_CHUNK_CASES and
            events[0].get('parent_cron_freeze_sha256') ==
            frozen['parent_cron_freeze_sha256'] and
            events[0].get('plan_sha256') == frozen['plan_sha256'] and
            events[0].get('ordered_task_identity_sha256') ==
            frozen['ordered_task_identity_sha256'] and
            events[0].get('source_commit') == frozen['source_commit'] and
            events[0].get('runtime_fingerprint_sha256') ==
            frozen['parent_runtime_fingerprint_sha256'] and
            events[0].get('pinned_python_runtime_sha256') ==
            frozen['pinned_python_runtime_sha256'] and
            events[0].get('train_only_release_guard_pilot_sha256') ==
            frozen['train_only_release_guard_pilot_sha256'] and
            events[0].get('v2_retirement_public_sha256') ==
            frozen['v2_retirement_public_sha256'] and
            events[0].get('historical_v2_controls_reused') == 0 and
            events[0].get('historical_v3_controls_reused') == 0 and
            events[0].get('model_calls') == 0 and
            events[0].get('official_final_admitted') == 0,
            'chunked journal header differs from pre-result v4 freeze')


def validate_case_sequence(events: list[dict], cases: list[dict]) -> None:
    """Keep the task order exact; an infrastructure retry never changes IDs."""
    starts = [row for row in events if row.get('event') == 'case_attempt_started']
    completed = [row for row in events if row.get('event') == 'case_completed']
    retries = [row for row in events if row.get('event') == 'attempt_reconciled']
    position = {id(row): ordinal for ordinal, row in enumerate(events)}
    require(len(completed) <= 100 and len(starts) <= 100 + RETRY_CAP and
            len(retries) <= RETRY_CAP and
            [row.get('index') for row in completed] == list(range(len(completed))),
            'completed case order, total, or study-wide retry cap changed')
    for index, case in enumerate(cases):
        attempts = [row for row in starts if row.get('index') == index]
        require(len(attempts) <= 2 and
                [row.get('attempt') for row in attempts] == list(range(len(attempts))) and
                all(row.get('task_id') == case['task_id'] and
                    row.get('package_sha256') == case['package_sha256']
                    for row in attempts),
                'attempt count, order, or task identity changed')
        done = [row for row in completed if row.get('index') == index]
        retry = [row for row in retries if row.get('index') == index]
        require(len(done) <= 1 and
                (not done or (len(attempts) >= 1 and
                              done[0].get('attempt') == attempts[-1]['attempt'])),
                'duplicate or unbound case completion')
        require(len(retry) <= 1 and
                (len(attempts) < 2 or len(retry) == 1) and
                (not retry or (attempts and
                               retry[0].get('attempt') == 0 and
                               position[id(attempts[0])] < position[id(retry[0])] and
                               (len(attempts) < 2 or
                                position[id(retry[0])] < position[id(attempts[1])]))) and
                (not done or position[id(attempts[-1])] < position[id(done[0])]) and
                (not done or not retry or done[0].get('attempt') == 1),
                'retry authorization or case event order changed')
        if index > len(completed):
            require(not attempts, 'later task started before current case finished')
    require(len({row.get('index') for row in retries}) == len(retries) and
            all(row.get('attempt') == 0 and 0 <= row.get('index', -1) < 100
                for row in retries),
            'whole-case infrastructure retry cap exceeded')


def validate_attempt_inventory(run_dir: Path, events: list[dict]) -> None:
    """An unjournaled attempt directory is a crash boundary, never a new slot."""
    expected = {f"case-{row['index']:03d}-attempt-{row['attempt']}"
                for row in events if row.get('event') == 'case_attempt_started'}
    parent = run_dir / 'attempts'
    actual = {path.name for path in parent.iterdir()} if parent.exists() else set()
    require(all(path.is_dir() and not path.is_symlink()
                for path in parent.iterdir()) if parent.exists() else True,
            'unexpected non-directory Magento attempt evidence')
    require(actual == expected,
            'unjournaled or missing attempt directory; stop before replay')


def validate_completed_prefix(run_dir: Path, events: list[dict],
                              cases: list[dict],
                              runtime_fingerprint: str) -> int:
    completed = [row for row in events if row.get('event') == 'case_completed']
    for index, row in enumerate(completed):
        digest = verify_finished_attempt(run_dir, events, index,
                                         row['attempt'], cases[index],
                                         runtime_fingerprint)
        require(row.get('calibration_sha256') == digest,
                'previously completed case receipt changed')
    return len(completed)


def _boundary_payload(events: list[dict], cases: list[dict],
                      frozen: dict, freeze_sha: str,
                      dispatch: dict) -> dict:
    completed = [row for row in events if row.get('event') == 'case_completed']
    count = len(completed)
    return {
        'freeze_v4_sha256': freeze_sha,
        'parent_v3_freeze_sha256': frozen['parent_v3_freeze_sha256'],
        'dispatch_sequence': dispatch['sequence'],
        'completed_distinct_cases': count,
        'newly_completed_this_dispatch':
        count - dispatch['completed_before_dispatch'],
        'ordered_completed_task_identity_sha256':
        case_identity_digest(cases[:count]),
        'completed_calibration_receipts_sha256':
        sha(('\n'.join(row['calibration_sha256'] for row in completed) +
             '\n').encode()),
        'journal_prefix_sha256': sha(b''.join(encode(row) for row in events)),
        'infrastructure_retries': len([row for row in events
                                       if row.get('event') == 'attempt_reconciled']),
        'model_calls': 0, 'official_final_admitted': 0,
    }


def validate_chunk_boundaries(events: list[dict], cases: list[dict],
                              frozen: dict, freeze_sha: str) -> None:
    """Verify each partial receipt against its exact preceding journal bytes."""
    dispatch = None
    finished = False
    completed_so_far = 0
    for position, row in enumerate(events):
        if row.get('event') == 'run_started':
            require(position == 0, 'duplicate campaign header')
        elif row.get('event') == 'dispatch_started':
            require(dispatch is None and not finished and
                    row.get('freeze_v4_sha256') == freeze_sha and
                    row.get('parent_v3_freeze_sha256') ==
                    frozen['parent_v3_freeze_sha256'] and
                    type(row.get('max_cases')) is int and
                    1 <= row['max_cases'] <= MAX_CHUNK_CASES and
                    row.get('completed_before_dispatch') == len([
                        prior for prior in events[:position]
                        if prior.get('event') == 'case_completed']) and
                    row.get('model_calls') == row.get('official_final_admitted') == 0,
                    'dispatch changed the v4 freeze, chunk cap, or completed prefix')
            dispatch = row
        elif row.get('event') in ('case_attempt_started', 'case_completed'):
            require(dispatch is not None and not finished and
                    row.get('index') == completed_so_far,
                    'candidate case appeared outside its ordered bounded dispatch')
            if row['event'] == 'case_completed':
                completed_so_far += 1
                require(completed_so_far - dispatch['completed_before_dispatch'] <=
                        dispatch['max_cases'],
                        'candidate case exceeded its dispatch cap')
        elif row.get('event') in ('chunk_completed', 'run_completed'):
            require(dispatch is not None and not finished and position > 0,
                    'case-boundary receipt has no dispatch')
            prefix = events[:position]
            expected = _boundary_payload(prefix, cases, frozen,
                                         freeze_sha, dispatch)
            require(all(row.get(key) == value for key, value in expected.items()) and
                    0 <= expected['newly_completed_this_dispatch'] <=
                    dispatch['max_cases'] and
                    row.get('max_cases') == dispatch['max_cases'] and
                    row.get('dispatch_sequence') == dispatch['sequence'],
                    'case-boundary receipt, hash, or dispatch count changed')
            count = expected['completed_distinct_cases']
            if row['event'] == 'chunk_completed':
                require(0 < count < 100 and
                        expected['newly_completed_this_dispatch'] > 0 and
                        prefix[-1].get('event') == 'case_completed',
                        'partial receipt was not emitted after a complete case')
                dispatch = None
            else:
                require(count == 100 and position == len(events) - 1 and
                        (prefix[-1].get('event') == 'case_completed' or
                         (prefix[-1].get('event') == 'dispatch_started' and
                          expected['newly_completed_this_dispatch'] == 0)),
                        '100-case receipt was not emitted at a complete boundary')
                finished = True
        else:
            require(dispatch is not None and not finished,
                    'attempt event appeared outside a bounded dispatch')
    require(not finished or events[-1].get('event') == 'run_completed',
            'events appended after terminal 100-case receipt')


def _lock():
    LOCK.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError('another Magento admission worker is active') from None
    return fd


def _unlock(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _check_single_dispatch(run_dir: Path, freeze_sha: str) -> None:
    for candidate in (ROOT / 'work/magento-original').glob(
            'clean-v4-*/journal.private.jsonl'):
        if candidate.resolve() == (run_dir / 'journal.private.jsonl').resolve():
            continue
        events = read_journal(candidate)
        require(not events or events[0].get('freeze_v4_sha256') != freeze_sha,
                'v4 100-case campaign already dispatched elsewhere')


def _finish_partial_chunk(journal: Path, run_dir: Path,
                          cases: list[dict], frozen: dict, freeze_sha: str,
                          old: dict, dispatch: dict,
                          max_cases: int) -> dict:
    events = read_journal(journal)
    validate_case_sequence(events, cases)
    validate_attempt_inventory(run_dir, events)
    completed = validate_completed_prefix(
        run_dir, events, cases, old['runtime_fingerprint_sha256'])
    require(0 < completed < 100 and
            events[-1].get('event') == 'case_completed' and
            completed - dispatch['completed_before_dispatch'] == max_cases,
            'chunk cannot stop before a complete candidate case')
    sweep_v3.assert_absent()
    receipt = _boundary_payload(events, cases, frozen, freeze_sha, dispatch)
    append_event(journal, {'event': 'chunk_completed', **receipt,
                           'max_cases': max_cases})
    events = read_journal(journal)
    validate_chunk_boundaries(events, cases, frozen, freeze_sha)
    return {'status': 'partial_evaluator_gui_controls_complete',
            'completed_distinct_cases': completed,
            'newly_completed_this_dispatch': max_cases,
            'next_case_index': completed,
            'chunk_receipt_sequence': events[-1]['sequence'],
            'chunk_receipt_sha256': sha(encode(events[-1])),
            'journal_sha256': sha(journal.read_bytes()),
            'model_calls': 0, 'official_final_admitted': 0}


def run_campaign(plan: Path, plan_sha256: str, source: Path,
                 old_freeze: Path, freeze_v4: Path, run_dir: Path,
                 *, resume: bool, max_cases: int) -> dict:
    require(type(max_cases) is int and 1 <= max_cases <= MAX_CHUNK_CASES,
            'v4 requires an explicit bounded 1-to-5 case dispatch')
    require(run_dir.resolve() == V4_RUN.resolve() and
            run_dir.resolve() != V2_RUN.resolve(),
            'clean_v4_run_must_start_in_its_own_exact_directory_from_index_zero')
    private = (ROOT / 'work').resolve()
    require(all(path.resolve().is_relative_to(private) for path in
                (plan, source, old_freeze, freeze_v4, run_dir)),
            'all plans, freezes, source, and attempts must stay private')
    frozen, old, freeze_sha = validate_freeze(
        freeze_v4, old_freeze, plan, plan_sha256, source)
    cases = validate_plan(plan, plan_sha256)
    journal = run_dir / 'journal.private.jsonl'
    fd = _lock()
    try:
        _check_single_dispatch(run_dir, freeze_sha)
        if resume:
            require(run_dir.is_dir() and journal.is_file(),
                    'resume requires the original private campaign journal')
        else:
            require(not run_dir.exists(), 'a new campaign needs a fresh output path')
            sweep_v3.assert_absent()
            run_dir.mkdir(parents=True, mode=0o700)
            append_event(journal, {
                'event': 'run_started', 'freeze_v4_sha256': freeze_sha,
                'parent_v3_freeze_sha256': frozen['parent_v3_freeze_sha256'],
                'max_cases_per_dispatch': MAX_CHUNK_CASES,
                'parent_cron_freeze_sha256': frozen['parent_cron_freeze_sha256'],
                'plan_sha256': plan_sha256,
                'ordered_task_identity_sha256': frozen['ordered_task_identity_sha256'],
                'source_commit': frozen['source_commit'],
                'runtime_fingerprint_sha256': frozen['parent_runtime_fingerprint_sha256'],
                'pinned_python_runtime_sha256': frozen['pinned_python_runtime_sha256'],
                'train_only_release_guard_pilot_sha256':
                frozen['train_only_release_guard_pilot_sha256'],
                'v2_retirement_public_sha256': frozen['v2_retirement_public_sha256'],
                'historical_v2_controls_reused': 0,
                'historical_v3_controls_reused': 0,
                'max_infrastructure_retries': RETRY_CAP,
                'model_calls': 0, 'official_final_admitted': 0})
        events = read_journal(journal)
        validate_run_header(events, freeze_sha, frozen)
        validate_case_sequence(events, cases)
        validate_chunk_boundaries(events, cases, frozen, freeze_sha)
        validate_attempt_inventory(run_dir, events)
        require(not any(row.get('event') == 'run_completed' for row in events),
                '100-case campaign already completed')
        completed_before = validate_completed_prefix(
            run_dir, events, cases, old['runtime_fingerprint_sha256'])
        dispatches = [row for row in events
                      if row.get('event') == 'dispatch_started']
        boundaries = [row for row in events if row.get('event') in
                      ('chunk_completed', 'run_completed')]
        if len(dispatches) > len(boundaries):
            require(resume and len(dispatches) == len(boundaries) + 1,
                    'open dispatch requires same-journal explicit resume')
            dispatch = dispatches[-1]
            require(dispatch['max_cases'] == max_cases and
                    completed_before >= dispatch['completed_before_dispatch'] and
                    completed_before - dispatch['completed_before_dispatch'] <=
                    max_cases,
                    'open dispatch cap or completed prefix changed')
        else:
            require(not resume or events[-1].get('event') == 'chunk_completed',
                    'resume requires a closed chunk boundary')
            sweep_v3.assert_absent()
            append_event(journal, {'event': 'dispatch_started',
                                   'freeze_v4_sha256': freeze_sha,
                                   'parent_v3_freeze_sha256':
                                   frozen['parent_v3_freeze_sha256'],
                                   'completed_before_dispatch': completed_before,
                                   'max_cases': max_cases,
                                   'model_calls': 0,
                                   'official_final_admitted': 0})
            dispatch = read_journal(journal)[-1]
        new_completed = completed_before - dispatch['completed_before_dispatch']
        if new_completed == max_cases and completed_before < 100:
            return _finish_partial_chunk(
                journal, run_dir, cases, frozen, freeze_sha,
                old, dispatch, max_cases)
        for index, case in enumerate(cases):
            events = read_journal(journal)
            validate_case_sequence(events, cases)
            completed = [row for row in case_events(events, index)
                         if row.get('event') == 'case_completed']
            if completed:
                number = completed[0]['attempt']
                digest = verify_finished_attempt(
                    run_dir, events, index, number, case,
                    old['runtime_fingerprint_sha256'])
                require(completed[0].get('calibration_sha256') == digest,
                        'previously completed case receipt changed')
                continue
            starts = start_events(events, index)
            if starts:
                number = starts[-1]['attempt']
                scoped = [row for row in case_events(events, index)
                          if row.get('attempt') == number]
                calibrated = [row for row in scoped
                              if row.get('event') == 'task_gui_calibrated']
                if calibrated:
                    sweep_v3.assert_absent()
                    digest = verify_finished_attempt(
                        run_dir, events, index, number, case,
                        old['runtime_fingerprint_sha256'])
                    append_event(journal, {'event': 'case_completed',
                                           'index': index, 'attempt': number,
                                           'calibration_sha256': digest,
                                           'model_calls': 0,
                                           'official_final_admitted': 0})
                    new_completed += 1
                    if new_completed == max_cases and index < 99:
                        return _finish_partial_chunk(
                            journal, run_dir, cases, frozen, freeze_sha,
                            old, dispatch, max_cases)
                    continue
                reconciled = [row for row in scoped
                              if row.get('event') == 'attempt_reconciled']
                require(number == 0 and len(reconciled) == 1 and
                        len(starts) == 1 and
                        len([row for row in events if row.get('event') ==
                             'attempt_reconciled']) <= RETRY_CAP,
                        'incomplete attempt needs exact reconciliation; no automatic retry')
                receipt_path = attempt_dir(run_dir, index, 0) / 'reconciliation.private.json'
                receipt, receipt_sha = read_json(receipt_path)
                audit, audit_sha = read_json(receipt_path.parent /
                                              'reconciliation-audit.private.json')
                intent, intent_sha = read_json(receipt_path.parent /
                                                'reconciliation-intent.private.json')
                require(reconciled[0].get('reconciliation_sha256') == receipt_sha and
                        reconciled[0].get('audit_sha256') == audit_sha and
                        reconciled[0].get('classification') ==
                        audit.get('classification') and
                        receipt.get('schema') ==
                        'envloop-magento-clean-cleanup-private-v4' and
                        receipt.get('status') == 'exact_pair_retired_for_one_whole_case_retry' and
                        receipt.get('case_index') == index and
                        receipt.get('task_id') == case['task_id'] and
                        receipt.get('package_sha256') == case['package_sha256'] and
                        receipt.get('plan_sha256') == plan_sha256 and
                        receipt.get('freeze_v4_sha256') == freeze_sha and
                        receipt.get('audit_sha256') == audit_sha and
                        receipt.get('cleanup_intent_sha256') == intent_sha and
                        intent.get('material_witness') ==
                        audit.get('material_witness') ==
                        receipt.get('material_witness') and
                        receipt.get('both_containers_absent') is True and
                        receipt.get('model_calls') ==
                        receipt.get('official_final_admitted') == 0,
                        'first attempt has no immutable cleanup evidence')
                number = 1
            else:
                number = 0
            sweep_v3.assert_absent()
            target = attempt_dir(run_dir, index, number)
            require(not target.exists(), 'attempt files already exist')
            target.mkdir(parents=True, mode=0o700)
            append_event(journal, {'event': 'case_attempt_started',
                                   'index': index, 'attempt': number,
                                   'task_id': case['task_id'],
                                   'package_sha256': case['package_sha256'],
                                   'model_calls': 0, 'official_final_admitted': 0})
            try:
                sweep_v3.task(index, case, plan, plan_sha256, source,
                              target, journal, cellwide_freeze=old,
                              journal_append=lambda path, event: append_event(
                                  path, {**event, 'attempt': number}))
            except Exception as error:
                append_event(journal, {'event': 'attempt_stopped',
                                       'index': index, 'attempt': number,
                                       'error_type': type(error).__name__,
                                       'error_sha256': sha(str(error).encode()),
                                       'model_calls': 0,
                                       'official_final_admitted': 0})
                raise
            events = read_journal(journal)
            digest = verify_finished_attempt(run_dir, events, index, number,
                                             case, old['runtime_fingerprint_sha256'])
            sweep_v3.assert_absent()
            append_event(journal, {'event': 'case_completed',
                                   'index': index, 'attempt': number,
                                   'calibration_sha256': digest,
                                   'model_calls': 0, 'official_final_admitted': 0})
            new_completed += 1
            print(json.dumps({'status': 'evaluator_gui_control_completed',
                              'completed_distinct_cases': index + 1,
                              'requested': 100, 'official_final_admitted': 0}),
                  flush=True)
            if new_completed == max_cases and index < 99:
                return _finish_partial_chunk(
                    journal, run_dir, cases, frozen, freeze_sha,
                    old, dispatch, max_cases)
        events = read_journal(journal)
        validate_case_sequence(events, cases)
        require(len([row for row in events if row.get('event') ==
                     'case_completed']) == 100,
                '100 distinct calibrations required')
        sweep_v3.assert_absent()
        require(0 <= 100 - completed_before <= max_cases,
                'final dispatch exceeded the frozen chunk bound')
        boundary = _boundary_payload(events, cases, frozen, freeze_sha, dispatch)
        append_event(journal, {'event': 'run_completed', **boundary,
                               'max_cases': max_cases,
                               'distinct_cases': 100,
                               'infrastructure_retries': len([
                                   row for row in events if row.get('event') ==
                                   'attempt_reconciled']),
                               'model_calls': 0, 'official_final_admitted': 0})
        events = read_journal(journal)
        validate_chunk_boundaries(events, cases, frozen, freeze_sha)
        return {'status': '100_evaluator_gui_controls_completed',
                'completed_distinct_cases': 100,
                'journal_sha256': sha(journal.read_bytes()),
                'model_calls': 0, 'official_final_admitted': 0}
    finally:
        _unlock(fd)


def _docker_inspect(name: str) -> dict | None:
    result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                             'inspect', name], capture_output=True, timeout=30)
    if result.returncode != 0:
        return None
    rows = json.loads(result.stdout)
    require(len(rows) == 1 and rows[0].get('Name') == '/' + name,
            'disposable container name or identity changed')
    return rows[0]


def _live_pair(prepared: dict) -> list[dict]:
    app = _docker_inspect(sweep_v3.APP)
    search = _docker_inspect(sweep_v3.SEARCH)
    require(app is not None and search is not None,
            'incomplete pair cannot be identity-bound for a retry')
    values = ((app, sweep_v3.APP,
               prepared['application_clone']['container_id_sha256'], IMAGE),
              (search, sweep_v3.SEARCH,
               prepared['search_sidecar_id_sha256'], NATIVE_SEARCH_IMAGE))
    result = []
    for container, name, expected_id, expected_image in values:
        require(sha(container['Id'].encode()) == expected_id and
                container['Image'] == expected_image and
                container.get('Mounts') == [],
                'disposable pair differs from prepared IDs/images/mounts')
        require(container['State']['Running'] is True,
                'exited pair has no live SQL/search equivalence; new cell decision required')
        result.append({'name': name, 'container_id_sha256': expected_id,
                       'image_sha256': expected_image, 'mount_count': 0})
    return result


def _unreceipted_preseed_witness(pair: str, scoped: list[dict],
                                old: dict) -> dict:
    """Read-only adopt a live, unseeded prepare pair; never start an exited one."""
    step = f'{pair}-prepare'
    intents = [row for row in scoped if row.get('event') == 'step_intent'
               and row.get('step') == step]
    require(len(intents) == 1 and
            not any(row.get('event') == 'step_intent' and
                    row.get('step') == f'{pair}-seed' for row in scoped),
            'unreceipted pair crossed the task-seed boundary')
    app = _docker_inspect(sweep_v3.APP)
    search = _docker_inspect(sweep_v3.SEARCH)
    require(app is not None and search is not None,
            'an exited/partial prepare pair has no complete live material proof')
    observed = ((app, sweep_v3.APP, IMAGE),
                (search, sweep_v3.SEARCH, NATIVE_SEARCH_IMAGE))
    upper = next((row['time'] for row in reversed(scoped)
                  if row.get('event') == 'attempt_stopped'), time.time())
    identities = []
    for container, name, image in observed:
        created = datetime.fromisoformat(container['Created'].replace(
            'Z', '+00:00')).timestamp()
        require(container['Image'] == image and
                container.get('Mounts') == [] and
                container['State']['Running'] is True and
                intents[0]['time'] - 2 <= created <= upper + 2,
                'exited/unreceipted pair cannot prove exact creation window and material')
        identity = sha(container['Id'].encode())
        identities.append({'name': name, 'container_id_sha256': identity,
                           'image_sha256': image, 'mount_count': 0,
                           'created': container['Created']})
    diagnostics = {}
    for container, name, _ in observed:
        logs = subprocess.run(['docker', '--context', 'colima-cua-scale',
                               'logs', name], capture_output=True, timeout=30)
        require(logs.returncode == 0,
                'unreceipted container diagnostics unavailable')
        diagnostics[name] = {
            'inspect_sha256': sha(encode(container)),
            'stdout_log_sha256': sha(logs.stdout),
            'stderr_log_sha256': sha(logs.stderr),
        }
    current = clone.audit_existing(sweep_v3.SEARCH_SHA,
                                   'read_only_v3_unreceipted_preseed_adoption')
    cron = clone.verify_cron_never_autostarted()
    price = clone.read_price_index_shape()
    require(current['application_clone']['container_id_sha256'] ==
            identities[0]['container_id_sha256'] and
            current['search_sidecar_id_sha256'] ==
            identities[1]['container_id_sha256'] and
            cron['config_sha256'] == old['runtime']['cron_config_sha256'] and
            price['price_rows'] == 8156 and
            price['price_key_sets_equal'] is True and
            price['price_changed_rows'] == 0 and
            price['live_price_sha256'] == price['replica_price_sha256'],
            'unreceipted pair has no equivalent cron/source/price state')
    material = {
        'app_id_sha256': identities[0]['container_id_sha256'],
        'search_id_sha256': identities[1]['container_id_sha256'],
        'source_search_sha256': current['search_documents_sha256'],
        'search_documents': current['search_document_count'],
        'cron_config_sha256': cron['config_sha256'],
        'price_rows': price['price_rows'],
        'price_changed_rows': price['price_changed_rows'],
        'price_key_sets_equal': price['price_key_sets_equal'],
        'live_price_sha256': price['live_price_sha256'],
        'replica_price_sha256': price['replica_price_sha256'],
        'quote_pages': 0,
    }
    return {'state': 'unreceipted_live_preseed_equivalent',
            'containers': identities,
            'material_current_sha256': sha(encode(material)),
            'material_current_fields': material,
            'material_equal_exact': True,
            'task_seeded': False,
            'diagnostic_hashes': diagnostics}


def _active_pair(scoped: list[dict]) -> str | None:
    positive = any(row.get('event') == 'pair_cleanup_verified' and
                   row.get('pair') == 'positive' for row in scoped)
    negative = any(row.get('event') == 'pair_cleanup_verified' and
                   row.get('pair') == 'negative' for row in scoped)
    require(not negative or positive,
            'negative cleanup cannot precede positive cleanup')
    if negative:
        return None
    started_negative = any(row.get('event') == 'step_intent' and
                           str(row.get('step', '')).startswith('negative-')
                           for row in scoped)
    if started_negative:
        return 'negative'
    return None if positive else 'positive'


def _retryable_interruption(scoped: list[dict],
                            *, known_neutral_timeout: bool = False,
                            abandoned_gui_terminal: bool = False,
                            unreceipted_preseed_equivalent: bool = False) -> None:
    require(not any(row.get('event') in ('task_gui_calibrated',
                                        'attempt_reconciled', 'case_completed')
                    for row in scoped),
            'completed/reconciled attempt cannot be retried')
    failed = [row for row in scoped if row.get('event') == 'step_finished' and
              row.get('exit_code') != 0]
    require(not failed or (known_neutral_timeout and len(failed) == 1 and
                          failed[0].get('step') in
                          ('positive-neutral', 'negative-neutral')) or
            (unreceipted_preseed_equivalent and len(failed) == 1 and
             failed[0].get('step') in ('positive-prepare',
                                      'negative-prepare')),
            'nonzero GUI/setup/verifier process is a deterministic failure, not infrastructure')
    intents = [row for row in scoped if row.get('event') == 'step_intent']
    finishes = [row for row in scoped if row.get('event') == 'step_finished']
    require(len(finishes) <= len(intents) and
            [row.get('step') for row in finishes] ==
            [row.get('step') for row in intents[:len(finishes)]],
            'step sequence changed before operator reconciliation')
    pending = intents[len(finishes):]
    require(len(pending) <= 1 and
            (not any(row.get('step') in ('positive-gui', 'negative-gui')
                     for row in pending) or abandoned_gui_terminal),
            'an interrupted GUI action may have mutated state; no bounded retry')
    timeouts = [row for row in scoped if row.get('event') ==
                'step_timeout_uncertain']
    require(len(timeouts) <= 1 and
            (not timeouts or (len(pending) == 1 and
                              timeouts[0].get('step') == pending[0].get('step'))),
            'timeout does not bind the unfinished non-GUI step')
    require(bool(pending) or known_neutral_timeout or
            unreceipted_preseed_equivalent or
            not any(row.get('event') == 'attempt_stopped' for row in scoped),
            'completed step followed by an exception is not host loss')


def _known_neutral_timeout(base: Path, index: int,
                           scoped: list[dict]) -> str | None:
    failed = [row for row in scoped if row.get('event') == 'step_finished'
              and row.get('exit_code') != 0]
    if len(failed) != 1 or failed[0].get('step') not in (
            'positive-neutral', 'negative-neutral'):
        return None
    step = failed[0]['step']
    pair = step.split('-', 1)[0]
    source = base / f'case-{index:03d}' / pair
    stderr_path = source / f'{step}-stderr.private.bin'
    process_path = source / f'{step}-process.private.json'
    neutral = source / 'neutral'
    if not (stderr_path.is_file() and process_path.is_file() and
            (neutral / 'private-before.json').is_file() and
            not (neutral / 'private-after.json').exists() and
            not (neutral / 'result.json').exists()):
        return None
    stderr = stderr_path.read_bytes()
    process = json.loads(process_path.read_bytes())
    bound = (process.get('exit_code') != 0 and
             process.get('stderr_sha256') == failed[0].get('stderr_sha256') ==
             sha(stderr) and
             not any(row.get('event') == 'step_intent' and
                     row.get('step') == f'{pair}-gui' for row in scoped))
    if not bound:
        return None
    if (b'Locator.click: Timeout 60000ms exceeded' in stderr and
            b'element is not visible' in stderr and
            b'data-action="item-edit"' in stderr):
        return 'known_neutral_cms_menu_timeout_before_edit'
    if (b'Locator.wait_for: Timeout 120000ms exceeded' in stderr and
            b'locator("h1.page-title")' in stderr):
        return 'known_neutral_page_title_timeout_before_edit'
    return None


def _pending_gui_step(base: Path, index: int,
                      scoped: list[dict]) -> str | None:
    intents = [row.get('step') for row in scoped if row.get('event') ==
               'step_intent']
    finishes = [row.get('step') for row in scoped if row.get('event') ==
                'step_finished']
    if len(intents) != len(finishes) + 1 or intents[:-1] != finishes:
        return None
    step = intents[-1]
    if step not in ('positive-gui', 'negative-gui'):
        return None
    pair = step.split('-', 1)[0]
    output = base / f'case-{index:03d}' / pair / (
        'gui-positive' if pair == 'positive' else 'gui-wrong-variant')
    if (output / 'result.json').exists() or (output / 'private-after.json').exists():
        return None
    return step


def _gui_driver_terminal() -> bool:
    result = subprocess.run(['ps', '-ww', '-axo', 'pid=,command='],
                            capture_output=True, timeout=15)
    require(result.returncode == 0, 'GUI driver process state unavailable')
    return not any(b'qualify_magento_original_catalog_v3.py' in line
                   for line in result.stdout.splitlines())


def _material_witness(case: dict, pair_dir: Path,
                      scoped: list[dict],
                      *, exact_pre_gui: bool = False) -> dict:
    prepared, prepared_sha = read_json(pair_dir / 'prepare.private.json')
    containers = _live_pair(prepared)
    seed_path = pair_dir / 'seed.private.json'
    if not seed_path.exists():
        require(not any(row.get('event') == 'step_intent' and
                        row.get('step') == f'{pair_dir.name}-seed'
                        for row in scoped),
                'unfinished seed could have mutated the clone')
        # Re-read the live original catalog. The prepared receipt alone
        # cannot prove that cron/search remained stable after host sleep.
        live = clone.audit_existing(sweep_v3.SEARCH_SHA,
                                    'read_only_v3_interruption_audit')
        price = clone.read_price_index_shape()
        require(live['application_clone']['container_id_sha256'] ==
                prepared['application_clone']['container_id_sha256'] and
                live['search_sidecar_id_sha256'] ==
                prepared['search_sidecar_id_sha256'] and
                price['price_rows'] == 8156 and
                price['price_key_sets_equal'] is True and
                price['price_changed_rows'] == 0 and
                price['live_price_sha256'] == price['replica_price_sha256'],
                'unseeded pair material source/index drifted after interruption')
        live_material = {
            'app_id_sha256': live['application_clone']['container_id_sha256'],
            'search_id_sha256': live['search_sidecar_id_sha256'],
            'source_search_sha256': live['search_documents_sha256'],
            'price_rows': price['price_rows'],
            'live_price_sha256': price['live_price_sha256'],
            'replica_price_sha256': price['replica_price_sha256'],
            'quote_pages': 0,
        }
        return {'state': 'prepared_unseeded',
                'prepared_sha256': prepared_sha, 'containers': containers,
                'material_reference_sha256': prepared_sha,
                'material_current_sha256': sha(encode(live_material)),
                'allowed_volatile_fields': []}
    seed, seed_sha = read_json(seed_path)
    require(seed.get('task_id') == case['task_id'] and
            type(seed.get('page_id')) is int and seed['page_id'] > 0,
            'seed receipt differs from frozen case')
    control_dir = pair_dir / ('gui-positive' if pair_dir.name == 'positive'
                              else 'gui-wrong-variant')
    control_after = control_dir / 'private-after.json'
    if exact_pre_gui:
        require(not control_after.exists() and
                not (control_dir / 'result.json').exists(),
                'abandoned GUI wrote a saved result or post-action snapshot')
    if control_after.is_file():
        result_path = control_after.parent / 'result.json'
        result, _ = read_json(result_path)
        expected = 1.0 if pair_dir.name == 'positive' else 0.0
        require(result.get('score', {}).get('score') == expected and
                result['score'].get('independent_saved_state') is True and
                result.get('model_calls') ==
                result.get('official_final_tasks_admitted') == 0,
                'completed GUI result cannot be confused with failed GUI')
        reference = control_after
    else:
        reference = pair_dir / 'normalized-baseline.private.json'
        if not reference.is_file() and not exact_pre_gui:
            reference = pair_dir / 'neutral/private-before.json'
        require(reference.is_file(),
                'seeded pair has no pre-mutation material snapshot')
    baseline, baseline_sha = read_json(reference)
    live = read_snapshot(case, sweep_v3.APP, 7794, 7795,
                         seed['page_id'], search_host=sweep_v3.SEARCH)
    if not control_after.is_file():
        check_baseline(case, live)
    if exact_pre_gui:
        require(live == baseline,
                'abandoned GUI changed monitored state from exact normalized baseline')
        time.sleep(2)
        again = read_snapshot(case, sweep_v3.APP, 7794, 7795,
                              seed['page_id'], search_host=sweep_v3.SEARCH)
        require(again == baseline,
                'abandoned GUI state was not stable on independent readback')
        cron = clone.verify_cron_never_autostarted()
        price = clone.read_price_index_shape()
        require(cron['config_sha256'] ==
                prepared['train_probe_cron']['config_sha256'] and
                price['price_rows'] == 8156 and
                price['price_key_sets_equal'] is True and
                price['price_changed_rows'] == 0 and
                price['live_price_sha256'] == price['replica_price_sha256'],
                'abandoned GUI runtime or derived price index drifted')
        volatility = []
        runtime_check = {'cron_config_sha256': cron['config_sha256'],
                         'price_rows': price['price_rows'],
                         'price_changed_rows': price['price_changed_rows'],
                         'price_key_sets_equal': price['price_key_sets_equal'],
                         'live_price_sha256': price['live_price_sha256'],
                         'replica_price_sha256': price['replica_price_sha256']}
    else:
        volatility = check_material_reset(baseline, live)
        runtime_check = None
    return {'state': 'saved_gui_state' if control_after.is_file()
            else 'seeded_pre_gui',
            'seed_sha256': seed_sha, 'prepared_sha256': prepared_sha,
            'containers': containers,
            'material_reference_sha256': baseline_sha,
            'material_current_sha256': sha(encode(live)),
            'material_current_snapshot': live,
            'material_equal_exact': live == baseline,
            'live_runtime_check': runtime_check,
            'allowed_volatile_fields': volatility}


def inspect_interruption(run_dir: Path, journal: Path, cases: list[dict],
                         frozen: dict, old: dict) -> dict:
    events = read_journal(journal)
    validate_case_sequence(events, cases)
    completed = [row for row in events if row.get('event') == 'case_completed']
    index = len(completed)
    require(index < 100, 'all cases already completed')
    starts = start_events(events, index)
    require(len(starts) == 1 and starts[0].get('attempt') == 0,
            'only a first-attempt failure can receive one bounded retry')
    require(len([row for row in events if row.get('event') ==
                 'attempt_reconciled']) < RETRY_CAP,
            'study-wide infrastructure retry cap reached')
    case = cases[index]
    scoped = [row for row in case_events(events, index)
              if row.get('attempt') == 0]
    base = attempt_dir(run_dir, index, 0)
    known_timeout = _known_neutral_timeout(base, index, scoped)
    pending_gui = _pending_gui_step(base, index, scoped)
    driver_terminal = _gui_driver_terminal() if pending_gui else False
    require(not pending_gui or driver_terminal,
            'original GUI driver is still running; no reconciliation')
    pair = _active_pair(scoped)
    witness = None
    unreceipted = False
    if pair == 'negative':
        positive_cleanups = [row for row in scoped if row.get('event') ==
                             'pair_cleanup_verified' and
                             row.get('pair') == 'positive']
        positive_result, _ = read_json(
            base / f'case-{index:03d}/positive/gui-positive/result.json')
        require(len(positive_cleanups) == 1 and
                positive_result.get('score', {}).get('score') == 1.0 and
                positive_result['score'].get('independent_saved_state') is True and
                positive_result['score'].get('task_id') == case['task_id'] and
                positive_result.get('model_calls') ==
                positive_result.get('official_final_tasks_admitted') == 0,
                'negative interruption lacks its completed native positive')
    if pair is None:
        sweep_v3.assert_absent()
    else:
        pair_dir = base / f'case-{index:03d}' / pair
        prep_path = pair_dir / 'prepare.private.json'
        if prep_path.is_file():
            prepared, _ = read_json(prep_path)
            old_contract.validate_prepared(
                prepared, config_sha256=old['runtime']['cron_config_sha256'])
            witness = _material_witness(case, pair_dir, scoped,
                                        exact_pre_gui=bool(pending_gui))
        else:
            app = _docker_inspect(sweep_v3.APP)
            search = _docker_inspect(sweep_v3.SEARCH)
            if app is None and search is None:
                require(not any(row.get('event') == 'step_intent' and
                                row.get('step') == f'{pair}-seed'
                                for row in scoped),
                        'unreceipted seed may have mutated an absent pair')
            else:
                witness = _unreceipted_preseed_witness(pair, scoped, old)
                unreceipted = True
    _retryable_interruption(scoped,
                            known_neutral_timeout=bool(known_timeout),
                            abandoned_gui_terminal=bool(pending_gui and
                                                        driver_terminal),
                            unreceipted_preseed_equivalent=unreceipted)
    return {'schema': 'envloop-magento-clean-attempt-audit-private-v4',
            'status': 'invalid_infrastructure_attempt_before_gui_mutation',
            'case_index': index, 'attempt': 0,
            'task_id': case['task_id'],
            'package_sha256': case['package_sha256'],
            'plan_sha256': frozen['plan_sha256'],
            'freeze_v4_sha256': sha((json.dumps(frozen, indent=2,
                                               sort_keys=True) + '\n').encode()),
            'journal_sha256_before_audit': sha(journal.read_bytes()),
            'audit_observed_time': time.time(),
            'active_pair': pair, 'material_witness': witness,
            'classification': (known_timeout if known_timeout else
                               'abandoned_gui_no_material_change' if pending_gui else
                               'unreceipted_live_preseed_equivalent' if unreceipted else
                               'host_or_step_timeout_pre_gui_no_process_failure'),
            'gui_driver_terminal_at_audit': driver_terminal,
            'whole_case_retry_cap_per_id': 1,
            'study_wide_retry_cap': RETRY_CAP,
            'model_calls': 0, 'official_final_admitted': 0}


def _stable_audit(record: dict) -> dict:
    result = json.loads(json.dumps(record))
    result.pop('audit_observed_time', None)
    witness = result.get('material_witness')
    if isinstance(witness, dict) and witness.get('state') == (
            'unreceipted_live_preseed_equivalent'):
        # Container logs are retained by hash at the first audit; they may
        # grow while the read-only material state stays unchanged.
        witness.pop('diagnostic_hashes', None)
    return result


def _verify_unreceipted_receipt(previous: Path, index: int,
                               scoped: list[dict], audit: dict,
                               old: dict) -> None:
    pair = audit.get('active_pair')
    witness = audit.get('material_witness', {})
    path = previous / f'case-{index:03d}' / str(pair)
    starts = [row for row in scoped if row.get('event') == 'step_intent' and
              row.get('step') == f'{pair}-prepare']
    require(pair in ('positive', 'negative') and
            len(starts) == 1 and
            not (path / 'prepare.private.json').exists() and
            not any(row.get('event') == 'step_intent' and
                    row.get('step') == f'{pair}-seed' for row in scoped) and
            witness.get('state') == 'unreceipted_live_preseed_equivalent' and
            witness.get('task_seeded') is False and
            witness.get('material_equal_exact') is True,
            'unreceipted retry crossed seed or lacks live adoption proof')
    fields = witness['material_current_fields']
    require(fields.get('source_search_sha256') == sweep_v3.SEARCH_SHA and
            fields.get('search_documents') == 181 and
            fields.get('cron_config_sha256') ==
            old['runtime']['cron_config_sha256'] and
            fields.get('price_rows') == 8156 and
            fields.get('price_changed_rows') == 0 and
            fields.get('price_key_sets_equal') is True and
            fields.get('live_price_sha256') ==
            fields.get('replica_price_sha256') and
            fields.get('quote_pages') == 0 and
            sha(encode(fields)) == witness['material_current_sha256'],
            'unreceipted pair source/cron/price/quote proof changed')
    identities = witness['containers']
    require(len(identities) == 2 and
            [row['name'] for row in identities] ==
            [sweep_v3.APP, sweep_v3.SEARCH] and
            [row['image_sha256'] for row in identities] ==
            [IMAGE, NATIVE_SEARCH_IMAGE] and
            all(row.get('mount_count') == 0 for row in identities) and
            fields['app_id_sha256'] == identities[0]['container_id_sha256'] and
            fields['search_id_sha256'] == identities[1]['container_id_sha256'],
            'unreceipted pair exact no-mount identities changed')
    upper = next((row['time'] for row in reversed(scoped)
                  if row.get('event') == 'attempt_stopped'),
                 audit['audit_observed_time'])
    for row in identities:
        created = datetime.fromisoformat(row['created'].replace(
            'Z', '+00:00')).timestamp()
        require(starts[0]['time'] - 2 <= created <= upper + 2,
                'unreceipted pair creation escaped prepare intent window')
    diagnostic = witness.get('diagnostic_hashes', {})
    require(set(diagnostic) == {sweep_v3.APP, sweep_v3.SEARCH} and
            all(len(value) == 64 and
                all(char in '0123456789abcdef' for char in value)
                for record in diagnostic.values() for value in record.values()) and
            all(set(record) == {'inspect_sha256', 'stdout_log_sha256',
                                'stderr_log_sha256'}
                for record in diagnostic.values()),
            'unreceipted Docker inspect/log diagnostics missing')


def _cleanup_step(journal: Path, case_index: int, container: dict,
                  action: str) -> None:
    name = container['name']
    expected = container['container_id_sha256']
    events = read_journal(journal)
    matching = [row for row in events if row.get('event') == 'cleanup_step_intent'
                and row.get('index') == case_index and row.get('name') == name
                and row.get('action') == action and
                row.get('container_id_sha256') == expected]
    info = _docker_inspect(name)
    if info is None:
        removal = [row for row in events if row.get('event') ==
                   'cleanup_step_intent' and row.get('index') == case_index
                   and row.get('name') == name and row.get('action') == 'rm'
                   and row.get('container_id_sha256') == expected]
        require(len(removal) == 1,
                'container disappeared without an exact removal intent')
        return
    require(sha(info['Id'].encode()) == expected and
            info['Image'] == container['image_sha256'] and
            info.get('Mounts') == [],
            'cleanup refused changed identity, image, or mounted container')
    if action == 'stop' and not info['State']['Running']:
        require(len(matching) == 1,
                'container stopped without an exact stop intent')
        return
    require(not matching, 'cleanup action already dispatched but not reconciled')
    append_event(journal, {'event': 'cleanup_step_intent',
                           'index': case_index, 'attempt': 0,
                           'name': name, 'action': action,
                           'container_id_sha256': expected,
                           'official_final_admitted': 0})
    result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                             action, name], capture_output=True, timeout=70)
    require(result.returncode == 0,
            'exact disposable pair cleanup stopped; inspect before resuming')
    append_event(journal, {'event': 'cleanup_step_finished',
                           'index': case_index, 'attempt': 0,
                           'name': name, 'action': action,
                           'container_id_sha256': expected,
                           'stdout_sha256': sha(result.stdout),
                           'stderr_sha256': sha(result.stderr),
                           'official_final_admitted': 0})


def reconcile_attempt(plan: Path, plan_sha256: str, source: Path,
                      old_freeze: Path, freeze_v4: Path, run_dir: Path,
                      *, mode: str) -> dict:
    frozen, old, freeze_sha = validate_freeze(
        freeze_v4, old_freeze, plan, plan_sha256, source)
    cases = validate_plan(plan, plan_sha256)
    journal = run_dir / 'journal.private.jsonl'
    fd = _lock()
    try:
        events = read_journal(journal)
        validate_run_header(events, freeze_sha, frozen)
        validate_case_sequence(events, cases)
        validate_chunk_boundaries(events, cases, frozen, freeze_sha)
        validate_attempt_inventory(run_dir, events)
        validate_completed_prefix(run_dir, events, cases,
                                  old['runtime_fingerprint_sha256'])
        require(len([row for row in events if row.get('event') ==
                     'dispatch_started']) > len([
                         row for row in events if row.get('event') in
                         ('chunk_completed', 'run_completed')]),
                'reconciliation requires an open bounded dispatch')
        completed = [row for row in events if row.get('event') ==
                     'case_completed']
        index = len(completed)
        require(index < 100, 'no interrupted candidate remains')
        base = attempt_dir(run_dir, index, 0)
        audit_path = base / 'reconciliation-audit.private.json'
        intent_path = base / 'reconciliation-intent.private.json'
        receipt_path = base / 'reconciliation.private.json'
        if receipt_path.exists():
            require(mode == 'cleanup',
                    'completed reconciliation is not a new read-only audit')
            receipt, receipt_sha = read_json(receipt_path)
            audit, audit_sha = read_json(audit_path)
            intent, intent_sha = read_json(intent_path)
            require(receipt.get('schema') ==
                    'envloop-magento-clean-cleanup-private-v4' and
                    receipt.get('case_index') == index and
                    receipt.get('task_id') == cases[index]['task_id'] and
                    receipt.get('package_sha256') ==
                    cases[index]['package_sha256'] and
                    receipt.get('plan_sha256') == plan_sha256 and
                    receipt.get('freeze_v4_sha256') == freeze_sha and
                    receipt.get('audit_sha256') == audit_sha and
                    receipt.get('cleanup_intent_sha256') == intent_sha and
                    intent.get('material_witness') ==
                    audit.get('material_witness') ==
                    receipt.get('material_witness') and
                    receipt.get('both_containers_absent') is True and
                    receipt.get('model_calls') ==
                    receipt.get('official_final_admitted') == 0,
                    'saved cleanup receipt differs from interrupted case')
            sweep_v3.assert_absent()
            matches = [row for row in events if row.get('event') ==
                       'attempt_reconciled' and row.get('index') == index]
            if not matches:
                require(len([row for row in events if row.get('event') ==
                             'attempt_reconciled']) < RETRY_CAP,
                        'study-wide retry cap reached before journal recovery')
                append_event(journal, {'event': 'attempt_reconciled',
                                       'index': index, 'attempt': 0,
                                       'classification': audit['classification'],
                                       'reconciliation_sha256': receipt_sha,
                                       'audit_sha256': receipt['audit_sha256'],
                                       'both_containers_absent': True,
                                       'model_calls': 0,
                                       'official_final_admitted': 0})
            else:
                require(len(matches) == 1 and
                        matches[0].get('reconciliation_sha256') == receipt_sha,
                        'duplicate or changed reconciliation event')
            return {'status': 'exact_pair_retired_for_one_whole_case_retry',
                    'case_index': index,
                    'reconciliation_sha256': receipt_sha,
                    'official_final_admitted': 0}
        if mode == 'audit':
            require(not audit_path.exists() and not intent_path.exists(),
                    'audit already exists; use cleanup or resolve its mismatch')
            record = inspect_interruption(run_dir, journal, cases,
                                          frozen, old)
            record['freeze_v4_sha256'] = freeze_sha
            digest = private_new(audit_path, record)
            return {'status': record['status'],
                    'case_index': index, 'audit_sha256': digest,
                    'official_final_admitted': 0}
        require(mode == 'cleanup' and audit_path.is_file(),
                'read-only infrastructure audit required before cleanup')
        audited, audit_sha = read_json(audit_path)
        require(audited.get('schema') ==
                'envloop-magento-clean-attempt-audit-private-v4' and
                audited.get('case_index') == index and
                audited.get('task_id') == cases[index]['task_id'] and
                audited.get('plan_sha256') == plan_sha256 and
                audited.get('freeze_v4_sha256') == freeze_sha and
                audited.get('model_calls') ==
                audited.get('official_final_admitted') == 0,
                'reconciliation audit was altered or belongs to another case')
        if not intent_path.exists():
            current = inspect_interruption(run_dir, journal, cases,
                                           frozen, old)
            current['freeze_v4_sha256'] = freeze_sha
            require(_stable_audit(current) == _stable_audit(audited),
                    'live pair or material state changed after read-only audit')
            intent = {'schema': 'envloop-magento-clean-cleanup-intent-private-v4',
                      'case_index': index, 'attempt': 0,
                      'task_id': cases[index]['task_id'],
                      'audit_sha256': audit_sha,
                      'journal_sha256_before_cleanup': sha(journal.read_bytes()),
                      'active_pair': audited['active_pair'],
                      'material_witness': audited['material_witness'],
                      'model_calls': 0, 'official_final_admitted': 0}
            intent_sha = private_new(intent_path, intent)
            append_event(journal, {'event': 'reconciliation_cleanup_intent',
                                   'index': index, 'attempt': 0,
                                   'intent_sha256': intent_sha,
                                   'audit_sha256': audit_sha,
                                   'official_final_admitted': 0})
        else:
            intent, intent_sha = read_json(intent_path)
            matches = [row for row in events if row.get('event') ==
                       'reconciliation_cleanup_intent' and
                       row.get('index') == index and
                       row.get('intent_sha256') == intent_sha]
            if not matches:
                require(sha(journal.read_bytes()) ==
                        intent.get('journal_sha256_before_cleanup'),
                        'cleanup intent without matching journal boundary')
                current = inspect_interruption(run_dir, journal, cases,
                                               frozen, old)
                current['freeze_v4_sha256'] = freeze_sha
                require(_stable_audit(current) == _stable_audit(audited),
                        'material state changed before cleanup intent recovery')
                append_event(journal, {
                    'event': 'reconciliation_cleanup_intent',
                    'index': index, 'attempt': 0,
                    'intent_sha256': intent_sha,
                    'audit_sha256': audit_sha,
                    'official_final_admitted': 0})
                events = read_journal(journal)
            require(intent.get('schema') ==
                    'envloop-magento-clean-cleanup-intent-private-v4' and
                    intent.get('case_index') == index and
                    intent.get('audit_sha256') == audit_sha and
                    intent.get('material_witness') ==
                    audited.get('material_witness') and
                    any(row.get('event') == 'reconciliation_cleanup_intent' and
                        row.get('index') == index and
                        row.get('intent_sha256') == intent_sha for row in events),
                    'partial cleanup lacks its exact immutable intent')
        pair = audited['active_pair']
        if pair is not None:
            containers = audited['material_witness']['containers']
            require([row['name'] for row in containers] ==
                    [sweep_v3.APP, sweep_v3.SEARCH],
                    'cleanup pair identities changed')
            for item in containers:
                _cleanup_step(journal, index, item, 'stop')
                _cleanup_step(journal, index, item, 'rm')
        sweep_v3.assert_absent()
        require(len([row for row in read_journal(journal)
                     if row.get('event') == 'attempt_reconciled']) < RETRY_CAP,
                'study-wide retry cap reached before authorization')
        receipt = {
            'schema': 'envloop-magento-clean-cleanup-private-v4',
            'status': 'exact_pair_retired_for_one_whole_case_retry',
            'case_index': index, 'attempt': 0,
            'task_id': cases[index]['task_id'],
            'package_sha256': cases[index]['package_sha256'],
            'plan_sha256': plan_sha256, 'freeze_v4_sha256': freeze_sha,
            'audit_sha256': audit_sha, 'cleanup_intent_sha256': intent_sha,
            'active_pair': pair, 'material_witness':
            audited['material_witness'],
            'both_containers_absent': True,
            'whole_case_retry_cap_per_id': 1,
            'study_wide_retry_cap': RETRY_CAP,
            'model_calls': 0, 'official_final_admitted': 0,
        }
        digest = private_new(receipt_path, receipt)
        append_event(journal, {'event': 'attempt_reconciled',
                               'index': index, 'attempt': 0,
                               'classification': audited['classification'],
                               'reconciliation_sha256': digest,
                               'audit_sha256': audit_sha,
                               'both_containers_absent': True,
                               'model_calls': 0,
                               'official_final_admitted': 0})
        return {'status': receipt['status'], 'case_index': index,
                'reconciliation_sha256': digest,
                'study_wide_retries_authorized': len([
                    row for row in read_journal(journal) if row.get('event') ==
                    'attempt_reconciled']),
                'official_final_admitted': 0}
    finally:
        _unlock(fd)


def audit_campaign(plan: Path, plan_sha256: str, source: Path,
                   old_freeze: Path, freeze_v4: Path,
                   run_dir: Path) -> dict:
    frozen, old, freeze_sha = validate_freeze(
        freeze_v4, old_freeze, plan, plan_sha256, source)
    cases = validate_plan(plan, plan_sha256)
    journal = run_dir / 'journal.private.jsonl'
    events = read_journal(journal)
    validate_run_header(events, freeze_sha, frozen)
    validate_case_sequence(events, cases)
    validate_chunk_boundaries(events, cases, frozen, freeze_sha)
    validate_attempt_inventory(run_dir, events)
    completed = [row for row in events if row.get('event') == 'case_completed']
    require(len(completed) == 100 and
            events[-1].get('event') == 'run_completed' and
            events[-1].get('distinct_cases') == 100 and
            events[-1].get('model_calls') ==
            events[-1].get('official_final_admitted') == 0,
            '100 distinct frozen GUI cases have not completed')
    reconciled = [row for row in events if row.get('event') ==
                  'attempt_reconciled']
    require(len(reconciled) <= RETRY_CAP and
            events[-1].get('infrastructure_retries') == len(reconciled),
            'study-wide retry accounting changed')
    receipts = []
    allowed_clocks = 0
    for index, case in enumerate(cases):
        row = completed[index]
        number = row['attempt']
        digest = verify_finished_attempt(
            run_dir, events, index, number, case,
            old['runtime_fingerprint_sha256'])
        require(row.get('calibration_sha256') == digest,
                'journal and candidate calibration differ')
        case_dir = attempt_dir(run_dir, index, number) / f'case-{index:03d}'
        calibration, _ = read_json(case_dir / 'calibration.private.json')
        for pair in ('positive', 'negative'):
            prepared, prep_sha = read_json(case_dir / pair / 'prepare.private.json')
            old_contract.validate_prepared(
                prepared, config_sha256=old['runtime']['cron_config_sha256'])
            require(calibration['receipt_sha256'][f'{pair}_prepare'] == prep_sha,
                    'prepared pair differs from frozen runtime or calibration')
            runtime, runtime_sha = read_json(case_dir / pair / 'runtime.private.json')
            require(calibration['receipt_sha256'][f'{pair}_runtime'] == runtime_sha and
                    runtime['app'] == prepared['application_clone'] and
                    runtime['sidecar_id_sha256'] ==
                    prepared['search_sidecar_id_sha256'],
                    'runtime container identity differs from preparation')
        reset, _ = read_json(case_dir / 'negative/fresh-reset.private.json')
        allowed_clocks += bool(reset.get('allowed_volatile_fields'))
        if number == 1:
            previous = attempt_dir(run_dir, index, 0)
            cleanup, cleanup_sha = read_json(
                previous / 'reconciliation.private.json')
            audit, audit_sha = read_json(
                previous / 'reconciliation-audit.private.json')
            intent, intent_sha = read_json(
                previous / 'reconciliation-intent.private.json')
            rows = [event for event in reconciled if event.get('index') == index]
            require(len(rows) == 1 and
                    rows[0].get('reconciliation_sha256') == cleanup_sha and
                    rows[0].get('audit_sha256') == audit_sha and
                    rows[0].get('classification') == audit['classification'] and
                    cleanup['cleanup_intent_sha256'] == intent_sha and
                    cleanup['audit_sha256'] == audit_sha and
                    cleanup['task_id'] == case['task_id'] and
                    cleanup['package_sha256'] == case['package_sha256'] and
                    cleanup['plan_sha256'] == plan_sha256 and
                    cleanup['freeze_v4_sha256'] == freeze_sha and
                    cleanup['both_containers_absent'] is True and
                    cleanup['model_calls'] ==
                    cleanup['official_final_admitted'] == 0 and
                    audit['classification'] in (
                        'host_or_step_timeout_pre_gui_no_process_failure',
                        'known_neutral_cms_menu_timeout_before_edit',
                        'known_neutral_page_title_timeout_before_edit',
                        'abandoned_gui_no_material_change',
                        'unreceipted_live_preseed_equivalent') and
                    intent['material_witness'] ==
                    audit['material_witness'] == cleanup['material_witness'],
                    'whole-case retry lacks the exact invalid-attempt evidence')
            prior = [event for event in case_events(events, index)
                     if event.get('attempt') == 0 and event.get('event') not in (
                         'reconciliation_cleanup_intent',
                         'cleanup_step_intent', 'cleanup_step_finished',
                         'attempt_reconciled')]
            known = _known_neutral_timeout(previous, index, prior)
            pending_gui = _pending_gui_step(previous, index, prior)
            unreceipted = (audit['classification'] ==
                           'unreceipted_live_preseed_equivalent')
            expected_class = (known if known else
                              'abandoned_gui_no_material_change' if pending_gui else
                              'unreceipted_live_preseed_equivalent' if unreceipted else
                              'host_or_step_timeout_pre_gui_no_process_failure')
            require(audit['classification'] == expected_class,
                'original failure classification changed')
            if pending_gui:
                pair = pending_gui.split('-', 1)[0]
                baseline_path = (previous / f'case-{index:03d}' / pair /
                                 'normalized-baseline.private.json')
                baseline, baseline_sha = read_json(baseline_path)
                witness = audit['material_witness']
                require(audit.get('gui_driver_terminal_at_audit') is True and
                        witness.get('state') == 'seeded_pre_gui' and
                        witness.get('material_reference_sha256') == baseline_sha and
                        witness.get('material_equal_exact') is True and
                        witness.get('material_current_snapshot') == baseline and
                        witness.get('live_runtime_check', {}).get(
                            'cron_config_sha256') ==
                        old['runtime']['cron_config_sha256'] and
                        witness.get('live_runtime_check', {}).get(
                            'price_rows') == 8156 and
                        witness.get('live_runtime_check', {}).get(
                            'price_changed_rows') == 0 and
                        witness.get('live_runtime_check', {}).get(
                            'price_key_sets_equal') is True and
                        witness.get('live_runtime_check', {}).get(
                            'live_price_sha256') ==
                        witness.get('live_runtime_check', {}).get(
                            'replica_price_sha256') and
                        witness.get('allowed_volatile_fields') == [],
                        'abandoned GUI did not preserve exact saved baseline')
            if unreceipted:
                _verify_unreceipted_receipt(previous, index, prior,
                                            audit, old)
            _retryable_interruption(prior, known_neutral_timeout=bool(known),
                                    abandoned_gui_terminal=bool(pending_gui),
                                    unreceipted_preseed_equivalent=unreceipted)
        receipts.append(digest)
    require(len([row for row in events if row.get('event') ==
                 'case_attempt_started']) == 100 + len(reconciled),
            'attempt count differs from bounded retry count')
    classes = sorted({row['classification'] for row in reconciled})
    return {
        'schema': 'envloop-magento-clean-100-gui-controls-public-v4',
        'status': '100_fresh_evaluator_gui_controls_passed_no_final_admissions',
        'date': '2026-09-29',
        'parent_v3_freeze_sha256': frozen['parent_v3_freeze_sha256'],
        'max_cases_per_dispatch': MAX_CHUNK_CASES,
        'partial_chunk_receipts': len([row for row in events if row.get('event') ==
                                      'chunk_completed']),
        'parent_cron_freeze_sha256': frozen['parent_cron_freeze_sha256'],
        'resumable_freeze_sha256': freeze_sha,
        'runtime_fingerprint_sha256': old['runtime_fingerprint_sha256'],
        'pinned_python_runtime_sha256': frozen['pinned_python_runtime_sha256'],
        'train_only_release_guard_pilot_sha256':
        frozen['train_only_release_guard_pilot_sha256'],
        'v2_retirement_public_sha256': frozen['v2_retirement_public_sha256'],
        'plan_sha256': plan_sha256,
        'ordered_task_identity_sha256': frozen['ordered_task_identity_sha256'],
        'journal_sha256': sha(journal.read_bytes()),
        'calibration_receipts_sha256': sha(('\n'.join(receipts) + '\n').encode()),
        'distinct_candidate_controls': 100,
        'positive_saved_state_pass': 100,
        'wrong_variant_saved_state_rejected': 100,
        'fresh_clone_material_reset_pass': 100,
        'bounded_invalid_infrastructure_retries': len(reconciled),
        'invalid_attempts_by_classification': {
            name: sum(row['classification'] == name for row in reconciled)
            for name in classes},
        'study_wide_infrastructure_retry_cap': RETRY_CAP,
        'journal_wall_seconds': max(0.0, events[-1]['time'] - events[0]['time']),
        'reset_clock_only_exception_count': allowed_clocks,
        'historical_controls_reused': 0,
        'v2_partial_controls_excluded': 14,
        'model_calls': 0, 'official_final_admitted': 0,
    }


def _private_paths(*paths: Path) -> None:
    private = (ROOT / 'work').resolve()
    require(all(path.resolve().is_relative_to(private) for path in paths),
            'Magento private input/output must remain under ignored work/')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'run', 'reconcile', 'audit'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--parent-freeze', type=Path, required=True)
    parser.add_argument('--freeze-v4', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-cases', type=int)
    parser.add_argument('--mode', choices=('audit', 'cleanup'))
    parser.add_argument('--public-out', type=Path)
    args = parser.parse_args()
    plan, source, parent, v4 = (path.resolve() for path in
                                (args.plan, args.source,
                                 args.parent_freeze, args.freeze_v4))
    _private_paths(plan, source, parent, v4)
    require(v4 == PRIVATE_FREEZE.resolve(),
            'clean_v4_requires_its_exact_new_private_freeze_path')
    require((args.action == 'run' and args.max_cases is not None) or
            (args.action != 'run' and args.max_cases is None),
            'only run accepts the explicit bounded --max-cases option')
    require(args.action == 'freeze' or args.run_dir is not None,
            'run/reconcile/audit require the original private campaign directory')
    run_dir = args.run_dir.resolve() if args.run_dir is not None else None
    if run_dir is not None:
        _private_paths(run_dir)
        require(run_dir == V4_RUN.resolve(),
                'clean_v4_requires_its_exact_new_run_directory')
    if args.action == 'freeze':
        require(not v4.exists() and args.run_dir is None,
                'v4 freeze must precede candidate controls')
        require(args.public_out is not None and
                args.public_out.resolve() == PUBLIC_FREEZE.resolve() and
                not PUBLIC_FREEZE.exists(),
                'fresh dated public freeze receipt required before controls')
        receipt = build_freeze(ROOT, parent, plan, args.plan_sha256, source)
        digest = private_new(v4, receipt)
        public = {
            'schema': 'envloop-magento-clean-100-freeze-public-v4',
            'date': '2026-09-29',
            'status': 'pre_result_bounded_chunk_protocol_frozen',
            'private_freeze_sha256': digest,
            'parent_v3_freeze_sha256': receipt['parent_v3_freeze_sha256'],
            'max_cases_per_dispatch': MAX_CHUNK_CASES,
            'parent_cron_freeze_sha256': receipt['parent_cron_freeze_sha256'],
            'runtime_fingerprint_sha256':
            receipt['parent_runtime_fingerprint_sha256'],
            'pinned_python_runtime_sha256':
            receipt['pinned_python_runtime_sha256'],
            'train_only_release_guard_pilot_sha256':
            receipt['train_only_release_guard_pilot_sha256'],
            'v2_retirement_public_sha256':
            receipt['v2_retirement_public_sha256'],
            'historical_v2_controls_reused': 0,
            'historical_v3_controls_reused': 0,
            'plan_sha256': args.plan_sha256,
            'ordered_task_identity_sha256':
            receipt['ordered_task_identity_sha256'],
            'whole_case_retry_cap_per_id': PER_CASE_RETRY_CAP,
            'study_wide_infrastructure_retry_cap': RETRY_CAP,
            'fresh_gui_controls_required': 100,
            'model_calls': 0, 'official_final_admitted': 0,
        }
        raw = (json.dumps(public, indent=2, sort_keys=True) + '\n').encode()
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        out_fd = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o644)
        with os.fdopen(out_fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        result = {'status': receipt['status'],
                  'freeze_v4_sha256': digest,
                  'public_receipt_sha256': sha(raw),
                  'parent_cron_freeze_sha256':
                  receipt['parent_cron_freeze_sha256'],
                  'official_final_admitted': 0}
    elif args.action == 'run':
        result = run_campaign(plan, args.plan_sha256, source, parent, v4,
                              run_dir, resume=args.resume,
                              max_cases=args.max_cases)
    elif args.action == 'reconcile':
        require(args.mode in ('audit', 'cleanup'),
                'operator reconciliation requires explicit audit or cleanup')
        result = reconcile_attempt(plan, args.plan_sha256, source, parent,
                                   v4, run_dir, mode=args.mode)
    else:
        require(args.public_out is not None and
                args.public_out.resolve().is_relative_to(
                    (ROOT / 'docs/evidence').resolve()) and
                not args.public_out.exists(),
                'audit requires a fresh English public aggregate path')
        result = audit_campaign(plan, args.plan_sha256, source, parent,
                                v4, run_dir)
        raw = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        result = {'status': result['status'],
                  'public_sha256': sha(raw), 'official_final_admitted': 0}
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
