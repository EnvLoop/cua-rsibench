"""A hard-task control needs raw scoring, persisted state, and exact reset."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import assess_saas_control_receipts_v1 as controls  # noqa: E402


def fixture() -> tuple[dict, dict]:
    expected = {'milestone[title]': 'release',
                'milestone[start_date]': '2026-10-01',
                'milestone[due_date]': '2026-10-15'}
    task = {'task_id': 590, 'sites': ['gitlab'],
            'eval': [{'evaluator': 'AgentResponseEvaluator'},
                     {'evaluator': 'NetworkEventEvaluator', 'expected': {'post_data': expected}}]}
    baseline = {'business_sha256': 'a' * 64, 'project_id': 8, 'milestones': []}
    attempts = []
    for index, due in enumerate(('2026-10-15', '2026-10-16', '2026-10-15')):
        correct = index != 1
        attempts.append({
            'official_evaluator': {'score': 1.0 if correct else 0.0,
                                   'status': 'success' if correct else 'failure',
                                   'error_present': False},
            'raw_and_sanitized_score_equal': True,
            'auth_state_retained': False,
            'raw_har_retained': False,
            'db_readback': {'milestone': {'title': 'release', 'start_date': '2026-10-01',
                                          'due_date': due, 'project_id': 8}},
            'reset': {'business_state_restored': True, 'baseline_sha256': 'a' * 64},
        })
    result = {
        'task_id': 590,
        'source': {'dataset_sha256': controls.gitlab.SOURCE_SHA256,
                   'git_commit': controls.gitlab.SOURCE_COMMIT,
                   'task_sha256': controls.canonical_sha(task)},
        'container': {'image_sha256': controls.GITLAB_IMAGE, 'loopback_port': 8013},
        'original_snapshot_seeded': False,
        'complete': True, 'model_calls': 0, 'hundred_task_ready': False,
        'qualified_task_count': 1, 'scores': [1.0, 0.0, 1.0],
        'business_baseline': baseline,
        'final_business_state': copy.deepcopy(baseline),
        'attempts': attempts,
    }
    return task, result


def check(task: dict, result: dict) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / 'receipt.json'
        path.write_text(json.dumps(result))
        return controls.validate_gitlab_hard_milestone(path, task, {590})


def magento_fixture() -> tuple[dict, dict, dict]:
    task = {'task_id': 499, 'sites': ['shopping_admin'], 'eval': []}
    forensic = {
        'source': {'git_commit': controls.magento.SOURCE_COMMIT,
                   'dataset_sha256': controls.magento.SOURCE_SHA256,
                   'task_record_sha256': controls.canonical_sha(task)},
        'container': {'image_sha256': controls.MAGENTO_IMAGE,
                      'container_id_sha256': 'a' * 64},
        'target_track_matches_source': True,
        'wrong_order_untouched': True,
        'sanitized_score': 1.0,
        'raw_and_sanitized_evaluator_disagreement_observed': True,
        'raw_har_score': 'unknown_after_temporary_file_removed',
        'development_control_qualified': False,
    }
    failure = {
        'container': {'image_sha256': controls.MAGENTO_IMAGE,
                      'container_id_sha256': 'b' * 64},
        'target_shipment_count': 0,
        'comparator_shipment_count': 0,
        'search_probe_exit_code': 7,
        'official_scored_attempts': 0,
        'official_final_admitted': False,
    }
    return task, forensic, failure


def check_magento(task: dict, forensic: dict, failure: dict) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        first, second = Path(temporary) / 'forensic.json', Path(temporary) / 'failure.json'
        first.write_text(json.dumps(forensic))
        second.write_text(json.dumps(failure))
        return controls.validate_magento_hard_shipment_rejection(first, second, task, {499})


class SaaSControlReceiptTests(unittest.TestCase):
    def test_real_shape_stays_development_only(self):
        task, result = fixture()
        assessment = check(task, result)
        self.assertTrue(assessment['development_workflow_qualified'])
        self.assertFalse(assessment['official_final_task_admitted'])
        self.assertEqual(assessment['environment_seed_kind'],
                         'minimal_synthetic_not_original_webarena_snapshot')

    def test_network_score_without_independent_wrong_date_is_rejected(self):
        task, result = fixture()
        result['attempts'][1]['db_readback']['milestone']['due_date'] = '2026-10-15'
        with self.assertRaisesRegex(ValueError, 'near-miss due date'):
            check(task, result)

    def test_raw_redacted_disagreement_or_reset_drift_is_rejected(self):
        task, result = fixture()
        result['attempts'][0]['raw_and_sanitized_score_equal'] = False
        with self.assertRaisesRegex(ValueError, 'trace integrity'):
            check(task, result)
        task, result = fixture()
        result['attempts'][2]['reset']['baseline_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'per-attempt reset'):
            check(task, result)

    def test_source_record_hash_drift_is_rejected(self):
        task, result = fixture()
        result['source']['task_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'source receipt drift'):
            check(task, result)

    def test_magento_sanitized_only_one_is_rejected_unscored(self):
        task, forensic, failure = magento_fixture()
        assessment = check_magento(task, forensic, failure)
        self.assertFalse(assessment['development_workflow_qualified'])
        self.assertTrue(assessment['rejected_unscored_attempt'])
        self.assertFalse(assessment['official_final_task_admitted'])

    def test_magento_same_clone_or_false_raw_agreement_is_rejected(self):
        task, forensic, failure = magento_fixture()
        failure['container']['container_id_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'distinct pinned-image clones'):
            check_magento(task, forensic, failure)
        task, forensic, failure = magento_fixture()
        forensic['raw_and_sanitized_evaluator_disagreement_observed'] = False
        with self.assertRaisesRegex(ValueError, 'incorrectly promoted'):
            check_magento(task, forensic, failure)


if __name__ == '__main__':
    unittest.main()
