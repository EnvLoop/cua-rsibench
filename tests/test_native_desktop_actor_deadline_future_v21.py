import unittest
from native_desktop_factory.actor_deadline_future_v21 import (
    ActorDeadlineReached,DeadlineFuture,retrospective_timeout_origin,wait_budget,
)


class DeadlineFutureTests(unittest.TestCase):
    def setUp(self):
        self.now=10.0;self.waits=[]

    def future(self,advance,result='completed',error=None):
        owner=self
        class Future:
            def result(self,timeout):
                owner.waits.append(timeout);owner.now+=advance
                if error:raise error
                return result
        return Future()

    def test_subsecond_actor_budget_is_not_discarded_or_rounded(self):
        f=DeadlineFuture(self.future(.1),actor_deadline=10.25,clock=lambda:self.now)
        self.assertEqual(f.result(timeout=120),'completed')
        self.assertEqual(self.waits,[.25])

    def test_exact_fractional_remaining_is_forwarded_to_future(self):
        f=DeadlineFuture(self.future(1),actor_deadline=13.57152125,clock=lambda:self.now)
        f.result(timeout=120)
        self.assertAlmostEqual(self.waits[0],3.57152125)

    def test_actual_actor_deadline_timeout_is_explicit_and_poisoned(self):
        f=DeadlineFuture(self.future(3.57152125,error=TimeoutError()),actor_deadline=13.57152125,clock=lambda:self.now)
        with self.assertRaises(ActorDeadlineReached) as caught:f.result(timeout=120)
        self.assertTrue(caught.exception.proof.actor_deadline_reached)
        self.assertFalse(caught.exception.proof.model_completion_known)
        self.assertFalse(caught.exception.proof.receipt()['late_gui_application_authorized'])
        with self.assertRaisesRegex(ValueError,'consumed_future_wait'):f.result(timeout=120)
        self.assertEqual(len(self.waits),1)

    def test_independent_provider_timeout_before_actor_deadline_stays_provider_fault(self):
        error=TimeoutError('synthetic provider wait')
        f=DeadlineFuture(self.future(120,error=error),actor_deadline=730,clock=lambda:self.now)
        with self.assertRaises(TimeoutError) as caught:f.result(timeout=120)
        self.assertIs(caught.exception,error);self.assertIsNone(f.last_deadline_proof)

    def test_late_completed_result_is_retained_without_returning_an_action(self):
        value={'private_model_result':'synthetic'}
        f=DeadlineFuture(self.future(2,result=value),actor_deadline=11,clock=lambda:self.now)
        with self.assertRaises(ActorDeadlineReached) as caught:f.result(timeout=120)
        self.assertIs(caught.exception.late_result,value)
        self.assertTrue(caught.exception.proof.model_completion_known)
        self.assertEqual(caught.exception.proof.event,'model_response_completed_after_actor_deadline')

    def test_already_expired_future_has_no_second_provider_wait(self):
        f=DeadlineFuture(self.future(0),actor_deadline=9,clock=lambda:self.now)
        with self.assertRaises(ActorDeadlineReached):f.result(timeout=120)
        self.assertEqual(self.waits,[])

    def test_legacy_three_second_timeout_does_not_invent_literal_exhaustion_or_score(self):
        result=retrospective_timeout_origin(remaining_seconds=3.5715212500072084,
            legacy_wait_seconds=3,observed_wait_seconds=3.0011472500045784)
        self.assertEqual(result['status'],'actor_budget_constrained_timeout')
        self.assertAlmostEqual(result['estimated_remaining_after_timeout_seconds'],.57037400000263)
        self.assertFalse(result['literal_actor_deadline_exhaustion_proven'])
        self.assertIsNone(result['independent_task_score'])

    def test_uniform_policy_has_no_model_slot_or_checkpoint_exception(self):
        for _ in range(5):
            self.assertEqual(wait_budget(actor_deadline=720,provider_timeout=120,now=719.75),.25)

    def test_invalid_clock_or_timeout_is_refused(self):
        for value in [float('nan'),float('inf'),True]:
            with self.assertRaises(ValueError):wait_budget(actor_deadline=value,provider_timeout=120,now=0)
        with self.assertRaises(ValueError):wait_budget(actor_deadline=10,provider_timeout=0,now=0)
