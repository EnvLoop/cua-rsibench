"""Qualify one five-variant Magento price task in a disposable local clone.

The GUI oracle is scripted, not a model rollout. Published WebArena evaluators
remain unchanged; independent SQL readback and rollback add state evidence.
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
VERSION = 'magento-variant-price-v1'
COMMIT = '6473f72db5dcefc97b5725b59e734504edc28a21'
DATA_SHA = 'd65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30'
TASK_SHA = 'a39bdffcb64ffc8cbb5305858853c6c87664eac0060fedfd554b5bf6bfe9f177'
TASK_ID = 777
CONTEXT = 'colima-cua-scale'
CONTAINER = 'cua-v06-magento-price'
IMAGE = 'sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13'
BASE = 'http://localhost:7792/admin'
TARGETS = {111: 'MH05-XS-Green', 114: 'MH05-S-Green', 117: 'MH05-M-Green',
           120: 'MH05-L-Green', 123: 'MH05-XL-Green'}
WRONG = {112: 'MH05-XS-Red'}
PARENT_ID = 126
IDS = tuple(sorted((*TARGETS, *WRONG, PARENT_ID)))
PRICE_ATTR = 77
MONITORED = ('catalog_product_entity', 'catalog_product_entity_decimal',
             'catalog_product_entity_int', 'catalog_product_entity_varchar',
             'catalog_product_entity_text', 'catalog_product_entity_datetime',
             'catalog_product_index_price', 'catalog_product_index_price_replica',
             'cataloginventory_stock_item')
RESTORE = ('catalog_product_entity_decimal', 'catalog_product_entity_int',
           'catalog_product_entity_varchar', 'catalog_product_entity_text',
           'catalog_product_index_price', 'catalog_product_index_price_replica',
           'cataloginventory_stock_item', 'catalog_product_entity')
SENSITIVE = re.compile(r'password|passwd|token|secret|session|form_key|authorization|cookie|^sid$', re.I)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


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
    return ((u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1')
             and u.port == 7792 and not u.username and not u.password)
            or u.scheme in ('data', 'blob', 'about'))


def price_from_post(post):
    """Extract one ordinary field from Magento's multipart or URL-encoded form."""
    for param in post.get('params') or ():
        if param.get('name') == 'product[price]' and 'value' in param:
            return str(param['value'])
    mime, body = post.get('mimeType', ''), post.get('text', '')
    if 'application/x-www-form-urlencoded' in mime:
        return dict(parse_qsl(body, keep_blank_values=True)).get('product[price]')
    if 'multipart/form-data' in mime:
        match = re.search(r'boundary=([^;\s]+)', mime)
        if not match:
            return None
        for part in body.split('--' + match.group(1)):
            header, sep, value = part.partition('\r\n\r\n')
            if not sep:
                header, sep, value = part.partition('\n\n')
            if sep and re.search(r'name="product\[price\]"', header):
                return value.rstrip('\r\n')
    return None


def sanitize_har(raw):
    """Keep the published evaluator's URL, response and price field only."""
    entries = []
    for entry in raw['log']['entries']:
        request, response = entry['request'], entry['response']
        clean = {'url': safe_url(request['url']), 'method': request['method'],
                 'headers': [h for h in request.get('headers', [])
                             if h['name'].lower() in ('content-type', 'accept')],
                 'queryString': [{'name': k, 'value': v}
                                 for k, v in parse_qsl(urlsplit(safe_url(request['url'])).query)],
                 'cookies': []}
        post = request.get('postData') or {}
        if '/catalog/product/save/id/' in request['url']:
            price = price_from_post(post)
            require(price is not None, 'price field missing from product save HAR')
            clean['postData'] = {'mimeType': 'application/x-www-form-urlencoded',
                                 'text': urlencode({'product[price]': price})}
        entries.append({'startedDateTime': entry.get('startedDateTime'), 'request': clean,
                        'response': {'status': response['status'], 'headers': [], 'cookies': [],
                                     'redirectURL': safe_url(response.get('redirectURL', '')),
                                     'content': {}}})
    return {'log': {'version': '1.2', 'creator': {'name': VERSION, 'version': '1'}, 'entries': entries}}


def source_proof(source):
    source = Path(source).resolve()
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], check=True,
                            capture_output=True, text=True).stdout.strip()
    require(commit == COMMIT, 'pinned WebArena-Verified commit changed')
    dirty = subprocess.run(['git', '-C', str(source), 'status', '--porcelain', '--',
                            'src', 'assets/dataset', 'examples/configs'], check=True,
                           capture_output=True, text=True).stdout
    require(not dirty.strip(), 'official evaluator/task/config checkout is modified')
    dataset = source / 'assets/dataset/webarena-verified.json'
    require(sha(dataset.read_bytes()) == DATA_SHA, 'pinned task dataset changed')
    task = next(row for row in json.loads(dataset.read_text()) if row['task_id'] == TASK_ID)
    require(task['sites'] == ['shopping_admin'] and task['revision'] == 2
            and task['intent_template_id'] == 742 and digest(task) == TASK_SHA,
            'task identity or assertion changed')
    urls = [e['expected']['url'] for e in task['eval'] if e['evaluator'] == 'NetworkEventEvaluator']
    require(len(urls) == 5 and all(any(f'/save/id/{key}/' in url for url in urls) for key in TARGETS),
            'five-variant evaluator contract changed')
    import webarena_verified
    require(Path(webarena_verified.__file__).resolve().is_relative_to(source / 'src'),
            'evaluator imported from another installation')
    files = {p.relative_to(source).as_posix(): sha(p.read_bytes())
             for p in (source / 'src/webarena_verified').rglob('*.py')}
    return task, {'git_commit': commit, 'dataset_sha256': DATA_SHA,
                  'task_sha256': TASK_SHA, 'evaluator_source_sha256': digest(files),
                  'evaluator_source_file_count': len(files),
                  'versions': {name: importlib.metadata.version(name)
                               for name in ('webarena-verified', 'playwright', 'pydantic')}}


def container_proof():
    raw = subprocess.run(['docker', '--context', CONTEXT, 'inspect', CONTAINER], check=True,
                         capture_output=True, text=True, timeout=30).stdout
    c = json.loads(raw)[0]
    require(c['Image'] == IMAGE and c['State']['Running'], 'isolated container image/state changed')
    ports = c['NetworkSettings']['Ports']
    require(ports['80/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '7792'}]
            and ports['8877/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '7793'}]
            and not c['Mounts'], 'isolated clone port/mount contract changed')
    return {'name': CONTAINER, 'docker_context': CONTEXT, 'image_sha256': IMAGE,
            'container_id_sha256': sha(c['Id']), 'local_ports': [7792, 7793], 'mounts': 0}


def php_exec(code):
    return subprocess.run(['docker', '--context', CONTEXT, 'exec', '-i', CONTAINER, 'php'],
                          input=code, text=True, check=True, capture_output=True, timeout=120).stdout


DB_READ = r'''<?php
$cfg=include '/var/www/magento2/app/etc/env.php';$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);$db->exec('START TRANSACTION READ ONLY');
$tables=TABLES;$restore=RESTORE;$ids=IDS;$list=implode(',',array_map('intval',$ids));
$out=['tables'=>[],'selected'=>[],'identities'=>[]];
foreach($tables as $table){$rows=$db->query('SELECT * FROM `'.$table.'`')->fetchAll(PDO::FETCH_ASSOC);$hashes=[];
 foreach($rows as $row){ksort($row);$hashes[]=hash('sha256',json_encode($row,JSON_UNESCAPED_SLASHES));}sort($hashes);
 $out['tables'][$table]=['rows'=>count($rows),'sha256'=>hash('sha256',implode("\n",$hashes))];}
foreach($restore as $table){$key=$table==='cataloginventory_stock_item'?'product_id':'entity_id';
 $s=$db->query('SELECT * FROM `'.$table.'` WHERE `'.$key.'` IN ('.$list.')');
 $out['selected'][$table]=$s->fetchAll(PDO::FETCH_ASSOC);}
$s=$db->query('SELECT e.entity_id,e.sku,e.type_id,sl.parent_id FROM catalog_product_entity e LEFT JOIN catalog_product_super_link sl ON sl.product_id=e.entity_id WHERE e.entity_id IN ('.$list.') ORDER BY e.entity_id');
$out['identities']=$s->fetchAll(PDO::FETCH_ASSOC);
$db->rollBack();echo json_encode($out,JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
'''.replace('TABLES', json.dumps(MONITORED)).replace('RESTORE', json.dumps(RESTORE)).replace('IDS', json.dumps(IDS))


def read_db():
    data = json.loads(php_exec(DB_READ))
    require(set(data['tables']) == set(MONITORED) and set(data['selected']) == set(RESTORE),
            'database snapshot scope incomplete')
    identities = {int(row['entity_id']): row for row in data['identities']}
    require(set(identities) == set(IDS), 'variant identity rows missing')
    for entity_id, sku in {**TARGETS, **WRONG}.items():
        row = identities[entity_id]
        require(row['sku'] == sku and row['type_id'] == 'simple'
                and int(row['parent_id']) == PARENT_ID, 'variant SKU/parent changed')
    require(identities[PARENT_ID]['type_id'] == 'configurable', 'configurable parent changed')
    return data


def prices(snapshot):
    rows = snapshot['selected']['catalog_product_entity_decimal']
    return {int(row['entity_id']): row['value'] for row in rows
            if int(row['attribute_id']) == PRICE_ATTR and int(row['store_id']) == 0}


def public_db(snapshot):
    return {'tables': snapshot['tables'], 'prices': {str(k): v for k, v in prices(snapshot).items()},
            'selected_row_sha256': {table: digest(rows) for table, rows in snapshot['selected'].items()},
            'selected_row_counts': {table: len(rows) for table, rows in snapshot['selected'].items()},
            'read_only_transaction': True}


def restore_rows(original):
    """Restore selected product, EAV, index and stock rows atomically."""
    payload = base64.b64encode(json.dumps(original['selected'], separators=(',', ':')).encode()).decode()
    code = r'''<?php
$cfg=include '/var/www/magento2/app/etc/env.php';$d=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$d['host'].';dbname='.$d['dbname'],$d['username'],$d['password']);
$db->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$snapshot=json_decode(base64_decode('PAYLOAD'),true,512,JSON_THROW_ON_ERROR);$ids=IDS;
if(array_keys($snapshot)!==RESTORE)throw new Exception('restore table set changed');
foreach($snapshot as $table=>$rows){$key=$table==='cataloginventory_stock_item'?'product_id':'entity_id';
 foreach($rows as $row){if(!in_array((int)$row[$key],$ids,true))throw new Exception('restore entity mismatch');}}
$list=implode(',',array_map('intval',$ids));$db->beginTransaction();
try{
 foreach(['catalog_product_entity_decimal','catalog_product_entity_int','catalog_product_entity_varchar',
          'catalog_product_entity_text','catalog_product_index_price','catalog_product_index_price_replica'] as $table){
  $db->exec('DELETE FROM `'.$table.'` WHERE entity_id IN ('.$list.')');
  foreach($snapshot[$table] as $row){$fields=array_keys($row);$sql='INSERT INTO `'.$table.'` (`'.implode('`,`',$fields).'`) VALUES ('.implode(',',array_fill(0,count($fields),'?')).')';
   $db->prepare($sql)->execute(array_values($row));}}
 foreach($snapshot['cataloginventory_stock_item'] as $row){$fields=array_values(array_filter(array_keys($row),fn($f)=>$f!=='item_id'));
  $sql='UPDATE cataloginventory_stock_item SET '.implode(',',array_map(fn($f)=>'`'.$f.'`=?',$fields)).' WHERE item_id=?';
  $values=array_map(fn($f)=>$row[$f],$fields);$values[]=$row['item_id'];$db->prepare($sql)->execute($values);}
 foreach($snapshot['catalog_product_entity'] as $row){$fields=array_values(array_filter(array_keys($row),fn($f)=>$f!=='entity_id'));
  $sql='UPDATE catalog_product_entity SET '.implode(',',array_map(fn($f)=>'`'.$f.'`=?',$fields)).' WHERE entity_id=?';
  $values=array_map(fn($f)=>$row[$f],$fields);$values[]=$row['entity_id'];$db->prepare($sql)->execute($values);}
 $db->commit();echo 'restored';}catch(Throwable $e){$db->rollBack();throw $e;}
'''.replace('PAYLOAD', payload).replace('RESTORE', json.dumps(list(RESTORE))).replace('IDS', json.dumps(list(IDS)))
    require(php_exec(code).strip() == 'restored', 'transactional product restore failed')


def validate_positive(before, after):
    old, new = prices(before), prices(after)
    require(all(float(old[key]) == 52.0 and float(new[key]) == 47.0 for key in TARGETS),
            'five target prices did not persist as 52 to 47')
    require(float(old[112]) == 52.0 and new[112] == old[112], 'wrong-color comparator changed')
    require(all(after['tables'][table] == before['tables'][table] for table in MONITORED
                if table not in RESTORE), 'an unrelated monitored business table changed')
    require(after['tables']['catalog_product_entity_decimal']['sha256'] !=
            before['tables']['catalog_product_entity_decimal']['sha256'], 'price EAV table did not change')


def validate_negative(before, after):
    old, new = prices(before), prices(after)
    require(all(new[key] == old[key] for key in TARGETS), 'wrong-object negative touched a green target')
    require(float(old[112]) == 52.0 and float(new[112]) == 47.0,
            'wrong-object red variant did not persist')
    require(all(after['tables'][table] == before['tables'][table] for table in MONITORED
                if table not in RESTORE), 'an unrelated monitored business table changed')


def validate_reset(before, after):
    require(after['tables'] == before['tables'] and after['selected'] == before['selected']
            and after['identities'] == before['identities'],
            'transactional product restore did not recover monitored baseline')


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


async def open_products(page):
    menu = page.locator('[data-ui-id="menu-magento-catalog-catalog-products"] > a')
    for _ in range(4):
        if await menu.is_visible():
            break
        await page.locator('#menu-magento-catalog-catalog > a').click()
        await page.wait_for_timeout(300)
    await menu.click()
    await page.get_by_role('heading', name='Products', exact=True).wait_for(timeout=120000)
    await page.locator('input#fulltext:visible').first.wait_for(timeout=120000)


async def edit_variant(page, entity_id, sku, destination):
    await open_products(page)
    search = page.locator('input#fulltext:visible').first
    await search.fill(sku)
    await search.press('Enter')
    row = page.locator('table.data-grid tbody tr').filter(has_text=sku).first
    await row.wait_for(timeout=120000)
    require(sku in await row.inner_text(), 'search result SKU does not match')
    edit = row.get_by_text('Edit', exact=True)
    require(urlsplit(await edit.get_attribute('href')).path.endswith(f'/catalog/product/edit/id/{entity_id}/'),
            'product edit link points at another entity')
    await edit.click()
    await page.locator('h1.page-title').wait_for(timeout=120000)
    visible_sku = page.locator('input[name="product[sku]"]:visible').first
    await visible_sku.wait_for(timeout=120000)
    require(await visible_sku.input_value() == sku, 'visible product SKU does not match target')
    price = page.locator('input[name="product[price]"]:visible').first
    await price.wait_for(timeout=120000)
    require(float(await price.input_value()) == 52.0, 'visible baseline price changed')
    await page.screenshot(path=str(destination / f'before-{entity_id}.png'), full_page=True,
                          mask=[page.locator('.admin-user')])
    await price.fill('47.00')
    require(float(await price.input_value()) == 47.0, 'visible price edit failed')
    async with page.expect_response(lambda r: f'/catalog/product/save/id/{entity_id}/' in r.url
                                    and r.request.method == 'POST', timeout=120000) as response_info:
        await page.get_by_role('button', name='Save', exact=True).click()
    response = await response_info.value
    require(response.status == 302, 'native product save did not redirect')
    await page.screenshot(path=str(destination / f'after-{entity_id}.png'), full_page=True,
                          mask=[page.locator('.admin-user')])
    return {'entity_id': entity_id, 'sku': sku, 'save_response_status': response.status,
            'post_save_url': safe_url(page.url)}


async def gui_case(browser, source, destination, variants):
    destination.mkdir(mode=0o700)
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
        page.set_default_timeout(60000)
        credentials = json.loads((Path(source) / 'examples/configs/config.example.json').read_text())['environments']['__SHOPPING_ADMIN__']['credentials']
        saves = []
        try:
            require(not await context.cookies(), 'browser context is not fresh')
            await page.goto(BASE, wait_until='domcontentloaded', timeout=120000)
            await page.get_by_label('Username', exact=True).fill(credentials['username'])
            await page.get_by_label('Password', exact=True).fill(credentials['password'])
            await page.get_by_role('button', name='Sign in', exact=True).click()
            await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=120000)
            for entity_id, sku in variants.items():
                saves.append(await edit_variant(page, entity_id, sku, destination))
                print(json.dumps({'case': destination.name, 'saved_id': entity_id}), flush=True)
        finally:
            await context.close()
        raw = json.loads(raw_path.read_text())
        clean = sanitize_har(raw)
        clean_path = destination / 'network.har'
        write_new(clean_path, clean)
        wa = evaluator(source)
        raw_score, clean_score = evaluate(wa, raw_path), evaluate(wa, clean_path)
        write_new(destination / 'evaluator-comparison.json',
                  {'raw': raw_score, 'sanitized': clean_score})
        require(raw_score == clean_score, 'HAR redaction altered official scoring')
        require(credentials['password'] not in clean_path.read_text(), 'password in sanitized trace')
        receipt = {'saved': saves, 'blocked_external_requests': blocked,
                   'network_entries': len(clean['log']['entries']),
                   'raw_har_sha256': sha(raw_path.read_bytes()),
                   'sanitized_har_sha256': sha(clean_path.read_bytes()),
                   'raw_har_retained': False, 'auth_state_retained': False,
                   'published_evaluator': clean_score,
                   'raw_and_sanitized_evaluator_equal': True,
                   'screenshot_sha256': {p.name: sha(p.read_bytes()) for p in destination.glob('*.png')}}
        write_new(destination / 'receipt.json', receipt)
        return receipt


async def run(source, out):
    from playwright.async_api import async_playwright
    source, out = Path(source).resolve(), Path(out).resolve()
    require(out.is_relative_to(ROOT / 'work/scale-v06'), 'output must stay in work/scale-v06')
    require(not out.exists(), 'choose a fresh private evidence directory')
    out.mkdir(parents=True, mode=0o700)
    report = {'version': VERSION, 'started_at': time.time(), 'task_id': TASK_ID,
              'complete': False, 'model_calls': 0, 'paid_provider_calls': 0,
              'user_account_accessed': False, 'hundred_task_ready': False,
              'qualification_scope': 'one scripted five-variant Magento price mutation and rollback'}
    original = None
    private_rollback = out / 'rollback.private.json'
    try:
        task, source_info = source_proof(source)
        report.update(source=source_info, container=container_proof(),
                      task_intent=task['intent'], tool_sha256=sha(Path(__file__).read_bytes()))
        original = read_db()
        require(all(float(prices(original)[key]) == 52.0 for key in (*TARGETS, *WRONG)),
                'baseline prices differ from published task')
        write_new(private_rollback, original)
        write_new(out / 'db-before.json', public_db(original))
        cases = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            report['browser_version'] = browser.version
            try:
                for name, variants, validator, expected in (
                    ('positive-five-green', TARGETS, validate_positive, 1.0),
                    ('wrong-color-red-xs', WRONG, validate_negative, 0.0)):
                    receipt = await gui_case(browser, source, out / name, variants)
                    after = read_db()
                    write_new(out / f'db-after-{name}.json', public_db(after))
                    validator(original, after)
                    score = receipt['published_evaluator']
                    require(score['score'] == expected and
                            score['status'] == ('success' if expected else 'failure') and
                            not score['error_present'],
                            'official evaluator did not discriminate positive and wrong color')
                    restore_rows(original)
                    reset = read_db()
                    write_new(out / f'db-restored-{name}.json', public_db(reset))
                    validate_reset(original, reset)
                    cases.append({'name': name, 'official_score': expected,
                                  'database_reset_verified': True,
                                  'receipt_sha256': sha((out / name / 'receipt.json').read_bytes())})
                    print(json.dumps({'case': name, 'official_score': expected,
                                      'database_reset_verified': True}), flush=True)
            finally:
                await browser.close()
        report.update(complete=True, qualified_task_count=1, cases=cases,
                      database_reset_verified=True,
                      limitation='One scripted task in one clone. No model rollout, 100-task-ready population, or generic Magento reset proved.')
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc)[:500])
        raise
    finally:
        if original is not None:
            try:
                restore_rows(original)
                validate_reset(original, read_db())
                report['final_reset_verified'] = True
                private_rollback.unlink()
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
