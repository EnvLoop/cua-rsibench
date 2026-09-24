"""Offline capacity/design planner for a proposed four-by-six Data study.

This stdlib-only tool never imports execution/provider clients, reads hidden task
contents, allocates infrastructure, or predicts scores. Its task slots and cost
envelopes are plans, not manufactured benchmark instances or execution evidence.
The default reflects the user's explicit full-scale authorization; this tool
cannot dispatch work, and the six application profiles remain unbuilt.

Examples:
  python tools/plan_factory_scale.py example --out work/scale-input.json
  python tools/plan_factory_scale.py plan --config work/scale-input.json --out work/scale-plan.json
  python tools/plan_factory_scale.py plan  # proposed defaults, JSON to stdout
"""
import argparse
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


SCHEMA = 'factory-scale-plan-v1'
HEX = re.compile(r'[a-f0-9]{64}')
SLUG = re.compile(r'[a-z][a-z0-9-]{0,47}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum, maximum, label):
    require(type(value) is int and minimum <= value <= maximum, label + ': invalid integer')
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def default_config():
    """Explicit proposals only: six application profiles still need to be chosen."""
    return {
        'researchers': [{'id': alias, 'model': model} for alias, model in (
            ('astra', 'gpt-6-astra'), ('sol', 'gpt-5.6-sol'),
            ('sol6', 'gpt-6-sol'), ('luna6', 'gpt-6-luna'))],
        'cells': [{'id': f'cell-{number:02}', 'application': None, 'interface': None,
                   'selection_tasks': 20, 'final_tasks': 100, 'split_manifest': None,
                   'runtime_sha256': None, 'verifier_sha256': None}
                  for number in range(1, 7)],
        'research_seeds': [23],
        'final_seeds': [23],
        'teacher': 'gpt-5.6-sol', 'student': 'Qwen/Qwen3.8-27B',
        'spending_authorized_by_user': True,
        'budget': {'rounds': 5, 'training_tokens_per_campaign': 1048576,
                   'wall_time_budget_sec': 57600, 'Tinker_cost_budget_usd': 500,
                   'training_tokens_per_candidate': 262144, 'optimizer_steps': 32,
                   'batch_size': 2, 'researcher_calls_per_round': 40,
                   'researcher_output_tokens_per_call': 6000,
                   'logical_turns_per_round': 20, 'program_runs_per_round': 12,
                   'teacher_rollouts_per_round': 3, 'teacher_calls_per_round': 100,
                   'teacher_output_tokens_per_call': 1024},
        'execution': {'tasks_per_chunk': 3, 'actor_actions': 90,
                      'actor_output_tokens_per_call': 512,
                      'actor_timeout_seconds': 1500, 'child_job_cap_seconds': 2700,
                      'orchestrator_lease_seconds': 3600, 'cleanup_margin_seconds': 300,
                      'global_active_remote_jobs': 3, 'selection_repetitions': 1,
                      'selection_full_suite_replays': 1, 'final_full_suite_replays': 1},
        'input_tokens_per_call_assumption': {'student': None, 'teacher': None, 'researcher': None},
        'pricing_usd_per_million': {'student_input': '1.86', 'student_output': '5.595',
                                  'teacher_input': None, 'teacher_output': None,
                                  'researcher_input': None, 'researcher_output': None,
                                  'training_scheduled_tokens': '4.103'},
        'template_holdout': 'shared_allowed',
    }


def positive_price(value, label):
    if value is None:
        return None
    require(not isinstance(value, bool), label + ': invalid decimal')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(label + ': invalid decimal') from None
    require(amount.is_finite() and amount >= 0, label + ': invalid decimal')
    return amount


def validate_splits(manifest, selection_count, final_count, template_holdout):
    """Check declared identities only; no protected prompts or outcomes accepted."""
    require(isinstance(manifest, dict) and set(manifest) == {'train', 'selection', 'final'},
            'split manifest needs exactly train, selection, final')
    sets = {}
    counts = {}
    for split, rows in manifest.items():
        require(isinstance(rows, list) and bool(rows), 'split manifest cannot be empty')
        for row in rows:
            require(isinstance(row, dict) and set(row) == {
                'task_id', 'source_groups', 'template_group', 'instance_group', 'package_sha256'},
                'task metadata must contain only identity/provenance/hash fields')
            require(isinstance(row['task_id'], str) and SLUG.fullmatch(row['task_id']), 'invalid task ID')
            require(isinstance(row['source_groups'], list) and row['source_groups']
                    and all(isinstance(x, str) and x for x in row['source_groups'])
                    and len(set(row['source_groups'])) == len(row['source_groups']), 'invalid source groups')
            require(all(isinstance(row[key], str) and row[key] for key in ('template_group', 'instance_group')),
                    'template and instance group identities required')
            require(isinstance(row['package_sha256'], str) and HEX.fullmatch(row['package_sha256']),
                    'valid package hash required')
        task_ids = {r['task_id'] for r in rows}
        require(len(task_ids) == len(rows), 'duplicate task identity within split')
        sets[split] = {'tasks': task_ids, 'sources': {x for r in rows for x in r['source_groups']},
                       'templates': {r['template_group'] for r in rows},
                       'instances': {r['instance_group'] for r in rows},
                       'packages': {r['package_sha256'] for r in rows}}
        require(len(sets[split]['packages']) == len(rows), 'duplicate task package within split')
        counts[split] = {'tasks': len(rows), 'source_groups': len(sets[split]['sources']),
                         'template_groups': len(sets[split]['templates']),
                         'instance_groups': len(sets[split]['instances'])}
    require(counts['selection']['tasks'] == selection_count and counts['final']['tasks'] == final_count,
            'split manifest task counts differ from requested cell')
    require(counts['final']['instance_groups'] == final_count, 'final variants cannot masquerade as independent instances')
    for first, second in (('train', 'selection'), ('train', 'final'), ('selection', 'final')):
        for kind in ('tasks', 'sources', 'instances', 'packages'):
            require(not sets[first][kind] & sets[second][kind], f'{kind} overlap between {first} and {second}')
        if template_holdout == 'disjoint_required':
            require(not sets[first]['templates'] & sets[second]['templates'], 'template holdout overlap')
    return {'declared_split_identity_checks_pass': True, 'manifest_sha256': fingerprint(manifest),
            'counts': counts, 'package_contents_verified': False,
            'access_control_verified': False, 'realism_or_solvability_verified': False}


def validate(config):
    defaults = default_config()
    require(isinstance(config, dict) and set(config) == set(defaults), 'configuration keys must match the example schema')
    require(isinstance(config['researchers'], list) and len(config['researchers']) == 4, 'exactly four researchers required')
    aliases, models = [], []
    for row in config['researchers']:
        require(isinstance(row, dict) and set(row) == {'id', 'model'}, 'researcher requires exact id/model')
        require(isinstance(row['id'], str) and SLUG.fullmatch(row['id']), 'invalid researcher alias')
        require(isinstance(row['model'], str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,119}', row['model'])), 'invalid model identifier')
        aliases.append(row['id']); models.append(row['model'])
    require(len(set(aliases)) == len(set(models)) == 4, 'duplicate researcher alias or model')
    for kind in ('teacher', 'student'):
        require(isinstance(config[kind], str) and bool(config[kind]), 'exact ' + kind + ' identifier required')
    require(type(config['spending_authorized_by_user']) is bool, 'user spending authorization must be explicit')
    for key in ('research_seeds', 'final_seeds'):
        values = config[key]
        require(isinstance(values, list) and 1 <= len(values) <= 100, key + ' requires one to 100 entries')
        for seed in values: integer(seed, 0, 2**31 - 1, key)
        if key == 'research_seeds':
            require(len(values) == len(set(values)), 'research seeds must be unique')
    require(config['template_holdout'] in ('shared_allowed', 'disjoint_required'), 'unknown template holdout policy')
    budget, execution = config['budget'], config['execution']
    require(isinstance(budget, dict) and set(budget) == set(defaults['budget']), 'budget fields differ')
    require(isinstance(execution, dict) and set(execution) == set(defaults['execution']), 'execution fields differ')
    for key, value in budget.items():
        if key == 'Tinker_cost_budget_usd':
            require(positive_price(value, 'budget.' + key) is not None and Decimal(str(value)) > 0,
                    'positive nominal Tinker cost budget required')
        else:
            integer(value, 1, 10**10, 'budget.' + key)
    require(budget['logical_turns_per_round'] <= budget['researcher_calls_per_round'], 'logical turns exceed charged-call capacity')
    require(budget['training_tokens_per_candidate'] <= budget['training_tokens_per_campaign'], 'candidate token bound exceeds campaign budget')
    for key, value in execution.items(): integer(value, 0 if key.endswith('_replays') else 1, 10**7, 'execution.' + key)
    require(execution['tasks_per_chunk'] <= 3, 'planner preserves the current one-to-three-task execution boundary')
    require(execution['actor_actions'] <= 128, 'proxy action bound exceeded')
    require(execution['actor_timeout_seconds'] <= execution['child_job_cap_seconds'], 'actor timeout exceeds child job cap')
    require(execution['child_job_cap_seconds'] + execution['cleanup_margin_seconds'] < execution['orchestrator_lease_seconds'],
            'orchestrator lease lacks collection/cleanup headroom')
    require(execution['selection_full_suite_replays'] <= 1 and execution['final_full_suite_replays'] <= 1,
            'only zero or one predeclared whole-suite replay allowed')
    require(isinstance(config['input_tokens_per_call_assumption'], dict)
            and set(config['input_tokens_per_call_assumption']) == {'student', 'teacher', 'researcher'}, 'input token assumption fields differ')
    for key, value in config['input_tokens_per_call_assumption'].items():
        if value is not None: integer(value, 0, 10**7, key + ' input token assumption')
    require(isinstance(config['pricing_usd_per_million'], dict)
            and set(config['pricing_usd_per_million']) == set(defaults['pricing_usd_per_million']), 'pricing fields differ')
    for key, value in config['pricing_usd_per_million'].items(): positive_price(value, key)
    require(isinstance(config['cells'], list) and len(config['cells']) == 6, 'exactly six evaluation cells required')
    seen = set()
    for cell in config['cells']:
        require(isinstance(cell, dict) and set(cell) == set(defaults['cells'][0]), 'cell fields differ')
        require(isinstance(cell['id'], str) and SLUG.fullmatch(cell['id']) and cell['id'] not in seen, 'duplicate or invalid evaluation cell')
        seen.add(cell['id'])
        for field in ('selection_tasks', 'final_tasks'): integer(cell[field], 1, 10000, cell['id'] + '.' + field)
        for field in ('application', 'interface'):
            require(cell[field] is None or isinstance(cell[field], str) and bool(cell[field]), 'invalid cell scope')
        for field in ('runtime_sha256', 'verifier_sha256'):
            require(cell[field] is None or isinstance(cell[field], str) and HEX.fullmatch(cell[field]), 'invalid binding hash')
        if cell['split_manifest'] is not None:
            validate_splits(cell['split_manifest'], cell['selection_tasks'], cell['final_tasks'], config['template_holdout'])


def chunks(cell_id, split, count, size, actions):
    result = []
    for offset in range(0, count, size):
        end = min(offset + size, count)
        result.append({'id': f'{cell_id}-{split}-chunk-{offset // size:03}',
                       'planned_slot_start_inclusive': offset, 'planned_slot_end_exclusive': end,
                       'task_count': end - offset, 'proxy_request_capacity': max(256, (end - offset) * actions)})
    return result


def cost_estimate(config, calls, training_tokens):
    """Conditional token envelope, never an invoice or authorized spend limit."""
    output_caps = {'student': config['execution']['actor_output_tokens_per_call'],
                   'teacher': config['budget']['teacher_output_tokens_per_call'],
                   'researcher': config['budget']['researcher_output_tokens_per_call']}
    components = {}
    for role, call_count in calls.items():
        assumption = config['input_tokens_per_call_assumption'][role]
        for direction, tokens in [('input', None if assumption is None else assumption * call_count),
                                  ('output', output_caps[role] * call_count)]:
            key = role + '_' + direction
            price = positive_price(config['pricing_usd_per_million'][key], key)
            components[key] = {'tokens': tokens, 'token_basis': 'explicit per-call input assumption' if direction == 'input' else 'configured output cap times call bound',
                               'usd': None if tokens is None or price is None else str(Decimal(tokens) * price / Decimal(1000000))}
    price = positive_price(config['pricing_usd_per_million']['training_scheduled_tokens'], 'training rate')
    components['training_scheduled_tokens'] = {'tokens': training_tokens, 'token_basis': 'global campaign scheduled-token cap',
        'usd': None if price is None else str(Decimal(training_tokens) * price / Decimal(1000000))}
    known = [Decimal(row['usd']) for row in components.values() if row['usd'] is not None]
    return {'components': components, 'known_token_cost_subtotal_usd': str(sum(known, Decimal(0))) if known else None,
            'token_cost_estimate_usd': str(sum(known, Decimal(0))) if len(known) == len(components) else None,
            'all_in_total_usd': None, 'spending_authorized_by_user': config['spending_authorized_by_user'],
            'dispatch_capability': False,
            'excluded_costs': ['E2B actor/verifier/proxy/controller compute', 'storage/egress', 'provider minimums and discounts',
                               'unreceipted or ambiguously charged inference beyond the stated call envelope'],
            'interpretation': 'Conditional planning envelope only; input sizes and account prices must be measured. Training sequence limits do not bound actor input tokens. The nominal Tinker dollar cap can stop a campaign before this token/call envelope is reached.'}


CHANGES = [
    {'area': 'matrix manifest and roster', 'files': ['src/cursibench/factory_roster.py', 'tools/run_factory_study.py'],
     'change': 'Add cell and research-seed axes; one registry/dataset namespace per researcher x cell x seed. All four researchers receive matched initial diagnostics and immutable cell settings.'},
    {'area': 'applications and task inventory', 'files': ['src/cursibench/factory_cases.py', 'src/cursibench/factory_export.py', 'src/cursibench/factory_final.py'],
     'change': 'Implement six declared profiles and independently validate task solvability, realism, and separate verifiers. The existing compiler/export/runtime is Kanboard-specific; six labels do not create six benchmarks.'},
    {'area': 'global and campaign resource gates', 'files': ['src/cursibench/factory_budget.py', 'src/cursibench/factory_campaign.py', 'tools/run_factory_round.py'],
     'change': 'Preserve local reservations; enforce the nominal 16-hour/$500 Tinker campaign limits and add shared atomic caps for student sampling, teacher/researcher calls, paid retry charges, separate E2B compute and global concurrency across cells. Existing training-token caps alone do not bound evaluation cost.'},
    {'area': 'selection batching', 'files': ['tools/run_cloud_chain_remote.py', 'src/cursibench/factory_results.py'],
     'change': 'Replace exactly-three selection-suite assumption with manifest batches of at most three and full-task-set aggregation. Declare family metadata rather than infer families from task-name segments.'},
    {'area': 'final binding and repetitions', 'files': ['src/cursibench/factory_final.py', 'tools/prepare_remote_factory_final.py', 'tools/prepare_factory_comparison.py'],
     'change': 'Replace six tasks/two chunks/two repetitions with manifest-defined counts and seed schedule; allow final tail batches of one or two without padding. Freeze every matrix campaign before any final, bind exact checkpoint/task/runtime/seed and deduplicate equal checkpoints only after freeze.'},
    {'area': 'durability, cost and recovery', 'files': ['tools/remote_cloud_worker.py', 'src/cursibench/sample_cache.py', 'tools/remote_evidence_audit.py'],
     'change': 'Reuse one child per bounded chunk, durable job/request IDs, orphan reconciliation and exact archive audits. Never replay uncertain mutations/model calls; reserve any separately reported whole-suite recovery before dispatch and preserve originals.'},
    {'area': 'isolation and inference', 'files': ['src/cursibench/factory_workspace.py', 'src/cursibench/factory_research.py', 'src/cursibench/tinker_backend.py'],
     'change': 'Keep final task contents unavailable to research/teacher workspaces; separate evaluator storage/credentials from merely hashed manifests. The new Qwen3.8-27B student needs its own image/text training and sampling proof; historical 4B results remain separate.'},
    {'area': 'publication and audit', 'files': ['tools/audit_factory_study.py', 'tools/build_factory_report.py'],
     'change': 'Remove two-cohort/three-selection/six-final publication assumptions. Report per-cell and predeclared aggregate denominators, independent research seeds, runtime variants and infrastructure failures without filling missing outcomes with zero.'},
]


def plan(config):
    validate(config)
    config = copy.deepcopy(config)
    budget, execution = config['budget'], config['execution']
    seed_count, researcher_count = len(config['research_seeds']), len(config['researchers'])
    reps, batch = len(config['final_seeds']), execution['tasks_per_chunk']
    campaigns, cells, blockers = [], [], []
    selected_trials = base_trials = selection_trials = selected_chunks = base_chunks = selection_chunks = 0
    for cell in config['cells']:
        cell_id = cell['id']
        final_batches = chunks(cell_id, 'final', cell['final_tasks'], batch, execution['actor_actions'])
        selection_batches = chunks(cell_id, 'selection', cell['selection_tasks'], batch, execution['actor_actions'])
        split = validate_splits(cell['split_manifest'], cell['selection_tasks'], cell['final_tasks'], config['template_holdout']) if cell['split_manifest'] else None
        missing = [field for field in ('application', 'interface', 'runtime_sha256', 'verifier_sha256', 'split_manifest') if cell[field] is None]
        blockers.extend(cell_id + ': missing ' + field for field in missing)
        cells.append({'id': cell_id, 'application': cell['application'], 'interface': cell['interface'],
                      'runtime_sha256': cell['runtime_sha256'], 'verifier_sha256': cell['verifier_sha256'],
                      'declared_scope_only': True, 'split_checks': split,
                      'selection_tasks': cell['selection_tasks'], 'final_tasks': cell['final_tasks'],
                      'selection_chunks': selection_batches, 'final_chunks': final_batches})
        for researcher in config['researchers']:
            for seed in config['research_seeds']:
                campaign = {'id': f'{researcher["id"]}--{cell_id}--seed-{seed}', 'researcher': researcher,
                            'cell': cell_id, 'research_seed': seed, 'planned_round_limit': budget['rounds'],
                            'training_token_cap': budget['training_tokens_per_campaign'],
                            'wall_time_budget_sec': budget['wall_time_budget_sec'],
                            'Tinker_cost_budget_usd': str(Decimal(str(budget['Tinker_cost_budget_usd']))),
                            'final_plan_requires': ['frozen selection and remaining reservation resolution',
                                'checkpoint and training/data hashes', 'sealed cell task/package hashes',
                                'runtime/verifier hashes', 'repetition ordinal and sampling seed',
                                'selection freeze before final start', 'all expected task results once each']}
                campaigns.append(campaign)
        # Base evidence is shared only within this cell and matched runtime/seed;
        # budget conservatively assumes each researcher produces a distinct checkpoint.
        base_trials += cell['final_tasks'] * reps
        selected_trials += cell['final_tasks'] * reps * researcher_count * seed_count
        base_chunks += len(final_batches) * reps
        selected_chunks += len(final_batches) * reps * researcher_count * seed_count
        selection_runs = (1 + researcher_count * seed_count * budget['rounds']) * execution['selection_repetitions']
        selection_trials += cell['selection_tasks'] * selection_runs
        selection_chunks += len(selection_batches) * selection_runs
    campaign_count = len(campaigns)
    rounds = campaign_count * budget['rounds']
    training_cap = campaign_count * min(budget['training_tokens_per_campaign'], budget['rounds'] * budget['training_tokens_per_candidate'])
    final_initial = base_trials + selected_trials
    final_initial_chunks = base_chunks + selected_chunks
    final_with_recovery = final_initial * (1 + execution['final_full_suite_replays'])
    selection_with_recovery = selection_trials * (1 + execution['selection_full_suite_replays'])
    all_chunks = final_initial_chunks * (1 + execution['final_full_suite_replays']) + selection_chunks * (1 + execution['selection_full_suite_replays'])
    calls = {'student': (final_with_recovery + selection_with_recovery) * execution['actor_actions'],
             'teacher': rounds * budget['teacher_calls_per_round'],
             'researcher': rounds * budget['researcher_calls_per_round']}
    blockers += ['new versioned protocol/runner/audit changes are not implemented by this planner',
                 'real task contents, independent verifiers, solvability and leakage must be audited before launch',
                 'account-specific prices and atomic Tinker-dollar/wall-time/global inference-compute gates must be implemented']
    if not config['spending_authorized_by_user']:
        blockers.append('paid execution is not authorized by the user in this configuration')
    return {'schema': SCHEMA, 'status': 'offline_proposal_only', 'config_sha256': fingerprint(config),
            'executed': False, 'executable_now': False, 'provider_calls': 0, 'outcomes': None,
            'spending_authorized_by_user': config['spending_authorized_by_user'],
            'researcher_count': researcher_count, 'evaluation_cell_count': len(cells),
            'research_seed_count': seed_count, 'matrix_campaigns': campaign_count,
            'teacher': config['teacher'], 'student': config['student'],
            'campaigns': campaigns, 'cells': cells,
            'assumptions': {'defaults_are_proposals_not_upstream_protocol_claims': True,
                'selection_tasks_are_configurable_and_separate_from_finals': True,
                'final_seed_schedule': config['final_seeds'],
                'final_seed_interpretation': 'sampling repetitions of the same task set, not additional task instances or researcher seeds',
                'checkpoint_deduplication': 'capacity assumes all selected checkpoints distinct; equality is checked only after freeze',
                'baseline_sharing': 'one matched base execution per cell/task/seed; never share across cells or changed runtime',
                'cross_cell_identity': 'all task and checkpoint identities are scoped by cell; overlap across real cell datasets must be disclosed and cannot be counted as independent evidence',
                'source_groups': 'must represent leakage units such as original documents/accounts/organizations, not row aliases',
                'template_holdout': config['template_holdout'],
                'hashes_are_not_access_control': True,
                'nominal_reference_budget': '16-hour research wall-time and $500 Tinker cap per researcher/cell/seed; E2B and other provider costs are separate',
                'nominal_budgets_are_not_actual_spend': True,
                'official_final_execution_default': 'one per task; extra repetitions must be explicitly configured for the relevant evaluation design'},
            'inventory': {'planned_unique_final_instances': sum(c['final_tasks'] for c in cells),
                'planned_unique_selection_instances': sum(c['selection_tasks'] for c in cells),
                'new_task_instances_generated': 0, 'validated_task_packages': 0,
                'recorded_outcomes': 0},
            'capacity': {'research_round_ceiling': rounds, 'trained_candidates_ceiling_not_prediction': rounds,
                'global_training_token_cap': training_cap,
                'nominal_wall_time_budget_sec_per_campaign': budget['wall_time_budget_sec'],
                'aggregate_nominal_campaign_hours': campaign_count * budget['wall_time_budget_sec'] / 3600,
                'nominal_Tinker_cost_budget_usd_per_campaign': str(Decimal(str(budget['Tinker_cost_budget_usd']))),
                'aggregate_nominal_Tinker_budget_usd': str(campaign_count * Decimal(str(budget['Tinker_cost_budget_usd']))),
                'Tinker_budget_excludes': ['E2B infrastructure', 'researcher and teacher calls through AgentRouterHub', 'other provider charges'],
                'full_candidate_cap_rounds_per_campaign': min(budget['rounds'], budget['training_tokens_per_campaign'] // budget['training_tokens_per_candidate']),
                'training_budget_note': 'round and token limits both apply; the round ceiling does not promise all rounds can use the per-candidate maximum',
                'selection_initial_trials': selection_trials, 'selection_initial_remote_chunks': selection_chunks,
                'final_base_initial_trials': base_trials, 'final_selected_initial_trials': selected_trials,
                'final_total_initial_trials': final_initial, 'final_initial_remote_chunks': final_initial_chunks,
                'selection_trial_ceiling_with_recovery': selection_with_recovery,
                'final_trial_ceiling_with_recovery': final_with_recovery,
                'remote_chunk_ceiling_with_recovery': all_chunks,
                'student_call_ceiling_with_recovery': calls['student'],
                'researcher_charged_call_ceiling': calls['researcher'], 'teacher_charged_call_ceiling': calls['teacher'],
                'teacher_rollout_ceiling': rounds * budget['teacher_rollouts_per_round'],
                'program_run_ceiling': rounds * budget['program_runs_per_round'],
                'training_record_coverage_per_candidate': budget['optimizer_steps'] * budget['batch_size'],
                'concurrent_remote_job_limit': execution['global_active_remote_jobs'],
                'task_sandbox_ceiling_during_remote_only': execution['global_active_remote_jobs'] * (2 + 2 * batch),
                'concurrency_note': 'conservative controller + proxy + actor/verifier overlap; researcher workspaces/teacher episodes need separate reserved capacity',
                'controller_lease_hours_ceiling': all_chunks * execution['orchestrator_lease_seconds'] / 3600,
                'runtime_note': 'lease-hours are a scheduling/compute envelope, not predicted elapsed time or billed utilization'},
            'cost': cost_estimate(config, calls, training_cap),
            'recovery_policy': {'selection_full_suite_replays_max': execution['selection_full_suite_replays'],
                'final_full_suite_replays_max': execution['final_full_suite_replays'],
                'eligible': 'only infrastructure-invalid whole logical suites after independent admission',
                'originals_preserved': True, 'valid_scores_retried': False,
                'recovery_rows_mixed_with_originals': False, 'retry_counts_as_new_independent_repetition': False,
                'uncertain_creation': 'reconcile unique job metadata and preserve attempt ledger before any authorized create retry',
                'uncertain_dispatch': 'read durable intent/result; never replay unresolved model/action effects',
                'same_checkpoint_tasks_runtime_seed_required': True},
            'minimum_versioned_changes': CHANGES, 'readiness_blockers': blockers}


def write_new(path, value):
    destination = Path(path)
    require(not destination.exists(), 'refuse to overwrite an existing artifact')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    example = sub.add_parser('example')
    example.add_argument('--out')
    command = sub.add_parser('plan')
    command.add_argument('--config', type=Path)
    command.add_argument('--out')
    args = parser.parse_args()
    try:
        value = default_config() if args.command == 'example' else plan(
            json.loads(args.config.read_text()) if args.config else default_config())
        if args.out:
            write_new(args.out, value)
            print(json.dumps({'written': args.out, 'provider_calls': 0, 'executed': False}))
        else:
            print(json.dumps(value, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'invalid_offline_plan', 'error': str(exc)}), file=__import__('sys').stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
