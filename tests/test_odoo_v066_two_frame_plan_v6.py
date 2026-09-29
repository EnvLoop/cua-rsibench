"""Offline fresh-epoch and private-freeze checks for Odoo v6."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import odoo_v066_two_frame_plan_v6 as plan


def private_write(path: Path, value: dict | str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, dict) else value)
    path.chmod(0o600)


class TwoFramePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.worker = root / "selection"
        self.worker.mkdir(mode=0o700)
        (self.worker / "private").mkdir(mode=0o700)
        private_write(self.worker / ".env", "ODOO_PARTITION=selection\n")
        self.prior_path = root / "prior.private.json"
        self.public_path = root / "prior.public.json"
        self.freeze_path = root / "source.private.json"
        self.prior = {
            "tasks": [{"task_id": "same-task"}],
            "run_nonce_hex": "1" * 32,
            "fresh_run_directory_name": "current-candidate-v5",
            "current_candidate_private_sha256": "c" * 64,
            "physical_dispatch_profile": "prior-v5",
        }
        self.prior_public = {"candidate_count": 20}
        self.incident = {
            "failure_receipt_sha256": "f" * 64,
            "prior_no_gui_gate_sha256": "g" * 64,
            "worker_lease_prefix_sha256": "l" * 64,
        }
        private_write(self.prior_path, self.prior)
        private_write(self.public_path, self.prior_public)
        private_write(self.freeze_path, {})
        self.nonce = "2" * 32
        self.real_digest = plan.digest

    def fake_digest(self, path: Path) -> str:
        if path == plan.source.FREEZE:
            return "s" * 64
        return self.real_digest(path)

    def build(self, *, allow_current_run: bool = False):
        with patch.object(plan, "audit_private_freeze",
                          return_value={"official_final_tasks_admitted": 0}), \
             patch.object(plan, "_prior", return_value=(
                 self.prior, self.prior_public, self.incident, "f" * 64)), \
             patch.object(plan, "digest", side_effect=self.fake_digest):
            return plan.build(
                worker_dir=self.worker,
                prior_private_plan=self.prior_path,
                prior_public_plan=self.public_path,
                private_freeze=self.freeze_path,
                nonce=self.nonce,
                allow_current_run=allow_current_run)

    def test_private_plan_keeps_task_but_uses_new_nonce_and_profile(self) -> None:
        private, public = self.build()
        self.assertEqual(private["tasks"][0]["task_id"], "same-task")
        self.assertNotEqual(private["run_nonce_hex"], self.prior["run_nonce_hex"])
        self.assertEqual(private["physical_dispatch_profile"], plan.PROFILE)
        self.assertEqual(public["run_nonce_sha256"],
                         sha256(bytes.fromhex(self.nonce)).hexdigest())
        self.assertNotIn("same-task", json.dumps(public))
        self.assertNotIn(self.nonce, json.dumps(public))

    def test_existing_attempt_requires_audit_mode(self) -> None:
        run = (self.worker / "private/v066_scale_controls" /
               f"current-candidate-two-frame-v6-{self.nonce}")
        run.mkdir(mode=0o700, parents=True)
        private_write(run / "batch-intent.private.json",
                      {"run_nonce_hex": self.nonce})
        with self.assertRaises(plan.TwoFramePlanError):
            self.build()
        private, _ = self.build(allow_current_run=True)
        self.assertEqual(private["fresh_run_directory_name"], run.name)

    def test_private_source_freeze_binds_prior_failure(self) -> None:
        with patch.object(plan.source, "validate"), \
             patch.object(plan, "_prior", return_value=(
                 self.prior, self.prior_public, self.incident, "f" * 64)), \
             patch.object(plan, "digest", side_effect=self.fake_digest):
            value = plan.build_private_freeze(
                worker_dir=self.worker,
                prior_private_plan=self.prior_path,
                prior_public_plan=self.public_path)
        self.assertEqual(value["prior_v5_terminal_failure_receipt_sha256"],
                         "f" * 64)
        self.assertFalse(value["campaign_dispatch_authorized"])
        self.assertEqual(value["official_final_tasks_admitted"], 0)


if __name__ == "__main__":
    unittest.main()
