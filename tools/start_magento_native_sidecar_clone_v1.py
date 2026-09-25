"""Prepare a fresh Magento clone with pinned native ARM Elasticsearch 7.10.2.

This isolates the x86 Magento application image from its slow emulated Java
service. The two no-mount containers and their shared network are trusted
environment setup only; no task, actor, model, or score is run here.
"""

from __future__ import annotations

import argparse
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
from tools.start_magento_original_clone_v1 import docker


APP = 'envloop-magento-original-control'
HTTP_PORT = 7794
CONTROL_PORT = 7795
READ_CONFIG_PHP = r'''$c=include '/var/www/magento2/app/etc/env.php';
$d=$c['db']['connection']['default'];
$p=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$p->exec('START TRANSACTION READ ONLY');
$rows=$p->query("SELECT path,value FROM core_config_data WHERE scope='default' AND scope_id=0 AND path IN ('catalog/search/engine','catalog/search/elasticsearch7_server_hostname','catalog/search/elasticsearch7_server_port','catalog/search/elasticsearch7_index_prefix','web/unsecure/base_url','web/secure/base_url')")->fetchAll(PDO::FETCH_ASSOC);
$quotes=(int)$p->query("SELECT COUNT(*) FROM cms_page WHERE identifier LIKE 'envloop-quote-%'")->fetchColumn();
$p->rollBack();echo json_encode(['rows'=>$rows,'quote_pages'=>$quotes],JSON_THROW_ON_ERROR);'''


def require_absent(name: str) -> None:
    result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                             'inspect', name], capture_output=True,
                            text=True, timeout=15)
    require(result.returncode != 0, f'{name} already exists; inspect instead of replacing')


def sidecar_health() -> dict | None:
    try:
        raw = docker('exec', NATIVE_SEARCH_HOST, 'curl', '-fsS',
                     '--max-time', '5', 'http://127.0.0.1:9200/_cluster/health',
                     timeout=10)
        state = json.loads(raw)
        if (state.get('status') in ('yellow', 'green') and
                state.get('number_of_nodes') == 1 and
                state.get('number_of_pending_tasks') == 0 and
                not state.get('timed_out')):
            return {'status': state['status'], 'nodes': 1, 'pending_tasks': 0}
    except (ValueError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def wait_ready(check, label: str, seconds: int = 180):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(3)
    raise TimeoutError(f'{label} did not become ready')


def stop_embedded_search() -> None:
    # Supervisor starts the embedded x86 service automatically. Stop only this
    # disposable app container; the native sidecar remains independent.
    for _ in range(20):
        try:
            docker('exec', APP, 'supervisorctl', 'stop', 'elasticsearch', timeout=30)
            break
        except ValueError:
            time.sleep(1)
    else:
        raise ValueError('embedded search could not be stopped')
    process_list = docker('exec', APP, 'ps', '-eo', 'pid,args', timeout=15)
    stale_markers = ('org.elasticsearch.tools.java_version_checker.JavaVersionChecker',
                     'org.elasticsearch.tools.launchers.JvmOptionsParser')
    stale = [line.strip().split(None, 1)[0] for line in process_list.splitlines()
             if any(marker in line for marker in stale_markers)]
    if stale:
        require(all(pid.isdigit() for pid in stale), 'embedded helper PID changed')
        docker('exec', APP, 'kill', '-KILL', *stale, timeout=15)


def http_ready() -> bool:
    try:
        return docker('exec', APP, 'curl', '-sS', '-o', '/dev/null',
                      '-w', '%{http_code}', '--max-time', '5',
                      'http://127.0.0.1/admin', timeout=10) in ('200', '301', '302')
    except (ValueError, subprocess.TimeoutExpired):
        return False


def audit_existing(expected_search_sha256: str, mode: str) -> dict:
    clone = check_clone(APP, HTTP_PORT, CONTROL_PORT)
    check_native_search_sidecar(APP)
    health = sidecar_health()
    require(health is not None, 'native search sidecar health changed')
    config = json.loads(docker('exec', APP, 'php', '-r', READ_CONFIG_PHP,
                               timeout=30))
    expected = {
        'catalog/search/engine': 'elasticsearch7',
        'catalog/search/elasticsearch7_server_hostname': NATIVE_SEARCH_HOST,
        'catalog/search/elasticsearch7_server_port': '9200',
        'catalog/search/elasticsearch7_index_prefix': 'magento2',
        'web/unsecure/base_url': f'http://localhost:{HTTP_PORT}/',
        'web/secure/base_url': f'http://localhost:{HTTP_PORT}/',
    }
    require(config['quote_pages'] == 0 and
            {row['path']: row['value'] for row in config['rows']} == expected,
            'native-sidecar app config or unseeded source changed')
    search = json.loads(docker('exec', APP, 'curl', '-fsS', '--max-time', '30',
                               f'http://{NATIVE_SEARCH_HOST}:9200/magento2_product_1/_search?size=1000',
                               timeout=45))
    hits = search['hits']['hits']
    docs = {row['_id']: row['_source'] for row in hits}
    require(len(hits) == search['hits']['total']['value'] == 181 and
            canonical_sha(docs) == expected_search_sha256,
            'native-sidecar catalog differs from frozen source index')
    sidecar = json.loads(docker('inspect', NATIVE_SEARCH_HOST))[0]
    return {'schema': 'envloop-magento-native-sidecar-clone-preparation-v1',
            'status': 'clone_and_sidecar_prepared_no_task_seeded',
            'preparation_mode': mode,
            'application_clone': clone,
            'search_sidecar_image_sha256': NATIVE_SEARCH_IMAGE,
            'search_sidecar_id_sha256': hashlib.sha256(sidecar['Id'].encode()).hexdigest(),
            'search_network': NATIVE_SEARCH_NETWORK,
            'search_health': health, 'search_document_count': 181,
            'search_documents_sha256': canonical_sha(docs),
            'official_final_tasks_admitted': 0}


def prepare(expected_search_sha256: str,
            *, adopt_existing: bool = False) -> dict:
    require(len(expected_search_sha256) == 64 and
            all(char in '0123456789abcdef' for char in expected_search_sha256),
            'frozen source search digest required')
    if adopt_existing:
        return audit_existing(expected_search_sha256,
                              'read_only_adoption_after_reindex_retry')
    require_absent(APP)
    require_absent(NATIVE_SEARCH_HOST)
    images = {raw['Id']: raw for raw in json.loads(
        docker('image', 'inspect', IMAGE, NATIVE_SEARCH_IMAGE))}
    require(IMAGE in images and NATIVE_SEARCH_IMAGE in images and
            images[NATIVE_SEARCH_IMAGE]['Architecture'] == 'arm64' and
            images[IMAGE]['Architecture'] == 'amd64',
            'pinned app/sidecar image architecture changed')
    networks = json.loads(docker('network', 'inspect', NATIVE_SEARCH_NETWORK))
    require(len(networks) == 1 and networks[0]['Driver'] == 'bridge',
            'dedicated search network missing')
    docker('run', '-d', '--name', NATIVE_SEARCH_HOST,
           '--network', NATIVE_SEARCH_NETWORK, '--memory', '1536m',
           '-e', 'discovery.type=single-node',
           '-e', 'ES_JAVA_OPTS=-Xms512m -Xmx512m',
           NATIVE_SEARCH_IMAGE, timeout=120)
    wait_ready(sidecar_health, 'native search')
    docker('run', '-d', '--name', APP, '--network', NATIVE_SEARCH_NETWORK,
           '-p', f'127.0.0.1:{HTTP_PORT}:80',
           '-p', f'127.0.0.1:{CONTROL_PORT}:8877',
           IMAGE, timeout=120)
    check_clone(APP, HTTP_PORT, CONTROL_PORT)
    stop_embedded_search()
    wait_ready(http_ready, 'Magento HTTP')
    settings = (
        ('catalog/search/engine', 'elasticsearch7'),
        ('catalog/search/elasticsearch7_server_hostname', NATIVE_SEARCH_HOST),
        ('catalog/search/elasticsearch7_server_port', '9200'),
        ('catalog/search/elasticsearch7_index_prefix', 'magento2'),
        ('web/unsecure/base_url', f'http://localhost:{HTTP_PORT}/'),
        ('web/secure/base_url', f'http://localhost:{HTTP_PORT}/'),
    )
    for key, value in settings:
        docker('exec', APP, 'php', '/var/www/magento2/bin/magento',
               'config:set', key, value, timeout=180)
    docker('exec', APP, 'php', '/var/www/magento2/bin/magento',
           'cache:clean', 'config', timeout=180)
    output = docker('exec', APP, 'php', '/var/www/magento2/bin/magento',
                    'indexer:reindex', 'catalogsearch_fulltext', timeout=180)
    require('Catalog Search index has been rebuilt successfully' in output,
            'native-sidecar reindex did not complete')
    return audit_existing(expected_search_sha256, 'new_clone')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-search-sha256', required=True)
    parser.add_argument('--adopt-existing', action='store_true',
                        help='read-only audit after a bounded reindex failure')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new private work/ receipt required')
    receipt = prepare(args.expected_search_sha256,
                      adopt_existing=args.adopt_existing)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': receipt['status'],
                      'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                      'search_document_count': 181,
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
