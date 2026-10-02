"""Development exposure removes a whole correlated project from final eligibility."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gitlab_world import factory, quarantine


WORLD = factory.build_world("development-quarantine-test-private-seed-001")
TASK = next(row for row in WORLD["tasks"]
            if row["template_group"] == "cross_record_issue_triage")


class GitLabQuarantineTests(unittest.TestCase):
    def test_one_gui_control_quarantines_five_source_correlated_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(quarantine, "REGISTRY", Path(tmp) / "private.json"), \
                    patch.object(quarantine.bootstrap, "world", return_value=WORLD):
                counts = quarantine.add_by_task(TASK["task_id"],
                                                reason="gui_development_control")
                self.assertEqual(counts["quarantined_source_families"], 1)
                self.assertEqual(counts["quarantined_final_candidate_ids"], 5)
                self.assertEqual(counts["still_unexposed_final_candidates"], 95)
                self.assertFalse(counts["unexposed_100_candidate_inventory_intact"])
                self.assertEqual(len(quarantine.excluded_task_ids()), 5)
                self.assertEqual(quarantine.REGISTRY.stat().st_mode & 0o777, 0o600)
                self.assertEqual(quarantine.add_by_task(
                    TASK["task_id"], reason="gui_development_control"), counts)
                with self.assertRaises(RuntimeError):
                    quarantine.add_by_task(TASK["task_id"], reason="operator_review")


if __name__ == "__main__":
    unittest.main()
