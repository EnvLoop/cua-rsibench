"""Offline 20-task PowerPoint selection paid coverage and live gate."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cursibench.full_study_selection_paid_coverage_v1 import validate
from cursibench.scale_action_contract import make_observation
from cursibench import scale_action_output_v066
from tests.test_office_web_excel_selection_worker_v1 import (
    FakeSampler, FakeSession, sha,
)
from tests.test_office_web_ppt_teacher_worker_v1 import (
    png, pptx, write_private,
)
from tools import office_web_ppt_selection_worker_v1 as worker


class PptFakeSession(FakeSession):
    def __init__(self, repo, roster, checkpoint):
        super().__init__(repo, roster, checkpoint)
        self.intent['cell_id'] = 'powerpoint-web'
        self.attempt = 'ppt-selection-a1'

    def record_selection_scored(self, *, attempt_id, result,
                                paid_attempt_ids):
        self.scored = validate(
            cell_id='powerpoint-web', attempt_id=attempt_id,
            checkpoint_sha256=sha(self.checkpoint),
            selection_tasks=list(self.views['selection']),
            selection_identities_sha256=sha(worker._canonical(
                list(self.views['selection']))),
            paid_calls=[row for row in self.paid_calls if
                        row['attempt_id'] in paid_attempt_ids],
            related_paid_attempt_ids={row['attempt_id'] for row in
                                      self.paid_calls})
        self.scored['result'] = result
        return self.scored


class FakePptTaskWorker:
    def __init__(self, path: Path, *, reset_drift=False):
        self.binding = json.loads(path.read_bytes())
        self.reset_drift = reset_drift

    def _binding(self, task):
        if (self.binding['task_id'] != task['task_id'] or
                self.binding['workflow'] not in
                {'nominal_output_growth', 'per_capita_growth',
                 'inflation_acceleration', 'labor_rate_change',
                 'population_growth', 'output_per_person_divergence',
                 'price_labor_spread', 'dual_threshold_review'}):
            raise worker.PptSelectionError(
                'unsupported_wdi_selection_workflow')
        return self.binding, None, None, None

    def run_task(self, *, task, out_dir, sample_student, dispatch_e2b):
        def lease(request):
            return {'created': True,
                    'sandbox_id': task['task_id'] + '-' + request['phase']}
        actor = dispatch_e2b(
            lease_seconds=300, reserve_usd='1',
            provider=lease, phase='actor')
        observation = make_observation(
            task_id=task['task_id'],
            task_binding_sha256=task['package_sha256'],
            instruction=task['visible_instruction'],
            step=0, screenshot_bytes=png())
        write_private(out_dir / 'frames' / 'step-000.png',
                      observation.screenshot_bytes)
        sample = sample_student(observation)
        action = scale_action_output_v066.normalize_model_action(
            sample['text'], observation,
            current_frame_id=observation.frame_id)
        if action['type'] != 'finish':
            raise AssertionError('fake sampler did not finish')
        reset = dispatch_e2b(
            lease_seconds=300, reserve_usd='1',
            provider=lease, phase='reset')
        if self.reset_drift:
            raise worker.PptSelectionError('fresh_copy_reset_changed')
        saved = out_dir / 'artifacts' / 'saved-graph'
        saved_bytes = pptx(task['task_id'])
        write_private(saved / 'first.private.pptx', saved_bytes)
        write_private(saved / 'second.private.pptx', saved_bytes)
        saved_sha = sha(saved_bytes)
        verifier = {
            'schema': 'cua-office-ppt-selection-verifier-v1',
            'task_id': task['task_id'], 'score': 0,
            'saved_state_sha256': saved_sha,
        }
        reset_receipt = {
            'schema': 'cua-office-ppt-selection-reset-v1',
            'task_id': task['task_id'], 'fresh_sandbox': True,
        }
        write_private(out_dir / 'verifier.private.json',
                      worker._canonical(verifier))
        write_private(out_dir / 'reset.private.json',
                      worker._canonical(reset_receipt))
        receipt = {
            'schema': worker.TASK_SCHEMA,
            'task_id': task['task_id'],
            'package_sha256': task['package_sha256'],
            'worker_runtime_sha256': worker.runtime_sha256(),
            'score': 0,
            'saved_state_sha256': saved_sha,
            'verifier_receipt_sha256': sha(
                (out_dir / 'verifier.private.json').read_bytes()),
            'reset_receipt_sha256': sha(
                (out_dir / 'reset.private.json').read_bytes()),
            'sample_paid_attempt_ids': [sample['paid_attempt_id']],
            'e2b_paid_attempt_ids': [actor['attempt_id'],
                                     reset['attempt_id']],
        }
        path = out_dir / 'task-receipt.private.json'
        write_private(path, worker._canonical(receipt))
        row = {key: receipt[key] for key in (
            'task_id', 'package_sha256', 'score',
            'saved_state_sha256', 'verifier_receipt_sha256',
            'reset_receipt_sha256')}
        return {'task_receipt_path': str(path),
                'task_receipt_sha256': sha(path.read_bytes()),
                'result_row': row,
                'paid_attempt_ids':
                    receipt['sample_paid_attempt_ids'] +
                    receipt['e2b_paid_attempt_ids']}


class PptSelectionBatchTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()
        (self.repo / 'work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=self.repo / 'work', prefix='ppt-selection-batch-test-')
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)
        self.roster = [{'task_id': f'ppt-wdi-{index:016x}',
                        'package_sha256': sha(f'package-{index}')}
                       for index in range(20)]
        self.checkpoint = 'tinker://example/sampler_weights/ppt-selection'
        self.session = PptFakeSession(self.repo, self.roster,
                                      self.checkpoint)
        self.started = {
            'attempt_id': self.session.attempt,
            'checkpoint_path_sha256': sha(self.checkpoint),
            'selection_tasks': self.roster,
            'selection_identities_sha256':
                sha(worker._canonical(self.roster)),
            'task_count': 20,
        }
        entries = []
        workflows = ('nominal_output_growth', 'per_capita_growth',
                     'inflation_acceleration', 'labor_rate_change',
                     'population_growth',
                     'output_per_person_divergence',
                     'price_labor_spread', 'dual_threshold_review')
        for index, row in enumerate(self.roster):
            path = self.private / 'bindings' / \
                (row['task_id'] + '.private.json')
            write_private(path, worker._canonical({
                'task_id': row['task_id'],
                'visible_instruction': 'Repair the WDI seven-slide brief.',
                'workflow': workflows[index % 8],
                'lease_seconds': 300,
            }))
            entries.append({**row, 'binding_path': str(path),
                            'binding_sha256': sha(path.read_bytes())})
        self.manifest_path = self.private / 'manifest.private.json'
        write_private(self.manifest_path, worker._canonical({
            'schema': worker.BATCH_SCHEMA,
            'cell_id': 'powerpoint-web', 'split': 'selection',
            'selection_attempt': self.session.attempt,
            'selection_identities_sha256':
                sha(worker._canonical(self.roster)),
            'checkpoint_path_sha256': sha(self.checkpoint),
            'worker_runtime_sha256': worker.runtime_sha256(),
            'tasks': entries,
        }))
        self.sampler = FakeSampler(self.checkpoint)

    def batch(self, *, gate=None, reset_drift=False):
        return worker.PptSelectionBatch(
            self.session, self.started, self.checkpoint,
            self.manifest_path, self.private / 'result',
            task_worker_factory=lambda path: FakePptTaskWorker(
                path, reset_drift=reset_drift),
            sampler_factory=lambda _config: self.sampler,
            selection_graph_gate=gate)

    def test_twenty_task_paid_qwen_and_e2b_coverage(self):
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            result = self.batch(gate=lambda _bindings: None).run()
        self.assertEqual(len(result['result']['tasks']), 20)
        self.assertEqual(self.session.scored['sample_paid_attempt_count'], 20)
        self.assertEqual(
            self.session.scored['environment_paid_attempt_count'], 40)
        self.assertEqual(self.session.scored['total_paid_attempt_count'], 61)
        self.assertIs(self.sampler.closed, True)

    def test_live_gate_refuses_before_any_paid_call(self):
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            with self.assertRaisesRegex(
                    worker.PptSelectionError,
                    'graph_matrix_and_actor_account_not_qualified'):
                self.batch().run()
        self.assertEqual(self.session.paid_calls, [])

    def test_reset_drift_records_invalid_without_a_zero_score(self):
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            with self.assertRaisesRegex(worker.PptSelectionError,
                                        'fresh_copy_reset_changed'):
                self.batch(gate=lambda _bindings: None,
                           reset_drift=True).run()
        self.assertIsNone(self.session.scored)
        self.assertEqual(self.session.invalid['failure_type'],
                         'environment')

    def test_checkpoint_and_unsupported_workflow_fail_before_payment(self):
        with self.assertRaisesRegex(worker.PptSelectionError,
                                    'start_or_checkpoint_unbound'):
            worker.PptSelectionBatch(
                self.session, self.started,
                self.checkpoint + '-changed',
                self.manifest_path, self.private / 'result')
        manifest = json.loads(self.manifest_path.read_bytes())
        path = Path(manifest['tasks'][0]['binding_path'])
        binding = json.loads(path.read_bytes())
        binding['workflow'] = 'chart_caption_reconciliation'
        write_private(path, worker._canonical(binding))
        manifest['tasks'][0]['binding_sha256'] = sha(path.read_bytes())
        write_private(self.manifest_path, worker._canonical(manifest))
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            with self.assertRaisesRegex(worker.PptSelectionError,
                                        'unsupported_wdi_selection_workflow'):
                self.batch(gate=lambda _bindings: None).run()
        self.assertEqual(self.session.paid_calls, [])


if __name__ == '__main__':
    unittest.main()
