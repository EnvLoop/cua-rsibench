"""Read-only checks for the public Odoo train post-reconcile receipt."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_train_post_reclassification_v1 as receipt


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(receipt.canonical(value))
    path.chmod(0o600)


class SavedJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = Path(self.temp.name) / "journal.private.jsonl"
        self.task = {"task_id": "synthetic-private-id",
                     "package_sha256": "a" * 64}
        self.attempt_sha = "b" * 64
        self.authority_sha = "c" * 64
        previous = "0" * 64
        self.rows = []
        for sequence, event in enumerate(receipt.EVENTS):
            row = {"schema":
                   "envloop-odoo-v066-scale-control-journal-event-v1",
                   "sequence": sequence, "previous_sha256": previous,
                   "event": event, "ordinal": 0,
                   "task_id": self.task["task_id"],
                   "package_sha256": self.task["package_sha256"],
                   "attempt_dir": "attempt-000"}
            if sequence == 2:
                row["authority_sha256"] = self.authority_sha
                row["attempt_receipt_sha256"] = self.attempt_sha
            row["row_sha256"] = receipt.digest(receipt.canonical(row))
            self.rows.append(row)
            previous = row["row_sha256"]
        self.old_raw = b"".join(receipt.canonical(row)
                                for row in self.rows[:2])
        self.journal.write_bytes(self.old_raw + receipt.canonical(self.rows[2]))
        self.journal.chmod(0o600)

    def check(self):
        return receipt._journal(
            self.journal, old_journal_sha=receipt.digest(self.old_raw),
            old_tail_sha=self.rows[1]["row_sha256"], task=self.task,
            attempt_sha=self.attempt_sha, authority_sha=self.authority_sha)

    def test_retained_failure_and_append_only_reclassification(self):
        journal_sha, tail = self.check()
        self.assertEqual(journal_sha, receipt.digest(self.journal.read_bytes()))
        self.assertEqual(tail, self.rows[2]["row_sha256"])

    def test_changed_old_failure_or_extra_event_rejected(self):
        changed = dict(self.rows[1], event="case_completed")
        self.journal.write_bytes(receipt.canonical(self.rows[0]) +
                                 receipt.canonical(changed) +
                                 receipt.canonical(self.rows[2]))
        with self.assertRaisesRegex(receipt.ReclassificationAuditError,
                                    "retained_old_journal_changed"):
            self.check()
        self.journal.write_bytes(self.old_raw +
                                 receipt.canonical(self.rows[2]) +
                                 receipt.canonical(self.rows[2]))
        with self.assertRaisesRegex(receipt.ReclassificationAuditError,
                                    "journal_event_count_invalid"):
            self.check()

    def test_hash_valid_but_wrong_authority_rejected(self):
        row = dict(self.rows[2], authority_sha256="d" * 64)
        row.pop("row_sha256")
        row["row_sha256"] = receipt.digest(receipt.canonical(row))
        self.journal.write_bytes(self.old_raw + receipt.canonical(row))
        with self.assertRaisesRegex(receipt.ReclassificationAuditError,
                                    "journal_reclassification_unbound"):
            self.check()


class SavedBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.private = self.root / "private"
        self.run.mkdir(mode=0o700)
        self.private.mkdir(mode=0o700)
        self.sql = self.run / "current-baseline-sql.private.json"
        self.files = self.run / "current-baseline-filestore.private.json"
        self.frozen_sql = self.private / "baseline_snapshot.json"
        self.frozen_files = self.private / "baseline-filestore-manifest.json"
        write(self.sql, {"rows": [1]})
        write(self.files, {"all_files": ["a", "b"]})
        write(self.frozen_sql, {"rows": [1]})
        write(self.frozen_files, {"all_files": ["a", "b"]})
        self.check = {"schema": "envloop-odoo-v066-current-baseline-check-v1",
                      "status":
                      "current_sql_and_full_filestore_equal_frozen_baseline",
                      "sql_snapshot_sha256": receipt.digest(self.sql.read_bytes()),
                      "filestore_manifest_sha256":
                      receipt.digest(self.files.read_bytes()),
                      "frozen_sql_baseline_sha256":
                      receipt.digest(self.frozen_sql.read_bytes()),
                      "frozen_filestore_manifest_sha256":
                      receipt.digest(self.frozen_files.read_bytes()),
                      "original_service_state_restored": True,
                      "current_baseline_checked_after_old_lease_release": True,
                      "official_final_tasks_admitted": 0}
        self.check_path = self.run / "current-baseline-check.private.json"
        write(self.check_path, self.check)
        self.checkpoint = {
            "baseline_snapshot_sha256":
                receipt.digest(self.frozen_sql.read_bytes()),
            "baseline_filestore_manifest_sha256":
                receipt.digest(self.frozen_files.read_bytes())}

    def test_saved_full_baseline_matches_frozen_snapshot(self):
        self.assertEqual(receipt._baseline(
            self.run, self.private, self.checkpoint),
            receipt.digest(self.check_path.read_bytes()))

    def test_hash_valid_different_filestore_or_unrestored_service_rejected(self):
        write(self.files, {"all_files": ["a"]})
        self.check["filestore_manifest_sha256"] = (
            receipt.digest(self.files.read_bytes()))
        write(self.check_path, self.check)
        with self.assertRaisesRegex(receipt.ReclassificationAuditError,
                                    "current_baseline_not_bound_or_exact"):
            receipt._baseline(self.run, self.private, self.checkpoint)
        write(self.files, {"all_files": ["a", "b"]})
        self.check["filestore_manifest_sha256"] = (
            receipt.digest(self.files.read_bytes()))
        self.check["original_service_state_restored"] = False
        write(self.check_path, self.check)
        with self.assertRaisesRegex(receipt.ReclassificationAuditError,
                                    "current_baseline_not_bound_or_exact"):
            receipt._baseline(self.run, self.private, self.checkpoint)


class PreservedReconcileTests(unittest.TestCase):
    def setUp(self):
        value = os.environ.get("ODOO_POST_RECLASS_EVIDENCE_ROOT")
        if not value:
            self.skipTest("preserved private Odoo reconcile root not supplied")
        root = Path(value)
        work = root / "work/odoo-original/v066-scale-controls-20260928"
        private = (root / "enterprise_fallback/odoo18/partition_workers"
                   / "train/private")
        repo = Path(__file__).resolve().parents[1]
        self.old_plan = work / "train/plan-current.private.json"
        self.args = {
            "run_dir": private / "v066_scale_controls/controls-20260928-v1",
            "worker_private": private,
            "old_private_plan": self.old_plan,
            "new_private_plan": work / "train/plan-lease-amended.private.json",
            "adoption_private": work / "lease-timing-adoption.private.json",
            "incident_private": work / "incident-20260928.private.json",
            "incident_public": repo / "docs/evidence/odoo-v066-scale-first-train-inline-lease-incident-2026-09-28.json",
            "old_source_freeze": repo / "docs/evidence/odoo-v066-scale-control-source-freeze-2026-09-28.json",
            "new_source_freeze": repo / "docs/evidence/odoo-v066-scale-control-lease-amended-source-freeze-2026-09-28.json",
        }

    def test_real_hashes_and_public_field_limit(self):
        result = receipt.audit(**self.args)
        self.assertEqual(result["current_baseline_check_sha256"],
                         "2a56f99084b14cf81f115582417a5cd00a8a32bb7920d7c866a1f4acca82c45c")
        self.assertEqual(result["journal_tail_sha256"],
                         "32bff23be060984a6a3e9b11ab13d295df5cade68e22c11855592cb99224839a")
        self.assertEqual(result["official_final_tasks_admitted"], 0)
        self.assertFalse(result["original_gui_attempt_replayed"])
        public_text = json.dumps(result, sort_keys=True)
        private_task_id = json.loads(self.old_plan.read_bytes())["tasks"][0]["task_id"]
        self.assertNotIn(private_task_id, public_text)
        self.assertNotIn(str(self.args["run_dir"]), public_text)
        self.assertEqual(set(result), {
            "schema", "status", "split", "completed_raw_case_count",
            "current_sql_equal_frozen_baseline",
            "current_full_physical_filestore_equal_frozen_baseline",
            "original_service_state_restored",
            "original_case_failed_event_retained", "original_gui_attempt_replayed",
            "saved_attempt_positive_reward", "saved_attempt_wrong_object_reward",
            "saved_attempt_full_reset_exact", "source_visual_review_pending",
            "old_source_revision", "corrected_source_revision",
            "old_source_freeze_sha256", "corrected_source_freeze_sha256",
            "old_private_plan_sha256", "corrected_private_plan_sha256",
            "incident_public_sha256", "private_adoption_sha256",
            "old_attempt_sha256", "current_baseline_check_sha256",
            "private_reclassification_authority_sha256", "journal_sha256",
            "journal_tail_sha256", "official_final_tasks_admitted", "model_attempts"})

    def test_changed_saved_check_is_rejected_without_private_mutation(self):
        original = receipt._json
        target = self.args["run_dir"] / "current-baseline-check.private.json"

        def changed(path, *, private=True):
            value = original(path, private=private)
            if Path(path) == target:
                return dict(value, original_service_state_restored=False)
            return value

        with patch.object(receipt, "_json", side_effect=changed):
            with self.assertRaisesRegex(receipt.ReclassificationAuditError,
                                        "current_baseline_not_bound_or_exact"):
                receipt.audit(**self.args)


if __name__ == "__main__":
    unittest.main()
