"""Offline fake-backend GUI checks and exact pinned task-157 evaluator checks."""
import asyncio
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from cursibench.scale_vision_proxy import (
    Limits, MODEL, PROCESSOR, RENDERER, VisionSamplingAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'magento_model_pilot', ROOT / 'tools/run_magento_model_pilot_v06.py')
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class FakeFuture:
    def __init__(self, backend):
        self.backend = backend

    def result(self, timeout):
        if self.backend.error:
            raise self.backend.error
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1], stop_reason='stop')],
                               prompt_cache_hit_tokens=0)


class FakeBackend:
    """Uses only the same rendered model inputs the real backend receives."""
    def __init__(self, mode='navigate'):
        self.identity = {'model': MODEL, 'renderer': RENDERER,
                         'image_processor': PROCESSOR, 'sampling_kind': 'base', 'seed': 23}
        self.mode = mode
        self.error = None
        self.calls = 0
        self.output = ''

    def render(self, image, instruction, visible_text):
        turn = json.loads(instruction)
        visible = json.loads(visible_text)
        labels = {row['label']: row['ref'] for row in visible['controls']}
        assert image.size == (640, 480)
        if self.mode == 'shell':
            kind, extra = 'shell', {'command': 'echo forbidden'}
        elif turn['step'] == 0:
            kind, extra = 'click', {'target': {'ref': labels['Customers']}}
        elif turn['step'] == 1:
            kind, extra = 'click', {'target': {'ref': labels['All Customers']}}
        else:
            kind, extra = 'finish', {}
        self.output = json.dumps({
            'version': turn['version'], 'task_id': turn['task_id'],
            'task_binding_sha256': turn['task_binding_sha256'],
            'step': turn['step'], 'frame_id': turn['frame_id'],
            'type': kind, 'memory': 'Menu opened.', **extra,
        })
        return object(), {'input_tokens': 80, 'image_tokens': 40,
                          'chunk_types': ['EncodedTextChunk', 'ImageChunk']}

    def submit(self, prompt, max_output_tokens):
        self.calls += 1
        return FakeFuture(self)

    def decode(self, tokens):
        return self.output


class PilotBoundaries(unittest.TestCase):
    def test_strict_local_origin_and_read_only_measurement(self):
        self.assertTrue(pilot.permitted_request('http://localhost:7780/admin', 'GET'))
        self.assertTrue(pilot.permitted_request('http://127.0.0.1:7780/admin', 'HEAD'))
        self.assertTrue(pilot.permitted_request('http://localhost:7780/admin/login', 'POST', setup=True))
        for url, method in (
            ('http://localhost:7780/admin', 'POST'),
            ('http://localhost:7781/admin', 'GET'),
            ('http://localhost.evil.com:7780/admin', 'GET'),
            ('https://localhost:7780/admin', 'GET'),
            ('http://user:secret@localhost:7780/admin', 'GET'),
            ('http://[::1]:7780/admin', 'GET'),
            ('http://localhost:notaport/admin', 'GET'),
        ):
            with self.subTest(url=url):
                self.assertFalse(pilot.permitted_request(url, method))

    def test_public_urls_and_blocked_requests_cannot_expose_query_values(self):
        self.assertEqual(
            pilot.public_url('http://localhost:7780/admin/customer/index/?email=private%40example.com&form_key=secret'),
            'http://localhost:7780/admin/customer/index/')
        self.assertEqual(pilot.sampling_failure_class('provider_timeout_uncertain'),
                         'transport_or_provider_failure')
        self.assertEqual(pilot.sampling_failure_class('rendering_error'),
                         'environment_failure')
        self.assertEqual(pilot.campaign_metadata(pilot.CAMPAIGN_ID)['campaign_id'],
                         'magento-base-pilot-v1')

    def test_admission_rejects_blocked_network_and_keeps_scores_consistent(self):
        policy = {'status': 'completed', 'failure_class': None, 'failure_code': None}
        official = {'status': 'success', 'score': 1.0}
        gui = {'grid_loaded': True}
        blocked = pilot.admit_outcome(policy, official, gui,
            blocked=[{'method': 'POST', 'url_sha256': 'a' * 64}], business_unchanged=True)
        self.assertEqual((blocked['status'], blocked['score'], blocked['failure_code']),
                         ('unscored', None, 'blocked_network_request'))
        changed = pilot.admit_outcome(policy, official, gui,
            blocked=[], business_unchanged=False)
        self.assertEqual((changed['status'], changed['score']), ('unscored', None))
        late_parse = policy | {'failure_class': 'model_failure', 'failure_code': 'invalid_action'}
        reached = pilot.admit_outcome(late_parse, official, gui,
            blocked=[], business_unchanged=True)
        self.assertEqual((reached['score'], reached['failure_class']), (1.0, None))
        self.assertIn('later invalid model action', reached['qualification_note'])
        no_grid = pilot.admit_outcome(late_parse, official, {'grid_loaded': False},
            blocked=[], business_unchanged=True)
        self.assertEqual((no_grid['score'], no_grid['failure_class'], no_grid['failure_code']),
                         (0.0, 'model_failure', 'final_grid_not_loaded'))
        wrong_route = pilot.admit_outcome(policy, {'status': 'failure', 'score': 0.0}, gui,
            blocked=[], business_unchanged=True)
        self.assertEqual((wrong_route['score'], wrong_route['failure_class']),
                         (0.0, 'model_failure'))


class FakeBrowserPilot(unittest.IsolatedAsyncioTestCase):
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
          <button onclick="document.getElementById('all').hidden=false">Customers</button>
          <button hidden id="all" onclick="document.querySelector('h1').textContent='Customers';
            document.getElementById('grid').hidden=false">All Customers</button>
          <table id="grid" hidden><tbody><tr><td>1</td><td>One</td></tr>
          <tr><td>2</td><td>Two</td></tr></tbody></table>
          <button hidden onclick="window.secret=true">Hidden Delete</button>
        ''')

    async def asyncTearDown(self):
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()
        self.temp.cleanup()

    def adapter(self, backend):
        return VisionSamplingAdapter(backend, Path(self.temp.name) / 'journal',
                                     limits=Limits(max_actions=pilot.MAX_ACTIONS))

    async def test_fake_proxy_observes_visible_controls_and_dispatches_only_gui_actions(self):
        backend = FakeBackend()
        policy = await pilot.execute_policy(
            self.page, self.adapter(backend), instruction='View the details of all customers',
            binding='a' * 64, request_prefix='fake-magento-157')
        self.assertEqual(policy['status'], 'completed')
        self.assertEqual([row['action_type'] for row in policy['actions']],
                         ['click', 'click', 'finish'])
        self.assertEqual(backend.calls, 3)
        self.assertEqual(await self.page.locator('h1').inner_text(), 'Customers')
        self.assertEqual(await self.page.locator('#grid tr:visible').count(), 2)
        self.assertFalse(await self.page.evaluate('Boolean(window.secret)'))
        self.assertNotIn('Hidden Delete', json.dumps(policy))

    async def test_shell_model_output_is_rejected_before_browser_dispatch(self):
        backend = FakeBackend(mode='shell')
        policy = await pilot.execute_policy(
            self.page, self.adapter(backend), instruction='View the details of all customers',
            binding='a' * 64, request_prefix='fake-shell-157')
        self.assertEqual((policy['status'], policy['failure_class']),
                         ('completed', 'model_failure'))
        self.assertEqual(policy['failure_code'], 'invalid_action')
        self.assertEqual(await self.page.locator('h1').inner_text(), 'Dashboard')
        self.assertEqual(backend.calls, 1)

    async def test_provider_timeout_is_unscored_and_not_retried(self):
        backend = FakeBackend()
        backend.error = TimeoutError('provider timed out')
        policy = await pilot.execute_policy(
            self.page, self.adapter(backend), instruction='View the details of all customers',
            binding='a' * 64, request_prefix='fake-timeout-157')
        self.assertEqual((policy['status'], policy['failure_class']),
                         ('unscored', 'transport_or_provider_failure'))
        self.assertEqual(policy['failure_code'], 'provider_timeout_uncertain')
        self.assertEqual(backend.calls, 1)
        self.assertEqual(await self.page.locator('h1').inner_text(), 'Dashboard')


@unittest.skipUnless(pilot.SOURCE.exists() and
                     importlib.util.find_spec('webarena_verified') is not None,
                     'pinned WebArena source and package required')
class PublishedEvaluatorIntegration(unittest.TestCase):
    def test_exact_task_157_positive_and_negative_are_discriminated(self):
        task, proof = pilot.smoke.source_proof(pilot.SOURCE)
        self.assertEqual(task['task_id'], 157)
        self.assertEqual(proof['git_commit'], pilot.smoke.COMMIT)
        official = pilot.smoke.evaluator(pilot.SOURCE)

        def trace(path):
            raw = {'log': {'entries': [{
                'request': {'url': pilot.BASE + path, 'method': 'GET',
                            'headers': [{'name': 'Accept', 'value': 'text/html'},
                                        {'name': 'Cookie', 'value': 'private'}]},
                'response': {'status': 200, 'headers': [], 'redirectURL': '',
                             'content': {}},
            }]}}
            return raw, pilot.smoke.sanitize_har(raw)

        positive_raw, positive_clean = trace('/customer/index/')
        negative_raw, negative_clean = trace('/sales/order/')
        positive = pilot.smoke.evaluate(official, positive_clean['log']['entries'])
        negative = pilot.smoke.evaluate(official, negative_clean['log']['entries'])
        self.assertEqual((positive['status'], positive['score']), ('success', 1.0))
        self.assertEqual((negative['status'], negative['score']), ('failure', 0.0))
        self.assertEqual(positive['evaluator_checksum'], negative['evaluator_checksum'])
        self.assertNotIn('private', json.dumps(positive_clean))
        self.assertEqual(pilot.smoke.evaluate(official, positive_raw['log']['entries']), positive)
        self.assertEqual(pilot.smoke.evaluate(official, negative_raw['log']['entries']), negative)


if __name__ == '__main__':
    unittest.main()
