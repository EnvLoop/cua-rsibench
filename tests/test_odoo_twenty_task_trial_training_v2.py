"""Synthetic protocol fixtures only: zero actual task/provider/training credit.

The source epochs and private hash chains are exercised offline. These tests
must never dispatch an actor, teacher request, or Tinker training operation.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import twenty_task_trial_training_v2 as train
from enterprise_fallback.odoo18 import twenty_task_trial_training_v1 as original
from test_odoo_twenty_task_trial_training_v1 import (
    SyntheticNativeTeacherFixture, actual_datum, hashed, packet, synthetic_batch,
)


def rewrite_native_receipt(fixture, changes):
    """Retain a complete matching hash chain around deliberately invalid proof."""
    path = fixture.episode / 'episode.private.json'
    receipt = json.loads(path.read_bytes())
    receipt.update(changes)
    native_sha = packet(path, receipt)['sha256']
    fixture.descriptor['episode_receipt_sha256'] = native_sha
    packet(fixture.directory / 'native-teacher-result.private.json', {
        'episode_receipt_path': str(path), 'episode_receipt_sha256': native_sha,
    })
    rendered = deepcopy(fixture.batch.receipt)
    rendered['episode_receipt_sha256s'] = [native_sha]
    fixture.batch = SimpleNamespace(datums=fixture.batch.datums,
                                   prompts=fixture.batch.prompts, receipt=rendered)
    fixture.replace_pickle(fixture.batch)


def rewrite_saved_state(fixture, changes):
    path = fixture.episode / 'state.private.json'
    state = json.loads(path.read_bytes())
    state.update(changes)
    state_ref = packet(path, state)
    rewrite_native_receipt(fixture, {'saved_state_ref': state_ref})


def synthetic_render(cell_id, task_ids, episode_shas, turns, vision):
    return synthetic_batch(task_ids[0], episode_shas[0], turns, vision)


def synthetic_training_profile():
    anchor_path = original.ROOT / 'runtime/qwen38-vision/real-gui-diagnostic-prereg-v1.json'
    return {
        'schema': 'envloop-odoo20-qwen-sft-training-v1',
        'model': original.MODEL, 'action_profile': 'scale-action-profile-v0.6.6',
        'full_study_ratified_training_profile_claim': False,
        'automatic_replay_after_uncertain_call': False,
        'provider_invoice_required_for_cost_claim': True,
        'hyperparameter_reference_sha256': hashed(anchor_path.read_bytes()),
        'previous_training_asset_sha256': '599287bd38a7d673e29031d2554862df47251fd7fe9ace9c8eb9a02b267feb20',
        'pre_result_schedule_amendment': True,
        'coverage_policy': 'Synthetic fixture: one batch of two per step covers four 90-action episodes.',
        'optimizer_steps': 192, 'batch_size': 2, 'lora_rank': 8,
        'seed': 23, 'learning_rate': '0.0001', 'sampling_temperature': 0,
        'sample_max_tokens': 512, 'minimum_distinct_training_tasks': 4,
        'minimum_distinct_workflows': 4, 'max_supervised_tokens': 32768,
        'max_scheduled_tokens': 12582912,
    }


class SyntheticLineageFixture:
    """Hash-bound private plans with invented final metadata, no task bodies."""
    def __init__(self, root):
        self.root = root.resolve()
        self.namespace = self.root / 'work/synthetic-lineage.private'
        self.namespace.mkdir(parents=True)
        metadata = [
            {'task_id': f'ELPO-HID-SYNTH-{family}-{index:02d}', 'family': family,
             'package_sha256': 'a' * 64, 'source_asset_sha256': 'd' * 64}
            for family in ('purchase', 'inventory', 'sales', 'crm') for index in range(5)
        ]
        self.ancestor = {
            'schema': 'envloop-single-environment-twenty-task-trial-v1',
            'cell_id': 'odoo-community', 'study_type': 'single_environment_development_trial',
            'models': {'student': original.MODEL, 'teacher': 'gpt-6-sol',
                       'initial_researcher': 'gpt-6-sol'},
            'native_binding_sha256': 'b' * 64, 'sampling_seed': 'synthetic-lineage-seed',
            'final_tasks_metadata': metadata,
            'family_counts': {'purchase': 5, 'inventory': 5, 'sales': 5, 'crm': 5},
            'final_task_count': 20, 'selection_task_count': 20, 'train_task_count': 20,
            'actor_limits': {'actions': 90, 'seconds': 720, 'owned_lifecycle_seconds': 1200},
            'original_candidate_count': 100, 'sampling_uses_model_outcomes': False,
            'original_verifier_and_reset_required': True,
            'base_and_selected_checkpoint_same_final_tasks_required': True,
            'checkpoint_selection_before_final_outcomes_required': True,
            'formal_large_study_credit': 0, 'full_six_environment_publication_claim': False,
            'unknown_billing_is_null': True,
        }
        self.ancestor_path = self.namespace / 'synthetic-v13-plan.private.json'
        self.ancestor_sha = packet(self.ancestor_path, self.ancestor)['sha256']
        self.target = deepcopy(self.ancestor)
        self.target.update(runtime_epoch='v14', native_binding_sha256='1' * 64,
            teacher_data_plan_refs=[{
                'path': self.ancestor_path.name, 'sha256': self.ancestor_sha,
                'native_binding_sha256': 'b' * 64, 'native_epoch': 'v13',
            }])
        self.target_path = self.namespace / 'synthetic-v14-plan.private.json'
        self.target_sha = packet(self.target_path, self.target)['sha256']
        self.binding13 = {'binding_sha256': 'b' * 64, 'source_epoch': {'native': 'v13'}}
        self.binding14 = {'binding_sha256': '1' * 64, 'source_epoch': {'native': 'v14'}}

    def reopen(self):
        self.target_sha = packet(self.target_path, self.target)['sha256']
        with patch.object(train, 'ROOT', self.root), \
             patch.object(train, 'ANCESTOR_PLAN_SHA', self.ancestor_sha), \
             patch.object(train, 'ANCESTOR_NATIVE_BINDING_SHA', 'b' * 64), \
             patch.object(train.workers13, 'public_binding', return_value=self.binding13), \
             patch.object(train.workers14, 'public_binding', return_value=self.binding14):
            return train.checked_lineage(self.target_path, self.target_sha)


class LineageAuthorityTests(unittest.TestCase):
    def test_only_the_exact_production_ancestor_is_allowlisted(self):
        self.assertEqual(train.ANCESTOR_PLAN_SHA,
                         '126dfcdd9b270a489d0e7a34a64538a546738c81a04179bd089e454f6633436e')
        self.assertEqual(train.ANCESTOR_NATIVE_BINDING_SHA,
                         '56b3e77c254c5dd38d6bbaebf4661d3d71a7d053de44c942e055f0adf89842f4')

    def test_literal_v13_ancestor_and_fresh_v14_target_have_separate_authorities(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticLineageFixture(Path(temp))
            plan, origins = fixture.reopen()
            self.assertEqual(plan, fixture.target)
            self.assertEqual(set(origins), {fixture.ancestor_sha, fixture.target_sha})
            self.assertEqual(origins[fixture.ancestor_sha].native_epoch, 'v13')
            self.assertEqual(origins[fixture.target_sha].native_epoch, 'v14')
            self.assertEqual(origins[fixture.ancestor_sha].native_binding_sha256, 'b' * 64)
            self.assertEqual(origins[fixture.target_sha].native_binding_sha256, '1' * 64)
            self.assertIs(origins[fixture.ancestor_sha].workers, train.workers13)
            self.assertIs(origins[fixture.target_sha].workers, train.workers14)
            self.assertEqual(origins[fixture.ancestor_sha].plan['final_tasks_metadata'],
                             origins[fixture.target_sha].plan['final_tasks_metadata'])

    def test_unapproved_ancestor_sha_epoch_or_native_binding_is_rejected(self):
        for field, value in (
            ('sha256', '9' * 64), ('native_epoch', 'v14'),
            ('native_binding_sha256', '1' * 64),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticLineageFixture(Path(temp))
                fixture.target['teacher_data_plan_refs'][0][field] = value
                with self.assertRaisesRegex(train.TrainingError, 'unapproved_teacher_data_ancestor'):
                    fixture.reopen()

    def test_source_binding_drift_and_ancestor_file_drift_are_rejected(self):
        for defect in ('v13_source', 'v14_source', 'ancestor_bytes', 'target_epoch'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticLineageFixture(Path(temp))
                if defect == 'v13_source':
                    fixture.binding13['binding_sha256'] = '9' * 64
                elif defect == 'v14_source':
                    fixture.binding14['binding_sha256'] = '9' * 64
                elif defect == 'ancestor_bytes':
                    with fixture.ancestor_path.open('ab') as stream:
                        stream.write(b'\n')
                else:
                    fixture.target['runtime_epoch'] = 'v13'
                with self.assertRaises(ValueError):
                    fixture.reopen()

    def test_rehashed_target_cannot_change_frozen_final_metadata_seed_models_or_limits(self):
        for defect in ('final_metadata', 'seed', 'student', 'teacher', 'researcher',
                       'family_counts', 'actions', 'seconds', 'original_candidate_count',
                       'sampling_outcomes', 'selection_before_final'):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticLineageFixture(Path(temp))
                if defect == 'final_metadata':
                    fixture.target['final_tasks_metadata'][0]['package_sha256'] = '9' * 64
                elif defect == 'seed':
                    fixture.target['sampling_seed'] = 'different-seed'
                elif defect in ('student', 'teacher', 'researcher'):
                    key = 'initial_researcher' if defect == 'researcher' else defect
                    fixture.target['models'][key] = 'gpt-6-astra'
                elif defect == 'family_counts':
                    fixture.target['family_counts']['sales'] = 4
                elif defect in ('actions', 'seconds'):
                    fixture.target['actor_limits'][defect] += 1
                elif defect == 'original_candidate_count':
                    fixture.target['original_candidate_count'] = 20
                elif defect == 'sampling_outcomes':
                    fixture.target['sampling_uses_model_outcomes'] = True
                else:
                    fixture.target['checkpoint_selection_before_final_outcomes_required'] = False
                with self.assertRaisesRegex(ValueError, 'authority|frozen_task_or_model_contract|limits_changed'):
                    fixture.reopen()


class ExplicitTrainingProfileTests(unittest.TestCase):
    def reopen_profile(self, namespace, profile):
        path = namespace / 'synthetic-training-profile.private.json'
        profile_sha = packet(path, profile)['sha256']
        return train.frozen_training({'training_asset_sha256': profile_sha}, namespace, {
            'trial_training_ref': {'path': str(path), 'sha256': profile_sha},
            'actor_limits': {'actions': 90},
        })

    def test_explicit_192_step_profile_preserves_bound_rank_seed_learning_rate(self):
        with tempfile.TemporaryDirectory() as temp:
            settings, profile_sha = self.reopen_profile(Path(temp).resolve(), synthetic_training_profile())
            self.assertEqual((settings['optimizer_steps'], settings['batch_size'],
                              settings['lora_rank'], settings['seed']), (192, 2, 8, 23))
            self.assertEqual(settings['learning_rate'], '0.0001')
            self.assertTrue(settings['pre_result_schedule_amendment'])
            self.assertFalse(settings['full_study_ratified_training_profile_claim'])
            self.assertFalse(settings['automatic_replay_after_uncertain_call'])
            self.assertEqual(len(profile_sha), 64)

    def test_changed_schedule_anchor_model_or_hyperparameters_are_rejected_after_rehash(self):
        for field, value in (
            ('optimizer_steps', 64), ('batch_size', 3), ('lora_rank', 16), ('seed', 24),
            ('learning_rate', '0.0002'), ('model', 'Qwen/Qwen3-30B'),
            ('pre_result_schedule_amendment', False),
            ('previous_training_asset_sha256', '0' * 64),
            ('hyperparameter_reference_sha256', '0' * 64),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                profile = synthetic_training_profile()
                profile[field] = value
                with self.assertRaises(train.TrainingError):
                    self.reopen_profile(Path(temp).resolve(), profile)

    def test_profile_cannot_be_public_or_unbound_to_target_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            namespace = Path(temp).resolve()
            path = namespace / 'synthetic-training-profile.private.json'
            profile_sha = packet(path, synthetic_training_profile())['sha256']
            plan = {'trial_training_ref': {'path': str(path), 'sha256': profile_sha}}
            with self.assertRaises(train.TrainingError):
                train.frozen_training({'training_asset_sha256': '0' * 64}, namespace, plan)
            path.chmod(0o644)
            with self.assertRaisesRegex(train.TrainingError, 'private_owned_input'):
                train.frozen_training({'training_asset_sha256': profile_sha}, namespace, plan)


class OriginEpisodeFixture(SyntheticNativeTeacherFixture):
    """V13 origin and V14 target remain visibly distinct synthetic authorities."""
    def __init__(self, root):
        root = root.resolve()
        super().__init__(root)
        self.plan['runtime_epoch'] = 'v13'
        self.source_binding = {
            'binding_sha256': 'b' * 64, 'source_epoch': {'native': 'v13'},
            'source_sha256s': {'enterprise_fallback/odoo18/verify.py': 'e' * 64},
        }
        self.workers = SimpleNamespace(
            public_binding=lambda: deepcopy(self.source_binding),
            _model_modules=lambda binding: (SimpleNamespace(adapter_sha256=lambda: 'f' * 64),),
            private_json=original.trial.workers.private_json,
            require=original.trial.workers.require,
        )
        self.origin = SimpleNamespace(plan=self.plan, plan_path=root / 'ancestor-plan.private.json',
            plan_sha256='c' * 64, native_binding_sha256='b' * 64,
            native_epoch='v13', workers=self.workers)
        self.target = deepcopy(self.plan)
        self.target.update(runtime_epoch='v14', native_binding_sha256='1' * 64)
        self.manifest['trial_plan_sha256'] = '2' * 64
        self.descriptor.update(origin_trial_plan_sha256='c' * 64,
                               origin_native_binding_sha256='b' * 64,
                               origin_native_epoch='v13')

    def reopen_v2(self):
        vision = SimpleNamespace(render=lambda *args: (self.batch.prompts[0], None))
        with patch.object(original.trial.teacher, '_render_turns', synthetic_render):
            return train.reopen_episode(self.directory, self.descriptor, self.manifest,
                self.target, self.task, self.proposal, vision,
                origins={'c' * 64: self.origin})


class OriginEvidenceTests(unittest.TestCase):
    def test_native13_origin_is_reopened_without_relabeling_its_raw_or_rendered_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = OriginEpisodeFixture(Path(temp))
            before = {path: path.read_bytes() for path in fixture.directory.rglob('*') if path.is_file()}
            result = fixture.reopen_v2()
            self.assertEqual(result.receipt, fixture.batch.receipt)
            self.assertEqual(result.origin_metadata['origin_native_epoch'], 'v13')
            self.assertEqual(result.origin_metadata['origin_native_binding_sha256'], 'b' * 64)
            self.assertEqual(result.origin_metadata['origin_trial_plan_sha256'], 'c' * 64)
            self.assertEqual(json.loads((fixture.directory / 'rendered-train-receipt.private.json').read_bytes())
                             ['trial_plan_sha256'], 'c' * 64)
            self.assertEqual(json.loads((fixture.episode / 'episode.private.json').read_bytes())
                             ['runtime_sha256'], 'b' * 64)
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_origin_epoch_binding_hash_or_plan_mismatch_is_rejected(self):
        for field, value in (
            ('origin_native_epoch', 'v14'),
            ('origin_native_binding_sha256', '1' * 64),
            ('origin_trial_plan_sha256', '9' * 64),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                fixture = OriginEpisodeFixture(Path(temp))
                fixture.descriptor[field] = value
                with self.assertRaises(train.TrainingError):
                    fixture.reopen_v2()

    def test_rehashed_failed_native_trajectory_cannot_supply_training_credit(self):
        for failure in ('episode_status', 'independent_save', 'no_regression'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                fixture = OriginEpisodeFixture(Path(temp))
                if failure == 'episode_status':
                    rewrite_native_receipt(fixture, {'status': 'failed'})
                    label = 'worker_episode_identity_or_split_invalid'
                else:
                    key = 'target_state_pass' if failure == 'independent_save' else 'no_regression_pass'
                    rewrite_saved_state(fixture, {key: False, 'evaluator_result': 'fail'})
                    label = 'episode_independent_saved_state_missing'
                with self.assertRaisesRegex(ValueError, label):
                    fixture.reopen_v2()

    def test_matching_hashes_do_not_admit_foreign_teacher_or_wrong_source_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = OriginEpisodeFixture(Path(temp))
            request = fixture.directory / 'teacher-call-000-request.private.json'
            packet(request, {**json.loads(request.read_bytes()), 'model': 'gpt-6.1-sol'})
            with self.assertRaisesRegex(train.TrainingError, 'actual_active_teacher_model'):
                fixture.reopen_v2()
        with tempfile.TemporaryDirectory() as temp:
            fixture = OriginEpisodeFixture(Path(temp))
            rewrite_native_receipt(fixture, {'adapter_sha256': '9' * 64})
            with self.assertRaisesRegex(ValueError, 'worker_episode_identity_or_split_invalid'):
                fixture.reopen_v2()

    def test_fresh_origin_proxy_does_not_mutate_shared_v13_teacher_workers(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = OriginEpisodeFixture(Path(temp))
            workers_before = original.trial.workers
            first = train.scoped_origin_trial(fixture.origin)
            second = train.scoped_origin_trial(fixture.origin)
            self.assertIsNot(first, second)
            self.assertIs(first.workers, fixture.workers)
            self.assertIs(second.workers, fixture.workers)
            self.assertIs(original.trial.workers, workers_before)


class DatasetDispatchTests(unittest.TestCase):
    def load_synthetic_dataset(self, namespace, *, has_fresh_v14):
        worker = namespace / 'public-worker/train'
        families = ('purchase', 'inventory', 'sales', 'crm')
        cases = {family: [
            {'id': f'ELPO-TRN-SYNTH-{family}-{index:02d}', 'family': family,
             'prompt': 'Synthetic public TRAIN fixture. Never execute as actual evidence.'}
            for index in range(5)
        ] for family in families}
        rows = [{'task_id': row['id'], 'package_sha256': 'a' * 64}
                for family in families for row in cases[family]]
        worker_sha = packet(worker / 'private/task_set_manifest.json', {'train': rows})['sha256']
        cases_sha = packet(worker / 'private/partition_cases.json', {'cases': cases})['sha256']
        chosen = [cases[family][0]['id'] for family in families]
        proposal = {'hypothesis': 'Synthetic fixture only.', 'train_task_ids': chosen,
                    'teacher_request': 'Synthetic teacher fixture. No provider dispatch.'}
        proposal_ref = packet(namespace / 'synthetic-proposal.private.json', proposal)
        plan = {'models': {'student': original.MODEL, 'teacher': 'gpt-6-sol',
                           'initial_researcher': 'gpt-6-sol'},
                'native_binding_sha256': '1' * 64, 'runtime_epoch': 'v14',
                'final_tasks_metadata': [{'task_id': f'ELPO-HID-SYNTH-{i:03d}'} for i in range(20)]}
        target_sha = '2' * 64
        origins = {
            'c' * 64: SimpleNamespace(plan_path=namespace / 'synthetic-ancestor-plan.private.json'),
            target_sha: SimpleNamespace(plan_path=namespace / 'synthetic-target-plan.private.json'),
        }
        descriptors = [{
            'task_id': task_id, 'directory': f'synthetic-teacher-{index}.private',
            'origin_trial_plan_sha256': target_sha if has_fresh_v14 and index == 3 else 'c' * 64,
            'origin_native_epoch': 'v14' if has_fresh_v14 and index == 3 else 'v13',
            'origin_native_binding_sha256': '1' * 64 if has_fresh_v14 and index == 3 else 'b' * 64,
            'episode_receipt_sha256': 'e' * 64, 'rendered_sha256': 'f' * 64,
        } for index, task_id in enumerate(chosen)]
        manifest = {'schema': train.SCHEMA, 'trial_plan_sha256': target_sha,
                    'target_execution_native_epoch': 'v14', 'formal_large_study_credit': 0,
                    'train_worker_ref': {'path': str(worker), 'sha256': worker_sha},
                    'train_cases_sha256': cases_sha, 'proposal_ref': proposal_ref,
                    'batches': descriptors}
        path = namespace / 'synthetic-training-input.private.json'
        manifest_sha = packet(path, manifest)['sha256']
        prompt = actual_datum().model_input

        def reopened(directory, descriptor, *args, **kwargs):
            return SimpleNamespace(datums=[actual_datum()], prompts=[prompt],
                receipt={'synthetic': True, 'train_task_ids': [descriptor['task_id']]},
                origin_metadata={key: descriptor[key] for key in (
                    'task_id', 'origin_trial_plan_sha256', 'origin_native_binding_sha256',
                    'origin_native_epoch', 'episode_receipt_sha256', 'rendered_sha256')})

        with patch.object(train, 'checked_lineage', return_value=(plan, origins)), \
             patch.object(train, 'check_sources'), \
             patch.object(train, 'frozen_training', return_value=(synthetic_training_profile(), '8' * 64)), \
             patch.object(train.original_trial, 'checked_proposal', return_value=proposal), \
             patch.object(train.original_trial.teacher, '_load_renderer', return_value=None), \
             patch.object(train, 'reopen_episode', side_effect=reopened):
            return train.load_inputs(plan_path=namespace / 'synthetic-target-plan.private.json',
                plan_sha=target_sha, manifest_path=path, manifest_sha=manifest_sha,
                trust_owned_rendered=True)

    def test_mixed_origins_are_preserved_and_a_fresh_v14_episode_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            namespace = Path(temp).resolve()
            inputs = self.load_synthetic_dataset(namespace, has_fresh_v14=True)
            self.assertEqual([row['origin_native_epoch'] for row in inputs.origin_metadata],
                             ['v13', 'v13', 'v13', 'v14'])
            self.assertEqual(inputs.execution_native_epoch, 'v14')
            self.assertEqual(len(inputs.datums), 4)
            self.assertEqual(len(inputs.indices), 192)
            self.assertEqual(inputs.scheduled_tokens, 384 * 5)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(train.TrainingError, 'fresh_v14_teacher_origin_required'):
                self.load_synthetic_dataset(Path(temp).resolve(), has_fresh_v14=False)

    def test_lineage_is_durable_before_the_owned_v1_tinker_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp).resolve()
            origins = [{'origin_native_epoch': 'v13', 'formal_large_study_credit': 0},
                       {'origin_native_epoch': 'v14', 'formal_large_study_credit': 0}]
            inputs = SimpleNamespace(identity='a' * 64, execution_native_epoch='v14',
                execution_native_binding_sha256='1' * 64, origin_metadata=origins)

            def synthetic_dispatch(actual_inputs, actual_out):
                self.assertIs(actual_inputs, inputs)
                self.assertEqual(actual_out, out)
                lineage = json.loads((out / 'training-data-lineage.private.json').read_bytes())
                self.assertEqual(lineage['teacher_episode_origins'], origins)
                self.assertEqual(lineage['target_execution_native_epoch'], 'v14')
                self.assertFalse(lineage['v13_data_relabelled_v14'])
                self.assertEqual(lineage['v13_qualification_credit'], 0)
                self.assertIsNone(lineage['actual_cost_usd'])
                return {'synthetic': True, 'formal_large_study_credit': 0}

            with patch.object(train.base, 'train_real', side_effect=synthetic_dispatch) as dispatch:
                result = train.train_real(inputs, out)
            self.assertEqual(result['formal_large_study_credit'], 0)
            dispatch.assert_called_once()

    def test_uncertain_dispatch_consumes_dataset_and_forbids_second_output_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            namespace = Path(temp).resolve()
            inputs = SimpleNamespace(namespace=namespace, identity='a' * 64,
                training_sha='b' * 64, training=synthetic_training_profile(),
                plan={'models': {'teacher': 'gpt-6-sol'}}, datums=[actual_datum()],
                scheduled_tokens=5, execution_native_epoch='v14')
            kwargs = {'plan_path': 'unused', 'plan_sha': 'c' * 64, 'manifest_path': 'unused',
                      'manifest_sha': 'd' * 64, 'execute': True, 'trust_owned_rendered': True}
            with patch.object(train, 'load_inputs', return_value=inputs), \
                 patch.object(train, 'train_real', side_effect=RuntimeError('Synthetic uncertain dispatch')) as dispatch, \
                 patch.dict('os.environ', {'TINKER_API_KEY': 'synthetic-not-a-real-key'}):
                with self.assertRaises(RuntimeError):
                    train.run(output_root=namespace / 'first.private', **kwargs)
                with self.assertRaisesRegex(train.TrainingError, 'already_consumed_no_replay'):
                    train.run(output_root=namespace / 'second.private', **kwargs)
            dispatch.assert_called_once()
            consumed = next(namespace.glob('tinker-training-*-consumed.private.json'))
            self.assertFalse(json.loads(consumed.read_bytes())['automatic_replay_authorized'])


class TrainingScheduleTests(unittest.TestCase):
    def test_new_capacity_covers_four_complete_ninety_action_trajectories(self):
        settings = {'batch_size': 2, 'optimizer_steps': 192,
                    'max_supervised_tokens': 32768, 'max_scheduled_tokens': 4194304}
        datums = [actual_datum() for _ in range(4 * 90)]
        indices, scheduled = train.fixed_schedule(datums, settings)
        self.assertEqual(len(indices), 192)
        self.assertTrue(all(len(batch) == 2 for batch in indices))
        self.assertEqual({index for batch in indices for index in batch}, set(range(360)))
        self.assertEqual(scheduled, 384 * 5)
        self.assertEqual(indices[-1], [22, 23])
        with self.assertRaisesRegex(train.TrainingError, 'capacity_prerequisite'):
            train.fixed_schedule([actual_datum() for _ in range(385)], settings)
        with self.assertRaisesRegex(train.TrainingError, 'scheduled_token_cap'):
            train.fixed_schedule(datums, {**settings, 'max_scheduled_tokens': scheduled - 1})

    def test_no_datum_may_exceed_individual_token_bound(self):
        settings = {'batch_size': 2, 'optimizer_steps': 192,
                    'max_supervised_tokens': 4, 'max_scheduled_tokens': 4194304}
        with self.assertRaisesRegex(train.TrainingError, 'supervised_token_cap'):
            train.fixed_schedule([actual_datum()], settings)


if __name__ == '__main__':
    unittest.main()
