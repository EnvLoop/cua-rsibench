"""TRAIN teacher facade over the shared current native Desktop episode.

Callbacks already reserve/dispatch their teacher and E2B calls. This adapter
reopens those actual records; it never creates a second Tinker charge or a
synthetic paid ID. Constructors are source-only.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time
from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action
from . import current_episode_paid_id_v22 as engine
from . import admit
from .factory import digest

SOURCE_FILES=('native_desktop_factory/current_episode_paid_id_v22.py','native_desktop_factory/current_teacher_worker_v22.py',
 'native_desktop_factory/prospective_model_worker_v21.py','native_desktop_factory/deadline_model_transport_v21.py','native_desktop_factory/actor_deadline_future_v21.py',
 'src/cursibench/full_study_teacher_adapter_v1.py','src/cursibench/full_study_teacher_current_v22.py','tests/test_native_desktop_current_episode_paid_id_v22.py','tests/test_native_desktop_current_teacher_worker_v22.py')

def require(value,code):
 if not value:raise ValueError(code)

def private(path):return engine.integration.controls.private(Path(path))
def write(path,value):
 raw=teacher._canonical(value);path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(descriptor,'wb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
 return {'path':Path(path).name,'sha256':digest(Path(path).read_bytes())}

def source_closure(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);return {name:digest((root/name).read_bytes()) for name in SOURCE_FILES}

class PaidProvenance:
 """Read actual session hash-chain, budget and private request/result bytes."""
 def __init__(self,session):self.session=session
 def snapshot(self):return {r['data']['attempt_id'] for r in self.session._events('paid_intent')}
 def new(self,before,*,category,identity,step=None,frame_sha256=None,result_sha256=None):
  self.session._audit_paid_files()
  intents=[r['data'] for r in self.session._events('paid_intent') if r['data']['attempt_id'] not in before]
  require(len(intents)==1 and intents[0]['category']==category,'Exactly one authentic callback paid intent required')
  intent=intents[0];identifier=intent['attempt_id'];folder=Path(self.session.directory)
  request_raw=private(folder/(identifier+'.request.private.json'));request=json.loads(request_raw)
  require(digest(request_raw)==intent['request_sha256'] and request['cell_id']=='desktop-native' and request['train_task_id']==identity['task_id'] and
   request['package_sha256']==identity['package_sha256'],'Callback actual paid request task/category changed')
  if step is not None:require(request['step']==step and request['frame_sha256']==frame_sha256,'Callback actual paid frame/step changed')
  row=self.session.budget.owner_attempts(self.session.owner).get(identifier)
  require(type(row) is dict and row['category']==category and row['request_sha256']==intent['request_sha256'] and row['status'] in ['dispatched','uncertain','settled'],
   'Authentic callback budget dispatch missing')
  result_path=folder/(identifier+'.result.private.json');result=None
  if result_sha256 is not None:
   result_raw=private(result_path);result=json.loads(result_raw)
   events=[r['data'] for r in self.session._events('paid_result') if r['data']['attempt_id']==identifier]
   require(len(events)==1 and events[0]['result_sha256']==result_sha256==digest(result_raw),'Callback actual paid result SHA changed')
  return {'attempt_id':identifier,'category':category,'request':request,'request_sha256':intent['request_sha256'],'result':result,'result_sha256':result_sha256,
   'budget_status':row['status'],'actual_usd':row.get('actual_usd')}

class TeacherSampler:
 def __init__(self,*,callback,provenance,identity,paid,actor_getter):
  self.callback,self.provenance,self.identity,self.paid,self.actor_getter=callback,provenance,identity,paid,actor_getter
  self.deadline_proof=None
  self.backend=SimpleNamespace(identity={'sampling_kind':'authentic_teacher_projection','model':teacher.matrix.TEACHER});self.records=[];self.last=None
 def sample(self,*,observation,request_id,task_dir,remaining_seconds,actor_deadline):
  actor=self.actor_getter();require(actor is not None and not actor.killed,'Current native teacher actor missing')
  before=self.provenance.snapshot();started=time.monotonic()
  def current_frame():return actor.current_teacher_frame_id()
  try:returned=self.callback(observation,current_frame)
  except BaseException as error:
   from .actor_deadline_future_v21 import ActorDeadlineReached
   if isinstance(error,ActorDeadlineReached):self.deadline_proof=error.proof.receipt()
   actual=self.provenance.new(before,category='teacher_rollout',identity=self.identity,step=observation.step,frame_sha256=digest(observation.screenshot_bytes))
   self.paid.last_actual=actual;raise
  require(set(returned)=={'action','trace_row','teacher_result_sha256'},'Actual teacher callback shape changed')
  actual=self.provenance.new(before,category='teacher_rollout',identity=self.identity,step=observation.step,frame_sha256=digest(observation.screenshot_bytes),result_sha256=returned['teacher_result_sha256'])
  require(type(actual['result']) is dict and set(actual['result'])=={'text','receipt'} and actual['result']['receipt']['reported_model']==teacher.matrix.TEACHER and
   actual['result']['receipt']['status']=='completed','Authentic teacher response/usage missing')
  action=validate_action(returned['action'],observation,current_frame_id=current_frame())
  require(normalize_model_action(actual['result']['text'],observation,current_frame_id=current_frame())==action and returned['trace_row']['action']==action and
   returned['trace_row']['teacher_result_sha256']==actual['result_sha256'],'Actual teacher text/action/trace mismatch')
  projection={k:v for k,v in action.items() if k not in {'version','task_id','task_binding_sha256','frame_id','step'}}
  text=teacher._canonical(projection).decode().strip();require(normalize_model_action(text,observation,current_frame_id=current_frame())==action,'Minimal teacher projection changed action')
  record={'actual_paid':actual,'callback':returned,'projection_sha256':digest(text.encode()),'elapsed_seconds':time.monotonic()-started}
  self.last=record;self.records.append(record);self.paid.last_actual=actual
  write(Path(task_dir)/f'teacher-{observation.step:03d}.private.json',record)
  # These are actual teacher counts, not a Tinker usage record. Engine metadata
  # keeps the original paid result SHA plus a separately labelled projection.
  return {'status':'completed','text':text,'usage':actual['result']['receipt']['usage'],'elapsed_seconds':record['elapsed_seconds'],
   'actual_teacher_result_sha256':actual['result_sha256'],'teacher_projection_sha256':record['projection_sha256'],'new_dispatch':True,'reused':False}
 def assert_deadline_stop(self,deadline):
  require(self.paid.last_actual is not None,'Actual consumed teacher intent missing')
  engine.transport.checked_deadline_proof(self.deadline_proof,deadline)
  return self.deadline_proof

class TeacherPaidCalls:
 def __init__(self,*,session,identity,root,dispatch_e2b):
  self.session,self.identity,self.root,self.dispatch_e2b=session,identity,Path(root),dispatch_e2b
  self.provenance=PaidProvenance(session);self.attempt_id=session.owner;self.ids=[];self.calls=[];self.last_actual=None;self.sampler=None
 def invoke(self,*,suffix,category,request,provider,identity=None):
  require(identity==self.identity,'Teacher current episode task identity changed')
  if category=='e2b':
   require(request['lease_seconds']==1200 and request['phase'] in ['actor','reset'],'Uniform native teacher lease changed')
   before=self.provenance.snapshot();paid=self.dispatch_e2b(lease_seconds=1200,reserve_usd='0.333333334',provider=provider,phase=request['phase'])
   actual=self.provenance.new(before,category='e2b',identity=self.identity,result_sha256=paid['result_sha256'])
   require(paid['attempt_id']==actual['attempt_id'] and paid['result']==actual['result'],'Actual E2B callback record changed')
   raw=actual['result'];result={'status':'active','sandbox_id_sha256':digest(raw['sandbox_id'].encode()),'lease_seconds':raw['lease_seconds']}
  else:
   require(category=='tinker' and self.sampler is not None,'Only current engine sampling hook may project authentic teacher response')
   # This internal engine label creates no Tinker session or paid call.
   try:result=provider(request)
   except BaseException:
    actual=self.last_actual
    if actual is not None:self.ids.append(actual['attempt_id']);self.calls.append(actual);write(self.root/f'paid-link-{len(self.calls):03d}.private.json',{'engine_hook_category':'teacher_projection','actual_paid':actual,'no_second_charge':True,'result_known':False})
    raise
   actual=self.sampler.last['actual_paid']
  self.last_actual=actual;self.ids.append(actual['attempt_id']);self.calls.append(actual)
  write(self.root/f'paid-link-{len(self.calls):03d}.private.json',{'engine_hook_category':category,'actual_paid':actual,'no_second_charge':True})
  return result,actual['result_sha256'],actual['attempt_id']
 def actual_sample_attempt_id(self,*,ordinal,step):
  actual=self.last_actual;require(actual is not None and actual['category']=='teacher_rollout' and actual['request']['step']==step,'Actual consumed teacher sample paid ID required')
  return actual['attempt_id']

class TeacherNativeGuest:
 def __init__(self,guest):self.guest=guest;self.frame=None
 def __getattr__(self,key):return getattr(self.guest,key)
 def observe(self,**kwargs):self.frame=self.guest.observe(**kwargs);return self.frame
 def current_teacher_frame_id(self):return self.frame.frame_id if self.frame is not None and not self.guest.killed and time.monotonic()<self.frame.expires_at else 'stale'
 def dispatch_model(self,*args,**kwargs):return self.guest.dispatch_model(*args,**kwargs)

class CurrentTeacherEpisode(engine.DesktopProspectiveModelWorker):
 def __init__(self,*,guest_factory=None):
  super().__init__(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'));self.guest_factory=guest_factory;self.teacher_actor=None
 def _create(self,*,paid,package,ordinal,phase,gui_root):
  out=gui_root/package['identity']['task_id']/phase;out.mkdir(parents=True,mode=0o700);guest=None
  def create(request):
   nonlocal guest
   if self.guest_factory is None:
    from .reconcile_interrupted_sweep import active_hashes
    active,count=active_hashes();require(not active and count==0,'Native teacher create requires active-zero')
    factory=engine.transport.create_guest
   else:factory=self.guest_factory
   guest=TeacherNativeGuest(factory(root=gui_root,out=out,filename=package['filename']))
   return {'schema':teacher.E2B_RESULT_SCHEMA,'sandbox_id':guest.sandbox.sandbox_id,'lease_seconds':1200,'created':True}
  try:paid.invoke(suffix=f'e2b-{ordinal:03d}-{phase}',category='e2b',identity=package['identity'],request={'phase':phase,'lease_seconds':1200},provider=create)
  except BaseException:
   if guest is not None:guest.close()
   raise
  if phase=='actor':self.teacher_actor=guest
  return guest

class DesktopCurrentTeacherWorker:
 cell_id='desktop-native'
 action_profile='scale-action-profile-v0.6.6'
 original_software_gui=True
 original_surface='native'
 requires_e2b=True
 requires_fresh_e2b_reset=True
 def __init__(self,*,session,admissions_path,proposal_path,enable_live=False):
  self.session=session;self.admissions_path=Path(admissions_path);self.proposal_path=Path(proposal_path);self.enable_live=enable_live
  proposal=engine.integration.proposal();self.adapter_sha256=proposal['adapter_source_sha256'];self.runtime_sha256=proposal['worker_runtime_sha256'];self.verifier_sha256=proposal['verifier_sha256']
  self.sources=source_closure()
 def _gate(self,task):
  require(self.enable_live is True,'Current teacher native dispatch disabled before private package read')
  from cursibench import full_study_runtime_v2 as policy_runtime
  require(type(self.session) is policy_runtime.CampaignSession and type(self.session.study) is policy_runtime.FrozenStudy,'Real witnessed v22 teacher campaign required')
  require(source_closure()==self.sources,'Current teacher source closure changed')
  from cursibench.full_study_native_counterparts_v22 import require_activation
  registration=self.session.study.policy_manifest.get('native_counterparts',{}).get(self.cell_id)
  require(type(registration) is dict and set(self.sources)<=set(registration.get('native_source_sha256s',{})) and
   all(registration['native_source_sha256s'][name]==value for name,value in self.sources.items()),'Teacher closure must be registered for all five slots before campaigns')
  require_activation(registration)
  with engine.integration.runtime_context(),policy_runtime.runtime_context(self.session.study):
   worker=engine.DesktopProspectiveModelWorker(study=self.session.study,admissions_path=self.admissions_path,proposal_path=self.proposal_path,enable_live=True)
   admitted=worker._gate()
  views=self.session.study.task_views(self.cell_id)['train'];identity={k:task[k] for k in ['task_id','package_sha256']}
  require(identity in [{k:r[k] for k in identity} for r in views],'Current teacher task outside frozen TRAIN20')
  return admitted
 def run_episode(self,*,task,out_dir,sample_teacher,dispatch_e2b):
  admitted=self._gate(task);root=Path(out_dir)
  # Only TRAIN metadata is matched before its evaluator package is opened.
  candidate=Path(admitted['candidate_root']);inventory=json.loads(private(candidate/'candidate-inventory.json'))
  matches=[r for r in inventory['tasks'] if r['task_id']==task['task_id']]
  require(len(matches)==1 and matches[0]['split']=='train' and matches[0]['package_sha256']==task['package_sha256'],'Current teacher package must be exact TRAIN identity')
  directory,source,oracle=admit._package(candidate,matches[0]);files=[p for p in directory.iterdir() if p.suffix in ['.xlsx','.pptx','.docx']]
  require(len(files)==1 and oracle['split']=='train' and (directory/'actor_task.txt').read_text()==task['visible_instruction'],'Current teacher source/visible projection changed')
  package={'identity':{k:task[k] for k in ['task_id','package_sha256']},'source':source,'oracle':oracle,'filename':files[0].name,'instruction':task['visible_instruction'],'guest_reference_path':admitted['guest_public']}
  return self._run_current(admitted=admitted,package=package,root=root,sample_teacher=sample_teacher,dispatch_e2b=dispatch_e2b)
 def _run_current(self,*,admitted,package,root,sample_teacher,dispatch_e2b,episode=None):
  batch=root/'current-native-engine';batch.mkdir(mode=0o700,exist_ok=False)
  current=episode or CurrentTeacherEpisode();paid=TeacherPaidCalls(session=self.session,identity=package['identity'],root=batch,dispatch_e2b=dispatch_e2b)
  sampler=TeacherSampler(callback=sample_teacher,provenance=paid.provenance,identity=package['identity'],paid=paid,actor_getter=lambda:current.teacher_actor);paid.sampler=sampler
  self.current_episode=current;self.active_paid=paid;self.current_episode_root=batch
  try:
   result,evaluator,trace,elapsed,outcome=current._episode(admitted=admitted,package=package,ordinal=0,batch=batch,paid=paid,sampler=sampler)
   require(result['score']==1 and outcome=='finished' and elapsed<=720 and len(trace)==len(sampler.records) and trace[-1]['action']['type']=='finish','Teacher current saved/reset result is not an admitted demonstration')
   return self._receipt(root=root,package=package,result=result,evaluator=evaluator,trace=trace,records=sampler.records,paid=paid)
  except BaseException as error:
   write(batch/'teacher-terminal.private.json',{'status':'not_admitted_no_replay','error_class':type(error).__name__,'actual_paid_attempt_ids':paid.ids,
    'actual_last_attempt':paid.last_actual,'teacher_source_sha256s':self.sources,'official_model_results':0})
   raise
 def authorize_actual_budget_reset(self,*,task,episode_dir):
  paid=getattr(self,'active_paid',None);current=getattr(self,'current_episode',None);root=Path(episode_dir)/'current-native-engine'
  require(paid is not None and current is not None and root==self.current_episode_root and paid.identity=={k:task[k] for k in ['task_id','package_sha256']},'Teacher budget reset must bind this current episode')
  actor=current.teacher_actor;require(actor is not None and actor.killed,'Teacher budget reset requires actual owned actor close')
  evaluator=root/'gui'/task['task_id']/'evaluator';budget_raw=private(evaluator/'actor-budget-stop.private.json');budget=json.loads(budget_raw);clock_raw=private(evaluator/'actor-clock.private.json');clock=json.loads(clock_raw)
  engine.transport.checked_deadline_proof(budget['actor_deadline_proof'],clock['actor_deadline_monotonic'])
  identifier=paid.actual_sample_attempt_id(ordinal=0,step=paid.last_actual['request']['step'])
  require(budget['sample_paid_attempt_id']==identifier and budget['gui_applied'] is False and clock['model_outcome']=='actor_wall_budget' and
   clock['actor_elapsed_seconds']==720 and clock['native_actions_after_deadline']==0,'Actual teacher deadline/clock/paid identity proof changed')
  close_raw=private(actor.out/'guest.private.json');closed=json.loads(close_raw)
  require(closed['kill_returned'] is True and closed['is_running_after_kill'] is False,'Actual actor termination proof missing')
  paid.provenance.new({r['data']['attempt_id'] for r in self.session._events('paid_intent') if r['data']['attempt_id']!=identifier},category='teacher_rollout',identity=paid.identity,
   step=paid.last_actual['request']['step'],frame_sha256=paid.last_actual['request']['frame_sha256'])
  write(root/'one-use-budget-reset-authorization.private.json',{'schema':'cua-native-teacher-budget-reset-authorization-v22','actual_teacher_paid_attempt_id':identifier,
   'actor_budget_stop_sha256':digest(budget_raw),'actor_clock_sha256':digest(clock_raw),'actor_close_sha256':digest(close_raw),'same_request_replay_authorized':False,'official_model_results':0})
  return True
 def _receipt(self,*,root,package,result,evaluator,trace,records,paid):
  identity=package['identity'];task=json.loads(private(evaluator/'task.private.json'));saved=private(evaluator/task['saved_file']);reset=json.loads(private(evaluator/'reset.private.json'));verified=json.loads(private(evaluator/'verifier.private.json'))
  require(verified['score']==1 and verified['fair_result']['passed'] is True and engine.no_regression_passed(verified['fair_result']) and saved!=package['source'] and
   reset['actor_guest_sha256']!=reset['reset_guest_sha256'] and reset['actor_terminated'] is reset['reset_terminated'] is True and
   reset['initial_state_sha256']==reset['restored_state_sha256']==digest(package['source']),'Teacher actual saved/native/distinct-reset proof changed')
  frame_refs=[];rows=[];shas=[]
  for ordinal,(entry,record) in enumerate(zip(trace,records)):
   original=record['callback'];require(entry['paid_attempt_id']==record['actual_paid']['attempt_id'] and entry['model_result_sha256']==original['teacher_result_sha256'],'Current engine actual teacher identity changed')
   image_ref=entry['sampled_frame'];image=private(root/'current-native-engine'/'gui'/image_ref['private_path']);require(digest(image)==image_ref['sha256']==original['trace_row']['frame_sha256'],'Actual paid teacher/native frame bytes differ')
   target=root/'frames'/f'step-{ordinal:03d}.png';target.parent.mkdir(mode=0o700,exist_ok=True)
   descriptor=__import__('os').open(target,__import__('os').O_WRONLY|__import__('os').O_CREAT|__import__('os').O_EXCL,0o600)
   with __import__('os').fdopen(descriptor,'wb') as output:output.write(image)
   frame_refs.append({'path':str(target.relative_to(root)),'sha256':digest(image)});rows.append(original['trace_row']);shas.append(original['teacher_result_sha256'])
  artifacts=root/'artifacts';artifacts.mkdir(mode=0o700)
  saved_path=artifacts/('saved'+Path(package['filename']).suffix);saved_path.write_bytes(saved);saved_path.chmod(0o600);saved_ref={'path':str(saved_path.relative_to(root)),'sha256':digest(saved)}
  neutral={'source_sha256':digest(package['source']),'reset_equivalence':'exact_original_bytes'}
  baseline=write(artifacts/'baseline.private.json',neutral);baseline['path']='artifacts/'+baseline['path'];restored=write(artifacts/'restored.private.json',neutral);restored['path']='artifacts/'+restored['path']
  state=write(root/'saved-state.private.json',{'schema':teacher.STATE_SCHEMA,'cell_id':self.cell_id,**identity,'independent_of_actor':True,'native_save_observed':True,'target_state_pass':True,'no_regression_pass':True,
   'saved_artifact_sha256':digest(saved),'saved_artifact_ref':saved_ref,'verifier_sha256':self.verifier_sha256,'evaluator_result':'pass'})
  reset_ref=write(root/'reset.private.json',{'schema':teacher.RESET_SCHEMA,'cell_id':self.cell_id,**identity,'independent_of_actor':True,'fresh_environment':True,'state_equivalence_pass':True,'sandbox_terminated':True,
   'baseline_semantic_sha256':baseline['sha256'],'restored_semantic_sha256':restored['sha256'],'baseline_state_ref':baseline,'restored_state_ref':restored})
  action_ref=write(root/'actions.private.json',rows)
  receipt={'schema':teacher.EPISODE_SCHEMA,'status':'admitted','split':'train','cell_id':self.cell_id,**identity,'action_profile':self.action_profile,'teacher_model':teacher.matrix.TEACHER,
   'original_software_gui':True,'original_surface':'native','runtime_sha256':self.runtime_sha256,'adapter_sha256':self.adapter_sha256,'frame_refs':frame_refs,'action_trace_ref':action_ref,
   'saved_state_ref':state,'reset_ref':reset_ref,'teacher_result_sha256s':shas,'e2b_attempt_ids':[r['attempt_id'] for r in paid.calls if r['category']=='e2b']}
  ref=write(root/'episode.private.json',receipt)
  write(root/'current-engine-link.private.json',{'schema':'cua-native-current-teacher-engine-link-v22','current_episode_result':result,'teacher_source_sha256s':self.sources,
   'actor_clock_ref':{'path':str((evaluator/'actor-clock.private.json').relative_to(root)),'sha256':digest(private(evaluator/'actor-clock.private.json'))},
   'actual_paid_attempt_ids':paid.ids,'no_tinker_calls_or_second_teacher_charge':True,'common_semantic_native_guard_qualification_claimed':False})
  return {'episode_receipt_path':str(root/'episode.private.json'),'episode_receipt_sha256':ref['sha256']}


def source_registration(*,root,native_epoch_sha256):
 from cursibench.full_study_native_counterparts_v22 import register
 sources=source_closure(root)
 return register(root,cell_id='desktop-native',native_source_sha256s=sources,
  actor_clock_source_sha256=sources['native_desktop_factory/actor_deadline_future_v21.py'],native_epoch_sha256=native_epoch_sha256,qualified=False)
