"""Common current-screen recorder for train-only Magento GUI demonstrations.

The deterministic teacher reads the published task and selects visible GUI
targets. Its output goes through the same strict normalized action boundary as
the Qwen pilot, then through browser primitives. Screenshots and controls are
captured before every action. All raw evidence remains in ignored work/.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from cursibench.gui_sft_data_v1 import MAX_ACTIONS, json_text, sha256
from cursibench.scale_action_contract import ContractLimits, make_observation
from cursibench.scale_action_output_v062 import normalize_model_action


ROOT = Path(__file__).resolve().parents[1]
CONTAINER = 'cua-v06-magento-sft777'
BASE = 'http://localhost:7790/admin'
PORTS = (7790, 7791)
MAX_STABLE_ATTEMPTS = 6
DASHBOARD_TABLE_SELECTOR = 'table:not(nav table):not(aside table):not(.admin__menu table)'


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


order = _load(ROOT / 'tools/qualify_magento_order_address_v1.py', 'magento_address_qualifier')
host = _load(ROOT / 'tools/run_magento_model_pilot_v06.py', 'magento_gui_dispatch_host')
order.CONTAINER = CONTAINER


def write_private(path: Path, value) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')
    path.chmod(0o600)


def require(ok, code: str):
    if not ok:
        raise RuntimeError(code)


def clone_preflight() -> dict:
    proof = order.container_proof()
    require(proof['name'] == CONTAINER and proof['local_ports'] == list(PORTS),
            'clone_identity_mismatch')
    base = subprocess.run(['docker', '--context', order.CONTEXT, 'exec',
                           '-w', '/var/www/magento2', CONTAINER, 'php', 'bin/magento',
                           'config:show', 'web/unsecure/base_url'],
                          check=True, capture_output=True, text=True, timeout=90).stdout.strip()
    require(base == 'http://localhost:7790/', 'clone_base_url_mismatch')
    response = subprocess.run(['curl', '-sS', '--max-time', '30', '-D', '-', '-o',
                               '/dev/null', 'http://127.0.0.1:7790/admin'],
                              check=True, capture_output=True, text=True, timeout=35).stdout
    status = re.findall(r'^HTTP/\S+\s+(\d{3})', response, flags=re.M)
    locations = re.findall(r'^Location:\s*(\S+)', response, flags=re.I | re.M)
    require(status == ['302'] and len(locations) == 1, 'clone_redirect_invalid')
    redirect = urlsplit(locations[0])
    require(redirect.scheme == 'http' and redirect.hostname == 'localhost' and
            redirect.port == 7790 and redirect.path == '/admin',
            'clone_redirect_not_isolated')
    return {'image_sha256': proof['image_sha256'],
            'container_id_sha256': proof['container_id_sha256'],
            'loopback_ports': list(PORTS), 'mounts': proof['mounts'],
            'base_url_isolated': True}


def _short(text: str, maximum=200) -> str:
    return ' '.join(text.split())[:maximum]


async def visible_controls(page):
    """Expose current, enabled, viewport-hittable controls only."""
    viewport = page.viewport_size or {'width': 1440, 'height': 1000}
    controls, handles = [], {}
    for handle in await page.locator(host.CONTROL_SELECTOR).element_handles():
        if len(controls) >= 120:
            break
        try:
            if not await handle.is_visible() or not await handle.is_enabled() or \
                    await handle.evaluate('(e) => !!e.closest(".admin-user")'):
                continue
            box = await handle.bounding_box()
            if box is None:
                continue
            x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
            if not (0 <= x < viewport['width'] and 0 <= y < viewport['height']):
                continue
            if not await handle.evaluate('''(e, p) => {
                const hit = document.elementFromPoint(p.x, p.y);
                return hit === e || (hit !== null && e.contains(hit));
            }''', {'x': x, 'y': y}):
                continue
            tag = (await handle.evaluate('(e) => e.tagName')).lower()
            role = await handle.get_attribute('role') or {
                'a': 'link', 'button': 'button', 'input': 'textbox',
                'select': 'combobox', 'textarea': 'textbox'}.get(tag, 'control')
            label = (await handle.get_attribute('aria-label') or
                     await handle.inner_text() or await handle.get_attribute('title') or
                     await handle.get_attribute('placeholder') or
                     await handle.evaluate('(e) => e.labels?.[0]?.innerText || ""') or '')
            label = _short(label)
            if not label:
                label = f'Unlabeled {role} at screenshot ({round(x)}, {round(y)})'
            ref = f'c{len(controls) + 1:03d}'
            controls.append({'ref': ref, 'role': _short(role, 80), 'label': label,
                             'visible': True, 'enabled': True})
            handles[ref] = handle
        except Exception:
            continue
    return controls, handles


async def screenshot(page) -> bytes:
    path = urlsplit(page.url).path
    masks = [page.locator('.admin-user')]
    if path.rstrip('/') == '/admin' or re.fullmatch(r'/admin/admin/dashboard(?:/.*)?', path):
        masks.append(page.locator(DASHBOARD_TABLE_SELECTOR))
    return await page.screenshot(type='png', full_page=False, caret='hide',
                                 animations='disabled', mask=masks)


async def capture(page, *, task_id, task_intent, binding, step, memory, previous):
    for _ in range(MAX_STABLE_ATTEMPTS):
        try:
            await page.wait_for_load_state('networkidle', timeout=20_000)
        except Exception:
            pass
        url = page.url
        first = await screenshot(page)
        await page.wait_for_timeout(250)
        second = await screenshot(page)
        if first != second or page.url != url:
            continue
        controls, handles = await visible_controls(page)
        headings = []
        for item in await page.locator('h1, h2').element_handles():
            if await item.is_visible():
                headings.append(_short(await item.inner_text()))
        final = await screenshot(page)
        if final != second or page.url != url:
            continue
        observation = make_observation(
            task_id=f'webarena.shopping_admin.{task_id}', task_binding_sha256=binding,
            instruction=task_intent, step=step, screenshot_bytes=final,
            a11y_text='Visible headings: ' + '; '.join(headings[:12]),
            dom_text='', controls=controls, previous_action_result=previous,
            memory=memory, limits=ContractLimits(max_step=MAX_ACTIONS))
        return observation, handles, url
    raise RuntimeError('unstable_current_frame')


async def target_for(page, locator, handles, *, prefer_coordinate=False):
    element = await locator.element_handle(timeout=45_000)
    require(element is not None and await element.is_visible() and await element.is_enabled(),
            'teacher_target_not_visible')
    if not prefer_coordinate:
        for ref, handle in handles.items():
            if await handle.evaluate('(e, candidate) => e === candidate', element):
                return {'ref': ref}
    box = await element.bounding_box()
    require(box is not None, 'teacher_target_outside_viewport')
    x, y = round(box['x'] + box['width'] / 2), round(box['y'] + box['height'] / 2)
    viewport = page.viewport_size or {'width': 1440, 'height': 1000}
    require(0 <= x < viewport['width'] and 0 <= y < viewport['height'],
            'teacher_target_outside_viewport')
    require(await element.evaluate('''(e, p) => {
        const hit = document.elementFromPoint(p.x, p.y);
        return hit === e || (hit !== null && e.contains(hit));
    }''', {'x': x, 'y': y}), 'teacher_target_obscured')
    return {'x': x, 'y': y}


class Recorder:
    def __init__(self, page, out: Path, task_id: int, task_intent: str, binding: str):
        self.page, self.out = page, out
        self.task_id, self.intent, self.binding = task_id, task_intent, binding
        self.steps = []
        self.memory = ''
        self.previous = None

    async def act(self, kind: str, *, locator=None, text=None, key=None,
                  dx=None, dy=None,
                  prefer_coordinate=False,
                  memory: str = ''):
        step = len(self.steps)
        require(step < MAX_ACTIONS, 'teacher_action_limit')
        for attempt in range(MAX_STABLE_ATTEMPTS):
            observation, handles, frame_url = await capture(
                self.page, task_id=self.task_id, task_intent=self.intent,
                binding=self.binding, step=step, memory=self.memory,
                previous=self.previous)
            action = {'type': kind}
            if locator is not None:
                action['target'] = await target_for(
                    self.page, locator, handles,
                    prefer_coordinate=prefer_coordinate)
            if kind == 'type':
                action.update(text=text, mode='fill')
            if kind == 'key':
                action['key'] = key
            if kind == 'scroll':
                action.update(dx=dx, dy=dy)
            action['memory'] = memory[:4000]
            normalized = normalize_model_action(json_text(action), observation,
                                                current_frame_id=observation.frame_id)
            # A changed frame is discarded before it becomes a training row.
            fresh = await screenshot(self.page)
            if (self.page.url == frame_url and
                    sha256(fresh) == observation.screenshot['sha256']):
                break
            if attempt == 0:
                debug = self.out / 'private-stale-diagnostics'
                debug.mkdir(mode=0o700, parents=True, exist_ok=True)
                for name, image in (('captured', observation.screenshot_bytes),
                                    ('fresh', fresh)):
                    path = debug / f'step-{step:03d}-{name}.png'
                    path.write_bytes(image)
                    path.chmod(0o600)
        else:
            raise RuntimeError('stale_frame_before_teacher_dispatch')
        frame = self.out / 'frames' / f'step-{step:03d}.png'
        frame.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        frame.write_bytes(observation.screenshot_bytes)
        frame.chmod(0o600)
        result = await host.dispatch_action(self.page, normalized, observation, handles)
        require(result == {'status': 'applied', 'code': 'ok'}, 'teacher_gui_action_failed')
        self.steps.append({
            'step': step, 'screenshot_file': f'frames/step-{step:03d}.png',
            'screenshot_sha256': sha256(observation.screenshot_bytes),
            'observation': {
                'task_id': observation.task_id,
                'task_binding_sha256': observation.task_binding_sha256,
                'instruction': observation.instruction,
                'a11y_text': observation.a11y_text,
                'dom_text': observation.dom_text,
                'controls': [vars(item) for item in observation.controls],
                'previous_action_result': observation.previous_action_result,
                'memory': observation.memory,
            }, 'action': action,
        })
        self.previous = result
        self.memory = action['memory']
        return result


async def ensure_target_visible(recorder: Recorder, locator, *, memory: str):
    """Record every scroll required to bring a teacher-selected field onscreen."""
    viewport = recorder.page.viewport_size or {'width': 1440, 'height': 1000}
    for _ in range(6):
        box = await locator.bounding_box()
        require(box is not None, 'teacher_target_missing')
        center = box['y'] + box['height'] / 2
        if 0 <= center < viewport['height']:
            return
        await recorder.act('scroll', dx=0,
                           dy=560 if center >= viewport['height'] else -560,
                           memory=memory)
    raise RuntimeError('teacher_target_outside_viewport')
