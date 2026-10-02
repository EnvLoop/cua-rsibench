"""Offline process watchdog, journal terminal, and exact-reset tests."""

from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import v066_supervised_final_one_v1 as lane


class SupervisedGitLabOneTests(unittest.TestCase):
    def test_child_timeout_terminates_process_group(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            stdout, stderr = root / "stdout.private.log", root / "stderr.private.log"
            result = lane.supervise_child(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                cwd=root, env=dict(os.environ),
                stdout_path=stdout, stderr_path=stderr,
                timeout_seconds=0.15, grace_seconds=0.2)
            self.assertTrue(result["timed_out"])
            self.assertTrue(result["child_terminated"])
            self.assertNotEqual(result["exit_code"], 0)
            self.assertEqual(stdout.stat().st_mode & 0o077, 0)
            self.assertEqual(stderr.stat().st_mode & 0o077, 0)
            with self.assertRaises(ProcessLookupError):
                os.kill(result["child_pid"], 0)

    def _fake_reset_context(self, temporary: Path, *, world_exists: bool,
                            state_matches: bool):
        private = temporary / "private"
        private.mkdir(mode=0o700)
        (private / "demo-prestop.json").write_text(json.dumps({"stable": "demo"}))
        state_file = private / "cow-reset-state.json"
        state_file.write_text(json.dumps({"clone_generation": 7}))
        baseline = {"business_sha256": "a" * 64}
        current = baseline if state_matches else {"business_sha256": "b" * 64}
        state = {"baseline_business_sha256": baseline["business_sha256"],
                 "clone_generation": 7,
                 "seed_volume_lowerdirs": {"config": "config-lower",
                                           "logs": "logs-lower",
                                           "data": "data-lower"}}
        proof_world = {"running": True, "health": "healthy",
                       "image_id": lane.runtime.IMAGE_ID}
        proof_demo = {"running": False, "stable": "demo"}
        calls = []

        def inspect(_name):
            if not world_exists:
                raise subprocess.CalledProcessError(1, "docker inspect")
            return {}

        def proof(name):
            return proof_world if name == lane.runtime.WORLD else proof_demo

        patches = (
            patch.object(lane, "PRIVATE_ROOT", private),
            patch.object(lane.reset, "STATE_FILE", state_file),
            patch.object(lane.reset, "_baseline", return_value=baseline),
            patch.object(lane.reset, "_state", return_value=state),
            patch.object(lane.runtime, "inspect", side_effect=inspect),
            patch.object(lane.runtime, "proof", side_effect=proof),
            patch.object(lane.runtime, "stable_identity",
                         side_effect=lambda row: row["stable"]),
            patch.object(lane.verify, "state_snapshot", return_value=current),
            patch.object(lane.reset, "reset",
                         side_effect=lambda: calls.append("reset") or
                         {"cold_reset": True,
                          "same_business_sha256": True}),
            patch.object(lane.reset, "_unmount_and_clear",
                         side_effect=lambda role: calls.append("unmount:" + role)),
            patch.object(lane.reset, "_mount",
                         side_effect=lambda role, lower:
                         calls.append("mount:" + role + ":" + lower)),
            patch.object(lane.reset, "_create_case",
                         side_effect=lambda: calls.append("create") or
                         {"container_id_sha256": "c" * 64}),
        )
        return patches, calls, state_file

    def test_existing_world_cleanup_requires_independent_exact_state(self):
        with TemporaryDirectory() as temporary:
            patches, calls, _ = self._fake_reset_context(
                Path(temporary), world_exists=True, state_matches=True)
            with _many_patches(patches):
                result = lane.exact_cold_reset()
            self.assertTrue(result["cold_reset_exact"])
            self.assertEqual(result["mode"], "existing_world_cold_reset")
            self.assertEqual(calls, ["reset"])

    def test_existing_world_bad_readback_fails_closed(self):
        with TemporaryDirectory() as temporary:
            patches, calls, _ = self._fake_reset_context(
                Path(temporary), world_exists=True, state_matches=False)
            with _many_patches(patches):
                with self.assertRaisesRegex(
                        lane.SupervisionError, "not_exact"):
                    lane.exact_cold_reset()
            self.assertEqual(calls, ["reset"])

    def test_missing_world_recreated_then_state_committed_only_after_exact_readback(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            patches, calls, state_file = self._fake_reset_context(
                root, world_exists=False, state_matches=True)
            with _many_patches(patches):
                result = lane.exact_cold_reset()
            self.assertTrue(result["cold_reset_exact"])
            self.assertEqual(result["mode"],
                             "missing_world_recreated_from_immutable_lowerdirs")
            self.assertIn("create", calls)
            self.assertEqual(json.loads(state_file.read_bytes())[
                "clone_generation"], 8)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            patches, calls, state_file = self._fake_reset_context(
                root, world_exists=False, state_matches=False)
            with _many_patches(patches):
                with self.assertRaises(lane.SupervisionError):
                    lane.exact_cold_reset()
            self.assertIn("create", calls)
            self.assertEqual(json.loads(state_file.read_bytes())[
                "clone_generation"], 7)

    def test_pending_or_unstarted_id_is_terminalized_without_replay(self):
        with TemporaryDirectory() as temporary:
            private = Path(temporary) / "private"
            private.mkdir(mode=0o700)
            run = private / "run"
            run.mkdir(mode=0o700)
            old = {"task_roster": [{"task_id": "t0",
                                    "package_sha256": "b" * 64}],
                   "source_bundle_sha256": "c" * 64}
            with patch.object(lane, "RUN_DIR", run):
                result = lane.terminalize_uncertain(
                    0, old, "a" * 64,
                    error_type="SupervisedProcessTimeout",
                    wall_seconds=7.25)
                entries = lane.lane.read_journal(run, "a" * 64)
                state = lane.lane.journal_state(entries, old)
            self.assertTrue(result["terminal_failure"])
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[1]["wall_seconds"], 7.25)
            self.assertTrue(state["failed"])
            self.assertIsNone(state["pending"])


class _many_patches:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for patcher in self.patches:
            patcher.start()

    def __exit__(self, *_exc):
        for patcher in reversed(self.patches):
            patcher.stop()


if __name__ == "__main__":
    unittest.main()
