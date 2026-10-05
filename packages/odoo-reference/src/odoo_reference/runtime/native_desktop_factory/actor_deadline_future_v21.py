"""Typed deadline proof only; no provider/future implementation."""
from dataclasses import dataclass

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
