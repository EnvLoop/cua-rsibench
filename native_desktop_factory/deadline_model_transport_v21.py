"""Uniform five-slot deadline transport; native guard and scorer are unchanged."""
from __future__ import annotations
from dataclasses import replace,fields
import math
from pathlib import Path
import time

from .uniform_model_transport_v11 import *
from . import uniform_model_transport_v11 as legacy
from .actor_deadline_future_v21 import ActorDeadlineProof,ActorDeadlineReached,DeadlineFuture


def checked_deadline_proof(value,deadline):
    names={f.name for f in fields(ActorDeadlineProof)}
    if not isinstance(value,dict) or value.get('schema')!='cua-actor-deadline-proof-v21':
        raise ValueError('v21_deadline_proof_missing')
    proof=ActorDeadlineProof(**{name:value[name] for name in names})
    numbers=[proof.actor_deadline_monotonic,proof.wait_started_monotonic,
             proof.wait_ended_monotonic,proof.wait_timeout_seconds]
    if (not all(type(v) in (int,float) and math.isfinite(v) for v in numbers) or
        proof.actor_deadline_monotonic!=deadline or not proof.actor_deadline_reached or
        proof.wait_ended_monotonic<proof.wait_started_monotonic or proof.wait_timeout_seconds<0 or
        proof.wait_timeout_seconds>min(120,max(0,deadline-proof.wait_started_monotonic)) or
        type(proof.model_dispatch_may_have_occurred) is not bool or type(proof.model_completion_known) is not bool or
        value.get('same_request_replay_authorized') is not False or
        value.get('late_gui_application_authorized') is not False or
        proof.event not in {'actor_deadline_reached_before_wait','actor_deadline_reached_during_wait',
                           'actor_deadline_reached_before_submission','model_response_completed_after_actor_deadline'}):
        raise ValueError('v21_deadline_proof_changed')
    return proof


class DeadlineBackend:
    def __init__(self,backend,deadline):
        self.backend=backend;self.identity=backend.identity;self.deadline=deadline
        self.future=None;self.before_submit_proof=None
    def render(self,*args):return self.backend.render(*args)
    def decode(self,*args):return self.backend.decode(*args)
    def submit(self,*args):
        now=time.monotonic()
        if now>=self.deadline:
            self.before_submit_proof=ActorDeadlineProof(self.deadline,now,now,0,
                'actor_deadline_reached_before_submission',False,False)
            raise ActorDeadlineReached(self.before_submit_proof)
        self.future=DeadlineFuture(self.backend.submit(*args),actor_deadline=self.deadline)
        return self.future
    @property
    def proof(self):
        return self.before_submit_proof or (self.future.last_deadline_proof if self.future else None)


class CleanRuntimeSampler(legacy.CleanRuntimeSampler):
    def __init__(self):
        super().__init__();self.last_deadline_proof=None;self.shutdown_ack=None;self.task_deadlines={}

    def sample_rendered(self,*,request_id,task_dir,remaining_seconds,actor_deadline,
                        image_bytes,instruction,visible_text):
        from cursibench.scale_vision_proxy import Limits,VisionSamplingAdapter
        from .qwen_sampler_process_v21 import write_new
        now=time.monotonic()
        if type(actor_deadline) not in (int,float) or not math.isfinite(actor_deadline) or actor_deadline>now+720:
            raise ValueError('v21_actor_deadline_not_uniform')
        key=str(task_dir.resolve())
        if key in self.task_deadlines and self.task_deadlines[key]!=actor_deadline:
            raise ValueError('v21_actor_deadline_extended_or_changed')
        self.task_deadlines[key]=actor_deadline
        wrapped=DeadlineBackend(self.backend,actor_deadline)
        adapter=self.adapters.get(key)
        if adapter is None:
            adapter=VisionSamplingAdapter(wrapped,task_dir/'sampling-journal',limits=Limits(
                max_actions=MAX_ACTIONS,input_tokens=32768,output_tokens=self.max_output_tokens,
                request_timeout_seconds=120))
            self.adapters[key]=adapter
        adapter.backend=wrapped
        # Limits keeps its integer schema; the future receives the exact float.
        adapter.limits=replace(adapter.limits,request_timeout_seconds=max(1,min(120,
            math.ceil(max(0,actor_deadline-time.monotonic())))))
        result=adapter.sample(request_id=request_id,image_bytes=image_bytes,
                              instruction=instruction,visible_text=visible_text)
        proof=wrapped.proof
        if proof is not None:
            self.last_failure=result;self.last_deadline_proof=proof.receipt()
            proof_path=task_dir/'sampling-journal'/(request_id+'.deadline.private.json')
            write_new(proof_path,{'actor_deadline_proof':self.last_deadline_proof,
                'retained_sampling_failure':result,'same_request_replay_authorized':False})
            if wrapped.future is not None and wrapped.future.late_result is not None:
                response=wrapped.future.late_result
                sequences=getattr(response,'sequences',[])
                values=[{'tokens':list(v.tokens),'stop_reason':getattr(v,'stop_reason',None)} for v in sequences]
                if len(values)!=1 or len(values[0]['tokens'])>self.max_output_tokens:
                    raise ValueError('v21_late_response_bound_changed')
                write_new(task_dir/'sampling-journal'/(request_id+'.late-response.private.json'),{
                    'sequences':values,'gui_application_authorized':False,'official_final_credit':0})
            raise ActorDeadlineReached(proof)
        if result.get('reused') or result.get('new_dispatch') is not True or result.get('status')!='completed':
            self.last_failure=result
            raise ValueError('v21_model_sample_failed_or_uncertain_no_replay')
        return {**result,'reported_model':MODEL,'checkpoint_path_sha256':self.checkpoint_sha256,
                'backend_checkpoint_identity_sha256':self.backend.identity['checkpoint_sha256']}

    def close(self,success):
        if self.shutdown_ack is not None:return self.shutdown_ack
        service,self.service=self.service,None
        holder=getattr(service,'_session_holder',None) if service is not None else None
        identifier=getattr(holder,'_session_id',None)
        ack={'schema':'cua-provider-shutdown-ack-v21','status':'no_service_created' if service is None else 'uncertain',
             'owned_session_id_sha256':digest(identifier.encode()) if isinstance(identifier,str) else None,
             'automatic_retries':0,'new_model_requests':0}
        try:
            if service is not None:
                service.close('success' if success else 'errored').result(timeout=30)
                ack['status']='acknowledged'
        except Exception as exc:
            ack['exception_type']=type(exc).__name__
            ack['error_sha256']=digest(str(exc).encode())
        self.shutdown_ack=ack
        return ack


class ModelSampler(legacy.ModelSampler):
    def __init__(self,*,repo_root=None,journal_root=None,plan_sha256=None):
        from .qwen_sampler_process_v21 import SamplerProcess
        self.process=SamplerProcess(repo_root=repo_root,journal_root=journal_root,plan_sha256=plan_sha256)
        self.backend=None;self.checkpoint_sha256=None;self.deadline_stop=None

    def sample(self,*,observation,request_id,task_dir,remaining_seconds,actor_deadline):
        import base64
        rendered=output.render_for_model(observation)
        try:
            result=self.process.call('sample',{'request_id':request_id,'task_dir':str(task_dir.resolve()),
                'remaining_seconds':remaining_seconds,'actor_deadline':actor_deadline,
                'image_base64':base64.b64encode(rendered['image_bytes']).decode(),
                'instruction':rendered['instruction'],'visible_text':rendered['visible_text']},
                timeout=min(185,max(0,actor_deadline-time.monotonic())+5))
        except ActorDeadlineReached as exc:
            self.deadline_stop=exc.proof.receipt()
            raise
        if result.get('status')!='completed' or result.get('reused') or result.get('new_dispatch') is not True:
            raise ValueError('v21_model_sample_failed_or_uncertain_no_replay')
        return result

    def assert_deadline_stop(self,deadline):
        checked_deadline_proof(self.deadline_stop,deadline)
        if not self.process.poisoned or not self.process.acknowledgement_verified:
            raise ValueError('v21_actor_deadline_unacknowledged_or_unpoisoned')
        return self.deadline_stop
