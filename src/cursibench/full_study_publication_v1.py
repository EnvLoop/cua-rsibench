"""Fail-closed source audit for the English full-study result paper.

The historical v1 execution index is unchanged. Publication additionally
requires independently reviewed application evidence and complete per-attempt
telemetry. No provider calls or application actions occur in this module.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from statistics import median

from . import full_study_matrix_v1 as matrix
from . import full_study_results_v1 as results
from . import scale_final_v06 as evidence


TELEMETRY_SCHEMA = 'cua-full-study-final-attempt-telemetry-index-v1'
EXECUTION_TELEMETRY_SCHEMA = 'cua-full-study-execution-telemetry-v1'
REVIEW_SCHEMA = 'cua-full-study-independent-release-audit-v1'
CELL_REVIEW_SCHEMA = 'cua-full-study-independent-cell-review-v1'
TRAJECTORY_SCHEMA = 'cua-full-study-campaign-trajectory-index-v1'
CAMPAIGN_TRAJECTORY_SCHEMA = 'cua-full-study-campaign-trajectory-v1'
TIMEOUT_TYPES = {
    'none', 'provider', 'transport', 'environment', 'verifier',
    'actor_action_budget', 'actor_wall_budget',
}
PUBLISHED_STUDY_ID = 'full-computer-use-v1'
USAGE_FIELDS = results.USAGE_FIELDS
ROUND_FAILURE_TYPES = results.FAILURE_TYPES | {'validation', 'budget', 'other'}
_VERIFIED_PUBLICATION_TOKEN = object()


class VerifiedPublicationData(dict):
    """In-process result of the complete source audit, not a public input format.

    The renderer accepts this type for an unwatermarked report. This is an
    accidental-misuse boundary, not a security boundary against Python code
    that deliberately forges objects inside this process.
    """

    def __init__(self, value: dict, *, _token: object) -> None:
        if _token is not _VERIFIED_PUBLICATION_TOKEN:
            raise ValueError('publication data must come from the complete source audit')
        super().__init__(value)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path, label: str) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f'{label}: invalid JSON') from None
    require(isinstance(value, dict), f'{label}: JSON object required')
    return value, raw


def read_reference(root: Path, reference: object, label: str) -> dict:
    _, raw = evidence.evidence_file(root, reference, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f'{label}: invalid JSON') from None
    require(isinstance(value, dict), f'{label}: JSON object required')
    return value


def _review_bundle(review: dict, root: Path, summary: dict) -> dict:
    review = evidence.exact(review, {
        'schema', 'study_id', 'matrix_plan_sha256',
        'execution_index_sha256', 'cells',
    }, 'independent review index')
    require(review['schema'] == REVIEW_SCHEMA and
            review['study_id'] == summary['study_id'] and
            review['matrix_plan_sha256'] == summary['matrix_plan_sha256'] and
            review['execution_index_sha256'] == summary['execution_index_sha256'],
            'independent review does not bind the audited result')
    cells = review['cells']
    require(isinstance(cells, list) and len(cells) == len(matrix.CELLS),
            'six independent cell reviews required')
    seen: set[str] = set()
    checks = (
        'source_rights_checked', 'hidden_split_checked',
        'gui_trace_and_saved_state_readback_checked',
        'reset_and_negative_controls_checked',
        'evaluator_independent_of_actor',
    )
    for entry in cells:
        entry = evidence.exact(entry, {'cell_id', 'receipt'}, 'cell review reference')
        cell_id = entry['cell_id']
        require(cell_id in matrix.CELLS and cell_id not in seen,
                'unknown or duplicate independent cell review')
        seen.add(cell_id)
        receipt = evidence.exact(
            read_reference(root, entry['receipt'], f'{cell_id} review'),
            {'schema', 'cell_id', 'study_id', 'matrix_plan_sha256',
             'execution_index_sha256', 'reviewer_id', 'reviewed_at_utc',
             'checked_final_task_count', 'evidence_bundle_sha256',
             'method_notes', 'passed', *checks},
            f'{cell_id} review')
        try:
            reviewed = datetime.fromisoformat(receipt['reviewed_at_utc'])
        except (TypeError, ValueError):
            raise ValueError(f'{cell_id}: review timestamp invalid') from None
        require(receipt['schema'] == CELL_REVIEW_SCHEMA and
                receipt['cell_id'] == cell_id and
                receipt['study_id'] == summary['study_id'] and
                receipt['matrix_plan_sha256'] == summary['matrix_plan_sha256'] and
                receipt['execution_index_sha256'] == summary['execution_index_sha256'] and
                type(receipt['checked_final_task_count']) is int and
                receipt['checked_final_task_count'] == matrix.OFFICIAL_PER_CELL and
                all(receipt[key] is True for key in checks) and
                receipt['passed'] is True and
                evidence.is_hash(receipt['evidence_bundle_sha256']) and
                isinstance(receipt['reviewer_id'], str) and
                bool(receipt['reviewer_id'].strip()) and
                isinstance(receipt['method_notes'], str) and
                bool(receipt['method_notes'].strip()) and
                reviewed.tzinfo is not None and
                reviewed.utcoffset() == timezone.utc.utcoffset(reviewed),
                f'{cell_id}: independent review incomplete')
    require(seen == set(matrix.CELLS), 'independent review cell coverage incomplete')
    return {'cell_count': len(seen), 'index_sha256': evidence.digest(evidence.json_bytes(review))}


def _attempt_telemetry(metric: object, attempt: dict, first: dict | None,
                       *, cell_id: str, owner: str, task_id: str) -> dict:
    label = f'{cell_id}/{owner}/{task_id}/{attempt["attempt_id"]}'
    metric = evidence.exact(metric, {
        'attempt_id', 'attempt_receipt_sha256', 'timeout_subtype',
        'action_count', 'wall_time_ms', 'provider_latency_ms',
        'telemetry_trace_sha256', 'retry_provenance',
    }, f'{label} telemetry')
    require(metric['attempt_id'] == attempt['attempt_id'] and
            metric['attempt_receipt_sha256'] == attempt['receipt_sha256'] and
            evidence.is_hash(metric['telemetry_trace_sha256']) and
            metric['timeout_subtype'] in TIMEOUT_TYPES and
            all(type(metric[key]) is int and metric[key] >= 0 for key in (
                'action_count', 'wall_time_ms', 'provider_latency_ms')),
            f'{label}: telemetry identity or measurement invalid')
    span_ms = (attempt['finished_at'] - attempt['started_at'] + 1) * 1000
    require(metric['wall_time_ms'] <= span_ms,
            f'{label}: wall time exceeds receipt time window')
    subtype = metric['timeout_subtype']
    if subtype in results.FAILURE_TYPES:
        require(attempt['status'] == 'invalid' and
                attempt['failure_type'] == subtype,
                f'{label}: infrastructure timeout differs from failure type')
    elif subtype in {'actor_action_budget', 'actor_wall_budget'}:
        require(attempt['status'] == 'scored' and attempt['score'] == 0,
                f'{label}: actor budget timeout must be a scored model failure')
    if first is None:
        require(metric['retry_provenance'] is None,
                f'{label}: initial attempt cannot claim retry provenance')
    else:
        provenance = evidence.exact(metric['retry_provenance'], {
            'prior_attempt_id', 'prior_attempt_receipt_sha256',
            'retry_rule_sha256',
        }, f'{label} retry provenance')
        require(provenance['prior_attempt_id'] == first['attempt_id'] and
                provenance['prior_attempt_receipt_sha256'] == first['receipt_sha256'] and
                evidence.is_hash(provenance['retry_rule_sha256']),
                f'{label}: retry does not bind prior attempt and frozen rule')
    return metric


def _telemetry_bundle(telemetry: dict, root: Path, index: dict,
                      index_root: Path, summary: dict) -> dict:
    telemetry = evidence.exact(telemetry, {
        'schema', 'study_id', 'matrix_plan_sha256',
        'execution_index_sha256', 'executions',
    }, 'final-attempt telemetry index')
    require(telemetry['schema'] == TELEMETRY_SCHEMA and
            telemetry['study_id'] == summary['study_id'] and
            telemetry['matrix_plan_sha256'] == summary['matrix_plan_sha256'] and
            telemetry['execution_index_sha256'] == summary['execution_index_sha256'],
            'final-attempt telemetry does not bind the audited result')
    execution_refs = {(row['cell_id'], row['owner_slot']): row['receipt']
                      for row in index['final_executions']}
    entries = telemetry['executions']
    require(isinstance(entries, list) and len(entries) == len(execution_refs),
            'telemetry must cover every unique checkpoint execution')
    seen: set[tuple[str, str]] = set()
    actions: list[int] = []
    wall_times: list[int] = []
    provider_latencies: list[int] = []
    timeout_counts: Counter[str] = Counter()
    attempts = 0
    retries = 0
    for entry in entries:
        entry = evidence.exact(entry, {'cell_id', 'owner_slot', 'receipt'},
                               'execution telemetry reference')
        cell_id, owner = entry['cell_id'], entry['owner_slot']
        key = (cell_id, owner)
        require(key in execution_refs and key not in seen,
                'unknown or duplicate execution telemetry')
        seen.add(key)
        source_ref = execution_refs[key]
        source = read_reference(index_root, source_ref,
                                f'{cell_id}/{owner} final execution')
        measured = evidence.exact(
            read_reference(root, entry['receipt'], f'{cell_id}/{owner} telemetry'),
            {'schema', 'cell_id', 'owner_slot', 'execution_receipt_sha256', 'tasks'},
            f'{cell_id}/{owner} telemetry')
        require(measured['schema'] == EXECUTION_TELEMETRY_SCHEMA and
                measured['cell_id'] == cell_id and
                measured['owner_slot'] == owner and
                measured['execution_receipt_sha256'] == source_ref['sha256'],
                f'{cell_id}/{owner}: telemetry does not bind execution receipt')
        task_rows = measured['tasks']
        require(isinstance(task_rows, list) and len(task_rows) == 100,
                f'{cell_id}/{owner}: telemetry requires exactly 100 tasks')
        source_tasks = {row['task_id']: row for row in source['tasks']}
        task_seen: set[str] = set()
        for task in task_rows:
            task = evidence.exact(task, {'task_id', 'attempts'},
                                  'task telemetry')
            task_id = task['task_id']
            require(task_id in source_tasks and task_id not in task_seen,
                    f'{cell_id}/{owner}: unknown or duplicate task telemetry')
            task_seen.add(task_id)
            original = source_tasks[task_id]['attempts']
            metrics = task['attempts']
            require(isinstance(metrics, list) and len(metrics) == len(original),
                    f'{cell_id}/{owner}/{task_id}: attempt telemetry incomplete')
            if len(original) == 2:
                require(original[0]['finished_at'] <= original[1]['started_at'],
                        f'{cell_id}/{owner}/{task_id}: recovery precedes invalid attempt')
            for position, (metric, attempt) in enumerate(zip(metrics, original)):
                row = _attempt_telemetry(metric, attempt,
                                         original[0] if position == 1 else None,
                                         cell_id=cell_id, owner=owner,
                                         task_id=task_id)
                actions.append(row['action_count'])
                wall_times.append(row['wall_time_ms'])
                provider_latencies.append(row['provider_latency_ms'])
                timeout_counts[row['timeout_subtype']] += 1
                attempts += 1
                retries += position == 1
        require(task_seen == set(source_tasks),
                f'{cell_id}/{owner}: telemetry task coverage incomplete')
    require(seen == set(execution_refs), 'telemetry execution coverage incomplete')
    require(attempts >= summary['unique_checkpoint_task_executions'] and
            retries == attempts - summary['unique_checkpoint_task_executions'],
            'telemetry attempt/retry count differs from audited executions')
    invalid_attempts = sum(summary['infrastructure_invalid_attempts_by_type'].values())
    require(retries == invalid_attempts,
            'telemetry retry count differs from preserved invalid attempts')
    return {
        'index_sha256': evidence.digest(evidence.json_bytes(telemetry)),
        'execution_count': len(entries), 'task_count': len(entries) * 100,
        'attempt_count': attempts, 'retry_count': retries,
        'timeout_counts': {key: timeout_counts[key] for key in sorted(TIMEOUT_TYPES)},
        'action_counts': actions, 'wall_times_ms': wall_times,
        'provider_latencies_ms': provider_latencies,
    }


def _usage_aggregates(index: dict, root: Path, summary: dict) -> dict:
    amounts = {key: Decimal(0) for key in USAGE_FIELDS}
    failures: Counter[str] = Counter()
    for row in index['campaigns']:
        usage = read_reference(root, row['usage'],
                               f'{row["cell_id"]}/{row["researcher_id"]} usage')
        for key in USAGE_FIELDS:
            amounts[key] += results.actual_usd(usage[key], key)
        failures.update(usage['failure_counts'])
    campaign_total = sum(amounts.values(), Decimal(0))
    require(campaign_total == results.actual_usd(
                summary['reported_campaign_cost_subtotal_usd'],
                'reported campaign cost subtotal'),
            'campaign cost components differ from audited result')
    return {
        'cost_components_usd': {key: str(amounts[key]) for key in USAGE_FIELDS},
        'shared_base_final_usd': summary['reported_shared_base_final_cost_subtotal_usd'],
        'campaign_failures_by_type': {key: failures[key]
                                      for key in sorted(results.FAILURE_TYPES)},
    }


def _selection_attempt(value: object, *, label: str, position: int,
                       earlier: dict | None, started: int, finished: int) -> dict:
    attempt = evidence.exact(value, {
        'attempt_id', 'status', 'score_wins', 'task_count',
        'result_receipt_sha256', 'failure_type', 'started_at',
        'finished_at', 'retry_rule_sha256',
    }, f'{label} selection attempt')
    require(isinstance(attempt['attempt_id'], str) and
            bool(attempt['attempt_id'].strip()) and
            attempt['status'] in {'scored', 'invalid'} and
            type(attempt['started_at']) is int and
            type(attempt['finished_at']) is int and
            started <= attempt['started_at'] <= attempt['finished_at'] <= finished and
            type(attempt['task_count']) is int and
            attempt['task_count'] == matrix.SELECTION_PER_CELL and
            evidence.is_hash(attempt['result_receipt_sha256']),
            f'{label}: selection attempt identity, timing, or source invalid')
    if attempt['status'] == 'scored':
        require(type(attempt['score_wins']) is int and
                0 <= attempt['score_wins'] <= matrix.SELECTION_PER_CELL and
                attempt['failure_type'] is None,
                f'{label}: scored selection result invalid')
    else:
        require(attempt['score_wins'] is None and
                attempt['failure_type'] in ROUND_FAILURE_TYPES,
                f'{label}: invalid selection result lacks failure class')
    if position == 0:
        require(attempt['retry_rule_sha256'] is None,
                f'{label}: initial selection attempt has a retry rule')
    else:
        require(earlier is not None and earlier['status'] == 'invalid' and
                earlier['finished_at'] <= attempt['started_at'] and
                attempt['attempt_id'] != earlier['attempt_id'] and
                evidence.is_hash(attempt['retry_rule_sha256']),
                f'{label}: selection retry lacks preserved invalid attempt or rule')
    return attempt


def _search_metrics(scored_rows: list[dict]) -> dict:
    require(bool(scored_rows), 'at least one valid selection score required')
    scores = [row['wins'] for row in scored_rows]
    best = max(scores)
    best_row = next(row for row in scored_rows if row['wins'] == best)
    return {
        'first_valid_wins': scores[0], 'best_valid_wins': best,
        'last_valid_wins': scores[-1], 'best_valid_round': best_row['round'],
        'improved_over_first_valid': best > scores[0],
        'last_below_peak_after_search': (
            scored_rows[-1]['round'] > best_row['round'] and scores[-1] < best),
        'declining_valid_transitions': sum(
            after < before for before, after in zip(scores, scores[1:])),
    }


def _trajectory_bundle(trajectory: dict, root: Path, index: dict,
                       index_root: Path, summary: dict) -> dict:
    trajectory = evidence.exact(trajectory, {
        'schema', 'study_id', 'matrix_plan_sha256',
        'execution_index_sha256', 'campaigns',
    }, 'campaign trajectory index')
    require(trajectory['schema'] == TRAJECTORY_SCHEMA and
            trajectory['study_id'] == summary['study_id'] and
            trajectory['matrix_plan_sha256'] == summary['matrix_plan_sha256'] and
            trajectory['execution_index_sha256'] == summary['execution_index_sha256'],
            'campaign trajectories do not bind the audited result')
    campaigns = {(row['cell_id'], row['researcher_id']): row
                 for row in index['campaigns']}
    entries = trajectory['campaigns']
    require(isinstance(entries, list) and len(entries) == len(campaigns) == 24,
            'all 24 campaign trajectories required')
    seen: set[tuple[str, str]] = set()
    summaries = []
    total_rounds = 0
    total_scored = 0
    total_unscored = 0
    total_selection_retries = 0
    round_wall_times: list[int] = []
    round_cost_total = Decimal(0)
    for entry in entries:
        entry = evidence.exact(entry, {'cell_id', 'researcher_id', 'receipt'},
                               'campaign trajectory reference')
        cell_id, researcher_id = entry['cell_id'], entry['researcher_id']
        key = (cell_id, researcher_id)
        require(key in campaigns and key not in seen,
                'unknown or duplicate campaign trajectory')
        seen.add(key)
        campaign = campaigns[key]
        freeze = read_reference(index_root, campaign['selection_freeze'],
                                f'{cell_id}/{researcher_id} selection freeze')
        usage = read_reference(index_root, campaign['usage'],
                               f'{cell_id}/{researcher_id} usage')
        receipt = evidence.exact(
            read_reference(root, entry['receipt'], f'{cell_id}/{researcher_id} trajectory'),
            {'schema', 'study_id', 'cell_id', 'researcher_id',
             'selection_freeze_receipt_sha256', 'usage_receipt_sha256',
             'training_lineage_sha256', 'selection_results_bundle_sha256',
             'base_selection_wins', 'base_selection_results_sha256', 'rounds'},
            f'{cell_id}/{researcher_id} trajectory')
        require(receipt['schema'] == CAMPAIGN_TRAJECTORY_SCHEMA and
                receipt['study_id'] == summary['study_id'] and
                receipt['cell_id'] == cell_id and
                receipt['researcher_id'] == researcher_id and
                receipt['selection_freeze_receipt_sha256'] ==
                    campaign['selection_freeze']['sha256'] and
                receipt['usage_receipt_sha256'] == campaign['usage']['sha256'] and
                receipt['training_lineage_sha256'] == freeze['training_lineage_sha256'] and
                receipt['selection_results_bundle_sha256'] ==
                    freeze['selection_results_sha256'] and
                evidence.is_hash(receipt['base_selection_results_sha256']) and
                type(receipt['base_selection_wins']) is int and
                0 <= receipt['base_selection_wins'] <= matrix.SELECTION_PER_CELL,
                f'{cell_id}/{researcher_id}: trajectory lineage or base score invalid')
        rounds = receipt['rounds']
        require(isinstance(rounds, list) and rounds,
                f'{cell_id}/{researcher_id}: ordered rounds required')
        incumbent_checkpoint = freeze['base_checkpoint_sha256']
        incumbent_wins = receipt['base_selection_wins']
        scored_rows = []
        public_rows = []
        submitted_count = 0
        selection_count = 0
        previous_finished = freeze['campaign_started_at']
        cost = Decimal(0)
        for position, value in enumerate(rounds, start=1):
            label = f'{cell_id}/{researcher_id}/round-{position}'
            row = evidence.exact(value, {
                'round_index', 'started_at', 'finished_at',
                'candidate_submitted', 'hypothesis_sha256',
                'training_data_sha256', 'training_receipt_sha256',
                'training_base_checkpoint_sha256',
                'checkpoint_sha256', 'selection_attempts',
                'regressions_vs_incumbent', 'promotion_decision',
                'incumbent_after_checkpoint_sha256',
                'cost_usd', 'cost_basis', 'failure_type',
            }, label)
            require(type(row['round_index']) is int and
                    row['round_index'] == position and
                    type(row['started_at']) is int and
                    type(row['finished_at']) is int and
                    previous_finished <= row['started_at'] <=
                    row['finished_at'] <= freeze['campaign_finished_at'] and
                    evidence.is_hash(row['hypothesis_sha256']) and
                    type(row['candidate_submitted']) is bool and
                    row['cost_basis'] == usage['cost_basis'],
                    f'{label}: round ordering, hypothesis, or cost basis invalid')
            previous_finished = row['finished_at']
            round_cost = results.actual_usd(row['cost_usd'], f'{label} cost')
            cost += round_cost
            round_cost_total += round_cost
            round_wall_times.append(row['finished_at'] - row['started_at'])
            submitted_count += row['candidate_submitted']
            if row['candidate_submitted']:
                require(evidence.is_hash(row['training_data_sha256']) and
                        row['training_base_checkpoint_sha256'] ==
                            freeze['base_checkpoint_sha256'],
                        f'{label}: submitted candidate lacks data or fixed base')
            else:
                require(row['training_data_sha256'] is None and
                        row['training_receipt_sha256'] is None and
                        row['training_base_checkpoint_sha256'] is None and
                        row['checkpoint_sha256'] is None,
                        f'{label}: no-candidate round claims training evidence')
            if row['checkpoint_sha256'] is not None:
                require(row['candidate_submitted'] and
                        evidence.is_hash(row['checkpoint_sha256']) and
                        evidence.is_hash(row['training_receipt_sha256']),
                        f'{label}: checkpoint lacks training provenance')
            else:
                require(row['training_receipt_sha256'] is None,
                        f'{label}: training receipt without checkpoint')
            attempts = row['selection_attempts']
            require(isinstance(attempts, list) and len(attempts) <= 2 and
                    (not attempts or row['checkpoint_sha256'] is not None),
                    f'{label}: selection attempts lack checkpoint')
            selection_count += len(attempts)
            total_selection_retries += max(0, len(attempts) - 1)
            checked = []
            for attempt_index, attempt in enumerate(attempts):
                checked.append(_selection_attempt(
                    attempt, label=label, position=attempt_index,
                    earlier=checked[0] if attempt_index else None,
                    started=row['started_at'], finished=row['finished_at']))
            if checked:
                require(sum(attempt['status'] == 'scored' for attempt in checked) <= 1 and
                        (checked[-1]['status'] == 'scored' or
                         all(attempt['status'] == 'invalid' for attempt in checked)),
                        f'{label}: multiple valid selection evaluations')
            scored = checked[-1] if checked and checked[-1]['status'] == 'scored' else None
            if scored is not None:
                wins = scored['score_wins']
                regressions = row['regressions_vs_incumbent']
                require(type(regressions) is int and
                        0 <= regressions <= matrix.SELECTION_PER_CELL and
                        row['failure_type'] is None,
                        f'{label}: scored candidate regression evidence invalid')
                if row['promotion_decision'] == 'promoted':
                    require(wins > incumbent_wins and regressions == 0 and
                            row['incumbent_after_checkpoint_sha256'] ==
                                row['checkpoint_sha256'],
                            f'{label}: promotion violates strict gain/no regression')
                    incumbent_checkpoint = row['checkpoint_sha256']
                    incumbent_wins = wins
                else:
                    require(row['promotion_decision'] == 'retained' and
                            row['incumbent_after_checkpoint_sha256'] ==
                                incumbent_checkpoint,
                            f'{label}: retained checkpoint changed')
                scored_rows.append({'round': position, 'wins': wins})
            else:
                require(row['regressions_vs_incumbent'] is None and
                        row['promotion_decision'] == 'retained' and
                        row['incumbent_after_checkpoint_sha256'] ==
                            incumbent_checkpoint and
                        row['failure_type'] in ROUND_FAILURE_TYPES and
                        (not checked or row['failure_type'] ==
                         checked[-1]['failure_type']),
                        f'{label}: unscored round lacks failure or retains wrong checkpoint')
            public_rows.append({
                'round': position, 'candidate_submitted': row['candidate_submitted'],
                'selection_wins': scored['score_wins'] if scored else None,
                'promotion_decision': row['promotion_decision'],
                'failure_type': row['failure_type'],
                'cost_usd': row['cost_usd'],
                'wall_seconds': row['finished_at'] - row['started_at'],
            })
        require(submitted_count == freeze['candidate_count'] and
                selection_count == freeze['selection_evaluations'] and
                previous_finished <= freeze['selection_frozen_at'] and
                incumbent_checkpoint == freeze['selected_checkpoint_sha256'] and
                scored_rows and
                cost <= (results.actual_usd(usage['all_in_usd'], 'all_in_usd') -
                         results.actual_usd(usage['selected_final_usd'],
                                            'selected_final_usd')),
                f'{cell_id}/{researcher_id}: trajectory differs from frozen selection or usage')
        search_metrics = _search_metrics(scored_rows)
        total_rounds += len(rounds)
        total_scored += len(scored_rows)
        total_unscored += len(rounds) - len(scored_rows)
        summaries.append({
            'cell_id': cell_id, 'researcher_id': researcher_id,
            'round_count': len(rounds), 'candidate_submissions': submitted_count,
            'selection_attempt_count': selection_count,
            'scored_round_count': len(scored_rows),
            **search_metrics,
            'selected_checkpoint_selection_wins': incumbent_wins,
            'round_cost_subtotal_usd': str(cost),
            'round_wall_seconds_subtotal': sum(
                row['wall_seconds'] for row in public_rows),
            'rounds': public_rows,
        })
    require(seen == set(campaigns), 'campaign trajectory coverage incomplete')
    summaries.sort(key=lambda row: (matrix.CELLS.index(row['cell_id']),
                                    list(matrix.RESEARCHERS).index(row['researcher_id'])))
    return {
        'index_sha256': evidence.digest(evidence.json_bytes(trajectory)),
        'campaign_count': len(summaries),
        'round_count': total_rounds,
        'scored_round_count': total_scored,
        'unscored_round_count': total_unscored,
        'selection_retry_count': total_selection_retries,
        'round_cost_subtotal_usd': str(round_cost_total),
        'round_wall_seconds_median': median(round_wall_times),
        'improved_over_first_valid_campaigns': sum(
            row['improved_over_first_valid'] for row in summaries),
        'last_below_peak_campaigns': sum(
            row['last_below_peak_after_search'] for row in summaries),
        'campaigns': summaries,
    }


def load_publication_data(*, matrix_manifest: Path, execution_index: Path,
                          audited_summary: Path, telemetry_index: Path,
                          independent_review: Path,
                          trajectory_index: Path) -> VerifiedPublicationData:
    """Rebuild and verify every input before returning aggregate report data."""
    manifest, manifest_raw = read_json(matrix_manifest, 'matrix manifest')
    plan = matrix.build(manifest, matrix_manifest.parent,
                        evidence.digest(manifest_raw))
    index, _ = read_json(execution_index, 'execution index')
    plan_sha = evidence.digest(evidence.json_bytes(plan))
    recomputed = results.audit(plan, index, execution_index.parent,
                               plan_sha256=plan_sha,
                               bootstrap_replicates=10_000)
    summary, summary_raw = read_json(audited_summary, 'audited summary')
    require(summary == recomputed,
            'supplied summary differs from a fresh full-study audit')
    require(summary['schema'] == results.SUMMARY_SCHEMA and
            summary['study_id'] == PUBLISHED_STUDY_ID and
            summary['campaign_count'] == 24 and
            summary['distinct_final_task_identities'] == 600 and
            summary['slot_task_result_count'] == 3000 and
            len(summary['comparisons']) == 24 and
            plan['student_model'] == matrix.STUDENT and
            plan['teacher_model'] == matrix.TEACHER and
            plan['researchers'] == matrix.RESEARCHERS and
            all(row['summary']['bootstrap_replicates'] == 10_000 and
                row['summary']['bootstrap_seed'] == 23
                for row in summary['comparisons']),
            'full preregistered result or bootstrap protocol missing')
    telemetry, telemetry_raw = read_json(telemetry_index, 'telemetry index')
    measures = _telemetry_bundle(telemetry, telemetry_index.parent, index,
                                 execution_index.parent, summary)
    trajectory, trajectory_raw = read_json(trajectory_index, 'campaign trajectory index')
    search = _trajectory_bundle(trajectory, trajectory_index.parent, index,
                                execution_index.parent, summary)
    review, review_raw = read_json(independent_review, 'independent review')
    reviewed = _review_bundle(review, independent_review.parent, summary)
    usage = _usage_aggregates(index, execution_index.parent, summary)
    family_counts = {cell['cell_id']: len(set(cell['analysis_family_by_task'].values()))
                     for cell in plan['cells']}
    return VerifiedPublicationData({
        'plan': plan, 'summary': summary, 'telemetry': measures,
        'review': reviewed, 'usage': usage, 'trajectory': search,
        'family_counts': family_counts,
        'source_hashes': {
            'matrix_manifest_sha256': evidence.digest(manifest_raw),
            'matrix_plan_sha256': plan_sha,
            'execution_index_sha256': summary['execution_index_sha256'],
            'audited_summary_sha256': evidence.digest(summary_raw),
            'telemetry_index_sha256': evidence.digest(telemetry_raw),
            'trajectory_index_sha256': evidence.digest(trajectory_raw),
            'independent_review_sha256': evidence.digest(review_raw),
        },
    }, _token=_VERIFIED_PUBLICATION_TOKEN)
