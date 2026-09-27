"""Retire only the successful unseeded cron-never-autostart train probe pair."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess

from magento_catalog_factory.plan import ROOT, require
from tools.start_magento_native_sidecar_clone_v1 import (
    APP, NATIVE_SEARCH_HOST, audit_existing,
    read_price_index_shape, verify_cron_never_autostarted,
)
from tools.sweep_magento_original_gui_controls_v1 import assert_absent, write_new

PROBE = ROOT / 'work/magento-original/cron-never-autostart-train-probe-20260927-v2'
SOURCE = PROBE / 'startup.private.json'
AUDIT = PROBE / 'probe-pair-audit.private.json'
LOCK = ROOT / 'work/magento-original/exclusive-worker.lock'
FROZEN = '54ca1d8ef5cb82ed879338e6740a589a930e50cd8a54f495c234c5f5b0acf6fb'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def audit() -> dict:
    source_raw = SOURCE.read_bytes()
    source = json.loads(source_raw)
    require(source['schema'] == 'envloop-magento-cron-never-autostart-train-probe-v2'
            and source['model_calls'] == 0 and
            source['official_final_tasks_admitted'] == 0 and
            source['train_probe_cron']['policy'] ==
            'cron_autostart_disabled_before_supervisor' and
            all(row['price_changed_rows'] == 0 for row in
                source['train_probe_price_stages'].values()),
            'not the successful unseeded v2 probe')
    current = audit_existing(FROZEN, 'cron_v2_readonly_before_cleanup')
    require(current['application_clone']['container_id_sha256'] ==
            source['application_clone']['container_id_sha256'] and
            current['search_sidecar_id_sha256'] ==
            source['search_sidecar_id_sha256'] and
            current['application_clone']['mount_count'] == 0,
            'probe pair identity or mounts changed')
    cron = verify_cron_never_autostarted()
    price = read_price_index_shape()
    require(cron['config_sha256'] == source['train_probe_cron']['config_sha256']
            and price['price_rows'] == 8156 and
            price['price_changed_rows'] == 0 and
            price['price_key_sets_equal'] is True,
            'cron or price index changed after probe')
    return {'schema': 'envloop-magento-cron-v2-pair-audit-private-v1',
            'source_receipt_sha256': sha(source_raw),
            'app_container_id_sha256': source['application_clone']['container_id_sha256'],
            'search_container_id_sha256': source['search_sidecar_id_sha256'],
            'cron_config_sha256': cron['config_sha256'],
            'search_documents_sha256': current['search_documents_sha256'],
            'price_changed_rows': 0, 'task_seeded': False,
            'model_calls': 0, 'official_final_admitted': 0}


def cleanup(saved: dict, raw: bytes) -> dict:
    require(audit() == saved, 'live probe pair changed after audit')
    steps = []
    for name, expected in ((APP, saved['app_container_id_sha256']),
                           (NATIVE_SEARCH_HOST, saved['search_container_id_sha256'])):
        for action in ('stop', 'rm'):
            result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                     'inspect', name], capture_output=True,
                                    timeout=30, check=True)
            info = json.loads(result.stdout)[0]
            require(sha(info['Id'].encode()) == expected and not info['Mounts'],
                    'exact probe pair changed during cleanup')
            outcome = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                      action, name], capture_output=True, timeout=70)
            steps.append({'container_id_sha256': expected, 'action': action,
                          'exit_code': outcome.returncode,
                          'stdout_sha256': sha(outcome.stdout),
                          'stderr_sha256': sha(outcome.stderr)})
            require(outcome.returncode == 0, 'exact probe cleanup failed')
    assert_absent()
    receipt = {'schema': 'envloop-magento-cron-v2-pair-cleanup-private-v1',
               'audit_sha256': sha(raw), 'steps': steps,
               'both_containers_cleaned': True, 'task_seeded': False,
               'model_calls': 0, 'official_final_admitted': 0}
    receipt_sha = write_new(PROBE / 'probe-pair-cleanup.private.json', receipt)
    return {'status': 'successful_train_probe_pair_retired',
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
            record = audit()
            raw = (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()
            out_fd = os.open(AUDIT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(out_fd, 'wb') as stream:
                stream.write(raw)
            print(json.dumps({'status': 'successful_train_probe_pair_audited',
                              'audit_sha256': sha(raw), 'official_final_admitted': 0}))
        else:
            raw = AUDIT.read_bytes()
            print(json.dumps(cleanup(json.loads(raw), raw), sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
