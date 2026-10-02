"""Retire only the second unseeded Magento index-drift pair after audit.

This frees disposable container names for a separate training startup probe.
It never retries the failed candidate, repairs an index, or credits a score.
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
from magento_catalog_factory.verify import canonical_sha, check_native_search_sidecar
from tools.start_magento_native_sidecar_clone_v1 import (
    APP, HTTP_PORT, CONTROL_PORT, NATIVE_SEARCH_HOST,
    NATIVE_SEARCH_IMAGE, READ_CONFIG_PHP, docker,
)
from tools.reconcile_magento_unseeded_search_drift_v1 import SQL_READ
from tools.sweep_magento_original_gui_controls_v1 import append_event, assert_absent, write_new

SWEEP = ROOT / 'work/magento-original/sweep-final-candidates032-099-resume1'
PUBLIC = ROOT / 'docs/evidence/magento-original-cellwide-index-drift-stop-2026-09-27.json'
AUDIT = SWEEP / 'case-035/positive/cellwide-halt-audit.private.json'
LOCK = ROOT / 'work/magento-original/exclusive-worker.lock'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def valid_halt(events: list[dict]) -> None:
    require(events and events[-1].get('event') == 'sweep_stopped' and
            events[-1].get('passed') == 3 and
            [e.get('index') for e in events if e.get('event') == 'task_gui_calibrated']
            == [32, 33, 34] and
            any(e.get('event') == 'step_finished' and e.get('index') == 35 and
                e.get('step') == 'positive-prepare' and e.get('exit_code') == 1
                for e in events) and
            not any(e.get('index') == 35 and e.get('step', '').endswith('-seed')
                    for e in events), 'not the exact unseeded second drift halt')


def read_only_audit() -> dict:
    public = json.loads(PUBLIC.read_bytes())
    journal_raw = (SWEEP / 'events.private.jsonl').read_bytes()
    require(sha(journal_raw) == public['failed_journal_sha256'],
            'stopped journal changed')
    valid_halt([json.loads(x) for x in journal_raw.splitlines()])
    app = check_clone(APP, HTTP_PORT, CONTROL_PORT)
    check_native_search_sidecar(APP)
    search = json.loads(docker('inspect', NATIVE_SEARCH_HOST))[0]
    require(search['Image'] == NATIVE_SEARCH_IMAGE and
            search['State']['Running'] and not search['Mounts'],
            'pinned no-mount search pair changed')
    config = json.loads(docker('exec', APP, 'php', '-r', READ_CONFIG_PHP,
                               timeout=30))
    require(config['quote_pages'] == 0, 'task quote present')
    sql = json.loads(docker('exec', APP, 'php', '-r', SQL_READ, timeout=90))
    require(sql['price_rows'] == public['live_price_index_rows'] and
            sql['price_changed_rows'] ==
            public['derived_price_rows_differing_from_replica'] and
            sql['price_changed_fields'] == public['derived_fields_changed'] and
            sql['price_key_sets_equal'] is True,
            'live price-index drift no longer matches stopped evidence')
    response = json.loads(docker('exec', APP, 'curl', '-fsS', '--max-time', '30',
                                 f'http://{NATIVE_SEARCH_HOST}:9200/magento2_product_1/_search?size=1000',
                                 timeout=45))
    hits = response['hits']['hits']
    docs = {row['_id']: row['_source'] for row in hits}
    require(len(docs) == len(hits) == public['search_documents'] and
            canonical_sha(docs) == public['observed_search_sha256'],
            'search index no longer matches stopped evidence')
    return {'schema': 'envloop-magento-cellwide-halt-audit-private-v1',
            'public_receipt_sha256': sha(PUBLIC.read_bytes()),
            'journal_sha256': sha(journal_raw),
            'app_container_id_sha256': app['container_id_sha256'],
            'search_container_id_sha256': sha(search['Id'].encode()),
            'app_image_sha256': app['image_sha256'],
            'search_image_sha256': search['Image'],
            'loopback_ports': app['loopback_ports'], 'mount_count': 0,
            'quote_pages': 0, 'search_sha256': canonical_sha(docs),
            'price_changed_rows': sql['price_changed_rows'],
            'task_seeded': False, 'model_calls': 0,
            'official_final_admitted': 0}


def cleanup(saved: dict, raw: bytes) -> dict:
    require(read_only_audit() == saved, 'live pair changed after audit')
    journal = SWEEP / 'events.private.jsonl'
    append_event(journal, {'event': 'operator_cellwide_halt_cleanup_intent',
                           'index': 35, 'time': time.time(),
                           'audit_sha256': sha(raw), 'task_seeded': False,
                           'official_final_admitted': 0})
    steps = []
    for name, expected in ((APP, saved['app_container_id_sha256']),
                           (NATIVE_SEARCH_HOST, saved['search_container_id_sha256'])):
        for action in ('stop', 'rm'):
            info = json.loads(docker('inspect', name))[0]
            require(sha(info['Id'].encode()) == expected and not info['Mounts'],
                    'exact cleanup identity changed')
            result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                     action, name], capture_output=True, timeout=70)
            steps.append({'container_id_sha256': expected,
                          'action': action, 'exit_code': result.returncode,
                          'stdout_sha256': sha(result.stdout),
                          'stderr_sha256': sha(result.stderr)})
            require(result.returncode == 0, 'exact cleanup failed')
    assert_absent()
    receipt = {'schema': 'envloop-magento-cellwide-halt-cleanup-private-v1',
               'audit_sha256': sha(raw), 'steps': steps,
               'both_containers_cleaned': True, 'task_seeded': False,
               'model_calls': 0, 'official_final_admitted': 0}
    receipt_sha = write_new(SWEEP / 'case-035/positive/cellwide-halt-cleanup.private.json',
                            receipt)
    append_event(journal, {'event': 'operator_cellwide_halt_reconciled',
                           'index': 35, 'time': time.time(),
                           'audit_sha256': sha(raw),
                           'cleanup_receipt_sha256': receipt_sha,
                           'official_final_admitted': 0})
    return {'status': 'pair_retired_for_train_probe',
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
            raw = (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()
            out_fd = os.open(AUDIT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(out_fd, 'wb') as f:
                f.write(raw)
            print(json.dumps({'status': 'cellwide_halt_read_only_audited',
                              'audit_sha256': sha(raw), 'official_final_admitted': 0}))
        else:
            raw = AUDIT.read_bytes()
            print(json.dumps(cleanup(json.loads(raw), raw), sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
