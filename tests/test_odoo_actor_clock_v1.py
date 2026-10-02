"""Actual current native guard clock with real lease; no native/provider calls."""
import json
import unittest
from test_odoo_native_surface_real_lease_v12 import held_fixture,native,workers
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from enterprise_fallback.odoo18.odoo_actor_clock_v1 import LateNativeCompletion


class ActorClockTests(unittest.TestCase):
    def test_actual_native_start_deadline_io_and_end_before_evaluation(self):
        with held_fixture() as (adapter,page,_private,root):
            observation,_=adapter.observe_for_model()
            action=adapter.parse_current_action('{"type":"click","target":{"x":350,"y":50}}')
            result=adapter.dispatch(action)
            self.assertEqual(result['status'],'applied')
            clock=adapter.actor_clock
            self.assertEqual(clock.started,adapter.started)
            self.assertEqual(clock.deadline,adapter.started+720)
            self.assertEqual(len(clock.events),1)
            self.assertEqual(clock.events[0]['status'],'returned')
            clock.end('model_finish')
            raw=json.loads((root/'actor-clock/end.private.json').read_bytes())
            self.assertEqual(raw['native_actions_after_deadline'],0)
            self.assertEqual(raw['end_boundary'],'before_evaluator_gui_reload_saved_readback_and_reset')
            self.assertLessEqual(raw['actor_ended_monotonic'],raw['actor_deadline_monotonic'])

    def test_deadline_before_dispatch_has_no_gui_and_exact_typed_proof(self):
        with held_fixture() as (adapter,page,_private,root):
            adapter.observe_for_model()
            action=adapter.parse_current_action('{"type":"click","target":{"x":350,"y":50}}')
            page.tick=adapter.actor_clock.deadline
            with self.assertRaises(ActorDeadlineReached) as caught:adapter.dispatch(action)
            self.assertEqual(page.calls,[])
            self.assertTrue(caught.exception.proof.actor_deadline_reached)
            adapter.actor_clock.end('task_wall_budget',deadline_exception=caught.exception)
            raw=json.loads((root/'actor-clock/end.private.json').read_bytes())
            self.assertEqual(raw['actor_elapsed_seconds'],720)
            self.assertEqual(raw['native_actions_after_deadline'],0)
            self.assertFalse(list((root/'surface-guard').glob('turn-000/driver-*')))

    def test_late_native_completion_is_retained_and_never_admitted(self):
        with held_fixture() as (adapter,page,_private,root):
            adapter.observe_for_model()
            action=adapter.parse_current_action('{"type":"click","target":{"x":350,"y":50}}')
            def slow(*_args):page.calls.append(('actual_started',));page.tick=adapter.actor_clock.deadline+0.01
            page.mouse.click=slow
            with self.assertRaises(native.GuardDriverUncertain):adapter.dispatch(action)
            self.assertEqual(page.calls,[('actual_started',)])
            self.assertGreater(adapter.actor_clock.events[0]['completed_monotonic'],adapter.actor_clock.deadline)
            with self.assertRaises(Exception):adapter.actor_clock.end('model_finish')
            self.assertFalse((root/'actor-clock/end.private.json').exists())

    def test_early_native_transport_fault_is_not_an_actor_deadline(self):
        with held_fixture() as (adapter,page,_private,root):
            adapter.observe_for_model()
            action=adapter.parse_current_action('{"type":"click","target":{"x":350,"y":50}}')
            def broken(*_args):raise TimeoutError('synthetic early native fault')
            page.mouse.click=broken
            with self.assertRaises(native.GuardDriverUncertain):adapter.dispatch(action)
            self.assertLess(page.tick,adapter.actor_clock.deadline)
            self.assertIsNone(adapter.actor_clock.deadline_exception)
            self.assertEqual(adapter.actor_clock.events[0]['status'],'unknown')
            self.assertFalse((root/'actor-clock/end.private.json').exists())


if __name__=='__main__':unittest.main()
