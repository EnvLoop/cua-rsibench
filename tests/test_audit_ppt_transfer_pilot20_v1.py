"""Optional real-evidence replay for the train-only PPT transfer pilot."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.audit_ppt_transfer_pilot20_v1 import audit


ROOT = Path(__file__).resolve().parents[1]


class TransferPilotAuditTests(unittest.TestCase):
    def setUp(self):
        source = os.environ.get("PPT_TRANSFER_REBASE_EVIDENCE_ROOT")
        if not source:
            self.skipTest("owner-only transfer replay bundle not supplied")
        source = Path(source)
        self.args = {
            "private_root": ROOT / "work/office-transfer-ppt-pilot20-offline-20260929",
            "source_root": source / "replay-anchors/transfer-official-csv",
            "calibration_boundary": source / "boundary-v1/manifest.private.json",
            "original_v13_plan": source / "replay-anchors/active-v13-plan.private.json",
            "future_queue": source / "replay-anchors/future-reserve-queue.private.json",
            "historical_plan_dir": source / "replay-anchors/historical",
            "public_receipt": ROOT / "docs/evidence/office-ppt-transfer-pilot20-offline-2026-09-29.json",
        }

    def test_all_twenty_saved_artifacts_reopen_from_exact_sources(self):
        result = audit(**self.args)
        published = json.loads((ROOT / "docs/evidence/"
            "office-ppt-transfer-pilot20-independent-audit-2026-09-29.json").read_bytes())
        self.assertEqual(result, published)
        self.assertEqual(result["saved_artifact_and_near_miss_controls_passed"], 20)
        self.assertEqual(result["office_web_gui_admitted"], 0)
        self.assertFalse(result["visual_pdf_review_completed"])

    def test_overstated_public_gui_admission_is_rejected_before_artifact_loop(self):
        public = json.loads(self.args["public_receipt"].read_bytes())
        public["office_web_gui_admitted"] = 1
        with tempfile.TemporaryDirectory() as scratch:
            forged = Path(scratch) / "forged-public.json"
            forged.write_text(json.dumps(public))
            with self.assertRaisesRegex(
                    ValueError, "transfer_public_receipt_not_exact_or_overclaims"):
                audit(**{**self.args, "public_receipt": forged})


if __name__ == "__main__":
    unittest.main()
