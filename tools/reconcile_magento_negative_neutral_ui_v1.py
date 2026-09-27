"""Retire one stopped Magento negative-neutral CMS menu failure.

The positive control and original failure stay immutable. This tool verifies
the failed negative clone is still at its seeded material baseline, binds the
two disposable container identities, and cleans them before a separately
authorized one-case fresh-clone infrastructure retry. It never scores a model.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from magento_catalog_factory.verify import check_baseline, read_snapshot
from tools.sweep_magento_original_gui_controls_v1 import (
    APP, SEARCH, append_event, assert_absent, sha, write_new,
)


def inspect_expected(name: str, expected_id_sha: str,
                     expected_image_sha: str) -> dict:
    raw = subprocess.check_output(
        ['docker', '--context', 'colima-cua-scale', 'inspect', name],
        timeout=30)
    rows = json.loads(raw)
    require(len(rows) == 1, 'one disposable Magento container required')
    item = rows[0]
    require(sha(item['Id'].encode()) == expected_id_sha and
            item['Image'] == expected_image_sha and
            item['State']['Running'] is True and
            item['Mounts'] == [],
            'live disposable container identity, image or mounts changed')
    return {'name': name, 'id_sha256': expected_id_sha,
            'image_sha256': expected_image_sha}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sweep-dir', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    sweep, plan = args.sweep_dir.resolve(), args.plan.resolve()
    require(sweep.is_relative_to(private) and plan.is_relative_to(private)
            and sha(plan.read_bytes()) == args.plan_sha256
            and 0 <= args.index < 100,
            'private stopped sweep and frozen plan required')
    journal = sweep / 'events.private.jsonl'
    journal_raw = journal.read_bytes()
    events = [json.loads(line) for line in journal_raw.splitlines()]
    require(events and events[-1]['event'] == 'sweep_stopped' and
            events[-1].get('official_final_admitted') == 0 and
            not any(row.get('event') ==
                    'operator_reconciled_negative_neutral_ui_unstable'
                    and row.get('index') == args.index for row in events),
            'original stopped failure must remain unreconciled')
    failures = [row for row in events if row.get('event') ==
                'step_finished' and row.get('index') == args.index and
                row.get('step') == 'negative-neutral']
    require(len(failures) == 1 and failures[0]['exit_code'] != 0 and
            events[-1]['passed'] == args.index - events[0]['start_index'],
            'single negative-neutral failure at this index required')
    require(any(row.get('event') == 'pair_cleanup_verified' and
                row.get('index') == args.index and
                row.get('pair') == 'positive' for row in events) and
            not any(row.get('event') == 'pair_cleanup_verified' and
                    row.get('index') == args.index and
                    row.get('pair') == 'negative' for row in events),
            'positive pair must be cleaned and negative pair still live')
    row = json.loads(plan.read_bytes())['cases']['official_candidate'][args.index]
    case = load_case(plan, args.plan_sha256, row['task_id'])
    base = sweep / f'case-{args.index:03d}'
    positive_result = json.loads((base / 'positive/gui-positive/result.json').read_bytes())
    negative = base / 'negative'
    before_path = negative / 'neutral/private-before.json'
    process_path = negative / 'negative-neutral-process.private.json'
    stderr_path = negative / 'negative-neutral-stderr.private.bin'
    seed_path = negative / 'seed.private.json'
    prepare_path = negative / 'prepare.private.json'
    require(all(path.is_file() for path in
                (before_path, process_path, stderr_path, seed_path,
                 prepare_path)) and
            not (negative / 'neutral/result.json').exists() and
            not (negative / 'neutral/private-after.json').exists() and
            not (negative / 'gui-wrong-variant/result.json').exists() and
            positive_result['score']['score'] == 1.0 and
            positive_result['task_id'] == case['task_id'],
            'failure stage or saved positive control changed')
    process = json.loads(process_path.read_bytes())
    stderr_raw = stderr_path.read_bytes()
    require(process['exit_code'] != 0 and
            process['stderr_sha256'] == failures[0]['stderr_sha256'] ==
            sha(stderr_raw) and
            b'Locator.click: Timeout 60000ms exceeded' in stderr_raw and
            b'element is not visible' in stderr_raw and
            b'data-action="item-edit"' in stderr_raw,
            'retained error is not the bounded native CMS menu failure')
    seed = json.loads(seed_path.read_bytes())
    prepare = json.loads(prepare_path.read_bytes())
    before_raw = before_path.read_bytes()
    before = json.loads(before_raw)
    require(seed['task_id'] == case['task_id'] and
            seed['page_id'] == before['page_id'],
            'seeded quote page binding changed')
    lock_path = ROOT / 'work/magento-original/exclusive-worker.lock'
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        containers = [
            inspect_expected(APP,
                             prepare['application_clone']['container_id_sha256'],
                             prepare['application_clone']['image_sha256']),
            inspect_expected(SEARCH,
                             prepare['search_sidecar_id_sha256'],
                             prepare['search_sidecar_image_sha256']),
        ]
        current = read_snapshot(case, APP, 7794, 7795,
                                seed['page_id'], search_host=SEARCH)
        check_baseline(case, current)
        require(current['database']['prices'] == before['database']['prices'] and
                current['database']['quote'] == before['database']['quote'] and
                current['database']['hashes']['business'] ==
                before['database']['hashes']['business'] and
                current['database']['hashes']['other_catalog'] ==
                before['database']['hashes']['other_catalog'] and
                current['search']['other_documents_sha256'] ==
                before['search']['other_documents_sha256'],
                'failed GUI control changed material application state')
        if args.audit_only:
            print(json.dumps({'status':
                              'negative_neutral_ui_failure_material_state_unchanged',
                              'container_identities_bound': 2,
                              'saved_positive_score': 1.0,
                              'negative_gui_attempted': False,
                              'model_calls': 0,
                              'official_final_admitted': 0}, sort_keys=True))
            return
        intent = {'schema': 'envloop-magento-negative-neutral-ui-cleanup-intent-v1',
                  'index': args.index, 'task_id': case['task_id'],
                  'plan_sha256': args.plan_sha256,
                  'stopped_journal_sha256': sha(journal_raw),
                  'process_stderr_sha256': sha(stderr_raw),
                  'material_before_sha256': sha(before_raw),
                  'material_current_sha256': sha((json.dumps(
                      current, sort_keys=True, separators=(',', ':')) + '\n').encode()),
                  'containers': containers,
                  'model_calls': 0, 'official_final_admitted': 0}
        intent_sha = write_new(negative / 'recovery-cleanup-intent.private.json',
                               intent)
        for name in (APP, SEARCH):
            subprocess.run(['docker', '--context', 'colima-cua-scale',
                            'stop', name], check=True, timeout=60,
                           capture_output=True)
            subprocess.run(['docker', '--context', 'colima-cua-scale',
                            'rm', name], check=True, timeout=30,
                           capture_output=True)
        assert_absent()
        receipt = {'schema': 'envloop-magento-negative-neutral-ui-cleanup-private-v1',
                   'status': 'failed_negative_pair_retired_for_one_fresh_retry',
                   'index': args.index, 'task_id': case['task_id'],
                   'plan_sha256': args.plan_sha256,
                   'cleanup_intent_sha256': intent_sha,
                   'original_journal_sha256': sha(journal_raw),
                   'process_stderr_sha256': sha(stderr_raw),
                   'material_state_unchanged': True,
                   'saved_positive_score': 1.0,
                   'negative_gui_attempted': False,
                   'task_seeded': True,
                   'both_containers_cleaned': True,
                   'model_calls': 0, 'official_final_admitted': 0}
        receipt_sha = write_new(negative / 'recovery-cleanup.private.json',
                                receipt)
        append_event(journal, {
            'event': 'operator_reconciled_negative_neutral_ui_unstable',
            'index': args.index, 'time': time.time(),
            'task_seeded': True,
            'negative_gui_attempted': False,
            'both_containers_cleaned': True,
            'cleanup_receipt_sha256': receipt_sha,
            'model_calls': 0, 'official_final_admitted': 0})
        print(json.dumps({'status': receipt['status'],
                          'cleanup_receipt_sha256': receipt_sha,
                          'official_final_admitted': 0}, sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
