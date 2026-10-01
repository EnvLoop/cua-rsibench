"""Explicit pre-result policy amendment; never mutates an older frozen plan."""
from __future__ import annotations
import copy
import hashlib
import json
from . import full_study_budget_v1 as legacy
from . import full_study_matrix_v1 as matrix
from . import full_study_selection_environment_v2 as environment

SCHEMA='cua-full-study-unlimited-dollar-and-budget-performance-policy-v2'


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def build(plan,*,user_authorization_sha256,pre_result_review_sha256,official_model_results_before=0):
    plan_sha,_,limits=legacy._plan_limits(plan)
    legacy._hash(user_authorization_sha256,'direct human authorization')
    legacy._hash(pre_result_review_sha256,'pre-result scope review')
    if type(official_model_results_before) is not int or official_model_results_before!=0:
        raise ValueError('policy_amendment_must_precede_official_results')
    retained={}
    for intent in plan['campaign_intents']:
        if intent.get('campaign_hours_cap')!=16 or not isinstance(intent.get('matched_count_caps'),dict) or not intent['matched_count_caps']:
            raise ValueError('explicit_16h_and_matched_compute_caps_required')
        owner=intent['cell_id']+':'+intent['researcher_id']
        retained[owner]={k:copy.deepcopy(intent[k]) for k in ['campaign_hours_cap','matched_count_caps','e2b_sandbox_hours_cap']}
    return {'schema':SCHEMA,'status':'pre_result_uniform_amendment',
        'parent_plan_sha256':plan_sha,'user_authorization_sha256':user_authorization_sha256,
        'pre_result_review_sha256':pre_result_review_sha256,'official_model_results_before_amendment':0,
        'dollar_policy':'unlimited_authorized_spend_no_programmatic_dollar_ceiling',
        'global_usd_ceiling':None,'category_usd_ceilings':None,'owner_usd_ceilings':None,
        'direct_human_spending_authorized':True,'funding_availability_is_not_assumed':True,
        'owners':sorted(limits),'configuration_slots':['shared-base',*matrix.RESEARCHERS],
        'retained_campaign_compute_limits':retained,
        'retained_task_limits':{'max_actions':90,'actor_seconds':720,'lease_seconds':1200},
        'retained_task_scope':{'cells':list(matrix.CELLS),'campaigns':24,'official_identities':600,
                               'selection_tasks_per_slot':20,'final_tasks_per_slot':100,
                               'initial_slot_task_results':3000},
        'performance_policy':'verified_budget_ended_task_is_scored_with_inference_and_billing_separate',
        'required_performance_evidence':['saved_state','independent_verifier','fresh_distinct_reset',
            'owned_guest_cleanup','proven_no_late_gui','provider_close_ack'],
        'earlier_provider_fault_is_infrastructure_invalid':True,
        'unknown_cost_is_null_not_zero':True,'unknown_inference_is_not_completed':True,
        'same_request_replay_authorized':False,'old_results_reclassified':False,
        'effective_environment_categories':environment.BY_CELL,
        'environment_policy_sha256':environment.binding_sha256(),
        'owned_native_office_account_lease_seconds':1200,
        'e2b_calls_not_fabricated_for_owned_office_account':True}


def validate(value,plan):
    if not isinstance(value,dict):raise ValueError('policy_amendment_object_required')
    expected=build(plan,user_authorization_sha256=value.get('user_authorization_sha256'),
        pre_result_review_sha256=value.get('pre_result_review_sha256'),
        official_model_results_before=value.get('official_model_results_before_amendment'))
    if value!=expected:raise ValueError('uniform_policy_amendment_changed')
    return sha(canonical(value))
