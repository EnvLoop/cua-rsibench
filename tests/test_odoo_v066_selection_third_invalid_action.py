from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from tools import audit_odoo_v066_selection_third_invalid_action_v1 as incident


ROOT = Path(__file__).resolve().parents[1]


class ThirdRetainedAttemptTests(unittest.TestCase):
    def setUp(self):
        external = os.environ.get("ODOO_THIRD_SELECTION_EVIDENCE_ROOT")
        if not external:
            self.skipTest("private third Odoo selection attempt not supplied")
        self.external = Path(external)
        self.worker = (self.external /
            "enterprise_fallback/odoo18/partition_workers/selection")
        self.attempt = (self.worker /
            "private/v066_scale_controls/controls-20260929-pinned-border-01"
            "/attempt-000")

    def test_actual_failure_reopens_and_matches_field_limited_receipt(self):
        report = incident.audit(
            repo=ROOT, worker=self.worker,
            run_dir=self.attempt.parent,
            previous_run_dir=(self.worker / "private/v066_scale_controls/"
                              "controls-20260929-exact-return-01"),
            private_plan_path=(self.external / "work/odoo-original/"
                "v066-scale-controls-20260928/selection/"
                "plan-pinned-border-rfq-view-20260929.private.json"),
            public_plan_path=(ROOT / "docs/evidence/"
                "odoo-v066-selection-control-plan-pinned-border-rfq-view-2026-09-29.json"),
            source_freeze_path=(ROOT / "docs/evidence/"
                "odoo-v066-scale-pinned-border-rfq-view-source-freeze-2026-09-29.json"),
            previous_incident_public_path=(ROOT / "docs/evidence/"
                "odoo-v066-selection-second-post-intent-stale-2026-09-29.json"),
            verify_services=True)
        published = json.loads((ROOT / "docs/evidence/"
            "odoo-v066-selection-third-validator-mismatch-2026-09-29.json").read_text())
        self.assertEqual(report, published)
        self.assertTrue(report["base_v06_rejects_saved_double_click_invalid_action"])
        self.assertTrue(report["extended_v066_accepts_saved_double_click"])
        self.assertFalse(report["step_eight_mouse_action_dispatched"])

    def test_changed_saved_target_fails_without_private_mutation(self):
        original = json.loads((self.attempt /
            "actions/step-008-intent.private.json").read_text())
        original["normalized_action"]["target"] = {"x": 508, "y": 480}
        with self.assertRaisesRegex(
                incident.ThirdIncidentError,
                "third_step_eight_intended_action_changed"):
            incident._validation_boundary(self.attempt, original)


if __name__ == "__main__":
    unittest.main()
