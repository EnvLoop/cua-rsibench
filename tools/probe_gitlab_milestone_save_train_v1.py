"""Train-project-only GitLab milestone save/reload calibration.

Run only after the original GitLab GUI sweep is terminal and no other GitLab
worker owns its disposable instance. This never touches the final sweep index.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import time

from gitlab_world import (bootstrap, factory, gui_controls, gui_workflows,
                          operators, reset, runtime, verify)


PRIVATE = runtime.PRIVATE / "train-milestone-save-probe"


def score_train_probe(project: dict, progress: dict,
                      before: dict, after: dict) -> float:
    """Apply the final milestone target/no-regression fields on a train source."""
    project_id = int(progress["project_id"])
    if before["schema"] != verify.SCHEMA or before["project_ids"] != after["project_ids"]:
        raise RuntimeError("train probe did not preserve the frozen project roster")
    verify._unchanged_tables(before, after, "issues", "milestones")
    verify._unchanged_other_git(before, after, project_id)
    new, removed, modified = verify._table_delta(before, after, "milestones")
    if len(new) != 1 or removed or modified:
        raise RuntimeError("train probe changed unrelated milestone rows")
    milestone = verify._rows_by_id(after["db"]["milestones"])[next(iter(new))]
    policy = project["policy"]
    if (milestone["project_id"] != project_id
            or milestone["title"] != policy["milestone_title"]
            or milestone["start_date"] != policy["milestone_start"]):
        raise RuntimeError("train probe milestone identity/start date differs")
    active = verify._issue(before, project_id, int(progress["issue_iids"]["active"]))
    validation = verify._issue(before, project_id, int(progress["issue_iids"]["validation"]))
    verify._only_issue_fields(before, after, {
        active["id"]: {"milestone_id": milestone["id"]},
        validation["id"]: {"milestone_id": milestone["id"]}})
    return 1.0 if milestone["due_date"] == policy["milestone_due"] else 0.0


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
    initial = verify.state_snapshot()
    if initial["business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("train probe did not start from frozen cold baseline")
    credentials = json.loads(operators.CREDENTIALS.read_text())["train"]
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder = PRIVATE / ("run-" + str(time.time_ns()))
    folder.mkdir(mode=0o700)
    scores = []
    resets = []
    visible_reload = []
    case_receipts = {}
    cases = (("positive-1", False), ("wrong-due-date", True),
             ("positive-2", False))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for label, wrong_due in cases:
                case_dir = folder / label
                case_dir.mkdir(mode=0o700)
                before = verify.state_snapshot()
                if before["business_sha256"] != baseline["business_sha256"]:
                    raise RuntimeError("train probe case lacked frozen baseline")
                context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                async def guard(route):
                    if gui_controls._local_url(route.request.url):
                        await route.continue_()
                    else:
                        await route.abort()
                await context.route("**/*", guard)
                page = await context.new_page()
                result = None
                after = None
                try:
                    if await context.cookies():
                        raise RuntimeError("train browser context was not fresh")
                    await gui_controls._login(page, credentials["username"],
                                               credentials["password"])
                    gui = await gui_workflows.milestone(
                        page, project, progress, case_dir, wrong_due=wrong_due)
                    after = verify.state_snapshot()
                    score = score_train_probe(project, progress, before, after)
                    result = {"label": label, "score": score,
                              "before_business_sha256": before["business_sha256"],
                              "after_business_sha256": after["business_sha256"],
                              "visible_reload_verified": gui[
                                  "issue_links_reload_verified"],
                              "issue_link_attempts": gui["issue_link_attempts"],
                              "independent_saved_state_checked": True,
                              "no_regression_checked": True}
                finally:
                    await context.close()
                    cold = reset.reset()
                    resets.append(cold["same_business_sha256"])
                if result is None:
                    raise RuntimeError("train milestone GUI case failed before scoring")
                post_reset = verify.state_snapshot()
                if post_reset["business_sha256"] != baseline["business_sha256"]:
                    raise RuntimeError("train milestone probe did not restore DB/Git baseline")
                result["post_reset_business_sha256"] = post_reset["business_sha256"]
                result["cold_reset_verified"] = cold["same_business_sha256"]
                factory.write_private(case_dir / "receipt.json", result)
                case_receipts[label] = {"path": label + "/receipt.json",
                                        "sha256": factory.sha256(
                                            (case_dir / "receipt.json").read_bytes())}
                scores.append(result["score"])
                visible_reload.append(result["visible_reload_verified"])
        finally:
            await browser.close()
    passed = scores == [1.0, 0.0, 1.0] and resets == [True] * 3 and all(visible_reload)
    private = {"schema": "envloop-gitlab-train-milestone-save-probe-v2",
               "workflow": "release_milestone_coordination",
               "partition": "train", "project_path": project["full_path"],
               "scores": scores, "cold_resets": resets,
               "case_receipts": case_receipts,
               "baseline_business_sha256": baseline["business_sha256"],
               "generic_operator_sha256": hashlib.sha256(
                   Path(gui_workflows.__file__).read_bytes()).hexdigest(),
               "probe_script_sha256": hashlib.sha256(
                   Path(__file__).read_bytes()).hexdigest(),
               "visible_reload_verified_all": all(visible_reload),
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
