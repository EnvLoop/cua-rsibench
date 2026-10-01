"""Independent reopen of original Office lifecycle, guard, scoring and paid files."""
from pathlib import Path
import json,math
from tools import office_owned_folder_runtime_v2 as office
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_performance_coverage_v2 as coverage


def office_json_ref(root,ref):
 path,raw=final.private_reference(Path(root),ref,'office_actual_private_artifact');return json.loads(raw),raw


def reset_state(package,path):
 office.require(package.neutral(path)['equivalent'] is True,'Original Office source/reset semantic relation failed')
 return {'schema':'office-current-source-equivalent-state-v4','task_id':package.actor.task_id,'package_sha256':package.binding_sha256,
  'baseline_sha256':package.actor.baseline_sha256,'original_neutral_verifier_passed':True}


def native_operations(root):
 root=Path(root);operations=[]
 for directory in sorted((root/'native-operations.private').glob('operation-*')):
  request=json.loads(office.private(directory/'request.private.json'));response=json.loads(office.private(directory/'response.private.json'))
  office.require(response['request_sha256']==office.sha(office.private(directory/'request.private.json')) and response['sequence']==request['sequence'] and response['operation']==request['operation'] and request['one_use'] is True,'Native request/response identity changed')
  consumed=json.loads(office.private(directory/'consumed.private.json'));office.require(consumed['response_sha256']==office.sha(office.private(directory/'response.private.json')) and consumed['one_use'] is True,'Native response not consumed exactly once')
  if response['status']!='completed':
   failure=response['result'];office.require(failure.get('actor_deadline_rejected') is True and failure.get('native_driver_attempted') is False and failure.get('native_operation_may_be_uncertain') is False,'Uncertain native operation cannot score')
  operations.append((request,response))
 return operations


def reopen_native(package,root):
 root=Path(root);admission=json.loads(office.private(root/'native-source-admission.private.json'));evidence=Path(admission['native_evidence_root'])
 operations=native_operations(root);downloads={};items={}
 for request,response in operations:
  if response['status']!='completed':continue
  kind=response['operation'];record=response['result']
  if kind in ('folder_inventory','create_document','double_download','close_document','remove_document'):
   office.validate_native_record(record,operation=kind,account=admission['account_principal_sha256'],folder=admission['folder_scope_sha256'])
   for ref in record['raw_refs']:final.private_reference(evidence,ref,'office_native_raw_ui')
  if kind=='create_document':
   purpose=request['payload']['purpose'];office.require(purpose not in items,'Native create replay or unexpected reset');items[purpose]=record['item']['item_identity_sha256']
  if kind=='double_download':
   purpose=request['payload']['purpose'];office.require(purpose not in downloads and record['item_identity_sha256']==request['payload']['item']['item_identity_sha256'] and record.get('download_surface')=='folder_toolbar' and len(record['download_refs'])==2,'Actual owned item/two folder-toolbar download events required')
   paths=[];raws=[]
   for ref in record['download_refs']:
    path,raw=final.private_reference(evidence,ref,'office_actual_download');paths.append(path);raws.append(raw)
   office.require(raws[0]==raws[1],'Actual saved native download not stable');downloads[purpose]=(paths[0],record['item_identity_sha256'])
 office.require({'before_actor','saved_actor','fresh_reset'}<=set(downloads) and set(items)=={'actor','reset'} and items['actor']!=items['reset'],'Distinct actual actor/reset documents required')
 for name,purpose in [('before_actor','actor'),('saved_actor','actor'),('fresh_reset','reset')]:office.require(downloads[name][1]==items[purpose],'Readback switched native document')
 initial,saved,restored=[downloads[name][0] for name in ('before_actor','saved_actor','fresh_reset')]
 initial_state=reset_state(package,initial);restored_state=reset_state(package,restored);office.require(initial_state==restored_state,'Original reset state relation changed')
 independent=package.strict_score(saved);office.require(independent['score'] in (0,1),'Existing strict saved scorer infrastructure failure is unscored')
 recorded=json.loads(office.private(root/'native.private/saved-state-score.private.json'));reset=json.loads(office.private(root/'native.private/reset-score.private.json'))
 office.require(recorded==independent and reset==package.neutral(restored),'Independent original saved/reset recheck changed')
 inventories=[response['result'] for _,response in operations if response['operation']=='folder_inventory' and response['status']=='completed']
 office.require(inventories and inventories[0]['items']==[] and inventories[-1]['items']==[],'Actual native full inventory must begin/end empty')
 removed=[response['result']['item_identity_sha256'] for _,response in operations if response['operation']=='remove_document' and response['status']=='completed']
 closed=[response['result']['item_identity_sha256'] for _,response in operations if response['operation']=='close_document' and response['status']=='completed']
 office.require(sorted(removed)==sorted(items.values()) and sorted(closed)==sorted(items.values()),'Exact actor/reset item close/removal required')
 return {'score':int(independent['score']),'strict':independent,'saved_path':saved,'reset_path':restored,'initial_path':initial,'initial_state':initial_state,'reset_state':restored_state,'operations':operations}


def reopen_task(package,root):
 root=Path(root);checked=reopen_native(package,root);result=json.loads(office.private(root/'task-result.private.json'));clock=json.loads(office.private(root/'actor-clock.private.json'))
 office.require(result['task_id']==package.actor.task_id and result['package_sha256']==package.binding_sha256 and clock['deadline']==clock['started']+720 and clock['native_actions_after_deadline']==0 and 0<=clock['actor_seconds']<=720 and all(type(clock[k]) in (int,float) and math.isfinite(clock[k]) for k in ('started','deadline','raw_end','actor_seconds')),'Current Office task/actor clock changed')
 office.require(clock['actor_seconds']==min(clock['raw_end']-clock['started'],720) and 0<=result['lifecycle_seconds']<=1200 and result['lifecycle_ended']-result['lifecycle_started']>=result['lifecycle_seconds'] and result['lifecycle_started']<=clock['started']<=clock['raw_end']<=result['lifecycle_ended'],'Actual actor/lifecycle clocks changed')
 for request,response in checked['operations']:
  if response['operation'] not in ('native_surface','resolve_native_targets','dispatch_native_primitive'):continue
  office.require(request['payload']['actor_deadline_epoch_ms']==clock['actor_deadline_epoch_ms'],'Native request actor deadline changed')
  if response['operation']=='dispatch_native_primitive' and response['status']=='completed':
   driver=response['result'];office.require(driver['actor_deadline_epoch_ms']==clock['actor_deadline_epoch_ms'] and driver['native_driver_started_epoch_ms']<=driver['native_driver_completed_epoch_ms']<clock['actor_deadline_epoch_ms'],'Native driver was applied after actor deadline')
 trace=json.loads(office.private(root/'actions.private.json'));office.require(len(trace)<=90 and all(not r.get('applied_before_deadline') is False for r in trace),'Actor trace/action budget changed')
 actor_root=root/'native.private/actor-private'
 for path in sorted(actor_root.glob('turn-*/receipt.private.json')):
  receipt=json.loads(office.private(path));office.safety.validate_receipt(receipt)
  prefix=path.parent;decision=json.loads(office.private(prefix/'decision.private.json'))
  office.require(receipt['decision_sha256']==office.safety.digest(decision),'Original shared guard decision changed')
  for name in ('observation','predispatch'):
   envelope=json.loads(office.private(prefix/(name+'-envelope.private.json')));office.safety.validate_envelope(envelope)
   ref=envelope['raw_image'];image=office.private(actor_root/ref['path']);office.require(office.sha(image)==ref['sha256'] and envelope['task_binding_sha256']==package.binding_sha256 and envelope['expires_at']-envelope['captured_at']<=150,'Guard frame image/task/TTL changed')
  if receipt['status']=='applied':office.require(receipt['driver_result']=='succeeded' and decision['status']=='accepted','Applied native action bypassed physical guard')
 close_raw=office.private(root/'sampler.private/provider-close.private.json');close=json.loads(close_raw)
 office.require(close['acknowledged'] is True and result['account_lease_released'] is True and result['saved_state_readback_verified'] is True and result['fresh_reset_verified'] is True,'Actual owned provider close/readback/reset/account release required')
 if close.get('child_terminal_sha256'):
  raw=office.private(root/'sampler.private/rpc.private/child-terminal.private.json');value=json.loads(raw)
  office.require(office.sha(raw)==close['child_terminal_sha256'] and value['provider_shutdown_acknowledged'] is True and value['forced_termination'] is False,'Actual provider close terminal changed')
 office.require(checked['score']==result['score']==result['raw_strict_saved_score'],'Existing independent strict scorer result changed')
 return {**checked,'clock':clock,'result':result,'task_sha256':office.sha(office.private(root/'task-result.private.json')),'close_sha256':office.sha(close_raw)}


def paid_calls(authority):
 session=authority.session;calls=[];ids=[];references=[]
 if hasattr(session,'journal'):
  session._audit_paid_files();prefix=authority.started['attempt_id'];results={r['data']['attempt_id']:r['data'] for r in session._events('paid_result')}
  for row in session._events('paid_intent'):
   data=row['data'];identifier=data['attempt_id']
   if not identifier.startswith(prefix+'-'):continue
   raw=office.private(session.directory/(identifier+'.request.private.json'));office.require(office.sha(raw)==data['request_sha256'],'Exact paid request changed');request=json.loads(raw);result=None
   if identifier in results:
    raw=office.private(session.directory/(identifier+'.result.private.json'));office.require(office.sha(raw)==results[identifier]['result_sha256'],'Actual paid result changed');result=json.loads(raw)
   calls.append({'attempt_id':identifier,'category':data['category'],'request':request,'result_present':result is not None,'result_status':None if result is None else result.get('status')});ids.append(identifier)
 else:
  prefix=session.attempt_id;references=session.paid_references()
  for ref in references:
   envelope,envelope_raw=office_json_ref(session.directory,ref['request_ref']);request,_=office_json_ref(session.directory,envelope['worker_request_ref']);result=None
   ledger=session.budget.owner_attempts(session.owner)[ref['attempt_id']]
   office.require(office.sha(envelope_raw)==ledger['request_sha256'] and envelope['category']==ref['category'] and ledger['category']==ref['category'],'Actual shared-base ledger/envelope changed')
   if ref['result_ref'] is not None:
    normalized,_=office_json_ref(session.directory,ref['result_ref']);result,_=office_json_ref(session.directory,normalized['worker_result_ref'])
   calls.append({'attempt_id':ref['attempt_id'],'category':ref['category'],'request':request,'result_present':result is not None,'result_status':None if result is None else result.get('status')});ids.append(ref['attempt_id'])
 return prefix,calls,ids,references


def paid_coverage(authority,task_records,budget_receipts):
 office.require(len(task_records)==20 and len({r['task_id'] for r in task_records})==20,'All20 actual task performances required')
 prefix,calls,ids,_=paid_calls(authority)
 expected={r['environment_paid_attempt_id'] for r in task_records}|{i for r in task_records for i in r['sampler_paid_attempt_ids']}
 office.require(expected==set(ids),'Office task records hide/miss actual paid requests')
 for call in calls:
  request=call['request'];task=next((r for r in task_records if r['task_id']==request.get('task_id')),None)
  if call['category']=='tinker' and task is not None:
   root=Path(task['episode_root']);frames={json.loads(office.private(p))['frame_sha256'] for p in (root/'sampler.private').glob('sample-*.request.private.json')}
   office.require(request.get('frame_sha256') in frames,'Actual paid sample not bound to native frame')
 return coverage.validate(plan=authority.study.parent.plan,amendment=authority.study.amendment,cell_id=authority.cell,owner_slot=authority.owner,
  attempt_id=prefix,checkpoint_sha256=authority.checkpoint,selection_tasks=authority.study.task_views(authority.cell)['selection'],paid_calls=calls,
  related_paid_attempt_ids=set(ids),budget_performance_receipts=budget_receipts),ids


def task_projection(package,root):
 root=Path(root);checked=reopen_task(package,root)
 def write(name,value):office.write_new(root/name,office.canonical(value));return office.sha(office.private(root/name))
 common={'task_id':package.actor.task_id,'package_sha256':package.binding_sha256}
 saved=write('saved-state.private.json',{**common,'saved_artifact_sha256':office.sha(office.private(checked['saved_path'])),'independent_readback':True})
 verifier=write('verifier.private.json',{**common,'score':checked['score'],'strict_saved_result':checked['strict'],'independent_of_actor':True,'no_regression_passed':preserved(checked['strict'])})
 reset=write('reset.private.json',{**common,'distinct_native_document':True,'state':checked['reset_state'],'initial_state_sha256':office.sha(office.canonical(checked['initial_state'])),'restored_state_sha256':office.sha(office.canonical(checked['reset_state']))})
 office.write_new(root/'task.private.json',office.canonical({**common,'owner_slot':checked['result']['owner_slot'],'checkpoint_sha256':checked['result']['checkpoint_sha256'],'amendment_sha256':checked['result']['amendment_sha256']}))
 return {**common,'score':checked['score'],'saved_state_sha256':saved,'verifier_receipt_sha256':verifier,'reset_receipt_sha256':reset}


def preserved(strict):
 raw=strict['raw_strict'];return raw['preservation_pass'] if 'preservation_pass' in raw else bool(strict['score'])


def final_outcome(authority,package,root,started_at,budget_verification=None,attempt_dir=None):
 import time
 a=authority;checked=reopen_task(package,root);command=a.command;root=Path(root);reference_root=Path(attempt_dir or root);record=checked['result'];clock=checked['clock'];prefix=command['attempt_id']
 def write(name,value):office.write_new(root/name,office.canonical(value));return final.reference(reference_root,root/name)
 office.write_new(root/'saved-artifact.private.bin',office.private(checked['saved_path']));saved_ref=final.reference(reference_root,root/'saved-artifact.private.bin')
 verifier=write('final-verifier.private.json',{'schema':final.VERIFIER_SCHEMA,'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,'attempt_id':prefix,
  'saved_state_sha256':saved_ref['sha256'],'score':checked['score'],'no_regression_checked':True,'no_regression_passed':preserved(checked['strict']),'independent_of_actor':True,'gold_withheld_from_actor':True})
 initial=office.sha(office.canonical(checked['initial_state']));restored=office.sha(office.canonical(checked['reset_state']))
 office.require(initial==restored==a.authority.initial_state_by_task[a.cell][package.actor.task_id],'Actual reset representation differs from independently qualified initial state')
 reset=write('final-reset.private.json',{'schema':final.RESET_SCHEMA,'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,'attempt_id':prefix,
  'fresh_environment':True,'restored_after_attempt':True,'initial_state_sha256':initial,'restored_state_sha256':restored})
 trace=json.loads(office.private(root/'actions.private.json'));applied=sum(r['status']=='applied' for r in trace);turns=len(trace)
 obs=write('final-observations.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':prefix,'kind':'observations','action_profile':'scale-action-profile-v0.6.6','count':turns,'screenshot_only':True})
 actions=write('final-actions.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':prefix,'kind':'actions','action_profile':'scale-action-profile-v0.6.6','count':applied,'current_frame_validated':True})
 actor_ms=int(record['actor_seconds']*1000);life_ms=int(record['lifecycle_seconds']*1000)
 actor_clock=write('final-actor-clock.private.json',{'schema':'cua-full-study-final-actor-clock-v2','attempt_id':prefix,'max_actions':90,'actor_seconds_limit':720,'lease_seconds_limit':1200,
  'actor_wall_time_ms':actor_ms,'lifecycle_wall_time_ms':life_ms,'native_actions_after_deadline':0,'evaluation_outside_actor_clock':True,'raw_clock_sha256':office.sha(office.private(root/'actor-clock.private.json'))})
 calls=[{'request_id':'environment','paid_attempt_id':prefix,'kind':'environment','intent':final.reference(reference_root,root/'environment.intent.private.json'),'result':final.reference(reference_root,root/'environment.result.private.json')}];samples=[]
 for path in sorted((root/'sampler.private').glob('*.intent.private.json')):
  value=json.loads(office.private(path));response=path.with_name(path.name.replace('.intent.','.result.'));result_ref=None
  if response.exists():
   result=json.loads(office.private(response));result_ref=final.reference(reference_root,response)
   if value['kind']=='sample':samples.append(result)
  calls.append({'request_id':value['request_id'],'paid_attempt_id':value['paid_attempt_id'],'kind':value['kind'],'intent':final.reference(reference_root,path),'result':result_ref})
 tokens={k:sum(r['usage'][k] for r in samples) if samples and all(type(r['usage'].get(k)) is int for r in samples) and not record['actor_budget_proof'] else None for k in ('input_tokens','image_tokens','output_tokens')}
 usage=write('final-usage.private.json',{'schema':'cua-full-study-authentic-unknown-usage-v2','attempt_id':prefix,'cost_basis':'authentic_usage_unknown','cost_usd':None,
  **tokens,'provider_billed_tokens':None,'provider_invoice_sha256':None,'paid_calls':calls})
 proof=None
 if record['actor_budget_proof'] is not None:
  office.require(budget_verification is not None,'Actual checked Office budget evidence required before final projection')
  from tools.office_current_budget_performance_v4 import verify_budget_performance
  receipt=verify_budget_performance(study=a.study,owner_slot=a.owner,verification=budget_verification['arguments']);proof=write('final-budget-performance.private.json',{'verification':budget_verification,'receipt':receipt})
 latency=sum(r['elapsed_seconds'] for r in samples if type(r.get('elapsed_seconds')) in (int,float))
 office.require(all(type(r.get('elapsed_seconds')) in (int,float) for r in samples),'Actual completed provider latency required')
 return {'schema':final.OUTCOME_SCHEMA,'status':'scored','score':checked['score'],'failure_type':None,'started_at':started_at,'finished_at':int(time.time()),
  'cost_basis':'authentic_usage_unknown','cost_usd':None,'usage':usage,'reset':reset,'saved_state':saved_ref,'verifier':verifier,'observation_trace':obs,'action_trace':actions,
  'action_count':applied,'turn_count':turns,'wall_time_ms':actor_ms,'provider_latency_ms':int(latency*1000),'timeout_subtype':record['model_outcome'] if record['model_outcome'] in ('actor_wall_budget','actor_action_budget') else 'none',
  'action_profile':'scale-action-profile-v0.6.6','actor_clock':actor_clock,'lifecycle_wall_time_ms':life_ms,'budget_performance':proof}
