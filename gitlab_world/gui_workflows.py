"""Deterministic native-GitLab GUI controls for causal workflow families.

All task mutations use visible Playwright UI only. The evaluator-owned caller
performs SQL/Git readback and cold reset after these functions return.
"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
from pathlib import Path

from . import runtime


async def policy(page, project: dict, folder: Path) -> dict:
    repo = project["full_path"]
    await page.goto(runtime.BASE + "/" + repo + "/-/blob/main/security/release-policy.md",
                    wait_until="domcontentloaded", timeout=90000)
    await page.get_by_text(project["policy"]["milestone_title"],
                           exact=False).first.wait_for(timeout=30000)
    visible = await page.locator("body").inner_text()
    if (project["advisories"][0]["cveID"] not in visible or
            project["principals"]["oncall"] not in visible):
        raise RuntimeError("rendered release policy lacks target source fields")
    file = folder / "policy.png"
    await page.screenshot(path=str(file), full_page=True)
    return {"policy_rendered": True,
            "policy_screenshot_sha256": hashlib.sha256(file.read_bytes()).hexdigest()}


async def milestone(page, project: dict, progress: dict, folder: Path,
                    *, wrong_due: bool = False) -> dict:
    source = await policy(page, project, folder)
    repo, policy_row = project["full_path"], project["policy"]
    due = date.fromisoformat(policy_row["milestone_due"])
    if wrong_due:
        due += timedelta(days=2)
    due_text = due.isoformat()
    await page.goto(runtime.BASE + "/" + repo + "/-/milestones",
                    wait_until="domcontentloaded")
    await page.get_by_role("link", name="New milestone").click()
    await page.locator("#milestone_title").fill(policy_row["milestone_title"])
    for _ in range(3):
        start = page.locator("#milestone_start_date")
        await start.click()
        await start.fill(policy_row["milestone_start"])
        await start.press("Tab")
        end = page.locator("#milestone_due_date")
        await end.click()
        await end.fill(due_text)
        await end.press("Tab")
        values = [await page.locator("#milestone_" + name).input_value()
                  for name in ("title", "start_date", "due_date")]
        if values == [policy_row["milestone_title"], policy_row["milestone_start"], due_text]:
            break
    if values != [policy_row["milestone_title"], policy_row["milestone_start"], due_text]:
        raise RuntimeError("visible milestone form values differ")
    await page.screenshot(path=str(folder / "milestone-form.png"), full_page=True)
    await page.get_by_role("button", name="Create milestone").click()
    await page.wait_for_url(lambda url: "/milestones/new" not in url, timeout=90000)
    if "/-/milestones/" not in page.url:
        raise RuntimeError("GitLab did not show a saved milestone")
    await page.get_by_text(policy_row["milestone_title"], exact=False).first.wait_for(timeout=30000)
    await page.screenshot(path=str(folder / "milestone-saved.png"), full_page=True)
    for key in ("active", "validation"):
        iid = int(progress["issue_iids"][key])
        await page.goto(runtime.BASE + "/" + repo + "/-/issues/" + str(iid),
                        wait_until="domcontentloaded", timeout=90000)
        await page.get_by_text("Active remediation:" if key == "active"
                               else "Validate mitigation:", exact=False).first.wait_for(timeout=30000)
        section = page.locator('[data-testid="work-item-milestone"]')
        await section.locator('[data-testid="edit-button"]').click()
        search = section.locator('[data-testid="listbox-search-input"]')
        await search.fill(policy_row["milestone_title"])
        await section.get_by_role("option").filter(
            has_text=policy_row["milestone_title"]).first.click()
        if await section.locator('[data-testid="apply-button"]').count():
            await section.locator('[data-testid="apply-button"]').click()
        await section.locator('[data-testid="edit-button"]').wait_for(timeout=30000)
        await section.get_by_text(policy_row["milestone_title"], exact=False).first.wait_for()
        await page.screenshot(path=str(folder / ("issue-" + key + "-linked.png")),
                              full_page=True)
    return {**source, "saved_visible": True, "issue_links_visible": 2,
            "wrong_due_negative": wrong_due,
            "milestone_screenshot_sha256": hashlib.sha256(
                (folder / "milestone-saved.png").read_bytes()).hexdigest()}


async def merge_request(page, project: dict, progress: dict, folder: Path,
                        *, wrong_mr: bool = False) -> dict:
    source = await policy(page, project, folder)
    repo = project["full_path"]
    await page.goto(runtime.BASE + "/" + repo + "/-/merge_requests",
                    wait_until="domcontentloaded", timeout=90000)
    await page.get_by_text("Merge requests", exact=False).first.wait_for()
    await page.screenshot(path=str(folder / "merge-request-list.png"), full_page=True)
    role = "stale" if wrong_mr else "approved"
    iid = int(progress["mr_iids"][role])
    await page.goto(runtime.BASE + "/" + repo + "/-/merge_requests/" + str(iid),
                    wait_until="domcontentloaded", timeout=90000)
    await page.locator('[data-testid="merge-button"]').wait_for(timeout=60000)
    body = await page.locator("body").inner_text()
    expected_hint = ("Historical workaround" if wrong_mr else
                     "approved release evidence")
    if project["asset_id"] not in body or expected_hint not in body:
        raise RuntimeError("MR description does not match selected native record")
    changes = page.get_by_role("link", name="Changes", exact=False)
    if await changes.count():
        await changes.first.click()
        await page.get_by_text("docs/response-runbook.md", exact=False).first.wait_for()
        await page.screenshot(path=str(folder / "merge-request-diff.png"), full_page=True)
        await page.get_by_role("link", name="Overview", exact=False).first.click()
    if await page.locator("#remove-source-branch-input").is_checked():
        await page.locator("#remove-source-branch-input").uncheck()
    await page.screenshot(path=str(folder / "merge-request-before.png"), full_page=True)
    await page.locator('[data-testid="merge-button"]').click(timeout=90000)
    await page.get_by_text("Merged", exact=True).first.wait_for(timeout=90000)
    await page.screenshot(path=str(folder / "merge-request-after.png"), full_page=True)
    return {**source, "saved_visible": True, "wrong_mr_negative": wrong_mr,
            "source_branch_left_intact": True,
            "merge_screenshot_sha256": hashlib.sha256(
                (folder / "merge-request-after.png").read_bytes()).hexdigest()}


async def access_handoff(page, project: dict, progress: dict, folder: Path,
                         *, overprivileged: bool = False) -> dict:
    source = await policy(page, project, folder)
    repo = project["full_path"]
    await page.goto(runtime.BASE + "/" + repo + "/-/project_members",
                    wait_until="domcontentloaded", timeout=90000)
    contractor = project["principals"]["contractor"]
    row = page.get_by_role("row").filter(has_text="@" + contractor)
    await row.wait_for(timeout=30000)
    await page.screenshot(path=str(folder / "members-before.png"), full_page=True)
    await row.locator('[data-testid="user-action-dropdown"] button').first.click()
    await row.get_by_text("Remove member", exact=True).click()
    dialog = page.get_by_role("dialog")
    await dialog.get_by_role("button", name="Remove member").click()
    await row.wait_for(state="detached", timeout=30000)
    await page.screenshot(path=str(folder / "member-removed.png"), full_page=True)
    await page.get_by_role("button", name="Invite members").first.click()
    invite = page.get_by_role("dialog")
    incoming = project["principals"]["incoming"]
    await invite.locator('[data-testid="members-token-select-input"]').fill(incoming)
    await invite.get_by_role("menuitem").filter(has_text=incoming).first.click()
    await invite.locator('[data-testid="base-dropdown-toggle"]').click()
    role = "Maintainer" if overprivileged else "Reporter"
    await invite.get_by_role("option", name=role, exact=True).click()
    expiry = invite.locator('input[placeholder="YYYY-MM-DD"]')
    await expiry.fill(project["policy"]["access_expiry"])
    await expiry.press("Tab")
    if await expiry.input_value() != project["policy"]["access_expiry"]:
        raise RuntimeError("visible access expiration form differs from policy")
    await page.screenshot(path=str(folder / "member-invite-form.png"), full_page=True)
    await invite.locator('[data-testid="invite-modal-submit"]').click()
    await invite.wait_for(state="hidden", timeout=60000)
    incoming_row = page.get_by_role("row").filter(has_text="@" + incoming)
    await incoming_row.wait_for(timeout=60000)
    visible = await incoming_row.inner_text()
    if role not in visible:
        raise RuntimeError("saved GitLab member row lacks intended role")
    expiry_saved = incoming_row.locator('input[placeholder="Expiration date"]')
    await expiry_saved.wait_for(timeout=30000)
    expected_expiry = project["policy"]["access_expiry"]
    # The modal can display the requested date yet persist the prior day in
    # this 18.5 image. Treat the saved members table as the visible readback,
    # then repair it through the inline GUI rather than accepting the modal.
    if await expiry_saved.input_value() != expected_expiry:
        await expiry_saved.fill(expected_expiry)
        await expiry_saved.press("Tab")
        await page.wait_for_timeout(450)
        await page.reload(wait_until="domcontentloaded")
        incoming_row = page.get_by_role("row").filter(has_text="@" + incoming)
        expiry_saved = incoming_row.locator('input[placeholder="Expiration date"]')
        await expiry_saved.wait_for(timeout=30000)
    if await expiry_saved.input_value() != expected_expiry:
        raise RuntimeError("saved GitLab membership expiration differs from policy")
    await page.screenshot(path=str(folder / "members-after.png"), full_page=True)
    return {**source, "saved_visible": True,
            "overprivileged_negative": overprivileged,
            "direct_member_row_visible": True,
            "member_screenshot_sha256": hashlib.sha256(
                (folder / "members-after.png").read_bytes()).hexdigest()}


async def _edit_repository_file(page, project: dict, path: str,
                                old_text: str, new_text: str,
                                folder: Path, label: str) -> None:
    repo = project["full_path"]
    await page.goto(runtime.BASE + "/" + repo + "/-/blob/main/" + path,
                    wait_until="domcontentloaded", timeout=90000)
    await page.get_by_role("button", name="Edit", exact=True).click()
    await page.get_by_text("Edit single file", exact=False).first.click()
    await page.wait_for_url(lambda url: "/-/edit/main/" in url, timeout=90000)
    editor = page.locator(".monaco-editor").first
    await editor.wait_for(timeout=30000)
    await editor.click()
    await page.keyboard.press("ControlOrMeta+F")
    find = page.locator(".find-widget.visible").first
    await find.get_by_role("button", name="Toggle Replace").click()
    await find.locator('textarea[aria-label="Find"]').fill(old_text)
    await find.locator('textarea[aria-label="Replace"]').fill(new_text)
    replace_all = find.get_by_role("button", name="Replace All", exact=False)
    await replace_all.wait_for(timeout=30000)
    if await replace_all.get_attribute("aria-disabled") == "true":
        raise RuntimeError("repository target text was not found in visible editor")
    await replace_all.click()
    await find.get_by_role("button", name="Close", exact=False).click()
    await page.screenshot(path=str(folder / (label + "-editor.png")), full_page=True)
    await page.locator('[data-testid="blob-edit-header-commit-button"]').click()
    dialog = page.get_by_role("dialog")
    await dialog.wait_for(timeout=30000)
    # The default branch is the intended saved artifact. GitLab may offer a
    # new branch as an alternative; require the original branch explicitly.
    target = dialog.get_by_text("Commit to the main branch", exact=False)
    if await target.count():
        await target.first.click()
    message = dialog.locator('input[name="commit_message"],textarea[name="commit_message"]')
    if await message.count():
        await message.first.fill("Reconcile response control " + label)
    await dialog.get_by_role("button", name="Commit changes").click()
    await page.wait_for_url(lambda url: "/-/edit/" not in url, timeout=90000)
    await page.screenshot(path=str(folder / (label + "-saved.png")), full_page=True)


async def ci_and_runbook(page, project: dict, progress: dict, folder: Path,
                         *, partial_negative: bool = False) -> dict:
    source = await policy(page, project, folder)
    current_ci = project["files"][".gitlab-ci.yml"]
    old_ci = "when: never"
    new_ci = "if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'"
    expected_ci = current_ci.replace(old_ci, new_ci)
    if expected_ci == current_ci:
        raise RuntimeError("CI source did not contain disabled gate")
    await _edit_repository_file(page, project, ".gitlab-ci.yml", old_ci, new_ci,
                                folder, "ci")
    if not partial_negative:
        current = project["files"]["docs/response-runbook.md"]
        old_contact = "Current contact: pending"
        new_contact = "Current contact: @" + project["principals"]["oncall"]
        expected = current.replace(old_contact, new_contact)
        if expected == current:
            raise RuntimeError("runbook source did not contain pending contact")
        await _edit_repository_file(page, project, "docs/response-runbook.md",
                                    old_contact, new_contact, folder, "runbook")
    return {**source, "saved_visible": True,
            "partial_change_negative": partial_negative,
            "ci_saved_screenshot_sha256": hashlib.sha256(
                (folder / "ci-saved.png").read_bytes()).hexdigest()}
