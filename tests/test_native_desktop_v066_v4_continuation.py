"""Offline safety checks for the source-bound 89-ID Desktop continuation."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_day_rollover_attrition_audit_v4 as audit
from native_desktop_factory import v066_day_rollover_continuation_v4 as v4
from native_desktop_factory import v066_day_rollover_durable_child_v4 as child
from tests.test_native_desktop_v066_caret_liveness_v4 import _png


def _ref(root: Path, name: str, data: bytes) -> dict:
    (root / name).write_bytes(data)
    return {"private_path": name, "bytes": len(data),
            "sha256": sha256(data).hexdigest()}


class RawFrameAuditTests(unittest.TestCase):
    def test_only_exact_cross_observation_caret_witness_passes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = _png(), _png(x=502)
            first = _ref(root, "observed.png", a)
            alternate = _ref(root, "alternate.png", b)
            attempt_dir = root / "synthetic-11/positive"
            attempt_dir.mkdir(parents=True)
            samples = [_ref(root, f"sample-{i}.png", b)
                       for i in range(6)]
            action_sha = sha256(b"synthetic-action").hexdigest()
            manifest_path = attempt_dir / "probe-step-00-00.json"
            manifest_path.write_text(json.dumps({
                "schema": "cua-native-wdi-v066-internal-caret-probe-private-v4",
                "status": "pending_exact_alternate",
                "step": 0, "frame_attempt": 0,
                "action_sha256": action_sha,
                "observed_sha256": sha256(a).hexdigest(),
                "sample_frames": samples,
                "sample_application_sha256s": [
                    audit.strict.prototype._application_sha(b)] * 6,
            }))
            manifest_path.chmod(0o600)
            receipt = {"physical_frame_resamples": [{
                "step": 0, "attempt": 0,
                "observed": first, "changed": alternate}],
                "actor_steps": [{"observation": first,
                                 "predispatch": alternate,
                                 "action_payload_sha256": action_sha}],
                "task_id": "synthetic-11", "attempt": "positive"}
            self.assertEqual(audit._guard_frames(root, receipt), 1)
            without_prior = {**receipt, "physical_frame_resamples": []}
            with self.assertRaises(ValueError):
                audit._guard_frames(root, without_prior)

    def test_material_drift_is_never_a_resample(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = _ref(root, "observed.png", _png())
            material = _ref(root, "material.png", _png(material=True))
            receipt = {"physical_frame_resamples": [{
                "step": 0, "attempt": 0,
                "observed": first, "changed": material}],
                "actor_steps": [{"observation": first,
                                 "predispatch": first}],
                "task_id": "synthetic-11", "attempt": "positive"}
            with self.assertRaisesRegex(ValueError, "material drift"):
                audit._guard_frames(root, receipt)


class RootOwnedPlanTests(unittest.TestCase):
    def test_offline_plan_selects_only_next_untouched_ids(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {"attempts_root": root / "v066-final-gui",
                     "old_original_root": root / "old-a/v066-final-gui",
                     "old_caret_root": root / "old-b/v066-final-gui",
                     "old_failed_scoped_root": root / "old-c/v066-final-gui"}
            rows = [{"task_id": f"synthetic-{i}"} for i in range(100)]
            progress = {"v4_new_complete_trios": 0,
                        "independently_accepted_complete_trios": 8,
                        "four_root_full_lease_intents_charged": 55}
            with patch.object(v4, "validate_live", return_value=(
                    {}, progress, paths, rows)), patch.object(
                    v4, "combined_budget", return_value={
                        "combined_full_lease_intents": 61}):
                plan = v4.run_batch(freeze=root / "unused", run_dir=root / "unused",
                                    max_new_ids=2, execute=False)
                self.assertEqual(plan["new_ids_selected"], 2)
                self.assertEqual(plan["projected_four_root_full_lease_intents"], 61)
                self.assertEqual(plan["official_final_admissions"], 0)
                for forbidden in (0, 3):
                    with self.assertRaises(ValueError):
                        v4.run_batch(freeze=root / "unused",
                                     run_dir=root / "unused",
                                     max_new_ids=forbidden, execute=False)

    def test_child_refuses_unfrozen_direct_dispatch(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            child._precreate_gate()

    def test_child_binds_exact_fsynced_budget_before_create(self):
        budget = {
            "schema": "cua-native-wdi-v066-precreate-budget-private-v3",
            "status": "fsynced_before_provider_create",
            "task_id": "synthetic-11", "attempt": "positive",
            "provider_active_before_intent": 0,
            "storage_dispatch_ready": True, "credential_present": True,
            "sdk_versions": {"e2b-desktop": "2.2.0", "e2b": "2.51.0",
                             "Pillow": "11.3.0"},
            "power": {"source": "Battery Power"},
        }
        budget_raw = json.dumps(budget).encode()
        intent = {
            "schema": "cua-native-wdi-v066-final-control-intent-v1",
            "status": "recorded_before_provider_create",
            "task_id": "synthetic-11", "attempt": "positive",
            "lease_seconds": 600,
            "precreate_budget_sha256": sha256(budget_raw).hexdigest(),
            "durable_child_wrapper_sha256": "a" * 64,
        }
        intent_raw = json.dumps(intent).encode()
        child._verify_precreate_receipts(
            task_id="synthetic-11", attempt="positive",
            wrapper_sha="a" * 64,
            intent_raw=intent_raw, budget_raw=budget_raw)
        with self.assertRaisesRegex(ValueError, "budget or intent"):
            child._verify_precreate_receipts(
                task_id="synthetic-11", attempt="positive",
                wrapper_sha="a" * 64,
                intent_raw=intent_raw,
                budget_raw=json.dumps({**budget,
                                       "provider_active_before_intent": 1}).encode())
        with self.assertRaisesRegex(ValueError, "budget or intent"):
            child._verify_precreate_receipts(
                task_id="synthetic-11", attempt="positive",
                wrapper_sha="a" * 64,
                intent_raw=json.dumps({**intent,
                                       "lease_seconds": 601}).encode(),
                budget_raw=budget_raw)

    def test_child_enforces_selected_id_and_attempt_order(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            run = {"selected_private_task_ids": ["synthetic-11", "synthetic-12"],
                   "task_outcomes": []}
            child._verify_batch_order(run=run, root=root,
                                      task_id="synthetic-11", attempt="positive")
            with self.assertRaisesRegex(ValueError, "next root-owned"):
                child._verify_batch_order(run=run, root=root,
                                          task_id="synthetic-12", attempt="positive")
            with self.assertRaisesRegex(ValueError, "completed prior"):
                child._verify_batch_order(run=run, root=root,
                                          task_id="synthetic-11", attempt="near-miss")
            prior = root / "synthetic-11/positive"
            prior.mkdir(parents=True)
            (prior / "receipt.json").write_text(json.dumps({
                "task_id": "synthetic-11", "attempt": "positive",
                "status": "control_passed", "is_running_after_kill": False}))
            child._verify_batch_order(run=run, root=root,
                                      task_id="synthetic-11", attempt="near-miss")
            run["task_outcomes"] = [{"private_task_id": "synthetic-11",
                                      "status": "provisional_trio_complete"}]
            child._verify_batch_order(run=run, root=root,
                                      task_id="synthetic-12", attempt="positive")

    def test_child_refuses_partial_or_skipped_roster_id(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            candidate.mkdir()
            raw = json.dumps({"tasks": [
                {"split": "final_candidate", "task_id": f"synthetic-{i}"}
                for i in range(100)]}).encode()
            (candidate / "candidate-inventory.json").write_bytes(raw)
            frozen = {"candidate_inventory_sha256": sha256(raw).hexdigest()}
            run = {"selected_private_task_ids": ["synthetic-11", "synthetic-12"]}
            child._verify_untouched_roster(
                frozen=frozen, run=run, root=root / "attempts",
                candidate_root=candidate)
            with self.assertRaisesRegex(ValueError, "partial, reused, or skipped"):
                child._verify_untouched_roster(
                    frozen=frozen,
                    run={"selected_private_task_ids": ["synthetic-10"]},
                    root=root / "attempts", candidate_root=candidate)
            with self.assertRaisesRegex(ValueError, "incomplete earlier"):
                child._verify_untouched_roster(
                    frozen=frozen,
                    run={"selected_private_task_ids": ["synthetic-12"]},
                    root=root / "attempts", candidate_root=candidate)


if __name__ == "__main__":
    unittest.main()
