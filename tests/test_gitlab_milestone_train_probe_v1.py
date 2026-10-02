"""The train-only milestone probe uses persisted state and no regression."""

from __future__ import annotations

import copy
from datetime import date, timedelta
import unittest

from gitlab_world import factory, gui_workflows, verify
from tools.probe_gitlab_milestone_save_train_v1 import score_train_probe


WORLD = factory.build_world("private-milestone-probe-fixture-seed-001")
PROJECT = next(p for p in WORLD["projects"] if p["partition"] == "train")
PROGRESS = {"project_id": 17, "issue_iids": {"active": 1, "validation": 2}}


def before_state():
    return {"schema": verify.SCHEMA, "project_ids": [17, 18],
            "business_sha256": "before",
            "db": {"projects": [{"id": 17}, {"id": 18}],
                   "issues": [
                       {"id": 201, "project_id": 17, "iid": 1,
                        "milestone_id": None, "due_date": None},
                       {"id": 202, "project_id": 17, "iid": 2,
                        "milestone_id": None, "due_date": None},
                       {"id": 301, "project_id": 18, "iid": 1,
                        "milestone_id": None, "due_date": None}],
                   "milestones": [], "issue_assignees": [], "labels": [],
                   "issue_label_links": [], "members": [], "merge_requests": []},
            "git": {"17": {"refs": {"refs/heads/main": "a" * 40},
                           "main_blobs_sha256": {"README.md": "r"}},
                    "18": {"refs": {"refs/heads/main": "b" * 40},
                           "main_blobs_sha256": {"README.md": "s"}}}}


def after_state(*, wrong_due=False):
    after = copy.deepcopy(before_state())
    due = PROJECT["policy"]["milestone_due"]
    if wrong_due:
        due = (date.fromisoformat(due) + timedelta(days=2)).isoformat()
    after["business_sha256"] = "after"
    after["db"]["milestones"] = [{"id": 401, "project_id": 17,
                                   "title": PROJECT["policy"]["milestone_title"],
                                   "start_date": PROJECT["policy"]["milestone_start"],
                                   "due_date": due}]
    after["db"]["issues"][0]["milestone_id"] = 401
    after["db"]["issues"][1]["milestone_id"] = 401
    return after


class TrainMilestoneReadbackTests(unittest.TestCase):
    def test_correct_and_wrong_due_date_are_distinguished(self):
        self.assertEqual(score_train_probe(PROJECT, PROGRESS, before_state(),
                                           after_state()), 1.0)
        self.assertEqual(score_train_probe(PROJECT, PROGRESS, before_state(),
                                           after_state(wrong_due=True)), 0.0)

    def test_missing_second_link_and_unrelated_change_fail(self):
        after = after_state()
        after["db"]["issues"][1]["milestone_id"] = None
        with self.assertRaises(verify.QualificationError):
            score_train_probe(PROJECT, PROGRESS, before_state(), after)
        after = after_state()
        after["db"]["issues"][2]["due_date"] = "2026-09-28"
        with self.assertRaises(verify.QualificationError):
            score_train_probe(PROJECT, PROGRESS, before_state(), after)


class FakeMilestoneLocator:
    def __init__(self, page, kind):
        self.page, self.kind = page, kind

    @property
    def first(self):
        return self

    def locator(self, selector):
        if selector == '[data-testid="edit-button"]':
            return FakeMilestoneLocator(self.page, "edit")
        if selector == '[data-testid="listbox-search-input"]':
            return FakeMilestoneLocator(self.page, "search")
        if selector == '[data-testid="apply-button"]':
            return FakeMilestoneLocator(self.page, "apply")
        if selector == ".gl-spinner":
            return FakeMilestoneLocator(self.page, "spinner")
        raise AssertionError(selector)

    def get_by_text(self, text, **kwargs):
        return FakeMilestoneLocator(self.page, "milestone")

    def get_by_role(self, role):
        if role != "option":
            raise AssertionError(role)
        return FakeMilestoneLocator(self.page, "option")

    def filter(self, **kwargs):
        return self

    async def count(self):
        if self.kind == "milestone":
            return int(self.page.visible)
        if self.kind == "apply":
            return 1
        return 1

    async def is_visible(self):
        return self.page.visible

    async def click(self):
        if self.kind == "option":
            self.page.visible = True
        elif self.kind == "apply":
            self.page.saves += 1
            self.page.persisted = self.page.saves >= self.page.save_on_attempt

    async def fill(self, value):
        return None

    async def wait_for(self, **kwargs):
        if self.kind == "milestone" and not self.page.visible:
            raise TimeoutError("milestone is absent")


class FakeMilestonePage:
    def __init__(self, save_on_attempt):
        self.save_on_attempt = save_on_attempt
        self.saves = 0
        self.persisted = False
        self.visible = False
        self.reloads = 0

    async def goto(self, url, **kwargs):
        self.visible = self.persisted

    async def reload(self, **kwargs):
        self.reloads += 1
        self.visible = self.persisted

    def get_by_text(self, text, **kwargs):
        return FakeMilestoneLocator(self, "heading")

    def locator(self, selector):
        if selector != '[data-testid="work-item-milestone"]':
            raise AssertionError(selector)
        return FakeMilestoneLocator(self, "section")

    async def wait_for_timeout(self, milliseconds):
        return None


class MilestoneVisibleReloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_visible_link_is_retried_until_reload_persists(self):
        page = FakeMilestonePage(save_on_attempt=2)
        attempts = await gui_workflows._link_issue_milestone_with_reload(
            page, "private/project", 1, "Expected milestone", "Expected issue")
        self.assertEqual(attempts, 2)
        self.assertEqual(page.reloads, 2)

    async def test_never_persisted_link_fails_after_three_attempts(self):
        page = FakeMilestonePage(save_on_attempt=99)
        with self.assertRaises(RuntimeError):
            await gui_workflows._link_issue_milestone_with_reload(
                page, "private/project", 1, "Expected milestone", "Expected issue")
        self.assertEqual(page.saves, 3)
        self.assertEqual(page.reloads, 3)


if __name__ == "__main__":
    unittest.main()
