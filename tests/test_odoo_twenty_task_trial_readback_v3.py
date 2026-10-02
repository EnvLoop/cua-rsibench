"""Typed native reference validation and immutable V3 migration; no paid work."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_readback_v3 as subject
from enterprise_fallback.odoo18 import twenty_task_trial_evaluator_v2 as old_evaluator
from enterprise_fallback.odoo18 import twenty_task_trial_evaluator_v3 as evaluator
from enterprise_fallback.odoo18 import twenty_task_trial_selection_v3 as selection


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root/'clock.private.json'
        self.path.write_text(json.dumps({'schema': 'odoo-actual-actor-clock-v1', 'actor_elapsed_seconds': 9}))
        self.path.chmod(0o600)
        self.ref = subject.typed_reference(self.root, 'clock.private.json', 'native_observation_envelope')

    def test_full_typed_metadata_reopened_by_original_native_verifier(self):
        self.assertEqual(set(self.ref), {'schema', 'path', 'sha256', 'size', 'kind'})
        with patch.object(subject.workers, 'native_ref_bytes', wraps=subject.workers.native_ref_bytes) as checked:
            value = subject.read_ref(self.root, self.ref)
            checked.assert_called_once_with(self.root, self.ref)
        self.assertEqual(value['actor_elapsed_seconds'], 9)

    def test_schema_kind_size_hash_paths_and_private_modes_remain_strict(self):
        for key, value in [('schema', 'wrong'), ('kind', 'dispatch_receipt'), ('size', self.ref['size']+1),
                           ('sha256', '0'*64), ('path', '../clock.private.json')]:
            changed = {**self.ref, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError): subject.read_ref(self.root, changed)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError): subject.read_ref(self.root, self.ref)

    def test_simple_refs_work_and_no_extra_metadata_can_be_silently_discarded(self):
        simple = {key: self.ref[key] for key in ('path', 'sha256')}
        self.assertEqual(subject.read_ref(self.root, simple)['actor_elapsed_seconds'], 9)
        with self.assertRaisesRegex(ValueError, 'exact_reference'):
            subject.read_ref(self.root, {**simple, 'ignored_field': True})

    def test_absolute_metadata_reader_and_relative_typed_reader_are_distinct(self):
        absolute = {'path': str(self.path), 'sha256': self.ref['sha256']}
        self.assertEqual(evaluator.read_ref(absolute)['actor_elapsed_seconds'], 9)
        self.assertEqual(evaluator._impl._ref(self.root, self.ref)['actor_elapsed_seconds'], 9)

    def test_v2_namespaces_and_native14_actor_source_do_not_change(self):
        self.assertIsNot(old_evaluator._impl, evaluator._impl)
        self.assertIsNot(old_evaluator._impl._ref, evaluator._impl._ref)
        self.assertEqual(old_evaluator.workers.public_binding()['binding_sha256'], evaluator.workers.public_binding()['binding_sha256'])
        self.assertEqual(evaluator.source_binding()['schema'], 'envloop-odoo20-evaluator-source-v3')
        self.assertEqual(selection.source_binding()['schema'], 'envloop-odoo20-selection-source-v3')
        for module in (evaluator, selection):
            self.assertEqual(subject.digest((evaluator.ROOT/module._PARENT).read_bytes()), module._PARENT_SHA)

    def test_missing_import_review_or_partial_import_pointer_cannot_resume(self):
        with self.assertRaisesRegex(ValueError, 'optional_saved_case_import'):
            selection.run(saved_case_import_path='somewhere', execute=False)
        with patch.object(selection._impl, 'run_owned_task') as actor:
            with self.assertRaisesRegex(ValueError, 'explicit_selection_dispatch'):
                selection.run(plan_path='', plan_sha='', native_binding_path='', native_binding_sha='',
                    train_control_path='', train_control_sha='', selection_control_path='', selection_control_sha='',
                    local_cost_authority_path='', local_cost_authority_sha='', worker_dir='', checkpoint_path='',
                    output_root='', root_review_path='', root_review_sha='', execute=False)
            actor.assert_not_called()

    def test_import_needs_exact_root_review_and_same_sampling_configuration(self):
        task = {'task_id': 'SYNTHETIC-SEL-0', 'package_sha256': 'a'*64}
        native = selection.workers.public_binding()
        value = {'schema': 'envloop-odoo20-saved-selection-case-import-candidate-v3',
            'status': 'saved_original_first_case_independently_replayed', 'trial_plan_sha256': 'b'*64,
            'native_binding_sha256': native['binding_sha256'], 'task': task, 'base_mode': True,
            'model': evaluator.MODEL, 'sampling_seed': 17, 'sample_max_tokens': 4096,
            'new_model_calls': 0, 'formal_large_study_credit': 0, 'same_request_replay_authorized': False}
        review = {'schema': 'envloop-odoo20-saved-case-import-root-review-v3', 'trial_plan_sha256': 'b'*64,
            'candidate_sha256': 'c'*64, 'native_binding_sha256': native['binding_sha256'],
            'same_actor_sampler_scorer_reset_verified': True, 'readback_reference_fix_only': True,
            'original_model_request_replay_authorized': False, 'original_first_case_import_authorized': True}
        with patch.object(selection._impl.evaluator, 'read_ref', return_value=value), \
             patch.object(selection.workers, 'private_json', return_value={}), \
             patch.object(selection.workers, '_model_modules') as model:
            with self.assertRaisesRegex(ValueError, 'explicit_saved_case_import_review'):
                selection._import('/synthetic', 'c'*64, '/review', 'd'*64, [task], 'b'*64, True, evaluator.MODEL, 0, 4096)
            model.assert_not_called()
        with patch.object(selection._impl.evaluator, 'read_ref', return_value=value), \
             patch.object(selection.workers, 'private_json', return_value=review), \
             patch.object(selection.workers, '_model_modules') as model:
            with self.assertRaisesRegex(ValueError, 'same_original_first_case_model_metadata_budget'):
                selection._import('/synthetic', 'c'*64, '/review', 'd'*64, [task], 'b'*64, True, evaluator.MODEL, 0, 4096)
            model.assert_not_called()

    def test_zero_byte_journal_lock_can_mirror_but_empty_evidence_cannot(self):
        lock = self.root/'journal.lock'; lock.touch(mode=0o600)
        self.assertEqual(subject.mirror_bytes(lock), b'')
        empty = self.root/'clock-empty.private.json'; empty.touch(mode=0o600)
        with self.assertRaises(ValueError): subject.mirror_bytes(empty)

    def test_actual_saved_case_import_source_integration_without_dispatch(self):
        """Local optional fixture: actual90-call task and explicit root review."""
        stage = evaluator.ROOT/'work/odoo-twenty-task-trial-20261001.private'
        launch = stage/'selection-base-native14-readback-v3-02-supervision.private/launch-intent.private.json'
        if not launch.is_file(): self.skipTest('Actual private saved selection episode is unavailable')
        argv = json.loads(launch.read_bytes())['argv']
        arg = lambda name: argv[argv.index('--'+name)+1]
        plan, _ = evaluator.checked_trial(arg('plan-path'), arg('plan-sha'))
        manifest = selection.workers.private_json(Path(arg('worker-dir'))/'private/task_set_manifest.json')
        identities = [{key: row[key] for key in ('task_id', 'package_sha256')} for row in manifest['selection']]
        with patch.object(selection._impl, 'run_owned_task', side_effect=AssertionError('Native dispatch is forbidden')), \
             patch.object(selection._impl, 'sampler_class', side_effect=AssertionError('Provider setup is forbidden')):
            entries, scores = selection._import(arg('saved-case-import-path'), arg('saved-case-import-sha'),
                arg('saved-case-review-path'), arg('saved-case-review-sha'), identities, arg('plan-sha'), True,
                plan['models']['student'], int(arg('sampling-seed')), int(arg('sample-max-tokens')))
        self.assertEqual(len(entries), 1)
        self.assertEqual(scores, [{'task': identities[0], 'score': 0}])
        self.assertEqual(entries[0]['task']['task_id'], 'ELPO-SEL-0001')


if __name__ == '__main__': unittest.main()
