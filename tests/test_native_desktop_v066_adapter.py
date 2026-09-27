"""Native Desktop proposed v0.6.6 acts only through bounded GUI methods."""

from __future__ import annotations

import io
import unittest

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


if __name__ == "__main__":
    unittest.main()
