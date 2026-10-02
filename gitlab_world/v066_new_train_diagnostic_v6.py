"""One-use, new-identity TRAIN GUI diagnostic on original GitLab CE.

The source is frozen before any intent. A later explicit run executes only a
TRAIN-partition, evaluator-operated 1/0/1 label edit. It preserves the old
terminal final-task failure and never calls a student model or admits a final
task. Raw Docker startup logs and State-only inspect bytes stay private.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from . import bootstrap, factory, gui_controls, operators, reset, runtime
from . import train_teacher_oracle_v066 as oracle, verify
from . import prospective_final_controls_v066 as lane
from . import v066_boot_only_probe_v5 as boot
from . import v066_infra_recovery_v4 as replacement
from . import v066_infra_requalification_v1 as recovery
from . import v066_requalified_continuation_v1 as terminal
from . import v066_supervised_final_one_v1 as one
from . import v066_train_gui_pair as first_train
from . import v066_train_target_shape_v1 as second_train


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = runtime.PRIVATE
RUN = PRIVATE_ROOT / "v066-new-train-diagnostic-v6-20260930"
CASES_DIR = RUN / "cases"
PLAN = RUN / "source-freeze.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-new-train-diagnostic-v6-source-freeze-2026-09-30.json"
INTENT = RUN / "intent.private.json"
CHILD_RESULT = RUN / "child-result.private.json"
SUPERVISOR_RESULT = RUN / "supervisor-result.private.json"
PUBLIC_RESULT = ROOT / "docs/evidence/gitlab-v066-new-train-diagnostic-v6-outcome-2026-09-30.json"
PARENT_BOOT_AUDIT = ROOT / "docs/evidence/gitlab-v066-boot-only-probe-v5-independent-audit-2026-09-30.json"
PARENT_BOOT_AUDIT_SHA256 = "3f676a808ff446648c5bea132704952734c1ee9df4886814c963cd7d8be3ef96"
CASES = (("positive-1", "active", 1.0),
         ("wrong-historical-issue", "historical_duplicate", 0.0),
         ("positive-2", "active", 1.0))
SELECTED_TRAIN_ORDINAL = 2
WALL_SECONDS = 3600
GRACE_SECONDS = 30
PLAN_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-private-plan-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-public-plan-v1"
INTENT_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-private-intent-v1"
CASE_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-private-case-v1"
CHILD_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-private-child-v1"
SUPERVISOR_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-private-supervisor-v1"
PUBLIC_RESULT_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v6-public-outcome-v1"
SOURCE_FILES = (
    "gitlab_world/v066_new_train_diagnostic_v6.py",
    "tests/test_gitlab_v066_new_train_diagnostic_v6.py",
    "docs/FULL_STUDY_GITLAB_V066_NEW_TRAIN_DIAGNOSTIC_V6_2026-09-30.md",
    "gitlab_world/gui_controls.py",
    "gitlab_world/operators.py",
    "gitlab_world/factory.py",
    "gitlab_world/bootstrap.py",
    "gitlab_world/train_teacher_oracle_v066.py",
    "gitlab_world/v066_train_gui_pair.py",
    "gitlab_world/v066_train_target_shape_v1.py",
    "gitlab_world/verify.py",
    "gitlab_world/reset.py",
    "gitlab_world/runtime.py",
    "gitlab_world/v066_boot_only_probe_v5.py",
)


class DiagnosticError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DiagnosticError(code)


def _source_hashes() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _private_json(path: Path) -> tuple[dict, str]:
    return one.private_json(path)


def select_train_task() -> tuple[dict, str]:
    """Select one previously unused TRAIN identity, never a final ID."""
    require(bootstrap.WORLD_FILE.is_file() and
            bootstrap.WORLD_FILE.stat().st_mode & 0o077 == 0,
            "original_private_train_world_missing")
    world = json.loads(bootstrap.WORLD_FILE.read_bytes())
    train = [row for row in world["tasks"] if row["partition"] == "train"]
    matches = sorted((row for row in train
                      if row["template_group"] == "issue_label_from_alert"),
                     key=lambda row: row["task_id"])
    require(len(train) == 20 and len(matches) == 5,
            "train_label_roster_changed")
    task = matches[SELECTED_TRAIN_ORDINAL]
    first, _first_binding = first_train._train_task()
    second, _second_binding = second_train.second_train_task()
    require(task["partition"] == "train" and
            task["task_id"] not in {first["task_id"], second["task_id"]} and
            task["project_family"] not in {
                first["project_family"], second["project_family"]} and
            task["source_family"] not in {
                first["source_family"], second["source_family"]},
            "new_train_identity_replays_prior_paid_train_task")
    v4, _v4_sha = _private_json(replacement.PRIVATE_PLAN)
    require(task["task_id"] not in {
                row["task_id"] for row in v4["candidate_roster"]} and
            one.sha(task["source_family"].encode()) not in {
                row["source_family_sha256"] for row in
                v4["candidate_roster"]},
            "train_diagnostic_overlaps_final_replacement_cohort")
    project, progress = verify._context(task)
    baseline = json.loads((PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes())
    project_id = int(progress["project_id"])
    label_id = verify._project_label_id(
        baseline, project_id, task["oracle"]["expected_priority"])
    target_issue_ids = {
        int(verify._issue(baseline, project_id,
                          int(progress["issue_iids"][key]))["id"])
        for key in ("active", "historical_duplicate")}
    require(project["partition"] == "train" and
            not any(int(row["target_id"]) in target_issue_ids and
                    int(row["label_id"]) == label_id
                    for row in baseline["db"]["issue_label_links"]),
            "new_train_label_target_already_present_in_baseline")
    return task, factory.sha256(factory.canonical(task))


def _parent_binding(ratification_private: Path) -> dict:
    require(PARENT_BOOT_AUDIT.is_file() and
            one.sha(PARENT_BOOT_AUDIT.read_bytes()) ==
            PARENT_BOOT_AUDIT_SHA256,
            "reviewed_boot_only_independent_audit_missing_or_changed")
    boot_report = json.loads(PARENT_BOOT_AUDIT.read_bytes())
    current = boot.audit(ratification_private)
    prior = terminal.audit(ratification_private)
    require(boot_report.get("status") ==
            "separate_read_only_saved_forensics_audit_passed_boot_only" and
            boot_report.get("completed_boot_only_clones") == 3 and
            boot_report.get("selection_or_final_tasks_dispatched") == 0 and
            boot_report.get("model_calls") ==
            boot_report.get("official_final_admitted") == 0 and
            current.get("status") == "three_boot_only_clones_exact_baseline" and
            current.get("completed_boot_clones") == 3 and
            current.get("final_world_exact_baseline") is True and
            current.get("task_intents") == 0 and
            prior.get("status") == "terminal_failure_no_replay" and
            prior.get("completed_current_controls") == 13 and
            prior.get("pending_batch") is False and
            prior.get("pending_id") is False and
            prior.get("official_final_admitted") == 0,
            "boot_only_success_or_terminal_no_replay_boundary_changed")
    return boot_report


def _public_plan(private: dict, private_sha: str) -> dict:
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_new_train_diagnostic_no_gui_attempt_yet",
        "private_plan_sha256": private_sha,
        "source_bundle_sha256": private["source_bundle_sha256"],
        "parent_boot_independent_audit_sha256":
            private["parent_boot_independent_audit_sha256"],
        "intent_nonce_sha256": private["intent_nonce_sha256"],
        "partition": "train",
        "selected_new_train_identity": True,
        "original_evaluator_checkout_only": True,
        "planned_gui_case_scores": [1.0, 0.0, 1.0],
        "planned_fresh_cold_resets": 3,
        "child_watchdog_seconds": WALL_SECONDS,
        "raw_startup_logs_private_before_cleanup_required": True,
        "same_failed_final_identity_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }


def freeze(ratification_private: Path) -> dict:
    require(not PLAN.exists() and not PUBLIC_PLAN.exists() and
            not INTENT.exists() and not CASES_DIR.exists(),
            "fresh_new_train_diagnostic_epoch_required")
    _parent_binding(ratification_private)
    task, package_sha = select_train_task()
    acl = first_train._acl_and_split_evidence()
    sources = _source_hashes()
    nonce = secrets.token_hex(32)
    private = {
        "schema": PLAN_SCHEMA,
        "status": "source_frozen_new_train_diagnostic_no_gui_attempt_yet",
        "source_sha256s": sources,
        "source_bundle_sha256": one.sha(one.canonical(sources)),
        "parent_boot_independent_audit_sha256":
            one.sha(PARENT_BOOT_AUDIT.read_bytes()),
        "ratification_private_sha256": one.sha(ratification_private.read_bytes()),
        "original_world_sha256": one.sha(bootstrap.WORLD_FILE.read_bytes()),
        "original_baseline_sha256": one.sha(
            (PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes()),
        "train_task_id": task["task_id"],
        "train_task_package_sha256": package_sha,
        "train_task_source_family_sha256":
            one.sha(task["source_family"].encode()),
        "train_acl_and_split_evidence": acl,
        "selected_train_ordinal": SELECTED_TRAIN_ORDINAL,
        "intent_nonce": nonce,
        "intent_nonce_sha256": one.sha(nonce.encode()),
        "child_watchdog_seconds": WALL_SECONDS,
        "same_failed_final_identity_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }
    RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(RUN.stat().st_mode & 0o077 == 0,
            "new_train_diagnostic_private_directory_permissive")
    digest = one.write_new(PLAN, private)
    public = _public_plan(private, digest)
    one.write_new(PUBLIC_PLAN, public, 0o644)
    return public


def validate_freeze(ratification_private: Path) -> tuple[dict, str, dict]:
    _parent_binding(ratification_private)
    task, package_sha = select_train_task()
    acl = first_train._acl_and_split_evidence()
    plan, plan_sha = _private_json(PLAN)
    sources = _source_hashes()
    require(plan.get("schema") == PLAN_SCHEMA and
            plan.get("status") ==
            "source_frozen_new_train_diagnostic_no_gui_attempt_yet" and
            plan.get("source_sha256s") == sources and
            plan.get("source_bundle_sha256") == one.sha(one.canonical(sources)) and
            plan.get("parent_boot_independent_audit_sha256") ==
            one.sha(PARENT_BOOT_AUDIT.read_bytes()) and
            plan.get("ratification_private_sha256") ==
            one.sha(ratification_private.read_bytes()) and
            plan.get("original_world_sha256") ==
            one.sha(bootstrap.WORLD_FILE.read_bytes()) and
            plan.get("original_baseline_sha256") ==
            one.sha((PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes()) and
            plan.get("train_task_id") == task["task_id"] and
            plan.get("train_task_package_sha256") == package_sha and
            plan.get("train_task_source_family_sha256") ==
            one.sha(task["source_family"].encode()) and
            plan.get("train_acl_and_split_evidence") == acl and
            plan.get("selected_train_ordinal") == SELECTED_TRAIN_ORDINAL and
            isinstance(plan.get("intent_nonce"), str) and
            len(plan["intent_nonce"]) == 64 and
            plan.get("intent_nonce_sha256") ==
            one.sha(plan["intent_nonce"].encode()) and
            plan.get("child_watchdog_seconds") == WALL_SECONDS and
            plan.get("same_failed_final_identity_replay_authorized") is False and
            plan.get("provider_calls") ==
            plan.get("selection_or_final_tasks_dispatched") ==
            plan.get("official_final_admitted") == 0 and
            json.loads(PUBLIC_PLAN.read_bytes()) == _public_plan(plan, plan_sha),
            "new_train_diagnostic_source_or_private_identity_changed")
    return plan, plan_sha, task


def score_saved_case(task: dict, before: dict, after: dict,
                     *, negative: bool) -> dict:
    """Independent persisted-state score, including exact wrong-object delta."""
    scored = oracle.evaluate_train_task(task, before, after)
    require(scored.get("reward") == (0.0 if negative else 1.0),
            "train_saved_state_oracle_score_changed")
    project, progress = verify._context(task)
    project_id = int(progress["project_id"])
    verify._unchanged_tables(before, after, "issue_label_links")
    verify._unchanged_other_git(before, after, project_id)
    key = "historical_duplicate" if negative else "active"
    issue = verify._issue(before, project_id, int(progress["issue_iids"][key]))
    label_id = verify._project_label_id(
        before, project_id, task["oracle"]["expected_priority"])
    verify._added_label_link(before, after, int(issue["id"]), label_id)
    return {"score": scored["reward"],
            "target_or_controlled_wrong_object_verified": True,
            "independent_no_regression_checked": True}


async def _gui_label(browser, task: dict, issue_key: str,
                     folder: Path) -> dict:
    project, progress = verify._context(task)
    credentials = json.loads(operators.CREDENTIALS.read_bytes())["train"]
    context = await browser.new_context(viewport={"width": 1440, "height": 1000})
    blocked = []

    async def guard(route):
        if gui_controls._local_url(route.request.url):
            await route.continue_()
        else:
            blocked.append(route.request.url.split(":", 1)[0])
            await route.abort()

    await context.route("**/*", guard)
    page = await context.new_page()
    try:
        require(not await context.cookies(),
                "new_train_browser_context_has_prior_auth")
        await gui_controls._login(page, credentials["username"],
                                  credentials["password"])
        repo = project["full_path"]
        await page.goto(runtime.BASE + "/" + repo +
                        "/-/blob/main/security/release-policy.md",
                        wait_until="domcontentloaded", timeout=90000)
        label = task["oracle"]["expected_priority"]
        await page.get_by_text(label, exact=False).first.wait_for(timeout=30000)
        await page.screenshot(path=str(folder / "policy.png"), full_page=True)
        issue_iid = int(progress["issue_iids"][issue_key])
        await page.goto(runtime.BASE + "/" + repo + "/-/issues/" + str(issue_iid),
                        wait_until="domcontentloaded", timeout=90000)
        await page.get_by_text(
            "Active remediation:" if issue_key == "active" else
            "Historical verification:", exact=False).last.wait_for(timeout=30000)
        await page.screenshot(path=str(folder / "issue-before.png"), full_page=True)
        labels = page.locator('[data-testid="work-item-labels"]')
        await labels.locator('[data-testid="edit-button"]').click()
        await labels.get_by_role("option").filter(has_text=label).click()
        await labels.locator('[data-testid="apply-button"]').click()
        await labels.locator('[data-testid="' + label + '"]').wait_for(timeout=30000)
        await labels.locator(".gl-spinner").wait_for(state="hidden", timeout=30000)
        await page.reload(wait_until="domcontentloaded", timeout=90000)
        await labels.locator('[data-testid="' + label + '"]').wait_for(timeout=30000)
        await page.screenshot(path=str(folder / "issue-after.png"), full_page=True)
        return {"saved_visible_after_reload": True,
                "fresh_browser_context": True,
                "blocked_external_request_schemes": sorted(set(blocked)),
                "screenshots_sha256": {
                    name: one.sha((folder / name).read_bytes())
                    for name in ("policy.png", "issue-before.png",
                                 "issue-after.png")}}
    finally:
        await context.close()


async def _one_case(browser, task: dict, old: dict, case_index: int,
                    name: str, issue_key: str, expected_score: float) -> dict:
    folder = CASES_DIR / f"{case_index:02d}-{name}"
    folder.mkdir(mode=0o700, exist_ok=False)
    baseline = json.loads((PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes())
    before = verify.state_snapshot()
    require(before["business_sha256"] == baseline["business_sha256"] and
            baseline["business_sha256"] == old["baseline_business_sha256"],
            "new_train_case_not_at_frozen_original_baseline")
    factory.write_private(folder / "before.private.json", before)
    gui = None
    after = None
    score = None
    error_type = None
    try:
        gui = await _gui_label(browser, task, issue_key, folder)
        after = verify.state_snapshot()
        factory.write_private(folder / "after.private.json", after)
        score = score_saved_case(task, before, after,
                                 negative=expected_score == 0.0)
    except Exception as exc:
        error_type = type(exc).__name__
    reset_receipt = None
    restored_exact = False
    try:
        reset_receipt = reset.reset()
        restored = verify.state_snapshot()
        factory.write_private(folder / "restored.private.json", restored)
        lane.assert_live_world(old)
        restored_exact = (restored == baseline and
                          reset_receipt["cold_reset"] is True and
                          reset_receipt["same_business_sha256"] is True and
                          reset_receipt["container_identity_changed"] is True)
    except Exception as exc:
        error_type = error_type or type(exc).__name__
    forensic = None
    try:
        forensic = boot.capture_startup_forensics(folder)
    except Exception as exc:
        error_type = error_type or type(exc).__name__
    record = {
        "schema": CASE_SCHEMA, "case_index": case_index,
        "case_name": name, "issue_variant": issue_key,
        "expected_score": expected_score,
        "gui": gui, "score": score,
        "before_sha256": one.sha((folder / "before.private.json").read_bytes()),
        "after_sha256": one.sha((folder / "after.private.json").read_bytes())
        if after is not None else None,
        "restored_sha256": one.sha((folder / "restored.private.json").read_bytes())
        if (folder / "restored.private.json").exists() else None,
        "reset_receipt": reset_receipt,
        "restored_exact": restored_exact,
        "forensics": forensic,
        "error_type": error_type,
        "provider_calls": 0, "official_final_admitted": 0,
    }
    one.write_new(folder / "case-receipt.private.json", record)
    return record


def completed_case_trio(rows: list[dict]) -> bool:
    return len(rows) == 3 and all(
        row.get("error_type") is None and
        row.get("restored_exact") is True and
        (row.get("gui") or {}).get("saved_visible_after_reload") is True and
        (row.get("score") or {}).get("score") == row.get("expected_score") and
        (row.get("forensics") or {}).get("raw_startup_logs_saved") is True and
        (row.get("forensics") or {}).get("state_only_inspect_saved") is True
        for row in rows)


def _child_run(ratification_private: Path, reviewed_public_sha: str) -> dict:
    plan, plan_sha, task = validate_freeze(ratification_private)
    require(reviewed_public_sha == one.sha(PUBLIC_PLAN.read_bytes()),
            "reviewed_new_train_public_freeze_digest_required")
    intent, intent_sha = _private_json(INTENT)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("source_freeze_sha256") == plan_sha and
            intent.get("intent_nonce") == plan["intent_nonce"] and
            intent.get("train_task_id") == task["task_id"] and
            intent.get("train_task_package_sha256") ==
            plan["train_task_package_sha256"] and
            intent.get("same_failed_final_identity_replay_authorized") is False and
            not CHILD_RESULT.exists(),
            "new_train_child_without_unique_intent")
    old = terminal.validate_freeze(ratification_private)[1]["old"]
    lane.assert_live_world(old)
    CASES_DIR.mkdir(mode=0o700, exist_ok=False)
    async def run_cases():
        from playwright.async_api import async_playwright
        rows = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                for index, (name, issue_key, expected) in enumerate(CASES):
                    row = await _one_case(browser, task, old, index,
                                          name, issue_key, expected)
                    rows.append(row)
                    if (row["error_type"] or not row["restored_exact"] or
                            not row["forensics"] or
                            not row["forensics"]["raw_startup_logs_saved"] or
                            not row["forensics"]["state_only_inspect_saved"] or
                            row["score"]["score"] != expected):
                        break
            finally:
                await browser.close()
        return rows
    rows = asyncio.run(run_cases())
    status = ("three_train_gui_cases_saved_and_exactly_reset"
              if completed_case_trio(rows) else
              "train_gui_diagnostic_failed_no_replay")
    child = {
        "schema": CHILD_SCHEMA, "status": status,
        "source_freeze_sha256": plan_sha,
        "intent_sha256": intent_sha,
        "intent_nonce_sha256": plan["intent_nonce_sha256"],
        "train_task_package_sha256": plan["train_task_package_sha256"],
        "completed_cases": len(rows),
        "case_receipt_sha256s": [
            one.sha((CASES_DIR / f"{index:02d}-{CASES[index][0]}" /
                     "case-receipt.private.json").read_bytes())
            for index in range(len(rows))],
        "scores": [row["score"]["score"] if row["score"] else None
                   for row in rows],
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }
    digest = one.write_new(CHILD_RESULT, child)
    return {"status": status, "child_result_sha256": digest}


@contextmanager
def _locked():
    descriptor = os.open(RUN / ".diagnostic.lock",
                         os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                         0o600)
    try:
        require(stat.S_ISREG(os.fstat(descriptor).st_mode) and
                os.fstat(descriptor).st_mode & 0o077 == 0,
                "new_train_diagnostic_lock_not_private")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _artifact_tree_manifest() -> list[dict]:
    roots = (CASES_DIR, RUN / "supervisor-fallback")
    rows = []
    for root in roots:
        if not root.exists():
            continue
        require(root.is_dir() and not root.is_symlink() and
                root.stat().st_mode & 0o077 == 0,
                "new_train_artifact_tree_not_private")
        for path in sorted(root.rglob("*")):
            require(not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
                    "new_train_artifact_file_symlink_or_permissive")
            if path.is_dir():
                continue
            require(path.is_file(), "new_train_artifact_tree_nonregular_file")
            raw = path.read_bytes()
            rows.append({"path": str(path.relative_to(RUN)),
                         "sha256": one.sha(raw), "bytes": len(raw)})
    return rows


def _public_result(supervisor: dict, supervisor_sha: str) -> dict:
    return {
        "schema": PUBLIC_RESULT_SCHEMA,
        "status": supervisor["status"],
        "source_freeze_public_sha256": one.sha(PUBLIC_PLAN.read_bytes()),
        "supervisor_result_private_sha256": supervisor_sha,
        "intent_nonce_sha256": supervisor["intent_nonce_sha256"],
        "partition": "train",
        "completed_gui_cases": supervisor["completed_gui_cases"],
        "saved_state_scores": supervisor["saved_state_scores"],
        "private_artifact_file_count": len(supervisor["artifact_tree_manifest"]),
        "private_artifact_tree_sha256":
            one.sha(one.canonical(supervisor["artifact_tree_manifest"])),
        "raw_log_stdout_sha256s": supervisor["raw_log_stdout_sha256s"],
        "child_process_group_terminated":
            supervisor["child_process_group_terminated"],
        "post_attempt_exact_baseline": supervisor["post_attempt_exact_baseline"],
        "same_failed_final_identity_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }


def run_diagnostic(ratification_private: Path,
                   reviewed_public_sha: str) -> dict:
    plan, plan_sha, task = validate_freeze(ratification_private)
    require(reviewed_public_sha == one.sha(PUBLIC_PLAN.read_bytes()),
            "reviewed_new_train_public_freeze_digest_required")
    with _locked():
        require(not INTENT.exists() and not CHILD_RESULT.exists() and
                not SUPERVISOR_RESULT.exists() and not PUBLIC_RESULT.exists() and
                not CASES_DIR.exists(),
                "new_train_intent_already_dispatched_no_replay")
        old = terminal.validate_freeze(ratification_private)[1]["old"]
        lane.assert_live_world(old)
        intent = {
            "schema": INTENT_SCHEMA,
            "source_freeze_sha256": plan_sha,
            "reviewed_public_freeze_sha256": reviewed_public_sha,
            "intent_nonce": plan["intent_nonce"],
            "intent_nonce_sha256": plan["intent_nonce_sha256"],
            "train_task_id": task["task_id"],
            "train_task_package_sha256": plan["train_task_package_sha256"],
            "partition": "train",
            "same_failed_final_identity_replay_authorized": False,
            "provider_calls": 0,
            "selection_or_final_tasks_dispatched": 0,
        }
        intent_sha = one.write_new(INTENT, intent)
        argv = [sys.executable, "-m", "gitlab_world.v066_new_train_diagnostic_v6",
                "child-run", "--ratification-private", str(ratification_private),
                "--reviewed-public-sha256", reviewed_public_sha, "--execute"]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
        try:
            child = recovery._confirm_child_process_group(one.supervise_child(
                argv, cwd=ROOT, env=env,
                stdout_path=RUN / "child.stdout.private.log",
                stderr_path=RUN / "child.stderr.private.log",
                timeout_seconds=WALL_SECONDS, grace_seconds=GRACE_SECONDS))
        except Exception as exc:
            child = {"child_terminated": False,
                     "process_group_terminated": False,
                     "exit_code": None, "timed_out": False,
                     "supervision_error_type": type(exc).__name__}
        child_receipt = None
        child_sha = None
        if CHILD_RESULT.exists():
            child_receipt, child_sha = _private_json(CHILD_RESULT)
        passed = bool(child.get("child_terminated") and
                      child.get("process_group_terminated") and
                      not child.get("timed_out") and child.get("exit_code") == 0 and
                      child_receipt and child_receipt.get("status") ==
                      "three_train_gui_cases_saved_and_exactly_reset" and
                      child_receipt.get("completed_cases") == 3 and
                      child_receipt.get("scores") == [1.0, 0.0, 1.0] and
                      child_receipt.get("intent_sha256") == intent_sha and
                      child_receipt.get("source_freeze_sha256") == plan_sha and
                      child_receipt.get("intent_nonce_sha256") ==
                      plan["intent_nonce_sha256"] and
                      child_receipt.get("train_task_package_sha256") ==
                      plan["train_task_package_sha256"])
        fallback = None
        cleanup = None
        if child.get("child_terminated") and child.get("process_group_terminated"):
            if passed:
                try:
                    lane.assert_live_world(old)
                    cleanup = {"cold_reset_exact": True,
                               "mode": "three_child_case_resets_independently_read_back"}
                except Exception as exc:
                    passed = False
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
            if not passed:
                # Preserve the current container before exact cleanup, even
                # when a watchdog killed the child before its own capture.
                try:
                    folder = RUN / "supervisor-fallback"
                    folder.mkdir(mode=0o700, exist_ok=False)
                    fallback = boot.capture_startup_forensics(folder)
                    one.write_new(folder / "forensic-receipt.private.json", fallback)
                except Exception as exc:
                    fallback = {"capture_error_type": type(exc).__name__}
                try:
                    cleanup = one.exact_cold_reset()
                except Exception as exc:
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
        else:
            cleanup = {"cold_reset_exact": False,
                       "error_type": "child_process_group_unconfirmed_no_cleanup"}
        status = ("three_train_gui_cases_saved_and_exactly_reset"
                  if passed and cleanup.get("cold_reset_exact") is True else
                  "terminal_train_diagnostic_failed_exactly_reset_no_replay"
                  if cleanup.get("cold_reset_exact") is True else
                  "manual_review_required_no_replay")
        manifest = _artifact_tree_manifest()
        raw_hashes = []
        if child_receipt:
            for index in range(child_receipt["completed_cases"]):
                folder = CASES_DIR / f"{index:02d}-{CASES[index][0]}"
                receipt, _receipt_sha = _private_json(
                    folder / "case-receipt.private.json")
                forensic = receipt.get("forensics") or {}
                if forensic.get("raw_file_sha256s"):
                    raw_hashes.append(forensic["raw_file_sha256s"]["docker_logs_stdout"])
        if fallback and fallback.get("raw_file_sha256s"):
            raw_hashes.append(fallback["raw_file_sha256s"]["docker_logs_stdout"])
        supervisor = {
            "schema": SUPERVISOR_SCHEMA, "status": status,
            "source_freeze_sha256": plan_sha,
            "intent_sha256": intent_sha,
            "intent_nonce_sha256": plan["intent_nonce_sha256"],
            "child": child, "child_result_sha256": child_sha,
            "completed_gui_cases":
                child_receipt["completed_cases"] if child_receipt else 0,
            "saved_state_scores": child_receipt["scores"] if child_receipt else [],
            "artifact_tree_manifest": manifest,
            "raw_log_stdout_sha256s": raw_hashes,
            "fallback_forensics": fallback,
            "cleanup": cleanup,
            "post_attempt_exact_baseline":
                cleanup.get("cold_reset_exact") is True,
            "child_process_group_terminated":
                child.get("process_group_terminated") is True,
            "same_failed_final_identity_replay_authorized": False,
            "provider_calls": 0,
            "selection_or_final_tasks_dispatched": 0,
            "official_final_admitted": 0,
        }
        supervisor_sha = one.write_new(SUPERVISOR_RESULT, supervisor)
        public = _public_result(supervisor, supervisor_sha)
        one.write_new(PUBLIC_RESULT, public, 0o644)
        return public


def audit(ratification_private: Path) -> dict:
    plan, plan_sha, task = validate_freeze(ratification_private)
    if not INTENT.exists():
        require(not CHILD_RESULT.exists() and not SUPERVISOR_RESULT.exists() and
                not PUBLIC_RESULT.exists() and not CASES_DIR.exists(),
                "train_diagnostic_outputs_without_intent")
        return _public_plan(plan, plan_sha)
    intent, intent_sha = _private_json(INTENT)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("source_freeze_sha256") == plan_sha and
            intent.get("intent_nonce") == plan["intent_nonce"] and
            intent.get("train_task_id") == task["task_id"] and
            intent.get("train_task_package_sha256") ==
            plan["train_task_package_sha256"] and
            intent.get("partition") == "train" and
            intent.get("same_failed_final_identity_replay_authorized") is False and
            intent.get("provider_calls") ==
            intent.get("selection_or_final_tasks_dispatched") == 0,
            "train_diagnostic_intent_changed")
    if not SUPERVISOR_RESULT.exists():
        return {"status": "pending_train_diagnostic_intent_no_replay",
                "intent_nonce_sha256": plan["intent_nonce_sha256"],
                "provider_calls": 0, "official_final_admitted": 0}
    supervisor, supervisor_sha = _private_json(SUPERVISOR_RESULT)
    require(supervisor.get("schema") == SUPERVISOR_SCHEMA and
            supervisor.get("intent_sha256") == intent_sha and
            supervisor.get("source_freeze_sha256") == plan_sha and
            supervisor.get("intent_nonce_sha256") == plan["intent_nonce_sha256"] and
            supervisor.get("same_failed_final_identity_replay_authorized") is False and
            supervisor.get("provider_calls") ==
            supervisor.get("selection_or_final_tasks_dispatched") ==
            supervisor.get("official_final_admitted") == 0 and
            supervisor.get("artifact_tree_manifest") == _artifact_tree_manifest(),
            "train_diagnostic_supervisor_or_case_tree_changed")
    if supervisor["status"] == "terminal_train_diagnostic_failed_exactly_reset_no_replay":
        require(supervisor.get("post_attempt_exact_baseline") is True and
                supervisor.get("child_process_group_terminated") is True and
                supervisor.get("cleanup", {}).get("cold_reset_exact") is True,
                "train_diagnostic_terminal_status_without_exact_recovery")
    child_sha = supervisor.get("child_result_sha256")
    if child_sha is not None:
        child, actual_sha = _private_json(CHILD_RESULT)
        require(actual_sha == child_sha and
                child.get("schema") == CHILD_SCHEMA and
                child.get("intent_sha256") == intent_sha and
                child.get("train_task_package_sha256") ==
                plan["train_task_package_sha256"] and
                child.get("completed_cases") ==
                len(child.get("case_receipt_sha256s", [])) <= 3 and
                child.get("provider_calls") ==
                child.get("selection_or_final_tasks_dispatched") ==
                child.get("official_final_admitted") == 0,
                "train_diagnostic_child_receipt_changed")
        scores = []
        generations = []
        for index, expected_sha in enumerate(child["case_receipt_sha256s"]):
            name, issue_key, expected_score = CASES[index]
            folder = CASES_DIR / f"{index:02d}-{name}"
            receipt, receipt_sha = _private_json(
                folder / "case-receipt.private.json")
            require(receipt_sha == expected_sha and
                    receipt.get("schema") == CASE_SCHEMA and
                    receipt.get("case_index") == index and
                    receipt.get("case_name") == name and
                    receipt.get("issue_variant") == issue_key and
                    receipt.get("expected_score") == expected_score,
                    "train_diagnostic_case_receipt_changed")
            if receipt.get("error_type") is not None:
                continue
            before, before_sha = _private_json(folder / "before.private.json")
            after, after_sha = _private_json(folder / "after.private.json")
            restored, restored_sha = _private_json(folder / "restored.private.json")
            baseline = json.loads((PRIVATE_ROOT /
                                   "baseline-persisted-state.json").read_bytes())
            require(receipt.get("before_sha256") == before_sha and
                    receipt.get("after_sha256") == after_sha and
                    receipt.get("restored_sha256") == restored_sha and
                    before == baseline and
                    receipt.get("restored_exact") is True and
                    restored == baseline and
                    receipt.get("reset_receipt", {}).get("cold_reset") is True and
                    receipt["reset_receipt"].get("same_business_sha256") is True and
                    receipt["reset_receipt"].get("container_identity_changed") is True and
                    receipt.get("gui", {}).get("saved_visible_after_reload") is True,
                    "train_diagnostic_saved_state_or_reset_changed")
            score = score_saved_case(task, before, after,
                                     negative=expected_score == 0.0)
            require(score == receipt["score"] and
                    score["score"] == expected_score,
                    "train_diagnostic_independent_saved_score_changed")
            screenshots = receipt["gui"]["screenshots_sha256"]
            require(set(screenshots) == {"policy.png", "issue-before.png",
                                         "issue-after.png"},
                    "train_diagnostic_gui_screenshot_set_changed")
            for image_name, digest in screenshots.items():
                require(image_name in {"policy.png", "issue-before.png",
                                       "issue-after.png"} and
                        one.sha((folder / image_name).read_bytes()) == digest,
                        "train_diagnostic_gui_screenshot_changed")
            forensic = receipt["forensics"]
            require(forensic["raw_startup_logs_saved"] is True and
                    forensic["state_only_inspect_saved"] is True,
                    "train_diagnostic_raw_startup_forensics_missing")
            for key, filename in {
                "docker_logs_stdout": "docker-logs.stdout.private.log",
                "docker_logs_stderr": "docker-logs.stderr.private.log",
                "docker_state_stdout": "docker-state.stdout.private.json",
                "docker_state_stderr": "docker-state.stderr.private.log",
            }.items():
                path = folder / filename
                require(path.is_file() and not path.is_symlink() and
                        path.stat().st_mode & 0o077 == 0 and
                        len(path.read_bytes()) == forensic["raw_file_bytes"][key] and
                        one.sha(path.read_bytes()) == forensic["raw_file_sha256s"][key],
                        "train_diagnostic_raw_forensic_file_changed")
            state = json.loads((folder / "docker-state.stdout.private.json").read_bytes())
            require(state.get("Status") == "running" and
                    state.get("ExitCode") == 0 and
                    state.get("OOMKilled") is False and
                    state.get("Health", {}).get("Status") == "healthy",
                    "train_diagnostic_saved_post_reset_container_not_healthy")
            scores.append(score["score"])
            generations.append(receipt["reset_receipt"]["generation"])
        if supervisor["status"] == "three_train_gui_cases_saved_and_exactly_reset":
            require(child.get("status") == supervisor["status"] and
                    child.get("completed_cases") == 3 and
                    child.get("scores") == [1.0, 0.0, 1.0] and
                    scores == [1.0, 0.0, 1.0] and
                    len(generations) == 3 and
                    generations == list(range(generations[0], generations[0] + 3)) and
                    supervisor.get("child", {}).get("exit_code") == 0 and
                    supervisor["child"].get("timed_out") is False and
                    supervisor.get("child_process_group_terminated") is True and
                    supervisor.get("post_attempt_exact_baseline") is True,
                    "train_diagnostic_success_without_full_independent_gui_audit")
    require(json.loads(PUBLIC_RESULT.read_bytes()) ==
            _public_result(supervisor, supervisor_sha),
            "train_diagnostic_public_outcome_changed")
    return _public_result(supervisor, supervisor_sha)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit", "child-run",
                                           "run-diagnostic"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--reviewed-public-sha256", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        require(not args.execute, "freeze_is_offline_only")
        result = freeze(args.ratification_private)
    elif args.action == "audit":
        require(not args.execute, "audit_is_read_only")
        result = audit(args.ratification_private)
    elif args.action == "child-run":
        require(args.execute, "child_requires_explicit_execute")
        result = _child_run(args.ratification_private,
                            args.reviewed_public_sha256)
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result["status"] ==
                         "three_train_gui_cases_saved_and_exactly_reset" else 1)
    else:
        require(args.execute, "diagnostic_requires_explicit_execute")
        result = run_diagnostic(args.ratification_private,
                                args.reviewed_public_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
