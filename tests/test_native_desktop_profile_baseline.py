"""Hidden final profile baselines fail closed on split and cleanup evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from native_desktop_factory.profile_baseline_one import preflight
from native_desktop_factory.reconcile_profile_baseline_cleanup import reconcile


class FinalProfileBaselineTests(unittest.TestCase):
    def test_train_package_cannot_enter_final_profile_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "train" / "example"
            package.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "Only private final-candidate"):
                preflight(package, root)

    def test_cleanup_reconciliation_requires_mature_lease_and_absence(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt_path = Path(temporary) / "attempt" / "receipt.json"
            receipt_path.parent.mkdir()
            receipt_path.write_text(json.dumps({
                "schema": "cua-native-wdi-profile-baseline-v1",
                "status": "profile_baseline_observed", "task_id": "private-synthetic",
                "canonical_profile_sha256": "a" * 64,
                "input_unchanged_after_open": True,
                "sandbox_id_sha256": "b" * 64,
                "kill_error_type": "RemoteProtocolError",
                "lease_seconds": 120,
            }))
            with patch.dict(os.environ, {"E2B_API_KEY": "synthetic-test-key"}), \
                 patch("native_desktop_factory.reconcile_profile_baseline_cleanup.time.time",
                       return_value=time.time() + 500), \
                 patch("native_desktop_factory.reconcile_profile_baseline_cleanup.active_hashes",
                       return_value=(set(), 0)):
                result = reconcile(receipt_path, grace_seconds=90)
            self.assertEqual(result["status"], "reconciled_terminated_after_full_lease")
            self.assertFalse(result["specific_sandbox_running_at_check"])
            with patch.dict(os.environ, {"E2B_API_KEY": "synthetic-test-key"}), \
                 patch("native_desktop_factory.reconcile_profile_baseline_cleanup.time.time",
                       return_value=time.time() + 500), \
                 patch("native_desktop_factory.reconcile_profile_baseline_cleanup.active_hashes",
                       return_value=({"b" * 64}, 1)):
                with self.assertRaisesRegex(ValueError, "still running"):
                    reconcile(receipt_path, grace_seconds=90)


if __name__ == "__main__":
    unittest.main()
