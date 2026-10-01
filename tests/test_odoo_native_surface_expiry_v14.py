"""Real Unix lease + actual policy with fake UI/clock; zero live task credit."""
from contextlib import contextmanager
import dis
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import factory
import worker_lease
from cursibench import native_surface_guard_policy_v1 as policy
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v13 as old
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v14 as native
from enterprise_fallback.odoo18 import native_surface_workers_v13 as old_workers
from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from tests.test_odoo_native_surface_real_lease_v13 import NativePageFixture


class FakeClockPage(NativePageFixture):
    def __init__(self):
        super().__init__()
        self.expire_on_capture = None
        self.deadline = None

    def screenshot(self, **kwargs):
        raw = super().screenshot(**kwargs)
        if self.capture == self.expire_on_capture:
            self.tick = self.deadline
        return raw


@contextmanager
def held_fixture(module=native):
    """Use the real PID-bound Unix lease, never a provider or application."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve(); root.chmod(0o700)
        private, artifacts = root/'private', root/'artifacts'
        private.mkdir(mode=0o700); artifacts.mkdir(mode=0o700)
        credentials = private/'actor_credentials.json'
        credentials.write_text(json.dumps({'login':'source-fixture-actor','password':'synthetic-fixture'}))
        credentials.chmod(0o600)
        with patch.object(factory,'PRIVATE',private), patch.object(worker_lease,'PRIVATE',private), \
             patch.object(factory,'local_config',return_value={'ODOO_PORT':'8069','ODOO_PROJECT':'source_fixture'}), \
             patch('time.monotonic',return_value=1000.0):
            with worker_lease.exclusive_worker_operation('source_fixture_v14',root=private):
                page = FakeClockPage()
                adapter = module.OdooV066NativeSurfaceAdapter(page,task_id='source-fixture',
                    task_binding_sha256='a'*64,instruction='Synthetic source-only expiry fixture')
                adapter.clock = lambda:page.tick
                adapter._last_native_request = page.tick
                page.deadline = adapter.actor_clock.deadline
                with patch('time.monotonic',lambda:page.tick):
                    adapter.bind_guard(root=artifacts,worker_private=private)
                    yield adapter,page,private,artifacts


class NativeExpiryV14Tests(unittest.TestCase):
    def test_reproduces_v13_horizon_failure_with_263_seconds_remaining(self):
        with held_fixture(old) as (adapter,page,_private,root):
            page.tick = adapter.started + 456.6525215419824
            with self.assertRaisesRegex(policy.GuardError,'invalid_envelope'):
                adapter.observe_for_model()
            self.assertLess(page.tick,adapter.actor_clock.deadline)
            self.assertGreater(adapter.actor_clock.deadline-page.tick,262)
            self.assertEqual(page.calls,[])
            self.assertTrue((root/'surface-guard/turn-000/observation-native.private.json').exists())
            self.assertFalse((root/'surface-guard/turn-000/observation-envelope.private.json').exists())

    def test_v14_actual_observation_and_both_envelopes_are_capped_and_dispatch_still_audits(self):
        with held_fixture() as (adapter,page,_private,root):
            page.tick = adapter.started + 456.6525215419824
            observation,_ = adapter.observe_for_model()
            deadline = adapter.actor_clock.deadline
            self.assertEqual(observation.expires_at,deadline)
            self.assertLess(observation.issued_at,observation.expires_at)
            observed = json.loads((root/'surface-guard/turn-000/observation-envelope.private.json').read_bytes())
            self.assertEqual(observed['expires_at'],deadline)
            policy.validate_envelope(observed)
            action = adapter.parse_current_action('{"type":"type","text":"synthetic","mode":"insert"}')
            result = adapter.dispatch(action)
            self.assertEqual(result['status'],'applied')
            current = json.loads((root/'surface-guard/turn-000/predispatch-envelope.private.json').read_bytes())
            self.assertEqual(current['expires_at'],deadline)
            policy.validate_envelope(current)
            audited = workers.audit_native_contract(result['public_contract_receipt'],action,
                observation.screenshot_bytes,0,{'task_id':'source-fixture','package_sha256':'a'*64},root,
                observation_control_refs=sorted(c.ref for c in observation.controls if c.visible and c.enabled))
            self.assertEqual(audited['status'],'verified')
            self.assertEqual(audited['dispatch_status'],'applied')
            self.assertEqual(audited['profile'],'native-owned-surface-safety-envelope-v14')

    def test_held_lease_can_shorten_but_never_extend_actual_frame_or_actor_expiry(self):
        with held_fixture() as (adapter,page,_private,root):
            page.tick = adapter.started + 456
            adapter.boundary.lease['expires_at'] = adapter.started + 500
            observation,_ = adapter.observe_for_model()
            self.assertEqual(observation.expires_at,adapter.started+500)
            observed = json.loads((root/'surface-guard/turn-000/observation-envelope.private.json').read_bytes())
            policy.validate_envelope(observed)
            self.assertEqual(observed['expires_at'],observation.expires_at)
            self.assertEqual(adapter.actor_clock.deadline-adapter.started,720)

    def test_exact_720_deadline_is_typed_before_any_new_capture(self):
        with held_fixture() as (adapter,page,_private,root):
            page.tick = adapter.actor_clock.deadline
            before = page.capture
            with self.assertRaises(ActorDeadlineReached) as caught:
                adapter.observe_for_model()
            self.assertEqual(page.capture,before)
            self.assertEqual(page.calls,[])
            proof = caught.exception.proof
            self.assertTrue(proof.actor_deadline_reached)
            self.assertEqual(proof.actor_deadline_monotonic,adapter.started+720)
            stop = json.loads(next((root/'actor-clock').glob('stop-*.private.json')).read_bytes())
            self.assertEqual(stop['stage'],'before_native_observation_capture')
            self.assertFalse(stop['native_io_called'])

    def test_capture_returning_at_deadline_is_typed_and_unpublished(self):
        with held_fixture() as (adapter,page,_private,root):
            page.tick = adapter.actor_clock.deadline-1
            page.expire_on_capture = 3  # two readiness captures, then the actual frame
            with self.assertRaises(ActorDeadlineReached):
                adapter.observe_for_model()
            stop = json.loads(next((root/'actor-clock').glob('stop-*.private.json')).read_bytes())
            self.assertEqual(stop['stage'],'after_native_observation_capture')
            self.assertEqual(page.capture,3)
            self.assertEqual(page.calls,[])
            self.assertIsNone(adapter.latest)
            self.assertFalse((root/'surface-guard/turn-000/observation-envelope.private.json').exists())

    def test_expired_original_frame_before_actor_deadline_remains_guard_rejection(self):
        with held_fixture() as (adapter,page,_private,root):
            page.tick = adapter.started+100
            observation,_ = adapter.observe_for_model()
            action = adapter.parse_current_action('{"type":"type","text":"synthetic","mode":"insert"}')
            page.tick = observation.expires_at+1
            self.assertLess(page.tick,adapter.actor_clock.deadline)
            result = adapter.dispatch(action)
            self.assertEqual(result['status'],'rejected')
            self.assertEqual(page.calls,[])
            current = json.loads((root/'surface-guard/turn-000/predispatch-envelope.private.json').read_bytes())
            policy.validate_envelope(current)
            self.assertGreater(current['expires_at'],current['captured_at'])
            self.assertLessEqual(current['expires_at'],adapter.actor_clock.deadline)
            self.assertTrue((root/f'surface-guard/nonces/{observation.frame_id}.consumed.private.json').exists())

    def test_false_native_principal_is_still_rejected(self):
        with held_fixture() as (adapter,page,_private,_root):
            page.uid = 'res.partner:999'
            with self.assertRaises(policy.GuardError):
                adapter.observe_for_model()
            self.assertEqual(page.calls,[])

    def test_guard_rejection_and_nonce_consumption_remain_truthful(self):
        with held_fixture() as (adapter,page,_private,root):
            page.tick = adapter.started+456
            observation,_ = adapter.observe_for_model()
            page.focus = 'body'
            action = adapter.parse_current_action('{"type":"type","text":"synthetic","mode":"insert"}')
            result = adapter.dispatch(action)
            self.assertEqual(result['status'],'rejected')
            self.assertEqual(page.calls,[])
            self.assertEqual(adapter.step,1)
            self.assertIsNone(adapter.latest)
            self.assertTrue((root/f'surface-guard/nonces/{observation.frame_id}.consumed.private.json').exists())


class NativeV14SourceBindingTests(unittest.TestCase):
    def test_old_binding_and_class_remain_unchanged_after_loading_v14(self):
        self.assertEqual(old_workers.public_binding()['binding_sha256'],
                         '56b3e77c254c5dd38d6bbaebf4661d3d71a7d053de44c942e055f0adf89842f4')
        self.assertEqual(sha256(Path(old.__file__).read_bytes()).hexdigest(),
                         '1b4a8235950826f9e318cd72e0d9f31c39dfcb7177512f3e62d9fa0684b220cb')
        self.assertEqual(old.PROFILE,'native-owned-surface-safety-envelope-v13')
        self.assertIsNot(old.OdooV066NativeSurfaceAdapter,native.OdooV066NativeSurfaceAdapter)
        self.assertIsNot(old._impl,native._parent._impl)

    def test_all_execution_roles_share_the_exact_v14_adapter_and_original_scoring_sources(self):
        binding = workers.public_binding(); workers.validate_binding(binding)
        teacher,selection = workers._model_modules(binding)
        self.assertIs(teacher.OdooV066TrainAdapter,native.OdooV066NativeSurfaceAdapter)
        self.assertIs(selection.OdooV066TrainAdapter,native.OdooV066NativeSurfaceAdapter)
        self.assertIs(workers.common_adapter_class(),native.OdooV066NativeSurfaceAdapter)
        evaluator = workers.evaluator_module(binding)
        imports = [instruction.argval for instruction in dis.get_instructions(evaluator.execute_case)
                   if instruction.opname=='IMPORT_NAME']
        self.assertIn(workers.ADAPTER_MODULE,imports)
        from enterprise_fallback.odoo18 import native_surface_final_worker_v1 as final
        self.assertEqual(final.module_from_binding(binding),workers.__name__)
        self.assertIs(final._worker_module(workers.__name__).common_adapter_class(),native.OdooV066NativeSurfaceAdapter)
        previous = old_workers.public_binding()
        for path in ('enterprise_fallback/odoo18/verify.py','enterprise_fallback/odoo18/reset.py',
                     'enterprise_fallback/odoo18/partition_factory.py',
                     'enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py'):
            self.assertEqual(binding['source_sha256s'][path],previous['source_sha256s'][path])
        self.assertEqual(binding['native_adapter_binding']['max_actions'],90)
        self.assertEqual(binding['native_adapter_binding']['wall_seconds'],720)
        self.assertEqual(binding['native_surface_policy_sha256'],policy.POLICY_SHA)

    def test_new_binding_and_current_sources_require_fresh_qualification_not_v13_credit(self):
        binding = workers.public_binding()
        epoch = binding['source_epoch']
        self.assertEqual(epoch['native'],'v14')
        self.assertEqual(epoch['historical_control_credit'],0)
        self.assertEqual(epoch['v13_positive_control_credit'],0)
        self.assertTrue(epoch['fresh_train_full20_full100_required'])
        self.assertEqual(binding['old_positive_credit'],0)
        self.assertEqual(binding['official_final_tasks_admitted'],0)
        self.assertEqual(binding['model_attempts'],0)
        for name in ('enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v14.py',
                     'enterprise_fallback/odoo18/native_surface_workers_v14.py',
                     'tools/odoo_v066_native_surface_qualification_v14.py'):
            self.assertEqual(binding['source_sha256s'][name],sha256((workers._ROOT/name).read_bytes()).hexdigest())
        with self.assertRaises(workers.NativeMaterialWorkerError):
            workers.validate_binding(old_workers.public_binding())


if __name__=='__main__':
    unittest.main()
