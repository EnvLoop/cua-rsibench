"""Fail-closed native Desktop binding to the shared v0.6.4 action boundary."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_output_v065 import normalize_model_action as normalize_v065
from native_desktop_factory.qwen_v064_adapter import (
    PhysicalFrameDrift, application_frame_digest, dispatch, observe,
    parse_current_action, render_for_model,
)
from native_desktop_factory.qwen_v064_train_smoke import preflight


def png(color="white"):
    output = io.BytesIO()
    Image.new("RGB", (1280, 800), color).save(output, format="PNG")
    return output.getvalue()


class FakeSandbox:
    def __init__(self):
        self.image = png()
        self.calls = []

    def screenshot(self):
        return self.image

    def left_click(self, x, y):
        self.calls.append(("click", x, y))

    def press(self, keys):
        self.calls.append(("press", keys))

    def write(self, text):
        self.calls.append(("write", text))

    def scroll(self, *, direction, amount):
        self.calls.append(("scroll", direction, amount))


class DesktopV064AdapterTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = FakeSandbox()
        self.frame = observe(self.sandbox, task_id="train-calc", task_binding_sha256="a"*64,
                             instruction="Edit the visible workbook", step=0, max_actions=3)

    def test_screenshot_only_v064_fence_and_gui_click(self):
        rendered = render_for_model(self.frame)
        self.assertEqual(rendered["image_bytes"], self.sandbox.image)
        self.assertEqual(json.loads(rendered["instruction"])["output_version"],
                         "scale-action-output-v0.6.4")
        action = parse_current_action('```\n{"type":"click","target":{"x":91,"y":242}}\n```',
                                      self.frame, self.sandbox)
        self.assertEqual(dispatch(self.sandbox, action), "click")
        self.assertEqual(self.sandbox.calls, [("click", 91, 242)])

    def test_drift_and_nongui_outputs_do_not_dispatch(self):
        self.sandbox.image = png("black")
        stale_frames = []
        with self.assertRaises(PhysicalFrameDrift):
            parse_current_action('{"type":"click","target":{"x":91,"y":242}}',
                                 self.frame, self.sandbox,
                                 on_stale_frame=stale_frames.append)
        self.assertEqual(stale_frames, [self.sandbox.image])
        self.assertEqual(self.sandbox.calls, [])
        self.sandbox.image = png()
        with self.assertRaisesRegex(ContractError, "stale_frame") as error:
            parse_current_action('{"type":"click","target":{"ref":"visible-ref"}}',
                                 self.frame, self.sandbox)
        self.assertNotIsInstance(error.exception, PhysicalFrameDrift)
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            parse_current_action('{"type":"shell","command":"ls"}',
                                 self.frame, self.sandbox)
        self.assertEqual(self.sandbox.calls, [])

    def test_clock_and_status_only_do_not_spend_a_stale_resample(self):
        changed = Image.open(io.BytesIO(self.sandbox.image)).convert("RGB")
        for y in range(27):
            changed.putpixel((60, y), (0, 0, 0))
        for y in range(780, 800):
            changed.putpixel((60, y), (0, 0, 0))
        output = io.BytesIO()
        changed.save(output, format="PNG")
        self.sandbox.image = output.getvalue()
        self.assertEqual(application_frame_digest(self.sandbox.image),
                         application_frame_digest(self.frame.screenshot_bytes))
        action = parse_current_action('{"type":"click","target":{"x":91,"y":242}}',
                                      self.frame, self.sandbox)
        self.assertEqual(action["type"], "click")

    def test_horizontal_scroll_fails_closed(self):
        action = parse_current_action('{"type":"scroll","dx":120,"dy":0}',
                                      self.frame, self.sandbox)
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            dispatch(self.sandbox, action)
        self.assertEqual(self.sandbox.calls, [])

    def test_pixel_fill_cannot_select_whole_document(self):
        action = parse_current_action(
            '{"type":"type","target":{"x":91,"y":242},"text":"replacement","mode":"fill"}',
            self.frame, self.sandbox)
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            dispatch(self.sandbox, action)
        self.assertEqual(self.sandbox.calls, [])

    def test_cell_neutral_v065_normalizer_still_uses_current_desktop_frame(self):
        action = parse_current_action(
            '{"action":"click","target":{"x":91,"y":242}}',
            self.frame, self.sandbox, normalizer=normalize_v065)
        self.assertEqual(action["type"], "click")
        self.assertEqual(action["target"], {"x": 91, "y": 242})

    def test_final_candidate_rejected_before_inventory_or_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_dir = root / "final_candidate" / "withheld"
            package_dir.mkdir(parents=True)
            (package_dir / "package.json").write_text('{"split":"final_candidate"}')
            with self.assertRaisesRegex(ValueError, "Only train/selection"):
                preflight(package_dir, root)


if __name__ == "__main__":
    unittest.main()
