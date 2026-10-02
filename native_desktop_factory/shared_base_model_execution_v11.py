"""Desktop shared-base bridge preserving both actor and reset paid leases.

The old generic verifier admits one environment call per task. This additive
Desktop verifier retains every lease/sample, reopens native evidence, requires
settled account usage, and returns the same selection-only feedback contract.
Other cells continue through their original verifier.
"""
from __future__ import annotations
import json
from pathlib import Path
from decimal import Decimal

from cursibench import full_study_shared_base_execution_v1 as engine
from cursibench import full_study_shared_base_selection_v1 as shared
from cursibench import full_study_selection_paid_coverage_v1 as coverage
from . import model_transport_integration_v11 as integration
from . import prospective_model_worker_v11 as model
from .factory import digest

SCHEMA='cua-native-desktop-v11-shared-base-selection'
LEGACY_VERIFY=shared.verify_receipt


def verify_receipt(study,budget,cell_id:str,source:Path,*,require_registry:bool=True):
 if cell_id!='desktop-native':return LEGACY_VERIFY(study,budget,cell_id,source,require_registry=require_registry)
 admitted=integration.bind_frozen_study(study,admissions_path=study._desktop_v11_admissions_path,
                                      proposal_path=study._desktop_v11_proposal_path)
 expected=shared.receipt_path(study,cell_id);root=expected.parent
 integration.require(source.resolve()==expected.resolve() and budget.plan_sha256==study.plan_sha256,
                     'v11_shared_base_path_or_budget_changed')
 receipt,raw=shared._private_json(source,root);sha=digest(raw)
 p=integration.proposal();cell=next(r for r in study.plan['cells'] if r['cell_id']==cell_id)
 integration.require(set(receipt)=={'schema','plan_sha256','checkpoint_sha256','worker_runtime_sha256','proposal_sha256',
    'admissions_sha256','result_ref','batch_ref','paid_attempt_refs','paid_attempt_ids','official_final_tasks_observed'} and
    receipt['schema']==SCHEMA and receipt['plan_sha256']==study.plan_sha256 and
    receipt['checkpoint_sha256']==cell['base_checkpoint_sha256']==p['base_checkpoint_sha256'] and
    receipt['worker_runtime_sha256']==p['worker_runtime_sha256'] and
    receipt['proposal_sha256']==digest(study._desktop_v11_proposal_path.read_bytes()) and
    receipt['admissions_sha256']==digest(study._desktop_v11_admissions_path.read_bytes()) and
    receipt['official_final_tasks_observed']==0,'v11_shared_base_source_not_current')
 result,_=shared._json_ref(root,receipt['result_ref']);batch,_=shared._json_ref(root,receipt['batch_ref'])
 identities=list(study.task_views(cell_id)['selection'])
 expected_ids=[{k:r[k] for k in ['task_id','package_sha256']} for r in identities]
 integration.require(result['schema']=='cua-full-study-selection-saved-result-v1' and result['cell_id']==cell_id and
    result['checkpoint_sha256']==p['base_checkpoint_sha256'] and result['evaluator_isolated'] is True and
    [{k:r[k] for k in ['task_id','package_sha256']} for r in result['tasks']]==expected_ids and
    batch['task_count']==20 and batch['result_sha256']==receipt['result_ref']['sha256'],'v11_shared_base_result_changed')
 worker=model.DesktopProspectiveModelWorker(study=study,admissions_path=study._desktop_v11_admissions_path,
                                          proposal_path=study._desktop_v11_proposal_path)
 packages=worker._packages(admitted,identities,'selection')
 salt=json.loads(integration.controls.private(Path(admitted['private_map'])))['variant_salt']
 frames={};native=root/'native'
 for package,row in zip(packages,result['tasks']):
  out=native/'gui'/row['task_id']/'evaluator'
  task=json.loads(integration.controls.private(out/'task.private.json'))
  integration.require(all(task[k]==row[k] for k in row),'v11_shared_base_native_score_unbound')
  for key,name in [('saved_state_sha256','saved-state.private.json'),('verifier_receipt_sha256','verifier.private.json'),
                   ('reset_receipt_sha256','reset.private.json')]:
   integration.require(digest(integration.controls.private(out/name))==row[key],'v11_shared_base_native_artifact_changed')
  trace=json.loads(integration.controls.private(out/'actions.private.json'))
  worker._audit_episode(batch=native,out=out,package=package,salt=salt,actions=[r['action'] for r in trace if 'action' in r])
  frames[row['task_id']]={r['sampled_frame']['sha256'] for r in trace}
 owner=budget.owner_attempts(cell_id+':shared-base')
 records={k:r for k,r in owner.items() if r['category']!='shared_base_final'}
 integration.require(set(records)==set(receipt['paid_attempt_ids']) and len(records)==len(receipt['paid_attempt_ids']) and
                     len(receipt['paid_attempt_refs'])==len(records),'v11_shared_base_all_paid_intents_required')
 calls=[];seen=set();leases={r['task_id']:set() for r in expected_ids}
 for ref in receipt['paid_attempt_refs']:
  paid_id=ref['attempt_id'];integration.require(paid_id not in seen and paid_id in records,'v11_shared_base_duplicate_paid_record')
  seen.add(paid_id);record=records[paid_id]
  request,request_raw=shared._json_ref(root,ref['request_ref']);paid_result,_=shared._json_ref(root,ref['result_ref'])
  usage,usage_raw=shared._json_ref(root,ref['usage_ref'])
  worker_request,_=shared._json_ref(root,request['worker_request_ref'])
  worker_result,_=shared._json_ref(root,paid_result['worker_result_ref'])
  integration.require(record['status']=='settled' and record['category']==ref['category']==request['category'] and
    record['request_sha256']==digest(request_raw) and record['work_sha256']==digest(request_raw) and
    record['evidence_sha256']==digest(usage_raw) and Decimal(usage['actual_usd'])==Decimal(record['actual_usd']) and
    Decimal(record['actual_usd'])<=Decimal(record['reserved_usd']) and usage['invoice_basis']=='provider_invoice' and
    usage['provider_invoice_usd']==usage['actual_usd'],'v11_shared_base_usage_not_account_reconciled')
  shared._reference(root,usage['source_ref'])
  integration.require(worker_request==json.loads(integration.controls.private(native/'paid'/(paid_id+'.request.private.json'))) and
    worker_result==json.loads(integration.controls.private(native/'paid'/(paid_id+'.result.private.json'))),
    'v11_shared_base_paid_request_or_model_result_changed')
  task_id=worker_request.get('task_id');category=ref['category']
  if task_id is not None:
   integration.require(task_id in frames and worker_request['checkpoint_path_sha256']==p['base_checkpoint_sha256'],
                       'v11_shared_base_paid_task_changed')
   if category=='e2b':
    integration.require(worker_request['lease_seconds']==1200 and worker_request['phase'] in ['actor','reset'],
                        'v11_shared_base_lease_policy_changed')
    leases[task_id].add(worker_request['phase'])
   else:
    integration.require(worker_request['frame_sha256'] in frames[task_id] and worker_result['status']=='completed' and
                        worker_result['reported_model']==integration.matrix.STUDENT,'v11_shared_base_real_model_frame_unbound')
  calls.append({'attempt_id':paid_id,'category':category,'request':request,'result_present':True,'result_status':paid_result['status']})
 integration.require(all(phases=={'actor','reset'} for phases in leases.values()),'v11_shared_base_separate_reset_lease_missing')
 coverage.validate(cell_id=cell_id,attempt_id='base-selection-desktop-native',checkpoint_sha256=p['base_checkpoint_sha256'],
  selection_tasks=identities,selection_identities_sha256=digest(integration.canonical(identities)),paid_calls=calls,related_paid_attempt_ids=set(records))
 if require_registry:
  marker,_=shared._private_json(root/'accepted.private.json',root)
  integration.require(marker=={'schema':shared.REGISTRY_SCHEMA,'cell_id':cell_id,'receipt_sha256':sha},'v11_shared_base_registry_changed')
 return result,sha


def execute(study,*,worker:model.DesktopProspectiveModelWorker,usage_reconciler):
 """Gated executable baseline; reconciliation is required before campaign use."""
 worker._gate()
 integration.require(worker.study is study and callable(usage_reconciler),'v11_shared_base_worker_or_reconciler_missing')
 with integration.runtime_context():
  session=engine.SharedBaseSession(study,'desktop-native')
  native=worker.run_base_selection(session=session,out_dir=session.directory/'native')
  integration.require(native['status']=='scored' and native['paid_attempt_ids']==list(session.completed_paid),
                      'v11_shared_base_native_run_incomplete')
  paid=session.reconcile_all(usage_reconciler)
  root=session.directory
  receipt={'schema':SCHEMA,'plan_sha256':study.plan_sha256,'checkpoint_sha256':integration.proposal()['base_checkpoint_sha256'],
    'worker_runtime_sha256':integration.proposal()['worker_runtime_sha256'],
    'proposal_sha256':digest(study._desktop_v11_proposal_path.read_bytes()),
    'admissions_sha256':digest(study._desktop_v11_admissions_path.read_bytes()),
    'result_ref':{'path':'native/selection-result.private.json','sha256':native['result_sha256']},
    'batch_ref':{'path':'native/batch.private.json','sha256':native['batch_receipt_sha256']},
    'paid_attempt_refs':paid,'paid_attempt_ids':list(session.completed_paid),'official_final_tasks_observed':0}
  path=shared.receipt_path(study,'desktop-native');model.write(path,receipt)
  return study.admit_shared_base_selection('desktop-native',path)
