"""Offline guards for the versioned Magento visual observer."""
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
    'magento_price_model_pilot_v2', ROOT / 'tools/run_magento_price_model_pilot_v2.py')
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
        self.visual_feedback = []

    def render(self, image, instruction, visible_text):
        payload = json.loads(instruction)
        self.visual_feedback.append(payload['visual_progress'])
        visible = json.loads(visible_text)
        assert f'{pilot.MAX_GUI_ACTIONS} applied GUI actions' in payload['contract']
        assert 'Enter key action or a visible submit control' in payload['contract']
        assert 'After three identical applied actions' in payload['contract']
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
    def test_visual_progress_reports_identical_no_effect_actions_without_claiming_state(self):
        feedback = pilot.VisualProgress()
        image = b'frame pixels'
        observation = SimpleNamespace(screenshot={'sha256': pilot.hashlib.sha256(image).hexdigest()})
        click = {'type': 'click', 'target': {'ref': 'c017'}, 'memory': 'untrusted'}
        for repeat in range(1, 4):
            feedback.dispatched(click, observation, 'http://localhost:7792/admin',
                                {'status': 'applied', 'code': 'ok'})
            feedback.observed(image, 'http://localhost:7792/admin',
                              {'status': 'applied', 'code': 'ok'})
            self.assertTrue(feedback.current['screenshot_and_url_unchanged'])
            self.assertEqual(feedback.current[
                'consecutive_identical_actions_without_visible_change'], repeat)
            self.assertNotIn('untrusted', json.dumps(feedback.current))
        feedback.dispatched(click, observation, 'http://localhost:7792/admin',
                            {'status': 'applied', 'code': 'ok'})
        feedback.observed(b'new pixels', 'http://localhost:7792/admin',
                          {'status': 'applied', 'code': 'ok'})
        self.assertFalse(feedback.current['screenshot_and_url_unchanged'])
        self.assertEqual(feedback.current[
            'consecutive_identical_actions_without_visible_change'], 0)
        feedback.dispatched(click, observation, 'http://localhost:7792/admin',
                            {'status': 'applied', 'code': 'ok'})
        feedback.observed(image, 'http://localhost:7792/admin/catalog/',
                          {'status': 'applied', 'code': 'ok'})
        self.assertFalse(feedback.current['screenshot_and_url_unchanged'])
        self.assertEqual(feedback.current[
            'consecutive_identical_actions_without_visible_change'], 0)

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
        self.assertEqual(str(pilot.sample_reservation_usd() * 84), '5.36030208')
        self.assertEqual(pilot.published_rate_preflight()['max_samples'], 84)
        with patch.object(pilot, 'PUBLISHED_RATE_CAP_USD', pilot.Decimal('2')):
            with self.assertRaisesRegex(pilot.PilotError, 'published_rate_budget_exceeded'):
                pilot.published_rate_preflight()
        with patch.object(pilot, 'MAX_SAMPLES', pilot.MAX_GUI_ACTIONS +
                          pilot.MAX_STALE_SAMPLES - 1):
            with self.assertRaisesRegex(pilot.PilotError,
                                        'sample_budget_below_action_and_stale_ceiling'):
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

    def test_model_terminal_is_scored_only_after_valid_verification(self):
        self.assertEqual(pilot.NO_VISIBLE_PROGRESS_ACTIONS, 3)
        official = {'status': 'failure', 'score': 0.0}
        state = {'positive_state_pass': False}
        for code in ('no_visible_progress', 'action_budget_exhausted'):
            policy = {'status': 'completed', 'failure_class': 'model_failure',
                      'failure_code': code}
            outcome = pilot.admit_scored_result(policy, official, state,
                blocked=[], evaluator_equal=True)
            self.assertEqual((outcome['status'], outcome['score'],
                              outcome['failure_class'], outcome['failure_code']),
                             ('completed', 0.0, 'model_failure', code))
        no_progress = {'status': 'completed', 'failure_class': 'model_failure',
                       'failure_code': 'no_visible_progress'}
        positive = pilot.admit_scored_result(no_progress,
            {'status': 'success', 'score': 1.0},
            {'positive_state_pass': True}, blocked=[], evaluator_equal=True)
        self.assertEqual((positive['status'], positive['score']), ('completed', 1.0))

    def test_provider_gui_stale_and_verifier_failures_remain_unscored(self):
        state = {'positive_state_pass': False}
        official = {'status': 'failure', 'score': 0.0}
        for failure_class, code in (
                ('transport_or_provider_failure', 'sampling_transport_uncertain'),
                ('environment_failure', 'gui_dispatch_error'),
                ('environment_failure', 'stale_sample_budget_exhausted'),
                ('environment_failure', 'wall_clock_budget')):
            policy = {'status': 'unscored', 'failure_class': failure_class,
                      'failure_code': code}
            result = pilot.admit_scored_result(policy, official, state,
                blocked=[], evaluator_equal=True)
            self.assertEqual((result['status'], result['score'],
                              result['failure_class'], result['failure_code']),
                             ('unscored', None, failure_class, code))
        policy = {'status': 'completed', 'failure_class': None,
                  'failure_code': None}
        for blocked, equal, expected in (
                ([{'method': 'POST'}], True, 'blocked_or_evaluator_disagreement'),
                ([], False, 'blocked_or_evaluator_disagreement')):
            result = pilot.admit_scored_result(policy, official, state,
                blocked=blocked, evaluator_equal=equal)
            self.assertEqual((result['status'], result['score'],
                              result['failure_code']), ('unscored', None, expected))
        invalid = pilot.admit_scored_result(policy,
            {'status': 'error', 'score': None}, state,
            blocked=[], evaluator_equal=True)
        self.assertEqual((invalid['status'], invalid['score'],
                          invalid['failure_class']),
                         ('unscored', None, 'verifier_failure'))


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

    async def test_icon_only_button_is_screenshot_bound_and_model_visible(self):
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={'width': 640, 'height': 480})
                await page.set_content('''<input placeholder="Keywords">
                  <button id="search" style="width:32px;height:32px"></button>
                  <div style="height:2000px"></div>
                  <button id="offscreen" style="width:32px;height:32px"></button>''')
                controls, handles = await pilot.viewport_controls(page)
                buttons = [row for row in controls if row['role'] == 'button']
                self.assertEqual(len(buttons), 1)
                self.assertRegex(buttons[0]['label'],
                                 r'^Unlabeled button at screenshot \(\d+, \d+\)$')
                self.assertEqual(await handles[buttons[0]['ref']].get_attribute('id'),
                                 'search')
            finally:
                await browser.close()

    async def test_submit_control_is_button_and_password_value_is_not_a_label(self):
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={'width': 640, 'height': 480})
                await page.set_content('''<input type="password" value="not-for-model">
                  <input type="submit" value="Go">''')
                controls, _ = await pilot.viewport_controls(page)
                self.assertEqual([(row['role'], row['label']) for row in controls],
                                 [('button', 'Go')])
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
                    self.assertEqual(policy['max_gui_actions'], 80)
                    self.assertEqual(policy['max_samples'], 84)
                    self.assertEqual(policy['sample_attempt_count'], 2)
                    self.assertEqual(policy['applied_action_count'], 2)
                    self.assertEqual([a['action_type'] for a in policy['actions']],
                                     ['click', 'finish'])
                    self.assertEqual(len(list(frames.glob('*.png'))), 2)
                    self.assertIsNone(backend.visual_feedback[0])
                    self.assertFalse(backend.visual_feedback[1][
                        'screenshot_and_url_unchanged'])
                    await context.close()
                finally:
                    await browser.close()

    async def test_no_effect_click_feedback_reaches_next_model_sample(self):
        from playwright.async_api import async_playwright

        class NoEffectBackend(FakeBackend):
            def render(self, image, instruction, visible_text):
                payload = json.loads(instruction)
                self.visual_feedback.append(payload['visual_progress'])
                if len(self.visual_feedback) <= 2:
                    control = next(row for row in json.loads(visible_text)['controls']
                                   if row['label'] == 'Idle')
                    self.output = json.dumps({'type': 'click',
                                              'target': {'ref': control['ref']}})
                else:
                    self.output = json.dumps({'type': 'finish'})
                return object(), {'input_tokens': 100, 'image_tokens': 50,
                                  'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

        with TemporaryDirectory() as folder:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(viewport={'width': 640,
                                                                   'height': 480})
                    page = await context.new_page()
                    await page.set_content('<style>button,button:hover,'
                                           'button:active,button:focus{'
                                           'background:#eee;color:#000;'
                                           'border:1px solid #000;'
                                           'outline:none;box-shadow:none}'
                                           '</style>'
                                           '<h1>Dashboard</h1><button>Idle</button>')
                    backend = NoEffectBackend()
                    adapter = VisionSamplingAdapter(backend, Path(folder) / 'journal',
                        limits=Limits(max_actions=40, output_tokens=512))
                    budget = pilot.BudgetedAdapter(adapter,
                        deadline=time.monotonic() + 300)
                    frames = Path(folder) / 'frames'
                    frames.mkdir()
                    policy = await pilot.execute_policy(page, budget,
                        instruction='Use the visible controls', binding='b' * 64,
                        prefix='mag777-feedback-fake', frames=frames,
                        deadline=time.monotonic() + 300)
                    self.assertEqual(policy['status'], 'completed')
                    self.assertEqual([row['action_type'] for row in policy['actions']],
                                     ['click', 'click', 'finish'])
                    self.assertIsNone(backend.visual_feedback[0])
                    self.assertTrue(backend.visual_feedback[1][
                        'screenshot_and_url_unchanged'])
                    self.assertEqual(backend.visual_feedback[1][
                        'consecutive_identical_actions_without_visible_change'], 1)
                    self.assertEqual(backend.visual_feedback[2][
                        'consecutive_identical_actions_without_visible_change'], 2)
                    await context.close()
                finally:
                    await browser.close()

    async def test_three_identical_applied_no_effect_actions_stop_before_fourth_sample(self):
        from playwright.async_api import async_playwright

        class StuckBackend(FakeBackend):
            def render(self, image, instruction, visible_text):
                payload = json.loads(instruction)
                self.visual_feedback.append(payload['visual_progress'])
                control = next(row for row in json.loads(visible_text)['controls']
                               if row['label'] == 'Idle')
                self.output = json.dumps({'type': 'click',
                                          'target': {'ref': control['ref']}})
                return object(), {'input_tokens': 100, 'image_tokens': 50,
                                  'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

        with TemporaryDirectory() as folder:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(viewport={'width': 640, 'height': 480})
                    await page.set_content('<style>button,button:hover,'
                                           'button:active,button:focus{'
                                           'background:#eee;color:#000;'
                                           'border:1px solid #000;'
                                           'outline:none;box-shadow:none}'
                                           '</style><h1>Dashboard</h1><button>Idle</button>')
                    backend = StuckBackend()
                    adapter = VisionSamplingAdapter(backend, Path(folder) / 'journal',
                        limits=Limits(max_actions=84, output_tokens=512))
                    budget = pilot.BudgetedAdapter(adapter,
                        deadline=time.monotonic() + 300)
                    frames = Path(folder) / 'frames'
                    frames.mkdir()
                    policy = await pilot.execute_policy(page, budget,
                        instruction='Use the visible controls', binding='c' * 64,
                        prefix='mag777-stuck-fake', frames=frames,
                        deadline=time.monotonic() + 300)
                    self.assertEqual((policy['status'], policy['failure_class'],
                                      policy['failure_code']),
                                     ('completed', 'model_failure', 'no_visible_progress'))
                    self.assertEqual((policy['sample_attempt_count'],
                                      policy['action_attempt_count'],
                                      policy['applied_action_count'],
                                      budget.attempt_count), (3, 3, 3, 3))
                    self.assertEqual([row['action_type'] for row in policy['actions']],
                                     ['click', 'click', 'click'])
                    self.assertEqual(len(list(frames.glob('*.png'))), 4)
                    self.assertEqual([row and row[
                        'consecutive_identical_actions_without_visible_change']
                        for row in backend.visual_feedback], [None, 1, 2])
                finally:
                    await browser.close()

    async def test_third_identical_action_with_visible_change_can_continue(self):
        from playwright.async_api import async_playwright

        class DelayedProgressBackend(FakeBackend):
            def render(self, image, instruction, visible_text):
                payload = json.loads(instruction)
                self.visual_feedback.append(payload['visual_progress'])
                visible = json.loads(visible_text)
                if 'Ready' in visible['a11y_text']:
                    action = {'type': 'finish'}
                else:
                    control = next(row for row in visible['controls']
                                   if row['label'] == 'Idle')
                    action = {'type': 'click', 'target': {'ref': control['ref']}}
                self.output = json.dumps(action)
                return object(), {'input_tokens': 100, 'image_tokens': 50,
                                  'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

        with TemporaryDirectory() as folder:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(viewport={'width': 640, 'height': 480})
                    await page.set_content('<style>button,button:hover,'
                                           'button:active,button:focus{'
                                           'background:#eee;color:#000;'
                                           'border:1px solid #000;'
                                           'outline:none;box-shadow:none}'
                                           '</style><h1>Dashboard</h1>'
                                           '<button onclick="window.n=(window.n||0)+1;'
                                           "if(window.n===3)document.querySelector("
                                           "'h1').textContent='Ready'\">Idle</button>")
                    backend = DelayedProgressBackend()
                    adapter = VisionSamplingAdapter(backend, Path(folder) / 'journal',
                        limits=Limits(max_actions=84, output_tokens=512))
                    budget = pilot.BudgetedAdapter(adapter,
                        deadline=time.monotonic() + 300)
                    frames = Path(folder) / 'frames'
                    frames.mkdir()
                    policy = await pilot.execute_policy(page, budget,
                        instruction='Use the visible controls', binding='d' * 64,
                        prefix='mag777-delayed-progress-fake', frames=frames,
                        deadline=time.monotonic() + 300)
                    self.assertEqual((policy['status'], policy['failure_code']),
                                     ('completed', None))
                    self.assertEqual((policy['sample_attempt_count'],
                                      policy['applied_action_count']), (4, 4))
                    self.assertEqual([row['action_type'] for row in policy['actions']],
                                     ['click', 'click', 'click', 'finish'])
                    self.assertFalse(backend.visual_feedback[3][
                        'screenshot_and_url_unchanged'])
                finally:
                    await browser.close()

    async def test_normal_action_ceiling_is_scored_model_failure(self):
        from playwright.async_api import async_playwright

        class AlternatingBackend(FakeBackend):
            def render(self, image, instruction, visible_text):
                controls = json.loads(visible_text)['controls']
                label = 'A' if len(self.visual_feedback) % 2 == 0 else 'B'
                control = next(row for row in controls if row['label'] == label)
                self.visual_feedback.append(json.loads(instruction)['visual_progress'])
                self.output = json.dumps({'type': 'click',
                                          'target': {'ref': control['ref']}})
                return object(), {'input_tokens': 100, 'image_tokens': 50,
                                  'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

        self.assertEqual(pilot.MAX_GUI_ACTIONS, 80)
        with TemporaryDirectory() as folder:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(viewport={'width': 640, 'height': 480})
                    await page.set_content('<button>A</button><button>B</button>')
                    backend = AlternatingBackend()
                    adapter = VisionSamplingAdapter(backend, Path(folder) / 'journal',
                        limits=Limits(max_actions=3, output_tokens=512))
                    budget = pilot.BudgetedAdapter(adapter,
                        deadline=time.monotonic() + 300)
                    frames = Path(folder) / 'frames'
                    frames.mkdir()
                    with patch.object(pilot, 'MAX_GUI_ACTIONS', 3), \
                         patch.object(pilot, 'MAX_SAMPLES', 3), \
                         patch.object(pilot, 'MAX_STALE_SAMPLES', 0):
                        policy = await pilot.execute_policy(page, budget,
                            instruction='Use the visible controls', binding='e' * 64,
                            prefix='mag777-ceiling-fake', frames=frames,
                            deadline=time.monotonic() + 300)
                    self.assertEqual((policy['status'], policy['failure_class'],
                                      policy['failure_code']),
                                     ('completed', 'model_failure', 'action_budget_exhausted'))
                    self.assertEqual((policy['sample_attempt_count'],
                                      policy['applied_action_count']), (3, 3))
                    admitted = pilot.admit_scored_result(policy,
                        {'status': 'failure', 'score': 0.0},
                        {'positive_state_pass': False}, blocked=[],
                        evaluator_equal=True)
                    self.assertEqual((admitted['status'], admitted['score']),
                                     ('completed', 0.0))
                finally:
                    await browser.close()


if __name__ == '__main__':
    unittest.main()
