"""Synthetic restart authority/dispatch fixtures; no real clients or credit."""
from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_training_restart_v1 as subject
from enterprise_fallback.odoo18 import tinker_trial_recovery_v1 as recovery
from tests import test_tinker_trial_recovery_v1 as fixtures


class RestartEntryTests(unittest.TestCase):
    def fixture(self,root):
        stage,prior,authority,inputs=fixtures.RecoveryTests().fixture(root)
        inputs.training.update({'optimizer_steps':192,'seed':23})
        inputs.training_sha='b'*64;inputs.plan={'models':{'teacher':'gpt-6-sol'}}
        inputs.datums=['synthetic-datum'];inputs.scheduled_tokens=1
        inputs.origin_metadata=[];inputs.execution_native_epoch='v14';inputs.execution_native_binding_sha256='c'*64
        path=stage/'restart.private.json';recovery.base.write(path,authority)
        kwargs={'plan_path':'unused','plan_sha':'d'*64,'manifest_path':'unused','manifest_sha':'e'*64,
            'output_root':stage/authority['new_output_name'],'restart_authority_path':path,
            'restart_authority_sha':recovery.base.digest(path.read_bytes()),'prior_output_root':prior,
            'execute':True,'trust_owned_rendered':True}
        return stage,prior,authority,inputs,kwargs

    def test_dispatch_uses_scoped_service_and_original_formats_without_mutating_v1(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();stage,prior,_authority,inputs,kwargs=self.fixture(root)
            before=(stage/'consumed.private.json').read_bytes();original_factory=subject.base.no_retry_service_class
            seen=[]
            def fake_sdk(_inputs,out):
                self.assertTrue(list(stage.glob('tinker-fresh-restart-authority-*-consumed.private.json')))
                self.assertTrue((out/'training-data-lineage.private.json').exists())
                service=globals()['no_retry_service_class']()
                holder=service._get_session_holder.__globals__['InternalClientHolder']
                self.assertFalse(holder._should_pause_on_billing(object(),402,'synthetic'))
                seen.append('synthetic-no-network-dispatch')
                return {'checkpoint_path':'synthetic-result-sentinel','optimizer_steps_completed':192}
            with patch.object(recovery,'ROOT',root),patch.object(subject.data,'load_inputs',return_value=inputs), \
                 patch.object(subject.base,'train_real',fake_sdk),patch.dict('os.environ',{'TINKER_API_KEY':'synthetic-no-network-key'}):
                result=subject.run(**kwargs)
            self.assertEqual(result['optimizer_steps_completed'],192);self.assertEqual(len(seen),1)
            self.assertIs(subject.base.no_retry_service_class,original_factory)
            self.assertEqual((stage/'consumed.private.json').read_bytes(),before)
            request=json.loads((kwargs['output_root']/'training-request.private.json').read_bytes())
            self.assertEqual(request['schema'],'envloop-odoo20-tinker-training-request-v1')
            self.assertTrue(request['explicit_fresh_restart']['fresh_base_model_attempt'])
            self.assertFalse(request['explicit_fresh_restart']['prior_unknown_forward_backward_resubmitted'])

    def test_402_or_generic_ready_evidence_never_dispatches(self):
        for changed in ({'provider_http_status':402,'status':'not_ready'}, {'status_code':200,'actual_authenticated_tinker_read':True}):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();stage,_prior,authority,inputs,kwargs=self.fixture(root)
                access=stage/'bad-access.private.json';recovery.base.write(access,changed)
                authority['billing_access_receipt_ref']={'path':str(access),'sha256':recovery.base.digest(access.read_bytes())}
                new=stage/'changed-authority.private.json';recovery.base.write(new,authority)
                kwargs.update(restart_authority_path=new,restart_authority_sha=recovery.base.digest(new.read_bytes()))
                with patch.object(recovery,'ROOT',root),patch.object(subject.data,'load_inputs',return_value=inputs), \
                     patch.object(subject.base,'train_real',side_effect=AssertionError('No provider setup before access authority')):
                    with self.assertRaises(subject.base.TrainingError):subject.run(**kwargs)
                self.assertFalse(list(stage.glob('tinker-fresh-restart-authority-*-consumed.private.json')))

    def test_uncertain_fresh_attempt_consumes_authority_without_replaying_or_deleting_old_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();stage,_prior,_authority,inputs,kwargs=self.fixture(root)
            calls=[];before=(stage/'consumed.private.json').read_bytes()
            def uncertain(_inputs,_out):calls.append('synthetic-dispatch');raise RuntimeError('synthetic uncertain')
            with patch.object(recovery,'ROOT',root),patch.object(subject.data,'load_inputs',return_value=inputs), \
                 patch.object(subject.base,'train_real',uncertain),patch.dict('os.environ',{'TINKER_API_KEY':'synthetic-no-network-key'}):
                with self.assertRaises(RuntimeError):subject.run(**kwargs)
                with self.assertRaises(subject.base.TrainingError):subject.run(**kwargs)
            self.assertEqual(calls,['synthetic-dispatch'])
            self.assertEqual(len(list(stage.glob('tinker-fresh-restart-authority-*-consumed.private.json'))),1)
            self.assertEqual((stage/'consumed.private.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
