"""Synthetic train-only teacher tests never call a model or real application."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from cursibench import full_study_teacher_adapter_v1 as teacher  # noqa: E402
from cursibench import http_transport  # noqa: E402
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench.scale_action_contract import make_observation  # noqa: E402
from cursibench.scale_action_output_v066 import MODEL_ACTION_CONTRACT  # noqa: E402
from native_desktop_factory import qwen_v066_adapter  # noqa: E402
from native_desktop_factory.v066_final_freeze import source_hashes  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_private(path: Path, value: object) -> str:
    raw = teacher._canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)
    return sha(raw)


class FakeStudy:
    def __init__(self, root: Path, ratification_path: Path, ratification: dict):
        self.repo_root = root
        self.ratification_path = ratification_path
        self.ratification_sha256 = sha(ratification_path.read_bytes())
        self.ratification = ratification
        self.public_witness_sha256 = 'c' * 64
        self.plan = {
            'campaign_count': 24,
            'distinct_official_task_identities': 600,
            'cell_ids': list(matrix.CELLS),
            'cells': [{'cell_id': cell_id,
                       'matched_bindings': {'runtime': 'd' * 64,
                                            'verifier': '5' * 64}}
                      for cell_id in matrix.CELLS],
        }

    def student_training_configuration(self):
        return {'model': teacher.MODEL,
                'action_profile': teacher.ACTION_PROFILE_VERSION,
                'batch_size': 2, 'optimizer_steps': 1,
                'max_supervised_tokens': 32768,
                'max_scheduled_tokens': 10_000}, 'b' * 64

    def teacher_configuration(self):
        harness = {
            'schema': teacher.HARNESS_SCHEMA,
            'transport': 'agentrouterhub-responses-image-v1',
            'image_detail': 'high', 'max_frame_bytes': 4_000_000,
            'max_frame_pixels': 2_000_000,
            'max_actions_per_episode': 8,
            'max_input_tokens_per_call': 32768,
            'request_timeout_seconds': 180,
        }
        route = {
            'schema': teacher.RATE_SCHEMA,
            'model': matrix.TEACHER,
            'base_url': 'https://sub2api.agentrouterhub.com',
            'input_usd_per_million_tokens': '5',
            'output_usd_per_million_tokens': '20',
            'fixed_usd_per_call': '0',
            'billing_multiplier_upper': '2',
        }
        return {'model': matrix.TEACHER, 'config_sha256': 'e' * 64,
                'settings': {'reasoning_effort': 'low',
                             'reasoning_mode': 'standard',
                             'max_output_tokens': 128},
                'assets': {
                    'harness': teacher._canonical(harness),
                    'provider_route': teacher._canonical(route),
                    'tool_grammar': MODEL_ACTION_CONTRACT.encode(),
                    'prompt': b'Use only the visible GUI and one action per turn.',
                }}


class FakeSession:
    def __init__(self, root: Path, ratification_path: Path,
                 ratification: dict):
        self.study = FakeStudy(root, ratification_path, ratification)
        self.directory = root / 'work' / 'campaign'
        self.directory.mkdir(parents=True, mode=0o700)
        self.intent = {'cell_id': 'magento-admin', 'researcher_id': 'astra',
                       'e2b_usd_cap': '20',
                       'e2b_sandbox_hours_cap': '20'}
        self.views = {
            'train': ({'task_id': 'train-001',
                       'package_sha256': 'a' * 64},),
            'selection': tuple({'task_id': f'select-{n:03d}',
                                'package_sha256': 'b' * 64}
                               for n in range(20)),
        }
        self.proposal = {
            'schema': 'cua-full-study-researcher-proposal-v1',
            'hypothesis': 'Collect a train example.',
            'train_task_ids': ['train-001'],
            'teacher_request': 'Use the current GUI to save the train item.',
        }
        self.proposal_path = self.directory / 'proposal-001.private.json'
        self.proposal_sha = write_private(self.proposal_path, self.proposal)
        self.calls: list[dict] = []

    def _events(self, kind):
        if kind == 'researcher_proposal':
            return [{'data': {'round_index': 1,
                              'proposal_sha256': self.proposal_sha,
                              'hypothesis_sha256': sha(
                                  self.proposal['hypothesis'].encode()),
                              'train_context_sha256': self.context_sha}}]
        return []

    def _check_time(self):
        return None

    def _train_context(self, path):
        value = json.loads(path.read_bytes())
        return value['tasks'], sha(path.read_bytes())

    def dispatch_paid(self, **kwargs):
        self.calls.append(kwargs)
        result = kwargs['provider'](kwargs['request'])
        return {'attempt_id': kwargs['attempt_id'], 'result': result,
                'result_sha256': sha(teacher._canonical(result)),
                'billing_state': 'awaiting_provider_usage_reconciliation'}


class FakeWorker:
    cell_id = 'magento-admin'
    action_profile = teacher.ACTION_PROFILE_VERSION
    original_software_gui = True
    original_surface = 'web'
    requires_e2b = False

    def __init__(self, adapter_sha256: str, *,
                 cell_id='magento-admin', runtime_sha='d' * 64,
                 verifier_sha='5' * 64):
        self.cell_id = cell_id
        self.adapter_sha256 = adapter_sha256
        self.runtime_sha = runtime_sha
        self.verifier_sha = verifier_sha
        self.tamper = None
        self.calls = 0

    def run_episode(self, *, task, out_dir, sample_teacher, dispatch_e2b):
        self.calls += 1
        if self.requires_e2b:
            dispatch_e2b(lease_seconds=600, reserve_usd='0.500000000',
                         provider=lambda _request: {
                             'schema': teacher.E2B_RESULT_SCHEMA,
                             'sandbox_id': 'fake-train',
                             'lease_seconds': 600, 'created': True})
        frame_refs = []
        trace = []
        memory = ''
        previous = None
        image = io.BytesIO()
        Image.new('RGB', (160, 120), (70, 80, 90)).save(image, 'PNG')
        for step in (0, 1):
            observation = make_observation(
                task_id=task['task_id'],
                task_binding_sha256=task['package_sha256'],
                instruction=task['visible_instruction'],
                step=step, screenshot_bytes=image.getvalue(),
                a11y_text='Products',
                controls=[{'ref': 'c001', 'role': 'button',
                           'label': 'Save', 'visible': True,
                           'enabled': True}],
                previous_action_result=previous, memory=memory)
            sampled = sample_teacher(observation, lambda: observation.frame_id)
            path = out_dir / 'frames' / f'step-{step:03d}.png'
            path.write_bytes(image.getvalue())
            path.chmod(0o600)
            frame_refs.append({'path': f'frames/step-{step:03d}.png',
                               'sha256': sha(image.getvalue())})
            trace.append(sampled['trace_row'])
            memory = sampled['action']['memory']
            previous = {'status': 'applied', 'code': 'ok'}
        if self.tamper == 'frame':
            (out_dir / 'frames/step-000.png').write_bytes(b'tampered')
        if self.tamper == 'trace':
            trace[0]['action']['type'] = 'finish'
        trace_raw = teacher._canonical(trace)
        trace_path = out_dir / 'actions.private.json'
        trace_path.write_bytes(trace_raw)
        trace_path.chmod(0o600)
        common = {'cell_id': self.cell_id,
                  'task_id': task['task_id'],
                  'package_sha256': task['package_sha256']}
        saved = {**common, 'schema': teacher.STATE_SCHEMA,
                 'independent_of_actor': True,
                 'native_save_observed': True,
                 'target_state_pass': True,
                 'no_regression_pass': True,
                 'saved_artifact_sha256': 'f' * 64,
                 'verifier_sha256': self.verifier_sha,
                 'evaluator_result': 'pass'}
        reset = {**common, 'schema': teacher.RESET_SCHEMA,
                 'independent_of_actor': True,
                 'fresh_environment': True,
                 'state_equivalence_pass': True,
                 'sandbox_terminated': True}
        artifact_dir = out_dir / 'artifacts'
        artifact_dir.mkdir(mode=0o700)
        saved_artifact = artifact_dir / 'saved-artifact.private.json'
        saved_sha = write_private(saved_artifact, {'saved': True})
        saved['saved_artifact_sha256'] = saved_sha
        saved['saved_artifact_ref'] = {
            'path': 'artifacts/' + saved_artifact.name,
            'sha256': saved_sha}
        baseline_artifact = artifact_dir / 'baseline.private.json'
        restored_artifact = artifact_dir / 'restored.private.json'
        baseline_sha = write_private(baseline_artifact, {'state': 'baseline'})
        restored_sha = write_private(restored_artifact, {'state': 'baseline'})
        reset['baseline_semantic_sha256'] = baseline_sha
        reset['restored_semantic_sha256'] = restored_sha
        reset['baseline_state_ref'] = {
            'path': 'artifacts/' + baseline_artifact.name,
            'sha256': baseline_sha}
        reset['restored_state_ref'] = {
            'path': 'artifacts/' + restored_artifact.name,
            'sha256': restored_sha}
        if self.tamper == 'saved_state':
            saved['no_regression_pass'] = False
        if self.tamper == 'artifact':
            saved_artifact.write_bytes(b'changed after save')
        if self.tamper == 'reset':
            reset['restored_semantic_sha256'] = '2' * 64
        saved_path = out_dir / 'saved-state.private.json'
        reset_path = out_dir / 'reset.private.json'
        saved_sha = write_private(saved_path, saved)
        reset_sha = write_private(reset_path, reset)
        receipt = {
            'schema': teacher.EPISODE_SCHEMA, 'status': 'admitted',
            'split': 'train', **common,
            'action_profile': self.action_profile,
            'teacher_model': matrix.TEACHER,
            'original_software_gui': True,
            'original_surface': self.original_surface,
            'runtime_sha256': self.runtime_sha,
            'adapter_sha256': self.adapter_sha256,
            'frame_refs': frame_refs,
            'action_trace_ref': {'path': trace_path.name,
                                 'sha256': sha(trace_raw)},
            'saved_state_ref': {'path': saved_path.name,
                                'sha256': saved_sha},
            'reset_ref': {'path': reset_path.name,
                          'sha256': reset_sha},
            'teacher_result_sha256s': [
                row['teacher_result_sha256'] for row in trace],
            'e2b_attempt_ids': (['e2b-teacher-r001-e001']
                                if self.requires_e2b else []),
        }
        if self.tamper == 'split':
            receipt['split'] = 'final'
        receipt_path = out_dir / 'episode.private.json'
        receipt_sha = write_private(receipt_path, receipt)
        return {'episode_receipt_path': str(receipt_path),
                'episode_receipt_sha256': receipt_sha}


class TeacherAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cua-teacher-test-')
        self.root = Path(self.temp.name)
        (self.root / 'work').mkdir(mode=0o700)
        source = source_hashes()
        profiles = {cell_id: {
            'common_source_sha256s': source,
            'adapter_sha256': ('e' * 64 if cell_id != 'desktop-native'
                               else sha(Path(qwen_v066_adapter.__file__).read_bytes()))}
            for cell_id in matrix.CELLS}
        self.ratification = {
            'schema': 'cua-six-cell-action-profile-v066-ratification-v1',
            'status': 'ratified_pre_result',
            'ratified_utc': datetime.now(timezone.utc).isoformat(),
            'action_profile': teacher.ACTION_PROFILE_VERSION,
            'common_source_sha256s': source,
            'cell_profiles': profiles,
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }
        self.ratification_path = self.root / 'ratification.private.json'
        write_private(self.ratification_path, self.ratification)
        self.session = FakeSession(self.root, self.ratification_path,
                                   self.ratification)
        self.worker = FakeWorker('e' * 64)
        self.context = self.root / 'work' / 'context.private.json'
        write_private(self.context, {
            'schema': 'cua-full-study-researcher-train-view-v1',
            'cell_id': 'magento-admin',
            'tasks': [{'task_id': 'train-001',
                       'package_sha256': 'a' * 64,
                       'visible_instruction': 'Save the train item.'}],
        })
        self.session.context_path = self.context
        self.session.context_sha = sha(self.context.read_bytes())
        self.teacher_calls = 0

    def tearDown(self):
        self.temp.cleanup()

    def provider(self, request):
        self.teacher_calls += 1
        self.assertEqual(request['schema'], teacher.TEACHER_REQUEST_SCHEMA)
        self.assertEqual(request['train_task_id'], 'train-001')
        self.assertTrue(request['image_data_url'].startswith('data:image/png;base64,'))
        self.assertIn('scale-action-output-v0.6.6', request['user_text'])
        text = ('{"type":"click","target":{"ref":"c001"}}'
                if request['step'] == 0 else '{"type":"finish"}')
        return {'text': text,
                'receipt': {'reported_model': matrix.TEACHER,
                            'status': 'completed',
                            'response_id': f'fake-{self.teacher_calls}',
                            'usage': {'input_tokens': 100,
                                      'output_tokens': 10}}}

    def collect(self):
        # Unit tests use a synthetic renderer but still exercise the exact
        # persisted receipt fields expected by dispatcher._rendered_train_batch.
        def fake_render(cell_id, task_ids, episode_shas, turns, vision):
            self.assertEqual(cell_id, 'magento-admin')
            self.assertEqual(task_ids, ['train-001'])
            self.assertEqual(len(turns), 2)
            for turn in turns:
                prompt = teacher.output_v066.render_for_model(
                    turn['observation'])
                self.assertIn('scale-action-output-v0.6.6', prompt['instruction'])
            receipt = {
                'schema': teacher.RENDER_SCHEMA, 'cell_id': cell_id,
                'action_profile': teacher.ACTION_PROFILE_VERSION,
                'model': teacher.MODEL,
                'train_task_ids': task_ids,
                'episode_receipt_sha256s': episode_shas,
                'datum_token_lengths': [20] * len(turns),
                'prompt_token_lengths': [10] * len(turns),
            }
            return teacher.RenderedTrainBatch(
                [SimpleNamespace(model_input=SimpleNamespace(length=20))
                 for _ in turns],
                [SimpleNamespace(length=10) for _ in turns], receipt)
        with patch.object(teacher, '_load_renderer', return_value=object()), \
             patch.object(teacher, '_render_turns', side_effect=fake_render):
            return teacher.collect_train_batch(
                self.session, 1, self.context,
                self.root / 'work' / 'teacher-round-001',
                self.worker, teacher_provider=self.provider)

    def test_train_only_batch_and_exact_private_manifest(self):
        result = self.collect()
        self.assertEqual(self.teacher_calls, 2)
        self.assertEqual(self.worker.calls, 1)
        self.assertEqual([row['category'] for row in self.session.calls],
                         ['teacher_rollout', 'teacher_rollout'])
        for row in self.session.calls:
            self.assertEqual(row['resource_reservation'], {
                'teacher_rollout_calls': '1',
                'teacher_rollout_tokens': str(32768 + 128)})
            self.assertGreater(float(row['reserve_usd']), 0)
        manifest = json.loads(result.dataset_manifest_path.read_bytes())
        self.assertEqual(result.dataset_manifest_path.stat().st_mode & 0o777,
                         0o600)
        self.assertEqual(set(manifest), {
            'schema', 'cell_id', 'action_profile', 'model', 'train_task_ids',
            'train_package_sha256_by_id', 'episode_receipt_sha256s',
            'rendered_batch_sha256', 'admitted_train_only',
            'selection_task_count', 'final_task_count'})
        self.assertEqual(manifest['train_task_ids'], ['train-001'])
        self.assertEqual(manifest['train_package_sha256_by_id'],
                         {'train-001': 'a' * 64})
        self.assertEqual(manifest['selection_task_count'], 0)
        self.assertEqual(manifest['final_task_count'], 0)
        self.assertEqual(manifest['rendered_batch_sha256'],
                         sha(teacher._canonical(result.rendered_batch.receipt)))
        self.assertEqual(len(result.rendered_batch.datums), 2)

    def test_hidden_or_selection_id_rejected_before_paid_calls(self):
        for task_id in ('select-000', 'final-001'):
            self.session.proposal['train_task_ids'] = [task_id]
            self.session.proposal_sha = write_private(
                self.session.proposal_path, self.session.proposal)
            with self.assertRaisesRegex(teacher.TeacherAdapterError,
                                        'teacher_source_not_train_only'):
                self.collect()
            self.assertEqual(self.teacher_calls, 0)
            self.assertEqual(self.worker.calls, 0)

    def test_missing_or_changed_ratification_fails_before_paid_call(self):
        self.ratification_path.unlink()
        with self.assertRaisesRegex(teacher.TeacherAdapterError,
                                    'real_six_cell_ratification_missing'):
            self.collect()
        self.assertEqual(self.session.calls, [])

    def test_tampered_worker_artifacts_cannot_become_datums(self):
        for kind, code in (
            ('frame', 'episode_reference_hash_mismatch'),
            ('trace', 'episode_trace_differs_from_paid_actions'),
            ('saved_state', 'episode_independent_saved_state_missing'),
            ('artifact', 'episode_reference_hash_mismatch'),
            ('reset', 'episode_fresh_reset_missing'),
            ('split', 'worker_episode_identity_or_split_invalid'),
        ):
            self.worker.tamper = kind
            destination = self.root / 'work' / 'teacher-round-001'
            if destination.exists():
                # Each synthetic case represents a fresh campaign attempt.
                import shutil
                shutil.rmtree(destination)
            with self.assertRaisesRegex(teacher.TeacherAdapterError, code):
                self.collect()
            self.assertFalse((destination / 'dataset.private.json').exists())

    def test_e2b_reservation_precedes_teacher_and_is_separate(self):
        self.worker.requires_e2b = True
        self.collect()
        self.assertEqual([row['category'] for row in self.session.calls],
                         ['e2b', 'teacher_rollout', 'teacher_rollout'])
        self.assertEqual(self.session.calls[0]['resource_reservation'], {
            'e2b_sandbox_hours': '0.166666667',
            'e2b_peak_concurrency': '1'})

    def test_model_or_usage_ambiguity_has_no_dataset(self):
        def bad_provider(request):
            result = TeacherAdapterTests.provider(self, request)
            result['receipt']['reported_model'] = 'other-model'
            return result
        with patch.object(self, 'provider', side_effect=bad_provider):
            with self.assertRaisesRegex(teacher.TeacherAdapterError,
                                        'teacher_model_status_or_usage_ambiguous'):
                self.collect()
        self.assertFalse((self.root / 'work' / 'teacher-round-001' /
                          'dataset.private.json').exists())

    def test_changed_train_context_or_missing_renderer_stops_before_paid_work(self):
        self.session.context_sha = '0' * 64
        with self.assertRaisesRegex(teacher.TeacherAdapterError,
                                    'researcher_proposal_context_changed'):
            self.collect()
        self.assertEqual(self.session.calls, [])
        self.session.context_sha = sha(self.context.read_bytes())
        with patch.object(teacher, '_load_renderer',
                          side_effect=teacher.TeacherAdapterError(
                              'qwen_renderer_not_available')):
            with self.assertRaisesRegex(teacher.TeacherAdapterError,
                                        'qwen_renderer_not_available'):
                teacher.collect_train_batch(
                    self.session, 1, self.context,
                    self.root / 'work' / 'teacher-round-001',
                    self.worker, teacher_provider=self.provider)
        self.assertEqual(self.session.calls, [])
        self.assertFalse((self.root / 'work' / 'teacher-round-001').exists())

    def test_multimodal_responses_transport_has_image_and_no_text_fallback(self):
        request = {'model': matrix.TEACHER,
                   'reasoning_effort': 'low', 'reasoning_mode': 'standard',
                   'max_output_tokens': 128,
                   'system_prompt': 'Use the visible GUI.',
                   'user_text': 'Click Save.',
                   'image_data_url': 'data:image/png;base64,AAAA',
                   'image_detail': 'high'}
        captured = []

        def post(url, payload, headers, timeout):
            captured.append((url, payload, headers, timeout))
            return {'id': 'synthetic-response', 'model': matrix.TEACHER,
                    'status': 'completed',
                    'usage': {'input_tokens': 100, 'output_tokens': 10},
                    'output': [{'type': 'message', 'content': [
                        {'type': 'output_text', 'text': '{"type":"finish"}'}]}]}

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'synthetic-test-key'}), \
             patch.object(http_transport, 'post_json', side_effect=post):
            result = teacher._real_teacher_provider(request, 180)
        self.assertEqual(result['receipt']['reported_model'], matrix.TEACHER)
        self.assertEqual(len(captured), 1)
        url, payload, headers, timeout = captured[0]
        self.assertEqual(url, 'https://sub2api.agentrouterhub.com/v1/responses')
        self.assertEqual(timeout, 180)
        self.assertEqual(payload['input'][1]['content'][1], {
            'type': 'input_image', 'image_url': request['image_data_url'],
            'detail': 'high'})
        self.assertEqual(payload['store'], False)
        self.assertEqual(headers['Authorization'], 'Bearer synthetic-test-key')


if __name__ == '__main__':
    unittest.main()
