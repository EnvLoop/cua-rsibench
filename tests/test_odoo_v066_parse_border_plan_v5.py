"""Offline fresh-nonce checks for a same-task Odoo v5 candidate epoch."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import odoo_v066_parse_border_plan_v5 as plan


def private_write(path: Path, value: dict | str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if isinstance(value, dict):
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


class ParsePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.worker = root / "selection"
        self.worker.mkdir(mode=0o700)
        private = self.worker / "private"
        private.mkdir(mode=0o700)
        private_write(self.worker / ".env", "ODOO_PARTITION=selection\n")
        self.prior = root / "prior.private.json"
        self.prior_public = root / "prior.public.json"
        self.old = root / "old.private.json"
        self.old_public = root / "old.public.json"
        private_write(self.prior, {
            "tasks": [{"task_id": "same-task"}],
            "current_candidate_private_sha256": "c" * 64,
            "run_nonce_hex": "1" * 32,
        })
        for path in (self.prior_public, self.old, self.old_public):
            private_write(path, {})
        self.nonce = "2" * 32
        self.run_dir = private / "v066_scale_controls" / \
            f"current-candidate-parse-v5-{self.nonce}"
        self.run_dir.mkdir(mode=0o700, parents=True)
        private_write(self.run_dir / "batch-intent.private.json", {
            "run_nonce_hex": self.nonce,
        })
        self.failure = {
            "status":
                "one_original_current_candidate_gui_failure_independently_verified_no_replay",
            "rejected_action_dispatched": False,
            "baseline_sql_and_full_filestore_restored_exact": True,
            "failure_receipt_sha256": "f" * 64,
            "preceding_gate_sha256": "g" * 64,
        }

    def mock_template(self, **kwargs):
        template = kwargs["nonce"]
        self.assertNotEqual(template, self.nonce)
        return ({"tasks": [{"task_id": "same-task"}],
                 "current_candidate_private_sha256": "c" * 64,
                 "run_nonce_hex": template,
                 "fresh_run_directory_name": "current-candidate-" + template},
                {"run_nonce_sha256": sha256(bytes.fromhex(template)).hexdigest()})

    def test_new_attempt_keeps_task_and_rebinds_nonce(self) -> None:
        with patch.object(plan.source, "validate"), \
             patch.object(plan.source, "digest", return_value="s" * 64), \
             patch.object(plan.prior_audit, "audit"), \
             patch.object(plan.failure_audit, "audit", return_value=self.failure), \
             patch.object(plan.prior_epoch, "build", side_effect=self.mock_template):
            private, public = plan.build(
                worker_dir=self.worker, historical_root=self.worker,
                prior_private_plan=self.prior,
                prior_public_plan=self.prior_public,
                old_private_plan=self.old,
                old_public_plan=self.old_public,
                nonce=self.nonce, allow_current_run=True)
        self.assertEqual(private["tasks"][0]["task_id"], "same-task")
        self.assertEqual(private["run_nonce_hex"], self.nonce)
        self.assertEqual(private["fresh_run_directory_name"],
                         self.run_dir.name)
        self.assertEqual(public["run_nonce_sha256"],
                         sha256(bytes.fromhex(self.nonce)).hexdigest())
        self.assertNotIn(self.nonce, json.dumps(public))

    def test_existing_v5_run_rejected_as_fresh_plan(self) -> None:
        with patch.object(plan.source, "validate"), \
             patch.object(plan.source, "digest", return_value="s" * 64), \
             patch.object(plan.prior_audit, "audit"), \
             patch.object(plan.failure_audit, "audit", return_value=self.failure), \
             patch.object(plan.prior_epoch, "build", side_effect=self.mock_template):
            with self.assertRaises(plan.ParsePlanError):
                plan.build(
                    worker_dir=self.worker, historical_root=self.worker,
                    prior_private_plan=self.prior,
                    prior_public_plan=self.prior_public,
                    old_private_plan=self.old,
                    old_public_plan=self.old_public,
                    nonce=self.nonce, allow_current_run=False)


if __name__ == "__main__":
    unittest.main()
