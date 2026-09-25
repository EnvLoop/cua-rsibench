"""Candidate sweeper must never infer 100 admissions from inventory."""

import unittest
from unittest.mock import patch
from pathlib import Path
import json
import tempfile

from gitlab_world import factory, gui_controls, sweep


WORLD = factory.build_world("development-sweep-test-private-seed-001")


class GitLabOriginalSweepTests(unittest.TestCase):
    def test_100_candidates_but_only_20_have_a_gui_driver(self):
        with patch.object(sweep.bootstrap, "world", return_value=WORLD), \
                patch.object(sweep.quarantine, "load", return_value={"families": {}}):
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
        with patch.object(sweep.bootstrap, "world", return_value=WORLD), \
                patch.object(sweep.quarantine, "load", return_value={"families": {}}):
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

    def test_whole_family_quarantine_plus_unused_reserve_restores_100(self):
        reserve = factory.reserve_replacement("development-sweep-test-private-seed-001")
        combined = {**WORLD, "reserve_projects": [reserve["project"]],
                    "reserve_tasks": reserve["tasks"]}
        exposed = next(row for row in WORLD["tasks"]
                       if row["partition"] == "final_candidate_unsealed")
        excluded = {row["task_id"] for row in WORLD["tasks"]
                    if row["source_family"] == exposed["source_family"]}
        with patch.object(sweep.bootstrap, "world", return_value=combined), \
                patch.object(sweep.quarantine, "excluded_task_ids", return_value=excluded):
            clean = sweep.candidates()
            self.assertEqual(len(clean), 100)
            self.assertEqual(len({row["source_family"] for row in clean}), 20)
            self.assertFalse({row["task_id"] for row in clean} & excluded)


class GitLabSweepFailurePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_gui_error_is_recorded_before_sweep_stops(self):
        async def fail(*args, **kwargs):
            raise TimeoutError("private GUI detail")
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            (private / "baseline-persisted-state.json").write_text(
                json.dumps({"business_sha256": "same"}))
            item = {"task_id": "private-test-id", "template_group": "cross_record_issue_triage",
                    "source_family": "source"}
            with patch.object(sweep, "INDEX", private / "index.json"), \
                    patch.object(sweep.runtime, "PRIVATE", private), \
                    patch.object(sweep, "candidates", return_value=[item]), \
                    patch.object(sweep.quarantine, "excluded_task_ids", return_value=set()), \
                    patch.object(sweep.verify, "state_snapshot",
                                 return_value={"business_sha256": "same"}), \
                    patch.object(sweep.gui_controls, "run", side_effect=fail):
                with self.assertRaises(TimeoutError):
                    await sweep.run(1)
                index = json.loads((private / "index.json").read_text())
                self.assertEqual(index["items"]["private-test-id"]["status"],
                                 "driver_or_environment_failed")
                self.assertEqual(index["items"]["private-test-id"]["error_type"],
                                 "TimeoutError")
                self.assertEqual(len(index["items"]["private-test-id"]["attempts"]), 1)
                self.assertEqual((private / "index.json").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
