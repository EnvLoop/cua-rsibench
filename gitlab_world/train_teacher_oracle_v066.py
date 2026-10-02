"""Independent persisted-state oracle for GitLab train teacher episodes.

Only the four original training workflows are scored here. The production
readback is the evaluator-owned PostgreSQL and Git snapshot in ``verify``;
none of these fields are included in the actor observation or teacher prompt.
The final-candidate oracle and its source bytes remain untouched.
"""

from __future__ import annotations

from . import verify


TRAIN_FAMILIES = frozenset({
    "issue_label_from_alert", "issue_due_from_register",
    "milestone_window_from_policy", "guest_member_from_roster",
})


def evaluate_train_task(task: dict, before: dict, after: dict) -> dict:
    if (type(task) is not dict or task.get("partition") != "train" or
            task.get("template_group") not in TRAIN_FAMILIES):
        raise ValueError("train_only_oracle_required")
    if (before.get("schema") != verify.SCHEMA or
            after.get("schema") != verify.SCHEMA or
            before.get("project_ids") != after.get("project_ids")):
        raise ValueError("independent_snapshot_schema_or_roster_changed")
    project, progress = verify._context(task)
    if (project["partition"] != "train" or
            project["full_path"] != task["project_family"]):
        raise ValueError("oracle_project_not_train_bound")
    project_id = int(progress["project_id"])
    active = verify._issue(before, project_id,
                           int(progress["issue_iids"]["active"]))
    try:
        verify._require(before["business_sha256"] != after["business_sha256"],
                        "no persisted business change")
        verify._unchanged_other_git(before, after, project_id)
        family = task["template_group"]
        if family == "issue_label_from_alert":
            verify._unchanged_tables(before, after, "issue_label_links")
            verify._added_label_link(
                before, after, int(active["id"]),
                verify._project_label_id(
                    before, project_id, task["oracle"]["expected_priority"]))
        elif family == "issue_due_from_register":
            verify._unchanged_tables(before, after, "issues")
            verify._only_issue_fields(
                before, after,
                {int(active["id"]): {"due_date": project["policy"]["issue_due"]}})
        elif family == "milestone_window_from_policy":
            verify._unchanged_tables(before, after, "milestones")
            new, removed, modified = verify._table_delta(
                before, after, "milestones")
            verify._require(len(new) == 1 and not removed and not modified,
                            "milestone delta is not exactly one addition")
            milestone = verify._rows_by_id(after["db"]["milestones"])[
                next(iter(new))]
            policy = project["policy"]
            verify._require(
                milestone["project_id"] == project_id and
                milestone["title"] == policy["milestone_title"] and
                milestone["start_date"] == policy["milestone_start"] and
                milestone["due_date"] == policy["milestone_due"],
                "milestone project, title, or dates mismatch")
        elif family == "guest_member_from_roster":
            verify._unchanged_tables(before, after, "members")
            old = verify._rows_by_id(before["db"]["members"])
            current = verify._rows_by_id(after["db"]["members"])
            added = set(current) - set(old)
            verify._require(
                len(added) == 1 and not (set(old) - set(current)) and
                all(current[key] == old[key] for key in old),
                "member delta is not exactly one addition")
            member = current[next(iter(added))]
            verify._require(
                member["source_id"] == project_id and
                member["user_id"] == int(progress["user_ids"]["incoming"]) and
                member["access_level"] == 10 and
                member["expires_at"] is None,
                "new member is not the exact incoming Guest")
        return {
            "reward": 1.0, "checks_passed": True, "difference_codes": [],
            "before_business_sha256": before["business_sha256"],
            "after_business_sha256": after["business_sha256"],
        }
    except verify.QualificationError:
        return {
            "reward": 0.0, "checks_passed": False,
            "difference_codes": ["target_or_no_regression_mismatch"],
            "before_business_sha256": before["business_sha256"],
            "after_business_sha256": after["business_sha256"],
        }


__all__ = ["TRAIN_FAMILIES", "evaluate_train_task"]
