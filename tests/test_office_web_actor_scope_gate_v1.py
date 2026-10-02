"""Offline negative controls for the Office one-file actor evidence gate."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import time
import unittest

from PIL import Image

from tests.office_actor_scope_fixture import write_scope_fixture
from tools import office_web_actor_scope_gate_v1 as gate
from tools import office_web_e2b_login_bridge_v1 as bridge


def png() -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(stream, format='PNG')
    return stream.getvalue()


class OfficeActorScopeGateTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.session = self.directory / 'session.private.json'
        now = int(time.time())
        self.session_data = {
            'sandbox_id': 'sandbox-test-1234',
            'lease_started_at_unix': now - 30,
            'lease_seconds': 900,
        }
        bridge.write_new(self.session, self.session_data)
        self.url = 'https://onedrive.live.com/personal/0123456789ABCDEF/train'
        self.seed = gate.digest(b'synthetic-seed')
        self.receipt = write_scope_fixture(
            self.session, self.session_data, self.url, 'excel',
            self.seed, png())
        self.scope = self.directory / 'actor-scope.private.json'

    def check(self, **overrides):
        args = {
            'session_raw': self.session.read_bytes(),
            'sandbox_id': self.session_data['sandbox_id'],
            'item_url': self.url, 'app': 'excel',
            'lease_started_at_unix': self.session_data['lease_started_at_unix'],
            'lease_end_unix': (self.session_data['lease_started_at_unix'] +
                               self.session_data['lease_seconds']),
            'actor_seed_sha256': self.seed,
        }
        args.update(overrides)
        return gate.validate(self.scope, **args)

    def replace(self, path: Path, value: dict):
        path.unlink(missing_ok=True)
        bridge.write_new(path, value)

    def replace_receipt(self):
        self.replace(self.scope, self.receipt)

    def replace_permissions(self, name: str, mutation):
        path = self.directory / f'{name}-permissions.private.json'
        snapshot = json.loads(path.read_bytes())
        mutation(snapshot)
        self.replace(path, snapshot)
        key = 'owner_permissions' if name == 'assigned' else 'parent_permissions'
        self.receipt[key]['sha256'] = gate.digest(path.read_bytes())
        self.replace_receipt()

    def test_bound_synthetic_shape_is_explicitly_not_live_acl_proof(self):
        result = self.check()
        self.assertEqual(result['status'],
                         'train_scope_evidence_accepted_operator_review_only')
        self.assertEqual(result['official_final_admitted'], 0)
        self.assertEqual(len(result['receipt_sha256']), 64)

    def test_missing_stale_or_replayed_receipt_fails(self):
        self.scope.unlink()
        with self.assertRaisesRegex(gate.ScopeError,
                                    'private_scope_evidence_required'):
            self.check()
        self.replace_receipt()
        with self.assertRaisesRegex(gate.ScopeError,
                                    'scope_binding_or_freshness_failed'):
            self.check(item_url=self.url + '-another')
        self.receipt['observed_at_unix'] -= 3600
        self.replace_receipt()
        with self.assertRaisesRegex(gate.ScopeError,
                                    'scope_binding_or_freshness_failed'):
            self.check()

    def test_owner_actor_collision_and_review_gap_fail(self):
        self.receipt['actor_email'] = self.receipt['owner_email']
        self.receipt['actor_principal_sha256'] = self.receipt[
            'owner_principal_sha256']
        self.replace_receipt()
        with self.assertRaisesRegex(gate.ScopeError,
                                    'invalid_scope_principals_or_items'):
            self.check()
        self.receipt['actor_email'] = 'actor@example.test'
        self.receipt['actor_principal_sha256'] = gate.digest('actor@example.test')
        self.receipt['reviews']['sentinel_file_denied'] = False
        self.replace_receipt()
        with self.assertRaisesRegex(gate.ScopeError,
                                    'scope_operator_review_incomplete'):
            self.check()

    def test_anyone_or_extra_share_and_shared_parent_fail(self):
        def add_anyone(snapshot):
            snapshot['response']['value'].append({
                'id': 'anonymous-link', 'roles': ['write'],
                'link': {'scope': 'anonymous', 'type': 'edit'},
            })
        self.replace_permissions('assigned', add_anyone)
        with self.assertRaisesRegex(gate.ScopeError,
                                    'assigned_file_has_extra_permissions'):
            self.check()
        write_scope_fixture(self.session, self.session_data, self.url,
                            'excel', self.seed, png())
        self.receipt = json.loads(self.scope.read_bytes())
        def add_folder_share(snapshot):
            snapshot['response']['value'].append({
                'id': 'folder-share', 'roles': ['write'],
                'invitation': {'email': 'actor@example.test',
                               'signInRequired': True},
            })
        self.replace_permissions('parent', add_folder_share)
        with self.assertRaisesRegex(gate.ScopeError,
                                    'parent_folder_is_shared'):
            self.check()

    def test_wrong_recipient_or_tampered_evidence_fails(self):
        def wrong_recipient(snapshot):
            snapshot['response']['value'][0]['invitation']['email'] = (
                'other@example.test')
        self.replace_permissions('assigned', wrong_recipient)
        with self.assertRaisesRegex(gate.ScopeError,
                                    'assigned_file_not_single_specific_person_edit'):
            self.check()
        write_scope_fixture(self.session, self.session_data, self.url,
                            'excel', self.seed, png())
        (self.directory / 'sentinel_denial.private.png').write_bytes(
            png() + b'changed')
        with self.assertRaisesRegex(gate.ScopeError,
                                    'scope_evidence_hash_or_format_mismatch'):
            self.check()

    def test_excel_seed_mismatch_fails(self):
        with self.assertRaisesRegex(gate.ScopeError,
                                    'invalid_scope_principals_or_items'):
            self.check(actor_seed_sha256=gate.digest(b'other-seed'))


if __name__ == '__main__':
    unittest.main()
