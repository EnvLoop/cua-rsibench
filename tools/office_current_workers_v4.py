"""Executable teacher/selection/base/final counterparts for original Office."""
from pathlib import Path
from types import SimpleNamespace
import json,time
from tools import office_owned_folder_runtime_v2 as office
from tools.office_current_package_v4 import Package
from tools.office_current_authority_v4 import Authority,current_sources,verify_qualification
from tools.office_current_execution_v4 import TaskWorker
from tools.office_current_evidence_v4 import task_projection,reopen_task,paid_coverage,office_json_ref
from tools.office_current_budget_performance_v4 import descriptor
from tools.office_current_protocol_v4 import epoch_context,require_epoch,verify_budget
from cursibench import full_study_runtime_v2 as policy
from cursibench import full_study_final_dispatch_v1 as final

def counterpart_registry(repo):
 from cursibench import full_study_matrix_v1 as matrix
 return {'schema':'office-current-counterpart-registration-v4','cells':{cell:{'qualified':False,'max_actions':90,'actor_seconds':720,'lease_seconds':1200,
  'frame_ttl_seconds':150,'native_policy_sha256':office.safety.POLICY_SHA,'native_pump':'tools/office_current_cua_pump_v4.mjs',
  'teacher':'tools.office_current_teacher_v4.TeacherWorker','selection':'tools.office_current_workers_v4.run_selection','shared_base':'tools.office_current_workers_v4.admit_shared_base',
  'final':'tools.office_current_workers_v4.TrustedFinalWorker','neutral':'tools.office_current_neutral_v4',
  'student_slots':['shared-base',*matrix.RESEARCHERS],'all_actor_paths_same_native_loop':True} for cell in office.CELLS},'source_sha256s':current_sources(repo),
  'distinct_official_task_identities':600,'campaign_count':24,'initial_slot_task_results':3000,'actual_native_calls':0,'actual_provider_calls':0}


def run_selection(worker,*,quote,register=False):
 office.require(type(worker) is TaskWorker and worker.authority.teacher is False and worker.authority.command is None,'Actual current selection/base task worker required')
 a=worker.authority;identities=a.identities();office.require(len(identities)==20 and len({r['task_id'] for r in identities})==20,'Exactly frozen original selection20 required')
 office.require(not worker.output.exists() and worker.output.parent.resolve().is_relative_to(a.study.repo_root/'work'),'Fresh private selection output required');worker.output.mkdir(mode=0o700,parents=True)
 office.write_new(worker.output/'selection-intent.private.json',office.canonical({'identities':identities,'checkpoint_sha256':a.checkpoint,'owner_slot':a.owner,'source_sha256s':current_sources(a.study.repo_root),'same_intent_replay_authorized':False}))
 tasks=[];projections=[];budgets=[]
 with epoch_context(a.study):
  for ordinal,identity in enumerate(identities):
   result,root=worker.run(identity,ordinal=ordinal,quote=quote);package=a.load_package(identity,worker.metadata);row=task_projection(package,root)
   tasks.append({**result,'episode_root':str(root.resolve())});projections.append(row)
   if result['actor_budget_proof'] is not None:
    verification=descriptor(a.study,package,root);receipt=verify_budget(a.study,a.owner,verification)
    a.session.authorize_verified_budget_stop(receipt['sample_paid_attempt_id'],verification=verification);budgets.append(receipt)
  coverage,ids=paid_coverage(a,tasks,budgets)
  result={'schema':'cua-full-study-selection-saved-result-v1','cell_id':a.cell,'checkpoint_sha256':a.checkpoint,'evaluator_isolated':True,'tasks':projections}
  office.write_new(worker.output/'selection-result.private.json',office.canonical(result))
  ledger={'schema':'office-current-selection-ledger-v4','tasks':tasks,'coverage':coverage,'paid_attempt_ids':ids,'source_sha256s':current_sources(a.study.repo_root),'actual_cost_usd':None,'invoice_complete':False}
  office.write_new(worker.output/'selection-ledger.private.json',office.canonical(ledger))
  if register:
   office.require(type(a.session) is policy.CampaignSession and a.owner!='shared-base','Actual CP campaign selection registration required')
   registration=a.session.record_selection_scored(attempt_id=a.started['attempt_id'],result=result,paid_attempt_ids=ids)
  else:registration=None
  return {'status':'scored','result':result,'paid_attempt_ids':ids,'coverage':coverage,'root':str(worker.output.resolve()),'registration':registration,'actual_cost_usd':None}


def admit_shared_base(worker,native_result,*,usage_reconciler=None):
 a=worker.authority;office.require(a.owner=='shared-base' and native_result['status']=='scored' and native_result['root']==str(worker.output.resolve()),'Actual all20 current shared-base result required')
 with epoch_context(a.study):
  refs=a.session.reconcile_all(usage_reconciler or (lambda request:None));root=a.session.directory
  def reference(path):return final.reference(root,Path(path))
  receipt={'schema':'office-current-shared-base-performance-v4','cell_id':a.cell,'plan_sha256':a.study.plan_sha256,'amendment_sha256':a.study.amendment_sha256,
   'checkpoint_sha256':a.checkpoint,'source_sha256s':current_sources(a.study.repo_root),'selection_attempt':a.session.attempt_id,
   'qualification_ref':{'path':str(worker.qualification_path),'sha256':worker.qualification_sha256},'metadata_ref':{'path':str(worker.metadata),'sha256':office.sha(office.private(worker.metadata))},
   'result_ref':reference(worker.output/'selection-result.private.json'),'ledger_ref':reference(worker.output/'selection-ledger.private.json'),
   'paid_attempt_ids':native_result['paid_attempt_ids'],'paid_attempt_refs':refs,'official_final_tasks_observed':0}
  path=policy.shared_receipt_path(a.study,a.cell);office.write_new(path,office.canonical(receipt));result,digest=verify_shared_receipt(a.study,a.study.budget,a.cell,path,require_registry=False)
  office.write_new(root/'accepted.private.json',office.canonical({'schema':policy.shared.REGISTRY_SCHEMA,'cell_id':a.cell,'receipt_sha256':digest}))
  return {'task_count':20,'wins':sum(r['score'] for r in result['tasks']),'receipt_sha256':digest,'actual_cost_usd':None,'invoice_complete':False}


def verify_shared_receipt(study,budget,cell_id,source,*,require_registry=True):
 require_epoch(study);root=policy.shared_receipt_path(study,cell_id).parent;receipt,raw=policy.private(source,root)
 office.require(receipt['schema']=='office-current-shared-base-performance-v4' and receipt['cell_id']==cell_id and receipt['plan_sha256']==study.plan_sha256 and receipt['amendment_sha256']==study.amendment_sha256 and receipt['source_sha256s']==current_sources(study.repo_root) and receipt['official_final_tasks_observed']==0 and budget.amendment_sha256==study.amendment_sha256,'Shared-base current source/policy changed')
 verify_qualification(study,cell_id,receipt['qualification_ref']['path'],receipt['qualification_ref']['sha256'])
 metadata=Path(receipt['metadata_ref']['path']);office.require(metadata.resolve().is_relative_to(study.repo_root/'work') and office.sha(office.private(metadata))==receipt['metadata_ref']['sha256'],'Shared-base sealed metadata changed')
 result,_=office_json_ref(root,receipt['result_ref']);ledger,_=office_json_ref(root,receipt['ledger_ref']);expected={r['task_id']:r['package_sha256'] for r in study.task_views(cell_id)['selection']}
 office.require(len(result['tasks'])==20 and {r['task_id']:r['package_sha256'] for r in result['tasks']}==expected and len(ledger['tasks'])==20 and ledger['paid_attempt_ids']==receipt['paid_attempt_ids'],'All20 original shared-base task performances required')
 cell=next(c for c in study.plan['cells'] if c['cell_id']==cell_id);office.require(receipt['checkpoint_sha256']==cell['base_checkpoint_sha256'],'Real frozen shared-base checkpoint changed')
 # Read-only projection of the existing real session; this object has no paid
 # dispatch method and cannot authorize a provider. Its references are rebuilt
 # from the authentic append-only budget and existing private session files.
 session=SimpleNamespace(study=study,directory=root,owner=cell_id+':shared-base',attempt_id=receipt['selection_attempt'])
 session.budget=budget;session.paid_references=lambda:policy._shared_paid_references(session)
 a=SimpleNamespace(study=study,session=session,started=None,cell=cell_id,owner='shared-base',checkpoint=receipt['checkpoint_sha256'])
 office.require(session.paid_references()==receipt['paid_attempt_refs'],'Shared-base actual paid references changed')
 packages=json.loads(office.private(metadata));budgets=[]
 for native,row in zip(ledger['tasks'],result['tasks']):
  office.require(native['task_id']==row['task_id'] and native['package_sha256']==row['package_sha256'] and expected.get(row['task_id'])==row['package_sha256'],'Task order/identity changed')
  candidates=[r for r in packages if r['cell_id']==cell_id and r['split']=='selection' and r['task_id']==row['task_id'] and r['package_sha256']==row['package_sha256']]
  office.require(len(candidates)==1,'Private original task metadata is not unique');entry=candidates[0]
  package=Package(entry['descriptor'],package_root=entry['package_root']);office.require(package.binding_sha256==row['package_sha256'],'Original package bytes changed')
  episode=Path(native['episode_root']);office.require(episode.resolve().is_relative_to(root),'Shared-base native task escaped session')
  checked=reopen_task(package,episode)
  for field,name in [('saved_state_sha256','saved-state.private.json'),('verifier_receipt_sha256','verifier.private.json'),('reset_receipt_sha256','reset.private.json')]:office.require(row[field]==office.sha(office.private(episode/name)),'Actual saved/verifier/reset hash changed')
  office.require(row['score']==checked['score']==native['score'],'Shared-base independently rederived score changed')
  if native['actor_budget_proof'] is not None:budgets.append(verify_budget(study,'shared-base',descriptor(study,package,episode)))
 checked_coverage,ids=paid_coverage(a,ledger['tasks'],budgets)
 office.require(ids==receipt['paid_attempt_ids'] and checked_coverage==ledger['coverage'],'All actual shared-base paid/performance coverage changed')
 if require_registry:
  marker,_=policy.private(root/'accepted.private.json',root);office.require(marker=={'schema':policy.shared.REGISTRY_SCHEMA,'cell_id':cell_id,'receipt_sha256':office.sha(raw)},'Actual shared-base acceptance registry changed')
 return result,office.sha(raw)


class TrustedFinalWorker:
 def __init__(self,*,gate,cell_id,worker_options,quote):
  office.require(type(gate) is policy.FinalGate and len(gate.freezes)==24 and cell_id in office.CELLS,'Actual all24-chain FinalGate required before hidden body/provider')
  require_epoch(gate.study);verify_qualification(gate.study,cell_id,worker_options['qualification_path'],worker_options['qualification_sha256'])
  self.gate,self.cell,self.options,self.quote=gate,cell_id,worker_options,quote
  cell=next(c for c in gate.study.plan['cells'] if c['cell_id']==cell_id);bindings=cell['matched_bindings']
  adapter=gate.study.ratification['cell_profiles'][cell_id]['adapter_sha256']
  office.require(adapter==office.sha(Path(__file__).read_bytes()),'Fresh current Office adapter ratification required')
  self._identity={'schema':final.WORKER_SCHEMA,'cell_id':cell_id,'source_snapshot_sha256':bindings['source_snapshot'],'runtime_sha256':bindings['runtime'],
   'action_contract_sha256':bindings['action_contract'],'verifier_sha256':bindings['verifier'],'adapter_source_sha256':adapter,'action_profile':'scale-action-profile-v0.6.6',
   'observation_kind':'screenshot','actor_capability':'current_frame_gui_actions_only','evaluator_isolated':True,'cold_reset_supported':True,'saved_state_readback_supported':True}
 @property
 def identity(self):return dict(self._identity)
 def run_once(self,command,output_dir):
  office.require(command['schema']==final.COMMAND_SCHEMA and command['cell_id']==self.cell and int(time.time())>self.gate.last_selection_frozen_at,'Exact prospective original Office command required')
  # This real authority checks the dispatched parent reservation before the
  # worker can load one sealed final package or construct a model process.
  with epoch_context(self.gate.study):
   authority=Authority(authority=self.gate,cell_id=self.cell,owner_slot=command['owner_slot'],final_command=command)
   worker=TaskWorker(authority=authority,output_root=Path(output_dir),**self.options)
   started_at=int(time.time());identity=authority.identities()[0];result,root=worker.run(identity,quote=self.quote);package=authority.load_package(identity,worker.metadata);task_projection(package,root)
   verification=descriptor(authority.study,package,root) if result['actor_budget_proof'] is not None else None
   from tools.office_current_evidence_v4 import final_outcome
   return final_outcome(authority,package,root,started_at,budget_verification=verification,attempt_dir=output_dir)
