"""Synthetic evidence tests only; no native/provider execution or task bodies."""
import copy
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_evaluator_v1 as subject


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    return {'path': str(path), 'sha256': subject.digest(raw)}


class TrialEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binding = subject.source_binding()
        reference = subject.reference.reference_binding()
        rows = []
        for family in subject.FAMILIES:
            for index in range(25):
                name = f'SYNTHETIC-{family}-{index}'
                rows.append({'task_id': name, 'family': family, 'source_label': name+'.pdf',
                    **{key: subject.digest((name+key).encode()) for key in
                       ('package_sha256', 'source_asset_sha256', 'task_binding_sha256', 'visible_instruction_sha256')}})
        original = {'schema': 'odoo-native-reference-qualification-plan-v3', 'reference_binding': reference,
                    'native_core_plan': {'split': 'official_hidden', 'task_count': 100, 'tasks': rows,
                                        'native_worker_binding_sha256': self.binding['native_binding_sha256']}}
        original_ref = save(self.root/'original.private.json', original)
        seed = 'synthetic-fixed-seed'
        selected = []
        for family in subject.FAMILIES:
            selected.extend(sorted((row for row in rows if row['family'] == family), key=lambda row:
                subject.digest((seed+'\0'+row['task_id']+'\0'+row['package_sha256']).encode()))[:5])
        self.plan = {'schema': 'envloop-single-environment-twenty-task-trial-v1', 'cell_id': subject.CELL,
                    'study_type': 'single_environment_development_trial', 'original_candidate_count': 100,
                    'final_task_count': 20, 'selection_task_count': 20, 'train_task_count': 20,
                    'models': {'teacher': 'gpt-6-sol', 'initial_researcher': 'gpt-6-sol', 'student': subject.MODEL},
                    'actor_limits': self.binding['actor_limits'], 'native_binding_sha256': self.binding['native_binding_sha256'],
                    'reference_binding_sha256': self.binding['reference_binding_sha256'], 'formal_large_study_credit': 0,
                    'full_six_environment_publication_claim': False, 'sampling_uses_model_outcomes': False,
                    'unknown_billing_is_null': True, 'original_verifier_and_reset_required': True,
                    'base_and_selected_checkpoint_same_final_tasks_required': True,
                    'checkpoint_selection_before_final_outcomes_required': True, 'original_candidate_plan_ref': original_ref,
                    'sampling_seed': seed, 'family_counts': {family: 5 for family in subject.FAMILIES},
                    'final_tasks_metadata': selected}

    def check(self, plan=None):
        ref = save(self.root/'plan.private.json', self.plan if plan is None else plan)
        return subject.checked_trial(ref['path'], ref['sha256'])

    def test_metadata_preflight_preserves_hundred_and_does_not_open_bodies(self):
        original_read = subject.private
        paths = []
        def read(path):
            paths.append(str(path))
            self.assertNotIn('partition_cases', str(path))
            self.assertNotIn('gold', str(path))
            return original_read(path)
        with patch.object(subject, 'private', side_effect=read):
            plan, candidates = self.check()
        self.assertEqual((len(plan['final_tasks_metadata']), len(candidates)), (20, 100))
        self.assertEqual(subject.source_binding()['native_binding_sha256'], self.plan['native_binding_sha256'])

    def test_wrong_count_source_full_authority_and_sampling_are_rejected(self):
        changes = [('final_task_count', 100), ('cell_id', 'magento'), ('formal_large_study_credit', 1),
                   ('full_six_environment_publication_claim', True), ('sampling_uses_model_outcomes', True),
                   ('native_binding_sha256', '0'*64), ('reference_binding_sha256', '0'*64),
                   ('original_candidate_count', 20), ('schema', 'cua-full-study-final-plan-v1')]
        for key, value in changes:
            with self.subTest(key=key):
                plan = copy.deepcopy(self.plan)
                plan[key] = value
                with self.assertRaises(subject.legacy.OdooFinalWorkerError):
                    self.check(plan)

    def test_changed_duplicate_reordered_or_foreign_twenty_are_rejected(self):
        for mutation in ('duplicate', 'reorder', 'package', 'foreign', 'family', 'nineteen'):
            with self.subTest(mutation=mutation):
                plan = copy.deepcopy(self.plan)
                rows = plan['final_tasks_metadata']
                if mutation == 'duplicate': rows[1] = copy.deepcopy(rows[0])
                if mutation == 'reorder': rows[0], rows[1] = rows[1], rows[0]
                if mutation == 'package': rows[0]['package_sha256'] = '0'*64
                if mutation == 'foreign': rows[0]['task_id'] = 'SYNTHETIC-foreign'
                if mutation == 'family': rows[0]['family'] = 'sales'
                if mutation == 'nineteen': rows.pop()
                with self.assertRaises(subject.legacy.OdooFinalWorkerError): self.check(plan)

    def test_model_epoch_must_match_while_student_remains_qwen(self):
        plan = copy.deepcopy(self.plan)
        plan['models']['teacher'] = 'gpt-6.1-sol'
        with self.assertRaises(subject.legacy.OdooFinalWorkerError): self.check(plan)
        plan['models']['initial_researcher'] = 'gpt-6.1-sol'
        self.assertEqual(self.check(plan)[0]['models']['teacher'], 'gpt-6.1-sol')
        plan['models']['student'] = 'wrong-student'
        with self.assertRaises(subject.legacy.OdooFinalWorkerError): self.check(plan)

    def selection_fixture(self):
        audits = []
        selection = SimpleNamespace(campaign=SimpleNamespace(TINKER_PATH=re.compile(r'tinker://[^ ]+')),
            vision_digest=lambda value: subject.digest(json.dumps(value).encode()),
            _audit_task_artifacts=lambda episode, task, row: audits.append(task['task_id']))
        checkpoint = 'tinker://SYNTHETIC/sampler_weights/checkpoint'
        manifest = []
        entries = []
        for index in range(20):
            task = {'task_id': f'SYNTHETIC-SEL-{index}', 'package_sha256': subject.digest(str(index).encode())}
            manifest.append(task)
            episode = self.root/f'selection-{index}'
            episode.mkdir(mode=0o700)
            life = save(episode/'life.private.json', {'saved_readback_reset_and_provider_close_complete': True,
                'started_monotonic': 1, 'ended_monotonic': 4})
            close = save(episode/'close.private.json', {'status': 'acknowledged', 'real_close_call_returned': True})
            clock = save(episode/'clock.private.json', {'native_actions_after_deadline': 0,
                'evaluation_outside_actor_clock': True, 'actor_elapsed_seconds': 3})
            relative = lambda ref: {'path': Path(ref['path']).name, 'sha256': ref['sha256']}
            row = save(episode/'row.private.json', {**task, 'score': index%2,
                'owned_complete_lifecycle_ref': relative(life), 'provider_close_ref': relative(close),
                'actor_clock_ref': relative(clock)})
            setup = save(episode/'setup.private.json', {'status': 'ready', 'actual_backend_identity': {
                'sampling_kind': 'checkpoint', 'checkpoint_sha256': selection.vision_digest(checkpoint)}})
            entries.append({'task': task, 'episode_root': str(episode), 'native_row': relative(row),
                            'paid_setup_result': relative(setup)})
        freeze = {'schema': 'envloop-odoo20-selection-checkpoint-freeze-v1', 'trial_plan_sha256': 'a'*64,
            'evaluator_source_sha256': 'b'*64, 'checkpoint_path': checkpoint, 'checkpoint_sha256': subject.digest(checkpoint.encode()),
            'model': subject.MODEL, 'selection_split': 'selection', 'selection_tasks': entries,
            'checkpoint_frozen_before_final_outcomes': True, 'hidden_final_outcomes_used': False, 'formal_large_study_credit': 0}
        return freeze, manifest, selection, audits

    def check_selection(self, freeze, manifest, selection):
        ref = save(self.root/'freeze.private.json', freeze)
        return subject.checked_selection_freeze(ref, plan_sha='a'*64, source_sha='b'*64,
                                               selection_manifest=manifest, selection=selection)

    def test_selection_requires_all_twenty_raw_audits_and_actual_setup_identity(self):
        freeze, manifest, selection, audits = self.selection_fixture()
        self.check_selection(freeze, manifest, selection)
        self.assertEqual(len(audits), 20)
        setup = Path(freeze['selection_tasks'][-1]['episode_root'])/'setup.private.json'
        changed = json.loads(setup.read_bytes())
        changed['actual_backend_identity']['sampling_kind'] = 'base'
        ref = save(setup, changed)
        freeze['selection_tasks'][-1]['paid_setup_result']['sha256'] = ref['sha256']
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'actual_checkpoint_setup'):
            self.check_selection(freeze, manifest, selection)

    def test_selection_rejects_hidden_tuning_incomplete_roster_and_cross_epoch(self):
        freeze, manifest, selection, _ = self.selection_fixture()
        changes = [('hidden_final_outcomes_used', True), ('checkpoint_frozen_before_final_outcomes', False),
                   ('trial_plan_sha256', '0'*64), ('checkpoint_sha256', '0'*64), ('formal_large_study_credit', 1),
                   ('selection_split', 'official_hidden'), ('schema', 'cua-full-study-selection-frozen-v1')]
        for key, value in changes:
            mutated = copy.deepcopy(freeze)
            mutated[key] = value
            with self.subTest(key=key), self.assertRaises(subject.legacy.OdooFinalWorkerError):
                self.check_selection(mutated, manifest, selection)
        freeze['selection_tasks'].pop()
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'full_twenty'):
            self.check_selection(freeze, manifest, selection)

    def test_unknown_selection_close_or_changed_artifact_is_rejected(self):
        freeze, manifest, selection, _ = self.selection_fixture()
        episode = Path(freeze['selection_tasks'][0]['episode_root'])
        close = json.loads((episode/'close.private.json').read_bytes())
        close['real_close_call_returned'] = False
        ref = save(episode/'close.private.json', close)
        row = json.loads((episode/'row.private.json').read_bytes())
        row['provider_close_ref']['sha256'] = ref['sha256']
        row_ref = save(episode/'row.private.json', row)
        freeze['selection_tasks'][0]['native_row']['sha256'] = row_ref['sha256']
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'close_unproved'):
            self.check_selection(freeze, manifest, selection)

    def test_live_dispatch_is_explicit_and_cannot_accept_old_full_authority(self):
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'explicit_live'):
            subject.run(plan_path='', plan_sha='', native_binding_path='', native_binding_sha='',
                        selection_freeze_path='', selection_freeze_sha='', worker_dir='', output_root='',
                        root_review_path='', root_review_sha='', execute=False)
        binding = subject.workers.public_binding()
        with patch.object(subject, 'checked_trial', return_value=(self.plan, [])), \
             patch.object(subject.workers, 'private_json', side_effect=[binding,
                 {'schema': 'cua-full-study-final-root-review-v1', 'formal_admission_authorized': True}]), \
             patch.object(subject, 'run_owned_task') as native:
            with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'exact_development_root_review'):
                subject.run(plan_path='', plan_sha='a'*64, native_binding_path='', native_binding_sha='',
                    selection_freeze_path='', selection_freeze_sha='', worker_dir='', output_root='',
                    root_review_path='', root_review_sha='', execute=True)
            native.assert_not_called()

    def test_saved_score_reset_and_provider_close_are_rechecked(self):
        episode = self.root/'synthetic-final-episode'
        episode.mkdir(mode=0o700)
        task = {'task_id': 'SYNTHETIC-FINAL', 'package_sha256': 'a'*64}
        snapshot = {'value': 7}
        verdict = {'reward': 1.0, 'checks_passed': True, 'difference_codes': []}
        context = {'family': 'purchase', 'target': {}, 'baseline': {}, 'frozen_files': {}}
        proof = save(episode/'proof.private.json', {'observed': snapshot, 'physical_files': {},
            'attachment_paths': {}, 'verdict': verdict, 'context': context})
        relative = lambda ref: {'path': Path(ref['path']).name, 'sha256': ref['sha256']}
        save(episode/'saved-state.private.json', {'business_snapshot': snapshot})
        save(episode/'reset.private.json', {'pre_database_filestore_exact': True, 'post_database_filestore_exact': True})
        save(episode/'baseline-semantic.private.json', {'business_snapshot': {}})
        save(episode/'restored-semantic.private.json', {'business_snapshot': {}})
        save(episode/'usage.private.json', {'samples': [{'status': 'completed'}]})
        row = {'score': 1}
        evidence = {
            'actor_clock_ref': {'native_actions_after_deadline': 0, 'evaluation_outside_actor_clock': True, 'actor_elapsed_seconds': 3},
            'owned_complete_lifecycle_ref': {'saved_readback_reset_and_provider_close_complete': True,
                'started_monotonic': 1, 'ended_monotonic': 4},
            'provider_close_ref': {'status': 'acknowledged', 'real_close_call_returned': True}}
        for key, value in evidence.items(): row[key] = relative(save(episode/(key+'.private.json'), value))
        environment = SimpleNamespace(proofs=[relative(proof), relative(proof)], proof_context=context,
                                      runtime_receipt={'services_restored_to_initial_state': True})
        selection = SimpleNamespace(_audit_task_artifacts=lambda *_: None)
        metered = SimpleNamespace(calls=[{'kind': 'synthetic-fixture'}])
        def audit(): return subject.audit_saved_episode(episode, task, row, environment, selection, {}, self.root, metered)
        with patch.object(subject.workers, 'audit_readiness_receipt'), patch.object(subject.legacy, '_modules', return_value=[None]*4), \
             patch.object(subject.legacy, '_evaluate', return_value=verdict):
            self.assertEqual(audit()['score'], 1)
            row['score'] = 0
            with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'saved_score_changed'): audit()
            row['score'] = 1
            save(episode/'reset.private.json', {'pre_database_filestore_exact': True, 'post_database_filestore_exact': False})
            with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'exact_reset'): audit()
            save(episode/'reset.private.json', {'pre_database_filestore_exact': True, 'post_database_filestore_exact': True})
            changed = {**evidence['provider_close_ref'], 'real_close_call_returned': False}
            row['provider_close_ref'] = relative(save(episode/'provider_close_ref.private.json', changed))
            with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'close_unproved'): audit()


if __name__ == '__main__':
    unittest.main()
