"""One-file Graph lease fake transport; no live account mutation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cursibench.full_study_matrix_v1 import CELLS
from native_desktop_factory import qwen_v066_adapter
from native_desktop_factory.v066_final_freeze import source_hashes
from tools import office_graph_one_file_lease_v1 as lease


def sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def write_private(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(lease._canonical(value))
    path.chmod(0o600)


class FakeGraph:
    def __init__(self):
        self.active = False
        self.post_calls = self.delete_calls = 0
        self.get_calls = []
        self.invite_timeout_after_grant = False
        self.delete_timeout_after_revoke = False
        self.multi_status = False
        self.broad_link = False
        self.wrong_owner = False
        self.sentinel_visible_after_invite = False

    @staticmethod
    def _permission():
        return {'id': 'permission-1234', 'roles': ['write'],
                'invitation': {'email': 'actor@example.test',
                               'signInRequired': True}}

    def get(self, url, token):
        owner = token == 'owner-fake-token-12345'
        actor = token == 'actor-fake-token-12345'
        self.get_calls.append((url, 'owner' if owner else 'actor'))
        if url.endswith('/me'):
            return 200, {'id': ('wrong-owner' if self.wrong_owner else
                                'owner1234') if owner else 'actor1234'}
        if url.endswith('/drives/drive1234'):
            return 200, {'id': 'drive1234', 'driveType': 'personal',
                         'owner': {'user': {'id': 'owner1234'}}}
        if url.endswith('/permissions'):
            rows = [
                {'id': 'owner-permission', 'roles': ['owner'],
                 'grantedToV2': {'user': {'id': 'owner1234'}}},
                {'id': 'inherited-permission', 'roles': ['read'],
                 'inheritedFrom': {'driveId': 'drive1234',
                                   'id': 'parent1234'},
                 'grantedToV2': {'user': {'id': 'other-user'}}},
            ]
            if self.broad_link:
                rows.append({'id': 'broad-link', 'roles': ['write'],
                             'link': {'scope': 'anonymous', 'type': 'edit'}})
            if self.active and '/items/item1234/' in url:
                rows.append(self._permission())
            return 200, {'value': rows}
        if url.endswith('/items/item1234'):
            if actor:
                return (200 if self.active else 404), (
                    {'id': 'item1234'} if self.active else {})
            return 200, {'id': 'item1234',
                         'name': 'EL-PPT-Train-Test.pptx',
                         'file': {'mimeType': 'pptx'},
                         'parentReference': {
                             'driveId': 'drive1234', 'id': 'parent1234'}}
        if url.endswith('/items/parent1234'):
            return (404, {}) if actor else (200, {'id': 'parent1234'})
        if url.endswith('/items/sentinel1234'):
            if actor and self.active and self.sentinel_visible_after_invite:
                return 200, {'id': 'sentinel1234'}
            return (404, {}) if actor else (200, {'id': 'sentinel1234'})
        raise AssertionError('unexpected URL')

    def post(self, url, token, payload):
        self.post_calls += 1
        assert url.endswith('/items/item1234/invite')
        assert token == 'owner-fake-token-12345'
        assert payload == {'recipients': [{'email': 'actor@example.test'}],
                           'roles': ['write'], 'requireSignIn': True,
                           'sendInvitation': False}
        if self.multi_status:
            return 207, {'value': [{'error': {'code': 'partial'}}]}
        self.active = True
        if self.invite_timeout_after_grant:
            raise TimeoutError('response lost after provider grant')
        return 200, {'value': [self._permission()]}

    def delete(self, url, token):
        self.delete_calls += 1
        assert url.endswith('/items/item1234/permissions/permission-1234')
        assert token == 'owner-fake-token-12345'
        self.active = False
        if self.delete_timeout_after_revoke:
            raise TimeoutError('response lost after provider delete')
        return 204


class GraphLeaseTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work,
                                                 prefix='graph-lease-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ratification_path = self.root / 'ratification.private.json'
        common = source_hashes()
        ratification = {
            'schema': 'cua-six-cell-action-profile-v066-ratification-v1',
            'status': 'ratified_pre_result',
            'ratified_utc': datetime.now(timezone.utc).isoformat(),
            'action_profile': 'scale-action-profile-v0.6.6',
            'common_source_sha256s': common,
            'cell_profiles': {cell: {
                'common_source_sha256s': common,
                'adapter_sha256': (
                    sha(Path(qwen_v066_adapter.__file__).read_bytes())
                    if cell == 'desktop-native' else 'a' * 64),
            } for cell in CELLS},
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }
        write_private(self.ratification_path, ratification)
        self.cap_path = self.root / 'capability.private.json'
        now = datetime.now(timezone.utc)
        pilot_refs = {}
        for stage in ('owner_token_scope', 'actor_token_scope',
                      'silent_invite', 'exact_delete', 'actor_scope'):
            proof_path = self.root / f'pilot-{stage}.private.json'
            write_private(proof_path, {
                'schema': 'cua-office-graph-train-pilot-proof-v1',
                'stage': stage,
                'status': 'passed_authenticated_graph',
                'owner_user_id': 'owner1234',
                'actor_user_id': 'actor1234',
                'drive_id': 'drive1234',
                'source_split': 'train',
                'observed_scopes': (
                    ['Files.ReadWrite'] if stage == 'owner_token_scope' else
                    ['Files.Read'] if stage == 'actor_token_scope' else []),
                'request_sha256': sha(('request-' + stage).encode()),
                'response_sha256': sha(('response-' + stage).encode()),
                'permission_id_sha256': (
                    sha(b'pilot-permission') if stage in
                    ('silent_invite', 'exact_delete') else None),
                'target_parent_sentinel_scope_passed':
                    stage == 'actor_scope',
                'observed_at_utc': (now - timedelta(minutes=2)).isoformat(),
                'hidden_final_model_attempts': 0,
            })
            pilot_refs[stage] = self.ref(proof_path)
        self.capability = {
            'schema': lease.CAPABILITY_SCHEMA,
            'status': 'verified_train_only_account_pilot',
            'owner_user_id': 'owner1234', 'actor_user_id': 'actor1234',
            'owner_email_sha256': sha('owner@example.test'),
            'actor_email_sha256': sha('actor@example.test'),
            'drive_id': 'drive1234', 'drive_type': 'personal',
            'owner_delegated_scopes': ['Files.ReadWrite'],
            'actor_delegated_scopes': ['Files.Read'],
            'silent_personal_invite_verified': True,
            'exact_delete_verified': True,
            'actor_target_and_sentinel_verified': True,
            'pilot_receipts': pilot_refs,
            'recorded_at_utc': (now - timedelta(minutes=1)).isoformat(),
            'expires_at_utc': (now + timedelta(hours=1)).isoformat(),
            'hidden_final_model_attempts': 0,
        }
        write_private(self.cap_path, self.capability)
        self.source_path = self.root / 'source-readback.private.json'
        write_private(self.source_path, {
            'schema': 'cua-office-owner-item-source-readback-v1',
            'drive_id_sha256': sha('drive1234'),
            'item_id_sha256': sha('item1234'),
            'name_sha256': sha('EL-PPT-Train-Test.pptx'),
            'source_seed_sha256': '1' * 64,
            'owner_user_id_sha256': sha('owner1234'),
            'readback_passed': True,
        })
        self.spec_path = self.root / 'spec.private.json'
        self.spec = {
            'schema': lease.SPEC_SCHEMA,
            'cell_id': 'powerpoint-web', 'split': 'train',
            'task_package_sha256': '2' * 64,
            'source_seed_sha256': '1' * 64,
            'action_ratification_sha256':
                sha(self.ratification_path.read_bytes()),
            'owner_user_id': 'owner1234',
            'actor_user_id': 'actor1234',
            'owner_email': 'owner@example.test',
            'actor_email': 'actor@example.test',
            'drive_id': 'drive1234', 'item_id': 'item1234',
            'parent_item_id': 'parent1234',
            'sentinel_item_id': 'sentinel1234',
            'expected_name': 'EL-PPT-Train-Test.pptx',
            'ratification_ref': self.ref(self.ratification_path),
            'capability_ref': self.ref(self.cap_path),
            'item_readback_ref': self.ref(self.source_path),
        }
        write_private(self.spec_path, self.spec)
        self.graph = FakeGraph()
        self.directory = self.root / 'lease'
        self.tokens = patch.dict(os.environ, {
            'MS_GRAPH_OWNER_TOKEN': 'owner-fake-token-12345',
            'MS_GRAPH_ACTOR_TOKEN': 'actor-fake-token-12345'})
        self.tokens.start()
        self.addCleanup(self.tokens.stop)

    def ref(self, path: Path):
        return {'path': path.relative_to(Path.cwd() / 'work').as_posix(),
                'sha256': sha(path.read_bytes())}

    def controller(self):
        return lease.OneFileGraphLease(
            self.spec_path, self.directory,
            work_root=Path.cwd() / 'work',
            transport=self.graph)

    def test_exact_invite_actor_probe_and_revoke_preserve_owner_inherited(self):
        controller = self.controller()
        self.assertEqual(controller.state(), 'prepared')
        active = controller.invite()
        self.assertEqual(active['state'], 'active')
        self.assertEqual(self.graph.post_calls, 1)
        self.assertEqual(controller.snapshot()['provider_write_calls_claimed'], 1)
        self.assertEqual((self.directory / 'permission.private.json').stat().st_mode & 0o077, 0)
        with self.assertRaisesRegex(ValueError, 'already_dispatched'):
            controller.invite()
        reopened = self.controller()
        self.assertEqual(reopened.state(), 'active')
        closed = reopened.delete()
        self.assertEqual(closed['state'], 'closed')
        self.assertEqual(self.graph.delete_calls, 1)
        self.assertEqual(reopened.snapshot()['provider_write_calls_claimed'], 2)
        with self.assertRaisesRegex(ValueError, 'delete_requires_active'):
            reopened.delete()

    def test_invite_timeout_after_grant_is_read_only_reconciled(self):
        self.graph.invite_timeout_after_grant = True
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, 'invite_uncertain'):
            controller.invite()
        self.assertEqual(controller.state(), 'invite_uncertain')
        with self.assertRaisesRegex(ValueError, 'already_dispatched'):
            controller.invite()
        recovered = self.controller().reconcile_invite()
        self.assertEqual(recovered['state'], 'active')
        self.assertEqual(recovered['provider_write_calls'], 0)
        self.assertEqual(self.graph.post_calls, 1)

    def test_delete_timeout_after_revoke_is_read_only_reconciled(self):
        controller = self.controller()
        controller.invite()
        self.graph.delete_timeout_after_revoke = True
        with self.assertRaisesRegex(ValueError, 'delete_uncertain'):
            controller.delete()
        self.assertEqual(controller.state(), 'delete_uncertain')
        with self.assertRaisesRegex(ValueError, 'delete_requires_active'):
            controller.delete()
        recovered = self.controller().reconcile_delete()
        self.assertEqual(recovered['state'], 'closed')
        self.assertEqual(self.graph.delete_calls, 1)

    def test_missing_capability_or_scope_refuses_before_any_graph_call(self):
        self.capability['owner_delegated_scopes'] = ['Files.Read']
        write_private(self.cap_path, self.capability)
        self.spec['capability_ref'] = self.ref(self.cap_path)
        write_private(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'write_capability_unverified'):
            self.controller()
        self.assertEqual(self.graph.get_calls, [])

    def test_tampered_pilot_proof_or_missing_actor_token_refuses_write(self):
        proof_path = self.root / 'pilot-silent_invite.private.json'
        proof = json.loads(proof_path.read_bytes())
        proof['response_sha256'] = sha(b'changed')
        write_private(proof_path, proof)
        with self.assertRaisesRegex(ValueError, 'graph_pilot_silent_invite_bytes_changed'):
            self.controller()
        self.capability['pilot_receipts']['silent_invite'] = self.ref(proof_path)
        write_private(self.cap_path, self.capability)
        self.spec['capability_ref'] = self.ref(self.cap_path)
        write_private(self.spec_path, self.spec)
        controller = self.controller()
        with patch.dict(os.environ, {'MS_GRAPH_ACTOR_TOKEN': ''}):
            with self.assertRaisesRegex(ValueError, 'distinct_delegated_tokens_missing'):
                controller.invite()
        self.assertEqual(self.graph.post_calls, 0)
        self.assertEqual(self.graph.get_calls, [])

    def test_selection_final_write_waits_for_separate_matrix_gate(self):
        self.spec['split'] = 'final'
        self.spec['expected_name'] = 'EL-PPT-Final-Test.pptx'
        source = json.loads(self.source_path.read_bytes())
        source['name_sha256'] = sha(self.spec['expected_name'])
        write_private(self.source_path, source)
        self.spec['item_readback_ref'] = self.ref(self.source_path)
        write_private(self.spec_path, self.spec)
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, 'requires_separate_matrix_gate'):
            controller.invite()
        self.assertEqual(self.graph.get_calls, [])
        self.assertEqual(self.graph.post_calls, 0)

    def test_wrong_owner_broad_link_or_sentinel_access_refuses(self):
        for setting in ('wrong_owner', 'broad_link'):
            with self.subTest(setting=setting):
                graph = FakeGraph()
                setattr(graph, setting, True)
                self.graph = graph
                controller = self.controller()
                with self.assertRaises(ValueError):
                    controller.invite()
                self.assertEqual(graph.post_calls, 0)
        self.graph = FakeGraph()
        self.graph.sentinel_visible_after_invite = True
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, 'invite_uncertain'):
            controller.invite()
        self.assertEqual(self.graph.post_calls, 1)
        self.assertEqual(controller.state(), 'invite_uncertain')

    def test_multi_status_is_uncertain_never_automatically_replayed(self):
        self.graph.multi_status = True
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, 'invite_uncertain'):
            controller.invite()
        self.assertEqual(controller.reconcile_invite()['state'],
                         'invite_uncertain')
        self.assertEqual(self.graph.post_calls, 1)

    def test_process_death_after_intent_does_not_replay_post(self):
        def interrupted(_url, _token, _payload):
            raise SystemExit('simulated process death before provider response')
        self.graph.post = interrupted
        controller = self.controller()
        with self.assertRaises(SystemExit):
            controller.invite()
        self.assertEqual(self.controller().state(), 'invite_uncertain')
        self.assertEqual(self.controller().reconcile_invite(), {
            'state': 'invite_uncertain', 'actor_candidate_count': 0,
            'provider_write_calls': 0})

    def test_private_permission_id_tamper_blocks_exact_delete(self):
        controller = self.controller()
        controller.invite()
        path = self.directory / 'permission.private.json'
        value = json.loads(path.read_bytes())
        value['permission_id'] = 'permission-forged'
        write_private(path, value)
        with self.assertRaisesRegex(ValueError,
                                    'permission_file_exact_id_changed'):
            controller.delete()
        self.assertEqual(self.graph.delete_calls, 0)

    def test_changed_journal_or_ratification_fails_closed(self):
        controller = self.controller()
        controller.invite()
        journal = self.directory / 'events.private.jsonl'
        journal.write_bytes(journal.read_bytes().replace(
            b'active_verified', b'active_forged__'))
        with self.assertRaisesRegex(ValueError, 'journal_hash_broken'):
            self.controller()
        # A fresh lease with a changed ratification reference also refuses.
        self.directory = self.root / 'another-lease'
        self.spec['action_ratification_sha256'] = '0' * 64
        write_private(self.spec_path, self.spec)
        with self.assertRaisesRegex(ValueError, 'ratification_changed'):
            self.controller()


if __name__ == '__main__':
    unittest.main()
