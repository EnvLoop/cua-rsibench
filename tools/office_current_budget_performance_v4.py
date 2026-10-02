"""Read-only current Office deadline performance reader; never settles billing."""
from pathlib import Path
import json
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_package_v4 import Package
from tools.office_current_evidence_v4 import reopen_task
from native_desktop_factory.deadline_model_transport_v21 import checked_deadline_proof


def descriptor(study,package,root):
 root=Path(root)
 return {'adapter':{'module':__name__,'function':'verify_budget_performance','source_sha256':office.sha(Path(__file__).read_bytes())},
  'arguments':{'schema':'office-current-budget-input-v4','episode_root':str(root.resolve()),'package_root':str(package.root),
   'descriptor':{'path':str(package.descriptor.resolve()),'sha256':package.binding_sha256}}}


def verify_budget_performance(*,study,owner_slot,verification):
 from tools.office_current_protocol_v4 import require_epoch
 require_epoch(study)
 office.require(set(verification)=={'schema','episode_root','package_root','descriptor'} and verification['schema']=='office-current-budget-input-v4','Exact private Office budget descriptor required')
 work=study.repo_root/'work';root=Path(verification['episode_root']);package_path=Path(verification['descriptor']['path'])
 office.require(root.resolve().is_relative_to(work) and package_path.resolve().is_relative_to(work) and office.sha(office.private(package_path))==verification['descriptor']['sha256'],'Owned private Office budget package/episode changed')
 package=Package(package_path,package_root=verification['package_root']);checked=reopen_task(package,root);record=checked['result'];clock=checked['clock']
 office.require(record['owner_slot']==owner_slot and record['amendment_sha256']==study.amendment_sha256 and record['actor_budget_proof'] is not None and record['model_outcome']=='actor_wall_budget' and clock['raw_end']>=clock['deadline'],'Actual current Office budget stop required')
 if (root/'final-command.private.json').exists():
  from cursibench import full_study_final_dispatch_v1 as final
  command=json.loads(office.private(root/'final-command.private.json'));parent=study.budget.owner_attempts(package.actor.cell_id+':'+owner_slot).get(command['attempt_id'])
  office.require(command['schema']==final.COMMAND_SCHEMA and command['task_id']==package.actor.task_id and command['package_sha256']==package.binding_sha256 and command['owner_slot']==owner_slot and command['checkpoint_sha256']==record['checkpoint_sha256'] and command['max_actions']==90 and command['max_wall_seconds']==720 and parent and parent['request_sha256']==office.sha(office.private(root/'final-command.private.json'))==final.sha(final.canonical(command)),'Actual final parent command/task reservation changed')
 else:
  expected={r['task_id']:r['package_sha256'] for r in study.task_views(package.actor.cell_id)['train' if record['teacher'] else 'selection']}
  office.require(expected.get(package.actor.task_id)==package.binding_sha256,'Deadline body outside frozen original task scope')
 stop_raw=office.private(root/'sampler.private/actor-budget-stop.private.json');stop=json.loads(stop_raw);proof=checked_deadline_proof(stop['proof'],clock['deadline'])
 office.require(stop['proof']==record['actor_budget_proof'] and stop['gui_applied'] is False and stop['request_replayed'] is False,'Actual deadline proof/GUI withholding changed')
 identifier=stop['sample_paid_attempt_id'];ledger=study.budget.owner_attempts(package.actor.cell_id+':'+owner_slot).get(identifier)
 office.require(ledger and ledger['category'] in ('tinker','selected_final','shared_base_final','teacher_rollout') and ledger['status'] in ('uncertain','dispatched','settled'),'Actual consumed owned paid reservation required')
 paid_request=None
 if ledger['category'] in ('tinker','teacher_rollout'):
  directory=Path(record['paid_session_directory']);office.require(directory.resolve().is_relative_to(work),'Actual paid session escaped study')
  path=directory/(identifier+'.request.private.json') if (directory/'campaign.jsonl').exists() else directory/'paid'/(identifier+'.request.private.json')
  raw=office.private(path);office.require(office.sha(raw)==ledger['request_sha256'],'Actual consumed paid request hash changed');paid_request=json.loads(raw)
  if paid_request.get('worker_request_ref'):
   from tools.office_current_evidence_v4 import office_json_ref
   paid_request,_=office_json_ref(directory,paid_request['worker_request_ref'])
  office.require(paid_request['cell_id']==package.actor.cell_id and paid_request.get('task_id',paid_request.get('train_task_id'))==package.actor.task_id and paid_request['package_sha256']==package.binding_sha256,'Actual paid request switched task/cell/package')
 completed=0
 if record['teacher']:
  office.require(ledger['category']=='teacher_rollout','Teacher cannot substitute Qwen paid request')
  close=json.loads(office.private(root/'sampler.private/provider-close.private.json'));ref=close.get('external_evidence_ref')
  office.require(ref is not None,'Uncertain teacher requires actual external provider-close evidence')
  raw=office.private(Path(ref['path']));value=json.loads(raw)
  office.require(office.sha(raw)==ref['sha256'] and value['acknowledged'] is True and value['outstanding_requests']==0 and value['forced_termination'] is False and identifier in value['paid_attempt_ids'],'Teacher future remains uncertain/unclosed')
  provider_root=Path(ref['path']).parent;matches=[]
  for path in provider_root.glob('request-*.private.json'):
   request=json.loads(office.private(path))
   if request['request_sha256']==office.sha(office.canonical(paid_request)):
    proof_path=path.with_name(path.name.replace('request-','deadline-'));office.require(json.loads(office.private(proof_path))==stop['proof'],'Actual owned teacher future deadline changed');matches.append(path)
  office.require(len(matches)==1,'Actual teacher paid request/owned future not unique')
  completed=len(list((root/'sampler.private').glob('teacher-*.private.json')))
 else:
  calls=[]
  for path in sorted((root/'sampler.private').glob('sample-*.intent.private.json')):
   intent=json.loads(office.private(path));request_path=path.with_name(path.name.replace('.intent.','.request.'));request=json.loads(office.private(request_path))
   office.require(intent['request_sha256']==office.sha(office.private(request_path)) and intent['same_request_replay_authorized'] is False and request['task_id']==package.actor.task_id and request['package_sha256']==package.binding_sha256 and request['checkpoint_path_sha256']==record['checkpoint_sha256'],'Actual paid sample task/checkpoint changed')
   result=path.with_name(path.name.replace('.intent.','.result.'))
   if result.exists():office.require(json.loads(office.private(result))['status']=='completed','Earlier provider failure cannot become performance');completed+=1
   else:
    if paid_request is not None:office.require(request==paid_request,'Consumed model paid request differs from sampled native frame')
    envelope_path=root/f'native.private/actor-private/turn-{request["step"]:03d}/observation-envelope.private.json';envelope=json.loads(office.private(envelope_path));office.safety.validate_envelope(envelope)
    image=office.private(root/'native.private/actor-private'/envelope['raw_image']['path'])
    office.require(envelope['frame_id']==request['frame_id'] and envelope['raw_image']['sha256']==office.sha(image)==request['frame_sha256'] and envelope['task_binding_sha256']==package.binding_sha256,'Terminal sample not bound to actual guarded observation')
    calls.append(intent)
  office.require(len(calls)==1 and calls[0]['paid_attempt_id']==identifier and calls[0]['request_id']==stop['request_id'],'One actual terminal sample uncertainty required')
  journal=root/'sampler.private/rpc.private';terminal=json.loads(office.private(journal/'child-terminal.private.json'))
  office.require(terminal['provider_shutdown_acknowledged'] is True and terminal['forced_termination'] is False,'Real owned provider shutdown required')
  deadline_results=[]
  for path in journal.glob('[0-9][0-9][0-9].result.private.json'):
   response=json.loads(office.private(path));request_path=path.with_name(path.name.replace('.result.','.request.'));request=json.loads(office.private(request_path))
   office.require(response['request_sha256']==office.sha(office.private(request_path)) and request['plan_sha256']==study.plan_sha256 and request['same_request_replay_authorized'] is False,'Actual clean child request/plan changed')
   if response['status']=='actor_deadline':
    office.require(request['kind']=='sample' and request['arguments']['actor_deadline']==clock['deadline'] and response['actor_deadline_proof']==stop['proof'],'Actual child typed deadline changed');deadline_results.append(response)
  office.require(len(deadline_results)==1,'Actual clean-child typed deadline acknowledgement required')
 # The six references are checked again by the policy session on every reopen.
 evidence={name:office.sha(office.private(root/name)) for name in ('saved-state.private.json','verifier.private.json','reset.private.json','actor-clock.private.json','task.private.json')}
 evidence['actor-budget-stop.private.json']=office.sha(stop_raw)
 inference='late_completed_withheld_from_gui' if proof.model_completion_known else 'completion_unknown_after_actor_deadline' if proof.model_dispatch_may_have_occurred else 'not_submitted_before_actor_deadline'
 return {'schema':'cua-verified-budget-performance-with-unknown-billing-v22','amendment_sha256':study.amendment_sha256,'owner_slot':owner_slot,
  'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,'checkpoint_sha256':record['checkpoint_sha256'],'sample_paid_attempt_id':identifier,
  'performance_coverage_eligible':True,'provider_close_acknowledged':True,'formal_registration_performed':False,
  'performance':{'status':'independently_saved_scored_and_reset','score':checked['score']},
  'inference':{'status':inference,'completed_model_response_count':completed,'unknown_response_is_completed':False,'request_replayed':False},
  'billing':{'actual_usd':None,'provider_invoice_verified':False},'evidence_sha256':evidence}
