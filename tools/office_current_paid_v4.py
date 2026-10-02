"""Per-task authentic Qwen and teacher transactions for current native Office."""
from pathlib import Path
import json,time
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_authority_v4 import Authority
from native_desktop_factory.deadline_model_transport_v21 import ModelSampler,checked_deadline_proof
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from cursibench.scale_action_contract import Observation
from cursibench.scale_action_output_v066 import normalize_model_action

class PaidSampler:
 def __init__(self,*,authority:Authority,package,active,output,task_index,quote,delegate_factory=ModelSampler):
  self.authority,self.package,self.active,self.root,self.index,self.quote=authority,package,active,Path(output),task_index,quote
  self.root.mkdir(mode=0o700,exist_ok=False);self.factory=delegate_factory;self.delegate=None;self.deadline=None;self.step=0;self.paid=[];self.results=[];self.proof=None;self.closed=False;self.calls=[]
 def bind_actor_clock(self,started,deadline):
  office.require(deadline==started+720 and self.deadline is None,'Exact current720 actor clock required');self.started,self.deadline=started,deadline
 def dispatch(self,kind,request,provider,ordinal=0):
  a=self.authority
  request_id=f'{kind}-{ordinal:03d}'
  prefix=a.started['attempt_id'] if a.started else a.session.attempt_id if a.session else a.command['attempt_id']
  identifier=a.command['attempt_id'] if a.command is not None else prefix+f'-office-{self.index:03d}-{kind}-{ordinal:03d}'
  office.write_new(self.root/(request_id+'.request.private.json'),office.canonical(request))
  office.write_new(self.root/(request_id+'.intent.private.json'),office.canonical({'request_id':request_id,'paid_attempt_id':identifier,'kind':kind,'request_sha256':office.sha(office.canonical(request)),'same_request_replay_authorized':False}))
  call={'request_id':request_id,'paid_attempt_id':identifier,'kind':kind,'request':request,'result_sha256':None};self.calls.append(call);self.paid.append(identifier)
  if a.command is not None:result=provider(request);result_raw=office.canonical(result);digest=office.sha(result_raw)
  else:
   returned=a.session.dispatch_paid(attempt_id=identifier,category='tinker',work=request,request=request,reserve_usd=self.quote,resource_reservation={},provider=provider)
   office.require(returned['attempt_id']==identifier,'Actual Office paid ID changed');result,digest=returned['result'],returned['result_sha256']
   actual=a.session.directory/(identifier+'.result.private.json') if hasattr(a.session,'journal') else a.session.directory/'paid'/(identifier+'.worker-result.private.json')
   result_raw=office.private(actual)
  office.require(office.sha(result_raw)==digest and json.loads(result_raw)==result,'Actual provider result hash changed')
  office.write_new(self.root/(request_id+'.result.private.json'),result_raw);call['result_sha256']=digest
  return identifier,result,digest
 def start(self):
  a=self.authority;office.require(self.delegate is None and self.deadline is not None,'Fresh owned task sampler clock required')
  self.delegate=self.factory(repo_root=a.study.repo_root,journal_root=self.root/'rpc.private',plan_sha256=a.study.plan_sha256)
  request={'schema':'cua-full-study-selection-sampling-request-v1','cell_id':a.cell,'selection_attempt':a.started['attempt_id'] if a.started else a.session.attempt_id if a.session else a.command['attempt_id'],
   'checkpoint_path_sha256':a.checkpoint,'task_ordinal':self.index,'kind':'sampler_setup'}
  identifier,result,digest=self.dispatch('setup',request,lambda _:self.delegate.start(checkpoint_path=a.checkpoint_path,checkpoint_sha256=a.checkpoint,
   seed=a.sampling['seed'],max_output_tokens=a.sampling['max_output_tokens'],attempt_id='office-'+str(self.index)))
  office.require(result.get('status')=='ready' and result.get('checkpoint_path_sha256')==a.checkpoint,'Actual Qwen task setup uncertain; no replay')
 def __call__(self,observation):
  a=self.authority;office.require(type(observation) is Observation and observation.task_id==self.package.actor.task_id and observation.task_binding_sha256==self.package.binding_sha256 and
   observation.step==self.step and self.step<90 and self.active.current_frame_id()==observation.frame_id and time.monotonic()<observation.expires_at and time.monotonic()<self.deadline,'Actual owned Office current frame/deadline required')
  current_frame_proof(self.active,observation);self.package.revalidate()
  if self.delegate is None:self.start()
  request={'schema':'cua-full-study-selection-sampling-request-v1','cell_id':a.cell,'selection_attempt':a.started['attempt_id'] if a.started else a.session.attempt_id if a.session else a.command['attempt_id'],
   'task_id':observation.task_id,'package_sha256':observation.task_binding_sha256,'checkpoint_path_sha256':a.checkpoint,'step':self.step,'frame_sha256':office.sha(observation.screenshot_bytes)}
  request.update(frame_id=observation.frame_id,rpc_request_id='office-'+str(self.index)+'-'+str(observation.step),actor_deadline_monotonic=self.deadline)
  self.step+=1
  try:
   identifier,result,digest=self.dispatch('sample',request,lambda _:self.delegate.sample(observation=observation,request_id=request['rpc_request_id'],task_dir=self.root,
    remaining_seconds=max(0,self.deadline-time.monotonic()),actor_deadline=self.deadline),ordinal=observation.step)
  except ActorDeadlineReached as error:
   self.proof=self.delegate.assert_deadline_stop(self.deadline);office.require(self.proof==error.proof.receipt(),'Actual owned sampler deadline proof changed')
   office.write_new(self.root/'actor-budget-stop.private.json',office.canonical({'proof':self.proof,'sample_paid_attempt_id':self.calls[-1]['paid_attempt_id'],'request_id':self.calls[-1]['request_id'],'gui_applied':False,'request_replayed':False}));raise
  office.require(result.get('status')=='completed' and result.get('new_dispatch') is True and result.get('reused') is False,'Authentic completed response required')
  self.results.append(result);return result
 def close(self,success):
  if self.closed:return
  self.closed=True
  if self.delegate is None:office.write_new(self.root/'provider-close.private.json',office.canonical({'status':'no_service_created','acknowledged':True,'model_completion_uncertain':False}));return
  self.delegate.close(success)
  raw=office.private(self.root/'rpc.private/child-terminal.private.json');terminal=json.loads(raw)
  office.require(terminal.get('provider_shutdown_acknowledged') is True and terminal.get('forced_termination') is False,'Actual owned provider-close acknowledgement required')
  office.write_new(self.root/'provider-close.private.json',office.canonical({'status':'acknowledged','acknowledged':True,'child_terminal_sha256':office.sha(raw),'model_completion_uncertain':terminal['model_completion_uncertain']}))

def current_frame_proof(active,observation):
 from cursibench import native_surface_guard_policy_v1 as guard
 actor=active.actor;raw=office.private(actor.root/f'turn-{observation.step:03d}/observation-envelope.private.json');value=json.loads(raw);guard.validate_envelope(value)
 office.require(value['frame_id']==observation.frame_id and value['task_id']==observation.task_id and value['task_binding_sha256']==observation.task_binding_sha256 and value['raw_image']['sha256']==office.sha(observation.screenshot_bytes) and value['owned_surface'] is True and value['lease']['lease_id']==active.runtime.account_lease.token and active.runtime.account_lease.active(),'Actual guarded current Office frame/account lease required')
 return office.sha(raw)

class TeacherSampler:
 """Callback is already charged; validate its actual session events once."""
 def __init__(self,*,authority,package,active,callback,close_callback,output):
  office.require(authority.teacher is True and authority.session is not None,'Actual campaign teacher authority required')
  office.require(close_callback is None or callable(close_callback),'Actual external teacher close-evidence callback invalid')
  self.a,self.package,self.active,self.callback,self.close_callback,self.root=authority,package,active,callback,close_callback,Path(output);self.root.mkdir(mode=0o700,exist_ok=False);self.records=[];self.proof=None;self.deadline=None;self.closed=False;self.results=[]
 def bind_actor_clock(self,started,deadline):
  office.require(deadline==started+720 and callable(getattr(self.callback,'bind_actor_clock',None)),'Current bounded native teacher720 clock callback required');self.started,self.deadline=started,deadline;self.callback.bind_actor_clock(started,deadline)
 def __call__(self,observation):
  session=self.a.session;before={r['data']['attempt_id'] for r in session._events('paid_intent')};started=time.monotonic()
  office.require(self.active.current_frame_id()==observation.frame_id and time.monotonic()<self.deadline,'Actual teacher current frame/deadline required');current_frame_proof(self.active,observation);self.package.revalidate()
  try:returned=self.callback(observation,self.active.current_frame_id)
  except ActorDeadlineReached as error:
   self.proof=checked_deadline_proof(error.proof.receipt(),self.deadline).receipt();session._audit_paid_files()
   intents=[r['data'] for r in session._events('paid_intent') if r['data']['attempt_id'] not in before]
   office.require(len(intents)==1 and intents[0]['category']=='teacher_rollout','Actual uncertain teacher paid intent required')
   identifier=intents[0]['attempt_id'];self.records.append(identifier)
   request=json.loads(office.private(session.directory/(identifier+'.request.private.json')));teacher_request(self.a,request,observation)
   office.write_new(self.root/'actor-budget-stop.private.json',office.canonical({'proof':self.proof,'sample_paid_attempt_id':identifier,'request_id':identifier,'gui_applied':False,'request_replayed':False}));raise
  session._audit_paid_files();intents=[r['data'] for r in session._events('paid_intent') if r['data']['attempt_id'] not in before]
  office.require(len(intents)==1 and intents[0]['category']=='teacher_rollout','Exactly one actual charged teacher callback required')
  identifier=intents[0]['attempt_id'];request=json.loads(office.private(session.directory/(identifier+'.request.private.json')))
  teacher_request(self.a,request,observation)
  raw=office.private(session.directory/(identifier+'.result.private.json'));result=json.loads(raw)
  events=[r['data'] for r in session._events('paid_result') if r['data']['attempt_id']==identifier]
  ledger=session.budget.owner_attempts(session.owner).get(identifier)
  from cursibench.full_study_matrix_v1 import TEACHER
  office.require(set(returned)=={'action','trace_row','teacher_result_sha256'} and office.sha(raw)==returned['teacher_result_sha256'] and len(events)==1 and events[0]['result_sha256']==office.sha(raw) and ledger and ledger['category']=='teacher_rollout' and ledger['request_sha256']==office.sha(office.private(session.directory/(identifier+'.request.private.json'))) and result['receipt']['status']=='completed' and result['receipt']['reported_model']==TEACHER,'Authentic teacher result/ledger/model SHA required')
  action=normalize_model_action(result['text'],observation,current_frame_id=self.active.current_frame_id());office.require(action==returned['action']==returned['trace_row']['action'],'Actual teacher reply/action mismatch')
  office.write_new(self.root/f'teacher-{observation.step:03d}.private.json',office.canonical({'paid_attempt_id':identifier,'actual_result_sha256':office.sha(raw),'trace':returned['trace_row'],'teacher_usage':result['receipt'].get('usage'),'no_tinker_charge':True}))
  value={'status':'completed','text':result['text'],'usage':result['receipt'].get('usage'),'elapsed_seconds':time.monotonic()-started,'actual_teacher_result_sha256':office.sha(raw)};self.records.append(identifier);self.results.append(value);return value
 def close(self,success):
  if self.closed:return
  self.closed=True
  if self.close_callback is None:
   office.require(self.proof is None,'Uncertain teacher requires actual external close evidence; retain without admission')
   self.a.session._audit_paid_files();completed={r['data']['attempt_id']:r['data'] for r in self.a.session._events('paid_result')}
   office.require(all(i in completed for i in self.records),'Teacher synchronous callback incomplete')
   refs=[{'path':str((self.a.session.directory/(i+'.result.private.json')).resolve()),'sha256':completed[i]['result_sha256']} for i in self.records]
   office.write_new(self.root/'provider-close.private.json',office.canonical({'status':'all_synchronous_callbacks_completed','acknowledged':True,'actual_callback_paid_ids':self.records,'actual_completed_result_refs':refs,'owned_tinker_service_created':False}));return
  ref=self.close_callback(success,self.records)
  path=Path(ref['path']);office.require(path.resolve().is_relative_to(self.a.study.repo_root/'work'),'Teacher provider cleanup outside owned work')
  raw=office.private(path);value=json.loads(raw)
  office.require(office.sha(raw)==ref['sha256'] and value.get('schema')=='office-current-teacher-provider-close-v4' and value.get('paid_attempt_ids')==self.records and value.get('acknowledged') is True and value.get('outstanding_requests')==0 and value.get('forced_termination') is False,'Actual teacher provider completion/close proof required')
  office.write_new(self.root/'provider-close.private.json',office.canonical({**value,'external_evidence_ref':ref,'tinker_service_created':False}))

def teacher_request(authority,request,observation):
 office.require(request['cell_id']==authority.cell and request.get('train_task_id',request.get('task_id'))==observation.task_id and request['package_sha256']==observation.task_binding_sha256 and request['step']==observation.step and request['frame_sha256']==office.sha(observation.screenshot_bytes),'Actual teacher task/frame provenance changed')
