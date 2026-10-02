"""Tinker billing snapshots expose counts/hashes, never private attribution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from cursibench import full_study_tinker_billing_v1 as billing
from cursibench.full_study_tinker_preflight_v1 import PreflightError, sha256


ROOT = Path(__file__).resolve().parents[1]


class _Response:
    def __init__(self, data):
        self.data = data

    def model_dump_json(self):
        return json.dumps(self.data)


class _Rest:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get_billing_usage(self, start, end):
        self.calls.append((start, end))
        return _Future(_Response(self.data))


class _Future:
    def __init__(self, response):
        self.response = response

    def result(self, timeout):
        assert timeout in (30, 90)
        return self.response


class _Service:
    def __init__(self, data):
        self.rest = _Rest(data)
        self.events = []

    def create_rest_client(self):
        self.events.append("create_rest_client")
        return self.rest

    def close(self, status):
        self.events.append(("close", status))
        return _Future(None)


def _fixture(start: datetime, end: datetime) -> dict:
    return {
        "data": [{
            "bucket_start": start.isoformat().replace("+00:00", "Z"),
            "bucket_end": end.isoformat().replace("+00:00", "Z"),
            "base_model": "Qwen/Qwen3.8-27B",
            "session_id": "private-session-name",
            "user_name": "private-user-name",
            "event_info": {"type": "sampling_sample", "token_count": 42},
        }],
        "sessions": {"private-session-name": {
            "user_metadata": {"private_note": "must-not-be-published"}}},
    }


class BillingSnapshotTests(unittest.TestCase):
    def test_read_only_private_snapshot_and_public_projection(self):
        end = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0)
        start = end - timedelta(hours=1)
        service = _Service(_fixture(start, end))
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as scratch:
            out = Path(scratch) / "billing"
            receipt = billing.collect_read_only(
                ROOT, out, start=start, end=end,
                service_factory=lambda **_kwargs: service)
            self.assertEqual(service.events,
                             ["create_rest_client", ("close", "success")])
            self.assertEqual(service.rest.calls, [(start, end)])
            self.assertEqual(receipt["event_count"], 1)
            self.assertEqual(receipt["event_type_counts"],
                             {"sampling_sample": 1})
            self.assertEqual((out / "response.private.json").stat().st_mode
                             & 0o777, 0o600)
            raw = (out / "response.private.json").read_bytes()
            public = billing.public_summary(
                receipt, raw, private_receipt_sha256=sha256(
                    (out / "receipt.private.json").read_bytes()))
            self.assertEqual(public["event_count"], 1)
            self.assertIsNone(public["invoice_usd"])
            self.assertNotIn("private-session-name", json.dumps(public))
            self.assertNotIn("must-not-be-published", json.dumps(public))
            with self.assertRaisesRegex(PreflightError,
                                        "billing_private_receipt_not_publishable"):
                billing.public_summary(receipt, raw + b" ",
                                       private_receipt_sha256="a" * 64)

    def test_invalid_window_refuses_before_provider(self):
        now = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0)
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as scratch:
            with self.assertRaisesRegex(PreflightError,
                                        "billing_usage_window_invalid"):
                billing.collect_read_only(
                    ROOT, Path(scratch) / "billing",
                    start=now - timedelta(days=15), end=now,
                    service_factory=lambda **_kwargs: self.fail(
                        "provider called for invalid window"))

    def test_unknown_event_type_cannot_get_public_receipt(self):
        end = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0)
        start = end - timedelta(hours=1)
        data = _fixture(start, end)
        data["data"][0]["event_info"]["type"] = "unknown"
        with self.assertRaisesRegex(PreflightError,
                                    "billing_event_type_unknown"):
            billing._validate_response(json.dumps(data).encode(), start, end)


if __name__ == "__main__":
    unittest.main()
