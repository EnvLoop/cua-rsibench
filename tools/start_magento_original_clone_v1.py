"""Start and prepare a fresh, mount-free original-task Magento clone.

This only prepares a disposable local application. It does not install a task,
run an agent, score a task, or admit an official final identity. An interrupted
clone is left for inspection rather than silently replaced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import CONTEXT, IMAGE, CONTAINER_NAME, check_clone


READ_PREP_PHP = r'''$c=include '/var/www/magento2/app/etc/env.php';
$d=$c['db']['connection']['default'];
$p=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$p->exec('START TRANSACTION READ ONLY');
$rows=$p->query("SELECT path,value FROM core_config_data WHERE scope='default' AND scope_id=0 AND path IN ('web/unsecure/base_url','web/secure/base_url')")->fetchAll(PDO::FETCH_ASSOC);
$quotes=(int)$p->query("SELECT COUNT(*) FROM cms_page WHERE identifier LIKE 'envloop-quote-%'")->fetchColumn();
$p->rollBack();echo json_encode(['urls'=>$rows,'quote_pages'=>$quotes],JSON_THROW_ON_ERROR);'''


def docker(*args: str, timeout: int = 120) -> str:
    result = subprocess.run(['docker', '--context', CONTEXT, *args],
                            capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, 'disposable Docker preparation failed')
    return result.stdout.strip()


def search_health(container: str) -> dict | None:
    try:
        result = json.loads(docker('exec', container, 'curl', '-fsS',
                                   '--max-time', '5',
                                   'http://127.0.0.1:9200/_cluster/health',
                                   timeout=10))
        if result.get('status') not in ('yellow', 'green') or result.get('timed_out'):
            return None
        return {'status': result['status'],
                'number_of_nodes': result.get('number_of_nodes'),
                'pending_tasks': result.get('number_of_pending_tasks')}
    except (ValueError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def restart_stuck_search(container: str) -> None:
    """Clear orphaned Java startup helpers in this disposable clone only."""
    docker('exec', container, 'supervisorctl', 'stop', 'elasticsearch', timeout=60)
    process_list = docker('exec', container, 'ps', '-eo', 'pid,args', timeout=15)
    helper_classes = ('org.elasticsearch.tools.java_version_checker.JavaVersionChecker',
                      'org.elasticsearch.tools.launchers.JvmOptionsParser')
    stale = [line.strip().split(None, 1)[0] for line in process_list.splitlines()
             if any(name in line for name in helper_classes)]
    if stale:
        require(all(pid.isdigit() for pid in stale),
                'non-numeric isolated search helper PID')
        docker('exec', container, 'kill', '-KILL', *stale, timeout=15)
    docker('exec', container, 'supervisorctl', 'start', 'elasticsearch', timeout=60)


def wait_search(container: str, deadline_seconds: int = 420) -> dict:
    deadline = time.monotonic() + deadline_seconds
    attempted_restart = False
    while time.monotonic() < deadline:
        status = search_health(container)
        if (status is not None and status['number_of_nodes'] == 1 and
                status['pending_tasks'] == 0):
            return status
        if not attempted_restart and time.monotonic() > deadline - deadline_seconds / 2:
            restart_stuck_search(container)
            attempted_restart = True
        time.sleep(10)
    raise TimeoutError('dedicated Magento search service did not become ready')


def audit_running(container: str, http_port: int,
                  control_port: int, mode: str) -> dict:
    proof = check_clone(container, http_port, control_port)
    health = search_health(container)
    require(health is not None and health['number_of_nodes'] == 1 and
            health['pending_tasks'] == 0,
            'prepared clone search health changed')
    base = f'http://localhost:{http_port}/'
    config = json.loads(docker('exec', container, 'php', '-r', READ_PREP_PHP,
                               timeout=30))
    require(config['quote_pages'] == 0 and
            {row['path']: row['value'] for row in config['urls']} == {
                'web/unsecure/base_url': base, 'web/secure/base_url': base},
            'isolated Magento base URL or unseeded CMS readback changed')
    search = json.loads(docker('exec', container, 'curl', '-fsS',
                               '--max-time', '30',
                               'http://127.0.0.1:9200/magento2_product_1/_search?size=1',
                               timeout=45))
    require(search['hits']['total']['value'] == 181,
            'prepared image search catalog count changed')
    return {'schema': 'envloop-magento-original-clone-preparation-v1',
            'status': 'clone_prepared_no_task_seeded',
            'preparation_mode': mode,
            'clone': proof, 'container': container, 'base_url': base,
            'search_health': health, 'search_document_count': 181,
            'official_final_tasks_admitted': 0}


def configure_base_url(container: str, http_port: int) -> None:
    base = f'http://localhost:{http_port}/'
    for key in ('web/unsecure/base_url', 'web/secure/base_url'):
        docker('exec', container, 'php', '/var/www/magento2/bin/magento',
               'config:set', key, base, timeout=180)
    docker('exec', container, 'php', '/var/www/magento2/bin/magento',
           'cache:clean', 'config', timeout=180)


def prepare(container: str, http_port: int, control_port: int,
            *, adopt_existing: bool = False,
            resume_existing: bool = False) -> dict:
    require(CONTAINER_NAME.fullmatch(container) is not None and
            http_port != control_port and 1024 <= http_port <= 65535 and
            1024 <= control_port <= 65535,
            'dedicated clone name and unprivileged ports required')
    require(not (adopt_existing and resume_existing),
            'choose at most one existing-clone recovery mode')
    if adopt_existing:
        return audit_running(container, http_port, control_port,
                             'read_only_adoption_after_interrupted_preparation')
    if resume_existing:
        check_clone(container, http_port, control_port)
        config = json.loads(docker('exec', container, 'php', '-r', READ_PREP_PHP,
                                   timeout=30))
        require(config['quote_pages'] == 0,
                'cannot resume preparation after a task was seeded')
        health = search_health(container)
        require(health is not None and health['number_of_nodes'] == 1 and
                health['pending_tasks'] == 0,
                'cannot resume preparation before search is healthy')
        configure_base_url(container, http_port)
        return audit_running(container, http_port, control_port,
                             'resumed_after_search_startup_timeout')
    try:
        docker('inspect', container, timeout=15)
    except ValueError:
        pass
    else:
        raise ValueError('clone name already exists; inspect it instead of replacing it')
    image_info = json.loads(docker('image', 'inspect', IMAGE))[0]
    require(image_info['Id'] == IMAGE, 'pinned Magento image ID changed')
    docker('run', '-d', '--name', container,
           '-p', f'127.0.0.1:{http_port}:80',
           '-p', f'127.0.0.1:{control_port}:8877', IMAGE, timeout=120)
    check_clone(container, http_port, control_port)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            response = docker('exec', container, 'curl', '-sS', '-o', '/dev/null',
                              '-w', '%{http_code}', '--max-time', '5',
                              'http://127.0.0.1/admin', timeout=10)
            if response in ('200', '301', '302'):
                break
        except (ValueError, subprocess.TimeoutExpired):
            pass
        time.sleep(5)
    else:
        raise TimeoutError('dedicated Magento HTTP service did not become ready')
    wait_search(container)
    configure_base_url(container, http_port)
    return audit_running(container, http_port, control_port, 'new_clone')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--http-port', type=int, required=True)
    parser.add_argument('--control-port', type=int, required=True)
    parser.add_argument('--adopt-existing', action='store_true',
                        help='read-only audit after an interrupted preparation')
    parser.add_argument('--resume-existing', action='store_true',
                        help='configure an unseeded clone after slow search startup')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new ignored evaluator output under work/ required')
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        receipt = prepare(args.container, args.http_port, args.control_port,
                          adopt_existing=args.adopt_existing,
                          resume_existing=args.resume_existing)
    except Exception as error:
        print(json.dumps({'status': 'clone_preparation_failed',
                          'error_type': type(error).__name__,
                          'container': args.container}), file=sys.stderr)
        raise
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    with out.open('xb') as stream:
        stream.write(raw)
    out.chmod(0o600)
    print(json.dumps({'status': receipt['status'],
                      'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                      'search_document_count': 181,
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
