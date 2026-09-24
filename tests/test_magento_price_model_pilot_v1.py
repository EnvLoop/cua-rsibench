"""Offline guards for the bounded mutation-aware Qwen pilot."""
import asyncio
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from cursibench.scale_vision_proxy import (
    Limits, MODEL, PROCESSOR, RENDERER, VisionSamplingAdapter,
)


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'magento_price_model_pilot', ROOT / 'tools/run_magento_price_model_pilot_v1.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class FakeFuture:
    def result(self, timeout):
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1], stop_reason='stop')],
                               prompt_cache_hit_tokens=0)


class FakeBackend:
    identity = {'model': MODEL, 'renderer': RENDERER,
                'image_processor': PROCESSOR, 'sampling_kind': 'base', 'seed': 23}

    def __init__(self):
        self.output = ''

    def render(self, image, instruction, visible_text):
        payload = json.loads(instruction)
        visible = json.loads(visible_text)
        assert 'forty applied GUI actions' in payload['contract']
        assert payload['task_instruction'] == 'Update the five green prices'
        if 'Ready' in visible['a11y_text']:
            action = {'type': 'finish'}
        else:
            control = next(row for row in visible['controls'] if row['label'] == 'Open')
            action = {'type': 'click', 'target': {'ref': control['ref']}}
        self.output = json.dumps(action)
        return object(), {'input_tokens': 100, 'image_tokens': 50,
                          'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

    def submit(self, prompt, max_output_tokens):
        assert max_output_tokens == 512
        return FakeFuture()

    def decode(self, tokens):
        return self.output


class GuardTests(unittest.TestCase):
    def test_mutation_route_is_local_and_target_bound(self):
        allowed = pilot.permitted_request
        self.assertTrue(allowed('http://localhost:7792/admin/catalog/product/save/id/111/type/simple/', 'POST'))
        self.assertTrue(allowed('http://localhost:7792/admin/catalog/product/validate/id/123/type/simple/', 'POST'))
        self.assertTrue(allowed('http://localhost:7792/admin/mui/bookmark/save/', 'POST'))
        self.assertFalse(allowed('http://localhost:7792/admin/catalog/product/save/id/112/', 'POST'))
        self.assertFalse(allowed('http://localhost:7780/admin/catalog/product/save/id/111/', 'POST'))
        self.assertFalse(allowed('https://example.com/admin/catalog/product/save/id/111/', 'POST'))
        self.assertFalse(allowed('http://localhost:7792/admin/catalog/product/delete/id/111/', 'POST'))
        self.assertFalse(allowed('http://localhost:7792/admin/catalog/product/save/id/111/', 'PUT'))

    def test_clone_redirect_must_resolve_inside_disposable_port(self):
        self.assertEqual(pilot.validate_clone_redirect(302,
            'http://localhost:7792/admin')['status'], 302)
        with self.assertRaisesRegex(pilot.PilotError, 'clone_redirect_not_isolated'):
            pilot.validate_clone_redirect(302, 'http://localhost:7780/admin')

    def test_sample_reservation_fails_closed_above_cap(self):
        self.assertEqual(str(pilot.sample_reservation_usd() * 40), '2.55252480')
        self.assertEqual(pilot.published_rate_preflight()['max_samples'], 40)
        with patch.object(pilot, 'PUBLISHED_RATE_CAP_USD', pilot.Decimal('2')):
            with self.assertRaisesRegex(pilot.PilotError, 'published_rate_budget_exceeded'):
                pilot.published_rate_preflight()

    def test_usage_subtotal_includes_returned_output_tokens(self):
        budget = SimpleNamespace(attempt_count=2, reserved_usd='0.12762624')
        policy = {'samples': [{'usage': {'input_tokens': 2000, 'output_tokens': 20}},
                              {'usage': {'input_tokens': 3000, 'output_tokens': 30}}]}
        usage = pilot.summarize_usage(policy, budget)
        self.assertEqual(usage['rendered_multimodal_input_tokens'], 5000)
        self.assertEqual(usage['sampled_output_tokens'], 50)
        self.assertEqual(usage['published_rate_subtotal_usd'], '0.00957975')

    def test_budget_adapter_never_dispatches_after_deadline_or_cap(self):
        class Adapter:
            def __init__(self): self.calls = 0
            def failure(self, request_id, code):
                return {'status': 'error', 'error_subtype': code, 'request_id': request_id}
            def sample(self, **kwargs):
                self.calls += 1
                return {'status': 'completed', 'request_id': kwargs['request_id']}
        inner = Adapter()
        soon = pilot.BudgetedAdapter(inner, deadline=time.monotonic() + 30)
        self.assertEqual(soon.sample(request_id='near')['error_subtype'], 'wall_clock_budget')
        self.assertEqual(inner.calls, 0)
        safe = pilot.BudgetedAdapter(inner, deadline=time.monotonic() + 300)
        self.assertEqual(safe.sample(request_id='first')['status'], 'completed')
        self.assertEqual(inner.calls, 1)
        with patch.object(pilot, 'PUBLISHED_RATE_CAP_USD', pilot.Decimal('0.01')):
            self.assertEqual(safe.sample(request_id='blocked')['error_subtype'],
                             'published_rate_budget')
            self.assertEqual(inner.calls, 1)

    def test_wrong_color_readback_must_remain_unchanged(self):
        def snapshot():
            selected = {table: [] for table in pilot.price.RESTORE}
            selected['catalog_product_entity_decimal'] = [
                {'entity_id': i, 'attribute_id': pilot.price.PRICE_ATTR,
                 'store_id': 0, 'value': '52.000000'}
                for i in (*pilot.price.TARGETS, 112)]
            return {'selected': selected}
        before, after = snapshot(), snapshot()
        for row in after['selected']['catalog_product_entity_decimal']:
            if row['entity_id'] in pilot.price.TARGETS:
                row['value'] = '47.000000'
        self.assertTrue(pilot.state_summary(before, after)['positive_state_pass'])
        for row in after['selected']['catalog_product_entity_decimal']:
            if row['entity_id'] == 112:
                row['value'] = '47.000000'
        self.assertFalse(pilot.state_summary(before, after)['positive_state_pass'])


class ActionContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_offscreen_control_is_absent_from_model_observation(self):
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={'width': 640, 'height': 480})
                await page.set_content('''<button>On screen</button>
                  <div style="height:2000px"></div><button>Off screen</button>''')
                controls, _ = await pilot.viewport_controls(page)
                labels = [row['label'] for row in controls]
                self.assertIn('On screen', labels)
                self.assertNotIn('Off screen', labels)
            finally:
                await browser.close()

    async def test_two_action_fake_model_uses_real_fresh_frame_contract(self):
        from playwright.async_api import async_playwright
        with TemporaryDirectory() as folder:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(viewport={'width': 640, 'height': 480})
                    page = await context.new_page()
                    await page.set_content('''<h1>Dashboard</h1>
                      <button onclick="document.querySelector('h1').textContent='Ready'">Open</button>''')
                    backend = FakeBackend()
                    adapter = VisionSamplingAdapter(backend, Path(folder) / 'journal',
                        limits=Limits(max_actions=40, output_tokens=512))
                    budget = pilot.BudgetedAdapter(adapter,
                        deadline=time.monotonic() + 300)
                    frames = Path(folder) / 'frames'
                    frames.mkdir()
                    policy = await pilot.execute_policy(page, budget,
                        instruction='Update the five green prices', binding='a' * 64,
                        prefix='mag777-fake', frames=frames,
                        deadline=time.monotonic() + 300)
                    self.assertEqual(policy['status'], 'completed')
                    self.assertEqual(policy['max_gui_actions'], 40)
                    self.assertEqual(policy['max_samples'], 40)
                    self.assertEqual(policy['sample_attempt_count'], 2)
                    self.assertEqual(policy['applied_action_count'], 2)
                    self.assertEqual([a['action_type'] for a in policy['actions']],
                                     ['click', 'finish'])
                    self.assertEqual(len(list(frames.glob('*.png'))), 2)
                    await context.close()
                finally:
                    await browser.close()


if __name__ == '__main__':
    unittest.main()
