"""Source-only deadline primitive for a future v21 uniform actor protocol.

This module creates no provider request, controls no GUI, assigns no score and
does not activate a new worker. Legacy v11 pilot files and behavior stay intact.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time


@dataclass(frozen=True)
class ActorDeadlineProof:
    actor_deadline_monotonic: float
    wait_started_monotonic: float
    wait_ended_monotonic: float
    wait_timeout_seconds: float
    event: str
    model_dispatch_may_have_occurred: bool
    model_completion_known: bool

    @property
    def actor_deadline_reached(self):
        return self.wait_ended_monotonic >= self.actor_deadline_monotonic

    def receipt(self):
        return {
            'schema':'cua-actor-deadline-proof-v21',
            'actor_deadline_monotonic':self.actor_deadline_monotonic,
            'wait_started_monotonic':self.wait_started_monotonic,
            'wait_ended_monotonic':self.wait_ended_monotonic,
            'wait_timeout_seconds':self.wait_timeout_seconds,
            'event':self.event,
            'actor_deadline_reached':self.actor_deadline_reached,
            'model_dispatch_may_have_occurred':self.model_dispatch_may_have_occurred,
            'model_completion_known':self.model_completion_known,
            'same_request_replay_authorized':False,
            'late_gui_application_authorized':False,
        }


class ActorDeadlineReached(TimeoutError):
    def __init__(self,proof:ActorDeadlineProof,*,late_result=None):
        super().__init__('actor_deadline_reached_no_late_gui_or_replay')
        self.proof=proof
        # Only a trusted private receipt builder may serialize this object.
        self.late_result=late_result


def wait_budget(*,actor_deadline:float,provider_timeout:float|None,now:float):
    if not all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)
               for v in (actor_deadline,now)):
        raise ValueError('invalid_monotonic_actor_deadline')
    if provider_timeout is not None and (
        not isinstance(provider_timeout,(float,int)) or isinstance(provider_timeout,bool) or
        not math.isfinite(provider_timeout) or provider_timeout<=0):
        raise ValueError('invalid_provider_wait_timeout')
    remaining=max(0.0,float(actor_deadline-now))
    return remaining if provider_timeout is None else min(remaining,float(provider_timeout))


class DeadlineFuture:
    """Wait once on an already-submitted future using the exact actor deadline.

    ``clock`` is the same host monotonic clock as the actor. No integer floor,
    minimum remaining cutoff, new future, retry or provider cancellation exists.
    """
    def __init__(self,future,*,actor_deadline,clock=None):
        self.future=future;self.deadline=actor_deadline;self.clock=clock or time.monotonic
        self.consumed=False;self.last_deadline_proof=None
        self.late_result=None

    def result(self,timeout=None):
        if self.consumed:
            raise ValueError('consumed_future_wait_no_replay')
        self.consumed=True
        started=self.clock();budget=wait_budget(actor_deadline=self.deadline,provider_timeout=timeout,now=started)
        def deadline_error(event,known=False,late_result=None):
            proof=ActorDeadlineProof(self.deadline,started,self.clock(),budget,event,True,known)
            self.last_deadline_proof=proof
            self.late_result=late_result
            return ActorDeadlineReached(proof,late_result=late_result)
        if budget<=0:
            raise deadline_error('actor_deadline_reached_before_wait')
        try:
            value=self.future.result(timeout=budget)
        except TimeoutError:
            if self.clock()>=self.deadline:
                raise deadline_error('actor_deadline_reached_during_wait') from None
            raise  # Independent earlier provider timeout remains a provider fault.
        if self.clock()>=self.deadline:
            raise deadline_error('model_response_completed_after_actor_deadline',True,value)
        return value


def retrospective_timeout_origin(*,remaining_seconds,legacy_wait_seconds,observed_wait_seconds,
                                 provider_timeout_seconds=120):
    """Describe legacy timeout attribution without inventing a score or deadline.

    The old pilot records a relative remaining budget, not the absolute actor
    deadline at timeout. A clipped wait alone cannot prove literal exhaustion.
    """
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0
               for v in (remaining_seconds,legacy_wait_seconds,observed_wait_seconds,provider_timeout_seconds)):
        raise ValueError('invalid_legacy_timeout_measurement')
    limited=legacy_wait_seconds<provider_timeout_seconds and legacy_wait_seconds<=remaining_seconds
    return {
        'status':'actor_budget_constrained_timeout' if limited else 'provider_timeout_origin_unresolved',
        'legacy_integer_truncation_seconds':max(0.0,remaining_seconds-legacy_wait_seconds) if limited else None,
        'estimated_remaining_after_timeout_seconds':remaining_seconds-observed_wait_seconds,
        'literal_actor_deadline_exhaustion_proven':False,
        'independent_task_score':None,
        'same_request_replay_authorized':False,
    }
