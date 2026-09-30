import io
import json
from pathlib import Path

from PIL import Image, ImageDraw
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from native_desktop_factory import pre_observation_readiness_v12 as ready
from native_desktop_factory import qwen_v066_adapter_v4_strict as strict
from native_desktop_factory import selection_control_readiness_worker_v12 as worker


def png(*, tooltip=False, caret=False, material=False):
    image = Image.new('RGB', (1280, 800), 'white')
    draw = ImageDraw.Draw(image)
    if tooltip:
        draw.rectangle((14, 183, 97, 214), fill='gray')
    if caret:
        draw.line((52, 162, 52, 177), fill='black')
    if material:
        draw.point((900, 400), fill='red')
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


class Clock:
    def __init__(self):
        self.now = 0
        self.delays = []

    def clock(self):
        return self.now

    def sleep(self, delay):
        self.delays.append(delay)
        self.now += int(delay * 1_000_000_000)


class Native:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.inputs = []
        self.ids = None

    def get_current_window_id(self):
        return next(self.ids) if self.ids is not None else 'native-window'

    def get_window_title(self, _id):
        return 'Visible native document'

    def screenshot(self):
        return next(self.frames)

    def left_click(self, x, y):
        self.inputs.append(('click', x, y))

    def press(self, key):
        self.inputs.append(('key', key))


def samples(frames):
    native = Native(frames)
    clock = Clock()
    raw, rows = ready.passive_samples(native, clock=clock.clock, sleep=clock.sleep)
    return native, clock, raw, rows



class Wrapper:
    def __init__(self, native):
        self.sandbox = native

    def __getattr__(self, name):
        return getattr(self.sandbox, name)


class ReadinessTests(unittest.TestCase):
    def test_hover_transition_then_stable_full_tooltip_is_returned(self):
        a, b = png(), png(tooltip=True)
        native, clock, raw, rows = samples([a, a, b, b, b, b, b])
        assert raw == b
        assert len(rows) == 7 and native.inputs == []
        assert clock.delays == [.25, .25, .5, .5, .5, .5]
        assert rows[-1]['elapsed_ns'] == 2_500_000_000


    def test_native_caret_pair_is_classified_without_pixel_changes(self):
        a, b = png(tooltip=True), png(tooltip=True, caret=True)
        _native, _clock, raw, _rows = samples([a, a, a, a, b, a, b])
        assert raw == b


    def test_continued_material_drift_or_third_state_is_refused(self):
        for states in [[png(), png(material=True), png(), png()],
                       [png(), png(tooltip=True), png(), png(tooltip=True)],
                       [png(), png(caret=True), png(material=True), png()]]:
            with self.assertRaisesRegex(ValueError, 'did not settle'):
                samples([png()] * 3 + states)


    def test_mid_sample_native_window_change_is_refused_and_retained(self):
        native = Native([png()] * 7)
        native.ids = iter(['first', 'first', 'other'])
        clock = Clock()
        retained = []
        with self.assertRaisesRegex(ValueError, 'window or time'):
            ready.passive_samples(native, clock=clock.clock, sleep=clock.sleep,
                                  persist=lambda row, raw: retained.append((row, raw)))
        assert len(retained) == 1 and retained[0][0]['native_window_unchanged'] is False
        assert native.inputs == []


    def test_wall_bound_refuses_slow_native_capture(self):
        native = Native([png()] * 7)
        times = iter([0, 0, 31_000_000_000])
        with self.assertRaisesRegex(ValueError, 'window or time'):
            ready.passive_samples(native, clock=lambda: next(times), sleep=lambda _: None)


    def test_dispatch_inputs_are_unchanged_and_wrapper_owner_is_shared(self):
        native = Native([])
        actor = Wrapper(native)
        recorder = Wrapper(actor)
        assert ready.dispatch(actor, {'type': 'click', 'target': {'x': 52, 'y': 170}}) == 'click'
        assert ready.dispatch(actor, {'type': 'key', 'key': 'Control+A'}) == 'key'
        assert native.inputs == [('click', 52, 170), ('key', ['ctrl', 'a'])]
        assert ready._owner(recorder) is ready._owner(actor) is native
        assert native._v12_focus_pending is True


    def test_observation_preserves_final_full_frame_and_strict_guard(self):
        with TemporaryDirectory() as tmp:
            self._observation_test(Path(tmp))

    def _observation_test(self, tmp_path):
        a, b, changed = png(), png(tooltip=True), png(tooltip=True, material=True)
        native = Native([a, a, b, b, b, b, b, b, changed])
        native._v12_focus_pending = True
        root = tmp_path / 'root'
        out = root / 'case' / 'positive'
        out.mkdir(parents=True)
        import os
        env_patch = patch.dict(os.environ, {'ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT': str(root), 'ENVLOOP_DESKTOP_V4_ATTEMPT_DIR': str(out)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        clock = Clock()
        original = ready.passive_samples
        function_patch = patch.object(ready, 'passive_samples', lambda sb, **kwargs:
                                      original(sb, clock=clock.clock, sleep=clock.sleep, **kwargs))
        function_patch.start()
        self.addCleanup(function_patch.stop)
        observation = ready.observe(native, task_id='train.synthetic', task_binding_sha256='a' * 64,
                                    instruction='Synthetic readiness control.', step=1,
                                    previous_action_result={'status': 'applied', 'code': 'ok'})
        assert observation.screenshot_bytes == b and native._v12_focus_pending is False
        action = strict.parse_current_action('{"type":"type","text":"test","mode":"insert"}', observation, native)
        assert action['type'] == 'type'
        with self.assertRaises(strict.MaterialFrameDrift):
            strict.parse_current_action('{"type":"type","text":"test","mode":"insert"}', observation, native)
        assert native.inputs == []
        assert len(list(out.glob('readiness-*.png'))) == 7
        (out / 'frame-01-0.png').write_bytes(b)
        actions = [{'type': 'click', 'target': {'x': 52, 'y': 170}},
                   {'type': 'type', 'text': 'input', 'mode': 'insert'}]
        assert ready.audit_samples(root, out, actions, {}) == 1
        journal = out / 'pre-observation-readiness-v12.ndjson'
        original_log = journal.read_bytes()
        rows = [json.loads(line) for line in original_log.splitlines()]
        rows[-1]['elapsed_ns'] -= 1
        journal.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'stable fresh observation'):
            ready.audit_samples(root, out, actions, {})
        journal.write_bytes(original_log)
        (out / 'readiness-01-06.png').write_bytes(changed)
        with self.assertRaises(ValueError):
            ready.audit_samples(root, out, actions, {})


    def test_context_restores_all_frozen_function_references(self):
        old = (strict.observe, strict.dispatch, worker.audit.audit_attempt, worker.worker.epoch)
        with worker.context():
            assert strict.observe is ready.observe and strict.dispatch is ready.dispatch
            assert worker.audit.audit_attempt is worker.audit_attempt
        assert (strict.observe, strict.dispatch, worker.audit.audit_attempt, worker.worker.epoch) == old


    def test_paid_entry_refuses_without_explicit_flag(self):
        with self.assertRaisesRegex(ValueError, 'remains closed'):
            worker.run_trio(freeze_path=Path('absent'), permit_path=Path('absent'))

if __name__ == '__main__':
    unittest.main()
