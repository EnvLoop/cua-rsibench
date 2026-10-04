"""Detached lifetime, one-child and no-replay host tests; no native runtime."""
from pathlib import Path
import os
import signal
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools import supervise_gitlab_selection_reference_continuation_v1 as s


class Child:
    def __init__(self,waits):self.waits=iter(waits);self.signals=[];self.kills=0;self.wait_calls=[];self.pid=123;self.before_wait=None
    def wait(self,timeout):
        self.wait_calls.append(round(timeout,2))
        if self.before_wait is not None:
            callback=self.before_wait;self.before_wait=None;callback()
        value=next(self.waits)
        if value=='timeout':raise subprocess.TimeoutExpired('one-owned-worker',timeout)
        return value
    def poll(self):return None
    def send_signal(self,value):self.signals.append(value)
    def kill(self):self.kills+=1


class SupervisorTests(unittest.TestCase):
    def test_worker_failure_has_one_wait_no_signal_and_no_restart(self):
        child=Child([1]);result=s._wait_once(child,86400,1500)
        self.assertEqual(child.wait_calls,[86400]);self.assertEqual(result['exit_code'],1)
        self.assertEqual(child.signals,[]);self.assertEqual(child.kills,0);self.assertEqual(result['automatic_worker_restarts'],0)

    def test_host_expiry_signals_same_worker_once_and_waits_original_cleanup_grace(self):
        child=Child(['timeout',1]);result=s._wait_once(child,86400,1500)
        self.assertEqual(child.signals,[signal.SIGTERM]);self.assertEqual(child.wait_calls,[86400,1500]);self.assertEqual(child.kills,0)
        self.assertTrue(result['host_expiry_sigterm_sent_once']);self.assertFalse(result['cleanup_grace_hard_stop'])

    def test_grace_expiry_hard_stops_only_known_worker_and_never_infers_restoration(self):
        child=Child(['timeout','timeout',-9]);result=s._wait_once(child,86400,1500)
        self.assertEqual(child.signals,[signal.SIGTERM]);self.assertEqual(child.kills,1)
        self.assertEqual(child.wait_calls,[86400,1500,10]);self.assertTrue(result['cleanup_grace_hard_stop'])
        self.assertFalse(result['cleanup_success_inferred'])

    def test_unavailable_hard_stop_wait_is_terminal_uncertainty_without_second_signal(self):
        child=Child(['timeout','timeout','timeout']);result=s._wait_once(child,86400,1500)
        self.assertEqual(child.signals,[signal.SIGTERM]);self.assertEqual(child.kills,1)
        self.assertIsNone(result['exit_code']);self.assertTrue(result['hard_stop_terminal_wait_unavailable'])

    def test_detach_has_no_chat_pipes_or_tty_and_uses_private_file_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);seen={}
            def popen(argv,**kwargs):
                seen.update(kwargs);seen['stdout_name']=kwargs['stdout'].name;seen['stderr_name']=kwargs['stderr'].name
                return SimpleNamespace(pid=123)
            result=s._spawn_detached(['exact','supervisor'],stage,popen=popen)
            self.assertEqual(result.pid,123);self.assertTrue(seen['start_new_session']);self.assertTrue(seen['close_fds'])
            self.assertEqual(seen['stdin'],subprocess.DEVNULL);self.assertEqual(seen['env']['PYTHONPATH'],'.:src:tests')
            for name in ('supervisor.stdout.private.log','supervisor.stderr.private.log'):
                self.assertEqual((stage/name).stat().st_mode&0o777,0o600)

    def test_no_execute_does_not_read_approval_or_spawn(self):
        with patch.object(s,'_approval') as approval,patch.object(s,'_spawn_detached') as spawn:
            with self.assertRaisesRegex(ValueError,'explicit_root'):s.launch(review_path='missing',review_sha256='a'*64)
            approval.assert_not_called();spawn.assert_not_called()

    def test_consumed_launch_intent_refuses_second_supervisor(self):
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);review=stage/'review.private.json';s.c.world.write(review,{})
            authority={'output_root':str(stage/'controls.private')}
            with patch.object(s,'_approval',return_value=authority),patch.object(s.c,'source_binding',return_value={}),patch.object(s,'_spawn_detached',return_value=SimpleNamespace(pid=1)) as spawn:
                s.launch(review_path=review,review_sha256=s.c.ref(review)['sha256'],execute=True)
                with self.assertRaises(FileExistsError):s.launch(review_path=review,review_sha256=s.c.ref(review)['sha256'],execute=True)
                self.assertEqual(spawn.call_count,1)

    def test_proposal_path_cannot_be_used_as_root_approval(self):
        with patch.object(s.c,'check_authority') as check:
            with self.assertRaisesRegex(ValueError,'approved_path'):s._approval(s.c.STAGE/'proposal.private.json','a'*64)
            check.assert_not_called()

    def supervise_fixture(self,child,*,metadata_error=False,spawn_cancel=False,wait_cancel=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);stage=Path(temporary.name).resolve()
        review=stage/s.APPROVAL_NAME;s.c.world.write(review,{})
        authority={'output_root':str(stage/'controls.private'),'host_worker_seconds':86400,'host_cleanup_grace_seconds':1500,'native_source146':{},'controller_binding':{}}
        argv=[s.PYTHON,str(s.SUPERVISOR),'supervise','--review-path',str(review),'--review-sha256',s.c.ref(review)['sha256']]
        s.c.world.write(stage/'detached-launch-intent.private.json',{'argv':argv,'authority_ref':s.c.ref(review),'source_binding':{}})
        handlers={}
        def install(signum,handler):handlers[signum]=handler
        def popen(*args,**kwargs):
            if spawn_cancel:handlers[signal.SIGTERM](signal.SIGTERM,None)
            if wait_cancel:child.before_wait=lambda:handlers[signal.SIGTERM](signal.SIGTERM,None)
            return child
        with patch.object(s,'_approval',return_value=authority),patch.object(s.c,'source_binding',return_value={}),patch.object(s.os,'getsid',return_value=os.getpid()),patch.object(s.signal,'signal',side_effect=install),patch.object(s.subprocess,'Popen',side_effect=popen),patch.object(s.c.world,'source_hashes',side_effect=RuntimeError('fixture terminal metadata failure') if metadata_error else None,return_value={}):
            with self.assertRaises((RuntimeError,s.SupervisorCancelled)):
                s.supervise(review_path=review,review_sha256=s.c.ref(review)['sha256'])
        return stage,s.c.private(stage/'supervisor-unavailable.private.json')

    def test_full_supervise_metadata_failure_after_terminal_unknown_never_repeats_shutdown(self):
        child=Child(['timeout','timeout','timeout']);stage,receipt=self.supervise_fixture(child,metadata_error=True)
        self.assertEqual(child.wait_calls,[86400,1500,10]);self.assertEqual(child.signals,[signal.SIGTERM]);self.assertEqual(child.kills,1)
        self.assertTrue(receipt['same_worker_shutdown_after_supervisor_error']['hard_stop_terminal_wait_unavailable'])

    def test_supervisor_sigterm_at_popen_return_is_deferred_until_known_worker_pid(self):
        child=Child([-15]);stage,receipt=self.supervise_fixture(child,spawn_cancel=True)
        self.assertEqual(child.wait_calls,[1500]);self.assertEqual(child.signals,[signal.SIGTERM]);self.assertEqual(child.kills,0)
        self.assertEqual(s.c.private(stage/'worker-start.private.json')['pid'],123)
        self.assertTrue(receipt['same_worker_shutdown_after_supervisor_error']['supervisor_cancel_requested'])

    def test_supervisor_sigterm_during_wait_uses_same_worker_and_uncertainty_receipt(self):
        child=Child([-15]);stage,receipt=self.supervise_fixture(child,wait_cancel=True)
        self.assertEqual(child.wait_calls,[86400,1500]);self.assertEqual(child.signals,[signal.SIGTERM]);self.assertEqual(child.kills,0)
        self.assertEqual(receipt['error_type'],'SupervisorCancelled')
        self.assertFalse(receipt['same_worker_shutdown_after_supervisor_error']['cleanup_success_inferred'])


if __name__=='__main__':unittest.main()
