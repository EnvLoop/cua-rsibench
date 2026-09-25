"""Audit complete six-cell computer-use results before figures or a paper.

The caller must rebuild the final matrix from its source manifest. This module
binds the resulting plan to campaign and per-task receipts, separates scored
model outcomes from invalid infrastructure attempts, and computes the frozen
paired statistics. Receipt hashes establish integrity, not the truth of a GUI
trace; application-specific readback remains an independent audit obligation.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from . import full_study_matrix_v1 as matrix
from . import full_study_stats_v1 as stats
from . import scale_final_v06 as cell_final


SCHEMA = 'cua-full-study-execution-index-v1'
SUMMARY_SCHEMA = 'cua-full-study-audited-results-v1'
FAILURE_TYPES = {'provider', 'transport', 'environment', 'verifier'}
USAGE_FIELDS = (
    'tinker_nominal_usd', 'researcher_inference_usd',
    'teacher_rollout_usd', 'e2b_usd',
    'storage_application_usd', 'selected_final_usd',
)
COUNT_FIELDS = (
    'researcher_calls', 'teacher_rollout_tokens',
    'teacher_rollout_calls', 'e2b_peak_concurrency', 'candidate_submissions',
    'selection_evaluations',
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _reference_json(root: Path, reference: object, label: str) -> dict:
    _, raw = cell_final.evidence_file(root, reference, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f'{label}: invalid JSON receipt') from None
    _require(isinstance(value, dict), f'{label}: JSON object required')
    return value


def _task_packages(base_plan: dict) -> dict[str, str]:
    chunks = base_plan.get('chunks')
    _require(isinstance(chunks, list), 'final chunk plan missing')
    result = {}
    for chunk in chunks:
        for row in chunk.get('tasks', []):
            task = row.get('task_id')
            _require(task not in result and cell_final.is_hash(row.get('package_sha256')),
                     'duplicate task or missing package hash in plan')
            result[task] = row['package_sha256']
    _require(len(result) == matrix.OFFICIAL_PER_CELL,
             'final plan does not contain exactly 100 task packages')
    return result


def _freeze(receipt: object, *, cell_id: str, researcher_id: str,
            checkpoint: str, base_checkpoint: str) -> dict:
    receipt = cell_final.exact(receipt, {
        'schema', 'cell_id', 'researcher_id', 'base_checkpoint_sha256',
        'selected_checkpoint_sha256', 'training_lineage_sha256',
        'selection_results_sha256', 'selection_frozen_at',
        'campaign_started_at', 'campaign_finished_at',
        'candidate_count', 'selection_evaluations',
    }, 'selection freeze')
    _require(receipt['schema'] == 'cua-full-study-selection-freeze-v1' and
             receipt['cell_id'] == cell_id and
             receipt['researcher_id'] == researcher_id and
             receipt['base_checkpoint_sha256'] == base_checkpoint and
             receipt['selected_checkpoint_sha256'] == checkpoint and
             all(cell_final.is_hash(receipt[key]) for key in (
                 'training_lineage_sha256', 'selection_results_sha256')) and
             type(receipt['selection_frozen_at']) is int and
             type(receipt['campaign_started_at']) is int and
             type(receipt['campaign_finished_at']) is int and
             0 < receipt['campaign_started_at'] <=
             receipt['selection_frozen_at'] <= receipt['campaign_finished_at'] and
             receipt['campaign_finished_at'] - receipt['campaign_started_at'] <=
             matrix.CAMPAIGN_HOURS * 3600 and
             type(receipt['candidate_count']) is int and
             receipt['candidate_count'] >= 1 and
             type(receipt['selection_evaluations']) is int and
             receipt['selection_evaluations'] >= 1,
             f'{cell_id}/{researcher_id}: invalid selection freeze')
    return receipt


def _usage(receipt: object, *, cell_id: str, researcher_id: str,
           plan: dict, freeze: dict) -> dict:
    receipt = cell_final.exact(receipt, {
        'schema', 'cell_id', 'researcher_id', 'cost_basis',
        *USAGE_FIELDS, 'all_in_usd', *COUNT_FIELDS,
        'e2b_sandbox_hours',
        'provider_invoice_usd', 'failure_counts',
    }, 'campaign usage')
    _require(receipt['schema'] == 'cua-full-study-campaign-usage-v1' and
             receipt['cell_id'] == cell_id and
             receipt['researcher_id'] == researcher_id and
             receipt['cost_basis'] in ('provider_billed', 'published_rate_nominal'),
             'campaign usage identity or cost basis invalid')
    if receipt['provider_invoice_usd'] is not None:
        cell_final.amount(receipt['provider_invoice_usd'], 'provider_invoice_usd')
    # Keep the invoice null distinct from the positive, bounded nominal fields.
    amounts = {name: cell_final.amount(receipt[name], name) for name in USAGE_FIELDS}
    total = cell_final.amount(receipt['all_in_usd'], 'all_in_usd')
    _require(total == sum(amounts.values(), Decimal(0)),
             'campaign all-in subtotal does not equal its components')
    caps = {
        'tinker_nominal_usd': plan['tinker_usd_cap_per_campaign'],
        'researcher_inference_usd': plan['researcher_inference_usd_cap_per_campaign'],
        'teacher_rollout_usd': plan['teacher_rollout_usd_cap_per_campaign'],
        'e2b_usd': plan['e2b_usd_cap_per_campaign'],
        'storage_application_usd': plan['storage_application_usd_cap_per_campaign'],
        'all_in_usd': plan['per_campaign_all_in_ceiling_usd'],
    }
    for name, cap in caps.items():
        value = total if name == 'all_in_usd' else amounts[name]
        _require(value <= cell_final.amount(cap, name),
                 f'{cell_id}/{researcher_id}: {name} cap exceeded')
    count_caps = plan['matched_non_tinker_campaign_caps']
    counts = {
        'researcher_calls': 'researcher_calls_per_campaign',
        'teacher_rollout_tokens': 'teacher_rollout_tokens_per_campaign',
        'teacher_rollout_calls': 'teacher_rollout_calls_per_campaign',
        'e2b_peak_concurrency': 'e2b_peak_concurrency',
        'candidate_submissions': 'candidate_submissions_per_campaign',
        'selection_evaluations': 'selection_evaluations_per_campaign',
    }
    for name in COUNT_FIELDS:
        value = receipt[name]
        _require(type(value) is int and value >= 0,
                 f'{name}: nonnegative integer required')
        if name in counts:
            _require(value <= count_caps[counts[name]],
                     f'{cell_id}/{researcher_id}: {name} cap exceeded')
    _require(cell_final.amount(receipt['e2b_sandbox_hours'],
                               'e2b_sandbox_hours') <=
             cell_final.amount(plan['e2b_sandbox_hours_cap_per_campaign'],
                               'e2b_sandbox_hours_cap_per_campaign') and
             receipt['candidate_submissions'] == freeze['candidate_count'] and
             receipt['selection_evaluations'] == freeze['selection_evaluations'],
             f'{cell_id}/{researcher_id}: usage differs from frozen campaign')
    failures = receipt['failure_counts']
    _require(isinstance(failures, dict) and set(failures) == FAILURE_TYPES and
             all(type(value) is int and value >= 0 for value in failures.values()),
             'campaign failure counts incomplete')
    return receipt


def _execution(receipt: object, *, cell_id: str, owner: str,
               checkpoint: str, packages: dict[str, str], after_time: int) -> tuple[dict, Counter]:
    receipt = cell_final.exact(receipt, {
        'schema', 'cell_id', 'owner_slot', 'checkpoint_sha256',
        'status', 'started_at', 'finished_at', 'cost_basis',
        'cost_usd', 'tasks',
    }, 'final execution')
    _require(receipt['schema'] == 'cua-full-study-final-execution-v1' and
             receipt['cell_id'] == cell_id and receipt['owner_slot'] == owner and
             receipt['checkpoint_sha256'] == checkpoint and
             receipt['status'] == 'complete' and
             type(receipt['started_at']) is int and
             type(receipt['finished_at']) is int and
             after_time < receipt['started_at'] <= receipt['finished_at'] and
             receipt['cost_basis'] in ('provider_billed', 'published_rate_nominal'),
             f'{cell_id}/{owner}: final execution identity or timing invalid')
    cell_final.amount(receipt['cost_usd'], 'final execution cost')
    rows = receipt['tasks']
    _require(isinstance(rows, list) and len(rows) == 100,
             f'{cell_id}/{owner}: exactly 100 task results required')
    scores: dict[str, int] = {}
    invalid: Counter = Counter()
    for row in rows:
        row = cell_final.exact(row, {
            'task_id', 'package_sha256', 'score', 'saved_state_sha256',
            'verifier_receipt_sha256', 'reset_receipt_sha256',
            'observation_trace_sha256', 'action_trace_sha256', 'attempts',
        }, 'final task result')
        task = row['task_id']
        _require(task in packages and task not in scores and
                 row['package_sha256'] == packages[task] and
                 type(row['score']) is int and row['score'] in (0, 1) and
                 all(cell_final.is_hash(row[key]) for key in (
                     'saved_state_sha256', 'verifier_receipt_sha256',
                     'reset_receipt_sha256', 'observation_trace_sha256',
                     'action_trace_sha256')),
                 f'{cell_id}/{owner}: task score or evidence incomplete')
        attempts = row['attempts']
        _require(isinstance(attempts, list) and 1 <= len(attempts) <= 2,
                 'one valid attempt with at most one controlled recovery required')
        identifiers: set[str] = set()
        for index, attempt in enumerate(attempts):
            attempt = cell_final.exact(attempt, {
                'attempt_id', 'status', 'score', 'failure_type',
                'started_at', 'finished_at', 'receipt_sha256',
            }, 'task attempt')
            attempt_id = attempt['attempt_id']
            _require(isinstance(attempt_id, str) and attempt_id and
                     attempt_id not in identifiers and
                     type(attempt['started_at']) is int and
                     type(attempt['finished_at']) is int and
                     receipt['started_at'] <= attempt['started_at'] <=
                     attempt['finished_at'] <= receipt['finished_at'] and
                     cell_final.is_hash(attempt['receipt_sha256']),
                     'attempt identity, timestamp, or trace hash invalid')
            identifiers.add(attempt_id)
            if index == len(attempts) - 1:
                _require(attempt['status'] == 'scored' and
                         attempt['score'] == row['score'] and
                         attempt['failure_type'] is None,
                         'final attempt must be a valid scored model outcome')
            else:
                _require(attempt['status'] == 'invalid' and
                         attempt['score'] is None and
                         attempt['failure_type'] in FAILURE_TYPES,
                         'controlled recovery must preserve invalid attempt')
                invalid[attempt['failure_type']] += 1
        scores[task] = row['score']
    _require(set(scores) == set(packages),
             f'{cell_id}/{owner}: task coverage differs from frozen plan')
    return {'scores': scores, 'cost_usd': receipt['cost_usd'],
            'cost_basis': receipt['cost_basis']}, invalid


def audit(plan: object, index: object, root: Path, *,
          plan_sha256: str, bootstrap_replicates: int = 10_000) -> dict:
    _require(isinstance(plan, dict) and plan.get('schema') == matrix.PLAN_SCHEMA and
             plan.get('cell_ids') == list(matrix.CELLS) and
             plan.get('campaign_count') == 24 and
             plan.get('distinct_official_task_identities') == 600 and
             plan.get('initial_total_slot_task_results') == 3000 and
             plan.get('scores_present') is False and
             cell_final.digest(cell_final.json_bytes(plan)) == plan_sha256,
             'qualified final matrix plan required')
    index = cell_final.exact(index, {'schema', 'study_id', 'matrix_plan_sha256',
                                     'campaigns', 'final_executions'},
                             'execution index')
    _require(index['schema'] == SCHEMA and
             index['study_id'] == plan['study_id'] and
             index['matrix_plan_sha256'] == plan_sha256,
             'execution index does not bind the frozen matrix')
    cells = plan.get('cells')
    _require(isinstance(cells, list) and len(cells) == 6 and
             {cell.get('cell_id') for cell in cells} == set(matrix.CELLS),
             'six final matrix cells required')
    by_cell = {cell['cell_id']: cell for cell in cells}
    campaign_rows = index['campaigns']
    _require(isinstance(campaign_rows, list) and len(campaign_rows) == 24,
             'exactly 24 completed campaign records required')
    campaigns = {}
    reported_campaign_cost = Decimal(0)
    for raw in campaign_rows:
        row = cell_final.exact(raw, {'cell_id', 'researcher_id', 'status',
                                     'selection_freeze', 'usage'}, 'campaign record')
        cell_id, researcher_id = row['cell_id'], row['researcher_id']
        key = (cell_id, researcher_id)
        _require(row['status'] == 'complete' and
                 cell_id in by_cell and researcher_id in matrix.RESEARCHERS and
                 key not in campaigns, 'duplicate or unknown campaign')
        cell = by_cell[cell_id]
        selected = cell['researcher_plans'][researcher_id]['bindings']['checkpoint']
        base = cell['base']['bindings']['checkpoint']
        freeze = _freeze(_reference_json(root, row['selection_freeze'],
                                          f'{cell_id}/{researcher_id} freeze'),
                         cell_id=cell_id, researcher_id=researcher_id,
                         checkpoint=selected, base_checkpoint=base)
        usage = _usage(_reference_json(root, row['usage'],
                                        f'{cell_id}/{researcher_id} usage'),
                       cell_id=cell_id, researcher_id=researcher_id,
                       plan=plan, freeze=freeze)
        reported_campaign_cost += cell_final.amount(usage['all_in_usd'], 'all_in_usd')
        campaigns[key] = {'freeze': freeze, 'usage': usage}
    _require(set(campaigns) == {(cell, researcher) for cell in matrix.CELLS
                                for researcher in matrix.RESEARCHERS},
             'campaign coverage incomplete')
    expected_owners = {(cell_id, owner)
                       for cell_id, cell in by_cell.items()
                       for owner in set(cell['execution_evidence_owner_by_slot'].values())}
    execution_rows = index['final_executions']
    _require(isinstance(execution_rows, list) and
             len(execution_rows) == len(expected_owners),
             'unique checkpoint execution count differs from frozen matrix')
    executions = {}
    invalid_counts: Counter = Counter()
    shared_base_cost = Decimal(0)
    for raw in execution_rows:
        raw = cell_final.exact(raw, {'cell_id', 'owner_slot', 'receipt'},
                               'execution reference')
        cell_id, owner = raw['cell_id'], raw['owner_slot']
        key = (cell_id, owner)
        _require(key in expected_owners and key not in executions,
                 'unknown or duplicate execution owner')
        cell = by_cell[cell_id]
        slot_plan = cell['base'] if owner == 'shared-base' else cell['researcher_plans'][owner]
        checkpoint = slot_plan['bindings']['checkpoint']
        packages = _task_packages(cell['base'])
        last_freeze = max(campaigns[(cell_id, rid)]['freeze']['selection_frozen_at']
                          for rid in matrix.RESEARCHERS)
        record, invalid = _execution(
            _reference_json(root, raw['receipt'], f'{cell_id}/{owner} final execution'),
            cell_id=cell_id, owner=owner, checkpoint=checkpoint,
            packages=packages, after_time=last_freeze)
        _require(cell_final.amount(record['cost_usd'], 'final execution cost') <=
                 cell_final.amount(slot_plan['declared_all_in_cost_upper_bound_usd'],
                                   'slot final cost upper bound'),
                 f'{cell_id}/{owner}: final execution cost cap exceeded')
        invalid_counts.update(invalid)
        if owner == 'shared-base':
            shared_base_cost += cell_final.amount(record['cost_usd'], 'base cost')
        else:
            declared = campaigns[(cell_id, owner)]['usage']['selected_final_usd']
            _require(cell_final.amount(declared, 'selected_final_usd') ==
                     cell_final.amount(record['cost_usd'], 'selected final cost'),
                     f'{cell_id}/{owner}: selected final cost disagrees with campaign')
        executions[key] = record
    _require(set(executions) == expected_owners,
             'final execution evidence coverage incomplete')
    paired = []
    for cell_id in matrix.CELLS:
        cell = by_cell[cell_id]
        reuse = cell['execution_evidence_owner_by_slot']
        base_scores = executions[(cell_id, reuse['shared-base'])]['scores']
        for researcher_id in matrix.RESEARCHERS:
            owner = reuse[researcher_id]
            selected_scores = executions[(cell_id, owner)]['scores']
            if owner != researcher_id:
                _require(cell_final.amount(campaigns[(cell_id, researcher_id)]['usage'][
                    'selected_final_usd'], 'selected_final_usd') == 0,
                    f'{cell_id}/{researcher_id}: reused execution charged twice')
            summary = stats.paired_summary(
                base_scores, selected_scores, cell['analysis_family_by_task'],
                replicates=bootstrap_replicates)
            paired.append({'cell_id': cell_id, 'researcher_id': researcher_id,
                           'execution_evidence_owner': owner,
                           'summary': summary})
    _require(len(paired) == 24, 'paired result coverage incomplete')
    _require(reported_campaign_cost + shared_base_cost <=
             cell_final.amount(plan['declared_all_in_cost_upper_bound_usd'],
                               'declared study upper bound'),
             'audited total exceeds frozen study ceiling')
    invoice_complete = all(
        campaign['usage']['cost_basis'] == 'provider_billed' and
        campaign['usage']['provider_invoice_usd'] is not None
        for campaign in campaigns.values()) and all(
            execution['cost_basis'] == 'provider_billed'
            for execution in executions.values())
    return {
        'schema': SUMMARY_SCHEMA, 'study_id': plan['study_id'],
        'matrix_plan_sha256': plan_sha256,
        'execution_index_sha256': cell_final.digest(cell_final.json_bytes(index)),
        'campaign_count': 24, 'distinct_final_task_identities': 600,
        'slot_task_result_count': 3000,
        'unique_checkpoint_task_executions': len(executions) * 100,
        'infrastructure_invalid_attempts_by_type': {
            kind: invalid_counts[kind] for kind in sorted(FAILURE_TYPES)},
        'reported_campaign_cost_subtotal_usd': str(reported_campaign_cost),
        'reported_shared_base_final_cost_subtotal_usd': str(shared_base_cost),
        'reported_all_in_cost_subtotal_usd': str(reported_campaign_cost + shared_base_cost),
        'cost_bases_present': sorted({
            *(campaign['usage']['cost_basis'] for campaign in campaigns.values()),
            *(execution['cost_basis'] for execution in executions.values()),
        }),
        'provider_invoice_complete': invoice_complete,
        'application_receipt_truth_requires_independent_audit': True,
        'comparisons': paired,
    }
