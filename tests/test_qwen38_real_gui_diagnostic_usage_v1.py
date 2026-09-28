"""Provider billing attribution is tested without contacting Tinker."""

from __future__ import annotations

import json
import unittest

from cursibench import qwen38_real_gui_diagnostic_usage_v1 as usage


def raw(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


class DiagnosticUsageTests(unittest.TestCase):
    def setUp(self):
        self.plan = "a" * 64
        self.pricing = raw([{
            "tinker_id": "Qwen/Qwen3.8-27B", "type": "Vision model",
            "train": "$4", "prefill": "$2", "cached_prefill": "$1",
            "sample": "$6"}])
        self.events = {
            "sessions": {
                "matched": {"user_metadata": {
                    "purpose": "envloop-real-gui-diagnostic-v1",
                    "run_id": self.plan[:16], "split": "train"}},
                "other": {"user_metadata": {
                    "purpose": "other", "run_id": self.plan[:16],
                    "split": "train"}},
            },
            "data": [
                self.event("matched", "training", 1000, "0.004"),
                self.event("matched", "sampling_prefill", 500, "0.001",
                           cached=False),
                self.event("matched", "sampling_sample", 100, "0.0006"),
                self.event("matched", "checkpoint", None, "0.0002"),
                self.event("other", "training", 2000, "0.008"),
            ],
        }

    def event(self, session, kind, count, estimate, **fields):
        return {
            "session_id": session,
            "bucket_start": "2026-09-28T00:00:00Z",
            "bucket_end": "2026-09-28T01:00:00Z",
            "base_model": "Qwen/Qwen3.8-27B",
            "event_info": {"type": kind, "token_count": count, **fields},
            "estimated_cost_usd": estimate,
        }

    def audit(self):
        return usage.audit(
            usage_raw=raw(self.events), pricing_raw=self.pricing,
            plan_sha256=self.plan,
            window_start="2026-09-28T00:00:00Z",
            window_end="2026-09-28T02:00:00Z")

    def test_provider_tokens_and_estimate_are_attributed_not_invoiced(self):
        result = self.audit()
        self.assertEqual(result["matched_provider_event_count"], 4)
        self.assertEqual(result["unpriced_checkpoint_or_storage_event_count"], 1)
        self.assertEqual(result["provider_reported_billed_tokens"]["training"],
                         1000)
        self.assertEqual(result["nominal_token_rate_subtotal_usd"],
                         "0.0056")
        self.assertEqual(result[
            "provider_reported_estimated_cost_subtotal_usd"], "0.0058")
        self.assertIsNone(result["provider_invoice_usd"])
        self.assertIsNone(result["benchmark_score"])
        self.assertNotIn('"session_id"', json.dumps(result))

    def test_missing_matched_session_cannot_look_like_zero_cost(self):
        self.events["sessions"]["matched"]["user_metadata"]["run_id"] = \
            "f" * 16
        with self.assertRaisesRegex(usage.UsageError,
                                    "no_attributed_provider_events"):
            self.audit()

    def test_wrong_model_or_window_is_rejected(self):
        self.events["data"][0]["base_model"] = "other"
        with self.assertRaisesRegex(usage.UsageError,
                                    "matched_model_changed"):
            self.audit()
        self.events["data"][0]["base_model"] = "Qwen/Qwen3.8-27B"
        self.events["data"][0]["bucket_start"] = "2026-09-27T23:00:00Z"
        with self.assertRaisesRegex(usage.UsageError,
                                    "outside_window"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
