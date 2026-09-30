"""Deadline-aware, one-use clean sampler RPC with separate shutdown evidence."""
from __future__ import annotations
import argparse
import base64
from contextlib import redirect_stdout
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys

from .qwen_sampler_process_v11 import write_new,private_json,MAX_COMMANDS
from .actor_deadline_future_v21 import ActorDeadlineReached

ACTIVE_PROCESS=None


def delegated_pre_dispatch(*,repo_root,study_plan_sha256):
    if ACTIVE_PROCESS is None or ACTIVE_PROCESS.root!=Path(repo_root).absolute() or ACTIVE_PROCESS.plan!=study_plan_sha256:
        raise ValueError('v21_no_source_bound_clean_sampler')
    return ACTIVE_PROCESS.call('gate',{})


class SamplerProcess:
    def __init__(self,*,repo_root,journal_root,plan_sha256):
        global ACTIVE_PROCESS
        if repo_root is None or journal_root is None or not re.fullmatch('[0-9a-f]{64}',plan_sha256 or ''):
            raise ValueError('v21_explicit_sampler_root_and_plan_required')
        self.root=Path(repo_root).absolute();self.journal=Path(journal_root).absolute();self.plan=plan_sha256
        self.ordinal=0;self.poisoned=False;self.uncertain=False;self.closed=False;self.acknowledgement_verified=False
        executable=self.root/'work/qwen38-training-runtime/.venv/bin/python'
        if ACTIVE_PROCESS is not None or not executable.is_file() or self.journal.exists() or self.journal.is_symlink():
            raise ValueError('v21_sampler_runtime_or_exclusive_journal_changed')
        self.journal.mkdir(mode=0o700)
        env=os.environ.copy();env['PYTHONPATH']=str(self.root)+os.pathsep+str(self.root/'src')
        env.update(PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        for key in ('KMP_DUPLICATE_LIB_OK','OPENAI_API_KEY','ANTHROPIC_API_KEY','E2B_API_KEY'):
            env.pop(key,None)
        self.stderr=(self.journal/'child.stderr.private.log').open('xb')
        (self.journal/'child.stderr.private.log').chmod(0o600)
        command=[str(executable),'-m','native_desktop_factory.qwen_sampler_process_v21',
                 '--repo-root',str(self.root),'--journal',str(self.journal),'--plan',self.plan]
        write_new(self.journal/'child-launch.private.json',{'argv':command,'source_plan_sha256':self.plan,
                                                         'automatic_restarts':0})
        try:
            self.process=subprocess.Popen(command,cwd=self.root,env=env,stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=self.stderr,text=True,bufsize=1,start_new_session=True)
            write_new(self.journal/'child-started.private.json',{'pid':self.process.pid})
            ACTIVE_PROCESS=self
        except BaseException:
            self.stderr.close();raise

    def call(self,kind,arguments,*,timeout=900):
        if self.closed or self.poisoned or self.ordinal>=MAX_COMMANDS or kind not in ('setup','sample','gate','close'):
            raise ValueError('v21_sampler_command_consumed_or_poisoned')
        number=self.ordinal;self.ordinal+=1;self.acknowledgement_verified=False
        checksum=write_new(self.journal/f'{number:03d}.request.private.json',{
            'schema':'cua-clean-sampler-command-v21','ordinal':number,'kind':kind,
            'plan_sha256':self.plan,'arguments':arguments,'same_request_replay_authorized':False})
        try:
            self.process.stdin.write(json.dumps({'request':f'{number:03d}.request.private.json','sha256':checksum})+'\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout],[],[],timeout)[0]:
                raise TimeoutError('v21_sampler_acknowledgement_uncertain')
            line=self.process.stdout.readline(4097)
            if not line or len(line)>4096:raise ValueError('v21_sampler_acknowledgement_invalid')
            reply=json.loads(line)
            if set(reply)!={'ordinal','result','sha256'} or reply['ordinal']!=number or reply['result']!=f'{number:03d}.result.private.json':
                raise ValueError('v21_sampler_response_binding_changed')
            result,result_sha=private_json(self.journal/reply['result'])
            if result_sha!=reply['sha256'] or result['request_sha256']!=checksum:
                raise ValueError('v21_sampler_result_hash_changed')
            self.acknowledgement_verified=True
            if result['status']=='actor_deadline':
                from .deadline_model_transport_v21 import checked_deadline_proof
                proof=checked_deadline_proof(result['actor_deadline_proof'],arguments['actor_deadline'])
                self.poisoned=True
                self.uncertain=proof.model_dispatch_may_have_occurred and not proof.model_completion_known
                raise ActorDeadlineReached(proof)
            if result['status']!='completed':
                retained=result.get('retained_sampling_failure') or {}
                self.uncertain=retained.get('dispatch_may_have_occurred') is True
                raise ValueError('v21_sampler_failed_retained_result_no_replay')
            return result['value']
        except BaseException:
            self.poisoned=True
            if not self.acknowledgement_verified:self.uncertain=True
            raise

    def close(self,success):
        global ACTIVE_PROCESS
        if self.closed:return
        forced=False;shutdown=None
        try:
            if self.process.poll() is None:
                if not self.poisoned:
                    try:self.call('close',{'success':bool(success)},timeout=35)
                    except BaseException:pass
                # EOF permits only child cleanup. It cannot restart a request.
                try:self.process.stdin.close()
                except (OSError,ValueError):pass
                try:self.process.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    forced=True;self.process.terminate()
                    try:self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
        finally:
            ack=self.journal/'provider-shutdown.private.json'
            if ack.exists():
                try:
                    value,_=private_json(ack)
                    if value.get('plan_sha256')==self.plan:shutdown=value
                except (ValueError,OSError):pass
            write_new(self.journal/'child-terminal.private.json',{
                'pid':self.process.pid,'exit_code':self.process.returncode,'automatic_restarts':0,
                'command_poisoned':self.poisoned,'request_acknowledgement_verified':self.acknowledgement_verified,
                'model_completion_uncertain':self.uncertain,'forced_termination':forced,
                'provider_shutdown_acknowledged':shutdown is not None and shutdown.get('status') in ('acknowledged','no_service_created'),
                'provider_shutdown_receipt_sha256':sha256(ack.read_bytes()).hexdigest() if shutdown else None})
            self.stderr.close();self.closed=True
            if ACTIVE_PROCESS is self:ACTIVE_PROCESS=None


def serve(root,journal,plan,*,sampler_factory=None):
    from cursibench.full_study_qwen_runtime_gate_v1 import pre_dispatch
    from .deadline_model_transport_v21 import CleanRuntimeSampler
    sampler=(sampler_factory or CleanRuntimeSampler)();setup=False;ordinal=0
    try:
        for line in sys.stdin:
            if ordinal>=MAX_COMMANDS or len(line)>4096:raise ValueError('v21_sampler_command_bound')
            envelope=json.loads(line)
            if set(envelope)!={'request','sha256'} or envelope['request']!=f'{ordinal:03d}.request.private.json':
                raise ValueError('v21_sampler_command_order_or_replay')
            request,checksum=private_json(journal/envelope['request'])
            if checksum!=envelope['sha256'] or request['schema']!='cua-clean-sampler-command-v21' or request['ordinal']!=ordinal or request['plan_sha256']!=plan or request['same_request_replay_authorized'] is not False:
                raise ValueError('v21_sampler_command_source_changed')
            kind=request['kind'];args=request['arguments'];stop=False
            try:
                with redirect_stdout(sys.stderr):
                    if kind=='gate':value=pre_dispatch(repo_root=root,study_plan_sha256=plan)
                    elif kind=='setup' and not setup:
                        pre_dispatch(repo_root=root,study_plan_sha256=plan);setup=True
                        value=sampler.start(**args)
                    elif kind=='sample' and setup:
                        task_dir=Path(args['task_dir']).resolve()
                        if not task_dir.is_relative_to(journal.parent.resolve()):raise ValueError('v21_sampler_task_journal_escape')
                        value=sampler.sample_rendered(request_id=args['request_id'],task_dir=task_dir,
                            remaining_seconds=args['remaining_seconds'],actor_deadline=args['actor_deadline'],
                            image_bytes=base64.b64decode(args['image_base64'],validate=True),
                            instruction=args['instruction'],visible_text=args['visible_text'])
                    elif kind=='close':value=sampler.close(args['success']);stop=True
                    else:raise ValueError('v21_sampler_setup_state_changed')
                result={'status':'completed','request_sha256':checksum,'value':value}
            except ActorDeadlineReached as exc:
                result={'status':'actor_deadline','request_sha256':checksum,'actor_deadline_proof':exc.proof.receipt(),
                    'retained_sampling_failure':getattr(sampler,'last_failure',None),
                    'same_request_replay_authorized':False};stop=True
            except Exception as exc:
                result={'status':'failed','request_sha256':checksum,'exception_type':type(exc).__name__,
                    'retained_sampling_failure':getattr(sampler,'last_failure',None),
                    'same_request_replay_authorized':False};stop=True
            target=journal/f'{ordinal:03d}.result.private.json';result_sha=write_new(target,result)
            print(json.dumps({'ordinal':ordinal,'result':target.name,'sha256':result_sha}),file=sys.stdout,flush=True)
            ordinal+=1
            if stop:break
    finally:
        with redirect_stdout(sys.stderr):
            ack=sampler.close(False)
            write_new(journal/'provider-shutdown.private.json',{**ack,'plan_sha256':plan,
                'new_model_requests':0,'same_request_replay_authorized':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,required=True);parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--plan',required=True);args=parser.parse_args()
    if Path(__file__).resolve().parents[1]!=args.repo_root.resolve():raise ValueError('v21_sampler_code_not_source_bound')
    serve(args.repo_root.absolute(),args.journal.absolute(),args.plan)


if __name__=='__main__':main()
