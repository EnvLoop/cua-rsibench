"""Source-bound exact-deadline Tinker transport for current Odoo actors."""
from __future__ import annotations
from dataclasses import replace
import json
import math
from pathlib import Path
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from native_desktop_factory.deadline_model_transport_v21 import DeadlineBackend,checked_deadline_proof
from cursibench.scale_action_output_v066 import render_for_model
from cursibench.scale_vision_proxy import Limits,VisionSamplingAdapter
from cursibench.native_surface_guard_policy_v1 import GuardError


def sampler_class(selection):
    base=getattr(selection,'_actor_native_original_sampler_class',selection.RealTinkerSelectionSampler)
    class Sampler(base):
        def __enter__(self):
            import time
            self.lifecycle_started_monotonic=time.monotonic()
            return super().__enter__()

        def __exit__(self,exc_type,exc,tb):
            import os,time
            from hashlib import sha256
            service=self.service
            value={'schema':'odoo-owned-provider-close-v1','status':'no_service_created' if service is None else 'uncertain',
                'owned_service_object_sha256':None if service is None else sha256(f'{os.getpid()}:{id(service)}'.encode()).hexdigest(),
                'close_started_monotonic':time.monotonic(),'real_close_call_returned':False,
                'automatic_model_retries':0,'new_model_requests':0}
            try:
                result=super().__exit__(exc_type,exc,tb)
                if service is not None:value.update(status='acknowledged',real_close_call_returned=True)
                return result
            finally:
                value['close_ended_monotonic']=time.monotonic()
                clock=getattr(self,'actor_clock',None)
                if clock is not None and clock.store is not None:
                    self.provider_close_reference=clock.store.json('actor-clock/provider-close.private.json',value,'dispatch_receipt')

        def sample(self,observation,*,task_index,step,task_dir):
            clock=getattr(self,'actor_clock',None)
            if clock is None:raise GuardError('actor_deadline_sampler_clock_missing')
            clock.check('before_model_submission')
            wrapped=DeadlineBackend(self.backend,clock.deadline)
            adapter=self.adapters.get(task_index)
            if adapter is None:
                adapter=VisionSamplingAdapter(wrapped,task_dir/'sampling-journal',limits=Limits(
                    max_actions=selection.MAX_ACTIONS,input_tokens=selection.MAX_INPUT_TOKENS,
                    output_tokens=self.config['sample_max_tokens'],request_timeout_seconds=selection.SAMPLE_TIMEOUT_SECONDS))
                self.adapters[task_index]=adapter
            adapter.backend=wrapped
            adapter.limits=replace(adapter.limits,request_timeout_seconds=max(1,min(selection.SAMPLE_TIMEOUT_SECONDS,
                math.ceil(max(0,clock.deadline-clock.clock())))))
            request_id='odoo-sel-'+selection._hash(self.attempt_id.encode())[:10]+f'-{task_index:02d}-{step:03d}'
            result=adapter.sample(request_id=request_id,**render_for_model(observation))
            self.last_raw_result=result;self.last_request_id=request_id
            self.last_deadline_result=None;self.last_deadline_reference=None
            if wrapped.proof is not None:
                proof=checked_deadline_proof(wrapped.proof.receipt(),clock.deadline)
                late=getattr(wrapped.future,'late_result',None) if wrapped.future else None
                sequences=[] if late is None else [{'tokens':list(v.tokens),'stop_reason':getattr(v,'stop_reason',None)} for v in late.sequences]
                if sequences and (len(sequences)!=1 or len(sequences[0]['tokens'])>self.config['sample_max_tokens']):
                    raise GuardError('actor_deadline_late_result_unbounded')
                value={'schema':'odoo-typed-model-deadline-v1','task_id':observation.task_id,
                    'package_sha256':observation.task_binding_sha256,'step':step,'frame_id':observation.frame_id,
                    'frame_sha256':observation.screenshot['sha256'],'request_id':request_id,
                    'actor_deadline_proof':proof.receipt(),'sampling_failure':result,
                    'late_response_sequences':sequences,'gui_applied':False,'same_request_replay_authorized':False}
                reference=clock.store.json(f'actor-clock/sample-{step:03d}-deadline.private.json',value,'dispatch_receipt')
                self.last_deadline_result=value;self.last_deadline_reference=reference
                raise ActorDeadlineReached(proof,late_result=late)
            if result.get('status')!='completed' or result.get('reused') or result.get('new_dispatch') is not True:
                raise selection.SelectionProviderUncertain('actor_provider_fault_before_deadline_no_replay')
            return result
    return Sampler


def attach_sampler_clock(sampler,clock):
    """Pass the same real clock through metered/paid wrappers, without new IDs."""
    current=sampler;seen=set()
    while current is not None and id(current) not in seen:
        seen.add(id(current));current.actor_clock=clock
        current=getattr(current,'delegate',None)


def deadline_sample(sampler,observation,error):
    current=sampler;seen=set();paid=getattr(sampler,'parent_paid_attempt_id',None)
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        declared=getattr(current,'declared_attempt_ids',None)
        if paid is None and type(declared) is list and declared:paid=declared[-1]
        retained=getattr(current,'last_deadline_result',None)
        if retained is not None:
            if retained['actor_deadline_proof']!=error.proof.receipt() or retained['frame_id']!=observation.frame_id:
                raise GuardError('typed_actor_deadline_sample_unbound')
            failure=retained['sampling_failure']
            if type(paid) is not str or not paid:raise GuardError('actor_deadline_paid_reservation_evidence_missing')
            return {'step':observation.step,'status':'actor_deadline_proven','error_subtype':'actor_wall_budget',
                'usage':failure.get('usage'),'request_id_sha256':__import__('hashlib').sha256(retained['request_id'].encode()).hexdigest(),
                'paid_attempt_id':paid,'model_text_sha256':None,'deadline_evidence':current.last_deadline_reference}
        current=getattr(current,'delegate',None)
    raise GuardError('typed_actor_deadline_actual_sampling_evidence_missing')


def known_token_total(samples,key):
    values=[row.get('usage',{}).get(key) if type(row.get('usage')) is dict else None for row in samples]
    if any(type(value) is not int or value<0 for value in values):return None
    return sum(values)
