"""Fake-provider acceptance for Excel-web's train-only screenshot actor."""

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

from tools import excel_web_e2b_train_runner_v1 as runner
from tools import office_web_e2b_login_bridge_v1 as bridge
from tests.office_actor_scope_fixture import write_scope_fixture


def png(color='white'):
    stream = io.BytesIO()
    Image.new('RGB', (64, 48), color).save(stream, format='PNG')
    return stream.getvalue()


def xlsx():
    main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as package:
        package.writestr('[Content_Types].xml', '<Types/>')
        package.writestr('xl/workbook.xml',
                         f'<workbook xmlns="{main}" xmlns:r="{rel}">'
                         '<sheets><sheet name="Review" sheetId="1" '
                         'r:id="rId1"/></sheets></workbook>')
        package.writestr('xl/_rels/workbook.xml.rels',
                         '<Relationships><Relationship Id="rId1" '
                         'Target="worksheets/sheet1.xml"/></Relationships>')
        package.writestr('xl/worksheets/sheet1.xml',
                         f'<worksheet xmlns="{main}"><sheetData><row r="1">'
                         '<c r="A1"><v>1</v></c></row></sheetData></worksheet>')
    return stream.getvalue()


class FakeSandbox:
    sandbox_id = 'sandbox-excel-1234'

    def __init__(self, *, change_during_sample=False):
        self.calls = []
        self.screen = png()
        self.screenshots = 0
        self.change_during_sample = change_during_sample

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

    def write(self, value):
        self.calls.append(('write', value))

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
    def retrieve(self, _sandbox, _admission):
        return xlsx()


class ExcelWebTrainRunnerTests(unittest.TestCase):
    def setUp(self):
        private = Path.cwd() / 'work'
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task_id = 'xl-train-' + 'a' * 16
        self.session = self.root / 'login' / 'session.private.json'
        self.session.parent.mkdir()
        self.task = (self.root / 'packages' / 'train' /
                     self.task_id / 'task.private.json')
        self.task.parent.mkdir(parents=True)
        self.config = self.root / 'run.private.json'
        self.out = self.root / 'run-output'
        self.actor = self.task.parent / 'actor.xlsx'
        self.actor.write_bytes(xlsx())
        self.actor.chmod(0o600)
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
            'actor_task': 'Repair the visible train workbook and save it.',
            'actor_xlsx_sha256': runner.digest(self.actor.read_bytes()),
        }
        self.config_data = {
            'schema': runner.CONFIG_SCHEMA, 'split': 'train',
            'manual_login_confirmed_at_unix': now - 10,
            'workbook_url': (
                'https://onedrive.live.com/personal/'
                '0123456789ABCDEF/_layouts/15/Doc.aspx?'
                'sourcedoc=%7B00000000-0000-4000-8000-000000000000%7D'
                '&file=EL-Excel-Train-Example.xlsx&action=default'
                '&mobileredirect=true'),
            'max_steps': 3, 'wall_seconds': 300,
        }
        self.write_inputs()

    def write_inputs(self):
        for path, value in ((self.session, self.session_data),
                            (self.task, self.task_data),
                            (self.config, self.config_data)):
            if path.exists():
                path.unlink()
            bridge.write_new(path, value)
        write_scope_fixture(self.session, self.session_data,
                            self.config_data['workbook_url'], 'excel',
                            self.task_data['actor_xlsx_sha256'], png())

    def test_missing_actor_scope_denies_before_provider_connect(self):
        (self.session.parent / 'actor-scope.private.json').unlink()
        factory = FakeFactory()
        with self.assertRaisesRegex(runner.RunnerError,
                                    'actor_scope_unverified'):
            runner.run(self.session, self.task, self.config,
                       self.out, factory)
        self.assertEqual(factory.connect_calls, [])
        self.assertFalse(self.out.exists())

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

    def test_train_only_gui_journal_teardown_and_fail_closed_artifact(self):
        result, factory, sampler, service = self.invoke([
            {'type': 'click', 'target': {'x': 0, 'y': 0}},
            {'type': 'finish'},
        ])
        self.assertEqual(result['status'], 'artifact_gate_blocked')
        self.assertEqual(result['teardown'], 'killed')
        self.assertEqual((result['samples'], result['gui_actions']), (2, 1))
        self.assertFalse(result['cloud_seed_binding_qualified'])
        self.assertEqual(result['official_final_admitted'], 0)
        self.assertEqual(factory.connect_calls,
                         [((FakeSandbox.sandbox_id,), {})])
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])
        self.assertIn(('move_mouse', 0, 0), factory.sandbox.calls)
        self.assertIn(('left_click',), factory.sandbox.calls)
        self.assertEqual(service.close_status, 'success')
        sent = json.dumps(sampler.requests, default=lambda _: '<bytes>')
        for hidden in ('PrivateTestKey1234', FakeSandbox.sandbox_id,
                       self.config_data['workbook_url'],
                       self.task_data['actor_xlsx_sha256']):
            self.assertNotIn(hidden, sent)
        self.assertIn('Repair the visible train workbook', sent)
        events = [json.loads(line) for line in
                  (self.out / 'events.private.jsonl').read_text().splitlines()]
        self.assertEqual([row['sequence'] for row in events],
                         list(range(1, len(events) + 1)))
        self.assertEqual(len([row for row in events if
                              row['event'] == 'model_request_intent']), 2)
        self.assertEqual(len([row for row in events if
                              row['event'] == 'gui_action_intent']), 2)
        self.assertEqual(events[-1]['event'], 'teardown_result')
        self.assertEqual((self.out / 'events.private.jsonl').stat().st_mode
                         & 0o777, 0o600)
        frame = self.out / 'frame-000.private.png'
        self.assertEqual(runner.digest(frame.read_bytes()),
                         json.loads((self.out / 'frame-000.private.json')
                                    .read_text())['screenshot_sha256'])
        self.assertEqual(frame.stat().st_mode & 0o777, 0o600)
        stop = json.loads((self.session.parent / 'stop.private.json').read_text())
        self.assertEqual(stop['model_calls'], 2)

    def test_final_package_and_oracle_field_rejected_before_connect(self):
        final = self.root / 'packages' / 'final' / self.task_id / 'task.private.json'
        final.parent.mkdir(parents=True)
        bridge.write_new(final, self.task_data)
        with self.assertRaisesRegex(runner.RunnerError,
                                    'train_package_path_required'):
            runner.admit(self.session, final, self.config, self.out)
        self.task_data['oracle'] = {'answer': 'hidden'}
        self.write_inputs()
        with self.assertRaisesRegex(runner.RunnerError,
                                    'invalid_train_package'):
            runner.admit(self.session, self.task, self.config, self.out)
        self.assertFalse(self.out.exists())

    def test_actor_seed_binding_mismatch_rejected(self):
        self.task_data['actor_xlsx_sha256'] = '0' * 64
        self.write_inputs()
        with self.assertRaisesRegex(runner.RunnerError,
                                    'actor_seed_hash_mismatch'):
            runner.admit(self.session, self.task, self.config, self.out)

    def test_observed_excel_url_shape_rejects_other_hosts_and_final(self):
        valid = self.config_data['workbook_url']
        self.assertEqual(runner.validate_train_workbook_url(valid), valid)
        for bad in (
            valid.replace('EL-Excel-Train-Example', 'EL-Excel-Final-021'),
            valid.replace('onedrive.live.com', 'untrusted.example'),
            valid.replace('action=default', 'action=download'),
            valid + '&file=EL-Excel-Train-Other.xlsx',
            valid.replace('https://', 'http://'),
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(runner.RunnerError,
                                            'invalid_train_workbook_url'):
                    runner.validate_train_workbook_url(bad)

    def test_stale_pixels_never_dispatch_even_after_valid_model_action(self):
        factory = FakeFactory(change_during_sample=True)
        result, factory, _, _ = self.invoke([
            {'type': 'click', 'target': {'x': 10, 'y': 10}}],
            factory=factory)
        self.assertEqual(result['status'], 'frame_changed_during_sampling')
        self.assertEqual(result['gui_actions'], 0)
        self.assertFalse(any(call[0] == 'left_click'
                             for call in factory.sandbox.calls))
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])

    def test_excel_text_edit_uses_only_validated_pixel_actions(self):
        result, factory, _, _ = self.invoke([
            {'action': 'type', 'target': {'x': 6, 'y': 7},
             'text': '=SUM(A1:A2)', 'mode': 'fill'},
            {'type': 'key', 'key': 'Enter'},
            {'type': 'finish'},
        ])
        self.assertEqual(result['status'], 'artifact_gate_blocked')
        self.assertEqual(result['gui_actions'], 2)
        self.assertIn(('move_mouse', 6, 7), factory.sandbox.calls)
        self.assertIn(('press', ['ctrl', 'a']), factory.sandbox.calls)
        self.assertIn(('write', '=SUM(A1:A2)'), factory.sandbox.calls)
        self.assertIn(('press', 'enter'), factory.sandbox.calls)

    def test_invented_control_ref_never_dispatches(self):
        result, factory, _, _ = self.invoke([
            {'type': 'click', 'target': {'ref': 'invented'}}])
        self.assertEqual(result['status'], 'stale_frame')
        self.assertEqual(result['gui_actions'], 0)
        self.assertFalse(any(call[0] == 'left_click'
                             for call in factory.sandbox.calls))

    def test_injected_package_readback_stays_unscored(self):
        result, _, _, _ = self.invoke([{'type': 'finish'}],
                                      retriever=FakeArtifactRetriever())
        self.assertEqual(result['status'], 'artifact_readback_unscored')
        self.assertEqual(result['artifact']['sheet_count'], 1)
        self.assertEqual(result['artifact']['status'],
                         'package_readback_only_unscored')
        self.assertFalse(result['cloud_seed_binding_qualified'])
        with self.assertRaisesRegex(runner.RunnerError,
                                    'invalid_saved_xlsx'):
            runner.readback_xlsx(b'not an Excel workbook')

    def test_provider_error_and_desktop_identity_mismatch_still_teardown(self):
        result, factory, _, service = self.invoke([])
        self.assertEqual(result['status'], 'provider_or_desktop_error')
        self.assertEqual(result['teardown'], 'killed')
        self.assertEqual(factory.kill_calls, [FakeSandbox.sandbox_id])
        self.assertEqual(service.close_status, 'errored')

        self.out = self.root / 'run-output-again'
        self.session.parent.joinpath('stop.private.json').unlink()
        factory = FakeFactory()
        factory.sandbox.sandbox_id = 'another-desktop-1234'
        result, factory, sampler, _ = self.invoke([], factory=factory)
        self.assertEqual(result['status'], 'desktop_identity_mismatch')
        self.assertEqual(result['teardown'], 'killed')
        self.assertEqual(sampler.requests, [])
        self.assertFalse(any(call[0] == 'launch'
                             for call in factory.sandbox.calls))

    def test_unconfirmed_login_and_expired_lease_rejected(self):
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
