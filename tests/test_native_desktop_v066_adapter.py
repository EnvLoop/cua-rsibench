"""Native Desktop proposed v0.6.6 acts only through bounded GUI methods."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench.scale_action_contract import ContractError
from native_desktop_factory import qwen_v066_adapter as desktop


class FakeSandbox:
    def __init__(self):
        output = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(output, format="PNG")
        self.frame = output.getvalue()
        self.calls = []

    def screenshot(self): return self.frame
    def double_click(self, x, y): self.calls.append(("double_click", x, y))
    def left_click(self, x, y): self.calls.append(("click", x, y))
    def write(self, value): self.calls.append(("write", value))
    def press(self, keys): self.calls.append(("press", keys))


class NativeV066Tests(unittest.TestCase):
    def setUp(self):
        self.sandbox = FakeSandbox()
        self.frame = desktop.observe(self.sandbox, task_id="train.synthetic",
                                     task_binding_sha256="a" * 64,
                                     instruction="Edit the visible document.",
                                     step=0, max_actions=90)

    def run_action(self, raw):
        return desktop.dispatch(self.sandbox,
            desktop.parse_current_action(raw, self.frame, self.sandbox))

    def test_double_click_focused_insert_and_explicit_key(self):
        self.assertEqual(self.run_action('{"type":"double_click","target":{"x":400,"y":300}}'),
                         "double_click")
        self.assertEqual(self.run_action('{"type":"type","text":"replacement","mode":"insert"}'),
                         "type")
        self.assertEqual(self.run_action('{"type":"key","key":"Control+H"}'), "key")
        self.assertEqual(self.sandbox.calls, [
            ("double_click", 400, 300), ("write", "replacement"),
            ("press", ["ctrl", "h"]),
        ])

    def test_invalid_ref_and_targetless_fill_never_touch_gui(self):
        for raw in ('{"type":"double_click","target":{"ref":"invented"}}',
                    '{"type":"type","text":"unsafe","mode":"fill"}',
                    '{"type":"key","key":"Control+P"}'):
            with self.assertRaises(ContractError):
                self.run_action(raw)
        self.assertEqual(self.sandbox.calls, [])


def image_with_column(*, left=400, top=300, height=21, color=(0, 0, 0)):
    image = Image.new("RGB", (1280, 800), "white")
    for y in range(top, top + height):
        image.putpixel((left, y), color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class SequenceSandbox(FakeSandbox):
    def __init__(self, frames):
        super().__init__()
        self.frames = list(frames)
        self.last_screenshot = b""

    def screenshot(self):
        if self.frames:
            self.last_screenshot = self.frames.pop(0)
        return self.last_screenshot


class CaretAmendmentTests(unittest.TestCase):
    def setUp(self):
        self.plain = image_with_column(height=0)
        self.caret = image_with_column(height=21)
        self.raw_action = '{"type":"click","target":{"x":400,"y":300}}'

    def observation(self, sandbox):
        return desktop.observe(sandbox, task_id="train.synthetic",
                               task_binding_sha256="a" * 64,
                               instruction="Edit the visible document.",
                               step=0, max_actions=90)

    @patch.object(desktop.time, "sleep")
    def test_two_state_caret_return_accepts_current_frame(self, sleep):
        sandbox = SequenceSandbox([self.plain, self.caret, self.caret,
                                   self.plain])
        frame = self.observation(sandbox)
        action = desktop.parse_current_action(
            self.raw_action, frame, sandbox)
        self.assertEqual(action["type"], "click")
        self.assertEqual(sandbox.last_screenshot, self.plain)
        self.assertEqual(sleep.call_count, 2)

    @patch.object(desktop.time, "sleep")
    def test_persistent_one_pixel_edit_fails_closed(self, sleep):
        sandbox = SequenceSandbox([self.plain] + [self.caret] * 7)
        frame = self.observation(sandbox)
        stale = []
        with self.assertRaises(desktop.PhysicalFrameDrift):
            desktop.parse_current_action(
                self.raw_action, frame, sandbox,
                on_stale_frame=stale.append)
        self.assertEqual(stale, [self.caret])
        self.assertEqual(sleep.call_count, 5)
        self.assertEqual(sandbox.calls, [])

    @patch.object(desktop.time, "sleep")
    def test_third_application_state_fails_closed(self, sleep):
        third = image_with_column(left=401)
        sandbox = SequenceSandbox([self.plain, self.caret, third])
        frame = self.observation(sandbox)
        with self.assertRaises(desktop.PhysicalFrameDrift):
            desktop.parse_current_action(self.raw_action, frame, sandbox)
        self.assertEqual(sleep.call_count, 1)

    @patch.object(desktop.time, "sleep")
    def test_meaningful_content_change_is_never_tolerated(self, sleep):
        altered = Image.open(io.BytesIO(self.plain)).convert("RGB")
        for x in range(400, 410):
            for y in range(300, 310):
                altered.putpixel((x, y), (0, 0, 0))
        output = io.BytesIO()
        altered.save(output, format="PNG")
        sandbox = SequenceSandbox([self.plain, output.getvalue()])
        frame = self.observation(sandbox)
        with self.assertRaises(desktop.PhysicalFrameDrift):
            desktop.parse_current_action(self.raw_action, frame, sandbox)
        sleep.assert_not_called()

    def test_shape_limit_rejects_short_wide_and_multiple_blinks(self):
        long_caret = Image.open(io.BytesIO(
            image_with_column(height=42))).convert("RGB")
        long_caret.putpixel((400, 300), (17, 17, 17))
        output = io.BytesIO()
        long_caret.save(output, format="PNG")
        self.assertTrue(desktop._single_caret_column(
            self.plain, output.getvalue()))
        self.assertFalse(desktop._single_caret_column(
            self.plain, image_with_column(height=9)))
        self.assertFalse(desktop._single_caret_column(
            self.plain, image_with_column(height=46)))
        wide = Image.open(io.BytesIO(self.caret)).convert("RGB")
        for y in range(300, 321):
            wide.putpixel((401, y), (0, 0, 0))
        output = io.BytesIO()
        wide.save(output, format="PNG")
        self.assertFalse(desktop._single_caret_column(
            self.plain, output.getvalue()))


if __name__ == "__main__":
    unittest.main()
