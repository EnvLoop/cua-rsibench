"""Qualify one published Magento-admin order-address mutation in an isolated clone.

This is a scripted GUI oracle, not a model score. The official task/evaluator
are imported unchanged from the pinned WebArena-Verified checkout. Database
readback and transactional rollback are separate from that network evaluator.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
VERSION = 'magento-order-address-v1'
COMMIT = '6473f72db5dcefc97b5725b59e734504edc28a21'
DATA_SHA = 'd65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30'
TASK_ID = 538
CONTEXT = 'colima-cua-scale'
CONTAINER = 'cua-v06-magento-mutation'
IMAGE = 'sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13'
BASE = 'http://localhost:7790/admin'
TARGET = {598: 299, 600: 300}
ADDRESS = {'street[0]': '456 Oak Avenue', 'street[1]': 'Apartment 5B',
           'country_id': 'US', 'region': 'New York', 'region_id': '43',
           'city': 'New York', 'postcode': '10001'}
ADDRESS_COLUMNS = {'street', 'country_id', 'region', 'region_id', 'city', 'postcode'}
TABLES = ('sales_order_address', 'sales_order', 'sales_order_grid',
          'sales_order_status_history', 'customer_address_entity')
SENSITIVE = re.compile(r'password|passwd|token|secret|session|form_key|authorization|cookie|^sid$', re.I)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(value):
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')))


def write_new(path, value):
    path = Path(path)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    path.chmod(0o600)


def safe_url(value):
    if not value:
        return value
    u = urlsplit(value)
    path = re.sub(r'/key/[^/]+', '/key/REDACTED', u.path)
    query = [(k, 'REDACTED' if SENSITIVE.search(k) else v)
             for k, v in parse_qsl(u.query, keep_blank_values=True)]
    return urlunsplit((u.scheme, u.netloc.rsplit('@', 1)[-1], path, urlencode(query), ''))


def permitted_request(url):
    u = urlsplit(url)
    return (u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1')
            and u.port == 7790 and not u.username and not u.password) or u.scheme in ('data', 'blob', 'about')


def sanitize_har(raw):
    """Retain real URL/method/status and only task-relevant form fields."""
    entries = []
    for item in raw['log']['entries']:
        req, res = item['request'], item['response']
        clean_req = {'url': safe_url(req['url']), 'method': req['method'],
                     'headers': [h for h in req.get('headers', [])
                                 if h['name'].lower() in ('content-type', 'accept')],
                     'queryString': [{'name': k, 'value': v}
                                     for k, v in parse_qsl(urlsplit(safe_url(req['url'])).query)],
                     'cookies': []}
        post = req.get('postData') or {}
        if '/sales/order/addressSave/address_id/' in req['url'] and \
                'application/x-www-form-urlencoded' in post.get('mimeType', ''):
            values = dict(parse_qsl(post.get('text', ''), keep_blank_values=True))
            clean_req['postData'] = {'mimeType': 'application/x-www-form-urlencoded',
                                     'text': urlencode([(k, values[k]) for k in ADDRESS if k in values])}
        entries.append({'startedDateTime': item.get('startedDateTime'),
                        'request': clean_req,
                        'response': {'status': res['status'], 'headers': [], 'cookies': [],
                                     'redirectURL': safe_url(res.get('redirectURL', '')), 'content': {}}})
    return {'log': {'version': '1.2', 'creator': {'name': VERSION, 'version': '1'}, 'entries': entries}}


def source_proof(source):
    source = Path(source).resolve()
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                            check=True, capture_output=True, text=True).stdout.strip()
    require(commit == COMMIT, 'pinned WebArena-Verified commit changed')
    dirty = subprocess.run(['git', '-C', str(source), 'status', '--porcelain', '--',
                            'src', 'assets/dataset', 'examples/configs'],
                           check=True, capture_output=True, text=True).stdout
    require(not dirty.strip(), 'official evaluator/task/config checkout is modified')
    dataset = source / 'assets/dataset/webarena-verified.json'
    require(sha(dataset.read_bytes()) == DATA_SHA, 'pinned task dataset changed')
    task = next(row for row in json.loads(dataset.read_text()) if row['task_id'] == TASK_ID)
    require(task['sites'] == ['shopping_admin'] and task['revision'] == 2
            and task['intent_template_id'] == 240, 'task identity changed')
    require(task['intent'] == 'Modify the address of order #299 to 456 Oak Avenue, Apartment 5B, New York, NY, 10001',
            'task intent changed')
    require(task['eval'] == [
        {'evaluator': 'AgentResponseEvaluator', 'results_schema': {'type': 'null'},
         'expected': {'task_type': 'mutate', 'status': 'SUCCESS', 'retrieved_data': None}},
        {'evaluator': 'NetworkEventEvaluator', 'ignored_post_data_params_patterns': ['^form_key$'],
         'expected': {'url': '__SHOPPING_ADMIN__/sales/order/addressSave/address_id/598/',
                      'http_method': 'POST', 'post_data': ADDRESS, 'response_status': 302}}],
        'official task evaluator contract changed')
    import webarena_verified
    require(Path(webarena_verified.__file__).resolve().is_relative_to(source / 'src'),
            'evaluator imported from a different installation')
    files = {p.relative_to(source).as_posix(): sha(p.read_bytes())
             for p in (source / 'src/webarena_verified').rglob('*.py')}
    return task, {'git_commit': commit, 'dataset_sha256': DATA_SHA,
                  'task_sha256': digest(task), 'evaluator_source_sha256': digest(files),
                  'evaluator_source_file_count': len(files),
                  'versions': {name: importlib.metadata.version(name)
                               for name in ('webarena-verified', 'playwright', 'pydantic')}}


def container_proof():
    result = subprocess.run(['docker', '--context', CONTEXT, 'inspect', CONTAINER],
                            check=True, capture_output=True, text=True, timeout=30)
    c = json.loads(result.stdout)[0]
    require(c['Image'] == IMAGE and c['State']['Running'], 'isolated container image/state changed')
    ports = c['NetworkSettings']['Ports']
    require(ports['80/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '7790'}]
            and ports['8877/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '7791'}]
            and not c['Mounts'], 'isolated clone port/mount contract changed')
    return {'name': CONTAINER, 'docker_context': CONTEXT, 'image_sha256': IMAGE,
            'container_id_sha256': sha(c['Id']), 'local_ports': [7790, 7791], 'mounts': 0}


DB_READ = r'''<?php
$cfg=include '/var/www/magento2/app/etc/env.php';$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);$db->exec('START TRANSACTION READ ONLY');
$tables=['sales_order_address','sales_order','sales_order_grid','sales_order_status_history','customer_address_entity'];
$out=['tables'=>[],'rows'=>[],'grid_rows'=>[]];
foreach($tables as $table){$rows=$db->query('SELECT * FROM `'.$table.'`')->fetchAll(PDO::FETCH_ASSOC);$hashes=[];
 foreach($rows as $row){ksort($row);$hashes[]=hash('sha256',json_encode($row,JSON_UNESCAPED_SLASHES));}sort($hashes);
 $out['tables'][$table]=['rows'=>count($rows),'sha256'=>hash('sha256',implode("\n",$hashes))];}
foreach([598,600] as $id){$s=$db->prepare('SELECT * FROM sales_order_address WHERE entity_id=?');$s->execute([$id]);
 $out['rows'][(string)$id]=$s->fetch(PDO::FETCH_ASSOC);}
foreach([299,300] as $id){$s=$db->prepare('SELECT * FROM sales_order_grid WHERE entity_id=?');$s->execute([$id]);
 $out['grid_rows'][(string)$id]=$s->fetch(PDO::FETCH_ASSOC);}
$db->rollBack();echo json_encode($out,JSON_UNESCAPED_SLASHES);
'''


def php_exec(code):
    return subprocess.run(['docker', '--context', CONTEXT, 'exec', '-i', CONTAINER, 'php'],
                          input=code, text=True, check=True, capture_output=True, timeout=90).stdout


def read_db():
    data = json.loads(php_exec(DB_READ))
    require(set(data['tables']) == set(TABLES) and set(data['rows']) == {'598', '600'}
            and set(data['grid_rows']) == {'299', '300'},
            'database snapshot scope incomplete')
    require(all(data['rows'][str(key)]['parent_id'] == order for key, order in TARGET.items()),
            'order/address binding changed')
    return data


def public_db(snapshot):
    return {'tables': snapshot['tables'],
            'selected_rows': {key: {'entity_id': value['entity_id'], 'parent_id': value['parent_id'],
                                    'address_type': value['address_type'],
                                    'street': value['street'], 'city': value['city'],
                                    'region': value['region'], 'region_id': value['region_id'],
                                    'postcode': value['postcode'], 'country_id': value['country_id'],
                                    'full_row_sha256': digest(value)}
                              for key, value in snapshot['rows'].items()},
            'selected_order_grid': {key: {'billing_address': value['billing_address'],
                                          'full_row_sha256': digest(value)}
                                    for key, value in snapshot['grid_rows'].items()},
            'read_only_transaction': True}


def restore_rows(original):
    """Restore only the two isolated clone address rows inside one SQL transaction."""
    payload = base64.b64encode(json.dumps({'rows': original['rows'],
                                           'grid_rows': original['grid_rows']}).encode()).decode()
    script = r'''<?php
$cfg=include '/var/www/magento2/app/etc/env.php';$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$snapshot=json_decode(base64_decode('PAYLOAD'),true,512,JSON_THROW_ON_ERROR);
$rows=$snapshot['rows'];$grid=$snapshot['grid_rows'];
if(array_keys($rows)!==[598,600] && array_keys($rows)!==['598','600']){throw new Exception('rollback row IDs changed');}
if(array_keys($grid)!==[299,300] && array_keys($grid)!==['299','300']){throw new Exception('rollback grid IDs changed');}
$db->beginTransaction();
try{foreach($rows as $id=>$row){if((int)$id!==(int)$row['entity_id'])throw new Exception('rollback key mismatch');
 $fields=array_keys($row);$fields=array_values(array_filter($fields,fn($v)=>$v!=='entity_id'));
 $sql='UPDATE sales_order_address SET '.implode(',',array_map(fn($v)=>'`'.$v.'`=?',$fields)).' WHERE entity_id=?';
 $stmt=$db->prepare($sql);$values=array_map(fn($v)=>$row[$v],$fields);$values[]=$id;$stmt->execute($values);}
 foreach($grid as $id=>$row){if((int)$id!==(int)$row['entity_id'])throw new Exception('rollback grid key mismatch');
 $fields=array_keys($row);$fields=array_values(array_filter($fields,fn($v)=>$v!=='entity_id'));
 $sql='UPDATE sales_order_grid SET '.implode(',',array_map(fn($v)=>'`'.$v.'`=?',$fields)).' WHERE entity_id=?';
 $stmt=$db->prepare($sql);$values=array_map(fn($v)=>$row[$v],$fields);$values[]=$id;$stmt->execute($values);}
 $db->commit();echo 'restored';}catch(Throwable $e){$db->rollBack();throw $e;}
'''.replace('PAYLOAD', payload)
    require(php_exec(script).strip() == 'restored', 'isolated row restore failed')


def validate_change(before, after, changed_id):
    other_id = '600' if changed_id == '598' else '598'
    require(after['rows'][other_id] == before['rows'][other_id], 'unrelated order address changed')
    old, new = before['rows'][changed_id], after['rows'][changed_id]
    changed = {key for key in old if old[key] != new[key]}
    require(changed == {'street', 'region', 'region_id', 'city', 'postcode'},
            f'unexpected address fields changed: {sorted(changed)}')
    require(new['street'] == '456 Oak Avenue\nApartment 5B' and new['region'] == 'New York'
            and str(new['region_id']) == '43' and new['city'] == 'New York'
            and new['postcode'] == '10001' and new['country_id'] == 'US',
            'persisted address does not match task values')
    require(after['tables']['sales_order_address']['sha256'] != before['tables']['sales_order_address']['sha256'],
            'address table hash did not change')
    grid_id = str(TARGET[int(changed_id)])
    other_grid_id = '300' if grid_id == '299' else '299'
    require(after['grid_rows'][other_grid_id] == before['grid_rows'][other_grid_id],
            'unrelated order grid changed')
    changed_grid = {key for key in before['grid_rows'][grid_id]
                    if before['grid_rows'][grid_id][key] != after['grid_rows'][grid_id][key]}
    require(changed_grid == {'billing_address'} and
            '456 Oak Avenue' in after['grid_rows'][grid_id]['billing_address'],
            'order grid address did not track the target save')
    require(after['tables']['sales_order_grid']['sha256'] != before['tables']['sales_order_grid']['sha256'],
            'order grid hash did not change')
    require(all(after['tables'][table] == before['tables'][table] for table in TABLES
                if table not in ('sales_order_address', 'sales_order_grid')),
            'another monitored business table changed')
    return sorted(changed)


def validate_reset(before, after):
    require(after['tables'] == before['tables'] and after['rows'] == before['rows']
            and after['grid_rows'] == before['grid_rows'],
            'transactional row restore did not recover the baseline hashes')


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
            agent_response={'task_type': 'mutate', 'status': 'SUCCESS', 'retrieved_data': None},
            network_trace=trace)
    return {'task_id': result.task_id, 'status': str(result.status), 'score': result.score,
            'evaluators': [{'name': e.evaluator_name, 'status': str(e.status), 'score': e.score}
                           for e in result.evaluators_results],
            'evaluator_checksum': result.webarena_verified_evaluator_checksum,
            'data_checksum': result.webarena_verified_data_checksum,
            'error_present': result.error_msg is not None}


async def gui_case(browser, source, destination, order_id, address_id):
    destination.mkdir(mode=0o700)
    def progress(stage, **details):
        with (destination / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps({'at': time.time(), 'stage': stage, **details}) + '\n')
    with tempfile.TemporaryDirectory(prefix='.private-har-', dir=destination) as private:
        raw_path = Path(private) / 'network.har'
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000},
            record_har_path=str(raw_path), record_har_content='embed')
        blocked = 0
        async def guard(route):
            nonlocal blocked
            if permitted_request(route.request.url):
                await route.continue_()
            else:
                blocked += 1
                await route.abort()
        await context.route('**/*', guard)
        page = await context.new_page()
        page.set_default_timeout(45000)
        credentials = json.loads((Path(source) / 'examples/configs/config.example.json').read_text())['environments']['__SHOPPING_ADMIN__']['credentials']
        try:
            require(not await context.cookies(), 'browser context is not fresh')
            progress('native_login')
            await page.goto(BASE, wait_until='domcontentloaded', timeout=120000)
            await page.get_by_label('Username', exact=True).fill(credentials['username'])
            await page.get_by_label('Password', exact=True).fill(credentials['password'])
            await page.get_by_role('button', name='Sign in', exact=True).click()
            await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=120000)
            progress('open_orders')
            menu = page.locator('[data-ui-id="menu-magento-sales-sales-order"] > a')
            for _ in range(3):
                if await menu.is_visible():
                    break
                await page.locator('#menu-magento-sales-sales > a').click()
                await page.wait_for_timeout(250)
            await menu.click()
            await page.get_by_role('heading', name='Orders', exact=True).wait_for(timeout=120000)
            row = page.locator('table.data-grid tbody tr').filter(has_text=f'{order_id:09d}').first
            await row.wait_for(state='visible', timeout=120000)
            await row.get_by_text('View', exact=True).click()
            billing_title = page.locator('.admin__page-section-item-title:visible').filter(has_text='Billing Address').first
            await billing_title.wait_for(timeout=120000)
            require(f'#{order_id:09d}' in await page.locator('body').inner_text(), 'wrong order page opened')
            await page.screenshot(path=str(destination / 'order-before.png'), full_page=True,
                                  mask=[page.locator('.admin-user')])
            edit = billing_title.get_by_role('link', name='Edit')
            require(urlsplit(await edit.get_attribute('href')).path.endswith(f'/address_id/{address_id}/'),
                    'billing address link points at the wrong object')
            await edit.click()
            await page.wait_for_load_state('networkidle', timeout=60000)
            await page.locator('#street0').fill(ADDRESS['street[0]'])
            await page.locator('#street1').fill(ADDRESS['street[1]'])
            await page.locator('#city').fill(ADDRESS['city'])
            await page.locator('#postcode').fill(ADDRESS['postcode'])
            await page.locator('#region_id').select_option(label='New York')
            await page.wait_for_function("document.querySelector('#region').value === 'New York'", timeout=20000)
            form = await page.locator('form#edit_form').evaluate(
                '(e)=>Object.fromEntries([...new FormData(e).entries()].filter(([k])=>'
                '["street[0]","street[1]","country_id","region","region_id","city","postcode"].includes(k)))')
            require({k: v for k, v in form.items() if k != 'region'} ==
                    {k: v for k, v in ADDRESS.items() if k != 'region'},
                    f'visible form submission differs from task fields: {form}')
            progress('form_ready', region_post_value=form.get('region'))
            await page.screenshot(path=str(destination / 'form-before-save.png'), full_page=True,
                                  mask=[page.locator('.admin-user')])
            progress('save_address', order_id=order_id, address_id=address_id)
            async with page.expect_response(lambda r: '/sales/order/addressSave/address_id/' in r.url
                                            and r.request.method == 'POST', timeout=120000) as response_info:
                await page.get_by_role('button', name='Save Order Address', exact=True).click()
            response = await response_info.value
            require(response.status == 302, 'native address save did not redirect')
            await page.locator('.admin__page-section-item-title:visible').filter(has_text='Billing Address').first.wait_for(timeout=120000)
            await page.get_by_text('456 Oak Avenue', exact=False).first.wait_for(timeout=120000)
            await page.screenshot(path=str(destination / 'order-after.png'), full_page=True,
                                  mask=[page.locator('.admin-user')])
            gui = {'order_id': order_id, 'address_id': address_id,
                   'save_response_status': response.status,
                   'post_save_url': safe_url(page.url), 'visible_target_street': True}
            progress('saved_and_visible', **gui)
        finally:
            await context.close()
        raw = json.loads(raw_path.read_text())
        observed_save_posts = [{'mime_type': (e['request'].get('postData') or {}).get('mimeType'),
                                'body_length': len((e['request'].get('postData') or {}).get('text', ''))}
                               for e in raw['log']['entries']
                               if '/sales/order/addressSave/address_id/' in e['request']['url']]
        clean = sanitize_har(raw)
        wa = evaluator(source)
        raw_score = evaluate(wa, raw_path)
        clean_path = destination / 'network.har'
        write_new(clean_path, clean)
        clean_score = evaluate(wa, clean_path)
        require(raw_score == clean_score, 'HAR redaction altered the official evaluator outcome')
        require(credentials['password'] not in clean_path.read_text(), 'password in sanitized trace')
        receipt = {'gui': gui, 'blocked_external_requests': blocked,
                   'observed_save_posts': observed_save_posts,
                   'network_entries': len(clean['log']['entries']),
                   'raw_har_sha256': sha(raw_path.read_bytes()),
                   'sanitized_har_sha256': sha(clean_path.read_bytes()),
                   'raw_har_retained': False, 'auth_state_retained': False,
                   'published_evaluator': clean_score, 'raw_and_sanitized_evaluator_equal': True,
                   'screenshots': {name: sha((destination / name).read_bytes())
                                   for name in ('order-before.png', 'form-before-save.png', 'order-after.png')}}
        write_new(destination / 'receipt.json', receipt)
        return receipt


async def run(source, out):
    from playwright.async_api import async_playwright
    source, out = Path(source).resolve(), Path(out).resolve()
    require(out.is_relative_to(ROOT / 'work/scale-v06'), 'output must stay in work/scale-v06')
    require(not out.exists(), 'choose a fresh evidence directory')
    out.mkdir(parents=True, mode=0o700)
    report = {'version': VERSION, 'started_at': time.time(), 'task_id': TASK_ID,
              'complete': False, 'model_calls': 0, 'paid_provider_calls': 0,
              'user_account_accessed': False, 'hundred_task_ready': False,
              'qualification_scope': 'one scripted Magento order-address mutation and rollback'}
    original = None
    rollback_private = out / 'rollback.private.json'
    try:
        task, proof = source_proof(source)
        report.update(source=proof, container=container_proof(), task_intent=task['intent'],
                      tool_sha256=sha(Path(__file__).read_bytes()))
        original = read_db()
        write_new(rollback_private, original)
        write_new(out / 'db-before.json', public_db(original))
        cases = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            report['browser_version'] = browser.version
            try:
                for name, order_id, address_id, expected_score in (
                    ('positive-order-299', 299, 598, 1.0),
                    ('wrong-order-300', 300, 600, 0.0)):
                    receipt = await gui_case(browser, source, out / name, order_id, address_id)
                    after = read_db()
                    write_new(out / f'db-after-{name}.json', public_db(after))
                    changed = validate_change(original, after, str(address_id))
                    require(receipt['published_evaluator']['score'] == expected_score
                            and receipt['published_evaluator']['status'] == ('success' if expected_score else 'failure')
                            and not receipt['published_evaluator']['error_present'],
                            'official evaluator failed positive/negative discrimination')
                    restore_rows(original)
                    reset = read_db()
                    write_new(out / f'db-restored-{name}.json', public_db(reset))
                    validate_reset(original, reset)
                    cases.append({'name': name, 'score': expected_score,
                                  'changed_columns': changed, 'reset_verified': True,
                                  'receipt_sha256': sha((out / name / 'receipt.json').read_bytes())})
                    print(json.dumps({'case': name, 'score': expected_score,
                                      'changed_columns': changed, 'reset_verified': True}), flush=True)
            finally:
                await browser.close()
        report.update(complete=True, qualified_task_count=1, cases=cases,
                      database_reset_verified=True,
                      limitation='One scripted oracle task. Official HAR evaluator checks a request; independent SQL readback and reset are local pilot additions. No model generalization or 100-task readiness shown.')
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc)[:500])
        raise
    finally:
        if original is not None:
            try:
                restore_rows(original)
                final = read_db()
                validate_reset(original, final)
                report['final_reset_verified'] = True
                rollback_private.unlink()
            except Exception as rollback_error:
                report['final_reset_verified'] = False
                report['rollback_error_type'] = type(rollback_error).__name__
                report['complete'] = False
                report['qualified_task_count'] = 0
        report['finished_at'] = time.time()
        write_new(out / 'result.json', report)
    require(report.get('final_reset_verified'), 'final rollback verification failed')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=ROOT / 'work/scale-v06/sources/webarena-verified')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.source, args.out))
        print(json.dumps({key: result[key] for key in
                          ('complete', 'qualified_task_count', 'hundred_task_ready', 'final_reset_verified')}))
    except Exception as exc:
        print(json.dumps({'complete': False, 'error_type': type(exc).__name__,
                          'provider_calls': 0}), file=sys.stderr)
        raise SystemExit(1)
