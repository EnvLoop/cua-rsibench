"""Validate task-specific SaaS GUI receipts against pinned source and split.

Only named adapters are accepted. A public WebArena task can earn a narrowly
scoped development-control status, never a sealed official-final identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import build_saas_admission_matrix_v06 as matrix
import plan_gitlab_final_candidates_v06 as gitlab
import plan_magento_final_candidates_v06 as magento


GITLAB_IMAGE = 'sha256:f7e992491db0c80a9a3f066c2c26e69b444307b5a8834e1bdde7929c4a74e97e'
MAGENTO_IMAGE = 'sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13'


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_gitlab_hard_milestone(result_path: Path, source_row: dict, hard_ids: set[int]) -> dict:
    """Verify actual positive/near-miss/positive SQL-reset evidence for task 590."""
    raw = result_path.read_bytes()
    result = json.loads(raw)
    task_id = 590
    require(source_row['task_id'] == result.get('task_id') == task_id, 'GitLab task identity drift')
    require(task_id in hard_ids and source_row['sites'] == ['gitlab'], 'GitLab hard membership drift')
    require(result['source']['dataset_sha256'] == gitlab.SOURCE_SHA256
            and result['source']['git_commit'] == gitlab.SOURCE_COMMIT
            and result['source']['task_sha256'] == canonical_sha(source_row), 'GitLab source receipt drift')
    require(result['container']['image_sha256'] == GITLAB_IMAGE
            and result['container']['loopback_port'] == 8013
            and result['original_snapshot_seeded'] is False,
            'GitLab environment scope differs from synthetic isolated control')
    require(result['complete'] is True and result['model_calls'] == 0
            and result['hundred_task_ready'] is False
            and result['qualified_task_count'] == 1, 'GitLab control lifecycle incomplete')
    require(result['scores'] == [1.0, 0.0, 1.0], 'GitLab score sequence did not discriminate')
    baseline = result['business_baseline']
    require(result['final_business_state'] == baseline and not baseline['milestones'],
            'GitLab final monitored business baseline not restored')
    attempts = result['attempts']
    require(len(attempts) == 3, 'GitLab control needs three separate attempts')
    expected = source_row['eval'][1]['expected']['post_data']
    for index, attempt in enumerate(attempts):
        correct = index != 1
        official = attempt['official_evaluator']
        require(official['score'] == (1.0 if correct else 0.0)
                and official['status'] == ('success' if correct else 'failure')
                and official['error_present'] is False, 'GitLab official evaluator mismatch')
        require(attempt['raw_and_sanitized_score_equal'] is True
                and attempt['auth_state_retained'] is False
                and attempt['raw_har_retained'] is False,
                'GitLab trace integrity or privacy gate failed')
        saved = attempt['db_readback']['milestone']
        require(saved['title'] == expected['milestone[title]']
                and saved['start_date'] == expected['milestone[start_date]']
                and saved['project_id'] == baseline['project_id'],
                'GitLab persisted milestone target did not bind to requested project')
        require((saved['due_date'] == expected['milestone[due_date]']) == correct,
                'GitLab near-miss due date did not discriminate independently')
        require(attempt['reset']['business_state_restored'] is True
                and attempt['reset']['baseline_sha256'] == baseline['business_sha256'],
                'GitLab per-attempt reset did not recover monitored baseline')
    return {
        'site': 'gitlab',
        'task_id': task_id,
        'published_hard_subset': True,
        'task_record_sha256': canonical_sha(source_row),
        'private_result_sha256': hashlib.sha256(raw).hexdigest(),
        'control': 'native_gui_positive_near_miss_positive_with_independent_postgresql_and_reset',
        'environment_seed_kind': 'minimal_synthetic_not_original_webarena_snapshot',
        'development_workflow_qualified': True,
        'official_final_task_admitted': False,
    }


def validate_magento_hard_shipment_rejection(forensic_path: Path, failure_path: Path,
                                             source_row: dict, hard_ids: set[int]) -> dict:
    """Preserve both task-499 failure modes without admitting sanitized-only 1.0."""
    raw_forensic, raw_failure = forensic_path.read_bytes(), failure_path.read_bytes()
    forensic, failure = json.loads(raw_forensic), json.loads(raw_failure)
    task_id = 499
    require(source_row['task_id'] == task_id and task_id in hard_ids
            and source_row['sites'] == ['shopping_admin'], 'Magento hard task identity drift')
    require(forensic['source']['git_commit'] == magento.SOURCE_COMMIT
            and forensic['source']['dataset_sha256'] == magento.SOURCE_SHA256
            and forensic['source']['task_record_sha256'] == canonical_sha(source_row),
            'Magento source receipt drift')
    require(forensic['container']['image_sha256'] == failure['container']['image_sha256'] == MAGENTO_IMAGE
            and forensic['container']['container_id_sha256'] != failure['container']['container_id_sha256'],
            'Magento positive/retry were not distinct pinned-image clones')
    require(forensic['target_track_matches_source'] is True
            and forensic['wrong_order_untouched'] is True
            and forensic['sanitized_score'] == 1.0,
            'Magento first GUI attempt did not save the target as observed')
    require(forensic['raw_and_sanitized_evaluator_disagreement_observed'] is True
            and forensic['raw_har_score'] == 'unknown_after_temporary_file_removed'
            and forensic['development_control_qualified'] is False,
            'Magento trace disagreement was incorrectly promoted')
    require(failure['target_shipment_count'] == 0
            and failure['comparator_shipment_count'] == 0
            and failure['search_probe_exit_code'] != 0
            and failure['official_scored_attempts'] == 0
            and failure['official_final_admitted'] is False,
            'Magento fresh-clone timeout/search failure was incorrectly scored')
    return {
        'site': 'shopping_admin',
        'task_id': task_id,
        'published_hard_subset': True,
        'task_record_sha256': canonical_sha(source_row),
        'private_forensic_sha256': hashlib.sha256(raw_forensic).hexdigest(),
        'private_failure_sha256': hashlib.sha256(raw_failure).hexdigest(),
        'control': 'native_gui_persisted_but_raw_trace_invalid_then_fresh_clone_search_failure',
        'environment_seed_kind': 'pinned_magento_image_disposable_clones',
        'development_workflow_qualified': False,
        'rejected_unscored_attempt': True,
        'official_final_task_admitted': False,
    }


def assess(source: Path, hard_file: Path, *, gitlab_milestone_result: Path | None = None,
           magento499_forensic: Path | None = None,
           magento499_failure: Path | None = None) -> dict:
    combined = matrix.build(source, hard_file)
    rows, hard_ids = gitlab.source_rows(source, hard_file)
    controls = []
    if gitlab_milestone_result is not None:
        row = next(item for item in rows if item['task_id'] == 590)
        controls.append(validate_gitlab_hard_milestone(gitlab_milestone_result, row, hard_ids))
    if (magento499_forensic is None) != (magento499_failure is None):
        raise ValueError('Magento hard-task rejection needs both original forensic and fresh-clone failure receipts')
    if magento499_forensic is not None and magento499_failure is not None:
        magento_rows, _ = magento.source_rows(source, hard_file)
        row = next(item for item in magento_rows if item['task_id'] == 499)
        controls.append(validate_magento_hard_shipment_rejection(
            magento499_forensic, magento499_failure, row, hard_ids))
    for control in controls:
        cell = combined['cells'][control['site']]
        control['in_provisional_final'] = any(item['task_id'] == control['task_id']
                                              for item in cell['candidate_gate_queue'])
    return {
        'schema': 'cua-saas-control-assessment-v1',
        'status': 'development_controls_only_no_sealed_final_admission',
        'source': combined['source'],
        'counts': {
            **combined['counts'],
            'development_workflows_qualified': sum(item['development_workflow_qualified'] for item in controls),
            'rejected_unscored_attempts': sum(item.get('rejected_unscored_attempt', False) for item in controls),
            'development_attempts_in_provisional_final': sum(item['in_provisional_final'] for item in controls),
        },
        'controls': controls,
        'pending_by_site': {
            site: {'provisional_final_candidates': cell['provisional_final_count'],
                   'official_final_admitted': 0,
                   'pending_gate_instances': len(cell['candidate_gate_queue'])}
            for site, cell in combined['cells'].items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--hard-ids', type=Path, required=True)
    parser.add_argument('--gitlab-milestone-result', type=Path)
    parser.add_argument('--magento499-forensic', type=Path)
    parser.add_argument('--magento499-failure', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.source, args.hard_ids,
                    gitlab_milestone_result=args.gitlab_milestone_result,
                    magento499_forensic=args.magento499_forensic,
                    magento499_failure=args.magento499_failure)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    args.out.chmod(0o600)
    print(json.dumps(result['counts'], sort_keys=True))


if __name__ == '__main__':
    main()
