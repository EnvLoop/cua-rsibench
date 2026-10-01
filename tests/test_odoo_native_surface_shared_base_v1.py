"""Current real factory injection, with synthetic metadata only; no native/provider."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from tests import test_odoo_native_surface_final_worker_v1 as fixture_module
save=fixture_module.save
from enterprise_fallback.odoo18 import native_surface_shared_base_v1 as bridge
from enterprise_fallback.odoo18 import native_surface_final_worker_v1 as final_source
from enterprise_fallback.odoo18 import native_surface_workers_v11 as workers


class SharedBaseBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.FinalWorkerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.study=SimpleNamespace(plan=self.fixture.gate.plan,ratification=self.fixture.gate.frozen.ratification,
            ratification_path=self.fixture.protocol.ratification_path,ratification_sha256=self.fixture.gate.frozen.ratification_sha256)
        nonce='a'*32
        proof={'schema':workers.TRAIN_CONTROL_SCHEMA,'status':workers.TRAIN_CONTROL_STATUS,'split':'train','family':'purchase',
            'run_nonce_hex':nonce,'run_nonce_sha256':workers.digest(nonce.encode()),
            'native_adapter_binding_sha256':self.fixture.binding['native_adapter_binding']['binding_sha256'],
            'native_worker_binding_sha256':self.fixture.binding['binding_sha256'],
            'independent_baseline_reward':0.0,'independent_positive_reward':1.0,'independent_wrong_object_reward':0.0,
            'source_visual_review_pending':False,'fixture_only_not_native_qualification':True}
        proof.update({k:True for k in ('full_pre_web_filestore_reset_exact','protected_post_web_source_bytes_equal',
            'source_attachment_readback','original_services_restored','source_visual_review_verified','native_service_readiness_verified')})
        proof.update({k:'b'*64 for k in ('attempt_sha256','audit_sha256','plan_sha256','source_review_sha256',
            'source_frame_sha256','source_asset_sha256','native_service_readiness_receipt_sha256')})
        proof.update({k:0 for k in ('old_positive_credit','model_attempts','official_final_tasks_admitted')})
        self.control_path=self.fixture.protocol.work/'synthetic-train-proof.private.json';self.control_sha=save(self.control_path,proof)

    def run_bridge(self,callback):
        with patch.object(bridge.execution,'_verify_base_freeze',return_value={'synthetic_freeze_only':True}), \
             patch.object(bridge.execution,'run_odoo_shared_base',side_effect=callback):
            return bridge.run_odoo_shared_base(self.study,lambda row:row,native_binding_path=self.fixture.binding_path,
                native_binding_file_sha256=self.fixture.binding_sha,train_control_path=self.control_path,train_control_sha256=self.control_sha,
                worker_dir=self.fixture.worker_dir,local_cost_authority_path=self.fixture.cost_path,local_cost_authority_sha256=self.fixture.cost_sha)

    def test_existing_runner_gets_current_factory_and_actual_selection_worker_api(self):
        def runner(study,reconciler,**kwargs):
            factory=kwargs['worker_factory']
            worker=factory(worker_dir=self.fixture.worker_dir,private_output_root=self.fixture.protocol.work,
                ratification_path=self.study.ratification_path,ratification_sha256=self.study.ratification_sha256,
                expected_runtime_sha256=self.fixture.binding['binding_sha256'],
                expected_verifier_sha256=self.fixture.cell['matched_bindings']['verifier'],
                local_cost_authority_path=self.fixture.cost_path,local_cost_authority_sha256=self.fixture.cost_sha,
                allow_base_model=True,expected_base_checkpoint_sha256=self.fixture.cell['base']['bindings']['checkpoint'],enable_live=False)
            self.assertEqual(worker.runtime_sha256,self.fixture.binding['binding_sha256'])
            self.assertEqual(worker.verifier_sha256,self.fixture.cell['matched_bindings']['verifier'])
            self.assertIs(type(worker.environment),workers._model_modules(self.fixture.binding)[1].RealOdooSelectionEnvironment)
            self.assertTrue(worker.allow_base_model)
            return {'source_only_factory_called':True}
        with patch.object(final_source,'_modules',side_effect=AssertionError('no final body')):
            result=self.run_bridge(runner)
        self.assertTrue(result['source_only_factory_called'])

    def test_wrong_runtime_or_unfrozen_final_source_refuses_runner(self):
        for field in ('runtime','source_snapshot'):
            previous=self.fixture.cell['matched_bindings'][field];self.fixture.cell['matched_bindings'][field]='0'*64
            with self.assertRaisesRegex(workers.NativeMaterialWorkerError,'current_surface_binding'):
                self.run_bridge(lambda *a,**k:self.fail('runner must not open'))
            self.fixture.cell['matched_bindings'][field]=previous

    def test_historical_train_proof_refuses_current_factory(self):
        raw=self.control_path.read_bytes().replace(b'v11',b'v8')
        self.control_path.write_bytes(raw)
        self.control_sha=workers.digest(raw)
        with self.assertRaisesRegex(workers.NativeMaterialWorkerError,'fresh_native_train_control'):
            self.run_bridge(lambda *a,**k:self.fail('runner must not open'))
