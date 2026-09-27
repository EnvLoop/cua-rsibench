"""The train-only login bridge never injects credentials or leaks a sandbox."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import office_web_e2b_login_bridge_v1 as bridge


class FakeStream:
    def __init__(self) -> None:
        self.auth_required = False

    def start(self, *, require_auth: bool) -> None:
        self.auth_required = require_auth

    def get_url(self, **_kwargs) -> str:
        return 'https://example.e2b.app/vnc.html'

    def get_auth_key(self) -> str:
        return 'PrivateTestKey1234'


class FakeSandbox:
    sandbox_id = 'fake-sandbox-id'

    def __init__(self, template_id: str) -> None:
        self.template_id = template_id
        self.stream = FakeStream()
        self.launched = None
        self.killed = False

    def get_info(self, **_kwargs):
        return type('Info', (), {
            'template_id': self.template_id, 'envd_version': 'test-version'})()

    def launch(self, app: str, *, uri: str) -> None:
        self.launched = (app, uri)

    def kill(self) -> bool:
        self.killed = True
        return True


class FakeFactory:
    def __init__(self, template_id: str = bridge.EXPECTED_TEMPLATE_ID):
        self.template_id = template_id
        self.created_kwargs = None
        self.sandbox = None

    def create(self, **kwargs):
        self.created_kwargs = kwargs
        self.sandbox = FakeSandbox(self.template_id)
        return self.sandbox

    def connect(self, sandbox_id: str):
        assert sandbox_id == self.sandbox.sandbox_id
        return self.sandbox


class OfficeWebLoginBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path.cwd() / 'work'
        self.work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.work)
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'login-pilot'

    def test_manual_login_session_has_no_microsoft_credentials(self) -> None:
        factory = FakeFactory()
        with patch.dict(os.environ, {'E2B_API_KEY': 'test-only-key'}):
            result = bridge.start(self.out, 600,
                                  bridge.EXPECTED_TEMPLATE_ID, factory)
        self.assertEqual(result['status'], 'awaiting_manual_login')
        self.assertEqual(factory.created_kwargs['envs'], {})
        self.assertTrue(factory.created_kwargs['secure'])
        self.assertTrue(factory.sandbox.stream.auth_required)
        self.assertEqual(factory.sandbox.launched,
                         ('google-chrome', bridge.OFFICE_URL))
        self.assertFalse(factory.sandbox.killed)
        session_path = self.out / 'session.private.json'
        session = json.loads(session_path.read_bytes())
        self.assertFalse(session['credential_or_cookie_injection'])
        self.assertEqual(session['task_split'], 'train_only')
        self.assertEqual(session_path.stat().st_mode & 0o777, 0o600)
        stopped = bridge.stop(session_path, factory)
        self.assertEqual(stopped['status'], 'killed')
        self.assertTrue(factory.sandbox.killed)

    def test_template_drift_kills_created_sandbox(self) -> None:
        factory = FakeFactory(template_id='unexpected-template-id')
        with patch.dict(os.environ, {'E2B_API_KEY': 'test-only-key'}):
            with self.assertRaisesRegex(ValueError, 'template changed'):
                bridge.start(self.out, 600,
                             bridge.EXPECTED_TEMPLATE_ID, factory)
        self.assertTrue(factory.sandbox.killed)
        self.assertFalse((self.out / 'session.private.json').exists())
        failure = json.loads((self.out / 'failure.private.json').read_bytes())
        self.assertEqual(failure['sandbox_cleanup'], 'killed')
        self.assertEqual(failure['official_final_admitted'], 0)


if __name__ == '__main__':
    unittest.main()
