"""Candidate sweeper must never infer 100 admissions from inventory."""

import unittest
from unittest.mock import patch

from gitlab_world import factory, gui_controls, sweep


WORLD = factory.build_world("development-sweep-test-private-seed-001")


class GitLabOriginalSweepTests(unittest.TestCase):
    def test_100_candidates_but_only_20_have_a_gui_driver(self):
        with patch.object(sweep.bootstrap, "world", return_value=WORLD):
            summary = sweep.public_summary({"items": {}})
            self.assertEqual(summary["candidate_final_total"], 100)
            self.assertEqual(summary["candidate_families"], {
                "approved_merge_request_merge": 20,
                "ci_and_runbook_reconciliation": 20,
                "cross_record_issue_triage": 20,
                "least_privilege_access_handoff": 20,
                "release_milestone_coordination": 20})
            self.assertEqual(summary["statuses"], {"not_attempted": 100})
            self.assertEqual(summary["official_final_admitted"], 0)

    def test_public_summary_only_counts_explicit_per_id_controls(self):
        with patch.object(sweep.bootstrap, "world", return_value=WORLD):
            first = sweep.candidates()[0]["task_id"]
            summary = sweep.public_summary({"items": {
                first: {"status": "development_gui_trio_passed", "scores": [1, 0, 1]}}})
            self.assertEqual(summary["development_gui_trio_passed"], 1)
            self.assertEqual(summary["statuses"]["not_attempted"], 99)
            self.assertFalse(summary["complete_100_per_id_gui_admission"])
            self.assertNotIn(first, str(summary))

    def test_browser_network_guard_stays_on_loopback(self):
        self.assertTrue(gui_controls._local_url("http://127.0.0.1:8014/x"))
        self.assertFalse(gui_controls._local_url("http://127.0.0.1:8012/x"))
        self.assertFalse(gui_controls._local_url("https://gitlab.com/x"))
        self.assertFalse(gui_controls._local_url("http://username:pass@127.0.0.1:8014/x"))


if __name__ == "__main__":
    unittest.main()
