"""Audit and retire one exact, unseeded Magento search-index drift pair.

This is evaluator infrastructure reconciliation, never a task action or score.
The failed containers are read only until an audit receipt has been written.
No indexer, task seed, or source-data repair is dispatched here.
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

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import IMAGE, check_clone
from magento_catalog_factory.verify import (
    NATIVE_SEARCH_HOST, NATIVE_SEARCH_IMAGE, NATIVE_SEARCH_NETWORK,
    canonical_sha, check_native_search_sidecar,
)
from tools.start_magento_native_sidecar_clone_v1 import (
    READ_CONFIG_PHP, docker, sidecar_health,
)
from tools.sweep_magento_original_gui_controls_v1 import (
    APP, SEARCH, SEARCH_SHA, append_event, assert_absent, sha, write_new,
)


CASE_INDEX = 31
SWEEP_NAME = 'sweep-final-candidates030-099-v1'
ORIGINAL_JOURNAL_SHA = '4fea2b8ca9d9edb53db21dd6dd6493613e95bc44e2fe73fab9664f37cdacd196'
PRIOR_SNAPSHOT_SHA = 'b153331d179679b00e8949abb0be4cdd160aa6703a20464434a1b06fd419182d'
PRIOR_CALIBRATION_SHA = 'ad2749ed7aeef34281a7b1c943db8625cf510c83da2ad7a7db588c9d378db3fd'
FAILED_PROCESS_SHA = '0f3aece3dafb10d7fd28f62537bde50c440be8d6a8c66652422f752fe756a0ec'
FAILED_STDERR_SHA = '262e9a860cd4fd76827c86281163438da064af237418f27d5c0e4a049d66040e'
OBSERVED_SEARCH_SHA = '4bd64ae0b2032f221f8c2e56c1dd243f09677ce386860a6f4eb6d582e36ddc20'
STABLE_CATALOG = (
    'catalog_product_entity', 'catalog_product_entity_decimal',
    'catalog_product_entity_int', 'catalog_product_entity_varchar',
    'catalog_product_entity_text', 'catalog_product_entity_datetime',
    'catalog_product_index_price_replica', 'cataloginventory_stock_item',
)
STABLE_BUSINESS = (
    'sales_order', 'sales_order_item', 'customer_entity',
    'customer_address_entity', 'quote',
)
PRICE_FIELDS = frozenset({'final_price', 'min_price', 'max_price'})
AUDIT_NAME = 'index-drift-audit.private.json'
SQL_READ = r'''$cfg=include '/var/www/magento2/app/etc/env.php';
$d=$cfg['db']['connection']['default'];
$p=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$p->exec('START TRANSACTION READ ONLY');
$tables=['catalog_product_entity','catalog_product_entity_decimal',
 'catalog_product_entity_int','catalog_product_entity_varchar',
 'catalog_product_entity_text','catalog_product_entity_datetime',
 'catalog_product_index_price','catalog_product_index_price_replica',
 'cataloginventory_stock_item','sales_order','sales_order_item',
 'customer_entity','customer_address_entity','quote'];
$hashes=[];$price=[];
foreach($tables as $table){
 $all=[];
 foreach($p->query('SELECT * FROM `'.$table.'`') as $row){
  $canonical=[];foreach($row as $key=>$value){if(is_string($key))$canonical[$key]=$value;}
  ksort($canonical);
  $all[]=hash('sha256',json_encode($canonical,JSON_UNESCAPED_SLASHES));
  if($table==='catalog_product_index_price' ||
     $table==='catalog_product_index_price_replica'){
   $key=implode(':',[$canonical['entity_id'],$canonical['customer_group_id'],
                     $canonical['website_id']]);
   if(isset($price[$table][$key]))throw new Exception('duplicate price index key');
   $price[$table][$key]=$canonical;
  }
 }
 sort($all);$hashes[$table]=hash('sha256',implode("\n",$all));
}
$live=$price['catalog_product_index_price'];
$replica=$price['catalog_product_index_price_replica'];
$fields=[];$changed=0;$sameKeys=count($live)===count($replica);
foreach($live as $key=>$row){
 if(!isset($replica[$key])){$sameKeys=false;continue;}
 $other=$replica[$key];
 if($row!==$other){$changed++;
  foreach(array_unique(array_merge(array_keys($row),array_keys($other))) as $field){
   if(($row[$field]??null)!==($other[$field]??null))
    $fields[$field]=($fields[$field]??0)+1;
  }
 }
}
foreach($replica as $key=>$row){if(!isset($live[$key]))$sameKeys=false;}
$p->rollBack();
echo json_encode(['hashes'=>$hashes,'price_rows'=>count($live),
 'price_key_sets_equal'=>$sameKeys,'price_changed_rows'=>$changed,
 'price_changed_fields'=>$fields],JSON_THROW_ON_ERROR);'''


def _json_with_sha(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    require(sha(raw) == expected, f'{path.name} changed')
    return json.loads(raw)


def validate_stopped_attempt(events: list[dict], process: dict) -> tuple[float, float]:
    require(events and events[-1].get('event') == 'sweep_stopped' and
            events[-1].get('passed') == 1 and
            events[-1].get('official_final_admitted') == 0 and
            process.get('exit_code') == 1 and
            process.get('stdout_bytes') == 0 and
            process.get('stderr_sha256') == FAILED_STDERR_SHA,
            'original pre-task failure record changed')
    intent = [row for row in events if row.get('index') == CASE_INDEX and
              row.get('step') == 'positive-prepare' and
              row.get('event') == 'step_intent']
    finish = [row for row in events if row.get('index') == CASE_INDEX and
              row.get('step') == 'positive-prepare' and
              row.get('event') == 'step_finished' and row.get('exit_code') == 1]
    require(len(intent) == len(finish) == 1 and
            not any(row.get('index') == CASE_INDEX and
                    (row.get('step', '').endswith('-seed') or
                     row.get('event') == 'task_gui_calibrated') for row in events),
            'case was seeded, scored, or has a different failure sequence')
    return float(intent[0]['time']), float(finish[0]['time'])


def compare_sql_source(current: dict, prior: dict) -> dict:
    hashes = current.get('hashes', {})
    reference = prior['database']['hashes']['full']
    stable = STABLE_CATALOG + STABLE_BUSINESS
    require(all(hashes.get(name) == reference[name] for name in stable) and
            hashes.get('catalog_product_index_price') !=
            reference['catalog_product_index_price'] and
            current.get('price_rows') == 8156 and
            current.get('price_key_sets_equal') is True and
            current.get('price_changed_rows') == 2776 and
            current.get('price_changed_fields') == {
                'final_price': 2552, 'min_price': 2776, 'max_price': 223},
            'pre-task source differed beyond the observed derived price-index drift')
    return {'stable_catalog_tables_matched': len(STABLE_CATALOG),
            'stable_business_tables_matched': len(STABLE_BUSINESS),
            'live_price_index_sha256': hashes['catalog_product_index_price'],
            'frozen_price_index_sha256': reference['catalog_product_index_price'],
            'price_rows': 8156, 'price_changed_rows': 2776,
            'price_changed_fields': current['price_changed_fields']}


def _created_during_step(row: dict, start: float, finish: float) -> bool:
    created = datetime.fromisoformat(row['Created'].replace('Z', '+00:00')).timestamp()
    return start - 3 <= created <= finish + 3


def inspect_pair(start: float, finish: float) -> tuple[dict, dict]:
    app, search = json.loads(docker('inspect', APP, SEARCH))
    check_clone(APP, 7794, 7795)
    check_native_search_sidecar(APP)
    require(app['Name'] == '/' + APP and search['Name'] == '/' + SEARCH and
            app['Image'] == IMAGE and search['Image'] == NATIVE_SEARCH_IMAGE and
            app['State']['Running'] and search['State']['Running'] and
            not app['Mounts'] and not search['Mounts'] and
            _created_during_step(app, start, finish) and
            _created_during_step(search, start, finish) and
            NATIVE_SEARCH_NETWORK in app['NetworkSettings']['Networks'] and
            NATIVE_SEARCH_NETWORK in search['NetworkSettings']['Networks'],
            'failed attempt does not own these exact mount-free containers')
    require(sidecar_health() is not None, 'sidecar is not healthy')
    return app, search


def audit_live(sweep: Path) -> dict:
    require(sweep == (ROOT / 'work/magento-original' / SWEEP_NAME).resolve(),
            'only the stopped case-31 sweep is eligible')
    journal = sweep / 'events.private.jsonl'
    journal_raw = journal.read_bytes()
    require(sha(journal_raw) == ORIGINAL_JOURNAL_SHA,
            'original stopped journal changed or recovery already attempted')
    events = [json.loads(line) for line in journal_raw.splitlines()]
    case_dir = sweep / f'case-{CASE_INDEX:03d}/positive'
    process = _json_with_sha(case_dir / 'positive-prepare-process.private.json',
                             FAILED_PROCESS_SHA)
    require(sha((case_dir / 'positive-prepare-stderr.private.bin').read_bytes()) ==
            FAILED_STDERR_SHA, 'original process stderr changed')
    start, finish = validate_stopped_attempt(events, process)
    calibration = _json_with_sha(sweep / 'case-030/calibration.private.json',
                                 PRIOR_CALIBRATION_SHA)
    require(calibration['positive_score'] == 1.0 and
            calibration['wrong_variant_score'] == 0.0 and
            calibration['fresh_reset_passed'] is True,
            'preceding frozen-source control changed')
    prior = _json_with_sha(sweep / 'case-030/positive/neutral/private-before.json',
                           PRIOR_SNAPSHOT_SHA)
    require(prior['search']['full_sha256'] == SEARCH_SHA,
            'preceding source index was not frozen')
    app, search = inspect_pair(start, finish)
    config = json.loads(docker('exec', APP, 'php', '-r', READ_CONFIG_PHP,
                               timeout=30))
    expected = {
        'catalog/search/engine': 'elasticsearch7',
        'catalog/search/elasticsearch7_server_hostname': NATIVE_SEARCH_HOST,
        'catalog/search/elasticsearch7_server_port': '9200',
        'catalog/search/elasticsearch7_index_prefix': 'magento2',
        'web/unsecure/base_url': 'http://localhost:7794/',
        'web/secure/base_url': 'http://localhost:7794/',
    }
    require(config['quote_pages'] == 0 and
            {row['path']: row['value'] for row in config['rows']} == expected,
            'unseeded application config or quote count changed')
    result = json.loads(docker('exec', APP, 'curl', '-fsS', '--max-time', '30',
                               f'http://{SEARCH}:9200/magento2_product_1/_search?size=1000',
                               timeout=45))
    hits = result['hits']['hits']
    documents = {row['_id']: row['_source'] for row in hits}
    observed = canonical_sha(documents)
    require(len(hits) == len(documents) == result['hits']['total']['value'] == 181 and
            observed == OBSERVED_SEARCH_SHA and observed != SEARCH_SHA,
            'observed search index is no longer the exact stopped drift')
    sql = json.loads(docker('exec', APP, 'php', '-r', SQL_READ, timeout=120))
    material = compare_sql_source(sql, prior)
    return {
        'schema': 'envloop-magento-preseed-search-drift-private-audit-v1',
        'case_index': CASE_INDEX,
        'original_journal_sha256': ORIGINAL_JOURNAL_SHA,
        'failed_process_sha256': FAILED_PROCESS_SHA,
        'failed_stderr_sha256': FAILED_STDERR_SHA,
        'app_container_id_sha256': sha(app['Id'].encode()),
        'search_container_id_sha256': sha(search['Id'].encode()),
        'app_image_sha256': IMAGE,
        'search_image_sha256': NATIVE_SEARCH_IMAGE,
        'mount_count': 0, 'quote_pages': 0,
        'search_document_count': 181,
        'frozen_search_sha256': SEARCH_SHA,
        'observed_search_sha256': observed,
        'material': material,
        'task_seeded': False, 'model_calls': 0,
        'official_final_admitted': 0,
    }


def _require_same_audit(saved: dict, current: dict) -> None:
    require(saved == current, 'live source or container identity changed after audit')


def cleanup(sweep: Path, audit_path: Path) -> dict:
    require(audit_path == (sweep / f'case-{CASE_INDEX:03d}/positive' /
                           AUDIT_NAME).resolve() and audit_path.is_file(),
            'exact saved private audit required')
    lock_path = ROOT / 'work/magento-original/exclusive-worker.lock'
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        saved_raw = audit_path.read_bytes()
        saved = json.loads(saved_raw)
        current = audit_live(sweep)
        _require_same_audit(saved, current)
        journal = sweep / 'events.private.jsonl'
        append_event(journal, {
            'event': 'operator_preseed_search_drift_cleanup_intent',
            'index': CASE_INDEX, 'time': time.time(),
            'audit_sha256': sha(saved_raw),
            'task_seeded': False, 'official_final_admitted': 0,
        })
        processes = []
        for name, expected in ((APP, saved['app_container_id_sha256']),
                               (SEARCH, saved['search_container_id_sha256'])):
            for action, timeout in (('stop', 60), ('rm', 30)):
                row = json.loads(docker('inspect', name))[0]
                require(sha(row['Id'].encode()) == expected and not row['Mounts'] and
                        row['Image'] == (IMAGE if name == APP else NATIVE_SEARCH_IMAGE),
                        'container identity changed during cleanup')
                outcome = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                          action, name], capture_output=True,
                                         timeout=timeout, check=False)
                processes.append({'role': 'app' if name == APP else 'search',
                                  'action': action, 'exit_code': outcome.returncode,
                                  'stdout_sha256': sha(outcome.stdout),
                                  'stderr_sha256': sha(outcome.stderr)})
                require(outcome.returncode == 0,
                        'exact-pair cleanup failed; inspect before any recovery')
        assert_absent()
        receipt = {
            'schema': 'envloop-magento-preseed-search-drift-cleanup-private-v1',
            'case_index': CASE_INDEX,
            'original_journal_sha256': ORIGINAL_JOURNAL_SHA,
            'audit_sha256': sha(saved_raw),
            'app_container_id_sha256': saved['app_container_id_sha256'],
            'search_container_id_sha256': saved['search_container_id_sha256'],
            'steps': processes,
            'task_seeded': False, 'both_containers_cleaned': True,
            'model_calls': 0, 'official_final_admitted': 0,
        }
        receipt_sha = write_new(audit_path.parent /
                                'index-drift-cleanup.private.json', receipt)
        append_event(journal, {
            'event': 'operator_reconciled_pre_task_search_index_drift',
            'index': CASE_INDEX, 'time': time.time(),
            'task_seeded': False, 'both_containers_cleaned': True,
            'audit_sha256': sha(saved_raw),
            'cleanup_receipt_sha256': receipt_sha,
            'official_final_admitted': 0,
        })
        return {'status': 'exact_unseeded_drift_pair_retired',
                'cleanup_receipt_sha256': receipt_sha,
                'official_final_admitted': 0}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sweep-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('audit', 'cleanup'), required=True)
    args = parser.parse_args()
    sweep = args.sweep_dir.resolve()
    require(sweep == (ROOT / 'work/magento-original' / SWEEP_NAME).resolve(),
            'only the exact stopped case-31 sweep is eligible')
    audit_path = sweep / f'case-{CASE_INDEX:03d}/positive' / AUDIT_NAME
    if args.mode == 'audit':
        receipt = audit_live(sweep)
        digest = write_new(audit_path, receipt)
        print(json.dumps({'status': 'exact_preseed_drift_audited',
                          'private_audit_sha256': digest,
                          'official_final_admitted': 0}, sort_keys=True))
    else:
        print(json.dumps(cleanup(sweep, audit_path), sort_keys=True))


if __name__ == '__main__':
    main()
