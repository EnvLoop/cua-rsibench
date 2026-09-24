"""Local-only Magento task-157 smoke with the pinned WebArena-Verified evaluator.

This deterministic oracle smoke is not a model run or a 100-task qualification.
The reset scope is fresh authenticated browser state plus unchanged customer
business data; backend rollback after mutations is explicitly NOT qualified.
Public-demo credentials are loaded internally from the pinned upstream example.
"""
import argparse
import asyncio
import contextlib
import hashlib
import importlib.metadata
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

VERSION = 'magento-navigation-smoke-v1'
COMMIT = '6473f72db5dcefc97b5725b59e734504edc28a21'
CONTAINER = 'cua-v06-magento-smoke'
DOCKER_CONTEXT = 'colima-cua-scale'
IMAGE = 'sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13'
BASE = 'http://localhost:7780/admin'
TASK_ID = 157
ROOT = Path(__file__).resolve().parents[1]
SENSITIVE = re.compile(r'password|passwd|token|secret|session|form_key|authorization|cookie|^sid$', re.I)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    Path(path).chmod(0o600)


def local_url(value):
    u = urlsplit(value)
    require(u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1')
            and u.port == 7780 and not u.username and not u.password, 'only the disposable local Magento origin is allowed')
    return value


def permitted_request(url, method, *, setup=False):
    u = urlsplit(url)
    if u.scheme in ('data', 'blob', 'about'):
        return True
    return (u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1') and u.port == 7780
            and not u.username and not u.password
            and (setup or method in ('GET', 'HEAD', 'OPTIONS')))


def safe_url(value):
    if not value:
        return value
    u = urlsplit(value)
    path = re.sub(r'/key/[^/]+', '/key/REDACTED', u.path)
    query = [(k, 'REDACTED' if SENSITIVE.search(k) else v) for k, v in parse_qsl(u.query, keep_blank_values=True)]
    return urlunsplit((u.scheme, u.netloc.rsplit('@', 1)[-1], path, urlencode(query), ''))


def sanitize_har(raw):
    """Preserve observed URL/method/status; never invent or remove navigation."""
    allowed = {'accept', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-user', 'content-type'}
    entries = []
    for item in raw['log']['entries']:
        req, res = item['request'], item['response']
        entries.append({'startedDateTime': item.get('startedDateTime'),
            'request': {'url': safe_url(req['url']), 'method': req['method'],
                        'headers': [h for h in req.get('headers', []) if h['name'].lower() in allowed],
                        'queryString': [{'name': k, 'value': v} for k, v in parse_qsl(urlsplit(safe_url(req['url'])).query)],
                        'cookies': []},
            'response': {'status': res['status'], 'headers': [], 'cookies': [],
                         'redirectURL': safe_url(res.get('redirectURL', '')), 'content': {}}})
    return {'log': {'version': '1.2', 'creator': {'name': VERSION, 'version': '1'}, 'entries': entries}}


def verify_task(task):
    require(task['task_id'] == TASK_ID and task['revision'] == 2 and task['sites'] == ['shopping_admin'], 'unexpected pinned task identity')
    require(task['intent'] == 'View the details of all customers', 'task intent changed')
    require(task['eval'] == [
        {'evaluator': 'AgentResponseEvaluator', 'results_schema': {'type': 'null'},
         'expected': {'task_type': 'navigate', 'status': 'SUCCESS', 'retrieved_data': None}},
        {'evaluator': 'NetworkEventEvaluator', 'expected': {'url': '__SHOPPING_ADMIN__/customer/index/'}}],
        'published navigation evaluator contract changed')


def source_proof(source):
    source = Path(source).resolve()
    head = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
    require(head == COMMIT, 'upstream checkout differs from pinned commit')
    dirty = subprocess.run(['git', '-C', str(source), 'status', '--porcelain', '--', 'src', 'assets/dataset', 'examples/configs'],
                           check=True, capture_output=True, text=True).stdout
    require(not dirty.strip(), 'upstream evaluator/task/config checkout is modified')
    dataset = source / 'assets/dataset/webarena-verified.json'
    tasks = json.loads(dataset.read_text())
    task = next(row for row in tasks if row['task_id'] == TASK_ID)
    verify_task(task)
    import webarena_verified
    require(Path(webarena_verified.__file__).resolve().is_relative_to(source / 'src'), 'evaluator imported from another installation')
    files = {p.relative_to(source).as_posix(): sha(p.read_bytes()) for p in (source / 'src/webarena_verified').rglob('*.py')}
    return task, {'git_commit': head, 'dataset_sha256': sha(dataset.read_bytes()), 'task_sha256': digest(task),
                  'evaluator_source_sha256': digest(files), 'evaluator_source_file_count': len(files),
                  'versions': {k: importlib.metadata.version(k) for k in ['webarena-verified', 'playwright', 'pydantic']}}


def container_proof():
    command = ['docker', '--context', DOCKER_CONTEXT, 'inspect', CONTAINER]
    raw = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=30).stdout)[0]
    require(raw['Image'] == IMAGE and raw['State']['Running'], 'disposable container image/state differs')
    ports = raw['NetworkSettings']['Ports']
    require(ports['80/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '7780'}]
            and ports['8877/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '7781'}], 'container must expose only the expected local smoke ports')
    return {'name': CONTAINER, 'docker_context': DOCKER_CONTEXT, 'image_sha256': raw['Image'],
            'container_id_sha256': sha(raw['Id']), 'local_ports': [7780, 7781]}


DB_READONLY = '''<?php
$c=include '/var/www/magento2/app/etc/env.php';$d=$c['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);$db->exec('START TRANSACTION READ ONLY');
$names=['customer_entity','customer_address_entity','customer_grid_flat'];
foreach(['customer_entity','customer_address_entity'] as $base){foreach(['datetime','decimal','int','text','varchar'] as $kind){$names[]=$base.'_'.$kind;}}
$out=[];foreach($names as $table){$rows=$db->query('SELECT * FROM `'.$table.'`')->fetchAll(PDO::FETCH_ASSOC);$hashes=[];
foreach($rows as $row){ksort($row);$hashes[]=hash('sha256',json_encode($row));}sort($hashes);
$out[$table]=['rows'=>count($rows),'sha256'=>hash('sha256',implode("\\n",$hashes))];}
$db->rollBack();echo json_encode($out);
'''


def business_fingerprint():
    result = subprocess.run(['docker', '--context', DOCKER_CONTEXT, 'exec', '-i', CONTAINER, 'php'],
                            input=DB_READONLY, check=True, capture_output=True, text=True, timeout=60)
    rows = json.loads(result.stdout)
    require(len(rows) == 13 and rows['customer_entity']['rows'] > 0, 'customer business snapshot is incomplete')
    return {'tables': rows, 'sha256': digest(rows), 'readonly_transaction': True,
            'raw_customer_rows_exported': False, 'scope': '13 customer/address/EAV/grid tables; excludes authentication/session/UI bookkeeping'}


def evaluator(source):
    from webarena_verified.api import WebArenaVerified
    from webarena_verified.types.config import WebArenaVerifiedConfig
    logging.getLogger('webarena_verified').setLevel(logging.ERROR)
    config = WebArenaVerifiedConfig(test_data_file=Path(source) / 'assets/dataset/webarena-verified.json',
        environments={'shopping_admin': {'urls': [BASE, BASE.replace('localhost', '127.0.0.1')]}})
    return WebArenaVerified(config=config)


def evaluate(wa, trace):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = wa.evaluate_task(task_id=TASK_ID,
            agent_response={'task_type': 'navigate', 'status': 'SUCCESS', 'retrieved_data': None}, network_trace=trace)
    return {'task_id': result.task_id, 'status': str(result.status), 'score': result.score,
            'evaluators': [{'name': e.evaluator_name, 'status': str(e.status), 'score': e.score} for e in result.evaluators_results],
            'evaluator_checksum': result.webarena_verified_evaluator_checksum,
            'data_checksum': result.webarena_verified_data_checksum,
            'error_present': result.error_msg is not None}


async def browser_case(browser, source, destination, positive):
    destination.mkdir()
    def progress(stage, **details):
        with (destination / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps({'at': time.time(), 'stage': stage, **details}) + '\n')
    progress('fresh_native_login')
    credentials = json.loads((source / 'examples/configs/config.example.json').read_text())['environments']['__SHOPPING_ADMIN__']['credentials']
    setup = await browser.new_context()
    try:
        async def setup_guard(route):
            if permitted_request(route.request.url, route.request.method, setup=True):
                await route.continue_()
            else:
                await route.abort()
        await setup.route('**/*', setup_guard)
        require(not await setup.cookies(), 'fresh browser context unexpectedly has cookies')
        page = await setup.new_page()
        await page.goto(BASE, wait_until='domcontentloaded', timeout=90000)
        await page.get_by_label('Username', exact=True).fill(credentials['username'])
        await page.get_by_label('Password', exact=True).fill(credentials['password'])
        await page.get_by_role('button', name='Sign in', exact=True).click()
        await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=90000)
        await page.wait_for_load_state('networkidle', timeout=60000)
        state = await setup.storage_state()  # Memory only; never publish auth state.
    finally:
        await setup.close()
    with tempfile.TemporaryDirectory(prefix='.private-har-', dir=destination) as private:
        raw_path = Path(private) / 'network.har'
        context = await browser.new_context(storage_state=state, viewport={'width': 1440, 'height': 1000},
            record_har_path=str(raw_path), record_har_content='omit')
        blocked = []
        async def guard(route):
            request = route.request
            if not permitted_request(request.url, request.method):
                blocked.append({'method': request.method, 'url': safe_url(request.url)})
                await route.abort()
            else:
                await route.continue_()
        await context.route('**/*', guard)
        page = await context.new_page()
        page.set_default_timeout(30000)
        browser_error = None
        try:
            await page.goto(BASE, wait_until='domcontentloaded', timeout=90000)
            await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=90000)
            await page.wait_for_load_state('networkidle', timeout=60000)
            progress('dashboard_ready', url=safe_url(page.url))
            baseline = {'heading': await page.get_by_role('heading', name='Dashboard', exact=True).inner_text(),
                        'nav_text': await page.locator('nav').inner_text()}
            await page.screenshot(path=str(destination / 'baseline.png'), full_page=True,
                mask=[page.locator('.admin-user')])
            if positive:
                progress('click_customers_menu')
                await page.locator('#menu-magento-customer-customer > a').click()
                progress('click_all_customers')
                await page.locator('[data-ui-id="menu-magento-customer-customer-manage"] > a').click()
                heading = 'Customers'
            else:
                progress('click_sales_menu')
                await page.locator('#menu-magento-sales-sales > a').click()
                progress('click_orders')
                await page.locator('[data-ui-id="menu-magento-sales-sales-order"] > a').click()
                heading = 'Orders'
            progress('waiting_target_heading', expected_heading=heading, url=safe_url(page.url))
            await page.get_by_role('heading', name=heading, exact=True).wait_for(timeout=90000)
            progress('waiting_visible_grid')
            await page.screenshot(path=str(destination / 'target-loading.png'), full_page=True,
                mask=[page.locator('.admin-user')])
            await page.wait_for_load_state('networkidle', timeout=60000)
            records = page.locator('table.data-grid tbody tr:visible:has(td:nth-child(2))')
            await records.first.wait_for(state='visible', timeout=90000)
            final = {'heading': await page.get_by_role('heading', name=heading, exact=True).inner_text(),
                     'url': safe_url(page.url), 'visible_data_rows': await records.count(),
                     'grid_loaded': True}
            await page.screenshot(path=str(destination / 'final.png'), full_page=True,
                mask=[page.locator('.admin-user')])
            progress('target_visible', **final)
        except Exception as exc:
            browser_error = exc
            progress('browser_error', error_type=type(exc).__name__, url=safe_url(page.url))
            try:
                await page.screenshot(path=str(destination / 'failure.png'), full_page=True,
                    mask=[page.locator('.admin-user')], timeout=15000)
            except Exception:
                pass
        finally:
            await context.close()
        raw = json.loads(raw_path.read_text())
        sanitized = sanitize_har(raw)
        if browser_error is not None:
            write(destination / 'failure-network.har', sanitized)
            write(destination / 'failure.json', {'error_type': type(browser_error).__name__,
                'blocked_requests': blocked, 'raw_har_sha256': sha(raw_path.read_bytes()),
                'raw_har_retained': False, 'network_entries': len(sanitized['log']['entries'])})
            raise browser_error
        # The task itself remains unchanged; score equality checks redaction fidelity.
        wa = evaluator(source)
        raw_score = evaluate(wa, raw_path)
        clean_path = destination / 'network.har'
        write(clean_path, sanitized)
        clean_score = evaluate(wa, clean_path)
        require(raw_score == clean_score, 'trace redaction changed published evaluator outcome')
        require(credentials['password'] not in clean_path.read_text(), 'credential found in sanitized trace')
        record = {'case': destination.name, 'positive': positive, 'baseline': baseline, 'final_gui': final,
                  'reset': 'new empty browser context, native UI login, in-memory auth transfer, dashboard baseline',
                  'blocked_requests': blocked, 'network_entries': len(sanitized['log']['entries']),
                  'raw_har_sha256': sha(raw_path.read_bytes()), 'sanitized_har_sha256': sha(clean_path.read_bytes()),
                  'raw_har_retained': False, 'auth_state_retained': False,
                  'published_evaluator': clean_score, 'raw_and_sanitized_evaluator_equal': True,
                  'screenshots': {name: sha((destination / name).read_bytes()) for name in ['baseline.png', 'final.png']}}
        write(destination / 'receipt.json', record)
        return record


def validate_outcomes(cases, snapshots):
    require(len(cases) == 3 and [row['positive'] for row in cases] == [True, False, True], 'positive/negative/repeat sequence required')
    require([row['published_evaluator']['score'] for row in cases] == [1.0, 0.0, 1.0], 'published positive/negative discrimination failed')
    require([row['published_evaluator']['status'] for row in cases] == ['success', 'failure', 'success'], 'evaluator infrastructure error cannot be a valid negative')
    require(all(row['raw_and_sanitized_evaluator_equal'] for row in cases), 'raw/sanitized evidence mismatch')
    require(all(row.get('final_gui', {}).get('grid_loaded') is True
                and row['final_gui'].get('visible_data_rows', 0) > 1 for row in cases),
            'navigation-only or placeholder rows do not qualify a loaded business grid')
    require(cases[0]['baseline'] == cases[1]['baseline'] == cases[2]['baseline'], 'fresh-context baseline differs')
    require(len(snapshots) == 4 and len({row['sha256'] for row in snapshots}) == 1, 'read-only GUI changed customer business state')


async def run(source, out):
    from playwright.async_api import async_playwright
    source, out = Path(source).resolve(), Path(out).resolve()
    require(out.is_relative_to(ROOT / 'work/scale-v06'), 'receipts must remain in work/scale-v06')
    require(not out.exists(), 'preserve prior smoke evidence; choose a fresh output directory')
    out.mkdir(parents=True, mode=0o700)
    report = {'version': VERSION, 'task_id': TASK_ID, 'started_at': time.time(), 'complete': False,
              'tool_sha256': sha(Path(__file__).read_bytes()),
              'model_calls': 0, 'paid_provider_calls': 0, 'user_account_accessed': False,
              'qualification_scope': 'one read-only Magento navigation task and session-reset idempotence',
              'qualified_task_count': 0, 'hundred_task_ready': False, 'backend_mutation_reset_qualified': False}
    try:
        task, proof = source_proof(source)
        report.update(source=proof, container=container_proof(), task_intent=task['intent'])
        snapshots = [business_fingerprint()]
        write(out / 'business-before.json', snapshots[0])
        cases = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            report['browser_version'] = browser.version
            try:
                for name, positive in [('positive-1', True), ('wrong-orders', False), ('positive-2', True)]:
                    case = await browser_case(browser, source, out / name, positive)
                    cases.append(case)
                    snapshots.append(business_fingerprint())
                    write(out / ('business-after-' + name + '.json'), snapshots[-1])
                    print(json.dumps({'case': name, 'evaluator_score': case['published_evaluator']['score'],
                                      'network_entries': case['network_entries']}), flush=True)
            finally:
                await browser.close()
        validate_outcomes(cases, snapshots)
        report.update(complete=True, qualified_task_count=1, positive_scores=[1, 1], negative_score=0,
                      business_state_unchanged=True, fresh_context_baselines_equal=True,
                      cases=[{'path': row['case'], 'receipt_sha256': sha((out / row['case'] / 'receipt.json').read_bytes())} for row in cases],
                      limitation='Scripted oracle only, not a model score. No arbitrary database rollback, mutation tasks, or 100-task population is qualified.')
    except Exception as exc:
        report.update(error_type=type(exc).__name__, blocker='Local GUI/source/evaluator qualification did not complete; prior partial evidence preserved.')
        raise
    finally:
        report['finished_at'] = time.time()
        write(out / 'result.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'work/scale-v06/sources/webarena-verified')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.source, args.out))
        print(json.dumps({key: result[key] for key in ['complete', 'qualified_task_count', 'hundred_task_ready', 'model_calls']}))
    except Exception as exc:
        print(json.dumps({'complete': False, 'error_type': type(exc).__name__, 'provider_calls': 0}), file=sys.stderr)
        raise SystemExit(1)
