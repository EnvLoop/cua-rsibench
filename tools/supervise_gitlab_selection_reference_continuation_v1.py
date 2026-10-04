"""Durable detached, one-worker supervision of exact reference-only authority."""
from __future__ import annotations
import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from gitlab_world import v066_selection_reference_continuation_v1 as c

PYTHON = '/Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python'
SUPERVISOR = Path(__file__).resolve()
APPROVAL_NAME = c.ROOT_APPROVAL_NAME


class SupervisorCancelled(BaseException):
    pass


def _approval(review_path,review_sha256):
    path=Path(review_path).absolute()
    c.require(path==c.STAGE/APPROVAL_NAME,'supervisor_root_approved_path_required')
    authority=c.check_authority(path,review_sha256)
    c.require(authority['host_worker_seconds']==c.HOST_SECONDS and
        authority['host_cleanup_grace_seconds']==c.CLEANUP_GRACE_SECONDS and
        authority['one_worker_only'] is True and authority['automatic_worker_or_startup_retries']==0,
        'supervisor_exact_host_bounds_required')
    return authority


def _log(stage,name):
    fd=os.open(stage/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    return os.fdopen(fd,'wb',buffering=0)


def _spawn_detached(argv,stage,*,popen=subprocess.Popen):
    with _log(stage,'supervisor.stdout.private.log') as stdout,_log(stage,'supervisor.stderr.private.log') as stderr:
        return popen(argv,cwd=c.REPO,env={**os.environ,'PYTHONPATH':'.:src:tests','PYTHONDONTWRITEBYTECODE':'1'},
            stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)


def launch(*,review_path,review_sha256,execute=False):
    c.require(execute is True,'supervisor_explicit_root_launch_required')
    authority=_approval(review_path,review_sha256);stage=Path(authority['output_root']).parent
    c.require(not Path(authority['output_root']).exists() and not (stage/'worker-process-start.private.json').exists(),
        'supervisor_fresh_worker_namespace_required')
    argv=[PYTHON,str(SUPERVISOR),'supervise','--review-path',str(Path(review_path).absolute()),
        '--review-sha256',review_sha256]
    intent={'schema':'gitlab-continuation-detached-launch-v1','authority_ref':c.ref(review_path),
        'argv':argv,'cwd':str(c.REPO),'source_binding':c.source_binding(),
        'one_worker_only':True,'automatic_retries':0,'stdin':'DEVNULL','file_backed_stdout_stderr':True}
    c.world.write(stage/'detached-launch-intent.private.json',intent)
    try:
        child=_spawn_detached(argv,stage)
        receipt={'schema':'gitlab-continuation-detached-launch-start-v1','pid':child.pid,
            'intent_ref':c.ref(stage/'detached-launch-intent.private.json'),'authority_ref':c.ref(review_path),
            'detached_session_requested':True,'worker_replay_authorized':False}
        c.world.write(stage/'detached-launch-start.private.json',receipt)
        return receipt
    except BaseException as error:
        c.world.write(stage/'detached-launch-unavailable.private.json',{'error_type':type(error).__name__,
            'error':str(error),'retry_authorized':False,'native_execution_success_inferred':False})
        raise


def _wait_once(child,worker_seconds,grace_seconds,*,clock=time.monotonic,shutdown_state=None):
    """One known child; the only repeated waits observe that same process."""
    state={} if shutdown_state is None else shutdown_state
    if 'terminal_result' in state:return state['terminal_result']
    began=state.setdefault('began',clock());code=None
    worker_deadline=state.setdefault('worker_deadline',began+worker_seconds)
    if worker_seconds>0 and not state.get('shutdown_requested'):
        try:code=child.wait(timeout=worker_seconds)
        except subprocess.TimeoutExpired:state['host_timeout']=True;state['shutdown_requested']=True
    else:state['shutdown_requested']=True
    if state.get('shutdown_requested'):
        deadline=state.setdefault('grace_deadline',min(clock()+grace_seconds,worker_deadline+grace_seconds))
        if child.poll() is None and not state.get('term_attempted'):
            state['term_attempted']=True;child.send_signal(signal.SIGTERM)
        try:code=child.wait(timeout=max(0,deadline-clock()))
        except subprocess.TimeoutExpired:
            if child.poll() is None and not state.get('kill_attempted'):
                state['kill_attempted']=True;child.kill()
            final_deadline=state.setdefault('hard_wait_deadline',deadline+10)
            try:code=child.wait(timeout=min(10,max(0,final_deadline-clock())))
            except subprocess.TimeoutExpired:state['hard_wait_unavailable']=True
    result={'exit_code':code,'elapsed_host_seconds':clock()-began,
        'host_expiry_sigterm_sent_once':bool(state.get('host_timeout') and state.get('term_attempted')),
        'worker_sigterm_attempted_once':bool(state.get('term_attempted')),
        'supervisor_cancel_requested':bool(state.get('supervisor_cancel_requested')),
        'cleanup_grace_hard_stop':bool(state.get('kill_attempted')),
        'hard_stop_terminal_wait_unavailable':bool(state.get('hard_wait_unavailable')),
        'cleanup_success_inferred':False,'automatic_worker_restarts':0}
    state['terminal_result']=result
    return result


def supervise(*,review_path,review_sha256):
    authority=_approval(review_path,review_sha256);stage=Path(authority['output_root']).parent
    launch=c.private(stage/'detached-launch-intent.private.json')
    expected=[PYTHON,str(SUPERVISOR),'supervise','--review-path',str(Path(review_path).absolute()),
        '--review-sha256',review_sha256]
    c.require(launch['argv']==expected and launch['authority_ref']==c.ref(review_path) and
        launch['source_binding']==c.source_binding(),'supervisor_exact_consumed_launch_required')
    # Ancestor chat/session interruption cannot signal this detached session.
    c.require(os.getsid(0)==os.getpid(),'supervisor_detached_session_required')
    signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGHUP,signal.SIG_IGN)
    lease=os.open(stage/'supervisor-lease.private.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    child=None;shutdown_state={};previous_term=signal.getsignal(signal.SIGTERM)
    def cancel(_signal,_frame):
        if not shutdown_state.get('supervisor_cancel_requested'):
            shutdown_state['supervisor_cancel_requested']=True
            if not shutdown_state.get('spawning_worker'):
                raise SupervisorCancelled('supervisor_cancel_requested_same_worker_only')
    signal.signal(signal.SIGTERM,cancel)
    try:
        start=time.monotonic();deadline=start+authority['host_worker_seconds']
        shutdown_state['worker_deadline']=deadline
        c.world.write(stage/'supervisor-start.private.json',{'schema':'gitlab-continuation-supervisor-start-v1',
            'pid':os.getpid(),'ppid':os.getppid(),'session_id':os.getsid(0),'authority_ref':c.ref(review_path),
            'one_worker_only':True,'worker_started_monotonic':start,'worker_deadline_monotonic':deadline,
            'worker_seconds':authority['host_worker_seconds'],'cleanup_grace_seconds':authority['host_cleanup_grace_seconds'],
            'maximum_host_seconds_including_hard_stop_wait':authority['host_worker_seconds']+authority['host_cleanup_grace_seconds']+10,
            'kernel_lease_held':True,'supervisor_source_sha256':sha256(SUPERVISOR.read_bytes()).hexdigest()})
        argv=[PYTHON,'-m','gitlab_world.v066_selection_reference_continuation_v1','run',
            '--review-path',str(Path(review_path).absolute()),'--review-sha256',review_sha256,
            '--supervisor-intent-sha256',c.ref(stage/'supervisor-start.private.json')['sha256'],'--execute']
        c.world.write(stage/'worker-intent.private.json',{'argv':argv,'cwd':str(c.REPO),
            'authority_ref':c.ref(review_path),'supervisor_ref':c.ref(stage/'supervisor-start.private.json'),
            'maximum_worker_processes':1,'automatic_retries':0})
        with _log(stage,'worker.stdout.private.log') as stdout,_log(stage,'worker.stderr.private.log') as stderr:
            shutdown_state['spawning_worker']=True
            try:
                child=subprocess.Popen(argv,cwd=c.REPO,env={**os.environ,'PYTHONPATH':'.:src:tests','PYTHONDONTWRITEBYTECODE':'1'},
                    stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True)
            finally:shutdown_state['spawning_worker']=False
            c.world.write(stage/'worker-start.private.json',{'pid':child.pid,'supervisor_pid':os.getpid(),
                'worker_intent_ref':c.ref(stage/'worker-intent.private.json'),'one_worker_only':True})
            if shutdown_state.get('supervisor_cancel_requested'):
                raise SupervisorCancelled('supervisor_spawn_cancellation_deferred_until_known_worker_pid')
            terminal=_wait_once(child,max(0,deadline-time.monotonic()),authority['host_cleanup_grace_seconds'],shutdown_state=shutdown_state)
        terminal.update(schema='gitlab-continuation-worker-terminal-v1',pid=child.pid,supervisor_pid=os.getpid(),
            authority_ref=c.ref(review_path),worker_start_ref=c.ref(stage/'worker-start.private.json'),
            stdout_ref=c.ref(stage/'worker.stdout.private.log'),stderr_ref=c.ref(stage/'worker.stderr.private.log'),
            source146_unchanged=c.world.source_hashes()==authority['native_source146'],
            workflow_source_binding_unchanged=c.source_binding()==authority['controller_binding'],
            aggregate_result_present=(Path(authority['output_root'])/'aggregate-audit.private.json').exists(),
            qualification_or_model_or_final_credit=0)
        terminal['status']='worker_exit_requires_saved_aggregate_audit' if terminal['exit_code']==0 else 'worker_terminal_failure_no_retry'
        c.world.write(stage/'worker-terminal.private.json',terminal)
        return terminal
    except BaseException as error:
        shutdown=None
        if child is not None:
            try:shutdown=_wait_once(child,0,authority['host_cleanup_grace_seconds'],shutdown_state=shutdown_state)
            except BaseException as cleanup_error:shutdown={'error_type':type(cleanup_error).__name__,
                'error':str(cleanup_error),'worker_cleanup_may_be_uncertain':True}
        c.world.write(stage/'supervisor-unavailable.private.json',{'error_type':type(error).__name__,
            'error':str(error),'automatic_retry_authorized':False,'worker_cleanup_may_be_uncertain':True,
            'same_worker_shutdown_after_supervisor_error':shutdown,
            'qualification_or_model_or_final_credit':0})
        raise
    finally:signal.signal(signal.SIGTERM,previous_term);fcntl.flock(lease,fcntl.LOCK_UN);os.close(lease)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('launch','supervise'))
    p.add_argument('--review-path',required=True);p.add_argument('--review-sha256',required=True);p.add_argument('--execute',action='store_true')
    args=vars(p.parse_args());command=args.pop('command')
    if command=='launch':value=launch(**args)
    else:
        args.pop('execute');value=supervise(**args)
    print(json.dumps(value,sort_keys=True))


if __name__=='__main__':main()
