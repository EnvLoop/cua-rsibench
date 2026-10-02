"""Original Excel-web teacher worker under fake E2B, Graph and SEC oracle."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from cursibench.full_study_matrix_v1 import CELLS
from cursibench.full_study_teacher_adapter_v1 import _verify_episode
from cursibench import scale_action_output_v066
from native_desktop_factory import qwen_v066_adapter
from native_desktop_factory.v066_final_freeze import source_hashes
from tests.office_actor_scope_fixture import write_scope_fixture
from tests.test_office_web_ppt_teacher_worker_v1 import (
    FakeLeases, png, write_private,
)
from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tools import office_web_actor_scope_gate_v1 as scope_gate
from tools import office_web_e2b_login_bridge_v1 as bridge
from tools import office_web_excel_teacher_worker_v1 as worker_module
from tools import sec_excel_web_train_oracle_v1 as neutral_oracle


def sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


class FakeGraph:
    def __init__(self, *, wrong_saved=False, wrong_reset=False,
                 mismatched_pair=False, actor_permission_present=False,
                 wrong_saved_non_target=False):
        self.calls = []
        self.wrong_saved = wrong_saved
        self.wrong_reset = wrong_reset
        self.mismatched_pair = mismatched_pair
        self.actor_permission_present = actor_permission_present
        self.wrong_saved_non_target = wrong_saved_non_target

    def preflight(self):
        pass

    def capture(self, *, owner_user_id, drive_id, item_id,
                expected_name, out_dir):
        phase = out_dir.name.removesuffix('-graph')
        self.calls.append((phase, item_id))
        if phase == 'saved':
            payload = workbook(
                number='101' if self.wrong_saved_non_target else '100',
                formula='A1*2' if self.wrong_saved else 'A1*3')
        elif phase == 'reset' and self.wrong_reset:
            payload = workbook(number='101')
        else:
            payload = workbook()
        second = workbook(number='102') if (
            self.mismatched_pair and phase == 'saved') else payload
        write_private(out_dir / 'first.private.xlsx', payload)
        write_private(out_dir / 'second.private.xlsx', second)
        result = {
            'schema': 'cua-office-excel-owner-double-download-v1',
            'owner_user_id_sha256': sha(owner_user_id),
            'drive_id_sha256': sha(drive_id),
            'item_id_sha256': sha(item_id),
            'name_sha256': sha(expected_name),
            'etag_sha256': sha('etag'),
            'first_sha256': sha(payload),
            'second_sha256': sha(second),
            'byte_count': len(payload),
        }
        write_private(out_dir / 'readback.private.json',
                      worker_module._canonical(result))
        return result

    def verify_actor_revoked(self, *, owner_user_id, drive_id,
                             item_id, actor_email, prior_permission_id):
        phase = 'actor' if item_id == 'DEMO!101' else 'reset'
        self.calls.append((phase + '-revoked', item_id))
        if phase == 'actor' and self.actor_permission_present:
            raise ValueError('graph_prior_actor_permission_still_present')
        return {
            'schema': 'cua-office-excel-owner-revocation-readback-v1',
            'owner_user_id_sha256': sha(owner_user_id),
            'drive_id_sha256': sha(drive_id),
            'item_id_sha256': sha(item_id),
            'actor_email_sha256': sha(actor_email.casefold()),
            'prior_permission_id_sha256': sha(prior_permission_id),
            'actor_grants_remaining': 0, 'broad_links_remaining': 0,
            'remaining_permission_count': 2,
            'owner_permission_count': 1,
            'inherited_permission_count': 1,
            'existing_access_link_count': 0,
        }


class FakeOracle:
    def __init__(self, reference: Path):
        self.reference = reference

    def calibrate(self, seed, reference, _cases, _case_id):
        return {'schema': 'cua-sec-integrated-train-oracle-calibration-v1',
                'unsolved_seed_rejected': True,
                'positive_reference_passed': True,
                'checked_formula_targets': 25,
                'source_counterfactual_profiles': 2,
                'seed_sha256': sha(seed.read_bytes()),
                'reference_sha256': sha(reference.read_bytes())}

    def neutral(self, seed, candidate):
        return neutral_oracle.neutral(seed, candidate)

    def score(self, candidate, seed, _cases, _case_id):
        equivalent = neutral_oracle.neutral(candidate, self.reference)
        passed = equivalent['equivalent']
        return {'schema': 'cua-sec-integrated-train-saved-score-v1',
                'artifact_pass': passed,
                'checked_formula_targets': 25,
                'source_counterfactual_profiles': 2 if passed else 0,
                'error_count': 0 if passed else 1,
                'candidate_sha256': sha(candidate.read_bytes()),
                'seed_sha256': sha(seed.read_bytes()),
                'native_recalculation_verified': False}


class FakeSession:
    def __init__(self, root: Path, private: Path, task_id: str,
                 package_sha256: str, ratification_path: Path,
                 ratification: dict, ratification_sha256: str):
        self.study = type('Study', (), {
            'repo_root': root, 'ratification_path': ratification_path,
            'ratification': ratification,
            'ratification_sha256': ratification_sha256,
            'public_witness_sha256': 'f' * 64,
            'plan': {'campaign_count': 24,
                     'distinct_official_task_identities': 600,
                     'cell_ids': list(CELLS),
                     'cells': [{'cell_id': 'excel-web',
                                'matched_bindings': {
                                    'runtime': 'b' * 64,
                                    'verifier': 'c' * 64}}]},
        })()
        self.views = {
            'train': ({'task_id': task_id,
                       'package_sha256': package_sha256},),
            'selection': tuple({'task_id': f'select-{i:02}',
                                'package_sha256': 'e' * 64}
                               for i in range(20)),
        }
        self.intent = {'cell_id': 'excel-web', 'researcher_id': 'astra'}
        self.directory = private / 'campaign'
        self.directory.mkdir(mode=0o700)
        self.paid_calls = []

    def dispatch_paid(self, **kwargs):
        self.paid_calls.append(kwargs)
        result = kwargs['provider'](kwargs['request'])
        return {'attempt_id': kwargs['attempt_id'],
                'result': result,
                'result_sha256': sha(worker_module._canonical(result)),
                'billing_state': 'awaiting_provider_usage_reconciliation'}

    def _train_context(self, _path):
        return [], '0' * 64

    def _events(self, _kind=None):
        return []

    def _check_time(self):
        pass


class ExcelTeacherWorkerTests(unittest.TestCase):
    def setUp(self):
        private = Path.cwd() / 'work'
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private,
                                                 prefix='excel-teacher-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path.cwd()
        self.private = Path(self.temp.name)
        self.task_id = 'xl-train-' + 'a' * 16
        self.package_sha = 'd' * 64
        self.task = {'task_id': self.task_id,
                     'package_sha256': self.package_sha,
                     'visible_instruction': 'Repair the SEC train workbook.'}
        self.task_path = (self.private / 'packages' / 'train' /
                          self.task_id / 'task.private.json')
        seed = workbook()
        write_private(self.task_path.parent / 'actor.xlsx', seed)
        write_private(self.task_path, worker_module._canonical({
            'schema': 'excel-web-original-train-package-v1',
            'split': 'train', 'official_final_credit': 0,
            'task_id': self.task_id,
            'actor_task': self.task['visible_instruction'],
            'actor_xlsx_sha256': sha(seed),
        }))
        self.reference = self.private / 'reference.private.xlsx'
        write_private(self.reference, workbook(formula='A1*3'))
        self.cases = self.private / 'one-case.private.json'
        write_private(self.cases, worker_module._canonical([{
            'case_id': 'sec-train-case', 'split': 'train_candidate',
            'source_package': {
                'schema': 'sec-integrated-source-package-v1'},
        }]))
        common = source_hashes()
        self.ratification_path = self.private / 'ratification.private.json'
        self.ratification = {
            'schema': 'cua-six-cell-action-profile-v066-ratification-v1',
            'status': 'ratified_pre_result',
            'ratified_utc': datetime.now(timezone.utc).isoformat(),
            'action_profile': 'scale-action-profile-v0.6.6',
            'common_source_sha256s': common,
            'cell_profiles': {cell: {
                'common_source_sha256s': common,
                'adapter_sha256': (
                    worker_module.adapter_bundle_sha256()
                    if cell == 'excel-web' else
                    sha(Path(qwen_v066_adapter.__file__).read_bytes())
                    if cell == 'desktop-native' else 'a' * 64),
            } for cell in CELLS},
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }
        write_private(self.ratification_path,
                      worker_module._canonical(self.ratification))
        self.ratification_sha = sha(self.ratification_path.read_bytes())
        self.binding_path = self.private / 'binding.private.json'
        self.binding = {
            'schema': worker_module.SCHEMA, 'cell_id': 'excel-web',
            'task_id': self.task_id, 'package_sha256': self.package_sha,
            'task_path': str(self.task_path),
            'task_file_sha256': sha(self.task_path.read_bytes()),
            'actor_seed_sha256': sha(seed),
            'cases_path': str(self.cases),
            'cases_sha256': sha(self.cases.read_bytes()),
            'case_id': 'sec-train-case',
            'reference_path': str(self.reference),
            'reference_sha256': sha(self.reference.read_bytes()),
            'actor_item': self.item('DEMO!101', 'Actor'),
            'reset_item': self.item('DEMO!102', 'Reset'),
            'owner_email_sha256': scope_gate.digest('owner@example.test'),
            'actor_email_sha256': scope_gate.digest('actor@example.test'),
            'ratification_sha256': self.ratification_sha,
            'runtime_sha256': 'b' * 64,
            'verifier_sha256': 'c' * 64,
            'adapter_sha256': worker_module.adapter_bundle_sha256(),
            'adapter_source_sha256s': worker_module.source_bundle_sha256s(),
            'lease_seconds': 900, 'max_steps': 3,
            'wall_seconds': 300, 'manual_wait_seconds': 180,
            'post_finish_wait_seconds': 0,
            'e2b_reserve_usd': '1', 'graph_read_reserve_usd': '0.01',
        }
        self.save_binding()
        self.session = FakeSession(
            self.root, self.private, self.task_id, self.package_sha,
            self.ratification_path, self.ratification,
            self.ratification_sha)
        self.leases = FakeLeases()
        self.graph = FakeGraph()
        self.oracle = FakeOracle(self.reference)
        self.output = self.private / 'episode-001'
        self.output.mkdir(mode=0o700)
        (self.output / 'frames').mkdir(mode=0o700)
        self.turns = []

    @staticmethod
    def item(item_id, role):
        name = f'EL-Excel-Train-{role}.xlsx'
        return {'owner_user_id': 'owner1234',
                'drive_id': 'drive1234', 'item_id': item_id,
                'file_name': name,
                'edit_url': ('https://onedrive.live.com/personal/' +
                             '0123456789ABCDEF/_layouts/15/Doc.aspx?' +
                             'sourcedoc=%7B00000000-0000-4000-8000-000000000000%7D' +
                             f'&file={name}&action=edit')}

    def save_binding(self):
        write_private(self.binding_path,
                      worker_module._canonical(self.binding))

    def operator_wait(self, session_path, item, phase, _timeout):
        session = json.loads(session_path.read_bytes())
        now = int(time.time())
        bridge.write_new(session_path.parent / 'run.private.json', {
            'schema': 'excel-web-e2b-train-run-private-v1',
            'split': 'train',
            'manual_login_confirmed_at_unix': now,
            'workbook_url': item['edit_url'],
            'max_steps': 3, 'wall_seconds': 300,
        })
        receipt = write_scope_fixture(
            session_path, session, item['edit_url'], 'excel',
            self.binding['actor_seed_sha256'], png())
        if phase == 'reset':
            assigned = session_path.parent / 'assigned-permissions.private.json'
            snapshot = json.loads(assigned.read_bytes())
            snapshot['item_id'] = item['item_id']
            write_private(assigned, worker_module._canonical(snapshot))
            receipt['assigned_item_id'] = item['item_id']
            receipt['owner_permissions']['sha256'] = sha(assigned.read_bytes())
            write_private(session_path.parent / 'actor-scope.private.json',
                          worker_module._canonical(receipt))

    def sample_teacher(self, observation, current_frame_id):
        step = len(self.turns)
        raw = ('{"type":"click","target":{"x":10,"y":10}}'
               if step == 0 else '{"type":"finish"}')
        action = scale_action_output_v066.normalize_model_action(
            raw, observation, current_frame_id=current_frame_id())
        trace = {'step': step, 'frame_id': observation.frame_id,
                 'frame_sha256': observation.screenshot['sha256'],
                 'action': action,
                 'teacher_result_sha256': sha(f'fake-excel-teacher-{step}')}
        self.turns.append({'observation': observation, 'action': action,
                           'trace_row': trace,
                           'teacher_result_sha256':
                               trace['teacher_result_sha256']})
        return {'action': action, 'trace_row': trace,
                'teacher_result_sha256': trace['teacher_result_sha256']}

    def dispatch_e2b(self, *, lease_seconds, reserve_usd,
                     provider, phase='actor'):
        self.assertEqual(lease_seconds, 900)
        self.assertEqual(reserve_usd, '1')
        result = provider({'phase': phase})
        return {'attempt_id': 'e2b-excel-test-' + phase,
                'result': result,
                'result_sha256': sha(worker_module._canonical(result))}

    def run_worker(self):
        worker = worker_module.OfficeExcelTeacherWorker(
            self.session, self.binding_path,
            lease_factory=self.leases, graph_reader=self.graph,
            oracle_runner=self.oracle,
            operator_wait=self.operator_wait,
            operator_wait_revocation=lambda *_: None)
        result = worker.run_episode(
            task=self.task, out_dir=self.output,
            sample_teacher=self.sample_teacher,
            dispatch_e2b=self.dispatch_e2b)
        return worker, result

    def test_saved_formula_and_fresh_reset_bind_shared_teacher_receipt(self):
        worker, result = self.run_worker()
        self.assertEqual(self.leases.stop_calls,
                         ['actor-login', 'reset-login'])
        self.assertEqual(self.graph.calls,
                         [('actor-preflight', 'DEMO!101'),
                          ('saved', 'DEMO!101'),
                          ('actor-revoked', 'DEMO!101'),
                          ('reset', 'DEMO!102'),
                          ('reset-revoked', 'DEMO!102')])
        digest = _verify_episode(
            self.output, result,
            cell_id='excel-web', task=self.task,
            runtime_sha='b' * 64, adapter_sha=worker.adapter_sha256,
            verifier_sha='c' * 64, turns=self.turns,
            e2b_attempt_ids=['e2b-excel-test-actor',
                             'e2b-excel-test-reset'],
            requires_e2b=True, requires_fresh_e2b_reset=True)
        self.assertEqual(digest, result['episode_receipt_sha256'])
        self.assertEqual(len(self.turns), 2)
        self.assertEqual(len(self.session.paid_calls), 5)

    def test_wrong_source_or_case_split_refuses_before_cloud(self):
        self.binding['package_sha256'] = '0' * 64
        self.save_binding()
        with self.assertRaisesRegex(ValueError, 'binding_not_frozen_train_task'):
            self.run_worker()
        self.assertEqual(self.graph.calls, [])
        self.binding['package_sha256'] = self.package_sha
        self.save_binding()
        cases = json.loads(self.cases.read_bytes())
        cases[0]['split'] = 'final_candidate'
        write_private(self.cases, worker_module._canonical(cases))
        self.binding['cases_sha256'] = sha(self.cases.read_bytes())
        self.save_binding()
        with self.assertRaisesRegex(ValueError, 'case_not_single_sec_train_candidate'):
            self.run_worker()
        self.assertEqual(self.graph.calls, [])

    def test_wrong_saved_formula_blocks_reset_and_admitted_episode(self):
        self.graph.wrong_saved = True
        with self.assertRaisesRegex(ValueError, 'saved_formula_or_numeric_state_failed'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_changed_reset_numeric_cell_fails_fresh_equivalence(self):
        self.graph.wrong_reset = True
        with self.assertRaisesRegex(ValueError, 'fresh_copy_reset_state_changed'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls,
                         ['actor-login', 'reset-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_missing_one_file_acl_cleans_paid_lease_before_model(self):
        def no_scope(session_path, item, phase, _timeout):
            now = int(time.time())
            bridge.write_new(session_path.parent / 'run.private.json', {
                'schema': 'excel-web-e2b-train-run-private-v1',
                'split': 'train',
                'manual_login_confirmed_at_unix': now,
                'workbook_url': item['edit_url'],
                'max_steps': 3, 'wall_seconds': 300,
            })
        self.operator_wait = no_scope
        with self.assertRaisesRegex(ValueError, 'actor_scope_unverified'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertEqual(self.turns, [])

    def test_owner_double_download_mismatch_and_actor_permission_block(self):
        self.graph.mismatched_pair = True
        with self.assertRaisesRegex(ValueError, 'owner_double_download_not_bound'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_non_target_sec_numeric_mutation_is_rejected(self):
        self.graph.wrong_saved_non_target = True
        with self.assertRaisesRegex(ValueError, 'saved_formula_or_numeric_state_failed'):
            self.run_worker()
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_actor_grant_must_be_revoked_before_reset_share(self):
        self.graph.actor_permission_present = True
        with self.assertRaisesRegex(ValueError, 'prior_actor_permission_still_present'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertNotIn('sandbox-reset-001', self.leases.sandboxes)

    def test_frame_change_blocks_excel_gui_action(self):
        original = self.sample_teacher
        def changed(observation, current_frame_id):
            sampled = original(observation, current_frame_id)
            self.leases.sandboxes['sandbox-actor-001'].screen = png('black')
            return sampled
        self.sample_teacher = changed
        with self.assertRaisesRegex(ValueError, 'frame_changed_before_gui_dispatch'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_binding_preparer_is_offline_and_source_hash_bound(self):
        target = self.private / 'prepared-binding.private.json'
        result = worker_module.prepare_private_binding(
            self.session, task=self.task, task_path=self.task_path,
            cases_path=self.cases, case_id='sec-train-case',
            reference_path=self.reference,
            actor_item=self.binding['actor_item'],
            reset_item=self.binding['reset_item'],
            owner_email='owner@example.test',
            actor_email='actor@example.test',
            out_path=target, lease_seconds=900, max_steps=3,
            wall_seconds=300, manual_wait_seconds=180,
            post_finish_wait_seconds=0,
            e2b_reserve_usd='1', graph_read_reserve_usd='0.01',
            oracle_runner=self.oracle)
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(result['binding_sha256'], sha(target.read_bytes()))
        self.assertEqual(self.session.paid_calls, [])


if __name__ == '__main__':
    unittest.main()
