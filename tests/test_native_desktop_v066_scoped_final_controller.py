"""Fake-provider scoped final trio is budgeted and fail-stops before replay."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_scoped_profile_final_controller as control


class ScopedFinalControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempts = self.root / "v066-final-gui"
        self.attempts.mkdir()
        self.row = {"task_id": "fake-private-final",
                    "package_sha256": "a" * 64}
        self.paths = {}
        for name in ("ratification", "reservation", "private_map",
                     "profile_private", "guest_public", "fair_public",
                     "scoped_reference", "runtime_freeze", "bridge_path",
                     "original_root", "failed_root", "public_calibration",
                     "private_calibration_audit", "failed_private_stop",
                     "failed_public_interruption"):
            path = self.root / name
            path.write_text("{}")
            self.paths[name] = path
        self.gate = {key: self.paths[key] for key in (
            "scoped_reference", "runtime_freeze", "bridge_path",
            "original_root", "failed_root", "public_calibration",
            "private_calibration_audit", "failed_private_stop",
            "failed_public_interruption")}

    def fake_subprocess(self, *, fail_near=False):
        commands = []

        def run(command, **_kwargs):
            commands.append(command)
            attempt = command[command.index("--attempt") + 1]
            target = self.attempts / self.row["task_id"] / attempt
            status = ("cold_reset_observed" if attempt == "cold-reset"
                      else "control_passed")
            if attempt == "near-miss" and fail_near:
                status = "control_failed_or_infrastructure_invalid"
            (target / "receipt.json").write_text(json.dumps({
                "status": status,
                "sandbox_id_sha256": {"positive": "1", "near-miss": "2",
                                      "cold-reset": "3"}[attempt] * 64,
                "is_running_after_kill": False}))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        return commands, run

    def run_task(self, *, fail_near=False):
        commands, provider = self.fake_subprocess(fail_near=fail_near)
        with (patch.object(control, "validate_bridge"),
              patch.object(control, "combined_budget"),
              patch.object(control, "intent_budget"),
              patch.object(control, "storage_audit",
                           return_value={"dispatch_storage_ready": True}),
              patch.object(control.subprocess, "run", side_effect=provider)):
            result = control._run_one_task(
                self.row, candidate_root=self.root,
                attempts_root=self.attempts,
                private_map=self.paths["private_map"],
                profile_private=self.paths["profile_private"],
                guest_public=self.paths["guest_public"],
                fair_public=self.paths["fair_public"],
                ratification=self.paths["ratification"],
                reservation=self.paths["reservation"],
                gate=self.gate,
                stop=threading.Event(), intent_lock=threading.Lock())
        return result, commands

    def test_fake_positive_near_reset_uses_new_child_and_three_intents(self):
        result, commands = self.run_task()
        self.assertEqual(result["status"], "provisional_trio_complete")
        self.assertEqual(len(commands), 3)
        self.assertTrue(all(control.CHILD in cmd for cmd in commands))
        self.assertTrue(all("--three-root-bridge" in cmd and
                            "--scoped-reference" in cmd and
                            "--enable-paid-scoped-final" in cmd
                            for cmd in commands))
        intents = list(self.attempts.glob("*/*/intent.json"))
        self.assertEqual(len(intents), 3)
        for path in intents:
            row = json.loads(path.read_bytes())
            self.assertEqual(row["scoped_reference_sha256"],
                             control.digest(self.paths[
                                 "scoped_reference"].read_bytes()))
            self.assertTrue(row["three_root_bridge_sha256"])

    def test_failed_near_miss_stops_before_cold_reset(self):
        result, commands = self.run_task(fail_near=True)
        self.assertEqual(result["status"],
                         "stopped_after_invalid_or_uncertain_attempt")
        self.assertEqual(len(commands), 2)
        self.assertFalse((self.attempts / self.row["task_id"] /
                          "cold-reset").exists())

    def test_paid_full100_requires_explicit_review_gate(self):
        with self.assertRaisesRegex(ValueError, "disabled before review"):
            control.execute(
                candidate_root=self.root,
                attempts_root=self.attempts,
                private_map=self.paths["private_map"],
                profile_private=self.paths["profile_private"],
                guest_public=self.paths["guest_public"],
                fair_public=self.paths["fair_public"],
                ratification=self.paths["ratification"],
                reservation=self.paths["reservation"],
                run_dir=self.root / "run", gate=self.gate,
                task_cap=100, concurrency=2)
