"""Synthetic six-cell tests never dispatch a real provider or hidden task."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from cursibench import full_study_campaign_dispatch_v1 as dispatch  # noqa: E402
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_pre_campaign_v1 as pre_campaign  # noqa: E402
from cursibench import scale_final_v06 as cell_final  # noqa: E402
from native_desktop_factory import qwen_v066_adapter  # noqa: E402
from native_desktop_factory.v066_final_freeze import source_hashes  # noqa: E402
import test_full_study_matrix_v1 as matrix_fixture  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fake_researcher_receipt() -> dict:
    return {'reported_model': 'gpt-6-astra', 'status': 'completed',
            'usage': {'input_tokens': 100, 'output_tokens': 50}}


class FullStudyDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cua-study-dispatch-test-')
        self.root = Path(self.temp.name)
        matrix_fixture.FullStudyMatrixTests.root = self.root
        matrix_fixture.FullStudyMatrixTests.build_fixture()
        self.manifest_path = self.root / 'pre-campaign-protocol.json'
        protocol = json.loads(self.manifest_path.read_bytes())
        researcher_ref = protocol['configurations']['researchers']['astra']
        researcher_path = self.root / researcher_ref['path']
        researcher_config = json.loads(researcher_path.read_bytes())
        rate_ref = researcher_config['assets']['provider_route']
        rate_path = researcher_path.parent / rate_ref['path']
        rate_raw = cell_final.json_bytes({
            'schema': 'cua-agentrouterhub-rate-upper-v1',
            'model': 'gpt-6-astra',
            'base_url': 'https://sub2api.agentrouterhub.com',
            'input_usd_per_million_tokens': '10',
            'output_usd_per_million_tokens': '50',
            'fixed_usd_per_call': '0',
            'billing_multiplier_upper': '2',
        })
        rate_path.write_bytes(rate_raw)
        rate_ref['sha256'] = sha(rate_raw)
        researcher_raw = cell_final.json_bytes(researcher_config)
        researcher_path.write_bytes(researcher_raw)
        researcher_ref['sha256'] = sha(researcher_raw)
        student_ref = protocol['configurations']['student']
        student_path = self.root / student_ref['path']
        student_config = json.loads(student_path.read_bytes())
        training_ref = student_config['assets']['training']
        training_path = student_path.parent / training_ref['path']
        training_raw = cell_final.json_bytes({
            'schema': 'cua-full-study-qwen-sft-training-v1',
            'model': 'Qwen/Qwen3.8-27B',
            'action_profile': 'scale-action-profile-v0.6.6',
            'lora_rank': 8, 'seed': 23, 'batch_size': 1,
            'optimizer_steps': 2, 'learning_rate': '0.0001',
            'max_supervised_tokens': 32768,
            'max_scheduled_tokens': 100,
            'sample_max_tokens': 48,
            'train_usd_per_million_tokens': '4.103',
            'prefill_usd_per_million_tokens': '1.86',
            'sample_usd_per_million_tokens': '5.595',
            'billing_multiplier_upper': '2',
        })
        training_path.write_bytes(training_raw)
        training_ref['sha256'] = sha(training_raw)
        student_raw = cell_final.json_bytes(student_config)
        student_path.write_bytes(student_raw)
        student_ref['sha256'] = sha(student_raw)
        self.manifest_path.write_bytes(cell_final.json_bytes(protocol))
        self.prepared = self.root / 'prepared'
        pre_campaign.prepare(self.manifest_path, self.prepared)
        self.plan = json.loads((self.prepared / 'campaign-plan.json').read_bytes())
        self.ratification_path = self.root / 'ratification.private.json'
        common = source_hashes()
        profiles = {cell_id: {
            'common_source_sha256s': common,
            'adapter_sha256': ('a' * 64 if cell_id != 'desktop-native' else
                               sha(Path(qwen_v066_adapter.__file__).read_bytes())),
        } for cell_id in matrix.CELLS}
        self.ratification_path.write_bytes(cell_final.json_bytes({
            'schema': 'cua-six-cell-action-profile-v066-ratification-v1',
            'status': 'ratified_pre_result',
            'ratified_utc': datetime.now(timezone.utc).isoformat(),
            'action_profile': 'scale-action-profile-v0.6.6',
            'common_source_sha256s': common, 'cell_profiles': profiles,
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }))
        self.ratification_sha = sha(self.ratification_path.read_bytes())
        self.commit = 'b' * 40
        self.witness = {
            'schema': dispatch.WITNESS_SCHEMA,
            'status': 'frozen_before_campaign_dispatch',
            'study_id': self.plan['study_id'],
            'protocol_manifest_sha256': sha(self.manifest_path.read_bytes()),
            'campaign_plan_sha256': sha((self.prepared / 'campaign-plan.json').read_bytes()),
            'ratification_sha256': self.ratification_sha,
            'action_contract_sha256_by_cell': {
                row['cell_id']: row['matched_bindings']['action_contract']
                for row in self.plan['cells']},
            'campaign_count': 24,
            'admitted_final_task_identities': 600,
            'hidden_final_model_attempts_before_freeze': 0,
        }
        self.clock = [1_800_000_000]

    def tearDown(self):
        self.temp.cleanup()

    def frozen(self, witness=None):
        witness = self.witness if witness is None else witness
        return dispatch.FrozenStudy(
            repo_root=self.root, manifest_path=self.manifest_path,
            prepared_dir=self.prepared,
            ratification_path=self.ratification_path,
            public_commit_sha1=self.commit,
            witness_fetcher=lambda _url: cell_final.json_bytes(witness))

    def campaign(self, cell_id=matrix.CELLS[0]):
        frozen = self.frozen()
        session = frozen.open_campaign(
            self.root / 'work' / ('campaign-astra' if cell_id == matrix.CELLS[0]
                                  else 'campaign-astra-' + cell_id),
            cell_id=cell_id, researcher_id='astra',
            now=lambda: self.clock[0])
        return frozen, session

    def base_selection(self, session, *, winning_indices=()):
        tasks = [{'task_id': row['task_id'],
                  'package_sha256': row['package_sha256'],
                  'score': int(index in winning_indices),
                  'saved_state_sha256': sha(b'saved:' + row['task_id'].encode()),
                  'verifier_receipt_sha256': sha(b'verifier:' + row['task_id'].encode()),
                  'reset_receipt_sha256': sha(b'reset:' + row['task_id'].encode())}
                 for index, row in enumerate(session.views['selection'])]
        result = {'schema': 'cua-full-study-selection-saved-result-v1',
                  'cell_id': session.intent['cell_id'],
                  'checkpoint_sha256': session.intent['base_checkpoint_sha256'],
                  'evaluator_isolated': True, 'tasks': tasks}
        session.record_base_selection(result)
        train = self.root / 'work' / 'train-context.private.json'
        train.parent.mkdir(exist_ok=True)
        train.write_bytes(cell_final.json_bytes({
            'schema': 'cua-full-study-researcher-train-view-v1',
            'cell_id': session.intent['cell_id'],
            'tasks': [{'task_id': row['task_id'],
                       'package_sha256': row['package_sha256'],
                       'visible_instruction': 'Repair the train-only document.'}
                      for row in session.views['train']],
        }))
        train.chmod(0o600)
        return train

    def proposed_train_batch(self, session, *, baseline_winning_indices=()):
        context = self.base_selection(
            session, winning_indices=baseline_winning_indices)
        proposal = {'schema': 'cua-full-study-researcher-proposal-v1',
                    'hypothesis': 'Improve train workflow with native examples',
                    'train_task_ids': [session.views['train'][0]['task_id']],
                    'teacher_request': 'Collect train-only GUI actions.'}
        session.dispatch_researcher(
            round_index=1, train_context_path=context,
            provider=lambda _prompt, _settings: (
                json.dumps(proposal), fake_researcher_receipt()))
        task = session.views['train'][0]
        receipt = {
            'schema': 'cua-full-study-qwen-render-v066-v1',
            'cell_id': session.intent['cell_id'],
            'action_profile': 'scale-action-profile-v0.6.6',
            'model': 'Qwen/Qwen3.8-27B',
            'train_task_ids': [task['task_id']],
            'episode_receipt_sha256s': [sha(b'train GUI saved episode')],
            'datum_token_lengths': [20], 'prompt_token_lengths': [10],
        }
        rendered = SimpleNamespace(
            receipt=receipt,
            datums=[SimpleNamespace(model_input=SimpleNamespace(length=20))],
            prompts=[SimpleNamespace(length=10)])
        dataset = {
            'schema': 'cua-full-study-rendered-train-batch-v1',
            'cell_id': session.intent['cell_id'],
            'action_profile': 'scale-action-profile-v0.6.6',
            'model': 'Qwen/Qwen3.8-27B',
            'train_task_ids': [task['task_id']],
            'train_package_sha256_by_id': {
                task['task_id']: task['package_sha256']},
            'episode_receipt_sha256s': receipt['episode_receipt_sha256s'],
            'rendered_batch_sha256': sha(dispatch._canonical(receipt)),
            'admitted_train_only': True, 'selection_task_count': 0,
            'final_task_count': 0,
        }
        path = self.root / 'work' / 'dataset.private.json'
        path.write_bytes(cell_final.json_bytes(dataset))
        path.chmod(0o600)
        return rendered, path

    def trained_candidate(self, session, *, baseline_winning_indices=()):
        rendered, dataset = self.proposed_train_batch(
            session, baseline_winning_indices=baseline_winning_indices)
        result = session.dispatch_tinker_sft(
            round_index=1, dataset_manifest_path=dataset,
            rendered_batch=rendered,
            provider=lambda *_: {
                'checkpoint_path': 'tinker://fake/sampler_weights/ckpt-1',
                'observed_base_model': 'Qwen/Qwen3.8-27B',
                'optimizer_steps_completed': 2,
                'sample_token_count': 5,
                'sample_token_sha256': sha(b'five sample tokens'),
                'sdk_operation_count': 8,
            })
        return result

    def paid_selection_tasks(self, session, started):
        """Fake every task's model sample and one exact original-world lease."""
        attempt = started['attempt_id']
        cell = session.intent['cell_id']
        category = ('e2b' if cell in {'powerpoint-web', 'excel-web',
                                      'desktop-native'} else
                    'storage_application')
        env_id = attempt + '-env-batch'
        session.dispatch_paid(
            attempt_id=env_id, category=category,
            work={'selection_attempt': attempt,
                  'kind': 'complete_original_software_environment'},
            request={
                'schema': 'cua-full-study-selection-environment-request-v1',
                'selection_attempt': attempt, 'cell_id': cell,
                'selection_identities_sha256':
                    started['selection_identities_sha256'],
                'selection_tasks': started['selection_tasks'],
            },
            reserve_usd='0.01',
            resource_reservation=(
                {'e2b_sandbox_hours': '0.01',
                 'e2b_peak_concurrency': '1'} if category == 'e2b' else {}),
            provider=lambda _: {'status': 'fake_environment_completed'}),
        paid_ids = [env_id]
        for ordinal, task in enumerate(started['selection_tasks'], 1):
            sample_id = f'{attempt}-sample-{ordinal:03d}'
            session.dispatch_paid(
                attempt_id=sample_id, category='tinker',
                work={'selection_attempt': attempt,
                      'task_id': task['task_id'], 'kind': 'sample'},
                request={
                    'schema': 'cua-full-study-selection-sampling-request-v1',
                    'selection_attempt': attempt, 'cell_id': cell,
                    'task_id': task['task_id'],
                    'package_sha256': task['package_sha256'],
                    'checkpoint_path_sha256':
                        started['checkpoint_path_sha256'],
                    'step': 0,
                },
                reserve_usd='0.000001', resource_reservation={},
                provider=lambda _: {
                    'status': 'completed',
                    'reported_model': 'Qwen/Qwen3.8-27B',
                    'usage': {'input_tokens': 100,
                              'output_tokens': 10}})
            paid_ids.append(sample_id)
        return paid_ids

    def test_current_missing_real_manifest_refuses_before_fetch_or_provider(self):
        calls = []
        with self.assertRaisesRegex(ValueError, 'pre_campaign_manifest_missing'):
            dispatch.FrozenStudy(
                repo_root=ROOT,
                manifest_path=ROOT / 'work' / 'full-study' / 'absent.json',
                prepared_dir=self.prepared,
                ratification_path=self.ratification_path,
                public_commit_sha1=self.commit,
                witness_fetcher=lambda url: calls.append(url))
        self.assertEqual(calls, [])

    def test_synthetic_freeze_binds_24_intents_and_hides_final_view(self):
        frozen = self.frozen()
        self.assertEqual(len(frozen.intents), 24)
        self.assertEqual(frozen.teacher_configuration()['model'], 'gpt-5.6-sol')
        views = frozen.task_views(matrix.CELLS[0])
        self.assertEqual(len(views['selection']), 20)
        self.assertEqual(len(views['train']), 1)
        self.assertEqual(set(views), {'train', 'selection'})
        _, session = self.campaign()
        self.assertEqual(session.snapshot()['paid_attempt_count'], 0)

    def test_changed_prepared_plan_or_public_witness_fails_closed(self):
        plan_path = self.prepared / 'campaign-plan.json'
        original = plan_path.read_bytes()
        plan_path.write_bytes(original.replace(b'"campaign_count": 24',
                                               b'"campaign_count": 23'))
        with self.assertRaisesRegex(ValueError, 'prepared_campaign_plan_changed'):
            self.frozen()
        plan_path.write_bytes(original)
        wrong = dict(self.witness, ratification_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'public_witness_does_not_bind'):
            self.frozen(wrong)
        wrong = dict(self.witness, admitted_final_task_identities=599)
        with self.assertRaisesRegex(ValueError, 'public_witness_does_not_bind'):
            self.frozen(wrong)

    def test_paid_fake_provider_one_dispatch_private_resume_and_reconciliation(self):
        frozen, session = self.campaign()
        called = []
        result = session.dispatch_paid(
            attempt_id='researcher-001', category='researcher_inference',
            work={'round': 1}, request={'prompt': 'train sources only'},
            reserve_usd='1', resource_reservation={'researcher_calls': '1'},
            provider=lambda request: called.append(request) or {'text': 'proposal'})
        self.assertEqual(len(called), 1)
        self.assertEqual(result['billing_state'],
                         'awaiting_provider_usage_reconciliation')
        self.assertEqual(session.snapshot()['resource_reserved']['researcher_calls'], '1')
        self.assertEqual((session.directory / 'researcher-001.request.private.json').stat().st_mode & 0o077, 0)
        with self.assertRaisesRegex(ValueError, 'attempt_already_recorded'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train sources only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: called.append('duplicate'))
        self.assertEqual(len(called), 1)
        reopened = frozen.open_campaign(
            session.directory, cell_id=matrix.CELLS[0],
            researcher_id='astra', now=lambda: self.clock[0])
        self.assertEqual(reopened.snapshot()['provider_result_count'], 1)
        record = reopened.reconcile_paid('researcher-001', actual_usd='0.5',
                                         provider_usage_sha256=sha(b'billed provider usage'))
        self.assertEqual(record['status'], 'settled')
        self.assertEqual(
            reopened.snapshot()['cost_accounting_usd']
            ['researcher_inference']['reconciled_usd'], '0.5')
        with self.assertRaisesRegex(ValueError, 'already_reconciled'):
            reopened.reconcile_paid('researcher-001', actual_usd='0.5',
                                    provider_usage_sha256=sha(b'billed provider usage'))

    def test_uncertain_failure_blocks_next_call_until_usage_reconciled(self):
        _, session = self.campaign()
        def timeout(_):
            raise TimeoutError('provider body may have been accepted')
        with self.assertRaisesRegex(ValueError, 'paid_response_uncertain'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train sources only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=timeout)
        self.assertTrue(session.snapshot()['uncertain_unreconciled'])
        with self.assertRaisesRegex(ValueError, 'paid_call_unreconciled'):
            session.dispatch_paid(
                attempt_id='researcher-002', category='researcher_inference',
                work={'round': 2}, request={'prompt': 'different train query'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})
        session.reconcile_paid('researcher-001', actual_usd=None,
                               provider_no_charge_sha256=sha(b'provider no charge'))
        self.assertFalse(session.snapshot()['uncertain_unreconciled'])
        with self.assertRaisesRegex(ValueError, 'same_work_already_recorded'):
            session.dispatch_paid(
                attempt_id='researcher-002', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train sources only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})

    def test_time_limit_and_journal_tamper_stop_resumption(self):
        frozen, session = self.campaign()
        self.clock[0] += 16 * 3600 + 1
        with self.assertRaisesRegex(ValueError, 'sixteen_hour_limit'):
            session.dispatch_paid(
                attempt_id='late', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'too late'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})
        self.clock[0] -= 16 * 3600 + 1
        journal = session.directory / 'campaign.jsonl'
        journal.write_bytes(journal.read_bytes().replace(b'campaign_started',
                                                         b'campaign_changed'))
        with self.assertRaisesRegex(ValueError, 'journal_hash_chain_broken'):
            frozen.open_campaign(session.directory, cell_id=matrix.CELLS[0],
                                 researcher_id='astra', now=lambda: self.clock[0])

    def test_orphan_budget_reservation_from_pre_journal_crash_blocks_dispatch(self):
        _, session = self.campaign()
        session.budget.reserve('orphan-001', session.owner,
                               'researcher_inference', '1', sha(b'orphan work'))
        self.assertEqual(session.snapshot()['orphan_budget_attempts'], ['orphan-001'])
        with self.assertRaisesRegex(ValueError, 'paid_call_unreconciled'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})
        session.reconcile_orphan_reservation(
            'orphan-001', provider_no_charge_sha256=sha(b'provider no charge'))
        self.assertEqual(session.snapshot()['orphan_budget_attempts'], [])

    def test_researcher_call_cannot_omit_matched_call_counter(self):
        _, session = self.campaign()
        with self.assertRaisesRegex(ValueError, 'researcher_call_counter_required'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train only'},
                reserve_usd='1', resource_reservation={},
                provider=lambda _: {'text': 'must not run'})
        self.assertEqual(session.snapshot()['paid_attempt_count'], 0)

    def test_researcher_fake_responses_uses_train_and_selection_only(self):
        _, session = self.campaign()
        train_context = self.base_selection(session)
        observed = []
        proposal = {'schema': 'cua-full-study-researcher-proposal-v1',
                    'hypothesis': 'More examples for the train workflow',
                    'train_task_ids': [session.views['train'][0]['task_id']],
                    'teacher_request': 'Demonstrate the train task in the native GUI.'}
        def fake_provider(prompt, settings):
            observed.append((prompt, settings))
            return json.dumps(proposal), fake_researcher_receipt()
        result = session.dispatch_researcher(
            round_index=1, train_context_path=train_context,
            provider=fake_provider)
        self.assertEqual(result['train_task_count'], 1)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][1]['model'], 'gpt-6-astra')
        self.assertNotIn('-official-', observed[0][0])
        self.assertIn('-selection-', observed[0][0])
        self.assertEqual(len(session._events('researcher_proposal')), 1)

    def test_researcher_output_that_requests_final_task_is_retained_and_rejected(self):
        _, session = self.campaign()
        train_context = self.base_selection(session)
        forbidden = matrix.CELLS[0] + '-official-000'
        proposal = {'schema': 'cua-full-study-researcher-proposal-v1',
                    'hypothesis': 'Try leaked final task',
                    'train_task_ids': [forbidden],
                    'teacher_request': 'Use this task.'}
        with self.assertRaisesRegex(ValueError, 'researcher_output_invalid'):
            session.dispatch_researcher(
                round_index=1, train_context_path=train_context,
                provider=lambda _prompt, _settings: (
                    json.dumps(proposal), fake_researcher_receipt()))
        self.assertEqual(len(session._events('researcher_invalid_output')), 1)
        self.assertEqual(session.snapshot()['paid_attempt_count'], 1)
        with self.assertRaisesRegex(ValueError, 'round_not_sequential'):
            session.dispatch_researcher(
                round_index=1, train_context_path=train_context,
                provider=lambda *_: ('{}', {'reported_model': 'gpt-6-astra'}))

    def test_fake_tinker_uses_fresh_base_and_only_frozen_train_datum(self):
        _, session = self.campaign()
        rendered, dataset = self.proposed_train_batch(session)
        observed = []
        def fake_train(batch, config, indices):
            observed.append((batch, config, indices))
            return {'checkpoint_path': 'tinker://fake/sampler_weights/ckpt-1',
                    'observed_base_model': 'Qwen/Qwen3.8-27B',
                    'optimizer_steps_completed': 2,
                    'sample_token_count': 5,
                    'sample_token_sha256': sha(b'five sample tokens'),
                    'sdk_operation_count': 8}
        result = session.dispatch_tinker_sft(
            round_index=1, dataset_manifest_path=dataset,
            rendered_batch=rendered, provider=fake_train)
        self.assertEqual(result['optimizer_steps'], 2)
        self.assertEqual(result['scheduled_tokens'], 40)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][2], [[0], [0]])
        self.assertEqual(session.snapshot()['resource_reserved']['candidate_submissions'], '1')
        self.assertEqual(session.snapshot()['token_telemetry']['provider_input_tokens'], 100)
        self.assertEqual(session.snapshot()['token_telemetry']['tinker_scheduled_train_tokens'], 40)
        self.assertNotIn('checkpoint_path', result)
        self.assertEqual(len(session._events('tinker_checkpoint')), 1)

    def test_tinker_rejects_selection_or_final_source_before_provider(self):
        _, session = self.campaign()
        rendered, dataset_path = self.proposed_train_batch(session)
        dataset = json.loads(dataset_path.read_bytes())
        final_id = matrix.CELLS[0] + '-official-000'
        dataset['train_task_ids'] = [final_id]
        dataset_path.write_bytes(cell_final.json_bytes(dataset))
        called = []
        with self.assertRaisesRegex(ValueError, 'train_dataset_contains_unbound'):
            session.dispatch_tinker_sft(
                round_index=1, dataset_manifest_path=dataset_path,
                rendered_batch=rendered,
                provider=lambda *_: called.append('paid'))
        self.assertEqual(called, [])
        self.assertEqual(len(session._events('paid_intent')), 1)  # Researcher only.

    def test_selection_retry_and_strict_promotion_freeze(self):
        _, session = self.campaign()
        trained = self.trained_candidate(session)
        first = session.start_selection_attempt(
            round_index=1, attempt_id='selection-001')
        self.assertEqual(len(first['selection_tasks']), 20)
        self.assertNotIn('-official-', json.dumps(first))
        session.record_selection_invalid(
            attempt_id='selection-001', failure_type='environment',
            evaluator_receipt_sha256=sha(b'pre-mutation environment outage'))
        second = session.start_selection_attempt(
            round_index=1, attempt_id='selection-002',
            retry_rule_sha256=sha(b'predeclared one infrastructure retry'))
        self.assertEqual(second['checkpoint_path_sha256'],
                         trained['checkpoint_path_sha256'])
        paid_ids = self.paid_selection_tasks(session, second)
        base = json.loads((session.directory / 'base-selection.private.json').read_bytes())
        candidate = dict(base, checkpoint_sha256=trained['checkpoint_path_sha256'])
        candidate['tasks'] = [dict(row) for row in base['tasks']]
        candidate['tasks'][0]['score'] = 1
        selected = session.record_selection_scored(
            attempt_id='selection-002', result=candidate,
            paid_attempt_ids=paid_ids)
        self.assertTrue(selected['promoted'])
        self.assertEqual(selected['score_wins'], 1)
        with self.assertRaisesRegex(ValueError, 'provider_usage_not_reconciled'):
            session.freeze_selection()
        for attempt_id in ('researcher-001', 'tinker-001', *paid_ids):
            session.reconcile_paid(attempt_id, actual_usd='0.000000001',
                                   provider_usage_sha256=sha(attempt_id.encode()))
        frozen = session.freeze_selection()
        self.assertEqual(frozen['candidate_count'], 1)
        self.assertEqual(frozen['selection_evaluations'], 2)
        self.assertEqual(frozen['selected_checkpoint_sha256'],
                         trained['checkpoint_path_sha256'])
        with self.assertRaisesRegex(ValueError, 'campaign_frozen'):
            session.dispatch_paid(
                attempt_id='after-freeze', category='researcher_inference',
                work={'round': 2}, request={'prompt': 'forbidden'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})

    def test_self_hosted_odoo_selection_uses_local_application_cost(self):
        _, session = self.campaign('odoo-community')
        trained = self.trained_candidate(session)
        started = session.start_selection_attempt(
            round_index=1, attempt_id='odoo-selection-001')
        self.assertEqual(len(started['selection_tasks']), 20)
        paid_ids = self.paid_selection_tasks(session, started)
        base = json.loads((session.directory / 'base-selection.private.json').read_bytes())
        candidate = dict(base, checkpoint_sha256=trained['checkpoint_path_sha256'])
        candidate['tasks'] = [dict(row) for row in base['tasks']]
        scored = session.record_selection_scored(
            attempt_id='odoo-selection-001', result=candidate,
            paid_attempt_ids=paid_ids)
        self.assertEqual(scored['score_wins'], 0)
        self.assertFalse(scored['promoted'])
        event = session._events('selection_scored')[-1]
        self.assertEqual(event['data']['paid_attempt_ids'], paid_ids)
        self.assertRegex(event['data']['paid_coverage_sha256'],
                         r'^[0-9a-f]{64}$')

    def test_selection_rejects_evaluation_identity_or_missing_cost_category(self):
        _, session = self.campaign()
        trained = self.trained_candidate(session)
        session.start_selection_attempt(round_index=1,
                                        attempt_id='selection-001')
        base = json.loads((session.directory / 'base-selection.private.json').read_bytes())
        candidate = dict(base, checkpoint_sha256=trained['checkpoint_path_sha256'])
        candidate['tasks'] = [dict(row) for row in base['tasks']]
        candidate['tasks'][0]['task_id'] = matrix.CELLS[0] + '-official-000'
        with self.assertRaisesRegex(ValueError, 'unbound_or_unscored_task'):
            session.record_selection_scored(
                attempt_id='selection-001', result=candidate,
                paid_attempt_ids=['tinker-001'])
        candidate['tasks'][0]['task_id'] = base['tasks'][0]['task_id']
        with self.assertRaisesRegex(ValueError, 'sampler_or_environment_cost_missing'):
            session.record_selection_scored(
                attempt_id='selection-001', result=candidate,
                paid_attempt_ids=['tinker-001'])

    def test_selection_cannot_hide_paid_task_or_tamper_coverage_on_resume(self):
        _, session = self.campaign()
        trained = self.trained_candidate(session)
        started = session.start_selection_attempt(
            round_index=1, attempt_id='selection-coverage-001')
        paid_ids = self.paid_selection_tasks(session, started)
        base = json.loads((session.directory /
                           'base-selection.private.json').read_bytes())
        candidate = dict(base,
                         checkpoint_sha256=trained['checkpoint_path_sha256'])
        candidate['tasks'] = [dict(row) for row in base['tasks']]
        with self.assertRaisesRegex(ValueError,
                                    'selection_paid_attempt_hidden_or_missing'):
            session.record_selection_scored(
                attempt_id=started['attempt_id'], result=candidate,
                paid_attempt_ids=paid_ids[:-1])
        session.record_selection_scored(
            attempt_id=started['attempt_id'], result=candidate,
            paid_attempt_ids=paid_ids)
        coverage_path = (session.directory /
                         'selection-selection-coverage-001-paid-coverage.private.json')
        saved = coverage_path.read_bytes()
        coverage_path.write_bytes(saved.replace(
            b'"task_count":20', b'"task_count":19'))
        with self.assertRaisesRegex(ValueError,
                                    'selection_paid_coverage_receipt_changed'):
            session._incumbent()

    def test_selection_strict_gain_with_one_regression_retains_incumbent(self):
        _, session = self.campaign()
        trained = self.trained_candidate(
            session, baseline_winning_indices=(0,))
        started = session.start_selection_attempt(round_index=1,
                                                  attempt_id='selection-001')
        paid_ids = self.paid_selection_tasks(session, started)
        base = json.loads((session.directory / 'base-selection.private.json').read_bytes())
        candidate = dict(base, checkpoint_sha256=trained['checkpoint_path_sha256'])
        candidate['tasks'] = [dict(row) for row in base['tasks']]
        candidate['tasks'][0]['score'] = 0
        candidate['tasks'][1]['score'] = 1
        candidate['tasks'][2]['score'] = 1
        result = session.record_selection_scored(
            attempt_id='selection-001', result=candidate,
            paid_attempt_ids=paid_ids)
        self.assertEqual(result['score_wins'], 2)
        self.assertEqual(result['regressions_vs_incumbent'], 1)
        self.assertFalse(result['promoted'])
        self.assertEqual(result['selected_checkpoint_path_sha256'],
                         session.intent['base_checkpoint_sha256'])

    def test_paid_result_tamper_is_detected_on_restart(self):
        frozen, session = self.campaign()
        session.dispatch_paid(
            attempt_id='researcher-001', category='researcher_inference',
            work={'round': 1}, request={'prompt': 'train only'},
            reserve_usd='1', resource_reservation={'researcher_calls': '1'},
            provider=lambda _: {'text': 'proposal'})
        path = session.directory / 'researcher-001.result.private.json'
        path.write_bytes(path.read_bytes().replace(b'proposal', b'forgery '))
        with self.assertRaisesRegex(ValueError, 'paid_result_bytes_changed'):
            frozen.open_campaign(session.directory, cell_id=matrix.CELLS[0],
                                 researcher_id='astra', now=lambda: self.clock[0])


if __name__ == '__main__':
    unittest.main()
