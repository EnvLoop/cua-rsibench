"""Partial native-GUI selector failures stay unscored and private."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gitlab_legacy_audit", ROOT / "tools/audit_gitlab_legacy_driver_failures.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class GitLabLegacyFailureAuditTests(unittest.TestCase):
    def test_partial_artifacts_are_counted_without_a_task_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            gui = private / "gui-controls"
            triage = gui / "GLW-11-01" / "positive-1"
            milestone = gui / "GLW-11-02" / "trio-1" / "positive-1"
            triage.mkdir(parents=True)
            milestone.mkdir(parents=True)
            for folder, n in ((triage, 2), (milestone, 3)):
                for index in range(n):
                    (folder / f"frame-{index}.png").write_bytes(b"screenshot" +
                                                                 bytes([index]))
            with patch.object(audit, "PRIVATE", private), \
                    patch.object(audit, "GUI", gui), \
                    patch.object(audit, "OUTPUT", private / "legacy-private.json"):
                public = audit.build()
                self.assertEqual(public["partial_unscored_driver_failure_count"], 2)
                self.assertEqual(public["native_gui_screenshots_retained_private"], 5)
                self.assertFalse(public["promoted_to_official_results"])
                self.assertEqual((private / "legacy-private.json").stat().st_mode & 0o777,
                                 0o600)
                self.assertEqual(audit.build(), public)


if __name__ == "__main__":
    unittest.main()
