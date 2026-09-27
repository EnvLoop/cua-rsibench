"""GitLab per-ID failures are durable, ordered, and never model scores."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gitlab_world import failure_ledger


class GitLabFailureLedgerTests(unittest.TestCase):
    def test_append_only_chain_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private" / "failures.jsonl"
            with patch.object(failure_ledger, "PATH", path):
                first = failure_ledger.append(
                    task_id="private-1", source_family_sha256="a" * 64,
                    attempt_number=1, status="development_gui_trio_failed",
                    scores=[1.0, 0.0, 0.0], error_type=None,
                    cold_reset_verified=True)
                second = failure_ledger.append(
                    task_id="private-1", source_family_sha256="a" * 64,
                    attempt_number=2, status="driver_or_environment_failed",
                    scores=None, error_type="TimeoutError",
                    cold_reset_verified=True)
                self.assertEqual((first["entry_seq"], second["entry_seq"]), (1, 2))
                public = failure_ledger.audit()
                self.assertEqual(public["entry_count"], 2)
                self.assertEqual(public["head_sha256"], second["entry_sha256"])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                raw = path.read_text()
                path.write_text(raw.replace("TimeoutError", "FakeError"))
                with self.assertRaises(RuntimeError):
                    failure_ledger.audit()

    def test_unscored_failure_requires_bounded_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(failure_ledger, "PATH", Path(tmp) / "ledger"):
                with self.assertRaises(ValueError):
                    failure_ledger.append(
                        task_id="private", source_family_sha256="short",
                        attempt_number=1, status="driver_or_environment_failed",
                        scores=None, error_type="TimeoutError",
                        cold_reset_verified=False)
                self.assertEqual(failure_ledger.audit()["entry_count"], 0)


if __name__ == "__main__":
    unittest.main()
