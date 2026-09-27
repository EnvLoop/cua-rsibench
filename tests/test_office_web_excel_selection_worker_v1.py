"""Offline 20-task selection execution and paid coverage; no cloud calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cursibench.full_study_selection_paid_coverage_v1 import validate as paid_coverage
from cursibench.scale_action_contract import make_observation
from cursibench import scale_action_output_v066
from cursibench.scale_vision_proxy import MODEL
from tests.test_office_web_ppt_teacher_worker_v1 import (
    FakeSandbox, png, write_private,
)
from tests.test_sec_excel_web_train_oracle_v1 import workbook
from tools import office_web_excel_selection_worker_v1 as worker
from tools import sec_excel_web_selection_oracle_v1 as selection_oracle


def sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


class FakeSession:
    def __init__(self, repo: Path, roster: list[dict], checkpoint: str):
        self.views = {'selection': tuple(roster)}
        self.intent = {'cell_id': 'excel-web',
                       'e2b_sandbox_hours_cap': '100'}
        config = {'model': MODEL, 'action_profile':
                  worker.ACTION_PROFILE_VERSION,
                  'sample_max_tokens': 256, 'seed': 23,
                  'prefill_usd_per_million_tokens': '1',
                  'sample_usd_per_million_tokens': '1',
                  'billing_multiplier_upper': '2'}
        self.study = type('Study', (), {
            'repo_root': repo,
            'student_training_configuration':
                lambda _self: (config, 'b' * 64),
        })()
        self.checkpoint = checkpoint
        self.attempt = 'excel-selection-a1'
        self.paid_calls = []
        self.scored = None
        self.invalid = None

    def _events(self, kind=None):
        if kind == 'selection_started':
            return [{'data': {
                'attempt_id': self.attempt,
                'checkpoint_path_sha256': sha(self.checkpoint),
                'selection_identities_sha256':
                    sha(worker._canonical(list(self.views['selection']))),
            }}]
        if kind == 'paid_intent':
            return [{'data': {'attempt_id': row['attempt_id']}}
                    for row in self.paid_calls]
        return []

    def _counter_totals(self):
        return {'e2b_sandbox_hours': 0}

    def dispatch_paid(self, **kwargs):
        attempt_id = kwargs['attempt_id']
        if any(row['attempt_id'] == attempt_id for row in self.paid_calls):
            raise AssertionError('duplicate paid attempt')
        result = kwargs['provider'](kwargs['request'])
        self.paid_calls.append({
            'attempt_id': attempt_id, 'category': kwargs['category'],
            'request': kwargs['request'], 'result_present': True,
            'result_status': result.get('status'),
        })
        return {'attempt_id': attempt_id, 'result': result,
                'result_sha256': sha(worker._canonical(result)),
                'billing_state': 'awaiting_provider_usage_reconciliation'}

    def record_selection_scored(self, *, attempt_id, result,
                                paid_attempt_ids):
        self.scored = paid_coverage(
            cell_id='excel-web', attempt_id=attempt_id,
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

    def record_selection_invalid(self, **kwargs):
        self.invalid = kwargs
        return kwargs


class FakeSampler:
    def __init__(self, checkpoint: str):
        self.checkpoint = checkpoint
        self.closed = None

    def setup(self):
        return {'status': 'completed', 'model': MODEL,
                'checkpoint_path_sha256': sha(self.checkpoint)}

    def sample(self, observation, *, task_index, step):
        action = {'type': 'finish'}
        return {'status': 'completed', 'new_dispatch': True,
                'reused': False,
                'text': json.dumps(action),
                'usage': {'input_tokens': 500,
                          'output_tokens': 60}}

    def close(self, *, success):
        self.closed = success


class FakeTaskWorker:
    def __init__(self, path: Path, *, bad_reset: bool = False):
        self.path = path
        self.binding = json.loads(path.read_bytes())
        self.bad_reset = bad_reset

    def _binding(self, task):
        if self.binding['task_id'] != task['task_id']:
            raise worker.ExcelSelectionError('wrong_task_binding')
        if self.binding['workflow'] != 'sec-integrated':
            raise worker.ExcelSelectionError('unsupported_workflow')
        return self.binding, None, None, None

    def run_task(self, *, task, out_dir, sample_student, dispatch_e2b):
        def lease(_request):
            return {'created': True,
                    'sandbox_id': 'fake-' + task['task_id'] + '-' +
                        _request['phase']}
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
        paid = sample_student(observation)
        action = scale_action_output_v066.normalize_model_action(
            paid['text'], observation,
            current_frame_id=observation.frame_id)
        if action['type'] != 'finish':
            raise AssertionError('fake sampler did not finish')
        reset = dispatch_e2b(
            lease_seconds=300, reserve_usd='1',
            provider=lease, phase='reset')
        if self.bad_reset:
            raise worker.ExcelSelectionError('fresh_copy_reset_changed')
        saved = (out_dir / 'artifacts' / 'saved-graph')
        saved_bytes = workbook()
        write_private(saved / 'first.private.xlsx', saved_bytes)
        write_private(saved / 'second.private.xlsx', saved_bytes)
        saved_sha = sha((saved / 'first.private.xlsx').read_bytes())
        verifier = {
            'schema': 'cua-office-excel-selection-verifier-v1',
            'task_id': task['task_id'], 'score': 0,
            'saved_state_sha256': saved_sha,
        }
        reset_receipt = {
            'schema': 'cua-office-excel-selection-reset-v1',
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
            'verifier_receipt_sha256':
                sha((out_dir / 'verifier.private.json').read_bytes()),
            'reset_receipt_sha256':
                sha((out_dir / 'reset.private.json').read_bytes()),
            'sample_paid_attempt_ids': [paid['paid_attempt_id']],
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


class ExcelSelectionBatchTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()
        (self.repo / 'work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=self.repo / 'work', prefix='excel-selection-test-')
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)
        self.roster = [{'task_id': f'excel-select-{index:02d}',
                        'package_sha256': sha(f'package-{index}')}
                       for index in range(20)]
        self.checkpoint = 'tinker://example/sampler_weights/selection'
        self.session = FakeSession(self.repo, self.roster,
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
        for row in self.roster:
            path = self.private / 'bindings' / \
                (row['task_id'] + '.private.json')
            write_private(path, worker._canonical({
                'task_id': row['task_id'],
                'visible_instruction': 'Repair the original SEC workbook.',
                'workflow': 'sec-integrated',
                'lease_seconds': 300,
            }))
            entries.append({**row, 'binding_path': str(path),
                            'binding_sha256': sha(path.read_bytes())})
        self.manifest_path = self.private / 'manifest.private.json'
        self.manifest = {
            'schema': worker.BATCH_SCHEMA,
            'cell_id': 'excel-web', 'split': 'selection',
            'selection_attempt': self.session.attempt,
            'selection_identities_sha256':
                sha(worker._canonical(self.roster)),
            'checkpoint_path_sha256': sha(self.checkpoint),
            'worker_runtime_sha256': worker.runtime_sha256(),
            'tasks': entries,
        }
        write_private(self.manifest_path,
                      worker._canonical(self.manifest))
        self.sampler = FakeSampler(self.checkpoint)

    def make_batch(self, *, gate=None, bad_reset=False):
        return worker.ExcelSelectionBatch(
            self.session, self.started, self.checkpoint,
            self.manifest_path, self.private / 'result',
            task_worker_factory=lambda path: FakeTaskWorker(
                path, bad_reset=bad_reset),
            sampler_factory=lambda _config: self.sampler,
            selection_graph_gate=gate)

    def test_twenty_task_paid_qwen_and_e2b_coverage(self):
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            result = self.make_batch(gate=lambda _bindings: None).run()
        self.assertEqual(len(result['result']['tasks']), 20)
        self.assertEqual(self.session.scored['sample_paid_attempt_count'], 20)
        self.assertEqual(
            self.session.scored['environment_paid_attempt_count'], 40)
        self.assertEqual(
            self.session.scored['total_paid_attempt_count'], 61)
        self.assertIs(self.sampler.closed, True)
        self.assertIsNone(self.session.invalid)

    def test_default_graph_gate_blocks_before_any_paid_call(self):
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            with self.assertRaisesRegex(
                    worker.ExcelSelectionError,
                    'graph_matrix_and_actor_account_not_qualified'):
                self.make_batch().run()
        self.assertEqual(self.session.paid_calls, [])

    def test_checkpoint_and_unsupported_workflow_fail_before_paid(self):
        with self.assertRaisesRegex(worker.ExcelSelectionError,
                                    'start_or_checkpoint_unbound'):
            worker.ExcelSelectionBatch(
                self.session, self.started, self.checkpoint + '-changed',
                self.manifest_path, self.private / 'result')
        path = Path(self.manifest['tasks'][0]['binding_path'])
        value = json.loads(path.read_bytes())
        value['workflow'] = 'sec-cashquality'
        write_private(path, worker._canonical(value))
        self.manifest['tasks'][0]['binding_sha256'] = sha(path.read_bytes())
        write_private(self.manifest_path,
                      worker._canonical(self.manifest))
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            with self.assertRaisesRegex(worker.ExcelSelectionError,
                                        'unsupported_workflow'):
                self.make_batch(gate=lambda _bindings: None).run()
        self.assertEqual(self.session.paid_calls, [])

    def test_reset_drift_is_invalid_and_not_a_zero_score(self):
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            with self.assertRaisesRegex(worker.ExcelSelectionError,
                                        'fresh_copy_reset_changed'):
                self.make_batch(gate=lambda _bindings: None,
                                bad_reset=True).run()
        self.assertIsNone(self.session.scored)
        self.assertEqual(self.session.invalid['failure_type'],
                         'environment')
        self.assertEqual(len(self.session.paid_calls), 4)

    def test_reopened_saved_bytes_are_checked_against_ledger(self):
        batch = self.make_batch(gate=lambda _bindings: None)
        with patch('cursibench.full_study_teacher_adapter_v1._frozen_session'):
            batch.run()
            prepared, _config, _sha = batch.preflight()
        ledger = worker.SelectionTaskLedger(
            self.private / 'result' / 'tasks.private.jsonl', {
                'cell_id': 'excel-web', 'split': 'selection',
                'selection_attempt': self.session.attempt,
                'selection_identities_sha256':
                    sha(worker._canonical(self.roster)),
                'checkpoint_path_sha256': sha(self.checkpoint),
                'manifest_sha256': sha(self.manifest_path.read_bytes()),
                'worker_runtime_sha256': worker.runtime_sha256(),
            })
        rows, _paid = batch._completed_rows(ledger, prepared)
        self.assertEqual(len(rows), 20)
        saved = (self.private / 'result' / 'task-01' / 'artifacts' /
                 'saved-graph' / 'first.private.xlsx')
        write_private(saved, b'tampered')
        with self.assertRaisesRegex(worker.ExcelSelectionError,
                                    'completed_task_receipt_changed'):
            batch._completed_rows(ledger, prepared)


class SelectionTaskWorkerTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()
        (self.repo / 'work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            dir=self.repo / 'work', prefix='excel-selection-task-test-')
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)
        self.task = {'task_id': 'selection-real-worker-01',
                     'package_sha256': 'c' * 64,
                     'visible_instruction': 'Repair the SEC workbook.'}
        self.seed = self.private / 'seed.private.xlsx'
        self.saved = self.private / 'positive.private.xlsx'
        write_private(self.seed, workbook())
        write_private(self.saved, workbook(formula='A1*3'))
        self.binding_path = self.private / 'binding.private.json'
        write_private(self.binding_path,
                      worker._canonical({'test': True}))
        self.binding = {
            **self.task,
            'actor_seed_sha256': sha(self.seed.read_bytes()),
            'case_id': 'sec-selection-test',
            'actor_item': {'item_id': 'ITEM!101'},
            'reset_item': {'item_id': 'ITEM!102'},
            'max_steps': 4, 'manual_wait_seconds': 1,
            'post_finish_wait_seconds': 0,
        }
        self.session = SimpleNamespace(
            study=SimpleNamespace(repo_root=self.repo),
            views={'selection': [self.task]})
        self.sandboxes = {
            'actor': FakeSandbox('sandbox-selection-actor'),
            'reset': FakeSandbox('sandbox-selection-reset'),
        }

    def make_worker(self, *, reset_drift=False, saved_regression=False):
        class Oracle:
            def neutral(self, seed, candidate):
                return selection_oracle.neutral(seed, candidate)

            def score(self, candidate, seed, _cases, _case_id):
                positive = candidate.read_bytes() == self_saved.read_bytes()
                return {
                    'schema': selection_oracle.SCHEMA,
                    'status': 'scored',
                    'score': int(positive),
                    'candidate_sha256': sha(candidate.read_bytes()),
                    'seed_sha256': sha(seed.read_bytes()),
                    'preservation_pass': not saved_regression,
                    'checked_formula_targets': 33,
                    'source_counterfactual_profiles': 2,
                    'error_count': 0 if positive else 1,
                }

        self_saved = self.saved
        instance = worker.SelectionExcelTaskWorker(
            self.session, self.binding_path,
            lease_factory=SimpleNamespace(stop=lambda _p: 'killed'),
            graph_reader=SimpleNamespace(), oracle_runner=Oracle(),
            operator_wait_revocation=lambda *_args: None)
        instance._binding = lambda _task: (
            self.binding, self.binding_path, self.seed,
            self.private / 'cases.private.json')

        def lease(*, phase, item, binding, episode_dir, task_path,
                  dispatch_e2b):
            path = episode_dir / f'{phase}-session.private.json'
            write_private(path, b'{}\n')
            paid = {'attempt_id': 'e2b-' + phase,
                    'result': {'sandbox_id':
                               self.sandboxes[phase].sandbox_id}}
            admitted = SimpleNamespace(
                wall_seconds=30, lease_end_unix=int(__import__('time').time())+120)
            return paid, path, admitted, self.sandboxes[phase]
        instance._lease = lease

        def capture(*, phase, item, binding, episode_dir):
            path = episode_dir / 'artifacts' / f'{phase}.private.xlsx'
            source = (self.saved if phase == 'saved' else
                      self.saved if phase == 'reset' and reset_drift else
                      self.seed)
            write_private(path, source.read_bytes())
            return path, {'phase': phase,
                          'item_id_sha256': sha(item['item_id'])}
        instance._graph_capture = capture
        instance._graph_actor_revoked = lambda **_kwargs: {
            'actor_grants_remaining': 0, 'broad_links_remaining': 0}
        return instance

    def test_gui_trace_saved_score_and_fresh_reset(self):
        task_dir = self.private / 'task-01'
        (task_dir / 'frames').mkdir(parents=True, mode=0o700)
        instance = self.make_worker()
        samples = []

        def sample(observation):
            samples.append(observation.step)
            raw = ('{"type":"click","target":{"x":10,"y":20}}'
                   if observation.step == 0 else
                   '{"type":"finish"}')
            return {'status': 'completed', 'text': raw,
                    'paid_attempt_id': 'sample-' +
                        str(observation.step),
                    'paid_result_sha256': sha(raw)}

        result = instance.run_task(
            task=self.task, out_dir=task_dir,
            sample_student=sample,
            dispatch_e2b=lambda **_kwargs: None)
        self.assertEqual(samples, [0, 1])
        self.assertEqual(result['result_row']['score'], 1)
        self.assertEqual(len(result['paid_attempt_ids']), 4)
        self.assertIn(('left_click',),
                      self.sandboxes['actor'].actions)
        self.assertTrue((task_dir / 'reset.private.json').is_file())

    def test_reset_drift_is_invalid_not_scored_zero(self):
        task_dir = self.private / 'task-02'
        (task_dir / 'frames').mkdir(parents=True, mode=0o700)
        instance = self.make_worker(reset_drift=True)
        with self.assertRaisesRegex(worker.ExcelSelectionError,
                                    'fresh_copy_reset_changed'):
            instance.run_task(
                task=self.task, out_dir=task_dir,
                sample_student=lambda observation: {
                    'status': 'completed', 'text': '{"type":"finish"}',
                    'paid_attempt_id': 'sample-0',
                    'paid_result_sha256': sha('sample-0')},
                dispatch_e2b=lambda **_kwargs: None)
        self.assertFalse((task_dir / 'task-receipt.private.json').exists())


if __name__ == '__main__':
    unittest.main()
