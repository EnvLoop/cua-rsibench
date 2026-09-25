"""Train-only technical GUI trajectory for pinned Magento task 777.

This public development task is permanently excluded from final evaluation.
The saved private episode can test multimodal SFT wiring but cannot measure a
post-training gain on task 777. No model service is called by this recorder.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlsplit

from cursibench.gui_sft_data_v1 import (
    SCHEMA, SOURCE_COMMIT, SOURCE_DATA_SHA256, TRAIN_TASK_ID,
    TRAIN_TEMPLATE_ID, sha256,
)
import magento_gui_sft_base_v1 as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE_IDS = (111, 114, 117, 120, 123)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


price = _load(ROOT / 'tools/qualify_magento_variant_price_v1.py', 'pinned_price_qualifier')
price.CONTAINER = base.CONTAINER
price.BASE = base.BASE


async def open_products(recorder: base.Recorder):
    page = recorder.page
    products = page.locator('[data-ui-id="menu-magento-catalog-catalog-products"] > a')
    if not await products.is_visible():
        await recorder.act('click', locator=page.locator('#menu-magento-catalog-catalog > a'),
                           memory='Open Catalog navigation.')
    await recorder.act('click', locator=products, memory='Open the product grid.')
    await page.get_by_role('heading', name='Products', exact=True).wait_for(timeout=120_000)
    await page.locator('input#fulltext:visible').first.wait_for(timeout=120_000)


async def edit_variant(recorder: base.Recorder, entity_id: int, sku: str):
    page = recorder.page
    await open_products(recorder)
    search = page.locator('input#fulltext:visible').first
    await recorder.act('type', locator=search, text=sku,
                       memory='Search for the visible product SKU.')
    await recorder.act('key', locator=search, key='Enter',
                       memory='Submit the product search.')
    row = page.locator('table.data-grid tbody tr').filter(has_text=sku).first
    await row.wait_for(state='visible', timeout=120_000)
    base.require(sku in await row.inner_text(), 'target_sku_not_in_visible_row')
    edit = row.get_by_text('Edit', exact=True)
    base.require(urlsplit(await edit.get_attribute('href')).path.endswith(
        f'/catalog/product/edit/id/{entity_id}/'), 'wrong_product_edit_link')
    await recorder.act('click', locator=edit, prefer_coordinate=True,
                       memory='Open the matching product variant.')
    visible_sku = page.locator('input[name="product[sku]"]:visible').first
    await visible_sku.wait_for(timeout=120_000)
    base.require(await visible_sku.input_value() == sku, 'wrong_visible_product_sku')
    field = page.locator('input[name="product[price]"]:visible').first
    await field.wait_for(timeout=120_000)
    base.require(float(await field.input_value()) == 52.0, 'baseline_variant_price_changed')
    await base.ensure_target_visible(recorder, field,
                                     memory='Scroll to the visible price field.')
    await recorder.act('type', locator=field, text='47.00',
                       memory='Set this variant to the requested price.')
    base.require(float(await field.input_value()) == 47.0, 'price_edit_not_visible')
    async with page.expect_response(lambda response:
            f'/catalog/product/save/id/{entity_id}/' in response.url and
            response.request.method == 'POST', timeout=120_000) as response_info:
        await recorder.act('click', locator=page.get_by_role('button', name='Save', exact=True),
                           memory='Save this variant before the next.')
    response = await response_info.value
    base.require(response.status == 302, 'native_product_save_failed')
    await page.get_by_text('You saved the product.', exact=True).wait_for(timeout=120_000)
    return response.status


async def record_gui(browser, source: Path, out: Path, task: dict, binding: str):
    credentials = json.loads((source / 'examples/configs/config.example.json').read_text())[
        'environments']['__SHOPPING_ADMIN__']['credentials']
    with tempfile.TemporaryDirectory(prefix='.private-har-', dir=out) as temporary:
        raw_har = Path(temporary) / 'network.har'
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000},
            service_workers='block', record_har_path=str(raw_har), record_har_content='embed')
        blocked = []
        async def guard(route):
            if base.order.permitted_request(route.request.url):
                await route.continue_()
            else:
                blocked.append(sha256(route.request.url.encode()))
                await route.abort()
        await context.route('**/*', guard)
        async def close_socket(socket):
            await socket.close()
        await context.route_web_socket('**/*', close_socket)
        page = await context.new_page()
        page.set_default_timeout(45_000)
        recorder = base.Recorder(page, out, TRAIN_TASK_ID, task['intent'], binding)
        saves = []
        try:
            base.require(not await context.cookies(), 'browser_context_not_fresh')
            await page.goto(base.BASE, wait_until='domcontentloaded', timeout=120_000)
            await page.get_by_label('Username', exact=True).fill(credentials['username'])
            await page.get_by_label('Password', exact=True).fill(credentials['password'])
            await page.get_by_role('button', name='Sign in', exact=True).click()
            await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=120_000)
            for entity_id, sku in price.TARGETS.items():
                status = await edit_variant(recorder, entity_id, sku)
                saves.append({'product_id': entity_id, 'save_status': status})
                print(json.dumps({'stage': 'saved_variant', 'count': len(saves)}), flush=True)
            await recorder.act('finish', memory='All five target variants visibly saved.')
        finally:
            await context.close()
        base.require(not blocked, 'external_network_request_blocked')
        raw = json.loads(raw_har.read_text())
        clean_har = Path(temporary) / 'network-clean.har'
        clean_har.write_text(json.dumps(price.sanitize_har(raw)))
        official = price.evaluator(source)
        raw_score = price.evaluate(official, raw_har)
        clean_score = price.evaluate(official, clean_har)
        base.write_private(out / 'evaluator.private.json', {
            'raw': raw_score, 'sanitized': clean_score,
            'save_count': len(saves), 'blocked_count': len(blocked)})
        base.require(raw_score == clean_score, 'sanitization_changed_official_evaluator')
        base.require(clean_score['score'] == 1.0 and clean_score['status'] == 'success'
                     and not clean_score['error_present'], 'published_evaluator_not_positive')
        return recorder.steps, {
            'published_evaluator_score': clean_score['score'],
            'raw_and_sanitized_evaluator_equal': True,
            'raw_har_sha256': sha256(raw_har.read_bytes()),
            'sanitized_har_sha256': sha256(clean_har.read_bytes()),
            'native_save_count': len(saves),
            'external_requests_blocked': len(blocked),
        }


async def run(source: Path, out: Path) -> dict:
    from playwright.async_api import async_playwright
    source, out = Path(source).resolve(), Path(out).resolve()
    base.require(out.is_relative_to(ROOT / 'work') and not out.exists(),
                 'output_requires_fresh_ignored_work_path')
    out.mkdir(mode=0o700, parents=True)
    report = {'schema': 'magento-price777-gui-sft-record-v1',
              'task_id': TRAIN_TASK_ID, 'intent_template_id': TRAIN_TEMPLATE_ID,
              'split': 'train', 'status': 'unscored', 'paid_provider_calls': 0,
              'model_calls': 0, 'episode_admitted': False,
              'screenshot_mask_policy': 'admin-user-and-dashboard-tables',
              'scope': 'technical SFT data gate, no trained-model score'}
    before = None
    before_search = None
    try:
        task, proof = price.source_proof(source)
        clone = base.clone_preflight()
        search_health = price.search_health()
        report.update(source=proof, clone=clone, search_health=search_health)
        before = price.read_db()
        before_search = price.read_search_index()
        base.require(all(float(price.prices(before)[key]) == 52.0
                         for key in (*price.TARGETS, *price.WRONG)),
                     'baseline_price_changed')
        base.require(float(before_search['parent_price_0_1']) == 52.0,
                     'baseline_search_price_changed')
        base.write_private(out / 'rollback.private.json', before)
        binding = price.digest({'source_commit': SOURCE_COMMIT,
                                'source_dataset_sha256': SOURCE_DATA_SHA256,
                                'task_id': TRAIN_TASK_ID, 'intent': task['intent'],
                                'split': 'train', 'runtime': clone})
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                steps, official = await record_gui(browser, source, out, task, binding)
            finally:
                await browser.close()
        after = price.read_db()
        price.validate_positive(before, after)
        search_after = price.read_search_index()
        base.require(float(search_after['parent_price_0_1']) == 47.0,
                     'search_index_target_price_not_saved')
        report['independent_saved_state_pass'] = True
        price.restore_rows(before)
        price.reindex_search()
        price.validate_reset(before, price.read_db())
        price.validate_search_reset(before_search, price.read_search_index())
        report['reset_verified'] = True
        admission = {**official, 'independent_saved_state_pass': True,
                     'reset_verified': True, 'search_index_reset_verified': True}
        episode = {'schema': SCHEMA, 'split': 'train',
                   'source_commit': SOURCE_COMMIT,
                   'source_dataset_sha256': SOURCE_DATA_SHA256,
                   'site': 'shopping_admin', 'task_id': TRAIN_TASK_ID,
                   'intent_template_id': TRAIN_TEMPLATE_ID,
                   'entity_tags': [f'magento:product:{entity_id}'
                                   for entity_id in SOURCE_IDS],
                   'admission': admission, 'steps': steps}
        base.write_private(out / 'episode.json', episode)
        report.update(status='completed', episode_admitted=True,
                      action_count=len(steps), screenshot_count=len(steps),
                      official_score=official['published_evaluator_score'],
                      episode_sha256=sha256((out / 'episode.json').read_bytes()),
                      raw_har_retained=False, auth_state_retained=False)
    except Exception as exc:
        report.update(status='unscored', failure_type=type(exc).__name__,
                      failure_code=str(exc)[:100])
        raise
    finally:
        if before is not None:
            try:
                price.restore_rows(before)
                if before_search is not None:
                    price.reindex_search()
                price.validate_reset(before, price.read_db())
                if before_search is not None:
                    price.validate_search_reset(before_search, price.read_search_index())
                report['final_reset_verified'] = True
                (out / 'rollback.private.json').unlink(missing_ok=True)
            except Exception as exc:
                report['final_reset_verified'] = False
                report['reset_error_type'] = type(exc).__name__
                report['episode_admitted'] = False
                (out / 'episode.json').unlink(missing_ok=True)
        report['finished_at'] = time.time()
        base.write_private(out / 'result.json', report)
    base.require(report.get('episode_admitted') and report.get('final_reset_verified'),
                 'episode_not_admitted')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args.source, args.out))
        print(json.dumps({key: result[key] for key in
                          ('status', 'task_id', 'action_count', 'official_score',
                           'final_reset_verified', 'paid_provider_calls')}))
    except Exception as exc:
        print(json.dumps({'status': 'unscored', 'failure_type': type(exc).__name__}),
              file=sys.stderr)
        raise SystemExit(1)
