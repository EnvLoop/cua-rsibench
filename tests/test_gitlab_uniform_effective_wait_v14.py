"""New neutral prerequisite and seven-role source closure; no native/provider."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_uniform_task_runtime_v14 as world,v066_uniform_model_workers_v14 as models,v066_neutral_telemetry_coldboot_v6 as cold

class EpochTests(unittest.TestCase):
 def test_old_neutral_proof_refuses_before_private_corpus_or_output(self):
  with tempfile.TemporaryDirectory() as folder:
   out=Path(folder)/'fresh'
   with patch.object(cold,'audit',return_value={'neutral_cycles_verified':3,'result_sha256':'a'*64}) as reader,patch.object(cold,'checked_plan') as plan:
    with self.assertRaisesRegex(ValueError,'new V6'):world.prepare(neutral_plan=Path('old'),neutral_permit=Path('permit'),out=out)
   reader.assert_called_once();plan.assert_not_called();self.assertFalse(out.exists())
 def test_old_task_epoch_refuses_before_neutral_native_proof(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'plan.private.json';world.write(path,{'schema':'envloop-gitlab-uniform-task-runtime-v13','private_root':folder})
   with patch.object(cold,'audit') as reader:
    with self.assertRaises(ValueError):world.checked_plan(path)
   reader.assert_not_called()
 def test_source_closure_and_seven_roles_cover_current_backend(self):
  binding=models.public_binding();names=set(binding['source_sha256s'])
  required={'gitlab_world/v066_effective_svwait_profile_v2.py','gitlab_world/v066_neutral_telemetry_coldboot_v6.py','gitlab_world/v066_uniform_task_runtime_v14.py','gitlab_world/v066_uniform_model_workers_v14.py','gitlab_world/v066_uniform_train_qualification_v14.py','gitlab_world/v066_uniform_reference_controls_v19.py','gitlab_world/v066_native_surface_adapter_v13.py'}
  self.assertTrue(required<=names)
  self.assertTrue(names<=set(cold.SOURCE_FILES),'Neutral must freeze the complete seven-role source closure')
  self.assertEqual(binding['uniform_guard_slots'],['base','selected-1','selected-2','selected-3','selected-4','teacher','control'])
  self.assertTrue(binding['uniform_backend_for_all_slots']);self.assertFalse(binding['old_cohort_backend_fallback']);self.assertEqual(binding['old_task_control_credit'],0)
  self.assertIs(world.TaskWorld.__init__.__kwdefaults__['backend_factory'],cold.NativeBackend)
  self.assertEqual(binding['matched_actor_budget']['max_actions'],90);self.assertEqual(binding['matched_actor_budget']['wall_seconds'],720)
 def test_adapter_policy_did_not_change_for_runtime_wait_fix(self):
  self.assertEqual(models.safety.__name__,'gitlab_world.v066_native_surface_adapter_v13')
  self.assertEqual(models.world.SCHEMA,'envloop-gitlab-uniform-task-runtime-v14')
 def test_neutral_v5_result_cannot_gain_new_effective_wait_credit(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'plan.private.json';cold.source.write_new(path,{'schema':'envloop-gitlab-neutral-telemetry-coldboot-plan-v5','evaluator_root':folder})
   with self.assertRaises(ValueError):cold.checked_plan(path)

if __name__=='__main__':unittest.main()
