"""Synthetic Odoo private-mode repair; no Docker or provider calls."""

from __future__ import annotations

import fcntl
from hashlib import sha256
import json
from pathlib import Path
import stat
import tempfile
import unittest

from tools import harden_odoo_private_evidence_v1 as harden


COMPOSE = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18/compose.yaml"


class HardenOdooPrivateEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workers = root / "workers"
        self.workers.mkdir()
        self.journal = root / "private-journal"
        self.journal.mkdir(mode=0o700)
        self.before = self.journal / "before.private.json"
        self.after = self.journal / "after.private.json"
        for split, dir_count, file_count in (
                ("train", 8, 23), ("selection", 3, 8),
                ("official_hidden", 4, 8)):
            private = self.workers / split / "private"
            private.mkdir(parents=True)
            private.chmod(0o700 if split == "selection" else 0o755)
            remaining_dirs = dir_count - (0 if split == "selection" else 1)
            for index in range(remaining_dirs):
                folder = private / f"extra-{index:02}"
                folder.mkdir()
                folder.chmod(0o755)
            for index in range(file_count):
                path = private / f"artifact-{index:02}.json"
                path.write_bytes(f"{split}:{index}".encode())
                path.chmod(0o644)
            lock = private / "worker-operation.lock"
            lock.write_bytes(b"")
            lock.chmod(0o600)
            events = private / "worker-lease-events.jsonl"
            events.write_text("\n".join(json.dumps(value) for value in (
                {"event": "acquired", "operation": "audit_partition", "pid": 42},
                {"event": "released", "operation": "audit_partition", "pid": 42},
            )) + "\n")
            events.chmod(0o600)

    def test_hardens_exact_modes_without_changing_bytes(self):
        original = {str(path.relative_to(self.workers)): sha256(path.read_bytes()).hexdigest()
                    for path in self.workers.rglob("*") if path.is_file()}
        result = harden.harden(self.workers, journal_before=self.before,
                               journal_after=self.after, compose=COMPOSE)
        self.assertEqual(result["affected_paths_verified_byte_identical"], 54)
        self.assertEqual(result["remaining_permissive_modes"],
                         {"directories": 0, "files": 0})
        self.assertEqual(stat.S_IMODE(self.before.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.after.stat().st_mode), 0o600)
        self.assertEqual(sha256(self.before.read_bytes()).hexdigest(),
                         result["before_journal_sha256"])
        self.assertEqual(sha256(self.after.read_bytes()).hexdigest(),
                         result["after_journal_sha256"])
        self.assertEqual(original, {
            str(path.relative_to(self.workers)): sha256(path.read_bytes()).hexdigest()
            for path in self.workers.rglob("*") if path.is_file()})
        with self.assertRaisesRegex(harden.HardeningError,
                                    "hardening_paths_invalid"):
            harden.harden(self.workers, journal_before=self.before,
                          journal_after=self.after, compose=COMPOSE)

    def test_active_worker_lock_stops_before_journal_or_chmod(self):
        lock = self.workers / "train" / "private" / "worker-operation.lock"
        with lock.open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with self.assertRaisesRegex(harden.HardeningError,
                                            "odoo_worker_lease_active"):
                    harden.harden(self.workers, journal_before=self.before,
                                  journal_after=self.after, compose=COMPOSE)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
        self.assertFalse(self.before.exists())
        self.assertEqual(stat.S_IMODE(
            (self.workers / "train" / "private" / "artifact-00.json").stat().st_mode),
            0o644)

    def test_unexpected_inventory_stops_before_journal(self):
        (self.workers / "official_hidden" / "private" / "artifact-00.json").chmod(0o600)
        with self.assertRaisesRegex(harden.HardeningError,
                                    "unexpected_private_mode_inventory"):
            harden.harden(self.workers, journal_before=self.before,
                          journal_after=self.after, compose=COMPOSE)
        self.assertFalse(self.before.exists())


if __name__ == "__main__":
    unittest.main()
