"""Offline crash-window and bounded-continuation checks; no provider calls."""

from __future__ import annotations

import json
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from native_desktop_factory import (
    v066_day_rollover_continuation_v3 as control,
    v066_day_rollover_durable_audit_v3 as durable_audit,
    v066_day_rollover_durable_child_v3 as child,
    v066_scoped_profile_final_controller as original,
)


class DurableContinuationTests(unittest.TestCase):
    def _paths(self, root: Path) -> dict[str, Path]:
        names = (
            "candidate_root", "attempts_root", "private_map",
            "profile_private", "guest_public", "fair_public",
            "action_ratification", "reservation", "old_original_root",
            "old_caret_root", "old_failed_scoped_root",
        )
        paths = {name: root / name for name in names}
        for name in ("action_ratification", "reservation"):
            paths[name].write_text(name)
        return paths

    def _gate(self, root: Path) -> dict[str, Path]:
        names = (
            "bridge_path", "original_root", "failed_root",
            "public_calibration", "private_calibration_audit",
            "scoped_reference", "runtime_freeze", "failed_private_stop",
            "failed_public_interruption",
        )
        gate = {name: root / name for name in names}
        for name in ("bridge_path", "scoped_reference", "runtime_freeze"):
            gate[name].write_text(name)
        return gate

    def test_original_child_dispatch_window_lacked_intent_fsync(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            paths = self._paths(root)
            gate = self._gate(root)
            row = {"task_id": "offline-only", "package_sha256": "a" * 64}
            with (patch.object(original, "validate_bridge"),
                  patch.object(original, "combined_budget"),
                  patch.object(original, "intent_budget"),
                  patch.object(original, "storage_audit",
                               return_value={"dispatch_storage_ready": True}),
                  patch.object(original.subprocess, "run",
                               side_effect=RuntimeError("injected crash before child")),
                  patch.object(os, "fsync", wraps=os.fsync) as fsync):
                with self.assertRaisesRegex(RuntimeError, "injected crash"):
                    original._run_one_task(
                        row, candidate_root=paths["candidate_root"],
                        attempts_root=paths["attempts_root"],
                        private_map=paths["private_map"],
                        profile_private=paths["profile_private"],
                        guest_public=paths["guest_public"],
                        fair_public=paths["fair_public"],
                        ratification=paths["action_ratification"],
                        reservation=paths["reservation"], gate=gate,
                        stop=threading.Event(), intent_lock=threading.Lock())
            self.assertTrue((paths["attempts_root"] / "offline-only" /
                             "positive/intent.json").exists())
            self.assertEqual(fsync.call_count, 0)

    def test_v3_fsyncs_budget_and_intent_before_injected_dispatch_failure(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            paths = self._paths(root)
            gate = self._gate(root)
            row = {"task_id": "offline-only", "package_sha256": "a" * 64}
            attempt_root = paths["attempts_root"] / "offline-only" / "positive"
            real_fsync = os.fsync
            with (patch.object(control, "_sdk_and_credential",
                               return_value=control.SDK_VERSIONS),
                  patch.object(control, "_power_snapshot", return_value={
                      "observed_utc": "test", "source": "Battery Power",
                      "battery_percent": 80}),
                  patch.object(control, "active_hashes", return_value=(set(), 0)),
                  patch.object(control, "validate_bridge"),
                  patch.object(control, "combined_budget", return_value={
                      "combined_full_lease_intents": 51}),
                  patch.object(control, "intent_budget", return_value={
                      "combined_intents": 25}),
                  patch.object(control, "storage_audit", return_value={
                      "dispatch_storage_ready": True}),
                  patch.object(os, "fsync", wraps=real_fsync) as fsync):
                def crash(_command):
                    self.assertTrue((attempt_root / "budget.json").is_file())
                    intent = json.loads((attempt_root / "intent.json").read_bytes())
                    self.assertEqual(intent["precreate_budget_sha256"],
                                     control.digest((attempt_root / "budget.json").read_bytes()))
                    self.assertGreaterEqual(fsync.call_count, 5)
                    raise RuntimeError("injected before provider")
                with patch.object(control, "_invoke_child", side_effect=crash):
                    with self.assertRaisesRegex(RuntimeError, "injected before"):
                        control._task(row=row, paths=paths, gate=gate,
                                      wrapper_sha="b" * 64,
                                      stop=threading.Event())
            self.assertTrue((attempt_root / "intent.json").is_file())

    def test_receipt_adapter_fsyncs_before_original_child_advances(self):
        with tempfile.TemporaryDirectory() as scratch:
            receipt = Path(scratch) / "receipt.json"
            with patch.object(os, "fsync", wraps=os.fsync) as fsync:
                def fake_original_main():
                    receipt.write_text('{"stage":"create_desktop"}\n')
                    self.assertEqual(receipt.read_text(),
                                     '{"stage":"create_desktop"}\n')
                    self.assertEqual(fsync.call_count, 2)
                with patch.object(child.original, "main",
                                  side_effect=fake_original_main):
                    child.main()

    def test_source_freeze_rejects_private_byte_mutation(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            base = root / "base.json"
            base.write_text("{}\n")
            freeze = root / "freeze.json"
            public = root / "public.json"
            value = {
                "schema": control.SCHEMA,
                "status": "frozen_before_durable_untouched_continuation",
                "source_sha256s": control._sources(),
                "same_id_retry_authorized": False,
                "official_final_admissions": 0,
                "base_freeze_path": str(base),
                "base_freeze_sha256": control.digest(base.read_bytes()),
                "public_path": str(public),
            }
            control._write_new(freeze, value)
            control._write_new(public, {
                "schema": control.PUBLIC_SCHEMA,
                "private_freeze_sha256": control.digest(freeze.read_bytes()),
                "source_sha256s": value["source_sha256s"],
            }, public=True)
            value["frozen_full100_source_sha256s"] = {}
            freeze.write_text(json.dumps(value))
            freeze.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "Published v3 source freeze"):
                control.validate_live(freeze=freeze)

    def test_preserved_v2_freeze_cannot_drop_paid_child_hashes(self):
        with tempfile.TemporaryDirectory() as scratch:
            mutant = Path(scratch) / "mutated-v2.private.json"
            mutant.write_text(json.dumps({
                "frozen_full100_source_sha256s": {},
            }))
            with self.assertRaisesRegex(ValueError, "Published v2 freeze"):
                control._verify_base_public(mutant)

    def test_timeout_kills_child_process_group(self):
        process = Mock()
        process.pid = 123456
        process.poll.return_value = None
        process.communicate.side_effect = subprocess.TimeoutExpired("fake", 720)
        process.wait.return_value = 0
        with (patch.object(control.subprocess, "Popen", return_value=process),
              patch.object(control.os, "killpg") as kill):
            code, stdout, stderr, uncertain = control._invoke_child(["fake"])
        self.assertIsNone(code)
        self.assertTrue(uncertain)
        self.assertEqual((stdout, stderr), ("", ""))
        kill.assert_called_once_with(123456, control.signal.SIGTERM)

    def test_independent_durable_audit_checks_three_lease_costs(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            roster = [{"task_id": f"offline-{index}"} for index in range(100)]
            wrapper_sha = "a" * 64
            for offset, attempt in enumerate(control.ATTEMPTS):
                directory = root / "offline-9" / attempt
                directory.mkdir(parents=True)
                budget = {
                    "schema": "cua-native-wdi-v066-precreate-budget-private-v3",
                    "status": "fsynced_before_provider_create",
                    "task_id": "offline-9", "attempt": attempt,
                    "provider_active_before_intent": 0,
                    "storage_dispatch_ready": True,
                    "credential_present": True,
                    "sdk_versions": control.SDK_VERSIONS,
                    "four_root_budget": {
                        "combined_full_lease_intents": 51 + offset,
                        "combined_conservative_reserved_usd": str(
                            Decimal(51 + offset) / Decimal(6))},
                    "fresh_lane_budget": {"combined_intents": 25 + offset},
                    "power": {"source": "Battery Power",
                              "observed_utc": "2026-09-29T00:00:00Z"},
                }
                budget_path = directory / "budget.json"
                budget_path.write_text(json.dumps(budget))
                intent = {
                    "schema": "cua-native-wdi-v066-final-control-intent-v1",
                    "task_id": "offline-9", "attempt": attempt,
                    "lease_seconds": control.LEASE_SECONDS,
                    "precreate_budget_sha256":
                        control.digest(budget_path.read_bytes()),
                    "durable_child_wrapper_sha256": wrapper_sha,
                }
                (directory / "intent.json").write_text(json.dumps(intent))
                (directory / "receipt.json").write_text(json.dumps({
                    "task_id": "offline-9", "attempt": attempt,
                    "status": "cold_reset_observed" if attempt == "cold-reset"
                              else "control_passed"}))
                for path in directory.iterdir():
                    path.chmod(0o600)
            result = durable_audit.audit(
                attempts_root=root, roster=roster,
                initial_accepted=8, prior_intents=24,
                wrapper_sha=wrapper_sha)
            self.assertEqual(result["new_durable_attempts_reopened"], 3)
            budget_path = root / "offline-9/positive/budget.json"
            budget = json.loads(budget_path.read_bytes())
            budget["four_root_budget"]["combined_conservative_reserved_usd"] = "0"
            budget_path.write_text(json.dumps(budget))
            with self.assertRaisesRegex(ValueError, "budget, intent, or receipt"):
                durable_audit.audit(
                    attempts_root=root, roster=roster,
                    initial_accepted=8, prior_intents=24,
                    wrapper_sha=wrapper_sha)

    def test_two_id_batch_audits_each_and_finishes_with_terminal_journal(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            paths = self._paths(root)
            for name in ("bridge_path", "old_original_root", "old_caret_root",
                         "public_day_audit", "private_day_audit", "reference_path",
                         "runtime_freeze", "failed_private_stop",
                         "failed_public_interruption"):
                paths[name] = root / name
            rows = [{"task_id": f"offline-{index}"} for index in range(100)]
            run_dir = root / "v066-durable-continuation-runs" / "batch-0001"
            paths["attempts_root"] = root / "v066-final-gui"
            freeze = root / "freeze.json"
            freeze.write_text("frozen")
            before = {"independently_accepted_complete_trios": 7}
            after_one = {"independently_accepted_complete_trios": 8}
            after_two = {"independently_accepted_complete_trios": 9}
            source = {"source_sha256s": {
                "native_desktop_factory/v066_day_rollover_durable_child_v3.py":
                    "a" * 64}}
            with (patch.object(control, "validate_live", side_effect=[
                    (source, before, paths, rows),
                    (source, after_one, paths, rows),
                    (source, after_two, paths, rows)]),
                  patch.object(control, "combined_budget", return_value={}),
                  patch.object(control, "_sdk_and_credential",
                               return_value=control.SDK_VERSIONS),
                  patch.object(control, "_power_snapshot", return_value={
                      "source": "AC Power"}),
                  patch.object(control, "active_hashes", return_value=(set(), 0)),
                  patch.object(control, "_task", return_value={
                      "status": "provisional_trio_complete"}) as task):
                result = control.run_batch(
                    freeze=freeze, run_dir=run_dir,
                    max_new_ids=2, execute=True)
            self.assertEqual(result["status"], "bounded_completed_and_audited")
            self.assertEqual(result["new_complete_trios"], 2)
            self.assertEqual(task.call_count, 2)
            journal = json.loads((run_dir / "run-receipt.json").read_bytes())
            self.assertEqual(journal["status"], "bounded_completed_and_audited")
            self.assertEqual(journal["independently_accepted_complete_trios_after"], 9)
            self.assertEqual(journal["official_final_admissions"], 0)

    def test_uncertain_first_id_stops_second_id_without_replay(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            paths = self._paths(root)
            for name in ("bridge_path", "public_day_audit", "private_day_audit",
                         "reference_path", "runtime_freeze", "failed_private_stop",
                         "failed_public_interruption"):
                paths[name] = root / name
            paths["attempts_root"] = root / "v066-final-gui"
            rows = [{"task_id": f"offline-{index}"} for index in range(100)]
            run_dir = root / "v066-durable-continuation-runs" / "batch-0001"
            freeze = root / "freeze.json"
            freeze.write_text("frozen")
            source = {"source_sha256s": {
                "native_desktop_factory/v066_day_rollover_durable_child_v3.py":
                    "a" * 64}}
            with (patch.object(control, "validate_live", return_value=(
                    source, {"independently_accepted_complete_trios": 7},
                    paths, rows)),
                  patch.object(control, "combined_budget", return_value={}),
                  patch.object(control, "_sdk_and_credential",
                               return_value=control.SDK_VERSIONS),
                  patch.object(control, "_power_snapshot", return_value={
                      "source": "Battery Power"}),
                  patch.object(control, "active_hashes", return_value=(set(), 0)),
                  patch.object(control, "_task", return_value={
                      "status": "stopped_after_invalid_or_uncertain_attempt"}) as task):
                result = control.run_batch(
                    freeze=freeze, run_dir=run_dir,
                    max_new_ids=2, execute=True)
            self.assertEqual(result["status"], "stopped_for_reconciliation")
            self.assertEqual(task.call_count, 1)
            journal = json.loads((run_dir / "run-receipt.json").read_bytes())
            self.assertEqual(journal["status"], "stopped_for_reconciliation")
            self.assertEqual(len(journal["task_outcomes"]), 1)

    def test_stale_independent_audit_cannot_mark_a_trio_complete(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            paths = self._paths(root)
            for name in ("bridge_path", "public_day_audit", "private_day_audit",
                         "reference_path", "runtime_freeze", "failed_private_stop",
                         "failed_public_interruption"):
                paths[name] = root / name
            paths["attempts_root"] = root / "v066-final-gui"
            rows = [{"task_id": f"offline-{index}"} for index in range(100)]
            run_dir = root / "v066-durable-continuation-runs" / "batch-0001"
            freeze = root / "freeze.json"
            freeze.write_text("frozen")
            source = {"source_sha256s": {
                "native_desktop_factory/v066_day_rollover_durable_child_v3.py":
                    "a" * 64}}
            unchanged = {"independently_accepted_complete_trios": 7}
            with (patch.object(control, "validate_live", side_effect=[
                    (source, unchanged, paths, rows),
                    (source, unchanged, paths, rows)]),
                  patch.object(control, "combined_budget", return_value={}),
                  patch.object(control, "_sdk_and_credential",
                               return_value=control.SDK_VERSIONS),
                  patch.object(control, "_power_snapshot", return_value={
                      "source": "AC Power"}),
                  patch.object(control, "active_hashes", return_value=(set(), 0)),
                  patch.object(control, "_task", return_value={
                      "status": "provisional_trio_complete"})):
                result = control.run_batch(
                    freeze=freeze, run_dir=run_dir,
                    max_new_ids=1, execute=True)
            self.assertEqual(result["status"],
                             "stopped_after_independent_audit_failure")
            journal = json.loads((run_dir / "run-receipt.json").read_bytes())
            self.assertEqual(journal["audit_error_type"], "ValueError")

    def test_root_interruption_leaves_explicit_terminal_no_replay_journal(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            paths = self._paths(root)
            for name in ("bridge_path", "public_day_audit", "private_day_audit",
                         "reference_path", "runtime_freeze", "failed_private_stop",
                         "failed_public_interruption"):
                paths[name] = root / name
            paths["attempts_root"] = root / "v066-final-gui"
            rows = [{"task_id": f"offline-{index}"} for index in range(100)]
            run_dir = root / "v066-durable-continuation-runs" / "batch-0001"
            freeze = root / "freeze.json"
            freeze.write_text("frozen")
            source = {"source_sha256s": {
                "native_desktop_factory/v066_day_rollover_durable_child_v3.py":
                    "a" * 64}}
            with (patch.object(control, "validate_live", return_value=(
                    source, {"independently_accepted_complete_trios": 7},
                    paths, rows)),
                  patch.object(control, "combined_budget", return_value={}),
                  patch.object(control, "_sdk_and_credential",
                               return_value=control.SDK_VERSIONS),
                  patch.object(control, "_power_snapshot", return_value={
                      "source": "Battery Power"}),
                  patch.object(control, "active_hashes", return_value=(set(), 0)),
                  patch.object(control, "_task",
                               side_effect=RuntimeError("injected root interruption"))):
                with self.assertRaisesRegex(RuntimeError, "injected root"):
                    control.run_batch(freeze=freeze, run_dir=run_dir,
                                      max_new_ids=2, execute=True)
            journal = json.loads((run_dir / "run-receipt.json").read_bytes())
            self.assertEqual(journal["status"],
                             "stopped_after_root_interruption")
            self.assertEqual(journal["interruption_type"], "RuntimeError")
            self.assertEqual(journal["official_final_admissions"], 0)


if __name__ == "__main__":
    unittest.main()
