"""Audit and retire only the failed unseeded Magento cron-startup probe pair."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import check_clone
from magento_catalog_factory.verify import check_native_search_sidecar
from tools.start_magento_native_sidecar_clone_v1 import (
    APP, HTTP_PORT, CONTROL_PORT, NATIVE_SEARCH_HOST,
    NATIVE_SEARCH_IMAGE, READ_CONFIG_PHP, docker,
)
from tools.sweep_magento_original_gui_controls_v1 import assert_absent, write_new

PROBE = ROOT / 'work/magento-original/cron-frozen-train-probe-20260927-v1'
AUDIT = PROBE / 'failed-pair-audit.private.json'
LOCK = ROOT / 'work/magento-original/exclusive-worker.lock'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def audit() -> dict:
    failure_raw = (PROBE / 'startup-failure.private.json').read_bytes()
    failure = json.loads(failure_raw)
    require(failure['schema'] == 'envloop-magento-cron-frozen-train-start-failure-v1'
            and failure['model_calls'] == 0 and
            failure['official_final_admitted'] == 0,
            'not the first failed training startup probe')
    app = check_clone(APP, HTTP_PORT, CONTROL_PORT)
    check_native_search_sidecar(APP)
    sidecar = json.loads(docker('inspect', NATIVE_SEARCH_HOST))[0]
    require(sidecar['Image'] == NATIVE_SEARCH_IMAGE and
            sidecar['State']['Running'] and not sidecar['Mounts'],
            'search image or mounts changed')
    config = json.loads(docker('exec', APP, 'php', '-r', READ_CONFIG_PHP,
                               timeout=30))
    require(config['quote_pages'] == 0, 'training probe unexpectedly seeded task')
    return {'schema': 'envloop-magento-failed-cron-probe-audit-private-v1',
            'failure_sha256': sha(failure_raw),
            'app_container_id_sha256': app['container_id_sha256'],
            'search_container_id_sha256': sha(sidecar['Id'].encode()),
            'app_image_sha256': app['image_sha256'],
            'search_image_sha256': sidecar['Image'],
            'loopback_ports': app['loopback_ports'],
            'app_mount_count': 0, 'search_mount_count': 0,
            'quote_pages': 0, 'model_calls': 0,
            'official_final_admitted': 0}


def cleanup(saved: dict, raw: bytes) -> dict:
    require(audit() == saved, 'failed training pair changed after audit')
    steps = []
    for name, expected in ((APP, saved['app_container_id_sha256']),
                           (NATIVE_SEARCH_HOST, saved['search_container_id_sha256'])):
        for action in ('stop', 'rm'):
            info = json.loads(docker('inspect', name))[0]
            require(sha(info['Id'].encode()) == expected and not info['Mounts'],
                    'exact training container changed')
            result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                     action, name], capture_output=True, timeout=70)
            steps.append({'container_id_sha256': expected,
                          'action': action, 'exit_code': result.returncode,
                          'stdout_sha256': sha(result.stdout),
                          'stderr_sha256': sha(result.stderr)})
            require(result.returncode == 0, 'training pair cleanup failed')
    assert_absent()
    receipt = {'schema': 'envloop-magento-failed-cron-probe-cleanup-private-v1',
               'audit_sha256': sha(raw), 'steps': steps,
               'both_containers_cleaned': True, 'task_seeded': False,
               'model_calls': 0, 'official_final_admitted': 0}
    receipt_sha = write_new(PROBE / 'failed-pair-cleanup.private.json', receipt)
    return {'status': 'failed_training_pair_retired',
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
            with os.fdopen(out_fd, 'wb') as f:
                f.write(raw)
            print(json.dumps({'status': 'failed_train_pair_read_only_audited',
                              'audit_sha256': sha(raw), 'official_final_admitted': 0}))
        else:
            raw = AUDIT.read_bytes()
            print(json.dumps(cleanup(json.loads(raw), raw), sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
