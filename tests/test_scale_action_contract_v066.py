"""v0.6.6 adds only bounded GUI primitives on the same current frame."""

from __future__ import annotations

import io
import json
import unittest

from PIL import Image

from cursibench import scale_action_contract as old
from cursibench.scale_action_contract_v066 import (
    ACTION_PROFILE_VERSION, NEW_KEY_CHORDS, public_receipt, validate_action,
)


class ActionV066Tests(unittest.TestCase):
    def setUp(self):
        out = io.BytesIO()
        Image.new("RGB", (64, 48), "white").save(out, format="PNG")
        self.frame = old.make_observation(
            task_id="train.synthetic", task_binding_sha256="a" * 64,
            instruction="Use visible GUI only.", step=0,
            screenshot_bytes=out.getvalue(),
            controls=[{"ref": "row", "role": "row", "label": "Current row",
                       "visible": True, "enabled": True}],
        )

    def action(self, kind, **extra):
        return {"version": old.VERSION, "task_id": self.frame.task_id,
                "task_binding_sha256": self.frame.task_binding_sha256,
                "step": self.frame.step, "frame_id": self.frame.frame_id,
                "type": kind, "memory": "", **extra}

    def check(self, action, *, frame_id=None):
        return validate_action(action, self.frame,
                               current_frame_id=frame_id or self.frame.frame_id)

    def test_double_click_has_old_target_and_frame_checks(self):
        action = self.action("double_click", target={"ref": "row"})
        self.assertEqual(self.check(action)["type"], "double_click")
        with self.assertRaisesRegex(old.ContractError, "invalid_action"):
            old.validate_action(action, self.frame,
                                current_frame_id=self.frame.frame_id)
        with self.assertRaisesRegex(old.ContractError, "stale_frame"):
            self.check(action, frame_id="old")
        with self.assertRaisesRegex(old.ContractError, "stale_frame"):
            self.check(self.action("double_click", target={"ref": "invented"}))
        with self.assertRaisesRegex(old.ContractError, "invalid_action"):
            self.check(self.action("double_click", target={"x": 64, "y": 1}))
        with self.assertRaisesRegex(old.ContractError, "expired_frame"):
            validate_action(action, self.frame,
                            current_frame_id=self.frame.frame_id,
                            now=self.frame.expires_at + 1)

    def test_explicit_new_key_chords_and_no_arbitrary_shortcuts(self):
        self.assertEqual(NEW_KEY_CHORDS,
                         {"Control+F", "Control+H", "Control+End", "Shift+End"})
        for chord in NEW_KEY_CHORDS:
            with self.subTest(chord=chord):
                self.assertEqual(self.check(self.action("key", key=chord))["key"], chord)
        for chord in ("Control+P", "Control+T", "Alt+F4", "Control+F;sh"):
            with self.subTest(chord=chord):
                with self.assertRaisesRegex(old.ContractError, "invalid_action"):
                    self.check(self.action("key", key=chord))

    def test_focused_insert_is_targetless_but_fill_is_not(self):
        focused = self.action("type", text="hello", mode="insert")
        self.assertNotIn("target", self.check(focused))
        with self.assertRaisesRegex(old.ContractError, "invalid_action"):
            old.validate_action(focused, self.frame,
                                current_frame_id=self.frame.frame_id)
        for payload in (self.action("type", text="hello", mode="fill"),
                        self.action("type", text="", mode="insert"),
                        self.action("type", text="x" * 8193, mode="insert"),
                        self.action("shell", command="ls")):
            with self.assertRaises(old.ContractError):
                self.check(payload)

    def test_duplicate_json_and_public_receipt_remain_safe(self):
        action = self.action("double_click", target={"x": 5, "y": 7})
        duplicate = json.dumps(action)[:-1] + ',"type":"shell"}'
        with self.assertRaisesRegex(old.ContractError, "invalid_action_json"):
            self.check(duplicate)
        receipt = public_receipt(self.frame, action=action)
        self.assertEqual(receipt["action_profile"], ACTION_PROFILE_VERSION)
        self.assertEqual(receipt["action_type"], "double_click")
        self.assertNotIn(self.frame.instruction, json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
