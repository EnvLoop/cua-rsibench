"""Narrow recovery of the interrupted, unseeded case-26 v4 prepare.

The v4 source stays immutable. This additive pre-result source authorizes only
exact-pair retirement after two source-state readbacks. It does not repair the
live application, seed a task, run a GUI, or replay a child process.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from tools import magento_clean_100_v4 as v4
from tools import magento_v4_preconfig_startup_amendment_20260929 as prior
from tools import sweep_magento_original_gui_controls_v3 as sweep
from tools.start_magento_native_sidecar_clone_v1 import READ_CONFIG_PHP
from tools.reconcile_magento_unseeded_search_drift_v1 import SQL_READ
from magento_catalog_factory.seed import check_clone
from magento_catalog_factory.verify import check_native_search_sidecar


CASE_INDEX = 26
CLASSIFICATION = 'preconfig_operator_interruption_no_task_seed'
ORIGINAL_JOURNAL_SHA = '6494fae429f0eac4f1512242c36265c3c85a8fc443f8073541c6800afc0a6186'
ORIGINAL_JOURNAL_BYTES = 335420
ORIGINAL_JOURNAL_ROWS = 834
PUBLIC_REL = Path('docs/evidence/magento-v4-case26-startup-interruption-freeze-2026-09-30.json')
FREEZE_NAME = 'case26-startup-interruption-freeze-20260930.private.json'
SOURCE_FILES = (
    'tools/magento_v4_case26_startup_interruption_20260930.py',
    'tools/magento_v4_preconfig_startup_amendment_20260929.py',
    'tools/magento_clean_100_v4.py',
    'tools/start_magento_native_sidecar_clone_v1.py',
    'tools/reconcile_magento_unseeded_search_drift_v1.py',
    'tools/audit_magento_v4_completed_prefix.py',
    'tests/test_magento_v4_case26_startup_interruption.py',
)


def paths(root: Path) -> dict:
    root = root.resolve()
    run = root / prior.RUN_REL
    attempt = v4.attempt_dir(run, CASE_INDEX, 0)
    return {'root': root, 'run': run, 'attempt': attempt,
            'journal': run / 'journal.private.jsonl',
            'freeze': run / FREEZE_NAME, 'public': root / PUBLIC_REL,
            'audit': attempt / 'reconciliation-audit.private.json',
            'intent': attempt / 'reconciliation-intent.private.json',
            'receipt': attempt / 'reconciliation.private.json'}


def _private(path: Path) -> tuple[dict, str]:
    v4.require(path.is_file() and not path.is_symlink() and
               path.stat().st_mode & 0o077 == 0, 'case26 private evidence unsafe')
    return v4.read_json(path)


def _sources(p: dict) -> dict:
    return {name: prior.sha((p['root'] / name).read_bytes()) for name in SOURCE_FILES}


def _context(p: dict, *, allow_appends: bool = False) -> dict:
    frozen, parent, cases = prior._frozen_context(prior._paths(p['root']))
    raw = p['journal'].read_bytes()
    lines = raw.splitlines(keepends=True)
    prefix = b''.join(lines[:ORIGINAL_JOURNAL_ROWS])
    v4.require(len(prefix) == ORIGINAL_JOURNAL_BYTES and
               prior.sha(prefix) == ORIGINAL_JOURNAL_SHA and
               (allow_appends or raw == prefix), 'case26 interruption boundary changed')
    rows = [json.loads(line) for line in lines[:ORIGINAL_JOURNAL_ROWS]]
    v4.validate_run_header(rows, prior.FREEZE_SHA, frozen)
    v4.validate_case_sequence(rows, cases)
    v4.validate_chunk_boundaries(rows, cases, frozen, prior.FREEZE_SHA)
    v4.require(len([r for r in rows if r.get('event') == 'case_completed']) == CASE_INDEX,
               'case26 completed prefix changed')
    scoped = [r for r in rows if r.get('index') == CASE_INDEX]
    v4.require([r.get('event') for r in scoped] ==
               ['case_attempt_started', 'step_intent'] and
               all(r.get('attempt') == 0 for r in scoped) and
               scoped[-1].get('step') == 'positive-prepare' and
               scoped[0].get('task_id') == cases[CASE_INDEX]['task_id'] and
               scoped[0].get('package_sha256') == cases[CASE_INDEX]['package_sha256'] and
               scoped[0].get('model_calls') == scoped[0].get('official_final_admitted') == 0,
               'case26 crossed seed, GUI, result, or retry boundary')
    pair = p['attempt'] / f'case-{CASE_INDEX:03d}'
    v4.require(not pair.is_symlink() and
               (not pair.exists() or all(q.is_dir() and not q.is_symlink()
                                        for q in pair.rglob('*'))),
               'case26 task preparation material already exists')
    v4.validate_completed_prefix(p['run'], rows, cases, parent['runtime_fingerprint_sha256'])
    return {'frozen': frozen, 'parent': parent, 'cases': cases,
            'rows': rows, 'start_time': scoped[-1]['time']}


def _workers_absent() -> dict:
    result = subprocess.run(['ps', '-axo', 'pid=,comm=,args='],
                            capture_output=True, text=True, check=True, timeout=15)
    matches = []
    needles = ('tools.magento_clean_100_v4 run',
               '/start_magento_native_sidecar_clone_v1.py',
               '/qualify_magento_original_catalog_v3.py',
               '/sweep_magento_original_gui_controls_v3.py')
    for line in result.stdout.splitlines():
        columns = line.strip().split(None, 2)
        if len(columns) != 3: continue
        pid, executable, command = columns
        if int(pid) == os.getpid(): continue
        if 'python' in Path(executable).name.lower() and any(n in command for n in needles):
            matches.append(int(pid))
    v4.require(not matches, 'case26 original worker is still live')
    return {'matching_original_workers': 0,
            'process_snapshot_sha256': prior.sha(result.stdout.encode())}


def _live_once(p: dict, source: dict) -> dict:
    workers = _workers_absent()
    app, search = (v4._docker_inspect(sweep.APP), v4._docker_inspect(sweep.SEARCH))
    v4.require(app is not None and search is not None, 'case26 complete pair missing')
    check_clone(sweep.APP, 7794, 7795)
    check_native_search_sidecar(sweep.APP)
    containers = []
    for row, name, image in ((app, sweep.APP, v4.IMAGE),
                             (search, sweep.SEARCH, v4.NATIVE_SEARCH_IMAGE)):
        created = datetime.fromisoformat(row['Created'].replace('Z', '+00:00')).timestamp()
        v4.require(row['Name'] == '/' + name and row['Image'] == image and
                   row['State']['Running'] is True and row['Mounts'] == [] and
                   source['start_time'] - 2 <= created <= time.time() + 2,
                   'case26 pair identity, image, mount or creation changed')
        containers.append({'name': name,
                           'container_id_sha256': prior.sha(row['Id'].encode()),
                           'image_sha256': image, 'mount_count': 0,
                           'created': row['Created']})
    cron = prior._docker('exec', sweep.APP, 'supervisorctl', 'status', 'cron',
                         timeout=15, allowed=(0, 3)).stdout
    embedded = prior._docker('exec', sweep.APP, 'supervisorctl', 'status',
                             'elasticsearch', timeout=15, allowed=(0, 3)).stdout
    config_raw = prior._docker('exec', sweep.APP, 'cat',
                               '/etc/supervisor.d/cron.ini', timeout=15).stdout.strip()
    v4.require(b'STOPPED' in cron and b'STOPPED' in embedded and
               b'autostart=false' in config_raw and prior.sha(config_raw) ==
               source['parent']['runtime']['cron_config_sha256'],
               'case26 cron or embedded search changed')
    config = json.loads(prior._docker('exec', sweep.APP, 'php', '-r',
                                      READ_CONFIG_PHP, timeout=60).stdout)
    v4.require(config == {'rows': [{'path': 'web/unsecure/base_url',
                                    'value': 'http://localhost:7780/'}],
                         'quote_pages': 0}, 'case26 source configuration or quote changed')
    sql = json.loads(prior._docker('exec', sweep.APP, 'php', '-r',
                                   SQL_READ, timeout=120).stdout)
    baseline, startup = prior._reference(prior._paths(p['root']))
    hashes = baseline['database']['hashes']['full']
    v4.require(set(sql['hashes']) == set(prior.STABLE_SQL) and
               all(sql['hashes'][key] == hashes[key] for key in prior.STABLE_SQL) and
               sql['price_rows'] == 8156 and sql['price_key_sets_equal'] is True and
               sql['price_changed_rows'] == 0 and sql['price_changed_fields'] == [] and
               sql['hashes']['catalog_product_index_price'] ==
               sql['hashes']['catalog_product_index_price_replica'] ==
               startup['train_probe_price_stages']['after_cron_policy_and_http_ready']['live_price_sha256'],
               'case26 SQL source or price index changed')
    indexes = json.loads(prior._docker('exec', sweep.SEARCH, 'curl', '-fsS',
                                       '--max-time', '8',
                                       'http://127.0.0.1:9200/_cat/indices?format=json', timeout=12).stdout)
    v4.require(indexes == [], 'case26 sidecar already contains a task/search index')
    http = prior._docker('exec', sweep.APP, 'curl', '-sS', '-o', '/dev/null',
                         '-w', '%{http_code}', '--max-time', '8',
                         'http://127.0.0.1/admin', timeout=12, allowed=(0, 28))
    # Readable unchanged SQL is the retirement proof. HTTP readiness is
    # diagnostic at this pre-configuration phase and cannot qualify a task.
    return {'state': 'live_unseeded_preconfig_operator_interruption',
            'containers': containers, 'sql_hashes': sql['hashes'],
            'sql_table_count': len(prior.STABLE_SQL), 'quote_pages': 0,
            'price_rows': 8156, 'price_changed_rows': 0,
            'price_key_sets_equal': True, 'native_sidecar_index_count': 0,
            'config_paths': ['web/unsecure/base_url'],
            'config_value_sha256': prior.sha(b'http://localhost:7780/'),
            'cron_config_sha256': prior.sha(config_raw), 'cron_stopped': True,
            'embedded_search_stopped': True, 'task_seeded': False,
            'material_equal_exact': True, 'workers': workers,
            'http_diagnostic': {'exit_code': http.returncode,
                                'status': http.stdout.decode().strip(),
                                'stderr_sha256': prior.sha(http.stderr)},
            'reference_baseline_sha256': prior.REFERENCE_BASELINE_SHA,
            'reference_startup_sha256': prior.REFERENCE_STARTUP_SHA,
            'model_calls': 0, 'official_final_admitted': 0}


def stable(witness: dict) -> dict:
    result = json.loads(json.dumps(witness))
    result.pop('observed_at', None)
    result.pop('http_diagnostic', None)
    result.pop('diagnostic_hashes', None)
    result.get('workers', {}).pop('process_snapshot_sha256', None)
    return result


def verify_witness(p: dict, witness: dict, parent: dict) -> None:
    baseline, startup = prior._reference(prior._paths(p['root']))
    v4.require(witness.get('state') == 'live_unseeded_preconfig_operator_interruption' and
               witness.get('sql_hashes') == {key: baseline['database']['hashes']['full'][key]
                                             for key in prior.STABLE_SQL} and
               witness.get('sql_table_count') == 14 and
               witness.get('price_rows') == 8156 and
               witness.get('price_changed_rows') == 0 and
               witness.get('price_key_sets_equal') is True and
               witness.get('quote_pages') == witness.get('native_sidecar_index_count') == 0 and
               witness.get('task_seeded') is False and
               witness.get('material_equal_exact') is True and
               witness.get('config_paths') == ['web/unsecure/base_url'] and
               witness.get('config_value_sha256') == prior.sha(b'http://localhost:7780/') and
               witness.get('cron_config_sha256') == parent['runtime']['cron_config_sha256'] and
               witness.get('cron_stopped') is witness.get('embedded_search_stopped') is True and
               witness.get('workers', {}).get('matching_original_workers') == 0 and
               witness.get('model_calls') == witness.get('official_final_admitted') == 0,
               'case26 saved source-state witness is not exact')
    containers = witness.get('containers', [])
    v4.require(len(containers) == 2 and
               [c.get('name') for c in containers] == [sweep.APP, sweep.SEARCH] and
               [c.get('image_sha256') for c in containers] == [v4.IMAGE, v4.NATIVE_SEARCH_IMAGE] and
               all(c.get('mount_count') == 0 for c in containers),
               'case26 saved pair image/mount identities changed')


def inspect(p: dict) -> dict:
    context = _context(p)
    first = _live_once(p, context)
    time.sleep(2)
    second = _live_once(p, context)
    v4.require(stable(first) == stable(second), 'case26 two source readbacks differ')
    verify_witness(p, first, context['parent'])
    diagnostics = {}
    for item in first['containers']:
        name = item['name']
        logs = prior._docker('logs', name, timeout=30)
        diagnostics[name] = {'stdout_sha256': prior.sha(logs.stdout),
                             'stderr_sha256': prior.sha(logs.stderr)}
    return {**first, 'diagnostic_hashes': diagnostics, 'observed_at': time.time()}


def validate_freeze(p: dict) -> tuple[dict, str]:
    frozen, digest = _private(p['freeze'])
    public = json.loads(p['public'].read_bytes())
    v4.require(frozen.get('schema') == 'envloop-magento-case26-startup-freeze-private-v1' and
               frozen.get('journal_sha256') == ORIGINAL_JOURNAL_SHA and
               frozen.get('classification') == CLASSIFICATION and
               frozen.get('source_sha256s') == _sources(p) and
               public.get('private_freeze_sha256') == digest and
               public.get('case_index') == CASE_INDEX and
               public.get('same_id_whole_case_retry_cap') == 1 and
               public.get('official_final_admitted') == 0,
               'case26 additive source freeze changed')
    return frozen, digest


def prepare(p: dict) -> dict:
    v4.require(not p['freeze'].exists() and not p['public'].exists(),
               'case26 source freeze paths consumed')
    witness = inspect(p)
    frozen = {'schema': 'envloop-magento-case26-startup-freeze-private-v1',
              'classification': CLASSIFICATION, 'case_index': CASE_INDEX,
              'journal_sha256': ORIGINAL_JOURNAL_SHA,
              'journal_bytes': ORIGINAL_JOURNAL_BYTES,
              'source_sha256s': _sources(p), 'initial_witness': witness,
              'model_calls': 0, 'official_final_admitted': 0}
    digest = v4.private_new(p['freeze'], frozen)
    public = {'schema': 'envloop-magento-case26-startup-freeze-public-v1',
              'status': 'source_frozen_no_cleanup_or_retry',
              'classification': CLASSIFICATION, 'case_index': CASE_INDEX,
              'private_freeze_sha256': digest, 'journal_sha256': ORIGINAL_JOURNAL_SHA,
              'source_sha256s': frozen['source_sha256s'],
              'completed_prior_controls': CASE_INDEX,
              'same_id_whole_case_retry_cap': 1, 'sql_source_tables_verified': 14,
              'unchanged_price_rows': 8156, 'task_seeded': False,
              'gui_actions': 0, 'model_calls': 0, 'official_final_admitted': 0}
    p['public'].parent.mkdir(parents=True, exist_ok=True)
    with p['public'].open('x') as stream:
        json.dump(public, stream, indent=2, sort_keys=True); stream.write('\n')
    return public


def audit(p: dict) -> dict:
    frozen, freeze_sha = validate_freeze(p)
    v4.require(not p['audit'].exists() and not p['intent'].exists(), 'case26 audit already exists')
    witness = inspect(p)
    v4.require(stable(witness) == stable(frozen['initial_witness']),
               'case26 source changed since additive freeze')
    case = _context(p)['cases'][CASE_INDEX]
    record = {'schema': 'envloop-magento-clean-attempt-audit-private-v4',
              'status': 'invalid_infrastructure_attempt_before_gui_mutation',
              'case_index': CASE_INDEX, 'attempt': 0, 'task_id': case['task_id'],
              'package_sha256': case['package_sha256'], 'plan_sha256': prior.PLAN_SHA,
              'freeze_v4_sha256': prior.FREEZE_SHA,
              'startup_interruption_amendment_freeze_sha256': freeze_sha,
              'journal_sha256_before_audit': ORIGINAL_JOURNAL_SHA,
              'classification': CLASSIFICATION, 'active_pair': 'positive',
              'material_witness': witness, 'model_calls': 0, 'official_final_admitted': 0}
    digest = v4.private_new(p['audit'], record)
    return {'status': record['status'], 'audit_sha256': digest,
            'case_index': CASE_INDEX, 'official_final_admitted': 0}


def cleanup(p: dict) -> dict:
    fd = v4._lock()
    try:
        frozen, freeze_sha = validate_freeze(p)
        audited, audit_sha = _private(p['audit'])
        v4.require(audited.get('classification') == CLASSIFICATION and
                   audited.get('case_index') == CASE_INDEX and
                   audited.get('startup_interruption_amendment_freeze_sha256') == freeze_sha,
                   'case26 audit is not source-bound')
        if not p['intent'].exists():
            witness = inspect(p)
            v4.require(stable(witness) == stable(audited['material_witness']),
                       'case26 source drifted before exact retirement')
            intent = {'schema': 'envloop-magento-clean-cleanup-intent-private-v4',
                      'case_index': CASE_INDEX, 'attempt': 0,
                      'task_id': audited['task_id'], 'audit_sha256': audit_sha,
                      'startup_interruption_amendment_freeze_sha256': freeze_sha,
                      'journal_sha256_before_cleanup': ORIGINAL_JOURNAL_SHA,
                      'active_pair': 'positive', 'material_witness': audited['material_witness'],
                      'model_calls': 0, 'official_final_admitted': 0}
            intent_sha = v4.private_new(p['intent'], intent)
            v4.append_event(p['journal'], {'event': 'reconciliation_cleanup_intent',
                            'index': CASE_INDEX, 'attempt': 0,
                            'intent_sha256': intent_sha, 'audit_sha256': audit_sha,
                            'official_final_admitted': 0})
        intent, intent_sha = _private(p['intent'])
        v4.require(intent['material_witness'] == audited['material_witness'] and
                   intent['audit_sha256'] == audit_sha, 'case26 cleanup intent changed')
        rows = v4.read_journal(p['journal'])
        intent_rows = [r for r in rows if r.get('event') == 'reconciliation_cleanup_intent'
                       and r.get('index') == CASE_INDEX]
        if not intent_rows:
            v4.require(prior.sha(p['journal'].read_bytes()) == ORIGINAL_JOURNAL_SHA,
                       'case26 missing intent event has changed journal')
            current = inspect(p)
            v4.require(stable(current) == stable(audited['material_witness']),
                       'case26 source changed before intent-event recovery')
            v4.append_event(p['journal'], {'event': 'reconciliation_cleanup_intent',
                            'index': CASE_INDEX, 'attempt': 0,
                            'intent_sha256': intent_sha, 'audit_sha256': audit_sha,
                            'official_final_admitted': 0})
        else:
            v4.require(len(intent_rows) == 1 and
                       intent_rows[0].get('intent_sha256') == intent_sha,
                       'case26 duplicate cleanup intent event')
        if not p['receipt'].exists():
            for item in audited['material_witness']['containers']:
                v4._cleanup_step(p['journal'], CASE_INDEX, item, 'stop')
                v4._cleanup_step(p['journal'], CASE_INDEX, item, 'rm')
            sweep.assert_absent()
            receipt = {'schema': 'envloop-magento-clean-cleanup-private-v4',
                       'status': 'exact_pair_retired_for_one_whole_case_retry',
                       'case_index': CASE_INDEX, 'attempt': 0,
                       'task_id': audited['task_id'], 'package_sha256': audited['package_sha256'],
                       'plan_sha256': prior.PLAN_SHA, 'freeze_v4_sha256': prior.FREEZE_SHA,
                       'startup_interruption_amendment_freeze_sha256': freeze_sha,
                       'audit_sha256': audit_sha, 'cleanup_intent_sha256': intent_sha,
                       'active_pair': 'positive', 'material_witness': audited['material_witness'],
                       'both_containers_absent': True, 'whole_case_retry_cap_per_id': 1,
                       'study_wide_retry_cap': v4.RETRY_CAP,
                       'model_calls': 0, 'official_final_admitted': 0}
            receipt_sha = v4.private_new(p['receipt'], receipt)
        else:
            receipt, receipt_sha = _private(p['receipt']); sweep.assert_absent()
        rows = v4.read_journal(p['journal'])
        matches = [r for r in rows if r.get('event') == 'attempt_reconciled' and r.get('index') == CASE_INDEX]
        if not matches:
            v4.append_event(p['journal'], {'event': 'attempt_reconciled',
                            'index': CASE_INDEX, 'attempt': 0,
                            'classification': CLASSIFICATION,
                            'reconciliation_sha256': receipt_sha, 'audit_sha256': audit_sha,
                            'both_containers_absent': True, 'model_calls': 0,
                            'official_final_admitted': 0})
        return verify_retired(p)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)


def verify_saved_retry(p: dict, rows: list[dict] | None = None) -> dict:
    frozen, freeze_sha = validate_freeze(p)
    context = _context(p, allow_appends=True)
    audit_record, audit_sha = _private(p['audit'])
    intent, intent_sha = _private(p['intent'])
    receipt, receipt_sha = _private(p['receipt'])
    witness = audit_record['material_witness']
    verify_witness(p, witness, context['parent'])
    v4.require(audit_record.get('classification') == CLASSIFICATION and
               audit_record.get('startup_interruption_amendment_freeze_sha256') == freeze_sha and
               stable(witness) == stable(frozen['initial_witness']) and
               intent.get('material_witness') == receipt.get('material_witness') == witness and
               intent.get('audit_sha256') == receipt.get('audit_sha256') == audit_sha and
               receipt.get('cleanup_intent_sha256') == intent_sha and
               receipt.get('both_containers_absent') is True and
               receipt.get('case_index') == CASE_INDEX and
               receipt.get('task_id') == context['cases'][CASE_INDEX]['task_id'] and
               receipt.get('package_sha256') == context['cases'][CASE_INDEX]['package_sha256'] and
               receipt.get('plan_sha256') == prior.PLAN_SHA and
               receipt.get('freeze_v4_sha256') == prior.FREEZE_SHA and
               receipt.get('model_calls') == receipt.get('official_final_admitted') == 0,
               'case26 saved recovery lineage changed')
    rows = rows if rows is not None else v4.read_journal(p['journal'])
    scoped = [r for r in rows if r.get('index') == CASE_INDEX and r.get('attempt') == 0]
    reconciled = [r for r in scoped if r.get('event') == 'attempt_reconciled']
    cleanup_intents = [r for r in scoped if r.get('event') == 'reconciliation_cleanup_intent']
    expected = [(c['name'], c['container_id_sha256'], action)
                for c in witness['containers'] for action in ('stop', 'rm')]
    operations = [(r.get('name'), r.get('container_id_sha256'), r.get('action'))
                  for r in scoped if r.get('event') == 'cleanup_step_intent']
    finished = [(r.get('name'), r.get('container_id_sha256'), r.get('action'))
                for r in scoped if r.get('event') == 'cleanup_step_finished']
    v4.require(len(reconciled) == len(cleanup_intents) == 1 and
               reconciled[0].get('classification') == CLASSIFICATION and
               reconciled[0].get('reconciliation_sha256') == receipt_sha and
               reconciled[0].get('audit_sha256') == audit_sha and
               cleanup_intents[0].get('intent_sha256') == intent_sha and
               operations == finished == expected and
               intent.get('journal_sha256_before_cleanup') == ORIGINAL_JOURNAL_SHA and
               audit_record.get('journal_sha256_before_audit') == ORIGINAL_JOURNAL_SHA,
               'case26 exact cleanup journal changed')
    return {'status': 'case26_preconfig_pair_retired_for_one_same_id_retry',
            'case_index': CASE_INDEX, 'reconciliation_sha256': receipt_sha,
            'amendment_freeze_sha256': freeze_sha, 'official_final_admitted': 0}


def verify_retired(p: dict) -> dict:
    result = verify_saved_retry(p)
    sweep.assert_absent()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'prepare', 'audit', 'cleanup', 'verify-retired'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--execute-cleanup', action='store_true')
    args = parser.parse_args(); p = paths(args.root)
    if args.action == 'inspect':
        w = inspect(p)
        result = {k: w[k] for k in ('state', 'sql_table_count', 'price_rows',
                  'price_changed_rows', 'native_sidecar_index_count', 'task_seeded',
                  'model_calls', 'official_final_admitted')}
    elif args.action == 'prepare': result = prepare(p)
    elif args.action == 'audit': result = audit(p)
    elif args.action == 'cleanup':
        v4.require(args.execute_cleanup, 'case26 cleanup requires explicit execution')
        result = cleanup(p)
    else: result = verify_retired(p)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
