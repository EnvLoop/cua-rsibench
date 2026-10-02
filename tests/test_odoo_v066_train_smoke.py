"""Fail-closed checks for the proposed Odoo v0.6.6 train-only smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "enterprise_fallback/odoo18"))
from enterprise_fallback.odoo18 import smoke_v066_train as smoke  # noqa: E402
from enterprise_fallback.odoo18 import publish_v066_train_smoke as publisher  # noqa: E402


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class TrainPartitionGateTests(unittest.TestCase):
    def test_only_isolated_train_partition_and_bound_single_price_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker = Path(temporary) / "train"
            private = worker / "private"
            private.mkdir(parents=True)
            case = {"id": "TRAIN-ONE", "lines": [{
                "initial": {"qty": 5, "price": 16.0, "date": "2026-01-01"},
                "expected": {"qty": 5, "price": 14.0, "date": "2026-01-01"},
            }]}
            (private / "partition_cases.json").write_text(json.dumps({
                "cases": {"purchase": [case]},
            }))
            tasks = [{"task_id": "TRAIN-ONE", "package_sha256": "a" * 64}]
            tasks += [{"task_id": f"TRAIN-{i}", "package_sha256": "b" * 64}
                      for i in range(2, 21)]
            (private / "task_set_manifest.json").write_text(json.dumps({
                "train": tasks,
            }))
            with (patch.object(smoke, "HERE", worker),
                  patch.object(smoke, "PRIVATE", private),
                  patch.object(smoke, "local_config", return_value={
                      "ODOO_PARTITION": "train",
                  })):
                selected, package, _, _ = smoke._train_case()
                self.assertEqual(selected["id"], "TRAIN-ONE")
                self.assertEqual(package, "a" * 64)
            with (patch.object(smoke, "HERE", worker),
                  patch.object(smoke, "PRIVATE", private),
                  patch.object(smoke, "local_config", return_value={
                      "ODOO_PARTITION": "official_hidden",
                  })):
                with self.assertRaisesRegex(ValueError, "train worker"):
                    smoke._train_case()


class PublicReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "attempt"
        self.directory.mkdir(mode=0o700)
        observations = []
        actions = []
        kinds = ["type", "key", "click", "click", "double_click",
                 "key", "type", "key"]
        for step, kind in enumerate(kinds):
            raw = f"fake-frame-{step}".encode()
            frame_sha = digest(raw)
            frame_id_sha = digest(f"frame-{step}".encode())
            frame = self.directory / f"frame-{step:02d}.png"
            frame.write_bytes(raw)
            frame.chmod(0o600)
            observations.append({"step": step, "frame_sha256": frame_sha,
                                 "frame_id_sha256": frame_id_sha})
            actions.append({
                "step": step, "type": kind,
                "target_kind": None if kind == "key" or step == 6 else "coordinate",
                "pre_dispatch_frame_sha256": frame_sha,
                "public_contract_receipt": {
                    "screenshot": {"sha256": frame_sha},
                    "frame_id_sha256": frame_id_sha,
                    "action_profile": "scale-action-profile-v0.6.6",
                    "action_type": kind,
                },
            })
        self.row = {
            "schema": publisher.SCHEMA, "partition": "train_only",
            "model_calls": 0, "provider_calls": 0,
            "official_final_tasks_observed": 0,
            "action_profile": "scale-action-profile-v0.6.6",
            "minimal_output_version": "scale-action-output-v0.6.6",
            "pre_full_reset_exact": True, "post_full_reset_exact": True,
            "worker_services_restored_to_initial_state": True,
            "max_actions": 12, "wall_seconds": 420,
            "status": "passed", "failure_class": None,
            "independent_baseline_unsolved": True,
            "gui_price_persisted_after_reload": True,
            "independent_positive_reward_one": True,
            "independent_checks_passed": True,
            "independent_difference_codes": [],
            "observations": observations, "actions": actions,
            "source_sha256": {name: digest((ROOT / relative).read_bytes())
                              for name, relative in publisher.SOURCES.items()},
        }
        self.write()

    def write(self):
        path = self.directory / "receipt.json"
        path.write_text(json.dumps(self.row))
        path.chmod(0o600)

    def test_accepts_only_source_bound_frame_bound_restored_positive(self):
        report = publisher.aggregate([self.directory], ROOT)
        self.assertEqual(report["successful_attempt_validated_gui_actions"], 8)
        self.assertEqual(report["successful_attempt_independent_business_and_source_reward"], 1.0)

    def test_rejects_missing_exact_restore_and_provider_call(self):
        self.row["post_full_reset_exact"] = False
        self.write()
        with self.assertRaisesRegex(ValueError, "restore or scope"):
            publisher.aggregate([self.directory], ROOT)
        self.row["post_full_reset_exact"] = True
        self.row["provider_calls"] = 1
        self.write()
        with self.assertRaisesRegex(ValueError, "restore or scope"):
            publisher.aggregate([self.directory], ROOT)

    def test_rejects_changed_frame_and_source(self):
        frame = self.directory / "frame-00.png"
        frame.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Raw observed frame"):
            publisher.aggregate([self.directory], ROOT)
        frame.write_bytes(b"fake-frame-0")
        self.row["source_sha256"]["smoke"] = "0" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "source binding changed"):
            publisher.aggregate([self.directory], ROOT)


if __name__ == "__main__":
    unittest.main()
