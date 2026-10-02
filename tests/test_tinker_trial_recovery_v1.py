"""Offline recovery primitives: synthetic IDs only, no actual SDK clients."""
import asyncio
from pathlib import Path
import json
import tempfile
import time
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import tinker_trial_recovery_v1 as recovery
from tinker.lib.api_future_impl import _APIFuture,_TransportError,_TransportErrorKind
from tinker.lib.internal_client_holder import InternalClientHolder
from tinker.lib.public_interfaces.service_client import ServiceClient


class RecoveryTests(unittest.TestCase):
    def test_metadata_is_durable_before_any_future_polling_and_duplicate_id_never_repolls(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve();out.chmod(0o700);seen=[]
            def delegate(*args,**kwargs):
                files=list(out.glob('sdk-future-*.private.json'))
                self.assertEqual(len(files),1)
                value=json.loads(files[0].read_bytes())
                self.assertEqual(value['request_id'],'synthetic-future-id')
                self.assertTrue(value['before_sdk_future_result_polling'])
                self.assertEqual(value['training_seq_id'],39)
                seen.append('poll-start');return 'synthetic-handle'
            tracked=recovery.future_metadata_factory(out,delegate)
            holder=SimpleNamespace(get_session_id=lambda:'synthetic-session')
            def _submit_chunk():
                request_id=38
                return tracked(dict,holder,SimpleNamespace(request_id='synthetic-future-id'),
                               request_type='ForwardBackward',request_start_time=1.0)
            self.assertEqual(_submit_chunk(),'synthetic-handle')
            with self.assertRaises(FileExistsError):_submit_chunk()
            self.assertEqual(seen,['poll-start'])

    def test_owned_402_is_immediate_fatal_and_does_not_mutate_sdk_or_v1_classes(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);out.chmod(0o700)
            service=recovery.recovery_ready_service_class(out)
            holder_class=service._get_session_holder.__globals__['InternalClientHolder']
            self.assertIsNot(holder_class,InternalClientHolder)
            self.assertFalse(holder_class._should_pause_on_billing(object(),402,'synthetic billing blocked'))
            self.assertIs(ServiceClient._get_session_holder.__globals__['InternalClientHolder'],InternalClientHolder)
            actual=object.__new__(_APIFuture)
            actual.holder=SimpleNamespace(_should_pause_on_billing=lambda *_:False,get_telemetry=lambda:None)
            actual.untyped_future=SimpleNamespace(request_id='synthetic-future-id')
            actual.model_cls=dict
            error=_TransportError(kind=_TransportErrorKind.FATAL,status_code=402,detail='synthetic402',exception=RuntimeError('synthetic402'))
            state=SimpleNamespace(connection_error_retries=0,bad_request_retries=0)
            with self.assertRaisesRegex(ValueError,'status 402'):
                asyncio.run(actual._handle_transport_error(error,state,0,0.0))

    def fixture(self,root):
        stage=root/'work/stage.private';stage.mkdir(parents=True,mode=0o700)
        for name in recovery.EXECUTION_SOURCE_FILES:
            copy=root/name;copy.parent.mkdir(parents=True,exist_ok=True)
            copy.write_bytes((recovery.ROOT/name).read_bytes())
        execution={name:recovery.base.digest((root/name).read_bytes()) for name in recovery.EXECUTION_SOURCE_FILES}
        prior=stage/'prior.private';prior.mkdir(mode=0o700)
        write=recovery.base.write
        request={'dataset_identity':'a'*64,'model':'Qwen/Qwen3.8-27B','fixed_training_settings':{'optimizer_steps':192}}
        write(prior/'training-request.private.json',request)
        write(prior/'session-create-result.private.json',{'status':'completed','result':{'session_id':'synthetic-session'}})
        write(prior/'lora-create-result.private.json',{'status':'completed','result':{'model_id':'synthetic-model'}})
        write(prior/'step-0018-optim-result.private.json',{'status':'completed'})
        write(prior/'step-0019-forward-backward-deadline.private.json',{'status':'synthetic-uncertain'})
        claim=stage/'consumed.private.json'
        write(claim,{'dataset_identity':'a'*64,'output_root':str(prior),'automatic_replay_authorized':False})
        from tools.check_odoo20_tinker_access_v1 import result_receipt
        terminal_end=time.time()
        terminal_path=stage/'terminal.private.json';write(terminal_path,{'exit_code':1,'automatic_restarts':0,'pid':2147483000,'started_at':terminal_end-1,'ended_at':terminal_end})
        terminal_ref={'path':str(terminal_path),'sha256':recovery.base.digest(terminal_path.read_bytes())}
        raw_path=stage/'capabilities.private.json';write(raw_path,{'supported_models':[{'model_name':recovery.base.MODEL,'trainable':True,'sampleable':True}]})
        raw_ref={'path':str(raw_path),'sha256':recovery.base.digest(raw_path.read_bytes())}
        receipt=result_receipt(terminal_ref=terminal_ref,terminal={'exit_code':1,'automatic_restarts':0,'ended_at':terminal_end},
            started_at=terminal_end,ended_at=terminal_end+0.1,capabilities={'supported_models':[{'model_name':recovery.base.MODEL,'trainable':True,'sampleable':True}]},
            status_code=200,error_type=None,close_returned=True,raw_provider_evidence_ref=raw_ref)
        billing=stage/'billing.private.json';write(billing,receipt)
        authority={'schema':recovery.RESTART_SCHEMA,'dataset_identity':'a'*64,'model':request['model'],'optimizer_steps':192,
            'prior_training_request_sha256':recovery.base.digest((prior/'training-request.private.json').read_bytes()),
            'prior_consumed_claim_ref':{'path':claim.name,'sha256':recovery.base.digest(claim.read_bytes())},
            'retire_prior_attempt':True,'start_from_fresh_base':True,'carry_prior_model_state':False,
            'automatic_replay_authorized':False,'fresh_restart_authorized':True,
            'billing_access_receipt_ref':{'path':str(billing),'sha256':recovery.base.digest(billing.read_bytes())},
            'prior_terminal_ref':terminal_ref,'execution_source_sha256s':execution,
            'new_attempt_nonce':'f'*32,'new_output_name':'fresh-explicit.private'}
        inputs=SimpleNamespace(namespace=stage,identity='a'*64,training={'model':request['model'],'optimizer_steps':192})
        return stage,prior,authority,inputs

    def test_explicit_restart_binds_retired_claim_and_billing_without_touching_old_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();stage,prior,authority,inputs=self.fixture(root)
            claim_before=(stage/'consumed.private.json').read_bytes()
            path=stage/'restart.private.json';recovery.base.write(path,authority)
            with patch.object(recovery,'ROOT',root):
                result=recovery.checked_restart_authority(path,recovery.base.digest(path.read_bytes()),inputs=inputs,prior_root=prior)
                self.assertFalse(result['prior_optimizer_state_recoverable_proved'])
                self.assertFalse(result['unknown_prior_forward_backward_resubmitted'])
                self.assertEqual(recovery.readonly_status_queries(result)[0],('get_training_run','synthetic-model'))
            self.assertEqual((stage/'consumed.private.json').read_bytes(),claim_before)
            self.assertFalse((stage/'fresh-explicit.private').exists())

    def test_positive_normal_output_name_and_exact_capabilities_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();stage,prior,authority,inputs=self.fixture(root)
            authority['new_output_name']='tinker-sol6-native14-training-02.private'
            path=stage/'restart.private.json';recovery.base.write(path,authority)
            with patch.object(recovery,'ROOT',root):
                result=recovery.checked_restart_authority(path,recovery.base.digest(path.read_bytes()),inputs=inputs,prior_root=prior)
                self.assertEqual(Path(result['new_output_root']).name,'tinker-sol6-native14-training-02.private')
                reference=authority['billing_access_receipt_ref']
                access=json.loads(Path(reference['path']).read_bytes())
                for index,change in enumerate(({'owned_close_awaited':False},{'checker_source_sha256':'0'*64},{'injected_authority':True})):
                    changed=stage/f'tampered-access-{index}.private.json';recovery.base.write(changed,{**access,**change})
                    ref={'path':str(changed),'sha256':recovery.base.digest(changed.read_bytes())}
                    with self.assertRaises(recovery.base.TrainingError):recovery.checked_access(ref,authority['prior_terminal_ref'])

    def test_replay_or_uncorrected_billing_or_state_carry_is_rejected(self):
        for defect in ('replay','billing','carry','dataset','source','live_pid','early_terminal'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();stage,prior,authority,inputs=self.fixture(root)
                if defect=='replay':authority['automatic_replay_authorized']=True
                if defect=='carry':authority['carry_prior_model_state']=True
                if defect=='dataset':authority['dataset_identity']='b'*64
                if defect=='source':
                    name=recovery.EXECUTION_SOURCE_FILES[0];(root/name).write_text('synthetic source drift')
                if defect in ('live_pid','early_terminal'):
                    terminal=stage/'changed-terminal.private.json'
                    old=json.loads(Path(authority['prior_terminal_ref']['path']).read_bytes())
                    if defect=='live_pid':old['pid']=os.getpid()
                    if defect=='early_terminal':old['ended_at']=0
                    recovery.base.write(terminal,old)
                    authority['prior_terminal_ref']={'path':str(terminal),'sha256':recovery.base.digest(terminal.read_bytes())}
                if defect=='billing':
                    billing=stage/'billing-failed.private.json';recovery.base.write(billing,{'status_code':402,'actual_authenticated_tinker_read':True})
                    authority['billing_access_receipt_ref']={'path':str(billing),'sha256':recovery.base.digest(billing.read_bytes())}
                path=stage/'restart.private.json';recovery.base.write(path,authority)
                with patch.object(recovery,'ROOT',root),self.assertRaises(recovery.base.TrainingError):
                    recovery.checked_restart_authority(path,recovery.base.digest(path.read_bytes()),inputs=inputs,prior_root=prior)


if __name__=='__main__':unittest.main()
