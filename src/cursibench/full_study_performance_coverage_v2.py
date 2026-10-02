"""Explicit amended performance coverage; inference/invoices stay independent.

Callers supply only receipts produced by the checked saved/reset adapter. This
does not register an attempt, invent paid results or settle a usage ledger.
"""
from . import full_study_policy_amendment_v2 as policy
from . import full_study_selection_environment_v2 as environment
from . import scale_final_v06 as common


def validate(*,plan,amendment,cell_id,owner_slot,attempt_id,checkpoint_sha256,selection_tasks,
             paid_calls,related_paid_attempt_ids,budget_performance_receipts):
    amendment_sha=policy.validate(amendment,plan)
    expected={v['task_id']:v['package_sha256'] for v in selection_tasks}
    if owner_slot not in amendment['configuration_slots'] or len(selection_tasks)!=20 or len(expected)!=20 or cell_id not in amendment['retained_task_scope']['cells'] or not common.is_hash(checkpoint_sha256):
        raise ValueError('matched_twenty_task_scope_required')
    environment_category=environment.category(cell_id)
    included=set();sampled=set();environments=set();completed=0;unknown=0;completion_unknown=0;known_late=0;not_submitted=0;used=set()
    budget={v['sample_paid_attempt_id']:v for v in budget_performance_receipts}
    if len(budget)!=len(budget_performance_receipts):raise ValueError('duplicate_budget_receipt')
    for paid in paid_calls:
        if set(paid)!={'attempt_id','category','request','result_present','result_status'}:raise ValueError('paid_call_shape_changed')
        identifier=paid['attempt_id'];request=paid['request'];kind=paid['category']
        if identifier in included or not identifier.startswith(attempt_id+'-') or request.get('cell_id')!=cell_id or request.get('selection_attempt')!=attempt_id:
            raise ValueError('paid_attempt_unbound_or_duplicate')
        included.add(identifier)
        task=request.get('task_id')
        if task is None:
            if not paid['result_present']:raise ValueError('setup_or_batch_environment_incomplete')
            if kind==environment_category:
                if type(request.get('selection_tasks')) is not list or len(request['selection_tasks'])!=20 or {r.get('task_id'):r.get('package_sha256') for r in request['selection_tasks']}!=expected:raise ValueError('batch_environment_task_scope_changed')
                environments.update(expected)
            elif kind!='tinker':raise ValueError('environment_category_changed')
            continue
        if task not in expected or request.get('package_sha256')!=expected[task] or request.get('checkpoint_path_sha256')!=checkpoint_sha256:
            raise ValueError('task_or_checkpoint_changed')
        if kind==environment_category:
            if not paid['result_present']:raise ValueError('environment_incomplete')
            environments.add(task)
        elif kind=='tinker':
            if paid['result_present'] is True and paid['result_status']=='completed':
                sampled.add(task);completed+=1;continue
            receipt=budget.get(identifier)
            if (receipt is None or receipt.get('schema')!='cua-verified-budget-performance-with-unknown-billing-v22' or
                receipt.get('amendment_sha256')!=amendment_sha or receipt.get('task_id')!=task or
                receipt.get('package_sha256')!=expected[task] or receipt.get('checkpoint_sha256')!=checkpoint_sha256 or
                receipt.get('owner_slot')!=owner_slot or
                receipt.get('performance_coverage_eligible') is not True or receipt.get('provider_close_acknowledged') is not True or
                receipt['performance'].get('status')!='independently_saved_scored_and_reset' or type(receipt['performance'].get('score')) is not int or receipt['performance'].get('score') not in (0,1) or
                receipt['inference'].get('status') not in {'completion_unknown_after_actor_deadline','late_completed_withheld_from_gui','not_submitted_before_actor_deadline'} or receipt['inference'].get('unknown_response_is_completed') is not False or receipt['inference'].get('request_replayed') is not False or
                receipt['billing'].get('actual_usd') is not None or receipt.get('formal_registration_performed') is not False or
                not all(common.is_hash(v) for v in receipt.get('evidence_sha256',{}).values()) or
                set(receipt.get('evidence_sha256',{}))!={'saved-state.private.json','verifier.private.json','reset.private.json',
                    'actor-clock.private.json','actor-budget-stop.private.json','task.private.json'}):
                raise ValueError('uncertain_call_has_no_checked_budget_performance')
            sampled.add(task);unknown+=1;used.add(identifier)
            status=receipt['inference']['status']
            completion_unknown+=status=='completion_unknown_after_actor_deadline'
            known_late+=status=='late_completed_withheld_from_gui'
            not_submitted+=status=='not_submitted_before_actor_deadline'
        else:raise ValueError('environment_category_changed')
    if included!=related_paid_attempt_ids or sampled!=set(expected) or environments!=set(expected) or used!=set(budget):
        raise ValueError('performance_coverage_or_retained_paid_set_incomplete')
    value={'schema':'cua-full-study-independent-performance-coverage-v2','amendment_sha256':amendment_sha,
        'cell_id':cell_id,'owner_slot':owner_slot,'selection_attempt':attempt_id,'checkpoint_sha256':checkpoint_sha256,
        'task_count':20,'completed_model_response_count':completed,
        'verified_budget_ended_unknown_response_count':unknown,
        'model_completion_unknown_count':completion_unknown,'known_late_withheld_response_count':known_late,
        'not_submitted_before_deadline_count':not_submitted,'all_paid_intents_retained':True,
        'performance_coverage_complete':True,'inference_completion_complete':unknown==0,
        'provider_invoice_verified':False,'actual_cost_usd':None,'formal_registration_performed':False}
    return {**value,'coverage_sha256':policy.sha(policy.canonical(value))}
