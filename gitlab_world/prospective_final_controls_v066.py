"""Source-frozen prospective evaluator GUI controls for 100 GitLab candidates.

This lane never calls a model, admits a final task, or retries an uncertain ID.
Its live command is deliberately separate from the read-only plan/audit paths.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Awaitable, Callable

from cursibench import scale_final_v06
from cursibench.full_study_matrix_v1 import CELLS
from native_desktop_factory.v066_final_freeze import source_hashes as common_source_hashes
from tools import audit_gitlab_final_candidate_preflight_v1 as prior

from . import bootstrap, factory, gui_controls, reset, runtime, verify


ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = "envloop-gitlab-v066-source-bound-final-controls-plan-v1"
CASE_SCHEMA = "envloop-gitlab-v066-source-bound-case-v1"
TRIO_SCHEMA = "envloop-gitlab-v066-source-bound-trio-v1"
PROBE_SCHEMA = "envloop-gitlab-v066-unrelated-change-probe-v1"
EVENT_SCHEMA = "envloop-gitlab-v066-control-journal-event-v1"
PROOF_ENVELOPE_SCHEMA = "envloop-gitlab-v066-v06-proof-source-envelope-v1"
SOURCE_FILES = (
    "gitlab_world/prospective_final_controls_v066.py",
    "tools/audit_gitlab_final_candidate_preflight_v1.py",
    "src/cursibench/scale_final_v06.py",
    "gitlab_world/gui_controls.py", "gitlab_world/gui_workflows.py",
    "gitlab_world/reset.py", "gitlab_world/verify.py",
    "gitlab_world/bootstrap.py", "gitlab_world/factory.py",
    "gitlab_world/operators.py", "gitlab_world/runtime.py",
    "gitlab_world/vision_actor_v066_train.py",
)
CASES = {
    "cross_record_issue_triage": (("positive-1", "active", 1.0),
                                  ("wrong-retired-asset", "historical_duplicate", 0.0),
                                  ("positive-2", "active", 1.0)),
    "release_milestone_coordination": (("positive-1", "correct", 1.0),
                                      ("wrong-due-date", "wrong_due", 0.0),
                                      ("positive-2", "correct", 1.0)),
    "approved_merge_request_merge": (("positive-1", "approved", 1.0),
                                     ("wrong-stale-mr", "stale", 0.0),
                                     ("positive-2", "approved", 1.0)),
    "least_privilege_access_handoff": (("positive-1", "correct", 1.0),
                                      ("overprivileged-role", "overprivileged", 0.0),
                                      ("positive-2", "correct", 1.0)),
    "ci_and_runbook_reconciliation": (("positive-1", "full", 1.0),
                                     ("partial-ci-only", "partial", 0.0),
                                     ("positive-2", "full", 1.0)),
}


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return factory.canonical(value)


def source_sha256s() -> dict[str, str]:
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def amended_ratification(private: Path, public: Path, old_sha: str) -> dict:
    require(private.is_file() and not private.is_symlink() and
            private.stat().st_mode & 0o077 == 0 and
            private.parent.stat().st_mode & 0o077 == 0 and
            public.is_file() and not public.is_symlink(),
            "amended_v066_ratification_files_missing_or_unsafe")
    private_raw, public_raw = private.read_bytes(), public.read_bytes()
    value, visible = json.loads(private_raw), json.loads(public_raw)
    common = common_source_hashes()
    gitlab_adapter = sha((ROOT / "gitlab_world/vision_actor_v066_train.py").read_bytes())
    profiles = value.get("cell_profiles")
    try:
        ratified = datetime.fromisoformat(value.get("ratified_utc"))
    except (TypeError, ValueError):
        raise ValueError("amended_v066_ratification_timestamp_invalid") from None
    require(value.get("schema") == "cua-six-cell-action-profile-v066-ratification-v1" and
            value.get("status") == "ratified_pre_result" and
            ratified.tzinfo is not None and
            ratified.astimezone(timezone.utc) <= datetime.now(timezone.utc) and
            value.get("action_profile") == "scale-action-profile-v0.6.6" and
            value.get("base_and_selected_identical") is True and
            value.get("hidden_final_model_attempts_before_ratification") == 0 and
            value.get("common_source_sha256s") == common and
            type(profiles) is dict and set(profiles) == set(CELLS) and
            all(profile.get("common_source_sha256s") == common
                for profile in profiles.values()) and
            profiles["gitlab"]["adapter_sha256"] == gitlab_adapter and
            visible.get("schema") ==
            "cua-six-cell-v066-caret-code-only-ratification-public-v1" and
            visible.get("status") ==
            "new_source_bytes_frozen_for_evaluator_controls_only" and
            visible.get("private_ratification_sha256") == sha(private_raw) and
            visible.get("supersedes_old_private_ratification_sha256") == old_sha and
            visible.get("common_source_sha256s") == common and
            visible.get("cell_adapter_sha256s") == {
                cell: profiles[cell]["adapter_sha256"] for cell in CELLS} and
            visible.get("qualified_final_tasks") == 0 and
            visible.get("researcher_campaigns") == 0 and
            visible.get("official_final_model_results") == 0,
            "amended_v066_gitlab_source_ratification_changed")
    return {"private_sha256": sha(private_raw), "public_sha256": sha(public_raw),
            "common_source_sha256s": common, "gitlab_adapter_sha256": gitlab_adapter}


def base_inputs(private_root: Path, preflight_private: Path,
                preflight_public: Path, ratification_private: Path,
                ratification_public: Path) -> dict:
    private_root = private_root.absolute()
    context_world, train, selection, final, context = prior.active_world(private_root)
    preflight, preflight_sha = prior.read_json(preflight_private, private_root)
    visible = json.loads(preflight_public.read_bytes())
    require(visible.get("schema") == prior.PUBLIC_SCHEMA and
            visible.get("private_per_task_ledger_sha256") == preflight_sha and
            visible.get("official_final_admitted") == 0 and
            visible.get("retained_first_attempt_failures") == 6 and
            preflight.get("schema") == prior.PRIVATE_SCHEMA and
            preflight.get("official_final_admitted") == 0 and
            preflight.get("model_calls_in_controls") == 0 and
            preflight.get("auditor_source_sha256") ==
            sha((ROOT / "tools/audit_gitlab_final_candidate_preflight_v1.py").read_bytes()) and
            preflight.get("task_sets") == {
                "train": context["task_sets"]["train"],
                "selection": context["task_sets"]["selection"],
                "provisional_final": context["task_sets"]["official"]} and
            len(preflight.get("per_task_control_evidence", [])) == 100 and
            len(train) == len(selection) == 20 and len(final) == 100,
            "prior_per_task_candidate_preflight_changed")
    amended = amended_ratification(
        ratification_private, ratification_public,
        preflight["v066_code_only_ratification_sha256"])
    baseline, baseline_sha = prior.read_json(
        private_root / "baseline-persisted-state.json", private_root)
    prior.verify_snapshot(baseline, baseline, baseline["business_sha256"])
    progress, progress_sha = prior.read_json(
        private_root / "bootstrap-progress.json", private_root)
    require(type(progress.get("projects")) is dict and
            len(progress["projects"]) == 31,
            "original_gitlab_bootstrap_roster_changed")
    roster = []
    for identity, task, old_control in zip(
            context["task_sets"]["official"], final,
            preflight["per_task_control_evidence"], strict=True):
        require(identity["task_id"] == task["task_id"] == old_control["task_id"] and
                old_control["control_preflight_passed"] is True and
                old_control["official_admitted"] is False and
                task["template_group"] in CASES,
                "prospective_roster_differs_from_prior_per_task_evidence")
        roster.append({"task_id": task["task_id"],
                       "package_sha256": identity["package_sha256"],
                       "source_family_sha256": sha(task["source_family"].encode()),
                       "template_group": task["template_group"]})
    require(len({row["source_family_sha256"] for row in roster}) == 20 and
            all(count == 5 for count in Counter(
                row["source_family_sha256"] for row in roster).values()),
            "prospective_roster_not_twenty_complete_source_families")
    return {"private_root": private_root, "world": context_world,
            "source_paths": tuple(path.absolute() for path in
                                  (preflight_private, preflight_public,
                                   ratification_private, ratification_public)),
            "world_sha256": context["world_sha256"],
            "preflight_private_sha256": preflight_sha,
            "preflight_public_sha256": sha(preflight_public.read_bytes()),
            "baseline_sha256": baseline_sha,
            "baseline_business_sha256": baseline["business_sha256"],
            "bootstrap_progress_sha256": progress_sha,
            "amended_ratification": amended, "roster": roster}


def plan_payload(inputs: dict) -> dict:
    sources = source_sha256s()
    return {"schema": PLAN_SCHEMA, "cell_id": "gitlab",
            "application": "GitLab CE 18.5.0-ce.0",
            "application_image_id": runtime.IMAGE_ID,
            "action_profile": "scale-action-profile-v0.6.6",
            "world_sha256": inputs["world_sha256"],
            "preflight_private_sha256": inputs["preflight_private_sha256"],
            "preflight_public_sha256": inputs["preflight_public_sha256"],
            "baseline_sha256": inputs["baseline_sha256"],
            "baseline_business_sha256": inputs["baseline_business_sha256"],
            "bootstrap_progress_sha256": inputs["bootstrap_progress_sha256"],
            "amended_ratification_private_sha256":
            inputs["amended_ratification"]["private_sha256"],
            "amended_ratification_public_sha256":
            inputs["amended_ratification"]["public_sha256"],
            "source_sha256s": sources,
            "source_bundle_sha256": sha(canonical(sources)),
            "task_roster": inputs["roster"],
            "fixed_case_scores": [1.0, 0.0, 1.0],
            "fresh_cold_resets_per_task": 3,
            "historical_first_attempt_failures_retained": 6,
            "max_wall_seconds_per_task": 7200,
            "one_new_source_bound_attempt_per_id": True,
            "retry_failed_or_uncertain_id": False,
            "model_calls": 0, "official_final_admitted": 0}


def write_new(path: Path, value: dict, mode: int = 0o600) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def freeze_plan(run_dir: Path, inputs: dict) -> dict:
    run_dir = run_dir.absolute()
    require(run_dir.parent == inputs["private_root"] and
            not run_dir.exists() and not run_dir.is_symlink(),
            "fresh_private_run_directory_required")
    run_dir.mkdir(mode=0o700)
    (run_dir / "attempts").mkdir(mode=0o700)
    plan = plan_payload(inputs)
    plan["frozen_utc"] = datetime.now(timezone.utc).isoformat()
    plan_sha = write_new(run_dir / "plan.private.json", plan)
    return {"schema": PLAN_SCHEMA, "plan_sha256": plan_sha,
            "candidate_count": len(plan["task_roster"]),
            "source_family_count": 20, "model_calls": 0,
            "official_final_admitted": 0}


def validate_plan(run_dir: Path, inputs: dict) -> tuple[dict, str]:
    run_dir = run_dir.absolute()
    require(run_dir.parent == inputs["private_root"] and
            run_dir.is_dir() and not run_dir.is_symlink() and
            run_dir.stat().st_mode & 0o077 == 0,
            "prospective_run_directory_not_private")
    plan, plan_sha = prior.read_json(run_dir / "plan.private.json", inputs["private_root"])
    now = plan_payload(inputs)
    require({key: value for key, value in plan.items() if key != "frozen_utc"} == now and
            type(plan.get("frozen_utc")) is str and
            datetime.fromisoformat(plan["frozen_utc"]).tzinfo is not None and
            datetime.fromisoformat(plan["frozen_utc"]).astimezone(timezone.utc) <=
            datetime.now(timezone.utc),
            "prospective_control_plan_or_source_drift")
    return plan, plan_sha


def read_journal(run_dir: Path, plan_sha: str) -> list[dict]:
    path = run_dir / "journal.private.jsonl"
    if not path.exists():
        return []
    raw = prior.read_file(path, run_dir.parent)
    require(not raw or raw.endswith(b"\n"), "prospective_journal_incomplete_tail")
    rows = []
    previous = "0" * 64
    for number, line in enumerate(raw.splitlines(), 1):
        entry = json.loads(line)
        require(type(entry) is dict and entry.get("schema") == EVENT_SCHEMA and
                entry.get("seq") == number and entry.get("previous_sha256") == previous and
                entry.get("plan_sha256") == plan_sha and
                entry.get("kind") in ("intent", "terminal") and
                entry.get("entry_sha256") == sha(canonical({
                    key: value for key, value in entry.items() if key != "entry_sha256"})),
                "prospective_journal_chain_or_plan_changed")
        rows.append(entry)
        previous = entry["entry_sha256"]
    return rows


def journal_state(entries: list[dict], plan: dict) -> dict:
    completed = []
    pending = None
    failed = False
    roster = plan["task_roster"]
    for entry in entries:
        if entry["kind"] == "intent":
            require(pending is None and not failed and
                    len(completed) < len(roster) and
                    entry.get("task_index") == len(completed) and
                    entry.get("task_id") == roster[len(completed)]["task_id"] and
                    entry.get("package_sha256") ==
                    roster[len(completed)]["package_sha256"] and
                    entry.get("source_bundle_sha256") ==
                    plan["source_bundle_sha256"] and
                    entry.get("official_final_admitted") == 0,
                    "prospective_journal_replay_or_roster_drift")
            pending = entry
        else:
            require(pending is not None and
                    entry.get("task_index") == pending["task_index"] and
                    entry.get("task_id") == pending["task_id"] and
                    entry.get("status") in ("control_passed", "control_failed") and
                    entry.get("official_final_admitted") == 0 and
                    isinstance(entry.get("wall_seconds"), (int, float)) and
                    not isinstance(entry.get("wall_seconds"), bool) and
                    0 <= entry["wall_seconds"] and
                    (entry["status"] != "control_passed" or
                     entry["wall_seconds"] <= plan["max_wall_seconds_per_task"]) and
                    ((entry.get("error_type") is None) ==
                     (entry["status"] == "control_passed")) and
                    ((entry.get("trio_receipt_sha256") is not None) ==
                     (entry["status"] == "control_passed")),
                    "prospective_terminal_without_matching_intent")
            if entry["status"] == "control_passed":
                completed.append(entry)
            else:
                failed = True
            pending = None
    return {"completed": completed, "pending": pending, "failed": failed,
            "next_index": len(completed),
            "finished_100": len(completed) == len(roster) and not failed and pending is None}


def append_event(path: Path, plan_sha: str, entries: list[dict], event: dict) -> dict:
    previous = entries[-1]["entry_sha256"] if entries else "0" * 64
    record = {"schema": EVENT_SCHEMA, "seq": len(entries) + 1,
              "previous_sha256": previous, "plan_sha256": plan_sha,
              "utc": datetime.now(timezone.utc).isoformat(), **event}
    record["entry_sha256"] = sha(canonical(record))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        require(os.fstat(descriptor).st_mode & 0o077 == 0,
                "prospective_journal_not_private")
        raw = canonical(record) + b"\n"
        require(os.write(descriptor, raw) == len(raw),
                "prospective_journal_short_write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    entries.append(record)
    return record


def _unrelated_perturbation(positive_state: dict) -> dict:
    changed = copy.deepcopy(positive_state)
    labels = changed["db"]["labels"]
    require(type(labels) is list and labels and type(labels[0].get("title")) is str,
            "unrelated_probe_has_no_label_row")
    labels[0]["title"] += " [unrelated verifier probe]"
    changed.pop("business_sha256")
    changed["business_sha256"] = sha(canonical(changed))
    return changed


async def live_one(plan: dict, plan_sha: str, index: int,
                   run_dir: Path, baseline: dict) -> dict:
    """Execute only real GUI actions; the caller must journal intent first."""
    require(runtime.PRIVATE.resolve() == run_dir.parent.resolve(),
            "live_gitlab_worktree_does_not_own_private_world")
    from playwright.async_api import async_playwright
    item = plan["task_roster"][index]
    task = gui_controls._task(item["task_id"])
    require(task["template_group"] == item["template_group"] and
            sha(task["source_family"].encode()) == item["source_family_sha256"],
            "live_task_source_identity_changed")
    folder = run_dir / "attempts" / f"{index:03d}"
    folder.mkdir(mode=0o700, exist_ok=False)
    cases = []
    source_bundle = plan["source_bundle_sha256"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for name, variant, expected_score in CASES[item["template_group"]]:
                require(sha(canonical(source_sha256s())) == source_bundle,
                        "gui_or_verifier_source_drift_before_case")
                attempted = None
                try:
                    attempted = await gui_controls.attempt(
                        browser, task, variant, name, folder)
                finally:
                    reset_receipt = reset.reset()
                    restored = verify.state_snapshot()
                    require(restored["business_sha256"] ==
                            baseline["business_sha256"] and
                            reset_receipt["cold_reset"] is True and
                            reset_receipt["same_business_sha256"] is True and
                            reset_receipt["container_identity_changed"] is True,
                            "post_case_fresh_reset_readback_changed")
                    factory.write_private(folder / name / "after-reset-persisted-state.json",
                                          restored)
                require(attempted is not None and
                        attempted["persisted_oracle"]["score"] == expected_score and
                        sha(canonical(source_sha256s())) == source_bundle,
                        "gui_case_score_or_source_drift")
                raw_receipt = folder / name / "receipt.json"
                after = folder / name / "after-persisted-state.json"
                restored_path = folder / name / "after-reset-persisted-state.json"
                all_screens = {path.name: sha(path.read_bytes())
                               for path in sorted((folder / name).glob("*.png"))}
                require(len(all_screens) >= 2, "source_bound_case_gui_screens_missing")
                completion = {"schema": CASE_SCHEMA, "task_id": item["task_id"],
                              "case": name, "expected_score": expected_score,
                              "plan_sha256": plan_sha,
                              "source_bundle_sha256": source_bundle,
                              "raw_receipt_sha256": sha(raw_receipt.read_bytes()),
                              "after_state_sha256": sha(after.read_bytes()),
                              "restored_state_sha256": sha(restored_path.read_bytes()),
                              "all_gui_screenshot_sha256s": all_screens,
                              "reset_receipt": reset_receipt,
                              "model_calls": 0, "official_final_admitted": 0}
                proof = folder / name / "case-complete.private.json"
                factory.write_private(proof, completion)
                source_bound_attempt = {**attempted, "cold_reset": reset_receipt}
                prior.verify_case(run_dir.parent, folder / name,
                                  source_bound_attempt, task_id=item["task_id"],
                                  baseline=baseline, expected_score=expected_score)
                cases.append({"case": name, "case_completion_sha256": sha(proof.read_bytes())})
        finally:
            await browser.close()
    positive = json.loads((folder / "positive-1" /
                           "after-persisted-state.json").read_bytes())
    altered = _unrelated_perturbation(positive)
    response = verify.evaluate_final_task(
        task, baseline, altered, inspect_live_git=False)
    require(response["score"] == 0.0 and response["no_regression"] is False and
            response["persisted_oracle"] is True,
            "independent_verifier_accepted_unrelated_change")
    negative_path = folder / "unrelated-change-state.private.json"
    factory.write_private(negative_path, altered)
    probe = {"schema": PROBE_SCHEMA, "task_id": item["task_id"],
             "plan_sha256": plan_sha,
             "positive_state_sha256": sha((folder / "positive-1" /
                                           "after-persisted-state.json").read_bytes()),
             "unrelated_state_sha256": sha(negative_path.read_bytes()),
             "mutation": "first_existing_label_title_appended",
             "verifier_response": response,
             "model_calls": 0, "official_final_admitted": 0}
    probe_path = folder / "unrelated-probe.private.json"
    factory.write_private(probe_path, probe)
    trio = {"schema": TRIO_SCHEMA, "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "plan_sha256": plan_sha, "source_bundle_sha256": source_bundle,
            "cases": cases, "control_scores": [1.0, 0.0, 1.0],
            "unrelated_probe_sha256": sha(probe_path.read_bytes()),
            "model_calls": 0, "official_final_admitted": 0}
    trio_path = folder / "trio-complete.private.json"
    factory.write_private(trio_path, trio)
    return {"task_id": item["task_id"], "trio_receipt_sha256": sha(trio_path.read_bytes()),
            "control_scores": [1.0, 0.0, 1.0],
            "fresh_cold_resets": 3, "model_calls": 0,
            "official_final_admitted": 0}


def assert_live_world(plan: dict) -> dict:
    require(runtime.ACTIVE_VERSION == "v3", "gitlab_v3_cold_baseline_required")
    state = runtime.proof(runtime.WORLD)
    require(state["running"] is True and state["health"] == "healthy" and
            state["image_id"] == plan["application_image_id"],
            "original_gitlab_world_not_ready_or_image_changed")
    baseline = json.loads((runtime.PRIVATE / "baseline-persisted-state.json").read_bytes())
    current = verify.state_snapshot()
    require(current["business_sha256"] == baseline["business_sha256"] ==
            plan["baseline_business_sha256"],
            "gitlab_world_not_at_frozen_cold_baseline")
    return baseline


async def run_loop(run_dir: Path, inputs: dict, *, max_tasks: int,
                   execute_one: Callable[[dict, str, int, Path, dict], Awaitable[dict]],
                   readiness: Callable[[dict], dict]) -> dict:
    require(1 <= max_tasks <= 100, "bounded_max_tasks_1_to_100_required")
    plan, plan_sha = validate_plan(run_dir, inputs)
    lock = run_dir / ".dispatch.lock"
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = run_dir / "journal.private.jsonl"
        entries = read_journal(run_dir, plan_sha)
        state = journal_state(entries, plan)
        require(state["pending"] is None and not state["failed"],
                "unresolved_or_failed_id_requires_separate_amendment")
        for _ in range(max_tasks):
            if state["finished_100"]:
                break
            if state["completed"] and execute_one is live_one:
                audited, _public = audit_controls(run_dir, inputs)
                require(audited["completed_task_count"] == len(state["completed"]),
                        "prior_source_bound_gui_receipts_changed_before_next_intent")
            if "source_paths" in inputs:
                fresh = base_inputs(inputs["private_root"], *inputs["source_paths"])
                require(plan_payload(fresh) == {
                    key: value for key, value in plan.items() if key != "frozen_utc"},
                    "private_source_or_ratification_drift_before_intent")
            require(sha(canonical(source_sha256s())) == plan["source_bundle_sha256"],
                    "prospective_source_drift_before_intent")
            baseline = readiness(plan)
            index = state["next_index"]
            item = plan["task_roster"][index]
            append_event(journal, plan_sha, entries,
                         {"kind": "intent", "task_index": index,
                          "task_id": item["task_id"],
                          "package_sha256": item["package_sha256"],
                          "source_bundle_sha256": plan["source_bundle_sha256"],
                          "official_final_admitted": 0})
            started = time.monotonic()
            try:
                result = await execute_one(plan, plan_sha, index, run_dir, baseline)
                elapsed = time.monotonic() - started
                require(result.get("task_id") == item["task_id"] and
                        result.get("control_scores") == [1.0, 0.0, 1.0] and
                        result.get("fresh_cold_resets") == 3 and
                        result.get("model_calls") == 0 and
                        result.get("official_final_admitted") == 0 and
                        elapsed <= plan["max_wall_seconds_per_task"] and
                        scale_final_v06.is_hash(result.get("trio_receipt_sha256")) and
                        sha(canonical(source_sha256s())) == plan["source_bundle_sha256"],
                        "source_bound_gui_control_result_invalid")
                trio_path = (run_dir / "attempts" / f"{index:03d}" /
                             "trio-complete.private.json")
                trio, trio_sha = prior.read_json(trio_path, run_dir.parent)
                require(trio_sha == result["trio_receipt_sha256"] and
                        trio.get("schema") == TRIO_SCHEMA and
                        trio.get("task_id") == item["task_id"] and
                        trio.get("package_sha256") == item["package_sha256"] and
                        trio.get("plan_sha256") == plan_sha and
                        trio.get("source_bundle_sha256") == plan["source_bundle_sha256"],
                        "source_bound_trio_receipt_missing_or_changed")
            except Exception as exc:
                append_event(journal, plan_sha, entries,
                             {"kind": "terminal", "task_index": index,
                              "task_id": item["task_id"],
                              "status": "control_failed", "error_type": type(exc).__name__,
                              "wall_seconds": round(time.monotonic() - started, 3),
                              "trio_receipt_sha256": None,
                              "official_final_admitted": 0})
                raise RuntimeError("prospective_gui_control_failed_no_auto_replay") from exc
            append_event(journal, plan_sha, entries,
                         {"kind": "terminal", "task_index": index,
                          "task_id": item["task_id"],
                          "status": "control_passed", "error_type": None,
                          "wall_seconds": round(elapsed, 3),
                          "trio_receipt_sha256": result["trio_receipt_sha256"],
                          "official_final_admitted": 0})
            state = journal_state(entries, plan)
        return {"status": "evaluator_controls_only_not_admitted",
                "completed": len(state["completed"]),
                "remaining": 100 - len(state["completed"]),
                "model_calls": 0, "official_final_admitted": 0}
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def derive_v06_proofs(identity: dict, baseline_business_sha256: str,
                      validated: dict, *, plan_sha256: str,
                      source_bundle_sha256: str) -> dict:
    """Convert only independently validated raw evidence into exact v0.6 fields.

    The envelope must be rechecked by a later admission verifier. This pure
    function does not write a task proof or change a qualification status.
    """
    cases = validated["cases"]
    require([row["score"] for row in cases] == [1.0, 0.0, 1.0] and
            len(cases) == 3 and
            validated["probe_response"]["score"] == 0.0 and
            validated["probe_response"]["no_regression"] is False and
            validated["probe_response"]["persisted_oracle"] is True and
            all(row["restored_business_sha256"] == baseline_business_sha256 and
                row["mutated_business_sha256"] != baseline_business_sha256
                for row in cases),
            "v06_proof_conversion_requires_validated_positive_negative_reset_probe")
    reset_proof = {
        "schema": "cua-task-reset-proof-v0.6",
        "task_id": identity["task_id"],
        "package_sha256": identity["package_sha256"],
        "initial_state_sha256": baseline_business_sha256,
        "mutated_state_sha256": cases[0]["mutated_business_sha256"],
        "restored_state_sha256": cases[0]["restored_business_sha256"],
        "fresh_environment": True, "passed": True,
    }
    verifier_proof = {
        "schema": "cua-task-verifier-proof-v0.6",
        "task_id": identity["task_id"],
        "package_sha256": identity["package_sha256"],
        "evaluator_isolated": True, "positive_accepted": True,
        "negative_rejected": True, "unrelated_changes_rejected": True,
        "passed": True,
    }
    envelope = {
        "schema": PROOF_ENVELOPE_SCHEMA,
        "task_id": identity["task_id"],
        "package_sha256": identity["package_sha256"],
        "plan_sha256": plan_sha256,
        "source_bundle_sha256": source_bundle_sha256,
        "trio_receipt_sha256": validated["trio_receipt_sha256"],
        "case_completion_sha256s": [row["case_completion_sha256"] for row in cases],
        "unrelated_probe_sha256": validated["unrelated_probe_sha256"],
        "reset_proof_sha256": sha(scale_final_v06.json_bytes(reset_proof)),
        "verifier_proof_sha256": sha(scale_final_v06.json_bytes(verifier_proof)),
        "proofs_are_supporting_evidence_not_cell_admission": True,
    }
    return {"reset_proof": reset_proof, "verifier_proof": verifier_proof,
            "source_envelope": envelope}


def audit_controls(run_dir: Path, inputs: dict,
                   *, evaluator: Callable = verify.evaluate_final_task) -> tuple[dict, dict]:
    """Reopen every complete case; never infer a pass from the journal alone."""
    plan, plan_sha = validate_plan(run_dir, inputs)
    state = journal_state(read_journal(run_dir, plan_sha), plan)
    baseline, baseline_sha = prior.read_json(
        inputs["private_root"] / "baseline-persisted-state.json",
        inputs["private_root"])
    require(baseline_sha == plan["baseline_sha256"],
            "prospective_baseline_bytes_changed")
    prior.verify_snapshot(baseline, baseline, baseline["business_sha256"])
    tasks = {row["task_id"]: row for row in
             bootstrap.all_tasks(inputs["world"])}
    audited = []
    for index, terminal in enumerate(state["completed"]):
        identity = plan["task_roster"][index]
        task_id = identity["task_id"]
        task = tasks[task_id]
        folder = run_dir / "attempts" / f"{index:03d}"
        trio, trio_sha = prior.read_json(
            folder / "trio-complete.private.json", inputs["private_root"])
        expected = CASES[identity["template_group"]]
        require(trio_sha == terminal["trio_receipt_sha256"] and
                trio.get("schema") == TRIO_SCHEMA and
                trio.get("task_id") == task_id and
                trio.get("package_sha256") == identity["package_sha256"] and
                trio.get("plan_sha256") == plan_sha and
                trio.get("source_bundle_sha256") == plan["source_bundle_sha256"] and
                trio.get("control_scores") == [1.0, 0.0, 1.0] and
                trio.get("model_calls") == trio.get("official_final_admitted") == 0 and
                type(trio.get("cases")) is list and len(trio["cases"]) == 3,
                "prospective_trio_receipt_invalid")
        case_rows = []
        for (name, _variant, expected_score), reference in zip(
                expected, trio["cases"], strict=True):
            require(reference.get("case") == name and
                    scale_final_v06.is_hash(reference.get("case_completion_sha256")),
                    "prospective_case_reference_invalid")
            case_dir = folder / name
            complete, complete_sha = prior.read_json(
                case_dir / "case-complete.private.json", inputs["private_root"])
            receipt_path = case_dir / "receipt.json"
            after_path = case_dir / "after-persisted-state.json"
            restored_path = case_dir / "after-reset-persisted-state.json"
            raw_receipt, receipt_sha = prior.read_json(receipt_path, inputs["private_root"])
            after, after_sha = prior.read_json(after_path, inputs["private_root"])
            restored, restored_sha = prior.read_json(restored_path, inputs["private_root"])
            all_screens = {path.name: sha(prior.read_file(path, inputs["private_root"]))
                           for path in sorted(case_dir.glob("*.png"))}
            require(complete_sha == reference["case_completion_sha256"] and
                    complete.get("schema") == CASE_SCHEMA and
                    complete.get("task_id") == task_id and
                    complete.get("case") == name and
                    complete.get("expected_score") == expected_score and
                    complete.get("plan_sha256") == plan_sha and
                    complete.get("source_bundle_sha256") == plan["source_bundle_sha256"] and
                    complete.get("raw_receipt_sha256") == receipt_sha and
                    complete.get("after_state_sha256") == after_sha and
                    complete.get("restored_state_sha256") == restored_sha and
                    len(all_screens) >= 2 and
                    complete.get("all_gui_screenshot_sha256s") == all_screens and
                    complete.get("model_calls") ==
                    complete.get("official_final_admitted") == 0,
                    "prospective_case_completion_or_raw_bytes_changed")
            combined = {**raw_receipt, "cold_reset": complete["reset_receipt"]}
            prior.verify_case(inputs["private_root"], case_dir, combined,
                              task_id=task_id, baseline=baseline,
                              expected_score=expected_score)
            prior.verify_snapshot(restored, baseline,
                                  baseline["business_sha256"])
            require(after["business_sha256"] != baseline["business_sha256"] and
                    restored["business_sha256"] == baseline["business_sha256"],
                    "prospective_mutation_or_restoration_invalid")
            case_rows.append({"case": name, "score": expected_score,
                              "case_completion_sha256": complete_sha,
                              "mutated_business_sha256": after["business_sha256"],
                              "restored_business_sha256": restored["business_sha256"],
                              "reset_generation": complete["reset_receipt"]["generation"]})
        generations = [row["reset_generation"] for row in case_rows]
        require(generations == list(range(generations[0], generations[0] + 3)),
                "prospective_resets_not_three_consecutive_generations")
        probe, probe_sha = prior.read_json(
            folder / "unrelated-probe.private.json", inputs["private_root"])
        altered, altered_sha = prior.read_json(
            folder / "unrelated-change-state.private.json", inputs["private_root"])
        positive, positive_sha = prior.read_json(
            folder / "positive-1" / "after-persisted-state.json",
            inputs["private_root"])
        require(probe_sha == trio["unrelated_probe_sha256"] and
                probe.get("schema") == PROBE_SCHEMA and
                probe.get("task_id") == task_id and
                probe.get("plan_sha256") == plan_sha and
                probe.get("positive_state_sha256") == positive_sha and
                probe.get("unrelated_state_sha256") == altered_sha and
                probe.get("mutation") == "first_existing_label_title_appended" and
                probe.get("model_calls") == probe.get("official_final_admitted") == 0 and
                altered == _unrelated_perturbation(positive),
                "prospective_unrelated_change_probe_bytes_invalid")
        prior.verify_snapshot(altered, baseline, altered["business_sha256"])
        rechecked = evaluator(task, baseline, altered, inspect_live_git=False)
        require(rechecked == probe["verifier_response"] and
                rechecked.get("score") == 0.0 and
                rechecked.get("no_regression") is False and
                rechecked.get("persisted_oracle") is True,
                "prospective_independent_verifier_probe_changed")
        audited.append({"task_id": task_id,
                        "package_sha256": identity["package_sha256"],
                        "source_family_sha256": identity["source_family_sha256"],
                        "trio_receipt_sha256": trio_sha,
                        "cases": case_rows,
                        "unrelated_probe_sha256": probe_sha,
                        "probe_response": rechecked})
    require(len(audited) == len(state["completed"]),
            "prospective_completed_receipt_coverage_changed")
    full = state["finished_100"] and len(audited) == 100
    proof_material = (
        [derive_v06_proofs(plan["task_roster"][index],
                           baseline["business_sha256"], row,
                           plan_sha256=plan_sha,
                           source_bundle_sha256=plan["source_bundle_sha256"])
         for index, row in enumerate(audited)] if full else [])
    private = {"schema": "envloop-gitlab-v066-control-audit-private-v1",
               "status": "source_bound_evaluator_controls_only_not_official_admission",
               "plan_sha256": plan_sha,
               "source_bundle_sha256": plan["source_bundle_sha256"],
               "completed_task_count": len(audited),
               "pending_intent": state["pending"] is not None,
               "terminal_failure": state["failed"],
               "all_100_controls_independently_validated": full,
               "validated_tasks": audited,
               "unissued_v06_proof_material": proof_material,
               "proof_files_issued": False,
               "model_calls": 0, "official_final_admitted": 0}
    public = {"schema": "envloop-gitlab-v066-control-audit-public-v1",
              "status": "source_bound_evaluator_controls_only_not_official_admission",
              "plan_sha256": plan_sha,
              "source_bundle_sha256": plan["source_bundle_sha256"],
              "completed_task_count": len(audited),
              "remaining_task_count": 100 - len(audited),
              "historical_first_attempt_failures_retained": 6,
              "pending_intent": state["pending"] is not None,
              "terminal_failure": state["failed"],
              "all_100_controls_independently_validated": full,
              "v06_unissued_proof_material_source_bound_to_raw_receipts": full,
              "official_final_admitted": 0, "model_calls": 0,
              "researcher_campaigns": 0}
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze-plan", "audit-journal",
                                           "audit-controls", "run"))
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--preflight-private", type=Path, required=True)
    parser.add_argument("--preflight-public", type=Path, required=True)
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--ratification-public", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--max-tasks", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--private-audit-out", type=Path)
    parser.add_argument("--public-audit-out", type=Path)
    args = parser.parse_args()
    inputs = base_inputs(args.private_root, args.preflight_private,
                         args.preflight_public, args.ratification_private,
                         args.ratification_public)
    if args.action == "freeze-plan":
        result = freeze_plan(args.run_dir, inputs)
    elif args.action == "audit-journal":
        plan, plan_sha = validate_plan(args.run_dir, inputs)
        state = journal_state(read_journal(args.run_dir, plan_sha), plan)
        result = {"status": "journal_only_not_raw_receipt_audit",
                  "completed": len(state["completed"]),
                  "pending": state["pending"] is not None,
                  "failed": state["failed"], "official_final_admitted": 0}
    elif args.action == "audit-controls":
        require(runtime.PRIVATE.resolve() == args.private_root.resolve(),
                "raw_receipt_audit_requires_original_gitlab_worktree")
        private, result = audit_controls(args.run_dir, inputs)
        if args.private_audit_out or args.public_audit_out:
            require(args.private_audit_out is not None and
                    args.public_audit_out is not None and
                    args.private_audit_out.absolute().parent == args.run_dir.absolute() and
                    args.public_audit_out.absolute().parent ==
                    (ROOT / "docs/evidence").absolute() and
                    not args.private_audit_out.exists() and
                    not args.public_audit_out.exists(),
                    "fresh_private_and_public_control_audit_paths_required")
            digest = write_new(args.private_audit_out, private)
            result["private_audit_sha256"] = digest
            write_new(args.public_audit_out, result, 0o644)
    else:
        require(args.execute is True, "explicit_execute_flag_required_for_live_gui")
        require(runtime.PRIVATE.resolve() == args.private_root.resolve(),
                "live_gitlab_worktree_does_not_own_private_world")
        result = asyncio.run(run_loop(args.run_dir, inputs, max_tasks=args.max_tasks,
                                      execute_one=live_one, readiness=assert_live_world))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
