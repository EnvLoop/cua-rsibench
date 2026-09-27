"""Synthetic negative controls for the Office authenticated-fork proposal.

No E2B or Microsoft request is made. The fake screenshots and owner sweep are
deliberately not evidence that an Office account is actually isolated.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import time
import unittest

from PIL import Image

from tests.office_actor_scope_fixture import (
    ACTOR, ASSIGNED, OWNER, write_scope_fixture,
)
from tools import office_web_actor_scope_gate_v1 as actor_scope
from tools import office_web_e2b_login_bridge_v1 as bridge
from tools import office_web_fork_scope_gate_v1 as fork_gate


def png() -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(stream, format='PNG')
    return stream.getvalue()


class OfficeForkScopeGateTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.directory.chmod(0o700)
        self.now = int(time.time())
        self.parent_id = 'parent-sandbox-1234'
        self.child_id = 'child-sandbox-5678'
        self.parent_start = self.now - 60
        self.parent_end = self.now + 900
        self.child_start = self.now - 15
        self.child_end = self.now + 600
        self.url = 'https://onedrive.live.com/personal/0123456789ABCDEF/train'
        self.seed = actor_scope.digest(b'synthetic-train-seed')
        self.owner_hash = actor_scope.digest(OWNER)
        self.actor_hash = actor_scope.digest(ACTOR)
        self.assigned_hash = actor_scope.digest(ASSIGNED)
        self.other_hash = actor_scope.digest('DEMO!999')
        self.manifest = actor_scope.digest(json.dumps(
            sorted([self.assigned_hash, self.other_hash]),
            separators=(',', ':')))

        self.parent_session = self.directory / 'parent-session.private.json'
        self.child_session = self.directory / 'session.private.json'
        bridge.write_new(self.parent_session, {'sandbox_id': self.parent_id})
        bridge.write_new(self.child_session, {
            'sandbox_id': self.child_id,
            'lease_started_at_unix': self.child_start,
            'lease_seconds': self.child_end - self.child_start,
        })
        self.scope = self.directory / 'actor-scope.private.json'
        write_scope_fixture(
            self.child_session, json.loads(self.child_session.read_bytes()),
            self.url, 'excel', self.seed, png())
        self.scope_body = json.loads(self.scope.read_bytes())
        self.baseline = self.directory / 'baseline.private.json'
        self.fork = self.directory / 'fork.private.json'

        base_inventory = self.inventory([], [])
        grant_inventory = self.inventory(['write'], [])
        self.put('baseline-inventory.private.json', base_inventory)
        self.put('grant-inventory.private.json', grant_inventory)
        self.baseline_body = {
            'schema': fork_gate.BASELINE_SCHEMA, 'split': 'train',
            'status': 'operator_reviewed',
            'prepared_at_unix': self.now - 20,
            'valid_until_unix': self.now + 240,
            'parent_session_sha256': actor_scope.digest(
                self.parent_session.read_bytes()),
            'parent_sandbox_id_sha256': actor_scope.digest(self.parent_id),
            'owner_principal_sha256': self.owner_hash,
            'actor_principal_sha256': self.actor_hash,
            'inventory_manifest_sha256': self.manifest,
            'inventory': self.reference('baseline-inventory.private.json'),
            'reviews': {key: True for key in fork_gate._BASELINE_REVIEWS},
            'evidence': self.pictures(fork_gate._BASELINE_IMAGES),
        }
        self.put('baseline.private.json', self.baseline_body)
        self.fork_body = {
            'schema': fork_gate.FORK_SCHEMA, 'split': 'train',
            'status': 'operator_reviewed',
            'baseline_sha256': actor_scope.digest(self.baseline.read_bytes()),
            'child_session_sha256': actor_scope.digest(
                self.child_session.read_bytes()),
            'parent_sandbox_id_sha256': actor_scope.digest(self.parent_id),
            'child_sandbox_id_sha256': actor_scope.digest(self.child_id),
            'owner_principal_sha256': self.owner_hash,
            'actor_principal_sha256': self.actor_hash,
            'assigned_item_id_sha256': self.assigned_hash,
            'scope_receipt_sha256': actor_scope.digest(self.scope.read_bytes()),
            'forked_at_unix': self.child_start,
            'pregrant_observed_at_unix': self.now - 10,
            'grant_observed_at_unix': self.now - 5,
            'inventory': self.reference('grant-inventory.private.json'),
            'reviews': {key: True for key in fork_gate._FORK_REVIEWS},
            'evidence': self.pictures(fork_gate._FORK_IMAGES),
        }
        self.put('fork.private.json', self.fork_body)

    def put(self, name: str, body: dict) -> Path:
        path = self.directory / name
        path.unlink(missing_ok=True)
        bridge.write_new(path, body)
        return path

    def reference(self, name: str) -> dict:
        return {'file': name,
                'sha256': actor_scope.digest((self.directory / name).read_bytes())}

    def pictures(self, names: tuple[str, ...]) -> dict:
        raw = png()
        result = {}
        for name in names:
            path = self.directory / f'{name}.private.png'
            path.write_bytes(raw)
            path.chmod(0o600)
            result[name] = {'file': path.name, 'sha256': actor_scope.digest(raw)}
        return result

    def inventory(self, assigned_roles: list[str], other_roles: list[str]
                  ) -> dict:
        return {
            'schema': fork_gate.INVENTORY_SCHEMA,
            'source': 'owner_authenticated_permission_sweep',
            'complete': True, 'manifest_sha256': self.manifest,
            'captured_at_unix': (self.now - 20 if not assigned_roles
                                 else self.now - 5),
            'owner_principal_sha256': self.owner_hash,
            'actor_principal_sha256': self.actor_hash,
            'entries': [
                {'item_id_sha256': self.assigned_hash,
                 'actor_roles': assigned_roles},
                {'item_id_sha256': self.other_hash,
                 'actor_roles': other_roles},
            ],
        }

    def check(self, **overrides):
        args = {
            'parent_session_raw': self.parent_session.read_bytes(),
            'child_session_raw': self.child_session.read_bytes(),
            'parent_sandbox_id': self.parent_id,
            'child_sandbox_id': self.child_id,
            'item_url': self.url, 'app': 'excel',
            'parent_lease_started_at_unix': self.parent_start,
            'parent_lease_end_unix': self.parent_end,
            'child_lease_started_at_unix': self.child_start,
            'child_lease_end_unix': self.child_end,
            'inventory_manifest_sha256': self.manifest,
            'inventory_count': 2, 'actor_seed_sha256': self.seed,
            'now': self.now,
        }
        args.update(overrides)
        return fork_gate.validate(self.baseline, self.fork, self.scope, **args)

    def test_bound_synthetic_train_proposal_has_zero_official_credit(self):
        result = self.check()
        self.assertEqual(result['status'],
                         'train_fork_scope_evidence_accepted_operator_review_only')
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['official_final_admitted'], 0)

    def test_child_or_scope_rebinding_fails(self):
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'invalid_fork_inputs'):
            self.check(child_sandbox_id=self.parent_id)
        self.fork_body['scope_receipt_sha256'] = actor_scope.digest('other')
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_child_binding_or_order_failed'):
            self.check()

    def test_prior_recent_history_or_missing_review_fails(self):
        self.fork_body['reviews'][
            'child_cloud_recent_has_no_benchmark_item'] = False
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_operator_review_incomplete'):
            self.check()

    def test_extra_grant_or_omitted_inventory_item_fails(self):
        extra = self.inventory(['write'], ['write'])
        self.put('grant-inventory.private.json', extra)
        self.fork_body['inventory'] = self.reference(
            'grant-inventory.private.json')
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_actor_has_extra_or_missing_grant'):
            self.check()
        extra['entries'].pop()
        self.put('grant-inventory.private.json', extra)
        self.fork_body['inventory'] = self.reference(
            'grant-inventory.private.json')
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_inventory_binding_failed'):
            self.check()

    def test_same_count_but_different_inventory_identity_fails(self):
        substituted = self.inventory(['write'], [])
        substituted['entries'][1]['item_id_sha256'] = actor_scope.digest(
            'DEMO!unlisted')
        self.put('grant-inventory.private.json', substituted)
        self.fork_body['inventory'] = self.reference(
            'grant-inventory.private.json')
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_inventory_manifest_mismatch'):
            self.check()

    def test_fork_before_baseline_or_stale_observation_fails(self):
        self.fork_body['forked_at_unix'] = self.now - 30
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_child_binding_or_order_failed'):
            self.check()
        self.fork_body['forked_at_unix'] = self.child_start
        self.fork_body['pregrant_observed_at_unix'] = self.now - 600
        self.put('fork.private.json', self.fork_body)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_child_binding_or_order_failed'):
            self.check()

    def test_wrong_private_mode_or_tampered_image_fails(self):
        self.fork.chmod(0o644)
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'private_fork_evidence_required'):
            self.check()
        self.fork.chmod(0o600)
        (self.directory / 'child-cloud-recent.private.png').write_bytes(
            png() + b'tamper')
        with self.assertRaisesRegex(fork_gate.ForkScopeError,
                                    'fork_visual_evidence_invalid'):
            self.check()


if __name__ == '__main__':
    unittest.main()
