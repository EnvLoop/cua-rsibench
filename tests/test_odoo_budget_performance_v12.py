"""Actual original actor loop/guard/scorer/raw deadline; synthetic native/SDK."""
import json
from types import SimpleNamespace
import unittest
from tests import test_odoo_actor_loop_v12 as fixture
from enterprise_fallback.odoo18 import native_surface_final_worker_v1 as legacy_final
from enterprise_fallback.odoo18 import native_surface_budget_performance_v12 as reader
from enterprise_fallback.odoo18.odoo_actor_model_modules_v1 import run_owned_task
from cursibench import full_study_final_dispatch_v1 as files


class BudgetPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ActorLoopTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_actual_budget_stop_saved_reset_close_and_readonly_rederivation(self):
        command,out=self.f.command()
        with self.f.production_fixture(command,budget_unknown=True) as (events,_business):
            instance=self.f.factory(True);self.f.reserve(command)
            _teacher,selection=instance.workers._model_modules(instance.binding)
            environment=legacy_final.environment_factory(selection,instance.worker_dir,instance.identities,instance.binding)
            episode=out/'native-episode';episode.mkdir(mode=0o700)
            environment._native_readiness_sink=lambda value:legacy_final.write(episode,'db-readiness.private.json',value)
            identity={'task_id':command['task_id'],'package_sha256':command['package_sha256']}
            environment.load_command_task(identity,episode)
            sampler=selection.RealTinkerSelectionSampler(checkpoint_path='Qwen/Qwen3.8-27B',config={
                'seed':23,'sample_max_tokens':512},output_root=episode,attempt_id=command['attempt_id'],
                base_mode=True,expected_base_checkpoint_sha256=command['checkpoint_sha256'])
            # This is the actual parent final reservation, never a made-up
            # sample ledger entry. The provider journal retains unique IDs.
            sampler.parent_paid_attempt_id=command['attempt_id']
            row=run_owned_task(environment=environment,task=identity,index=0,sampler=sampler,
                task_dir=episode,attempt_id=command['attempt_id'])
            self.assertEqual(row['termination'],'task_wall_budget')
            self.assertIsNone(row['sampled_output_tokens'])
            self.assertEqual(row['score'],0)
            self.assertIn('provider_close_ack',events)
            self.assertNotIn('native_click_returned',events)
            amendment='f'*64
            refs={}
            refs['native_binding']=legacy_final.write(episode,'current-native-binding.private.json',instance.binding)
            refs['task']=legacy_final.write(episode,'task.private.json',{
                'attempt_id':command['attempt_id'],'task_id':command['task_id'],'package_sha256':command['package_sha256'],
                'owner_slot':command['owner_slot'],'checkpoint_sha256':command['checkpoint_sha256'],'amendment_sha256':amendment})
            refs['native_row']=legacy_final.write(episode,'native-row.private.json',row)
            refs['live_saved_proof']=environment.proofs[-1]
            refs['provider_close']=files.reference(episode,episode/'actor-clock/provider-close.private.json')
            refs['actor_clock']=files.reference(episode,episode/'actor-clock/end.private.json')
            refs['actor_budget_stop']=files.reference(episode,episode/'actor-clock/budget-stop.private.json')
            refs['lifecycle']={'path':row['owned_complete_lifecycle_ref']['path'],'sha256':row['owned_complete_lifecycle_ref']['sha256']}
            descriptor={'schema':'odoo-budget-performance-input-v12','cell_id':'odoo-community',
                'episode_root':str(episode),'sample_paid_attempt_id':command['attempt_id'],**refs}
            study=SimpleNamespace(repo_root=self.f.protocol.repo,amendment_sha256=amendment)
            verified=reader.verify_budget_performance(study=study,owner_slot='shared-base',verification=descriptor)
            self.assertEqual(verified['performance']['score'],0)
            self.assertFalse(verified['inference']['unknown_response_is_completed'])
            self.assertEqual(verified['inference']['status'],'completion_unknown_after_actor_deadline')
            self.assertEqual(set(verified['evidence_sha256']),{'saved-state.private.json','verifier.private.json',
                'reset.private.json','actor-clock.private.json','actor-budget-stop.private.json','task.private.json'})
            self.assertEqual(verified['inference']['completed_model_response_count'],0)
            self.assertIsNone(verified['billing']['actual_usd'])
            self.assertTrue(verified['provider_close_acknowledged'])
            self.assertFalse(verified['formal_registration_performed'])
            bad={**descriptor,'sample_paid_attempt_id':'invented-reservation'}
            with self.assertRaises(Exception):reader.verify_budget_performance(study=study,owner_slot='shared-base',verification=bad)
            with self.assertRaises(Exception):reader.verify_budget_performance(study=study,owner_slot='sol6',verification=descriptor)
            close_path=episode/'actor-clock/provider-close.private.json'
            original_close=close_path.read_bytes()
            close=json.loads(original_close);close['status']='uncertain';close_path.write_bytes(files.canonical(close))
            bad={**descriptor,'provider_close':files.reference(episode,close_path)}
            with self.assertRaises(Exception):reader.verify_budget_performance(study=study,owner_slot='shared-base',verification=bad)
            close_path.write_bytes(original_close)
            clock_path=episode/'actor-clock/end.private.json';original_clock=clock_path.read_bytes()
            clock=json.loads(original_clock);clock['native_actions_after_deadline']=1;clock_path.write_bytes(files.canonical(clock))
            bad={**descriptor,'actor_clock':files.reference(episode,clock_path)}
            with self.assertRaises(Exception):reader.verify_budget_performance(study=study,owner_slot='shared-base',verification=bad)
            clock_path.write_bytes(original_clock)
            (episode/'saved-state.private.json').write_bytes(b'{}')
            with self.assertRaises(Exception):reader.verify_budget_performance(study=study,owner_slot='shared-base',verification=descriptor)


if __name__=='__main__':unittest.main()
