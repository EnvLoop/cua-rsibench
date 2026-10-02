"""Private frame bytes are append-only under a hard capacity and free-space floor."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from native_desktop_factory import v066_storage_budget as storage


class V066StorageBudgetTests(unittest.TestCase):
    def test_retains_raw_bytes_and_refuses_overwrite_or_cap_escape(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
                storage, "MAX_LANE_EVIDENCE_BYTES", 10), patch.object(
                storage, "MIN_HOST_FREE_BYTES_AFTER_WRITE", 0):
            root = Path(directory)
            stored = storage.reserve_and_write(root, root / "first.png", b"first")
            self.assertEqual(stored["bytes"], 5)
            self.assertEqual((root / "first.png").read_bytes(), b"first")
            with self.assertRaises(ValueError):
                storage.reserve_and_write(root, root / "first.png", b"other")
            with self.assertRaises(ValueError):
                storage.reserve_and_write(root, root / "second.png", b"second")
            state = storage.audit(root, verify_all_bytes=True)
            self.assertEqual(state["reserved_evidence_bytes"], 5)
            self.assertEqual(state["unresolved_write_count"], 0)

    def test_crash_between_reserve_and_write_blocks_resume(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
                storage, "MIN_HOST_FREE_BYTES_AFTER_WRITE", 0):
            root = Path(directory)
            storage.reserve_and_write(root, root / "saved.png", b"image")
            connection = sqlite3.connect(root / "storage-ledger.sqlite3")
            try:
                connection.execute("UPDATE evidence SET status='reserved'")
                connection.commit()
            finally:
                connection.close()
            self.assertFalse(storage.audit(root)["dispatch_storage_ready"])
            with self.assertRaises(ValueError):
                storage.audit(root, verify_all_bytes=True)

    def test_low_host_free_space_refuses_raw_frame_without_writing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
                storage.shutil, "disk_usage",
                return_value=SimpleNamespace(free=100)), patch.object(
                storage, "MIN_HOST_FREE_BYTES_AFTER_WRITE", 99):
            root = Path(directory)
            with self.assertRaises(ValueError):
                storage.reserve_and_write(root, root / "blocked.png", b"raw")
            self.assertFalse((root / "blocked.png").exists())


if __name__ == "__main__":
    unittest.main()
