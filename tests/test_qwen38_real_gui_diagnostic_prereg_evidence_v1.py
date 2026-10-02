"""Field-limited public prereg receipt cannot invent a paid result."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_qwen38_real_gui_diagnostic_prereg_v1 as evidence  # noqa: E402


class PreregEvidenceTests(unittest.TestCase):
    def test_receipt_binds_current_source_and_stays_blocked(self):
        receipt = json.loads(evidence.OUTPUT.read_bytes())
        checked = evidence.audit_receipt(receipt)
        self.assertEqual(checked["validated_train_source_tasks"], 1)
        self.assertEqual(checked["required_distinct_train_tasks"], 3)
        self.assertEqual(checked["optimizer_steps_preregistered"], 64)
        self.assertFalse(checked["pricing_quote_is_dispatch_gate"])
        self.assertTrue(checked["provider_invoice_required_for_cost_claim"])
        self.assertEqual(checked["paid_tinker_calls"], 0)
        self.assertEqual(checked["official_model_outcomes"], 0)
        self.assertIsNone(checked["benchmark_score"])

    def test_invented_call_or_changed_source_binding_is_rejected(self):
        for field, fake in (
            ("paid_tinker_calls", 1),
            ("source_manifest_sha256", "0" * 64),
            ("ratification_sha256", "0" * 64),
        ):
            receipt = evidence.expected_receipt()
            receipt[field] = fake
            with self.assertRaises(evidence.diagnostic.DiagnosticError):
                evidence.audit_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
