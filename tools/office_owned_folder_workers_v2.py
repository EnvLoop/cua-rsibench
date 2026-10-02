"""Truthful shared-base/TrustedFinalWorker seam for single-account Office.

Workers cannot report live readiness until the whole native lifecycle, generic
scorer and shared safety source have independent accepted qualification.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict
import json,time
from tools.office_owned_folder_runtime_v2 import Runtime,Package,require,source_hashes,sha,canonical,private,write_new
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_output_v066 import normalize_model_action
from cursibench.scale_action_contract import ContractError
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached

class OfficeOwnedFolderTaskWorker:
 def __init__(self,*,runtime_factory,package_loader,sampler,enable_live=False):
  self.runtime_factory,self.package_loader,self.sampler=runtime_factory,package_loader,sampler;self.enable_live=enable_live
 def run_task(self,identity,*,output_root,attempt_id,max_actions,max_wall_seconds):
  require(self.enable_live is True,'Office native execution requires exact qualification/source review')
  package=self.package_loader(identity);require(type(package) is Package and package.actor.task_id==identity['task_id'] and package.binding_sha256==identity['package_sha256'],
   'Opaque Office task/package identity changed')
  runtime=self.runtime_factory(output_root);lifecycle_started=time.monotonic();trace=[];saved=None;terminal_reason='none';actor_elapsed=0
  with runtime.open(package,attempt_id=attempt_id) as active:
   memory='';started=time.monotonic()
   if callable(getattr(self.sampler,'bind_actor_clock',None)):self.sampler.bind_actor_clock(started_monotonic=started,deadline_monotonic=started+max_wall_seconds)
   for step in range(max_actions):
    if time.monotonic()-started>=max_wall_seconds:terminal_reason='actor_wall_budget';break
    observation=active.observe(memory=memory)
    try:response=self.sampler(observation)
    except ActorDeadlineReached:
     terminal_reason='actor_wall_budget';break
    try:action=normalize_model_action(response['text'],observation,current_frame_id=active.current_frame_id())
    except ContractError:
     result=active.reject_model_output(response['text']);trace.append({'step':step,'action_sha256':sha(response['text'].encode()),'driver_status':result['status'],'contract_valid':False});continue
    result=active.dispatch(action);trace.append({'step':step,'action_sha256':sha(canonical(action)),'driver_status':result['status']})
    memory=action['memory']
    if action['type']=='finish' and result['status']=='applied':saved=active.read_saved_state();break
   else:terminal_reason='actor_action_budget'
   actor_elapsed=time.monotonic()-started
   if saved is None:saved=active.read_saved_state()
   if callable(getattr(self.sampler,'close',None)):self.sampler.close(success=True)
  require(saved is not None and runtime.root.joinpath('reset-score.private.json').is_file(),'Office saved readback/reset missing')
  require(saved['score'] in [0.0,1.0],'Office source/scorer failure must remain infrastructure outcome')
  receipt={'schema':'office-owned-folder-task-execution-v2','task_id':identity['task_id'],'package_sha256':identity['package_sha256'],
   'score':int(saved['score']) if terminal_reason=='none' else 0,'timeout_subtype':terminal_reason,'raw_strict_score':saved['score'],'native_metadata_normalization_applied':False,'development_only':runtime.mode=='native_development','official_final_credit':0,'native_policy_sha256':policy.POLICY_SHA,
   'saved_state_readback':True,'fresh_native_reset_verified':True,'trace':trace,'wall_ms':int(actor_elapsed*1000),'lifecycle_wall_ms':int((time.monotonic()-lifecycle_started)*1000)}
  write_new(runtime.root/'task-result.private.json',canonical(receipt));return receipt

class OfficeTrustedFinalWorker:
 """A truthful protocol object; missing qualification fails before paid work."""
 def __init__(self,*,cell_id,gate,task_worker,qualification_path,expected_qualification_sha256,bindings,execution_factory=None,outcome_adapter=None):
  from tools.office_owned_folder_paid_sampler_v2 import _formal_types
  formal_runtime=_formal_types()
  require(cell_id in ['powerpoint-web','excel-web'] and type(gate) is formal_runtime.FinalGate,'Real v22 six-cell/all24-chain FinalGate required')
  raw=private(qualification_path);require(sha(raw)==expected_qualification_sha256,'Office qualification receipt changed')
  qualification=json.loads(raw)
  require(qualification.get('schema')=='office-owned-folder-formal-qualification-v2' and qualification.get('accepted') is True and
   qualification.get('native_lifecycle_qualified') is True and qualification.get('generic_saved_scorer_qualified') is True and
   qualification.get('native_policy_sha256')==policy.POLICY_SHA and qualification.get('source_sha256s')==source_hashes(),
   'Office formal native lifecycle/generic scorer remain unqualified')
  self.cell_id,self.gate,self.worker,self.bindings=cell_id,gate,task_worker,bindings
  self.execution_factory,self.outcome_adapter=execution_factory,outcome_adapter
  self._identity={'schema':final.WORKER_SCHEMA,'cell_id':cell_id,'source_snapshot_sha256':bindings['source_snapshot'],
   'runtime_sha256':bindings['runtime'],'action_contract_sha256':bindings['action_contract'],'verifier_sha256':bindings['verifier'],
   'adapter_source_sha256':bindings['adapter'],'action_profile':'scale-action-profile-v0.6.6','observation_kind':'screenshot',
   'actor_capability':'current_frame_gui_actions_only','evaluator_isolated':True,'cold_reset_supported':True,'saved_state_readback_supported':True}
 @property
 def identity(self):return dict(self._identity)
 def run_once(self,command,output_dir):
  require(callable(self.execution_factory) and callable(self.outcome_adapter),'Final paid-envelope/outcome evidence adapter must be source-bound before publication')
  require(command.get('schema')==final.COMMAND_SCHEMA and command.get('cell_id')==self.cell_id and command.get('action_profile')=='scale-action-profile-v0.6.6' and
   int(time.time())>self.gate.last_selection_frozen_at,'Exact prospective final command/selection freeze required')
  # FinalDispatcher owns reservation, append-only intent and no-replay. A
  # source-bound factory selects this command's actual sampler; no global
  # default sampler or synthetic provider usage is substituted here.
  worker=self.execution_factory(command);require(type(worker) is OfficeOwnedFolderTaskWorker,'Uniform owned-folder task worker required')
  write_new(Path(output_dir)/'office-final-command.private.json',canonical(command))
  result=worker.run_task({'task_id':command['task_id'],'package_sha256':command['package_sha256']},output_root=Path(output_dir)/'owned-office-runtime.private',
   attempt_id=command['attempt_id'],max_actions=command['max_actions'],max_wall_seconds=command['max_wall_seconds'])
  outcome=self.outcome_adapter(command,result,Path(output_dir))
  require(type(outcome) is dict and outcome.get('schema')==final.OUTCOME_SCHEMA,'Actual usage/reset/trace/final outcome adapter required')
  return outcome

def run_shared_base20(*,task_worker,identities,output_root,checkpoint_sha256,base_freeze_sha256,coverage_session=None):
 require(len(identities)==20 and len({r['task_id'] for r in identities})==20,'Exactly frozen Office20 shared-base identities required')
 require(checkpoint_sha256 and base_freeze_sha256,'Real shared-base sampler freeze required')
 require(coverage_session is not None and callable(getattr(coverage_session,'run_owned_office_once',None)) and coverage_session.checkpoint_sha256==checkpoint_sha256 and
  coverage_session.base_freeze_sha256==base_freeze_sha256,'Shared-base paid reservation/coverage session must be source-bound before native model dispatch')
 root=Path(output_root);root.mkdir(mode=0o700,exist_ok=False)
 write_new(root/'shared-base20-intent.private.json',canonical({'identities':identities,'checkpoint_sha256':checkpoint_sha256,'base_freeze_sha256':base_freeze_sha256,'one_use':True}))
 outcomes=[]
 for ordinal,identity in enumerate(identities):
  # The paid session owns reservation, actual usage reconciliation and durable
  # no-replay. All twenty use the same task worker/native reset/strict scorer.
  result=coverage_session.run_owned_office_once(task_worker,identity,root,ordinal)
  require(type(result) is dict and result.get('task_id')==identity['task_id'] and result.get('package_sha256')==identity['package_sha256'],'Shared-base actual coverage receipt changed task')
  write_new(root/f'coverage-{ordinal:02d}.private.json',canonical(result));outcomes.append(result)
 return outcomes
