"""Optional read-only integration checks for the preserved second train pilot."""

from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import v066_requalification_pilot as pilot
from tools import record_odoo_v066_train_gui_v1 as recorder


ROOT = Path(__file__).resolve().parents[1]


class PreservedSecondPilotTests(unittest.TestCase):
    def setUp(self):
        values = [os.environ.get(name) for name in (
            "ODOO_SECOND_PILOT_ATTEMPT", "ODOO_SECOND_PRIVATE_PLAN",
            "ODOO_SECOND_PILOT_BINDING")]
        if not all(values):
            self.skipTest("private second-pilot paths not supplied")
        self.attempt, self.private_plan, self.binding = map(Path, values)
        self.train_private = self.attempt.parent.parent
        self.workers_root = self.train_private.parent.parent
        self.public_plan = ROOT / "docs/evidence/odoo-v066-prospective-gui-requalification-post-restart-2026-09-28.json"
        self.pilot_public = ROOT / "docs/evidence/odoo-v066-second-train-pilot-2026-09-28.json"
        self.sft_public = ROOT / "docs/evidence/odoo-v066-second-train-pilot-sft-source-2026-09-28.json"

    def test_real_pilot_and_sft_public_receipts_rederive(self):
        pilot_result = pilot.audit_pilot(
            private_plan_path=self.private_plan,
            public_plan_path=self.public_plan,
            workers_root=self.workers_root,
            attempt_dir=self.attempt)
        self.assertEqual(pilot_result, json.loads(self.pilot_public.read_bytes()))
        self.assertEqual(pilot_result["independent_positive_reward"], 1.0)
        self.assertEqual(pilot_result["independent_negative_reward"], 0.0)
        self.assertEqual(pilot_result["official_final_tasks_admitted"], 0)
        sft_result = recorder.audit_sft_source(
            out_dir=self.attempt, binding_path=self.binding,
            pilot_audit_path=self.pilot_public)
        self.assertEqual(sft_result, json.loads(self.sft_public.read_bytes()))
        self.assertEqual(sft_result["datum_count"], 12)
        self.assertFalse(sft_result["tinker_training_started"])
        trace = json.loads((self.attempt / "gui_trace.json").read_bytes())
        self.assertEqual(len(trace["pre_intent_rejections"]), 2)
        self.assertEqual([json.loads((self.attempt / ref["path"]).read_bytes())["error_code"]
                          for ref in trace["pre_intent_rejections"]],
                         ["stale_frame", "stale_frame"])

    def test_changed_pilot_public_receipt_blocks_sft_without_private_mutation(self):
        original = recorder._json

        def changed(path, *, private=True):
            value = original(path, private=private)
            if Path(path) == self.pilot_public:
                value = dict(value)
                value["private_attempt_sha256"] = "0" * 64
            return value

        with patch.object(recorder, "_json", side_effect=changed):
            with self.assertRaisesRegex(
                    recorder.RecorderError,
                    "exact_sft_source_or_pilot_not_admitted"):
                recorder.audit_sft_source(
                    out_dir=self.attempt, binding_path=self.binding,
                    pilot_audit_path=self.pilot_public)


if __name__ == "__main__":
    unittest.main()
