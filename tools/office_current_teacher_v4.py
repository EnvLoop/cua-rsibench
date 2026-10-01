"""Current original Office teacher on the same task loop; real paid callbacks.

The collector is checked against its historical source. Only Office's lifecycle
names, image byte paths and bounded teacher transport are projected additively.
"""
from pathlib import Path
from types import ModuleType
from concurrent.futures import ThreadPoolExecutor
import hashlib,inspect,json,time,sys
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_authority_v4 import Authority,verify_qualification
from tools.office_current_execution_v4 import TaskWorker
from tools.office_current_evidence_v4 import reopen_task,reset_state,preserved
from tools.office_current_protocol_v4 import epoch_context
from cursibench import full_study_teacher_adapter_v1 as legacy
from cursibench import full_study_matrix_v1 as matrix
from native_desktop_factory.actor_deadline_future_v21 import DeadlineFuture,ActorDeadlineReached
from tools.office_current_native_clock_v4 import deadline

# Bound literal by source review; never recompute an expected pin at execution.
EXPECTED_COLLECTOR_SHA='b5a6b434a03e1079a7db28982dc482527c0893aa809892d848daaa20cd0952fc'


def collector():
 raw=Path(legacy.__file__).read_bytes();office.require(hashlib.sha256(raw).hexdigest()==EXPECTED_COLLECTOR_SHA,'Historical teacher collector source changed')
 source=raw.decode();replacements=[
  ("response = (teacher_provider(paid_request) if teacher_provider\n                            is not None else _real_teacher_provider(\n                                paid_request, harness['request_timeout_seconds']))",'response = cell_worker.teacher_transport(paid_request,teacher_provider)'),
  ("reset.get('sandbox_terminated') is True","reset.get('owned_native_documents_closed') is True"),
  ("f'frames/step-{index:03d}.png'","f'frames/step-{index:03d}.image'"),
  ("_reference(directory, reference, suffix='.png')","_reference(directory, reference, suffix='.image')")]
 for before,after in replacements:
  office.require(source.count(before)==1,'Exact Office collector projection changed');source=source.replace(before,after)
 module=ModuleType('cursibench._office_current_teacher_v4');module.__file__=legacy.__file__;module.__package__='cursibench';sys.modules[module.__name__]=module;exec(compile(source,'office-current-teacher-collector-v4','exec'),module.__dict__)
 return module


class TeacherTransport:
 """One fresh owned HTTP client and future pool per native task; no retries."""
 def __init__(self,root,provider_timeout=120):
  self.root=Path(root);self.root.mkdir(mode=0o700,exist_ok=False);self.started=None;self.deadline=None;self.client=None;self.pool=ThreadPoolExecutor(max_workers=1);self.futures=[];self.closed=False;self.ordinal=0;self.provider_timeout=min(120,provider_timeout)
 def bind_actor_clock(self,started,absolute_deadline):
  office.require(self.deadline is None and absolute_deadline==started+720,'Exact native teacher clock required once');self.started,self.deadline=started,absolute_deadline
 def _provider(self,request,timeout):
  from cursibench import full_study_teacher_adapter_v1 as original
  source=inspect.getsource(original._real_teacher_provider)
  before='    from .http_transport import post_json\n';office.require(source.count(before)==1,'Original teacher HTTP projection changed');source=source.replace(before,'    post_json = owned_post_json\n')
  namespace=dict(vars(original));namespace['owned_post_json']=self._post;exec(compile(source,'office-current-owned-teacher-http-v4','exec'),namespace)
  return namespace['_real_teacher_provider'](request,timeout)
 def _post(self,url,payload,headers,timeout):
  import httpx
  deadline(self.deadline);remaining=max(0,self.deadline-time.monotonic())
  if self.client is None:self.client=httpx.Client(http2=True,limits=httpx.Limits(max_connections=1,max_keepalive_connections=1),follow_redirects=False)
  deadline(self.deadline)
  try:response=self.client.post(url,json=payload,headers=headers,timeout=httpx.Timeout(min(timeout,remaining),connect=min(20,remaining),pool=min(20,remaining),write=min(20,remaining)))
  except httpx.TimeoutException:
   if time.monotonic()>=self.deadline:raise TimeoutError('owned_teacher_wait_reached_actual_actor_deadline') from None
   raise
  response.raise_for_status();body=response.json()
  office.require(type(body) is dict,'Actual teacher response JSON required');body['__cua_transport']={'connect_attempts':1};return body
 def __call__(self,request,provider=None):
  deadline(self.deadline);ordinal=self.ordinal;self.ordinal+=1
  office.write_new(self.root/f'request-{ordinal:03d}.private.json',office.canonical({'request_sha256':office.sha(office.canonical(request)),'actor_deadline_monotonic':self.deadline,'same_request_replay_authorized':False}))
  started=time.monotonic();future=self.pool.submit(provider or (lambda value:self._provider(value,self.provider_timeout)),request);self.futures.append(future)
  wrapped=DeadlineFuture(future,actor_deadline=self.deadline)
  try:result=wrapped.result(timeout=self.provider_timeout)
  except ActorDeadlineReached as error:
   office.write_new(self.root/f'deadline-{ordinal:03d}.private.json',office.canonical(error.proof.receipt()))
   def retain(f):
    try:value={'actual_late_response':f.result(),'gui_application_authorized':False}
    except BaseException as exc:value={'actual_future_exception':type(exc).__name__,'model_completion_inferred':False,'gui_application_authorized':False}
    office.write_new(self.root/f'late-{ordinal:03d}.private.json',office.canonical(value))
   future.add_done_callback(retain);raise
  office.write_new(self.root/f'response-{ordinal:03d}.private.json',office.canonical({'result':result,'elapsed_seconds':time.monotonic()-started}));return result
 def close_evidence(self,success,paid_ids):
  office.require(not self.closed,'Owned teacher transport close is one-use');self.closed=True
  if self.client is not None:self.client.close()
  for future in self.futures:
   try:future.result(timeout=30)
   except BaseException:pass
  known=all(f.done() for f in self.futures);self.pool.shutdown(wait=known,cancel_futures=True)
  value={'schema':'office-current-teacher-provider-close-v4','paid_attempt_ids':list(paid_ids),'acknowledged':known,'outstanding_requests':sum(not f.done() for f in self.futures),
   'forced_termination':False,'owned_http_client_closed':self.client is None or self.client.is_closed,'owned_tinker_service_created':False,'actual_cost_usd':None}
  path=self.root/'close.private.json';office.write_new(path,office.canonical(value));return {'path':str(path.resolve()),'sha256':office.sha(office.private(path))}


class TeacherWorker:
 cell_id=None;action_profile='scale-action-profile-v0.6.6';original_software_gui=True;original_surface='web';requires_e2b=False;requires_fresh_e2b_reset=False
 def __init__(self,*,session,worker_options,quote):
  self.session,self.options,self.quote=session,worker_options,quote;self.cell_id=session.intent['cell_id']
  self.authority=Authority(authority=session.study,cell_id=self.cell_id,owner_slot=session.intent['researcher_id'],session=session,teacher=True)
  verify_qualification(session.study,self.cell_id,worker_options['qualification_path'],worker_options['qualification_sha256'])
  self.adapter_sha256=session.study.ratification['cell_profiles'][self.cell_id]['adapter_sha256']
  office.require(self.adapter_sha256==office.sha(Path(__file__).with_name('office_current_workers_v4.py').read_bytes()),'Fresh actual Office teacher adapter ratification required')
  _,harness,_,_=collector()._teacher_configuration(session);office.require(harness['max_actions_per_episode']==90,'Fresh matched90-action teacher harness required');self.provider_timeout=harness['request_timeout_seconds']
  self.teacher_transport=None
 def run_episode(self,*,task,out_dir,sample_teacher,dispatch_e2b):
  office.require(task.get('split','train')=='train' and {'task_id':task['task_id'],'package_sha256':task['package_sha256']} in self.authority.identities(),'Actual original TRAIN teacher task required')
  root=Path(out_dir);identity={k:task[k] for k in ('task_id','package_sha256')}
  self.teacher_transport=TeacherTransport(root/'owned-teacher-provider.private',self.provider_timeout);sample_teacher.bind_actor_clock=self.teacher_transport.bind_actor_clock
  options={**self.options,'teacher_callback':sample_teacher,'teacher_close_callback':self.teacher_transport.close_evidence}
  worker=TaskWorker(authority=self.authority,output_root=root/'native-run.private',**options)
  with epoch_context(self.session.study):result,native=worker.run(identity,quote=self.quote)
  package=self.authority.load_package(identity,worker.metadata);checked=reopen_task(package,native)
  if result['actor_budget_proof'] is not None:
   from tools.office_current_evidence_v4 import task_projection
   from tools.office_current_budget_performance_v4 import descriptor
   task_projection(package,native);verification=descriptor(self.session.study,package,native)
   with epoch_context(self.session.study):self.session.authorize_verified_budget_stop(json.loads(office.private(native/'sampler.private/actor-budget-stop.private.json'))['sample_paid_attempt_id'],verification=verification)
  office.require(result['score']==1 and result['model_outcome']=='finished','Deadline/failed teacher attempt is retained and cannot become training data')
  records=[json.loads(office.private(p)) for p in sorted((native/'sampler.private').glob('teacher-*.private.json'))]
  office.require(records and records[-1]['trace']['action']['type']=='finish','Actual teacher finish required before dataset admission')
  frames=[]
  for index,record in enumerate(records):
   envelope=json.loads(office.private(native/f'native.private/actor-private/turn-{index:03d}/observation-envelope.private.json'))
   raw=office.private(native/'native.private/actor-private'/envelope['raw_image']['path']);path=root/f'frames/step-{index:03d}.image';office.write_new(path,raw);frames.append({'path':str(path.relative_to(root)),'sha256':office.sha(raw)})
  traces=[r['trace'] for r in records];office.write_new(root/'actions.private.json',office.canonical(traces));artifacts=root/'artifacts';artifacts.mkdir(mode=0o700)
  saved=artifacts/('saved'+package.paths['baseline'].suffix);office.write_new(saved,office.private(checked['saved_path']))
  initial=artifacts/'baseline-state.private.json';restored=artifacts/'restored-state.private.json';office.write_new(initial,office.canonical(checked['initial_state']));office.write_new(restored,office.canonical(checked['reset_state']))
  def ref(path):return {'path':str(path.relative_to(root)),'sha256':office.sha(office.private(path))}
  common={k:task[k] for k in ('task_id','package_sha256')};common['cell_id']=self.cell_id
  state=root/'saved-state.private.json';office.write_new(state,office.canonical({'schema':legacy.STATE_SCHEMA,**common,'independent_of_actor':True,'native_save_observed':True,'target_state_pass':True,'no_regression_pass':preserved(checked['strict']),'saved_artifact_sha256':office.sha(office.private(saved)),'saved_artifact_ref':ref(saved),'verifier_sha256':self.authority.cell_plan['matched_bindings']['verifier'],'evaluator_result':'pass'}))
  reset=root/'reset.private.json';office.write_new(reset,office.canonical({'schema':legacy.RESET_SCHEMA,**common,'independent_of_actor':True,'fresh_environment':True,'state_equivalence_pass':True,'baseline_semantic_sha256':office.sha(office.private(initial)),'restored_semantic_sha256':office.sha(office.private(restored)),'owned_native_documents_closed':True,'baseline_state_ref':ref(initial),'restored_state_ref':ref(restored)}))
  receipt={'schema':legacy.EPISODE_SCHEMA,'status':'admitted','split':'train',**common,'action_profile':self.action_profile,'teacher_model':matrix.TEACHER,'original_software_gui':True,'original_surface':'web','runtime_sha256':self.authority.cell_plan['matched_bindings']['runtime'],'adapter_sha256':self.adapter_sha256,'frame_refs':frames,'action_trace_ref':ref(root/'actions.private.json'),'saved_state_ref':ref(state),'reset_ref':ref(reset),'teacher_result_sha256s':[r['actual_result_sha256'] for r in records],'e2b_attempt_ids':[]}
  path=root/'episode.private.json';office.write_new(path,office.canonical(receipt));return {'episode_receipt_path':str(path),'episode_receipt_sha256':office.sha(office.private(path))}


def collect_train_batch(session,round_index,train_context_path,out_dir,cell_worker,*,teacher_provider=None):
 office.require(type(cell_worker) is TeacherWorker and cell_worker.session is session,'Actual current Office teacher worker/session required')
 with epoch_context(session.study):return collector().collect_train_batch(session,round_index,train_context_path,out_dir,cell_worker,teacher_provider=teacher_provider)
