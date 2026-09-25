"""Independent, read-only PostgreSQL and Git oracle for the GitLab world."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from . import bootstrap, factory, runtime


SCHEMA = "envloop-gitlab-persisted-state-v1"


def _ids() -> list[int]:
    progress = json.loads(bootstrap.PROGRESS_FILE.read_text())
    if len(progress["projects"]) not in (30, 31) or not all(
            item.get("complete") for item in progress["projects"].values()):
        raise RuntimeError("GitLab project roster must be fully bootstrapped")
    ids = sorted(int(item["project_id"]) for item in progress["projects"].values())
    if len(set(ids)) != len(ids) or any(value <= 0 for value in ids):
        raise RuntimeError("project IDs invalid")
    return ids


def _sql_rows(select: str, table: str, where: str, order: str) -> list[dict]:
    # Call sites supply fixed SQL identifiers and a validated integer ID list.
    query = ("SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM "
             f"(SELECT {select} FROM {table} WHERE {where} ORDER BY {order}) q;")
    raw = runtime.docker("exec", runtime.WORLD, "gitlab-psql", "-At", "-c", query,
                         timeout=60)
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise RuntimeError("PostgreSQL oracle returned non-list")
    return rows


def _repo_dir(project_id: int) -> str:
    digest = hashlib.sha256(str(project_id).encode()).hexdigest()
    return ("/var/opt/gitlab/git-data/repositories/@hashed/"
            f"{digest[:2]}/{digest[2:4]}/{digest}.git")


def _git(project_id: int, *args: str) -> bytes:
    repo = _repo_dir(project_id)
    result = subprocess.run(["docker", "--context", runtime.CONTEXT, "exec",
                             runtime.WORLD, "git", "--git-dir=" + repo, *args],
                            capture_output=True, check=True, timeout=30)
    return result.stdout


def git_refs(project_id: int) -> dict[str, str]:
    lines = _git(project_id, "show-ref", "--heads").decode().splitlines()
    refs = {}
    for line in lines:
        sha, ref = line.split(" ", 1)
        if not ref.startswith("refs/heads/") or len(sha) != 40:
            raise RuntimeError("unexpected Git ref")
        refs[ref] = sha
    if "refs/heads/main" not in refs:
        raise RuntimeError("GitLab project main branch missing")
    return dict(sorted(refs.items()))


def git_blob(project_id: int, ref: str, path: str) -> bytes:
    if ref not in ("main",) and not ref.startswith("response-cve-"):
        raise ValueError("unapproved Git ref")
    if path not in ("README.md", ".gitlab-ci.yml", "docs/response-runbook.md",
                    "security/kev-register.csv", "security/release-policy.md",
                    "security/SECURITY.md"):
        raise ValueError("unapproved Git path")
    return _git(project_id, "show", "refs/heads/" + ref + ":" + path)


def state_snapshot() -> dict:
    ids = _ids()
    id_sql = ",".join(map(str, ids))
    query = {
        "projects": ("id,name,path,namespace_id,visibility_level,archived,"
                     "only_allow_merge_if_pipeline_succeeds", "projects", f"id IN ({id_sql})", "id"),
        "issues": ("id,project_id,iid,title,description,milestone_id,due_date,state_id,confidential",
                   "issues", f"project_id IN ({id_sql})", "id"),
        "issue_assignees": ("ia.issue_id,ia.user_id", "issue_assignees ia "
                            "JOIN issues i ON i.id=ia.issue_id",
                            f"i.project_id IN ({id_sql})", "ia.issue_id,ia.user_id"),
        "labels": ("id,title,project_id,color", "labels", f"project_id IN ({id_sql})", "id"),
        "issue_label_links": ("ll.id,ll.target_id,ll.label_id", "label_links ll "
                              "JOIN issues i ON i.id=ll.target_id AND ll.target_type='Issue'",
                              f"i.project_id IN ({id_sql})", "ll.id"),
        "milestones": ("id,project_id,title,start_date,due_date,state,description",
                       "milestones", f"project_id IN ({id_sql})", "id"),
        "members": ("id,source_id,user_id,access_level,expires_at,state,type",
                    "members", f"source_type='Project' AND source_id IN ({id_sql})", "id"),
        "merge_requests": ("id,target_project_id,iid,source_branch,target_branch,"
                           "state_id,merge_commit_sha,merged_commit_sha",
                           "merge_requests", f"target_project_id IN ({id_sql})", "id"),
    }
    db = {name: _sql_rows(*definition) for name, definition in query.items()}
    git = {str(project_id): {"refs": git_refs(project_id),
                             "main_blobs_sha256": {
                                 path: hashlib.sha256(git_blob(project_id, "main", path)).hexdigest()
                                 for path in ("README.md", ".gitlab-ci.yml",
                                              "docs/response-runbook.md", "security/kev-register.csv",
                                              "security/release-policy.md", "security/SECURITY.md")}}
           for project_id in ids}
    result = {"schema": SCHEMA, "project_ids": ids, "db": db, "git": git}
    result["business_sha256"] = factory.sha256(factory.canonical(result))
    return result


def _rows_by_id(rows: list[dict]) -> dict[int, dict]:
    result = {int(row["id"]): row for row in rows}
    if len(result) != len(rows):
        raise RuntimeError("duplicate persisted row ID")
    return result


def _changed(before: list[dict], after: list[dict]) -> dict:
    b, a = _rows_by_id(before), _rows_by_id(after)
    return {"added": sorted(set(a) - set(b)),
            "removed": sorted(set(b) - set(a)),
            "modified": sorted(key for key in set(a) & set(b) if a[key] != b[key])}


def state_diff(before: dict, after: dict) -> dict:
    if before["schema"] != SCHEMA or after["schema"] != SCHEMA:
        raise ValueError("persisted-state schema differs")
    if before["project_ids"] != after["project_ids"]:
        raise ValueError("world project roster changed")
    tables = {}
    for name in before["db"]:
        if name not in after["db"]:
            raise ValueError("persisted-state table missing")
        if name in ("issue_assignees",):
            # This table has no row ID; key by the immutable pair instead.
            b = {(r["issue_id"], r["user_id"]) for r in before["db"][name]}
            a = {(r["issue_id"], r["user_id"]) for r in after["db"][name]}
            tables[name] = {"added": sorted(a - b), "removed": sorted(b - a), "modified": []}
        else:
            tables[name] = _changed(before["db"][name], after["db"][name])
    changed_git = {pid: {"before": before["git"][pid], "after": after["git"][pid]}
                   for pid in before["git"] if before["git"][pid] != after["git"].get(pid)}
    return {"db": tables, "git_project_ids": sorted(map(int, changed_git)),
            "before_sha256": before["business_sha256"],
            "after_sha256": after["business_sha256"]}


def counts(snapshot: dict) -> dict:
    result = {name: len(rows) for name, rows in snapshot["db"].items()}
    result["projects_with_git_refs"] = len(snapshot["git"])
    return result


def verify_bootstrap(snapshot: dict) -> dict:
    project_count = len(snapshot["project_ids"])
    if project_count not in (30, 31):
        raise RuntimeError("GitLab project count is not an admitted bootstrap stage")
    expected = {"projects": project_count, "issues": project_count * 6,
                "members": project_count * 3,
                "merge_requests": project_count * 2,
                "projects_with_git_refs": project_count}
    actual = counts(snapshot)
    for name, value in expected.items():
        if actual[name] != value:
            raise RuntimeError(f"GitLab persisted {name} count {actual[name]} != {value}")
    if any(len(project["refs"]) != 3 for project in snapshot["git"].values()):
        raise RuntimeError("every project requires main and two MR branches")
    if actual["milestones"] != 0 or actual["issue_assignees"] != 0:
        raise RuntimeError("GitLab initial milestone or assignee state is not blank")
    return {"schema": "envloop-gitlab-real-world-readback-v1",
            "counts": actual, "business_sha256": snapshot["business_sha256"],
            "independent_postgresql_and_git_readback": True,
            "official_final_admitted": 0}


class QualificationError(ValueError):
    """Persisted state is incomplete, wrong, or regressed outside the target."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise QualificationError(reason)


def _context(task: dict) -> tuple[dict, dict]:
    world = bootstrap.world()
    matches = [project for project in bootstrap.all_projects(world)
               if project["full_path"] == task["project_family"]]
    if len(matches) != 1:
        raise ValueError("task project not found uniquely in private world")
    progress = json.loads(bootstrap.PROGRESS_FILE.read_text())["projects"][task["project_family"]]
    return matches[0], progress


def _table_delta(before: dict, after: dict, table: str) -> tuple[set[int], set[int], set[int]]:
    b = _rows_by_id(before["db"][table])
    a = _rows_by_id(after["db"][table])
    return set(a) - set(b), set(b) - set(a), {
        key for key in set(a) & set(b) if a[key] != b[key]}


def _unchanged_tables(before: dict, after: dict, *exceptions: str) -> None:
    for name in before["db"]:
        if name in exceptions:
            continue
        _require(before["db"][name] == after["db"][name],
                 f"unrelated persisted {name} changed")


def _unchanged_other_git(before: dict, after: dict, project_id: int,
                         *, allow_main: bool = False) -> None:
    target = str(project_id)
    for key, item in before["git"].items():
        if key != target:
            _require(after["git"].get(key) == item, "unrelated project Git state changed")
    if allow_main:
        b, a = before["git"][target], after["git"][target]
        _require({key: value for key, value in b["refs"].items() if key != "refs/heads/main"} ==
                 {key: value for key, value in a["refs"].items() if key != "refs/heads/main"},
                 "non-target Git ref changed")
        for path, digest in b["main_blobs_sha256"].items():
            if path not in ("docs/response-runbook.md", ".gitlab-ci.yml"):
                _require(a["main_blobs_sha256"].get(path) == digest,
                         "unrelated default-branch file changed")
    else:
        _require(before["git"][target] == after["git"].get(target),
                 "target project Git state changed unexpectedly")


def _issue(before: dict, project_id: int, iid: int) -> dict:
    matches = [row for row in before["db"]["issues"]
               if row["project_id"] == project_id and row["iid"] == iid]
    if len(matches) != 1:
        raise ValueError("issue identity not unique")
    return matches[0]


def _project_label_id(before: dict, project_id: int, title: str) -> int:
    labels = [row for row in before["db"]["labels"]
              if row["project_id"] == project_id and row["title"] == title]
    if len(labels) != 1:
        raise ValueError("policy label not seeded uniquely")
    return int(labels[0]["id"])


def _only_issue_fields(before: dict, after: dict,
                       allowed: dict[int, dict[str, object]]) -> None:
    b = _rows_by_id(before["db"]["issues"])
    a = _rows_by_id(after["db"]["issues"])
    _require(set(b) == set(a), "issue was added or deleted")
    for issue_id, old in b.items():
        expected = dict(old)
        expected.update(allowed.get(issue_id, {}))
        if a[issue_id] != expected:
            fields = sorted({*a[issue_id], *expected})
            changed = [name for name in fields
                       if a[issue_id].get(name) != expected.get(name)]
            raise QualificationError("issue fields differ from target/no-regression contract: "
                                     + ",".join(changed))


def _added_label_link(before: dict, after: dict, issue_id: int, label_id: int) -> None:
    b = _rows_by_id(before["db"]["issue_label_links"])
    a = _rows_by_id(after["db"]["issue_label_links"])
    _require(not (set(b) - set(a)), "existing label link removed")
    _require(all(a[key] == b[key] for key in b), "existing label link changed")
    new = [a[key] for key in set(a) - set(b)]
    _require(len(new) == 1 and new[0]["target_id"] == issue_id and
             new[0]["label_id"] == label_id, "wrong issue or priority label was added")


def _assign_exact(before: dict, after: dict, issue_id: int, user_id: int) -> None:
    b = {(row["issue_id"], row["user_id"])
         for row in before["db"]["issue_assignees"]}
    a = {(row["issue_id"], row["user_id"])
         for row in after["db"]["issue_assignees"]}
    _require(a == b | {(issue_id, user_id)}, "issue assignee changed incorrectly")


def _changed_paths(project_id: int, before_sha: str, after_sha: str) -> set[str]:
    result = _git(project_id, "diff", "--name-only", before_sha, after_sha)
    return set(result.decode().splitlines())


def evaluate_final_task(task: dict, before: dict, after: dict,
                        *, inspect_live_git: bool = True) -> dict:
    """Score one original final candidate using target and no-regression state.

    This is an oracle, not proof of GUI provenance or cold reset; admission
    additionally requires those separately bound receipts for this exact ID.
    """
    if task["partition"] != "final_candidate_unsealed":
        raise ValueError("this oracle covers original final candidates only")
    if before["schema"] != SCHEMA or after["schema"] != SCHEMA:
        raise ValueError("snapshot schema mismatch")
    if before["project_ids"] != after["project_ids"]:
        raise QualificationError("project roster changed")
    project, progress = _context(task)
    project_id = int(progress["project_id"])
    family = task["template_group"]
    active = _issue(before, project_id, int(progress["issue_iids"]["active"]))
    validation = _issue(before, project_id, int(progress["issue_iids"]["validation"]))
    try:
        _require(before["business_sha256"] != after["business_sha256"],
                 "candidate made no persisted business change")
        if family == "cross_record_issue_triage":
            _unchanged_tables(before, after, "issues", "issue_assignees", "issue_label_links")
            _unchanged_other_git(before, after, project_id)
            _only_issue_fields(before, after, {
                active["id"]: {"due_date": project["policy"]["issue_due"]}})
            _added_label_link(before, after, active["id"],
                              _project_label_id(before, project_id,
                                                task["oracle"]["expected_priority"]))
            _assign_exact(before, after, active["id"],
                          int(progress["user_ids"]["oncall"]))
        elif family == "release_milestone_coordination":
            _unchanged_tables(before, after, "issues", "milestones")
            _unchanged_other_git(before, after, project_id)
            new, removed, modified = _table_delta(before, after, "milestones")
            _require(len(new) == 1 and not removed and not modified,
                     "milestone creation changed another milestone")
            milestone = _rows_by_id(after["db"]["milestones"])[next(iter(new))]
            policy = project["policy"]
            _require(milestone["project_id"] == project_id and
                     milestone["title"] == policy["milestone_title"] and
                     milestone["start_date"] == policy["milestone_start"] and
                     milestone["due_date"] == policy["milestone_due"],
                     "milestone title, project, or dates incorrect")
            _only_issue_fields(before, after, {
                active["id"]: {"milestone_id": milestone["id"]},
                validation["id"]: {"milestone_id": milestone["id"]}})
        elif family == "approved_merge_request_merge":
            _unchanged_tables(before, after, "merge_requests")
            _unchanged_other_git(before, after, project_id, allow_main=True)
            approved_iid = int(progress["mr_iids"]["approved"])
            stale_iid = int(progress["mr_iids"]["stale"])
            b = {row["iid"]: row for row in before["db"]["merge_requests"]
                 if row["target_project_id"] == project_id}
            a = {row["iid"]: row for row in after["db"]["merge_requests"]
                 if row["target_project_id"] == project_id}
            _require(set(b) == set(a) and len(a) == 2 and a[stale_iid] == b[stale_iid],
                     "wrong MR or extra MR changed")
            _require(a[approved_iid]["state_id"] == 3 and
                     a[approved_iid]["merge_commit_sha"] is not None,
                     "approved MR is not persisted as merged")
            _require(before["git"][str(project_id)]["refs"]["refs/heads/main"] !=
                     after["git"][str(project_id)]["refs"]["refs/heads/main"],
                     "default branch did not advance")
            if inspect_live_git:
                old = before["git"][str(project_id)]["refs"]["refs/heads/main"]
                new_sha = after["git"][str(project_id)]["refs"]["refs/heads/main"]
                _require(_changed_paths(project_id, old, new_sha) ==
                         {"docs/response-runbook.md"}, "MR changed unexpected Git files")
                content = git_blob(project_id, "main", "docs/response-runbook.md").decode()
                _require(content == project["files"]["docs/response-runbook.md"] +
                         "\n" + f"Approved remediation evidence for {task['oracle']['cve']} "
                         f"on {project['asset_id']}-1.\n",
                         "merged content differs from approved source")
        elif family == "least_privilege_access_handoff":
            _unchanged_tables(before, after, "members")
            _unchanged_other_git(before, after, project_id)
            old_id = int(progress["user_ids"]["contractor"])
            new_id = int(progress["user_ids"]["incoming"])
            b, a = (_rows_by_id(snapshot["db"]["members"])
                    for snapshot in (before, after))
            removed = [b[member_id] for member_id in set(b) - set(a)]
            added = [a[member_id] for member_id in set(a) - set(b)]
            _require(len(removed) == len(added) == 1 and
                     removed[0]["source_id"] == project_id and
                     removed[0]["user_id"] == old_id and
                     added[0]["source_id"] == project_id and
                     added[0]["user_id"] == new_id and
                     added[0]["access_level"] == 20 and
                     added[0]["expires_at"] == project["policy"]["access_expiry"] and
                     all(b[key] == a[key] for key in set(b) & set(a)),
                     "ACL handoff incomplete, overprivileged, or regressed")
        elif family == "ci_and_runbook_reconciliation":
            _unchanged_tables(before, after)
            _unchanged_other_git(before, after, project_id, allow_main=True)
            old_sha = before["git"][str(project_id)]["refs"]["refs/heads/main"]
            new_sha = after["git"][str(project_id)]["refs"]["refs/heads/main"]
            _require(old_sha != new_sha, "default Git branch did not advance")
            if inspect_live_git:
                _require(_changed_paths(project_id, old_sha, new_sha) ==
                         {".gitlab-ci.yml", "docs/response-runbook.md"},
                         "CI/runbook task changed unexpected files")
                expected_ci = project["files"][".gitlab-ci.yml"].replace(
                    "    - when: never\n",
                    "    - if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'\n")
                expected_runbook = project["files"]["docs/response-runbook.md"].replace(
                    "Current contact: pending",
                    "Current contact: @" + project["principals"]["oncall"])
                _require(git_blob(project_id, "main", ".gitlab-ci.yml").decode() == expected_ci and
                         git_blob(project_id, "main", "docs/response-runbook.md").decode() ==
                         expected_runbook, "CI rule or runbook contact is incorrect")
        else:
            raise ValueError("unknown final template family")
        return {"task_id": task["task_id"], "score": 1.0,
                "persisted_oracle": True, "no_regression": True,
                "before_business_sha256": before["business_sha256"],
                "after_business_sha256": after["business_sha256"]}
    except QualificationError as exc:
        return {"task_id": task["task_id"], "score": 0.0,
                "persisted_oracle": True, "no_regression": False,
                "failure_code": str(exc),
                "before_business_sha256": before["business_sha256"],
                "after_business_sha256": after["business_sha256"]}


def save_baseline(snapshot: dict) -> Path:
    path = runtime.PRIVATE / "baseline-persisted-state.json"
    factory.write_private(path, snapshot)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "verify-bootstrap", "save-baseline"])
    args = parser.parse_args()
    snapshot = state_snapshot()
    if args.action == "snapshot":
        result = {"schema": snapshot["schema"], "counts": counts(snapshot),
                  "business_sha256": snapshot["business_sha256"]}
    else:
        result = verify_bootstrap(snapshot)
        if args.action == "save-baseline":
            save_baseline(snapshot)
            result["baseline_saved_private"] = True
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
