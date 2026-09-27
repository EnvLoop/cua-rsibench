"""Publication requires full attempt telemetry and independent cell review."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_publication_v1 as publication  # noqa: E402
from cursibench import full_study_results_v1 as results  # noqa: E402
from cursibench import scale_final_v06 as evidence  # noqa: E402
import test_full_study_results_v1 as fixture_module  # noqa: E402


def sha(value: str) -> str:
    return evidence.digest(value.encode())


class PublicationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix='cua-paper-gate-test-')
        cls.root = Path(cls.temp.name)
        fixture_module.FullStudyResultAuditTests.root = cls.root
        cls.plan, cls.index = fixture_module.FullStudyResultAuditTests.make_fixture()
        cls.plan_sha = evidence.digest(evidence.json_bytes(cls.plan))
        cls.index['matrix_plan_sha256'] = cls.plan_sha
        cls.summary = results.audit(cls.plan, cls.index, cls.root,
                                    plan_sha256=cls.plan_sha,
                                    bootstrap_replicates=100)
        cls.telemetry = cls.make_telemetry()
        cls.trajectory = cls.make_trajectory()
        cls.review = cls.make_review()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    @classmethod
    def ref(cls, name: str, value: dict) -> dict:
        path = cls.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = evidence.json_bytes(value)
        path.write_bytes(raw)
        return {'path': name, 'sha256': evidence.digest(raw)}

    @classmethod
    def make_telemetry(cls) -> dict:
        entries = []
        for row in cls.index['final_executions']:
            cell_id, owner = row['cell_id'], row['owner_slot']
            execution = publication.read_reference(cls.root, row['receipt'],
                                                   'fixture execution')
            tasks = []
            for task in execution['tasks']:
                attempts = []
                for attempt in task['attempts']:
                    attempts.append({
                        'attempt_id': attempt['attempt_id'],
                        'attempt_receipt_sha256': attempt['receipt_sha256'],
                        'timeout_subtype': 'none',
                        'action_count': 2, 'wall_time_ms': 500,
                        'provider_latency_ms': 250,
                        'telemetry_trace_sha256': sha('raw-telemetry-' +
                                                       task['task_id'] + owner),
                        'retry_provenance': None,
                    })
                tasks.append({'task_id': task['task_id'], 'attempts': attempts})
            receipt = {
                'schema': publication.EXECUTION_TELEMETRY_SCHEMA,
                'cell_id': cell_id, 'owner_slot': owner,
                'execution_receipt_sha256': row['receipt']['sha256'],
                'tasks': tasks,
            }
            entries.append({'cell_id': cell_id, 'owner_slot': owner,
                            'receipt': cls.ref(f'telemetry/{cell_id}-{owner}.json',
                                               receipt)})
        return {
            'schema': publication.TELEMETRY_SCHEMA,
            'study_id': cls.plan['study_id'],
            'matrix_plan_sha256': cls.plan_sha,
            'execution_index_sha256': cls.summary['execution_index_sha256'],
            'executions': entries,
        }

    @classmethod
    def make_review(cls) -> dict:
        entries = []
        for cell_id in matrix.CELLS:
            receipt = {
                'schema': publication.CELL_REVIEW_SCHEMA,
                'cell_id': cell_id, 'study_id': cls.plan['study_id'],
                'matrix_plan_sha256': cls.plan_sha,
                'execution_index_sha256': cls.summary['execution_index_sha256'],
                'reviewer_id': 'synthetic-fixture-reviewer',
                'reviewed_at_utc': '2026-09-27T00:00:00+00:00',
                'checked_final_task_count': 100,
                'evidence_bundle_sha256': sha(cell_id + ':fixture-evidence'),
                'method_notes': 'Synthetic test receipt, never publish.',
                'passed': True,
                'source_rights_checked': True,
                'hidden_split_checked': True,
                'gui_trace_and_saved_state_readback_checked': True,
                'reset_and_negative_controls_checked': True,
                'evaluator_independent_of_actor': True,
            }
            entries.append({'cell_id': cell_id,
                            'receipt': cls.ref(f'reviews/{cell_id}.json', receipt)})
        return {
            'schema': publication.REVIEW_SCHEMA,
            'study_id': cls.plan['study_id'],
            'matrix_plan_sha256': cls.plan_sha,
            'execution_index_sha256': cls.summary['execution_index_sha256'],
            'cells': entries,
        }

    @classmethod
    def make_trajectory(cls) -> dict:
        entries = []
        for campaign in cls.index['campaigns']:
            cell_id, researcher = campaign['cell_id'], campaign['researcher_id']
            freeze = publication.read_reference(cls.root,
                                                campaign['selection_freeze'],
                                                'fixture freeze')
            receipt = {
                'schema': publication.CAMPAIGN_TRAJECTORY_SCHEMA,
                'study_id': cls.plan['study_id'],
                'cell_id': cell_id, 'researcher_id': researcher,
                'selection_freeze_receipt_sha256':
                    campaign['selection_freeze']['sha256'],
                'usage_receipt_sha256': campaign['usage']['sha256'],
                'training_lineage_sha256': freeze['training_lineage_sha256'],
                'selection_results_bundle_sha256':
                    freeze['selection_results_sha256'],
                'base_selection_wins': 0,
                'base_selection_results_sha256': sha(cell_id + ':base-selection'),
                'rounds': [{
                    'round_index': 1, 'started_at': 200, 'finished_at': 900,
                    'candidate_submitted': True,
                    'hypothesis_sha256': sha(cell_id + researcher + ':hypothesis'),
                    'training_data_sha256': sha(cell_id + researcher + ':data'),
                    'training_receipt_sha256': sha(cell_id + researcher + ':train'),
                    'training_base_checkpoint_sha256':
                        freeze['base_checkpoint_sha256'],
                    'checkpoint_sha256': freeze['selected_checkpoint_sha256'],
                    'selection_attempts': [{
                        'attempt_id': 'selection-initial', 'status': 'scored',
                        'score_wins': 1, 'task_count': 20,
                        'result_receipt_sha256': sha(cell_id + researcher + ':select'),
                        'failure_type': None,
                        'started_at': 800, 'finished_at': 850,
                        'retry_rule_sha256': None,
                    }],
                    'regressions_vs_incumbent': 0,
                    'promotion_decision': 'promoted',
                    'incumbent_after_checkpoint_sha256':
                        freeze['selected_checkpoint_sha256'],
                    'cost_usd': '1', 'cost_basis': 'published_rate_nominal',
                    'failure_type': None,
                }],
            }
            entries.append({
                'cell_id': cell_id, 'researcher_id': researcher,
                'receipt': cls.ref(f'trajectory/{cell_id}-{researcher}.json',
                                   receipt),
            })
        return {
            'schema': publication.TRAJECTORY_SCHEMA,
            'study_id': cls.plan['study_id'],
            'matrix_plan_sha256': cls.plan_sha,
            'execution_index_sha256': cls.summary['execution_index_sha256'],
            'campaigns': entries,
        }

    def test_complete_fixture_covers_every_unique_execution_and_attempt(self):
        report = publication._telemetry_bundle(
            self.telemetry, self.root, self.index, self.root, self.summary)
        self.assertEqual((report['execution_count'], report['task_count'],
                          report['attempt_count'], report['retry_count']),
                         (30, 3000, 3000, 0))
        self.assertEqual(report['timeout_counts']['none'], 3000)
        self.assertEqual(publication._review_bundle(self.review, self.root,
                                                      self.summary)['cell_count'], 6)
        trajectory = publication._trajectory_bundle(
            self.trajectory, self.root, self.index, self.root, self.summary)
        self.assertEqual((trajectory['campaign_count'], trajectory['round_count'],
                          trajectory['scored_round_count']), (24, 24, 24))

    def test_missing_execution_or_attempt_fails_closed(self):
        bad = copy.deepcopy(self.telemetry)
        bad['executions'].pop()
        with self.assertRaisesRegex(ValueError, 'every unique checkpoint'):
            publication._telemetry_bundle(bad, self.root, self.index,
                                          self.root, self.summary)
        bad = copy.deepcopy(self.telemetry)
        receipt_ref = bad['executions'][0]['receipt']
        receipt = publication.read_reference(self.root, receipt_ref, 'fixture')
        receipt['tasks'][0]['attempts'].clear()
        receipt_ref = self.ref('tampered/missing-attempt.json', receipt)
        bad['executions'][0]['receipt'] = receipt_ref
        with self.assertRaisesRegex(ValueError, 'attempt telemetry incomplete'):
            publication._telemetry_bundle(bad, self.root, self.index,
                                          self.root, self.summary)

    def test_false_timeout_class_and_missing_review_fail_closed(self):
        bad = copy.deepcopy(self.telemetry)
        receipt = publication.read_reference(self.root,
                                            bad['executions'][0]['receipt'],
                                            'fixture')
        receipt['tasks'][0]['attempts'][0]['timeout_subtype'] = 'provider'
        bad['executions'][0]['receipt'] = self.ref('tampered/wrong-timeout.json',
                                                 receipt)
        with self.assertRaisesRegex(ValueError, 'infrastructure timeout'):
            publication._telemetry_bundle(bad, self.root, self.index,
                                          self.root, self.summary)
        bad_review = copy.deepcopy(self.review)
        bad_review['cells'].pop()
        with self.assertRaisesRegex(ValueError, 'six independent'):
            publication._review_bundle(bad_review, self.root, self.summary)

    def test_retry_must_bind_preserved_first_attempt_and_rule(self):
        first = {'attempt_id': 'initial', 'status': 'invalid', 'score': None,
                 'failure_type': 'transport', 'started_at': 1,
                 'finished_at': 2, 'receipt_sha256': sha('first')}
        second = {'attempt_id': 'recovery', 'status': 'scored', 'score': 1,
                  'failure_type': None, 'started_at': 3,
                  'finished_at': 4, 'receipt_sha256': sha('second')}
        metric = {'attempt_id': 'recovery', 'attempt_receipt_sha256': sha('second'),
                  'timeout_subtype': 'none', 'action_count': 4,
                  'wall_time_ms': 500, 'provider_latency_ms': 200,
                  'telemetry_trace_sha256': sha('trace'),
                  'retry_provenance': {
                      'prior_attempt_id': 'initial',
                      'prior_attempt_receipt_sha256': sha('first'),
                      'retry_rule_sha256': sha('rule'),
                  }}
        self.assertEqual(publication._attempt_telemetry(
            metric, second, first, cell_id='gitlab', owner='sol6',
            task_id='one')['action_count'], 4)
        bad = copy.deepcopy(metric)
        bad['retry_provenance']['prior_attempt_receipt_sha256'] = sha('wrong')
        with self.assertRaisesRegex(ValueError, 'retry does not bind'):
            publication._attempt_telemetry(bad, second, first,
                                           cell_id='gitlab', owner='sol6',
                                           task_id='one')

    def test_missing_trajectory_or_illegal_promotion_fails_closed(self):
        missing = copy.deepcopy(self.trajectory)
        missing['campaigns'].pop()
        with self.assertRaisesRegex(ValueError, '24 campaign trajectories'):
            publication._trajectory_bundle(missing, self.root, self.index,
                                           self.root, self.summary)
        bad = copy.deepcopy(self.trajectory)
        receipt = publication.read_reference(self.root,
                                            bad['campaigns'][0]['receipt'],
                                            'fixture trajectory')
        receipt['rounds'][0]['regressions_vs_incumbent'] = 1
        bad['campaigns'][0]['receipt'] = self.ref('tampered/illegal-promotion.json',
                                                receipt)
        with self.assertRaisesRegex(ValueError, 'strict gain/no regression'):
            publication._trajectory_bundle(bad, self.root, self.index,
                                           self.root, self.summary)
        wrong_base = copy.deepcopy(self.trajectory)
        receipt = publication.read_reference(
            self.root, wrong_base['campaigns'][0]['receipt'], 'fixture trajectory')
        receipt['rounds'][0]['training_base_checkpoint_sha256'] = sha('prior-adapter')
        wrong_base['campaigns'][0]['receipt'] = self.ref(
            'tampered/wrong-training-base.json', receipt)
        with self.assertRaisesRegex(ValueError, 'data or fixed base'):
            publication._trajectory_bundle(wrong_base, self.root, self.index,
                                           self.root, self.summary)

    def test_first_to_best_and_post_peak_decline_are_distinct(self):
        metrics = publication._search_metrics([
            {'round': 1, 'wins': 4},
            {'round': 3, 'wins': 9},
            {'round': 5, 'wins': 6},
        ])
        self.assertEqual((metrics['first_valid_wins'],
                          metrics['best_valid_wins'],
                          metrics['last_valid_wins'],
                          metrics['best_valid_round'],
                          metrics['declining_valid_transitions']),
                         (4, 9, 6, 3, 1))
        self.assertTrue(metrics['improved_over_first_valid'])
        self.assertTrue(metrics['last_below_peak_after_search'])

    def test_publication_loader_rejects_synthetic_and_tampered_summary(self):
        matrix_path = self.root / 'dummy-matrix.json'
        matrix_path.write_text('{}')
        index_path = self.root / 'synthetic-index.json'
        index_path.write_bytes(evidence.json_bytes(self.index))
        summary_path = self.root / 'synthetic-summary.json'
        summary_path.write_bytes(evidence.json_bytes(self.summary))
        telemetry_path = self.root / 'synthetic-telemetry.json'
        telemetry_path.write_bytes(evidence.json_bytes(self.telemetry))
        review_path = self.root / 'synthetic-review.json'
        review_path.write_bytes(evidence.json_bytes(self.review))
        trajectory_path = self.root / 'synthetic-trajectories.json'
        trajectory_path.write_bytes(evidence.json_bytes(self.trajectory))
        args = dict(matrix_manifest=matrix_path, execution_index=index_path,
                    audited_summary=summary_path, telemetry_index=telemetry_path,
                    independent_review=review_path,
                    trajectory_index=trajectory_path)
        with patch.object(publication.matrix, 'build', return_value=self.plan), \
             patch.object(publication.results, 'audit', return_value=self.summary):
            with self.assertRaisesRegex(ValueError, 'full preregistered result'):
                publication.load_publication_data(**args)
            changed = copy.deepcopy(self.summary)
            changed['campaign_count'] = 23
            summary_path.write_bytes(evidence.json_bytes(changed))
            with self.assertRaisesRegex(ValueError, 'differs from a fresh'):
                publication.load_publication_data(**args)


if __name__ == '__main__':
    unittest.main()
