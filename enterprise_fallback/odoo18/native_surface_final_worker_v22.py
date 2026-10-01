"""Actual witnessed-v22 Odoo final dispatch, source-only until qualified.

Uses unchanged native v13 actor/scorer/reset and authentic sampler journals.
The real 600-task/24-chain gate and already-reserved command remain mandatory.
"""
from __future__ import annotations
from decimal import Decimal
from hashlib import sha256
import json,os,time
from pathlib import Path
from types import FunctionType,SimpleNamespace
from cursibench import full_study_runtime_v2 as policy_runtime
from cursibench import full_study_final_dispatch_v1 as final
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from . import native_surface_final_worker_v1 as legacy
from . import native_surface_workers_v13 as workers
from .odoo_actor_model_modules_v1 import run_owned_task
from .odoo_actor_transport_v1 import attach_sampler_clock,known_token_total

ROOT=Path(__file__).resolve().parents[2]
CELL='odoo-community'
MODULE='enterprise_fallback.odoo18.native_surface_workers_v13'
require,digest,private,write=legacy.require,legacy.digest,legacy.private,legacy.write
runtime_gate=legacy.runtime_gate
_modules=legacy._modules
_worker_module=legacy._worker_module
module_from_binding=legacy.module_from_binding
OdooFinalWorkerError=legacy.OdooFinalWorkerError
FILES=('enterprise_fallback/odoo18/native_surface_final_worker_v22.py','tools/odoo_native_surface_final_v22.py',
 'enterprise_fallback/odoo18/native_surface_final_worker_v1.py','enterprise_fallback/odoo18/native_surface_budget_performance_v13.py',
 'src/cursibench/full_study_runtime_v2.py','src/cursibench/full_study_final_performance_v2.py')


def source_binding(native_worker_module=MODULE):
 require(native_worker_module==MODULE,'v22_current_v13_worker_required')
 value={'schema':'odoo-native-v22-final-source-binding-v1','native_worker_module':MODULE,
  'native_binding_sha256':workers.public_binding()['binding_sha256'],
  'source_sha256s':{n:digest((ROOT/n).read_bytes()) for n in FILES},'all_five_slots_same_source':True,
  'actual_v22_final_gate_required':True,'max_actions':90,'actor_seconds':720,'lifecycle_seconds':1200,
  'nominal_cost_is_not_actual_billing':True,'qualification_claimed':False}
 return {**value,'binding_sha256':digest(final.canonical(value))}


def study_source_snapshot(native_worker_module=MODULE):
 native=workers.public_binding();supplement=source_binding(native_worker_module)
 return {'schema':'odoo-native-v22-study-source-snapshot-v1','native_worker_binding_sha256':native['binding_sha256'],
  'v22_final_source_binding_sha256':supplement['binding_sha256'],
  'source_sha256s':{**native['source_sha256s'],**supplement['source_sha256s']}}


def _method(function):
 namespace=dict(function.__globals__)
 proxy=SimpleNamespace(**vars(final));proxy.FinalGate=policy_runtime.FinalGate
 namespace.update(final=proxy,source_binding=source_binding,study_source_snapshot=study_source_snapshot)
 cloned=FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
 cloned.__kwdefaults__=function.__kwdefaults__;return cloned


class MeteredSampler:
 """The actual whole-task paid ID is shared; request IDs are SDK journal IDs."""
 def __init__(self,delegate,episode,command):self.delegate=delegate;self.episode=episode;self.command=command;self.calls=[]
 def __getattr__(self,name):return getattr(self.delegate,name)
 def __enter__(self):self.delegate.__enter__();return self
 def __exit__(self,*args):return self.delegate.__exit__(*args)
 def sample(self,observation,**kwargs):
  attach_sampler_clock(self.delegate,self.actor_clock)
  request='odoo-sel-'+digest(self.delegate.attempt_id.encode())[:10]+f'-{kwargs["task_index"]:02d}-{kwargs["step"]:03d}'
  paid=self.command['attempt_id'];index=len(self.calls)
  intent=write(self.episode,f'final-sample-{index:03d}-intent.private.json',{'schema':'odoo-v22-actual-sample-intent-v1',
   'request_id':request,'paid_attempt_id':paid,'task_id':observation.task_id,'package_sha256':observation.task_binding_sha256,
   'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],'same_request_replay_authorized':False})
  call={'request_id':request,'paid_attempt_id':paid,'kind':'sample','intent':intent,'result':None,'provider_latency_ms':None}
  self.calls.append(call);began=time.monotonic()
  try:result=self.delegate.sample(observation,**kwargs)
  except ActorDeadlineReached:
   call['provider_latency_ms']=round((time.monotonic()-began)*1000);raise
  call['provider_latency_ms']=round((time.monotonic()-began)*1000)
  require(result.get('status')=='completed' and result.get('request_id')==request and
   result.get('new_dispatch') is True and result.get('reused') is False,'v22_actual_completed_sample_unproved')
  call['result']=write(self.episode,f'final-sample-{index:03d}-result.private.json',result)
  return {**result,'rendered_usage':result['usage'],'paid_attempt_id':paid}


class OdooNativeSurfaceFinalWorkerV22(legacy.OdooNativeSurfaceFinalWorker):
 _command=_method(legacy.OdooNativeSurfaceFinalWorker._command)
 run_once=_method(legacy.OdooNativeSurfaceFinalWorker.run_once)
 def __init__(self,**kwargs):
  require(type(kwargs.get('gate')) is policy_runtime.FinalGate,'real_witnessed_v22_final_gate_required')
  require(kwargs.get('native_worker_module',MODULE)==MODULE,'v22_current_v13_worker_required')
  kwargs['native_worker_module']=MODULE
  _method(legacy.OdooNativeSurfaceFinalWorker.__init__)(self,**kwargs)
 def _episode(self,command,output):
  _,selection=self.workers._model_modules(self.binding)
  training,_=self.gate.study.student_training_configuration()
  require(training['model']=='Qwen/Qwen3.8-27B' and Decimal(command['sampling']['temperature'])==0,'v22_frozen_sampler_changed')
  config={**training,'seed':command['sampling']['seed'],'sample_max_tokens':command['sampling']['max_output_tokens']}
  legacy.runtime_gate.pre_dispatch(repo_root=self.gate.study.repo_root,study_plan_sha256=self.gate.study.plan_sha256)
  require(bool(os.environ.get('TINKER_API_KEY')),'final_tinker_key_missing')
  began=time.monotonic();utc=int(time.time());episode=output/'native-episode';episode.mkdir(mode=0o700)
  identity={k:command[k] for k in ('task_id','package_sha256')}
  environment=legacy.environment_factory(selection,self.worker_dir,self.identities,self.binding)
  environment._native_readiness_sink=lambda value:write(episode,'db-readiness.private.json',value)
  environment.load_command_task(identity,episode)
  base=command['owner_slot']=='shared-base'
  actual=selection.RealTinkerSelectionSampler(checkpoint_path='Qwen/Qwen3.8-27B' if base else command['sampler_path'],
   config=config,output_root=episode,attempt_id=command['attempt_id'],base_mode=base,
   expected_base_checkpoint_sha256=command['checkpoint_sha256'] if base else None)
  metered=MeteredSampler(actual,episode,command);metered.parent_paid_attempt_id=command['attempt_id']
  row=run_owned_task(environment=environment,task=identity,index=0,sampler=metered,task_dir=episode,attempt_id=command['attempt_id'])
  require(time.monotonic()-began<=1200,'v22_owned_lifecycle_exceeded_1200')
  selection._audit_task_artifacts(episode,identity,row)
  self.workers.audit_readiness_receipt(episode/'db-readiness.private.json',self.binding,self.worker_dir)
  return self._outcome_v22(command,output,episode,row,environment,selection,metered,utc)
 def _outcome_v22(self,command,output,episode,row,environment,selection,metered,started_at):
  read=lambda name:json.loads(private(episode/name))
  saved=read('saved-state.private.json');reset=read('reset.private.json');baseline=read('baseline-semantic.private.json');restored=read('restored-semantic.private.json')
  require(reset['pre_database_filestore_exact'] is True and reset['post_database_filestore_exact'] is True and baseline==restored and
   digest(selection._canonical(baseline['business_snapshot']))==command['expected_initial_state_sha256'],'v22_saved_exact_reset_unproved')
  require(len(environment.proofs)>=2,'v22_saved_independent_proof_missing')
  proof=read(environment.proofs[-1]['path']);require(proof['observed']==saved['business_snapshot'] and proof['context']==environment.proof_context,'v22_saved_score_readback_changed')
  verify=legacy._modules(self.worker_dir,self.binding)[3];context=proof['context']
  verdict=legacy._evaluate(context['family'],command['task_id'],context['target'],context['baseline'],saved['business_snapshot'],
   proof['physical_files'],context['frozen_files'],proof['attachment_paths'],verify)
  score=int(verdict['reward']==1.0 and verdict['checks_passed'] is True and not verdict['difference_codes'])
  require(verdict==proof['verdict'] and score==row['score'],'v22_independent_saved_verdict_changed')
  clock=read(row['actor_clock_ref']['path']);life=read(row['owned_complete_lifecycle_ref']['path']);close=read(row['provider_close_ref']['path'])
  require(clock['native_actions_after_deadline']==0 and clock['evaluation_outside_actor_clock'] is True and clock['actor_elapsed_seconds']<=720 and
   life['saved_readback_reset_and_provider_close_complete'] is True and life['ended_monotonic']-life['started_monotonic']<=1200 and
   close['status']=='acknowledged' and close['real_close_call_returned'] is True,'v22_actual_actor_lifecycle_close_unproved')
  usage=read('usage.private.json');samples=usage['samples'];frames=read('frames.private.json');actions=read('actions.private.json')
  require(samples and len(samples)==len(metered.calls),'v22_actual_paid_sample_coverage_missing')
  unknown=[s for s in samples if s['status']=='actor_deadline_proven'];require(len(unknown)<=1,'v22_single_terminal_budget_stop_required')
  calls=[]
  for call in metered.calls:
   calls.append({k:({'path':'native-episode/'+v['path'],'sha256':v['sha256']} if k in ('intent','result') and v is not None else v)
    for k,v in call.items() if k!='provider_latency_ms'})
  usage_ref=write(output,'usage.private.json',{'schema':'cua-full-study-authentic-unknown-usage-v2','attempt_id':command['attempt_id'],
   'cost_basis':'authentic_usage_unknown','cost_usd':None,'input_tokens':known_token_total(samples,'input_tokens'),
   'image_tokens':known_token_total(samples,'image_tokens'),'output_tokens':known_token_total(samples,'output_tokens'),
   'provider_billed_tokens':None,'provider_invoice_sha256':None,'paid_calls':calls})
  clock_ms=round(clock['actor_elapsed_seconds']*1000);life_ms=round((life['ended_monotonic']-life['started_monotonic'])*1000)
  clock_ref=write(output,'actor-clock.private.json',{'schema':'cua-full-study-final-actor-clock-v2','attempt_id':command['attempt_id'],
   'max_actions':90,'actor_seconds_limit':720,'lease_seconds_limit':1200,'actor_wall_time_ms':clock_ms,'lifecycle_wall_time_ms':life_ms,
   'native_actions_after_deadline':0,'evaluation_outside_actor_clock':True,'raw_actor_clock':final.reference(output,episode/row['actor_clock_ref']['path'])})
  budget=None
  if unknown:
   write(episode,'native-binding.private.json',self.binding)
   write(episode,'task.private.json',{'attempt_id':command['attempt_id'],'task_id':command['task_id'],'package_sha256':command['package_sha256'],
    'owner_slot':command['owner_slot'],'checkpoint_sha256':command['checkpoint_sha256'],'amendment_sha256':self.gate.study.amendment_sha256})
   write(episode,'native-row.private.json',row)
   from . import native_surface_budget_performance_v13 as reader
   def ref(path):return final.reference(episode,episode/path)
   arguments={'schema':'odoo-budget-performance-input-v13','cell_id':CELL,'episode_root':str(episode),
    'native_binding':ref('native-binding.private.json'),'task':ref('task.private.json'),'native_row':ref('native-row.private.json'),
    'live_saved_proof':ref(environment.proofs[-1]['path']),'provider_close':ref(row['provider_close_ref']['path']),'lifecycle':ref(row['owned_complete_lifecycle_ref']['path']),
    'actor_clock':ref(row['actor_clock_ref']['path']),'actor_budget_stop':ref('actor-clock/budget-stop.private.json'),'sample_paid_attempt_id':command['attempt_id']}
   descriptor={'adapter':{'module':reader.__name__,'function':'verify_budget_performance','source_sha256':digest(Path(reader.__file__).read_bytes())},'arguments':arguments}
   checked=policy_runtime.verify_budget_artifacts(self.gate.study,command['owner_slot'],descriptor)
   budget=write(output,'budget-performance.private.json',{'receipt':checked,'verification':descriptor})
  saved_ref=final.reference(output,episode/'saved-state.private.json')
  reset_ref=write(output,'cold-reset.private.json',{'schema':final.RESET_SCHEMA,'task_id':command['task_id'],'package_sha256':command['package_sha256'],
   'attempt_id':command['attempt_id'],'fresh_environment':True,'restored_after_attempt':True,
   'initial_state_sha256':command['expected_initial_state_sha256'],'restored_state_sha256':command['expected_initial_state_sha256']})
  verifier_ref=write(output,'independent-verifier.private.json',{'schema':final.VERIFIER_SCHEMA,'task_id':command['task_id'],'package_sha256':command['package_sha256'],
   'attempt_id':command['attempt_id'],'saved_state_sha256':saved_ref['sha256'],'score':score,'no_regression_checked':True,
   'no_regression_passed':bool(verdict['checks_passed']),'independent_of_actor':True,'gold_withheld_from_actor':True})
  count=sum(a['native_dispatch_status']=='applied' for a in actions)
  obs_ref=write(output,'observations.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],'kind':'observations','action_profile':'scale-action-profile-v0.6.6','count':len(frames),'screenshot_only':True})
  act_ref=write(output,'actions.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],'kind':'actions','action_profile':'scale-action-profile-v0.6.6','count':count,'current_frame_validated':True})
  return {'schema':final.OUTCOME_SCHEMA,'status':'scored','score':score,'failure_type':None,'started_at':started_at,'finished_at':int(time.time()),
   'cost_basis':'authentic_usage_unknown','cost_usd':None,'usage':usage_ref,'reset':reset_ref,'saved_state':saved_ref,'verifier':verifier_ref,
   'observation_trace':obs_ref,'action_trace':act_ref,'action_count':count,'turn_count':len(frames),'wall_time_ms':clock_ms,
   'provider_latency_ms':sum(c['provider_latency_ms'] for c in metered.calls),'timeout_subtype':{'task_action_budget':'actor_action_budget','task_wall_budget':'actor_wall_budget'}.get(row['termination'],'none'),
   'action_profile':'scale-action-profile-v0.6.6','actor_clock':clock_ref,'lifecycle_wall_time_ms':life_ms,'budget_performance':budget}


def final_worker_factory(**kwargs):return OdooNativeSurfaceFinalWorkerV22(**kwargs)
