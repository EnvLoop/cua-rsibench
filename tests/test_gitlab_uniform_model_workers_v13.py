"""All factory source signatures include the shared runtime and guard."""
import unittest
from unittest.mock import patch
from gitlab_world import v066_uniform_model_workers_v13 as workers

class BindingTests(unittest.TestCase):
 def test_rejected_finish_is_not_finished_without_changing_action(self):
  teacher=workers._loop(workers._TeacherLoop);student=workers._loop(workers._StudentLoop)
  self.assertIn('active.finished',workers.inspect.getsource(workers._loop))
  self.assertEqual(teacher.__name__,workers._TeacherLoop.__name__);self.assertEqual(student.__name__,workers._StudentLoop.__name__)
 def test_source_scope_updates_same_runtime_for_all_slots_and_restores(self):
  before=workers.teacher.RUNTIME_FILES;student_before=workers.selection.RUNTIME_FILES
  with workers.source_scope():
   self.assertIn('gitlab_world/v066_uniform_task_runtime_v13.py',workers.teacher.RUNTIME_FILES)
   self.assertIn('gitlab_world/v066_native_surface_adapter_v13.py',workers.selection.RUNTIME_FILES)
   self.assertIs(workers.common.FullGitBackend,workers.FullGitBackend)
  self.assertEqual(workers.teacher.RUNTIME_FILES,before);self.assertEqual(workers.selection.RUNTIME_FILES,student_before)

if __name__=='__main__':unittest.main()

class FreshEpochTests(unittest.TestCase):
 def test_all_seven_slots_bind_same_v13_guard_source_and_old_binding_refuses(self):
  from gitlab_world import v066_uniform_model_workers_v12 as old
  value=workers.public_binding()
  self.assertEqual(value['uniform_guard_slots'],['base','selected-1','selected-2','selected-3','selected-4','teacher','control'])
  self.assertEqual(value['native_guard_module'],'gitlab_world.v066_native_surface_adapter_v13')
  self.assertEqual(value['old_task_control_credit'],0)
  self.assertIn('gitlab_world/v066_uniform_reference_controls_v18.py',workers.world.source_hashes())
  with self.assertRaises(ValueError):workers.validate_binding(old.public_binding())
 def test_factories_retain_same_v13_runtime_and_all_live_acceptance_flags_are_external(self):
  self.assertIs(workers.safety, __import__('gitlab_world.v066_native_surface_adapter_v13',fromlist=['NativeGuard']))
  self.assertIs(workers.world,__import__('gitlab_world.v066_uniform_task_runtime_v13',fromlist=['TaskWorld']))
  self.assertNotEqual(workers.world.SCHEMA,'envloop-gitlab-uniform-task-runtime-v12')
  self.assertTrue(callable(workers.train_worker));self.assertTrue(callable(workers.selection_worker))
  self.assertTrue(callable(workers.final_worker_factory));self.assertTrue(callable(workers.run_gitlab_shared_base))
