"""Offline V46 pair safety and uniform closure; no native qualification claim."""
import json
from pathlib import Path
import tempfile
import time
from types import MethodType,SimpleNamespace
import unittest
from unittest.mock import patch

from cursibench import native_surface_guard_policy_v1 as guard
from native_desktop_factory import common_native_guest_v31 as common
from native_desktop_factory import semantic_native_transport_v23 as transport
from native_desktop_factory import native_editor_runtime_v45 as old
from native_desktop_factory import native_editor_reader_v45 as old_reader
from native_desktop_factory import native_editor_evidence_v45 as old_evidence
from native_desktop_factory import native_guarded_observation_runtime_v46 as current
from tests import test_native_desktop_semantic_native_transport_v23 as synthetic


class ObservationPairTests(unittest.TestCase):
    def fixture(self):
        fixture=synthetic.SemanticTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        factory=current.factory(manifest=current.source_manifest())
        actor=object.__new__(factory.actor_class);actor.__dict__.update(fixture.actor.__dict__)
        actor.requested_points=[];actor.last_native_point=None
        actor.native_probe=MethodType(transport.SemanticModelGuest.native_probe,actor)
        fixture.actor=actor
        return fixture

    def observe(self,fixture,step=0):
        return fixture.actor.observe(identity={'task_id':'offline-fixture','package_sha256':'e'*64},
            instruction='Public synthetic fixture',step=step)

    def test_pending_observation_uses_one_original_capture_pair_and_honest_receipt(self):
        fixture=self.fixture();fixture.actor.pending=True
        with patch.object(transport.time,'sleep',side_effect=AssertionError('Extra readiness delay forbidden')):
            observation=self.observe(fixture)
        probes=[json.loads(p.read_bytes()) for p in sorted(fixture.out.glob('native-probe-*.private.json'))]
        self.assertEqual([p['phase'] for p in probes],['observation-before','observation-after'])
        self.assertEqual(fixture.images,1);self.assertEqual(fixture.native_calls,[])
        receipts=list(fixture.out.glob('semantic-readiness-*.private.json'))
        self.assertEqual(len(receipts),1)
        saved=json.loads(receipts[0].read_bytes())
        self.assertEqual(saved['observation_policy'],'native-guarded-observation-pairs-v46')
        self.assertFalse(saved['last_four_samples_claimed']);self.assertFalse(saved['pixel_equality_required'])
        self.assertFalse(fixture.actor.pending);self.assertIs(fixture.actor.last_observation,observation)

    def test_observation_pair_instability_refuses_before_observation_or_input(self):
        for field,replacement in [('window_id_sha256','f'*64),('native_pid',999),
                ('native_uid',2000),('owned_document_window',False),('owned_native_application',False),
                ('view_id','foreign'),('context_id','other-context'),('modal_id','dialog'),('focus_id','other-focus')]:
            with self.subTest(field=field):
                fixture=self.fixture();fixture.actor.pending=True
                screenshot=fixture.sandbox.screenshot
                def changed_capture():
                    image=screenshot();fixture.meta[field]=replacement;return image
                fixture.sandbox.screenshot=changed_capture
                with self.assertRaisesRegex(ValueError,'Native context changed across screenshot capture'):
                    self.observe(fixture)
                self.assertEqual(fixture.images,1);self.assertEqual(fixture.native_calls,[])
                self.assertIsNone(fixture.actor.last_observation);self.assertEqual(fixture.actor.consumed,set())
                self.assertTrue(fixture.actor.pending)

    def test_target_state_instability_in_pair_refuses_before_input(self):
        fixture=self.fixture();fixture.actor.pending=True;screenshot=fixture.sandbox.screenshot
        def changed_capture():
            image=screenshot();fixture.meta['targets'][0]['enabled']=False;return image
        fixture.sandbox.screenshot=changed_capture
        with self.assertRaisesRegex(ValueError,'Native context changed across screenshot capture'):
            self.observe(fixture)
        self.assertEqual(fixture.native_calls,[]);self.assertIsNone(fixture.actor.last_observation)

    def test_predispatch_pair_instability_refuses_before_input_or_nonce_consumption(self):
        fixture=self.fixture();observation=self.observe(fixture);screenshot=fixture.sandbox.screenshot
        def changed_capture():
            image=screenshot();fixture.meta['context_id']='changed-during-predispatch';return image
        fixture.sandbox.screenshot=changed_capture
        with self.assertRaisesRegex(ValueError,'Native context changed across screenshot capture'):
            fixture.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',observation,
                actor_deadline=time.monotonic()+720)
        self.assertEqual(fixture.native_calls,[]);self.assertEqual(fixture.actor.consumed,set())

    def test_original_guard_rejects_disabled_current_target_and_consumes_nonce(self):
        fixture=self.fixture();fixture.actor.pending=True;observation=self.observe(fixture)
        fixture.meta['targets'][0]['enabled']=False
        _,receipt=fixture.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',
            observation,actor_deadline=time.monotonic()+720)
        self.assertEqual(receipt['native_status'],'rejected');self.assertEqual(fixture.native_calls,[])
        self.assertIn(observation.frame_id,fixture.actor.consumed)
        self.assertEqual(fixture.images,2)
        with self.assertRaisesRegex(ValueError,'Current semantic native frame/clock required'):
            fixture.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',
                observation,actor_deadline=time.monotonic()+720)

    def test_original_guard_hard_stops_foreign_window_and_expired_actor_before_input(self):
        fixture=self.fixture();observation=self.observe(fixture);fixture.meta['window_id_sha256']='f'*64
        with self.assertRaises(guard.GuardError):
            fixture.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',
                observation,actor_deadline=time.monotonic()+720)
        self.assertEqual(fixture.native_calls,[]);self.assertTrue(fixture.actor.quarantined)
        fixture=self.fixture();observation=self.observe(fixture)
        with self.assertRaisesRegex(ValueError,'Current semantic native frame/clock required'):
            fixture.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',
                observation,actor_deadline=time.monotonic()-1)
        self.assertEqual(fixture.native_calls,[]);self.assertEqual(fixture.images,1)

    def test_original_inactive_lease_and_current_readonly_keyboard_target_refuse_input(self):
        fixture=self.fixture();observation=self.observe(fixture)
        fixture.sandbox.is_running=lambda **kwargs:False
        with self.assertRaises(guard.GuardError):
            fixture.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',
                observation,actor_deadline=time.monotonic()+720)
        self.assertEqual(fixture.native_calls,[])
        fixture=self.fixture();observation=self.observe(fixture)
        fixture.meta['targets'][0]['keyboard']=False
        _,receipt=fixture.actor.dispatch_model('{"type":"type","target":{"x":40,"y":40},"text":"synthetic","mode":"fill"}',
            observation,actor_deadline=time.monotonic()+720)
        self.assertEqual(receipt['native_status'],'rejected');self.assertEqual(fixture.native_calls,[])
        self.assertIn(observation.frame_id,fixture.actor.consumed)

    def test_all_roles_share_new_observe_and_original_guard_methods_without_mutating_v45(self):
        modules=(old,old_reader,old_evidence,transport)
        snapshots={module:(Path(module.__file__).read_bytes(),dict(vars(module))) for module in modules}
        old_manifest=old.source_manifest();previous=old.factory(manifest=old_manifest)
        original_methods={name:getattr(previous.actor_class,name) for name in ('observe','capture','envelope','lease_check','native_input','dispatch_model')}
        manifest=current.source_manifest();factory=current.factory(manifest=manifest)
        actors=[]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for role in common.ACTOR_PATHS:
                for filename in ('fixture.xlsx','fixture.docx','fixture.pptx'):
                    out=root/role/Path(filename).suffix[1:];out.mkdir(mode=0o700,parents=True)
                    actor=factory.wrap_owned_guest(SimpleNamespace(sandbox_id='offline-'+role,
                        commands=SimpleNamespace(),files=SimpleNamespace()),root=root,out=out,
                        filename=filename,lease_started_monotonic=time.monotonic())
                    actors.append(actor);self.assertIs(type(actor),factory.actor_class)
                    self.assertIs(actor.observe.__func__,factory.actor_class.observe)
            self.assertEqual(len(actors),21)
        self.assertIsNot(factory.actor_class.observe,original_methods['observe'])
        for name in ('capture','envelope','lease_check','native_input'):
            self.assertIs(getattr(factory.actor_class,name),original_methods[name])
        self.assertIs(factory.actor_class.dispatch_model.__code__,original_methods['dispatch_model'].__code__)
        self.assertIs(transport.guard.decision,guard.decision)
        for name,value in original_methods.items():self.assertIs(getattr(previous.actor_class,name),value)
        for module,(raw,attributes) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(),raw);self.assertEqual(dict(vars(module)),attributes)
        self.assertEqual(old.source_manifest(),old_manifest)

    def test_source_closure_names_amendment_preserves_budgets_and_refuses_formal_activation(self):
        manifest=current.source_manifest();before=old.source_manifest()
        for name,digest in before['source_sha256s'].items():self.assertEqual(manifest['source_sha256s'][name],digest)
        for name in current.EXTRA:self.assertIn(name,manifest['source_sha256s'])
        self.assertEqual(manifest['task_policy'],before['task_policy'])
        self.assertEqual(manifest['task_policy'],{'max_actions':90,'actor_seconds':720,'lease_seconds':1200})
        policy=manifest['observation_policy']
        self.assertEqual(policy['scope'],'all_seven_actor_paths');self.assertEqual(policy['observation_captures_per_turn'],1)
        self.assertTrue(policy['before_after_metadata_equality_required'])
        self.assertTrue(policy['native_guard_decision_unchanged']);self.assertFalse(policy['old_last_four_readiness_samples_required'])
        self.assertFalse(policy['enter_resampling_changed']);self.assertFalse(manifest['native_qualification_passed'])
        self.assertFalse(manifest['old_results_reclassified']);self.assertFalse(manifest['actor_office_api_available'])
        with self.assertRaisesRegex(ValueError,'Fresh common native qualification'):
            current.factory(manifest=manifest).require_activation()

if __name__=='__main__':unittest.main()
