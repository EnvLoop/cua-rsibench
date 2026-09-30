"""Executable common Desktop model worker for base/selected selection/final.

No evaluator script can become a model action. Task gold is opened only by the
trusted package loader after current120 admissions plus the six-cell public
freeze. Every create/sample has a durable intent and cannot be replayed.
"""
from __future__ import annotations

import base64
from decimal import Decimal,ROUND_CEILING
import importlib.metadata
import json
from pathlib import Path
import time

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_matrix_v1 as matrix
from cursibench import full_study_selection_paid_coverage_v1 as coverage
from cursibench import full_study_shared_base_execution_v1 as base_execution
from cursibench import scale_action_output_v066 as output
from cursibench.scale_action_contract import ContractError
from . import admit
from . import model_transport_integration_v11 as integration
from . import uniform_model_transport_v11 as transport
from . import post_enter_component_v19 as transport_audit
from . import v066_day_rollover_attrition_audit_v4 as caret_audit
from .factory import digest
from .official_saved_verifier import verify_official
from .v066_storage_budget import reserve_and_write,audit as storage_audit


def write(path:Path,value):
 integration.controls.accounting._write_new(path,value)
 return {'path':path.name,'sha256':digest(path.read_bytes())}


def sample_quote(training:dict,max_output:int):
 value=(Decimal(32768)*Decimal(training['prefill_usd_per_million_tokens'])+
        Decimal(max_output)*Decimal(training['sample_usd_per_million_tokens']))/Decimal(1_000_000)
 value*=Decimal(training['billing_multiplier_upper'])
 integration.require(value.is_finite() and value>0,'v11_sample_quote_invalid')
 return str(value.quantize(Decimal('0.000000001'),rounding=ROUND_CEILING))


def no_regression_passed(fair):
 """Target correctness and protected-content preservation are separate facts."""
 target_errors=('target_formula_wrong:','target_cached_result_wrong:',
                'target_cached_result_missing:','target_text_wrong:')
 return all(error.startswith(target_errors) for error in fair['errors'])


class PaidCalls:
 """Campaign/shared-base reserve callbacks; final uses its parent reservation."""
 def __init__(self,*,attempt_id:str,checkpoint:str,identities:list,output_dir:Path,
              runtime:str,quote:str,session=None,final_reserve:str|None=None,study=None):
  self.attempt_id=attempt_id;self.checkpoint=checkpoint;self.identities=identities
  self.root=output_dir;self.runtime=runtime;self.quote=quote;self.session=session
  self.reserve=Decimal(final_reserve) if final_reserve is not None else None
  self.study=session.study if session is not None else study
  integration.require(self.reserve is None or self.reserve>=Decimal('0.666666668')+91*Decimal(quote),
                      'v11_full_final_episode_reservation_required_before_setup')
  self.reserved=Decimal(0);self.ids=[];self.calls=[];self.usage=[];self.sample_latency_seconds=0
  (self.root/'paid').mkdir(mode=0o700)

 def invoke(self,*,suffix:str,category:str,request:dict,provider,identity=None):
  paid_id=self.attempt_id+'-'+suffix
  request={'schema':'cua-full-study-selection-sampling-request-v1' if category=='tinker' else 'cua-native-desktop-v11-e2b-lease',
   'cell_id':'desktop-native','selection_attempt':self.attempt_id,
   'checkpoint_path_sha256':self.checkpoint,'worker_runtime_sha256':self.runtime,
   **({'selection_identities_sha256':digest(integration.canonical(self.identities))} if identity is None else
      {'task_id':identity['task_id'],'package_sha256':identity['package_sha256']}),**request}
  reserve='0.333333334' if category=='e2b' else self.quote
  intent=self.root/'paid'/(paid_id+'.intent.private.json')
  integration.require(not intent.exists() and not intent.is_symlink(),'v11_paid_intent_consumed_no_replay')
  self.reserved+=Decimal(reserve)
  integration.require(self.reserve is None or self.reserved<=self.reserve,'v11_final_reservation_exhausted_before_dispatch')
  write(intent,{'schema':'cua-native-desktop-v11-paid-intent','attempt_id':paid_id,'category':category,
                'reserve_usd':reserve,'request_sha256':digest(integration.canonical(request)),
                'lease_seconds':1200 if category=='e2b' else None,'same_intent_replay_authorized':False})
  write(self.root/'paid'/(paid_id+'.request.private.json'),request)
  def checked_provider(actual):
   integration.require(actual==request,'v11_paid_request_changed')
   write(self.root/'paid'/(paid_id+'.dispatched.private.json'),{'intent_sha256':digest(intent.read_bytes())})
   return provider(actual)
  if self.session is not None:
   resources={'e2b_sandbox_hours':'0.333333334','e2b_peak_concurrency':'1'} if category=='e2b' else {}
   paid=self.session.dispatch_paid(attempt_id=paid_id,category=category,work=request,request=request,
                                  reserve_usd=reserve,resource_reservation=resources,provider=checked_provider)
   result=paid['result'];result_sha=paid['result_sha256']
  else:
   if category=='tinker':
    from cursibench.full_study_qwen_runtime_gate_v1 import pre_dispatch
    pre_dispatch(repo_root=self.study.repo_root,study_plan_sha256=self.study.plan_sha256)
   result=checked_provider(request);result_sha=digest(integration.canonical(result))
  write(self.root/'paid'/(paid_id+'.result.private.json'),result)
  self.ids.append(paid_id)
  self.calls.append({'attempt_id':paid_id,'category':category,'request':request,
                    'result_present':True,'result_status':result.get('status')})
  if category=='tinker' and identity is not None:
   self.usage.append(result['usage']);self.sample_latency_seconds+=result['elapsed_seconds']
  return result,result_sha,paid_id


class DesktopProspectiveModelWorker:
 cell_id='desktop-native'
 def __init__(self,*,study,admissions_path:Path,proposal_path:Path,enable_live:bool=False,final_gate=None):
  self.study=study;self.admissions_path=admissions_path;self.proposal_path=proposal_path;self.enable_live=enable_live
  self.final_gate=final_gate

 @property
 def identity(self):
  integration.require(type(self.study) is campaign.FrozenStudy,'v11_real_frozen_study_required')
  bindings=next(r for r in self.study.plan['cells'] if r['cell_id']==self.cell_id)['matched_bindings']
  return {'schema':final.WORKER_SCHEMA,'cell_id':self.cell_id,
   'source_snapshot_sha256':bindings['source_snapshot'],'runtime_sha256':integration.proposal()['worker_runtime_sha256'],
   'action_contract_sha256':bindings['action_contract'],'verifier_sha256':integration.proposal()['verifier_sha256'],
   'adapter_source_sha256':integration.proposal()['adapter_source_sha256'],'action_profile':'scale-action-profile-v0.6.6',
   'observation_kind':'screenshot','actor_capability':'current_frame_gui_actions_only','evaluator_isolated':True,
   'cold_reset_supported':True,'saved_state_readback_supported':True}

 def _gate(self):
  integration.require(self.enable_live is True,'v11_model_dispatch_disabled_before_private_read')
  admitted=integration.bind_frozen_study(self.study,admissions_path=self.admissions_path,proposal_path=self.proposal_path)
  versions={'e2b-desktop':'2.2.0','e2b':'2.51.0','Pillow':'11.3.0'}
  integration.require({k:importlib.metadata.version(k) for k in versions}==versions,'v11_pinned_native_model_runtime_missing')
  return admitted

 def _policy(self):
  cell=next(r for r in self.study.plan['cells'] if r['cell_id']==self.cell_id)
  training,_sha=self.study.student_training_configuration()
  sampling=cell['sampling']
  integration.require(training['model']==matrix.STUDENT and training['action_profile']=='scale-action-profile-v0.6.6' and
    Decimal(str(sampling['temperature']))==0 and 0<sampling['max_output_tokens']<=training['sample_max_tokens']<=4096 and
    Decimal(str(training['billing_multiplier_upper']))>=1,'v11_clean_model_policy_changed')
  return cell,training,sampling,sample_quote(training,sampling['max_output_tokens'])

 def _packages(self,admitted,identities,split):
  # First metadata-match the entire requested view; only then open its gold.
  selected=[r for r in admitted['roster'] if r['split']==split]
  expected=[{k:r[k] for k in ['task_id','package_sha256']} for r in selected]
  observed=[{k:r[k] for k in ['task_id','package_sha256']} for r in identities]
  integration.require(observed==expected if split=='selection' else len(observed)==1 and observed[0] in expected,
                      'v11_task_view_not_current_admitted_split')
  root=Path(admitted['candidate_root']);inventory=json.loads(integration.controls.private(root/'candidate-inventory.json'))
  by_id={r['task_id']:r for r in inventory['tasks']};packages=[]
  for identity in identities:
   row=by_id[identity['task_id']]
   integration.require(row['split']==split and row['package_sha256']==identity['package_sha256'],'v11_package_binding_changed')
   directory,source,oracle=admit._package(root,row)
   filename=next(p.name for p in directory.iterdir() if p.suffix in ['.xlsx','.pptx','.docx'])
   packages.append({'identity':{k:identity[k] for k in ['task_id','package_sha256']},'source':source,'oracle':oracle,
                    'filename':filename,'instruction':(directory/'actor_task.txt').read_text(),
                    'guest_reference_path':admitted['guest_public']})
  return packages

 def _create(self,*,paid:PaidCalls,package:dict,ordinal:int,phase:str,gui_root:Path):
  out=gui_root/package['identity']['task_id']/phase;out.mkdir(parents=True,mode=0o700)
  guest=None
  def provider(request):
   nonlocal guest
   from .reconcile_interrupted_sweep import active_hashes
   active,count=active_hashes()
   integration.require(not active and count==0,'v11_create_requires_active_zero')
   guest=transport.create_guest(root=gui_root,out=out,filename=package['filename'])
   return {'status':'active','sandbox_id_sha256':digest(guest.sandbox.sandbox_id.encode()),'lease_seconds':1200}
  try:
   paid.invoke(suffix=f'e2b-{ordinal:03d}-{phase}',category='e2b',identity=package['identity'],
               request={'phase':phase,'lease_seconds':1200},provider=provider)
  except BaseException:
   if guest is not None:guest.close()
   raise
  return guest

 def _episode(self,*,admitted,package:dict,ordinal:int,batch:Path,paid:PaidCalls,sampler:transport.ModelSampler):
  package={**package,'guest_reference_path':admitted['guest_public']}
  gui_root=batch/'gui';gui_root.mkdir(mode=0o700,exist_ok=True)
  out=gui_root/package['identity']['task_id']/'evaluator';out.mkdir(parents=True,mode=0o700)
  identity=package['identity'];source=package['source'];actor=None;reset=None
  guest_ref=json.loads(Path(admitted['guest_public']).read_bytes());reference=Path(admitted['scoped_reference'])
  salt=json.loads(integration.controls.private(Path(admitted['private_map'])))['variant_salt']
  trace=[];actions=[];actor_started=None;model_outcome='actor_action_budget';finished=False
  try:
   actor=self._create(paid=paid,package=package,ordinal=ordinal,phase='actor',gui_root=gui_root)
   actor.prepare(source=source,guest_reference=guest_ref,profile_reference=reference)
   actor_started=time.monotonic();deadline=actor_started+720;previous=None;memory=''
   for step in range(90):
    remaining=deadline-time.monotonic()
    if remaining<1:model_outcome='actor_wall_budget';break
    observation=actor.observe(identity=identity,instruction=package['instruction'],step=step,previous=previous,memory=memory)
    sampled_ref=reserve_and_write(gui_root,actor.out/f'sampled-{step:02d}.png',observation.screenshot_bytes)
    rendered=output.render_for_model(observation)
    request={'step':step,'frame_sha256':digest(observation.screenshot_bytes),
      'image_base64':base64.b64encode(rendered['image_bytes']).decode(),'instruction':rendered['instruction'],
      'visible_text':rendered['visible_text'],'sampling_kind':sampler.backend.identity['sampling_kind']}
    def provider(_request):
     return sampler.sample(observation=observation,request_id=paid.attempt_id+f'-{ordinal:03d}-{step:03d}',
                           task_dir=out,remaining_seconds=deadline-time.monotonic())
    result,result_sha,paid_id=paid.invoke(suffix=f'sample-{ordinal:03d}-{step:03d}',category='tinker',
                                        identity=identity,request=request,provider=provider)
    entry={'step':step,'sampled_frame':sampled_ref,'model_result_sha256':result_sha,'paid_attempt_id':paid_id,
           'model_text_sha256':digest(result['text'].encode()),'model_error_code':None}
    try:action,evidence=actor.dispatch_model(result['text'],observation,actor_deadline=deadline)
    except transport.strict.MaterialFrameDrift:raise
    except TimeoutError:model_outcome='actor_wall_budget';trace.append(entry);break
    except ContractError as exc:
     entry['model_error_code']=exc.code;model_outcome='model_invalid_action';trace.append(entry);break
    entry.update(evidence);entry['action_payload_sha256']=digest(result['text'].encode())
    entry['action']=action;entry['status']='applied';trace.append(entry);actions.append(action)
    write(out/f'step-{step:02d}.private.json',entry)
    if action['type']=='finish':finished=True;model_outcome='finished';break
    memory=action['memory'];previous={'status':'applied','code':'ok'}
   actor_elapsed=time.monotonic()-actor_started
   saved=actor.read_saved();saved_path=out/('saved'+Path(package['filename']).suffix)
   reserve_and_write(gui_root,saved_path,saved)
   fair=verify_official(source,saved,package['oracle'],private_salt=salt)
   score=int(finished and fair['passed'] is True and actor_elapsed<=720)
   actor.receipt.update({'task_id':identity['task_id'],'attempt':'actor',
    'actor_steps':[r for r in trace if r.get('status')=='applied'],
    'physical_frame_resamples':[retry for r in trace for retry in r.get('caret_resamples',[])],
    'post_enter_windows':actor.proxy.enter_count,'max_actor_actions':90,'max_actor_wall_seconds':720,
    'actor_elapsed_seconds':actor_elapsed,'model_outcome':model_outcome})
   actor.persist()
   integration.require(actor.close() is True,'v11_actor_cleanup_uncertain')
   reset=self._create(paid=paid,package=package,ordinal=ordinal,phase='reset',gui_root=gui_root)
   integration.require(reset.sandbox.sandbox_id!=actor.sandbox.sandbox_id,'v11_reset_reused_guest')
   reset.prepare(source=source,guest_reference=guest_ref,profile_reference=reference)
   restored=reset.read_saved();integration.require(restored==source,'v11_fresh_reset_original_bytes_changed')
   reserve_and_write(gui_root,reset.out/'cold-open.png',bytes(reset.sandbox.screenshot()))
   reserve_and_write(gui_root,out/('restored'+Path(package['filename']).suffix),restored)
   integration.require(reset.close() is True,'v11_reset_cleanup_uncertain')
   state=write(out/'saved-state.private.json',{'schema':'cua-native-desktop-v11-model-saved-state',**identity,
    'saved_artifact_sha256':digest(saved),'saved_artifact_ref':{'path':saved_path.name,'sha256':digest(saved)},
    'input_sha256':digest(source),'readback_performed':True,'native_save_observed':saved!=source})
   verify=write(out/'verifier.private.json',{'schema':'cua-native-desktop-v11-model-verifier',**identity,'score':score,
    'fair_result':fair,'verifier_sha256':integration.proposal()['verifier_sha256'],'independent_of_actor':True,'gold_withheld_from_actor':True})
   reset_ref=write(out/'reset.private.json',{'schema':'cua-native-desktop-v11-model-cold-reset',**identity,
    'fresh_environment':True,'state_equivalence_pass':True,'initial_state_sha256':digest(source),'restored_state_sha256':digest(restored),
    'actor_guest_sha256':actor.receipt['sandbox_id_sha256'],'reset_guest_sha256':reset.receipt['sandbox_id_sha256'],
    'actor_terminated':actor.killed,'reset_terminated':reset.killed})
   write(out/'actions.private.json',trace)
   result={**identity,'score':score,'saved_state_sha256':state['sha256'],
    'verifier_receipt_sha256':verify['sha256'],'reset_receipt_sha256':reset_ref['sha256']}
   write(out/'task.private.json',{**result,'ordinal':ordinal,'model_outcome':model_outcome,'action_count':len(actions),
    'turn_count':len(trace),'actor_elapsed_seconds':actor_elapsed,'saved_file':saved_path.name,
    'actor_dir':str(actor.out.relative_to(batch)),'reset_dir':str(reset.out.relative_to(batch)),
    'post_enter_windows':actor.proxy.enter_count})
   self._audit_episode(batch=batch,out=out,package=package,salt=salt,actions=actions)
   return result,out,trace,actor_elapsed,model_outcome
  finally:
   for guest in [actor,reset]:
    if guest is not None and not guest.killed:
     integration.require(guest.close() is True,'v11_cleanup_unverified_stop')

 def _audit_episode(self,*,batch:Path,out:Path,package:dict,salt:str,actions:list):
  task=json.loads(integration.controls.private(out/'task.private.json'))
  saved=(out/task['saved_file']).read_bytes();verification=json.loads(integration.controls.private(out/'verifier.private.json'))
  independent=verify_official(package['source'],saved,package['oracle'],private_salt=salt)
  integration.require(verification['fair_result']==independent and verification['score']==task['score'],
                      'v11_independent_saved_score_changed')
  reset=json.loads(integration.controls.private(out/'reset.private.json'))
  integration.require(reset['actor_guest_sha256']!=reset['reset_guest_sha256'] and reset['actor_terminated'] is reset['reset_terminated'] is True and
    reset['initial_state_sha256']==reset['restored_state_sha256']==digest(package['source']),'v11_cold_reset_audit_failed')
  gui=batch/'gui';actor=gui/Path(task['actor_dir']).relative_to('gui')
  receipt=json.loads(integration.controls.private(actor/'guest.private.json'))
  command=json.loads(integration.controls.private(actor/'guest-probe-command-v16.private.json'))
  transport.runtime_policy.verify(json.loads(command['stdout']), (actor/'guest-content-files-v16.jsonl.gz').read_bytes(),
                                 json.loads(Path(package['guest_reference_path']).read_bytes()))
  trace=json.loads(integration.controls.private(out/'actions.private.json'))
  transport.audit_model_readiness(gui,actor,actions,trace)
  transport_audit.post_enter_samples(gui,actor,actions,receipt)
  caret_audit._guard_frames(gui,receipt)
  integration.require(storage_audit(gui,verify_all_bytes=True)['unresolved_write_count']==0,'v11_raw_frame_bytes_unresolved')

 def _run_selection(self,*,session,started:dict,checkpoint_path:str|None,out_dir:Path,base:bool):
  admitted=self._gate();cell,training,sampling,quote=self._policy()
  expected_type=base_execution.SharedBaseSession if base else campaign.CampaignSession
  integration.require(type(session) is expected_type and session.study is self.study and session.intent['cell_id']==self.cell_id,
                      'v11_real_matched_selection_session_required')
  session._check_time();identities=list(self.study.task_views(self.cell_id)['selection'])
  integration.require(started['selection_tasks']==identities and started['task_count']==20 and
   started['selection_identities_sha256']==digest(integration.canonical(identities)),'v11_selection_start_view_changed')
  checkpoint=started['checkpoint_path_sha256']
  if base:
   integration.require(checkpoint_path is None and checkpoint==integration.proposal()['base_checkpoint_sha256'],'v11_base_sampler_not_frozen')
  else:
   integration.require(session.intent['researcher_id'] in matrix.RESEARCHERS and type(checkpoint_path) is str and
    digest(checkpoint_path.encode())==checkpoint,'v11_selected_checkpoint_not_exact')
   events=[r for r in session._events('selection_started') if r['data'].get('attempt_id')==started['attempt_id']]
   integration.require(len(events)==1 and events[0]['data']['checkpoint_path_sha256']==checkpoint,'v11_one_selection_started_event_required')
   found=[r for r in session._events('tinker_checkpoint') if r['data'].get('checkpoint_path_sha256')==checkpoint]
   integration.require(len(found)==1 and session._checkpoint_result(found[0])['sampler_path']==checkpoint_path,
                       'v11_selected_sampler_not_checkpoint_lineage')
  integration.require(not out_dir.exists() and not out_dir.is_symlink(),'v11_selection_root_consumed_no_replay')
  packages=self._packages(admitted,identities,'selection');out_dir.mkdir(parents=True,mode=0o700)
  write(out_dir/'started.private.json',{'schema':'cua-native-desktop-v11-model-batch-started','checkpoint':checkpoint,
    'source_runtime_sha256':integration.proposal()['worker_runtime_sha256'],'same_intent_replay_authorized':False})
  paid=PaidCalls(attempt_id=started['attempt_id'],checkpoint=checkpoint,identities=identities,output_dir=out_dir,
                 runtime=integration.proposal()['worker_runtime_sha256'],quote=quote,session=session)
  sampler=transport.ModelSampler(repo_root=self.study.repo_root,journal_root=out_dir/'sampler-process',
                                plan_sha256=self.study.plan_sha256);rows=[];success=False
  try:
   paid.invoke(suffix='sampler-setup',category='tinker',request={'kind':'sampler_setup','sampling_kind':'base' if base else 'checkpoint'},
    provider=lambda request:sampler.start(checkpoint_path=checkpoint_path,checkpoint_sha256=checkpoint,
      seed=sampling['seed'],max_output_tokens=sampling['max_output_tokens'],attempt_id=started['attempt_id']))
   for ordinal,package in enumerate(packages):
    row,*_=self._episode(admitted=admitted,package=package,ordinal=ordinal,batch=out_dir,paid=paid,sampler=sampler);rows.append(row)
   checked=coverage.validate(cell_id=self.cell_id,attempt_id=started['attempt_id'],checkpoint_sha256=checkpoint,
    selection_tasks=identities,selection_identities_sha256=started['selection_identities_sha256'],paid_calls=paid.calls,related_paid_attempt_ids=set(paid.ids))
   if not base:
    integration.require(checked==session._selection_paid_coverage(attempt_id=started['attempt_id'],checkpoint_sha256=checkpoint,
                                                               paid_attempt_ids=paid.ids),'v11_campaign_paid_coverage_changed')
   result={'schema':'cua-full-study-selection-saved-result-v1','cell_id':self.cell_id,'checkpoint_sha256':checkpoint,
           'evaluator_isolated':True,'tasks':rows}
   if not base:session._selection_result(result,checkpoint_sha256=checkpoint)
   result_ref=write(out_dir/'selection-result.private.json',result)
   ledger=write(out_dir/'task-ledger.private.json',{'schema':'cua-native-desktop-v11-model-task-ledger','tasks':rows,
     'paid_attempt_ids':paid.ids,'coverage':checked,'worker_runtime_sha256':integration.proposal()['worker_runtime_sha256']})
   batch_ref=write(out_dir/'batch.private.json',{'schema':'cua-native-desktop-v11-model-batch','task_count':20,
     'checkpoint_sha256':checkpoint,'result_sha256':result_ref['sha256'],'task_ledger_sha256':ledger['sha256'],
     'model_worker_profile_sha256':digest(self.proposal_path.read_bytes()),'official_final_model_attempts':0})
   success=True
   return {'status':'scored','result':result,'result_sha256':result_ref['sha256'],'paid_attempt_ids':paid.ids,
     'task_ledger_path':str(out_dir/'task-ledger.private.json'),'task_ledger_sha256':ledger['sha256'],
     'batch_receipt_path':str(out_dir/'batch.private.json'),'batch_receipt_sha256':batch_ref['sha256']}
  except Exception as exc:
   ref=write(out_dir/'invalid.private.json',{'schema':'cua-native-desktop-v11-invalid-batch','completed_task_count':len(rows),
    'exception_type':type(exc).__name__,'paid_attempt_ids':paid.ids,'same_intent_replay_authorized':False,'failed_task_score_inferred':False})
   return {'status':'invalid','failure_type':'environment','evaluator_receipt_sha256':ref['sha256'],'paid_attempt_ids':paid.ids}
  finally:sampler.close(success)

 def run_selection(self,*,session,started:dict,checkpoint_path:str,out_dir:Path):
  with integration.runtime_context():return self._run_selection(session=session,started=started,checkpoint_path=checkpoint_path,out_dir=out_dir,base=False)

 def run_base_selection(self,*,session,out_dir:Path):
  with integration.runtime_context():return self._run_selection(session=session,started=session.started,checkpoint_path=None,out_dir=out_dir,base=True)

 def run_once(self,command:dict,output_dir:Path):
  with integration.runtime_context():return self._run_once(command,output_dir)

 def _run_once(self,command:dict,output_dir:Path):
  """Concrete TrustedFinalWorker implementation under the parent reservation."""
  admitted=self._gate();cell,training,sampling,quote=self._policy()
  integration.require(type(self.final_gate) is final.FinalGate and self.final_gate.frozen is self.study,
                      'v11_real_post_campaign_final_gate_required')
  integration.require(command['schema']==final.COMMAND_SCHEMA and command['cell_id']==self.cell_id and
   command['owner_slot'] in ['shared-base',*matrix.RESEARCHERS] and command['max_actions']==90 and command['max_wall_seconds']==720 and
   command['sampling']==sampling and command['matched_bindings']==cell['matched_bindings'] and
   command['action_profile']=='scale-action-profile-v0.6.6','v11_final_command_not_uniform')
  checkpoint_path=command['sampler_path'];checkpoint=command['checkpoint_sha256']
  integration.require((command['owner_slot']=='shared-base' and checkpoint_path is None and
    checkpoint==integration.proposal()['base_checkpoint_sha256']) or (command['owner_slot']!='shared-base' and
   type(checkpoint_path) is str and digest(checkpoint_path.encode())==checkpoint),'v11_final_sampler_binding_changed')
  if command['owner_slot']!='shared-base':
   integration.require(self.final_gate.freezes[(self.cell_id,command['owner_slot'])]['selected_checkpoint_sha256']==checkpoint,
                       'v11_final_checkpoint_not_frozen_campaign_winner')
  integration.require(output_dir.is_dir() and not output_dir.is_symlink() and not any(output_dir.iterdir()),'v11_final_output_consumed_no_replay')
  packages=self._packages(admitted,[{'task_id':command['task_id'],'package_sha256':command['package_sha256']}],'final_candidate')
  package=packages[0]
  integration.require(digest(package['source'])==command['expected_initial_state_sha256'],'v11_final_original_reset_binding_changed')
  write(output_dir/'started.private.json',{'command_sha256':digest(integration.canonical(command)),'same_intent_replay_authorized':False})
  paid=PaidCalls(attempt_id=command['attempt_id'],checkpoint=checkpoint,identities=[package['identity']],output_dir=output_dir,
    runtime=integration.proposal()['worker_runtime_sha256'],quote=quote,final_reserve=command['reserve_usd'],study=self.study)
  sampler=transport.ModelSampler(repo_root=self.study.repo_root,journal_root=output_dir/'sampler-process',
                                plan_sha256=self.study.plan_sha256);started_at=int(time.time());success=False
  try:
   paid.invoke(suffix='sampler-setup',category='tinker',request={'kind':'sampler_setup'},provider=lambda request:sampler.start(
    checkpoint_path=checkpoint_path,checkpoint_sha256=checkpoint,seed=sampling['seed'],max_output_tokens=sampling['max_output_tokens'],attempt_id=command['attempt_id']))
   row,out,trace,elapsed,model_outcome=self._episode(admitted=admitted,package=package,ordinal=0,batch=output_dir,paid=paid,sampler=sampler)
   # Any clock overrun is preserved and requires reconciliation, never a pass.
   integration.require(elapsed<=720,'v11_actor_clock_overrun_invalid')
   usage={name:sum(u[name] for u in paid.usage) for name in ['input_tokens','image_tokens','output_tokens']}
   nominal=(Decimal('0.666666668')+(Decimal(usage['input_tokens'])*Decimal(training['prefill_usd_per_million_tokens'])+
    Decimal(usage['output_tokens'])*Decimal(training['sample_usd_per_million_tokens']))/Decimal(1_000_000)*Decimal(training['billing_multiplier_upper']))
   cost=str(nominal.quantize(Decimal('0.000000001'),rounding=ROUND_CEILING))
   usage_ref=write(output_dir/'usage.private.json',{'schema':final.USAGE_SCHEMA,'attempt_id':command['attempt_id'],
    'cost_basis':'published_rate_nominal','cost_usd':cost,**usage,'provider_billed_tokens':None,'provider_invoice_sha256':None})
   reset_ref=write(output_dir/'reset.private.json',{'schema':final.RESET_SCHEMA,'task_id':command['task_id'],
    'package_sha256':command['package_sha256'],'attempt_id':command['attempt_id'],'fresh_environment':True,
    'restored_after_attempt':True,'initial_state_sha256':digest(package['source']),'restored_state_sha256':digest(package['source'])})
   task=json.loads((out/'task.private.json').read_bytes());saved=(out/task['saved_file']).read_bytes()
   saved_path=out/task['saved_file']
   verification=json.loads((out/'verifier.private.json').read_bytes())
   verifier_ref=write(output_dir/'verifier.private.json',{'schema':final.VERIFIER_SCHEMA,'task_id':command['task_id'],
    'package_sha256':command['package_sha256'],'attempt_id':command['attempt_id'],'saved_state_sha256':digest(saved),'score':row['score'],
    'no_regression_checked':True,'no_regression_passed':no_regression_passed(verification['fair_result']),
    'independent_of_actor':True,'gold_withheld_from_actor':True})
   count=task['action_count'];turns=task['turn_count']
   obs_ref=write(output_dir/'observations.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],
    'kind':'observations','action_profile':'scale-action-profile-v0.6.6','count':turns,'screenshot_only':True})
   act_ref=write(output_dir/'actions.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],
    'kind':'actions','action_profile':'scale-action-profile-v0.6.6','count':count,'current_frame_validated':True})
   outcome={'schema':final.OUTCOME_SCHEMA,'status':'scored','score':row['score'],'failure_type':None,
    'started_at':started_at,'finished_at':int(time.time()),'cost_basis':'published_rate_nominal','cost_usd':cost,
    'usage':usage_ref,'reset':reset_ref,'saved_state':{'path':str(saved_path.relative_to(output_dir)),'sha256':digest(saved)},'verifier':verifier_ref,
    'observation_trace':obs_ref,'action_trace':act_ref,'action_count':count,'turn_count':turns,'wall_time_ms':int(elapsed*1000),
    'provider_latency_ms':int(paid.sample_latency_seconds*1000),
    'timeout_subtype':model_outcome if model_outcome in ['actor_wall_budget','actor_action_budget'] else 'none',
    'action_profile':'scale-action-profile-v0.6.6'}
   success=True;return outcome
  finally:sampler.close(success)
