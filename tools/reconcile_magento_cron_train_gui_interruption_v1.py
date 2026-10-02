"""Audit and retire one exact stopped cron-free Magento TRAIN GUI pair.

Audit mode is read-only; cleanup mode requires its saved evidence, rechecks the
live pair, then removes only those exact mount-free disposable containers. No
task is retried, scored, or admitted by this controller.
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
from tools.magento_cron_runtime_contract_v1 import validate_prepared, sha
from tools.start_magento_original_clone_v1 import docker
from tools.sweep_magento_original_gui_controls_v1 import (
    APP, SEARCH, append_event, assert_absent, write_new,
)


SWEEP = ROOT / 'work/magento-original/train-cron-never-autostart-gui-v1'
PLAN = ROOT / 'work/magento-original/train-policy-development-four.private.json'
PUBLIC = ROOT / 'docs/evidence/magento-cron-train-gui-interruption-2026-09-28.json'
NEGATIVE = SWEEP / 'case-000/negative'
AUDIT = NEGATIVE / 'train-interruption-audit.private.json'
LOCK = ROOT / 'work/magento-original/exclusive-worker.lock'


def _bound_file(path: Path, expected: str) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    require(sha(raw) == expected, 'stopped training evidence bytes changed')
    return json.loads(raw), raw


def validate_stopped_events(events: list[dict]) -> None:
    require(events and events[0].get('event') == 'sweep_started' and
            events[0].get('split') == 'train_policy_development' and
            events[0].get('start_index') == 0 and events[0].get('limit') == 1 and
            events[0].get('recovery_of_private_journal_sha256') is None and
            events[0].get('model_calls') == 0 and
            events[0].get('official_final_admitted') is False and
            events[-1].get('event') == 'sweep_stopped' and
            events[-1].get('passed') == 0 and
            events[-1].get('official_final_admitted') == 0 and
            len([row for row in events if row.get('event') == 'step_finished'
                 and row.get('step') == 'negative-neutral' and
                 row.get('index') == 0 and row.get('exit_code') == 1]) == 1 and
            [(row.get('index'), row.get('pair')) for row in events
             if row.get('event') == 'pair_cleanup_verified'] == [(0, 'positive')] and
            not any(row.get('event') == 'step_intent' and
                    row.get('step') in ('negative-finalize', 'negative-runtime',
                                        'fresh-reset', 'negative-gui')
                    for row in events),
            'only the original incomplete train negative-neutral control can be reconciled')


def _inspect_exact(name: str, expected_id: str, expected_image: str) -> dict:
    item = json.loads(docker('inspect', name))[0]
    require(sha(item['Id'].encode()) == expected_id and
            item['Image'] == expected_image and
            item['State']['Running'] is True and not item['Mounts'],
            'live disposable pair identity, image or mount state changed')
    return {'container_id_sha256': expected_id,
            'image_sha256': expected_image}


def read_only_audit() -> dict:
    public = json.loads(PUBLIC.read_bytes())
    require(public['schema'] == 'envloop-magento-cron-train-gui-interruption-public-v1' and
            public['status'] == 'train_negative_neutral_stopped_before_gui_edit' and
            public['model_calls'] == public['official_final_admitted'] == 0 and
            public['task_seeded'] is True and
            public['negative_gui_attempted'] is False and
            public['saved_positive_score'] == 1.0 and
            public['fresh_clone_retry_cap'] == 1,
            'train-only public failure rule changed')
    journal_raw = (SWEEP / 'events.private.jsonl').read_bytes()
    require(sha(journal_raw) == public['stopped_journal_sha256'],
            'original stopped train journal changed')
    events = [json.loads(line) for line in journal_raw.splitlines()]
    validate_stopped_events(events)
    require(events[0]['plan_sha256'] == public['train_plan_sha256'] ==
            sha(PLAN.read_bytes()),
            'train plan binding changed')
    seed, _ = _bound_file(NEGATIVE / 'seed.private.json',
                          public['negative_seed_sha256'])
    prepared, _ = _bound_file(NEGATIVE / 'prepare.private.json',
                              public['negative_prepare_sha256'])
    before, _ = _bound_file(NEGATIVE / 'neutral/private-before.json',
                            public['negative_before_sha256'])
    process, _ = _bound_file(NEGATIVE / 'negative-neutral-process.private.json',
                             public['failed_process_sha256'])
    stderr_raw = (NEGATIVE / 'negative-neutral-stderr.private.bin').read_bytes()
    require(sha(stderr_raw) == process['stderr_sha256'] ==
            public['failed_stderr_sha256'] and
            b'Locator.wait_for: Timeout 120000ms exceeded' in stderr_raw and
            b'h1.page-title' in stderr_raw and
            process['exit_code'] == 1 and
            not (NEGATIVE / 'neutral/result.json').exists() and
            not (NEGATIVE / 'neutral/private-after.json').exists() and
            not (NEGATIVE / 'gui-wrong-variant/result.json').exists(),
            'retained failure was not this native CMS title timeout')
    plan = json.loads(PLAN.read_bytes())
    case = load_case(PLAN, public['train_plan_sha256'],
                     plan['cases']['train_policy_development'][0]['task_id'])
    positive, _ = _bound_file(
        SWEEP / 'case-000/positive/gui-positive/result.json',
        public['saved_positive_result_sha256'])
    require(seed['task_id'] == positive['task_id'] == before['task_id'] ==
            case['task_id'] and
            seed['page_id'] == before['page_id'] and
            positive['score']['score'] == 1.0 and
            positive['score']['independent_saved_state'] is True,
            'saved positive or seeded negative task binding changed')
    validate_prepared(prepared,
                      config_sha256=public['cron_config_sha256'])
    app = _inspect_exact(APP,
                         prepared['application_clone']['container_id_sha256'],
                         prepared['application_clone']['image_sha256'])
    search = _inspect_exact(SEARCH,
                            prepared['search_sidecar_id_sha256'],
                            prepared['search_sidecar_image_sha256'])
    cron_status = subprocess.run(
        ['docker', '--context', 'colima-cua-scale', 'exec', APP,
         'supervisorctl', 'status', 'cron'], capture_output=True, text=True,
        timeout=15, check=False)
    cron_config = docker('exec', APP, 'cat', '/etc/supervisor.d/cron.ini', timeout=15)
    require('cron' in cron_status.stdout and 'STOPPED' in cron_status.stdout and
            'autostart=false' in cron_config and
            'autostart=true' not in cron_config and
            sha(cron_config.encode()) == public['cron_config_sha256'],
            'cron-free runtime no longer matches stopped pair')
    current = read_snapshot(case, APP, 7794, 7795,
                            seed['page_id'], search_host=SEARCH)
    check_baseline(case, current)
    require(current['database']['prices'] == before['database']['prices'] and
            current['database']['quote'] == before['database']['quote'] and
            current['database']['hashes']['business'] ==
            before['database']['hashes']['business'] and
            current['database']['hashes']['other_catalog'] ==
            before['database']['hashes']['other_catalog'] and
            current['search']['full_sha256'] == before['search']['full_sha256'] and
            current['search']['other_documents_sha256'] ==
            before['search']['other_documents_sha256'] and
            current['search']['document_count'] == 181,
            'stopped negative GUI attempt changed material state')
    return {'schema': 'envloop-magento-cron-train-gui-audit-private-v1',
            'public_failure_receipt_sha256': sha(PUBLIC.read_bytes()),
            'original_stopped_journal_sha256': sha(journal_raw),
            'plan_sha256': public['train_plan_sha256'],
            'app': app, 'search': search,
            'cron_config_sha256': sha(cron_config.encode()),
            'material_before_sha256': public['negative_before_sha256'],
            'material_current_sha256': sha((json.dumps(
                current, sort_keys=True, separators=(',', ':')) + '\n').encode()),
            'material_state_unchanged': True,
            'saved_positive_score': 1.0,
            'negative_gui_attempted': False,
            'model_calls': 0, 'official_final_admitted': 0}


def cleanup(saved: dict, saved_raw: bytes) -> dict:
    require(read_only_audit() == saved, 'live pair changed after saved audit')
    audit_sha = sha(saved_raw)
    journal = SWEEP / 'events.private.jsonl'
    append_event(journal, {'event': 'operator_cron_train_gui_cleanup_intent',
                           'index': 0, 'time': time.time(),
                           'audit_sha256': audit_sha,
                           'official_final_admitted': 0})
    steps = []
    for name, expected in ((APP, saved['app']['container_id_sha256']),
                           (SEARCH, saved['search']['container_id_sha256'])):
        for action in ('stop', 'rm'):
            item = json.loads(docker('inspect', name))[0]
            require(sha(item['Id'].encode()) == expected and not item['Mounts'],
                    'exact disposable pair changed during cleanup')
            result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                     action, name], capture_output=True, timeout=70)
            steps.append({'action': action, 'container_id_sha256': expected,
                          'exit_code': result.returncode,
                          'stdout_sha256': sha(result.stdout),
                          'stderr_sha256': sha(result.stderr)})
            require(result.returncode == 0, 'exact train pair cleanup failed')
    assert_absent()
    receipt = {'schema': 'envloop-magento-cron-train-gui-cleanup-private-v1',
               'status': 'stopped_train_pair_retired_for_one_full_fresh_retry',
               'audit_sha256': audit_sha,
               'original_stopped_journal_sha256': saved['original_stopped_journal_sha256'],
               'plan_sha256': saved['plan_sha256'],
               'steps': steps, 'both_containers_cleaned': True,
               'material_state_unchanged': True,
               'saved_positive_score': 1.0,
               'negative_gui_attempted': False,
               'model_calls': 0, 'official_final_admitted': 0}
    receipt_sha = write_new(NEGATIVE / 'train-interruption-cleanup.private.json',
                            receipt)
    append_event(journal, {'event': 'operator_reconciled_cron_train_gui_interruption',
                           'index': 0, 'time': time.time(),
                           'audit_sha256': audit_sha,
                           'cleanup_receipt_sha256': receipt_sha,
                           'task_seeded': True,
                           'both_containers_cleaned': True,
                           'negative_gui_attempted': False,
                           'model_calls': 0, 'official_final_admitted': 0})
    return {'status': receipt['status'],
            'cleanup_receipt_sha256': receipt_sha,
            'official_final_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('audit', 'cleanup'), required=True)
    args = parser.parse_args()
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == 'audit':
            record = read_only_audit()
            digest = write_new(AUDIT, record)
            print(json.dumps({'status': 'read_only_train_pair_audited',
                              'audit_sha256': digest,
                              'official_final_admitted': 0}, sort_keys=True))
        else:
            saved_raw = AUDIT.read_bytes()
            print(json.dumps(cleanup(json.loads(saved_raw), saved_raw), sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
