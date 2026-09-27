"""Current v0.6.6 preflight must not inherit historical v0.6.5 claims."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from cursibench import full_study_tinker_preflight_v066 as preflight
from cursibench import shared_action_bundle_v066 as bundle
from cursibench.full_study_tinker_preflight_v1 import sha256
from tests.test_full_study_tinker_preflight_v1 import FakeService, MODEL_ROW


ROOT = Path(__file__).resolve().parents[1]


class CurrentTinkerPreflightTests(unittest.TestCase):
    def test_read_only_current_bundle_and_sanitized_public_projection(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as scratch:
            output = Path(scratch) / "current-preflight"
            service = FakeService()
            receipt = preflight.run_read_only(
                ROOT, output,
                fetcher=lambda _url: json.dumps([MODEL_ROW]).encode(),
                service_factory=lambda **_kwargs: service)
            self.assertEqual(receipt["action_bundle"], bundle.build(ROOT))
            self.assertEqual(receipt["action_bundle"]["output_version"],
                             "scale-action-output-v0.6.6")
            self.assertEqual(receipt["training_or_sampling_provider_calls"], 0)
            self.assertFalse(receipt["campaign_dispatch_authorized"])
            self.assertFalse(receipt["six_cell_ratification_verified"])
            self.assertEqual(service.calls,
                             ["get_server_capabilities", ("close", "success")])
            private = output / "receipt.private.json"
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            summary = preflight.public_summary(
                ROOT, receipt, private_receipt_sha256=sha256(private.read_bytes()))
            self.assertEqual(summary["six_cell_action_bundle_sha256"],
                             receipt["action_bundle"]["bundle_sha256"])
            self.assertNotIn("user_metadata", json.dumps(summary))
            self.assertEqual(summary["official_final_results"], 0)

    def test_success_claim_or_changed_bundle_cannot_be_published(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as scratch:
            receipt = preflight.run_read_only(
                ROOT, Path(scratch) / "current-preflight",
                fetcher=lambda _url: json.dumps([MODEL_ROW]).encode(),
                service_factory=lambda **_kwargs: FakeService())
            forged = dict(receipt)
            forged["campaign_dispatch_authorized"] = True
            with self.assertRaisesRegex(ValueError,
                                        "v066_preflight_receipt_not_publishable"):
                preflight.public_summary(
                    ROOT, forged, private_receipt_sha256="a" * 64)
            forged = dict(receipt)
            forged["training_or_sampling_provider_calls"] = 1
            with self.assertRaisesRegex(ValueError,
                                        "v066_preflight_receipt_not_publishable"):
                preflight.public_summary(
                    ROOT, forged, private_receipt_sha256="a" * 64)
            forged = dict(receipt)
            forged["action_bundle"] = dict(receipt["action_bundle"])
            forged["action_bundle"]["bundle_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError,
                                        "shared_action_bundle_source_or_field_mismatch"):
                preflight.public_summary(
                    ROOT, forged, private_receipt_sha256="a" * 64)
            with self.assertRaisesRegex(ValueError,
                                        "private_receipt_sha256_invalid"):
                preflight.public_summary(ROOT, receipt,
                                         private_receipt_sha256="not-a-hash")


if __name__ == "__main__":
    unittest.main()
