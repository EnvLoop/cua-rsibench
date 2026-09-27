"""Independent PostgreSQL/Git scorer for four original GitLab selection tasks.

This evaluator-only module never enters the model-facing observation. It reads
the same full persisted snapshot as the final-task verifier but does not change
that verifier or the 100-task development control evidence.
"""

from __future__ import annotations

import hashlib

from . import verify


SELECTION_FAMILIES = frozenset({
    "issue_owner_transfer", "false_positive_closure",
    "runbook_contact_annotation", "reporter_member_expiry",
})


def evaluate_selection_task(task: dict, before: dict, after: dict) -> dict:
    if (type(task) is not dict or task.get("partition") != "selection" or
            task.get("template_group") not in SELECTION_FAMILIES):
        raise ValueError("selection_only_oracle_required")
    if (before.get("schema") != verify.SCHEMA or
            after.get("schema") != verify.SCHEMA or
            before.get("project_ids") != after.get("project_ids")):
        raise ValueError("independent_snapshot_schema_or_roster_changed")
    project, progress = verify._context(task)
    if (project["partition"] != "selection" or
            project["full_path"] != task["project_family"]):
        raise ValueError("oracle_project_not_selection_bound")
    project_id = int(progress["project_id"])
    try:
        verify._require(before["business_sha256"] != after["business_sha256"],
                        "no persisted business change")
        family = task["template_group"]
        if family == "issue_owner_transfer":
            verify._unchanged_tables(before, after, "issue_assignees")
            verify._unchanged_other_git(before, after, project_id)
            active = verify._issue(
                before, project_id, int(progress["issue_iids"]["active"]))
            verify._assign_exact(before, after, int(active["id"]),
                                 int(progress["user_ids"]["oncall"]))
        elif family == "false_positive_closure":
            verify._unchanged_tables(before, after, "issues")
            verify._unchanged_other_git(before, after, project_id)
            historical = verify._issue(
                before, project_id,
                int(progress["issue_iids"]["historical_duplicate"]))
            verify._require(historical["state_id"] == 1,
                            "historical issue did not start open")
            verify._only_issue_fields(
                before, after, {int(historical["id"]): {"state_id": 2}})
        elif family == "runbook_contact_annotation":
            verify._unchanged_tables(before, after)
            verify._unchanged_other_git(before, after, project_id,
                                        allow_main=True)
            target = str(project_id)
            old = before["git"][target]
            new = after["git"][target]
            verify._require(
                old["refs"]["refs/heads/main"] !=
                new["refs"]["refs/heads/main"],
                "default branch did not advance")
            source = project["files"]["docs/response-runbook.md"]
            verify._require(source.count("Current contact: pending") == 1,
                            "source runbook contact is not unique")
            expected = source.replace(
                "Current contact: pending",
                "Current contact: @" + project["principals"]["oncall"])
            expected_sha = hashlib.sha256(expected.encode()).hexdigest()
            verify._require(
                new["main_blobs_sha256"].get("docs/response-runbook.md") ==
                expected_sha and
                all(new["main_blobs_sha256"].get(path) == digest
                    for path, digest in old["main_blobs_sha256"].items()
                    if path != "docs/response-runbook.md"),
                "runbook content or unrelated default-branch blob differs")
        elif family == "reporter_member_expiry":
            verify._unchanged_tables(before, after, "members")
            verify._unchanged_other_git(before, after, project_id)
            old = verify._rows_by_id(before["db"]["members"])
            current = verify._rows_by_id(after["db"]["members"])
            added = set(current) - set(old)
            verify._require(
                len(added) == 1 and not (set(old) - set(current)) and
                all(current[key] == old[key] for key in old),
                "membership delta is not one addition")
            member = current[next(iter(added))]
            verify._require(
                member["source_id"] == project_id and
                member["user_id"] == int(progress["user_ids"]["incoming"]) and
                member["access_level"] == 20 and
                member["expires_at"] == project["policy"]["access_expiry"],
                "incoming Reporter role or expiry differs")
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


__all__ = ["SELECTION_FAMILIES", "evaluate_selection_task"]
