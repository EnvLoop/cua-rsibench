"""Offline native-GUI Office worker tests; no E2B, Graph, or model request."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import zipfile

from PIL import Image

from cursibench import scale_action_output_v066
from cursibench.full_study_teacher_adapter_v1 import _verify_episode
from cursibench.full_study_matrix_v1 import CELLS
from native_desktop_factory import qwen_v066_adapter
from native_desktop_factory.v066_final_freeze import source_hashes
from tests.office_actor_scope_fixture import write_scope_fixture
from tools import office_web_e2b_login_bridge_v1 as bridge
from tools import office_web_actor_scope_gate_v1 as scope_gate
from tools import office_web_ppt_teacher_worker_v1 as worker_module


def sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def write_private(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(raw)
    path.chmod(0o600)


def pptx(tag: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name in ('[Content_Types].xml', 'ppt/presentation.xml',
                     'ppt/_rels/presentation.xml.rels'):
            archive.writestr(name, '<root/>')
        archive.writestr('ppt/slides/slide1.xml', f'<root>{tag}</root>')
    return stream.getvalue()


def png(color='white') -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', (64, 48), color).save(stream, format='PNG')
    return stream.getvalue()


class FakeSandbox:
    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id
        self.actions = []
        self.title = 'Chrome'
        self.screen = png()

    def get_info(self, **_kwargs):
        return SimpleNamespace(template_id=bridge.EXPECTED_TEMPLATE_ID)

    def launch(self, application, *, uri):
        self.actions.append(('launch', application, uri))
        self.title = parse_qs(urlsplit(uri).query)['file'][0] + ' - PowerPoint'

    def get_current_window_id(self):
        return 'window-1'

    def get_window_title(self, _window_id):
        return self.title

    def screenshot(self):
        return self.screen

    def move_mouse(self, x, y):
        self.actions.append(('move_mouse', x, y))

    def left_click(self):
        self.actions.append(('left_click',))


class FakeLeases:
    def __init__(self):
        self.sandboxes = {}
        self.stop_calls = []

    def preflight(self):
        pass

    def create(self, out_dir: Path, lease_seconds: int):
        phase = out_dir.name.removesuffix('-login')
        sandbox_id = 'sandbox-' + phase + '-001'
        out_dir.mkdir(mode=0o700)
        now = int(time.time())
        bridge.write_new(out_dir / 'session.private.json', {
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
            'lease_started_at_unix': now - 2,
            'lease_seconds': lease_seconds,
            'sandbox_id': sandbox_id,
            'stream_url': 'https://fake.e2b.app/vnc.html',
            'stream_auth_key': 'SyntheticTestKey1234',
        })
        self.sandboxes[sandbox_id] = FakeSandbox(sandbox_id)
        return sandbox_id

    def connect(self, sandbox_id):
        return self.sandboxes[sandbox_id]

    def stop(self, session_path):
        self.stop_calls.append(session_path.parent.name)
        write_private(session_path.parent / 'stop.private.json',
                      b'{"status":"killed"}\n')
        return 'killed'


class FakeGraph:
    def __init__(self, *, reset_drift=False, saved_partial=False,
                 mismatch_pair=False, actor_permission_present=False):
        self.calls = []
        self.reset_drift = reset_drift
        self.saved_partial = saved_partial
        self.mismatch_pair = mismatch_pair
        self.actor_permission_present = actor_permission_present

    def preflight(self):
        pass

    def capture(self, *, owner_user_id, drive_id, item_id,
                expected_name, out_dir):
        phase = out_dir.name.removesuffix('-graph')
        self.calls.append((phase, item_id))
        if phase == 'saved':
            body = pptx('partial' if self.saved_partial else 'positive')
        elif phase == 'reset' and self.reset_drift:
            body = pptx('positive')
        else:
            body = pptx('baseline')
        second = pptx('other') if self.mismatch_pair and phase == 'saved' else body
        write_private(out_dir / 'first.private.pptx', body)
        write_private(out_dir / 'second.private.pptx', second)
        receipt = {
            'schema': 'cua-office-ppt-owner-double-download-v1',
            'owner_user_id_sha256': sha(owner_user_id),
            'drive_id_sha256': sha(drive_id),
            'item_id_sha256': sha(item_id),
            'name_sha256': sha(expected_name),
            'etag_sha256': sha('etag'),
            'first_sha256': sha(body), 'second_sha256': sha(second),
            'byte_count': len(body),
        }
        write_private(out_dir / 'readback.private.json',
                      worker_module._canonical(receipt))
        return receipt

    def permissions_empty(self, *, owner_user_id, drive_id, item_id):
        phase = 'actor' if item_id == 'DEMO!101' else 'reset'
        self.calls.append((phase + '-revoked', item_id))
        if phase == 'actor' and self.actor_permission_present:
            raise ValueError('graph_actor_permission_still_present')
        return {
            'schema': 'cua-office-ppt-owner-revocation-readback-v1',
            'owner_user_id_sha256': sha(owner_user_id),
            'drive_id_sha256': sha(drive_id),
            'item_id_sha256': sha(item_id),
            'permissions_count': 0,
        }


class FakeSession:
    def __init__(self, root: Path, private: Path, task_id: str,
                 package_sha256: str, ratification_path: Path,
                 ratification: dict, ratification_sha256: str):
        self.study = SimpleNamespace(
            repo_root=root, ratification_sha256=ratification_sha256,
            ratification_path=ratification_path, ratification=ratification,
            public_witness_sha256='f' * 64,
            plan={'campaign_count': 24,
                  'distinct_official_task_identities': 600,
                  'cell_ids': list(CELLS),
                  'cells': [{'cell_id': 'powerpoint-web',
                             'matched_bindings': {
                                 'runtime': 'b' * 64,
                                 'verifier': 'c' * 64}}]})
        self.views = {'train': ({'task_id': task_id,
                                 'package_sha256': package_sha256},),
                      'selection': tuple({'task_id': f'select-{index:02}',
                                          'package_sha256': 'e' * 64}
                                         for index in range(20))}
        self.intent = {'cell_id': 'powerpoint-web', 'researcher_id': 'astra'}
        self.directory = private / 'campaign'
        self.directory.mkdir(parents=True, mode=0o700)
        self.paid_calls = []

    def dispatch_paid(self, **kwargs):
        self.paid_calls.append(kwargs)
        result = kwargs['provider'](kwargs['request'])
        return {'attempt_id': kwargs['attempt_id'], 'result': result,
                'result_sha256': sha(worker_module._canonical(result)),
                'billing_state': 'awaiting_provider_usage_reconciliation'}

    def _train_context(self, _path):
        return [], '0' * 64

    def _events(self, _kind=None):
        return []

    def _check_time(self):
        pass


class OfficePptTeacherWorkerTests(unittest.TestCase):
    def setUp(self):
        private = Path.cwd() / 'work'
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private,
                                                 prefix='office-ppt-worker-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path.cwd()
        self.private = Path(self.temp.name)
        self.task_id = 'ppt-wdi-' + 'a' * 16
        self.package_sha = 'd' * 64
        self.task = {'task_id': self.task_id,
                     'package_sha256': self.package_sha,
                     'visible_instruction': 'Repair the train-only slide.'}
        self.task_path = (self.private / 'packages' / 'train' /
                          self.task_id / 'task.private.json')
        self.baseline = self.private / 'normalized-baseline.private.pptx'
        task_spec = {
            'schema': 'ppt-wdi-original-candidates-v1',
            'split': 'train', 'task_id': self.task_id,
            'actor_task': self.task['visible_instruction'],
            'official_final_credit': 0,
        }
        write_private(self.task_path, worker_module._canonical(task_spec))
        write_private(self.baseline, pptx('baseline'))
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
                    sha(Path(worker_module.__file__).read_bytes())
                    if cell == 'powerpoint-web' else
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
            'schema': worker_module.SCHEMA, 'cell_id': 'powerpoint-web',
            'task_id': self.task_id, 'package_sha256': self.package_sha,
            'task_path': str(self.task_path),
            'task_file_sha256': sha(self.task_path.read_bytes()),
            'normalized_baseline_path': str(self.baseline),
            'normalized_baseline_sha256': sha(self.baseline.read_bytes()),
            'actor_item': self.item('DEMO!101', 'Actor'),
            'reset_item': self.item('DEMO!102', 'Reset'),
            'owner_email_sha256': scope_gate.digest('owner@example.test'),
            'actor_email_sha256': scope_gate.digest('actor@example.test'),
            'ratification_sha256': self.ratification_sha,
            'runtime_sha256': 'b' * 64,
            'verifier_sha256': 'c' * 64,
            'verifier_module_sha256': sha(Path(worker_module.ppt_verify.__file__).read_bytes()),
            'adapter_sha256': sha(Path(worker_module.__file__).read_bytes()),
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
        self.output = self.private / 'episode-001'
        self.output.mkdir(mode=0o700)
        (self.output / 'frames').mkdir(mode=0o700)
        self.turns = []

    @staticmethod
    def item(item_id, role):
        file_name = f'EL-PPT-Train-{role}.pptx'
        return {
            'owner_user_id': 'owner1234', 'drive_id': 'drive1234',
            'item_id': item_id, 'file_name': file_name,
            'edit_url': ('https://onedrive.live.com/personal/' +
                         '0123456789ABCDEF/_layouts/15/Doc.aspx?' +
                         'sourcedoc=%7B00000000-0000-4000-8000-000000000000%7D' +
                         f'&file={file_name}&action=edit'),
        }

    def save_binding(self):
        write_private(self.binding_path,
                      worker_module._canonical(self.binding))

    def operator_wait(self, session_path, item, phase, _timeout):
        session = json.loads(session_path.read_bytes())
        now = int(time.time())
        bridge.write_new(session_path.parent / 'run.private.json', {
            'schema': 'office-web-e2b-train-run-private-v1',
            'split': 'train',
            'manual_login_confirmed_at_unix': now,
            'deck_url': item['edit_url'],
            'max_steps': 3, 'wall_seconds': 300,
        })
        receipt = write_scope_fixture(
            session_path, session, item['edit_url'], 'powerpoint',
            self.binding['normalized_baseline_sha256'], png())
        if phase == 'reset':
            assigned = session_path.parent / 'assigned-permissions.private.json'
            evidence = json.loads(assigned.read_bytes())
            evidence['item_id'] = item['item_id']
            write_private(assigned, worker_module._canonical(evidence))
            receipt['assigned_item_id'] = item['item_id']
            receipt['owner_permissions']['sha256'] = sha(assigned.read_bytes())
            write_private(session_path.parent / 'actor-scope.private.json',
                          worker_module._canonical(receipt))

    def sample_teacher(self, observation, current_frame_id):
        step = len(self.turns)
        action = (scale_action_output_v066.normalize_model_action(
            '{"type":"click","target":{"x":10,"y":10}}',
            observation, current_frame_id=current_frame_id()) if step == 0 else
            scale_action_output_v066.normalize_model_action(
                '{"type":"finish"}', observation,
                current_frame_id=current_frame_id()))
        trace = {'step': step, 'frame_id': observation.frame_id,
                 'frame_sha256': observation.screenshot['sha256'],
                 'action': action,
                 'teacher_result_sha256': sha(f'fake-teacher-{step}')}
        turn = {'observation': observation, 'action': action,
                'trace_row': trace,
                'teacher_result_sha256': trace['teacher_result_sha256']}
        self.turns.append(turn)
        return {'action': action, 'trace_row': trace,
                'teacher_result_sha256': trace['teacher_result_sha256']}

    def dispatch_e2b(self, *, lease_seconds, reserve_usd,
                     provider, phase='actor'):
        self.assertEqual(lease_seconds, 900)
        self.assertEqual(reserve_usd, '1')
        result = provider({'phase': phase})
        return {'attempt_id': 'e2b-test-' + phase,
                'result': result,
                'result_sha256': sha(worker_module._canonical(result))}

    @staticmethod
    def fake_freeze(_baseline, _task, *, office_web_normalized):
        assert office_web_normalized is True
        return {'schema': 'fake-frozen-oracle'}

    @staticmethod
    def fake_verify(_baseline, attempt, _oracle):
        raw = attempt.read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            text = archive.read('ppt/slides/slide1.xml').decode()
        if '>positive<' in text:
            changed = True
            correct = True
            score = 1.0
        elif '>partial<' in text:
            changed = True
            correct = False
            score = 0.0
        else:
            changed = False
            correct = False
            score = 0.0
        return {'status': 'scored', 'score': score,
                'target_correct': correct,
                'preservation_pass': True,
                'per_target': {'summary': {'changed': changed,
                                           'correct': correct}},
                'unexpected_parts': [],
                'official_final_credit': 0}

    def run_worker(self):
        worker = worker_module.OfficePptTeacherWorker(
            self.session, self.binding_path,
            lease_factory=self.leases, graph_reader=self.graph,
            operator_wait=self.operator_wait,
            operator_wait_revocation=lambda *_: None)
        with patch.object(worker_module.ppt_verify, 'freeze', self.fake_freeze),\
             patch.object(worker_module.ppt_verify, 'verify', self.fake_verify):
            result = worker.run_episode(
                task=self.task, out_dir=self.output,
                sample_teacher=self.sample_teacher,
                dispatch_e2b=self.dispatch_e2b)
        return worker, result

    def test_saved_positive_and_fresh_reset_match_teacher_adapter_contract(self):
        worker, result = self.run_worker()
        self.assertEqual(len(self.turns), 2)
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
            cell_id='powerpoint-web', task=self.task,
            runtime_sha='b' * 64, adapter_sha=worker.adapter_sha256,
            verifier_sha='c' * 64, turns=self.turns,
            e2b_attempt_ids=['e2b-test-actor', 'e2b-test-reset'],
            requires_e2b=True, requires_fresh_e2b_reset=True)
        self.assertEqual(digest, result['episode_receipt_sha256'])
        self.assertEqual([call['category'] for call in self.session.paid_calls],
                         ['storage_application'] * 5)

    def test_wrong_source_or_missing_scope_refuses_before_model_action(self):
        self.binding['package_sha256'] = 'e' * 64
        self.save_binding()
        with self.assertRaisesRegex(ValueError, 'binding_not_frozen_train_task'):
            self.run_worker()
        self.assertEqual(self.turns, [])
        self.assertEqual(self.graph.calls, [])

    def test_missing_one_file_acl_cleans_paid_actor_lease(self):
        def no_scope(session_path, item, phase, _timeout):
            now = int(time.time())
            bridge.write_new(session_path.parent / 'run.private.json', {
                'schema': 'office-web-e2b-train-run-private-v1',
                'split': 'train', 'manual_login_confirmed_at_unix': now,
                'deck_url': item['edit_url'],
                'max_steps': 3, 'wall_seconds': 300,
            })
        self.operator_wait = no_scope
        with self.assertRaisesRegex(ValueError, 'actor_scope_unverified'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertEqual(self.turns, [])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_changed_six_cell_ratification_refuses_before_graph_or_e2b(self):
        self.ratification['cell_profiles']['powerpoint-web']['adapter_sha256'] = '0' * 64
        write_private(self.ratification_path,
                      worker_module._canonical(self.ratification))
        with self.assertRaisesRegex(ValueError, 'ratification_changed'):
            self.run_worker()
        self.assertEqual(self.graph.calls, [])
        self.assertEqual(self.leases.sandboxes, {})

    def test_prior_actor_permission_must_be_revoked_before_reset_share(self):
        self.graph.actor_permission_present = True
        with self.assertRaisesRegex(ValueError, 'permission_still_present'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertNotIn('sandbox-reset-001', self.leases.sandboxes)

    def test_current_frame_change_blocks_gui_dispatch_and_cleans_lease(self):
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

    def test_private_binding_preparer_hashes_source_without_provider_call(self):
        path = self.private / 'prepared-binding.private.json'
        with patch.object(worker_module.ppt_verify, 'freeze', self.fake_freeze):
            result = worker_module.prepare_private_binding(
                self.session, task=self.task, task_path=self.task_path,
                normalized_baseline_path=self.baseline,
                actor_item=self.binding['actor_item'],
                reset_item=self.binding['reset_item'],
                owner_email='owner@example.test',
                actor_email='actor@example.test',
                out_path=path, lease_seconds=900, max_steps=3,
                wall_seconds=300, manual_wait_seconds=180,
                post_finish_wait_seconds=0,
                e2b_reserve_usd='1', graph_read_reserve_usd='0.01')
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(result['binding_sha256'], sha(path.read_bytes()))
        self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertEqual(self.session.paid_calls, [])

    def test_partial_saved_state_fails_without_reset_or_admitted_episode(self):
        self.graph.saved_partial = True
        with self.assertRaisesRegex(ValueError, 'saved_state_not_positive'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_reset_drift_fails_after_two_distinct_leases(self):
        self.graph.reset_drift = True
        with self.assertRaisesRegex(ValueError, 'fresh_copy_reset_state_changed'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls,
                         ['actor-login', 'reset-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())

    def test_divergent_owner_downloads_are_rejected(self):
        self.graph.mismatch_pair = True
        with self.assertRaisesRegex(ValueError, 'owner_double_download_not_bound'):
            self.run_worker()
        self.assertEqual(self.leases.stop_calls, ['actor-login'])
        self.assertFalse((self.output / 'episode.private.json').exists())


if __name__ == '__main__':
    unittest.main()
