"""Successor source and all-role wiring; no native or provider execution."""
from contextlib import contextmanager
from hashlib import sha256
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from gitlab_world import v066_neutral_telemetry_coldboot_v7 as cold
from gitlab_world import v066_uniform_task_runtime_v15 as world
from gitlab_world import v066_uniform_model_workers_v15 as models
from gitlab_world import v066_uniform_train_qualification_v15 as train
from gitlab_world import v066_uniform_reference_controls_v20 as control
from gitlab_world import v066_uniform_model_workers_v14 as old_models
from gitlab_world import v066_uniform_task_runtime_v14 as old_world
from gitlab_world import v066_neutral_telemetry_coldboot_v5 as status

SLOTS = ['base', 'selected-1', 'selected-2', 'selected-3', 'selected-4', 'teacher', 'control']
PINS = {
    'gitlab_world/v066_neutral_telemetry_coldboot_v6.py': '8aa6ed16c6af41f7c22fda4a99acb3bc60f3e9783a3f3aed31668d32f0483608',
    'gitlab_world/v066_uniform_task_runtime_v14.py': '7bb7eea6732b060b3022eda7ebdb8c7063241526e2f31fcaf57049abdb0d239a',
    'gitlab_world/v066_uniform_model_workers_v14.py': '52aa8618fa7ea52edbe68a33cc15a05ef3e0da3b1ea152f6ebee15a3b2d3cb0f',
    'gitlab_world/v066_uniform_train_qualification_v14.py': 'cecdc452419162bc8530392944b812679ab191d9c111fc425a590b2dd95980a9',
    'gitlab_world/v066_uniform_reference_controls_v19.py': '70584a25b04281f05e01aabc9f2ba60fda4487eaf101f631f1df6638de8c9c66',
}


class SourceAndGateTests(unittest.TestCase):
    def test_exact_ancestors_remain_frozen(self):
        for name, expected in PINS.items():
            self.assertEqual(sha256(Path(name).read_bytes()).hexdigest(), expected)

    def test_same_complete_neutral_and_model_closure_all_seven_slots(self):
        binding = models.public_binding()
        self.assertEqual(binding['source_sha256s'], cold.source_hashes())
        self.assertEqual(world.source_hashes(), cold.source_hashes())
        self.assertTrue(set(cold.SUCCESSOR_ROOTS) <= set(binding['source_sha256s']))
        self.assertEqual(binding['uniform_guard_slots'], SLOTS)
        self.assertTrue(binding['uniform_backend_for_all_slots'])
        self.assertFalse(binding['old_cohort_backend_fallback'])
        self.assertEqual(binding['old_task_control_credit'], 0)
        self.assertEqual(binding['matched_actor_budget']['max_actions'], 90)
        self.assertEqual(binding['matched_actor_budget']['wall_seconds'], 720)
        self.assertIs(models.safety, old_models.safety)
        self.assertEqual(world.TaskWorld.__init__.__kwdefaults__['backend_factory'], cold.NativeBackend)

    def test_prior_whole_binding_refused(self):
        with self.assertRaisesRegex(ValueError, 'source_binding_changed'):
            models.validate_binding(old_models.public_binding())

    def test_prior_task_schema_refused_before_neutral_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'plan.private.json'
            world.write(path, {'schema': old_world.SCHEMA, 'private_root': folder})
            with patch.object(cold, 'audit') as audit:
                with self.assertRaises(ValueError):
                    world.checked_plan(path)
            audit.assert_not_called()

    def test_prior_neutral_success_cannot_prepare_task_or_read_corpus(self):
        proof = {'neutral_cycles_verified': 3, 'native_effective_wait_verified': True,
                 'effective_wait_seconds': 60, 'result_sha256': 'a' * 64}
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'new'
            with patch.object(cold, 'audit', return_value=proof), patch.object(cold, 'checked_plan') as read:
                with self.assertRaisesRegex(ValueError, 'Fresh V7 three-cycle'):
                    world.prepare(neutral_plan=Path('old'), neutral_permit=Path('permit'), out=out)
            self.assertFalse(out.exists())
            read.assert_not_called()

    def test_new_proof_requires_exact_three_cycles_current_closure_and_wait(self):
        proof = {'neutral_source_epoch': cold.SCHEMA, 'neutral_source_sha256s': cold.source_hashes(),
                 'neutral_cycles_verified': 3, 'native_effective_wait_verified': True,
                 'effective_wait_seconds': 60, 'old_neutral_v6_credit': 0}
        world._fresh_neutral(proof)
        for key, value in [('neutral_cycles_verified', 2), ('neutral_source_sha256s', {}),
                           ('native_effective_wait_verified', False), ('effective_wait_seconds', 59),
                           ('old_neutral_v6_credit', 1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                world._fresh_neutral(proof | {key: value})

    def test_prior_neutral_plan_is_refused_by_original_schema_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'plan.private.json'
            world.write(path, {'schema': 'envloop-gitlab-neutral-effective-svwait-coldboot-plan-v6',
                               'evaluator_root': folder})
            with self.assertRaises(ValueError):
                cold.checked_plan(path)

    def test_repaired_reset_globals_are_current_and_cleanup_once_without_adoption(self):
        self.assertIs(world.TaskWorld.reset.__globals__, world.__dict__)
        self.assertIs(world.TaskWorld.reset.__globals__['checked_plan'], world.checked_plan)
        self.assertIs(world.TaskWorld.reset.__globals__['cold'], cold)
        for owned in (True, False):
            for failure in (KeyboardInterrupt(), asyncio.CancelledError(), SystemExit(2)):
                calls = []
                backend = SimpleNamespace(owned_cycles=set())
                def boot(index):
                    calls.append(('boot', index))
                    if owned:
                        backend.owned_cycles.add(index)
                    raise failure
                def teardown(index):
                    self.assertIn(index, backend.owned_cycles)
                    calls.append(('teardown', index))
                    backend.owned_cycles.remove(index)
                backend.boot, backend.teardown = boot, teardown
                instance = world.TaskWorld(Path('plan'), Path('permit'), Path('output'), phase='full-study')
                instance.backend = backend
                with self.assertRaises(type(failure)) as caught:
                    instance.reset()
                self.assertIs(caught.exception, failure)
                self.assertEqual(calls, [('boot', 0)] + ([('teardown', 0)] if owned else []))
                self.assertIsNone(instance.active_index)
                self.assertEqual(instance.generation, 0)


class FactoryAndScopeTests(unittest.TestCase):
    def assert_current(self):
        self.assertIs(models.common.FullGitBackend, models.FullGitBackend)
        self.assertIs(models.common.public_binding, models.public_binding)
        self.assertIs(models.world, world)
        self.assertTrue(set(cold.SUCCESSOR_ROOTS) <= set(models.teacher.RUNTIME_FILES))
        self.assertTrue(set(cold.SUCCESSOR_ROOTS) <= set(models.selection.RUNTIME_FILES))

    def test_scope_restores_ancestor_modules_after_nested_error(self):
        previous = (models.common.FullGitBackend, models.common.public_binding,
                    models.teacher.RUNTIME_FILES, models.selection.RUNTIME_FILES,
                    models.teacher.GitLabTrainEpisodeWorker.run_episode,
                    models.selection.GitLabSelectionWorker._task_episode)
        with self.assertRaisesRegex(RuntimeError, 'deliberate'):
            with models.source_scope():
                self.assert_current()
                with models.source_scope():
                    self.assert_current()
                    raise RuntimeError('deliberate')
        after = (models.common.FullGitBackend, models.common.public_binding,
                 models.teacher.RUNTIME_FILES, models.selection.RUNTIME_FILES,
                 models.teacher.GitLabTrainEpisodeWorker.run_episode,
                 models.selection.GitLabSelectionWorker._task_episode)
        self.assertEqual(previous, after)

    def test_teacher_and_each_selected_factory_keep_source_scope_on_later_calls(self):
        observed = []
        def teacher_factory(**kwargs):
            self.assert_current()
            def episode(**fields):
                self.assert_current()
                observed.append('teacher')
            return SimpleNamespace(run_episode=episode)
        def student_factory(**kwargs):
            self.assert_current()
            def call(**fields):
                self.assert_current()
                observed.append(kwargs['slot'])
            def frozen(session, started):
                self.assert_current()
            return SimpleNamespace(run_attempt=call, _task_episode=call, _require_frozen=frozen)
        with patch.object(models, '_TrainFactory', teacher_factory), patch.object(models, '_SelectionFactory', student_factory):
            teacher = models.train_worker()
            teacher.run_episode()
            for slot in SLOTS[1:5]:
                worker = models.selection_worker(slot=slot)
                worker.run_attempt()
                worker._task_episode()
                worker._require_frozen(None, None)
        self.assertEqual(observed, ['teacher', *[slot for slot in SLOTS[1:5] for _ in range(2)]])

    def test_shared_base_factory_uses_current_selection_and_scope(self):
        from gitlab_world import full_git_shared_base_execution_v1 as shared
        def dispatch(study, reconciler, **kwargs):
            self.assert_current()
            self.assertIs(models.common.selection_worker, models.selection_worker)
            return 'base-current'
        with patch.object(shared, 'run_gitlab_shared_base', dispatch):
            self.assertEqual(models.run_gitlab_shared_base(None, None), 'base-current')

    def test_train_and_control_functions_bind_successor_modules(self):
        for module in (train, control):
            self.assertIs(module.world, world)
            self.assertIs(module.models, models)
            self.assertIs(module.run.__globals__, module.__dict__)
        self.assertFalse(train.run.__kwdefaults__['execute'])
        self.assertFalse(control.run.__kwdefaults__['execute'])
        self.assertEqual(control.run.__kwdefaults__['maximum'], 100)
        self.assertEqual(control.run.__kwdefaults__['first_index'], 0)

    def test_each_role_backend_open_constructs_same_current_task_world(self):
        calls = []
        @contextmanager
        def task_open():
            yield
        def task_factory(plan, permit, artifacts, *, phase):
            calls.append((plan, permit, phase))
            return SimpleNamespace(open=task_open)
        @contextmanager
        def original_open(identity):
            yield SimpleNamespace()
        wrapper = SimpleNamespace(retain_before_reset=lambda failure: None)
        guard = SimpleNamespace(bind=lambda: None, close=lambda: None)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'artifacts').mkdir(mode=0o700)
            receipt = root / 'operator.private.json'
            world.write(receipt, {'identities': {'train': {'user_id': 7}}})
            with patch.object(world, 'TaskWorld', side_effect=task_factory), \
                 patch.object(models.operators, 'RECEIPT', receipt), \
                 patch.object(models.safety, 'NativeGuard', return_value=guard), \
                 patch.object(models.safety, 'GuardedSession', side_effect=lambda active, gate: active), \
                 patch.object(models.common, 'FullGitSession', return_value=wrapper):
                for role in SLOTS:
                    backend = models.FullGitBackend.__new__(models.FullGitBackend)
                    backend.binding = models.public_binding()
                    backend.plan_path, backend.permit_path = root / 'plan', root / 'permit'
                    backend.output_root, backend.phase, backend.partition = root, 'full-study', 'train'
                    backend.cohort_source_file_sha256 = 'a' * 64
                    backend.backend = SimpleNamespace(open=original_open)
                    with backend.open({'test_role': role}) as active:
                        self.assertIs(active, wrapper)
            self.assertEqual(calls, [(root / 'plan', root / 'permit', 'full-study')] * 7)

    def test_actual_final_run_once_maintains_scope_for_late_calls_and_errors(self):
        def original(instance, command, output_dir):
            self.assert_current()
            raise RuntimeError('final operation error')
        before = models.common.FullGitBackend
        final = models.GitLabUniformFinalWorker.__new__(models.GitLabUniformFinalWorker)
        with patch.object(models.final_worker.GitLabFullGitFinalWorker, 'run_once', original):
            with self.assertRaisesRegex(RuntimeError, 'final operation error'):
                final.run_once({}, Path('no-execution'))
        self.assertIs(models.common.FullGitBackend, before)

    def test_actual_final_common_binding_imports_successor_and_refuses_old_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'binding.private.json'
            world.write(path, models.public_binding())
            final = models.GitLabUniformFinalWorker.__new__(models.GitLabUniformFinalWorker)
            final.binding_path = path
            final.binding_file_sha256 = sha256(path.read_bytes()).hexdigest()
            common, binding = final._common_binding()
            self.assertIs(common, models)
            self.assertEqual(binding, models.public_binding())
            old = Path(folder) / 'old.private.json'
            world.write(old, old_models.public_binding())
            final.binding_path = old
            final.binding_file_sha256 = sha256(old.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'whole_proof_binding_changed'):
                final._common_binding()

    def test_neutral_scope_reuses_strict_status_decoder_and_restores(self):
        previous = status.previous.status_semantics
        with cold.version_scope():
            self.assertIs(status.previous.status_semantics, status.status_semantics)
        self.assertIs(status.previous.status_semantics, previous)


if __name__ == '__main__':
    unittest.main()
