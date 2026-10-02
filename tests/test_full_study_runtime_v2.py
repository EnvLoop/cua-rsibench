import copy
import json
from pathlib import Path
import unittest

from cursibench import full_study_campaign_dispatch_v1 as old
from cursibench import full_study_runtime_v2 as runtime
from cursibench import full_study_policy_amendment_v2 as policy
from tests import test_full_study_campaign_dispatch_v1 as fixtures
from tests import test_full_study_final_dispatch_v1 as final_fixtures
from tests import v22_policy_runtime_fixture as v2fixture


class RuntimeGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.FullStudyDispatchTests();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.parent=old.FrozenStudy(repo_root=self.fixture.root,manifest_path=self.fixture.manifest_path,
            prepared_dir=self.fixture.prepared,ratification_path=self.fixture.ratification_path,
            public_commit_sha1=self.fixture.commit,
            witness_fetcher=lambda _:old._canonical(self.fixture.witness))
        self.amendment=policy.build(self.parent.plan,user_authorization_sha256='a'*64,
            pre_result_review_sha256='b'*64)
        self.manifest=runtime.build_manifest(self.parent.plan,self.amendment,
            parent_protocol_sha256=self.parent.manifest_sha256,ratification_sha256=self.parent.ratification_sha256,
            source_manifest_sha256=policy.sha(policy.canonical(runtime.source_manifest(Path(runtime.__file__).resolve().parents[2]))))
        self.study=runtime.FrozenStudy(qualified_parent=self.parent,amendment=self.amendment,
            manifest=self.manifest,witness_bytes=policy.canonical(runtime.witness(self.manifest)))

    def test_real_600_qualification_freeze_and_fresh_policy_witness_are_both_required(self):
        self.assertEqual(self.parent.plan['distinct_official_task_identities'],600)
        self.assertEqual(self.study.policy_manifest['initial_slot_task_results'],3000)
        with self.assertRaises(ValueError):
            runtime.FrozenStudy(qualified_parent=object(),amendment=self.amendment,manifest=self.manifest,witness_bytes=b'{}')
        forged=copy.deepcopy(self.manifest);forged['amendment_sha256']='d'*64
        with self.assertRaises(ValueError):
            runtime.FrozenStudy(qualified_parent=self.parent,amendment=self.amendment,manifest=forged,
                witness_bytes=policy.canonical(runtime.witness(forged)))

    def test_real_campaign_class_admits_high_quote_with_16h_compute_and_no_replay_still_enforced(self):
        owner=next(iter(self.study.parent.intents))
        v2fixture.base_receipt(self.study,owner[0])
        session=self.study.open_campaign(self.fixture.root/'work/new-v2',cell_id=owner[0],researcher_id=owner[1],
            now=lambda:self.fixture.clock[0])
        # This exercises actual resource/paid/source journaling using the real
        # inherited campaign class; the provider is a synthetic callback.
        result=session.dispatch_paid(attempt_id='v2-large-quote',category='storage_application',
            work={'operation':'synthetic meter'},request={'operation':'synthetic meter'},reserve_usd='50000',
            resource_reservation={},provider=lambda request:{'status':'completed'})
        self.assertEqual(result['result']['status'],'completed')
        session.reconcile_paid('v2-large-quote',actual_usd='60000',provider_usage_sha256='e'*64)
        self.assertFalse(session.budget.snapshot()['paid_dispatch_frozen'])
        with self.assertRaises(ValueError):
            session.dispatch_paid(attempt_id='v2-large-quote',category='storage_application',
                work={'operation':'synthetic meter'},request={'operation':'synthetic meter'},reserve_usd='50000',
                resource_reservation={},provider=lambda request:{'status':'completed'})
        self.fixture.clock[0]+=16*3600+1
        with self.assertRaisesRegex(ValueError,'sixteen_hour'):session._check_time()

    def test_final_before_real_24_chains_cannot_pass_a_dictionary_claim(self):
        envelope={'schema':'cua-full-study-policy-final-witness-v2','amendment_sha256':self.study.amendment_sha256,
            'policy_manifest_sha256':self.study.manifest_sha256,'qualified_final_witness':{}}
        with self.assertRaises((ValueError,FileNotFoundError)):
            runtime.FinalGate(self.study,matrix_manifest_path=self.fixture.root/'missing-matrix',
                prepared_matrix_dir=self.fixture.root/'missing-prepared',completion_index_path=self.fixture.root/'missing-24-chains',
                final_public_commit_sha1='a'*40,policy_final_witness_bytes=policy.canonical(envelope))

    def test_reporting_never_fills_unknown_cost_with_zero_or_an_old_500_limit(self):
        value=runtime.result_projection([{'performance_eligible':True,'cost_usd':None,'invoice_complete':False,
            'inference':{'status':'completion_unknown_after_actor_deadline'}}])
        self.assertIsNone(value['actual_total_usd']);self.assertFalse(value['provider_invoice_complete'])
        self.assertNotIn('500',runtime.paper_budget_wording())


class RealFinalGateTests(unittest.TestCase):
    def test_actual_24_private_chains_and_all_600_admissions_are_reopened(self):
        f=final_fixtures.FullStudyFinalDispatchTests();f.setUp()
        self.addCleanup(f.tearDown)
        gate,envelope,index=v2fixture.final_gate(f)
        study=gate.study
        self.assertEqual(len(gate.freezes),24)
        self.assertEqual(len(gate.qualified.initial_state_by_task),6)
        self.assertTrue(all(len(v)==100 for v in gate.qualified.initial_state_by_task.values()))
        value=json.loads(index.read_bytes());value['campaigns']=value['campaigns'][:-1];index.write_bytes(policy.canonical(value))
        with self.assertRaises(ValueError):
            runtime.FinalGate(study,matrix_manifest_path=f.matrix_path,prepared_matrix_dir=gate.prepared_matrix_dir,
                completion_index_path=index,final_public_commit_sha1='c'*40,
                policy_final_witness_bytes=policy.canonical(envelope))


class PreparationEntrypointTests(unittest.TestCase):
    def test_source_manifest_new_witness_and_real_cli_check_are_bound_before_any_provider(self):
        import importlib.util
        from unittest.mock import patch
        f=fixtures.FullStudyDispatchTests();f.setUp();self.addCleanup(f.tearDown)
        parent=f.frozen();amendment=policy.build(parent.plan,user_authorization_sha256='a'*64,pre_result_review_sha256='b'*64)
        folder=parent.repo_root/'work/policy-v22.private'
        runtime.prepare_policy_runtime(qualified_parent=parent,amendment=amendment,output=folder)
        witness=f.root/'work/parent-witness.private.json';old._private_write_new(witness,old._canonical(f.witness))
        source_path=Path(runtime.__file__).resolve().parents[2]/'tools/full_study_campaign_dispatch_v2.py'
        spec=importlib.util.spec_from_file_location('checked_cli_test',source_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original=old._fetch_immutable_witness
        def immutable(url,fetcher):
            if fetcher is not None:return original(url,fetcher)
            self.assertIn('/docs/evidence/full-study-pre-result-policy-witness-v2.json',url)
            return (folder/'pre-result-witness.json').read_bytes()
        args=['--policy-dir',str(folder),'--parent-witness',str(witness),'--policy-public-commit','c'*40,
            '--repo-root',str(f.root),'--manifest',str(f.manifest_path),'--prepared-dir',str(f.prepared),
            '--ratification',str(f.ratification_path),'--public-commit',f.commit,'check']
        with patch.object(old,'_fetch_immutable_witness',side_effect=immutable):
            self.assertEqual(module.main(args),0)
        value=json.loads((folder/'policy-amendment.private.json').read_bytes());value['direct_human_spending_authorized']=False
        (folder/'policy-amendment.private.json').write_bytes(policy.canonical(value))
        with patch.object(old,'_fetch_immutable_witness',side_effect=immutable):
            self.assertEqual(module.main(args),2)
