"""Concrete same-loop original Office execution for student/teacher actors."""
from pathlib import Path
import json,time
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_native_clock_v4 import CurrentOperationSpool
from tools.office_current_authority_v4 import Authority,current_sources
from tools.office_current_paid_v4 import PaidSampler,TeacherSampler
from cursibench.scale_action_output_v066 import normalize_model_action
from cursibench.scale_action_contract import ContractError
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached

class TaskWorker:
 def __init__(self,*,authority,metadata_index,binding_path,profile_path,qualification_path,qualification_sha256,output_root,
  operation_spool_factory=CurrentOperationSpool,sampler_factory=PaidSampler,teacher_callback=None,teacher_close_callback=None):
  office.require(type(authority) is Authority,'Actual current Office authority required')
  self.authority=authority;authority.qualify(qualification_path,qualification_sha256)
  self.qualification_path=Path(qualification_path).resolve();self.qualification_sha256=qualification_sha256
  self.metadata=Path(metadata_index);self.binding_path=Path(binding_path);self.profile_path=Path(profile_path);self.output=Path(output_root)
  self.binding=json.loads(office.private(self.binding_path));self.profile=json.loads(office.private(self.profile_path))
  from tools.office_neutral_lifecycle_pilot_v4 import V4_FILES
  expected={name:current_sources(authority.study.repo_root)[name] for name in (*V4_FILES,'tools/office_current_cua_pump_v4.mjs') if name.endswith('.mjs')}
  office.require(expected==self.binding['supplemental_source_sha256s'] and self.profile['download_surface']=='folder_toolbar' and self.binding['max_wall_seconds']==1200 and
   self.profile['source_reviewed'] is True,'Current V4 native source/lease/profile binding required')
  office.require(self.output.resolve().is_relative_to(authority.study.repo_root/'work'),'Owned private study output required')
  if authority.owner=='shared-base' and authority.command is None:office.require(self.output.resolve().is_relative_to(authority.session.directory.resolve()),'Shared-base native output must belong to its actual paid session')
  self.spool_factory,self.sampler_factory,self.teacher_callback,self.teacher_close_callback=operation_spool_factory,sampler_factory,teacher_callback,teacher_close_callback

 def run(self,identity,*,ordinal=0,quote):
  # Authority and native qualification were checked before hidden body access.
  package=self.authority.load_package(identity,self.metadata)
  root=self.output/(str(ordinal).zfill(3)+'-'+identity['task_id']);office.require(not root.exists() and not root.is_symlink(),'Office current task intent consumed; no replay');root.mkdir(mode=0o700,parents=True)
  office.write_new(root/'task-intent.private.json',office.canonical({'identity':identity,'owner_slot':self.authority.owner,'current_sources':current_sources(self.authority.study.repo_root),'one_use':True}))
  admission={'schema':'office-owned-folder-native-host-source-review-v2','approved':True,'single_account':True,'graph_used':False,'actual_native_lifecycle_qualified':True,
   'account_principal_sha256':self.binding['account_principal_sha256'],'folder_scope_sha256':self.binding['folder_scope_sha256'],'native_evidence_root':self.binding['native_evidence_root'],
   'supplemental_source_sha256s':self.binding['supplemental_source_sha256s'],'qualified_before_hidden_body':True}
  # This flag is justified by the constructor's actual reopened qualification;
  # no preparation or source-registration path manufactures acceptance.
  admission_path=root/'native-source-admission.private.json';office.write_new(admission_path,office.canonical(admission))
  permit={'schema':'office-owned-folder-runtime-permit-v2','binding_sha256':office.sha(office.private(self.binding_path)),'source_reviewed':True}
  permit_path=root/'native-runtime-permit.private.json';office.write_new(permit_path,office.canonical(permit))
  spool=self.spool_factory(root/'native-operations.private',source_admission=admission_path)
  native=office.Runtime(spool,binding_path=self.binding_path,permit_path=permit_path,artifact_root=root/'native.private',mode='native')
  context=native.open(package,attempt_id='office-'+identity['task_id']);active=None;exit_started=False;sampler=None;trace=[];budget=None;outcome='actor_action_budget';raw_end=None;lifecycle=time.monotonic()
  def open_environment(_):
   nonlocal active
   active=context.__enter__()
   return {'status':'active','task_id':identity['task_id'],'package_sha256':identity['package_sha256'],'actual_native_account_lease':True,
    'lease_seconds':1200,'account_sha256':self.binding['account_principal_sha256'],'folder_scope_sha256':self.binding['folder_scope_sha256']}
  try:
   a=self.authority
   operation_prefix=a.started['attempt_id'] if a.started else getattr(a.session,'attempt_id','office-teacher-'+office.sha(str(root).encode())[:16]) if a.session else a.command['attempt_id']
   environment_request={'cell_id':a.cell,'selection_attempt':operation_prefix,
    **identity,'checkpoint_path_sha256':a.checkpoint,'phase':'actor_and_distinct_reset','lease_seconds':1200}
   if a.command is None:
    environment_id=environment_request['selection_attempt']+f'-office-{ordinal:03d}-native-account'
    a.session.dispatch_paid(attempt_id=environment_id,category='storage_application',work=environment_request,request=environment_request,
     reserve_usd=quote,resource_reservation={},provider=open_environment)
   else:
    from cursibench import full_study_final_dispatch_v1 as final_protocol
    environment_id=a.command['attempt_id'];office.write_new(root/'final-command.private.json',final_protocol.canonical(a.command))
    office.write_new(root/'environment.intent.private.json',office.canonical({'request_id':'environment','paid_attempt_id':environment_id,'same_request_replay_authorized':False,'request_sha256':office.sha(office.canonical(environment_request))}))
    environment_result=open_environment(environment_request);office.write_new(root/'environment.result.private.json',office.canonical(environment_result))
   started=time.monotonic();deadline=started+720;active.actor.bind_actor_clock(started,deadline)
   if a.teacher:
    office.require(callable(self.teacher_callback),'Authentic teacher callback required');sampler=TeacherSampler(authority=a,package=package,active=active,callback=self.teacher_callback,close_callback=self.teacher_close_callback,output=root/'sampler.private')
   else:sampler=self.sampler_factory(authority=a,package=package,active=active,output=root/'sampler.private',task_index=ordinal,quote=quote)
   sampler.bind_actor_clock(started,deadline)
   # Setup precedes observe so cold model initialization cannot age the
   # first150-second frame. It is still measured inside the actor clock.
   if callable(getattr(sampler,'start',None)):sampler.start()
   memory=''
   for step in range(90):
    if time.monotonic()>=deadline:outcome='actor_wall_budget';break
    try:
     observation=active.observe(memory=memory);response=sampler(observation)
    except ActorDeadlineReached as error:
     office.require(error.proof.actor_deadline_reached,'Earlier provider fault is not budget performance');budget=error.proof.receipt() if getattr(sampler,'proof',None) else None;outcome='actor_wall_budget';trace.append({'step':step,'status':'not_applied_actor_deadline','proof':error.proof.receipt()});break
    if time.monotonic()>=deadline:
     outcome='actor_wall_budget';trace.append({'step':step,'status':'completed_response_withheld_at_actor_deadline','frame_sha256':office.sha(observation.screenshot_bytes)});break
    try:action=normalize_model_action(response['text'],observation,current_frame_id=active.current_frame_id())
    except ContractError:
     try:result=active.reject_model_output(response['text'])
     except ActorDeadlineReached:outcome='actor_wall_budget';break
     trace.append({'step':step,'status':result['status'],'invalid_model_output':True,'frame_sha256':office.sha(observation.screenshot_bytes)});continue
    try:result=active.dispatch(action)
    except ActorDeadlineReached:outcome='actor_wall_budget';break
    trace.append({'step':step,'status':result['status'],'action':action,'frame_sha256':office.sha(observation.screenshot_bytes),'applied_before_deadline':time.monotonic()<=deadline})
    office.require(time.monotonic()<=deadline,'Native action completed after actor deadline')
    memory=action['memory']
    if action['type']=='finish' and result['status']=='applied':outcome='finished';break
   raw_end=time.monotonic();actor_seconds=min(raw_end-started,720) if outcome=='actor_wall_budget' else raw_end-started
   office.write_new(root/'actor-clock.private.json',office.canonical({'schema':'office-current-actor-clock-v4','started':started,'deadline':deadline,'raw_end':raw_end,
    'actor_seconds':actor_seconds,'model_outcome':outcome,'native_actions_after_deadline':0,'actor_deadline_epoch_ms':spool.actor_deadline_epoch_ms,'evaluation_outside_actor_clock':True}))
   sampler.close(True)
   exit_started=True;context.__exit__(None,None,None);active=None
   saved=json.loads(office.private(native.root/'saved-state-score.private.json'));reset=json.loads(office.private(native.root/'reset-score.private.json'))
   office.require(saved['score'] in (0,1) and reset['equivalent'] is True and not native.account_lease.path.exists(),'Actual independent saved score/fresh reset/owned cleanup required')
   office.write_new(root/'actions.private.json',office.canonical(trace))
   lifecycle_seconds=time.monotonic()-lifecycle;office.require(lifecycle_seconds<=1200,'Complete native/provider/readback/reset lifecycle exceeds1200 lease')
   result={**identity,'schema':'office-current-task-performance-v4','score':int(saved['score']),'raw_strict_saved_score':saved['score'],'model_outcome':outcome,
    'actor_seconds':actor_seconds,'lifecycle_seconds':lifecycle_seconds,'lifecycle_started':lifecycle,'lifecycle_ended':time.monotonic(),'actual_cost_usd':None,'invoice_complete':False,
    'saved_state_readback_verified':True,'fresh_reset_verified':True,'account_lease_released':True,'environment_paid_attempt_id':environment_id,
    'sampler_paid_attempt_ids':getattr(sampler,'paid',getattr(sampler,'records',[])),'actor_budget_proof':budget,'model_completion_unknown':bool(budget and not budget['model_completion_known']),
    'owner_slot':a.owner,'checkpoint_sha256':a.checkpoint,'amendment_sha256':a.study.amendment_sha256,'teacher':a.teacher,'native_evidence_root':self.binding['native_evidence_root']}
   result['paid_session_directory']=str(a.session.directory.resolve()) if a.session else None
   office.write_new(root/'task-result.private.json',office.canonical(result));return result,root
  except BaseException as error:
   office.write_new(root/'invalid.private.json',office.canonical({'status':'infrastructure_or_provider_invalid','error_class':type(error).__name__,'score_inferred':False,'request_replay_authorized':False}));raise
  finally:
   if sampler is not None and not getattr(sampler,'closed',False):sampler.close(False)
   if active is not None and not exit_started:exit_started=True;context.__exit__(None,None,None)
