"""Independent target and no-regression semantics for GitLab triage controls."""

import copy
import unittest
from unittest.mock import patch

from gitlab_world import factory, verify


WORLD = factory.build_world("private-development-fixture-seed-001")
PROJECT = next(project for project in WORLD["projects"]
               if project["partition"] == "final_candidate_unsealed")
TASK = next(task for task in WORLD["tasks"]
            if task["project_family"] == PROJECT["full_path"]
            and task["template_group"] == "cross_record_issue_triage")
PROGRESS = {"project_id": 17,
            "issue_iids": {"active": 1, "validation": 2},
            "user_ids": {"oncall": 101, "contractor": 102, "incoming": 103},
            "mr_iids": {"approved": 1, "stale": 2}}


def snapshot():
    return {
        "schema": verify.SCHEMA, "project_ids": [17, 18],
        "business_sha256": "before",
        "db": {
            "projects": [{"id": 17}, {"id": 18}],
            "issues": [
                {"id": 201, "project_id": 17, "iid": 1,
                 "title": "active", "due_date": None, "milestone_id": None},
                {"id": 202, "project_id": 17, "iid": 2,
                 "title": "validation", "due_date": None, "milestone_id": None},
                {"id": 301, "project_id": 18, "iid": 1,
                 "title": "unrelated", "due_date": None, "milestone_id": None}],
            "issue_assignees": [],
            "labels": [{"id": 51, "project_id": 17,
                        "title": TASK["oracle"]["expected_priority"]}],
            "issue_label_links": [{"id": 700, "target_id": 201, "label_id": 1}],
            "milestones": [], "members": [], "merge_requests": [],
        },
        "git": {"17": {"refs": {"refs/heads/main": "a" * 40},
                       "main_blobs_sha256": {"README.md": "r"}},
                "18": {"refs": {"refs/heads/main": "b" * 40},
                       "main_blobs_sha256": {"README.md": "s"}}},
    }


class GitLabWorldOracleTests(unittest.TestCase):
    def score(self, after):
        before = snapshot()
        with patch.object(verify, "_context", return_value=(PROJECT, PROGRESS)):
            return verify.evaluate_final_task(TASK, before, after,
                                              inspect_live_git=False)

    def correct_after(self):
        after = copy.deepcopy(snapshot())
        after["business_sha256"] = "after"
        after["db"]["issues"][0]["due_date"] = PROJECT["policy"]["issue_due"]
        after["db"]["issue_assignees"].append({"issue_id": 201, "user_id": 101})
        after["db"]["issue_label_links"].append(
            {"id": 701, "target_id": 201, "label_id": 51})
        return after

    def test_correct_persisted_composite_change_scores_one(self):
        self.assertEqual(self.score(self.correct_after())["score"], 1.0)

    def test_partial_or_wrong_object_fails(self):
        after = self.correct_after()
        after["db"]["issue_assignees"].clear()
        self.assertEqual(self.score(after)["score"], 0.0)
        after = self.correct_after()
        after["db"]["issue_label_links"][-1]["target_id"] = 202
        self.assertEqual(self.score(after)["score"], 0.0)

    def test_unrelated_issue_or_project_git_change_fails(self):
        after = self.correct_after()
        after["db"]["issues"][2]["due_date"] = PROJECT["policy"]["issue_due"]
        self.assertEqual(self.score(after)["score"], 0.0)
        after = self.correct_after()
        after["git"]["18"]["refs"]["refs/heads/main"] = "c" * 40
        self.assertEqual(self.score(after)["score"], 0.0)

    def test_no_persisted_change_fails(self):
        self.assertEqual(self.score(snapshot())["score"], 0.0)

    def test_snapshot_diff_identifies_rows_and_git(self):
        before, after = snapshot(), self.correct_after()
        delta = verify.state_diff(before, after)
        self.assertEqual(delta["db"]["issues"]["modified"], [201])
        self.assertEqual(delta["db"]["issue_assignees"]["added"], [(201, 101)])
        self.assertEqual(delta["git_project_ids"], [])

    def test_linked_milestone_requires_two_issues_and_exact_window(self):
        task = next(row for row in WORLD["tasks"]
                    if row["project_family"] == PROJECT["full_path"] and
                    row["template_group"] == "release_milestone_coordination")
        before = snapshot()
        after = copy.deepcopy(before)
        after["business_sha256"] = "after"
        policy = PROJECT["policy"]
        after["db"]["milestones"].append({
            "id": 401, "project_id": 17, "title": policy["milestone_title"],
            "start_date": policy["milestone_start"], "due_date": policy["milestone_due"]})
        after["db"]["issues"][0]["milestone_id"] = 401
        after["db"]["issues"][1]["milestone_id"] = 401
        with patch.object(verify, "_context", return_value=(PROJECT, PROGRESS)):
            self.assertEqual(verify.evaluate_final_task(
                task, before, after, inspect_live_git=False)["score"], 1.0)
            after["db"]["issues"][1]["milestone_id"] = None
            self.assertEqual(verify.evaluate_final_task(
                task, before, after, inspect_live_git=False)["score"], 0.0)

    def test_access_handoff_rejects_overprivileged_incoming_role(self):
        task = next(row for row in WORLD["tasks"]
                    if row["project_family"] == PROJECT["full_path"] and
                    row["template_group"] == "least_privilege_access_handoff")
        before = snapshot()
        before["db"]["members"] = [
            {"id": 501, "source_id": 17, "user_id": 102,
             "access_level": 20, "expires_at": None},
            {"id": 502, "source_id": 17, "user_id": 101,
             "access_level": 30, "expires_at": None}]
        after = copy.deepcopy(before)
        after["business_sha256"] = "after"
        after["db"]["members"] = [before["db"]["members"][1].copy(),
                                   {"id": 503, "source_id": 17, "user_id": 103,
                                    "access_level": 20,
                                    "expires_at": PROJECT["policy"]["access_expiry"]}]
        with patch.object(verify, "_context", return_value=(PROJECT, PROGRESS)):
            self.assertEqual(verify.evaluate_final_task(
                task, before, after, inspect_live_git=False)["score"], 1.0)
            after["db"]["members"][-1]["access_level"] = 40
            self.assertEqual(verify.evaluate_final_task(
                task, before, after, inspect_live_git=False)["score"], 0.0)


if __name__ == "__main__":
    unittest.main()
