"""Visible-GitLab GUI positive/near-miss controls for one original final ID.

Fixture bootstrap and independent readback are outside the agent action path.
Task mutations here use only Playwright's visible browser UI. This is a
deterministic development control, not a student-model run or official final.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from . import bootstrap, factory, gui_workflows, operators, quarantine, reset, runtime, verify


PRIVATE = runtime.PRIVATE / "gui-controls"


def _task(task_id: str) -> dict:
    found = [task for task in bootstrap.all_tasks(bootstrap.world())
             if task["task_id"] == task_id]
    if len(found) != 1:
        raise ValueError("task ID not unique in private world")
    task = found[0]
    if task["template_group"] not in (
            "cross_record_issue_triage", "release_milestone_coordination",
            "approved_merge_request_merge", "least_privilege_access_handoff",
            "ci_and_runbook_reconciliation"):
        raise ValueError("GUI control driver missing for this workflow")
    return task


def _local_url(value: str) -> bool:
    uri = urlsplit(value)
    return ((uri.scheme == "http" and uri.hostname in ("127.0.0.1", "localhost")
             and uri.port == 8014 and not uri.username and not uri.password)
            or uri.scheme in ("about", "blob", "data"))


async def _login(page, username: str, password: str) -> None:
    await page.goto(runtime.BASE + "/users/sign_in", wait_until="domcontentloaded")
    await page.locator("#user_login").fill(username)
    await page.locator("#user_password").fill(password)
    await page.get_by_role("button", name="Sign in").click()
    await page.wait_for_url(lambda value: "users/sign_in" not in value, timeout=90000)


async def _gui_issue_triage(page, project: dict, progress: dict,
                            task: dict, issue_key: str, folder: Path) -> dict:
    repo = project["full_path"]
    issue_iid = int(progress["issue_iids"][issue_key])
    policy = project["policy"]
    # Confirm that the policy and source register are actually rendered in
    # GitLab's original repository UI, not merely available to setup code.
    await page.goto(runtime.BASE + "/" + repo + "/-/blob/main/security/release-policy.md",
                    wait_until="domcontentloaded", timeout=90000)
    await page.get_by_text(policy["milestone_title"], exact=False).first.wait_for(timeout=30000)
    policy_text = await page.locator("body").inner_text()
    if (project["advisories"][0]["cveID"] not in policy_text or
            project["principals"]["oncall"] not in policy_text):
        raise RuntimeError("rendered policy lacks target advisory or on-call owner")
    await page.screenshot(path=str(folder / "policy.png"), full_page=True)

    await page.goto(runtime.BASE + "/" + repo + "/-/issues/" + str(issue_iid),
                    wait_until="domcontentloaded", timeout=90000)
    await page.get_by_text("Active remediation:" if issue_key == "active"
                           else "Historical verification:", exact=False).last.wait_for(timeout=30000)
    await page.screenshot(path=str(folder / "issue-before.png"), full_page=True)

    assignee = page.locator('[data-testid="work-item-assignees"]')
    await assignee.locator('[data-testid="edit-button"]').click()
    user = project["principals"]["oncall"]
    await assignee.get_by_role("option").filter(has_text="@" + user).click()
    await page.get_by_text("@" + user, exact=False).first.wait_for(timeout=30000)

    labels = page.locator('[data-testid="work-item-labels"]')
    await labels.locator('[data-testid="edit-button"]').click()
    label = task["oracle"]["expected_priority"]
    await labels.get_by_role("option").filter(has_text=label).click()
    await labels.locator('[data-testid="apply-button"]').click()
    await labels.locator('[data-testid="' + label + '"]').wait_for(timeout=30000)

    dates = page.locator('[data-testid="work-item-due-dates"]')
    await dates.locator('[data-testid="edit-button"]').click()
    expected_date = date.fromisoformat(policy["issue_due"]).strftime("%b %d, %Y").replace(" 0", " ")
    visible_date = ""
    for _ in range(3):
        due = dates.locator("#due-date-input")
        await due.fill(policy["issue_due"])
        await due.press("Tab")
        if await due.input_value() != policy["issue_due"]:
            continue
        await dates.locator('[data-testid="apply-button"]').click()
        value = dates.locator('[data-testid="due-date-value"]')
        await value.filter(has_not_text="None").wait_for(timeout=30000)
        visible_date = (await value.inner_text()).strip()
        if visible_date == expected_date:
            break
        await dates.locator('[data-testid="edit-button"]').click()
    if visible_date != expected_date:
        raise RuntimeError("GitLab visible due date differs from policy after bounded retries")
    await page.screenshot(path=str(folder / "issue-after.png"), full_page=True)
    return {"policy_rendered": True, "issue_iid": issue_iid,
            "saved_visible": True,
            "visible_assignee": await assignee.locator('a[href$="/' + user + '"]').count() > 0,
            "visible_priority": await labels.locator('[data-testid="' + label + '"]').count() > 0,
            "visible_due_date": True,
            "screenshot_sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                                  for name in ("policy.png", "issue-before.png", "issue-after.png")}}


async def attempt(browser, task: dict, issue_key: str, name: str,
                  run_folder: Path) -> dict:
    project, progress = verify._context(task)
    folder = run_folder / name
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    baseline = json.loads((runtime.PRIVATE / "baseline-persisted-state.json").read_text())
    before = verify.state_snapshot()
    if before["business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("GUI attempt did not start from frozen cold baseline")
    context = await browser.new_context(viewport={"width": 1440, "height": 1000})
    blocked = []
    request_paths = []
    async def guard(route):
        url = route.request.url
        if _local_url(url):
            uri = urlsplit(url)
            if uri.scheme == "http" and uri.path.startswith("/api/"):
                request_paths.append({"method": route.request.method,
                                      "path": uri.path})
            await route.continue_()
        else:
            blocked.append(urlsplit(url).hostname or "non-http")
            await route.abort()
    await context.route("**/*", guard)
    page = await context.new_page()
    try:
        if await context.cookies():
            raise RuntimeError("new browser context contains preexisting auth")
        credentials = json.loads(operators.CREDENTIALS.read_text())[
            "final_candidate_unsealed"]
        await _login(page, credentials["username"], credentials["password"])
        if task["template_group"] == "cross_record_issue_triage":
            gui = await _gui_issue_triage(page, project, progress, task, issue_key, folder)
        elif task["template_group"] == "release_milestone_coordination":
            gui = await gui_workflows.milestone(
                page, project, progress, folder, wrong_due=issue_key == "wrong_due")
        elif task["template_group"] == "approved_merge_request_merge":
            gui = await gui_workflows.merge_request(
                page, project, progress, folder, wrong_mr=issue_key == "stale")
        elif task["template_group"] == "least_privilege_access_handoff":
            gui = await gui_workflows.access_handoff(
                page, project, progress, folder,
                overprivileged=issue_key == "overprivileged")
        elif task["template_group"] == "ci_and_runbook_reconciliation":
            gui = await gui_workflows.ci_and_runbook(
                page, project, progress, folder,
                partial_negative=issue_key == "partial")
        else:
            raise RuntimeError("GUI workflow driver was not dispatched")
    finally:
        await context.close()
    after = verify.state_snapshot()
    factory.write_private(folder / "after-persisted-state.json", after)
    scored = verify.evaluate_final_task(task, before, after)
    receipt = {"schema": "envloop-gitlab-gui-control-attempt-v1", "task_id": task["task_id"],
               "case": name, "negative_variant": issue_key,
               "fresh_browser_context": True, "gui": gui,
               "persisted_oracle": scored, "blocked_external_request_hosts": sorted(set(blocked)),
               "local_api_request_paths": request_paths,
               "raw_har_retained": False, "credential_retained_in_receipt": False,
               "scoped_non_admin_operator": True,
               "model_calls": 0}
    factory.write_private(folder / "receipt.json", receipt)
    return receipt


async def run(task_id: str, *, exposed_development: bool = True) -> dict:
    from playwright.async_api import async_playwright
    task = _task(task_id)
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_folder = PRIVATE / task_id / ("trio-" + str(time.time_ns()))
    run_folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    attempts = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                cases_by_family = {
                "cross_record_issue_triage": (
                    ("positive-1", "active"),
                    ("wrong-retired-asset", "historical_duplicate"),
                    ("positive-2", "active")),
                "release_milestone_coordination": (
                    ("positive-1", "correct"), ("wrong-due-date", "wrong_due"),
                    ("positive-2", "correct")),
                "approved_merge_request_merge": (
                    ("positive-1", "approved"), ("wrong-stale-mr", "stale"),
                    ("positive-2", "approved")),
                "least_privilege_access_handoff": (
                    ("positive-1", "correct"),
                    ("overprivileged-role", "overprivileged"),
                    ("positive-2", "correct")),
                "ci_and_runbook_reconciliation": (
                    ("positive-1", "full"), ("partial-ci-only", "partial"),
                    ("positive-2", "full")),
            }
                cases = cases_by_family[task["template_group"]]
                for name, issue_key in cases:
                    attempt_result = None
                    try:
                        attempt_result = await attempt(browser, task, issue_key, name, run_folder)
                    finally:
                        reset_receipt = reset.reset()
                        if attempt_result is not None:
                            attempt_result["cold_reset"] = reset_receipt
                    if attempt_result is None:
                        raise RuntimeError("GUI attempt failed before persisted scoring")
                    attempts.append(attempt_result)
            finally:
                await browser.close()
    except Exception as exc:
        factory.write_private(run_folder / "failed-run.json", {
            "schema": "envloop-gitlab-gui-driver-failure-v1",
            "task_id": task_id, "family": task["template_group"],
            "completed_attempt_count": len(attempts),
            "error_type": type(exc).__name__,
            "private_exception": str(exc)[:4000],
            "official_final_admitted": 0})
        raise
    scores = [item["persisted_oracle"]["score"] for item in attempts]
    passed = scores == [1.0, 0.0, 1.0] and all(
        item["cold_reset"]["same_business_sha256"] and
        item["gui"]["policy_rendered"] and item["gui"]["saved_visible"]
        for item in attempts)
    # Direct development inspection exposes a whole project family. The
    # evaluator-owned sweeper retains every task ID, screenshot, and oracle in
    # private storage, and does not release a task-level result to researchers.
    exposure = (quarantine.add_by_task(task_id, reason="gui_development_control")
                if exposed_development else quarantine.public_counts())
    result = {"schema": "envloop-gitlab-original-world-gui-trio-v1",
              "task_id": task_id, "source_family_sha256": factory.sha256(task["source_family"]),
              "development_gui_control_passed": passed, "scores": scores,
              "fresh_browser_attempts": len(attempts),
              "cold_resets": sum(bool(item["cold_reset"]["cold_reset"]) for item in attempts),
              "model_calls": 0, "official_final_admitted": 0,
              "evaluator_owned_private_control": not exposed_development,
              "exposure_quarantine": exposure,
              "limitation": "Unsealed original development candidate; one GUI trio does not qualify 100 tasks."}
    factory.write_private(run_folder / "trio-private.json", {
        **result, "attempts": attempts})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.task_id)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
