"""Source/metadata and synthetic saved-artifact tests; no live controls."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_controls_v1 as subject
from tests import test_odoo_twenty_task_trial_evaluator_v1 as fixtures
save = fixtures.save


class TrialControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TrialEvaluatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        original = subject.evaluator.read_ref(self.fixture.plan['original_candidate_plan_ref'])
        roster = {'schema': subject.qualification.core.ROSTER_SCHEMA, 'split': 'official_hidden',
            'tasks': original['native_core_plan']['tasks'],
            'checkpoint': {key: subject.digest(key.encode()) for key in subject.qualification.core.CHECKPOINT_FILES}}
        self.original, _ = subject.qualification.prepare(roster)
        ref = save(self.root/'full-hundred-metadata.private.json', self.original)
        self.fixture.plan['original_candidate_plan_ref'] = ref
        self.trial_ref = save(self.root/'trial.private.json', self.fixture.plan)
        self.plan, self.public = subject.prepare(trial_plan_path=self.trial_ref['path'], trial_plan_sha=self.trial_ref['sha256'])

    def test_prepare_reads_only_metadata_preserves_hundred_and_fresh_native_nonce(self):
        with patch.object(subject, 'source_asset', side_effect=AssertionError('body read during prepare')), \
             patch.object(subject.reference, 'candidate_module', side_effect=AssertionError('native runner during prepare')):
            plan, public = subject.prepare(trial_plan_path=self.trial_ref['path'], trial_plan_sha=self.trial_ref['sha256'])
        self.assertEqual(len(plan['frozen_twenty_metadata']), 20)
        self.assertEqual(len(plan['native_core_plan']['tasks']), 100)
        self.assertEqual(plan['native_core_plan']['native_worker_binding_sha256'], self.original['native_core_plan']['native_worker_binding_sha256'])
        self.assertNotEqual(plan['native_core_plan']['run_nonce_hex'], self.original['native_core_plan']['run_nonce_hex'])
        self.assertEqual(public['model_calls'], 0)
        subject.validate_plan(plan)

    def test_wrong_metadata_foreign_source_hundred_admission_and_old_prefix_rejected(self):
        mutations = ('duplicate', 'reorder', 'unknown_task', 'core_twenty', 'old_nonce', 'formal_credit', 'model_call', 'old_schema')
        for mutation in mutations:
            value = copy.deepcopy(self.plan)
            if mutation == 'duplicate': value['frozen_twenty_metadata'][1] = value['frozen_twenty_metadata'][0]
            if mutation == 'reorder': value['frozen_twenty_metadata'].reverse()
            if mutation == 'unknown_task': value['frozen_twenty_metadata'][0]['task_id'] = 'SYNTHETIC-UNKNOWN'
            if mutation == 'core_twenty': value['native_core_plan']['task_count'] = 20
            if mutation == 'old_nonce':
                value['native_core_plan'] = copy.deepcopy(self.original['native_core_plan'])
                value['fresh_run_directory_name'] = 'odoo20-controls-'+value['native_core_plan']['run_nonce_hex']
            if mutation == 'formal_credit': value['official_final_tasks_admitted'] = 100
            if mutation == 'model_call': value['model_calls'] = 1
            if mutation == 'old_schema': value['schema'] = 'cua-full-study-six-cell-ratification-v1'
            with self.subTest(mutation=mutation), self.assertRaises(subject.evaluator.legacy.OdooFinalWorkerError):
                subject.validate_plan(value)

    def test_changed_original_checkpoint_or_native_source_is_rejected(self):
        for key in ('source_freeze_sha256', 'native_worker_binding_sha256'):
            value = copy.deepcopy(self.plan)
            value['native_core_plan'][key] = '0'*64
            with self.subTest(key=key), self.assertRaises(subject.evaluator.legacy.OdooFinalWorkerError):
                subject.validate_plan(value)
        value = copy.deepcopy(self.plan)
        value['native_core_plan']['checkpoint']['db_sha256'] = '0'*64
        with self.assertRaisesRegex(subject.evaluator.legacy.OdooFinalWorkerError, 'hundred_core_binding'):
            subject.validate_plan(value)

    def test_canonical_plan_bytes_and_exact_hash_required(self):
        path = self.root/'control-plan.private.json'
        path.write_bytes(subject.workers.canonical(self.plan)); path.chmod(0o600)
        subject._load(path, subject.digest(path.read_bytes()))
        path.write_text(json.dumps(self.plan, indent=2))
        with self.assertRaisesRegex(subject.evaluator.legacy.OdooFinalWorkerError, 'canonical_plan'):
            subject._load(path, subject.digest(path.read_bytes()))

    def test_original_saved_scores_source_reset_and_seventy_six_attachments_required(self):
        metadata = self.plan['frozen_twenty_metadata'][0]
        attempt = self.root/'synthetic-attempt'; attempt.mkdir(mode=0o700)
        save(attempt/'attempt.private.json', {'refs': {}})
        audit = {'independent_baseline_reward': 0.0, 'independent_positive_reward': 1.0,
            'independent_wrong_object_reward': 0.0, 'original_services_restored': True,
            'full_pre_web_filestore_reset_exact': True, 'protected_post_web_source_bytes_equal': True,
            'source_attachment_gui_frame_retained': True, 'protected_source_files_checked': 76,
            'model_attempts': 0, 'official_final_tasks_admitted': 0}
        facade = SimpleNamespace(_case_row=lambda *a: {}, audit_case=lambda **k: audit)
        with patch.object(subject.finalizer, '_v3_action_provenance', return_value={'synthetic_fixture': True}):
            subject._case_audit(facade, self.plan, metadata, attempt, self.root, 'f'*64)
            for key, bad in [('independent_wrong_object_reward', 1.0), ('original_services_restored', False),
                             ('full_pre_web_filestore_reset_exact', False), ('protected_post_web_source_bytes_equal', False),
                             ('source_attachment_gui_frame_retained', False), ('protected_source_files_checked', 16),
                             ('official_final_tasks_admitted', 100)]:
                old = audit[key]; audit[key] = bad
                with self.subTest(key=key), self.assertRaises(subject.evaluator.legacy.OdooFinalWorkerError):
                    subject._case_audit(facade, self.plan, metadata, attempt, self.root, 'f'*64)
                audit[key] = old

    def test_saved_result_rejects_nineteen_or_formal_admission_before_any_body_read(self):
        worker = self.root/'official_hidden'
        out = worker/'private/v066_twenty_task_controls_v1'/self.plan['fresh_run_directory_name']
        out.mkdir(parents=True, mode=0o700)
        intent = {'control_plan_sha256': 'f'*64, 'source_binding_sha256': self.plan['source_binding']['binding_sha256']}
        save(out/'control-intent.private.json', intent)
        result = {'schema': 'envloop-odoo20-native-controls-result-v1', 'status': subject.PENDING,
            'control_plan_sha256': 'f'*64, 'trial_plan_sha256': self.plan['trial_plan_ref']['sha256'],
            'saved_control_count': 20, 'original_world_count': 100, 'model_calls': 0,
            'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0, 'entries': [{}]*19}
        with patch.object(subject, '_load', return_value=self.plan), \
             patch.object(subject.qualification, '_facade', side_effect=AssertionError('body/native boundary crossed')):
            for mutation in ('nineteen', 'admitted'):
                value = copy.deepcopy(result)
                if mutation == 'admitted': value['entries'] = [{}]*20; value['official_final_tasks_admitted'] = 20
                save(out/'controls-result.private.json', value)
                with self.subTest(mutation=mutation), self.assertRaisesRegex(subject.evaluator.legacy.OdooFinalWorkerError, 'saved_control_result'):
                    subject.audit(plan_path='', plan_sha='f'*64, worker_dir=worker, run_dir=out)

    def test_run_cannot_execute_without_explicit_authority(self):
        with patch.object(subject.reference, 'candidate_module') as runner:
            with self.assertRaisesRegex(subject.evaluator.legacy.OdooFinalWorkerError, 'explicit_native_dispatch'):
                subject.run(plan_path='', plan_sha='', worker_dir='', run_dir='', train_control_path='', train_control_sha='',
                    root_review_path='', root_review_sha='')
            runner.assert_not_called()

    def test_independent_visual_review_cannot_use_an_unbound_or_missing_hash(self):
        with patch.object(subject, '_load', return_value=self.plan):
            for path, expected in (('review.private.json', None), ('review.private.json', 'bad'), (None, 'f'*64)):
                with self.subTest(path=path, expected=expected), self.assertRaisesRegex(subject.evaluator.legacy.OdooFinalWorkerError, 'hash_bound_reference'):
                    subject.audit(plan_path='', plan_sha='', worker_dir='', run_dir='', source_review_path=path, source_review_sha=expected)


if __name__ == '__main__': unittest.main()
