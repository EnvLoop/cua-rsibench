"""Train-only due-date calibration rejects wrong objects and unrelated edits."""

from __future__ import annotations

import copy
import unittest

from gitlab_world import factory, verify
from tools.probe_gitlab_issue_triage_train_v2 import score_train_probe


WORLD = factory.build_world("private-train-issue-probe-fixture-seed-001")
PROJECT = next(p for p in WORLD["projects"] if p["partition"] == "train")
PROGRESS = {"project_id": 17,
            "issue_iids": {"active": 1, "historical_duplicate": 3},
            "user_ids": {"oncall": 101}}


def before_state():
    return {"schema": verify.SCHEMA, "project_ids": [17, 18],
            "business_sha256": "before",
            "db": {"projects": [{"id": 17}, {"id": 18}],
                   "issues": [
                       {"id": 201, "project_id": 17, "iid": 1, "due_date": None},
                       {"id": 202, "project_id": 17, "iid": 2, "due_date": None},
                       {"id": 203, "project_id": 17, "iid": 3, "due_date": None},
                       {"id": 301, "project_id": 18, "iid": 1, "due_date": None}],
                   "milestones": [], "issue_assignees": [],
                   "labels": [{"id": 51, "project_id": 17,
                               "title": factory._priority(PROJECT["advisories"][0])}],
                   "issue_label_links": [], "members": [], "merge_requests": []},
            "git": {"17": {"refs": {"refs/heads/main": "a" * 40},
                           "main_blobs_sha256": {"README.md": "r"}},
                    "18": {"refs": {"refs/heads/main": "b" * 40},
                           "main_blobs_sha256": {"README.md": "s"}}}}


def after_state(*, wrong_issue=False):
    state = copy.deepcopy(before_state())
    target = 203 if wrong_issue else 201
    state["business_sha256"] = "after"
    next(row for row in state["db"]["issues"] if row["id"] == target)[
        "due_date"] = PROJECT["policy"]["issue_due"]
    state["db"]["issue_label_links"].append(
        {"id": 701, "target_id": target, "label_id": 51})
    state["db"]["issue_assignees"].append(
        {"issue_id": target, "user_id": 101})
    return state


class TrainIssueReadbackTests(unittest.TestCase):
    def test_positive_and_wrong_retired_asset_are_distinguished(self):
        self.assertEqual(score_train_probe(PROJECT, PROGRESS, before_state(),
                                           after_state(), wrong_issue=False), 1.0)
        self.assertEqual(score_train_probe(PROJECT, PROGRESS, before_state(),
                                           after_state(wrong_issue=True),
                                           wrong_issue=True), 0.0)

    def test_unrelated_issue_change_rejected(self):
        state = after_state()
        state["db"]["issues"][3]["due_date"] = PROJECT["policy"]["issue_due"]
        with self.assertRaises(verify.QualificationError):
            score_train_probe(PROJECT, PROGRESS, before_state(), state,
                              wrong_issue=False)


if __name__ == "__main__":
    unittest.main()
