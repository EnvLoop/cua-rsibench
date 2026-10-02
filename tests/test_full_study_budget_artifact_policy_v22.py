"""Actual RPC→saved/reset→policy adapter; synthetic provider/native surfaces."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from cursibench import full_study_runtime_v2 as runtime
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineProof,ActorDeadlineReached
from tests import test_full_study_campaign_dispatch_v1 as fixtures
from tests import v22_policy_runtime_fixture as policy_fixture
from tests import v22_budget_episode_fixture as episode_fixture


class BudgetArtifactTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FullStudyDispatchTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.study=policy_fixture.study(self.f.frozen())

    def test_actual_source_adapter_requires_saved_reset_close_and_retains_unknown_for_all_five_slots(self):
        task=self.study.task_views('desktop-native')['selection'][0]
        for owner in ['shared-base',*runtime.matrix.RESEARCHERS]:
            with self.subTest(owner=owner):
                descriptor,receipt,guests=episode_fixture.create(self.study,owner,self.study.repo_root/'work'/('budget-fixture-'+owner),task)
                self.assertEqual(receipt['performance']['score'],0);self.assertTrue(all(g.killed for g in guests))
                self.assertEqual(receipt['inference']['completed_model_response_count'],0)
                self.assertEqual(receipt['inference']['retained_error_result_count'],1)
                self.assertIsNone(receipt['billing']['actual_usd']);self.assertFalse(receipt['formal_registration_performed'])
                self.assertFalse(receipt['inference']['unknown_response_is_completed'])
                out=Path(descriptor['evaluator']);saved=out/'saved-state.private.json';raw=saved.read_bytes()
                saved.write_bytes(raw+b' ')
                with self.assertRaises(ValueError):runtime.verify_budget_artifacts(self.study,owner,descriptor)
                saved.write_bytes(raw)
                reset=out/'reset.private.json';raw=reset.read_bytes();reset.unlink()
                with self.assertRaises((ValueError,FileNotFoundError)):runtime.verify_budget_artifacts(self.study,owner,descriptor)
                runtime.campaign._private_write_new(reset,raw)
                terminal=Path(descriptor['batch'])/'sampler-process/child-terminal.private.json'
                value=json.loads(terminal.read_bytes());value['provider_shutdown_acknowledged']=False
                terminal.write_bytes(runtime.policy.canonical(value))
                with self.assertRaises(ValueError):runtime.verify_budget_artifacts(self.study,owner,descriptor)

    def test_real_paid_wrappers_preserve_only_typed_deadline_and_do_not_reinvoke_provider(self):
        task=self.study.task_views('desktop-native')['selection'][0]
        session=runtime.SharedBaseSession(self.study,'desktop-native')
        self.f.runtime_gate_mock.side_effect=None
        self.f.runtime_gate_mock.return_value={'runtime_spec_sha256':'d'*64,'toy_public_receipt_sha256':'e'*64,'runtime_gate_source_sha256':'f'*64}
        request={'cell_id':'desktop-native','selection_attempt':session.attempt_id,**task,
            'checkpoint_path_sha256':session.started['checkpoint_path_sha256'],'frame_sha256':'f'*64}
        proof=ActorDeadlineProof(720.,716.5,720.,3.5,'actor_deadline_reached_during_wait',True,False)
        calls=[]
        def provider(_):calls.append(1);raise ActorDeadlineReached(proof)
        identifier=session.attempt_id+'-sample-000'
        with self.assertRaises(ActorDeadlineReached):session.dispatch_paid(attempt_id=identifier,category='tinker',
            work=request,request=request,reserve_usd='2000',resource_reservation={},provider=provider)
        self.assertEqual(calls,[1]);self.assertEqual(session.budget.owner_attempts(session.owner)[identifier]['status'],'uncertain')
        self.assertFalse((session.directory/'paid'/(identifier+'.result.private.json')).exists())
        with self.assertRaises(ValueError):session.dispatch_paid(attempt_id=identifier,category='tinker',
            work=request,request=request,reserve_usd='2000',resource_reservation={},provider=provider)
        self.assertEqual(calls,[1])
        request_reset={**request,'phase':'reset','lease_seconds':1200}
        request_reset.pop('frame_sha256')
        session.dispatch_paid(attempt_id=session.attempt_id+'-reset-000',category='e2b',work=request_reset,request=request_reset,
            reserve_usd='1000',resource_reservation={'e2b_sandbox_hours':'0.333333334','e2b_peak_concurrency':'1'},provider=lambda _: {'status':'active'})
        with self.assertRaises(ValueError):session.dispatch_paid(attempt_id=session.attempt_id+'-reset-001',category='e2b',
            work=request_reset,request=request_reset,reserve_usd='1000',resource_reservation={'e2b_sandbox_hours':'0.333333334','e2b_peak_concurrency':'1'},provider=lambda _: {'status':'active'})

    def test_real_campaign_unknown_budget_performance_freezes_using_actual_incumbent_rule(self):
        from tests.test_full_study_campaign_dispatch_v1 import sha
        cell='desktop-native';owner='astra'
        base=policy_fixture.base_receipt(self.study,cell)
        session=self.study.open_campaign(self.study.repo_root/'work/v2-complete-campaign',cell_id=cell,researcher_id=owner,now=lambda:self.f.clock[0])
        self.f.runtime_gate_mock.side_effect=None
        self.f.runtime_gate_mock.return_value={'runtime_spec_sha256':'d'*64,'toy_public_receipt_sha256':'e'*64,'runtime_gate_source_sha256':'f'*64}
        with runtime.runtime_context(self.study):
            trained=self.f.trained_candidate(session)
            started=session.start_selection_attempt(round_index=1,attempt_id='selection-v22-fixture')
            ids=self.f.paid_selection_tasks(session,started)
        descriptor,receipt,_=episode_fixture.create(self.study,owner,self.study.repo_root/'work/campaign-budget-episode',
            started['selection_tasks'][0],attempt_id=started['attempt_id'],checkpoint_path='tinker://fake/sampler_weights/ckpt-1',session=session)
        identifier=receipt['sample_paid_attempt_id']
        session.authorize_verified_budget_stop(identifier,verification=descriptor)
        ids=[r['data']['attempt_id'] for r in session._events('paid_intent') if r['data']['attempt_id'].startswith(started['attempt_id']+'-')]
        rows=[{'task_id':task['task_id'],'package_sha256':task['package_sha256'],'score':0,'saved_state_sha256':'d'*64,'verifier_receipt_sha256':'e'*64,'reset_receipt_sha256':'f'*64}
              for task in started['selection_tasks']]
        rows[0].update(saved_state_sha256=receipt['evidence_sha256']['saved-state.private.json'],
            verifier_receipt_sha256=receipt['evidence_sha256']['verifier.private.json'],reset_receipt_sha256=receipt['evidence_sha256']['reset.private.json'])
        result={'schema':'cua-full-study-selection-saved-result-v1','cell_id':cell,
            'checkpoint_sha256':started['checkpoint_path_sha256'],'evaluator_isolated':True,'tasks':rows}
        scored=session.record_selection_scored(attempt_id=started['attempt_id'],result=result,paid_attempt_ids=ids)
        self.assertFalse(scored['promoted'])
        frozen=session.freeze_selection()
        self.assertEqual(frozen['selected_checkpoint_sha256'],session.intent['base_checkpoint_sha256'])
        self.assertEqual(session.budget.owner_attempts(session.owner)[identifier]['status'],'uncertain')
        self.assertIsNone(session.budget.snapshot()['actual_total_usd'])
        self.assertFalse((session.directory/(identifier+'.result.private.json')).exists())
        with self.assertRaises(ValueError):session.authorize_verified_budget_stop(identifier,verification=descriptor)
