"""Current native episode with real file/ledger bindings and synthetic IO only."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_output_v066 import normalize_model_action
from native_desktop_factory import current_teacher_worker_v22 as current
from native_desktop_factory.factory import digest
from tests.test_native_desktop_uniform_model_transport_v11 import FakeModelGuest
from tests.test_native_desktop_selection_worker_v066 import source_case
from tests.test_structural_guest_attestation_v16 import fixture

class LedgerSession:
 def __init__(self,root):
  self.directory=root;root.mkdir(mode=0o700);self.owner='desktop-native:astra';self.events=[];self.records={};self.calls=[]
  self.budget=SimpleNamespace(owner_attempts=lambda owner:self.records)
 def _events(self,kind):return [r for r in self.events if r['kind']==kind]
 def _audit_paid_files(self):
  for event in self._events('paid_intent'):
   data=event['data'];raw=(self.directory/(data['attempt_id']+'.request.private.json')).read_bytes();assert digest(raw)==data['request_sha256']
  for event in self._events('paid_result'):
   data=event['data'];assert digest((self.directory/(data['attempt_id']+'.result.private.json')).read_bytes())==data['result_sha256']
 def dispatch(self,identifier,category,request,provider):
  self.calls.append(category);request_ref=current.write(self.directory/(identifier+'.request.private.json'),request)
  self.events.append({'kind':'paid_intent','data':{'attempt_id':identifier,'category':category,'request_sha256':request_ref['sha256']}})
  self.records[identifier]={'category':category,'status':'dispatched','request_sha256':request_ref['sha256'],'actual_usd':None}
  try:result=provider(request)
  except BaseException:self.records[identifier]['status']='uncertain';raise
  ref=current.write(self.directory/(identifier+'.result.private.json'),result)
  self.events.append({'kind':'paid_result','data':{'attempt_id':identifier,'result_sha256':ref['sha256']}})
  return {'attempt_id':identifier,'result':result,'result_sha256':ref['sha256']}

class TeacherTests(unittest.TestCase):
 def context(self,root,mode='good'):
  source,neutral,positive,oracle,ext=source_case('calc-growth');identity={'task_id':'train-fixture','package_sha256':'b'*64};session=LedgerSession(root/'session')
  guest=root/'guest.private.json';current.write(guest,fixture()[2]);mapping=root/'map.private.json';current.write(mapping,{'variant_salt':'offline-only-'*4})
  admitted={'guest_public':str(guest),'scoped_reference':str(root/'profile'),'private_map':str(mapping)}
  package={'identity':identity,'source':source,'oracle':oracle,'filename':'train'+ext,'instruction':'Visible synthetic TRAIN task only','guest_reference_path':str(guest)}
  made=[];turns=[];observations=[]
  def factory(**kwargs):
   native=FakeModelGuest(kwargs['root'],kwargs['out'],kwargs['filename'],source,positive,kwargs['out'].name,identity)
   if mode=='reset' and kwargs['out'].name=='reset':native.read_saved=lambda:b'wrong original bytes'
   if mode=='budget' and kwargs['out'].name=='actor':
    original=native.observe
    def near_deadline(**arguments):self.clock.now=729.5;return original(**arguments)
    native.observe=near_deadline
   made.append(native);return native
  def sample(observation,current_frame_id):
   observations.append(observation)
   raw='{"type":"click","target":{"x":500,"y":400}}' if observation.step==0 else '{"type":"finish"}'
   request={'cell_id':'desktop-native','train_task_id':identity['task_id'],'package_sha256':identity['package_sha256'],'step':observation.step,'frame_sha256':digest(observation.screenshot_bytes)}
   def provider(_):
    if mode=='budget':
     from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineProof,ActorDeadlineReached
     self.clock.now=731.0;raise ActorDeadlineReached(ActorDeadlineProof(730.0,729.5,730.0,0.5,'actor_deadline_reached_during_wait',True,False))
    return {'text':raw,'receipt':{'status':'completed','reported_model':teacher.matrix.TEACHER,'response_id':'synthetic-response','usage':{'input_tokens':100,'output_tokens':8}}}
   paid=session.dispatch('teacher-r001-e001-s'+str(observation.step).zfill(3),'teacher_rollout',request,provider)
   action=normalize_model_action(raw,observation,current_frame_id=current_frame_id());trace={'step':observation.step,'frame_id':observation.frame_id,'frame_sha256':request['frame_sha256'],'action':action,'teacher_result_sha256':paid['result_sha256']}
   returned={'action':action,'trace_row':trace,'teacher_result_sha256':paid['result_sha256']}
   if mode=='sha':returned['teacher_result_sha256']='f'*64
   turns.append(returned);return returned
  sample.observations=observations
  def e2b(**kwargs):
   if mode=='budget' and kwargs['phase']=='reset':self.assertTrue(worker.authorize_actual_budget_reset(task=identity,episode_dir=root/'episode'))
   request={'cell_id':'desktop-native','train_task_id':identity['task_id'],'package_sha256':identity['package_sha256'],'lease_seconds':kwargs['lease_seconds'],'phase':kwargs['phase']}
   return session.dispatch('e2b-teacher-r001-e001'+('-reset' if kwargs['phase']=='reset' else ''),'e2b',request,kwargs['provider'])
  worker=object.__new__(current.DesktopCurrentTeacherWorker);worker.session=session;worker.sources=current.source_closure();proposal=current.engine.integration.proposal();worker.adapter_sha256=proposal['adapter_source_sha256'];worker.runtime_sha256=proposal['worker_runtime_sha256'];worker.verifier_sha256=proposal['verifier_sha256']
  episode=current.CurrentTeacherEpisode(guest_factory=factory)
  return worker,episode,admitted,package,sample,e2b,made,session,turns
 def test_actual_current_episode_and_authentic_teacher_e2b_provenance_save_reset(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);worker,episode,admitted,package,sample,e2b,made,session,turns=self.context(root)
   episode_root=root/'episode';episode_root.mkdir(mode=0o700)
   result=worker._run_current(admitted=admitted,package=package,root=episode_root,sample_teacher=sample,dispatch_e2b=e2b,episode=episode)
   self.assertIs(episode._episode.__func__,current.engine.DesktopProspectiveModelWorker._episode)
   self.assertEqual(session.calls,['e2b','teacher_rollout','teacher_rollout','e2b']);self.assertNotIn('tinker',session.calls)
   self.assertEqual(len(made),2);self.assertTrue(all(g.killed for g in made));self.assertNotEqual(made[0].sandbox.sandbox_id,made[1].sandbox.sandbox_id)
   receipt=json.loads(Path(result['episode_receipt_path']).read_bytes());self.assertEqual(receipt['teacher_result_sha256s'],[r['teacher_result_sha256'] for r in turns])
   self.assertEqual(receipt['e2b_attempt_ids'],['e2b-teacher-r001-e001','e2b-teacher-r001-e001-reset'])
   self.assertTrue((episode_root/'current-native-engine/gui/train-fixture/evaluator/actor-clock.private.json').exists())
   expected=[{'observation':obs,**row} for obs,row in zip(sample.observations,turns)]
   self.assertEqual(teacher._verify_episode(episode_root,result,cell_id='desktop-native',task=package['identity'],runtime_sha=worker.runtime_sha256,adapter_sha=worker.adapter_sha256,verifier_sha=worker.verifier_sha256,turns=expected,e2b_attempt_ids=receipt['e2b_attempt_ids'],requires_e2b=True,requires_fresh_e2b_reset=True),result['episode_receipt_sha256'])
 def test_true_teacher_deadline_retains_actual_paid_id_and_distinct_reset_without_fake_finish(self):
  class Clock:
   now=10.0
   def __call__(self):return self.now
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);self.clock=Clock();worker,episode,admitted,package,sample,e2b,made,session,turns=self.context(root,'budget');destination=root/'episode';destination.mkdir(mode=0o700)
   with patch.object(current.engine.transport.time,'monotonic',self.clock):
    with self.assertRaisesRegex(ValueError,'not an admitted'):worker._run_current(admitted=admitted,package=package,root=destination,sample_teacher=sample,dispatch_e2b=e2b,episode=episode)
   evaluator=destination/'current-native-engine/gui/train-fixture/evaluator';budget=json.loads((evaluator/'actor-budget-stop.private.json').read_bytes());task=json.loads((evaluator/'task.private.json').read_bytes())
   self.assertEqual(budget['sample_paid_attempt_id'],'teacher-r001-e001-s000');self.assertEqual(task['score'],0);self.assertEqual(task['model_outcome'],'actor_wall_budget');self.assertEqual(turns,[])
   self.assertEqual(session.calls,['e2b','teacher_rollout','e2b']);self.assertEqual(len(made),2);self.assertTrue(all(g.killed for g in made));self.assertFalse((destination/'episode.private.json').exists())
   self.assertTrue((destination/'current-native-engine/one-use-budget-reset-authorization.private.json').exists())
 def test_changed_actual_teacher_hash_cannot_admit_or_recharge(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);worker,episode,admitted,package,sample,e2b,made,session,_=self.context(root,'sha');destination=root/'episode';destination.mkdir(mode=0o700)
   with self.assertRaises((ValueError,AssertionError)):worker._run_current(admitted=admitted,package=package,root=destination,sample_teacher=sample,dispatch_e2b=e2b,episode=episode)
   self.assertEqual(session.calls,['e2b','teacher_rollout']);self.assertTrue(made[0].killed);self.assertFalse((destination/'episode.private.json').exists())
 def test_wrong_fresh_reset_never_produces_teacher_receipt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);worker,episode,admitted,package,sample,e2b,made,session,_=self.context(root,'reset');destination=root/'episode';destination.mkdir(mode=0o700)
   with self.assertRaisesRegex(ValueError,'reset'):worker._run_current(admitted=admitted,package=package,root=destination,sample_teacher=sample,dispatch_e2b=e2b,episode=episode)
   self.assertTrue(all(g.killed for g in made));self.assertFalse((destination/'episode.private.json').exists())

if __name__=='__main__':unittest.main()
