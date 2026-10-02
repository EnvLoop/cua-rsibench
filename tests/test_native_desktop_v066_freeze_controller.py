"""Prospective paid final controls refuse an absent or changed six-cell freeze."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cursibench.full_study_matrix_v1 import CELLS
from native_desktop_factory import v066_final_freeze as freeze
from native_desktop_factory import v066_final_rerun_controller as controller
from native_desktop_factory.v066_final_control_attempt import _operations


class V066FreezeControllerTests(unittest.TestCase):
    def _ratification(self):
        common = freeze.source_hashes()
        adapters = {cell: {"common_source_sha256s": common,
                           "adapter_sha256": "b" * 64} for cell in CELLS}
        adapters["desktop-native"]["adapter_sha256"] = freeze.digest(
            Path(freeze.qwen_v066_adapter.__file__).read_bytes())
        return {
            "schema": "cua-six-cell-action-profile-v066-ratification-v1",
            "status": "ratified_pre_result",
            "ratified_utc": datetime.now(timezone.utc).isoformat(),
            "action_profile": "scale-action-profile-v0.6.6",
            "common_source_sha256s": common,
            "cell_profiles": adapters,
            "base_and_selected_identical": True,
            "hidden_final_model_attempts_before_ratification": 0,
        }

    def test_six_cell_common_source_and_budget_reservation_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ratification = root / "ratification.json"
            ratification.write_text(json.dumps(self._ratification()))
            parsed, _sha = freeze.validate_ratification(ratification)
            self.assertEqual(len(parsed["cell_profiles"]), 6)
            parsed["cell_profiles"]["gitlab"]["common_source_sha256s"] = {}
            ratification.write_text(json.dumps(parsed))
            with self.assertRaises(ValueError):
                freeze.validate_ratification(ratification)
            ratification.write_text(json.dumps(self._ratification()))
            with patch.object(freeze, "_source_bindings", return_value={"sealed": "c" * 64}):
                lane = freeze.prepare_lane(
                    ratification=ratification, reservation=root / "lane.json",
                    candidate_root=root, guest_public=root, profile_private=root,
                    fair_public=root)
                self.assertEqual(lane["lane_cap_usd"], "60")
                self.assertEqual(lane["initial_full_lease_reserved_usd"], "50")
                freeze.validate_lane(
                    ratification=ratification, reservation=root / "lane.json",
                    candidate_root=root, guest_public=root, profile_private=root,
                    fair_public=root)

    def test_execute_cannot_reach_provider_without_ratification(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
                controller, "active_hashes") as active, patch.object(
                controller.subprocess, "run") as process:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                controller.execute(
                    candidate_root=root, attempts_root=root / "v066-final-gui",
                    private_map=root, profile_private=root,
                    guest_public=root, fair_public=root,
                    ratification=root / "missing-ratification.json",
                    reservation=root / "missing-reservation.json",
                    run_dir=root / "v066-rerun-runs" / "run",
                    task_cap=100, concurrency=3)
            active.assert_not_called()
            process.assert_not_called()
            self.assertFalse((root / "v066-rerun-runs" / "run").exists())

    def test_actor_translation_keeps_trusted_guards_outside_model_actions(self):
        operations = list(_operations(
            "wait 3\npress ctrl,h\nassert_window Find and Replace\n"
            "write replacement\nscreen edited\nreadback\nstop\n"))
        self.assertEqual([kind for kind, _ in operations],
                         ["actor", "actor", "actor", "assert_window",
                          "actor", "screen", "readback", "stop"])
        self.assertEqual(operations[2][1]["key"], "Control+H")


if __name__ == "__main__":
    unittest.main()
