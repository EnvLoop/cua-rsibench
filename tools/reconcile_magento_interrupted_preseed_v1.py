"""Retire the exact disposable Magento pair left by a pre-seed process exit.

This controller is scoped to the first intent in the ordinal-32 continuation.
It never seeds a task, reindexes, calls a model, or credits a GUI control.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import check_clone
from magento_catalog_factory.verify import check_native_search_sidecar, NATIVE_SEARCH_IMAGE
from tools.start_magento_native_sidecar_clone_v1 import (
    APP, HTTP_PORT, CONTROL_PORT, NATIVE_SEARCH_HOST, READ_CONFIG_PHP, docker,
)
from tools.sweep_magento_original_gui_controls_v1 import append_event, write_new, assert_absent


SWEEP = (ROOT / 'work/magento-original/sweep-final-candidates032-099-v1').resolve()
INDEX = 32
AUDIT = SWEEP / 'case-032/positive/interrupted-prepare-audit.private.json'
LOCK = ROOT / 'work/magento-original/exclusive-worker.lock'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_events(events: list[dict]) -> dict:
    require(len(events) == 2 and events[0].get('event') == 'sweep_started' and
            events[0].get('start_index') == INDEX and
            events[0].get('official_final_admitted') is False and
            events[0].get('model_calls') == 0 and
            events[1].get('event') == 'step_intent' and
            events[1].get('index') == INDEX and
            events[1].get('step') == 'positive-prepare',
            'only the exact pre-seed interrupted intent is eligible')
    return events[1]


def inspect_pair() -> dict:
    clone = check_clone(APP, HTTP_PORT, CONTROL_PORT)
    check_native_search_sidecar(APP)
    info = json.loads(docker('inspect', NATIVE_SEARCH_HOST))[0]
    require(info['Image'] == NATIVE_SEARCH_IMAGE and info['State']['Running']
            and not info['Mounts'], 'search sidecar identity or mounts changed')
    config = json.loads(docker('exec', APP, 'php', '-r', READ_CONFIG_PHP,
                               timeout=30))
    require(config['quote_pages'] == 0, 'task quote exists; pre-seed cleanup refused')
    return {'app_container_id_sha256': clone['container_id_sha256'],
            'search_container_id_sha256': sha(info['Id'].encode()),
            'app_image_sha256': clone['image_sha256'],
            'search_image_sha256': info['Image'],
            'app_mount_count': 0, 'search_mount_count': 0,
            'loopback_ports': clone['loopback_ports'],
            'quote_pages': 0,
            'config_rows_sha256': sha(json.dumps(config['rows'], sort_keys=True).encode())}


def audit() -> dict:
    journal = SWEEP / 'events.private.jsonl'
    raw = journal.read_bytes()
    events = [json.loads(line) for line in raw.splitlines()]
    intent = validate_events(events)
    pair = inspect_pair()
    return {'schema': 'envloop-magento-interrupted-preseed-audit-private-v1',
            'index': INDEX, 'original_journal_sha256': sha(raw),
            'intent_command_sha256': intent['command_sha256'],
            'intent_time': intent['time'], 'pair': pair,
            'task_seeded': False, 'model_calls': 0,
            'official_final_admitted': 0}


def cleanup(saved: dict, saved_raw: bytes) -> dict:
    current = audit()
    require(current == saved, 'journal or live container state changed after audit')
    journal = SWEEP / 'events.private.jsonl'
    append_event(journal, {'event': 'operator_interrupted_preseed_cleanup_intent',
                           'index': INDEX, 'time': time.time(),
                           'audit_sha256': sha(saved_raw),
                           'task_seeded': False, 'official_final_admitted': 0})
    steps = []
    for name, expected in ((APP, saved['pair']['app_container_id_sha256']),
                           (NATIVE_SEARCH_HOST, saved['pair']['search_container_id_sha256'])):
        for action in ('stop', 'rm'):
            info = json.loads(docker('inspect', name))[0]
            require(sha(info['Id'].encode()) == expected and not info['Mounts'],
                    'container identity changed during exact cleanup')
            result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                     action, name], capture_output=True, timeout=70)
            steps.append({'container_id_sha256': expected, 'action': action,
                          'exit_code': result.returncode,
                          'stdout_sha256': sha(result.stdout),
                          'stderr_sha256': sha(result.stderr)})
            require(result.returncode == 0, 'exact cleanup failed; inspect manually')
    assert_absent()
    receipt = {'schema': 'envloop-magento-interrupted-preseed-cleanup-private-v1',
               'index': INDEX, 'audit_sha256': sha(saved_raw),
               'steps': steps, 'both_containers_cleaned': True,
               'task_seeded': False, 'model_calls': 0,
               'official_final_admitted': 0}
    receipt_sha = write_new(SWEEP / 'case-032/positive/interrupted-prepare-cleanup.private.json',
                            receipt)
    append_event(journal, {'event': 'operator_interrupted_preseed_reconciled',
                           'index': INDEX, 'time': time.time(),
                           'audit_sha256': sha(saved_raw),
                           'cleanup_receipt_sha256': receipt_sha,
                           'task_seeded': False, 'official_final_admitted': 0})
    return {'status': 'exact_unseeded_pair_reconciled',
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
            result = audit()
            raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
            out_fd = os.open(AUDIT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(out_fd, 'wb') as stream:
                stream.write(raw)
            print(json.dumps({'status': 'read_only_preseed_interruption_audited',
                              'audit_sha256': sha(raw), 'official_final_admitted': 0}))
        else:
            raw = AUDIT.read_bytes()
            print(json.dumps(cleanup(json.loads(raw), raw), sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
