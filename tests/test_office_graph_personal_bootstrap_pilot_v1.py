"""Fake-only personal Graph pilot and ready-train-lease handoff."""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_office_graph_one_file_lease_v1 as graph_fixture
from tests.test_office_web_ppt_graph_readback_v1 import pptx
from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tools import office_graph_one_file_lease_v1 as lease
from tools import office_graph_personal_bootstrap_pilot_v1 as bootstrap

sha = graph_fixture.sha
write_private = graph_fixture.write_private


class FakeSourceReader:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.calls = []

    def preflight(self):
        pass

    def capture(self, *, owner_user_id, drive_id, item_id,
                expected_name, out_dir):
        self.calls.append((owner_user_id, drive_id, item_id,
                           expected_name))
        suffix = '.pptx' if expected_name.endswith('.pptx') else '.xlsx'
        lease._write_new(out_dir / ('first.private' + suffix), self.raw)
        lease._write_new(out_dir / ('second.private' + suffix), self.raw)
        result = {
            'schema': ('cua-office-ppt-owner-double-download-v1'
                       if suffix == '.pptx' else
                       'cua-office-excel-owner-double-download-v1'),
            'owner_user_id_sha256': sha(owner_user_id),
            'drive_id_sha256': sha(drive_id),
            'item_id_sha256': sha(item_id),
            'name_sha256': sha(expected_name),
            'etag_sha256': sha('etag'),
            'first_sha256': sha(self.raw),
            'second_sha256': sha(self.raw),
            'byte_count': len(self.raw),
        }
        lease._write_new(out_dir / 'readback.private.json',
                         lease._canonical(result))
        return result


class PersonalBootstrapTests(unittest.TestCase):
    def setUp(self):
        fixture = graph_fixture.GraphLeaseTests(methodName=
                                  'test_exact_invite_actor_probe_and_revoke_preserve_owner_inherited')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        self.work_root = Path.cwd() / 'work'
        self.raw = pptx('exact-train-source')
        self.source = self.root / 'train-source.private.pptx'
        self.source.write_bytes(self.raw)
        self.source.chmod(0o600)
        self.scope_path = self.root / 'oauth-scopes.private.json'
        now = datetime.now(timezone.utc)
        write_private(self.scope_path, {
            'schema':
                'cua-office-graph-delegated-scope-observation-v1',
            'status': 'observed_in_oauth_client_token_response',
            'source': 'evaluator_private_oauth_client',
            'owner_user_id': 'owner1234',
            'actor_user_id': 'actor1234',
            'owner_token_sha256':
                sha('owner-fake-token-12345'),
            'actor_token_sha256':
                sha('actor-fake-token-12345'),
            'owner_delegated_scopes': ['Files.ReadWrite'],
            'actor_delegated_scopes': ['Files.Read'],
            'recorded_at_utc':
                (now - timedelta(minutes=1)).isoformat(),
            'expires_at_utc':
                (now + timedelta(hours=1)).isoformat(),
        })
        self.spec_path = self.root / 'pilot-spec.private.json'
        self.spec = {
            'schema': bootstrap.SPEC_SCHEMA,
            'cell_id': 'powerpoint-web', 'split': 'train',
            'task_package_sha256': '2' * 64,
            'source_seed_sha256': sha(self.raw),
            'action_ratification_sha256':
                sha(fixture.ratification_path.read_bytes()),
            'owner_user_id': 'owner1234',
            'actor_user_id': 'actor1234',
            'owner_email': 'owner@example.test',
            'actor_email': 'actor@example.test',
            'drive_id': 'drive1234',
            'item_id': 'item1234',
            'parent_item_id': 'parent1234',
            'sentinel_item_id': 'sentinel1234',
            'expected_name': 'EL-PPT-Train-Test.pptx',
            'ratification_ref': fixture.ref(
                fixture.ratification_path),
            'source_ref': fixture.ref(self.source),
            'scope_receipt_ref': fixture.ref(self.scope_path),
            'hidden_final_model_attempts': 0,
        }
        write_private(self.spec_path, self.spec)
        self.directory = self.root / 'pilot'
        self.reader = FakeSourceReader(self.raw)

    def pilot(self):
        return bootstrap.PersonalGraphBootstrapPilot(
            self.spec_path, self.directory,
            work_root=self.work_root,
            transport=self.fixture.graph,
            source_reader=self.reader)

    def test_first_train_capability_bootstraps_existing_one_file_lease(self):
        pilot = self.pilot()
        checked = pilot.check()
        self.assertEqual(checked['provider_write_calls'], 0)
        self.assertEqual(self.fixture.graph.post_calls, 0)
        self.assertEqual(pilot.invite()['state'], 'active')
        self.assertEqual(self.fixture.graph.post_calls, 1)
        self.assertEqual(pilot.delete()['state'], 'closed')
        self.assertEqual(self.fixture.graph.delete_calls, 1)
        ready = pilot.finalize()
        self.assertEqual(ready['state'], 'train_capability_ready')
        self.assertEqual(len(self.reader.calls), 3)
        http_trace = self.directory / 'graph-http.private.jsonl'
        self.assertEqual(http_trace.stat().st_mode & 0o077, 0)
        self.assertNotIn(b'owner-fake-token-12345',
                         http_trace.read_bytes())
        self.assertNotIn(b'actor-fake-token-12345',
                         http_trace.read_bytes())
        spec_path = self.directory / 'ready-train-lease-spec.private.json'
        next_lease = lease.OneFileGraphLease(
            spec_path, self.root / 'next-lease',
            work_root=self.work_root,
            transport=self.fixture.graph)
        self.assertEqual(next_lease.snapshot()['state'], 'prepared')
        self.assertEqual(next_lease.invite()['state'], 'active')
        self.assertEqual(self.fixture.graph.post_calls, 2)
        self.assertEqual(next_lease.delete()['state'], 'closed')

    def test_missing_tokens_or_changed_source_refuses_before_graph_write(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(lease.GraphLeaseError,
                                        'distinct_delegated_tokens_missing'):
                self.pilot().check()
        self.assertEqual(self.fixture.graph.post_calls, 0)
        self.source.write_bytes(pptx('changed-source'))
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'source_bytes_changed'):
            self.pilot()
        self.assertEqual(self.fixture.graph.post_calls, 0)

    def test_selection_or_final_spec_cannot_bootstrap(self):
        self.spec['split'] = 'selection'
        write_private(self.spec_path, self.spec)
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'identity_or_train_scope_invalid'):
            self.pilot()
        self.assertEqual(self.fixture.graph.post_calls, 0)

    def test_scope_observation_must_bind_the_exact_host_tokens(self):
        observed = json.loads(
            self.scope_path.read_bytes())
        observed['owner_token_sha256'] = 'f' * 64
        write_private(self.scope_path, observed)
        self.spec['scope_receipt_ref'] = self.fixture.ref(
            self.scope_path)
        write_private(self.spec_path, self.spec)
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'tokens_do_not_match_scope_observation'):
            self.pilot().check()
        self.assertEqual(self.fixture.graph.get_calls, [])
        self.assertEqual(self.fixture.graph.post_calls, 0)

    def test_tampered_private_graph_trace_blocks_resume_before_write(self):
        pilot = self.pilot()
        pilot.check()
        trace = self.directory / 'graph-http.private.jsonl'
        changed = trace.read_bytes().replace(
            b'"status_code":200', b'"status_code":201', 1)
        self.assertNotEqual(changed, trace.read_bytes())
        trace.write_bytes(changed)
        trace.chmod(0o600)
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'journal_hash_broken'):
            self.pilot()
        self.assertEqual(self.fixture.graph.post_calls, 0)

    def test_lost_invite_ack_reconciles_read_only_without_post_replay(self):
        pilot = self.pilot()
        pilot.check()
        self.fixture.graph.invite_timeout_after_grant = True
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'invite_uncertain'):
            pilot.invite()
        self.assertEqual(self.fixture.graph.post_calls, 1)
        self.assertEqual(pilot.reconcile_invite()['state'], 'active')
        self.assertEqual(self.fixture.graph.post_calls, 1)
        self.assertEqual(pilot.delete()['state'], 'closed')
        self.assertEqual(pilot.finalize()['state'],
                         'train_capability_ready')

    def test_lost_delete_ack_reconciles_read_only_without_delete_replay(self):
        pilot = self.pilot()
        pilot.check()
        pilot.invite()
        self.fixture.graph.delete_timeout_after_revoke = True
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'delete_uncertain'):
            pilot.delete()
        self.assertEqual(self.fixture.graph.delete_calls, 1)
        self.assertEqual(pilot.reconcile_delete()['state'], 'closed')
        self.assertEqual(self.fixture.graph.delete_calls, 1)
        self.assertEqual(pilot.finalize()['state'],
                         'train_capability_ready')

    def test_excel_train_item_can_bootstrap_same_graph_boundary(self):
        class ExcelGraph(graph_fixture.FakeGraph):
            def get(self, url, token):
                code, body = super().get(url, token)
                if (url.endswith('/items/item1234') and
                        token == 'owner-fake-token-12345' and code == 200):
                    body['name'] = 'EL-Excel-Train-Test.xlsx'
                if (url.endswith('/items/sentinel1234') and
                        token == 'owner-fake-token-12345' and code == 200):
                    body = {
                        'id': 'sentinel1234',
                        'name': 'EL-Excel-Train-Reset.xlsx',
                        'file': {'mimeType': 'xlsx'},
                        'parentReference': {
                            'driveId': 'drive1234',
                            'id': 'parent1234'},
                    }
                return code, body
        self.fixture.graph = ExcelGraph()
        self.raw = workbook()
        self.source = self.root / 'excel-source.private.xlsx'
        self.source.write_bytes(self.raw)
        self.source.chmod(0o600)
        self.spec['cell_id'] = 'excel-web'
        self.spec['expected_name'] = 'EL-Excel-Train-Test.xlsx'
        self.spec['source_seed_sha256'] = sha(self.raw)
        self.spec['source_ref'] = self.fixture.ref(self.source)
        write_private(self.spec_path, self.spec)
        self.reader = FakeSourceReader(self.raw)
        pilot = self.pilot()
        self.assertEqual(pilot.check()['state'], 'checked_train_only')
        self.assertEqual(pilot.invite()['state'], 'active')
        self.assertEqual(pilot.delete()['state'], 'closed')
        ready = pilot.finalize()
        self.assertEqual(ready['state'], 'train_capability_ready')
        lease.OneFileGraphLease(
            self.directory / 'ready-train-lease-spec.private.json',
            self.root / 'next-excel-lease',
            work_root=self.work_root,
            transport=self.fixture.graph)
        binding_path = self.root / 'excel-reset-copy.private.json'
        write_private(binding_path, {
            'schema':
                'cua-office-graph-matching-train-reset-copy-v1',
            'cell_id': 'excel-web', 'split': 'train',
            'item_id': 'sentinel1234',
            'parent_item_id': 'parent1234',
            'sentinel_item_id': 'item1234',
            'expected_name': 'EL-Excel-Train-Reset.xlsx',
            'task_package_sha256': '2' * 64,
            'source_seed_sha256': sha(self.raw),
            'official_final_credit': 0,
        })
        self.assertEqual(pilot.prepare_matching_reset_copy(
            binding_path)['state'], 'train_reset_copy_ready')

    def test_failed_actor_isolation_can_explicitly_revoke_without_capability(self):
        pilot = self.pilot()
        pilot.check()
        self.fixture.graph.sentinel_visible_after_invite = True
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'invite_uncertain'):
            pilot.invite()
        self.assertEqual(self.fixture.graph.post_calls, 1)
        self.assertEqual(self.fixture.graph.delete_calls, 0)
        aborted = pilot.abort_delete_uncertain_grant()
        self.assertEqual(aborted['state'],
                         'closed_without_capability')
        self.assertEqual(self.fixture.graph.delete_calls, 1)
        with self.assertRaisesRegex(lease.GraphLeaseError,
                                    'closed_unfinalized_required'):
            pilot.finalize()
        self.assertFalse((self.directory /
                          'capability.private.json').exists())

    def test_distinct_neutral_reset_copy_gets_readonly_ready_lease_spec(self):
        class ResetGraph(graph_fixture.FakeGraph):
            def get(self, url, token):
                if (url.endswith('/items/sentinel1234') and
                        token == 'owner-fake-token-12345'):
                    return 200, {
                        'id': 'sentinel1234',
                        'name': 'EL-PPT-Train-Reset.pptx',
                        'file': {'mimeType': 'pptx'},
                        'parentReference': {
                            'driveId': 'drive1234',
                            'id': 'parent1234'},
                    }
                return super().get(url, token)
        self.fixture.graph = ResetGraph()
        pilot = self.pilot()
        pilot.check()
        pilot.invite()
        pilot.delete()
        pilot.finalize()
        binding_path = self.root / 'reset-copy.private.json'
        write_private(binding_path, {
            'schema':
                'cua-office-graph-matching-train-reset-copy-v1',
            'cell_id': 'powerpoint-web', 'split': 'train',
            'item_id': 'sentinel1234',
            'parent_item_id': 'parent1234',
            'sentinel_item_id': 'item1234',
            'expected_name': 'EL-PPT-Train-Reset.pptx',
            'task_package_sha256': '2' * 64,
            'source_seed_sha256': sha(self.raw),
            'official_final_credit': 0,
        })
        posts = self.fixture.graph.post_calls
        deletes = self.fixture.graph.delete_calls
        prepared = pilot.prepare_matching_reset_copy(binding_path)
        self.assertEqual(prepared['state'], 'train_reset_copy_ready')
        self.assertEqual(self.fixture.graph.post_calls, posts)
        self.assertEqual(self.fixture.graph.delete_calls, deletes)
        reset_spec = (self.directory / 'matching-reset-copy' /
                      'ready-reset-lease-spec.private.json')
        next_lease = lease.OneFileGraphLease(
            reset_spec, self.root / 'reset-lease',
            work_root=self.work_root,
            transport=self.fixture.graph)
        self.assertEqual(next_lease.snapshot()['state'], 'prepared')


if __name__ == '__main__':
    unittest.main()
