"""Read-only independent audit of a completed Magento v4 journal prefix.

The frozen campaign began with 2 + 5 + 5 + 5 + 5 completed controls. Later
requests name an exact completed boundary (27, 32, ..., 97, or 100). The
reader stops at that boundary and ignores any later live append. It never
contacts Docker, performs a GUI action, dispatches a task, or calls a model.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re

from tools import audit_magento_v4_partial_batch_20260929 as first
from tools import audit_magento_v4_seven_prefix_20260929 as seven
from tools import audit_magento_v4_seventeen_prefix_20260929 as seventeen
from tools import audit_magento_v4_twelve_prefix_20260929 as twelve
from tools import audit_magento_v4_twenty_two_prefix_20260930 as twenty_two
from tools import magento_clean_100_v4 as v4


SCHEMA = 'envloop-magento-v4-completed-prefix-independent-audit-public-v1'
BASE_COUNT = twenty_two.COMPLETED_COUNT
BASE_ROWS = twenty_two.PREFIX_ROWS
VALID_COUNTS = (BASE_COUNT, *range(27, 100, 5), 100)
BASE_PUBLIC = Path(
    'docs/evidence/magento-v4-first-twenty-two-independent-audit-2026-09-30.json')
ATTEMPT_PREFIX = re.compile(r'case-([0-9]{3})-')
AUDIT_ERROR = first.AuditError
RETRY_CLASSES = frozenset({
    'host_or_step_timeout_pre_gui_no_process_failure',
    'known_neutral_cms_menu_timeout_before_edit',
    'known_neutral_page_title_timeout_before_edit',
    'abandoned_gui_no_material_change',
    'unreceipted_live_preseed_equivalent',
})
CASE_EVENTS = frozenset({
    'case_attempt_started', 'step_intent', 'step_finished',
    'step_timeout_uncertain', 'pair_cleanup_verified',
    'task_gui_calibrated', 'case_completed', 'attempt_stopped',
    'reconciliation_cleanup_intent', 'cleanup_step_intent',
    'cleanup_step_finished', 'attempt_reconciled',
})
SHARED_AUDITORS = (
    ('shared_two_case_auditor_source_sha256',
     'tools/audit_magento_v4_partial_batch_20260929.py', first),
    ('shared_seven_case_auditor_source_sha256',
     'tools/audit_magento_v4_seven_prefix_20260929.py', seven),
    ('shared_twelve_case_auditor_source_sha256',
     'tools/audit_magento_v4_twelve_prefix_20260929.py', twelve),
    ('shared_seventeen_case_auditor_source_sha256',
     'tools/audit_magento_v4_seventeen_prefix_20260929.py', seventeen),
    ('shared_twenty_two_case_auditor_source_sha256',
     'tools/audit_magento_v4_twenty_two_prefix_20260930.py', twenty_two),
)


def _count(value: int) -> None:
    first.must(type(value) is int and value in VALID_COUNTS,
               'requested count is not a frozen completed chunk boundary')


def read_completed_prefix(path: Path, completed_count: int) -> tuple[list[dict], bytes]:
    """Read only the requested hash-chained prefix, even during a later run."""
    _count(completed_count)
    first.must(path.is_file() and not path.is_symlink(),
               'missing or linked private journal')
    rows: list[dict] = []
    lines: list[bytes] = []
    previous = '0' * 64
    with path.open('rb') as stream:
        for line in stream:
            first.must(line.endswith(b'\n'),
                       'requested chunk has an incomplete journal line')
            try:
                row = json.loads(line)
            except (ValueError, UnicodeDecodeError) as error:
                raise AUDIT_ERROR('invalid journal line before requested boundary') from error
            first.must(type(row) is dict and line == first.canonical(row) and
                       row.get('schema') == v4.JOURNAL_SCHEMA and
                       row.get('sequence') == len(rows) and
                       row.get('previous_line_sha256') == previous,
                       'noncanonical or broken append-only journal prefix')
            rows.append(row)
            lines.append(line)
            previous = first.sha(line)
            if (row.get('event') in ('chunk_completed', 'run_completed') and
                    row.get('completed_distinct_cases') == completed_count):
                first.must(row['event'] == (
                    'run_completed' if completed_count == 100 else
                    'chunk_completed'), 'wrong terminal event for requested boundary')
                if completed_count == 100:
                    first.must(stream.read(1) == b'',
                               'events appended after terminal 100-case receipt')
                return rows, b''.join(lines)
    raise AUDIT_ERROR('requested completed chunk boundary is not present')


def _success_shape(rows: list[dict], index: int, attempt: int) -> None:
    scoped = [row for row in rows if row.get('index') == index and
              row.get('attempt') == attempt]
    expected = [('case_attempt_started', None)]
    for step in first.ORIGINAL_STEPS:
        expected.extend((('step_intent', step), ('step_finished', step)))
        if step == 'positive-gui':
            expected.append(('pair_cleanup_verified', 'positive'))
        elif step == 'negative-gui':
            expected.append(('pair_cleanup_verified', 'negative'))
    expected.extend((('task_gui_calibrated', None), ('case_completed', None)))
    actual = [(row.get('event'), row.get('step') if row.get('event') in
               ('step_intent', 'step_finished') else
               row.get('pair') if row.get('event') == 'pair_cleanup_verified'
               else None) for row in scoped]
    first.must(actual == expected,
               'completed case has a foreign, missing, or reordered event')


def check_completed_chunks(rows: list[dict], cases: list[dict], freeze: dict,
                           freeze_sha: str, completed_count: int) -> dict:
    """Independently check every bounded dispatch after the published 22."""
    _count(completed_count)
    first.must(len(rows) >= BASE_ROWS and len(cases) == 100 and
               rows[-1].get('completed_distinct_cases') == completed_count,
               'journal or frozen plan does not reach requested boundary')
    baseline = twenty_two.check_fifth_chunk(
        rows[:BASE_ROWS], cases, freeze, freeze_sha)
    position = BASE_ROWS
    previous_count = BASE_COUNT
    chunks: list[dict] = []
    dispatches: list[dict] = []
    while previous_count < completed_count:
        next_count = min(previous_count + 5, 100)
        first.must(position < len(rows) and
                   rows[position].get('event') == 'dispatch_started',
                   'completed chunk has no single bounded dispatch')
        dispatch = rows[position]
        capacity = 5 if next_count < 100 else 100 - previous_count
        first.must(dispatch.get('completed_before_dispatch') == previous_count and
                   type(dispatch.get('max_cases')) is int and
                   (dispatch['max_cases'] == 5 if next_count < 100 else
                    capacity <= dispatch['max_cases'] <= 5) and
                   dispatch.get('freeze_v4_sha256') == freeze_sha and
                   dispatch.get('parent_v3_freeze_sha256') ==
                       freeze['parent_v3_freeze_sha256'] and
                   dispatch.get('model_calls') ==
                       dispatch.get('official_final_admitted') == 0,
                   'dispatch changes frozen source, order, or five-case cap')
        end = next((i for i in range(position + 1, len(rows)) if
                    rows[i].get('event') in ('chunk_completed', 'run_completed')),
                   None)
        first.must(end is not None,
                   'requested dispatch has no completed chunk receipt')
        body = rows[position + 1:end]
        boundary = rows[end]
        first.must(all(row.get('event') in CASE_EVENTS for row in body) and
                   all(type(row.get('index')) is int and
                       previous_count <= row['index'] < next_count and
                       row.get('attempt') in (0, 1) for row in body),
                   'chunk contains an unrelated or duplicated task event')
        for row in rows[position:end + 1]:
            first.must(row.get('model_calls', 0) in (0, False) and
                       row.get('official_final_admitted', 0) in (0, False),
                       'model or official final work appeared in evaluator chunk')
            if row.get('event') in ('case_attempt_started', 'case_completed',
                                    'attempt_stopped', 'attempt_reconciled'):
                first.must(row.get('model_calls') ==
                           row.get('official_final_admitted') == 0,
                           'case or retry event lost its explicit zero-work guard')
        starts = [row for row in body if row.get('event') ==
                  'case_attempt_started']
        completions = [row for row in body if row.get('event') ==
                       'case_completed']
        reconciled = [row for row in body if row.get('event') ==
                      'attempt_reconciled']
        first.must([row.get('index') for row in completions] ==
                   list(range(previous_count, next_count)) and
                   len(starts) == capacity + len(reconciled) and
                   all(row.get('task_id') == cases[row['index']]['task_id'] and
                       row.get('package_sha256') ==
                           cases[row['index']]['package_sha256']
                       for row in starts) and
                   all(row.get('index') in range(previous_count, next_count)
                       for row in reconciled),
                   'chunk changes ordered one-use task identities or retry count')
        for index in range(previous_count, next_count):
            attempts = [row['attempt'] for row in starts if row['index'] == index]
            done = [row for row in completions if row['index'] == index]
            retried = [row for row in reconciled if row['index'] == index]
            first.must(attempts in ([0], [0, 1]) and len(done) == 1 and
                       done[0].get('attempt') == attempts[-1] and
                       len(retried) == len(attempts) - 1 and
                       all(row.get('attempt') == 0 for row in retried),
                       'case replay or unreconciled retry changed')
            _success_shape(body, index, attempts[-1])
        completed = [row for row in rows[:end] if row.get('event') ==
                     'case_completed']
        receipts = [row['calibration_sha256'] for row in completed]
        first.must(boundary.get('event') == (
                       'run_completed' if next_count == 100 else
                       'chunk_completed') and
                   boundary.get('max_cases') == dispatch['max_cases'] and
                   boundary.get('dispatch_sequence') == dispatch['sequence'] and
                   boundary.get('freeze_v4_sha256') == freeze_sha and
                   boundary.get('parent_v3_freeze_sha256') ==
                       freeze['parent_v3_freeze_sha256'] and
                   boundary.get('completed_distinct_cases') == next_count and
                   boundary.get('newly_completed_this_dispatch') == capacity and
                   boundary.get('ordered_completed_task_identity_sha256') ==
                       v4.case_identity_digest(cases[:next_count]) and
                   boundary.get('completed_calibration_receipts_sha256') ==
                       first.sha(('\n'.join(receipts) + '\n').encode()) and
                   boundary.get('journal_prefix_sha256') ==
                       first.sha(b''.join(first.canonical(row)
                                          for row in rows[:end])) and
                   boundary.get('infrastructure_retries') ==
                       sum(row.get('event') == 'attempt_reconciled'
                           for row in rows[:end]) and
                   boundary['infrastructure_retries'] <=
                       freeze['study_wide_infrastructure_retry_cap'] and
                   boundary.get('model_calls') ==
                       boundary.get('official_final_admitted') == 0 and
                   (next_count != 100 or boundary.get('distinct_cases') == 100),
                   'completed chunk receipt or bounded retry total changed')
        dispatches.append(dispatch)
        chunks.append(boundary)
        previous_count, position = next_count, end + 1
    first.must(position == len(rows) and
               sum(row.get('event') == 'run_started' for row in rows) == 1 and
               sum(row.get('event') == 'dispatch_started' for row in rows) ==
                   len(baseline['dispatches']) + len(dispatches) and
               sum(row.get('event') in ('chunk_completed', 'run_completed')
                   for row in rows) == len(baseline['chunks']) + len(chunks),
               'requested prefix has extra dispatches or boundaries')
    return {'dispatches': (*baseline['dispatches'], *dispatches),
            'chunks': (*baseline['chunks'], *chunks),
            'completed': [row for row in rows if row.get('event') ==
                          'case_completed']}


def _scoped_attempt_inventory(run: Path, rows: list[dict], count: int) -> None:
    parent = run / 'attempts'
    first.must(parent.is_dir() and not parent.is_symlink(),
               'private attempt inventory is absent or linked')
    expected = {f"case-{row['index']:03d}-attempt-{row['attempt']}"
                for row in rows if row.get('event') == 'case_attempt_started'}
    actual = set()
    for path in parent.iterdir():
        match = ATTEMPT_PREFIX.match(path.name)
        if match and int(match[1]) < count:
            first.must(path.is_dir() and not path.is_symlink(),
                       'completed attempt directory is missing or linked')
            actual.add(path.name)
    first.must(actual == expected,
               'completed prefix has an unjournaled or missing attempt')


def _check_retry(run: Path, rows: list[dict], index: int, case: dict,
                 freeze: dict, freeze_sha: str, old: dict) -> str:
    """Reopen the saved invalid attempt and its exact-pair cleanup lineage."""
    previous = v4.attempt_dir(run, index, 0)
    audit, audit_sha = first.read_json(previous / 'reconciliation-audit.private.json')
    intent, intent_sha = first.read_json(previous / 'reconciliation-intent.private.json')
    cleanup, cleanup_sha = first.read_json(previous / 'reconciliation.private.json')
    scoped = [row for row in rows if row.get('index') == index and
              row.get('attempt') == 0]
    reconciled = [row for row in scoped if row.get('event') ==
                  'attempt_reconciled']
    cleanup_intents = [row for row in scoped if row.get('event') ==
                       'reconciliation_cleanup_intent']
    first.must(len(reconciled) == len(cleanup_intents) == 1 and
               audit.get('schema') ==
                   'envloop-magento-clean-attempt-audit-private-v4' and
               audit.get('status') ==
                   'invalid_infrastructure_attempt_before_gui_mutation' and
               intent.get('schema') ==
                   'envloop-magento-clean-cleanup-intent-private-v4' and
               cleanup.get('schema') ==
                   'envloop-magento-clean-cleanup-private-v4' and
               cleanup.get('status') ==
                   'exact_pair_retired_for_one_whole_case_retry' and
               all(item.get('case_index') == index and
                   item.get('task_id') == case['task_id'] and
                   item.get('attempt') == 0 and
                   item.get('model_calls') ==
                       item.get('official_final_admitted') == 0
                   for item in (audit, intent, cleanup)) and
               audit.get('package_sha256') ==
                   cleanup.get('package_sha256') == case['package_sha256'] and
               audit.get('plan_sha256') ==
                   cleanup.get('plan_sha256') == freeze['plan_sha256'] and
               audit.get('freeze_v4_sha256') ==
                   cleanup.get('freeze_v4_sha256') == freeze_sha and
               intent.get('audit_sha256') ==
                   cleanup.get('audit_sha256') ==
                   reconciled[0].get('audit_sha256') == audit_sha and
               cleanup_intents[0].get('intent_sha256') ==
                   cleanup.get('cleanup_intent_sha256') == intent_sha and
               reconciled[0].get('reconciliation_sha256') == cleanup_sha and
               reconciled[0].get('classification') ==
                   audit.get('classification') in RETRY_CLASSES and
               reconciled[0].get('both_containers_absent') is True and
               cleanup.get('both_containers_absent') is True and
               cleanup.get('whole_case_retry_cap_per_id') == 1 and
               cleanup.get('study_wide_retry_cap') ==
                   freeze['study_wide_infrastructure_retry_cap'] and
               intent.get('material_witness') ==
                   audit.get('material_witness') ==
                   cleanup.get('material_witness'),
               'retry identity, audit, intent, or cleanup receipt changed')
    before = rows[:rows.index(cleanup_intents[0])]
    first.must(intent.get('journal_sha256_before_cleanup') ==
               first.sha(b''.join(first.canonical(row) for row in before)) and
               audit.get('journal_sha256_before_audit') ==
                   first.sha(b''.join(first.canonical(row) for row in before)) and
               cleanup_intents[0].get('audit_sha256') == audit_sha,
               'retry cleanup intent is not bound to its prior journal')
    pair = audit.get('active_pair')
    witness = audit.get('material_witness')
    first.must(pair in (None, 'positive', 'negative') and
               cleanup.get('active_pair') == intent.get('active_pair') == pair and
               (pair is None or
                (type(witness) is dict and
                 type(witness.get('containers')) is list and
                 len(witness['containers']) == 2)),
               'retry active pair or material witness changed')
    if pair is not None:
        containers = witness['containers']
        first.must([item.get('name') for item in containers] ==
                   [first.sweep.APP, first.sweep.SEARCH] and
                   [item.get('image_sha256') for item in containers] ==
                   [v4.IMAGE, v4.NATIVE_SEARCH_IMAGE] and
                   all(item.get('mount_count') == 0 and
                       type(item.get('container_id_sha256')) is str and
                       re.fullmatch(r'[0-9a-f]{64}',
                                    item['container_id_sha256']) is not None
                       for item in containers),
                   'retry pair images or no-mount identities changed')
        expected = [(item.get('name'), item.get('container_id_sha256'), action)
                    for item in containers for action in ('stop', 'rm')]
        actions = [(row.get('name'), row.get('container_id_sha256'),
                    row.get('action')) for row in scoped if row.get('event') ==
                   'cleanup_step_intent']
        finishes = [(row.get('name'), row.get('container_id_sha256'),
                     row.get('action')) for row in scoped if row.get('event') ==
                    'cleanup_step_finished']
        first.must(actions == expected and len(finishes) == len(set(finishes)) and
                   all(item in actions for item in finishes) and
                   all(type(row.get('stdout_sha256')) is str and
                       re.fullmatch(r'[0-9a-f]{64}', row['stdout_sha256']) and
                       type(row.get('stderr_sha256')) is str and
                       re.fullmatch(r'[0-9a-f]{64}', row['stderr_sha256'])
                       for row in scoped if row.get('event') ==
                       'cleanup_step_finished'),
                   'retry did not retire the exact witnessed pair')
        if audit['classification'] != 'unreceipted_live_preseed_equivalent':
            pair_dir = previous / f'case-{index:03d}' / pair
            prepared, prepared_sha = first.read_json(
                pair_dir / 'prepare.private.json')
            v4.old_contract.validate_prepared(
                prepared, config_sha256=old['runtime']['cron_config_sha256'])
            first.must(witness.get('prepared_sha256') == prepared_sha,
                       'retry prepared pair differs from material witness')
            if witness.get('state') == 'prepared_unseeded':
                first.must(not (pair_dir / 'seed.private.json').exists() and
                           witness.get('material_reference_sha256') ==
                               prepared_sha and
                           witness.get('allowed_volatile_fields') == [],
                           'unseeded retry crossed the task material boundary')
            else:
                first.must(witness.get('state') in
                           ('seeded_pre_gui', 'saved_gui_state'),
                           'retry has no supported saved material state')
                seed, seed_sha = first.read_json(pair_dir / 'seed.private.json')
                first.must(seed.get('task_id') == case['task_id'] and
                           witness.get('seed_sha256') == seed_sha,
                           'retry seed differs from frozen task')
                control = pair_dir / ('gui-positive' if pair == 'positive'
                                      else 'gui-wrong-variant')
                after = control / 'private-after.json'
                if witness['state'] == 'saved_gui_state':
                    result, _ = first.read_json(control / 'result.json')
                    first.must(after.is_file() and
                               result.get('score', {}).get('score') ==
                                   (1.0 if pair == 'positive' else 0.0) and
                               result['score'].get('independent_saved_state')
                                   is True and
                               result.get('model_calls') ==
                                   result.get('official_final_tasks_admitted')
                                   == 0,
                               'retry saved GUI state has no valid prior score')
                    reference = after
                else:
                    first.must(not after.exists() and
                               not (control / 'result.json').exists(),
                               'pre-GUI retry contains a completed GUI edit')
                    reference = pair_dir / 'normalized-baseline.private.json'
                    if not reference.is_file():
                        reference = pair_dir / 'neutral/private-before.json'
                baseline, baseline_sha = first.read_json(reference)
                current = witness.get('material_current_snapshot')
                first.must(type(current) is dict and
                           witness.get('material_reference_sha256') ==
                               baseline_sha and
                           witness.get('material_current_sha256') ==
                               first.sha(first.canonical(current)) and
                           witness.get('allowed_volatile_fields') ==
                               v4.check_material_reset(baseline, current),
                           'retry material snapshot cannot be independently replayed')
    else:
        first.must(not any(row.get('event') in
                           ('cleanup_step_intent', 'cleanup_step_finished')
                           for row in scoped),
                   'pairless retry has unexpected container cleanup')
    prior = [row for row in scoped if row.get('event') not in
             ('reconciliation_cleanup_intent', 'cleanup_step_intent',
             'cleanup_step_finished', 'attempt_reconciled')]
    if pair == 'negative':
        positive, _ = first.read_json(
            previous / f'case-{index:03d}/positive/gui-positive/result.json')
        first.must(sum(row.get('event') == 'pair_cleanup_verified' and
                       row.get('pair') == 'positive' for row in prior) == 1 and
                   positive.get('score', {}).get('score') == 1.0 and
                   positive['score'].get('independent_saved_state') is True and
                   positive['score'].get('task_id') == case['task_id'] and
                   positive.get('package_sha256') ==
                       case['package_sha256'] and
                   positive.get('model_calls') ==
                       positive.get('official_final_tasks_admitted') == 0,
                   'negative retry lacks its completed native positive')
    known = v4._known_neutral_timeout(previous, index, prior)
    pending = v4._pending_gui_step(previous, index, prior)
    unreceipted = audit['classification'] == 'unreceipted_live_preseed_equivalent'
    expected_class = (known if known else
                      'abandoned_gui_no_material_change' if pending else
                      'unreceipted_live_preseed_equivalent' if unreceipted else
                      'host_or_step_timeout_pre_gui_no_process_failure')
    first.must(audit['classification'] == expected_class,
               'retry classification disagrees with frozen interruption')
    if pending:
        baseline, baseline_sha = first.read_json(
            previous / f'case-{index:03d}' / pending.split('-', 1)[0] /
            'normalized-baseline.private.json')
        first.must(audit.get('gui_driver_terminal_at_audit') is True and
                   witness.get('state') == 'seeded_pre_gui' and
                   witness.get('material_reference_sha256') == baseline_sha and
                   witness.get('material_equal_exact') is True and
                   witness.get('material_current_snapshot') == baseline and
                   witness.get('live_runtime_check', {}).get(
                       'cron_config_sha256') ==
                       old['runtime']['cron_config_sha256'] and
                   witness.get('live_runtime_check', {}).get('price_rows') ==
                       8156 and
                   witness.get('live_runtime_check', {}).get(
                       'price_changed_rows') == 0 and
                   witness.get('live_runtime_check', {}).get(
                       'price_key_sets_equal') is True and
                   witness.get('live_runtime_check', {}).get(
                       'live_price_sha256') ==
                       witness.get('live_runtime_check', {}).get(
                           'replica_price_sha256') and
                   witness.get('allowed_volatile_fields') == [],
                   'abandoned GUI retry lacks exact stable saved-state proof')
    if unreceipted:
        v4._verify_unreceipted_receipt(previous, index, prior, audit, old)
    v4._retryable_interruption(
        prior, known_neutral_timeout=bool(known),
        abandoned_gui_terminal=bool(pending),
        unreceipted_preseed_equivalent=unreceipted)
    return audit['classification']


PUBLIC_FIELDS = {
    'schema', 'date', 'status', 'independent_auditor_source_sha256',
    'shared_twenty_two_case_auditor_source_sha256',
    'shared_seventeen_case_auditor_source_sha256',
    'shared_twelve_case_auditor_source_sha256',
    'shared_seven_case_auditor_source_sha256',
    'shared_two_case_auditor_source_sha256',
    'baseline_twenty_two_public_sha256', 'source_freeze_sha256',
    'source_commit', 'plan_sha256', 'ordered_task_identity_sha256',
    'baseline_twenty_two_journal_prefix_sha256',
    'completed_journal_prefix_sha256', 'last_chunk_receipt_sha256',
    'completed_calibration_receipts_sha256',
    'planned_distinct_candidate_controls',
    'previously_published_candidate_controls',
    'new_candidate_controls_independently_audited',
    'completed_distinct_candidate_controls', 'completed_chunk_receipts_reopened',
    'new_chunk_receipts_reopened', 'last_chunk_new_case_count',
    'positive_saved_state_pass', 'wrong_variant_saved_state_rejected',
    'fresh_clone_material_reset_pass',
    'successful_step_process_receipts_reopened',
    'new_step_process_receipts_reopened', 'pair_cleanup_verified_events',
    'reconciled_same_id_infrastructure_retries',
    'study_wide_infrastructure_retry_cap',
    'invalid_attempts_by_classification',
    'live_disposable_pair_absence_checked',
    'historical_v2_v3_controls_reused', 'model_calls',
    'official_final_admitted',
}


def audit_completed_prefix(repo_root: Path, run_dir: Path,
                           completed_count: int) -> dict:
    """Replay only a fully closed prefix from the frozen private campaign."""
    _count(completed_count)
    root, run = repo_root.resolve(), run_dir.resolve()
    first.must(run == root / first.RUN_REL and run.is_dir() and
               not run_dir.is_symlink(),
               'audit requires exact original private v4 run directory')
    plan, source, cron, freeze_file = (
        root / first.PLAN_REL, root / first.SOURCE_REL,
        root / first.CRON_FREEZE_REL, root / first.V4_FREEZE_REL)
    freeze, old, freeze_sha = first.validate_source_bindings(
        root, plan, source, cron, freeze_file)
    cases = first.validate_plan(plan, freeze['plan_sha256'])
    first.must(v4.case_identity_digest(cases) ==
               freeze['ordered_task_identity_sha256'],
               'ordered frozen candidate identity changed')
    rows, raw = read_completed_prefix(run / 'journal.private.jsonl',
                                      completed_count)
    boundaries = check_completed_chunks(rows, cases, freeze, freeze_sha,
                                        completed_count)
    published, published_sha = first.read_json(root / BASE_PUBLIC)
    shared_hashes = {}
    for key, relative, module in SHARED_AUDITORS:
        digest = first.sha((root / relative).read_bytes())
        first.must(digest == first.sha(Path(module.__file__).read_bytes()) and
                   (published.get(key) == digest if module is not twenty_two
                    else published.get('independent_auditor_source_sha256')
                    == digest),
                   'loaded shared auditor differs from published source')
        shared_hashes[key] = digest
    baseline_raw = b''.join(first.canonical(row) for row in rows[:BASE_ROWS])
    first.must(published.get('schema') == twenty_two.SCHEMA and
               published.get('source_freeze_sha256') == freeze_sha and
               published.get('plan_sha256') == freeze['plan_sha256'] and
               published.get('ordered_task_identity_sha256') ==
                   freeze['ordered_task_identity_sha256'] and
               published.get('completed_distinct_candidate_controls') ==
                   BASE_COUNT and
               published.get('twenty_two_case_journal_prefix_sha256') ==
                   first.sha(baseline_raw) and
               published.get('fifth_chunk_receipt_sha256') ==
                   first.sha(first.canonical(boundaries['chunks'][4])) and
               published.get('independent_auditor_source_sha256') ==
                   first.sha((root /
                       'tools/audit_magento_v4_twenty_two_prefix_20260930.py')
                             .read_bytes()) and
               published.get('model_calls') ==
                   published.get('official_final_admitted') == 0,
               'published 22-case audit no longer binds the frozen prefix')
    v4.validate_run_header(rows, freeze_sha, freeze)
    v4.validate_case_sequence(rows, cases)
    v4.validate_chunk_boundaries(rows, cases, freeze, freeze_sha)
    _scoped_attempt_inventory(run, rows, completed_count)
    preconfig = first.check_preconfig_retry(
        root, run, rows, cases[0], freeze_sha)
    completed = boundaries['completed']
    first.must(len(completed) == completed_count and
               [row.get('index') for row in completed] ==
                   list(range(completed_count)),
               'completed tasks are not the ordered one-use prefix')
    classes = Counter({preconfig['classification']: 1})
    for index in range(1, completed_count):
        attempts = [row for row in rows if row.get('event') ==
                    'case_attempt_started' and row.get('index') == index]
        if len(attempts) == 2:
            classes[_check_retry(run, rows, index, cases[index],
                                 freeze, freeze_sha, old)] += 1
    first.must(sum(classes.values()) <=
               freeze['study_wide_infrastructure_retry_cap'] and
               sum(classes.values()) == sum(row.get('event') ==
                   'attempt_reconciled' for row in rows),
               'study-wide bounded retry accounting changed')
    receipts = []
    for index, row in enumerate(completed):
        attempt = row['attempt']
        seven.check_process_receipts(run, rows, index, attempt)
        receipts.append(first.check_successful_case(
            run, rows, index, attempt, cases[index],
            old['runtime_fingerprint_sha256']))
    first.must(receipts == [row['calibration_sha256'] for row in completed],
               'replayed native calibrations differ from ordered journal')
    final = boundaries['chunks'][-1]
    report = {
        'schema': SCHEMA, 'date': date.today().isoformat(),
        'status': 'completed_v4_evaluator_prefix_independently_audited_no_final_admissions',
        'independent_auditor_source_sha256':
            first.sha(Path(__file__).read_bytes()),
        **shared_hashes,
        'baseline_twenty_two_public_sha256': published_sha,
        'source_freeze_sha256': freeze_sha,
        'source_commit': freeze['source_commit'],
        'plan_sha256': freeze['plan_sha256'],
        'ordered_task_identity_sha256':
            freeze['ordered_task_identity_sha256'],
        'baseline_twenty_two_journal_prefix_sha256': first.sha(baseline_raw),
        'completed_journal_prefix_sha256': first.sha(raw),
        'last_chunk_receipt_sha256': first.sha(first.canonical(final)),
        'completed_calibration_receipts_sha256':
            final['completed_calibration_receipts_sha256'],
        'planned_distinct_candidate_controls': 100,
        'previously_published_candidate_controls': BASE_COUNT,
        'new_candidate_controls_independently_audited':
            completed_count - BASE_COUNT,
        'completed_distinct_candidate_controls': completed_count,
        'completed_chunk_receipts_reopened': len(boundaries['chunks']),
        'new_chunk_receipts_reopened':
            len(boundaries['chunks']) - 5,
        'last_chunk_new_case_count': final['newly_completed_this_dispatch'],
        'positive_saved_state_pass': completed_count,
        'wrong_variant_saved_state_rejected': completed_count,
        'fresh_clone_material_reset_pass': completed_count,
        'successful_step_process_receipts_reopened':
            completed_count * len(first.ORIGINAL_STEPS),
        'new_step_process_receipts_reopened':
            (completed_count - BASE_COUNT) * len(first.ORIGINAL_STEPS),
        'pair_cleanup_verified_events': completed_count * 2,
        'reconciled_same_id_infrastructure_retries': sum(classes.values()),
        'study_wide_infrastructure_retry_cap':
            freeze['study_wide_infrastructure_retry_cap'],
        'invalid_attempts_by_classification': dict(sorted(classes.items())),
        'live_disposable_pair_absence_checked': False,
        'historical_v2_v3_controls_reused': 0,
        'model_calls': 0, 'official_final_admitted': 0,
    }
    first.must(set(report) == PUBLIC_FIELDS,
               'public output field allowlist changed')
    return report


def render_markdown(report: dict) -> str:
    first.must(set(report) == PUBLIC_FIELDS,
               'unexpected public report fields')
    count = report['completed_distinct_candidate_controls']
    new = report['new_candidate_controls_independently_audited']
    remaining = 100 - count
    return (
        f'# Magento v4: independent audit of {count} completed controls\n\n'
        f'This read-only audit reopens the published 22-case prefix and {new} '
        f'additional evaluator GUI controls from the frozen 100-case plan. '
        f'All {count} saved-state positives score 1, wrong-variant controls '
        f'score 0, and fresh-clone material resets pass independent replay. '
        f'The audit reopened {report["successful_step_process_receipts_reopened"]} '
        f'successful native-step process receipts and '
        f'{report["pair_cleanup_verified_events"]} pair-cleanup events. '
        'There were 0 model calls and 0 official final tasks admitted.\n\n'
        f'The exact {count}-case journal prefix and its final chunk receipt '
        'are SHA-256 bound. Later appends do not change this result. '
        f'{report["reconciled_same_id_infrastructure_retries"]} same-ID '
        'infrastructure retries were reconciled within the frozen cap. '
        'Current live disposable-pair absence was not checked by this saved '
        'evidence auditor.\n\n'
        f'{remaining} candidate controls remain outside this prefix. '
        'Historical v2/v3 controls contribute zero; this result does not '
        'establish any model final outcome.\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--completed-count', type=int, required=True)
    parser.add_argument('--public-json', type=Path)
    parser.add_argument('--public-md', type=Path)
    args = parser.parse_args()
    first.must((args.public_json is None) == (args.public_md is None),
               'JSON and Markdown public outputs must be requested together')
    report = audit_completed_prefix(args.repo_root, args.run_dir,
                                    args.completed_count)
    if args.public_json is not None:
        public_dir = (Path(__file__).resolve().parents[1] /
                      'docs/evidence').resolve()
        for target in (args.public_json, args.public_md):
            first.must(target.resolve().is_relative_to(public_dir) and
                       not target.exists() and not target.is_symlink(),
                       'public outputs must be new files under auditor docs/evidence')
        args.public_json.parent.mkdir(parents=True, exist_ok=True)
        with args.public_json.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write('\n')
        with args.public_md.open('x', encoding='utf-8') as stream:
            stream.write(render_markdown(report))
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
