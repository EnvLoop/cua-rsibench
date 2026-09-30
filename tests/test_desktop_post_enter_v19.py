"""Exact observed Enter latency replay with unchanged material/window rules."""
from contextlib import ExitStack
import inspect
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from native_desktop_factory import post_enter_component_v19 as component
from native_desktop_factory import post_enter_control_proxy_v9 as old
from native_desktop_factory import post_enter_train_probe_v1 as train
from native_desktop_factory import v066_post_enter_control_audit_v9 as old_audit
from native_desktop_factory import selection_control_post_enter_epoch_v19 as epoch
from native_desktop_factory import selection_control_post_enter_worker_v19 as worker
from native_desktop_factory import selection_control_readiness_epoch_v18 as v18
from native_desktop_factory import selection_control_bounded_epoch_v17 as v17
from native_desktop_factory import pre_observation_readiness_v18 as ready
from native_desktop_factory import qwen_v066_adapter_v4_strict as strict
from native_desktop_factory import v066_post_enter_control_attempt_v9 as core
from native_desktop_factory import uniform_model_transport_v11 as model
from native_desktop_factory import model_transport_integration_v11 as integration
from native_desktop_factory import prospective_model_worker_v11 as model_worker
from native_desktop_factory.factory import digest
from tests.test_native_desktop_post_enter_train_probe_v1 import Guest, png
from tests.test_native_desktop_selection_worker_v066 import source_case
from tests.test_desktop_ancestor_accounting_v13 import intent

ELAPSED = (4877414125, 12427224542, 19116673750, 24644692625, 30117549792)
CAPTURE = (4877402083, 7273112584, 6414671792, 5245409000, 5204087542)


def make_proxy(cls, root, frames, *, times=None, titles=None):
    out = root / 'fixture/actor'; out.mkdir(parents=True)
    native = Guest(frames, titles=titles)
    moments = iter(times if times is not None else [0, *[t for e, c in zip(ELAPSED, CAPTURE) for t in (e - c, e)]])
    sleeps = []
    proxy = cls(native, storage_root=root, attempt_dir=out, document_filename='train.xlsx',
                clock=lambda: next(moments), sleep=sleeps.append)
    proxy.current_actor_step = 0
    return proxy, native, out, sleeps


def receipt():return {'profile_application_kind': 'calc', 'post_enter_windows': 1, 'actor_steps': []}


class EnterTests(unittest.TestCase):
    def test_thin_component_calls_unchanged_superclass_and_restores_both_old_bounds(self):
        self.assertIs(component.PostEnterControlProxyV19.__bases__[0], old.PostEnterControlProxyV9)
        self.assertIn('return super().press(key)', inspect.getsource(component.PostEnterControlProxyV19.press))
        self.assertEqual((old.MAX_PROBE_WALL_MS, old_audit.MAX_PROBE_WALL_MS, train.MAX_PROBE_WALL_MS), (30_000,) * 3)
        self.assertEqual(component.SAMPLE_DELAYS_MS, (0, 250, 250, 250, 250))

    def test_measured_all_five_stable_frames_reject_30_and_accept_60_in_proxy_and_auditor(self):
        frame = png('blue')
        for cls, accepted in [(old.PostEnterControlProxyV9, False), (component.PostEnterControlProxyV19, True)]:
            with TemporaryDirectory() as tmp:
                root = Path(tmp); proxy, native, out, sleeps = make_proxy(cls, root, [frame] * 5)
                if accepted:proxy.press('enter')
                else:
                    with self.assertRaisesRegex(ValueError, 'boundary changed'):proxy.press('enter')
                rows = [json.loads(s) for s in (out / 'post-enter-samples.ndjson').read_bytes().splitlines()]
                self.assertEqual([r['elapsed_since_enter_ns'] for r in rows], list(ELAPSED))
                self.assertEqual(native.actions, ['enter']); self.assertEqual(sleeps, [.25] * 4)
                with self.assertRaises(ValueError):old_audit.post_enter_samples(root, out, [{'type': 'key', 'key': 'Enter'}], receipt())
                self.assertEqual(component.post_enter_samples(root, out, [{'type': 'key', 'key': 'Enter'}], receipt()), 1)
                self.assertEqual((old.MAX_PROBE_WALL_MS, old_audit.MAX_PROBE_WALL_MS, train.MAX_PROBE_WALL_MS), (30_000,) * 3)
                rows.pop(); (out / 'post-enter-samples.ndjson').write_text(''.join(json.dumps(r) + '\n' for r in rows))
                with self.assertRaises(ValueError):component.post_enter_samples(root, out, [{'type': 'key', 'key': 'Enter'}], receipt())

    def test_window_oscillation_final_mismatch_over60_and_bad_clock_still_reject_without_next_input(self):
        a, b, c = png('red'), png('blue'), png('green')
        cases = [([a, b, a, b, b], None, None), ([a, b, c, c, c], None, None),
                 ([a, a, a, a, b], None, None), ([a] * 5, ['train.xlsx'] * 2 + ['modal'] * 3, None),
                 ([a] * 5, None, [0, 0, 60_000_000_001]), ([a] * 5, None, [0, 2, 1])]
        for frames, titles, moments in cases:
            with TemporaryDirectory() as tmp:
                proxy, native, _out, _sleep = make_proxy(component.PostEnterControlProxyV19, Path(tmp), frames, times=moments, titles=titles)
                with self.assertRaises(ValueError):proxy.press('enter')
                self.assertEqual(native.actions, ['enter']); self.assertEqual(old.MAX_PROBE_WALL_MS, 30_000)

    def test_all_five_actual_model_guests_bind_same_component_and_audit(self):
        for owner in ['shared-base', *integration.matrix.RESEARCHERS]:
            with TemporaryDirectory() as tmp:
                root = Path(tmp); out = root / 'fixture/actor'; out.mkdir(parents=True)
                native = Guest([png('blue')] * 5)
                guest = model.ModelGuest(native, root=root, out=out, filename='train.xlsx')
                self.assertIs(type(guest.proxy), component.PostEnterControlProxyV19)
                moments = iter([0, *[t for e, c in zip(ELAPSED, CAPTURE) for t in (e - c, e)]])
                guest.proxy.clock = lambda: next(moments); guest.proxy.sleep = lambda _: None; guest.proxy.current_actor_step = 0
                guest.proxy.press('enter'); self.assertEqual(native.actions, ['enter'])
                self.assertEqual(model_worker.transport_audit.post_enter_samples(root, out, [{'type': 'key', 'key': 'Enter'}], receipt()), 1)
        proposal = integration.proposal()
        self.assertEqual(proposal['post_enter_recipe'], component.RECIPE)
        self.assertEqual(proposal['post_enter_source_sha256'], digest(Path(component.__file__).read_bytes()))
        self.assertEqual((proposal['max_actor_actions'], proposal['max_actor_wall_seconds'], proposal['lease_seconds_each']), (90, 720, 1200))
        self.assertEqual(ready.MAX_WALL_MS, 60_000)

    def test_control_context_binds_proxy_and_auditor_and_restores_originals(self):
        original = (core.PostEnterControlProxyV9, old_audit.post_enter_samples, core.epoch)
        with worker.context():
            self.assertIs(core.PostEnterControlProxyV9, component.PostEnterControlProxyV19)
            self.assertIs(old_audit.post_enter_samples, component.post_enter_samples)
            self.assertIs(strict.observe, ready.observe); self.assertIs(core.epoch, epoch)
        self.assertEqual((core.PostEnterControlProxyV9, old_audit.post_enter_samples, core.epoch), original)

    def test_nested_history_counts_closed_v18_full_lease_and_excludes_only_fresh_v19(self):
        with TemporaryDirectory() as tmp:
            broad = Path(tmp); old17 = broad / 'v17'; closed18 = broad / 'v18'; own = broad / 'v19'
            intent(broad / 'past', 600); ancestor = epoch.ORIGINAL_ACCOUNTING([broad], exclude=old17)
            intent(old17); parent = epoch.ORIGINAL_ACCOUNTING([broad], exclude=closed18)
            prior = intent(closed18); manifest = epoch.ORIGINAL_MANIFEST([broad], exclude=own); intent(own)
            with epoch.parent_history(own):
                self.assertEqual(v18.ORIGINAL_ACCOUNTING([broad], exclude=closed18), parent)
                with v18.parent_history(closed18):self.assertEqual(v17.ORIGINAL_ACCOUNTING([broad], exclude=old17), ancestor)
            self.assertEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), manifest)
            self.assertEqual(epoch.ORIGINAL_ACCOUNTING([broad], exclude=own)['past_full_lease_seconds'], 3000)
            prior.write_bytes(prior.read_bytes() + b' ')
            self.assertNotEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), manifest)

    def test_real_inherited_control_writes_intent_then_hits_fake_create_once_under_v19(self):
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
            value = {'_freeze_sha256': digest(freeze.read_bytes()), 'source_sha256s': epoch.source_hashes(),
                'roster': [row], 'attempts_root': str(own), 'candidate_root': str(candidate), 'private_map': str(salt),
                'guest_public': str(guest), 'scoped_reference': str(scoped), 'ratification': str(ratification)}
            permit = root / 'permit.private.json'
            epoch.accounting._write_new(permit, {'schema': epoch.PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'],
                'source_sha256s': value['source_sha256s'], **{k: row[k] for k in ('task_id', 'package_sha256', 'split')},
                'post_enter_recipe': component.RECIPE, 'bounded_transport_recipe': epoch.parent.transport.RECIPE, 'passive_readiness_recipe': epoch.READINESS_RECIPE,
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
