"""A publication result needs all campaigns, task outcomes, and invalid attempts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_results_v1 as results  # noqa: E402
from cursibench import scale_final_v06 as cell_final  # noqa: E402


def sha(value: str) -> str:
    return cell_final.digest(value.encode())


class FullStudyResultAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix='cua-full-results-test-')
        cls.root = Path(cls.temp.name)
        cls.plan, cls.index = cls.make_fixture()
        cls.plan_sha = cell_final.digest(cell_final.json_bytes(cls.plan))
        cls.index['matrix_plan_sha256'] = cls.plan_sha

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    @classmethod
    def ref(cls, name: str, content: dict) -> dict:
        path = cls.root / 'receipts' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = cell_final.json_bytes(content)
        path.write_bytes(raw)
        return {'path': path.relative_to(cls.root).as_posix(),
                'sha256': cell_final.digest(raw)}

    @classmethod
    def make_fixture(cls) -> tuple[dict, dict]:
        cells = []
        campaigns = []
        executions = []
        for cell_id in matrix.CELLS:
            tasks = [{'task_id': f'{cell_id}-final-{i:03d}',
                      'package_sha256': sha(f'{cell_id}:{i}')}
                     for i in range(100)]
            chunks = [{'tasks': tasks[i:i+3]} for i in range(0, 100, 3)]
            base_checkpoint = sha(f'{cell_id}:base')
            selected = {rid: {'bindings': {'checkpoint': sha(f'{cell_id}:{rid}')},
                              'declared_all_in_cost_upper_bound_usd': '100'}
                        for rid in matrix.RESEARCHERS}
            cell = {
                'cell_id': cell_id,
                'base': {'bindings': {'checkpoint': base_checkpoint},
                         'chunks': chunks,
                         'declared_all_in_cost_upper_bound_usd': '100'},
                'researcher_plans': selected,
                'analysis_family_by_task': {
                    row['task_id']: f'{cell_id}-source-{i//10:02d}'
                    for i, row in enumerate(tasks)},
                'execution_evidence_owner_by_slot': {
                    'shared-base': 'shared-base',
                    **{rid: rid for rid in matrix.RESEARCHERS}},
            }
            cells.append(cell)
            for rid in matrix.RESEARCHERS:
                freeze = {
                    'schema': 'cua-full-study-selection-freeze-v1',
                    'cell_id': cell_id, 'researcher_id': rid,
                    'base_checkpoint_sha256': base_checkpoint,
                    'selected_checkpoint_sha256': selected[rid]['bindings']['checkpoint'],
                    'training_lineage_sha256': sha(f'{cell_id}:{rid}:training'),
                    'selection_results_sha256': sha(f'{cell_id}:{rid}:selection'),
                    'campaign_started_at': 100,
                    'selection_frozen_at': 1000,
                    'campaign_finished_at': 1000,
                    'candidate_count': 1, 'selection_evaluations': 1,
                }
                usage = {
                    'schema': 'cua-full-study-campaign-usage-v1',
                    'cell_id': cell_id, 'researcher_id': rid,
                    'cost_basis': 'published_rate_nominal',
                    'tinker_nominal_usd': '10',
                    'researcher_inference_usd': '2',
                    'teacher_rollout_usd': '1', 'e2b_usd': '1',
                    'storage_application_usd': '0',
                    'selected_final_usd': '3', 'all_in_usd': '17',
                    'researcher_calls': 1,
                    'teacher_rollout_tokens': 1000,
                    'teacher_rollout_calls': 1,
                    'e2b_sandbox_hours': '0.5',
                    'e2b_peak_concurrency': 1,
                    'candidate_submissions': 1,
                    'selection_evaluations': 1,
                    'provider_invoice_usd': None,
                    'failure_counts': {kind: 0 for kind in results.FAILURE_TYPES},
                }
                campaigns.append({
                    'cell_id': cell_id, 'researcher_id': rid, 'status': 'complete',
                    'selection_freeze': cls.ref(f'{cell_id}-{rid}-freeze.json', freeze),
                    'usage': cls.ref(f'{cell_id}-{rid}-usage.json', usage),
                })
            for owner in ('shared-base', *matrix.RESEARCHERS):
                checkpoint = base_checkpoint if owner == 'shared-base' else selected[owner]['bindings']['checkpoint']
                task_results = []
                for i, row in enumerate(tasks):
                    task, package = row['task_id'], row['package_sha256']
                    score = 0 if owner == 'shared-base' else int(i < 10)
                    task_results.append({
                        'task_id': task, 'package_sha256': package, 'score': score,
                        'saved_state_sha256': sha(task + ':state:' + owner),
                        'verifier_receipt_sha256': sha(task + ':verifier:' + owner),
                        'reset_receipt_sha256': sha(task + ':reset:' + owner),
                        'observation_trace_sha256': sha(task + ':observation:' + owner),
                        'action_trace_sha256': sha(task + ':action:' + owner),
                        'attempts': [{
                            'attempt_id': 'initial', 'status': 'scored',
                            'score': score, 'failure_type': None,
                            'started_at': 3001, 'finished_at': 3002,
                            'receipt_sha256': sha(task + ':attempt:' + owner),
                        }],
                    })
                receipt = {
                    'schema': 'cua-full-study-final-execution-v1',
                    'cell_id': cell_id, 'owner_slot': owner,
                    'checkpoint_sha256': checkpoint,
                    'status': 'complete', 'started_at': 3000,
                    'finished_at': 4000, 'cost_basis': 'published_rate_nominal',
                    'cost_usd': '2' if owner == 'shared-base' else '3',
                    'tasks': task_results,
                }
                executions.append({
                    'cell_id': cell_id, 'owner_slot': owner,
                    'receipt': cls.ref(f'{cell_id}-{owner}-final.json', receipt),
                })
        plan = {
            'schema': matrix.PLAN_SCHEMA, 'study_id': 'synthetic-validator-fixture',
            'cell_ids': list(matrix.CELLS), 'campaign_count': 24,
            'distinct_official_task_identities': 600,
            'initial_total_slot_task_results': 3000,
            'scores_present': False,
            'cells': cells,
            'tinker_usd_cap_per_campaign': '500',
            'researcher_inference_usd_cap_per_campaign': '100',
            'teacher_rollout_usd_cap_per_campaign': '25',
            'e2b_usd_cap_per_campaign': '20',
            'storage_application_usd_cap_per_campaign': '5',
            'e2b_sandbox_hours_cap_per_campaign': '20',
            'per_campaign_all_in_ceiling_usd': '750',
            'declared_all_in_cost_upper_bound_usd': '18600',
            'matched_non_tinker_campaign_caps': {
                'researcher_calls_per_campaign': 1000,
                'teacher_rollout_tokens_per_campaign': 1000000,
                'teacher_rollout_calls_per_campaign': 1000,
                'e2b_peak_concurrency': 3,
                'candidate_submissions_per_campaign': 25,
                'selection_evaluations_per_campaign': 25,
            },
        }
        index = {'schema': results.SCHEMA, 'study_id': plan['study_id'],
                 'matrix_plan_sha256': '', 'campaigns': campaigns,
                 'final_executions': executions}
        return plan, index

    def test_complete_index_produces_24_paired_comparisons(self):
        report = results.audit(self.plan, self.index, self.root,
                               plan_sha256=self.plan_sha,
                               bootstrap_replicates=100)
        self.assertEqual((report['campaign_count'],
                          report['distinct_final_task_identities'],
                          report['slot_task_result_count']), (24, 600, 3000))
        self.assertEqual(len(report['comparisons']), 24)
        self.assertEqual(report['comparisons'][0]['summary']['paired_delta_pp'], 10)
        self.assertEqual(report['reported_all_in_cost_subtotal_usd'], '420')
        self.assertEqual(report['cost_bases_present'], ['published_rate_nominal'])
        self.assertFalse(report['provider_invoice_complete'])

    def test_missing_result_or_pre_freeze_execution_is_rejected(self):
        bad = copy.deepcopy(self.index)
        bad['final_executions'].pop()
        with self.assertRaisesRegex(ValueError, 'execution count differs'):
            results.audit(self.plan, bad, self.root, plan_sha256=self.plan_sha,
                          bootstrap_replicates=100)
        bad = copy.deepcopy(self.index)
        ref = bad['final_executions'][0]['receipt']
        path = self.root / ref['path']
        original = path.read_bytes()
        try:
            receipt = json.loads(original)
            receipt['started_at'] = 999
            path.write_bytes(cell_final.json_bytes(receipt))
            ref['sha256'] = cell_final.digest(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'timing invalid'):
                results.audit(self.plan, bad, self.root,
                              plan_sha256=self.plan_sha,
                              bootstrap_replicates=100)
        finally:
            path.write_bytes(original)

    def test_infrastructure_invalid_attempt_cannot_be_encoded_as_model_zero(self):
        bad = copy.deepcopy(self.index)
        ref = bad['final_executions'][0]['receipt']
        path = self.root / ref['path']
        original = path.read_bytes()
        try:
            receipt = json.loads(original)
            attempt = receipt['tasks'][0]['attempts'][0]
            attempt.update(status='invalid', score=None, failure_type='transport')
            path.write_bytes(cell_final.json_bytes(receipt))
            ref['sha256'] = cell_final.digest(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'final attempt must be a valid scored'):
                results.audit(self.plan, bad, self.root,
                              plan_sha256=self.plan_sha,
                              bootstrap_replicates=100)
        finally:
            path.write_bytes(original)

    def test_controlled_recovery_retains_invalid_attempt_as_separate_failure(self):
        changed = copy.deepcopy(self.index)
        ref = changed['final_executions'][0]['receipt']
        path = self.root / ref['path']
        original = path.read_bytes()
        try:
            receipt = json.loads(original)
            task = receipt['tasks'][0]
            task['attempts'].insert(0, {
                'attempt_id': 'transport-first', 'status': 'invalid',
                'score': None, 'failure_type': 'transport',
                'started_at': 3000, 'finished_at': 3001,
                'receipt_sha256': sha('transport-receipt'),
            })
            path.write_bytes(cell_final.json_bytes(receipt))
            ref['sha256'] = cell_final.digest(path.read_bytes())
            report = results.audit(self.plan, changed, self.root,
                                   plan_sha256=self.plan_sha,
                                   bootstrap_replicates=100)
            self.assertEqual(report['infrastructure_invalid_attempts_by_type']['transport'], 1)
            self.assertEqual(report['slot_task_result_count'], 3000)
        finally:
            path.write_bytes(original)

    def test_selected_base_checkpoint_reuses_one_execution_without_losing_slot_result(self):
        plan = copy.deepcopy(self.plan)
        index = copy.deepcopy(self.index)
        cell_id = matrix.CELLS[0]
        cell = plan['cells'][0]
        base_checkpoint = cell['base']['bindings']['checkpoint']
        cell['researcher_plans']['luna6']['bindings']['checkpoint'] = base_checkpoint
        cell['execution_evidence_owner_by_slot']['luna6'] = 'shared-base'
        index['final_executions'] = [row for row in index['final_executions']
                                     if (row['cell_id'], row['owner_slot']) !=
                                     (cell_id, 'luna6')]
        campaign = next(row for row in index['campaigns']
                        if (row['cell_id'], row['researcher_id']) ==
                        (cell_id, 'luna6'))
        freeze_ref, usage_ref = campaign['selection_freeze'], campaign['usage']
        freeze_path = self.root / freeze_ref['path']
        usage_path = self.root / usage_ref['path']
        old_freeze, old_usage = freeze_path.read_bytes(), usage_path.read_bytes()
        try:
            freeze = json.loads(old_freeze)
            freeze['selected_checkpoint_sha256'] = base_checkpoint
            freeze_path.write_bytes(cell_final.json_bytes(freeze))
            freeze_ref['sha256'] = cell_final.digest(freeze_path.read_bytes())
            usage = json.loads(old_usage)
            usage['selected_final_usd'] = '0'
            usage['all_in_usd'] = '14'
            usage_path.write_bytes(cell_final.json_bytes(usage))
            usage_ref['sha256'] = cell_final.digest(usage_path.read_bytes())
            plan_sha = cell_final.digest(cell_final.json_bytes(plan))
            index['matrix_plan_sha256'] = plan_sha
            report = results.audit(plan, index, self.root,
                                   plan_sha256=plan_sha,
                                   bootstrap_replicates=100)
            self.assertEqual(report['slot_task_result_count'], 3000)
            self.assertEqual(report['unique_checkpoint_task_executions'], 2900)
            self.assertEqual(report['reported_all_in_cost_subtotal_usd'], '417')
            reused = next(row for row in report['comparisons']
                          if (row['cell_id'], row['researcher_id']) ==
                          (cell_id, 'luna6'))
            self.assertEqual(reused['summary']['paired_delta_pp'], 0)
        finally:
            freeze_path.write_bytes(old_freeze)
            usage_path.write_bytes(old_usage)


if __name__ == '__main__':
    unittest.main()
