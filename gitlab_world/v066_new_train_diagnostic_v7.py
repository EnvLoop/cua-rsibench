"""One-use new-identity TRAIN GUI diagnostic after the v6 terminal forensics.

V6's child completed 1/0/1, but its supervisor failed before a receipt. Its
consumed intent is never replayed. V7 selects another TRAIN source family and
saves every screenshot owner-only before the next GUI action. Artifact-review
failure yields a terminal non-success supervisor record rather than silently
promoting a successful child.
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

from . import bootstrap, factory, gui_controls, operators, runtime, verify
from . import prospective_final_controls_v066 as lane
from . import v066_boot_only_probe_v5 as boot
from . import v066_infra_recovery_v4 as replacement
from . import v066_infra_requalification_v1 as recovery
from . import v066_new_train_diagnostic_v6 as previous
from . import v066_requalified_continuation_v1 as terminal
from . import v066_supervised_final_one_v1 as one
from . import v066_train_gui_pair as first_train
from . import v066_train_target_shape_v1 as second_train


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = runtime.PRIVATE
RUN = PRIVATE_ROOT / "v066-new-train-diagnostic-v7-20260930"
CASES_DIR = RUN / "cases"
PLAN = RUN / "source-freeze.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-new-train-diagnostic-v7-source-freeze-2026-09-30.json"
INTENT = RUN / "intent.private.json"
CHILD_RESULT = RUN / "child-result.private.json"
SUPERVISOR_RESULT = RUN / "supervisor-result.private.json"
PUBLIC_RESULT = ROOT / "docs/evidence/gitlab-v066-new-train-diagnostic-v7-outcome-2026-09-30.json"
PARENT_FORENSIC = ROOT / "docs/evidence/gitlab-v066-new-train-v6-post-terminal-forensic-2026-09-30.json"
PARENT_FORENSIC_SHA256 = "6e3995c3ac913e0fe2308e46b18b022a965cab8e6f1b4c56396c7badbefe6c78"
SELECTED_TRAIN_ORDINAL = 3
CASES = previous.CASES
WALL_SECONDS = 3600
GRACE_SECONDS = 30
PLAN_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v7-private-plan-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v7-public-plan-v1"
INTENT_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v7-private-intent-v1"
CHILD_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v7-private-child-v1"
SUPERVISOR_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v7-private-supervisor-v1"
PUBLIC_RESULT_SCHEMA = "envloop-gitlab-v066-new-train-diagnostic-v7-public-outcome-v1"
SOURCE_FILES = (
    "gitlab_world/v066_new_train_diagnostic_v7.py",
    "tests/test_gitlab_v066_new_train_diagnostic_v7.py",
    "docs/FULL_STUDY_GITLAB_V066_NEW_TRAIN_DIAGNOSTIC_V7_2026-09-30.md",
    "gitlab_world/v066_new_train_diagnostic_v6.py",
    "tools/audit_gitlab_v6_train_post_terminal_20260930.py",
    "gitlab_world/gui_controls.py",
    "gitlab_world/operators.py",
    "gitlab_world/verify.py",
    "gitlab_world/reset.py",
    "gitlab_world/runtime.py",
)


class DiagnosticV7Error(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DiagnosticV7Error(code)


def _source_hashes() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _private_json(path: Path) -> tuple[dict, str]:
    return one.private_json(path)


def _v6_forensic_boundary(ratification_private: Path) -> dict:
    require(PARENT_FORENSIC.is_file() and
            one.sha(PARENT_FORENSIC.read_bytes()) == PARENT_FORENSIC_SHA256,
            "reviewed_v6_terminal_forensic_bytes_changed")
    published = json.loads(PARENT_FORENSIC.read_bytes())
    from tools import audit_gitlab_v6_train_post_terminal_20260930 as auditor
    reopened = auditor.audit(repo=ROOT,
                             ratification=ratification_private,
                             check_live=False)
    for key, value in published.items():
        if key in ("matching_original_processes_at_audit",
                   "live_original_postgres_git_exact_baseline"):
            continue
        require(reopened.get(key) == value,
                "v6_child_forensics_or_consumed_intent_changed")
    require(published.get("status") ==
            "child_trio_reopened_supervisor_completion_missing_no_replay" and
            published.get("saved_child_case_scores") == [1.0, 0.0, 1.0] and
            published.get("nine_pngs_mode_hardened_to_0600_bytes_unchanged") is True and
            published.get("original_supervisor_result_present") is False and
            published.get("original_public_outcome_present") is False and
            published.get("same_intent_replay_authorized") is False and
            published.get("selection_or_final_tasks_dispatched") ==
            published.get("model_calls") ==
            published.get("official_final_admitted") == 0,
            "v6_parent_is_not_terminal_child_only_no_replay")
    boot_result = boot.audit(ratification_private)
    old = terminal.audit(ratification_private)
    require(boot_result.get("status") ==
            "three_boot_only_clones_exact_baseline" and
            boot_result.get("task_intents") == 0 and
            old.get("status") == "terminal_failure_no_replay" and
            old.get("completed_current_controls") == 13,
            "boot_or_original_terminal_boundary_changed")
    return published


def select_train_task() -> tuple[dict, str]:
    require(bootstrap.WORLD_FILE.is_file() and
            bootstrap.WORLD_FILE.stat().st_mode & 0o077 == 0,
            "private_original_train_world_missing")
    world = json.loads(bootstrap.WORLD_FILE.read_bytes())
    train = [row for row in world["tasks"] if row["partition"] == "train"]
    matches = sorted((row for row in train
                      if row["template_group"] == "issue_label_from_alert"),
                     key=lambda row: row["task_id"])
    require(len(train) == 20 and len(matches) == 5,
            "original_train_label_roster_changed")
    task = matches[SELECTED_TRAIN_ORDINAL]
    first, _ = first_train._train_task()
    second, _ = second_train.second_train_task()
    third, _ = previous.select_train_task()
    used = (first, second, third)
    require(task["partition"] == "train" and
            all(task["task_id"] != row["task_id"] and
                task["project_family"] != row["project_family"] and
                task["source_family"] != row["source_family"]
                for row in used),
            "new_train_identity_replays_prior_paid_or_v6_gui_task")
    v4, _ = _private_json(replacement.PRIVATE_PLAN)
    require(task["task_id"] not in {
                row["task_id"] for row in v4["candidate_roster"]} and
            one.sha(task["source_family"].encode()) not in {
                row["source_family_sha256"] for row in
                v4["candidate_roster"]},
            "v7_train_source_overlaps_v4_final_replacement_cohort")
    project, progress = verify._context(task)
    baseline = json.loads((PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes())
    project_id = int(progress["project_id"])
    label_id = verify._project_label_id(
        baseline, project_id, task["oracle"]["expected_priority"])
    target_issues = {
        int(verify._issue(baseline, project_id,
                          int(progress["issue_iids"][key]))["id"])
        for key in ("active", "historical_duplicate")}
    require(project["partition"] == "train" and
            not any(int(row["target_id"]) in target_issues and
                    int(row["label_id"]) == label_id
                    for row in baseline["db"]["issue_label_links"]),
            "new_train_label_already_present_in_frozen_baseline")
    return task, factory.sha256(factory.canonical(task))


def _public_plan(private: dict, private_sha: str) -> dict:
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_new_train_identity_no_gui_dispatch",
        "private_plan_sha256": private_sha,
        "source_bundle_sha256": private["source_bundle_sha256"],
        "v6_child_only_forensic_sha256": private["v6_child_only_forensic_sha256"],
        "intent_nonce_sha256": private["intent_nonce_sha256"],
        "partition": "train",
        "new_source_family_outside_v4_final_cohort": True,
        "planned_case_scores": [1.0, 0.0, 1.0],
        "planned_exact_cold_resets": 3,
        "planned_child_watchdog_seconds": WALL_SECONDS,
        "screenshots_owner_only_from_creation": True,
        "artifact_permission_failure_forbids_success": True,
        "original_evaluator_checkout_only": True,
        "same_v6_or_terminal_final_identity_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }


def freeze(ratification_private: Path) -> dict:
    require(not PLAN.exists() and not PUBLIC_PLAN.exists() and
            not INTENT.exists() and not CASES_DIR.exists(),
            "fresh_v7_train_diagnostic_epoch_required")
    _v6_forensic_boundary(ratification_private)
    task, package_sha = select_train_task()
    acl = first_train._acl_and_split_evidence()
    sources = _source_hashes()
    nonce = secrets.token_hex(32)
    private = {
        "schema": PLAN_SCHEMA,
        "status": "source_frozen_new_train_identity_no_gui_dispatch",
        "source_sha256s": sources,
        "source_bundle_sha256": one.sha(one.canonical(sources)),
        "v6_child_only_forensic_sha256": PARENT_FORENSIC_SHA256,
        "v6_consumed_intent_sha256": json.loads(PARENT_FORENSIC.read_bytes())[
            "one_use_intent_sha256"],
        "ratification_private_sha256": one.sha(ratification_private.read_bytes()),
        "original_world_sha256": one.sha(bootstrap.WORLD_FILE.read_bytes()),
        "original_baseline_sha256": one.sha(
            (PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes()),
        "train_acl_and_split_evidence": acl,
        "train_task_id": task["task_id"],
        "train_task_package_sha256": package_sha,
        "train_task_source_family_sha256":
            one.sha(task["source_family"].encode()),
        "selected_train_ordinal": SELECTED_TRAIN_ORDINAL,
        "intent_nonce": nonce,
        "intent_nonce_sha256": one.sha(nonce.encode()),
        "child_watchdog_seconds": WALL_SECONDS,
        "same_v6_or_terminal_final_identity_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }
    RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(RUN.stat().st_mode & 0o077 == 0,
            "v7_private_run_directory_permissive")
    private_sha = one.write_new(PLAN, private)
    public = _public_plan(private, private_sha)
    one.write_new(PUBLIC_PLAN, public, 0o644)
    return public


def validate_freeze(ratification_private: Path) -> tuple[dict, str, dict]:
    _v6_forensic_boundary(ratification_private)
    task, package_sha = select_train_task()
    acl = first_train._acl_and_split_evidence()
    plan, plan_sha = _private_json(PLAN)
    sources = _source_hashes()
    require(plan.get("schema") == PLAN_SCHEMA and
            plan.get("status") == "source_frozen_new_train_identity_no_gui_dispatch" and
            plan.get("source_sha256s") == sources and
            plan.get("source_bundle_sha256") == one.sha(one.canonical(sources)) and
            plan.get("v6_child_only_forensic_sha256") == PARENT_FORENSIC_SHA256 and
            plan.get("v6_consumed_intent_sha256") ==
            json.loads(PARENT_FORENSIC.read_bytes())["one_use_intent_sha256"] and
            plan.get("ratification_private_sha256") ==
            one.sha(ratification_private.read_bytes()) and
            plan.get("original_world_sha256") ==
            one.sha(bootstrap.WORLD_FILE.read_bytes()) and
            plan.get("original_baseline_sha256") ==
            one.sha((PRIVATE_ROOT / "baseline-persisted-state.json").read_bytes()) and
            plan.get("train_acl_and_split_evidence") == acl and
            plan.get("train_task_id") == task["task_id"] and
            plan.get("train_task_package_sha256") == package_sha and
            plan.get("train_task_source_family_sha256") ==
            one.sha(task["source_family"].encode()) and
            plan.get("selected_train_ordinal") == SELECTED_TRAIN_ORDINAL and
            isinstance(plan.get("intent_nonce"), str) and
            len(plan["intent_nonce"]) == 64 and
            plan.get("intent_nonce_sha256") == one.sha(plan["intent_nonce"].encode()) and
            plan.get("child_watchdog_seconds") == WALL_SECONDS and
            plan.get("same_v6_or_terminal_final_identity_replay_authorized") is False and
            plan.get("provider_calls") ==
            plan.get("selection_or_final_tasks_dispatched") ==
            plan.get("official_final_admitted") == 0 and
            json.loads(PUBLIC_PLAN.read_bytes()) == _public_plan(plan, plan_sha),
            "v7_source_or_private_train_identity_changed")
    return plan, plan_sha, task


def _write_private_png(folder: Path, name: str, raw: bytes) -> str:
    """Expose a complete PNG atomically, owner-only, before another action."""
    require(name in {"policy.png", "issue-before.png", "issue-after.png"} and
            isinstance(raw, bytes) and raw.startswith(b"\x89PNG\r\n\x1a\n") and
            folder.is_dir() and not folder.is_symlink() and
            folder.stat().st_mode & 0o077 == 0,
            "v7_screenshot_not_png_or_private_folder")
    destination = folder / name
    require(not destination.exists() and not destination.is_symlink(),
            "v7_screenshot_destination_must_be_new")
    temporary = folder / ("." + name + "." + secrets.token_hex(8) + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        require(temporary.stat().st_mode & 0o077 == 0,
                "v7_temporary_screenshot_mode_not_owner_only")
        os.link(temporary, destination)
        require(destination.stat().st_mode & 0o077 == 0 and
                one.sha(destination.read_bytes()) == one.sha(raw),
                "v7_final_screenshot_changed_or_permissive")
    finally:
        if temporary.exists():
            temporary.unlink()
    return one.sha(raw)


async def _secure_screenshot(page, folder: Path, name: str) -> str:
    raw = await page.screenshot(type="png", full_page=True)
    return _write_private_png(folder, name, raw)


async def _secure_gui_label(browser, task: dict, issue_key: str,
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
                "v7_browser_context_has_prior_auth")
        await gui_controls._login(page, credentials["username"],
                                  credentials["password"])
        repo = project["full_path"]
        await page.goto(runtime.BASE + "/" + repo +
                        "/-/blob/main/security/release-policy.md",
                        wait_until="domcontentloaded", timeout=90000)
        label = task["oracle"]["expected_priority"]
        await page.get_by_text(label, exact=False).first.wait_for(timeout=30000)
        screens = {"policy.png": await _secure_screenshot(
            page, folder, "policy.png")}
        issue_iid = int(progress["issue_iids"][issue_key])
        await page.goto(runtime.BASE + "/" + repo + "/-/issues/" + str(issue_iid),
                        wait_until="domcontentloaded", timeout=90000)
        await page.get_by_text(
            "Active remediation:" if issue_key == "active" else
            "Historical verification:", exact=False).last.wait_for(timeout=30000)
        screens["issue-before.png"] = await _secure_screenshot(
            page, folder, "issue-before.png")
        labels = page.locator('[data-testid="work-item-labels"]')
        await labels.locator('[data-testid="edit-button"]').click()
        await labels.get_by_role("option").filter(has_text=label).click()
        await labels.locator('[data-testid="apply-button"]').click()
        await labels.locator('[data-testid="' + label + '"]').wait_for(timeout=30000)
        await labels.locator(".gl-spinner").wait_for(state="hidden", timeout=30000)
        await page.reload(wait_until="domcontentloaded", timeout=90000)
        await labels.locator('[data-testid="' + label + '"]').wait_for(timeout=30000)
        screens["issue-after.png"] = await _secure_screenshot(
            page, folder, "issue-after.png")
        return {"saved_visible_after_reload": True,
                "fresh_browser_context": True,
                "blocked_external_request_schemes": sorted(set(blocked)),
                "screenshots_sha256": screens,
                "frame_sequence": [
                    {"role": name, "sha256": screens[name]}
                    for name in ("policy.png", "issue-before.png",
                                 "issue-after.png")],
                "screenshots_owner_only_from_creation": True}
    finally:
        await context.close()


@contextmanager
def _scoped_v6_case_runner():
    old_dir, old_gui = previous.CASES_DIR, previous._gui_label
    previous.CASES_DIR = CASES_DIR
    previous._gui_label = _secure_gui_label
    try:
        yield
    finally:
        previous._gui_label = old_gui
        previous.CASES_DIR = old_dir


def _artifact_review() -> dict:
    """Record hashes and modes even if evidence is permissive; never throw for it."""
    rows = []
    issues = []
    for root in (CASES_DIR, RUN / "supervisor-fallback"):
        if not root.exists():
            continue
        if root.is_symlink() or not root.is_dir():
            issues.append("artifact_root_unsafe")
            continue
        if root.stat().st_mode & 0o077:
            issues.append("artifact_root_permissive")
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(RUN))
            if path.is_symlink():
                issues.append("artifact_symlink")
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                issues.append("artifact_permission")
            if path.is_dir():
                continue
            if not path.is_file():
                issues.append("artifact_nonregular")
                continue
            raw = path.read_bytes()
            rows.append({"path": relative, "mode": mode,
                         "sha256": one.sha(raw), "bytes": len(raw)})
    return {"files": rows, "issue_codes": sorted(set(issues)),
            "permission_gate_passed": not issues}


def _public_result(supervisor: dict, supervisor_sha: str) -> dict:
    review = supervisor["artifact_review"]
    return {
        "schema": PUBLIC_RESULT_SCHEMA,
        "status": supervisor["status"],
        "source_freeze_public_sha256": one.sha(PUBLIC_PLAN.read_bytes()),
        "supervisor_result_private_sha256": supervisor_sha,
        "intent_nonce_sha256": supervisor["intent_nonce_sha256"],
        "partition": "train",
        "completed_gui_cases": supervisor["completed_gui_cases"],
        "saved_state_scores": supervisor["saved_state_scores"]
            if supervisor["status"] == "three_train_gui_cases_independently_reviewable"
            else [],
        "private_artifact_count": len(review["files"]),
        "private_artifact_manifest_sha256": one.sha(one.canonical(review)),
        "artifact_permission_gate_passed": review["permission_gate_passed"],
        "supervisor_evidence_gate_passed":
            supervisor["status"] == "three_train_gui_cases_independently_reviewable",
        "independent_postrun_audit_required": True,
        "success_claim_authorized": False,
        "child_process_group_terminated":
            supervisor["child_process_group_terminated"],
        "post_attempt_exact_baseline": supervisor["post_attempt_exact_baseline"],
        "same_v6_or_terminal_final_identity_replay_authorized": False,
        "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }


def _child_run(ratification_private: Path, reviewed_sha: str) -> dict:
    plan, plan_sha, task = validate_freeze(ratification_private)
    require(reviewed_sha == one.sha(PUBLIC_PLAN.read_bytes()),
            "reviewed_v7_public_freeze_sha256_required")
    intent, intent_sha = _private_json(INTENT)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("source_freeze_sha256") == plan_sha and
            intent.get("intent_nonce") == plan["intent_nonce"] and
            intent.get("train_task_id") == task["task_id"] and
            intent.get("train_task_package_sha256") ==
            plan["train_task_package_sha256"] and
            intent.get("same_v6_or_terminal_final_identity_replay_authorized") is False and
            not CHILD_RESULT.exists(),
            "v7_child_without_unique_new_identity_intent")
    old = terminal.validate_freeze(ratification_private)[1]["old"]
    lane.assert_live_world(old)
    CASES_DIR.mkdir(mode=0o700, exist_ok=False)

    async def run_cases():
        from playwright.async_api import async_playwright
        rows = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                with _scoped_v6_case_runner():
                    for index, (name, issue_key, expected) in enumerate(CASES):
                        row = await previous._one_case(browser, task, old,
                                                       index, name, issue_key,
                                                       expected)
                        rows.append(row)
                        if (row["error_type"] or not row["restored_exact"] or
                                not row["forensics"] or
                                not row["forensics"]["raw_startup_logs_saved"] or
                                not row["forensics"]["state_only_inspect_saved"] or
                                not row["score"] or
                                row["score"]["score"] != expected or
                                not row["gui"] or
                                row["gui"].get("screenshots_owner_only_from_creation")
                                is not True):
                            break
            finally:
                await browser.close()
        return rows

    rows = asyncio.run(run_cases())
    status = ("three_train_gui_cases_saved_pending_supervisor_review"
              if previous.completed_case_trio(rows) and
              all((row.get("gui") or {}).get(
                  "screenshots_owner_only_from_creation") is True
                  for row in rows) else
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
                "v7_diagnostic_lock_not_private")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def run_diagnostic(ratification_private: Path, reviewed_sha: str) -> dict:
    plan, plan_sha, task = validate_freeze(ratification_private)
    require(reviewed_sha == one.sha(PUBLIC_PLAN.read_bytes()),
            "reviewed_v7_public_freeze_sha256_required")
    with _locked():
        require(not INTENT.exists() and not CHILD_RESULT.exists() and
                not SUPERVISOR_RESULT.exists() and not PUBLIC_RESULT.exists() and
                not CASES_DIR.exists(),
                "v7_intent_already_dispatched_no_replay")
        old = terminal.validate_freeze(ratification_private)[1]["old"]
        lane.assert_live_world(old)
        intent = {
            "schema": INTENT_SCHEMA,
            "source_freeze_sha256": plan_sha,
            "reviewed_public_freeze_sha256": reviewed_sha,
            "intent_nonce": plan["intent_nonce"],
            "intent_nonce_sha256": plan["intent_nonce_sha256"],
            "train_task_id": task["task_id"],
            "train_task_package_sha256": plan["train_task_package_sha256"],
            "partition": "train",
            "same_v6_or_terminal_final_identity_replay_authorized": False,
            "provider_calls": 0,
            "selection_or_final_tasks_dispatched": 0,
        }
        intent_sha = one.write_new(INTENT, intent)
        argv = [sys.executable, "-m", "gitlab_world.v066_new_train_diagnostic_v7",
                "child-run", "--ratification-private", str(ratification_private),
                "--reviewed-public-sha256", reviewed_sha, "--execute"]
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
            try:
                child_receipt, child_sha = _private_json(CHILD_RESULT)
            except Exception:
                child_receipt = None
                child_sha = None
        child_passed = bool(
            child.get("child_terminated") and
            child.get("process_group_terminated") and
            not child.get("timed_out") and child.get("exit_code") == 0 and
            child_receipt and child_receipt.get("status") ==
            "three_train_gui_cases_saved_pending_supervisor_review" and
            child_receipt.get("completed_cases") == 3 and
            child_receipt.get("scores") == [1.0, 0.0, 1.0] and
            child_receipt.get("intent_sha256") == intent_sha and
            child_receipt.get("source_freeze_sha256") == plan_sha and
            child_receipt.get("intent_nonce_sha256") == plan["intent_nonce_sha256"] and
            child_receipt.get("train_task_package_sha256") ==
            plan["train_task_package_sha256"])
        fallback = None
        cleanup = None
        if child.get("child_terminated") and child.get("process_group_terminated"):
            if child_passed:
                try:
                    lane.assert_live_world(old)
                    cleanup = {"cold_reset_exact": True,
                               "mode": "three_case_resets_independently_read_back"}
                except Exception as exc:
                    child_passed = False
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
            if not child_passed:
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
        # The v6 supervisor crashed here on nine mode-0644 PNG files. This
        # review records an error and still permits a non-success receipt.
        try:
            review = _artifact_review()
        except Exception as exc:
            review = {"files": [],
                      "issue_codes": ["artifact_review_error"],
                      "error_type": type(exc).__name__,
                      "permission_gate_passed": False}
        status = ("three_train_gui_cases_independently_reviewable"
                  if child_passed and cleanup.get("cold_reset_exact") is True and
                  review["permission_gate_passed"] is True else
                  "terminal_evidence_permission_failure_no_replay"
                  if child_passed and cleanup.get("cold_reset_exact") is True and
                  review["permission_gate_passed"] is False else
                  "terminal_train_diagnostic_failed_exactly_reset_no_replay"
                  if cleanup.get("cold_reset_exact") is True else
                  "manual_review_required_no_replay")
        supervisor = {
            "schema": SUPERVISOR_SCHEMA, "status": status,
            "source_freeze_sha256": plan_sha,
            "intent_sha256": intent_sha,
            "intent_nonce_sha256": plan["intent_nonce_sha256"],
            "child": child, "child_result_sha256": child_sha,
            "completed_gui_cases":
                child_receipt["completed_cases"] if child_receipt else 0,
            "saved_state_scores": child_receipt["scores"] if child_receipt else [],
            "artifact_review": review,
            "fallback_forensics": fallback,
            "cleanup": cleanup,
            "post_attempt_exact_baseline":
                cleanup.get("cold_reset_exact") is True,
            "child_process_group_terminated":
                child.get("process_group_terminated") is True,
            "same_v6_or_terminal_final_identity_replay_authorized": False,
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
                "v7_outputs_without_intent")
        return _public_plan(plan, plan_sha)
    intent, intent_sha = _private_json(INTENT)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("source_freeze_sha256") == plan_sha and
            intent.get("intent_nonce") == plan["intent_nonce"] and
            intent.get("train_task_id") == task["task_id"] and
            intent.get("train_task_package_sha256") ==
            plan["train_task_package_sha256"] and
            intent.get("partition") == "train" and
            intent.get("same_v6_or_terminal_final_identity_replay_authorized") is False and
            intent.get("provider_calls") ==
            intent.get("selection_or_final_tasks_dispatched") == 0,
            "v7_intent_changed_or_replayed")
    if not SUPERVISOR_RESULT.exists():
        return {"status": "pending_v7_intent_no_replay",
                "intent_nonce_sha256": plan["intent_nonce_sha256"],
                "provider_calls": 0, "official_final_admitted": 0}
    supervisor, supervisor_sha = _private_json(SUPERVISOR_RESULT)
    require(supervisor.get("schema") == SUPERVISOR_SCHEMA and
            supervisor.get("source_freeze_sha256") == plan_sha and
            supervisor.get("intent_sha256") == intent_sha and
            supervisor.get("intent_nonce_sha256") == plan["intent_nonce_sha256"] and
            supervisor.get("same_v6_or_terminal_final_identity_replay_authorized") is False and
            supervisor.get("provider_calls") ==
            supervisor.get("selection_or_final_tasks_dispatched") ==
            supervisor.get("official_final_admitted") == 0 and
            supervisor.get("artifact_review") == _artifact_review(),
            "v7_supervisor_or_private_artifact_review_changed")
    success = supervisor["status"] == "three_train_gui_cases_independently_reviewable"
    require(not success or
            (supervisor["artifact_review"]["permission_gate_passed"] is True and
             supervisor.get("child_result_sha256") is not None),
            "v7_success_without_owner_only_artifacts_or_child_result")
    if supervisor["status"] == "terminal_evidence_permission_failure_no_replay":
        require(supervisor["artifact_review"]["permission_gate_passed"] is False and
                supervisor.get("post_attempt_exact_baseline") is True,
                "v7_permission_failure_mislabeled_as_success")
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
                "v7_child_result_changed")
        if not success:
            require(json.loads(PUBLIC_RESULT.read_bytes()) ==
                    _public_result(supervisor, supervisor_sha),
                    "v7_terminal_public_outcome_changed")
            return _public_result(supervisor, supervisor_sha)
        scores = []
        generations = []
        for index, expected_sha in enumerate(child["case_receipt_sha256s"]):
            name, issue_key, expected_score = CASES[index]
            folder = CASES_DIR / f"{index:02d}-{name}"
            receipt, receipt_sha = _private_json(folder / "case-receipt.private.json")
            require(receipt_sha == expected_sha and
                    receipt.get("schema") == previous.CASE_SCHEMA and
                    receipt.get("case_index") == index and
                    receipt.get("case_name") == name and
                    receipt.get("issue_variant") == issue_key and
                    receipt.get("expected_score") == expected_score,
                    "v7_case_receipt_changed")
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
                    before == baseline and restored == baseline and
                    receipt.get("restored_exact") is True and
                    receipt.get("reset_receipt", {}).get("cold_reset") is True and
                    receipt["reset_receipt"].get("same_business_sha256") is True and
                    receipt["reset_receipt"].get("container_identity_changed") is True and
                    receipt.get("gui", {}).get("saved_visible_after_reload") is True and
                    receipt["gui"].get("screenshots_owner_only_from_creation") is True,
                    "v7_saved_state_or_exact_reset_changed")
            score = previous.score_saved_case(
                task, before, after, negative=expected_score == 0.0)
            require(score == receipt["score"] and score["score"] == expected_score,
                    "v7_independent_train_score_changed")
            screenshots = receipt["gui"]["screenshots_sha256"]
            require(set(screenshots) == {"policy.png", "issue-before.png",
                                         "issue-after.png"} and
                    receipt["gui"].get("frame_sequence") == [
                        {"role": name, "sha256": screenshots[name]}
                        for name in ("policy.png", "issue-before.png",
                                     "issue-after.png")],
                    "v7_screenshot_set_changed")
            for filename, digest in screenshots.items():
                path = folder / filename
                require(path.is_file() and not path.is_symlink() and
                        path.stat().st_mode & 0o077 == 0 and
                        one.sha(path.read_bytes()) == digest,
                        "v7_screenshot_bytes_or_owner_only_mode_changed")
            forensic = receipt["forensics"]
            require(forensic["raw_startup_logs_saved"] is True and
                    forensic["state_only_inspect_saved"] is True,
                    "v7_raw_startup_forensics_missing")
            state_path = folder / "docker-state.stdout.private.json"
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
                        "v7_raw_docker_log_or_state_bytes_changed")
            state = json.loads(state_path.read_bytes())
            require(state.get("Status") == "running" and
                    state.get("ExitCode") == 0 and
                    state.get("OOMKilled") is False and
                    state.get("Health", {}).get("Status") == "healthy",
                    "v7_saved_post_reset_world_not_healthy")
            scores.append(score["score"])
            generations.append(receipt["reset_receipt"]["generation"])
        if supervisor["status"] == "three_train_gui_cases_independently_reviewable":
            require(child.get("status") ==
                    "three_train_gui_cases_saved_pending_supervisor_review" and
                    child.get("completed_cases") == 3 and
                    child.get("scores") == scores == [1.0, 0.0, 1.0] and
                    generations == list(range(generations[0], generations[0] + 3)) and
                    supervisor["artifact_review"]["permission_gate_passed"] is True and
                    supervisor.get("post_attempt_exact_baseline") is True and
                    supervisor.get("child_process_group_terminated") is True and
                    supervisor.get("child", {}).get("exit_code") == 0 and
                    supervisor["child"].get("timed_out") is False,
                    "v7_success_without_independent_saved_gui_and_reset_audit")
    require(json.loads(PUBLIC_RESULT.read_bytes()) ==
            _public_result(supervisor, supervisor_sha),
            "v7_public_outcome_changed")
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
                         "three_train_gui_cases_saved_pending_supervisor_review" else 1)
    else:
        require(args.execute, "diagnostic_requires_explicit_execute")
        result = run_diagnostic(args.ratification_private,
                                args.reviewed_public_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
