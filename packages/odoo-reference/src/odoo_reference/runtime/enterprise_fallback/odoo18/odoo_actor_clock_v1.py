"""Actual Odoo actor timing, typed deadlines and durable native IO boundaries.

No task data, GUI/provider call, score or runtime activation occurs on import.
"""
from __future__ import annotations
from dataclasses import asdict
import math
import time
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineProof,ActorDeadlineReached
from cursibench.native_surface_guard_policy_v1 import GuardError

ACTOR_SECONDS=720
LEASE_SECONDS=1200


class LateNativeCompletion(GuardError):pass


class ActorClock:
    def __init__(self,*,task_id,package_sha256,started,clock=time.monotonic):
        if type(started) not in (int,float) or not math.isfinite(started):raise GuardError('actor_start_not_monotonic')
        self.task_id=task_id;self.package_sha256=package_sha256;self.started=float(started)
        self.deadline=self.started+ACTOR_SECONDS;self.clock=clock;self.store=None
        self.ended=None;self.raw_end=None;self.outcome=None;self.events=[];self.pending=None
        self.deadline_exception=None;self.deadline_ref=None;self.end_ref=None;self._event_number=0

    def bind(self,store):
        if self.store is not None:raise GuardError('actor_clock_already_bound')
        self.store=store
        return store.json('actor-clock/start.private.json',{'schema':'odoo-actual-actor-start-v1',
            'task_id':self.task_id,'package_sha256':self.package_sha256,'actor_started_monotonic':self.started,
            'actor_deadline_monotonic':self.deadline,'actor_seconds_limit':ACTOR_SECONDS,
            'start_boundary':'adapter_constructed_after_native_login_and_route'},'native_observation_envelope')

    def check(self,stage):
        now=self.clock()
        if self.ended is not None:raise GuardError('actor_clock_ended_no_replay')
        if now>=self.deadline:
            proof=ActorDeadlineProof(self.deadline,now,now,0,'actor_deadline_reached_before_submission',False,False)
            error=ActorDeadlineReached(proof)
            self.deadline_exception=error
            if self.store is not None:
                self.deadline_ref=self.store.json(f'actor-clock/stop-{self._event_number:03d}.private.json',{
                    'schema':'odoo-actual-actor-deadline-stop-v1','task_id':self.task_id,'package_sha256':self.package_sha256,
                    'stage':stage,'actor_deadline_proof':proof.receipt(),'native_io_called':False,
                    'same_request_replay_authorized':False},'dispatch_receipt')
                self._event_number+=1
            raise error
        return now

    def before_io(self,operation):
        now=self.check('before_native_io')
        if self.pending is not None:raise GuardError('actor_io_already_pending')
        self.pending={'operation':operation,'started_monotonic':now,'completed_monotonic':None,'status':'intent_before_native_io'}
        self.pending['intent']=self.store.json(f'actor-clock/io-{len(self.events):03d}-intent.private.json',{
            'schema':'odoo-actor-native-io-v1','task_id':self.task_id,'package_sha256':self.package_sha256,
            **self.pending,'absolute_actor_deadline':self.deadline},'action_intent')

    def after_io(self,operation,*,returned):
        if self.pending is None or self.pending['operation']!=operation:raise GuardError('actor_io_completion_unbound')
        now=self.clock();row={**self.pending,'completed_monotonic':now,'status':'returned' if returned else 'unknown'}
        row['completion']=self.store.json(f'actor-clock/io-{len(self.events):03d}-completion.private.json',{
            'schema':'odoo-actor-native-io-v1','task_id':self.task_id,'package_sha256':self.package_sha256,
            **row,'absolute_actor_deadline':self.deadline},'driver_result')
        self.events.append(row);self.pending=None
        if returned and now>self.deadline:raise LateNativeCompletion('native_io_returned_after_actor_deadline_not_admissible')

    def end(self,outcome,*,deadline_exception=None):
        if self.ended is not None:raise GuardError('actor_clock_end_already_recorded')
        now=self.clock();self.raw_end=now;self.outcome=outcome
        if deadline_exception is not None:
            if type(deadline_exception) is not ActorDeadlineReached or not deadline_exception.proof.actor_deadline_reached or deadline_exception.proof.actor_deadline_monotonic!=self.deadline:
                raise GuardError('actor_budget_stop_not_proven')
            self.deadline_exception=deadline_exception;self.ended=self.deadline
        else:
            self.ended=now
            if now>self.deadline:raise GuardError('untyped_actor_end_after_deadline')
        if self.pending is not None or any(row['status']!='returned' or row['completed_monotonic']>self.deadline for row in self.events):
            raise GuardError('actor_native_io_unknown_or_late')
        value={'schema':'odoo-actual-actor-clock-v1','task_id':self.task_id,'package_sha256':self.package_sha256,
            'actor_started_monotonic':self.started,'actor_deadline_monotonic':self.deadline,
            'actor_ended_monotonic':self.ended,'raw_end_acknowledged_monotonic':now,
            'actor_elapsed_seconds':self.ended-self.started,'raw_elapsed_until_ack_seconds':now-self.started,
            'model_outcome':outcome,'native_io':self.events,'native_actions_after_deadline':0,
            'evaluation_outside_actor_clock':True,'end_boundary':'before_evaluator_gui_reload_saved_readback_and_reset',
            'deadline_proof':None if deadline_exception is None else deadline_exception.proof.receipt()}
        self.end_ref=self.store.json('actor-clock/end.private.json',value,'native_observation_envelope')
        return self.end_ref
