"""Run one scripted GUI control on one original Magento catalog candidate.

The selected task is evaluator-private. This tool leaves the disposable clone
mutated so a separate fresh-clone reset must be proved before admission. It
never samples a model and does not write an official result.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from magento_catalog_factory.verify import check_baseline, read_snapshot, score_saved_state


def write_private(path: Path, value: object) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


async def sign_in(page, base_url: str, source: Path) -> None:
    config = source / 'examples/configs/config.example.json'
    require(config.is_file() and source.resolve().is_relative_to((ROOT / 'work').resolve()),
            'private pinned Magento login fixture unavailable')
    credentials = json.loads(config.read_text())['environments']['__SHOPPING_ADMIN__']['credentials']
    await page.goto(base_url, wait_until='domcontentloaded', timeout=120000)
    await page.get_by_label('Username', exact=True).fill(credentials['username'])
    await page.get_by_label('Password', exact=True).fill(credentials['password'])
    await page.get_by_role('button', name='Sign in', exact=True).click()
    await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=120000)


async def read_quote_in_gui(page, case: dict, out: Path) -> dict:
    # The fixture must be discoverable through the real CMS, not only SQL.
    content_menu = page.locator('#menu-magento-backend-content > a')
    pages_menu = page.locator('[data-ui-id="menu-magento-cms-cms-page"] > a')
    for _ in range(4):
        if await pages_menu.is_visible():
            break
        await content_menu.click()
        await page.wait_for_timeout(300)
    require(await pages_menu.is_visible(), 'native CMS Pages menu did not open')
    await pages_menu.click()
    await page.get_by_role('heading', name='Pages', exact=True).wait_for(timeout=120000)
    search = page.locator('input#fulltext:visible').first
    await search.wait_for(timeout=120000)
    await search.fill(case['quote_page_title'])
    await search.press('Enter')
    row = page.locator('table.data-grid tbody tr').filter(has_text=case['quote_page_title']).first
    await row.wait_for(timeout=120000)
    require(case['quote_page_title'] in await row.inner_text(),
            'quote page not visible in native CMS grid')
    # Magento's CMS grid keeps the Edit action inside a collapsed row menu.
    actions = row.locator('button.action-select')
    await actions.click()
    await row.get_by_text('Edit', exact=True).click()
    await page.locator('h1.page-title').filter(
        has_text=case['quote_page_title']).wait_for(timeout=120000)
    # Magento 2.4.6 collapses the Content accordion and displays raw HTML in
    # its Page Builder staging region, rather than a visible textarea.
    page_builder = page.get_by_text('Edit with Page Builder', exact=True)
    if not await page_builder.is_visible():
        section = None
        for _ in range(40):
            for candidate in await page.get_by_text('Content', exact=True).all():
                box = await candidate.bounding_box()
                if box is not None and box['x'] >= 100 and box['y'] >= 250:
                    section = candidate
                    break
            if section is not None:
                break
            await page.wait_for_timeout(250)
        require(section is not None, 'visible CMS Content accordion missing')
        await section.click()
    await page_builder.wait_for(timeout=120000)
    visible_text = ''
    for _ in range(40):
        visible_text = await page.locator('body').inner_text()
        if case['quote_page_body'] in visible_text:
            break
        await page.wait_for_timeout(250)
    require(case['quote_page_body'] in visible_text and
            hashlib.sha256(case['quote_page_body'].encode()).hexdigest() ==
            case['quote_page_body_sha256'],
            'native CMS Content region did not show the exact private quote')
    screenshot = out / 'private-quote-page.png'
    await page.screenshot(path=str(screenshot), full_page=False,
                          mask=[page.locator('.admin-user')])
    screenshot.chmod(0o600)
    return {'quote_visible_in_native_cms': True,
            'quote_body_sha256': case['quote_page_body_sha256'],
            'screenshot_sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()}


async def open_products(page) -> None:
    menu = page.locator('[data-ui-id="menu-magento-catalog-catalog-products"] > a')
    for _ in range(4):
        if await menu.is_visible():
            break
        await page.locator('#menu-magento-catalog-catalog > a').click()
        await page.wait_for_timeout(300)
    await menu.click()
    await page.get_by_role('heading', name='Products', exact=True).wait_for(timeout=120000)
    await page.locator('input#fulltext:visible').first.wait_for(timeout=120000)


async def edit_variant(page, row: dict, intended_price: str,
                       out: Path) -> dict:
    await open_products(page)
    search = page.locator('input#fulltext:visible').first
    await search.fill(row['sku'])
    await search.press('Enter')
    result = page.locator('table.data-grid tbody tr').filter(has_text=row['sku']).first
    await result.wait_for(timeout=120000)
    edit = result.get_by_text('Edit', exact=True)
    require(urlsplit(await edit.get_attribute('href')).path.endswith(
                f'/catalog/product/edit/id/{row["entity_id"]}/'),
            'visible product row points at another SKU')
    await edit.click()
    visible_sku = page.locator('input[name="product[sku]"]:visible').first
    await visible_sku.wait_for(timeout=120000)
    require(await visible_sku.input_value() == row['sku'],
            'native edit page shows another SKU')
    price = page.locator('input[name="product[price]"]:visible').first
    await price.wait_for(timeout=120000)
    require(round(float(await price.input_value()), 2) ==
            round(float(row['initial_price']), 2),
            'native edit page starting price changed')
    await price.fill(intended_price)
    async with page.expect_response(lambda response:
                                    f'/catalog/product/save/id/{row["entity_id"]}/' in
                                    response.url and response.request.method == 'POST',
                                    timeout=120000) as pending:
        await page.get_by_role('button', name='Save', exact=True).click()
    response = await pending.value
    require(response.status == 302, 'native product save did not redirect')
    await page.get_by_text('You saved the product.', exact=True).wait_for(timeout=120000)
    screenshot = out / f'private-save-{row["entity_id"]}.png'
    await page.screenshot(path=str(screenshot), full_page=False,
                          mask=[page.locator('.admin-user')])
    screenshot.chmod(0o600)
    return {'entity_id': row['entity_id'], 'sku': row['sku'],
            'native_save_status': response.status,
            'screenshot_sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()}


async def run(case: dict, source: Path, container: str,
              http_port: int, control_port: int, page_id: int,
              mode: str, out: Path, search_host: str = '127.0.0.1') -> dict:
    from playwright.async_api import async_playwright

    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    before = read_snapshot(case, container, http_port, control_port,
                           page_id, search_host=search_host)
    check_baseline(case, before)
    before_sha = write_private(out / 'private-before.json', before)
    base = f'http://localhost:{http_port}/admin'
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        blocked = 0
        async def guard(route):
            nonlocal blocked
            parsed = urlsplit(route.request.url)
            if ((parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1')
                 and parsed.port == http_port) or
                    parsed.scheme in ('data', 'blob', 'about')):
                await route.continue_()
            else:
                blocked += 1
                await route.abort()
        await context.route('**/*', guard)
        page = await context.new_page()
        page.set_default_timeout(60000)
        try:
            require(not await context.cookies(), 'browser context was not fresh')
            await sign_in(page, base, source)
            quote = await read_quote_in_gui(page, case, out)
            if mode == 'positive':
                edits = [(row, row['target_price']) for row in case['target_variants']]
            elif mode == 'neutral':
                edits = [(row, row['initial_price']) for row in case['target_variants']]
            else:
                comparator = case['untouched_comparators'][0]
                from decimal import Decimal
                wrong = str(Decimal(comparator['price']) + Decimal('0.05'))
                edits = [({'entity_id': comparator['entity_id'],
                           'sku': comparator['sku'],
                           'initial_price': comparator['price']}, wrong)]
            saves = [await edit_variant(page, row, target, out)
                     for row, target in edits]
        finally:
            await context.close()
            await browser.close()
    after = read_snapshot(case, container, http_port, control_port,
                          page_id, search_host=search_host)
    after_sha = write_private(out / 'private-after.json', after)
    score = score_saved_state(case, before, after)
    neutral_preserved = (
        after['database']['prices'] == before['database']['prices'] and
        after['database']['quote'] == before['database']['quote'] and
        after['database']['hashes']['other_catalog'] ==
        before['database']['hashes']['other_catalog'] and
        after['database']['hashes']['business'] ==
        before['database']['hashes']['business'] and
        after['search']['other_documents_sha256'] ==
        before['search']['other_documents_sha256'])
    require((mode == 'positive' and score['score'] == 1.0) or
            (mode == 'wrong-variant' and score['score'] == 0.0 and
             'untouched_variant_changed' in score['failure_codes']) or
            (mode == 'neutral' and neutral_preserved),
            'independent saved-state control did not discriminate')
    result = {'schema': 'envloop-magento-original-gui-control-v1',
              'status': ('neutral_fixture_normalization_development_only'
                         if mode == 'neutral' else
                         'single_control_passed_reset_still_required'),
              'mode': mode, 'task_id': case['task_id'],
              'package_sha256': case['package_sha256'],
              'before_sha256': before_sha, 'after_sha256': after_sha,
              'quote': quote, 'saved': saves, 'score': score,
              'external_requests_blocked': blocked,
              'search_backend': search_host,
              'neutral_preserved_other_business_state':
                  neutral_preserved if mode == 'neutral' else None,
              'model_calls': 0, 'official_final_tasks_admitted': 0,
              'fresh_clone_reset_passed': False}
    write_private(out / 'result.json', result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--http-port', type=int, required=True)
    parser.add_argument('--control-port', type=int, required=True)
    parser.add_argument('--page-id', type=int, required=True)
    parser.add_argument('--search-host', default='127.0.0.1',
                        choices=('127.0.0.1', 'envloop-magento-native-es'))
    parser.add_argument('--mode', choices=('neutral', 'positive', 'wrong-variant'),
                        required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new ignored work/ control output required')
    case = load_case(args.plan, args.plan_sha256, args.task_id)
    try:
        result = asyncio.run(run(case, args.source, args.container,
                                 args.http_port, args.control_port,
                                 args.page_id, args.mode, out,
                                 args.search_host))
        print(json.dumps({'status': result['status'], 'mode': result['mode'],
                          'score': result['score']['score'],
                          'official_final_tasks_admitted': 0}, sort_keys=True))
    except Exception as error:
        print(json.dumps({'status': 'control_failed',
                          'error_type': type(error).__name__,
                          'official_final_tasks_admitted': 0}), file=sys.stderr)
        raise


if __name__ == '__main__':
    main()
