"""v0.6.6 minimal output remains one bounded current-frame GUI action."""

from __future__ import annotations

import io
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from cursibench.scale_action_output_v065 import normalize_model_action as old_normalize
from cursibench.scale_action_output_v066 import (
    OUTPUT_VERSION, normalize_model_action, render_for_model,
)


def observation():
    image = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(image, format="PNG")
    return make_observation(task_id="train.synthetic", task_binding_sha256="a" * 64,
                            instruction="Use current GUI only.", step=0,
                            screenshot_bytes=image.getvalue(), controls=[])


class OutputV066Tests(unittest.TestCase):
    def setUp(self):
        self.frame = observation()

    def parse(self, raw: str, *, frame_id: str | None = None):
        return normalize_model_action(raw, self.frame,
                                      current_frame_id=frame_id or self.frame.frame_id)

    def test_double_click_and_alias_keep_current_frame_target(self):
        text = '{"action":"double_click","target":{"x":10,"y":20}}'
        for raw in (text, f'```json\n{text}\n```', f'```\n{text}\n```'):
            self.assertEqual(self.parse(raw)["type"], "double_click")
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            old_normalize(text, self.frame,
                          current_frame_id=self.frame.frame_id)
        with self.assertRaisesRegex(ContractError, "stale_frame"):
            self.parse(text, frame_id="obsolete")
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            self.parse('{"type":"double_click","target":{"x":80,"y":20}}')

    def test_new_chords_and_focused_insert_are_bounded(self):
        for chord in ("Control+F", "Control+H", "Control+End", "Shift+End"):
            self.assertEqual(self.parse(json.dumps({"type": "key", "key": chord}))["key"], chord)
        self.assertNotIn("target", self.parse('{"type":"type","text":"value","mode":"insert"}'))
        for raw in ('{"type":"key","key":"Control+P"}',
                    '{"type":"type","text":"value","mode":"fill"}',
                    '{"type":"type","text":"x","mode":"insert","url":"https://x"}',
                    '{"type":"double_click","target":{"ref":"invented"}}'):
            with self.assertRaises(ContractError):
                self.parse(raw)

    def test_extra_metadata_and_malformed_json_still_fail(self):
        for raw in ('{"type":"double_click","target":{"x":5,"y":5},"task_id":"forged"}',
                    '{"type":"double_click","type":"shell","target":{"x":5,"y":5}}',
                    'Do this: {"type":"double_click","target":{"x":5,"y":5}}',
                    '```json\n{"type":"double_click","target":{"x":5,"y":5}}\n```\nDone'):
            with self.assertRaises(ContractError):
                self.parse(raw)

    def test_prompt_does_not_expose_trusted_identity(self):
        rendered = json.loads(render_for_model(self.frame)["instruction"])
        self.assertEqual(rendered["output_version"], OUTPUT_VERSION)
        self.assertIn("double_click", rendered["contract"])
        self.assertIn("currently focused GUI control", rendered["contract"])
        for hidden in (self.frame.task_id, self.frame.task_binding_sha256,
                       self.frame.frame_id):
            self.assertNotIn(hidden, json.dumps(rendered))

    def test_unchanged_gui_actions_match_v065_in_non_desktop_cells(self):
        actions = (
            {"type": "click", "target": {"x": 10, "y": 20}},
            {"type": "type", "target": {"x": 10, "y": 20},
             "text": "text", "mode": "insert"},
            {"type": "key", "key": "Tab"},
            {"type": "scroll", "dx": 0, "dy": 240},
            {"type": "drag", "from": {"x": 5, "y": 5},
             "to": {"x": 10, "y": 10}},
            {"type": "wait", "duration_ms": 1000},
            {"type": "finish"},
        )
        for action in actions:
            raw = json.dumps(action)
            with self.subTest(action=action["type"]):
                self.assertEqual(self.parse(raw), old_normalize(
                    raw, self.frame, current_frame_id=self.frame.frame_id))


if __name__ == "__main__":
    unittest.main()
