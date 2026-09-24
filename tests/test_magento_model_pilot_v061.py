"""No-paid checks for minimal JSON output and the pinned v0.6 GUI host."""
import io
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from PIL import Image

from cursibench.scale_action_contract import (
    ContractError, VERSION as TRUSTED_VERSION, make_observation,
)
from cursibench.scale_action_output_v061 import (
    OUTPUT_VERSION, normalize_model_action, render_for_model,
)
from cursibench.scale_vision_proxy import (
    Limits, MODEL, PROCESSOR, RENDERER, VisionSamplingAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'magento_v061', ROOT / 'tools/run_magento_model_pilot_v061.py')
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def frame():
    image = io.BytesIO()
    Image.new('RGB', (64, 48), 'white').save(image, format='PNG')
    return make_observation(
        task_id='webarena.shopping_admin.157', task_binding_sha256='a' * 64,
        instruction='View the details of all customers', step=0,
        screenshot_bytes=image.getvalue(), a11y_text='Dashboard',
        controls=[{'ref': 'c001', 'role': 'link', 'label': 'CUSTOMERS',
                   'visible': True, 'enabled': True}],
    )


class MinimalOutputBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.observation = frame()
        self.payload = {'type': 'click', 'target': {'ref': 'c001'},
                        'memory': 'Open the customer menu.'}

    def normalize(self, value):
        return normalize_model_action(value, self.observation,
                                      current_frame_id=self.observation.frame_id)

    def test_bare_and_one_exact_json_fence_inject_trusted_fields(self):
        for raw in (json.dumps(self.payload),
                    '```json\n' + json.dumps(self.payload) + '\n```',
                    '  ```json\r\n' + json.dumps(self.payload) + '\r\n```  '):
            with self.subTest(raw=raw[:20]):
                action = self.normalize(raw)
                self.assertEqual(action['type'], 'click')
                self.assertEqual(action['version'], TRUSTED_VERSION)
                self.assertEqual(action['task_id'], self.observation.task_id)
                self.assertEqual(action['task_binding_sha256'], 'a' * 64)
                self.assertEqual(action['step'], 0)
                self.assertEqual(action['frame_id'], self.observation.frame_id)

    def test_prompt_contains_task_and_visible_ui_without_copy_fields(self):
        rendered = render_for_model(self.observation)
        instruction = json.loads(rendered['instruction'])
        visible = json.loads(rendered['visible_text'])
        self.assertEqual(instruction['output_version'], OUTPUT_VERSION)
        self.assertEqual(instruction['task_instruction'], self.observation.instruction)
        self.assertIn('one JSON object', instruction['contract'])
        self.assertEqual(visible['controls'][0]['label'], 'CUSTOMERS')
        self.assertEqual(rendered['image_bytes'], self.observation.screenshot_bytes)
        for private in (self.observation.task_id, self.observation.task_binding_sha256,
                        self.observation.frame_id, '"step":0'):
            self.assertNotIn(private, rendered['instruction'])

    def test_prose_multiple_objects_fences_and_duplicate_keys_are_rejected(self):
        bad = [
            'Click this: ' + json.dumps(self.payload),
            json.dumps(self.payload) + ' ' + json.dumps(self.payload),
            '```JSON\n' + json.dumps(self.payload) + '\n```',
            '```json\n' + json.dumps(self.payload) + '\n```\n```json\n' + json.dumps(self.payload) + '\n```',
            '```json\n' + json.dumps(self.payload) + '\n``` extra',
            '{"type":"click","type":"finish","target":{"ref":"c001"},"memory":"x"}',
            '[{"type":"finish","memory":"x"}]',
            '{"type":"finish","memory":"x"} trailing',
        ]
        for raw in bad:
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(ContractError, 'invalid_action_json'):
                self.normalize(raw)

    def test_extra_metadata_shell_api_url_and_selector_fields_are_rejected(self):
        for extra in (
            {'version': TRUSTED_VERSION}, {'task_id': self.observation.task_id},
            {'task_binding_sha256': 'a' * 64}, {'step': 0},
            {'frame_id': self.observation.frame_id}, {'url': 'http://localhost:7780/admin'},
            {'selector': '#menu'}, {'command': 'echo unsafe'},
            {'api': '/customer'}, {'path': '/tmp/file'},
        ):
            with self.subTest(extra=extra), self.assertRaisesRegex(ContractError, 'invalid_action'):
                self.normalize(json.dumps(self.payload | extra))
        for payload in (
            {'type': 'shell', 'command': 'echo unsafe', 'memory': ''},
            {'type': 'click', 'target': {'selector': '#menu'}, 'memory': ''},
            {'type': 'click', 'target': {'ref': 'stale'}, 'memory': ''},
            {'type': 'finish'},
        ):
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                self.normalize(json.dumps(payload))

    def test_stale_frame_stays_rejected_after_trusted_injection(self):
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            normalize_model_action(json.dumps(self.payload), self.observation,
                                   current_frame_id='other-frame')

    def test_old_host_source_and_first_pilot_version_remain_separate(self):
        self.assertEqual(pilot.host.VERSION, 'magento-model-pilot-v0.6.1')
        self.assertEqual(pilot.host.CAMPAIGN_ID, 'magento-base-pilot-v2')
        self.assertEqual(pilot.host.MAX_ACTIONS, 5)
        self.assertEqual(pilot.BASE_RUNNER_SHA256,
            __import__('hashlib').sha256(pilot.BASE_RUNNER.read_bytes()).hexdigest())


class FakeFuture:
    def __init__(self, backend):
        self.backend = backend

    def result(self, timeout):
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1], stop_reason='stop')],
                               prompt_cache_hit_tokens=0)


class MinimalFakeBackend:
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
            payload = {'type': 'finish', 'memory': 'Customer list visible.'}
        elif 'All Customers' in controls:
            payload = {'type': 'click', 'target': {'ref': controls['All Customers']},
                       'memory': 'Open the customer list.'}
        elif 'Customers' in controls:
            payload = {'type': 'click', 'target': {'ref': controls['Customers']},
                       'memory': 'Expand Customers.'}
        else:
            raise AssertionError('Expected visible customer control absent')
        self.output = '```json\n' + json.dumps(payload) + '\n```'
        assert prompt['output_version'] == OUTPUT_VERSION
        assert image.size == (640, 480)
        return object(), {'input_tokens': 80, 'image_tokens': 40,
                          'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

    def submit(self, prompt, max_output_tokens):
        self.calls += 1
        return FakeFuture(self)

    def decode(self, tokens):
        return self.output


class MinimalOutputBrowserTest(unittest.IsolatedAsyncioTestCase):
    async def test_fenced_minimal_actions_drive_visible_gui(self):
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
                        backend = MinimalFakeBackend()
                        adapter = VisionSamplingAdapter(backend, Path(temporary) / 'journal',
                                                        limits=Limits(max_actions=5))
                        result = await pilot.host.execute_policy(
                            page, adapter, instruction='View the details of all customers',
                            binding='a' * 64, request_prefix='minimal-fake-157')
                        self.assertEqual(result['status'], 'completed')
                        self.assertEqual([row['action_type'] for row in result['actions']],
                                         ['click', 'click', 'finish'])
                        self.assertEqual(backend.calls, 3)
                        self.assertEqual(await page.locator('h1').inner_text(), 'Customers')
                    finally:
                        await context.close()
                finally:
                    await browser.close()


if __name__ == '__main__':
    unittest.main()
