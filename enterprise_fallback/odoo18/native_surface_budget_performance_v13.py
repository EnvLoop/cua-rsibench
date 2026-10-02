"""Read-only actual saved Odoo budget performance; no scoring declarations."""
from __future__ import annotations
from hashlib import sha256
import importlib
import json
from pathlib import Path
from cursibench import full_study_final_dispatch_v1 as files
from cursibench.native_surface_guard_policy_v1 import GuardError
from native_desktop_factory.deadline_model_transport_v21 import checked_deadline_proof
from . import native_surface_workers_v13 as workers
from .native_surface_final_worker_v1 import _evaluate

FIELDS={'schema','cell_id','episode_root','native_binding','task','native_row','live_saved_proof',
    'provider_close','lifecycle','actor_clock','actor_budget_stop','sample_paid_attempt_id'}


def require(value,code):
    if not value:raise GuardError(code)


def verify_budget_performance(*,study,owner_slot,verification):
    require(type(verification) is dict and set(verification)==FIELDS and
        verification['schema']=='odoo-budget-performance-input-v13' and verification['cell_id']=='odoo-community',
        'odoo_budget_performance_descriptor_changed')
    root=Path(verification['episode_root'])
    require(root.is_dir() and not root.is_symlink() and root.stat().st_mode&0o077==0 and
        root.resolve().is_relative_to((study.repo_root/'work').resolve()),'odoo_budget_episode_outside_owned_work')
    def read(ref):
        _path,raw=files.private_reference(root,ref,'odoo_budget_evidence')
        value=json.loads(raw);require(type(value) is dict,'odoo_budget_evidence_object_required')
        return value,sha256(raw).hexdigest()
    binding,_=read(verification['native_binding']);workers.validate_binding(binding)
    task,task_sha=read(verification['task'])
    require(set(task)=={'attempt_id','task_id','package_sha256','owner_slot','checkpoint_sha256','amendment_sha256'} and
        task['owner_slot']==owner_slot and task['amendment_sha256']==study.amendment_sha256,
        'odoo_budget_task_owner_or_amendment_unbound')
    identity={'task_id':task['task_id'],'package_sha256':task['package_sha256']}
    row,_=read(verification['native_row'])
    require(all(row.get(k)==v for k,v in identity.items()) and row['termination']=='task_wall_budget',
        'odoo_budget_native_row_task_or_stop_changed')
    # Every native saved file, raw frame, sampler journal, reset and action
    # capsule is checked by the actual source-bound auditor first.
    _teacher,selection=workers._model_modules(binding)
    selection._audit_task_artifacts(root,identity,row)
    saved,saved_sha=read({'path':'saved-state.private.json','sha256':row['saved_state_sha256']})
    verdict,verdict_sha=read({'path':'verifier.private.json','sha256':row['verifier_receipt_sha256']})
    reset,reset_sha=read({'path':'reset.private.json','sha256':row['reset_receipt_sha256']})
    proof,_=read(verification['live_saved_proof'])
    require(proof['observed']==saved['business_snapshot'],'odoo_budget_scored_state_not_saved')
    native_verify=importlib.import_module('enterprise_fallback.odoo18.verify')
    context=proof['context']
    independent=_evaluate(context['family'],task['task_id'],context['target'],context['baseline'],saved['business_snapshot'],
        proof['physical_files'],context['frozen_files'],proof['attachment_paths'],native_verify)
    require(independent==proof['verdict'] and verdict['score']==row['score']==int(independent['reward']==1.0 and
        independent['checks_passed'] is True and independent['difference_codes']==[]),'odoo_budget_saved_score_not_rederived')
    require(reset['pre_database_filestore_exact'] is True and reset['post_database_filestore_exact'] is True and
        reset['baseline_semantic_sha256']==reset['restored_semantic_sha256'],'odoo_budget_reset_not_exact')
    clock,clock_sha=read(verification['actor_clock']);stop,stop_sha=read(verification['actor_budget_stop'])
    require(clock['schema']=='odoo-actual-actor-clock-v1' and clock['task_id']==task['task_id'] and
        clock['package_sha256']==task['package_sha256'] and clock['model_outcome']=='task_wall_budget' and
        clock['actor_deadline_monotonic']-clock['actor_started_monotonic']==720 and clock['actor_elapsed_seconds']==720 and
        clock['actor_ended_monotonic']==clock['actor_deadline_monotonic'] and
        clock['raw_end_acknowledged_monotonic']>=clock['actor_deadline_monotonic'] and
        clock['native_actions_after_deadline']==0 and clock['evaluation_outside_actor_clock'] is True,
        'odoo_budget_actual_actor_clock_changed')
    checked=checked_deadline_proof(stop['actor_deadline_proof'],clock['actor_deadline_monotonic'])
    require(clock['deadline_proof']==checked.receipt() and stop['model_response_used_for_gui'] is False and
        stop['same_request_replay_authorized'] is False and stop['native_io_called'] is False,
        'odoo_budget_stop_not_typed_or_replayed')
    for item in clock['native_io']:
        intent,_=read({'path':item['intent']['path'],'sha256':item['intent']['sha256']})
        completion,_=read({'path':item['completion']['path'],'sha256':item['completion']['sha256']})
        require(item['status']=='returned' and clock['actor_started_monotonic']<=item['started_monotonic']<=item['completed_monotonic']<=clock['actor_deadline_monotonic'] and
            intent['operation']==completion['operation']==item['operation'] and completion['status']=='returned',
            'odoo_budget_native_io_unknown_late_or_unbound')
    close,_=read(verification['provider_close']);life,_=read(verification['lifecycle'])
    require(close['status']=='acknowledged' and close['real_close_call_returned'] is True and
        close['automatic_model_retries']==0 and close['new_model_requests']==0 and
        life['schema']=='odoo-owned-complete-lifecycle-v12' and life['attempt_id']==task['attempt_id'] and
        life['ended_monotonic']>=close['close_ended_monotonic'] and
        0<=life['ended_monotonic']-life['started_monotonic']<=1200 and life['saved_readback_reset_and_provider_close_complete'] is True,
        'odoo_budget_owned_cleanup_or_close_unproved')
    require(life.get('actor_clock')==row['actor_clock_ref'] and life.get('provider_close') is not None and
        life['provider_close']['sha256']==verification['provider_close']['sha256'] and
        all(life.get('batch_cleanup',{}).get(name) is True for name in ('services_restored_to_initial_state',
            'final_database_snapshot_equal','final_physical_filestore_equal')),
        'odoo_budget_complete_lifecycle_not_bound_to_actual_cleanup')
    usage,_=read({'path':'usage.private.json','sha256':row['usage_sha256']})
    pending=[item for item in usage['samples'] if item['status']=='actor_deadline_proven']
    require(len(pending)==1 and pending[0]['paid_attempt_id']==verification['sample_paid_attempt_id'],
        'odoo_budget_actual_paid_request_missing')
    sample=workers.native_ref_bytes(root,pending[0]['deadline_evidence']);sample=json.loads(sample)
    require(sample['task_id']==task['task_id'] and sample['package_sha256']==task['package_sha256'] and
        sample['actor_deadline_proof']==checked.receipt() and sample['sampling_failure']['status']=='error' and
        sample['sampling_failure']['new_dispatch'] is True and sample['sampling_failure']['reused'] is False,
        'odoo_budget_unknown_response_not_retained_or_completed')
    completed=sum(item['status']=='completed' for item in usage['samples'])
    inference_status=('not_submitted_before_actor_deadline' if not checked.model_dispatch_may_have_occurred else
        'late_completed_withheld_from_gui' if checked.model_completion_known else 'completion_unknown_after_actor_deadline')
    return {'schema':'cua-verified-budget-performance-with-unknown-billing-v22',
        'task_id':task['task_id'],'package_sha256':task['package_sha256'],'owner_slot':owner_slot,
        'checkpoint_sha256':task['checkpoint_sha256'],
        'performance':{'status':'independently_saved_scored_and_reset','score':row['score']},
        'inference':{'status':inference_status,'unknown_response_is_completed':False,'request_replayed':False,'completed_model_response_count':completed},
        'billing':{'actual_usd':None},'provider_close_acknowledged':True,
        'sample_paid_attempt_id':verification['sample_paid_attempt_id'],
        'evidence_sha256':{'saved-state.private.json':saved_sha,'verifier.private.json':verdict_sha,
            'reset.private.json':reset_sha,'actor-clock.private.json':clock_sha,
            'actor-budget-stop.private.json':stop_sha,'task.private.json':task_sha},
        'amendment_sha256':task['amendment_sha256'],'performance_coverage_eligible':True,
        'formal_registration_performed':False}
