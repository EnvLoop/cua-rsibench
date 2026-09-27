"""Offline acceptance tests for the train-only original Office desktop pilot."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from tools import office_web_e2b_login_bridge_v1 as bridge
from tools import office_web_e2b_train_runner_v1 as runner


def png(color='white'):
    output = io.BytesIO()
    Image.new('RGB', (64, 48), color).save(output, format='PNG')
    return output.getvalue()


def valid_pptx():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as package:
        for name in ('[Content_Types].xml', 'ppt/presentation.xml',
                     'ppt/_rels/presentation.xml.rels',
                     'ppt/slides/slide1.xml'):
            package.writestr(name, '<root/>')
    return output.getvalue()


class FakeSandbox:
    sandbox_id = 'sandbox-test-1234'

    def __init__(self, *, change_during_sample=False):
        self.calls = []
        self.screen = png()
        self.change_during_sample = change_during_sample
        self.screenshots = 0

    def get_info(self, **kwargs):
        self.calls.append(('get_info', kwargs))
        return type('Info', (), {'template_id': bridge.EXPECTED_TEMPLATE_ID})()

    def launch(self, app, *, uri):
        self.calls.append(('launch', app, uri))

    def screenshot(self):
        self.screenshots += 1
        if self.change_during_sample and self.screenshots == 2:
            return png('black')
        return self.screen

    def move_mouse(self, x, y):
        self.calls.append(('move_mouse', x, y))

    def left_click(self):
        self.calls.append(('left_click',))

    def press(self, key):
        self.calls.append(('press', key))

    def write(self, text):
        self.calls.append(('write', text))

    def scroll(self, **kwargs):
        self.calls.append(('scroll', kwargs))

    def drag(self, start, end):
        self.calls.append(('drag', start, end))


class FakeFactory:
    def __init__(self, **kwargs):
        self.sandbox = FakeSandbox(**kwargs)
        self.connect_calls = []
        self.kill_calls = []

    def connect(self, *args, **kwargs):
        self.connect_calls.append((args, kwargs))
        return self.sandbox

    def kill(self, sandbox_id):
        self.kill_calls.append(sandbox_id)
        return True


class FakeService:
    def __init__(self):
        self.close_status = None

    def close(self, status):
        self.close_status = status
        return type('Future', (), {'result': lambda self, timeout: None})()


class FakeSampler:
    binding = {'backend': {'model': runner.MODEL}}

    def __init__(self, actions):
        self.actions = list(actions)
        self.requests = []

    def sample(self, *, request_id, image_bytes, instruction, visible_text):
        self.requests.append({'request_id': request_id,
                              'image_bytes': image_bytes,
                              'instruction': instruction,
                              'visible_text': visible_text})
        return {'request_id': request_id, 'status': 'completed',
                'text': json.dumps(self.actions.pop(0)), 'usage': {}}


class FakeArtifactRetriever:
    def retrieve(self, sandbox, admission):
        return valid_pptx()


class OfficeWebTrainRunnerTests(unittest.TestCase):
    def setUp(self):
        private = Path.cwd() / 'work'
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task_id = 'ppt-wdi-' + 'a' * 16
        self.session = self.root / 'login' / 'session.private.json'
        self.session.parent.mkdir()
        self.task = (self.root / 'packages' / 'train' /
                     self.task_id / 'task.private.json')
        self.task.parent.mkdir(parents=True)
        self.config = self.root / 'run.private.json'
        self.out = self.root / 'run-output'
        now = int(time.time())
        self.session_data = {
            'schema': bridge.SCHEMA,
            'status': 'awaiting_manual_login',
            'task_split': 'train_only',
            'account_login': 'manual_only',
            'credential_or_cookie_injection': False,
            'credential_snapshot_or_export': False,
            'official_final_admitted': 0,
            'model_calls': 0,
            'sdk_version': '2.2.0',
            'expected_template_id': bridge.EXPECTED_TEMPLATE_ID,
            'observed_template_id': bridge.EXPECTED_TEMPLATE_ID,
            'lease_started_at_unix': now - 30,
            'lease_seconds': 900,
            'sandbox_id': FakeSandbox.sandbox_id,
            'stream_url': 'https://private.e2b.app/vnc.html',
            'stream_auth_key': 'PrivateTestKey1234',
        }
        self.task_data = {
            'schema': runner.TASK_SCHEMA, 'split': 'train',
            'official_final_credit': 0, 'task_id': self.task_id,
            'actor_task': 'Change the visible train slide and save.',
            'correct': {'gold': 'TRAIN_ONLY_SECRET'},
        }
        self.config_data = {
            'schema': runner.CONFIG_SCHEMA, 'split': 'train',
            'manual_login_confirmed_at_unix': now - 10,
            'deck_url': ('https://onedrive.live.com/personal/'
                         '0123456789ABCDEF/_layouts/15/Doc.aspx?'
                         'sourcedoc=%7B00000000-0000-4000-8000-000000000000%7D'
                         '&file=EL-PPT-Train-Example.pptx&action=edit'
                         '&mobileredirect=true'),
            'max_steps': 3, 'wall_seconds': 300,
        }
        self.write_inputs()

    def write_inputs(self):
        for path, data in ((self.session, self.session_data),
                           (self.task, self.task_data),
                           (self.config, self.config_data)):
            if path.exists():
                path.unlink()
            bridge.write_new(path, data)

    def invoke(self, actions, *, factory=None, retriever=None):
        factory = factory or FakeFactory()
        sampler = FakeSampler(actions)
        service = FakeService()
        def make_sampler(path, max_steps):
            self.assertEqual(path, self.out / 'proxy')
            self.assertEqual(max_steps, 3)
            return sampler, service
        with patch.dict(os.environ, {'E2B_API_KEY': 'fake-only'}):
            result = runner.run(self.session, self.task, self.config,
                                self.out, factory, make_sampler, retriever)
        return result, factory, sampler, service

    def test_train_only_gui_journal_and_teardown_with_fail_closed_artifact(self):
        result, factory, sampler, service = self.invoke([
            {'type': 'click', 'target': {'x': 0, 'y': 0}},
            {'type': 'finish'},
        ])
        self.assertEqual(result['status'], 'artifact_gate_blocked')
        self.assertEqual(result['teardown'], 'killed')
        self.assertEqual(result['samples'], 2)
        self.assertEqual(result['gui_actions'], 1)
        self.assertEqual(factory.connect_calls,
                         [((FakeSandbox.sandbox_id,), {})])
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])
        self.assertIn(('move_mouse', 0, 0), factory.sandbox.calls)
        self.assertIn(('left_click',), factory.sandbox.calls)
        self.assertEqual(service.close_status, 'success')
        self.assertEqual(len(sampler.requests), 2)
        sent = json.dumps(sampler.requests[0], default=lambda x: '<bytes>')
        for private in ('TRAIN_ONLY_SECRET', 'PrivateTestKey1234',
                        FakeSandbox.sandbox_id, self.config_data['deck_url']):
            self.assertNotIn(private, sent)
        self.assertIn('Change the visible train slide', sent)
        events_path = self.out / 'events.private.jsonl'
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        self.assertEqual([row['sequence'] for row in events],
                         list(range(1, len(events) + 1)))
        self.assertEqual(len([row for row in events if
                              row['event'] == 'model_request_intent']), 2)
        self.assertEqual(len([row for row in events if
                              row['event'] == 'model_request_result']), 2)
        self.assertEqual(len([row for row in events if
                              row['event'] == 'gui_action_intent']), 2)
        self.assertEqual(events[-1]['event'], 'teardown_result')
        self.assertEqual(events_path.stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.session.parent / 'stop.private.json').exists())
        self.assertNotIn('PrivateTestKey1234', events_path.read_text())

    def test_final_package_path_and_split_rejected_before_connect(self):
        final = self.root / 'packages' / 'final' / self.task_id / 'task.private.json'
        final.parent.mkdir(parents=True)
        bridge.write_new(final, self.task_data)
        with self.assertRaisesRegex(runner.RunnerError,
                                    'train_package_path_required'):
            runner.admit(self.session, final, self.config, self.out)
        self.task_data['split'] = 'official_final'
        self.write_inputs()
        with self.assertRaisesRegex(runner.RunnerError,
                                    'invalid_train_package'):
            runner.admit(self.session, self.task, self.config, self.out)
        self.assertFalse(self.out.exists())

    def test_observed_onedrive_train_route_rejects_final_or_other_hosts(self):
        self.assertEqual(
            runner.validate_train_deck_url(self.config_data['deck_url']),
            self.config_data['deck_url'])
        for bad in (
            self.config_data['deck_url'].replace(
                'EL-PPT-Train-Example', 'EL-PPT-Final-021'),
            self.config_data['deck_url'].replace(
                'onedrive.live.com', 'untrusted.example'),
            self.config_data['deck_url'].replace(
                'action=edit', 'action=default'),
            self.config_data['deck_url'] + '&file=EL-PPT-Train-Other.pptx',
        ):
            with self.subTest(url=bad):
                with self.assertRaisesRegex(runner.RunnerError,
                                            'invalid_train_deck_url'):
                    runner.validate_train_deck_url(bad)

    def test_stale_frame_never_dispatches_and_still_kills(self):
        factory = FakeFactory(change_during_sample=True)
        result, factory, _, service = self.invoke([
            {'type': 'click', 'target': {'x': 10, 'y': 10}}],
            factory=factory)
        self.assertEqual(result['status'], 'frame_changed_during_sampling')
        self.assertEqual(result['gui_actions'], 0)
        self.assertFalse(any(call[0] == 'left_click'
                             for call in factory.sandbox.calls))
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])
        self.assertEqual(service.close_status, 'errored')

    def test_invalid_model_action_never_dispatches(self):
        result, factory, _, _ = self.invoke([
            {'type': 'click', 'target': {'ref': 'invented'}}])
        self.assertEqual(result['status'], 'stale_frame')
        self.assertEqual(result['gui_actions'], 0)
        self.assertFalse(any(call[0] == 'left_click'
                             for call in factory.sandbox.calls))

    def test_connect_failure_still_uses_class_level_kill(self):
        class FailingConnectFactory(FakeFactory):
            def connect(self, *args, **kwargs):
                self.connect_calls.append((args, kwargs))
                raise RuntimeError('offline fake connect failure')
        factory = FailingConnectFactory()
        result, _, sampler, _ = self.invoke([], factory=factory)
        self.assertEqual(result['status'], 'provider_or_desktop_error')
        self.assertEqual(result['teardown'], 'killed')
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])
        self.assertEqual(sampler.requests, [])

    def test_reconnect_identity_mismatch_never_launches_or_samples(self):
        factory = FakeFactory()
        factory.sandbox.sandbox_id = 'different-sandbox-1234'
        result, _, sampler, _ = self.invoke([], factory=factory)
        self.assertEqual(result['status'], 'desktop_identity_mismatch')
        self.assertFalse(any(call[0] == 'launch'
                             for call in factory.sandbox.calls))
        self.assertEqual(sampler.requests, [])
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])

    def test_artifact_interface_checks_pptx_but_does_not_score(self):
        result, _, _, _ = self.invoke([{'type': 'finish'}],
                                      retriever=FakeArtifactRetriever())
        self.assertEqual(result['status'], 'artifact_readback_unscored')
        self.assertEqual(result['artifact']['slide_xml_count'], 1)
        self.assertEqual(result['artifact']['status'],
                         'package_readback_only_unscored')
        with self.assertRaisesRegex(runner.RunnerError, 'invalid_saved_pptx'):
            runner.readback_pptx(b'not a PowerPoint')

    def test_expired_lease_and_unconfirmed_login_fail_preflight(self):
        self.session_data['lease_started_at_unix'] = int(time.time()) - 900
        self.write_inputs()
        with self.assertRaisesRegex(runner.RunnerError,
                                    'lease_expired_or_too_short'):
            runner.admit(self.session, self.task, self.config, self.out)
        self.session_data['lease_started_at_unix'] = int(time.time()) - 30
        self.config_data['manual_login_confirmed_at_unix'] = 0
        self.write_inputs()
        with self.assertRaisesRegex(runner.RunnerError,
                                    'invalid_run_config'):
            runner.admit(self.session, self.task, self.config, self.out)


if __name__ == '__main__':
    unittest.main()
