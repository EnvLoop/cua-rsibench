"""Exact signed prefixes and strict suffixes for append-only Odoo leases."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import odoo_v066_retained_lease_prefix_v3 as lease
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


def row(event: str, operation: str, pid: int, second: int) -> dict:
    return {"event": event, "operation": operation, "pid": pid,
            "at_utc": f"2026-09-29T00:00:{second:02d}+00:00"}


def encode(rows: list[dict]) -> bytes:
    return b"".join((json.dumps(item, sort_keys=True) + "\n").encode()
                    for item in rows)


class HistoricalLeasePrefixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.events = self.private / "worker-lease-events.jsonl"
        self.intent = self.private / "intent.private.json"
        self.failure = self.private / "failure.private.json"
        self.rows = [
            row("acquired", "bootstrap", 11, 0),
            row("released", "bootstrap", 11, 1),
            row("acquired", controller.LEASE_OPERATION, 12, 2),
            row("released", controller.LEASE_OPERATION, 12, 6),
            row("acquired", "selection_baseline", 13, 7),
            row("released", "selection_baseline", 13, 8),
            row("acquired", controller.LEASE_OPERATION, 14, 9),
            row("released", controller.LEASE_OPERATION, 14, 12),
        ]
        self.original = encode(self.rows[:4])
        self.sha = sha256(self.original).hexdigest()
        protocol.write_new(self.intent, {
            "started_at_utc": "2026-09-29T00:00:03+00:00"
        }, private=True)
        protocol.write_new(self.failure, {"status": "failed"}, private=True)
        timestamp = datetime(2026, 9, 29, 0, 0, 5,
                             tzinfo=timezone.utc).timestamp()
        os.utime(self.failure, (timestamp, timestamp))
        self.write(encode(self.rows))

    def write(self, raw: bytes) -> None:
        self.events.write_bytes(raw)
        self.events.chmod(0o600)

    def inspect(self) -> dict:
        return lease.inspect_prefix(
            worker_private=self.private, published_sha256=self.sha,
            intent_path=self.intent, failure_path=self.failure)

    def test_exact_original_prefix_and_two_new_pairs(self) -> None:
        result = self.inspect()
        self.assertEqual(result["published_prefix_sha256"], self.sha)
        self.assertEqual(result["published_prefix_bytes"], len(self.original))
        self.assertEqual(result["published_prefix_rows"], 4)
        self.assertEqual(result["appended_complete_lease_pairs"], 2)
        self.assertEqual(result["current_full_log_sha256"],
                         sha256(self.events.read_bytes()).hexdigest())

    def test_tampered_historical_prefix_refuses(self) -> None:
        changed = list(self.rows)
        changed[0] = {**changed[0], "pid": 99}
        changed[1] = {**changed[1], "pid": 99}
        self.write(encode(changed))
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "published_prefix_changed"):
            self.inspect()

    def test_unpaired_appended_event_refuses(self) -> None:
        self.write(encode(self.rows[:-1]))
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "unpaired_rows"):
            self.inspect()

    def test_appended_wrong_pid_or_operation_refuses(self) -> None:
        changed = list(self.rows)
        changed[-1] = {**changed[-1], "pid": 88}
        self.write(encode(changed))
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "pair_or_order_invalid"):
            self.inspect()

    def test_appended_timestamp_reversal_refuses(self) -> None:
        changed = list(self.rows)
        changed[-1] = {**changed[-1], "at_utc":
                       "2026-09-29T00:00:08+00:00"}
        self.write(encode(changed))
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "pair_or_order_invalid"):
            self.inspect()

    def test_original_release_must_cover_failed_attempt(self) -> None:
        timestamp = datetime(2026, 9, 29, 0, 0, 7,
                             tzinfo=timezone.utc).timestamp()
        os.utime(self.failure, (timestamp, timestamp))
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "not_bound_to_attempt"):
            self.inspect()

    def test_noncanonical_or_truncated_suffix_refuses(self) -> None:
        self.write(self.original +
                   b'{"operation": "selection_baseline", "event": "acquired",'
                   b' "pid": 13, "at_utc": "2026-09-29T00:00:07+00:00"}\n'
                   + encode(self.rows[5:]))
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "noncanonical_row"):
            self.inspect()
        self.write(encode(self.rows)[:-1])
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "current_log_truncated"):
            self.inspect()

    def test_signed_prefix_must_end_at_original_release(self) -> None:
        self.sha = sha256(encode(self.rows[:2])).hexdigest()
        with self.assertRaisesRegex(lease.HistoricalLeaseError,
                                    "original_pair_not_at_prefix_end"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
