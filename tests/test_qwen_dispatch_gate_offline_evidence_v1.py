"""Receipt audit only; the publisher's focused suite runs separately."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_qwen_dispatch_gate_offline_v1 as evidence  # noqa: E402


class DispatchGateEvidenceTests(unittest.TestCase):
    def test_committed_receipt_binds_current_sources_and_public_toy(self):
        receipt = json.loads(evidence.OUTPUT.read_bytes())
        checked = evidence.audit_receipt(receipt)
        self.assertEqual(checked["focused_fake_provider_tests_passed"], 44)
        self.assertEqual(checked["real_provider_calls_by_builder"], 0)
        self.assertEqual(checked["real_researcher_campaigns"], 0)
        self.assertEqual(checked["official_final_model_outcomes"], 0)
        self.assertIsNone(checked["benchmark_score"])

    def test_claimed_live_result_or_source_drift_is_rejected(self):
        receipt = evidence.expected_receipt(focused_test_count=44)
        receipt["real_researcher_campaigns"] = 1
        with self.assertRaises(evidence.EvidenceError):
            evidence.audit_receipt(receipt)
        receipt = evidence.expected_receipt(focused_test_count=44)
        first = evidence.SOURCE_PATHS[0]
        receipt["source_sha256s"][first] = "0" * 64
        with self.assertRaises(evidence.EvidenceError):
            evidence.audit_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
