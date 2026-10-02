"""English pilot publication from verified40 matched native saved outcomes only.

This command has no preview, simulated-score, partial-result or publish mode.
Private evidence is independently reopened; public outputs exclude credentials,
private paths and sampler URIs. Rendering completion still requires visual QA.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import math
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape
from enterprise_fallback.odoo18 import twenty_task_trial_evaluator_v3 as evaluator
from enterprise_fallback.odoo18 import twenty_task_trial_selection_v4 as selection
from enterprise_fallback.odoo18 import twenty_task_trial_readback_v3 as readback
from enterprise_fallback.odoo18 import native_surface_final_worker_v1 as original

SCHEMA = 'envloop-odoo20-pilot-publication-v3'
REQUEST_FIELDS = {'schema', 'plan_ref', 'training_result_ref', 'baseline_selection_ref',
    'checkpoint_selection_ref', 'checkpoint_freeze_ref', 'final_pair_ref', 'final_controls_descriptor_ref', 'teacher_attempt_refs', 'training_manifest_ref',
    'training_restart_authority_ref'}
TERMINATIONS = {'model_finish', 'model_action_invalid', 'task_action_budget', 'task_wall_budget'}
FAMILIES = ('purchase', 'inventory', 'sales', 'crm')
LANES = ('baseline', 'selected_checkpoint')


def require(condition, code):
    if not condition: raise ValueError(code)


def public_safe(value):
    """Reject unsafe output rather than silently redacting scientific evidence."""
    if isinstance(value, dict):
        for key, item in value.items(): public_safe(key); public_safe(item)
        return value
    if isinstance(value, (list, tuple)):
        for item in value: public_safe(item)
        return value
    if isinstance(value, str):
        require(not re.search(r'[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef\U00020000-\U000323af]', value), 'public_english_only')
        patterns = (r'(?i)(?:sk-|tml-|e2b_)[A-Za-z0-9_-]{6,}', r'(?i)bearer\s+[A-Za-z0-9._-]+',
            r'(?i)tinker://', r'(?i)(?:/Users/|/home/|/var/|/private/|/tmp/|[A-Z]:\\)',
            r'(?i)\.private(?:\b|/)', r'(?i)(?:api[_ -]?key|password|passwd|secret|access[_ -]?token|authorization)',
            r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
        require(not any(re.search(pattern, value) for pattern in patterns), 'public_sensitive_content_forbidden')
    return value


def validate_publication(record):
    public_safe(record)
    require(type(record) is dict and record.get('schema') == SCHEMA and
        record.get('scope') == 'single_environment_20_task_pilot' and record.get('cell_id') == 'odoo-community' and
        record.get('full_study_completed') is False and record.get('final_task_count') == 20 and
        record.get('final_outcome_count') == 40 and record.get('native_control_count') == 20 and
        all(record.get(field) is True for field in ('independent_source_review_complete',
            'selection_checkpoint_frozen_before_final', 'training_owned_cleanup_verified', 'matched_final_evidence_verified')) and
        record.get('teacher_model') == 'gpt-6-sol' and record.get('student_model') == 'Qwen/Qwen3.8-27B' and
        record.get('actual_cost_usd') is None, 'verified_complete_single_environment_pilot_required')
    task_ids, outcomes = record.get('task_ids'), record.get('outcomes')
    require(type(task_ids) is list and len(task_ids) == len(set(task_ids)) == 20 and
        all(type(name) is str and name for name in task_ids) and type(outcomes) is list and len(outcomes) == 40,
        'exact_twenty_tasks_forty_outcomes_required')
    seen, families = set(), {}
    for row in outcomes:
        require(type(row) is dict and row.get('task_id') in task_ids and row.get('lane') in LANES and
            row.get('family') in FAMILIES and row.get('status') == 'saved_scored_reset_and_closed' and
            type(row.get('score')) is int and row['score'] in (0, 1) and
            type(row.get('actions')) is int and 0 <= row['actions'] <= 90 and
            type(row.get('samples')) is int and row['samples'] > 0 and
            type(row.get('actor_seconds')) in (int, float) and 0 <= row['actor_seconds'] <= 720 and
            type(row.get('lifecycle_seconds')) in (int, float) and 0 <= row['lifecycle_seconds'] <= 1200 and
            row.get('termination') in TERMINATIONS, 'final_outcome_identity_score_or_lifecycle_invalid')
        for field in ('rendered_input_tokens', 'sampled_output_tokens', 'provider_latency_ms'):
            require(row.get(field) is None or type(row[field]) is int and row[field] >= 0, 'usage_must_be_observed_or_unknown')
        key = (row['task_id'], row['lane']); require(key not in seen, 'duplicated_final_task_lane')
        seen.add(key)
        require(row['task_id'] not in families or families[row['task_id']] == row['family'], 'paired_family_changed')
        families[row['task_id']] = row['family']
    require(seen == {(task, lane) for task in task_ids for lane in LANES} and
        Counter(families.values()) == Counter({family: 5 for family in FAMILIES}), 'exact_matched_family_coverage_required')
    return record


def uncertainty(record):
    """Matched binary transitions, Wilson95 rates and exact paired McNemar."""
    validate_publication(record)
    rows = {(row['task_id'], row['lane']): row for row in record['outcomes']}
    transitions = {'both_pass': 0, 'base_only': 0, 'checkpoint_only': 0, 'both_fail': 0}
    family = {name: {'task_count': 5, 'baseline_passes': 0, 'selected_checkpoint_passes': 0} for name in FAMILIES}
    for task in record['task_ids']:
        baseline, selected = rows[(task,'baseline')], rows[(task,'selected_checkpoint')]
        key = {(1,1):'both_pass',(1,0):'base_only',(0,1):'checkpoint_only',(0,0):'both_fail'}[(baseline['score'],selected['score'])]
        transitions[key] += 1
        family[baseline['family']]['baseline_passes'] += baseline['score']
        family[baseline['family']]['selected_checkpoint_passes'] += selected['score']
    def wilson(count):
        n, z = 20, 1.959963984540054
        center = (count/n+z*z/(2*n))/(1+z*z/n)
        half = z*math.sqrt((count/n)*(1-count/n)/n+z*z/(4*n*n))/(1+z*z/n)
        return [max(0.0,center-half), min(1.0,center+half)]
    base = transitions['both_pass']+transitions['base_only']
    selected = transitions['both_pass']+transitions['checkpoint_only']
    discordant = transitions['base_only']+transitions['checkpoint_only']
    tail = min(transitions['base_only'],transitions['checkpoint_only'])
    p = 1.0 if discordant == 0 else min(1.0,2*sum(math.comb(discordant,k) for k in range(tail+1))/(2**discordant))
    return {'transitions':transitions,'family_counts':family,
        'baseline_wilson95':wilson(base),'selected_checkpoint_wilson95':wilson(selected),
        'paired_delta_percentage_points':(selected-base)*5,
        'exact_paired_mcnemar_two_sided_p':p,'uncertainty_note':'Small-sample descriptive intervals and exact paired test; no multi-environment claim.'}


def _absolute(ref): return evaluator.read_ref(ref)


def _private(path): return json.loads(evaluator.private(path))


def audit_training_operations(root, inputs, result, request):
    """Require every real scheduled operation, including late/uncertain errors."""
    root = Path(root)
    require(result['optimizer_steps_completed'] == inputs.training['optimizer_steps'] == len(inputs.indices) and
        result['scheduled_tokens'] == inputs.scheduled_tokens and request['datum_count'] == len(inputs.datums),
        'actual_complete_frozen_training_schedule_required')
    def operation(name, expected_request):
        require(not (root/(name+'-error.private.json')).exists() and not (root/(name+'-deadline.private.json')).exists(),
                'uncertain_training_operation_not_publishable')
        intent = _private(root/(name+'-intent.private.json')); retained = _private(root/(name+'-result.private.json'))
        require(intent['schema'] == 'envloop-odoo20-tinker-operation-intent-v1' and intent['operation'] == name and
            intent['dataset_identity'] == inputs.identity and intent['request'] == expected_request and
            intent['before_provider_call'] is True and intent['automatic_replay_authorized'] is False and
            retained['status'] == 'completed' and retained['formal_large_study_credit'] == 0,
            'actual_training_operation_intent_or_completion_changed')
        return retained['result']
    session = operation('session-create', {'model': inputs.plan['models']['student'], 'max_retries': 0, 'holder_retries': False})
    require(type(session) is dict and bool(session.get('session_id')), 'actual_training_session_identity_missing')
    lora = operation('lora-create', {'model': inputs.plan['models']['student'], 'rank': inputs.training['lora_rank'],
        'seed': inputs.training['seed'], 'optimizer': 'adamw'})
    require(type(lora) is dict and bool(lora.get('model_id')), 'actual_lora_identity_missing')
    from tinker import types
    params = types.AdamParams(learning_rate=float(inputs.training['learning_rate'])).model_dump(mode='json')
    for step, indices in enumerate(inputs.indices):
        backward = operation(f'step-{step:04d}-forward-backward', {'datum_indices': indices, 'loss_fn': 'cross_entropy'})
        require(type(backward) is dict and type(backward.get('metrics')) is dict and
            type(backward.get('loss_fn_output_type')) is str and type(backward.get('loss_fn_outputs')) is list and
            len(backward['loss_fn_outputs']) == len(indices), 'actual_forward_backward_response_invalid')
        optimized = operation(f'step-{step:04d}-optim', params)
        require(type(optimized) is dict and type(optimized.get('metrics')) is dict, 'actual_optimizer_response_invalid')
    checkpoint = operation('sampler-weights-save', {'name': 'odoo20-'+inputs.identity[:24]})
    require(type(checkpoint) is dict and checkpoint.get('path') == result['checkpoint_path'], 'actual_saved_sampler_path_changed')
    sampler = operation('sampler-create', {'model_path': result['checkpoint_path'], 'retry_logic': False})
    require(type(sampler) is dict and bool(sampler.get('response_type')), 'actual_sampler_creation_missing')
    require(operation('sampler-base-read', {}) == inputs.plan['models']['student'], 'actual_sampler_base_read_changed')
    sample = operation('checkpoint-sample', {'prompt_index': 0, 'max_tokens': inputs.training['sample_max_tokens'],
        'temperature': 0, 'seed': inputs.training['seed']})
    require(type(sample) is dict and type(sample.get('sequences')) is list and len(sample['sequences']) == 1 and
        type(sample['sequences'][0].get('tokens')) is list and
        len(sample['sequences'][0]['tokens']) == result['sample_token_count'] <= inputs.training['sample_max_tokens'],
        'actual_saved_checkpoint_sample_unproved')
    operation('service-close', {'status': 'success'})


def audit_v4_selection_lineage(baseline, selected, plan_sha):
    """Recheck V4's pure continuation gate without creating a freeze artifact."""
    require(baseline.get('orchestration_epoch') == selected.get('orchestration_epoch') == 'v4' and
        selected.get('continuation_authority_ref') is selected.get('infrastructure_exclusion') is None and
        selected.get('imported_row_source_binding') is None, 'actual_v4_continuation_and_fresh_checkpoint_pair_required')
    ref = baseline['continuation_authority_ref']
    authority, candidate = selection._authority(ref['path'], ref['sha256'],
        [row['task'] for row in baseline['selection_tasks']], plan_sha, evaluator.MODEL, 0, 4096)
    require(baseline['infrastructure_exclusion'] == candidate['infrastructure_exclusion'] and
        baseline['imported_row_source_binding'] == candidate['source_binding']['original_selection_source_binding'] and
        baseline['selection_tasks'][:3] == candidate['selection_tasks'] and baseline['scores'][:3] == candidate['scores'],
        'actual_original_v3_imported_prefix_or_exclusion_changed')
    exclusion = baseline['infrastructure_exclusion']
    require(exclusion['classification'] == 'provider_infrastructure_uncertain_no_model_score' and exclusion['model_score'] is None and
        exclusion['original_request_replay_authorized'] is False and exclusion['original_attempt_resume_authorized'] is False and
        authority['actor_sampler_scorer_reset_changed'] is False, 'infrastructure_exclusion_must_not_become_model_score')
    return {'classification': exclusion['classification'], 'model_score': None,
        'completed_original_calls': exclusion['completed_sample_calls'],
        'uncertain_original_calls': len(exclusion['uncertain_request_ids']),
        'whole_task_replacement_count': 1, 'original_requests_replayed': False, 'imported_original_v3_cases': 3}


def audit_training_restart(root, inputs, request, authority_ref):
    """Post-run saved audit; deliberately avoids the predispatch freshness gate."""
    restart = request.get('explicit_fresh_restart')
    if restart is None:
        require(authority_ref is None, 'restart_authority_without_restart_attempt')
        return []
    require(type(authority_ref) is dict and restart['restart_authority_sha256'] == authority_ref['sha256'],
            'actual_restart_authority_reference_required')
    from enterprise_fallback.odoo18 import tinker_trial_recovery_v1 as recovery
    authority = _absolute(authority_ref)
    prior_root = Path(restart['prior_output_root']).resolve()
    prior = recovery.failed_attempt(prior_root)
    require(authority['schema'] == recovery.RESTART_SCHEMA and authority['dataset_identity'] == inputs.identity == prior['dataset_identity'] and
        authority['model'] == inputs.training['model'] == prior['model'] and
        authority['optimizer_steps'] == inputs.training['optimizer_steps'] == prior['optimizer_steps_planned'] == 192 and
        authority['prior_training_request_sha256'] == restart['prior_training_request_sha256'] == prior['training_request_sha256'] and
        authority['retire_prior_attempt'] is authority['start_from_fresh_base'] is authority['fresh_restart_authorized'] is True and
        authority['carry_prior_model_state'] is authority['automatic_replay_authorized'] is False and
        restart['fresh_base_model_attempt'] is True and restart['prior_model_state_carried'] is False and
        restart['prior_unknown_forward_backward_resubmitted'] is restart['automatic_replay_authorized'] is False,
        'actual_explicit_fresh_training_restart_policy_required')
    source_map = authority['execution_source_sha256s']
    require(source_map == restart['execution_source_sha256s'], 'restart_execution_source_binding_changed')
    recovery.check_execution_sources(source_map)
    source_check = _private(Path(root)/'restart-execution-source-check.private.json')
    require(source_check['schema'] == 'envloop-odoo20-restart-execution-source-check-v1' and
        source_check['execution_source_sha256s'] == source_map and source_check['checked_after_training'] is True and
        source_check['source_bytes_unchanged'] is True, 'actual_post_training_source_check_required')
    for field in ('prior_consumed_claim_ref','prior_terminal_ref','billing_access_receipt_ref'):
        require(authority[field] == restart[field], 'restart_prior_reference_changed')
    # Prior claim refs follow the original training loader's relative namespace.
    from enterprise_fallback.odoo18 import twenty_task_trial_training_v1 as base
    prior_claim_path = base.reference(inputs.namespace, authority['prior_consumed_claim_ref'])
    prior_claim = base.private_json(prior_claim_path, authority['prior_consumed_claim_ref']['sha256'], root=inputs.namespace)
    terminal = _absolute(authority['prior_terminal_ref'])
    require(prior_claim['dataset_identity'] == inputs.identity and Path(prior_claim['output_root']).resolve() == prior_root and
        prior_claim['automatic_replay_authorized'] is False and terminal['exit_code'] == 1 and terminal['automatic_restarts'] == 0,
        'actual_prior_failed_training_claim_or_terminal_changed')
    recovery.checked_access(authority['billing_access_receipt_ref'], authority['prior_terminal_ref'])
    identity = evaluator.digest(json.dumps({'dataset':inputs.identity,'authority':authority_ref['sha256'],
        'nonce':authority['new_attempt_nonce']},sort_keys=True).encode())
    require(identity == restart['restart_claim_identity'] and Path(root).resolve() == Path(inputs.namespace)/authority['new_output_name'],
            'actual_fresh_restart_namespace_or_claim_identity_changed')
    consumed = _private(Path(inputs.namespace)/('tinker-fresh-restart-authority-'+identity+'-consumed.private.json'))
    require(consumed['schema'] == 'envloop-odoo20-fresh-restart-authority-consumed-v1' and
        consumed['dataset_identity'] == inputs.identity and consumed['restart_authority_sha256'] == authority_ref['sha256'] and
        Path(consumed['prior_output_root']).resolve() == prior_root and Path(consumed['output_root']).resolve() == Path(root).resolve() and
        consumed['automatic_replay_authorized'] is consumed['prior_unknown_request_replayed'] is False,
        'actual_one_use_restart_authority_consumption_required')
    prior_close = _private(prior_root/'owned-provider-close.private.json')
    settlement = audit_prior_local_settlement(prior_root, terminal, inputs.identity)
    indices = prior['completed_optimizer_step_indices']
    require(indices == list(range(len(indices))), 'prior_training_optimizer_frontier_not_contiguous')
    for index in indices:
        for suffix in ('forward-backward','optim'):
            name = f'step-{index:04d}-{suffix}'
            intent, result = _private(prior_root/(name+'-intent.private.json')), _private(prior_root/(name+'-result.private.json'))
            require(intent['dataset_identity'] == inputs.identity and intent['operation'] == name and
                intent['before_provider_call'] is True and intent['automatic_replay_authorized'] is False and
                result['status'] == 'completed', 'prior_training_completed_frontier_unproved')
    require(len(prior['uncertain_forward_backward_deadlines']) > 0 and not (prior_root/'actual-training-result.private.json').exists(),
            'prior_training_uncertainty_must_remain_separate')
    return [{'classification':'interrupted_prior_training_attempt_no_checkpoint',
        'completed_optimizer_steps':len(indices), 'uncertain_forward_backward_operations':len(prior['uncertain_forward_backward_deadlines']),
        'cleanup_proved_at_original_close_snapshot':prior_close['owned_client_cleanup_proved'],
        'all_calls_settled_at_original_close_snapshot':prior_close['lifecycle']['all_owned_calls_settled'],
        'local_calls_settled_after_terminal':True, 'settled_local_operation_count':settlement['settled_operations'],
        'remote_uncertain_operation_completion':'unknown',
        'prior_weights_carried':False, 'uncertain_operations_replayed':False, 'actual_cost_usd':None,
        'restart_authority_sha256':authority_ref['sha256']}]


def audit_prior_local_settlement(root, terminal, dataset_identity):
    """Derive post-terminal local settlement without changing bad close snapshots."""
    root = Path(root)
    require(type(terminal.get('pid')) is int and terminal['pid'] > 0 and terminal['exit_code'] == 1 and
        terminal['automatic_restarts'] == 0, 'actual_prior_failed_worker_terminal_required')
    try: os.kill(terminal['pid'],0)
    except ProcessLookupError: pass
    else: require(False,'prior_local_worker_still_live')
    intents = sorted(root.glob('*-intent.private.json'))
    require(bool(intents), 'prior_local_operation_intents_missing')
    last = 0.0
    for path in intents:
        intent = _private(path); operation = intent['operation']
        require(intent['schema'] == 'envloop-odoo20-tinker-operation-intent-v1' and
            intent['dataset_identity'] == dataset_identity and intent['before_provider_call'] is True and
            intent['automatic_replay_authorized'] is False, 'prior_local_intent_identity_changed')
        result_path, error_path = root/(operation+'-result.private.json'), root/(operation+'-error.private.json')
        require(result_path.is_file() != error_path.is_file(), 'prior_local_operation_not_terminal_or_ambiguous')
        retained = result_path if result_path.is_file() else error_path
        row = _private(retained)
        require((result_path.is_file() and row['status'] == 'completed') or
            (error_path.is_file() and row['status'] == 'uncertain_no_replay' and row['automatic_replay_authorized'] is False),
            'prior_local_operation_terminal_status_changed')
        last = max(last,path.stat().st_mtime,retained.stat().st_mtime)
        deadline = root/(operation+'-deadline.private.json')
        if deadline.exists():
            value = _private(deadline)
            require(value['status'] == 'uncertain_owned_future_retained' and value['automatic_replay_authorized'] is False,
                    'prior_local_deadline_status_changed')
            last = max(last,deadline.stat().st_mtime)
    close_result = _private(root/'service-close-result.private.json')
    close_snapshot = _private(root/'owned-provider-close.private.json')
    require(close_result['status'] == 'completed' and close_snapshot['real_close_call_returned'] is True and
        terminal['ended_at'] >= max(last,(root/'owned-provider-close.private.json').stat().st_mtime),
        'prior_terminal_must_follow_last_local_settlement_and_sdk_close')
    return {'settled_operations':len(intents),'local_worker_dead':True,
        'sdk_service_close_result_completed':True,'remote_uncertain_operation_completion':'unknown'}


def _task_packet(root, row, metadata):
    """Read the saved verifier directly and recompute its independent verdict."""
    task = {'task_id': metadata['task_id'], 'package_sha256': metadata['package_sha256']}
    packet = readback.read_ref(root, row['result'])
    require(packet['schema'] == 'envloop-odoo20-final-development-result-v3' and
        packet['status'] == 'independently_saved_scored_reset_and_closed' and packet['task'] == task and
        packet['lane'] == row['lane'] and packet['score'] == row['score'], 'actual_final_packet_binding_changed')
    episode = Path(root)/Path(row['result']['path']).parent
    native = packet['native_row']; binding = evaluator.workers.public_binding()
    _, actor_module = evaluator.workers._model_modules(binding)
    actor_module._audit_task_artifacts(episode, task, native)
    saved = _private(episode/'saved-state.private.json'); proof_paths = sorted(episode.glob('live-proof-*.private.json'))
    require(len(proof_paths) >= 2, 'actual_live_saved_proofs_missing')
    proof = _private(proof_paths[-1]); context = proof['context']
    verify = importlib.import_module('verify')
    require(Path(verify.__file__).resolve() == evaluator.ROOT/'enterprise_fallback/odoo18/verify.py' and
        evaluator.digest(Path(verify.__file__).read_bytes()) == binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'],
        'original_independent_verifier_source_changed')
    require(proof['observed'] == saved['business_snapshot'], 'saved_proof_snapshot_changed')
    verdict = original._evaluate(context['family'], task['task_id'], context['target'], context['baseline'],
        saved['business_snapshot'], proof['physical_files'], context['frozen_files'], proof['attachment_paths'], verify)
    require(verdict == proof['verdict'] and int(verdict['reward'] == 1 and verdict['checks_passed'] and not verdict['difference_codes']) == packet['score'],
        'actual_independent_final_score_changed')
    reset = _private(episode/'reset.private.json')
    require(reset['pre_database_filestore_exact'] and reset['post_database_filestore_exact'] and
        _private(episode/'baseline-semantic.private.json') == _private(episode/'restored-semantic.private.json'), 'actual_final_reset_unproved')
    clock, life, close = (readback.read_ref(episode, native[key]) for key in
        ('actor_clock_ref', 'owned_complete_lifecycle_ref', 'provider_close_ref'))
    require(clock['native_actions_after_deadline'] == 0 and clock['evaluation_outside_actor_clock'] is True and
        life['saved_readback_reset_and_provider_close_complete'] is True and close['status'] == 'acknowledged' and
        close['real_close_call_returned'] is True and life['actor_clock'] == native['actor_clock_ref'] and
        life['provider_close'] == native['provider_close_ref'] and
        all(packet['runtime_cleanup'][field] is True for field in ('services_restored_to_initial_state',
            'final_database_snapshot_equal', 'final_physical_filestore_equal')), 'actual_final_owned_cleanup_unproved')
    usage = _private(episode/'usage.private.json'); actions = _private(episode/'actions.private.json')
    calls = packet['provider_calls']; require(len(calls) == len(usage['samples']) == native['sample_count'], 'final_paid_call_coverage_changed')
    for call in calls:
        readback.read_ref(episode, call['intent'])
        if call['result'] is not None:
            actual = readback.read_ref(episode, call['result'])
            require(actual['status'] == 'completed' and actual['request_id'] == call['request_id'] and
                actual['new_dispatch'] is True and actual['reused'] is False, 'actual_final_provider_result_unproved')
    latency = None if any(call['provider_latency_ms'] is None for call in calls) else sum(call['provider_latency_ms'] for call in calls)
    return {'task_id': task['task_id'], 'family': metadata['family'], 'lane': row['lane'], 'score': packet['score'],
        'status': 'saved_scored_reset_and_closed', 'actions': sum(action['native_dispatch_status'] == 'applied' for action in actions),
        'samples': native['sample_count'], 'actor_seconds': clock['actor_elapsed_seconds'],
        'lifecycle_seconds': life['ended_monotonic']-life['started_monotonic'],
        'rendered_input_tokens': usage['rendered_input_tokens'], 'sampled_output_tokens': usage['sampled_output_tokens'],
        'provider_latency_ms': latency, 'termination': native['termination'], 'saved_packet_sha256': row['result']['sha256']}


def load_evidence(request):
    require(type(request) is dict and set(request) == REQUEST_FIELDS and request['schema'] == 'envloop-odoo20-report-request-v3',
            'exact_private_report_evidence_request_required')
    plan_ref = request['plan_ref']; plan, _ = evaluator.checked_trial(plan_ref['path'], plan_ref['sha256'])
    pair = _absolute(request['final_pair_ref']); pair_root = Path(request['final_pair_ref']['path']).parent
    require(pair.get('schema') == 'envloop-odoo20-final-development-pair-result-v3' and pair.get('status') == 'forty_native_outcomes_audited' and
        pair.get('trial_plan_sha256') == plan_ref['sha256'] and pair.get('tasks_per_lane') == 20 and len(pair.get('outcomes', [])) == 40,
        'actual_complete_forty_final_outcomes_required_before_reporting')
    descriptor = _absolute(request['final_controls_descriptor_ref'])
    evaluator.checked_final_controls(request['final_controls_descriptor_ref'], plan_path=plan_ref['path'], plan_sha=plan_ref['sha256'],
        worker_dir=descriptor['worker_dir'])
    intent = _private(pair_root/'pair-intent.private.json')
    require(intent['source_binding'] == evaluator.source_binding() and intent['trial_plan_sha256'] == plan_ref['sha256'] and
        pair['selection_freeze_sha256'] == intent['selection_freeze_sha256'] == request['checkpoint_freeze_ref']['sha256'],
        'actual_final_common_source_or_checkpoint_freeze_changed')
    baseline = _absolute(request['baseline_selection_ref']); selected = _absolute(request['checkpoint_selection_ref'])
    current_source = selection.source_binding(); _, selector = selection.workers._model_modules(selection.workers.public_binding())
    for result, base in ((baseline, True), (selected, False)):
        require(result['schema'] == 'envloop-odoo20-selection-complete-v3' and result['status'] == 'twenty_saved_scores_reset_and_closed' and
            result['base_mode'] is base and result['trial_plan_sha256'] == plan_ref['sha256'] and result['source_binding'] == current_source and
            result['hidden_final_outcomes_used'] is False, 'actual_matched_full_selection_pair_required')
        selection.audit_selection_result(result, selector)
    exclusion_summary = audit_v4_selection_lineage(baseline, selected, plan_ref['sha256'])
    require([row['task'] for row in baseline['selection_tasks']] == [row['task'] for row in selected['selection_tasks']] and
        all(new['score'] >= old['score'] for old, new in zip(baseline['scores'], selected['scores'], strict=True)), 'selection_no_regression_unproved')
    freeze = evaluator.checked_selection_freeze(request['checkpoint_freeze_ref'], plan_sha=plan_ref['sha256'],
        source_sha=evaluator.source_binding()['binding_sha256'], selection_manifest=[row['task'] for row in selected['selection_tasks']], selection=selector)
    training = _absolute(request['training_result_ref']); training_root = Path(request['training_result_ref']['path']).parent
    close = _private(training_root/'owned-provider-close.private.json'); train_request = _private(training_root/'training-request.private.json')
    # The same saved-only training loader independently verifies authenticated
    # researcher/teacher results, positive native traces and image/mask lineage.
    from enterprise_fallback.odoo18 import twenty_task_trial_training_v2 as training_source
    inputs = training_source.load_inputs(plan_path=plan_ref['path'], plan_sha=plan_ref['sha256'],
        manifest_path=request['training_manifest_ref']['path'], manifest_sha=request['training_manifest_ref']['sha256'],
        trust_owned_rendered=True)
    require(training['schema'] in ('envloop-odoo20-actual-tinker-training-result-v1', 'envloop-odoo20-actual-tinker-training-result-v2') and
        training['model'] == training['observed_base_model'] == plan['models']['student'] and
        training['checkpoint_path'] == selected['checkpoint_path'] == freeze['checkpoint_path'] and
        training['dataset_identity'] == train_request['dataset_identity'] == inputs.identity and
        train_request['manifest_sha256'] == request['training_manifest_ref']['sha256'] and
        train_request['teacher_model'] == inputs.plan['models']['teacher'] == plan['models']['teacher'] and
        train_request['trial_plan_sha256'] == plan_ref['sha256'] and
        training['optimizer_steps_completed'] > 0 and close['real_close_call_returned'] is True and close['owned_client_cleanup_proved'] is True and
        close['lifecycle']['all_owned_calls_settled'] is True, 'actual_trained_checkpoint_and_owned_close_required')
    audit_training_operations(training_root, inputs, training, train_request)
    training_restarts = audit_training_restart(training_root, inputs, train_request, request['training_restart_authority_ref'])
    metadata = {row['task_id']: row for row in plan['final_tasks_metadata']}
    outcomes = []
    for row in pair['outcomes']:
        require(row['task']['task_id'] in metadata and row['task']['package_sha256'] == metadata[row['task']['task_id']]['package_sha256'],
                'final_task_outside_frozen_twenty')
        outcomes.append(_task_packet(pair_root, row, metadata[row['task']['task_id']]))
    attempts = []
    for ordinal, ref in enumerate(request['teacher_attempt_refs']):
        result = _absolute(ref)
        require(type(result) is dict, 'actual_teacher_attempt_receipt_required')
        attempts.append({'attempt': f'A{ordinal+1:02d}', 'receipt_sha256': ref['sha256'],
            'status': str(result.get('status', 'retained_failure_evidence')),
            'failure_subtype': str(result.get('error_type', result.get('termination', 'none'))),
            'actual_cost_usd': None})
    record = {'schema': SCHEMA, 'scope': 'single_environment_20_task_pilot', 'cell_id': 'odoo-community',
        'full_study_completed': False, 'final_task_count': 20, 'final_outcome_count': 40,
        'task_ids': [row['task_id'] for row in plan['final_tasks_metadata']], 'outcomes': outcomes,
        'native_control_count': 20, 'independent_source_review_complete': True, 'selection_checkpoint_frozen_before_final': True,
        'training_owned_cleanup_verified': True, 'matched_final_evidence_verified': True,
        'teacher_model': plan['models']['teacher'], 'student_model': plan['models']['student'], 'actual_cost_usd': None,
        'source_provenance': 'synthetic_business_documents_real_odoo_community',
        'source_bindings': {'native': plan['native_binding_sha256'], 'reference': plan['reference_binding_sha256'],
            'evaluator': evaluator.source_binding()['binding_sha256'], 'selection': current_source['binding_sha256']},
        'training': {'datum_count': train_request['datum_count'], 'optimizer_steps': training['optimizer_steps_completed'],
            'checkpoint_sha256': evaluator.digest(training['checkpoint_path'].encode())},
        'infrastructure_exclusions': [exclusion_summary],
        'prior_training_attempts': training_restarts,
        'imported_selection_source_binding': baseline['imported_row_source_binding']['binding_sha256'],
        'teacher_attempts': attempts, 'provider_billed_tokens': None,
        'raw_evidence_hashes': {field: request[field]['sha256'] for field in REQUEST_FIELDS if field.endswith('_ref') and request[field] is not None}}
    return validate_publication(record)


def manuscript(record):
    validate_publication(record)
    totals = {lane: sum(row['score'] for row in record['outcomes'] if row['lane'] == lane) for lane in LANES}
    delta = (totals['selected_checkpoint']-totals['baseline'])*5
    stats = uncertainty(record)
    interval = lambda value: f'{value[0]*100:.1f}% to {value[1]*100:.1f}%'
    lines = ['# EnvLoop: A Twenty-Task Computer-Use Data Pilot',
        'EnvLoop | Technical Report',
        '## Abstract',
        f'This controlled pilot evaluates a data-generation and fine-tuning workflow in Odoo Community. '
        f'The base model solves {totals["baseline"]}/20 final tasks; the selected checkpoint solves '
        f'{totals["selected_checkpoint"]}/20, a paired difference of {delta:+d} percentage points. '
        'Every final task has matched saved-state evaluation, exact reset and acknowledged provider closure. '
        'The experiment covers one application and one researcher configuration. The larger four-by-six study remains incomplete.',
        '## Experimental contract',
        'The study follows the controlled-component framing of RSIBench [1]. The researcher and GUI teacher use Sol 6; '
        'the student uses Qwen/Qwen3.8-27B. TRAIN20, selection20 and the frozen final20 remain separate. '
        'Only the data-generation strategy and resulting LoRA weights vary. The native action interface, independent verifier, '
        'reset procedure, task identities and execution limits are shared. Checkpoint selection is frozen before final outcomes.',
        'Each partition spans purchase, inventory, sales and CRM. The final set contains five tasks per family, sampled from '
        'an unchanged 100-task source world without using model outcomes. Actors receive the current screenshot, visible task '
        'instruction and permitted GUI actions; reference answers remain inside the trusted evaluator. The actor has at most '
        '90 actions and 720 seconds. Saved readback, reset and provider closure must finish within 1200 seconds.',
        '## Environment and provenance',
        'Odoo Community is the real application. Business documents and records in this pilot are authored synthetic fixtures, '
        'clearly labelled as synthetic. They are not real customer records. Native positive, unsolved and wrong-object controls '
        'were independently checked for all twenty final tasks and their source attachments were visually reviewed.',
        '## Results',
        '| Model | Final successes | Final success rate |\n| --- | --- | --- |\n'
        f'| Base | {totals["baseline"]}/20 | {totals["baseline"]*5}% |\n'
        f'| Selected checkpoint | {totals["selected_checkpoint"]}/20 | {totals["selected_checkpoint"]*5}% |',
        '![Matched final saved-state outcomes.](figures/final-success.png)',
        f'Wilson 95% intervals are {interval(stats["baseline_wilson95"])} for the base rate and '
        f'{interval(stats["selected_checkpoint_wilson95"])} for the selected-checkpoint rate. '
        f'The exact two-sided paired McNemar p-value is {stats["exact_paired_mcnemar_two_sided_p"]:.4f}. '
        'These small-sample summaries accompany the paired task outcomes; they do not establish cross-environment generalization.',
        '| Matched transition | Tasks |\n| --- | --- |\n'+
        '\n'.join(f'| {name.replace("_", " ")} | {count} |' for name,count in stats['transitions'].items()),
        '| Task family | Tasks | Base passes | Checkpoint passes |\n| --- | --- | --- | --- |\n'+
        '\n'.join(f'| {name} | 5 | {counts["baseline_passes"]} | {counts["selected_checkpoint_passes"]} |' for name,counts in stats['family_counts'].items()),
        '![Each point represents an actual final task execution; colors distinguish the two matched models.](figures/actor-time.png)',
        'Training loss, a saved checkpoint and selection scores are diagnostic evidence. They are not final improvement claims. '
        'Only the paired forty final executions above establish the measured difference. With twenty tasks and one configuration, '
        'the result does not establish broad software coverage, repeatability across seeds or full-system recursive self-improvement.',
        '## Failures, timing and cost',
        'Teacher-generation failures are retained separately from student final outcomes. Model action-budget exhaustion, '
        'provider faults and infrastructure failures are distinct categories. Actor time excludes trusted saved-state evaluation; '
        'the complete lifecycle includes saved readback, reset and real provider closure. Rendered input counts and sampled '
        'output counts are reported separately from provider-billed token counts. Actual billed dollars and provider-billed '
        'tokens are unknown where no authentic invoice is available; they remain null.',
        'The baseline selection run retains three originally completed cases through a saved-evidence import. '
        'One incomplete provider infrastructure attempt is excluded without a model score. Its original request IDs are '
        'not replayed; a separately reviewed fresh whole-task replacement completes that task. This orchestration amendment '
        'preserves the actor, sampler, verifier, reset, observations and execution limits. The trained-checkpoint selection '
        'uses twenty fresh tasks under the same authority.',
        f'The accepted training batch contains {record.get("training", {}).get("datum_count", "unknown")} image/action examples '
        f'and completes {record.get("training", {}).get("optimizer_steps", "unknown")} optimizer steps. '
        'All owned training calls settle and the SDK client teardown is verified before evaluation. '
        'This does not assert independent closure of every underlying transport. No failed request is silently replayed.',
        '## Reproducibility and limits',
        'The public evidence file includes task-level binary outcomes, action/sample counts, timings, usage fields and source '
        'hashes. Private application data, credentials and sampler locations are excluded. The public code describes the '
        'protocol; replaying private execution evidence requires access to its separately retained artifacts. '
        'This report makes no completed full-study admission claim.',
        '## Reference', '[1] RSIBench. Modular RSI Research Infrastructure. https://rsibench.co/.']
    if record.get('teacher_attempts'):
        rows = ['| Attempt | Retained status | Failure subtype |', '| --- | --- | --- |']
        rows.extend(f'| {row["attempt"]} | {row["status"]} | {row["failure_subtype"]} |' for row in record['teacher_attempts'])
        lines.insert(-2, '## Teacher-generation attempt ledger')
        lines.insert(-2, '\n'.join(rows))
    if record.get('prior_training_attempts'):
        rows = ['| Prior training attempt | Completed optimizer steps | Uncertain forward/backward operations |', '| --- | --- | --- |']
        rows.extend(f'| Interrupted; no checkpoint | {row["completed_optimizer_steps"]} | {row["uncertain_forward_backward_operations"]} |'
                    for row in record['prior_training_attempts'])
        lines.insert(-2, '## Prior training infrastructure attempts')
        lines.insert(-2, '\n'.join(rows))
        lines.insert(-2, 'The prior optimizer steps are not included in the completed fresh training schedule. '
                     'No earlier model state is carried into the fresh attempt, and uncertain operations are not resubmitted.')
    text = '\n\n'.join(lines)+'\n'; public_safe(text); return text


def _figures(record, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir()
    success = [sum(row['score'] for row in record['outcomes'] if row['lane'] == lane) for lane in LANES]
    fig, ax = plt.subplots(figsize=(6.2, 3.3)); ax.bar(['Base', 'Selected checkpoint'], success, color=['#64748b', '#2563eb'])
    ax.set_ylim(0, 20); ax.set_ylabel('Passed final tasks / 20'); ax.spines[['top','right']].set_visible(False)
    for index, count in enumerate(success): ax.text(index, count+0.4, f'{count}/20', ha='center')
    fig.tight_layout(); fig.savefig(out/'final-success.png', dpi=180); fig.savefig(out/'final-success.pdf'); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    for lane, color in zip(LANES, ('#64748b', '#2563eb'), strict=True):
        rows = {row['task_id']: row for row in record['outcomes'] if row['lane'] == lane}
        ax.plot(range(1,21), [rows[name]['actor_seconds'] for name in record['task_ids']], 'o-', color=color,
                label='Base' if lane == 'baseline' else 'Selected checkpoint', markersize=3)
    ax.axhline(720, color='#9f1239', linestyle='--', linewidth=1, label='Actor limit')
    ax.set(xlabel='Frozen task ordinal', ylabel='Actor time (seconds)', xlim=(0.5,20.5)); ax.legend(fontsize=8)
    ax.spines[['top','right']].set_visible(False); fig.tight_layout(); fig.savefig(out/'actor-time.png', dpi=180)
    fig.savefig(out/'actor-time.pdf'); plt.close(fig)


def _pdf(text, output, record):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.lib import colors
    width = A4[0]-108
    styles = {'title': ParagraphStyle('title', fontName='Times-Bold', fontSize=21, leading=25, spaceAfter=14),
        'heading': ParagraphStyle('heading', fontName='Times-Bold', fontSize=13, leading=17, spaceBefore=14, spaceAfter=7, keepWithNext=True),
        'body': ParagraphStyle('body', fontName='Times-Roman', fontSize=10, leading=14, spaceAfter=8),
        'caption': ParagraphStyle('caption', fontName='Times-Roman', fontSize=8, leading=11, spaceAfter=10)}
    story = []
    for block in text.split('\n\n'):
        if not block.strip(): continue
        if block.startswith('# '): story.append(Paragraph(escape(block[2:]), styles['title']))
        elif block.startswith('## '): story.append(Paragraph(escape(block[3:]), styles['heading']))
        elif block.startswith('|'):
            rows = [[Paragraph(escape(cell.strip()), styles['caption']) for cell in line.strip('|').split('|')]
                for line in block.splitlines() if not re.fullmatch(r'[| :\-]+', line)]
            table = Table(rows, colWidths=[width/len(rows[0])]*len(rows[0]), repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef5')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),0.5,colors.HexColor('#52627a')),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story.append(table); story.append(Spacer(1,8))
        elif block.startswith('!['):
            caption, relative = re.fullmatch(r'!\[(.*?)\]\((.*?)\)', block).groups()
            image = Image(str(output.parent/relative)); height = width*image.imageHeight/image.imageWidth
            story.append(KeepTogether([Image(str(output.parent/relative), width=width, height=height), Paragraph(escape(caption), styles['caption'])]))
        else: story.append(Paragraph(escape(block), styles['body']))
    def footer(canvas, doc):
        canvas.setFont('Times-Roman',8); canvas.drawString(54,25,'EnvLoop | Odoo twenty-task pilot')
        canvas.drawRightString(A4[0]-54,25,str(doc.page))
    SimpleDocTemplate(str(output), pagesize=A4, leftMargin=54, rightMargin=54, topMargin=50, bottomMargin=45,
        title='EnvLoop: A Twenty-Task Computer-Use Data Pilot', author='EnvLoop').build(story,onFirstPage=footer,onLaterPages=footer)


def generate(*, request_path, request_sha, output_root):
    request = evaluator.workers.private_json(request_path, request_sha)
    record = load_evidence(request)
    out = Path(output_root); require(not out.exists() and not out.is_symlink(), 'fresh_report_output_required')
    # First actual authoring command is protected by the PDF skill marker.
    import subprocess
    candidates = sorted((Path.home()/'.codex/plugins/cache/openai-primary-runtime/pdf').glob(
        '*/skills/pdf/container_tools/mark_artifact_operation_started.mjs'), reverse=True)
    marker = candidates[0] if candidates else Path(__file__).resolve().parents[1]/'container_tools/mark_artifact_operation_started.mjs'
    require(marker.is_file(), 'pdf_artifact_operation_marker_unavailable')
    subprocess.run(['node', str(marker), '--operation-kind', 'create', '--expected-output-count', '3', '--output-format', 'pdf'], check=True)
    out.mkdir(parents=True)
    text = manuscript(record)
    record['uncertainty'] = uncertainty(record)
    (out/'public-evidence.json').write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    (out/'technical-report.md').write_text(text)
    _figures(record, out/'figures'); _pdf(text, out/'technical-report.pdf', record)
    (out/'render-status.json').write_text(json.dumps({'schema':'envloop-odoo20-report-render-status-v3',
        'artifact_created':True,'visual_qa_completed':False,'published':False}, sort_keys=True)+'\n')
    return {'status':'created_pending_visual_pdf_review','output_root':str(out.resolve()),'published':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-path', required=True); parser.add_argument('--request-sha', required=True)
    parser.add_argument('--output-root', required=True)
    print(json.dumps(generate(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__': main()
