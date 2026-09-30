"""Checked budget-ended performance, independent of inference/billing status.

No actor/provider call, invented sample response, task score or charge occurs.
This adapter requires a pre-result amendment and actual uniform v21 artifacts.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from cursibench import full_study_policy_amendment_v2 as policy
from . import prospective_model_worker_v21 as worker
from . import model_transport_integration_v21 as integration


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def private_json(path,root):
    path=Path(path).absolute();root=Path(root).resolve()
    if path.resolve()!=path or not path.is_relative_to(root) or path.is_symlink():
        raise ValueError('budget_performance_private_path_changed')
    raw=integration.controls.private(path)
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('budget_performance_object_required')
    return value


def verify(*,plan,amendment,owner_slot,batch,evaluator,package,private_salt,checkpoint_sha256):
    amendment_sha=policy.validate(amendment,plan)
    if owner_slot not in amendment['configuration_slots']:raise ValueError('unmatched_owner_slot')
    return verify_artifacts(owner_slot=owner_slot,batch=batch,evaluator=evaluator,package=package,
        private_salt=private_salt,checkpoint_sha256=checkpoint_sha256,amendment_sha256=amendment_sha)


def verify_artifacts(*,owner_slot,batch,evaluator,package,private_salt,checkpoint_sha256,amendment_sha256=None):
    if owner_slot not in ['shared-base',*integration.matrix.RESEARCHERS]:raise ValueError('unmatched_owner_slot')
    if not isinstance(checkpoint_sha256,str) or not re.fullmatch('[a-f0-9]{64}',checkpoint_sha256):
        raise ValueError('checkpoint_sha256_required')
    batch=Path(batch).resolve();out=Path(evaluator).absolute()
    if out.resolve()!=out or not out.is_relative_to(batch):raise ValueError('owned_episode_path_required')
    task=private_json(out/'task.private.json',batch)
    if any(task.get(k)!=v for k,v in package['identity'].items()) or task.get('model_outcome')!='actor_wall_budget' or type(task.get('score')) is not int or task['score']!=0:
        raise ValueError('verified_budget_ended_task_required_no_score_inference')
    trace=json.loads(integration.controls.private(out/'actions.private.json'))
    actions=[row['action'] for row in trace if row.get('status')=='applied']
    model=worker.DesktopProspectiveModelWorker(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'))
    # Recompute saved-state verification and inspect native/reset/clock evidence.
    model._audit_episode(batch=batch,out=out,package=package,salt=private_salt,actions=actions)
    restored=out/('restored'+Path(package['filename']).suffix)
    if integration.controls.private(restored)!=package['source']:
        raise ValueError('actual_fresh_reset_bytes_changed')
    budget=private_json(out/'actor-budget-stop.private.json',batch)
    proof=budget['actor_deadline_proof']
    if budget.get('gui_applied') is not False or not any(row.get('status')=='not_applied_actor_deadline' for row in trace):
        raise ValueError('explicit_unapplied_deadline_sample_required')
    process=batch/'sampler-process';matches=[]
    setups=[]
    for path in process.glob('[0-9]*.request.private.json'):
        request=private_json(path,batch)
        if request.get('kind')=='setup':
            result_path=path.with_name(path.name.replace('.request.','.result.'))
            result=private_json(result_path,batch)
            if (request['arguments'].get('checkpoint_sha256')!=checkpoint_sha256 or
                result.get('request_sha256')!=sha(path) or result.get('status')!='completed' or
                result['value'].get('sampling_kind')!=('base' if owner_slot=='shared-base' else 'checkpoint')):
                raise ValueError('owner_checkpoint_setup_not_bound')
            setups.append(path)
    if len(setups)!=1:raise ValueError('one_source_bound_model_setup_required')
    for path in process.glob('[0-9]*.result.private.json'):
        response=private_json(path,batch)
        if response.get('status')=='actor_deadline' and response.get('actor_deadline_proof')==proof:
            request_path=path.with_name(path.name.replace('.result.','.request.'))
            request=private_json(request_path,batch)
            if response.get('request_sha256')!=sha(request_path) or request.get('kind')!='sample' or Path(request['arguments']['task_dir']).resolve()!=out:
                raise ValueError('deadline_rpc_hash_or_task_changed')
            matches.append(path)
    if len(matches)!=1:raise ValueError('one_acknowledged_deadline_rpc_required')
    terminal=private_json(process/'child-terminal.private.json',batch)
    close_path=process/'provider-shutdown.private.json';close=private_json(close_path,batch)
    if (terminal.get('command_poisoned') is not True or terminal.get('request_acknowledgement_verified') is not True or
        terminal.get('provider_shutdown_acknowledged') is not True or terminal.get('forced_termination') is not False or
        terminal.get('provider_shutdown_receipt_sha256')!=sha(close_path) or close.get('status') not in {'acknowledged','no_service_created'}):
        raise ValueError('bounded_owned_provider_close_ack_required')
    paid_id=budget['sample_paid_attempt_id'];paid=batch/'paid'
    intent=paid/(paid_id+'.intent.private.json');dispatch=paid/(paid_id+'.dispatched.private.json')
    private_json(intent,batch);sent=private_json(dispatch,batch)
    if sent.get('intent_sha256')!=sha(intent) or (paid/(paid_id+'.result.private.json')).exists():
        raise ValueError('uncertain_paid_intent_changed_or_result_invented')
    with sqlite3.connect('file:'+str(out/'sampling-journal/requests.sqlite3')+'?mode=ro',uri=True) as db:
        rows=[json.loads(raw) for state,raw in db.execute('select state,result from requests') if state=='complete' and raw]
    completed=sum(row.get('status')=='completed' for row in rows)
    failed=sum(row.get('status')=='error' for row in rows)
    if proof['model_completion_known']:
        inference='late_completed_withheld_from_gui'
    elif proof['model_dispatch_may_have_occurred']:
        inference='completion_unknown_after_actor_deadline'
    else:
        inference='not_submitted_before_actor_deadline'
    return {'schema':'cua-verified-budget-performance-with-unknown-billing-v22',
        'amendment_sha256':amendment_sha256,'task_id':task['task_id'],'package_sha256':task['package_sha256'],
        'owner_slot':owner_slot,'checkpoint_sha256':checkpoint_sha256,
        'performance':{'status':'independently_saved_scored_and_reset','score':task['score'],
            'actor_budget_ended':True,'applied_gui_action_count':len(actions),'actor_seconds':task['actor_elapsed_seconds']},
        'inference':{'status':inference,'completed_model_response_count':completed,
            'retained_error_result_count':failed,'unknown_response_is_completed':False,'request_replayed':False},
        'billing':{'status':'unknown_until_authentic_usage_reconciliation','actual_usd':None,
            'provider_billed_tokens':None,'provider_invoice_verified':False},
        'provider_close_acknowledged':True,'old_paid_intents_preserved':True,
        'evidence_sha256':{name:sha(out/name) for name in ['saved-state.private.json','verifier.private.json',
            'reset.private.json','actor-clock.private.json','actor-budget-stop.private.json','task.private.json']},
        'sample_paid_attempt_id':paid_id,'paid_intent_sha256':sha(intent),
        'rpc_result_sha256':sha(matches[0]),'shutdown_sha256':sha(close_path),
        'performance_coverage_eligible':amendment_sha256 is not None,'invoice_complete_eligible':False,
        'formal_registration_performed':False,'official_final_credit':0}
