"""Read-only post-terminal audit of the original GitLab v6 TRAIN diagnostic.

This auditor writes only a separate forensic receipt. It never creates a
supervisor result, publishes the original outcome, replays an intent, or
changes Docker. Private task, issue, label, and credential values stay out of
the public receipt.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys


PLAN_SHA256 = "8355a85d2401428ee1bb3065fd989f6e8cad85e1bcd4a15cc7c60422022b1940"
PUBLIC_PLAN_SHA256 = "d758ae8763eb72a0cb96c6baf580e24c3bb1481f6aed30d0412be4511a4e6e4a"
INTENT_SHA256 = "494baa19276ff6ebff359a0ed072b16567cd6751470b4e83816c2c57d1195470"
CHILD_SHA256 = "c75054b916be7afb010dc9f924f87b32c86c9be43c29a390e29a7caf19230d54"
PREHARDENING_SHA256 = "b2f85e99f80060778d461ce84b1ca8792cdbc8a524cfc5f2cd879a4b6bce415c"
HARDENING_SHA256 = "90fbd5cd179c3e2266b313db176ded5f173ca43ad52d5b31a7fd8e7d6cbaac69"
CASE_VARIANTS = ("active", "historical_duplicate", "active")
EXPECTED_SCORES = (1.0, 0.0, 1.0)
SOURCE_FILES = (
    "gitlab_world/v066_new_train_diagnostic_v6.py",
    "tests/test_gitlab_v066_new_train_diagnostic_v6.py",
    "docs/FULL_STUDY_GITLAB_V066_NEW_TRAIN_DIAGNOSTIC_V6_2026-09-30.md",
    "gitlab_world/gui_controls.py", "gitlab_world/operators.py",
    "gitlab_world/factory.py", "gitlab_world/bootstrap.py",
    "gitlab_world/train_teacher_oracle_v066.py",
    "gitlab_world/v066_train_gui_pair.py",
    "gitlab_world/v066_train_target_shape_v1.py",
    "gitlab_world/verify.py", "gitlab_world/reset.py",
    "gitlab_world/runtime.py", "gitlab_world/v066_boot_only_probe_v5.py",
)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def private(path: Path) -> tuple[bytes, dict]:
    need(path.is_file() and not path.is_symlink() and
         path.stat().st_mode & 0o077 == 0,
         "private_forensic_file_absent_or_permissive")
    raw = path.read_bytes()
    return raw, json.loads(raw)


def _within(root: Path, relative: str) -> Path:
    need(type(relative) is str and relative and not relative.startswith("/"),
         "forensic_relative_path_invalid")
    original = root / relative
    path = original.resolve()
    need(not original.is_symlink() and
         path.is_relative_to(root.resolve()) and not path.is_symlink(),
         "forensic_path_outside_private_root")
    return path


def source_and_intent(repo: Path, root: Path) -> tuple[dict, dict, dict, dict]:
    plan_raw, plan = private(root / "source-freeze.private.json")
    intent_raw, intent = private(root / "intent.private.json")
    child_raw, child = private(root / "child-result.private.json")
    need(digest(plan_raw) == PLAN_SHA256 and
         digest(intent_raw) == INTENT_SHA256 and
         digest(child_raw) == CHILD_SHA256,
         "frozen_train_plan_intent_or_child_sha_changed")
    pub_raw = (repo / "docs/evidence/"
               "gitlab-v066-new-train-diagnostic-v6-source-freeze-2026-09-30.json").read_bytes()
    public = json.loads(pub_raw)
    need(digest(pub_raw) == PUBLIC_PLAN_SHA256 and
         public.get("private_plan_sha256") == PLAN_SHA256 and
         set(plan.get("source_sha256s", {})) == set(SOURCE_FILES) and
         all(digest((repo / name).read_bytes()) == plan["source_sha256s"][name]
             for name in SOURCE_FILES) and
         plan.get("source_bundle_sha256") == digest(canonical(plan["source_sha256s"])) and
         plan.get("original_baseline_sha256") == digest((repo /
             "work/gitlab-full-world/baseline-persisted-state.json").read_bytes()) and
         plan.get("original_world_sha256") == digest((repo /
             "work/gitlab-full-world/world-private.json").read_bytes()) and
         plan.get("selected_train_ordinal") == 2 and
         plan.get("same_failed_final_identity_replay_authorized") is False and
         plan.get("provider_calls") == plan.get("official_final_admitted") == 0 and
         intent.get("schema") ==
             "envloop-gitlab-v066-new-train-diagnostic-v6-private-intent-v1" and
         intent.get("source_freeze_sha256") == PLAN_SHA256 and
         intent.get("reviewed_public_freeze_sha256") == PUBLIC_PLAN_SHA256 and
         intent.get("intent_nonce") == plan.get("intent_nonce") and
         intent.get("intent_nonce_sha256") == plan.get("intent_nonce_sha256") and
         intent.get("train_task_id") == plan.get("train_task_id") and
         intent.get("partition") == "train" and
         intent.get("same_failed_final_identity_replay_authorized") is False and
         intent.get("provider_calls") == intent.get("selection_or_final_tasks_dispatched") == 0 and
         child.get("schema") ==
             "envloop-gitlab-v066-new-train-diagnostic-v6-private-child-v1" and
         child.get("status") == "three_train_gui_cases_saved_and_exactly_reset" and
         child.get("source_freeze_sha256") == PLAN_SHA256 and
         child.get("intent_sha256") == INTENT_SHA256 and
         child.get("intent_nonce_sha256") == plan.get("intent_nonce_sha256") and
         child.get("train_task_package_sha256") == plan.get("train_task_package_sha256") and
         child.get("completed_cases") == 3 and
         child.get("scores") == list(EXPECTED_SCORES) and
         len(child.get("case_receipt_sha256s", [])) == 3 and
         child.get("provider_calls") == child.get("selection_or_final_tasks_dispatched") ==
             child.get("official_final_admitted") == 0,
         "train_source_identity_or_child_claim_changed")
    world = json.loads((repo / "work/gitlab-full-world/world-private.json").read_bytes())
    matches = [task for task in world["tasks"]
               if task["task_id"] == plan["train_task_id"]]
    need(len(matches) == 1 and matches[0]["partition"] == "train" and
         digest(canonical(matches[0])) == plan["train_task_package_sha256"],
         "train_partition_or_package_changed")
    return plan, intent, child, matches[0]


def saved_case_trio(repo: Path, root: Path, child: dict, task: dict) -> dict:
    baseline = json.loads((repo / "work/gitlab-full-world/"
                           "baseline-persisted-state.json").read_bytes())
    progress = json.loads((repo / "work/gitlab-full-world/"
                           "bootstrap-progress.json").read_bytes())
    project = progress["projects"][task["project_family"]]
    project_id = int(project["project_id"])
    issue_iids = project["issue_iids"]
    matches = [row for row in baseline["db"]["labels"]
               if int(row["project_id"]) == project_id and
               row["title"] == task["oracle"]["expected_priority"]]
    need(len(matches) == 1, "train_priority_label_not_unique")
    label_id = int(matches[0]["id"])
    target_ids = set()
    for variant in ("active", "historical_duplicate"):
        issue_matches = [row for row in baseline["db"]["issues"]
                         if int(row["project_id"]) == project_id and
                         int(row["iid"]) == int(issue_iids[variant])]
        need(len(issue_matches) == 1, "train_scored_issue_not_unique")
        target_ids.add(int(issue_matches[0]["id"]))
    need(len(target_ids) == 2 and not any(
        int(row["target_id"]) in target_ids and int(row["label_id"]) == label_id
        for row in baseline["db"]["issue_label_links"]),
        "train_baseline_already_has_priority_label_on_scored_issue")
    results = []
    generations = []
    screenshot_count = 0
    raw_log_count = 0
    for index, expected in enumerate(EXPECTED_SCORES):
        folder = root / "cases" / f"{index:02d}-{('positive-1', 'wrong-historical-issue', 'positive-2')[index]}"
        receipt_raw, receipt = private(folder / "case-receipt.private.json")
        before_raw, before = private(folder / "before.private.json")
        after_raw, after = private(folder / "after.private.json")
        restored_raw, restored = private(folder / "restored.private.json")
        need(digest(receipt_raw) == child["case_receipt_sha256s"][index] and
             receipt.get("case_index") == index and
             receipt.get("issue_variant") == CASE_VARIANTS[index] and
             receipt.get("expected_score") == expected and
             receipt.get("schema") ==
                "envloop-gitlab-v066-new-train-diagnostic-v6-private-case-v1" and
             receipt.get("error_type") is None and
             receipt.get("before_sha256") == digest(before_raw) and
             receipt.get("after_sha256") == digest(after_raw) and
             receipt.get("restored_sha256") == digest(restored_raw) and
             before == baseline and restored == baseline and
             receipt.get("restored_exact") is True and
             receipt.get("reset_receipt", {}).get("cold_reset") is True and
             receipt["reset_receipt"].get("same_business_sha256") is True and
             receipt["reset_receipt"].get("container_identity_changed") is True and
             receipt.get("score", {}).get("score") == expected and
             receipt["score"].get("independent_no_regression_checked") is True and
             receipt["score"].get("target_or_controlled_wrong_object_verified") is True and
             receipt.get("provider_calls") == receipt.get("official_final_admitted") == 0,
             "train_case_saved_score_or_reset_receipt_changed")
        structural = {name: value for name, value in after.items()
                      if name != "business_sha256"}
        need(digest(canonical(structural)) == after.get("business_sha256") and
             before["git"] == after["git"] and
             before["project_ids"] == after["project_ids"] and
             before["schema"] == after["schema"] and
             all(before["db"][name] == after["db"][name]
                 for name in before["db"] if name != "issue_label_links"),
             "train_saved_git_or_unrelated_postgres_state_changed")
        old_links = {int(row["id"]): row for row in before["db"]["issue_label_links"]}
        new_links = {int(row["id"]): row for row in after["db"]["issue_label_links"]}
        added = set(new_links) - set(old_links)
        need(len(added) == 1 and not (set(old_links) - set(new_links)) and
             all(new_links[key] == row for key, row in old_links.items()),
             "train_label_link_not_exact_one_addition")
        new_link = new_links[next(iter(added))]
        issue_matches = [row for row in before["db"]["issues"]
                         if int(row["project_id"]) == project_id and
                         int(row["iid"]) == int(issue_iids[CASE_VARIANTS[index]])]
        need(len(issue_matches) == 1 and
             int(new_link["target_id"]) == int(issue_matches[0]["id"]) and
             int(new_link["label_id"]) == label_id,
             "train_wrong_or_active_issue_link_delta_changed")
        active_matches = [row for row in before["db"]["issues"]
                          if int(row["project_id"]) == project_id and
                          int(row["iid"]) == int(issue_iids["active"])]
        need(len(active_matches) == 1 and
             (int(new_link["target_id"]) == int(active_matches[0]["id"])) ==
                (expected == 1.0),
             "train_saved_state_label_score_not_rederived")
        gui = receipt.get("gui") or {}
        screenshots = gui.get("screenshots_sha256") or {}
        need(gui.get("saved_visible_after_reload") is True and
             gui.get("fresh_browser_context") is True and
             set(screenshots) == {"policy.png", "issue-before.png", "issue-after.png"},
             "train_gui_reload_or_screenshot_set_changed")
        for filename, expected_sha in screenshots.items():
            path = folder / filename
            need(path.is_file() and digest(path.read_bytes()) == expected_sha,
                 "train_raw_gui_screenshot_changed")
            screenshot_count += 1
        forensic = receipt.get("forensics") or {}
        need(forensic.get("raw_startup_logs_saved") is True and
             forensic.get("state_only_inspect_saved") is True,
             "train_raw_startup_forensics_not_saved")
        for key, filename in (
            ("docker_logs_stdout", "docker-logs.stdout.private.log"),
            ("docker_logs_stderr", "docker-logs.stderr.private.log"),
            ("docker_state_stdout", "docker-state.stdout.private.json"),
            ("docker_state_stderr", "docker-state.stderr.private.log"),
        ):
            path = folder / filename
            raw, _unused = (private(path) if path.suffix == ".json" else
                            (path.read_bytes(), None))
            need(path.is_file() and not path.is_symlink() and
                 path.stat().st_mode & 0o077 == 0 and
                 len(raw) == forensic["raw_file_bytes"][key] and
                 digest(raw) == forensic["raw_file_sha256s"][key],
                 "train_raw_docker_log_or_state_bytes_changed")
            raw_log_count += 1
        state = json.loads((folder / "docker-state.stdout.private.json").read_bytes())
        need(state.get("Status") == "running" and state.get("ExitCode") == 0 and
             state.get("OOMKilled") is False and
             state.get("Health", {}).get("Status") == "healthy",
             "train_post_reset_saved_docker_state_not_healthy")
        results.append(expected)
        generations.append(receipt["reset_receipt"]["generation"])
    need(results == list(EXPECTED_SCORES) and
         generations == list(range(generations[0], generations[0] + 3)),
         "train_case_scores_or_reset_generations_changed")
    return {"scores": results, "screenshots": screenshot_count,
            "raw_docker_log_and_state_files": raw_log_count,
            "reset_generation_count": len(generations)}


def permissions_and_hardening(root: Path) -> dict:
    before_raw, before = private(root / "prehardening-mode-manifest.private.json")
    after_raw, after = private(root / "screenshot-mode-hardening.private.json")
    need(digest(before_raw) == PREHARDENING_SHA256 and
         digest(after_raw) == HARDENING_SHA256 and
         before.get("schema") ==
             "envloop-gitlab-v066-new-train-v6-prehardening-mode-manifest-private-v1" and
         before.get("intent_sha256") == INTENT_SHA256 and
         before.get("child_result_sha256") == CHILD_SHA256 and
         before.get("source_public_sha256") == PUBLIC_PLAN_SHA256 and
         before.get("original_supervisor_receipt_absent") is True and
         after.get("schema") ==
             "envloop-gitlab-v066-new-train-v6-screenshot-mode-hardening-private-v1" and
         after.get("before_manifest_sha256") == PREHARDENING_SHA256 and
         after.get("same_intent_replay_authorized") is False and
         after.get("model_calls") == after.get("official_final_admitted") == 0,
         "train_original_permission_snapshot_or_hardening_receipt_changed")
    recorded_before = datetime.fromisoformat(before["recorded_utc"])
    recorded_after = datetime.fromisoformat(after["recorded_utc"])
    need(recorded_before.tzinfo is not None and
         recorded_after.tzinfo is not None and
         recorded_before < recorded_after,
         "train_pre_and_post_hardening_timestamps_reversed")
    rows = before.get("rows", [])
    fixed = after.get("files", [])
    need(len(rows) == 36 and len(fixed) == 9 and
         len({row["path"] for row in rows}) == 36 and
         len({row["path"] for row in fixed}) == 9,
         "train_forensic_tree_or_hardening_denominator_changed")
    old_pngs = {row["path"] for row in rows
                if row.get("mode_octal") == "0o644"}
    fixed_paths = {row["path"] for row in fixed}
    need(len(old_pngs) == 9 and old_pngs == fixed_paths and
         all(path.endswith(".png") for path in old_pngs),
         "train_nine_original_permissive_files_not_exact_png_set")
    for item in fixed:
        need(item.get("before_mode") == "0644" and
             item.get("after_mode") == "0600",
             "train_screenshot_hardening_mode_transition_changed")
    fixed_by_path = {item["path"]: item for item in fixed}
    for row in rows:
        path = _within(root, row["path"])
        need(path.exists() and
             row.get("type") == ("directory" if path.is_dir() else "file") and
             not path.is_symlink(),
             "train_forensic_artifact_type_changed")
        if path.is_dir():
            need(row.get("mode_octal") == "0o700" and
                 path.stat().st_mode & 0o777 == 0o700,
                 "train_private_case_directory_changed")
        else:
            raw = path.read_bytes()
            need(len(raw) == row.get("bytes") and
                 digest(raw) == row.get("sha256"),
                 "train_post_hardening_file_bytes_changed")
            if row["path"] in fixed_paths:
                need(path.stat().st_mode & 0o777 == 0o600 and
                     fixed_by_path[row["path"]].get("sha256") == digest(raw),
                     "train_exact_nine_screenshot_hardening_not_preserved")
            else:
                need(row.get("mode_octal") == "0o600" and
                     path.stat().st_mode & 0o777 == 0o600,
                     "train_other_private_artifact_mode_changed")
    actual = {str(path.relative_to(root)) for path in (root / "cases").rglob("*")}
    need(actual == {row["path"] for row in rows},
         "train_case_tree_extra_or_missing_artifact")
    return {"prehardening_artifacts": len(rows),
            "original_permissive_screenshots": len(old_pngs),
            "hardened_screenshot_bytes_unchanged": True}


def process_and_live_baseline(repo: Path, ratification: Path) -> dict:
    listing = subprocess.run(["ps", "-axo", "pid=,command="],
                             capture_output=True, text=True,
                             timeout=10, check=True).stdout.splitlines()
    pattern = re.compile(r"(?:^|\s)-m\s+gitlab_world\.v066_new_train_diagnostic_v6(?:\s|$)")
    need(not any(pattern.search(row) for row in listing),
         "original_train_diagnostic_process_still_running")
    script = ("from pathlib import Path; "
              "from gitlab_world import v066_requalified_continuation_v1 as t; "
              "from gitlab_world import prospective_final_controls_v066 as l; "
              "old=t.validate_freeze(Path(__import__('sys').argv[1]))[1]['old']; "
              "l.assert_live_world(old); print('exact_baseline')")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src") + os.pathsep + str(repo)
    result = subprocess.run(
        [sys.executable, "-c", script,
         str(ratification)], cwd=repo, env=env,
        capture_output=True, text=True, timeout=180)
    need(result.returncode == 0 and result.stdout.strip() == "exact_baseline",
         "live_original_gitlab_baseline_not_exact")
    return {"matching_original_processes": 0,
            "live_original_postgres_and_git_exact_baseline": True}


def audit(*, repo: Path, ratification: Path, check_live: bool = True) -> dict:
    root = repo / "work/gitlab-full-world/v066-new-train-diagnostic-v6-20260930"
    need(repo.is_absolute() and root.is_dir() and not root.is_symlink(),
         "original_gitlab_private_train_root_absent")
    plan, intent, child, task = source_and_intent(repo, root)
    need(not (root / "supervisor-result.private.json").exists() and
         not (repo / "docs/evidence/"
              "gitlab-v066-new-train-diagnostic-v6-outcome-2026-09-30.json").exists(),
         "original_supervisor_or_public_outcome_unexpectedly_exists")
    saved = saved_case_trio(repo, root, child, task)
    hardening = permissions_and_hardening(root)
    stdout_raw, stdout = private(root / "child.stdout.private.log")
    stderr_path = root / "child.stderr.private.log"
    need(stderr_path.is_file() and not stderr_path.is_symlink() and
         stderr_path.stat().st_mode & 0o077 == 0,
         "train_child_stderr_not_private")
    stderr_raw = stderr_path.read_bytes()
    need(stdout.get("status") == child["status"] and
         stdout.get("child_result_sha256") == CHILD_SHA256 and
         stderr_raw == b"" and
         intent.get("same_failed_final_identity_replay_authorized") is False,
         "train_child_terminal_stdout_or_stderr_changed")
    live = (process_and_live_baseline(repo, ratification) if check_live else
            {"matching_original_processes": None,
             "live_original_postgres_and_git_exact_baseline": None})
    return {
        "schema": "envloop-gitlab-v066-new-train-v6-post-terminal-forensic-public-v1",
        "status": "child_trio_reopened_supervisor_completion_missing_no_replay",
        "source_freeze_public_sha256": PUBLIC_PLAN_SHA256,
        "source_freeze_private_sha256": PLAN_SHA256,
        "one_use_intent_sha256": INTENT_SHA256,
        "child_result_private_sha256": CHILD_SHA256,
        "prehardening_mode_manifest_sha256": PREHARDENING_SHA256,
        "screenshot_hardening_receipt_sha256": HARDENING_SHA256,
        "child_stdout_sha256": digest(stdout_raw),
        "child_stderr_sha256": digest(stderr_raw),
        "partition": "train",
        "saved_child_case_scores": saved["scores"],
        "saved_child_case_count": len(saved["scores"]),
        "gui_screenshots_reopened": saved["screenshots"],
        "raw_docker_log_and_state_files_reopened":
            saved["raw_docker_log_and_state_files"],
        "fresh_exact_reset_generations": saved["reset_generation_count"],
        "all_before_and_restored_postgres_git_states_equal_frozen_baseline": True,
        "only_one_scoped_label_link_changed_per_gui_case": True,
        "prehardening_artifact_entries": hardening["prehardening_artifacts"],
        "prehardening_permissive_pngs": hardening["original_permissive_screenshots"],
        "nine_pngs_mode_hardened_to_0600_bytes_unchanged": True,
        "original_supervisor_result_present": False,
        "original_public_outcome_present": False,
        "supervisor_success_claim_authorized": False,
        "matching_original_processes_at_audit": live["matching_original_processes"],
        "live_original_postgres_git_exact_baseline":
            live["live_original_postgres_and_git_exact_baseline"],
        "same_intent_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "model_calls": 0,
        "official_final_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.public_out.exists() or args.public_out.is_symlink():
        raise ValueError("Exclusive separate forensic receipt required")
    result = audit(repo=args.repo.resolve(),
                   ratification=args.ratification_private.resolve())
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"],
                      "public_sha256": digest(raw),
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
