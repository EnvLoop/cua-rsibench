"""No-paid tests for fresh-frame resampling and immutable GUI references."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from cursibench.scale_vision_proxy import (
    Limits, MODEL, PROCESSOR, RENDERER, VisionSamplingAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'magento_v063', ROOT / 'tools/run_magento_model_pilot_v063.py')
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class FakeFuture:
    def __init__(self, backend, index):
        self.backend, self.index = backend, index

    def result(self, timeout):
        if self.backend.fail_first and self.index == 1:
            raise TimeoutError('fake provider timeout')
        if self.backend.pause_first and self.index == 1:
            self.backend.started.set()
            if not self.backend.release.wait(timeout=5):
                raise TimeoutError('test release missing')
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1], stop_reason='stop')],
                               prompt_cache_hit_tokens=0)


class FakeBackend:
    identity = {'model': MODEL, 'renderer': RENDERER,
                'image_processor': PROCESSOR, 'sampling_kind': 'base', 'seed': 23}

    def __init__(self, *, pause_first=False, coordinate=False, fail_first=False):
        self.pause_first, self.coordinate, self.fail_first = pause_first, coordinate, fail_first
        self.started, self.release = threading.Event(), threading.Event()
        self.calls, self.output = 0, ''

    def render(self, image, instruction, visible_text):
        prompt = json.loads(instruction)
        visible = json.loads(visible_text)
        controls = {row['label']: row['ref'] for row in visible['controls']}
        if self.coordinate:
            action = {'type': 'click', 'target': {'x': 70, 'y': 84}} if self.calls == 0 else {'type': 'finish'}
        elif 'Visible headings: Customers' in visible['a11y_text']:
            action = {'type': 'finish'}
        elif 'All Customers' in controls:
            action = {'type': 'click', 'target': {'ref': controls['All Customers']}}
        else:
            action = {'type': 'click', 'target': {'ref': controls['Customers']}}
        self.output = '```json\n' + json.dumps(action) + '\n```'
        assert prompt['output_version'] == pilot.OUTPUT_VERSION
        assert image.size == (640, 480)
        return object(), {'input_tokens': 80, 'image_tokens': 40,
                          'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

    def submit(self, prompt, max_output_tokens):
        self.calls += 1
        return FakeFuture(self, self.calls)

    def decode(self, tokens):
        return self.output


class ProtocolTests(unittest.TestCase):
    def test_versions_budgets_and_old_sources_are_pinned(self):
        self.assertEqual(pilot.host.VERSION, 'magento-model-pilot-v0.6.3')
        self.assertEqual(pilot.host.CAMPAIGN_ID, 'magento-base-pilot-v4')
        self.assertEqual((pilot.MAX_GUI_ACTIONS, pilot.MAX_SAMPLES, pilot.MAX_STALE_SAMPLES),
                         (5, 7, 2))
        self.assertEqual(hashlib.sha256(pilot.BASE_RUNNER.read_bytes()).hexdigest(),
                         pilot.BASE_RUNNER_SHA256)
        self.assertEqual(hashlib.sha256(pilot.V062_BOUNDARY.read_bytes()).hexdigest(),
                         pilot.V062_BOUNDARY_SHA256)


class DriftBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.temp = TemporaryDirectory()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(viewport={'width': 640, 'height': 480},
                                                      service_workers='block')
        self.page = await self.context.new_page()
        await self.page.set_content('''
            <h1>Dashboard</h1>
            <button id="customers" onclick="window.clicks=(window.clicks||0)+1;
              document.querySelector('h1').textContent='Customers'">Customers</button>
        ''')

    async def asyncTearDown(self):
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()
        self.temp.cleanup()

    def adapter(self, backend):
        return VisionSamplingAdapter(backend, Path(self.temp.name) / 'journal',
                                     limits=Limits(max_actions=pilot.MAX_SAMPLES))

    async def run_policy(self, backend):
        return await pilot.host.execute_policy(
            self.page, self.adapter(backend),
            instruction='View the details of all customers',
            binding='a' * 64, request_prefix='drift-fake-157')

    async def test_async_pixel_drift_discards_completed_sample_then_uses_new_id(self):
        backend = FakeBackend(pause_first=True)

        async def mutate():
            self.assertTrue(await asyncio.to_thread(backend.started.wait, 5))
            await self.page.evaluate("document.querySelector('h1').textContent='Dashboard ready'")
            backend.release.set()

        mutation = asyncio.create_task(mutate())
        policy = await self.run_policy(backend)
        await mutation
        self.assertEqual(policy['status'], 'completed')
        self.assertEqual(policy['stale_sample_count'], 1)
        self.assertEqual(policy['stale_reasons'], ['pixels_changed'])
        self.assertEqual(policy['sample_attempt_count'], 3)
        self.assertEqual(policy['applied_action_count'], 2)
        self.assertEqual([row['action_type'] for row in policy['actions']], ['click', 'finish'])
        self.assertEqual(await self.page.evaluate('window.clicks'), 1)
        self.assertTrue(policy['samples'][0]['discarded_as_stale'])
        self.assertEqual(len({row['request_id_sha256'] for row in policy['samples']}), 3)
        self.assertTrue(all(row['new_dispatch'] for row in policy['samples']))

    async def test_ref_identity_drift_rejects_identical_looking_replacement(self):
        backend = FakeBackend(pause_first=True)

        async def replace():
            self.assertTrue(await asyncio.to_thread(backend.started.wait, 5))
            await self.page.evaluate("""() => {
              const old = document.querySelector('#customers');
              old.replaceWith(old.cloneNode(true));
            }""")
            backend.release.set()

        replacement = asyncio.create_task(replace())
        policy = await self.run_policy(backend)
        await replacement
        self.assertEqual(policy['status'], 'completed')
        self.assertEqual(policy['stale_sample_count'], 1)
        self.assertEqual(policy['stale_reasons'], ['ref_identity_changed'])
        self.assertEqual(await self.page.evaluate('window.clicks'), 1)
        self.assertEqual(len({row['request_id_sha256'] for row in policy['samples']}),
                         policy['sample_attempt_count'])

    async def test_coordinate_action_never_dispatches_against_changed_pixels(self):
        backend = FakeBackend(pause_first=True, coordinate=True)

        async def mutate():
            self.assertTrue(await asyncio.to_thread(backend.started.wait, 5))
            await self.page.evaluate("document.querySelector('h1').textContent='Dashboard ready'")
            backend.release.set()

        mutation = asyncio.create_task(mutate())
        policy = await self.run_policy(backend)
        await mutation
        self.assertEqual(policy['stale_sample_count'], 1)
        self.assertEqual(policy['stale_reasons'], ['pixels_changed'])
        self.assertEqual([row['action_type'] for row in policy['actions']], ['finish'])
        self.assertIsNone(await self.page.evaluate('window.clicks'))

    async def test_stale_discard_budget_stops_after_three_unique_samples(self):
        backend = FakeBackend()

        async def always_changed(page, observation, frame_url):
            return False, 'pixels_changed'

        with patch.object(pilot, '_same_pixels', always_changed):
            policy = await self.run_policy(backend)
        self.assertEqual((policy['status'], policy['failure_code']),
                         ('unscored', 'stale_sample_budget_exhausted'))
        self.assertEqual(policy['stale_sample_count'], 3)
        self.assertEqual(policy['sample_attempt_count'], 3)
        self.assertEqual(policy['applied_action_count'], 0)
        self.assertEqual(backend.calls, 3)
        self.assertEqual(len({row['request_id_sha256'] for row in policy['samples']}), 3)

    async def test_provider_timeout_is_unscored_without_new_sample(self):
        backend = FakeBackend(fail_first=True)
        policy = await self.run_policy(backend)
        self.assertEqual((policy['status'], policy['failure_code']),
                         ('unscored', 'provider_timeout_uncertain'))
        self.assertEqual(policy['sample_attempt_count'], 1)
        self.assertEqual(policy['stale_sample_count'], 0)
        self.assertEqual(backend.calls, 1)


if __name__ == '__main__':
    unittest.main()
