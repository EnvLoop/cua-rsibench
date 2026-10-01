import copy,json,os,tempfile,unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from types import SimpleNamespace
from enterprise_fallback.odoo18 import twenty_task_trial_teacher_v1 as trial

class AuthorityTests(unittest.TestCase):
 def plan(self):
  return {'schema':'envloop-single-environment-twenty-task-trial-v1','cell_id':'odoo-community','final_task_count':20,'selection_task_count':20,'train_task_count':20,'native_binding_sha256':'a'*64,'models':{'student':'Qwen/Qwen3.8-27B','teacher':'gpt-6-sol','initial_researcher':'gpt-6-sol'},'full_six_environment_publication_claim':False,'final_tasks_metadata':[{'task_id':f'{family}-{i}','family':family} for family in ('purchase','inventory','sales','crm') for i in range(5)]}
 def check(self,value):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'plan.json';raw=json.dumps(value).encode();path.write_bytes(raw);path.chmod(0o600)
   with patch.object(trial.workers,'public_binding',return_value={'binding_sha256':'a'*64}):return trial.checked_trial(path,sha256(raw).hexdigest())
 def test_actual_single_cell_shape_has_no_large_study_authority(self):self.assertFalse(self.check(self.plan())['full_six_environment_publication_claim'])
 def test_old_large_count_foreign_cell_and_source_refuse(self):
  for key,value in [('final_task_count',100),('cell_id','gitlab'),('native_binding_sha256','b'*64),('full_six_environment_publication_claim',True)]:
   plan=self.plan();plan[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.check(plan)
 def test_duplicate_or_family_skew_cannot_be_counted_as_twenty(self):
  for mode in ('duplicate','family'):
   plan=self.plan()
   if mode=='duplicate':plan['final_tasks_metadata'][1]['task_id']=plan['final_tasks_metadata'][0]['task_id']
   else:plan['final_tasks_metadata'][1]['family']='sales'
   with self.assertRaises(ValueError):self.check(plan)

class NativeReceiptBindingTests(unittest.TestCase):
 def test_actual_source_scope_uses_sol61_without_mutating_historical_teacher(self):
  binding=trial.workers.public_binding()
  historical_model=trial.teacher.matrix.TEACHER
  training,_=trial.scoped_model_modules(binding,'gpt-6-sol')
  scoped=training.OdooTrainEpisodeWorker.run_episode
  self.assertEqual(scoped.__globals__['teacher'].matrix.TEACHER,'gpt-6-sol')
  self.assertEqual(trial.teacher.matrix.TEACHER,historical_model)
  fresh,_=trial.workers._model_modules(binding)
  self.assertEqual(fresh.OdooTrainEpisodeWorker.run_episode.__globals__['teacher'].matrix.TEACHER,historical_model)
  self.assertEqual(trial.workers.public_binding()['binding_sha256'],binding['binding_sha256'])

 def verify_fixture(self,tamper=None,model='gpt-6-sol'):
  # Synthetic test artifacts carry no actual task, teacher or training credit.
  from tests.test_full_study_teacher_adapter_v1 import FakeWorker,write_private
  with tempfile.TemporaryDirectory() as tmp:
   episode=Path(tmp)/'episode';episode.mkdir(mode=0o700);(episode/'frames').mkdir(mode=0o700)
   task={'task_id':'train-test','package_sha256':'a'*64,'visible_instruction':'Synthetic test'}
   turns=[]
   def sample(observation,current_frame):
    action=trial.output.normalize_model_action(json.dumps({'type':'click','target':{'ref':'c001'}} if observation.step==0 else {'type':'finish'}),observation,current_frame_id=current_frame())
    trace={'step':observation.step,'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],'action':action,'teacher_result_sha256':'c'*64}
    turns.append({'observation':observation,'action':action,'trace_row':copy.deepcopy(trace),'teacher_result_sha256':'c'*64})
    return {'action':action,'trace_row':trace,'teacher_result_sha256':'c'*64}
   worker=FakeWorker('e'*64,cell_id='odoo-community');worker.tamper=tamper
   result=worker.run_episode(task=task,out_dir=episode,sample_teacher=sample,dispatch_e2b=None)
   receipt_path=Path(result['episode_receipt_path']);receipt=json.loads(receipt_path.read_bytes());receipt['teacher_model']=model
   result['episode_receipt_sha256']=write_private(receipt_path,receipt)
   active=SimpleNamespace(runtime_sha256=worker.runtime_sha,adapter_sha256=worker.adapter_sha256,verifier_sha256=worker.verifier_sha)
   return trial.verify_trial_episode(episode,result,task,turns,active,'gpt-6-sol')

 def test_source_verifier_reopens_actual_fixture_artifacts_with_trial_model(self):
  self.assertEqual(len(self.verify_fixture()),64)

 def test_artifact_trace_reset_split_and_old_model_are_rejected(self):
  for tamper in ('frame','trace','saved_state','artifact','reset','split'):
   with self.subTest(tamper=tamper),self.assertRaises(ValueError):self.verify_fixture(tamper)
  with self.assertRaises(ValueError):self.verify_fixture(model='gpt-5.6-sol')

class ResearcherReturnTests(unittest.TestCase):
 def fixture(self,model='gpt-6-sol',changed=False):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);proposal={'hypothesis':'Synthetic test','train_task_ids':['test-train'],'teacher_request':'GUI only'}
   text=json.dumps(proposal);response={'model':model,'status':'completed','id':'synthetic-test-response','output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}
   raw=json.dumps(response).encode();(root/'raw-response.private.json').write_bytes(raw);(root/'raw-response.private.json').chmod(0o600)
   trial.write(root/'provider-result.private.json',{'reported_model':model,'provider_status':'completed','response_id':response['id'],'response_sha256':sha256(raw).hexdigest(),'proposal_text_sha256':sha256(text.encode()).hexdigest()})
   if changed:proposal['hypothesis']='Changed after response'
   path=root/'validated-proposal.private.json';trial.write(path,proposal)
   return trial.checked_proposal(path,sha256(path.read_bytes()).hexdigest(),'gpt-6-sol')
 def test_exact_synthetic_model_receipt_and_proposal_match(self):self.assertEqual(self.fixture()['train_task_ids'],['test-train'])
 def test_old_model_or_changed_proposal_cannot_enter_new_epoch(self):
  with self.assertRaises(ValueError):self.fixture(model='gpt-6.1-sol')
  with self.assertRaises(ValueError):self.fixture(changed=True)

class AppliedTrainingTurnTests(unittest.TestCase):
 def actual_contracts(self,root,adapter,page):
  """Production guard/Unix lease on synthetic UI; no provider or service."""
  (root/'artifacts').mkdir(mode=0o700)
  contracts=root/'artifacts/native-contracts';contracts.mkdir(mode=0o700)
  frames=root/'frames';frames.mkdir(mode=0o700)
  turns=[]
  for index,kind in enumerate(('click','click','finish')):
   page.disabled=False
   observation,_=adapter.observe_for_model()
   payload={'type':kind}
   if kind=='click':payload['target']={'x':350,'y':50}
   action=adapter.parse_current_action(json.dumps(payload))
   if index==1:page.disabled=True  # Same safe observed target becomes disabled.
   result=adapter.dispatch(action)
   frame=frames/f'step-{index:03d}.png';frame.write_bytes(observation.screenshot_bytes);frame.chmod(0o600)
   trace={'step':index,'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],
    'action':action,'teacher_result_sha256':str(index+1)*64}
   turns.append({'observation':observation,'action':action,'trace_row':trace,'teacher_result_sha256':trace['teacher_result_sha256']})
   trial.write(contracts/f'step-{index:03d}.private.json',{'step':index,'action':action,
    'frame_sha256':observation.screenshot['sha256'],
    'native_observation_control_refs':sorted(c.ref for c in observation.controls if c.visible and c.enabled),
    'contract_receipt':result['public_contract_receipt'],'native_dispatch_status':result['status']})
  trial.write(root/'actions.private.json',[turn['trace_row'] for turn in turns])
  return turns
 def test_actual_applied_and_finished_only_rejected_trace_is_retained(self):
  from tests.test_odoo_native_surface_real_lease_v13 import held_fixture
  with held_fixture() as (adapter,page,_private,root):
   turns=self.actual_contracts(root,adapter,page)
   packets=[root/f'artifacts/native-contracts/step-{i:03d}.private.json' for i in range(3)]
   statuses=[json.loads(p.read_bytes())['native_dispatch_status'] for p in packets]
   self.assertEqual(statuses,['applied','rejected','finished'])
   originals=[sha256(p.read_bytes()).hexdigest() for p in [*packets,root/'actions.private.json']]
   admitted=trial.admissible_training_turns(root,turns)
   self.assertEqual(admitted,[turns[0],turns[2]])
   self.assertEqual([t['observation'].step for t in admitted],[0,2])
   self.assertEqual(len(turns),3);self.assertEqual(turns[1]['action']['type'],'click')
   self.assertEqual(originals,[sha256(p.read_bytes()).hexdigest() for p in [*packets,root/'actions.private.json']])
   rejected=json.loads(packets[1].read_bytes())
   capsule=json.loads(trial.workers.native_ref_bytes(root,rejected['contract_receipt']['native_surface_guard']))
   self.assertEqual(capsule['receipt']['status'],'rejected');self.assertEqual(capsule['receipt']['driver_result'],'not_attempted')
 def test_missing_unknown_status_changed_step_frame_or_action_never_curates(self):
  from tests.test_odoo_native_surface_real_lease_v13 import held_fixture
  for defect in ('missing','unknown','wrong_step','wrong_frame','wrong_action','finished_click','applied_finish'):
   with self.subTest(defect=defect),held_fixture() as (adapter,page,_private,root):
    turns=self.actual_contracts(root,adapter,page)
    index=2 if defect=='applied_finish' else 0
    path=root/f'artifacts/native-contracts/step-{index:03d}.private.json'
    if defect=='missing':path.unlink()
    else:
     value=json.loads(path.read_bytes())
     if defect=='unknown':value['native_dispatch_status']='pending'
     if defect=='wrong_step':value['step']=99
     if defect=='wrong_frame':value['frame_sha256']='0'*64
     if defect=='wrong_action':value['action']={**value['action'],'type':'wait','duration_ms':100}
     if defect=='finished_click':value['native_dispatch_status']='finished'
     if defect=='applied_finish':value['native_dispatch_status']='applied'
     path.write_text(json.dumps(value));path.chmod(0o600)
    with self.assertRaises(Exception):trial.admissible_training_turns(root,turns)

class RendererPreflightTests(unittest.TestCase):
 def test_renderer_failure_precedes_output_paid_intent_factory_and_native(self):
  from uuid import uuid4
  root=Path(trial.__file__).resolve().parents[2]
  out=root/'work'/('source-test-renderer-no-dispatch-'+uuid4().hex)
  plan=AuthorityTests().plan();proposal={'hypothesis':'Synthetic public TRAIN fixture','train_task_ids':['train-000'],
   'teacher_request':'Read only the visible public source and use GUI actions.'}
  world={'cases':{family:[{'id':f'train-{family}-{i}','family':family,'prompt':'Synthetic public training instruction'}
   for i in range(5)] for family in ('purchase','inventory','sales','crm')}}
  world['cases']['purchase'][0]['id']='train-000'
  manifest={'train':[{'task_id':c['id'],'package_sha256':'a'*64} for group in world['cases'].values() for c in group]}
  def private(path,*_args):
   if str(path).endswith('partition_cases.json'):return world
   if str(path).endswith('task_set_manifest.json'):return manifest
   raise AssertionError('Unexpected preflight evidence read')
  events=[]
  def native_factory(*_args,**_kwargs):events.append('native_factory');raise AssertionError('native factory must not run')
  def render():events.append('renderer_preflight');raise RuntimeError('synthetic missing image processor')
  with patch.dict(os.environ,{},clear=True),patch.object(trial,'checked_trial',return_value=plan),patch.object(trial,'checked_proposal',return_value=proposal), \
   patch.object(trial.workers,'private_json',side_effect=private),patch.object(trial.workers,'train_worker',native_factory), \
   patch.object(trial.teacher,'_load_renderer',side_effect=render),patch.object(trial.teacher,'_real_teacher_provider',side_effect=AssertionError('No API')), \
   patch.object(trial,'write',side_effect=AssertionError('No paid/storage dispatch before renderer')):
   with self.assertRaisesRegex(RuntimeError,'missing image processor'):
    trial.run(plan_path='/unused/public-plan.private.json',plan_sha='a'*64,worker_dir='/unused/train',
     native_binding_path='/unused/native-binding.private.json',native_binding_sha='a'*64,
     train_control_path='/unused/accepted-train.private.json',train_control_sha='a'*64,
     proposal_path='/unused/public-proposal.private.json',proposal_sha='a'*64,task_id='train-000',output_root=out,execute=True)
  self.assertEqual(events,['renderer_preflight']);self.assertFalse(out.exists())
  self.assertFalse(out.parent.joinpath(out.name+'-paid-intent.private.json').exists())

class OwnedDeadlineCallbackTests(unittest.TestCase):
 def clock(self,deadline):
  import time
  from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached,ActorDeadlineProof
  class Clock:
   def __init__(self):self.deadline=deadline;self.stages=[]
   def clock(self):return time.monotonic()
   def check(self,stage):
    self.stages.append(stage);now=time.monotonic()
    if now>=self.deadline:
     raise ActorDeadlineReached(ActorDeadlineProof(self.deadline,now,now,0,'actor_deadline_reached_before_submission',False,False))
  return Clock()
 def test_real_future_completed_callback_and_close_have_truthful_counts(self):
  import time
  owner=trial.OwnedTeacherCalls();clock=self.clock(time.monotonic()+1);events=[]
  def callback(observation,current):
   events.append((observation,current()));owner.check_current();return {'status':'completed','synthetic':True}
  try:
   value=owner.call(callback,'public-observation',lambda:'fresh-frame',clock)
   self.assertEqual(value,{'status':'completed','synthetic':True});self.assertEqual(events,[('public-observation','fresh-frame')])
   receipt=owner.close(timeout_seconds=.1)
   self.assertEqual(receipt['submitted_callbacks'],1);self.assertEqual(receipt['settled_callbacks'],1)
   self.assertEqual(receipt['pending_callbacks'],0);self.assertTrue(receipt['all_callbacks_settled'])
   self.assertTrue(receipt['executor_shutdown_returned'])
  finally:owner.close(timeout_seconds=.1)
 def test_typed_deadline_pending_then_settled_callback_is_not_replayed(self):
  import time,threading
  from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
  owner=trial.OwnedTeacherCalls();release=threading.Event();entered=threading.Event();events=[]
  clock=self.clock(time.monotonic()+.04)
  def callback(observation,current):
   events.append('submitted_once');entered.set();release.wait(timeout=1);owner.check_current()
   return {'status':'late-completed'}
  try:
   with self.assertRaises(ActorDeadlineReached):owner.call(callback,None,lambda:'fresh-frame',clock)
   self.assertTrue(entered.is_set());pending=owner.close(timeout_seconds=.01)
   self.assertEqual(pending['submitted_callbacks'],1);self.assertEqual(pending['pending_callbacks'],1)
   self.assertEqual(pending['settled_callbacks'],0);self.assertFalse(pending['all_callbacks_settled'])
   release.set();settled=owner.close(timeout_seconds=.2)
   self.assertEqual(settled['pending_callbacks'],0);self.assertEqual(settled['settled_callbacks'],1)
   self.assertTrue(settled['all_callbacks_settled']);self.assertEqual(events,['submitted_once'])
  finally:release.set();owner.close(timeout_seconds=.2)
 def test_expired_clock_never_submits_callback(self):
  import time
  from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
  owner=trial.OwnedTeacherCalls();callback=__import__('unittest.mock',fromlist=['Mock']).Mock()
  try:
   with self.assertRaises(ActorDeadlineReached):owner.call(callback,None,lambda:'old-frame',self.clock(time.monotonic()-1))
   callback.assert_not_called();receipt=owner.close(timeout_seconds=.01)
   self.assertEqual(receipt['submitted_callbacks'],0);self.assertEqual(receipt['pending_callbacks'],0)
  finally:owner.close(timeout_seconds=.01)

if __name__=='__main__':unittest.main()
