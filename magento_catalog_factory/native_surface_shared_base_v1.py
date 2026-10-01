"""Read-only admission of twenty actual saved Magento shared-base episodes."""
from pathlib import Path
import json
from cursibench import full_study_runtime_v2 as runtime
from .native_surface_workers_v1 import CELL,Inputs,digest,private_json,write,require,public_binding
from .native_surface_budget_performance_v1 import audit_episode

SCHEMA='magento-native-v22-shared-base-performance'


def admit_shared_base(*,study,inputs,session,native_result,usage_reconciler):
    require(session.study is study and session.owner==CELL+':shared-base' and native_result['status']=='scored',
        'magento_actual_shared_base_session_required')
    refs=session.reconcile_all(usage_reconciler)
    root=session.directory;native=Path(native_result['task_ledger_path']).parent
    require(native.resolve().is_relative_to(root.resolve()),'magento_base_native_output_outside_owned_session')
    def ref(path):return {'path':str(path.relative_to(root)),'sha256':digest(path.read_bytes())}
    receipt={'schema':SCHEMA,'plan_sha256':study.plan_sha256,'amendment_sha256':study.amendment_sha256,
        'source_binding_sha256':inputs.binding['binding_sha256'],'base_checkpoint_sha256':session.started['checkpoint_path_sha256'],
        'selection_attempt':session.started['attempt_id'],'official_final_tasks_observed':0,'paid_coverage_sha256':native_result['performance_coverage']['coverage_sha256'],
        'result_ref':ref(native/'selection-result.private.json'),'ledger_ref':ref(native/'task-ledger.private.json'),
        'paid_attempt_ids':native_result['paid_attempt_ids'],'paid_attempt_refs':refs,
        'inputs':{'plan_path':str(inputs.plan_path),'plan_sha256':inputs.plan_sha,
            'binding_path':str(inputs.binding_path),'binding_sha256':inputs.binding_sha,
            'lane_path':str(inputs.lane_path),'lane_sha256':inputs.lane_sha,'output_root':str(inputs.output)}}
    path=runtime.shared_receipt_path(study,CELL);write(root,path.name,receipt)
    result,sha=verify_shared_receipt(study,study.budget,CELL,path,require_registry=False)
    write(root,'accepted.private.json',{'schema':runtime.shared.REGISTRY_SCHEMA,'cell_id':CELL,'receipt_sha256':sha})
    return {'task_count':20,'wins':sum(row['score'] for row in result['tasks']),'receipt_sha256':sha,
        'actual_cost_usd':None,'invoice_complete':False}


def verify_shared_receipt(study,budget,cell_id,source,*,require_registry=True):
    require(cell_id==CELL,'magento_shared_wrong_cell')
    root=runtime.shared_receipt_path(study,CELL).parent
    receipt,raw=runtime.private(source,root)
    require(set(receipt)=={'schema','plan_sha256','amendment_sha256','source_binding_sha256','base_checkpoint_sha256',
        'selection_attempt','official_final_tasks_observed','paid_coverage_sha256','result_ref','ledger_ref','paid_attempt_ids','paid_attempt_refs','inputs'} and
        receipt['schema']==SCHEMA and receipt['plan_sha256']==study.plan_sha256 and
        receipt['amendment_sha256']==study.amendment_sha256==budget.amendment_sha256 and
        receipt['official_final_tasks_observed']==0,'magento_shared_policy_binding_changed')
    inputs=Inputs(**receipt['inputs'])
    require(inputs.binding['binding_sha256']==receipt['source_binding_sha256']==public_binding()['binding_sha256'],
        'magento_shared_source_epoch_changed')
    def read(reference):
        from cursibench.full_study_final_dispatch_v1 import private_reference
        path,content=private_reference(root,reference,'actual_magento_base_evidence');return path,json.loads(content)
    result_path,result=read(receipt['result_ref']);_,ledger=read(receipt['ledger_ref'])
    identities=[{k:r[k] for k in ('task_id','package_sha256')} for r in study.task_views(CELL)['selection']]
    require(result=={'schema':'cua-full-study-selection-saved-result-v1','cell_id':CELL,
        'checkpoint_sha256':receipt['base_checkpoint_sha256'],'evaluator_isolated':True,'tasks':ledger['tasks']} and
        len(result['tasks'])==20 and ledger['paid_attempt_ids']==receipt['paid_attempt_ids'] and
        ledger['amendment_sha256']==study.amendment_sha256 and ledger['source_binding_sha256']==inputs.binding['binding_sha256'],
        'magento_shared_twenty_saved_results_changed')
    task_by_id={}
    for identity,row,folder in zip(identities,result['tasks'],ledger['episode_dirs'],strict=True):
        require({k:row[k] for k in ('task_id','package_sha256')}==identity,'magento_shared_task_identity_changed')
        episode=result_path.parent/folder;native=private_json(episode/'native-row.private.json');audit=audit_episode(episode,native)
        require(row['score']==native['score'] and all(row[field]==digest((episode/name).read_bytes()) for field,name in
            [('saved_state_sha256','saved-state.private.json'),('verifier_receipt_sha256','verifier.private.json'),('reset_receipt_sha256','reset.private.json')]),
            'magento_shared_saved_reset_hash_changed')
        task_by_id[row['task_id']]={'frame_shas':{frame['frame']['sha256'] for frame in audit['frames']}}
    checked=runtime._verify_shared_paid_v2(study,budget,CELL,root,receipt,identities,task_by_id)
    require(checked==ledger['coverage'],'magento_shared_coverage_changed')
    if require_registry:
        marker=private_json(root/'accepted.private.json')
        require(marker=={'schema':runtime.shared.REGISTRY_SCHEMA,'cell_id':CELL,'receipt_sha256':digest(raw)},'magento_shared_registry_changed')
    return result,digest(raw)
