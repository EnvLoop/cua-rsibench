"""Amended results audit; actual costs are nullable, full performance is not."""
from pathlib import Path
import json
from decimal import Decimal
from . import full_study_runtime_v2 as runtime
from . import full_study_final_dispatch_v1 as final
from . import full_study_results_v1 as legacy
from . import full_study_policy_amendment_v2 as policy


def audit(gate,execution_index,root):
    if type(gate) is not runtime.FinalGate:raise ValueError('real_v2_final_gate_required')
    root=Path(root);expected={(cell,owner) for cell in runtime.matrix.CELLS
        for owner in set(next(v for v in gate.plan['cells'] if v['cell_id']==cell)['execution_evidence_owner_by_slot'].values())}
    if type(execution_index) is not dict or set(execution_index)!={'schema','policy_manifest_sha256','amendment_sha256','executions'} or execution_index['schema']!='cua-full-study-performance-execution-index-v2' or execution_index['policy_manifest_sha256']!=gate.study.manifest_sha256 or execution_index['amendment_sha256']!=gate.study.amendment_sha256:
        raise ValueError('performance_index_policy_changed')
    seen=set();scores={};costs=[]
    for entry in execution_index['executions']:
        if set(entry)!={'cell_id','owner_slot','receipt'}:raise ValueError('execution_entry_shape_changed')
        key=(entry['cell_id'],entry['owner_slot'])
        if key not in expected or key in seen:raise ValueError('execution_owner_duplicate_or_unknown')
        seen.add(key);execution_path,raw=final.private_reference(root,entry['receipt'],'performance_execution')
        value=json.loads(raw);cell=next(v for v in gate.plan['cells'] if v['cell_id']==key[0])
        packages=legacy._task_packages(cell['base']);slot=cell['base'] if key[1]=='shared-base' else cell['researcher_plans'][key[1]]
        if value.get('schema')!='cua-full-study-final-performance-execution-v2' or value.get('status')!='complete' or value.get('cell_id')!=key[0] or value.get('owner_slot')!=key[1] or value.get('checkpoint_sha256')!=slot['bindings']['checkpoint'] or value.get('amendment_sha256')!=gate.study.amendment_sha256 or len(value.get('tasks',[]))!=100:
            raise ValueError('all_100_checked_tasks_required')
        tasks={};ids=set()
        for task in value['tasks']:
            identifier=task['task_id']
            if identifier in tasks or packages.get(identifier)!=task['package_sha256'] or type(task['score']) is not int or task['score'] not in (0,1) or not all(final.evidence.is_hash(task[k]) for k in ('saved_state_sha256','verifier_receipt_sha256','reset_receipt_sha256','observation_trace_sha256','action_trace_sha256')):
                raise ValueError('task_performance_or_saved_reset_binding_changed')
            for attempt in task['attempts']:
                if attempt['attempt_id'] in ids or not final.evidence.is_hash(attempt['receipt_sha256']):raise ValueError('retained_attempt_duplicate')
                ids.add(attempt['attempt_id'])
                out=execution_path.parent.parent/attempt['attempt_id']
                actual,attempt_raw=final.private_json(out/'attempt-receipt.private.json',root,'retained_final_attempt')
                if policy.sha(attempt_raw)!=attempt['receipt_sha256'] or actual.get('attempt_id')!=attempt['attempt_id'] or actual.get('task_id')!=identifier or actual.get('package_sha256')!=task['package_sha256'] or actual.get('checkpoint_sha256')!=value['checkpoint_sha256']:
                    raise ValueError('actual_private_attempt_identity_or_hash_changed')
                checked={}
                for name,ref in actual['artifact_refs'].items():
                    if ref is not None:
                        _,artifact=final.private_reference(out,ref,name);checked[name]=artifact
                if actual['status']=='scored':
                    if actual['score'] not in (0,1) or not all(k in checked for k in ('saved_state','verifier','reset','actor_clock')):
                        raise ValueError('saved_reset_clock_missing')
                    verifier=json.loads(checked['verifier']);reset=json.loads(checked['reset']);clock=json.loads(checked['actor_clock'])
                    if verifier.get('score')!=actual['score'] or verifier.get('saved_state_sha256')!=policy.sha(checked['saved_state']) or verifier.get('independent_of_actor') is not True or verifier.get('gold_withheld_from_actor') is not True or verifier.get('no_regression_checked') is not True or (actual['score']==1 and verifier.get('no_regression_passed') is not True):
                        raise ValueError('independent_saved_score_unbound')
                    initial=gate.initial_state_by_task[key[0]][identifier]
                    if reset.get('fresh_environment') is not True or reset.get('restored_after_attempt') is not True or reset.get('initial_state_sha256')!=initial or reset.get('restored_state_sha256')!=initial:
                        raise ValueError('fresh_exact_reset_missing')
                    if clock.get('actor_seconds_limit')!=720 or clock.get('max_actions')!=90 or clock.get('native_actions_after_deadline')!=0 or not 0<=clock.get('actor_wall_time_ms',-1)<=720000:
                        raise ValueError('uniform_actual_actor_clock_required')
                record=gate.budget.owner_attempts(key[0]+':'+key[1]).get(attempt['attempt_id'])
                if record is None:raise ValueError('authentic_paid_intent_not_retained')
                if actual['cost_usd'] is None:
                    if record['actual_usd'] is not None or record['status'] not in {'dispatched','uncertain'}:raise ValueError('unknown_bill_was_invented')
                elif record['status']!='settled' or record['actual_usd']!=actual['cost_usd'] or record['evidence_sha256']!=actual['usage_receipt_sha256']:
                    raise ValueError('authentic_charge_not_reconciled')
            tasks[identifier]=task['score']
        if set(tasks)!=set(packages):raise ValueError('official_task_scope_changed')
        if value['cost_usd'] is None:
            if value['invoice_complete'] is not False:raise ValueError('unknown_cost_is_not_invoice_complete')
        else:
            legacy.actual_usd(value['cost_usd'],'authentic observed cost')
        scores[key]=tasks;costs.append(value['cost_usd'])
    if seen!=expected:raise ValueError('all_cells_unique_checkpoint_results_required')
    slot_count=sum(len(scores[(cell,owner)]) for cell in runtime.matrix.CELLS
        for owner in next(v for v in gate.plan['cells'] if v['cell_id']==cell)['execution_evidence_owner_by_slot'].values())
    if slot_count!=3000:raise ValueError('all_3000_slot_task_results_required')
    return {'schema':'cua-full-study-amended-performance-results-v2','amendment_sha256':gate.study.amendment_sha256,
        'distinct_official_task_identities':600,'slot_task_results':3000,'performance_complete':True,
        'actual_total_usd':None if any(v is None for v in costs) else str(sum((Decimal(v) for v in costs),Decimal(0))),
        'provider_invoice_complete':all(v is not None for v in costs),'dollar_ceiling_usd':None,
        'paper_budget_wording':runtime.paper_budget_wording(),'official_result_publication_performed':False}
