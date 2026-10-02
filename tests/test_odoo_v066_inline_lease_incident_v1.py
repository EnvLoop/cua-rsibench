"""Read-only evidence/tamper tests for the preserved inline-lease incident."""

from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_inline_lease_incident_v1 as incident


ROOT = Path(__file__).resolve().parents[1]


class PreservedInlineLeaseIncidentTests(unittest.TestCase):
    def setUp(self):
        values = [os.environ.get(name) for name in (
            "ODOO_SCALE_OLD_RUN", "ODOO_SCALE_TRAIN_PRIVATE",
            "ODOO_SCALE_OLD_PRIVATE_PLAN")]
        if not all(values):
            self.skipTest("preserved private scale paths not supplied")
        self.run_dir, self.train_private, self.old_plan = map(Path, values)
        self.args = {
            "repo": ROOT,
            "run_dir": self.run_dir,
            "worker_private": self.train_private,
            "old_private_plan": self.old_plan,
            "old_public_plan": ROOT / "docs/evidence/odoo-v066-train-control-plan-2026-09-28.json",
            "old_source_freeze": ROOT / "docs/evidence/odoo-v066-scale-control-source-freeze-2026-09-28.json",
        }

    def test_saved_actor_state_passes_only_after_lease_release(self):
        private, public = incident.audit(**self.args)
        recorded = json.loads((ROOT / "docs/evidence/odoo-v066-scale-first-train-inline-lease-incident-2026-09-28.json").read_bytes())
        self.assertEqual(public, recorded)
        self.assertEqual(public["saved_actor_positive_reward"], 1.0)
        self.assertEqual(public["saved_wrong_object_reward"], 0.0)
        self.assertFalse(public["current_live_sql_and_full_filestore_baseline_queried"])
        self.assertFalse(public["reclassification_authorized"])
        self.assertEqual(private["failed_journal_rows_retained"], 2)
        self.assertTrue(public["original_case_failed_journal_row_retained"])
        self.assertNotIn(private["task_id"], json.dumps(public))

    def test_old_frozen_source_tamper_rejected_without_docker(self):
        original = incident.old_blob

        def changed(repo, relative):
            result = original(repo, relative)
            return result + b"changed" if relative.endswith("scale_controller_v1.py") else result

        with patch.object(incident, "old_blob", side_effect=changed):
            with self.assertRaisesRegex(incident.IncidentAuditError,
                                        "old_frozen_source_blob_changed"):
                incident.audit(**self.args)

    def test_retained_journal_failure_is_required(self):
        original = incident.controller.read_journal

        def changed(path):
            rows, tail, count = original(path)
            rows = [dict(row) for row in rows]
            rows[-1]["event"] = "case_completed"
            return rows, tail, count

        with patch.object(incident.controller, "read_journal", side_effect=changed):
            with self.assertRaisesRegex(incident.IncidentAuditError,
                                        "old_failure_journal_not_preserved"):
                incident.audit(**self.args)


if __name__ == "__main__":
    unittest.main()
