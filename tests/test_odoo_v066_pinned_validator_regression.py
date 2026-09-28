"""Source-only replay of frozen selection action types at adapter boundary."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from cursibench.scale_action_contract import make_observation
from cursibench.scale_action_contract_v066 import validate_action as v066_validate
from enterprise_fallback.odoo18.odoo_v066_scale_exact_return_adapter import (
    OdooV066ScaleExactReturnAdapter)
from enterprise_fallback.odoo18.odoo_v066_scale_pinned_border_adapter import (
    OdooV066ScalePinnedBorderAdapter, validate_action as pinned_validate)
from tests.test_odoo_v066_pinned_border_adapter import png


ACTION_TYPES = ["type", "key", "click", "click", "click", "wait",
                "click", "click", "double_click"]


def through_adapter(action: dict, observation):
    actor = object.__new__(OdooV066ScalePinnedBorderAdapter)
    actor.latest = observation
    actor._pending_dispatch_action = None
    actor._physical_guard_receipt = None

    def fake_parent(self, checked):
        self._physical_guard_receipt = {
            "profile": "fake-exact-frame", "classification": "exact_physical_frame"}
        return {"action": checked, "public_contract_receipt": {
            "screenshot": {"sha256": observation.screenshot["sha256"]}}}

    with patch.object(OdooV066ScaleExactReturnAdapter, "dispatch",
                      autospec=True, side_effect=fake_parent):
        return actor.dispatch(action)


class ValidatorBoundaryTests(unittest.TestCase):
    def test_exact_extended_validator_identity_and_finish(self):
        self.assertIs(pinned_validate, v066_validate)
        frame = png()
        observation = make_observation(
            task_id="OFFLINE-TEST-1", task_binding_sha256="b" * 64,
            instruction="offline adapter validation", step=0,
            screenshot_bytes=frame, controls=[], memory="")
        action = {
            "version": "scale-computer-use-v0.6",
            "task_id": observation.task_id,
            "task_binding_sha256": observation.task_binding_sha256,
            "step": 0, "frame_id": observation.frame_id,
            "type": "finish", "memory": "",
        }
        self.assertEqual(through_adapter(action, observation)["action"]["type"],
                         "finish")

    def test_all_frozen_selection_action_types_validate_without_gui(self):
        external = os.environ.get("ODOO_PINNED_VALIDATOR_EVIDENCE_ROOT")
        if not external:
            self.skipTest("private frozen selection attempt not supplied")
        attempt = (Path(external) /
                   "enterprise_fallback/odoo18/partition_workers/selection/private"
                   "/v066_scale_controls/controls-20260929-pinned-border-01"
                   "/attempt-000")
        seen = []
        for step in range(len(ACTION_TYPES)):
            paths = sorted((attempt / "actions").glob(
                f"step-{step:03d}*-intent.private.json"))
            self.assertEqual(len(paths), 1, step)
            intent = json.loads(paths[0].read_text())
            action = intent["normalized_action"]
            frame = (attempt / intent["frame_ref"]["path"]).read_bytes()
            self.assertEqual(sha256(frame).hexdigest(),
                             intent["frame_sha256"])
            visible = json.loads((attempt /
                intent["visible_text_ref"]["path"]).read_text())
            observation = make_observation(
                task_id=action["task_id"],
                task_binding_sha256=action["task_binding_sha256"],
                instruction="offline frozen-action validation", step=step,
                screenshot_bytes=frame, controls=visible["controls"],
                previous_action_result=(
                    {"status": "applied", "code": "ok"}
                    if step else None), memory=action["memory"])
            observation = replace(observation, frame_id=action["frame_id"])
            checked = through_adapter(action, observation)["action"]
            self.assertEqual(checked, action)
            seen.append(checked["type"])
        self.assertEqual(seen, ACTION_TYPES)


if __name__ == "__main__":
    unittest.main()
