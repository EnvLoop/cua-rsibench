"""Offline selection-only Office lease and actor-scope admission tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from tests.test_office_web_ppt_teacher_worker_v1 import png, write_private
from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tools import office_web_actor_scope_gate_v1 as scope_gate
from tools import office_web_excel_selection_boundary_v1 as boundary


def sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


class ExcelSelectionBoundaryTests(unittest.TestCase):
    def setUp(self):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=work, prefix='excel-selection-boundary-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task_id = 'excel-selection-01'
        self.package_sha = 'a' * 64
        self.instruction = 'Repair the original SEC workbook.'
        self.task = {'task_id': self.task_id,
                     'package_sha256': self.package_sha,
                     'visible_instruction': self.instruction}
        self.seed = workbook()
        self.task_path = self.root / 'packages' / 'selection' / \
            self.task_id / 'task.private.json'
        write_private(self.task_path.parent / 'actor.xlsx', self.seed)
        write_private(self.task_path, boundary._canonical({
            'schema': boundary.TASK_SCHEMA,
            'split': 'selection', 'official_final_credit': 0,
            'task_id': self.task_id,
            'actor_task': self.instruction,
            'actor_xlsx_sha256': sha(self.seed),
        }))
        self.url = ('https://onedrive.live.com/personal/' +
                    '1234567890abcdef/_layouts/15/Doc.aspx?' +
                    'sourcedoc=%7B00000000-0000-0000-0000-000000000001%7D'
                    '&file=EL-Excel-Selection-Test.xlsx&action=edit')
        self.directory = self.root / 'actor-login'
        self.directory.mkdir(mode=0o700)
        now = int(time.time())
        self.session = {
            'schema': boundary.SESSION_SCHEMA,
            'status': 'awaiting_manual_login',
            'task_split': 'selection_only',
            'account_login': 'manual_only',
            'credential_or_cookie_injection': False,
            'credential_snapshot_or_export': False,
            'official_final_admitted': 0,
            'model_calls': 0,
            'sdk_version': '2.2.0',
            'expected_template_id': boundary.EXPECTED_TEMPLATE_ID,
            'observed_template_id': boundary.EXPECTED_TEMPLATE_ID,
            'lease_started_at_unix': now - 2,
            'lease_seconds': 900,
            'sandbox_id': 'sandbox-selection-001',
            'stream_url': 'https://fake.e2b.app/vnc.html',
            'stream_auth_key': 'SyntheticTestKey1234',
        }
        self.session_path = self.directory / 'session.private.json'
        write_private(self.session_path,
                      boundary._canonical(self.session))
        self.config_path = self.directory / 'run.private.json'
        write_private(self.config_path, boundary._canonical({
            'schema': boundary.CONFIG_SCHEMA, 'split': 'selection',
            'manual_login_confirmed_at_unix': now,
            'workbook_url': self.url,
            'max_steps': 20, 'wall_seconds': 600,
        }))
        for name in scope_gate._EVIDENCE_NAMES:
            write_private(self.directory / f'{name}.private.png', png())
        self.owner = 'owner@example.test'
        self.actor = 'actor@example.test'
        self.permission = {
            'id': 'permission-actor-1', 'roles': ['write'],
            'invitation': {'email': self.actor,
                           'signInRequired': True}}
        self.assigned = [
            {'id': 'owner-entry', 'roles': ['owner'],
             'grantedToV2': {'user': {'id': 'owner1234',
                                      'email': self.owner}}},
            {'id': 'inherited-entry', 'roles': ['read'],
             'inheritedFrom': {'id': 'parent-1'},
             'grantedToV2': {'user': {'id': 'other1234'}}},
            self.permission,
        ]
        self.parent = self.assigned[:2]
        self.write_scope(now)

    def write_scope(self, now):
        owner_hash = sha(self.owner.casefold())
        for name, item, rows in (
                ('assigned-permissions', 'ITEM!101', self.assigned),
                ('parent-permissions', 'ITEM!100', self.parent)):
            write_private(self.directory / f'{name}.private.json',
                          boundary._canonical({
                              'schema': scope_gate.SNAPSHOT_SCHEMA,
                              'owner_principal_sha256': owner_hash,
                              'item_id': item,
                              'http_status': 200,
                              'response': {'value': rows},
                          }))
        graph = {
            'schema': boundary.GRAPH_LEASE_SCHEMA,
            'status': 'active_verified_pre_result',
            'cell_id': 'excel-web', 'split': 'selection',
            'task_id': self.task_id,
            'package_sha256': self.package_sha,
            'actor_seed_sha256': sha(self.seed),
            'item_id_sha256': sha('ITEM!101'),
            'permission_id_sha256': sha(self.permission['id']),
            'actor_email_sha256': sha(self.actor.casefold()),
            'actor_target_read_and_sentinel_denial_passed': True,
        }
        write_private(self.directory /
                      'selection-graph-lease.private.json',
                      boundary._canonical(graph))
        scope = {
            'schema': boundary.SCOPE_SCHEMA,
            'split': 'selection',
            'status': 'operator_reviewed',
            'observed_at_unix': now,
            'valid_until_unix': now + 300,
            'session_sha256': sha(self.session_path.read_bytes()),
            'sandbox_id_sha256': sha(self.session['sandbox_id']),
            'assigned_url_sha256': sha(self.url),
            'task_id': self.task_id,
            'package_sha256': self.package_sha,
            'actor_seed_sha256': sha(self.seed),
            'owner_email': self.owner,
            'actor_email': self.actor,
            'owner_principal_sha256': owner_hash,
            'actor_principal_sha256': sha(self.actor.casefold()),
            'assigned_item_id': 'ITEM!101',
            'parent_item_id': 'ITEM!100',
            'owner_permissions': {
                'file': 'assigned-permissions.private.json',
                'sha256': sha((self.directory /
                               'assigned-permissions.private.json')
                              .read_bytes())},
            'parent_permissions': {
                'file': 'parent-permissions.private.json',
                'sha256': sha((self.directory /
                               'parent-permissions.private.json')
                              .read_bytes())},
            'graph_lease': {
                'file': 'selection-graph-lease.private.json',
                'sha256': sha((self.directory /
                               'selection-graph-lease.private.json')
                              .read_bytes())},
            'evidence': {name: {
                'file': f'{name}.private.png',
                'sha256': sha(png()),
            } for name in scope_gate._EVIDENCE_NAMES},
            'reviews': {name: True for name in (
                'distinct_accounts', 'actor_signed_in_as_actor',
                'assigned_file_editable', 'sentinel_file_denied',
                'owner_seed_readback_matched',
                'no_other_benchmark_item_visible')},
        }
        write_private(self.directory / 'actor-scope.private.json',
                      boundary._canonical(scope))

    def admit(self):
        return boundary.admit(
            self.session_path, self.task_path, self.config_path,
            self.root / 'unused-out', work_root=self.root,
            expected_task=self.task, now=int(time.time()))

    def test_selection_scope_preserves_owner_and_inherited_entries(self):
        admitted = self.admit()
        self.assertEqual(admitted.task_id, self.task_id)
        self.assertEqual(admitted.assigned_item_id, 'ITEM!101')
        self.assertEqual(admitted.permission_id_sha256,
                         sha('permission-actor-1'))

    def test_parent_actor_and_broad_link_fail_closed(self):
        self.parent.append(self.permission)
        self.write_scope(int(time.time()))
        with self.assertRaisesRegex(
                boundary.ExcelSelectionBoundaryError,
                'parent_or_file_scope_not_single'):
            self.admit()
        self.parent.pop()
        self.assigned.append({'id': 'anonymous-link',
                              'roles': ['write'],
                              'link': {'scope': 'anonymous'}})
        self.write_scope(int(time.time()))
        with self.assertRaisesRegex(
                boundary.ExcelSelectionBoundaryError,
                'parent_or_file_scope_not_single'):
            self.admit()

    def test_train_url_and_wrong_task_split_fail_closed(self):
        with self.assertRaisesRegex(boundary.ExcelSelectionBoundaryError,
                                    'excel_selection_url_invalid'):
            boundary.validate_selection_url(self.url.replace(
                'Selection', 'Train'))
        wrong = json.loads(self.task_path.read_bytes())
        wrong['split'] = 'train'
        write_private(self.task_path, boundary._canonical(wrong))
        with self.assertRaisesRegex(boundary.ExcelSelectionBoundaryError,
                                    'package_not_frozen'):
            self.admit()


if __name__ == '__main__':
    unittest.main()
