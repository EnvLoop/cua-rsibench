"""Real request journal and typed deadline primitive; synthetic future only."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_odoo_native_surface_real_lease_v12 import held_fixture,workers
from tests.test_scale_vision_proxy import FakeBackend
from enterprise_fallback.odoo18.odoo_actor_transport_v1 import sampler_class
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached


class ActorTransportTests(unittest.TestCase):
    def sampler(self,adapter,page,root,*,delay,timeout=False):
        selection=workers._model_modules(workers.public_binding())[1]
        cls=sampler_class(selection)
        sample=cls(checkpoint_path='Qwen/Qwen3.8-27B',config={'seed':23,'sample_max_tokens':512},
            output_root=root,attempt_id='actual-parent-reservation',base_mode=True,expected_base_checkpoint_sha256='a'*64)
        sample.actor_clock=adapter.actor_clock
        backend=FakeBackend()
        def submit(*_args):
            backend.submissions.append('actual-single-submission')
            class Future:
                def result(self,timeout=None):
                    backend.timeouts.append(timeout);page.tick+=delay
                    if timeout is not None and delay>=timeout and timeout_flag:raise TimeoutError('synthetic future timeout')
                    return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1,2,3],stop_reason='stop')])
            return Future()
        timeout_flag=timeout;backend.submit=submit;sample.backend=backend
        return sample,selection,backend

    def test_fractional_remaining_clips_same_future_and_preserves_unknown_output_tokens(self):
        with held_fixture() as (adapter,page,_private,root):
            observation,_=adapter.observe_for_model()
            page.tick=adapter.actor_clock.deadline-0.375
            sampler,_selection,backend=self.sampler(adapter,page,root,delay=.375,timeout=True)
            with self.assertRaises(ActorDeadlineReached) as caught:
                sampler.sample(observation,task_index=0,step=0,task_dir=root)
            self.assertEqual(backend.timeouts,[.375])
            self.assertEqual(len(backend.submissions),1)
            self.assertTrue(caught.exception.proof.actor_deadline_reached)
            self.assertIsNone(sampler.last_raw_result['usage']['output_tokens'])
            self.assertEqual(sampler.last_raw_result['status'],'error')
            self.assertTrue((root/'sampling-journal/requests.sqlite3').exists())
            self.assertEqual(page.calls,[])

    def test_earlier_provider_timeout_keeps_provider_fault_type(self):
        with held_fixture() as (adapter,page,_private,root):
            observation,_=adapter.observe_for_model()
            sampler,selection,backend=self.sampler(adapter,page,root,delay=120,timeout=True)
            with self.assertRaises(selection.SelectionProviderUncertain):
                sampler.sample(observation,task_index=0,step=0,task_dir=root)
            self.assertLess(page.tick,adapter.actor_clock.deadline)
            self.assertEqual(backend.timeouts,[120])
            self.assertIsNone(sampler.last_deadline_reference)
            self.assertEqual(page.calls,[])

    def test_known_late_response_retained_without_decoding_or_gui(self):
        with held_fixture() as (adapter,page,_private,root):
            observation,_=adapter.observe_for_model();page.tick=adapter.actor_clock.deadline-.125
            sampler,_selection,backend=self.sampler(adapter,page,root,delay=.2)
            with self.assertRaises(ActorDeadlineReached) as caught:
                sampler.sample(observation,task_index=0,step=0,task_dir=root)
            self.assertTrue(caught.exception.proof.model_completion_known)
            self.assertEqual(sampler.last_deadline_result['late_response_sequences'][0]['tokens'],[1,2,3])
            self.assertEqual(page.calls,[])
            self.assertEqual(len(backend.submissions),1)


if __name__=='__main__':unittest.main()
