"""Offline lineage and full-lease tests; no sandbox or model call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from native_desktop_factory import v066_caret_full100_preflight as gate
from native_desktop_factory import v066_caret_full100_dispatch as dispatch
from native_desktop_factory import v066_caret_train_replay as replay
from native_desktop_factory import qwen_v066_adapter


def private_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    path.chmod(0o600)


def png(*, caret=False, large=False) -> bytes:
    image = Image.new("RGB", (1280, 800), "white")
    if caret:
        for y in range(300, 321):
            image.putpixel((400, y), (0, 0, 0))
    if large:
        for x in range(300, 310):
            for y in range(300, 310):
                image.putpixel((x, y), (0, 0, 0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class CrossRootFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidates = self.root / "candidates"
        self.candidates.mkdir(mode=0o700)
        self.final = {f"private-task-{i:03d}": "a" * 64
                      for i in range(100)}
        inventory = {
            "design_revision": "v2-distinct-structures",
            "tasks": [{"task_id": task_id,
                       "split": "final_candidate",
                       "package_sha256": package_sha}
                      for task_id, package_sha in self.final.items()]}
        (self.candidates / "candidate-inventory.json").write_text(
            json.dumps(inventory))
        self.inventory_sha = gate.digest(
            (self.candidates / "candidate-inventory.json").read_bytes())
        self.original = self.root / "original" / "v066-final-gui"
        self.original.mkdir(parents=True, mode=0o700)
        self.original.chmod(0o700)
        self.fresh = self.root / "amended" / "v066-final-gui"
        self.old_ratification = self.root / "old-ratification.json"
        self.old_reservation = self.root / "old-reservation.json"
        private_json(self.old_ratification, {
            "schema": "cua-six-cell-action-profile-v066-ratification-v1",
            "status": "ratified_pre_result",
            "common_source_sha256s": gate.common_source_hashes(),
            "cell_profiles": {"desktop-native": {
                "adapter_sha256": gate.OLD_ADAPTER_SHA256}}})
        self.old_rat_sha = gate.digest(self.old_ratification.read_bytes())
        private_json(self.old_reservation, {
            "schema": "cua-native-wdi-v066-final-control-lane-reservation-v1",
            "ratification_sha256": self.old_rat_sha,
            "source_bindings": {
                "candidate_inventory_sha256": self.inventory_sha},
            "lane_cap_usd": "60"})
        self.old_res_sha = gate.digest(self.old_reservation.read_bytes())
        self.failed_task_id = "private-task-007"
        self._write_attempts()
        self.journal = self.root / "old-run.json"
        private_json(self.journal, {
            "schema": "cua-native-wdi-v066-final-rerun-private-v1",
            "status": "stopped_for_reconciliation",
            "plan": {"candidate_inventory_sha256": self.inventory_sha},
            "ratification_sha256": self.old_rat_sha,
            "reservation_sha256": self.old_res_sha,
            "official_final_model_attempts": 0,
            "official_final_admissions": 0,
            "task_outcomes": ([{"status": "provisional_trio_complete"}] * 6 +
                              [{"status": "stopped_after_invalid_or_uncertain_attempt",
                                "private_task_id": self.failed_task_id}] +
                              [{"status": "stopped_before_next_create"}] * 92)})
        self._write_storage()

    def _write_attempts(self):
        ordinal = 0
        for i in range(8):
            task_id = f"private-task-{i:03d}"
            names = (("positive",) if i == 7 else
                     ("positive", "near-miss", "cold-reset"))
            for attempt in names:
                path = self.original / task_id / attempt
                path.mkdir(parents=True, mode=0o700)
                path.parent.chmod(0o700)
                status = ("control_failed_or_infrastructure_invalid"
                          if i == 7 else
                          "cold_reset_observed" if attempt == "cold-reset"
                          else "control_passed")
                private_json(path / "intent.json", {
                    "schema": "cua-native-wdi-v066-final-control-intent-v1",
                    "created_utc": (
                        datetime.now(timezone.utc) - timedelta(hours=2)
                    ).isoformat(),
                    "task_id": task_id, "attempt": attempt,
                    "package_sha256": self.final[task_id],
                    "lease_seconds": 600,
                    "ratification_sha256": self.old_rat_sha,
                    "reservation_sha256": self.old_res_sha})
                receipt = {
                    "schema": "cua-native-wdi-v066-gui-control-attempt-v1",
                    "task_id": task_id, "attempt": attempt,
                    "package_sha256": self.final[task_id],
                    "runner_sha256": gate.OLD_RUNNER_SHA256,
                    "native_adapter_sha256": gate.OLD_ADAPTER_SHA256,
                    "ratification_sha256": self.old_rat_sha,
                    "lane_reservation_sha256": self.old_res_sha,
                    "official_hidden_final_model_attempts": 0,
                    "kill_returned": True,
                    "is_running_after_kill": False,
                    "sandbox_id_sha256": f"{ordinal:064x}",
                    "status": status}
                if status == "control_failed_or_infrastructure_invalid":
                    receipt.update({
                        "error_type": "PhysicalFrameDrift",
                        "contract_error_code": "stale_frame",
                        "expected_actor_action_count": 53,
                        "actor_steps": [{"step": j, "status": "applied"}
                                        for j in range(33)],
                        "physical_frame_resamples": [
                            {"step": 33, "attempt": j} for j in range(5)]})
                private_json(path / "receipt.json", receipt)
                ordinal += 1

    def _write_storage(self):
        self.raw = (self.original /
                    "private-task-000/positive/frame-00-0.png")
        self.raw.write_bytes(b"retained raw screenshot")
        self.raw.chmod(0o600)
        database = self.original / "storage-ledger.sqlite3"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE budget(id INTEGER PRIMARY KEY, reserved_bytes INTEGER)")
        connection.execute("CREATE TABLE evidence(path TEXT, bytes INTEGER, sha256 TEXT, status TEXT)")
        connection.execute("INSERT INTO budget VALUES (1, ?)",
                           (self.raw.stat().st_size,))
        connection.execute("INSERT INTO evidence VALUES (?, ?, ?, ?)",
                           (str(self.raw.relative_to(self.original)),
                            self.raw.stat().st_size,
                            gate.digest(self.raw.read_bytes()), "written"))
        connection.commit()
        connection.close()
        database.chmod(0o600)

    def original_kwargs(self):
        return {"candidate_root": self.candidates,
                "original_root": self.original,
                "old_run_journal": self.journal,
                "old_ratification": self.old_ratification,
                "old_reservation": self.old_reservation}

    def synthetic_public_amendment(self, retained):
        value = json.loads(gate.AMENDMENT.read_bytes())
        value.update({
            "candidate_inventory_sha256":
                retained["candidate_inventory_sha256"],
            "old_six_cell_ratification_sha256":
                retained["original_ratification_sha256"],
            "old_desktop_lane_reservation_sha256":
                retained["original_reservation_sha256"],
            "retained_old_run_journal_sha256":
                retained["original_run_journal_sha256"],
            "retained_old_attempt_tree_sha256":
                retained["original_attempt_tree_sha256"],
            "retained_old_attempt_tree_files":
                retained["original_attempt_tree_files"],
            "retained_old_storage_ledger_sha256":
                retained["original_storage"]["ledger_sha256"],
            "retained_old_raw_evidence_rows_verified":
                retained["original_storage"]["verified_raw_evidence_rows"],
            "retained_old_raw_evidence_bytes_verified":
                retained["original_storage"]["reserved_evidence_bytes"],
        })
        path = self.root / "public-amendment.json"
        path.write_text(json.dumps(value))
        patcher = patch.object(gate, "AMENDMENT", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        return path

    def test_old22_and_new300_charge_one_existing_60_dollar_lane(self):
        retained = gate.audit_retained_original(**self.original_kwargs())
        self.assertEqual(retained["original_intents"], 22)
        self.assertEqual(retained["original_complete_trios"], 7)
        self.assertEqual(retained["original_storage"]["verified_raw_evidence_rows"], 1)
        before = retained["original_attempt_tree_sha256"]
        planned = gate.combined_budget(
            original_root=self.original, fresh_root=self.fresh,
            proposed_new_intents=300)
        self.assertEqual(planned["combined_full_lease_intents"], 322)
        self.assertEqual(planned["combined_conservative_reserved_usd"],
                         "53.66666666666666666666666667")
        self.assertEqual(gate.audit_retained_original(
            **self.original_kwargs())["original_attempt_tree_sha256"], before)
        with self.assertRaises(ValueError):
            gate.combined_budget(original_root=self.original,
                                 fresh_root=self.fresh,
                                 proposed_new_intents=301)

    def test_original_raw_bytes_and_attempt_count_cannot_be_laundered(self):
        self.raw.write_bytes(b"changed raw screenshot")
        with self.assertRaisesRegex(ValueError, "raw-frame bytes changed"):
            gate.audit_retained_original(**self.original_kwargs())

    def test_old_lease_plus_grace_blocks_new_paid_preflight(self):
        path = self.original / "private-task-000/positive/intent.json"
        intent = json.loads(path.read_bytes())
        intent["created_utc"] = datetime.now(timezone.utc).isoformat()
        private_json(path, intent)
        retained = gate.audit_retained_original(**self.original_kwargs())
        self.assertFalse(retained["original_all_leases_plus_grace_mature"])
        with self.assertRaisesRegex(ValueError, "cleanup grace"):
            gate.preflight_fresh_full100(
                **self.original_kwargs(), fresh_root=self.fresh,
                new_ratification=self.root / "not-yet-ratified",
                new_reservation=self.root / "not-yet-reserved",
                bridge_path=self.root / "not-yet-bridged",
                profile_private=self.root / "profile",
                guest_public=self.root / "guest",
                fair_public=self.root / "fair")

    def test_paid_wrapper_requires_explicit_enable_and_composite_gate(self):
        kwargs = {"candidate_root": self.candidates,
                  "original_root": self.original,
                  "fresh_root": self.fresh,
                  "old_run_journal": self.journal,
                  "old_ratification": self.old_ratification,
                  "old_reservation": self.old_reservation,
                  "new_ratification": self.root / "new-ratification.json",
                  "new_reservation": self.root / "new-reservation.json",
                  "bridge_path": self.root / "bridge.json",
                  "private_map": self.root / "private-map.json",
                  "profile_private": self.root / "profile.json",
                  "guest_public": self.root / "guest.json",
                  "fair_public": self.root / "fair.json",
                  "run_dir": self.root / "amended/v066-rerun-runs/run-1",
                  "concurrency": 2}
        with patch.object(dispatch, "frozen_execute") as provider:
            with self.assertRaisesRegex(ValueError, "disabled"):
                dispatch.execute_amended_full100(**kwargs)
            provider.assert_not_called()
            with patch.object(dispatch, "preflight_fresh_full100",
                              side_effect=ValueError("bridge missing")):
                with self.assertRaisesRegex(ValueError, "bridge missing"):
                    dispatch.execute_amended_full100(
                        **kwargs, enable_paid_control_run=True)
                provider.assert_not_called()
            with patch.object(dispatch, "preflight_fresh_full100",
                              return_value={"combined_budget": {
                                  "combined_full_lease_intents": 322}}):
                dispatch.execute_amended_full100(
                    **kwargs, enable_paid_control_run=True)
                provider.assert_called_once()
                self.assertEqual(provider.call_args.kwargs["task_cap"], 100)
                self.assertEqual(provider.call_args.kwargs["attempts_root"],
                                 self.fresh)

    def test_bridge_requires_old_tree_new_hash_and_unused_root(self):
        retained = gate.audit_retained_original(**self.original_kwargs())
        amendment_path = self.synthetic_public_amendment(retained)
        new_ratification = self.root / "new-ratification.json"
        new_reservation = self.root / "new-reservation.json"
        prior = (datetime.now(timezone.utc) -
                 timedelta(minutes=2)).isoformat()
        private_json(new_ratification, {"ratified_utc": prior})
        private_json(new_reservation, {"recorded_utc": prior})
        bridge = gate.expected_bridge(
            retained=retained, new_ratification=new_ratification,
            new_reservation=new_reservation)
        bridge["recorded_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        bridge_path = self.root / "private-bridge.json"
        private_json(bridge_path, bridge)
        kwargs = {**self.original_kwargs(), "fresh_root": self.fresh,
                  "new_ratification": new_ratification,
                  "new_reservation": new_reservation,
                  "bridge_path": bridge_path,
                  "profile_private": self.root / "unused-profile",
                  "guest_public": self.root / "unused-guest",
                  "fair_public": self.root / "unused-fair"}
        with patch.object(gate, "validate_lane", return_value={}):
            ready = gate.preflight_fresh_full100(**kwargs)
            self.assertEqual(ready["combined_budget"][
                "combined_full_lease_intents"], 322)
            self.assertFalse(ready["provider_active_zero_verified"])
            # A second launch using a used attempts root fails before dispatch.
            path = self.fresh / "private-task-000" / "positive"
            path.mkdir(parents=True, mode=0o700)
            self.fresh.chmod(0o700)
            private_json(path / "intent.json", {
                "schema": "cua-native-wdi-v066-final-control-intent-v1",
                "lease_seconds": 600, "task_id": "private-task-000",
                "attempt": "positive"})
            with self.assertRaisesRegex(ValueError, "unused fresh root"):
                gate.preflight_fresh_full100(**kwargs)
            bridge["original_attempt_tree_sha256"] = "0" * 64
            private_json(bridge_path, bridge)
            with self.assertRaisesRegex(ValueError, "reservation bridge invalid"):
                gate.preflight_fresh_full100(**kwargs)
            amendment = json.loads(amendment_path.read_text())
            amendment["retained_old_attempt_tree_sha256"] = "0" * 64
            amendment_path.write_text(json.dumps(amendment))
            with self.assertRaisesRegex(
                    ValueError, "does not bind old evidence"):
                gate.preflight_fresh_full100(**kwargs)


class TrainOnlyReplayTests(unittest.TestCase):
    def test_public_pre_result_amendment_binds_exact_adapter_source(self):
        path = (Path(__file__).resolve().parents[1] / "docs/evidence" /
                "native-wdi-v066-caret-pre-result-amendment-2026-09-28.json")
        public = json.loads(path.read_bytes())
        self.assertEqual(public["old_adapter_sha256"],
                         gate.OLD_ADAPTER_SHA256)
        self.assertEqual(public["proposed_new_adapter_sha256"],
                         gate.digest(Path(qwen_v066_adapter.__file__).read_bytes()))
        self.assertEqual(public["official_final_admissions"], 0)
        self.assertEqual(public["official_model_results"], 0)

    def test_raw_train_pairs_have_positive_and_negative_shape_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "v066-train-primitive-smoke-001"
            directory.mkdir()
            plain, caret, material = png(), png(caret=True), png(large=True)
            rows = []
            for step, changed in enumerate((caret, material)):
                (directory / f"frame-{step:02d}-0.png").write_bytes(plain)
                (directory / f"drift-{step:02d}-0.png").write_bytes(changed)
                rows.append({"step": step, "frame_attempt": 0,
                             "observation_screenshot_sha256": gate.digest(plain),
                             "changed_screenshot_sha256": gate.digest(changed)})
            (directory / "receipt.json").write_text(json.dumps({
                "schema": "cua-native-wdi-gui-development-attempt-v1",
                "split": "train",
                "purpose": "v066_public_train_primitive_smoke_no_model",
                "official_final_model_attempts": 0,
                "physical_frame_resamples": rows}))
            result = replay.replay_train_shape(root)
            self.assertEqual(result["train_drift_pairs"], 2)
            self.assertEqual(result["narrow_caret_shape_pairs"], 1)
            self.assertEqual(result["material_or_other_pairs_rejected"], 1)
            receipt = directory / "receipt.json"
            data = json.loads(receipt.read_text())
            data["split"] = "final_candidate"
            receipt.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "non-train"):
                replay.replay_train_shape(root)
