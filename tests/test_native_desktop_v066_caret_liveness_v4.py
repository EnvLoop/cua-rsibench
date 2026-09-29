"""Offline safety checks for the prospective two-observation Desktop guard."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import qwen_v066_adapter_v4 as adapter


def _png(*, x: int | None = None, height: int = 18,
         material: bool = False) -> bytes:
    image = Image.new("RGB", (1280, 800), "white")
    if x is not None:
        for y in range(495, 495 + height):
            image.putpixel((x, y), (0, 0, 0))
    if material:
        for x0 in range(600, 610):
            for y in range(500, 510):
                image.putpixel((x0, y), (0, 0, 0))
    raw = io.BytesIO()
    image.save(raw, format="PNG")
    return raw.getvalue()


class Sandbox:
    def __init__(self, frames: list[bytes]):
        self.frames = list(frames)
        self.last_screenshot = b""
        self.calls = []

    def screenshot(self) -> bytes:
        if self.frames:
            self.last_screenshot = self.frames.pop(0)
        return self.last_screenshot

    def left_click(self, x: int, y: int) -> None:
        self.calls.append((x, y))


class LivenessTests(unittest.TestCase):
    action = '{"type":"click","target":{"x":400,"y":300}}'

    def observe(self, sandbox: Sandbox):
        return adapter.observe(
            sandbox, task_id="train.synthetic",
            task_binding_sha256="a" * 64,
            instruction="Edit the visible document.", step=0, max_actions=90)

    @patch.object(adapter.v3.time, "sleep")
    def test_repeated_two_state_blink_accepts_only_after_second_observation(
            self, sleep):
        plain, caret = _png(), _png(x=502)
        sandbox = Sandbox([plain] + [caret] * 6 + [plain, caret])
        first = self.observe(sandbox)
        with self.assertRaises(adapter.PhysicalFrameDrift):
            adapter.parse_current_action(self.action, first, sandbox)
        self.assertEqual(sleep.call_count, 5)
        second = self.observe(sandbox)
        result = adapter.parse_current_action(self.action, second, sandbox)
        self.assertEqual(result["type"], "click")
        self.assertEqual(sandbox.last_screenshot, caret)
        self.assertEqual(sandbox.calls, [])

    @patch.object(adapter.v3.time, "sleep")
    def test_persistent_one_pixel_edit_cannot_prove_return(self, _sleep):
        plain, edited = _png(), _png(x=502)
        sandbox = Sandbox([plain] + [edited] * 8)
        with self.assertRaises(adapter.PhysicalFrameDrift):
            adapter.parse_current_action(self.action, self.observe(sandbox), sandbox)
        with self.assertRaises(adapter.PhysicalFrameDrift):
            adapter.parse_current_action(self.action, self.observe(sandbox), sandbox)
        self.assertEqual(sandbox.calls, [])

    @patch.object(adapter.v3.time, "sleep")
    def test_third_state_and_action_change_fail_closed(self, _sleep):
        plain, caret, other = _png(), _png(x=502), _png(x=503)
        for tail, action in ((other, self.action),
                             (caret, '{"type":"click","target":{"x":401,"y":300}}')):
            sandbox = Sandbox([plain] + [caret] * 6 + [plain, tail])
            with self.assertRaises(adapter.PhysicalFrameDrift):
                adapter.parse_current_action(
                    self.action, self.observe(sandbox), sandbox)
            with self.assertRaises(adapter.PhysicalFrameDrift):
                adapter.parse_current_action(action, self.observe(sandbox), sandbox)
            self.assertEqual(sandbox.calls, [])

    @patch.object(adapter.v3.time, "sleep")
    def test_material_change_never_enters_blink_state(self, sleep):
        plain, changed = _png(), _png(material=True)
        sandbox = Sandbox([plain, changed])
        with self.assertRaises(adapter.PhysicalFrameDrift):
            adapter.parse_current_action(
                self.action, self.observe(sandbox), sandbox)
        sleep.assert_not_called()
        self.assertEqual(sandbox.calls, [])


if __name__ == "__main__":
    unittest.main()
