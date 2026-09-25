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


def wait_search(container: str, deadline_seconds: int = 420) -> dict:
    deadline = time.monotonic() + deadline_seconds
    attempted_restart = False
    while time.monotonic() < deadline:
        status = search_health(container)
        if (status is not None and status['number_of_nodes'] == 1 and
                status['pending_tasks'] == 0):
            return status
        if not attempted_restart and time.monotonic() > deadline - deadline_seconds / 2:
            docker('exec', container, 'supervisorctl', 'restart', 'elasticsearch',
                   timeout=60)
            attempted_restart = True
        time.sleep(10)
    raise TimeoutError('dedicated Magento search service did not become ready')


def prepare(container: str, http_port: int, control_port: int) -> dict:
    require(CONTAINER_NAME.fullmatch(container) is not None and
            http_port != control_port and 1024 <= http_port <= 65535 and
            1024 <= control_port <= 65535,
            'dedicated clone name and unprivileged ports required')
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
    proof = check_clone(container, http_port, control_port)
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
    health = wait_search(container)
    base = f'http://localhost:{http_port}/'
    for key in ('web/unsecure/base_url', 'web/secure/base_url'):
        docker('exec', container, 'php', '/var/www/magento2/bin/magento',
               'config:set', key, base, timeout=180)
    docker('exec', container, 'php', '/var/www/magento2/bin/magento',
           'cache:clean', 'config', timeout=180)
    observed = docker('exec', container, 'php', '/var/www/magento2/bin/magento',
                      'config:show', 'web/unsecure/base_url', timeout=60)
    require(observed == base, 'isolated Magento base URL readback changed')
    search = json.loads(docker('exec', container, 'curl', '-fsS',
                               '--max-time', '30',
                               'http://127.0.0.1:9200/magento2_product_1/_search?size=1',
                               timeout=45))
    require(search['hits']['total']['value'] == 181,
            'prepared image search catalog count changed')
    return {'schema': 'envloop-magento-original-clone-preparation-v1',
            'status': 'clone_prepared_no_task_seeded',
            'clone': proof, 'container': container, 'base_url': base,
            'search_health': health, 'search_document_count': 181,
            'official_final_tasks_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--http-port', type=int, required=True)
    parser.add_argument('--control-port', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new ignored evaluator output under work/ required')
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        receipt = prepare(args.container, args.http_port, args.control_port)
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
