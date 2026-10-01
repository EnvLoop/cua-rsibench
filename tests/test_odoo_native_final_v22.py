"""Actual v22 gate/command API; native/SDK are synthetic and read-only sources."""
from pathlib import Path
from types import SimpleNamespace
import copy,json,tempfile,unittest
from unittest.mock import patch
from cursibench import full_study_runtime_v2 as runtime,full_study_final_dispatch_v1 as final
from enterprise_fallback.odoo18 import native_surface_final_worker_v22 as source,native_surface_workers_v13 as workers
from tests import test_full_study_final_dispatch_v1 as gates,v22_policy_runtime_fixture as fixtures
from tests.test_odoo_native_surface_final_worker_v1 import save
from tests.test_odoo_native_surface_real_lease_v13 import held_fixture
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached,ActorDeadlineProof


class FinalV22Tests(unittest.TestCase):
 def setUp(self):
  self.f=gates.FullStudyFinalDispatchTests();self.f.setUp();self.addCleanup(self.f.tearDown)
  self.gate,_,_=fixtures.final_gate(self.f);self.cell=next(c for c in self.gate.plan['cells'] if c['cell_id']==source.CELL)
  self.binding=workers.public_binding();self.bpath=self.f.work/'native13.private.json';self.bsha=save(self.bpath,self.binding)
  self.spath=self.f.work/'native22-source.private.json';self.ssha=save(self.spath,source.source_binding())
  for key,value in {'runtime':self.binding['binding_sha256'],'source_snapshot':source.digest(final.canonical(source.study_source_snapshot())),
   'verifier':self.binding['source_sha256s']['enterprise_fallback/odoo18/verify.py']}.items():
   self.cell['matched_bindings'][key]=value
   for slot in [self.cell['base'],*self.cell['researcher_plans'].values()]:slot['bindings'][key]=value
  self.gate.frozen.ratification['cell_profiles'][source.CELL]['adapter_sha256']=self.binding['source_sha256s'][workers.ADAPTER_FILE]
  self.out=(self.f.work/'out-v22').resolve();self.out.mkdir(mode=0o700)
 def worker(self):
  return source.final_worker_factory(gate=self.gate,native_worker_module=source.MODULE,native_binding_path=self.bpath,native_binding_file_sha256=self.bsha,
   source_binding_path=self.spath,source_binding_file_sha256=self.ssha,worker_dir=self.f.work/'official_hidden',final_output_root=self.out,
   local_cost_authority_path=self.f.work/'unused-nominal.private.json',local_cost_authority_sha256='a'*64,enable_live=True)
 def command(self):
  task=next(r for c in self.cell['base']['chunks'] for r in c['tasks']);slot=self.cell['base'];attempt=f'final-3-shared-base-000-0'
  # Matrix order supplies the exact authoritative ordinal.
  attempt=f'final-{source.legacy.matrix.CELLS.index(source.CELL):02d}-shared-base-000-0'
  command={'schema':final.COMMAND_SCHEMA,'study_id':self.gate.plan['study_id'],'cell_id':source.CELL,'owner_slot':'shared-base',**task,
   'checkpoint_sha256':slot['bindings']['checkpoint'],'sampler_path':None,'expected_initial_state_sha256':self.gate.initial_state_by_task[source.CELL][task['task_id']],
   'attempt_id':attempt,'retry_index':0,'retry_rule_sha256':None,'action_profile':'scale-action-profile-v0.6.6','sampling':slot['sampling'],
   'max_actions':90,'max_wall_seconds':720,'matched_bindings':self.cell['matched_bindings'],'reserve_usd':'1'}
  output=self.out/attempt;output.mkdir(mode=0o700);return command,output
 def test_real_v22_constructor_is_metadata_only_and_legacy_gate_refuses(self):
  with patch.object(source.legacy,'_modules',side_effect=AssertionError('hidden body')):worker=self.worker()
  self.assertEqual(worker.identity['runtime_sha256'],self.binding['binding_sha256'])
  with self.assertRaisesRegex(ValueError,'v22_final_gate'):source.final_worker_factory(gate=object())
 def test_actual_reservation_exact_fields_checkpoint_and_no_replay(self):
  worker=self.worker();cmd,out=self.command()
  with self.assertRaisesRegex(ValueError,'reservation'):worker._command(cmd,out)
  self.gate.budget.reserve(cmd['attempt_id'],source.CELL+':shared-base','shared_base_final','1',source.digest(final.canonical(cmd)))
  self.gate.budget.mark_dispatched(cmd['attempt_id'],source.digest(final.canonical(cmd)));worker._command(cmd,out)
  for key,value in [('cell_id','gitlab'),('task_id','wrong'),('checkpoint_sha256','0'*64),('max_wall_seconds',1200),('sampling',{}),('owner_slot','unknown')]:
   with self.subTest(key=key),self.assertRaises(ValueError):worker._command({**cmd,key:value},out)
  with self.assertRaises(ValueError):worker._command({**cmd,'unknown':True},out)
  with patch.object(worker,'_episode',side_effect=RuntimeError('synthetic provider fault')) as episode:
   with self.assertRaises(RuntimeError):worker.run_once(cmd,out)
   with self.assertRaises(ValueError):worker.run_once(cmd,out)
   self.assertEqual(episode.call_count,1)
 def test_source_registration_keeps_actor57_binding_separate(self):
  value=source.source_binding();self.assertEqual(value['native_binding_sha256'],workers.public_binding()['binding_sha256'])
  self.assertFalse(value['qualification_claimed']);self.assertEqual(value['actor_seconds'],720);self.assertEqual(value['lifecycle_seconds'],1200)


class MeteringTests(unittest.TestCase):
 def test_actual_parent_paid_id_and_sdk_request_id_preserved(self):
  with held_fixture() as (adapter,page,_private,root):
   observation,_=adapter.observe_for_model();attempt='final-parent-reservation'
   request='odoo-sel-'+source.digest(attempt.encode())[:10]+'-00-000'
   delegate=SimpleNamespace(attempt_id=attempt,sample=lambda *a,**kw:{'status':'completed','request_id':request,'new_dispatch':True,'reused':False,'text':'{"type":"finish"}','usage':{'input_tokens':10,'image_tokens':5,'output_tokens':3}})
   wrapped=source.MeteredSampler(delegate,root,{'attempt_id':attempt});wrapped.actor_clock=adapter.actor_clock
   result=wrapped.sample(observation,task_index=0,step=0,task_dir=root)
   self.assertEqual(result['paid_attempt_id'],attempt);self.assertEqual(wrapped.calls[0]['request_id'],request)
   intent=json.loads((root/wrapped.calls[0]['intent']['path']).read_bytes());self.assertEqual(intent['paid_attempt_id'],attempt)
   self.assertFalse(intent['same_request_replay_authorized'])
 def test_typed_deadline_retains_intent_without_completed_result_or_replay(self):
  with held_fixture() as (adapter,page,_private,root):
   observation,_=adapter.observe_for_model();proof=ActorDeadlineProof(adapter.actor_clock.deadline,page.tick,adapter.actor_clock.deadline,120,'actor_deadline_reached_during_wait',True,False)
   def unknown(*args,**kw):raise ActorDeadlineReached(proof)
   wrapped=source.MeteredSampler(SimpleNamespace(attempt_id='actual-parent',sample=unknown),root,{'attempt_id':'actual-parent'});wrapped.actor_clock=adapter.actor_clock
   with self.assertRaises(ActorDeadlineReached):wrapped.sample(observation,task_index=0,step=0,task_dir=root)
   self.assertIsNone(wrapped.calls[0]['result']);self.assertTrue((root/wrapped.calls[0]['intent']['path']).is_file())

class NoRetrySDKTests(unittest.TestCase):
 def test_real_installed_sdk_no_retry_configuration_base_and_four_checkpoint_slots(self):
  from enterprise_fallback.odoo18.odoo_no_retry_sampler_v22 import sampler_class
  from cursibench.scale_vision_proxy import MODEL,digest,QwenVisionRenderer
  import tinker
  _,selection=workers._model_modules(workers.public_binding())
  calls=[]
  class Client:
   def get_base_model(self):return MODEL
  class Service:
   def __init__(self,**kwargs):calls.append(('service',kwargs))
   def create_sampling_client(self,**kwargs):calls.append(('sampling',kwargs));return Client()
  with patch.object(tinker,'ServiceClient',Service),patch.object(QwenVisionRenderer,'load',return_value=SimpleNamespace(identity={'model':MODEL})):
   for owner in ['shared-base','astra','sol','luna','reference']:
    base=owner=='shared-base';path=MODEL if base else 'tinker://fixture/sampler_weights/'+owner
    actual=sampler_class(selection)(checkpoint_path=path,config={'seed':0},output_root=Path('/unused'),attempt_id='source-test-'+owner,
      base_mode=base,expected_base_checkpoint_sha256=digest(MODEL) if base else None)
    actual.__enter__();self.assertEqual(actual.backend.identity['checkpoint_sha256'],digest(path))
  self.assertEqual(len(calls),10)
  for kind,value in calls:
   if kind=='service':self.assertEqual(value['max_retries'],0)
   else:self.assertFalse(value['retry_config'].enable_retry_logic)

if __name__=='__main__':unittest.main()
