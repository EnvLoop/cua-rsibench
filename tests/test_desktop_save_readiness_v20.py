"""Shared Save-transition settling before a fresh exact guarded observation."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from native_desktop_factory import save_readiness_v20 as ready
from native_desktop_factory import pre_observation_readiness_v18 as old
from native_desktop_factory import selection_control_save_epoch_v20 as epoch
from native_desktop_factory import selection_control_save_worker_v20 as worker
from native_desktop_factory import selection_control_post_enter_epoch_v19 as v19
from native_desktop_factory import selection_control_readiness_epoch_v18 as v18
from native_desktop_factory import post_enter_component_v19 as component
from native_desktop_factory import v066_post_enter_control_attempt_v9 as core
from native_desktop_factory import qwen_v066_adapter_v4_strict as strict
from native_desktop_factory import uniform_model_transport_v11 as model
from native_desktop_factory import model_transport_integration_v11 as integration
from native_desktop_factory.factory import digest
from tests.test_desktop_focus_readiness_v12 import Native, Clock, png
from tests.test_native_desktop_selection_worker_v066 import source_case
from tests.test_desktop_ancestor_accounting_v13 import intent

SAVE = {'type': 'key', 'key': 'Control+S'}
WAIT = '{"type":"wait","duration_ms":2000}'


class SaveTests(unittest.TestCase):
    def test_only_save_trigger_added_original_capture_rules_and_limits_reused(self):
        self.assertFalse(old.needs_readiness(SAVE)); self.assertTrue(ready.needs_readiness(SAVE))
        for action in [{'type': 'key', 'key': 'Control+A'}, {'type': 'key', 'key': 'Escape'},
                       {'type': 'type', 'text': 'public', 'mode': 'insert'}, {'type': 'click', 'target': {'x': 5, 'y': 5}}]:
            self.assertEqual(ready.needs_readiness(action), old.needs_readiness(action))
        self.assertIs(ready.passive_samples, old.passive_samples); self.assertIs(ready.settled_suffix, old.settled_suffix)
        self.assertEqual(ready.MAX_WALL_MS, 60_000); self.assertEqual(ready.SAMPLE_DELAYS_MS, old.SAMPLE_DELAYS_MS)

    def test_original_material_guard_rejects_preexisting_save_animation(self):
        from cursibench.scale_action_contract import make_observation
        a, b = png(), png(material=True)
        native = Native([b])
        observation = make_observation(task_id='public.synthetic', task_binding_sha256='a' * 64,
            instruction='Visible synthetic UI.', step=1, screenshot_bytes=a, previous_action_result={'status': 'applied', 'code': 'ok'})
        with self.assertRaises(strict.MaterialFrameDrift):strict.parse_current_action(WAIT, observation, native)
        self.assertEqual(native.inputs, [])

    def test_all_five_actual_model_guests_save_once_then_return_full_stable_frame_and_exact_parse(self):
        a, b = png(), png(material=True)
        for owner in ['shared-base', *integration.matrix.RESEARCHERS]:
            with TemporaryDirectory() as tmp:
                root = Path(tmp); out = root / 'fixture/actor'; out.mkdir(parents=True)
                native = Native([a, a, b, b, b, b, b, b])
                native.get_window_title = lambda _id: 'Confirm File Format'
                guest = model.ModelGuest(native, root=root, out=out, filename='train.xlsx')
                with model.evidence_scope(root, out):ready.dispatch(guest.proxy, SAVE)
                original = ready.passive_samples; clock = Clock()
                with patch.object(ready, 'passive_samples', lambda sb, **kwargs:
                          original(sb, clock=clock.clock, sleep=clock.sleep, **kwargs)):
                    observation = guest.observe(identity={'task_id': 'fixture', 'package_sha256': 'a' * 64},
                        instruction='Visible synthetic Save dialog.', step=1, previous={'status': 'applied', 'code': 'ok'})
                self.assertEqual(observation.screenshot_bytes, b)
                self.assertEqual(native.inputs, [('key', ['ctrl', 's'])])
                self.assertEqual(len((out / 'pre-observation-readiness-v12.ndjson').read_bytes().splitlines()), 7)
                self.assertEqual(strict.parse_current_action(WAIT, observation, native)['type'], 'wait')
                (out / 'frame-01-0.png').write_bytes(b)
                self.assertEqual(ready.audit_samples(root, out, [SAVE, {'type': 'wait', 'duration_ms': 2000}], {}), 1)
        proposal = integration.proposal()
        self.assertIs(model.readiness, ready)
        self.assertEqual(proposal['passive_readiness_recipe'], ready.RECIPE)
        self.assertEqual(proposal['passive_readiness_source_sha256'], digest(Path(ready.__file__).read_bytes()))
        self.assertEqual((proposal['max_actor_actions'], proposal['max_actor_wall_seconds'], proposal['lease_seconds_each']), (90, 720, 1200))

    def test_drift_after_settled_observation_and_window_change_remain_fatal(self):
        from cursibench.scale_action_contract import make_observation
        a, b = png(), png(material=True)
        observation = make_observation(task_id='public.synthetic', task_binding_sha256='a' * 64,
            instruction='Visible synthetic UI.', step=1, screenshot_bytes=a, previous_action_result={'status': 'applied', 'code': 'ok'})
        with self.assertRaises(strict.MaterialFrameDrift):strict.parse_current_action(WAIT, observation, Native([b]))
        native = Native([a] * 7); native.ids = iter(['first', 'first', 'different'])
        clock = Clock()
        with self.assertRaisesRegex(ValueError, 'window or time'):
            ready.passive_samples(native, clock=clock.clock, sleep=clock.sleep)
        with self.assertRaisesRegex(ValueError, 'did not settle'):
            clock = Clock(); ready.passive_samples(Native([a] * 6 + [b]), clock=clock.clock, sleep=clock.sleep)

    def test_control_context_binds_same_save_trigger_and_restores_all_ancestors(self):
        before = (strict.observe, strict.dispatch, core.epoch)
        with worker.context():
            self.assertIs(strict.observe, ready.observe); self.assertIs(strict.dispatch, ready.dispatch)
            self.assertIs(core.epoch, epoch); self.assertIs(core.PostEnterControlProxyV9, component.PostEnterControlProxyV19)
        self.assertEqual((strict.observe, strict.dispatch, core.epoch), before)

    def test_new_history_retains_closed_v19_lease_and_old_sources(self):
        with TemporaryDirectory() as tmp:
            broad = Path(tmp); old18 = broad / 'v18'; closed19 = broad / 'v19'; own = broad / 'v20'
            intent(broad / 'past', 600); old = epoch.ORIGINAL_ACCOUNTING([broad], exclude=old18)
            intent(old18); parent = epoch.ORIGINAL_ACCOUNTING([broad], exclude=closed19)
            prior = intent(closed19); manifest = epoch.ORIGINAL_MANIFEST([broad], exclude=own); intent(own)
            with epoch.parent_history(own):
                self.assertEqual(v19.ORIGINAL_ACCOUNTING([broad], exclude=closed19), parent)
                with v19.parent_history(closed19):self.assertEqual(v18.ORIGINAL_ACCOUNTING([broad], exclude=old18), old)
            self.assertEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), manifest)
            self.assertEqual(epoch.ORIGINAL_ACCOUNTING([broad], exclude=own)['past_full_lease_seconds'], 3000)
            prior.write_bytes(prior.read_bytes() + b' ')
            self.assertNotEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), manifest)

    def test_real_inherited_control_writes_intent_then_hits_fake_create_once_under_v20(self):
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp); own = root / 'attempts'; candidate = root / 'candidate'; candidate.mkdir()
            package = root / 'package'; package.mkdir()
            source, _neutral, _positive, oracle, extension = source_case('calc-growth')
            (package / ('fixture' + extension)).write_bytes(source); (package / 'actor_task.txt').write_text('Public synthetic task.')
            row = {'task_id': 'fixture', 'package_sha256': 'a' * 64, 'split': 'selection', 'workflow': 'calc-growth'}
            epoch.accounting._write_new(candidate / 'candidate-inventory.json', {'tasks': [row]})
            salt = root / 'map.private.json'; epoch.accounting._write_new(salt, {'variant_salt': 'fixture-' * 8})
            guest = root / 'guest.json'; guest.write_text('{}'); scoped = root / 'scoped.json'; scoped.write_text('{}')
            ratification = root / 'ratification.json'; ratification.write_text('{}')
            freeze = root / 'freeze.private.json'; epoch.accounting._write_new(freeze, {'offline': True})
            value = {'_freeze_sha256': digest(freeze.read_bytes()), 'source_sha256s': epoch.source_hashes(), 'bounded_transport_recipe': epoch.parent.parent.transport.RECIPE,
                'roster': [row], 'attempts_root': str(own), 'candidate_root': str(candidate), 'private_map': str(salt),
                'guest_public': str(guest), 'scoped_reference': str(scoped), 'ratification': str(ratification)}
            permit = root / 'permit.private.json'
            epoch.accounting._write_new(permit, {'schema': epoch.PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'],
                'source_sha256s': value['source_sha256s'], **{k: row[k] for k in ('task_id', 'package_sha256', 'split')},
                'post_enter_recipe': component.RECIPE, 'bounded_transport_recipe': epoch.parent.parent.transport.RECIPE, 'passive_readiness_recipe': epoch.READINESS_RECIPE,
                'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
                'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
            calls = []
            class FakeBoundary(Exception):pass
            class Sandbox:
                @staticmethod
                def create(**kwargs):
                    assert (own / 'fixture/positive/intent.json').is_file()
                    assert (own / 'fixture/positive/child-started.json').is_file()
                    assert strict.observe is ready.observe and strict.dispatch is ready.dispatch
                    assert core.epoch is epoch
                    assert core.PostEnterControlProxyV9 is component.PostEnterControlProxyV19
                    calls.append(kwargs); raise FakeBoundary()
            stack.enter_context(patch.dict('sys.modules', {'e2b_desktop': SimpleNamespace(Sandbox=Sandbox)}))
            stack.enter_context(patch.dict(os.environ, {'E2B_API_KEY': 'offline-fixture'}))
            stack.enter_context(patch.object(epoch, 'validate', return_value=value))
            stack.enter_context(patch.object(core.admit, '_package', return_value=(package, source, oracle)))
            stack.enter_context(patch.object(core, 'validate_reference', return_value=({'applications': {'calc': 'b' * 64}}, 'b' * 64)))
            stack.enter_context(patch.object(core, 'storage_audit', return_value={'dispatch_storage_ready': True}))
            stack.enter_context(patch.object(core.importlib.metadata, 'version', side_effect=lambda name:
                {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}[name]))
            stack.enter_context(patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes', return_value=([], 0)))
            with self.assertRaisesRegex(ValueError, 'no subsequent create or replay'):
                worker.run_trio(freeze_path=freeze, permit_path=permit, enable_paid_controls=True)
            self.assertEqual(len(calls), 1); self.assertEqual(calls[0]['timeout'], 1200)
            self.assertEqual(json.loads((own / 'fixture/positive/receipt.json').read_bytes())['error_type'], 'FakeBoundary')
            with self.assertRaises(ValueError):worker.run_trio(freeze_path=freeze, permit_path=permit, enable_paid_controls=True)
            self.assertEqual(len(calls), 1)


if __name__ == '__main__':unittest.main()
