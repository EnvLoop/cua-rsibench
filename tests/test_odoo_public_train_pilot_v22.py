"""Actual V13 loop with a public TRAIN bridge; no live native/provider calls."""
from contextlib import contextmanager
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from enterprise_fallback.odoo18 import native_public_train_pilot_v22 as source
from tests.test_odoo_native_final_v22_production import ProductionV22Tests,save
from tests.test_odoo_native_material_workers_v2 import fake_train_proof
from cursibench import full_study_runtime_v2 as formal
import factory


class PublicTrainTests(unittest.TestCase):
    def setUp(self):
        self.f=ProductionV22Tests('test_actual_unknown_deadline_saved_scored_reset_and_provider_close');self.f.setUp();self.addCleanup(self.f.doCleanups)
        previous=self.f.worker_dir;self.f.worker_dir=previous.with_name('train');previous.rename(self.f.worker_dir);self.f.private=self.f.worker_dir/'private'
        proof=fake_train_proof(self.f.binding);proof['schema']=source.workers.TRAIN_CONTROL_SCHEMA;proof['status']=source.workers.TRAIN_CONTROL_STATUS
        self.proof_path=self.f.protocol.work/'train-proof.private.json';self.proof_sha=save(self.proof_path,proof)
        self.owned=source.ROOT/'work'/('source-test-public-train-'+self.f.protocol.work.name)
        self.addCleanup(lambda:__import__('shutil').rmtree(self.owned,ignore_errors=True))
    def request(self,task):
        request={'schema':'odoo-public-train-model-pilot-request-v22','attempt_id':'public-train-source-fixture',
            'worker_dir':str(self.f.worker_dir),'output_root':str(self.owned),'native_binding':{'path':str(self.f.binding_path),'sha256':self.f.binding_sha},
            'train_control':{'path':str(self.proof_path),'sha256':self.proof_sha},'task':copy.deepcopy(task),
            'training_config':{'model':'Qwen/Qwen3.8-27B','seed':0,'sample_max_tokens':256},'source_binding_sha256':source.source_binding()['binding_sha256']}
        return request,{'schema':'odoo-public-train-model-pilot-root-review-v22','request_sha256':source.digest(source.legacy.final.canonical(request)),
            'source_binding_sha256':request['source_binding_sha256'],'one_public_train_paid_pilot_authorized':True,
            'formal_registration_authorized':False,'automatic_retry_authorized':False}
    @contextmanager
    def environment(self,**flags):
        command,_=self.f.command()
        with self.f.production_fixture(command,**flags) as details:
            world=json.loads((self.f.private/'partition_cases.json').read_bytes())
            world['cases']={family:rows[:5] for family,rows in world['cases'].items()}
            (self.f.private/'partition_cases.json').write_bytes(source.legacy.final.canonical(world))
            manifest=json.loads((self.f.private/'task_set_manifest.json').read_bytes())
            ids={case['id'] for rows in world['cases'].values() for case in rows}
            manifest['train']=[row for row in manifest['official'] if row['task_id'] in ids];manifest['official']=[]
            (self.f.private/'task_set_manifest.json').write_bytes(source.legacy.final.canonical(manifest))
            request,review=self.request({k:command[k] for k in ('task_id','package_sha256')})
            original_enter=self.f.selection.RealTinkerSelectionSampler.__enter__
            def entered(delegate):
                returned=original_enter(delegate);delegate.backend=__import__('types').SimpleNamespace(identity={'model':'Qwen/Qwen3.8-27B','sampling_kind':'base','checkpoint_sha256':source.digest(b'Qwen/Qwen3.8-27B')});return returned
            with patch.object(self.f.selection.RealTinkerSelectionSampler,'__enter__',entered),patch.object(factory,'local_config',return_value={'ODOO_PORT':'8069','ODOO_PROJECT':'source_fixture','ODOO_PARTITION':'train'}), \
                 patch.object(source,'sampler_class',side_effect=lambda selection:selection.RealTinkerSelectionSampler):
                yield request,review,details
    def test_constructor_metadata_only_no_final_gate_or_case_body(self):
        task={'task_id':'public-train-synthetic','package_sha256':'a'*64};request,review=self.request(task)
        with patch.object(source,'modules',side_effect=AssertionError('native')),patch.object(formal,'FinalGate',side_effect=AssertionError('fake600')):
            instance=source.PublicTrainPilot(request,review)
        self.assertFalse(self.owned.exists())
        with self.assertRaisesRegex(ValueError,'explicit_live'):instance.run_once()
        for key,value in [('source_binding_sha256','0'*64),('task',{'task_id':'bad','package_sha256':'bad'}),('training_config',{'model':'wrong'})]:
            bad={**request,key:value};bad_review={**review,'request_sha256':source.digest(source.legacy.final.canonical(bad))}
            with self.subTest(key=key),self.assertRaises(ValueError):source.PublicTrainPilot(bad,bad_review)
        with self.assertRaisesRegex(ValueError,'root_review'):source.PublicTrainPilot(request,{**review,'formal_registration_authorized':True})
    def test_actual_public_train_loop_paid_intents_saved_reset_close_no_replay(self):
        with self.environment() as (request,review,(events,_)):
            instance=source.PublicTrainPilot(request,review,enable_live=True);row=instance.run_once()
            with self.assertRaisesRegex(ValueError,'no_replay'):instance.run_once()
        self.assertEqual(row['score'],1);self.assertEqual(events[-1],'provider_close_ack')
        result=json.loads((self.owned/'pilot-result.private.json').read_bytes());self.assertEqual(result['formal_credit'],0)
        self.assertIsNone(result['actual_cost_usd']);self.assertEqual(len(result['paid_sample_calls']),2)
        self.assertTrue(all(c['paid_attempt_id']==request['attempt_id'] for c in result['paid_sample_calls']))
        self.assertTrue((self.owned/'paid-parent-intent.private.json').exists());self.assertTrue((self.owned/'paid-setup-intent.private.json').exists())
        self.assertTrue(result['native_row']['owned_complete_lifecycle_ref'])
    def test_setup_result_evidence_failure_closes_exact_owned_delegate(self):
        from types import SimpleNamespace
        from tests.test_odoo_native_surface_real_lease_v13 import held_fixture
        with held_fixture() as (_,_,_,root):
            events=[]
            class Delegate:
                backend=SimpleNamespace(identity={'model':'Qwen/Qwen3.8-27B'})
                def __enter__(self):events.append('real_enter');return self
                def __exit__(self,*_):events.append('real_close');return False
            sampler=source.PaidPilotSampler(Delegate(),root,{'attempt_id':'public-train-evidence-failure'})
            real_write=source.write
            def write(root,name,value):
                if name=='paid-setup-result.private.json':raise OSError('synthetic storage failure')
                return real_write(root,name,value)
            with patch.object(source,'write',side_effect=write),self.assertRaises(OSError):sampler.__enter__()
            self.assertEqual(events,['real_enter','real_close'])
            self.assertTrue((root/'paid-setup-intent.private.json').exists())

    def test_final_or_other_task_never_dispatches_sdk(self):
        with self.environment() as (request,review,(events,_)):
            request['task']['task_id']='outside-train';review['request_sha256']=source.digest(source.legacy.final.canonical(request))
            instance=source.PublicTrainPilot(request,review,enable_live=True)
            with self.assertRaisesRegex(ValueError,'public_train_partition'):instance.run_once()
        self.assertNotIn('provider_sample',events);self.assertFalse((self.owned/'pilot-result.private.json').exists())
    def test_uncertain_provider_preserves_intent_reset_and_no_result_or_retry(self):
        with self.environment(uncertain=True) as (request,review,(events,_)):
            instance=source.PublicTrainPilot(request,review,enable_live=True)
            with self.assertRaises(Exception):instance.run_once()
            with self.assertRaisesRegex(ValueError,'no_replay'):instance.run_once()
        self.assertIn('cold_reset',events);self.assertIn('provider_close_ack',events)
        self.assertTrue((self.owned/'final-sample-000-intent.private.json').exists());self.assertFalse((self.owned/'final-sample-000-result.private.json').exists())
        self.assertTrue((self.owned/'pilot-failure.private.json').exists())

if __name__=='__main__':unittest.main()
