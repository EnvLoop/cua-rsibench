"""Offline fake MSAL device-code enrollment; no login or Graph request."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import office_graph_msal_device_code_v1 as auth
from tools.run_office_graph_msal_device_code_v1 import main as cli_main


class FakeApp:
    calls = []
    missing_scope = False
    wrong_uri = False

    def __init__(self, client_id, *, authority):
        self.client_id = client_id
        self.authority = authority
        self.role = None

    def initiate_device_flow(self, *, scopes):
        self.role = ('owner' if 'Files.ReadWrite' in scopes
                     else 'actor')
        self.calls.append((self.role, tuple(scopes)))
        return {
            'user_code': 'ABCD-1234',
            'verification_uri': ('https://other.example/devicelogin'
                                 if self.wrong_uri else
                                 'https://microsoft.com/devicelogin'),
            'expires_at': time.time() + 600,
        }

    def acquire_token_by_device_flow(self, flow):
        scopes = ('Files.ReadWrite User.Read' if self.role == 'owner'
                  else 'Files.Read User.Read')
        return {
            'access_token': 'fake-' + self.role + '-' + 'x' * 48,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ('User.Read' if self.missing_scope else scopes),
        }


class DeviceCodeTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=work, prefix='office-msal-fake-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work_root = work
        self.config_path = self.root / 'app.private.json'
        self.config = {
            'schema': auth.APP_SCHEMA,
            'client_id': '00000000-0000-0000-0000-000000000001',
            'authority': auth.AUTHORITY,
            'account_audience': 'personal_microsoft_accounts_only',
            'public_client_flows_enabled': True,
            'role_scopes': auth.SCOPES,
            'expected_graph_user_ids': {
                'owner': 'owner1234',
                'actor': 'actor1234'},
            'max_device_seconds': 600,
        }
        self.config_path.write_bytes(auth._canonical(self.config))
        self.config_path.chmod(0o600)
        self.auth_dir = self.root / 'auth'
        FakeApp.calls = []
        FakeApp.missing_scope = False
        FakeApp.wrong_uri = False
        self.fake_msal = SimpleNamespace(
            PublicClientApplication=FakeApp)
        self.prompt = []

    def graph_me(self, token):
        return {'id': ('owner1234' if 'owner' in token else
                       'actor1234')}

    def enroll(self, role):
        return auth.login_role(
            role=role, config_path=self.config_path,
            output_dir=self.auth_dir / role,
            work_root=self.work_root,
            present=lambda uri, code: self.prompt.append((uri, code)),
            msal_module=self.fake_msal,
            graph_me=self.graph_me)

    def test_two_distinct_device_logins_make_private_scope_proof(self):
        self.assertEqual(self.enroll('owner')['role'], 'owner')
        self.assertEqual(self.enroll('actor')['role'], 'actor')
        self.assertEqual(len(self.prompt), 2)
        self.assertEqual(FakeApp.calls, [
            ('owner', ('Files.ReadWrite', 'User.Read')),
            ('actor', ('Files.Read', 'User.Read'))])
        ready = auth.finalize_scopes(
            config_path=self.config_path,
            auth_dir=self.auth_dir,
            work_root=self.work_root)
        self.assertTrue(ready['owner_actor_distinct'])
        scope_path = self.auth_dir / 'oauth-scopes.private.json'
        scope = json.loads(scope_path.read_bytes())
        self.assertEqual(scope['schema'], auth.SCOPE_SCHEMA)
        self.assertEqual(scope['owner_delegated_scopes'],
                         auth.SCOPES['owner'])
        self.assertEqual(scope['actor_delegated_scopes'],
                         auth.SCOPES['actor'])
        self.assertEqual(scope_path.stat().st_mode & 0o077, 0)
        for role in ('owner', 'actor'):
            token = self.auth_dir / role / 'access-token.private'
            self.assertEqual(token.stat().st_mode & 0o077, 0)
            self.assertNotIn(token.read_bytes(), scope_path.read_bytes())
        old_owner = os.environ.get('MS_GRAPH_OWNER_TOKEN')
        old_actor = os.environ.get('MS_GRAPH_ACTOR_TOKEN')
        seen = []
        auth.with_private_tokens(
            auth_dir=self.auth_dir, work_root=self.work_root,
            run=lambda: seen.append((
                os.environ['MS_GRAPH_OWNER_TOKEN'],
                os.environ['MS_GRAPH_ACTOR_TOKEN'])))
        self.assertNotEqual(seen[0][0], seen[0][1])
        self.assertEqual(os.environ.get('MS_GRAPH_OWNER_TOKEN'),
                         old_owner)
        self.assertEqual(os.environ.get('MS_GRAPH_ACTOR_TOKEN'),
                         old_actor)

    def test_wrong_personal_identity_refuses_before_token_storage(self):
        with self.assertRaisesRegex(auth.DeviceAuthError,
                                    'wrong_personal_account'):
            auth.login_role(
                role='owner', config_path=self.config_path,
                output_dir=self.auth_dir / 'owner',
                work_root=self.work_root,
                present=lambda *_: None,
                msal_module=self.fake_msal,
                graph_me=lambda _token: {'id': 'different'})
        self.assertFalse((self.auth_dir /
                          'owner' / 'access-token.private').exists())

    def test_missing_scope_or_changed_verification_host_fails(self):
        FakeApp.missing_scope = True
        with self.assertRaisesRegex(auth.DeviceAuthError,
                                    'granted_scopes_insufficient'):
            self.enroll('owner')
        self.assertFalse((self.auth_dir /
                          'owner' / 'access-token.private').exists())
        FakeApp.missing_scope = False
        FakeApp.wrong_uri = True
        with self.assertRaisesRegex(auth.DeviceAuthError,
                                    'verification_uri_unexpected'):
            self.enroll('owner')

    def test_config_requires_user_owned_public_client_registration(self):
        self.config['client_id'] = 'not-an-app-registration'
        self.config_path.write_bytes(auth._canonical(self.config))
        with self.assertRaisesRegex(auth.DeviceAuthError,
                                    'app_registration_config_invalid'):
            auth.load_app_config(self.config_path,
                                 self.work_root)
        self.assertEqual(FakeApp.calls, [])

    def test_check_config_is_offline_and_field_limited(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli_main([
                '--work-root', str(self.work_root),
                '--config', str(self.config_path),
                '--auth-dir', str(self.auth_dir),
                'check-config'])
        self.assertEqual(code, 0)
        self.assertIn('provider_calls', output.getvalue())
        self.assertNotIn(self.config['client_id'],
                         output.getvalue())
        self.assertEqual(FakeApp.calls, [])

    def test_changed_access_token_blocks_pilot_wrapper(self):
        self.enroll('owner')
        self.enroll('actor')
        auth.finalize_scopes(
            config_path=self.config_path,
            auth_dir=self.auth_dir,
            work_root=self.work_root)
        token = self.auth_dir / 'actor' / 'access-token.private'
        token.write_bytes(b'tampered-token')
        with self.assertRaisesRegex(auth.DeviceAuthError,
                                    'access_token_changed'):
            auth.with_private_tokens(
                auth_dir=self.auth_dir, work_root=self.work_root,
                run=lambda: self.fail('pilot must not run'))


if __name__ == '__main__':
    unittest.main()
