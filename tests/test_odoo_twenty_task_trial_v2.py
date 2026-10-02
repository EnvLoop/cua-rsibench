"""V14 wrappers and final admission gate; synthetic metadata/evidence only."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_evaluator_v1 as old_evaluator
from enterprise_fallback.odoo18 import twenty_task_trial_evaluator_v2 as evaluator
from enterprise_fallback.odoo18 import twenty_task_trial_selection_v2 as selection
from enterprise_fallback.odoo18 import twenty_task_trial_controls_v2 as controls
from tests import test_odoo_twenty_task_trial_evaluator_v1 as fixtures


class V14TrialTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TrialEvaluatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        old = old_evaluator.read_ref(self.fixture.plan['original_candidate_plan_ref'])
        roster = {'schema': controls.qualification.core.ROSTER_SCHEMA, 'split': 'official_hidden',
            'tasks': old['native_core_plan']['tasks'],
            'checkpoint': {key: evaluator.digest(key.encode()) for key in controls.qualification.core.CHECKPOINT_FILES}}
        self.original, _ = controls.qualification.prepare(roster)
        source = evaluator.source_binding()
        self.plan = copy.deepcopy(self.fixture.plan)
        self.plan.update(native_binding_sha256=source['native_binding_sha256'],
            reference_binding_sha256=source['reference_binding_sha256'],
            original_candidate_plan_ref=fixtures.save(self.root/'native14-hundred.private.json', self.original))
        self.plan_ref = fixtures.save(self.root/'native14-trial.private.json', self.plan)
        self.control_plan, _ = controls.prepare(trial_plan_path=self.plan_ref['path'], trial_plan_sha=self.plan_ref['sha256'])
        self.worker = self.root/'official_hidden'
        self.run_dir = self.worker/'private/v066_twenty_task_controls_v2'/self.control_plan['fresh_run_directory_name']

    def test_v1_source_pins_and_historical_namespace_are_preserved(self):
        for subject in (evaluator, selection, controls):
            path = evaluator.ROOT/subject._PARENT
            self.assertEqual(evaluator.digest(path.read_bytes()), subject._PARENT_SHA)
        self.assertEqual(old_evaluator.workers.public_binding()['profile'], 'native-owned-surface-safety-envelope-v13')
        self.assertEqual(evaluator.workers.public_binding()['profile'], 'native-owned-surface-safety-envelope-v14')
        self.assertNotEqual(old_evaluator.source_binding()['native_binding_sha256'], evaluator.source_binding()['native_binding_sha256'])

    def test_metadata_preflight_current_native14_reference4_and_exact20_preserves100(self):
        with patch.object(controls._impl, 'source_asset', side_effect=AssertionError('hidden-body read')):
            plan, candidates = evaluator.checked_trial(self.plan_ref['path'], self.plan_ref['sha256'])
            controls.validate_plan(self.control_plan)
        self.assertEqual((len(plan['final_tasks_metadata']), len(candidates)), (20, 100))
        self.assertEqual(self.control_plan['schema'], 'envloop-odoo20-native-control-plan-v2')
        self.assertEqual(self.control_plan['native_core_plan']['physical_dispatch_profile'], 'native-owned-surface-safety-envelope-v14')
        self.assertEqual(self.control_plan['reference_binding']['schema'], 'odoo-native-viewport-reference-source-v4')

    def test_prior_native13_plan_wrong_reference_or_model_epoch_cannot_enter(self):
        old_ref = fixtures.save(self.root/'old-plan.private.json', self.fixture.plan)
        with self.assertRaises(evaluator.legacy.OdooFinalWorkerError): evaluator.checked_trial(old_ref['path'], old_ref['sha256'])
        for field, value in (('reference_binding_sha256', '0'*64), ('native_binding_sha256', '0'*64),
                             ('models', {'initial_researcher': 'gpt-6-astra', 'teacher': 'gpt-6-astra', 'student': evaluator.MODEL})):
            plan = copy.deepcopy(self.plan); plan[field] = value
            ref = fixtures.save(self.root/'bad-plan.private.json', plan)
            with self.subTest(field=field), self.assertRaises(evaluator.legacy.OdooFinalWorkerError):
                evaluator.checked_trial(ref['path'], ref['sha256'])

    def test_control_v1_or_shrunken_world_or_prior_nonce_is_not_qualified(self):
        for mutation in ('v1', 'shrink', 'old_nonce', 'credit'):
            plan = copy.deepcopy(self.control_plan)
            if mutation == 'v1': plan['schema'] = 'envloop-odoo20-native-control-plan-v1'
            if mutation == 'shrink': plan['native_core_plan']['task_count'] = 20
            if mutation == 'old_nonce':
                plan['native_core_plan'] = self.original['native_core_plan']
                plan['fresh_run_directory_name'] = 'odoo20-controls-'+plan['native_core_plan']['run_nonce_hex']
            if mutation == 'credit': plan['official_final_tasks_admitted'] = 100
            with self.subTest(mutation=mutation), self.assertRaises(evaluator.legacy.OdooFinalWorkerError): controls.validate_plan(plan)

    def descriptor_fixture(self):
        plan_ref = fixtures.save(self.root/'controls-plan.private.json', self.control_plan)
        derived = {'schema': 'envloop-odoo20-native-controls-audit-v2', 'status': controls.VERIFIED,
            'trial_plan_sha256': self.plan_ref['sha256'], 'native_binding_sha256': self.plan['native_binding_sha256'],
            'reference_binding_sha256': self.plan['reference_binding_sha256'], 'control_count': 20, 'original_world_count': 100,
            'source_visual_review_pending': False, 'model_calls': 0, 'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0,
            'rows': [{'task_id': row['task_id'], 'package_sha256': row['package_sha256'], 'family': row['family'],
                      'independent_scores': [0, 1, 0], 'source_visual_review_verified': True} for row in self.plan['final_tasks_metadata']]}
        audit_ref = fixtures.save(self.root/'controls-audit.private.json', derived)
        review_ref = fixtures.save(self.root/'independent-review.private.json', {'schema': 'SYNTHETIC-FIXTURE-REVIEW'})
        descriptor = {'schema': 'envloop-odoo20-final-controls-descriptor-v2', 'trial_plan_sha256': self.plan_ref['sha256'],
            'control_plan_ref': plan_ref, 'control_audit_ref': audit_ref, 'source_review_ref': review_ref,
            'worker_dir': str(self.worker), 'run_dir': str(self.run_dir), 'formal_large_study_credit': 0}
        return descriptor, derived

    def check(self, descriptor, derived):
        ref = fixtures.save(self.root/'descriptor.private.json', descriptor)
        with patch.object(controls, 'audit', return_value=derived) as replay:
            checked = evaluator.checked_final_controls(ref, plan_path=self.plan_ref['path'], plan_sha=self.plan_ref['sha256'], worker_dir=self.worker)
            replay.assert_called_once_with(plan_path=descriptor['control_plan_ref']['path'], plan_sha=descriptor['control_plan_ref']['sha256'],
                worker_dir=str(self.worker), run_dir=str(self.run_dir), source_review_path=descriptor['source_review_ref']['path'],
                source_review_sha=descriptor['source_review_ref']['sha256'])
        return checked

    def test_all20_are_independently_replayed_and_source_review_hash_is_consumed(self):
        descriptor, derived = self.descriptor_fixture()
        self.assertEqual(self.check(descriptor, derived), descriptor)

    def test_pending_typed_verified_nineteen_wrong_scores_or_unreviewed_fail(self):
        descriptor, baseline = self.descriptor_fixture()
        for kind in ('pending', 'nineteen', 'wrong_score', 'unreviewed', 'duplicate', 'native13', 'formal_credit'):
            derived = copy.deepcopy(baseline)
            if kind == 'pending': derived['status'] = controls.PENDING
            if kind == 'nineteen': derived['rows'].pop(); derived['control_count'] = 19
            if kind == 'wrong_score': derived['rows'][0]['independent_scores'] = [0, 1, 1]
            if kind == 'unreviewed': derived['rows'][0]['source_visual_review_verified'] = False
            if kind == 'duplicate': derived['rows'][1] = derived['rows'][0]
            if kind == 'native13': derived['native_binding_sha256'] = old_evaluator.workers.public_binding()['binding_sha256']
            if kind == 'formal_credit': derived['official_final_tasks_admitted'] = 20
            mutated = copy.deepcopy(descriptor)
            mutated['control_audit_ref'] = fixtures.save(self.root/'controls-audit.private.json', derived)
            with self.subTest(kind=kind), self.assertRaisesRegex(evaluator.legacy.OdooFinalWorkerError, 'all_twenty_actual_controls'):
                self.check(mutated, derived)

    def test_corrupt_or_old_descriptor_cannot_authorize_paid_final_dispatch(self):
        descriptor, derived = self.descriptor_fixture()
        descriptor['schema'] = 'envloop-odoo20-final-controls-descriptor-v1'
        ref = fixtures.save(self.root/'bad-descriptor.private.json', descriptor)
        with patch.object(evaluator._impl, 'run') as final_dispatch:
            with self.assertRaisesRegex(evaluator.legacy.OdooFinalWorkerError, 'exact_final_control_descriptor'):
                evaluator.run(final_controls_descriptor_path=ref['path'], final_controls_descriptor_sha=ref['sha256'],
                    plan_path=self.plan_ref['path'], plan_sha=self.plan_ref['sha256'], worker_dir=self.worker, execute=True)
            final_dispatch.assert_not_called()
        descriptor['schema'] = 'envloop-odoo20-final-controls-descriptor-v2'
        ref = fixtures.save(self.root/'descriptor.private.json', descriptor)
        Path(descriptor['source_review_ref']['path']).write_text('{}')
        with self.assertRaisesRegex(evaluator.legacy.OdooFinalWorkerError, 'reference_changed'):
            evaluator.checked_final_controls(ref, plan_path=self.plan_ref['path'], plan_sha=self.plan_ref['sha256'], worker_dir=self.worker)

    def test_selection_uses_v14_native_roles_and_ref4_finalizer(self):
        self.assertEqual(selection.workers.public_binding()['binding_sha256'], evaluator.workers.public_binding()['binding_sha256'])
        self.assertTrue(selection.controls.SCHEMA.endswith('-v4'))
        source = selection.source_binding()
        self.assertEqual(source['schema'], 'envloop-odoo20-selection-source-v2')
        self.assertEqual(source['native_binding_sha256'], self.plan['native_binding_sha256'])
        self.assertIn('enterprise_fallback/odoo18/native_reference_split_finalizer_v4.py', source['source_sha256s'])


if __name__ == '__main__': unittest.main()
