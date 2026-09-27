"""Train-project-only GitLab issue save/reload 1/0/1 calibration.

Run only after the original 100-ID sweep is terminal, with exclusive access to
the disposable GitLab world. This never writes the final GUI sweep index.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import time

from gitlab_world import (bootstrap, factory, gui_controls, operators, reset,
                          runtime, verify)


PRIVATE = runtime.PRIVATE / "train-issue-triage-probe"


def score_train_probe(project: dict, progress: dict,
                      before: dict, after: dict, *, wrong_issue: bool) -> float:
    """Read all monitored DB/Git state for exact target or plausible wrong issue."""
    project_id = int(progress["project_id"])
    if before["schema"] != verify.SCHEMA or before["project_ids"] != after["project_ids"]:
        raise RuntimeError("train issue probe did not preserve frozen project roster")
    verify._unchanged_tables(before, after, "issues", "issue_assignees", "issue_label_links")
    verify._unchanged_other_git(before, after, project_id)
    key = "historical_duplicate" if wrong_issue else "active"
    issue = verify._issue(before, project_id, int(progress["issue_iids"][key]))
    verify._only_issue_fields(before, after, {
        issue["id"]: {"due_date": project["policy"]["issue_due"]}})
    label_id = verify._project_label_id(
        before, project_id, factory._priority(project["advisories"][0]))
    verify._added_label_link(before, after, issue["id"], label_id)
    verify._assign_exact(before, after, issue["id"],
                         int(progress["user_ids"]["oncall"]))
    return 0.0 if wrong_issue else 1.0


async def run() -> dict:
    from playwright.async_api import async_playwright

    world = bootstrap.world()
    train_projects = sorted((p for p in world["projects"] if p["partition"] == "train"),
                            key=lambda p: p["index"])
    if len(train_projects) != 5:
        raise RuntimeError("training source project roster differs")
    project = train_projects[0]
    progress = json.loads(bootstrap.PROGRESS_FILE.read_text())["projects"][
        project["full_path"]]
    baseline = json.loads((runtime.PRIVATE / "baseline-persisted-state.json").read_text())
    if verify.state_snapshot()["business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("train issue probe did not start from frozen cold baseline")
    credentials = json.loads(operators.CREDENTIALS.read_text())["train"]
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = PRIVATE / ("run-" + str(time.time_ns()))
    folder.mkdir(mode=0o700)
    scores = []
    resets = []
    case_receipts = {}
    cases = (("positive-1", "active", False),
             ("wrong-retired-asset", "historical_duplicate", True),
             ("positive-2", "active", False))
    task = {"oracle": {"expected_priority": factory._priority(
        project["advisories"][0])}}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for label, issue_key, wrong_issue in cases:
                case_dir = folder / label
                case_dir.mkdir(mode=0o700)
                before = verify.state_snapshot()
                if before["business_sha256"] != baseline["business_sha256"]:
                    raise RuntimeError("train issue case lacked frozen baseline")
                context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                async def guard(route):
                    if gui_controls._local_url(route.request.url):
                        await route.continue_()
                    else:
                        await route.abort()
                await context.route("**/*", guard)
                page = await context.new_page()
                result = None
                try:
                    if await context.cookies():
                        raise RuntimeError("train issue browser context was not fresh")
                    await gui_controls._login(page, credentials["username"],
                                               credentials["password"])
                    gui = await gui_controls._gui_issue_triage(
                        page, project, progress, task, issue_key, case_dir)
                    after = verify.state_snapshot()
                    score = score_train_probe(project, progress, before, after,
                                              wrong_issue=wrong_issue)
                    result = {"label": label, "score": score,
                              "before_business_sha256": before["business_sha256"],
                              "after_business_sha256": after["business_sha256"],
                              "visible_reload_verified": gui[
                                  "due_date_reload_verified"],
                              "independent_saved_state_checked": True,
                              "no_regression_checked": True}
                finally:
                    await context.close()
                    cold = reset.reset()
                    resets.append(cold["same_business_sha256"])
                if result is None:
                    raise RuntimeError("train issue GUI case failed before scoring")
                post_reset = verify.state_snapshot()
                if post_reset["business_sha256"] != baseline["business_sha256"]:
                    raise RuntimeError("train issue probe did not restore DB/Git baseline")
                result["post_reset_business_sha256"] = post_reset["business_sha256"]
                result["cold_reset_verified"] = cold["same_business_sha256"]
                factory.write_private(case_dir / "receipt.json", result)
                case_receipts[label] = {"path": label + "/receipt.json",
                                        "sha256": factory.sha256(
                                            (case_dir / "receipt.json").read_bytes())}
                scores.append(score)
        finally:
            await browser.close()
    passed = scores == [1.0, 0.0, 1.0] and resets == [True] * 3
    private = {"schema": "envloop-gitlab-train-issue-triage-probe-v2",
               "workflow": "cross_record_issue_triage",
               "partition": "train", "project_path": project["full_path"],
               "scores": scores, "cold_resets": resets,
               "case_receipts": case_receipts,
               "baseline_business_sha256": baseline["business_sha256"],
               "generic_operator_sha256": hashlib.sha256(
                   Path(gui_controls.__file__).read_bytes()).hexdigest(),
               "probe_script_sha256": hashlib.sha256(
                   Path(__file__).read_bytes()).hexdigest(),
               "visible_reload_verified_all": True,
               "independent_saved_state_checked": True,
               "no_regression_checked": True,
               "passed": passed, "model_calls": 0,
               "official_final_admitted": 0}
    factory.write_private(folder / "summary-private.json", private)
    return {"schema": private["schema"], "partition": "train",
            "scores": scores, "cold_resets": sum(resets),
            "passed": passed,
            "generic_operator_sha256": private["generic_operator_sha256"],
            "private_receipt_sha256": factory.sha256(
                (folder / "summary-private.json").read_bytes()),
            "official_final_admitted": 0}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2, sort_keys=True))
