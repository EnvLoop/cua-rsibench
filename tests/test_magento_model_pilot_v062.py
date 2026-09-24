"""Offline v0.6.2 optional-memory checks; no Tinker provider calls."""
import io
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, VERSION as TRUSTED_VERSION, make_observation
from cursibench.scale_action_output_v062 import OUTPUT_VERSION, normalize_model_action, render_for_model
from cursibench.scale_vision_proxy import Limits, MODEL, PROCESSOR, RENDERER, VisionSamplingAdapter

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('magento_v062', ROOT / 'tools/run_magento_model_pilot_v062.py')
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def frame(*, step=0, memory=''):
    picture = io.BytesIO()
    Image.new('RGB', (64, 48), 'white').save(picture, format='PNG')
    return make_observation(
        task_id='webarena.shopping_admin.157', task_binding_sha256='a' * 64,
        instruction='View the details of all customers', step=step,
        screenshot_bytes=picture.getvalue(), a11y_text='Dashboard',
        controls=[{'ref': 'c004', 'role': 'link', 'label': 'CUSTOMERS',
                   'visible': True, 'enabled': True}],
        previous_action_result=({'status': 'applied', 'code': 'ok'} if step else None),
        memory=memory,
    )


class OptionalMemoryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.observation = frame()
        self.payload = {'type': 'click', 'target': {'ref': 'c004'}}

    def normalize(self, payload, observation=None):
        observation = observation or self.observation
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        return normalize_model_action(raw, observation,
                                      current_frame_id=observation.frame_id)

    def test_paid_v061_shape_without_memory_is_now_a_valid_gui_action(self):
        raw = '```json\n' + json.dumps(self.payload) + '\n```'
        action = self.normalize(raw)
        self.assertEqual(action['type'], 'click')
        self.assertEqual(action['target'], {'ref': 'c004'})
        self.assertEqual(action['memory'], '')
        self.assertEqual(action['version'], TRUSTED_VERSION)
        self.assertEqual(action['task_id'], self.observation.task_id)
        self.assertEqual(action['task_binding_sha256'], 'a' * 64)
        self.assertEqual(action['step'], 0)
        self.assertEqual(action['frame_id'], self.observation.frame_id)

    def test_missing_memory_carries_current_bounded_memory_and_explicit_memory_wins(self):
        later = frame(step=1, memory='Customer menu opened.')
        self.assertEqual(self.normalize(self.payload, later)['memory'],
                         'Customer menu opened.')
        self.assertEqual(self.normalize(self.payload | {'memory': 'Open list.'}, later)['memory'],
                         'Open list.')
        with self.assertRaisesRegex(ContractError, 'invalid_action'):
            self.normalize(self.payload | {'memory': None}, later)
        with self.assertRaisesRegex(ContractError, 'invalid_action'):
            self.normalize(self.payload | {'memory': 'x' * 4097}, later)

    def test_finish_and_other_kinds_keep_exact_fields(self):
        self.assertEqual(self.normalize({'type': 'finish'})['memory'], '')
        self.assertEqual(self.normalize({'type': 'scroll', 'dx': 0, 'dy': 200})['type'], 'scroll')
        with self.assertRaisesRegex(ContractError, 'invalid_action'):
            self.normalize({'type': 'finish', 'target': {'ref': 'c004'}})
        with self.assertRaisesRegex(ContractError, 'invalid_action'):
            self.normalize({'type': 'click'})

    def test_prompt_marks_memory_optional_without_trusted_copy_fields(self):
        rendered = render_for_model(self.observation)
        instruction = json.loads(rendered['instruction'])
        visible = json.loads(rendered['visible_text'])
        self.assertEqual(instruction['output_version'], OUTPUT_VERSION)
        self.assertIn('memory field is optional', instruction['contract'])
        self.assertEqual(visible['controls'][0]['ref'], 'c004')
        for hidden in (self.observation.task_id, self.observation.task_binding_sha256,
                       self.observation.frame_id, '"step":0'):
            self.assertNotIn(hidden, rendered['instruction'])

    def test_extra_fields_non_gui_actions_and_stale_targets_still_rejected(self):
        for extra in (
            {'version': TRUSTED_VERSION}, {'task_id': self.observation.task_id},
            {'task_binding_sha256': 'a' * 64}, {'step': 0},
            {'frame_id': self.observation.frame_id}, {'url': 'http://localhost:7780/'},
            {'selector': '#menu'}, {'command': 'echo unsafe'},
            {'api': '/customer'}, {'path': '/tmp/file'},
        ):
            with self.subTest(extra=extra), self.assertRaisesRegex(ContractError, 'invalid_action'):
                self.normalize(self.payload | extra)
        for bad in (
            {'type': 'shell', 'command': 'echo unsafe'},
            {'type': 'click', 'target': {'selector': '#menu'}},
            {'type': 'click', 'target': {'ref': 'old-ref'}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                self.normalize(bad)

    def test_prose_multiple_objects_fences_and_duplicate_keys_still_rejected(self):
        object_text = json.dumps(self.payload)
        for bad in (
            'Click: ' + object_text,
            object_text + ' ' + object_text,
            '```JSON\n' + object_text + '\n```',
            '```json\n' + object_text + '\n```\n```json\n' + object_text + '\n```',
            '```json\n' + object_text + '\n``` trailing',
            '{"type":"click","type":"finish","target":{"ref":"c004"}}',
        ):
            with self.subTest(bad=bad[:30]), self.assertRaisesRegex(ContractError, 'invalid_action_json'):
                self.normalize(bad)

    def test_stale_frame_and_pinned_host_remain_bound(self):
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            normalize_model_action(json.dumps(self.payload), self.observation,
                                   current_frame_id='stale')
        self.assertEqual(pilot.host.VERSION, 'magento-model-pilot-v0.6.2')
        self.assertEqual(pilot.host.CAMPAIGN_ID, 'magento-base-pilot-v3')
        self.assertEqual(pilot.host.MAX_ACTIONS, 5)
        self.assertEqual(pilot.BASE_RUNNER_SHA256,
            __import__('hashlib').sha256(pilot.BASE_RUNNER.read_bytes()).hexdigest())


class FakeFuture:
    def result(self, timeout):
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1], stop_reason='stop')],
                               prompt_cache_hit_tokens=0)


class FakeBackend:
    identity = {'model': MODEL, 'renderer': RENDERER,
                'image_processor': PROCESSOR, 'sampling_kind': 'base', 'seed': 23}

    def __init__(self):
        self.output = ''
        self.calls = 0

    def render(self, image, instruction, visible_text):
        prompt = json.loads(instruction)
        visible = json.loads(visible_text)
        controls = {row['label']: row['ref'] for row in visible['controls']}
        if 'Visible headings: Customers' in visible['a11y_text']:
            action = {'type': 'finish'}
        elif 'All Customers' in controls:
            action = {'type': 'click', 'target': {'ref': controls['All Customers']}}
        else:
            action = {'type': 'click', 'target': {'ref': controls['Customers']}}
        self.output = '```json\n' + json.dumps(action) + '\n```'
        assert prompt['output_version'] == OUTPUT_VERSION
        assert image.size == (640, 480)
        return object(), {'input_tokens': 80, 'image_tokens': 40,
                          'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

    def submit(self, prompt, max_output_tokens):
        self.calls += 1
        return FakeFuture()

    def decode(self, tokens):
        return self.output


class OptionalMemoryBrowserTest(unittest.IsolatedAsyncioTestCase):
    async def test_fenced_actions_without_memory_drive_visible_gui(self):
        from playwright.async_api import async_playwright
        with TemporaryDirectory() as temporary:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(viewport={'width': 640, 'height': 480},
                                                        service_workers='block')
                    try:
                        page = await context.new_page()
                        await page.set_content('''
                          <h1>Dashboard</h1>
                          <button onclick="document.getElementById('all').hidden=false">Customers</button>
                          <button id="all" hidden onclick="document.querySelector('h1').textContent='Customers';
                            this.hidden=true">All Customers</button>
                        ''')
                        backend = FakeBackend()
                        adapter = VisionSamplingAdapter(backend, Path(temporary) / 'journal',
                                                        limits=Limits(max_actions=5))
                        policy = await pilot.host.execute_policy(
                            page, adapter, instruction='View the details of all customers',
                            binding='a' * 64, request_prefix='v062-fake-157')
                        self.assertEqual(policy['status'], 'completed')
                        self.assertEqual([row['action_type'] for row in policy['actions']],
                                         ['click', 'click', 'finish'])
                        self.assertEqual(backend.calls, 3)
                        self.assertEqual(await page.locator('h1').inner_text(), 'Customers')
                    finally:
                        await context.close()
                finally:
                    await browser.close()


if __name__ == '__main__':
    unittest.main()
