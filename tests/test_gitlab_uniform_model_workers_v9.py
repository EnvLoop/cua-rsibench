"""All factory source signatures include the shared runtime and guard."""
import unittest
from unittest.mock import patch
from gitlab_world import v066_uniform_model_workers_v9 as workers

class BindingTests(unittest.TestCase):
 def test_rejected_finish_is_not_finished_without_changing_action(self):
  teacher=workers._loop(workers._TeacherLoop);student=workers._loop(workers._StudentLoop)
  self.assertIn('active.finished',workers.inspect.getsource(workers._loop))
  self.assertEqual(teacher.__name__,workers._TeacherLoop.__name__);self.assertEqual(student.__name__,workers._StudentLoop.__name__)
 def test_source_scope_updates_same_runtime_for_all_slots_and_restores(self):
  before=workers.teacher.RUNTIME_FILES;student_before=workers.selection.RUNTIME_FILES
  with workers.source_scope():
   self.assertIn('gitlab_world/v066_uniform_task_runtime_v9.py',workers.teacher.RUNTIME_FILES)
   self.assertIn('gitlab_world/v066_native_surface_adapter_v9.py',workers.selection.RUNTIME_FILES)
   self.assertIs(workers.common.FullGitBackend,workers.FullGitBackend)
  self.assertEqual(workers.teacher.RUNTIME_FILES,before);self.assertEqual(workers.selection.RUNTIME_FILES,student_before)

if __name__=='__main__':unittest.main()
