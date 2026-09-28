"""Old22 and halted2 cannot be omitted from a new scoped final lease."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_scoped_profile_bridge as bridge
from native_desktop_factory.v066_final_freeze import digest


class ScopedThreeRootBridgeTests(unittest.TestCase):
    def test_exclusive_bridge_binds_all_three_roots_and_stop_bytes(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            old = root / "old/v066-final-gui"
            failed = root / "failed/v066-final-gui"
            fresh = root / "fresh/v066-final-gui"
            old.mkdir(parents=True)
            failed.mkdir(parents=True)
            files = {}
            for name in ("rat", "public-cal", "private-cal", "ref",
                         "runtime", "lane", "profile", "guest", "fair"):
                files[name] = root / f"{name}.json"
                files[name].write_text("{}")
            stop = root / "stop.private.json"
            stop.write_text("retained failed stop")
            interruption = root / "interruption-public.json"
            interruption.write_text(json.dumps({
                "private_stop_reconciliation_sha256": digest(stop.read_bytes())}))
            target = root / "bridge.private.json"
            fake_plan = {
                "candidate_inventory_sha256": "c" * 64,
                "old_evidence": {"original_attempt_tree_sha256": "a" * 64},
                "halted_amended_tree_sha256": "b" * 64,
                "halted_amended_stop_sha256": digest(stop.read_bytes()),
                "budget": {"combined_full_lease_intents": 324,
                           "combined_conservative_reserved_usd": "54"},
            }
            kwargs = {
                "bridge_path": target,
                "candidate_root": root / "candidates",
                "original_root": old, "failed_root": failed,
                "fresh_root": fresh,
                "action_ratification": files["rat"],
                "public_calibration": files["public-cal"],
                "private_calibration_audit": files["private-cal"],
                "scoped_reference": files["ref"],
                "runtime_freeze": files["runtime"],
                "new_lane_reservation": files["lane"],
                "profile_private": files["profile"],
                "guest_public": files["guest"],
                "fair_public": files["fair"],
            }
            with (patch.object(bridge, "inspect", return_value=(fake_plan, {})),
                  patch.object(bridge, "validate_runtime",
                               return_value=({}, "r" * 64)),
                  patch.object(bridge, "validate_lane", return_value={
                      "source_bindings": {
                          "candidate_inventory_sha256": "c" * 64}})):
                output = bridge.prepare(
                    **kwargs,
                    old_run_journal=root / "old-journal",
                    old_ratification=root / "old-rat",
                    old_reservation=root / "old-res",
                    failed_run_journal=root / "failed-journal",
                    failed_ratification=root / "failed-rat",
                    failed_reservation=root / "failed-res",
                    failed_private_stop=stop,
                    failed_public_interruption=interruption,
                    active_probe=lambda: (set(), 0))
                self.assertEqual(output["combined_full_lease_intents_planned"],
                                 324)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                with self.assertRaisesRegex(ValueError, "exclusive"):
                    bridge.prepare(
                        **kwargs,
                        old_run_journal=root / "old-journal",
                        old_ratification=root / "old-rat",
                        old_reservation=root / "old-res",
                        failed_run_journal=root / "failed-journal",
                        failed_ratification=root / "failed-rat",
                        failed_reservation=root / "failed-res",
                        failed_private_stop=stop,
                        failed_public_interruption=interruption,
                        active_probe=lambda: (set(), 0))

            with (patch.object(bridge, "validate_runtime",
                               return_value=({}, "r" * 64)),
                  patch.object(bridge, "validate_lane", return_value={
                      "source_bindings": {
                          "candidate_inventory_sha256": "c" * 64}}),
                  patch.object(bridge, "_tree_digest",
                               side_effect=lambda path: (
                                   "a" * 64 if path == old else "b" * 64, 1)),
                  patch.object(bridge, "combined_budget", return_value={
                      "combined_full_lease_intents": 324,
                      "combined_conservative_reserved_usd": "54"})):
                value, sha = bridge.validate(
                    **kwargs, failed_private_stop=stop,
                    failed_public_interruption=interruption)
                self.assertEqual(sha, output["bridge_sha256"])
                self.assertEqual(value["halted_amended_intents"], 2)
                stop.write_text("changed stop")
                with self.assertRaisesRegex(ValueError, "stop receipt changed"):
                    bridge.validate(
                        **kwargs, failed_private_stop=stop,
                        failed_public_interruption=interruption)
