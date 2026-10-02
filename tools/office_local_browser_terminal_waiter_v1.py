"""Terminal-first private frame waiter. No browser/session capability is accepted.

Provider execution is only through the unchanged native-admitted clean-runtime
sampler. Startup does not create a service or dispatch a model request.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time

from tools import office_single_account_train_pilot_v1 as private
from tools.office_local_browser_qwen_base_sampler_v1 import admit, run


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def publish_new(target: Path, value):
    raw = value if isinstance(value, bytes) else private._canonical(value)
    temporary = target.with_name(target.name+'.'+secrets.token_hex(12)+'.pending')
    private._write_new(temporary, raw)
    try:
        os.link(temporary, target)
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink()
    return sha(raw)


def load_session(artifact_root: Path, repo_root: Path, *, now_ms=None):
    root=Path(artifact_root).absolute();repo=Path(repo_root).absolute();work=repo/'work'
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    private._require(root.is_dir() and not root.is_symlink() and root.resolve()==root and
        root.is_relative_to(work.resolve()) and root.stat().st_mode&0o077==0,
        'private_terminal_spool_root_required')
    spool=root/'terminal-spool.private'
    private._require(spool.is_dir() and not spool.is_symlink() and spool.stat().st_mode&0o077==0,
        'private_terminal_spool_directory_required')
    session,raw=private._json(spool/'session.private.json',work)
    required={'schema','session_id','binding_sha256','native_admission_sha256',
        'visible_instruction_ref','cua_helper_sha256','waiter_sha256',
        'max_steps','expires_at_ms','max_call_ms'}
    private._require(set(session)==required and session['schema']=='office-local-terminal-spool-session-v1' and
        isinstance(session['session_id'],str) and len(session['session_id'])==32 and
        type(session['max_steps']) is int and 1<=session['max_steps']<=120 and
        type(session['max_call_ms']) is int and 1000<=session['max_call_ms']<=55000 and
        type(session['expires_at_ms']) is int and now_ms<session['expires_at_ms']<=now_ms+900000,
        'invalid_terminal_spool_session')
    admission,admission_raw=private._json(root/'native-admission.private.json',work)
    private._require(admission['schema']=='office-local-browser-native-sampler-admission-v1' and
        admission['mode']=='native_development' and admission['split']=='train' and
        admission['binding_sha256']==session['binding_sha256'] and
        admission['max_steps']==session['max_steps'] and sha(admission_raw)==session['native_admission_sha256'],
        'terminal_spool_admission_changed')
    instruction,_=private._ref(session['visible_instruction_ref'],work,maximum=16384)
    private._require(instruction.resolve().is_relative_to(root) and
        session['visible_instruction_ref']['sha256']==admission['visible_instruction_sha256'],
        'terminal_spool_instruction_changed')
    for field,name in {'cua_helper_sha256':'office_local_browser_terminal_spool_v1.mjs',
                       'waiter_sha256':'office_local_browser_terminal_waiter_v1.py'}.items():
        private._require(sha((repo/'tools'/name).read_bytes())==session[field],
                         'terminal_spool_reviewed_source_changed')
    return root,repo,spool,session,sha(raw),instruction


def serve(artifact_root: Path, *, repo_root: Path, sampler_runner=run,
          clock=lambda:int(time.time()*1000), pause=time.sleep, poll_seconds=0.1):
    private._require(0.01<=poll_seconds<=1,'invalid_terminal_poll_interval')
    root,repo,spool,session,session_sha,instruction=load_session(artifact_root,repo_root,now_ms=clock())
    publish_new(spool/'waiter-start.private.json',{
        'schema':'office-terminal-waiter-start-v1','session_sha256':session_sha,
        'single_worker_only':True,'official_final_credit':0})
    def poison(code,step):
        try:
            publish_new(spool/'poison.private.json',{
                'schema':'office-terminal-spool-poison-v1','status':'consumed_session_no_replay',
                'code':code,'session_sha256':session_sha,'step':step,'official_final_credit':0})
        except FileExistsError:
            pass
    status='stopped';completed=0
    try:
        publish_new(spool/'waiter-ready.private.json',{
            'schema':'office-terminal-waiter-ready-v1','status':'ready','session_sha256':session_sha})
        for step in range(session['max_steps']):
            prefix=f'{step:03d}';request_path=spool/'requests.private'/f'{prefix}.request.private.json'
            while not request_path.exists():
                if (spool/'stop.private.json').exists() or (spool/'poison.private.json').exists():
                    return {'status':'stopped','completed_samples':completed,'official_final_credit':0}
                private._require(clock()<session['expires_at_ms'],'terminal_spool_lease_expired')
                pause(poll_seconds)
            request,_=private._json(request_path,repo/'work')
            required={'schema','session_sha256','step','frame_id','deadline_ms','frame_ref','context_ref'}
            private._require(set(request)==required and request['schema']=='office-terminal-spool-request-v1' and
                request['session_sha256']==session_sha and request['step']==step and
                type(request['deadline_ms']) is int and clock()<request['deadline_ms']<=clock()+session['max_call_ms'],
                'terminal_request_binding_or_deadline_changed')
            publish_new(spool/'intents.private'/f'{prefix}.private.json',{
                'schema':'office-terminal-spool-consumed-frame-intent-v1','session_sha256':session_sha,
                'step':step,'request_sha256':sha(request_path.read_bytes()),'single_dispatch_only':True,
                'official_final_credit':0})
            frame_path,frame_raw=private._ref(request['frame_ref'],repo/'work')
            context_path,_=private._ref(request['context_ref'],repo/'work')
            private._require(frame_path.resolve().is_relative_to(root/'frames.private') and
                context_path==spool/'requests.private'/f'{prefix}.context.private.json',
                'terminal_frame_or_context_outside_session')
            context,_=private._json(context_path,repo/'work')
            private._require(set(context)=={'memory','previous_action_result'},'terminal_context_invalid')
            admission,frame,_,_,_=admit(root/'native-admission.private.json',frame_path,instruction,repo/'work',**context)
            private._require(frame['frame_id']==request['frame_id'] and frame['step']==step and
                request['deadline_ms']<=min(frame['expires_at_ms'],session['expires_at_ms']) and
                clock()<request['deadline_ms'],'terminal_current_frame_changed')
            if (spool/'poison.private.json').exists() or (spool/'stop.private.json').exists():
                raise ValueError('terminal_session_stopped_before_dispatch')
            out=spool/'samples.private'/f'{prefix}.private'
            result=sampler_runner(root/'native-admission.private.json',frame_path,instruction,out,
                repo_root=repo,**context)
            completed+=1
            result_raw=private._private(out/'result.private.json',repo/'work',2_000_000)
            action_raw=private._private(out/'action.private.json',repo/'work',16384)
            private._require(json.loads(result_raw)==result and result['status']=='normalized_current_frame_action_only' and
                result['action_sha256']==sha(action_raw) and result['frame_sha256']==sha(frame_raw) and
                result['native_admission_sha256']==session['native_admission_sha256'] and
                result['sampling']['new_dispatch'] is True and result['sampling']['reused'] is False,
                'terminal_normalized_result_changed')
            late=(clock()>=request['deadline_ms'] or (spool/'poison.private.json').exists() or
                  (spool/'stop.private.json').exists())
            response={'schema':'office-terminal-spool-response-v1','session_sha256':session_sha,
                'step':step,'frame_id':frame['frame_id'],
                'status':'late_no_replay' if late else 'normalized_current_frame_action_only',
                'result_ref':{'path':str((out/'result.private.json').relative_to(repo/'work')),'sha256':sha(result_raw)},
                'action_ref':{'path':str((out/'action.private.json').relative_to(repo/'work')),'sha256':sha(action_raw)}}
            publish_new(spool/'responses.private'/f'{prefix}.response.private.json',response)
            if late:
                poison('late_terminal_result_no_replay',step);status='poisoned';break
        return {'status':status,'completed_samples':completed,'official_final_credit':0}
    except BaseException as exc:
        status='failed_or_uncertain_no_replay';poison(type(exc).__name__,completed)
        try:
            publish_new(spool/'waiter-failure.private.json',{
                'schema':'office-terminal-waiter-failure-v1','status':status,
                'exception_type':type(exc).__name__,'error_sha256':sha(str(exc).encode()),
                'completed_samples':completed,'official_final_credit':0})
        except FileExistsError:
            pass
        raise
    finally:
        publish_new(spool/'waiter-terminal.private.json',{
            'schema':'office-terminal-waiter-terminal-v1','status':status,
            'completed_samples':completed,'session_sha256':session_sha,'official_final_credit':0})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-root',type=Path,required=True)
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
    if not args.run:
        *_,session_sha,_=load_session(args.artifact_root,repo)
        print(json.dumps({'status':'offline_spool_session_checked','session_sha256':session_sha,
                          'provider_calls':0,'official_final_credit':0}));return
    result=serve(args.artifact_root,repo_root=repo)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    try:
        main()
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'rejected_or_failed_no_replay','exception_type':type(exc).__name__,
                          'official_final_credit':0}));sys.exit(1)
