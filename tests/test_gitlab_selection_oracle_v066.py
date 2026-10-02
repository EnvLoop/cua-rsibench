"""Synthetic original-GitLab selection oracle target/no-regression checks."""

from __future__ import annotations

import copy
import hashlib
import unittest
from unittest.mock import patch

from gitlab_world import factory, selection_oracle_v066 as oracle, verify


WORLD = factory.build_world("private-development-fixture-seed-001")
PROJECT = next(row for row in WORLD["projects"]
               if row["partition"] == "selection")
TASKS = [row for row in WORLD["tasks"]
         if row["project_family"] == PROJECT["full_path"]]
PROGRESS = {"project_id": 17,
            "issue_iids": {"active": 1, "historical_duplicate": 3},
            "user_ids": {"oncall": 101, "incoming": 103}}


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def snapshot() -> dict:
    return {
        "schema": verify.SCHEMA, "project_ids": [17, 18],
        "business_sha256": "before",
        "db": {
            "projects": [{"id": 17}, {"id": 18}],
            "issues": [
                {"id": 201, "project_id": 17, "iid": 1,
                 "title": "active", "state_id": 1},
                {"id": 203, "project_id": 17, "iid": 3,
                 "title": "historical", "state_id": 1},
                {"id": 301, "project_id": 18, "iid": 1,
                 "title": "unrelated", "state_id": 1}],
            "issue_assignees": [], "labels": [], "issue_label_links": [],
            "milestones": [], "members": [], "merge_requests": [],
        },
        "git": {
            "17": {
                "refs": {"refs/heads/main": "a" * 40,
                         "refs/heads/feature": "f" * 40},
                "main_blobs_sha256": {
                    "README.md": digest("readme"),
                    ".gitlab-ci.yml": digest("ci"),
                    "docs/response-runbook.md": digest(
                        PROJECT["files"]["docs/response-runbook.md"]),
                }},
            "18": {
                "refs": {"refs/heads/main": "b" * 40},
                "main_blobs_sha256": {"README.md": digest("unrelated")}},
        },
    }


class SelectionOracleTests(unittest.TestCase):
    def score(self, task, before, after):
        with patch.object(verify, "_context",
                          return_value=(PROJECT, PROGRESS)):
            return oracle.evaluate_selection_task(task, before, after)

    def positive(self, task):
        before = snapshot()
        after = copy.deepcopy(before)
        after["business_sha256"] = "after"
        family = task["template_group"]
        if family == "issue_owner_transfer":
            after["db"]["issue_assignees"] = [
                {"issue_id": 201, "user_id": 101}]
        elif family == "false_positive_closure":
            after["db"]["issues"][1]["state_id"] = 2
        elif family == "runbook_contact_annotation":
            source = PROJECT["files"]["docs/response-runbook.md"]
            expected = source.replace(
                "Current contact: pending",
                "Current contact: @" + PROJECT["principals"]["oncall"])
            after["git"]["17"]["refs"]["refs/heads/main"] = "c" * 40
            after["git"]["17"]["main_blobs_sha256"][
                "docs/response-runbook.md"] = digest(expected)
        elif family == "reporter_member_expiry":
            after["db"]["members"] = [{
                "id": 501, "source_id": 17, "user_id": 103,
                "access_level": 20,
                "expires_at": PROJECT["policy"]["access_expiry"]}]
        else:
            raise AssertionError("unexpected family")
        return before, after

    def test_four_original_selection_targets_and_collateral_negatives(self):
        self.assertEqual(len(TASKS), 4)
        for task in TASKS:
            with self.subTest(family=task["template_group"]):
                before, after = self.positive(task)
                passed = self.score(task, before, after)
                self.assertEqual((passed["reward"], passed["checks_passed"]),
                                 (1.0, True))
                after["db"]["issues"][2]["title"] = "collateral"
                failed = self.score(task, before, after)
                self.assertEqual((failed["reward"], failed["checks_passed"]),
                                 (0.0, False))

    def test_wrong_issue_wrong_member_and_modified_other_blob_fail(self):
        task = next(row for row in TASKS
                    if row["template_group"] == "issue_owner_transfer")
        before, after = self.positive(task)
        after["db"]["issue_assignees"][0]["issue_id"] = 203
        self.assertEqual(self.score(task, before, after)["reward"], 0.0)
        task = next(row for row in TASKS
                    if row["template_group"] == "reporter_member_expiry")
        before, after = self.positive(task)
        after["db"]["members"][0]["access_level"] = 30
        self.assertEqual(self.score(task, before, after)["reward"], 0.0)
        task = next(row for row in TASKS
                    if row["template_group"] == "runbook_contact_annotation")
        before, after = self.positive(task)
        after["git"]["17"]["main_blobs_sha256"][".gitlab-ci.yml"] = "0" * 64
        self.assertEqual(self.score(task, before, after)["reward"], 0.0)

    def test_nonselection_and_unchanged_business_rejected(self):
        task = TASKS[0]
        before = snapshot()
        self.assertEqual(self.score(task, before, before)["reward"], 0.0)
        with self.assertRaisesRegex(ValueError, "selection_only"):
            oracle.evaluate_selection_task(
                {**task, "partition": "final_candidate_unsealed"},
                before, before)


if __name__ == "__main__":
    unittest.main()
