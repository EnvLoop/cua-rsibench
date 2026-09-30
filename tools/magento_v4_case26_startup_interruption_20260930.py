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
import re
import subprocess
from tempfile import NamedTemporaryFile
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
V1_PUBLIC_REL = Path('docs/evidence/magento-v4-case26-startup-interruption-freeze-2026-09-30.json')
V1_FREEZE_NAME = 'case26-startup-interruption-freeze-20260930.private.json'
V1_FREEZE_SHA = 'a5470097ad2490ab4d92d6b3216118162e81e24fb2c2da75e4aed17efaad65f3'
V1_PUBLIC_SHA = 'c4f217fcc19f94a43dea630b36fc86191305c4149044badd6d29e7e27a7fdd8a'
V1_AUDIT_SHA = '984be8ced69c6909379afebd733a309266cca33a40124336b354514898eba2dd'
PUBLIC_REL = Path('docs/evidence/magento-v4-case26-startup-interruption-v2-freeze-2026-09-30.json')
FREEZE_NAME = 'case26-startup-interruption-v2-freeze-20260930.private.json'
SOURCE_FILES = (
    'tools/magento_v4_case26_startup_interruption_20260930.py',
    'tools/magento_v4_preconfig_startup_amendment_20260929.py',
    'tools/magento_clean_100_v4.py',
    'tools/start_magento_native_sidecar_clone_v1.py',
    'tools/reconcile_magento_unseeded_search_drift_v1.py',
    'tools/audit_magento_v4_completed_prefix.py',
    'tests/test_magento_v4_case26_startup_interruption.py',
    'docs/FULL_STUDY_MAGENTO_CASE26_STARTUP_INTERRUPTION_V2_2026-09-30.md',
)


def paths(root: Path) -> dict:
    root = root.resolve()
    run = root / prior.RUN_REL
    attempt = v4.attempt_dir(run, CASE_INDEX, 0)
    return {'root': root, 'run': run, 'attempt': attempt,
            'journal': run / 'journal.private.jsonl',
            'freeze': run / FREEZE_NAME, 'public': root / PUBLIC_REL,
            'v1_freeze': run / V1_FREEZE_NAME, 'v1_public': root / V1_PUBLIC_REL,
            'audit': attempt / 'reconciliation-audit.private.json',
            'historical_audit': attempt / 'reconciliation-audit.v1-preintent-20260930.private.json',
            'candidate_audit': attempt / 'reconciliation-audit.v2-candidate-20260930.private.json',
            'supersession_intent': attempt / 'reconciliation-audit-supersession-v2-intent.private.json',
            'supersession_receipt': attempt / 'reconciliation-audit-supersession-v2.private.json',
            'intent': attempt / 'reconciliation-intent.private.json',
            'receipt': attempt / 'reconciliation.private.json'}


def _private(path: Path) -> tuple[dict, str]:
    v4.require(path.is_file() and not path.is_symlink() and
               path.stat().st_mode & 0o077 == 0, 'case26 private evidence unsafe')
    return v4.read_json(path)


def _sources(p: dict) -> dict:
    return {name: prior.sha((p['root'] / name).read_bytes()) for name in SOURCE_FILES}


def _mutation_root(p: dict) -> None:
    v4.require(p['root'].resolve() == Path(__file__).resolve().parents[1] == v4.ROOT.resolve(),
               'case26 writes require the loaded original evaluator checkout and its lock')


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
            'observed_at': time.time(),
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


def verify_witness(p: dict, witness: dict, parent: dict, *,
                   start_time: float | None = None) -> None:
    baseline, startup = prior._reference(prior._paths(p['root']))
    v4.require(witness.get('state') == 'live_unseeded_preconfig_operator_interruption' and
               witness.get('sql_hashes') == {key: baseline['database']['hashes']['full'][key]
                                             for key in prior.STABLE_SQL} and
               witness.get('sql_table_count') == 14 and
               witness.get('sql_hashes', {}).get('catalog_product_index_price') ==
               witness.get('sql_hashes', {}).get('catalog_product_index_price_replica') ==
               startup['train_probe_price_stages']['after_cron_policy_and_http_ready']['live_price_sha256'] and
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
               all(c.get('mount_count') == 0 and
                   type(c.get('container_id_sha256')) is str and
                   re.fullmatch(r'[0-9a-f]{64}', c['container_id_sha256']) and
                   type(c.get('created')) is str for c in containers) and
               len({c['container_id_sha256'] for c in containers}) == 2,
               'case26 saved pair image/mount identities changed')
    observed = witness.get('observed_at')
    v4.require(type(observed) in (int, float), 'case26 observation clock invalid')
    for container in containers:
        created = datetime.fromisoformat(container['created'].replace('Z', '+00:00'))
        v4.require(created.tzinfo is not None and created.timestamp() <= observed + 2 and
                   (start_time is None or start_time - 2 <= created.timestamp()),
                   'case26 saved pair creation escaped the prepare window')


def inspect(p: dict) -> dict:
    context = _context(p)
    first = _live_once(p, context)
    time.sleep(2)
    second = _live_once(p, context)
    v4.require(stable(first) == stable(second), 'case26 two source readbacks differ')
    verify_witness(p, first, context['parent'], start_time=context['start_time'])
    diagnostics = {}
    for item in first['containers']:
        name = item['name']
        logs = prior._docker('logs', name, timeout=30)
        diagnostics[name] = {'stdout_sha256': prior.sha(logs.stdout),
                             'stderr_sha256': prior.sha(logs.stderr)}
    return {**first, 'diagnostic_hashes': diagnostics, 'observed_at': time.time()}


def _identity(context: dict, freeze_sha: str) -> dict:
    case = context['cases'][CASE_INDEX]
    return {'case_index': CASE_INDEX, 'attempt': 0, 'task_id': case['task_id'],
            'package_sha256': case['package_sha256'], 'plan_sha256': prior.PLAN_SHA,
            'freeze_v4_sha256': prior.FREEZE_SHA,
            'startup_interruption_amendment_freeze_sha256': freeze_sha,
            'active_pair': 'positive', 'whole_case_retry_cap_per_id': 1,
            'study_wide_retry_cap': v4.RETRY_CAP,
            'model_calls': 0, 'official_final_admitted': 0}


def _check_record(record: dict, context: dict, freeze_sha: str,
                  schema: str, status: str | None = None) -> None:
    v4.require(record.get('schema') == schema and
               (status is None or record.get('status') == status) and
               all(type(record.get(key)) is type(value) and record.get(key) == value for key, value in
                   _identity(context, freeze_sha).items()),
               'case26 record schema, identity, source, caps or zero-work changed')


def _historical_v1(p: dict) -> dict:
    frozen, digest = _private(p['v1_freeze'])
    public_raw = p['v1_public'].read_bytes()
    v4.require(digest == V1_FREEZE_SHA and prior.sha(public_raw) == V1_PUBLIC_SHA and
               json.loads(public_raw)['private_freeze_sha256'] == digest and
               frozen.get('journal_sha256') == ORIGINAL_JOURNAL_SHA and
               frozen.get('classification') == CLASSIFICATION and
               frozen.get('case_index') == CASE_INDEX and
               frozen.get('model_calls') == frozen.get('official_final_admitted') == 0,
               'case26 retained v1 source freeze changed')
    return frozen


def _v1_audit(p: dict, context: dict, historical: Path) -> tuple[dict, bytes]:
    record, digest = _private(historical)
    raw = historical.read_bytes()
    case = context['cases'][CASE_INDEX]
    v4.require(digest == V1_AUDIT_SHA and
               record.get('schema') == 'envloop-magento-clean-attempt-audit-private-v4' and
               record.get('status') == 'invalid_infrastructure_attempt_before_gui_mutation' and
               record.get('case_index') == CASE_INDEX and record.get('attempt') == 0 and
               record.get('task_id') == case['task_id'] and
               record.get('package_sha256') == case['package_sha256'] and
               record.get('plan_sha256') == prior.PLAN_SHA and
               record.get('freeze_v4_sha256') == prior.FREEZE_SHA and
               record.get('startup_interruption_amendment_freeze_sha256') == V1_FREEZE_SHA and
               record.get('journal_sha256_before_audit') == ORIGINAL_JOURNAL_SHA and
               record.get('classification') == CLASSIFICATION and
               record.get('active_pair') == 'positive' and
               record.get('model_calls') == record.get('official_final_admitted') == 0 and
               stable(record['material_witness']) ==
               stable(_historical_v1(p)['initial_witness']),
               'case26 retained original pre-intent audit changed')
    verify_witness(p, record['material_witness'], context['parent'],
                   start_time=context['start_time'])
    return record, raw


def _public_freeze(frozen: dict, digest: str) -> dict:
    return {'schema': 'envloop-magento-case26-startup-freeze-public-v2',
            'status': 'source_frozen_v2_no_audit_supersession_cleanup_or_retry',
            'classification': CLASSIFICATION, 'case_index': CASE_INDEX,
            'private_freeze_sha256': digest, 'journal_sha256': ORIGINAL_JOURNAL_SHA,
            'source_sha256s': frozen['source_sha256s'],
            'retained_v1_private_freeze_sha256': V1_FREEZE_SHA,
            'retained_v1_public_freeze_sha256': V1_PUBLIC_SHA,
            'original_preintent_audit_sha256': V1_AUDIT_SHA,
            'original_audit_preserved_before_replacement_required': True,
            'completed_prior_controls': CASE_INDEX,
            'same_id_whole_case_retry_cap': 1, 'sql_source_tables_verified': 14,
            'unchanged_price_rows': 8156, 'task_seeded': False,
            'gui_actions': 0, 'model_calls': 0, 'official_final_admitted': 0}


def validate_freeze(p: dict) -> tuple[dict, str]:
    previous = _historical_v1(p)
    frozen, digest = _private(p['freeze'])
    v4.require(frozen.get('schema') == 'envloop-magento-case26-startup-freeze-private-v2' and
               frozen.get('journal_sha256') == ORIGINAL_JOURNAL_SHA and
               frozen.get('journal_bytes') == ORIGINAL_JOURNAL_BYTES and
               frozen.get('classification') == CLASSIFICATION and
               frozen.get('case_index') == CASE_INDEX and
               frozen.get('retained_v1_private_freeze_sha256') == V1_FREEZE_SHA and
               frozen.get('retained_v1_public_freeze_sha256') == V1_PUBLIC_SHA and
               frozen.get('original_preintent_audit_sha256') == V1_AUDIT_SHA and
               frozen.get('source_sha256s') == _sources(p) and
               frozen.get('model_calls') == frozen.get('official_final_admitted') == 0 and
               stable(frozen['initial_witness']) == stable(previous['initial_witness']) and
               json.loads(p['public'].read_bytes()) == _public_freeze(frozen, digest),
               'case26 additive v2 source freeze changed')
    return frozen, digest


def prepare(p: dict) -> dict:
    _mutation_root(p)
    v4.require(all(not p[key].exists() and not p[key].is_symlink() for key in
                   ('freeze', 'public', 'intent', 'receipt', 'historical_audit',
                    'candidate_audit', 'supersession_intent', 'supersession_receipt')),
               'case26 v2 freeze requires an untouched pre-cleanup boundary')
    context = _context(p)
    previous = _historical_v1(p)
    _v1_audit(p, context, p['audit'])
    witness = inspect(p)
    v4.require(stable(witness) == stable(previous['initial_witness']),
               'case26 live source differs from the retained v1 freeze')
    frozen = {'schema': 'envloop-magento-case26-startup-freeze-private-v2',
              'classification': CLASSIFICATION, 'case_index': CASE_INDEX,
              'journal_sha256': ORIGINAL_JOURNAL_SHA,
              'journal_bytes': ORIGINAL_JOURNAL_BYTES,
              'source_sha256s': _sources(p), 'initial_witness': witness,
              'retained_v1_private_freeze_sha256': V1_FREEZE_SHA,
              'retained_v1_public_freeze_sha256': V1_PUBLIC_SHA,
              'original_preintent_audit_sha256': V1_AUDIT_SHA,
              'model_calls': 0, 'official_final_admitted': 0}
    digest = v4.private_new(p['freeze'], frozen)
    public = _public_freeze(frozen, digest)
    p['public'].parent.mkdir(parents=True, exist_ok=True)
    with p['public'].open('x') as stream:
        json.dump(public, stream, indent=2, sort_keys=True); stream.write('\n')
    return public


def _atomic_bytes(path: Path, raw: bytes, *, replace: bool = False) -> None:
    v4.require(path.parent.is_dir() and not path.parent.is_symlink() and
               not path.is_symlink(), 'case26 audit supersession target unsafe')
    with NamedTemporaryFile(dir=path.parent, prefix='.case26-audit-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            if replace:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _supersession_identity(p: dict, context: dict, freeze_sha: str,
                            replacement_sha: str) -> dict:
    return {**_identity(context, freeze_sha),
            'retained_v1_private_freeze_sha256': V1_FREEZE_SHA,
            'original_preintent_audit_sha256': V1_AUDIT_SHA,
            'replacement_audit_sha256': replacement_sha,
            'historical_audit_path': str(p['historical_audit'].relative_to(p['attempt'])),
            'candidate_audit_path': str(p['candidate_audit'].relative_to(p['attempt'])),
            'standard_audit_path': str(p['audit'].relative_to(p['attempt'])),
            'journal_sha256_before_supersession': ORIGINAL_JOURNAL_SHA,
            'cleanup_authorized_by_supersession': False}


def _supersession_records(p: dict, context: dict, freeze_sha: str) -> tuple[dict, str]:
    audit_record, audit_sha = _private(p['audit'])
    candidate, candidate_sha = _private(p['candidate_audit'])
    _v1_audit(p, context, p['historical_audit'])
    intent, intent_sha = _private(p['supersession_intent'])
    receipt, _ = _private(p['supersession_receipt'])
    _check_record(audit_record, context, freeze_sha,
                  'envloop-magento-clean-attempt-audit-private-v4',
                  'invalid_infrastructure_attempt_before_gui_mutation')
    identity = _supersession_identity(p, context, freeze_sha, audit_sha)
    v4.require(audit_record == candidate and audit_sha == candidate_sha and
               audit_record.get('classification') == CLASSIFICATION and
               audit_record.get('journal_sha256_before_audit') == ORIGINAL_JOURNAL_SHA and
               audit_record.get('original_preintent_audit_sha256') == V1_AUDIT_SHA and
               audit_record.get('historical_audit_path') == identity['historical_audit_path'] and
               all(intent.get(k) == receipt.get(k) == value for k, value in identity.items()) and
               intent.get('schema') == 'envloop-magento-case26-preintent-audit-supersession-intent-private-v2' and
               receipt.get('schema') == 'envloop-magento-case26-preintent-audit-supersession-private-v2' and
               receipt.get('status') == 'original_audit_archived_v2_audit_activated_no_cleanup' and
               receipt.get('supersession_intent_sha256') == intent_sha and
               receipt.get('original_audit_bytes_preserved') is True,
               'case26 original audit preservation or v2 supersession changed')
    return audit_record, audit_sha


def audit(p: dict) -> dict:
    """Explicit pre-intent supersession; archive original bytes before replace."""
    _mutation_root(p)
    fd = v4._lock()
    try:
        frozen, freeze_sha = validate_freeze(p)
        context = _context(p)
        v4.require(all(not p[k].exists() and not p[k].is_symlink()
                       for k in ('intent', 'receipt')),
                   'case26 audit supersession is forbidden after cleanup intent')
        witness = inspect(p)
        v4.require(stable(witness) == stable(frozen['initial_witness']),
                   'case26 source changed since additive v2 freeze')
        if not p['supersession_intent'].exists():
            original, original_raw = _v1_audit(p, context, p['audit'])
            if not p['candidate_audit'].exists():
                record = {**_identity(context, freeze_sha),
                          'schema': 'envloop-magento-clean-attempt-audit-private-v4',
                          'status': 'invalid_infrastructure_attempt_before_gui_mutation',
                          'journal_sha256_before_audit': ORIGINAL_JOURNAL_SHA,
                          'classification': CLASSIFICATION, 'material_witness': witness,
                          'original_preintent_audit_sha256': V1_AUDIT_SHA,
                          'historical_audit_path': str(p['historical_audit'].relative_to(p['attempt']))}
                v4.private_new(p['candidate_audit'], record)
            candidate, candidate_sha = _private(p['candidate_audit'])
            _check_record(candidate, context, freeze_sha,
                          'envloop-magento-clean-attempt-audit-private-v4',
                          'invalid_infrastructure_attempt_before_gui_mutation')
            v4.require(stable(candidate['material_witness']) == stable(witness) and
                       candidate.get('original_preintent_audit_sha256') == V1_AUDIT_SHA,
                       'case26 staged v2 audit changed')
            if not p['historical_audit'].exists():
                _atomic_bytes(p['historical_audit'], original_raw)
            _v1_audit(p, context, p['historical_audit'])
            v4.private_new(p['supersession_intent'], {
                **_supersession_identity(p, context, freeze_sha, candidate_sha),
                'schema': 'envloop-magento-case26-preintent-audit-supersession-intent-private-v2'})
        candidate, candidate_sha = _private(p['candidate_audit'])
        intent, intent_sha = _private(p['supersession_intent'])
        _v1_audit(p, context, p['historical_audit'])
        identity = _supersession_identity(p, context, freeze_sha, candidate_sha)
        _check_record(candidate, context, freeze_sha,
                      'envloop-magento-clean-attempt-audit-private-v4',
                      'invalid_infrastructure_attempt_before_gui_mutation')
        v4.require(intent.get('schema') == 'envloop-magento-case26-preintent-audit-supersession-intent-private-v2' and
                   all(intent.get(k) == value for k, value in identity.items()) and
                   stable(candidate['material_witness']) == stable(witness),
                   'case26 supersession intent or staged audit changed')
        current, current_sha = _private(p['audit'])
        v4.require(current_sha in (V1_AUDIT_SHA, candidate_sha),
                   'case26 standard audit was changed outside supersession')
        if current_sha == V1_AUDIT_SHA:
            v4.require(not p['supersession_receipt'].exists(),
                       'case26 completed supersession was rolled back')
            _atomic_bytes(p['audit'], p['candidate_audit'].read_bytes(), replace=True)
        if not p['supersession_receipt'].exists():
            v4.private_new(p['supersession_receipt'], {
                **identity,
                'schema': 'envloop-magento-case26-preintent-audit-supersession-private-v2',
                'status': 'original_audit_archived_v2_audit_activated_no_cleanup',
                'supersession_intent_sha256': intent_sha,
                'original_audit_bytes_preserved': True})
        record, digest = _supersession_records(p, context, freeze_sha)
        return {'status': record['status'], 'audit_sha256': digest,
                'retained_original_audit_sha256': V1_AUDIT_SHA,
                'case_index': CASE_INDEX, 'official_final_admitted': 0}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)


def _cleanup_events(rows: list[dict], witness: dict, *, complete: bool = False) -> dict:
    scoped = [r for r in rows[ORIGINAL_JOURNAL_ROWS:]
              if r.get('index') == CASE_INDEX and r.get('attempt') == 0]
    allowed = {'reconciliation_cleanup_intent', 'cleanup_step_intent',
               'cleanup_step_finished', 'attempt_reconciled'}
    v4.require(all(r.get('event') in allowed and r.get('official_final_admitted') == 0 and
                   r.get('model_calls', 0) == 0 for r in scoped),
               'case26 post-boundary task activity or nonzero work appeared')
    intents = [r for r in scoped if r['event'] == 'reconciliation_cleanup_intent']
    reconciled = [r for r in scoped if r['event'] == 'attempt_reconciled']
    operations = [r for r in scoped if r['event'] == 'cleanup_step_intent']
    finished = [r for r in scoped if r['event'] == 'cleanup_step_finished']
    key = lambda r: (r.get('name'), r.get('container_id_sha256'), r.get('action'))
    expected = [(c['name'], c['container_id_sha256'], action)
                for c in witness['containers'] for action in ('stop', 'rm')]
    actions, finishes = list(map(key, operations)), list(map(key, finished))
    positions = {id(r): i for i, r in enumerate(scoped)}
    v4.require(len(intents) <= 1 and len(reconciled) <= 1 and
               actions == expected[:len(actions)] and
               len(finishes) == len(set(finishes)) and
               finishes == [item for item in expected if item in finishes] and
               all(item in actions for item in finishes) and
               all(type(r.get('stdout_sha256')) is str and
                   re.fullmatch(r'[0-9a-f]{64}', r['stdout_sha256']) and
                   type(r.get('stderr_sha256')) is str and
                   re.fullmatch(r'[0-9a-f]{64}', r['stderr_sha256'])
                   for r in finished) and
               all(len(intents) == 1 and positions[id(intents[0])] < positions[id(r)]
                   for r in operations) and
               all(positions[id(next(o for o in operations if key(o) == key(r)))] <
                   positions[id(r)] for r in finished) and
               (not reconciled or (actions == expected and
                   all(positions[id(r)] < positions[id(reconciled[0])]
                       for r in operations + finished))) and
               (not complete or (len(intents) == len(reconciled) == 1 and actions == expected)),
               'case26 exact cleanup intent/effect journal changed')
    return {'scoped': scoped, 'intent_rows': intents, 'reconciled': reconciled,
            'expected': expected, 'actions': actions, 'finishes': finishes,
            'missing_finishes': [item for item in expected if item not in finishes]}


def _check_cleanup_intent(intent: dict, context: dict, freeze_sha: str,
                          audit_record: dict, audit_sha: str) -> None:
    _check_record(intent, context, freeze_sha,
                  'envloop-magento-clean-cleanup-intent-private-v4')
    v4.require(intent.get('material_witness') == audit_record['material_witness'] and
               intent.get('audit_sha256') == audit_sha and
               intent.get('journal_sha256_before_cleanup') == ORIGINAL_JOURNAL_SHA,
               'case26 cleanup intent changed')


def _append_cleanup_intent(p: dict, context: dict, freeze_sha: str,
                           intent_sha: str, audit_sha: str) -> None:
    v4.append_event(p['journal'], {
        'event': 'reconciliation_cleanup_intent', 'index': CASE_INDEX,
        **_identity(context, freeze_sha), 'intent_sha256': intent_sha,
        'audit_sha256': audit_sha})


def _check_cleanup_intent_event(event: dict, context: dict, freeze_sha: str,
                                intent_sha: str, audit_sha: str) -> None:
    v4.require(event.get('event') == 'reconciliation_cleanup_intent' and
               event.get('index') == CASE_INDEX and
               all(event.get(k) == value for k, value in _identity(context, freeze_sha).items()) and
               event.get('intent_sha256') == intent_sha and
               event.get('audit_sha256') == audit_sha,
               'case26 cleanup intent event changed')


def _check_cleanup_receipt(receipt: dict, context: dict, freeze_sha: str,
                           audited: dict, audit_sha: str, intent_sha: str,
                           events: dict) -> None:
    _check_record(receipt, context, freeze_sha,
                  'envloop-magento-clean-cleanup-private-v4',
                  'exact_pair_retired_for_one_whole_case_retry')
    v4.require(receipt.get('material_witness') == audited['material_witness'] and
               receipt.get('audit_sha256') == audit_sha and
               receipt.get('cleanup_intent_sha256') == intent_sha and
               receipt.get('both_containers_absent') is True and
               receipt.get('original_cleanup_command_results_reconstructed') is False and
               receipt.get('cleanup_effects_observed_from_exact_pair_absence') is True and
               receipt.get('cleanup_finish_event_count') == len(events['finishes']) and
               receipt.get('cleanup_actions_with_unrecorded_command_results') ==
                   [list(item) for item in events['missing_finishes']],
               'case26 cleanup receipt does not bind the observed exact retirement')


def cleanup(p: dict) -> dict:
    _mutation_root(p)
    fd = v4._lock()
    try:
        frozen, freeze_sha = validate_freeze(p)
        context = _context(p, allow_appends=True)
        _workers_absent()
        audited, audit_sha = _supersession_records(p, context, freeze_sha)
        v4.require(stable(audited['material_witness']) == stable(frozen['initial_witness']),
                   'case26 v2 audit material differs from source freeze')
        verify_witness(p, audited['material_witness'], context['parent'],
                       start_time=context['start_time'])
        if not p['intent'].exists():
            v4.require(not p['receipt'].exists(), 'case26 cleanup receipt lacks its intent')
            witness = inspect(p)
            v4.require(stable(witness) == stable(audited['material_witness']),
                       'case26 source drifted before exact retirement')
            intent = {**_identity(context, freeze_sha),
                      'schema': 'envloop-magento-clean-cleanup-intent-private-v4',
                      'audit_sha256': audit_sha,
                      'journal_sha256_before_cleanup': ORIGINAL_JOURNAL_SHA,
                      'material_witness': audited['material_witness']}
            v4.private_new(p['intent'], intent)
        intent, intent_sha = _private(p['intent'])
        _check_cleanup_intent(intent, context, freeze_sha, audited, audit_sha)
        rows = v4.read_journal(p['journal'])
        events = _cleanup_events(rows, audited['material_witness'])
        if not events['intent_rows']:
            v4.require(prior.sha(p['journal'].read_bytes()) == ORIGINAL_JOURNAL_SHA,
                       'case26 missing intent event has changed journal')
            current = inspect(p)
            v4.require(stable(current) == stable(audited['material_witness']),
                       'case26 source changed before intent-event recovery')
            _append_cleanup_intent(p, context, freeze_sha, intent_sha, audit_sha)
        else:
            _check_cleanup_intent_event(events['intent_rows'][0], context,
                                        freeze_sha, intent_sha, audit_sha)
        if not p['receipt'].exists():
            _workers_absent()
            for item in audited['material_witness']['containers']:
                v4._cleanup_step(p['journal'], CASE_INDEX, item, 'stop')
                v4._cleanup_step(p['journal'], CASE_INDEX, item, 'rm')
            sweep.assert_absent()
            events = _cleanup_events(v4.read_journal(p['journal']), audited['material_witness'])
            v4.require(events['actions'] == events['expected'],
                       'case26 retirement lacks four exact ordered intents')
            receipt = {**_identity(context, freeze_sha),
                       'schema': 'envloop-magento-clean-cleanup-private-v4',
                       'status': 'exact_pair_retired_for_one_whole_case_retry',
                       'audit_sha256': audit_sha, 'cleanup_intent_sha256': intent_sha,
                       'material_witness': audited['material_witness'],
                       'both_containers_absent': True,
                       'cleanup_finish_event_count': len(events['finishes']),
                       'cleanup_actions_with_unrecorded_command_results':
                           [list(item) for item in events['missing_finishes']],
                       'original_cleanup_command_results_reconstructed': False,
                       'cleanup_effects_observed_from_exact_pair_absence': True}
            receipt_sha = v4.private_new(p['receipt'], receipt)
        else:
            receipt, receipt_sha = _private(p['receipt'])
            sweep.assert_absent()
        events = _cleanup_events(v4.read_journal(p['journal']), audited['material_witness'])
        _check_cleanup_receipt(receipt, context, freeze_sha, audited,
                               audit_sha, intent_sha, events)
        if not events['reconciled']:
            v4.append_event(p['journal'], {
                'event': 'attempt_reconciled', 'index': CASE_INDEX,
                **_identity(context, freeze_sha), 'classification': CLASSIFICATION,
                'reconciliation_sha256': receipt_sha, 'audit_sha256': audit_sha,
                'both_containers_absent': True})
        return verify_retired(p)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)


def verify_saved_retry(p: dict, rows: list[dict] | None = None) -> dict:
    frozen, freeze_sha = validate_freeze(p)
    context = _context(p, allow_appends=True)
    audit_record, audit_sha = _supersession_records(p, context, freeze_sha)
    intent, intent_sha = _private(p['intent'])
    receipt, receipt_sha = _private(p['receipt'])
    witness = audit_record['material_witness']
    verify_witness(p, witness, context['parent'], start_time=context['start_time'])
    _check_cleanup_intent(intent, context, freeze_sha, audit_record, audit_sha)
    _check_record(receipt, context, freeze_sha,
                  'envloop-magento-clean-cleanup-private-v4',
                  'exact_pair_retired_for_one_whole_case_retry')
    v4.require(audit_record.get('classification') == CLASSIFICATION and
               audit_record.get('journal_sha256_before_audit') == ORIGINAL_JOURNAL_SHA and
               stable(witness) == stable(frozen['initial_witness']) and
               receipt.get('material_witness') == witness and
               receipt.get('audit_sha256') == audit_sha and
               receipt.get('cleanup_intent_sha256') == intent_sha and
               receipt.get('both_containers_absent') is True and
               receipt.get('original_cleanup_command_results_reconstructed') is False and
               receipt.get('cleanup_effects_observed_from_exact_pair_absence') is True,
               'case26 saved recovery lineage changed')
    rows = rows if rows is not None else v4.read_journal(p['journal'])
    v4.require(rows[:ORIGINAL_JOURNAL_ROWS] == context['rows'],
               'case26 supplied retry journal differs from the frozen prefix')
    v4.validate_case_sequence(rows, context['cases'])
    events = _cleanup_events(rows, witness, complete=True)
    _check_cleanup_receipt(receipt, context, freeze_sha, audit_record,
                           audit_sha, intent_sha, events)
    _check_cleanup_intent_event(events['intent_rows'][0], context,
                                freeze_sha, intent_sha, audit_sha)
    reconciled = events['reconciled'][0]
    v4.require(all(reconciled.get(k) == value for k, value in _identity(context, freeze_sha).items()) and
               reconciled.get('classification') == CLASSIFICATION and
               reconciled.get('reconciliation_sha256') == receipt_sha and
               reconciled.get('audit_sha256') == audit_sha and
               reconciled.get('both_containers_absent') is True and
               receipt.get('cleanup_finish_event_count') == len(events['finishes']) and
               receipt.get('cleanup_actions_with_unrecorded_command_results') ==
                   [list(item) for item in events['missing_finishes']],
               'case26 exact cleanup journal changed')
    return {'status': 'case26_preconfig_pair_retired_for_one_same_id_retry',
            'case_index': CASE_INDEX, 'reconciliation_sha256': receipt_sha,
            'amendment_freeze_sha256': freeze_sha,
            'original_cleanup_command_results_reconstructed': False,
            'cleanup_finish_event_count': len(events['finishes']),
            'official_final_admitted': 0}


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
