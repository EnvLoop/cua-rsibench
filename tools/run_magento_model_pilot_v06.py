"""Bounded v0.6 model-driven pilot on disposable WebArena Magento task 157.

The trusted host logs in with the pinned public demo account and invokes the
published evaluator. The student receives only the task intent, current masked
screenshot, visible headings/controls, previous action status, and its own
bounded memory through scale_action_contract and scale_vision_proxy. No model
output can select a URL, selector, shell command, API call, or local file.

This is one read-only navigation pilot, not a 100-task qualification or a
backend-mutation reset. Use a fresh --out path for every execution. Provider
uncertainty is unscored and the proxy journal never automatically retries it.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit

from cursibench.scale_action_contract import (
    ContractError, ContractLimits, make_observation, public_receipt as action_receipt,
    render_for_proxy, validate_action,
)
from cursibench.scale_vision_proxy import (
    Limits as VisionLimits, QwenVisionRenderer, TinkerVisionBackend,
    VisionSamplingAdapter, campaign_metadata, public_receipt as sample_receipt,
)

VERSION = 'magento-model-pilot-v0.6'
MAX_ACTIONS = 5
CAMPAIGN_ID = 'magento-base-pilot-v1'
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'work/scale-v06/sources/webarena-verified'
BASE = 'http://localhost:7780/admin'
CONTROL_SELECTOR = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="menuitem"]'
MEASUREMENT_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

_smoke_spec = importlib.util.spec_from_file_location(
    'pinned_magento_smoke', ROOT / 'tools/qualify_magento_navigation_v1.py')
smoke = importlib.util.module_from_spec(_smoke_spec)
_smoke_spec.loader.exec_module(smoke)


class PilotError(RuntimeError):
    """Only fixed failure codes may be written to a public receipt."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def permitted_request(url: str, method: str, *, setup: bool = False) -> bool:
    """No remote origins, URL credentials, service workers, or writes in rollout."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme in ('data', 'blob', 'about'):
            return True  # Browser-local resources, not network requests.
        return (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1')
                and parsed.port == 7780 and parsed.username is None
                and parsed.password is None and (setup or method in MEASUREMENT_METHODS))
    except ValueError:
        return False


def public_url(url: str) -> str:
    """A route hint without URL query, fragment, credentials, or form key."""
    safe = urlsplit(smoke.safe_url(url))
    return urlunsplit((safe.scheme, safe.netloc, safe.path, '', ''))


def sampling_failure_class(subtype: str | None) -> str:
    if isinstance(subtype, str) and (subtype.startswith('provider_') or subtype in (
            'prior_dispatch_uncertain', 'request_transport_error')):
        return 'transport_or_provider_failure'
    return 'environment_failure'


def admit_outcome(policy: dict, official: dict, final_gui: dict,
                  *, blocked: list[dict], business_unchanged: bool) -> dict:
    """Apply pilot safety and loaded-grid gates after exact official scoring."""
    if not business_unchanged:
        return {'status': 'unscored', 'score': None,
                'failure_class': 'environment_failure', 'failure_code': 'business_state_changed'}
    if blocked:
        return {'status': 'unscored', 'score': None,
                'failure_class': 'environment_failure', 'failure_code': 'blocked_network_request'}
    if policy['status'] != 'completed':
        return {'status': 'unscored', 'score': None,
                'failure_class': policy['failure_class'], 'failure_code': policy['failure_code']}
    if official['status'] not in ('success', 'failure') or official['score'] not in (0.0, 1.0):
        return {'status': 'unscored', 'score': None,
                'failure_class': 'verifier_failure', 'failure_code': 'invalid_official_result'}
    if official['score'] == 1.0 and not final_gui['grid_loaded']:
        return {'status': 'completed', 'score': 0.0, 'pilot_task_complete': False,
                'failure_class': 'model_failure', 'failure_code': 'final_grid_not_loaded',
                'qualification_note': 'Published navigation event passed; final customer grid was not loaded.'}
    if official['score'] == 1.0:
        outcome = {'status': 'completed', 'score': 1.0, 'pilot_task_complete': True,
                   'failure_class': None, 'failure_code': None}
        if policy['failure_class'] == 'model_failure':
            outcome['qualification_note'] = (
                'The customer grid was loaded before a later invalid model action; '
                'the achieved task state takes precedence for this navigation pilot.')
        return outcome
    return {'status': 'completed', 'score': 0.0, 'pilot_task_complete': False,
            'failure_class': 'model_failure',
            'failure_code': policy['failure_code'] or 'navigation_target_not_reached'}


async def install_guard(context, *, setup: bool, blocked: list[dict]) -> None:
    async def route_request(route):
        request = route.request
        if permitted_request(request.url, request.method, setup=setup):
            await route.continue_()
        else:
            blocked.append({'method': request.method,
                            'url_sha256': smoke.sha(request.url)})
            await route.abort()

    await context.route('**/*', route_request)
    # HTTP routing does not cover WebSockets. This read-only task needs none.
    async def close_socket(socket):
        await socket.close()

    await context.route_web_socket('**/*', close_socket)


def _short_text(value: str, maximum: int) -> str:
    value = ' '.join(value.split())
    return value[:maximum]


async def _visible_controls(page) -> tuple[list[dict], dict[str, object]]:
    controls: list[dict] = []
    handles: dict[str, object] = {}
    for handle in await page.locator(CONTROL_SELECTOR).element_handles():
        if len(controls) >= 120:
            break
        try:
            if not await handle.is_visible() or not await handle.is_enabled():
                continue
            if await handle.evaluate('(element) => !!element.closest(".admin-user")'):
                continue
            tag = (await handle.evaluate('(element) => element.tagName')).lower()
            role = await handle.get_attribute('role') or {
                'a': 'link', 'button': 'button', 'input': 'textbox',
                'select': 'combobox', 'textarea': 'textbox',
            }.get(tag, 'control')
            role = _short_text(role, 80) or 'control'
            label = (await handle.get_attribute('aria-label')
                     or await handle.inner_text()
                     or await handle.get_attribute('title')
                     or await handle.get_attribute('placeholder')
                     or '')
            label = _short_text(label, 200)
            if not label:
                continue
            ref = f'c{len(controls) + 1:03d}'
            controls.append({'ref': ref, 'role': role,
                             'label': label, 'visible': True, 'enabled': True})
            handles[ref] = handle
        except Exception:
            # A detached element is not current visible evidence.
            continue
    return controls, handles


async def capture_frame(page, *, instruction: str, binding: str, step: int,
                        memory: str, previous: dict | None):
    image = await page.screenshot(type='png', full_page=False, animations='disabled',
                                  mask=[page.locator('.admin-user')])
    controls, handles = await _visible_controls(page)
    headings = []
    for heading in await page.locator('h1, h2').element_handles():
        try:
            if await heading.is_visible():
                headings.append(_short_text(await heading.inner_text(), 200))
        except Exception:
            continue
    observation = make_observation(
        task_id='webarena.shopping_admin.157', task_binding_sha256=binding,
        instruction=instruction, step=step, screenshot_bytes=image,
        a11y_text='Visible headings: ' + '; '.join(headings[:12]),
        dom_text='', controls=controls, previous_action_result=previous,
        memory=memory, limits=ContractLimits(max_step=MAX_ACTIONS),
    )
    return observation, handles, page.url


def _target_xy(target: dict, handles: dict[str, object]):
    if 'x' in target:
        return target['x'], target['y']
    return handles[target['ref']]


async def _point(page, target: dict, handles: dict[str, object]):
    item = _target_xy(target, handles)
    if isinstance(item, tuple):
        return item
    if not await item.is_visible() or not await item.is_enabled():
        raise PilotError('target_not_found')
    box = await item.bounding_box()
    if box is None:
        raise PilotError('target_not_found')
    return box['x'] + box['width'] / 2, box['y'] + box['height'] / 2


async def dispatch_action(page, action: dict, observation, handles: dict[str, object]):
    """The only student-controlled path: bounded Playwright GUI primitives."""
    validate_action(action, observation, current_frame_id=observation.frame_id)
    kind = action['type']
    if kind == 'finish':
        return {'status': 'applied', 'code': 'ok'}
    if kind == 'wait':
        await page.wait_for_timeout(action['duration_ms'])
    elif kind == 'click':
        target = action['target']
        if 'ref' in target:
            handle = handles[target['ref']]
            if not await handle.is_visible() or not await handle.is_enabled():
                return {'status': 'rejected', 'code': 'target_not_found'}
            await handle.click(timeout=15000)
        else:
            await page.mouse.click(target['x'], target['y'])
    elif kind == 'type':
        target = action['target']
        if 'ref' in target:
            handle = handles[target['ref']]
            if not await handle.is_visible() or not await handle.is_enabled():
                return {'status': 'rejected', 'code': 'target_not_found'}
            if action['mode'] == 'fill':
                await handle.fill(action['text'], timeout=15000)
            else:
                await handle.focus()
                await page.keyboard.insert_text(action['text'])
        else:
            await page.mouse.click(target['x'], target['y'])
            if action['mode'] == 'fill':
                await page.keyboard.press('ControlOrMeta+A')
            await page.keyboard.insert_text(action['text'])
    elif kind == 'key':
        if 'target' in action:
            target = action['target']
            if 'ref' in target:
                await handles[target['ref']].focus()
            else:
                await page.mouse.click(target['x'], target['y'])
        await page.keyboard.press(action['key'])
    elif kind == 'scroll':
        if 'target' in action:
            target = action['target']
            if 'ref' in target:
                await handles[target['ref']].hover()
            else:
                await page.mouse.move(target['x'], target['y'])
        await page.mouse.wheel(action['dx'], action['dy'])
    elif kind == 'drag':
        start = await _point(page, action['from'], handles)
        end = await _point(page, action['to'], handles)
        await page.mouse.move(*start)
        await page.mouse.down()
        await page.mouse.move(*end, steps=8)
        await page.mouse.up()
    else:
        raise PilotError('invalid_action')
    if kind in ('click', 'type', 'key', 'drag'):
        try:
            await page.wait_for_load_state('networkidle', timeout=60000)
        except Exception as exc:
            if type(exc).__name__ == 'TimeoutError':
                raise PilotError('action_timeout') from None
            raise
    return {'status': 'applied', 'code': 'ok'}


async def execute_policy(page, adapter, *, instruction: str, binding: str,
                         request_prefix: str):
    """At most five samples and five validated GUI actions, with frame recheck."""
    memory = ''
    previous = None
    action_rows = []
    sample_rows = []
    for step in range(MAX_ACTIONS):
        observation, handles, frame_url = await capture_frame(
            page, instruction=instruction, binding=binding, step=step,
            memory=memory, previous=previous)
        request = render_for_proxy(observation)
        try:
            result = await asyncio.to_thread(adapter.sample,
                request_id=f'{request_prefix}-step-{step}', **request)
        except Exception:
            return {'status': 'unscored', 'failure_class': 'transport_or_provider_failure',
                    'failure_code': 'sampling_transport_uncertain', 'actions': action_rows,
                    'samples': sample_rows}
        if type(result) is not dict:
            return {'status': 'unscored', 'failure_class': 'transport_or_provider_failure',
                    'failure_code': 'sampling_result_invalid', 'actions': action_rows,
                    'samples': sample_rows}
        sample_rows.append(sample_receipt(result))
        if result.get('status') != 'completed' or type(result.get('text')) is not str:
            return {'status': 'unscored',
                    'failure_class': sampling_failure_class(result.get('error_subtype')),
                    'failure_code': result.get('error_subtype') or 'sampling_failed',
                    'actions': action_rows, 'samples': sample_rows}
        # Sampling runs in another thread. Re-observe after it returns so the
        # action cannot be dispatched against a changed page or old frame.
        current_image = await page.screenshot(type='png', full_page=False,
            animations='disabled', mask=[page.locator('.admin-user')])
        if page.url != frame_url or hashlib.sha256(current_image).hexdigest() != observation.screenshot['sha256']:
            return {'status': 'unscored', 'failure_class': 'environment_failure',
                    'failure_code': 'stale_frame', 'actions': action_rows,
                    'samples': sample_rows}
        try:
            action = validate_action(result['text'], observation,
                                     current_frame_id=observation.frame_id)
            # Recheck the same frame immediately before the sole dispatch path.
            validate_action(action, observation, current_frame_id=observation.frame_id)
            previous = await dispatch_action(page, action, observation, handles)
        except ContractError as exc:
            action_rows.append(action_receipt(observation, error=exc))
            return {'status': 'completed', 'failure_class': 'model_failure',
                    'failure_code': exc.code, 'actions': action_rows,
                    'samples': sample_rows}
        except PilotError as exc:
            if exc.code == 'target_not_found':
                previous = {'status': 'rejected', 'code': 'target_not_found'}
            else:
                return {'status': 'unscored', 'failure_class': 'environment_failure',
                        'failure_code': exc.code, 'actions': action_rows,
                        'samples': sample_rows}
        except Exception:
            return {'status': 'unscored', 'failure_class': 'environment_failure',
                    'failure_code': 'gui_dispatch_error', 'actions': action_rows,
                    'samples': sample_rows}
        action_rows.append(action_receipt(observation, action=action))
        memory = action['memory']
        if action['type'] == 'finish':
            break
    return {'status': 'completed', 'failure_class': None, 'failure_code': None,
            'actions': action_rows, 'samples': sample_rows}


async def _login(browser, source: Path):
    credentials = json.loads((source / 'examples/configs/config.example.json').read_text())[
        'environments']['__SHOPPING_ADMIN__']['credentials']
    context = await browser.new_context(service_workers='block')
    blocked = []
    try:
        await install_guard(context, setup=True, blocked=blocked)
        if await context.cookies():
            raise PilotError('nonempty_fresh_context')
        page = await context.new_page()
        await page.goto(BASE, wait_until='domcontentloaded', timeout=90000)
        await page.get_by_label('Username', exact=True).fill(credentials['username'])
        await page.get_by_label('Password', exact=True).fill(credentials['password'])
        await page.get_by_role('button', name='Sign in', exact=True).click()
        await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=90000)
        await page.wait_for_load_state('networkidle', timeout=60000)
        if blocked:
            raise PilotError('setup_blocked_request')
        return await context.storage_state()  # Never persisted or shown to model.
    finally:
        await context.close()


async def _final_gui(page):
    heading = page.get_by_role('heading', name='Customers', exact=True)
    if await heading.count() == 0 or not await heading.is_visible():
        return {'customers_heading': False, 'grid_loaded': False, 'visible_data_rows': 0,
                'url': public_url(page.url)}
    records = page.locator('table.data-grid tbody tr:visible:has(td:nth-child(2))')
    try:
        await records.first.wait_for(state='visible', timeout=90000)
    except Exception:
        pass
    count = await records.count()
    return {'customers_heading': True, 'grid_loaded': count > 1,
            'visible_data_rows': count, 'url': public_url(page.url)}


async def run(source: Path, out: Path, adapter_factory):
    """Preflight, one model attempt, independent exact scoring, private receipt."""
    from playwright.async_api import async_playwright

    source, out = Path(source).resolve(), Path(out).resolve()
    if not out.is_relative_to(ROOT / 'work/scale-v06') or out.exists():
        raise PilotError('invalid_output_path')
    out.mkdir(parents=True, mode=0o700)
    out.chmod(0o700)
    report = {'version': VERSION, 'task_id': 157, 'status': 'unscored',
              'score': None, 'started_at': time.time(), 'max_actions': MAX_ACTIONS,
              'campaign_id': CAMPAIGN_ID,
              'hundred_task_ready': False, 'backend_mutation_reset_qualified': False,
              'auth_state_retained': False, 'raw_har_retained': False}
    try:
        task, source_proof = smoke.source_proof(source)
        smoke.verify_task(task)
        report['source'] = source_proof
        report['container'] = smoke.container_proof()
        before = smoke.business_fingerprint()
        report['business_before_sha256'] = before['sha256']
        binding = smoke.digest({'pilot': VERSION, 'source': source_proof,
                                'task_id': task['task_id'], 'intent': task['intent'],
                                'max_actions': MAX_ACTIONS})
        report['task_binding_sha256'] = binding
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                state = await _login(browser, source)
                with tempfile.TemporaryDirectory(prefix='.private-har-', dir=out) as temporary:
                    raw_path = Path(temporary) / 'network.har'
                    context = await browser.new_context(
                        storage_state=state, viewport={'width': 1440, 'height': 1000},
                        service_workers='block', record_har_path=str(raw_path),
                        record_har_content='omit')
                    blocked = []
                    try:
                        await install_guard(context, setup=False, blocked=blocked)
                        page = await context.new_page()
                        page.set_default_timeout(30000)
                        await page.goto(BASE, wait_until='domcontentloaded', timeout=90000)
                        await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=90000)
                        await page.wait_for_load_state('networkidle', timeout=60000)
                        try:
                            adapter = adapter_factory(out / 'private-journal')
                        except Exception as exc:
                            report['failure_class'] = 'transport_or_provider_failure'
                            report['failure_code'] = (
                                exc.code if isinstance(exc, PilotError) else 'provider_initialization_error')
                            report['blocked_requests'] = blocked
                            return report
                        request_prefix = 'mag157-' + hashlib.sha256(str(out).encode()).hexdigest()[:16]
                        policy = await execute_policy(page, adapter, instruction=task['intent'],
                            binding=binding, request_prefix=request_prefix)
                        report['policy'] = policy
                        report['final_gui'] = await _final_gui(page)
                        report['blocked_requests'] = blocked
                    finally:
                        await context.close()
                    after = smoke.business_fingerprint()
                    report['business_after_sha256'] = after['sha256']
                    report['business_state_unchanged'] = before['sha256'] == after['sha256']
                    if not report['business_state_unchanged']:
                        report['failure_class'] = 'environment_failure'
                        report['failure_code'] = 'business_state_changed'
                    elif blocked:
                        report['failure_class'] = 'environment_failure'
                        report['failure_code'] = 'blocked_network_request'
                    elif policy['status'] != 'completed':
                        report['failure_class'] = policy['failure_class']
                        report['failure_code'] = policy['failure_code']
                    else:
                        raw = json.loads(raw_path.read_text())
                        sanitized = smoke.sanitize_har(raw)
                        clean_path = Path(temporary) / 'network-clean.har'
                        smoke.write(clean_path, sanitized)
                        official = smoke.evaluator(source)
                        raw_score = smoke.evaluate(official, raw_path)
                        clean_score = smoke.evaluate(official, clean_path)
                        if raw_score != clean_score or clean_score['status'] not in ('success', 'failure'):
                            report['failure_class'] = 'verifier_failure'
                            report['failure_code'] = 'evaluator_disagreement'
                        else:
                            report['published_evaluator'] = clean_score
                            report['raw_and_sanitized_evaluator_equal'] = True
                            report['network_entries'] = len(sanitized['log']['entries'])
                            report['sanitized_har_sha256'] = smoke.sha(clean_path.read_bytes())
                            report['loaded_customer_grid'] = report['final_gui']['grid_loaded']
                            report.update(admit_outcome(policy, clean_score,
                                report['final_gui'], blocked=blocked,
                                business_unchanged=report['business_state_unchanged']))
                    report['raw_har_sha256'] = smoke.sha(raw_path.read_bytes())
            finally:
                await browser.close()
    except Exception as exc:
        report['failure_class'] = 'environment_failure'
        report['failure_code'] = exc.code if isinstance(exc, PilotError) else type(exc).__name__
    finally:
        report['finished_at'] = time.time()
        smoke.write(out / 'result.json', report)
    return report


class LiveAdapterFactory:
    def __init__(self):
        self.service = None

    def __call__(self, journal):
        if not os.environ.get('TINKER_API_KEY'):
            raise PilotError('tinker_key_missing')
        import tinker
        renderer = QwenVisionRenderer.load()
        self.service = tinker.ServiceClient(user_metadata=campaign_metadata(CAMPAIGN_ID))
        backend = TinkerVisionBackend.from_service(self.service, renderer)
        return VisionSamplingAdapter(backend, journal, limits=VisionLimits(
            max_actions=MAX_ACTIONS, output_tokens=512, request_timeout_seconds=240))

    def close(self, status):
        if self.service is not None:
            try:
                self.service.close(status).result(timeout=30)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    factory = LiveAdapterFactory()
    try:
        result = asyncio.run(run(args.source, args.out, factory))
        print(json.dumps({key: result.get(key) for key in (
            'version', 'task_id', 'status', 'score', 'pilot_task_complete',
            'failure_class', 'failure_code', 'max_actions')}, sort_keys=True), flush=True)
        raise SystemExit(0 if result['status'] == 'completed' else 2)
    finally:
        factory.close('success' if 'result' in locals() and result['status'] == 'completed' else 'errored')


if __name__ == '__main__':
    main()
