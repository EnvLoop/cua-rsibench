"""Synthetic protocol fixture only: no real final task, provider, or GUI call."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from cursibench import full_study_budget_v1 as budget  # noqa: E402
from cursibench import full_study_campaign_dispatch_v1 as campaign  # noqa: E402
from cursibench import full_study_final_dispatch_v1 as final  # noqa: E402
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_pre_campaign_v1 as pre  # noqa: E402
from cursibench import full_study_publication_v1 as publication  # noqa: E402
from cursibench import full_study_results_v1 as results  # noqa: E402
from cursibench import scale_final_v06 as evidence  # noqa: E402
from native_desktop_factory import qwen_v066_adapter  # noqa: E402
from native_desktop_factory.v066_final_freeze import source_hashes  # noqa: E402
import test_full_study_matrix_v1 as fixture  # noqa: E402


def write(path: Path, value: object) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    final.private_write_new(path, evidence.json_bytes(value))
    return {'path': path.name, 'sha256': final.sha(path.read_bytes())}


class FakeTrustedWorker:
    def __init__(self, cell: dict, *, first_invalid: bool = False,
                 wrong_profile: bool = False, raise_after_dispatch: bool = False,
                 scored_zero: bool = False):
        bindings = cell['matched_bindings']
        self.identity = {
            'schema': final.WORKER_SCHEMA, 'cell_id': cell['cell_id'],
            'source_snapshot_sha256': bindings['source_snapshot'],
            'runtime_sha256': bindings['runtime'],
            'action_contract_sha256': bindings['action_contract'],
            'verifier_sha256': bindings['verifier'],
            'adapter_source_sha256': (
                final.sha(Path(qwen_v066_adapter.__file__).read_bytes())
                if cell['cell_id'] == 'desktop-native' else 'a' * 64),
            'action_profile': ('wrong' if wrong_profile else
                               'scale-action-profile-v0.6.6'),
            'observation_kind': 'screenshot',
            'actor_capability': 'current_frame_gui_actions_only',
            'evaluator_isolated': True, 'cold_reset_supported': True,
            'saved_state_readback_supported': True,
        }
        self.first_invalid = first_invalid
        self.invalid_consumed = False
        self.raise_after_dispatch = raise_after_dispatch
        self.scored_zero = scored_zero
        self.commands = []

    def run_once(self, command: dict, output_dir: Path) -> dict:
        self.commands.append(copy.deepcopy(command))
        if self.raise_after_dispatch:
            raise TimeoutError('synthetic callback ambiguity')
        assert 'gold' not in command and 'verifier' not in command
        assert 'visible_instruction' not in command
        invalid = self.first_invalid and not self.invalid_consumed and command['retry_index'] == 0
        self.invalid_consumed |= invalid
        attempt_id = command['attempt_id']
        usage = write(output_dir / 'usage.json', {
            'schema': final.USAGE_SCHEMA, 'attempt_id': attempt_id,
            'cost_basis': 'published_rate_nominal', 'cost_usd': '0.01',
            'input_tokens': 10, 'image_tokens': 5,
            'output_tokens': 2, 'provider_billed_tokens': None,
            'provider_invoice_sha256': None,
        })
        initial = command['expected_initial_state_sha256']
        reset = write(output_dir / 'reset.json', {
            'schema': final.RESET_SCHEMA, 'task_id': command['task_id'],
            'package_sha256': command['package_sha256'],
            'attempt_id': attempt_id,
            'fresh_environment': True, 'restored_after_attempt': True,
            'initial_state_sha256': initial,
            'restored_state_sha256': initial,
        })
        observations = write(output_dir / 'observations.json', {
            'schema': final.TRACE_SCHEMA, 'attempt_id': attempt_id,
            'kind': 'observations',
            'action_profile': 'scale-action-profile-v0.6.6',
            'count': 2, 'screenshot_only': True,
        })
        actions = write(output_dir / 'actions.json', {
            'schema': final.TRACE_SCHEMA, 'attempt_id': attempt_id,
            'kind': 'actions',
            'action_profile': 'scale-action-profile-v0.6.6',
            'count': 1, 'current_frame_validated': True,
        })
        state_ref = verifier_ref = None
        if not invalid:
            saved_state = output_dir / 'state.bin'
            final.private_write_new(saved_state, b'synthetic saved state')
            state_ref = final.reference(output_dir, saved_state)
            verifier_ref = write(output_dir / 'verifier.json', {
                'schema': final.VERIFIER_SCHEMA,
                'task_id': command['task_id'],
                'package_sha256': command['package_sha256'],
                'attempt_id': attempt_id,
                'saved_state_sha256': final.sha(saved_state.read_bytes()),
                'score': 0 if self.scored_zero else 1,
                'no_regression_checked': True,
                'no_regression_passed': not self.scored_zero,
                'independent_of_actor': True,
                'gold_withheld_from_actor': True,
            })
        now = int(time.time())
        return {
            'schema': final.OUTCOME_SCHEMA,
            'status': 'invalid' if invalid else 'scored',
            'score': None if invalid else 0 if self.scored_zero else 1,
            'failure_type': 'transport' if invalid else None,
            'started_at': now, 'finished_at': now,
            'cost_basis': 'published_rate_nominal', 'cost_usd': '0.01',
            'usage': usage, 'reset': reset,
            'saved_state': state_ref, 'verifier': verifier_ref,
            'observation_trace': observations, 'action_trace': actions,
            'action_count': 1, 'turn_count': 2,
            'wall_time_ms': 0, 'provider_latency_ms': 0,
            'timeout_subtype': 'transport' if invalid else 'none',
            'action_profile': 'scale-action-profile-v0.6.6',
        }


class FullStudyFinalDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cua-final-dispatch-test-')
        self.repo = Path(self.temp.name)
        self.work = self.repo / 'work'
        self.work.mkdir(mode=0o700)
        fixture.FullStudyMatrixTests.root = self.work
        self.matrix_value = fixture.FullStudyMatrixTests.build_fixture()
        # Every selected slot retains its base checkpoint. This exercises the
        # exact-base reuse path without inventing Tinker sampler URLs.
        for cell in self.matrix_value['cells']:
            base = json.loads((self.work / cell['base_manifest']['path']).read_bytes())
            checkpoint = base['bindings']['checkpoint']['sha256']
            for rid, ref in cell['selected_manifests'].items():
                path = self.work / ref['path']
                selected = json.loads(path.read_bytes())
                freeze_path = path.parent / selected['bindings']['checkpoint']['freeze_receipt']['path']
                freeze = json.loads(freeze_path.read_bytes())
                freeze['checkpoint_sha256'] = checkpoint
                freeze_path.write_bytes(evidence.json_bytes(freeze))
                selected['bindings']['checkpoint']['sha256'] = checkpoint
                selected['bindings']['checkpoint']['freeze_receipt']['sha256'] = final.sha(
                    freeze_path.read_bytes())
                path.write_bytes(evidence.json_bytes(selected))
                ref['sha256'] = final.sha(path.read_bytes())
        self.protocol_path = self.work / 'pre-campaign-protocol.json'
        self.prepared_pre = self.work / 'prepared-pre'
        pre.prepare(self.protocol_path, self.prepared_pre)
        self.matrix_path = self.work / 'matrix.private.json'
        final.private_write_new(self.matrix_path,
                                evidence.json_bytes(self.matrix_value))
        self.prepared_matrix = self.work / 'prepared-matrix'
        matrix.prepare(self.matrix_path, self.prepared_matrix)
        self.matrix_plan = json.loads((self.prepared_matrix /
                                      'matrix-plan.json').read_bytes())
        common = source_hashes()
        profiles = {cell_id: {
            'common_source_sha256s': common,
            'adapter_sha256': (final.sha(Path(qwen_v066_adapter.__file__).read_bytes())
                               if cell_id == 'desktop-native' else 'a' * 64),
        } for cell_id in matrix.CELLS}
        self.ratification_path = self.work / 'ratification.private.json'
        final.private_write_new(self.ratification_path, evidence.json_bytes({
            'schema': 'cua-six-cell-action-profile-v066-ratification-v1',
            'status': 'ratified_pre_result',
            'ratified_utc': datetime.now(timezone.utc).isoformat(),
            'action_profile': 'scale-action-profile-v0.6.6',
            'common_source_sha256s': common, 'cell_profiles': profiles,
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }))
        pre_plan = json.loads((self.prepared_pre / 'campaign-plan.json').read_bytes())
        witness = {
            'schema': campaign.WITNESS_SCHEMA,
            'status': 'frozen_before_campaign_dispatch',
            'study_id': pre_plan['study_id'],
            'protocol_manifest_sha256': final.sha(self.protocol_path.read_bytes()),
            'campaign_plan_sha256': final.sha((self.prepared_pre /
                                               'campaign-plan.json').read_bytes()),
            'ratification_sha256': final.sha(self.ratification_path.read_bytes()),
            'action_contract_sha256_by_cell': {
                row['cell_id']: row['matched_bindings']['action_contract']
                for row in pre_plan['cells']},
            'campaign_count': 24,
            'admitted_final_task_identities': 600,
            'hidden_final_model_attempts_before_freeze': 0,
        }
        self.frozen = campaign.FrozenStudy(
            repo_root=self.repo, manifest_path=self.protocol_path,
            prepared_dir=self.prepared_pre,
            ratification_path=self.ratification_path,
            public_commit_sha1='b' * 40,
            witness_fetcher=lambda _url: evidence.json_bytes(witness))
        self.budget = budget.StudyBudgetLedger(
            self.work / 'full-study-budget.jsonl', self.frozen.plan)
        self.completions = []
        frozen_at = int(time.time()) - 10
        for cell in self.matrix_plan['cells']:
            cell_id = cell['cell_id']
            base = cell['base']['bindings']['checkpoint']
            for rid in matrix.RESEARCHERS:
                owner = f'{cell_id}:{rid}'
                attempt_id = f'tinker-{cell_id}-{rid}'
                work_sha = final.sha(attempt_id.encode())
                self.budget.reserve(attempt_id, owner, 'tinker', '0.01', work_sha)
                self.budget.mark_dispatched(attempt_id, work_sha)
                self.budget.settle(attempt_id, '0.01', final.sha(b'usage'))
                directory = self.work / 'campaigns' / f'{cell_id}-{rid}'
                directory.mkdir(parents=True, mode=0o700)
                freeze_path = directory / 'selection-freeze.private.json'
                checkpoint_event = {
                    'round_index': 1, 'paid_attempt_id': attempt_id,
                    'dataset_manifest_sha256': final.sha(b'synthetic train dataset'),
                    'training_config_sha256': final.sha(b'synthetic training config'),
                    'checkpoint_path_sha256': final.sha(attempt_id.encode()),
                    'optimizer_steps': 1, 'scheduled_tokens': 20,
                    'epoch_seconds': frozen_at - 2,
                }
                selection_event = {
                    'round_index': 1, 'attempt_id': f'select-{cell_id}-{rid}',
                    'checkpoint_path_sha256': checkpoint_event['checkpoint_path_sha256'],
                    'score_wins': 0, 'epoch_seconds': frozen_at - 1,
                }
                freeze = {
                    'schema': 'cua-full-study-selection-freeze-v1',
                    'cell_id': cell_id, 'researcher_id': rid,
                    'base_checkpoint_sha256': base,
                    'selected_checkpoint_sha256': base,
                    'training_lineage_sha256': final.sha(campaign._canonical([checkpoint_event])),
                    'selection_results_sha256': final.sha(campaign._canonical([selection_event])),
                    'campaign_started_at': frozen_at - 100,
                    'selection_frozen_at': frozen_at,
                    'campaign_finished_at': frozen_at,
                    'candidate_count': 1, 'selection_evaluations': 1,
                }
                final.private_write_new(freeze_path, evidence.json_bytes(freeze))
                intent = self.frozen.intents[(cell_id, rid)]
                journal = campaign.CampaignJournal(directory / 'campaign.jsonl', {
                    'schema': campaign.JOURNAL_SCHEMA, 'kind': 'header',
                    'plan_sha256': self.frozen.plan_sha256,
                    'intent_sha256': intent['intent_sha256'],
                    'ratification_sha256': self.frozen.ratification_sha256,
                    'public_witness_sha256': self.frozen.public_witness_sha256,
                    'owner': owner,
                })
                journal.append('campaign_started',
                               {'epoch_seconds': frozen_at - 100})
                journal.append('tinker_checkpoint', checkpoint_event)
                journal.append('selection_scored', selection_event)
                journal.append('selection_frozen', {
                    'freeze_sha256': final.sha(freeze_path.read_bytes()),
                    'selected_checkpoint_sha256': base,
                    'selected_selection_wins': 0,
                    'epoch_seconds': frozen_at,
                })
                self.completions.append({
                    'cell_id': cell_id, 'researcher_id': rid,
                    'selection_freeze': final.reference(self.work, freeze_path),
                    'campaign_journal': final.reference(self.work, journal.path),
                })
        self.completion_index_path = self.work / 'completion-index.private.json'
        self.write_completion_index(self.completions)
        self.public_final_witness = {
            'schema': final.PUBLIC_FINAL_SCHEMA,
            'status': 'frozen_before_first_final_dispatch',
            'study_id': self.matrix_plan['study_id'],
            'pre_campaign_public_witness_sha256': self.frozen.public_witness_sha256,
            'matrix_manifest_sha256': self.matrix_plan['matrix_manifest_sha256'],
            'matrix_plan_sha256': final.sha((self.prepared_matrix /
                                             'matrix-plan.json').read_bytes()),
            'completion_index_sha256': final.sha(self.completion_index_path.read_bytes()),
            'ratification_sha256': self.frozen.ratification_sha256,
            'retry_rule_sha256': final.RETRY_RULE_SHA256,
            'selection_freeze_sha256_by_campaign': {
                f"{row['cell_id']}:{row['researcher_id']}":
                    row['selection_freeze']['sha256']
                for row in self.completions},
            'official_final_model_attempts_before_freeze': 0,
        }
        self.sampler_path = self.work / 'sampler-bindings.private.json'
        final.private_write_new(self.sampler_path, evidence.json_bytes({
            'schema': 'cua-full-study-final-sampler-bindings-v1',
            'study_id': self.matrix_plan['study_id'],
            'matrix_plan_sha256': final.sha((self.prepared_matrix /
                                             'matrix-plan.json').read_bytes()),
            'owners': [{
                'cell_id': cell['cell_id'], 'owner_slot': 'shared-base',
                'checkpoint_sha256': cell['base']['bindings']['checkpoint'],
                'sampler_path': None,
                'observed_base_model': matrix.STUDENT,
                'action_profile': 'scale-action-profile-v0.6.6',
            } for cell in self.matrix_plan['cells']],
        }))

    def tearDown(self):
        self.temp.cleanup()

    def write_completion_index(self, entries):
        payload = {
            'schema': final.GATE_SCHEMA,
            'study_id': self.matrix_plan['study_id'],
            'matrix_plan_sha256': final.sha((self.prepared_matrix /
                                             'matrix-plan.json').read_bytes()),
            'retry_rule_sha256': final.RETRY_RULE_SHA256,
            'campaigns': entries,
        }
        self.completion_index_path.write_bytes(evidence.json_bytes(payload))
        self.completion_index_path.chmod(0o600)

    def gate(self):
        return final.FinalGate(
            frozen=self.frozen, matrix_manifest_path=self.matrix_path,
            prepared_matrix_dir=self.prepared_matrix,
            completion_index_path=self.completion_index_path,
            final_public_commit_sha1='c' * 40,
            witness_fetcher=lambda _url: evidence.json_bytes(self.public_final_witness))

    def controller(self, workers=None):
        gate = self.gate()
        workers = workers or {cell_id: FakeTrustedWorker(
            next(row for row in gate.plan['cells'] if row['cell_id'] == cell_id))
            for cell_id in matrix.CELLS}
        return final.FinalController(
            gate, workers=workers, sampler_bindings_path=self.sampler_path,
            output_dir=self.work / 'final-output'), workers

    def test_missing_campaign_blocks_all_final_workers(self):
        self.write_completion_index(self.completions[:-1])
        with self.assertRaisesRegex(ValueError,
                                    'completion_index_not_frozen_full_matrix'):
            self.gate()

    def test_frozen_base_reuse_and_one_bounded_infrastructure_retry(self):
        gate = self.gate()
        workers = {cell_id: FakeTrustedWorker(
            next(row for row in gate.plan['cells'] if row['cell_id'] == cell_id),
            first_invalid=cell_id == matrix.CELLS[0])
            for cell_id in matrix.CELLS}
        controller, _ = self.controller(workers)
        cell_id = matrix.CELLS[0]
        first_task = controller._task_order(cell_id, 'shared-base')[0]
        invalid = controller.run_task(cell_id, 'shared-base', first_task['task_id'])
        self.assertEqual(invalid['status'], 'invalid_reconciled_retry_available')
        recovered = controller.run_task(cell_id, 'shared-base', first_task['task_id'])
        self.assertEqual((recovered['score'], len(recovered['attempts'])), (1, 2))
        self.assertEqual(len(workers[cell_id].commands), 2)
        self.assertEqual(controller.run_task(cell_id, 'shared-base', first_task['task_id']),
                         recovered)
        self.assertEqual(len(workers[cell_id].commands), 2)
        with self.assertRaisesRegex(ValueError,
                                    'final_execution_requires_100_scored_tasks'):
            controller.materialize_execution(cell_id, 'shared-base')
        for task in controller._task_order(cell_id, 'shared-base')[1:]:
            controller.run_task(cell_id, 'shared-base', task['task_id'])
        refs = controller.materialize_execution(cell_id, 'shared-base')
        result_path, result_raw = final.private_reference(
            self.work, refs['final_execution'], 'execution')
        result = json.loads(result_raw)
        scores, invalid_counts = results._execution(
            result, cell_id=cell_id, owner='shared-base',
            checkpoint=gate.plan['cells'][0]['base']['bindings']['checkpoint'],
            packages=results._task_packages(gate.plan['cells'][0]['base']),
            after_time=gate.last_selection_frozen_at)
        self.assertEqual((len(scores['scores']), invalid_counts['transport']),
                         (100, 1))
        execution_index = {'final_executions': [{
            'cell_id': cell_id, 'owner_slot': 'shared-base',
            'receipt': refs['final_execution']}],
        }
        summary = {
            'study_id': gate.plan['study_id'],
            'matrix_plan_sha256': gate.plan_sha256,
            'execution_index_sha256': 'd' * 64,
            'unique_checkpoint_task_executions': 100,
            'infrastructure_invalid_attempts_by_type': {
                kind: int(kind == 'transport') for kind in results.FAILURE_TYPES},
        }
        telemetry = {'schema': publication.TELEMETRY_SCHEMA,
                     'study_id': gate.plan['study_id'],
                     'matrix_plan_sha256': gate.plan_sha256,
                     'execution_index_sha256': 'd' * 64,
                     'executions': [{
                         'cell_id': cell_id, 'owner_slot': 'shared-base',
                         'receipt': refs['telemetry']}],
                     }
        measures = publication._telemetry_bundle(
            telemetry, self.work, execution_index, self.work, summary)
        self.assertEqual((measures['task_count'], measures['attempt_count'],
                          measures['retry_count']), (100, 101, 1))
        self.assertEqual({command['owner_slot'] for command in
                          workers[cell_id].commands}, {'shared-base'})
        self.assertEqual(result_path.stat().st_mode & 0o077, 0)

    def test_worker_version_and_ambiguous_dispatch_fail_closed(self):
        gate = self.gate()
        workers = {cell_id: FakeTrustedWorker(
            next(row for row in gate.plan['cells'] if row['cell_id'] == cell_id),
            wrong_profile=cell_id == matrix.CELLS[0])
            for cell_id in matrix.CELLS}
        with self.assertRaisesRegex(ValueError, 'trusted_cell_worker_contract_mismatch'):
            self.controller(workers)
        workers[matrix.CELLS[0]] = FakeTrustedWorker(
            gate.plan['cells'][0], raise_after_dispatch=True)
        controller, _ = self.controller(workers)
        task = controller._task_order(matrix.CELLS[0], 'shared-base')[0]
        with self.assertRaises(TimeoutError):
            controller.run_task(matrix.CELLS[0], 'shared-base', task['task_id'])
        with self.assertRaisesRegex(ValueError,
                                    'unresolved_final_attempt_no_automatic_replay'):
            controller.run_task(matrix.CELLS[0], 'shared-base', task['task_id'])
        self.assertEqual(len(workers[matrix.CELLS[0]].commands), 1)

    def test_independently_detected_collateral_change_is_model_zero(self):
        gate = self.gate()
        workers = {cell_id: FakeTrustedWorker(
            next(row for row in gate.plan['cells'] if row['cell_id'] == cell_id),
            scored_zero=cell_id == matrix.CELLS[0])
            for cell_id in matrix.CELLS}
        controller, _ = self.controller(workers)
        task = controller._task_order(matrix.CELLS[0], 'shared-base')[0]
        result = controller.run_task(matrix.CELLS[0], 'shared-base',
                                     task['task_id'])
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['attempts'][0]['status'], 'scored')
        self.assertEqual(len(workers[matrix.CELLS[0]].commands), 1)


if __name__ == '__main__':
    unittest.main()
