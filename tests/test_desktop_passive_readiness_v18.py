"""Measured six-shot latency replay; no provider, model or native calls."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import pre_observation_readiness_v12 as old
from native_desktop_factory import pre_observation_readiness_v18 as ready
from native_desktop_factory import save_readiness_v20 as adopted
from native_desktop_factory import selection_control_readiness_epoch_v18 as epoch
from native_desktop_factory import selection_control_readiness_worker_v18 as worker
from native_desktop_factory import selection_control_bounded_epoch_v17 as v17
from native_desktop_factory import selection_control_structural_epoch_v16 as v16
from native_desktop_factory import selection_control_accounting_epoch_v13 as history
from native_desktop_factory import qwen_v066_adapter_v4_strict as strict
from native_desktop_factory import v066_post_enter_control_attempt_v9 as core
from native_desktop_factory import model_transport_integration_v11 as integration
from native_desktop_factory import uniform_model_transport_v11 as model
from native_desktop_factory.factory import digest
from tests.test_desktop_focus_readiness_v12 import Native, Wrapper, png
from tests.test_desktop_ancestor_accounting_v13 import intent
from tests.test_native_desktop_selection_worker_v066 import source_case

# Exact retained v17 elapsed/capture durations; synthetic seventh is explicit.
ELAPSED = (4635729916, 9663876166, 15917170458, 22058600625, 26892426833, 31169201125)
CAPTURE = (3942242958, 4758546083, 5981309083, 5628351542, 4314772542, 3758849834)


def timeline(*, seventh_elapsed=35_669_201_125):
    return [0, *[time for elapsed, capture in zip(ELAPSED, CAPTURE) for time in (elapsed - capture, elapsed)],
            ELAPSED[-1] + 500_000_000, seventh_elapsed]


def replay(module, frames, *, times=None, native=None, retained=None):
    native = native or Native(frames); moments = iter(timeline() if times is None else times)
    return module.passive_samples(native, clock=lambda: next(moments), sleep=lambda _seconds: None,
        persist=(lambda row, raw: retained.append((row, raw))) if retained is not None else None)


class ReadinessTests(unittest.TestCase):
    def test_v18_is_exact_v12_copy_except_component_wall_bound(self):
        self.assertEqual(Path(ready.__file__).read_bytes(),
                         Path(old.__file__).read_bytes().replace(b'MAX_WALL_MS = 30_000', b'MAX_WALL_MS = 60_000'))
        self.assertEqual(ready.SAMPLE_DELAYS_MS, (0, 250, 250, 500, 500, 500, 500))

    def test_measured_six_sample_latency_rejects_30_and_accepts_60_only_after_full_seven(self):
        frame = png(tooltip=True); retained = []
        with self.assertRaisesRegex(ValueError, 'window or time'):
            replay(old, [frame] * 7, retained=retained)
        self.assertEqual([r['elapsed_ns'] for r, _raw in retained], list(ELAPSED))
        self.assertEqual(len(retained), 6)
        raw, rows = replay(ready, [frame] * 7)
        self.assertEqual(raw, frame); self.assertEqual(len(rows), 7)
        self.assertEqual(rows[-1]['elapsed_ns'], 35_669_201_125)
        with self.assertRaises(StopIteration):replay(ready, [frame] * 6)

    def test_60_bound_does_not_admit_material_drift_identity_change_bad_clock_or_overrun(self):
        frame = png(tooltip=True)
        with self.assertRaisesRegex(ValueError, 'did not settle'):
            replay(ready, [frame] * 6 + [png(tooltip=True, material=True)])
        native = Native([frame] * 7); native.ids = iter(['first', 'first', 'changed'])
        with self.assertRaisesRegex(ValueError, 'window or time'):replay(ready, [], native=native)
        for moments in ([0, -1, 10], [0, 2, 1], timeline(seventh_elapsed=60_000_000_001)):
            with self.assertRaisesRegex(ValueError, 'window or time'):replay(ready, [frame] * 7, times=moments)
        raw, _rows = replay(ready, [frame] * 5 + [png(tooltip=True, caret=True), frame])
        self.assertEqual(raw, frame)

    def test_all_five_actual_model_observations_use_same_full_seven_readiness_and_actor_bound(self):
        frame = png(tooltip=True)
        for owner in ['shared-base', *integration.matrix.RESEARCHERS]:
            with TemporaryDirectory() as tmp:
                root = Path(tmp); out = root / 'fixture/actor'; out.mkdir(parents=True)
                native = Native([frame] * 8); guest = model.ModelGuest(native, root=root, out=out, filename='fixture.xlsx')
                self.assertEqual(ready.dispatch(guest.proxy, {'type': 'click', 'target': {'x': 52, 'y': 170}}), 'click')
                self.assertIs(ready._owner(guest.recorder), ready._owner(guest.proxy))
                original = ready.passive_samples; moments = iter(timeline())
                with patch.object(adopted, 'passive_samples', lambda sb, **kwargs: original(sb,
                          clock=lambda: next(moments), sleep=lambda _: None, **kwargs)):
                    observation = guest.observe(identity={'task_id': 'fixture', 'package_sha256': 'a' * 64},
                        instruction='Public synthetic readiness test.', step=1, previous={'status': 'applied', 'code': 'ok'})
                self.assertEqual(observation.screenshot_bytes, frame)
                self.assertEqual(native.inputs, [('click', 52, 170)])
                self.assertEqual(len((out / 'pre-observation-readiness-v12.ndjson').read_bytes().splitlines()), 7)
                # Existing physical-frame parser receives the raw full PNG.
                action = strict.parse_current_action('{"type":"key","key":"Escape"}', observation, native)
                self.assertEqual(action['type'], 'key')
        proposal = integration.proposal()
        self.assertIs(model.readiness, adopted)
        self.assertEqual(proposal['passive_readiness_recipe'], adopted.RECIPE)
        self.assertEqual(proposal['passive_readiness_source_sha256'], digest(Path(adopted.__file__).read_bytes()))
        self.assertEqual((proposal['max_actor_actions'], proposal['max_actor_wall_seconds'], proposal['lease_seconds_each']), (90, 720, 1200))

    def test_v18_context_binds_inherited_control_functions_and_restores_v12(self):
        before = (strict.observe, strict.dispatch, core.epoch)
        with worker.context():
            self.assertIs(strict.observe, ready.observe); self.assertIs(strict.dispatch, ready.dispatch)
            self.assertIs(core.epoch, epoch)
        self.assertEqual((strict.observe, strict.dispatch, core.epoch), before)
        with patch.object(epoch, 'validate', side_effect=AssertionError('Private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                worker.run_trio(freeze_path=Path('/absent'), permit_path=Path('/absent'))

    def test_nested_history_excludes_only_fresh_v18_and_counts_closed_v17_full_lease(self):
        with TemporaryDirectory() as tmp:
            broad = Path(tmp); past = broad / 'past'; closed16 = broad / 'v16'; closed17 = broad / 'v17'; own = broad / 'v18'
            intent(past, 600); old16 = history.ORIGINAL_ACCOUNTING([broad], exclude=closed16)
            intent(closed16); old17 = history.ORIGINAL_ACCOUNTING([broad], exclude=closed17)
            prior = intent(closed17); frozen_manifest = epoch.ORIGINAL_MANIFEST([broad], exclude=own); intent(own)
            with epoch.parent_history(own):
                self.assertEqual(v17.ORIGINAL_ACCOUNTING([broad], exclude=closed17), old17)
                with v17.parent_history(closed17), v16.parent_history(closed16):
                    self.assertEqual(history.ORIGINAL_ACCOUNTING([broad], exclude=closed16), old16)
            self.assertEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), frozen_manifest)
            self.assertEqual(epoch.ORIGINAL_ACCOUNTING([broad], exclude=own)['past_full_lease_seconds'], 3000)
            prior.write_bytes(prior.read_bytes() + b' ')
            self.assertNotEqual(epoch.ORIGINAL_MANIFEST([broad], exclude=own), frozen_manifest)

    def test_real_inherited_control_writes_intent_then_hits_fake_create_once_under_v18(self):
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
                'bounded_transport_recipe': epoch.transport.RECIPE, 'passive_readiness_recipe': epoch.READINESS_RECIPE,
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
