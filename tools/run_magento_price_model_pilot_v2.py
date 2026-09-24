"""Versioned Qwen3.8-27B GUI pilot with neutral visual-progress feedback.

This mutation runner is separate from the pinned read-only task-157 pilot. The
model can choose only one validated visible GUI action per Tinker sample. The
host owns login, local-only routing, the original evaluator, saved-state SQL
and search-index readback, and clone-only reset. Raw frames/model text/HAR stay
under ignored work/; the result is a field-limited private receipt.
"""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import traceback
from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractLimits, make_observation
from cursibench.scale_vision_proxy import (
    Limits as VisionLimits, QwenVisionRenderer, TinkerVisionBackend,
    VisionSamplingAdapter, campaign_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'work/scale-v06/sources/webarena-verified'
BASE = 'http://localhost:7792/admin'
VERSION = 'magento-price777-model-pilot-v2'
CAMPAIGN_ID = 'magento-price777-base-pilot-v2'
MAX_SAMPLES = 84
MAX_GUI_ACTIONS = 80
MAX_STALE_SAMPLES = 4
NO_VISIBLE_PROGRESS_ACTIONS = 3
WALL_SECONDS = 1800
REQUEST_TIMEOUT_SECONDS = 90
MAX_INPUT_TOKENS = 32768
MAX_OUTPUT_TOKENS = 512
PREFILL_USD_PER_M = Decimal('1.86')
SAMPLE_USD_PER_M = Decimal('5.595')
PUBLISHED_RATE_CAP_USD = Decimal('10')
DASHBOARD_TABLE_SELECTOR = (
    'table:not(nav table):not(aside table):not(.admin__menu table)'
    ':not(.admin__menu-wrapper table)'
)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


price = _load(ROOT / 'tools/qualify_magento_variant_price_v1.py', 'magento_price_qualification')
v063 = _load(ROOT / 'tools/run_magento_model_pilot_v063.py', 'pinned_magento_v063')


class PilotError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def sample_reservation_usd():
    return ((Decimal(MAX_INPUT_TOKENS) * PREFILL_USD_PER_M +
             Decimal(MAX_OUTPUT_TOKENS) * SAMPLE_USD_PER_M) / Decimal(1_000_000))


def published_rate_preflight():
    if MAX_SAMPLES < MAX_GUI_ACTIONS + MAX_STALE_SAMPLES:
        raise PilotError('sample_budget_below_action_and_stale_ceiling')
    worst = sample_reservation_usd() * MAX_SAMPLES
    if worst > PUBLISHED_RATE_CAP_USD:
        raise PilotError('published_rate_budget_exceeded')
    return {'max_samples': MAX_SAMPLES, 'max_input_tokens_per_sample': MAX_INPUT_TOKENS,
            'max_output_tokens_per_sample': MAX_OUTPUT_TOKENS,
            'uncached_prefill_usd_per_million': str(PREFILL_USD_PER_M),
            'sample_usd_per_million': str(SAMPLE_USD_PER_M),
            'worst_case_published_rate_reservation_usd': str(worst),
            'published_rate_cap_usd': str(PUBLISHED_RATE_CAP_USD),
            'provider_invoice_known': False}


def validate_clone_redirect(status, location):
    try:
        parsed = urlsplit(location)
        if (status != 302 or parsed.scheme != 'http' or
                parsed.hostname not in ('localhost', '127.0.0.1') or
                parsed.port != 7792 or parsed.path != '/admin' or
                parsed.username or parsed.password):
            raise PilotError('clone_redirect_not_isolated')
    except ValueError:
        raise PilotError('clone_redirect_not_isolated') from None
    return {'status': status, 'location_origin': 'http://localhost:7792'}


def clone_route_preflight():
    response = subprocess.run(['curl', '-sS', '-m', '30', '-D', '-', '-o',
        '/dev/null', 'http://127.0.0.1:7792/admin'], check=True,
        capture_output=True, text=True, timeout=35)
    lines = response.stdout.splitlines()
    statuses = [int(match.group(1)) for line in lines
                if (match := re.match(r'^HTTP/\S+\s+(\d{3})', line))]
    locations = [line.split(':', 1)[1].strip() for line in lines
                 if line.lower().startswith('location:')]
    if len(statuses) != 1 or len(locations) != 1:
        raise PilotError('clone_redirect_not_isolated')
    return validate_clone_redirect(statuses[0], locations[0])


def permitted_request(url, method, *, setup=False):
    try:
        parsed = urlsplit(url)
        if parsed.scheme in ('data', 'blob', 'about'):
            return True
        if not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1')
                and parsed.port == 7792 and not parsed.username and not parsed.password):
            return False
        if setup or method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if method != 'POST':
            return False
        if parsed.path == '/admin/mui/bookmark/save/':
            return True
        ids = '|'.join(str(i) for i in price.TARGETS)
        return bool(re.fullmatch(r'/admin/catalog/product/(?:validate|save)/id/(?:'
                                 + ids + r')/(?:.*)?', parsed.path))
    except ValueError:
        return False


async def install_guard(context, *, setup, blocked):
    async def route_request(route):
        request = route.request
        if permitted_request(request.url, request.method, setup=setup):
            await route.continue_()
        else:
            blocked.append({'method': request.method,
                            'url_sha256': price.sha(request.url)})
            await route.abort()
    await context.route('**/*', route_request)
    async def close_socket(socket):
        await socket.close()
    await context.route_web_socket('**/*', close_socket)


class VisualProgress:
    """Report only what a prior GUI action changed in the observed viewport.

    No application state, task answer, or DOM event handler is consulted. A
    matching screenshot is evidence of no *visible* progress, not proof that
    the application did nothing.
    """

    def __init__(self):
        self.pending = None
        self.last_signature = None
        self.same_action_streak = 0
        self.current = None

    @staticmethod
    def signature(action):
        return json.dumps({key: value for key, value in action.items()
                           if key not in ('memory', 'version', 'task_id',
                                          'task_binding_sha256', 'step', 'frame_id')},
                          sort_keys=True, separators=(',', ':'))

    def dispatched(self, action, observation, url_before, result):
        if result.get('status') != 'applied':
            self.pending = None
            self.last_signature = None
            self.same_action_streak = 0
            return
        target = action.get('target')
        self.pending = {'signature': self.signature(action),
                        'type': action['type'],
                        'target': target if isinstance(target, dict) else None,
                        'screenshot_sha256': observation.screenshot['sha256'],
                        'url_before': url_before}

    def observed(self, image, url, previous):
        if previous is None:
            self.current = None
            return
        if self.pending is None:
            # A confirmation capture may be followed by the next model frame.
            # Keep that observed feedback until another action is dispatched.
            return
        self.current = None
        pending, self.pending = self.pending, None
        same_view = (hashlib.sha256(image).hexdigest() ==
                     pending['screenshot_sha256'] and url == pending['url_before'])
        if same_view:
            self.same_action_streak = (self.same_action_streak + 1
                if pending['signature'] == self.last_signature else 1)
            self.last_signature = pending['signature']
        else:
            self.same_action_streak = 0
            self.last_signature = None
        self.current = {
            'previous_gui_action': pending['type'],
            'previous_target': pending['target'],
            'screenshot_and_url_unchanged': same_view,
            'consecutive_identical_actions_without_visible_change':
                self.same_action_streak,
            'scope': 'Screenshot pixels and page URL only; no claim about saved state',
        }

    def third_identical_action_pending(self):
        """A final observation can now confirm or refute a third no-op."""
        return (self.pending is not None and
                self.same_action_streak == NO_VISIBLE_PROGRESS_ACTIONS - 1 and
                self.pending['signature'] == self.last_signature)


def render_for_model(observation, feedback=None):
    rendered = v063.render_for_model(observation)
    payload = json.loads(rendered['instruction'])
    contract = payload['contract']
    if any(fragment not in contract for fragment in
           ('five applied GUI actions', 'seven samples', 'two such discards')):
        raise PilotError('pinned_model_contract_changed')
    payload['contract'] = (contract.replace('five applied GUI actions',
                                            f'{MAX_GUI_ACTIONS} applied GUI actions')
                           .replace('seven samples', f'{MAX_SAMPLES} samples')
                           .replace('two such discards',
                                    f'{MAX_STALE_SAMPLES} such discards'))
    payload['contract'] += (
        ' The host may report whether the previous GUI action changed the '
        'screenshot or URL. Repeated identical actions with unchanged pixels '
        'should prompt reconsideration of the visible controls or allowed '
        'keyboard actions. A filled input may require an Enter key action or '
        'a visible submit control; clicking the same input again only focuses '
        'it. After three identical applied actions with no screenshot or URL '
        'change, the host stops and scores the resulting state. The host never '
        'chooses an action for you.')
    payload['visual_progress'] = feedback.current if feedback else None
    rendered['instruction'] = json.dumps(payload, ensure_ascii=False,
                                          sort_keys=True, separators=(',', ':'))
    return rendered


class BudgetedAdapter:
    """Reserve maximum published-rate tokens before every possible dispatch."""
    def __init__(self, adapter, *, deadline):
        self.adapter = adapter
        self.deadline = deadline
        self.attempt_count = 0

    def sample(self, *, request_id, **request):
        if time.monotonic() + REQUEST_TIMEOUT_SECONDS >= self.deadline:
            return self.adapter.failure(request_id, 'wall_clock_budget')
        if self.attempt_count >= MAX_SAMPLES or (
                sample_reservation_usd() * (self.attempt_count + 1) >
                PUBLISHED_RATE_CAP_USD):
            return self.adapter.failure(request_id, 'published_rate_budget')
        self.attempt_count += 1
        return self.adapter.sample(request_id=request_id, **request)

    @property
    def reserved_usd(self):
        return str(sample_reservation_usd() * self.attempt_count)


def summarize_usage(policy, budget_adapter):
    samples = policy.get('samples', []) if isinstance(policy, dict) else []
    rendered_in = 0
    sampled_out = 0
    missing_usage = 0
    for row in samples:
        usage = row.get('usage') or {}
        if type(usage.get('input_tokens')) is int:
            rendered_in += usage['input_tokens']
        else:
            missing_usage += 1
        if type(usage.get('output_tokens')) is int:
            sampled_out += usage['output_tokens']
        else:
            missing_usage += 1
    if budget_adapter.attempt_count > len(samples):
        missing_usage += budget_adapter.attempt_count - len(samples)
    estimate = ((Decimal(rendered_in) * PREFILL_USD_PER_M +
                 Decimal(sampled_out) * SAMPLE_USD_PER_M) / Decimal(1_000_000))
    return {'rendered_multimodal_input_tokens': rendered_in,
            'sampled_output_tokens': sampled_out,
            'missing_usage_fields': missing_usage,
            'published_rate_subtotal_usd': str(estimate) if not missing_usage else None,
            'reserved_maximum_published_rate_usd': budget_adapter.reserved_usd,
            'provider_billed_tokens_known': False, 'provider_invoice_usd_known': False,
            'basis': 'rendered and returned token lengths, not provider billing'}


def entity_rows(snapshot, entity_id):
    return {table: [row for row in rows if int(row[
        'product_id' if table == 'cataloginventory_stock_item' else 'entity_id']) == entity_id]
            for table, rows in snapshot['selected'].items()}


def state_summary(before, after):
    old, new = price.prices(before), price.prices(after)
    target_hits = [key for key in price.TARGETS
                   if float(old[key]) == 52.0 and float(new[key]) == 47.0]
    wrong_unchanged = (old[112] == new[112] and
                       entity_rows(before, 112) == entity_rows(after, 112))
    return {'target_47_count': len(target_hits),
            'target_ids_at_47': target_hits,
            'wrong_color_unchanged': wrong_unchanged,
            'positive_state_pass': len(target_hits) == 5 and wrong_unchanged,
            'target_prices': {str(key): new[key] for key in price.TARGETS},
            'wrong_color_price': new[112]}


def admit_scored_result(policy, official, state_result, *, blocked,
                        evaluator_equal):
    """Keep infrastructure failures unscored and model terminals scorable."""
    if blocked or not evaluator_equal:
        return {'status': 'unscored', 'score': None,
                'failure_class': 'environment_failure',
                'failure_code': 'blocked_or_evaluator_disagreement'}
    if policy['status'] != 'completed':
        return {'status': 'unscored', 'score': None,
                'failure_class': policy['failure_class'],
                'failure_code': policy['failure_code']}
    if official['status'] not in ('success', 'failure') or official['score'] not in (0.0, 1.0):
        return {'status': 'unscored', 'score': None,
                'failure_class': 'verifier_failure',
                'failure_code': 'invalid_official_result'}
    success = official['score'] == 1.0 and state_result['positive_state_pass']
    if success:
        return {'status': 'completed', 'score': 1.0,
                'pilot_task_complete': True}
    return {'status': 'completed', 'score': 0.0,
            'pilot_task_complete': False,
            'failure_class': 'model_failure',
            'failure_code': (policy.get('failure_code')
                             if policy.get('failure_class') == 'model_failure'
                             else None) or 'requested_prices_not_all_persisted'}


async def login(browser, source, blocked):
    credentials = json.loads((source / 'examples/configs/config.example.json').read_text())[
        'environments']['__SHOPPING_ADMIN__']['credentials']
    context = await browser.new_context(service_workers='block')
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
        if blocked:
            raise PilotError('setup_blocked_request')
        return await context.storage_state()
    finally:
        await context.close()


def should_mask_dashboard_tables(page):
    """Limit table redaction to the Magento Dashboard route, not product grids."""
    path = urlsplit(page.url).path
    return (path.rstrip('/') == '/admin' or
            re.fullmatch(r'/admin/admin/dashboard(?:/.*)?', path) is not None)


def screenshot_masks(page):
    masks = [page.locator('.admin-user')]
    if should_mask_dashboard_tables(page):
        masks.append(page.locator(DASHBOARD_TABLE_SELECTOR))
    return masks


async def screenshot_for_observation(page):
    """Use the exact same privacy mask for model frames and stale checks."""
    return await page.screenshot(type='png', full_page=False,
                                 animations='disabled', mask=screenshot_masks(page))


async def inside_masked_dashboard_table(page, element):
    return should_mask_dashboard_tables(page) and await element.evaluate(
        '(node, selector) => !!node.closest("table")?.matches(selector)',
        DASHBOARD_TABLE_SELECTOR)


async def _same_pixels(page, observation, frame_url):
    if page.url != frame_url:
        return False, 'unexpected_navigation_during_sampling'
    image = await screenshot_for_observation(page)
    if hashlib.sha256(image).hexdigest() != observation.screenshot['sha256']:
        return False, 'pixels_changed'
    return True, None


async def viewport_controls(page):
    """Expose controls whose screenshot center is inside the viewport and clickable."""
    viewport = page.viewport_size or {'width': 1440, 'height': 1000}
    controls, handles = [], {}
    for handle in await page.locator(v063.host.CONTROL_SELECTOR).element_handles():
        if len(controls) >= 120:
            break
        try:
            if not await handle.is_visible() or not await handle.is_enabled():
                continue
            if await handle.evaluate('(element) => !!element.closest(".admin-user")'):
                continue
            if await inside_masked_dashboard_table(page, handle):
                continue
            box = await handle.bounding_box()
            if box is None:
                continue
            center_x = box['x'] + box['width'] / 2
            center_y = box['y'] + box['height'] / 2
            if not (0 <= center_x < viewport['width'] and
                    0 <= center_y < viewport['height']):
                continue
            # is_visible() does not account for a menu scrim or another
            # element intercepting pointer events above this control. The
            # advertised ref must be the element a center click can reach.
            if not await handle.evaluate('''(element, point) => {
                const hit = document.elementFromPoint(point.x, point.y);
                return hit !== null && (hit === element || element.contains(hit));
            }''', {'x': center_x, 'y': center_y}):
                continue
            tag = (await handle.evaluate('(element) => element.tagName')).lower()
            input_type = (await handle.get_attribute('type') or '').lower() if tag == 'input' else ''
            role = await handle.get_attribute('role') or {
                'a': 'link', 'button': 'button',
                'input': ('button' if input_type in ('button', 'submit', 'reset')
                          else 'searchbox' if input_type == 'search' else 'textbox'),
                'select': 'combobox', 'textarea': 'textbox',
            }.get(tag, 'control')
            label = (await handle.get_attribute('aria-label')
                     or await handle.inner_text()
                     or await handle.get_attribute('title')
                     or await handle.get_attribute('placeholder')
                     or await handle.get_attribute('alt')
                     or (await handle.get_attribute('value')
                         if tag == 'button' or input_type in
                            ('button', 'submit', 'reset') else None)
                     or '')
            label = v063.host._short_text(label, 200)
            if not label and (tag == 'button' or role in
                              ('button', 'link', 'menuitem')):
                # Icon-only controls still have a visible location in the
                # screenshot. Do not infer a purpose from CSS or hidden DOM.
                label = (f'Unlabeled {role} at screenshot '
                         f'({round(center_x)}, {round(center_y)})')
            if not label:
                continue
            ref = f'c{len(controls) + 1:03d}'
            controls.append({'ref': ref, 'role': v063.host._short_text(role, 80),
                             'label': label, 'visible': True, 'enabled': True})
            handles[ref] = handle
        except Exception:
            continue
    return controls, handles


def make_capture(frames, feedback):
    count = 0
    async def capture(page, *, instruction, binding, step, memory, previous):
        nonlocal count
        try:
            await page.wait_for_load_state('networkidle', timeout=20000)
        except Exception:
            pass  # Pixel/ref checks still fail closed if the page changes.
        await page.wait_for_timeout(350)
        image = await screenshot_for_observation(page)
        feedback.observed(image, page.url, previous)
        count += 1
        path = frames / f'frame-{count:03d}-step-{step:02d}.png'
        path.write_bytes(image)
        path.chmod(0o600)
        controls, handles = await v063.host._visible_controls(page)
        headings = []
        for heading in await page.locator('h1, h2').element_handles():
            try:
                if await heading.is_visible() and not await inside_masked_dashboard_table(
                        page, heading):
                    headings.append(v063.host._short_text(await heading.inner_text(), 200))
            except Exception:
                continue
        observation = make_observation(
            task_id='webarena.shopping_admin.777', task_binding_sha256=binding,
            instruction=instruction, step=step, screenshot_bytes=image,
            a11y_text='Visible headings: ' + '; '.join(headings[:12]),
            dom_text='', controls=controls, previous_action_result=previous,
            memory=memory, limits=ContractLimits(max_step=MAX_GUI_ACTIONS))
        return observation, handles, page.url
    return capture


async def execute_scored_policy(page, adapter, *, instruction, binding,
                                request_prefix, feedback):
    """v063 action protocol with a v2-only, observed model-failure terminal.

    Keep the pinned v063 runner unchanged. A third identical applied action is
    checked with a fresh screenshot/URL before any further model sample. The
    local loop owns the receipts, so stopping retains exact sample/action
    counts instead of reconstructing them from a raised exception.
    """
    memory = ''
    previous = None
    actions = []
    samples = []
    stale_reasons = []
    applied_count = 0

    def outcome(status, failure_class=None, failure_code=None):
        return {
            'status': status, 'failure_class': failure_class,
            'failure_code': failure_code, 'actions': actions, 'samples': samples,
            'action_attempt_count': len(actions),
            'applied_action_count': applied_count,
            'sample_attempt_count': len(samples),
            'stale_sample_count': len(stale_reasons),
            'stale_reasons': list(stale_reasons),
            'max_gui_actions': MAX_GUI_ACTIONS,
            'max_samples': MAX_SAMPLES,
            'max_stale_samples': MAX_STALE_SAMPLES,
        }

    async def discard_stale(reason):
        stale_reasons.append(reason)
        samples[-1]['discarded_as_stale'] = True
        samples[-1]['stale_reason'] = reason
        if reason == 'unexpected_navigation_during_sampling':
            return outcome('unscored', 'environment_failure', reason)
        if len(stale_reasons) > MAX_STALE_SAMPLES:
            return outcome('unscored', 'environment_failure',
                           'stale_sample_budget_exhausted')
        return None

    while len(actions) < MAX_GUI_ACTIONS and len(samples) < MAX_SAMPLES:
        step = len(actions)
        sample_index = len(samples)
        observation, handles, frame_url = await v063.host.capture_frame(
            page, instruction=instruction, binding=binding, step=step,
            memory=memory, previous=previous)
        request = v063.host.render_for_proxy(observation)
        request_id = f'{request_prefix}-sample-{sample_index}-step-{step}'
        try:
            result = await asyncio.to_thread(adapter.sample,
                                             request_id=request_id, **request)
        except Exception:
            return outcome('unscored', 'transport_or_provider_failure',
                           'sampling_transport_uncertain')
        if type(result) is not dict:
            return outcome('unscored', 'transport_or_provider_failure',
                           'sampling_result_invalid')
        samples.append(v063.host.sample_receipt(result))
        if result.get('status') != 'completed' or type(result.get('text')) is not str:
            return outcome('unscored',
                           v063.host.sampling_failure_class(result.get('error_subtype')),
                           result.get('error_subtype') or 'sampling_failed')

        same, reason = await _same_pixels(page, observation, frame_url)
        if not same:
            decision = await discard_stale(reason)
            if decision is not None:
                return decision
            continue
        try:
            action = v063.host.validate_action(result['text'], observation,
                current_frame_id=observation.frame_id)
        except v063.host.ContractError as exc:
            actions.append(v063.host.action_receipt(observation, error=exc))
            return outcome('completed', 'model_failure', exc.code)

        if not await v063._same_visible_refs(page, action, observation, handles):
            decision = await discard_stale('ref_identity_changed')
            if decision is not None:
                return decision
            continue
        same, reason = await _same_pixels(page, observation, frame_url)
        if not same:
            decision = await discard_stale(reason)
            if decision is not None:
                return decision
            continue
        try:
            v063.host.validate_action(action, observation,
                                     current_frame_id=observation.frame_id)
            previous = await v063.host.dispatch_action(page, action,
                                                       observation, handles)
        except v063.host.ContractError as exc:
            actions.append(v063.host.action_receipt(observation, error=exc))
            return outcome('completed', 'model_failure', exc.code)
        except v063.host.PilotError as exc:
            if exc.code == 'target_not_found':
                previous = {'status': 'rejected', 'code': 'target_not_found'}
            else:
                return outcome('unscored', 'environment_failure', exc.code)
        except Exception:
            return outcome('unscored', 'environment_failure', 'gui_dispatch_error')
        actions.append(v063.host.action_receipt(observation, action=action))
        if previous['status'] == 'applied':
            applied_count += 1
        memory = action['memory']
        if action['type'] == 'finish':
            return outcome('completed')

        # A post-action observation is needed even when this was action 80.
        # It consumes neither another model sample nor another GUI action.
        if feedback.third_identical_action_pending():
            await v063.host.capture_frame(
                page, instruction=instruction, binding=binding,
                step=len(actions), memory=memory, previous=previous)
            if feedback.same_action_streak >= NO_VISIBLE_PROGRESS_ACTIONS:
                return outcome('completed', 'model_failure', 'no_visible_progress')
    if len(actions) >= MAX_GUI_ACTIONS:
        return outcome('completed', 'model_failure', 'action_budget_exhausted')
    return outcome('unscored', 'environment_failure', 'sample_budget_exhausted')


async def execute_policy(page, adapter, *, instruction, binding, prefix, frames,
                         deadline):
    feedback = VisualProgress()
    saved = (v063.MAX_GUI_ACTIONS, v063.MAX_SAMPLES, v063.MAX_STALE_SAMPLES,
             v063.host.MAX_ACTIONS, v063.host.capture_frame,
             v063.host.render_for_proxy, v063.host._visible_controls,
             v063.host.dispatch_action)
    v063.MAX_GUI_ACTIONS, v063.MAX_SAMPLES = MAX_GUI_ACTIONS, MAX_SAMPLES
    v063.MAX_STALE_SAMPLES = MAX_STALE_SAMPLES
    v063.host.MAX_ACTIONS = MAX_GUI_ACTIONS
    v063.host.capture_frame = make_capture(frames, feedback)
    v063.host.render_for_proxy = lambda observation: render_for_model(
        observation, feedback)
    v063.host._visible_controls = viewport_controls
    original_dispatch = v063.host.dispatch_action
    async def logged_dispatch(page, action, observation, handles):
        url_before = page.url
        try:
            result = await original_dispatch(page, action, observation, handles)
            feedback.dispatched(action, observation, url_before, result)
            return result
        except Exception as exc:
            path = frames.parent / 'private-dispatch-errors.jsonl'
            with path.open('a') as stream:
                stream.write(json.dumps({'type': type(exc).__name__,
                    'step': observation.step, 'action_type': action.get('type'),
                    'traceback': traceback.format_exc()}) + '\n')
            path.chmod(0o600)
            raise
    v063.host.dispatch_action = logged_dispatch
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PilotError('wall_clock_budget')
        return await asyncio.wait_for(execute_scored_policy(
            page, adapter, instruction=instruction, binding=binding,
            request_prefix=prefix, feedback=feedback), timeout=remaining)
    finally:
        (v063.MAX_GUI_ACTIONS, v063.MAX_SAMPLES, v063.MAX_STALE_SAMPLES,
         v063.host.MAX_ACTIONS, v063.host.capture_frame,
         v063.host.render_for_proxy, v063.host._visible_controls,
         v063.host.dispatch_action) = saved


class LiveAdapterFactory:
    def __init__(self):
        self.service = None

    def __call__(self, journal, *, deadline):
        if not os.environ.get('TINKER_API_KEY'):
            raise PilotError('tinker_key_missing')
        import tinker
        renderer = QwenVisionRenderer.load()
        self.service = tinker.ServiceClient(
            user_metadata=campaign_metadata(CAMPAIGN_ID))
        backend = TinkerVisionBackend.from_service(self.service, renderer)
        adapter = VisionSamplingAdapter(backend, journal, limits=VisionLimits(
            max_actions=MAX_SAMPLES, input_tokens=MAX_INPUT_TOKENS,
            output_tokens=MAX_OUTPUT_TOKENS,
            request_timeout_seconds=REQUEST_TIMEOUT_SECONDS))
        return BudgetedAdapter(adapter, deadline=deadline)

    def close(self, status):
        if self.service is not None:
            try:
                self.service.close(status).result(timeout=30)
            except Exception:
                pass


async def run(source, out, adapter_factory):
    from playwright.async_api import async_playwright
    source, out = Path(source).resolve(), Path(out).resolve()
    if not out.is_relative_to(ROOT / 'work/scale-v06') or out.exists():
        raise PilotError('invalid_output_path')
    out.mkdir(parents=True, mode=0o700)
    out.chmod(0o700)
    frames = out / 'private-frames'
    frames.mkdir(mode=0o700)
    started = time.monotonic()
    deadline = started + WALL_SECONDS
    report = {'version': VERSION, 'task_id': 777, 'model': 'Qwen/Qwen3.8-27B',
              'model_kind': 'base', 'training_or_checkpoint_used': False,
              'started_at': time.time(), 'max_samples': MAX_SAMPLES,
              'max_gui_actions': MAX_GUI_ACTIONS, 'wall_limit_seconds': WALL_SECONDS,
              'scored_model_terminal_rule': {
                  'code': 'no_visible_progress',
                  'identical_applied_action_threshold': NO_VISIBLE_PROGRESS_ACTIONS,
                  'observation': 'unchanged screenshot pixels and page URL',
                  'verifier_and_reset_required': True},
              'campaign_id': CAMPAIGN_ID, 'status': 'unscored', 'score': None,
              'hundred_task_ready': False, 'official_final_task_count': 0,
              'auth_state_retained': False, 'raw_har_retained': False,
              'published_rate_budget': published_rate_preflight()}
    before = None
    search_before = None
    budget_adapter = None
    try:
        if not os.environ.get('TINKER_API_KEY'):
            raise PilotError('tinker_key_missing')
        task, source_info = price.source_proof(source)
        report['source'] = source_info
        report['container'] = price.container_proof()
        report['clone_route'] = clone_route_preflight()
        report['search_health'] = price.search_health()
        before = price.read_db()
        search_before = price.read_search_index()
        report['sql_before'] = price.public_db(before)
        report['search_before'] = search_before
        if not all(float(price.prices(before)[key]) == 52.0 for key in (*price.TARGETS, *price.WRONG)):
            raise PilotError('baseline_price_changed')
        if float(search_before['parent_price_0_1']) != 52.0:
            raise PilotError('baseline_search_price_changed')
        binding = price.digest({'version': VERSION, 'source': source_info,
            'task_id': 777, 'intent': task['intent'], 'max_samples': MAX_SAMPLES,
            'max_gui_actions': MAX_GUI_ACTIONS,
            'no_visible_progress_actions': NO_VISIBLE_PROGRESS_ACTIONS})
        report['task_binding_sha256'] = binding
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                setup_blocked = []
                state = await login(browser, source, setup_blocked)
                with tempfile.TemporaryDirectory(prefix='.private-har-', dir=out) as temp:
                    raw_path = Path(temp) / 'network.har'
                    context = await browser.new_context(storage_state=state,
                        viewport={'width': 1440, 'height': 1000},
                        service_workers='block', record_har_path=str(raw_path),
                        record_har_content='embed')
                    blocked = []
                    try:
                        await install_guard(context, setup=False, blocked=blocked)
                        page = await context.new_page()
                        page.set_default_timeout(30000)
                        await page.goto(BASE, wait_until='domcontentloaded', timeout=90000)
                        await page.get_by_role('heading', name='Dashboard', exact=True).wait_for(timeout=90000)
                        budget_adapter = adapter_factory(out / 'private-journal',
                                                         deadline=deadline)
                        prefix = 'mag777-' + hashlib.sha256(str(out).encode()).hexdigest()[:16]
                        try:
                            report['policy'] = await execute_policy(page, budget_adapter,
                                instruction=task['intent'], binding=binding,
                                prefix=prefix, frames=frames, deadline=deadline)
                        except asyncio.TimeoutError:
                            report['policy'] = {'status': 'unscored',
                                'failure_class': 'environment_failure',
                                'failure_code': 'wall_clock_budget',
                                'samples': [], 'actions': []}
                        report['final_url_path'] = urlsplit(page.url).path
                        report['blocked_requests'] = blocked
                    finally:
                        await context.close()
                    report['raw_har_sha256'] = price.sha(raw_path.read_bytes())
                    raw = json.loads(raw_path.read_text())
                    sanitized = price.sanitize_har(raw)
                    clean_path = out / 'private-sanitized-network.har'
                    price.write_new(clean_path, sanitized)
                    official = price.evaluator(source)
                    raw_score = price.evaluate(official, raw_path)
                    clean_score = price.evaluate(official, clean_path)
                    report['published_evaluator_raw'] = raw_score
                    report['published_evaluator_sanitized'] = clean_score
                    report['raw_and_sanitized_evaluator_equal'] = raw_score == clean_score
                    report['sanitized_har_sha256'] = price.sha(clean_path.read_bytes())
            finally:
                await browser.close()
        after = price.read_db()
        search_after = price.read_search_index()
        report['sql_after'] = price.public_db(after)
        report['search_after'] = search_after
        state_result = state_summary(before, after)
        report['independent_state'] = state_result
        report['usage'] = summarize_usage(report.get('policy'), budget_adapter)
        if state_result['positive_state_pass']:
            price.validate_positive(before, after)
        policy = report['policy']
        official = report['published_evaluator_sanitized']
        report.update(admit_scored_result(policy, official, state_result,
            blocked=blocked,
            evaluator_equal=report['raw_and_sanitized_evaluator_equal']))
        report['official_network_score_diagnostic'] = official['score']
    except Exception as exc:
        report['failure_class'] = ('environment_failure' if isinstance(exc, PilotError)
                                   else 'transport_or_environment_failure')
        report['failure_code'] = exc.code if isinstance(exc, PilotError) else type(exc).__name__
    finally:
        if budget_adapter is not None and 'usage' not in report:
            report['usage'] = summarize_usage(report.get('policy'), budget_adapter)
        if before is not None:
            try:
                price.restore_rows(before)
                if search_before is not None:
                    price.reindex_search()
                restored = price.read_db()
                price.validate_reset(before, restored)
                report['sql_restored'] = price.public_db(restored)
                if search_before is not None:
                    search_restored = price.read_search_index()
                    price.validate_search_reset(search_before, search_restored)
                    report['search_restored'] = search_restored
                report['final_monitored_reset_verified'] = True
            except Exception as exc:
                report['final_monitored_reset_verified'] = False
                report['reset_error_type'] = type(exc).__name__
                report['status'] = 'unscored'
                report['score'] = None
        report['elapsed_seconds'] = time.monotonic() - started
        report['finished_at'] = time.time()
        price.write_new(out / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    factory = LiveAdapterFactory()
    try:
        result = asyncio.run(run(args.source, args.out, factory))
        print(json.dumps({key: result.get(key) for key in
            ('version', 'task_id', 'status', 'score', 'failure_class',
             'failure_code', 'final_monitored_reset_verified', 'elapsed_seconds')},
            sort_keys=True), flush=True)
        raise SystemExit(0 if result['status'] == 'completed' else 2)
    finally:
        factory.close('success' if 'result' in locals() and result['status'] == 'completed' else 'errored')


if __name__ == '__main__':
    main()
