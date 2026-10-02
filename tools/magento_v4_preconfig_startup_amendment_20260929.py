"""Source-bound recovery for one v4 Magento HTTP startup interruption.

The original v4 source freeze stays immutable. ``inspect`` is entirely
read-only. ``prepare`` and ``audit`` only write new private evidence; ``cleanup``
is an explicit operator action that retires the two exact disposable containers
after a second live SQL/search/cron readback. No task or model is run here.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from magento_catalog_factory.plan import require
from magento_catalog_factory.seed import IMAGE, check_clone
from magento_catalog_factory.verify import (
    NATIVE_SEARCH_HOST, NATIVE_SEARCH_IMAGE, NATIVE_SEARCH_NETWORK,
    check_native_search_sidecar,
)
from tools import magento_clean_100_v4 as v4
from tools import sweep_magento_original_gui_controls_v3 as sweep
from tools.reconcile_magento_unseeded_search_drift_v1 import SQL_READ
from tools.start_magento_native_sidecar_clone_v1 import READ_CONFIG_PHP


DATE = '2026-09-29'
CLASSIFICATION = 'preconfig_http_startup_timeout_no_task_seed'
ORIGINAL_JOURNAL_SHA = 'bcd10f1d8bf40c38e53eaa417c47fb2c95205740fd585f4d03ae7ca791332669'
ORIGINAL_JOURNAL_LENGTH = 3384
PROCESS_SHA = 'e6a3a7c3266fc23416f2d345883807611c54a7f2d04154fb17602e90e56e026b'
STDERR_SHA = '320d6f20b9e0101825ea24187166a3edd2061abb6a3e6a2e2ef72b7515297f73'
REFERENCE_BASELINE_SHA = 'b153331d179679b00e8949abb0be4cdd160aa6703a20464434a1b06fd419182d'
REFERENCE_STARTUP_SHA = 'cb59cdfd92994ecc2be8c0eb2654f140a225c724eb9e9713386fa72a9ab5d7b9'
PLAN_SHA = '1df41f027b5f284c7ff7ed162f42f075259960242a295e0a430bff1c8b479ae1'
FREEZE_SHA = '870e1cd54e8cb6ea81a088f731e0b5d8a2fe2ab40d41dd2ae465bf8878b6a8d1'
INCIDENT_REL = Path('docs/evidence/magento-v4-preconfig-startup-stop-2026-09-29.json')
RUN_REL = Path('work/magento-original/clean-v4-100-20260929')
SOURCE_REL = Path('work/webarena-source')
BASELINE_REL = Path('work/magento-original/sweep-final-candidates030-099-v1/case-030/positive/neutral/private-before.json')
STARTUP_REL = Path('work/magento-original/cron-never-autostart-train-probe-20260927-v2/startup.private.json')
ATTEMPT_REL = Path('attempts/case-000-attempt-0')
CASE_REL = ATTEMPT_REL / 'case-000/positive'
STOP_EVENTS = ('run_started', 'dispatch_started', 'case_attempt_started',
               'step_intent', 'step_finished', 'attempt_stopped')
STABLE_SQL = ('catalog_product_entity', 'catalog_product_entity_decimal',
              'catalog_product_entity_int', 'catalog_product_entity_varchar',
              'catalog_product_entity_text', 'catalog_product_entity_datetime',
              'catalog_product_index_price', 'catalog_product_index_price_replica',
              'cataloginventory_stock_item', 'sales_order', 'sales_order_item',
              'customer_entity', 'customer_address_entity', 'quote')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, expected_sha: str | None = None) -> dict:
    raw = path.read_bytes()
    require(expected_sha is None or sha(raw) == expected_sha,
            f'{path.name} changed from the incident source binding')
    return json.loads(raw)


def _docker(*args: str, timeout: int = 120,
            allowed: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(['docker', '--context', 'colima-cua-scale', *args],
                            capture_output=True, timeout=timeout)
    require(result.returncode in allowed, 'read-only Docker query failed')
    return result


def _paths(root: Path) -> dict[str, Path]:
    root = root.resolve()
    run = root / RUN_REL
    attempt = run / ATTEMPT_REL
    return {'root': root, 'run': run, 'attempt': attempt,
            'journal': run / 'journal.private.jsonl',
            'process': run / CASE_REL / 'positive-prepare-process.private.json',
            'stderr': run / CASE_REL / 'positive-prepare-stderr.private.bin',
            'source_freeze': run / 'preconfig-amendment-freeze.private.json',
            'audit': attempt / 'reconciliation-audit.private.json',
            'intent': attempt / 'reconciliation-intent.private.json',
            'receipt': attempt / 'reconciliation.private.json',
            'incident': root / INCIDENT_REL}


def _frozen_context(paths: dict[str, Path]) -> tuple[dict, dict, list[dict]]:
    root = paths['root']
    plan = root / 'work/magento-original/candidate-plan-v2.private.json'
    source = root / SOURCE_REL
    old = root / 'work/magento-original/cron-freeze-20260928.private.json'
    freeze = root / 'work/magento-original/clean-v4-freeze-20260929.private.json'
    require(sha(plan.read_bytes()) == PLAN_SHA and sha(freeze.read_bytes()) == FREEZE_SHA,
            'original task plan or v4 source freeze changed')
    frozen, parent, digest = v4.validate_freeze(
        freeze, old, plan, PLAN_SHA, source, root=root)
    require(digest == FREEZE_SHA and frozen['ordered_case_count'] == 100 and
            frozen['model_calls'] == frozen['official_final_admitted'] == 0,
            'prospective v4 study binding changed')
    cases = json.loads(plan.read_bytes())['cases']['official_candidate']
    require(len(cases) == 100 and
            v4.case_identity_digest(cases) == frozen['ordered_task_identity_sha256'],
            'ordered 100-case identity changed')
    return frozen, parent, cases


def classify_saved_failure(paths: dict[str, Path]) -> dict:
    """No live container query and no write; this is the immutable stop gate."""
    frozen, parent, cases = _frozen_context(paths)
    raw = paths['journal'].read_bytes()
    require(len(raw) == ORIGINAL_JOURNAL_LENGTH and
            sha(raw) == ORIGINAL_JOURNAL_SHA,
            'original stopped v4 journal changed or cleanup already started')
    events = v4.read_journal(paths['journal'])
    v4.validate_run_header(events, FREEZE_SHA, frozen)
    v4.validate_case_sequence(events, cases)
    v4.validate_chunk_boundaries(events, cases, frozen, FREEZE_SHA)
    v4.validate_attempt_inventory(paths['run'], events)
    require(tuple(row.get('event') for row in events) == STOP_EVENTS and
            len([row for row in events if row.get('event') == 'case_completed']) == 0 and
            events[1].get('max_cases') == 2 and
            events[2].get('index') == events[3].get('index') ==
            events[4].get('index') == events[5].get('index') == 0 and
            all(row.get('attempt') == 0 for row in events[2:]) and
            events[3].get('step') == events[4].get('step') == 'positive-prepare' and
            events[4].get('exit_code') == 1 and
            events[5].get('error_type') == 'ValueError' and
            all(row.get('model_calls') == row.get('official_final_admitted') == 0
                for row in (events[0], events[1], events[2], events[5])),
            'interruption is not the exact first pre-config prepare failure')
    process = _read_json(paths['process'], PROCESS_SHA)
    stderr = paths['stderr'].read_bytes()
    require(sha(stderr) == STDERR_SHA and
            process.get('stderr_sha256') == events[4].get('stderr_sha256') == STDERR_SHA and
            process.get('exit_code') == 1 and
            process.get('stdout_bytes') == 0 and
            b'TimeoutError: Magento HTTP did not become ready' in stderr and
            not (paths['run'] / CASE_REL / 'prepare.private.json').exists() and
            not (paths['run'] / CASE_REL / 'seed.private.json').exists() and
            not (paths['run'] / CASE_REL / 'gui-positive').exists(),
            'failed prepare bytes or no-seed/no-GUI boundary changed')
    return {'frozen': frozen, 'parent': parent, 'cases': cases,
            'events': events, 'start_time': events[3]['time'],
            'stop_time': events[5]['time']}


def _reference(paths: dict[str, Path]) -> tuple[dict, dict]:
    baseline = _read_json(paths['root'] / BASELINE_REL, REFERENCE_BASELINE_SHA)
    startup = _read_json(paths['root'] / STARTUP_REL, REFERENCE_STARTUP_SHA)
    require(baseline['search']['full_sha256'] == sweep.SEARCH_SHA and
            startup['train_probe_price_stages']['after_cron_policy_and_http_ready']
            ['price_rows'] == 8156,
            'historical original-software source reference changed')
    return baseline, startup


def _live_once(paths: dict[str, Path], source: dict) -> dict:
    app = v4._docker_inspect(sweep.APP)
    search = v4._docker_inspect(sweep.SEARCH)
    require(app is not None and search is not None,
            'both original disposable containers must still be present')
    check_clone(sweep.APP, 7794, 7795)
    check_native_search_sidecar(sweep.APP)
    identities = []
    for row, name, image in ((app, sweep.APP, IMAGE),
                             (search, sweep.SEARCH, NATIVE_SEARCH_IMAGE)):
        created = datetime.fromisoformat(row['Created'].replace('Z', '+00:00')).timestamp()
        require(row['Name'] == '/' + name and row['Image'] == image and
                row['State']['Running'] is True and row['Mounts'] == [] and
                NATIVE_SEARCH_NETWORK in row['NetworkSettings']['Networks'] and
                source['start_time'] - 2 <= created <= source['stop_time'] + 2,
                'container identity/creation window/image/network changed')
        identities.append({'name': name, 'container_id_sha256': sha(row['Id'].encode()),
                           'image_sha256': image, 'mount_count': 0,
                           'created': row['Created']})
    cron_status = _docker('exec', sweep.APP, 'supervisorctl', 'status', 'cron',
                          timeout=15, allowed=(0, 3)).stdout.decode()
    es_status = _docker('exec', sweep.APP, 'supervisorctl', 'status', 'elasticsearch',
                        timeout=15, allowed=(0, 3)).stdout.decode()
    cron_config = _docker('exec', sweep.APP, 'cat', '/etc/supervisor.d/cron.ini',
                          timeout=15).stdout.decode().strip().encode()
    expected_cron = source['parent']['runtime']['cron_config_sha256']
    require('cron' in cron_status and 'STOPPED' in cron_status and
            'elasticsearch' in es_status and 'STOPPED' in es_status and
            b'autostart=false' in cron_config and
            sha(cron_config) == expected_cron,
            'frozen cron and embedded-search startup policy changed')
    http = _docker('exec', sweep.APP, 'curl', '-sS', '-o', '/dev/null',
                   '-w', '%{http_code}', '--max-time', '8',
                   'http://127.0.0.1/admin', timeout=12).stdout.decode().strip()
    require(http in ('200', '301', '302'),
            'Magento app is not read-only HTTP-ready after the startup timeout')
    health = json.loads(_docker('exec', sweep.SEARCH, 'curl', '-fsS', '--max-time',
                                '8', 'http://127.0.0.1:9200/_cluster/health',
                                timeout=12).stdout)
    require(health.get('status') in ('yellow', 'green') and
            health.get('number_of_nodes') == 1 and
            health.get('number_of_pending_tasks') == 0 and
            health.get('timed_out') is False,
            'native sidecar health changed')
    config = json.loads(_docker('exec', sweep.APP, 'php', '-r', READ_CONFIG_PHP,
                                timeout=30).stdout)
    require(config.get('quote_pages') == 0 and
            config.get('rows') == [{'path': 'web/unsecure/base_url',
                                    'value': 'http://localhost:7780/'}],
            'pre-config startup now has configured settings or a seeded quote')
    sql = json.loads(_docker('exec', sweep.APP, 'php', '-r', SQL_READ,
                             timeout=120).stdout)
    baseline, startup = _reference(paths)
    reference_hashes = baseline['database']['hashes']['full']
    require(set(sql['hashes']) == set(STABLE_SQL) and
            all(sql['hashes'][name] == reference_hashes[name]
                for name in STABLE_SQL) and
            sql.get('price_rows') == 8156 and
            sql.get('price_key_sets_equal') is True and
            sql.get('price_changed_rows') == 0 and
            sql.get('price_changed_fields') == [] and
            sql['hashes']['catalog_product_index_price'] ==
            sql['hashes']['catalog_product_index_price_replica'] ==
            startup['train_probe_price_stages']['after_cron_policy_and_http_ready']
            ['live_price_sha256'],
            'unseeded original SQL source or derived price index drifted')
    indexes = json.loads(_docker('exec', sweep.SEARCH, 'curl', '-fsS', '--max-time',
                                 '8', 'http://127.0.0.1:9200/_cat/indices?format=json',
                                 timeout=12).stdout)
    require(indexes == [], 'native sidecar already holds an index')
    return {'state': 'live_unseeded_preconfig_http_timeout',
            'containers': identities,
            'config_paths': ['web/unsecure/base_url'],
            'config_value_sha256': sha(b'http://localhost:7780/'),
            'quote_pages': 0, 'sql_table_count': len(STABLE_SQL),
            'sql_hashes': sql['hashes'],
            'price_rows': 8156, 'price_changed_rows': 0,
            'price_key_sets_equal': True,
            'native_sidecar_index_count': 0,
            'cron_config_sha256': sha(cron_config),
            'cron_stopped': True, 'embedded_search_stopped': True,
            'http_status': http, 'sidecar_health': health['status'],
            'task_seeded': False, 'model_calls': 0,
            'official_final_admitted': 0}


def _stable_witness(record: dict) -> dict:
    result = json.loads(json.dumps(record))
    result.pop('audit_observed_time', None)
    result.pop('diagnostic_hashes', None)
    # A 200/302 response and green/yellow health are both admissible once the
    # exact SQL/search/cron state and container IDs remain unchanged.
    result.pop('http_status', None)
    result.pop('sidecar_health', None)
    return result


def inspect(paths: dict[str, Path]) -> dict:
    source = classify_saved_failure(paths)
    first = _live_once(paths, source)
    time.sleep(2)
    second = _live_once(paths, source)
    require(_stable_witness(first) == _stable_witness(second),
            'two independent read-only material observations differ')
    diagnostics = {}
    for item in first['containers']:
        name = item['name']
        info = v4._docker_inspect(name)
        require(info is not None and
                sha(info['Id'].encode()) == item['container_id_sha256'],
                'container changed during diagnostic readback')
        logs = _docker('logs', name, timeout=30)
        diagnostics[name] = {'inspect_sha256': sha(v4.encode(info)),
                             'stdout_log_sha256': sha(logs.stdout),
                             'stderr_log_sha256': sha(logs.stderr)}
    return {**first, 'diagnostic_hashes': diagnostics,
            'original_journal_sha256': ORIGINAL_JOURNAL_SHA,
            'failed_process_sha256': PROCESS_SHA,
            'failed_stderr_sha256': STDERR_SHA,
            'reference_baseline_sha256': REFERENCE_BASELINE_SHA,
            'reference_startup_sha256': REFERENCE_STARTUP_SHA,
            'audit_observed_time': time.time()}


def _source_freeze(paths: dict[str, Path]) -> tuple[dict, str]:
    incident, incident_sha = _read_json_with_sha(paths['incident'])
    require(incident.get('schema') ==
            'envloop-magento-v4-preconfig-startup-incident-public-v1' and
            incident.get('status') ==
            'read_only_two_pass_preconfig_source_audit_no_cleanup_or_retry' and
            incident.get('classification') == CLASSIFICATION and
            incident.get('original_journal_sha256') == ORIGINAL_JOURNAL_SHA and
            incident.get('failed_process_sha256') == PROCESS_SHA and
            incident.get('failed_stderr_sha256') == STDERR_SHA and
            incident.get('v4_freeze_sha256') == FREEZE_SHA and
            incident.get('v4_frozen_runner_source_sha256') ==
            sha((paths['root'] / 'tools/magento_clean_100_v4.py').read_bytes()) and
            incident.get('amendment_source_sha256') == sha(Path(__file__).read_bytes()) and
            incident.get('amendment_test_source_sha256') ==
            sha((paths['root'] /
                 'tests/test_magento_v4_preconfig_startup_amendment_20260929.py')
                .read_bytes()) and
            incident.get('cleanup_executed') is False and
            incident.get('retry_authorized') is False and
            incident.get('official_final_admitted') == incident.get('model_calls') == 0,
            'public incident source commitment changed')
    value = {'schema': 'envloop-magento-v4-preconfig-amendment-freeze-private-v1',
             'status': 'one_original_case0_attempt0_preconfig_recovery_only',
             'original_journal_sha256': ORIGINAL_JOURNAL_SHA,
             'original_journal_length': ORIGINAL_JOURNAL_LENGTH,
             'failed_process_sha256': PROCESS_SHA,
             'failed_stderr_sha256': STDERR_SHA,
             'reference_baseline_sha256': REFERENCE_BASELINE_SHA,
             'reference_startup_sha256': REFERENCE_STARTUP_SHA,
             'plan_sha256': PLAN_SHA, 'freeze_v4_sha256': FREEZE_SHA,
             'amendment_source_sha256': sha(Path(__file__).read_bytes()),
             'incident_public_sha256': incident_sha,
             'classification': CLASSIFICATION,
             'one_same_id_whole_case_retry_only': True,
             'model_calls': 0, 'official_final_admitted': 0}
    return value, incident_sha


def _read_json_with_sha(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), sha(raw)


def prepare(paths: dict[str, Path]) -> dict:
    classify_saved_failure(paths)
    require(not any(paths[key].exists() for key in ('source_freeze', 'audit',
                                                   'intent', 'receipt')),
            'supplement must be frozen before any supplemental reconciliation')
    value, _ = _source_freeze(paths)
    digest = v4.private_new(paths['source_freeze'], value)
    return {'status': 'preconfig_amendment_source_frozen_no_cleanup',
            'source_freeze_sha256': digest, 'official_final_admitted': 0}


def _validate_source_freeze(paths: dict[str, Path]) -> str:
    expected, _ = _source_freeze(paths)
    observed, digest = _read_json_with_sha(paths['source_freeze'])
    require(observed == expected,
            'one-case preconfig amendment source freeze changed')
    return digest


def audit(paths: dict[str, Path]) -> dict:
    freeze_sha = _validate_source_freeze(paths)
    require(not any(paths[key].exists() for key in ('audit', 'intent', 'receipt')),
            'supplement audit already exists or cleanup was started')
    witness = inspect(paths)
    source = classify_saved_failure(paths)
    case = source['cases'][0]
    value = {'schema': 'envloop-magento-clean-attempt-audit-private-v4',
             'status': 'invalid_infrastructure_attempt_before_gui_mutation',
             'case_index': 0, 'attempt': 0,
             'task_id': case['task_id'],
             'package_sha256': case['package_sha256'],
             'plan_sha256': PLAN_SHA, 'freeze_v4_sha256': FREEZE_SHA,
             'preconfig_amendment_freeze_sha256': freeze_sha,
             'journal_sha256_before_audit': ORIGINAL_JOURNAL_SHA,
             'active_pair': 'positive', 'classification': CLASSIFICATION,
             'material_witness': witness,
             'whole_case_retry_cap_per_id': 1,
             'study_wide_retry_cap': 20,
             'model_calls': 0, 'official_final_admitted': 0}
    digest = v4.private_new(paths['audit'], value)
    return {'status': 'preconfig_original_case0_audited_no_cleanup',
            'audit_sha256': digest, 'official_final_admitted': 0}


def _lock(paths: dict[str, Path]) -> int:
    path = paths['root'] / 'work/magento-original/exclusive-worker.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError('another Magento admission worker is active') from None
    return fd


def cleanup(paths: dict[str, Path]) -> dict:
    """Explicit operator-only exact pair retirement; never called by inspect."""
    fd = _lock(paths)
    try:
        freeze_sha = _validate_source_freeze(paths)
        audited, audit_sha = _read_json_with_sha(paths['audit'])
        require(audited.get('schema') ==
                'envloop-magento-clean-attempt-audit-private-v4' and
                audited.get('case_index') == audited.get('attempt') == 0 and
                audited.get('classification') == CLASSIFICATION and
                audited.get('preconfig_amendment_freeze_sha256') == freeze_sha and
                audited.get('journal_sha256_before_audit') == ORIGINAL_JOURNAL_SHA and
                audited.get('model_calls') == audited.get('official_final_admitted') == 0,
                'saved source-bound preconfig audit changed')
        if not paths['intent'].exists():
            current = inspect(paths)
            require(_stable_witness(current) ==
                    _stable_witness(audited['material_witness']),
                    'live SQL/search/cron/container material changed after audit')
            value = {'schema': 'envloop-magento-clean-cleanup-intent-private-v4',
                     'case_index': 0, 'attempt': 0,
                     'task_id': audited['task_id'],
                     'audit_sha256': audit_sha,
                     'preconfig_amendment_freeze_sha256': freeze_sha,
                     'journal_sha256_before_cleanup': sha(paths['journal'].read_bytes()),
                     'active_pair': 'positive',
                     'material_witness': audited['material_witness'],
                     'model_calls': 0, 'official_final_admitted': 0}
            intent_sha = v4.private_new(paths['intent'], value)
            v4.append_event(paths['journal'], {
                'event': 'reconciliation_cleanup_intent',
                'index': 0, 'attempt': 0, 'intent_sha256': intent_sha,
                'audit_sha256': audit_sha, 'official_final_admitted': 0})
        intent, intent_sha = _read_json_with_sha(paths['intent'])
        events = v4.read_journal(paths['journal'])
        intent_events = [row for row in events if row.get('event') ==
                         'reconciliation_cleanup_intent' and
                         row.get('intent_sha256') == intent_sha]
        if not intent_events:
            require(sha(paths['journal'].read_bytes()) ==
                    intent.get('journal_sha256_before_cleanup'),
                    'private cleanup intent exists without its unchanged journal boundary')
            current = inspect(paths)
            require(_stable_witness(current) ==
                    _stable_witness(audited['material_witness']),
                    'material changed before cleanup intent recovery')
            v4.append_event(paths['journal'], {
                'event': 'reconciliation_cleanup_intent',
                'index': 0, 'attempt': 0, 'intent_sha256': intent_sha,
                'audit_sha256': audit_sha, 'official_final_admitted': 0})
            events = v4.read_journal(paths['journal'])
            intent_events = [row for row in events if row.get('event') ==
                             'reconciliation_cleanup_intent' and
                             row.get('intent_sha256') == intent_sha]
        require(intent.get('schema') ==
                'envloop-magento-clean-cleanup-intent-private-v4' and
                intent.get('audit_sha256') == audit_sha and
                intent.get('preconfig_amendment_freeze_sha256') == freeze_sha and
                intent.get('material_witness') == audited['material_witness'] and
                len(intent_events) == 1,
                'exact private cleanup intent or journal lineage missing')
        if paths['receipt'].exists():
            receipt, receipt_sha = _read_json_with_sha(paths['receipt'])
            require(receipt.get('audit_sha256') == audit_sha and
                    receipt.get('cleanup_intent_sha256') == intent_sha and
                    receipt.get('both_containers_absent') is True,
                    'existing retirement receipt changed')
            sweep.assert_absent()
        else:
            containers = audited['material_witness']['containers']
            require([row['name'] for row in containers] ==
                    [sweep.APP, sweep.SEARCH],
                    'audited disposable pair names changed')
            for item in containers:
                v4._cleanup_step(paths['journal'], 0, item, 'stop')
                v4._cleanup_step(paths['journal'], 0, item, 'rm')
            sweep.assert_absent()
            receipt = {
                'schema': 'envloop-magento-clean-cleanup-private-v4',
                'status': 'exact_pair_retired_for_one_whole_case_retry',
                'case_index': 0, 'attempt': 0,
                'task_id': audited['task_id'],
                'package_sha256': audited['package_sha256'],
                'plan_sha256': PLAN_SHA, 'freeze_v4_sha256': FREEZE_SHA,
                'preconfig_amendment_freeze_sha256': freeze_sha,
                'audit_sha256': audit_sha,
                'cleanup_intent_sha256': intent_sha,
                'active_pair': 'positive',
                'material_witness': audited['material_witness'],
                'both_containers_absent': True,
                'whole_case_retry_cap_per_id': 1,
                'study_wide_retry_cap': 20,
                'model_calls': 0, 'official_final_admitted': 0}
            receipt_sha = v4.private_new(paths['receipt'], receipt)
        events = v4.read_journal(paths['journal'])
        matches = [row for row in events if row.get('event') ==
                   'attempt_reconciled' and row.get('index') == 0]
        if not matches:
            v4.append_event(paths['journal'], {
                'event': 'attempt_reconciled', 'index': 0, 'attempt': 0,
                'classification': CLASSIFICATION,
                'reconciliation_sha256': receipt_sha,
                'audit_sha256': audit_sha,
                'both_containers_absent': True,
                'model_calls': 0, 'official_final_admitted': 0})
        else:
            require(len(matches) == 1 and
                    matches[0].get('reconciliation_sha256') == receipt_sha and
                    matches[0].get('audit_sha256') == audit_sha,
                    'prior reconciliation differs from this exact pair retirement')
        return {'status': 'exact_preconfig_pair_retired_for_one_same_id_retry',
                'reconciliation_sha256': receipt_sha,
                'official_final_admitted': 0}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def verify_retired(paths: dict[str, Path]) -> dict:
    """Read-only independent gate before dispatching the original v4 retry."""
    freeze_sha = _validate_source_freeze(paths)
    frozen, _, cases = _frozen_context(paths)
    audit, audit_sha = _read_json_with_sha(paths['audit'])
    intent, intent_sha = _read_json_with_sha(paths['intent'])
    receipt, receipt_sha = _read_json_with_sha(paths['receipt'])
    raw = paths['journal'].read_bytes()
    require(sha(raw[:ORIGINAL_JOURNAL_LENGTH]) == ORIGINAL_JOURNAL_SHA,
            'original stopped journal prefix changed')
    events = v4.read_journal(paths['journal'])
    v4.validate_run_header(events, FREEZE_SHA, frozen)
    v4.validate_case_sequence(events, cases)
    v4.validate_chunk_boundaries(events, cases, frozen, FREEZE_SHA)
    v4.validate_attempt_inventory(paths['run'], events)
    reconciled = [row for row in events if row.get('event') ==
                  'attempt_reconciled' and row.get('index') == 0]
    require(len(reconciled) == 1 and
            len([row for row in events if row.get('event') ==
                 'case_attempt_started']) == 1 and
            not any(row.get('event') == 'case_completed' for row in events) and
            reconciled[0].get('classification') == CLASSIFICATION and
            reconciled[0].get('reconciliation_sha256') == receipt_sha and
            reconciled[0].get('audit_sha256') == audit_sha and
            audit.get('preconfig_amendment_freeze_sha256') ==
            intent.get('preconfig_amendment_freeze_sha256') ==
            receipt.get('preconfig_amendment_freeze_sha256') == freeze_sha and
            receipt.get('audit_sha256') == intent.get('audit_sha256') == audit_sha and
            receipt.get('cleanup_intent_sha256') == intent_sha and
            receipt.get('material_witness') ==
            intent.get('material_witness') ==
            audit.get('material_witness') and
            receipt.get('both_containers_absent') is True and
            receipt.get('model_calls') ==
            receipt.get('official_final_admitted') == 0,
            'preconfig source, exact cleanup, or one-retry lineage changed')
    for item in audit['material_witness']['containers']:
        for action in ('stop', 'rm'):
            matches = [row for row in events if row.get('event') ==
                       'cleanup_step_intent' and row.get('index') == 0 and
                       row.get('name') == item['name'] and
                       row.get('action') == action and
                       row.get('container_id_sha256') ==
                       item['container_id_sha256']]
            require(len(matches) == 1,
                    'one exact container cleanup intent is missing or duplicated')
    sweep.assert_absent()
    return {'status': 'one_same_id_v4_retry_lineage_verified',
            'case_index': 0, 'reconciliation_sha256': receipt_sha,
            'official_final_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'prepare', 'audit',
                                           'cleanup', 'verify-retired'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--execute-cleanup', action='store_true')
    args = parser.parse_args()
    paths = _paths(args.root)
    if args.action == 'inspect':
        witness = inspect(paths)
        result = {'status': 'read_only_preconfig_pair_verified',
                  'material_witness_sha256': sha(v4.encode(_stable_witness(witness))),
                  'sql_table_count': witness['sql_table_count'],
                  'quote_pages': witness['quote_pages'],
                  'native_sidecar_index_count': witness['native_sidecar_index_count'],
                  'model_calls': 0, 'official_final_admitted': 0}
    elif args.action == 'prepare':
        result = prepare(paths)
    elif args.action == 'audit':
        result = audit(paths)
    elif args.action == 'cleanup':
        require(args.execute_cleanup,
                'cleanup needs explicit --execute-cleanup after operator review')
        result = cleanup(paths)
    else:
        result = verify_retired(paths)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
