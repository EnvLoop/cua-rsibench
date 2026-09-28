"""Original seven-slide WDI selection scorer with synthetic Office normalization."""

from __future__ import annotations

import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from ppt_wdi_factory import plan, verify
from cursibench.full_study_matrix_v1 import CELLS
from native_desktop_factory import qwen_v066_adapter
from native_desktop_factory.v066_final_freeze import source_hashes
from ppt_wdi_factory.build import (
    DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON, DEFAULT_SKILL,
    prepare_builder,
)
from tools import ppt_wdi_selection_oracle_v1 as oracle
from tools import office_web_ppt_teacher_worker_v1 as train_worker
from tools import office_web_ppt_selection_worker_v1 as worker
from tools import office_web_ppt_selection_boundary_v1 as boundary
from tools import office_web_actor_scope_gate_v1 as scope_gate
from tools.office_web_ppt_selection_worker_v1 import SelectionOracleSubprocess
from tests.test_office_web_ppt_teacher_worker_v1 import (
    FakeSandbox, png, write_private,
)


def sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


@unittest.skipUnless(DEFAULT_SKILL.is_dir() and DEFAULT_MODULES.is_dir(),
                     'bundled presentation runtime unavailable')
class PptSelectionOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = Path.cwd() / 'work'
        work.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(
            dir=work, prefix='ppt-selection-oracle-test-')
        cls.root = Path(cls.temp.name)
        cls.task = plan.build(bytes.fromhex('f0' * 32))[
            'sets']['selection'][0]
        cls.package = cls.root / 'packages' / 'selection' / \
            cls.task['task_id']
        cls.package.mkdir(parents=True)
        cls.task_path = cls.package / 'task.private.json'
        cls.task_path.write_bytes(plan.canonical(cls.task))
        cls.task_path.chmod(0o600)
        builder = prepare_builder(cls.root, DEFAULT_MODULES)
        environment = {
            **os.environ,
            'PRESENTATIONS_SKILL_DIR': str(DEFAULT_SKILL),
            'RUNTIME_PYTHON': str(DEFAULT_PYTHON),
            'RUNTIME_NODE': str(DEFAULT_NODE),
            'RUNTIME_NODE_MODULES': str(DEFAULT_MODULES),
        }
        subprocess.run([
            str(DEFAULT_NODE), str(builder), str(cls.task_path),
            str(cls.package / 'draft.pptx')], check=True,
            capture_output=True, env=environment)
        cls.source = cls.package / 'source.pptx'
        subprocess.run([
            str(DEFAULT_NODE),
            str(Path('ppt_wdi_factory/finalize_deck.mjs').resolve()),
            str(cls.package / 'draft.pptx'), str(cls.source)],
            check=True, capture_output=True, env=environment)
        cls.source.chmod(0o600)
        # Synthetic test normalization: add the Calibri Office theme path.
        # This is a unit fixture, not an authenticated PowerPoint web save.
        cls.baseline = cls.package / 'synthetic-normalized.pptx'
        with ZipFile(cls.source) as original, ZipFile(
                cls.baseline, 'w', compression=ZIP_DEFLATED) as output:
            for name in original.namelist():
                output.writestr(name, original.read(name))
            output.writestr(
                'ppt/theme/theme2.xml',
                original.read('ppt/slideMasters/theme/theme2.xml'))
        cls.baseline.chmod(0o600)
        frozen = verify.freeze(cls.baseline, cls.task,
                               office_web_normalized=True)
        targets = {name: row['correct'] for name, row in
                   frozen['targets'].items()}
        cls.positive = cls.package / 'positive.pptx'
        cls.near_miss = cls.package / 'near-miss.pptx'
        cls.collateral = cls.package / 'collateral.pptx'
        verify._write_variant(cls.baseline, cls.positive,
                              targets, frozen)
        verify._write_variant(cls.baseline, cls.near_miss,
                              {'summary': targets['summary']}, frozen)
        verify._write_variant(cls.baseline, cls.collateral,
                              targets, frozen, collateral=True)
        for path in (cls.positive, cls.near_miss, cls.collateral):
            path.chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_eight_workflow_selection_shape(self):
        roster = plan.build(bytes.fromhex('f0' * 32))[
            'sets']['selection']
        self.assertEqual(len(roster), 20)
        self.assertEqual({row['workflow'] for row in roster},
                         set(plan.WORKFLOWS[:8]))
        self.assertTrue(all(row['target_keys'] ==
                            ['summary', 'ledger', 'interpretation']
                            for row in roster))
        self.assertEqual(self.task['target_keys'],
                         ['summary', 'ledger', 'interpretation'])
        self.assertIn(self.task['workflow'], plan.WORKFLOWS[:8])
        self.assertEqual(oracle.exact_case(
            self.task_path, self.task['task_id']), self.task)

    def test_positive_partial_collateral_and_reset(self):
        calibration = oracle.calibrate(
            self.baseline, self.positive, self.near_miss,
            self.collateral, self.task, self.source)
        self.assertTrue(calibration['positive_passed'])
        self.assertEqual(calibration['target_count'], 3)
        positive = oracle.score(self.positive,
                                self.baseline, self.task)
        self.assertEqual(positive['score'], 1)
        self.assertTrue(
            positive['native_chart_and_workbook_preserved'])
        self.assertEqual(oracle.score(self.near_miss,
                                      self.baseline,
                                      self.task)['score'], 0)
        collateral = oracle.score(self.collateral,
                                  self.baseline, self.task)
        self.assertEqual(collateral['score'], 0)
        self.assertFalse(collateral['preservation_pass'])
        neutral = oracle.neutral(self.baseline,
                                 self.baseline, self.task)
        self.assertTrue(neutral['equivalent'])
        self.assertEqual(neutral['changed_target_count'], 0)

    def test_evaluator_subprocess_reopens_saved_deck(self):
        calibration = SelectionOracleSubprocess().calibrate(
            self.baseline, self.positive, self.near_miss,
            self.collateral, self.source,
            self.task_path, self.task['task_id'])
        self.assertTrue(calibration['native_chart_and_workbook_checked'])
        separate = SelectionOracleSubprocess().score(
            self.positive, self.baseline,
            self.task_path, self.task['task_id'])
        self.assertEqual(separate['schema'], oracle.SCORE_SCHEMA)
        self.assertEqual(separate['score'], 1)

    def prepared_worker(self, suffix: str):
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
                    sha(Path(train_worker.__file__).read_bytes())
                    if cell == 'powerpoint-web' else
                    sha(Path(qwen_v066_adapter.__file__).read_bytes())
                    if cell == 'desktop-native' else 'a' * 64),
            } for cell in CELLS},
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }
        rat_path = self.package / f'ratification-{suffix}.private.json'
        rat_path.write_bytes(worker._canonical(ratification))
        rat_path.chmod(0o600)
        identity = {'task_id': self.task['task_id'],
                    'package_sha256': 'd' * 64}
        session = type('FakeSession', (), {})()
        session.study = type('Study', (), {
            'repo_root': Path.cwd(),
            'ratification_path': rat_path,
            'ratification_sha256': sha(rat_path.read_bytes()),
            'ratification': ratification,
            'plan': {'cells': [{'cell_id': 'powerpoint-web',
                               'matched_bindings': {
                                   'verifier': 'c' * 64}}]},
        })()
        session.views = {'selection': (identity,)}
        session.intent = {'cell_id': 'powerpoint-web'}
        visible = {**identity,
                   'visible_instruction': self.task['actor_task']}
        def item(item_id, role):
            return {'owner_user_id': 'owner1234',
                    'drive_id': 'drive1234', 'item_id': item_id,
                    'file_name': f'EL-PPT-Selection-{role}.pptx',
                    'edit_url': (
                        'https://onedrive.live.com/personal/' +
                        '1234567890abcdef/_layouts/15/Doc.aspx?' +
                        'sourcedoc=%7B00000000-0000-0000-0000-' +
                        ('000000000001' if role == 'Actor' else
                         '000000000002') + '%7D' +
                        f'&file=EL-PPT-Selection-{role}.pptx&action=edit')}
        prepared = worker.prepare_private_binding(
            session, task=visible, task_path=self.task_path,
            normalized_baseline_path=self.baseline,
            positive_path=self.positive, near_miss_path=self.near_miss,
            collateral_path=self.collateral,
            actor_item=item('ITEM!101', 'Actor'),
            reset_item=item('ITEM!102', 'Reset'),
            owner_email='owner@example.test',
            actor_email='actor@example.test',
            out_path=self.package / f'binding-{suffix}.private.json',
            post_finish_wait_seconds=0,
            oracle_runner=SelectionOracleSubprocess())
        instance = worker.SelectionPptTaskWorker(
            session, Path(prepared['binding_path']),
            oracle_runner=SelectionOracleSubprocess(),
            lease_factory=SimpleNamespace(stop=lambda _path: 'killed'),
            operator_wait_revocation=lambda *_args: None)
        return session, instance, identity, visible, prepared

    def test_private_binding_covers_eight_workflows_with_three_targets(self):
        _session, instance, identity, _visible, prepared = \
            self.prepared_worker('binding')
        self.assertEqual(prepared['binding_sha256'],
                         sha(Path(prepared['binding_path']).read_bytes()))
        self.assertEqual(instance._binding(identity)[0]['workflow'],
                         self.task['workflow'])

    def test_gui_trace_saved_pptx_score_and_fresh_copy_reset(self):
        _session, instance, _identity, visible, _prepared = \
            self.prepared_worker('episode')
        task_dir = self.package / 'episode'
        (task_dir / 'frames').mkdir(parents=True, mode=0o700)
        sandboxes = {'actor': FakeSandbox('sandbox-ppt-selection-actor'),
                     'reset': FakeSandbox('sandbox-ppt-selection-reset')}

        def lease(*, phase, item, binding, episode_dir, task_path,
                  dispatch_e2b):
            path = episode_dir / f'{phase}-session.private.json'
            write_private(path, b'{}\n')
            paid = {'attempt_id': 'e2b-' + phase,
                    'result': {'sandbox_id': sandboxes[phase].sandbox_id}}
            admission = SimpleNamespace(
                wall_seconds=30, lease_end_unix=int(time.time()) + 120)
            return paid, path, admission, sandboxes[phase]
        instance._lease = lease

        def capture(*, phase, item, binding, episode_dir):
            if phase == 'saved':
                self.assertIn(('left_click',),
                              sandboxes['actor'].actions)
                payload = self.positive.read_bytes()
            else:
                payload = self.baseline.read_bytes()
            path = episode_dir / 'artifacts' / f'{phase}.private.pptx'
            write_private(path, payload)
            return path, {'phase': phase,
                          'item_id_sha256': sha(item['item_id'])}
        instance._graph_capture = capture
        instance._graph_actor_revoked = lambda **_kwargs: {
            'actor_grants_remaining': 0,
            'broad_links_remaining': 0}
        samples = []
        def sample(observation):
            samples.append(observation.step)
            raw = ('{"type":"click","target":{"x":10,"y":20}}'
                   if observation.step == 0 else
                   '{"type":"finish"}')
            return {'status': 'completed', 'text': raw,
                    'paid_attempt_id': 'sample-' +
                        str(observation.step),
                    'paid_result_sha256': sha(raw)}
        result = instance.run_task(
            task=visible, out_dir=task_dir,
            sample_student=sample,
            dispatch_e2b=lambda **_kwargs: None)
        self.assertEqual(samples, [0, 1])
        self.assertEqual(result['result_row']['score'], 1)
        self.assertTrue((task_dir / 'reset.private.json').is_file())
        self.assertEqual(len(result['paid_attempt_ids']), 4)

    def test_selection_only_one_file_actor_admission(self):
        _session, instance, _identity, visible, _prepared = \
            self.prepared_worker('scope')
        binding = instance._binding({
            'task_id': visible['task_id'],
            'package_sha256': visible['package_sha256']})[0]
        directory = self.package / 'scope-login'
        directory.mkdir(mode=0o700)
        now = int(time.time())
        login = {
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
            'sandbox_id': 'sandbox-ppt-selection-001',
            'stream_url': 'https://fake.e2b.app/vnc.html',
            'stream_auth_key': 'SyntheticTestKey1234',
        }
        session_path = directory / 'session.private.json'
        write_private(session_path, boundary._canonical(login))
        url = binding['actor_item']['edit_url']
        run_path = directory / 'run.private.json'
        write_private(run_path, boundary._canonical({
            'schema': boundary.CONFIG_SCHEMA, 'split': 'selection',
            'manual_login_confirmed_at_unix': now,
            'deck_url': url, 'max_steps': 20,
            'wall_seconds': 600,
        }))
        owner = 'owner@example.test'
        actor = 'actor@example.test'
        owner_hash = sha(owner.casefold())
        actor_hash = sha(actor.casefold())
        permission = {'id': 'permission-actor-1',
                      'roles': ['write'],
                      'invitation': {'email': actor,
                                     'signInRequired': True}}
        owner_entry = {'id': 'owner-entry', 'roles': ['owner'],
                       'grantedToV2': {'user': {'id': 'owner1234',
                                                'email': owner}}}
        inherited = {'id': 'inherited-entry', 'roles': ['read'],
                     'inheritedFrom': {'id': 'ITEM!100'},
                     'grantedToV2': {'user': {'id': 'other1234'}}}
        def snapshot(name, item_id, rows):
            path = directory / f'{name}.private.json'
            write_private(path, boundary._canonical({
                'schema': scope_gate.SNAPSHOT_SCHEMA,
                'owner_principal_sha256': owner_hash,
                'item_id': item_id, 'http_status': 200,
                'response': {'value': rows},
            }))
            return {'file': path.name,
                    'sha256': sha(path.read_bytes())}
        assigned = snapshot('assigned-permissions', 'ITEM!101',
                            [owner_entry, inherited, permission])
        parent = snapshot('parent-permissions', 'ITEM!100',
                          [owner_entry, inherited])
        graph_path = directory / 'selection-graph-lease.private.json'
        write_private(graph_path, boundary._canonical({
            'schema': boundary.GRAPH_LEASE_SCHEMA,
            'status': 'active_verified_pre_result',
            'cell_id': 'powerpoint-web', 'split': 'selection',
            'task_id': visible['task_id'],
            'package_sha256': visible['package_sha256'],
            'actor_seed_sha256':
                binding['normalized_baseline_sha256'],
            'item_id_sha256': sha('ITEM!101'),
            'permission_id_sha256': sha(permission['id']),
            'actor_email_sha256': actor_hash,
            'actor_target_read_and_sentinel_denial_passed': True,
        }))
        evidence = {}
        for name in scope_gate._EVIDENCE_NAMES:
            path = directory / f'{name}.private.png'
            write_private(path, png())
            evidence[name] = {'file': path.name,
                              'sha256': sha(path.read_bytes())}
        scope = {
            'schema': boundary.SCOPE_SCHEMA,
            'split': 'selection', 'status': 'operator_reviewed',
            'observed_at_unix': now,
            'valid_until_unix': now + 300,
            'session_sha256': sha(session_path.read_bytes()),
            'sandbox_id_sha256': sha(login['sandbox_id']),
            'assigned_url_sha256': sha(url),
            'task_id': visible['task_id'],
            'package_sha256': visible['package_sha256'],
            'actor_seed_sha256':
                binding['normalized_baseline_sha256'],
            'owner_email': owner, 'actor_email': actor,
            'owner_principal_sha256': owner_hash,
            'actor_principal_sha256': actor_hash,
            'assigned_item_id': 'ITEM!101',
            'parent_item_id': 'ITEM!100',
            'owner_permissions': assigned,
            'parent_permissions': parent,
            'graph_lease': {'file': graph_path.name,
                            'sha256': sha(graph_path.read_bytes())},
            'evidence': evidence,
            'reviews': {name: True for name in (
                'distinct_accounts', 'actor_signed_in_as_actor',
                'assigned_file_editable', 'sentinel_file_denied',
                'owner_seed_readback_matched',
                'no_other_benchmark_item_visible')},
        }
        write_private(directory / 'actor-scope.private.json',
                      boundary._canonical(scope))
        admitted = boundary.admit(
            session_path, self.task_path, run_path,
            self.package / 'unused-admit',
            work_root=Path.cwd() / 'work',
            expected_task={**visible,
                'actor_seed_sha256':
                    binding['normalized_baseline_sha256']},
            now=now)
        self.assertEqual(admitted.deck_url, url)
        self.assertEqual(admitted.permission_id_sha256,
                         sha(permission['id']))


if __name__ == '__main__':
    unittest.main()
