"""Dated, fail-closed batches around the frozen GitLab one-ID GUI supervisor.

This layer does not implement GUI actions, model calls, retries, or reset logic.
Each new ID is passed exactly once to the existing source-frozen supervisor,
whose child has the 7200-second process watchdog and exact cold-reset recovery.
The batch journal is append-only; an uncertain pending ID is never dispatched
again. An explicit resume can only reconcile an existing one-ID result.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path

from . import prospective_final_controls_v066 as lane
from . import v066_supervised_final_one_v1 as one


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = one.RUN_DIR / "batches-20260929"
PRIVATE_PLAN = BATCH_DIR / "source-plan.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-supervised-batch-plan-2026-09-29.json"
THREE_PUBLIC = ROOT / "docs/evidence/gitlab-v066-current-three-id-controls-2026-09-29.json"
THREE_PRIVATE = one.RUN_DIR / "current-v066-three-id-private-audit-20260929.json"
PLAN_SCHEMA = "envloop-gitlab-v066-supervised-batch-source-plan-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-supervised-batch-source-plan-public-v1"
EVENT_SCHEMA = "envloop-gitlab-v066-supervised-batch-event-v1"
RECEIPT_SCHEMA = "envloop-gitlab-v066-supervised-batch-receipt-private-v1"
RECEIPT_PUBLIC_SCHEMA = "envloop-gitlab-v066-supervised-batch-receipt-public-v1"
SOURCE_FILES = (
    "gitlab_world/v066_supervised_final_batch_v1.py",
    "tests/test_gitlab_v066_supervised_final_batch.py",
    "docs/FULL_STUDY_GITLAB_V066_BATCH_2026-09-29.md",
    "gitlab_world/v066_supervised_final_one_v1.py",
    "tests/test_gitlab_v066_supervised_final_one.py",
    "gitlab_world/prospective_final_controls_v066.py",
)


class BatchError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise BatchError(code)


def source_hashes() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _read_private(path: Path) -> tuple[dict, str]:
    return one.private_json(path)


def _initial_audit(old: dict, bound: dict, old_sha: str) -> tuple[dict, str, str]:
    journal = lane.read_journal(one.RUN_DIR, old_sha)
    state = lane.journal_state(journal, old)
    require(state["next_index"] == 3 and state["pending"] is None and
            not state["failed"], "batch_requires_three_clean_prior_ids")
    one._prior_supervision_complete(3, old_sha)
    current_private, current_public = lane.audit_controls(one.RUN_DIR, bound)
    previous, previous_sha = _read_private(THREE_PRIVATE)
    public_raw = THREE_PUBLIC.read_bytes()
    visible = json.loads(public_raw)
    require(previous == current_private and
            visible == {**current_public, "private_audit_sha256": previous_sha} and
            previous["completed_task_count"] == 3 and
            previous["pending_intent"] is False and
            previous["terminal_failure"] is False and
            previous["model_calls"] == previous["official_final_admitted"] == 0,
            "prior_three_raw_receipts_or_published_audit_changed")
    journal_path = one.RUN_DIR / "journal.private.jsonl"
    raw = journal_path.read_bytes()
    require(len(raw.splitlines()) == 6 and raw.endswith(b"\n"),
            "first_three_original_journal_not_exactly_six_events")
    return previous, previous_sha, one.sha(raw)


def freeze(ratification_private: Path) -> dict:
    require(not BATCH_DIR.exists() and not PRIVATE_PLAN.exists() and
            not PUBLIC_PLAN.exists(), "fresh_batch_source_freeze_required")
    wrapper, old, bound, old_sha = one.validate_plan(ratification_private)
    prior, prior_sha, journal_sha = _initial_audit(old, bound, old_sha)
    require(one.RUN_DIR.is_dir() and one.RUN_DIR.stat().st_mode & 0o077 == 0,
            "original_gitlab_run_directory_not_private")
    sources = source_hashes()
    BATCH_DIR.mkdir(mode=0o700)
    value = {
        "schema": PLAN_SCHEMA,
        "status": "source_frozen_three_prior_controls_no_batch_dispatch",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "original_100_id_plan_sha256": old_sha,
        "one_id_supervisor_plan_sha256": one.sha(one.PLAN.read_bytes()),
        "one_id_supervisor_source_bundle_sha256": wrapper["source_bundle_sha256"],
        "first_three_private_audit_sha256": prior_sha,
        "first_three_public_audit_sha256": one.sha(THREE_PUBLIC.read_bytes()),
        "first_three_journal_sha256": journal_sha,
        "first_three_supervision_result_sha256s": [
            _read_private(one.SUPERVISION / f"{index:03d}-result.private.json")[1]
            for index in range(3)],
        "baseline_business_sha256": old["baseline_business_sha256"],
        "source_sha256s": sources,
        "source_bundle_sha256": one.sha(one.canonical(sources)),
        "prior_control_count": prior["completed_task_count"],
        "one_id_hard_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
        "one_id_cold_reset_required": True,
        "automatic_same_id_replay": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    private_sha = one.write_new(PRIVATE_PLAN, value)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_batch_layer_no_live_batch_yet",
        "private_plan_sha256": private_sha,
        "source_bundle_sha256": value["source_bundle_sha256"],
        "original_100_id_plan_sha256": old_sha,
        "one_id_supervisor_plan_sha256": value["one_id_supervisor_plan_sha256"],
        "first_three_private_audit_sha256": prior_sha,
        "prior_control_count": 3,
        "remaining_control_count": 97,
        "one_id_hard_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
        "automatic_same_id_replay": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    one.write_new(PUBLIC_PLAN, public, 0o644)
    return public


def validate_plan(ratification_private: Path) -> tuple[dict, dict, dict, str]:
    wrapper, old, bound, old_sha = one.validate_plan(ratification_private)
    require(BATCH_DIR.is_dir() and not BATCH_DIR.is_symlink() and
            BATCH_DIR.stat().st_mode & 0o077 == 0,
            "batch_directory_missing_or_unsafe")
    plan, plan_sha = _read_private(PRIVATE_PLAN)
    visible = json.loads(PUBLIC_PLAN.read_bytes())
    previous, previous_sha = _read_private(THREE_PRIVATE)
    first_three = [
        _read_private(one.SUPERVISION / f"{index:03d}-result.private.json")[1]
        for index in range(3)]
    sources = source_hashes()
    require(plan.get("schema") == PLAN_SCHEMA and
            plan.get("status") ==
            "source_frozen_three_prior_controls_no_batch_dispatch" and
            plan.get("original_100_id_plan_sha256") == old_sha and
            plan.get("one_id_supervisor_plan_sha256") ==
            one.sha(one.PLAN.read_bytes()) and
            plan.get("one_id_supervisor_source_bundle_sha256") ==
            wrapper["source_bundle_sha256"] and
            plan.get("first_three_private_audit_sha256") == previous_sha and
            plan.get("first_three_public_audit_sha256") ==
            one.sha(THREE_PUBLIC.read_bytes()) and
            plan.get("first_three_journal_sha256") == one.sha(
                b"\n".join((one.RUN_DIR / "journal.private.jsonl")
                           .read_bytes().splitlines()[:6]) + b"\n") and
            plan.get("first_three_supervision_result_sha256s") == first_three and
            plan.get("baseline_business_sha256") ==
            old["baseline_business_sha256"] and
            plan.get("source_sha256s") == sources and
            plan.get("source_bundle_sha256") == one.sha(one.canonical(sources)) and
            plan.get("prior_control_count") == 3 and
            plan.get("one_id_hard_watchdog_seconds") == one.CHILD_TIMEOUT_SECONDS and
            plan.get("one_id_cold_reset_required") is True and
            plan.get("automatic_same_id_replay") is False and
            plan.get("model_calls") == plan.get("official_final_admitted") == 0 and
            previous.get("completed_task_count") == 3 and
            visible.get("schema") == PUBLIC_SCHEMA and
            visible.get("private_plan_sha256") == plan_sha and
            visible.get("source_bundle_sha256") == plan["source_bundle_sha256"] and
            visible.get("original_100_id_plan_sha256") == old_sha and
            visible.get("first_three_private_audit_sha256") == previous_sha and
            visible.get("prior_control_count") == 3 and
            visible.get("remaining_control_count") == 97 and
            visible.get("one_id_hard_watchdog_seconds") ==
            one.CHILD_TIMEOUT_SECONDS and
            visible.get("automatic_same_id_replay") is False and
            visible.get("model_calls") == 0 and
            visible.get("official_final_admitted") == 0,
            "source_bound_batch_plan_changed")
    try:
        frozen = datetime.fromisoformat(plan["frozen_utc"])
    except (KeyError, TypeError, ValueError):
        raise BatchError("batch_freeze_time_invalid") from None
    require(frozen.tzinfo is not None and
            frozen.astimezone(timezone.utc) <= datetime.now(timezone.utc),
            "batch_freeze_time_invalid")
    # Current raw evidence may extend beyond three IDs. The immutable prefix
    # must remain byte-for-byte equivalent to the already published audit.
    current, _ = lane.audit_controls(one.RUN_DIR, bound)
    require(current["completed_task_count"] >= 3 and
            current["validated_tasks"][:3] == previous["validated_tasks"] and
            current["plan_sha256"] == old_sha,
            "original_three_control_prefix_changed")
    return plan, old, bound, old_sha


def _read_journal(plan_sha: str, old: dict) -> tuple[list[dict], dict]:
    path = BATCH_DIR / "journal.private.jsonl"
    if not path.exists():
        return [], {"next_index": 3, "closed_batches": [], "pending_batch": None,
                    "pending_id": None, "stopped_failure": False}
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0,
            "batch_journal_missing_or_unsafe")
    raw = path.read_bytes()
    require(raw.endswith(b"\n"), "batch_journal_incomplete_tail")
    entries: list[dict] = []
    previous = "0" * 64
    state = {"next_index": 3, "closed_batches": [], "pending_batch": None,
             "pending_id": None, "stopped_failure": False}
    for seq, line in enumerate(raw.splitlines(), 1):
        entry = json.loads(line)
        require(type(entry) is dict and entry.get("schema") == EVENT_SCHEMA and
                entry.get("seq") == seq and
                entry.get("plan_sha256") == plan_sha and
                entry.get("previous_sha256") == previous and
                entry.get("entry_sha256") == one.sha(one.canonical({
                    key: value for key, value in entry.items()
                    if key != "entry_sha256"})),
                "batch_journal_hash_chain_changed")
        kind = entry.get("kind")
        pending = state["pending_batch"]
        if kind == "batch_start":
            require(pending is None and not state["stopped_failure"] and
                    entry.get("batch_number") == len(state["closed_batches"]) and
                    entry.get("start_index") == state["next_index"] and
                    type(entry.get("max_new_ids")) is int and
                    1 <= entry["max_new_ids"] <= 100 - state["next_index"],
                    "batch_journal_invalid_start_or_replay")
            state["pending_batch"] = {"batch_number": entry["batch_number"],
                                      "start_index": entry["start_index"],
                                      "max_new_ids": entry["max_new_ids"],
                                      "completed": 0,
                                      "start_entry_sha256": entry["entry_sha256"]}
        elif kind == "id_intent":
            require(pending is not None and state["pending_id"] is None and
                    pending["completed"] < pending["max_new_ids"] and
                    entry.get("batch_number") == pending["batch_number"] and
                    entry.get("task_index") == state["next_index"] and
                    entry.get("task_id") ==
                    old["task_roster"][state["next_index"]]["task_id"] and
                    entry.get("package_sha256") ==
                    old["task_roster"][state["next_index"]]["package_sha256"] and
                    lane.scale_final_v06.is_hash(
                        entry.get("pre_id_raw_audit_sha256")) and
                    entry.get("baseline_business_sha256") ==
                    old["baseline_business_sha256"],
                    "batch_journal_invalid_id_intent")
            state["pending_id"] = entry
        elif kind == "id_completed":
            require(pending is not None and state["pending_id"] is not None and
                    entry.get("batch_number") == pending["batch_number"] and
                    entry.get("task_index") == state["next_index"] and
                    all(lane.scale_final_v06.is_hash(entry.get(key)) for key in
                        ("supervisor_result_sha256", "raw_audit_sha256",
                         "baseline_business_sha256")) and
                    entry["baseline_business_sha256"] ==
                    old["baseline_business_sha256"],
                    "batch_journal_invalid_id_completion")
            pending["completed"] += 1
            state["next_index"] += 1
            state["pending_id"] = None
        elif kind == "id_failed":
            require(pending is not None and state["pending_id"] is not None and
                    entry.get("batch_number") == pending["batch_number"] and
                    entry.get("task_index") == state["next_index"] and
                    lane.scale_final_v06.is_hash(entry.get("supervisor_result_sha256")) and
                    entry.get("no_replay") is True,
                    "batch_journal_invalid_terminal_failure")
            state["pending_id"] = None
            state["stopped_failure"] = True
        elif kind == "batch_end":
            require(pending is not None and state["pending_id"] is None and
                    entry.get("batch_number") == pending["batch_number"] and
                    entry.get("start_index") == pending["start_index"] and
                    entry.get("completed_count") == pending["completed"] and
                    entry.get("next_index") == state["next_index"] and
                    ((entry.get("status") == "completed_requested_ids" and
                      pending["completed"] == pending["max_new_ids"] and
                      not state["stopped_failure"]) or
                     (entry.get("status") == "stopped_on_failed_id_no_replay" and
                      state["stopped_failure"])),
                    "batch_journal_invalid_batch_end")
            state["closed_batches"].append({**pending,
                                            "status": entry["status"],
                                            "end_entry_sha256": entry["entry_sha256"]})
            state["pending_batch"] = None
        else:
            raise BatchError("batch_journal_unknown_event")
        entries.append(entry)
        previous = entry["entry_sha256"]
    return entries, state


def _append(entries: list[dict], plan_sha: str, payload: dict) -> dict:
    path = BATCH_DIR / "journal.private.jsonl"
    require(not path.is_symlink() and
            (not path.exists() or path.stat().st_mode & 0o077 == 0),
            "batch_journal_output_not_private")
    event = {"schema": EVENT_SCHEMA, "seq": len(entries) + 1,
             "plan_sha256": plan_sha,
             "previous_sha256": entries[-1]["entry_sha256"] if entries
             else "0" * 64, **payload}
    event["entry_sha256"] = one.sha(one.canonical(event))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as stream:
        stream.write(one.canonical(event) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    entries.append(event)
    return event


@contextmanager
def _batch_lock():
    path = BATCH_DIR / ".batch.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        require(os.fstat(fd).st_mode & 0o077 == 0,
                "batch_lock_not_private")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _verify_passed(index: int, old: dict, bound: dict,
                   old_sha: str) -> tuple[str, str]:
    receipt_path = one.SUPERVISION / f"{index:03d}-result.private.json"
    receipt, receipt_sha = _read_private(receipt_path)
    require(receipt.get("schema") == one.RESULT_SCHEMA and
            receipt.get("status") ==
            "one_id_completed_and_raw_receipts_independently_audited" and
            receipt.get("task_index") == index and
            receipt.get("task_id") == old["task_roster"][index]["task_id"] and
            receipt.get("original_100_id_plan_sha256") == old_sha and
            receipt.get("post_attempt_baseline_exact") is True and
            receipt.get("raw_audit") == {
                "completed_task_count": index + 1,
                "all_current_raw_receipts_reopened": True} and
            receipt.get("provider_or_gui_replay_authorized") is False and
            receipt.get("official_final_admitted") == 0 and
            receipt.get("child", {}).get("child_terminated") is True and
            receipt["child"].get("timed_out") is False and
            receipt["child"].get("exit_code") == 0,
            "one_id_supervision_not_cleanly_completed")
    state = lane.journal_state(lane.read_journal(one.RUN_DIR, old_sha), old)
    require(state["next_index"] == index + 1 and
            state["pending"] is None and not state["failed"],
            "one_id_original_journal_not_cleanly_completed")
    audit, _ = lane.audit_controls(one.RUN_DIR, bound)
    require(audit["completed_task_count"] == index + 1 and
            audit["pending_intent"] is False and
            audit["terminal_failure"] is False and
            audit["validated_tasks"][-1]["task_id"] ==
            old["task_roster"][index]["task_id"],
            "one_id_independent_raw_audit_failed")
    baseline = lane.assert_live_world(old)
    require(baseline["business_sha256"] == old["baseline_business_sha256"],
            "next_id_cold_baseline_changed")
    return receipt_sha, one.sha(one.canonical(audit))


def _verify_failed(index: int, old: dict, old_sha: str) -> str:
    receipt, receipt_sha = _read_private(
        one.SUPERVISION / f"{index:03d}-result.private.json")
    state = lane.journal_state(lane.read_journal(one.RUN_DIR, old_sha), old)
    require(receipt.get("schema") == one.RESULT_SCHEMA and
            receipt.get("task_index") == index and
            receipt.get("task_id") == old["task_roster"][index]["task_id"] and
            receipt.get("status") in (
                "one_id_terminal_no_replay_exactly_reset",
                "manual_review_required_no_replay") and
            receipt.get("provider_or_gui_replay_authorized") is False and
            receipt.get("official_final_admitted") == 0 and
            state["next_index"] == index,
            "failed_id_receipt_or_journal_changed")
    return receipt_sha


def _receipt_paths(number: int) -> tuple[Path, Path]:
    return (BATCH_DIR / f"batch-{number:03d}-receipt.private.json",
            ROOT / "docs/evidence" /
            f"gitlab-v066-supervised-batch-{number:03d}-2026-09-29.json")


def _finalize_receipt(number: int, entries: list[dict], state: dict,
                      plan_sha: str, old_sha: str) -> dict:
    closed = state["closed_batches"][number]
    private_path, public_path = _receipt_paths(number)
    in_batch = [entry for entry in entries
                if entry.get("batch_number") == number]
    result_hashes = [entry["supervisor_result_sha256"] for entry in in_batch
                     if entry["kind"] in ("id_completed", "id_failed")]
    receipt = {"schema": RECEIPT_SCHEMA,
               "status": closed["status"],
               "batch_number": number,
               "plan_sha256": plan_sha,
               "original_100_id_plan_sha256": old_sha,
               "start_index": closed["start_index"],
               "max_new_ids": closed["max_new_ids"],
               "completed_count": closed["completed"],
               "next_index": closed["start_index"] + closed["completed"],
               "terminal_journal_entry_sha256": closed["end_entry_sha256"],
               "supervisor_result_sha256s": result_hashes,
               "automatic_same_id_replay": False,
               "official_final_admitted": 0}
    if private_path.exists():
        saved, private_sha = _read_private(private_path)
        require(saved == receipt, "closed_batch_private_receipt_changed")
    else:
        private_sha = one.write_new(private_path, receipt)
    visible = {"schema": RECEIPT_PUBLIC_SCHEMA,
               "status": closed["status"],
               "batch_number": number,
               "private_receipt_sha256": private_sha,
               "plan_sha256": plan_sha,
               "start_index": closed["start_index"],
               "completed_count": closed["completed"],
               "next_index": receipt["next_index"],
               "terminal_journal_entry_sha256": closed["end_entry_sha256"],
               "model_calls": 0,
               "official_final_admitted": 0}
    if public_path.exists():
        require(json.loads(public_path.read_bytes()) == visible,
                "closed_batch_public_receipt_changed")
    else:
        one.write_new(public_path, visible, 0o644)
    return visible


def _reconcile_pending_id(entries: list[dict], state: dict, plan_sha: str,
                          old: dict, bound: dict, old_sha: str) -> tuple[list[dict], dict]:
    intent = state["pending_id"]
    if intent is None:
        return entries, state
    index = intent["task_index"]
    result_path = one.SUPERVISION / f"{index:03d}-result.private.json"
    require(result_path.is_file(),
            "pending_id_without_supervisor_result_manual_review_no_replay")
    try:
        result_sha, audit_sha = _verify_passed(index, old, bound, old_sha)
    except Exception:
        result_sha = _verify_failed(index, old, old_sha)
        _append(entries, plan_sha, {
            "kind": "id_failed", "batch_number": intent["batch_number"],
            "task_index": index, "supervisor_result_sha256": result_sha,
            "no_replay": True})
    else:
        _append(entries, plan_sha, {
            "kind": "id_completed", "batch_number": intent["batch_number"],
            "task_index": index, "supervisor_result_sha256": result_sha,
            "raw_audit_sha256": audit_sha,
            "baseline_business_sha256": old["baseline_business_sha256"]})
    return _read_journal(plan_sha, old)


def run_batch(ratification_private: Path, *, max_new_ids: int,
              resume_pending: bool = False) -> dict:
    require(type(max_new_ids) is int and 1 <= max_new_ids <= 97,
            "explicit_bounded_max_new_ids_required")
    plan, old, bound, old_sha = validate_plan(ratification_private)
    plan_sha = one.sha(PRIVATE_PLAN.read_bytes())
    with _batch_lock():
        entries, state = _read_journal(plan_sha, old)
        for number in range(len(state["closed_batches"])):
            _finalize_receipt(number, entries, state, plan_sha, old_sha)
        if state["pending_batch"] is not None:
            require(resume_pending and
                    state["pending_batch"]["max_new_ids"] == max_new_ids,
                    "pending_batch_requires_explicit_same_budget_resume")
            entries, state = _reconcile_pending_id(
                entries, state, plan_sha, old, bound, old_sha)
            batch = state["pending_batch"]
        else:
            require(not state["stopped_failure"],
                    "prior_batch_failed_id_no_replay")
            require(not resume_pending, "no_pending_batch_to_resume")
            require(max_new_ids <= 100 - state["next_index"],
                    "max_new_ids_exceeds_remaining_roster")
            current = lane.journal_state(
                lane.read_journal(one.RUN_DIR, old_sha), old)
            require(current["next_index"] == state["next_index"] and
                    current["pending"] is None and not current["failed"],
                    "external_one_id_progress_or_uncertain_journal")
            one._prior_supervision_complete(state["next_index"], old_sha)
            audit, _ = lane.audit_controls(one.RUN_DIR, bound)
            require(audit["completed_task_count"] == state["next_index"],
                    "batch_start_raw_receipt_count_mismatch")
            lane.assert_live_world(old)
            number = len(state["closed_batches"])
            _append(entries, plan_sha, {
                "kind": "batch_start", "batch_number": number,
                "start_index": state["next_index"],
                "max_new_ids": max_new_ids})
            entries, state = _read_journal(plan_sha, old)
            batch = state["pending_batch"]
        require(batch is not None, "batch_journal_pending_state_missing")
        while batch["completed"] < batch["max_new_ids"] and not state["stopped_failure"]:
            index = state["next_index"]
            require(state["pending_id"] is None,
                    "pending_id_cannot_be_replayed")
            current = lane.journal_state(
                lane.read_journal(one.RUN_DIR, old_sha), old)
            require(current["next_index"] == index and
                    current["pending"] is None and not current["failed"],
                    "external_one_id_progress_or_uncertain_journal")
            audit, _ = lane.audit_controls(one.RUN_DIR, bound)
            require(audit["completed_task_count"] == index,
                    "before_id_raw_receipt_count_mismatch")
            lane.assert_live_world(old)
            require(not (one.SUPERVISION /
                         f"{index:03d}-intent.private.json").exists() and
                    not (one.SUPERVISION /
                         f"{index:03d}-result.private.json").exists(),
                    "same_id_supervisor_attempt_already_exists")
            item = old["task_roster"][index]
            _append(entries, plan_sha, {
                "kind": "id_intent", "batch_number": batch["batch_number"],
                "task_index": index, "task_id": item["task_id"],
                "package_sha256": item["package_sha256"],
                "pre_id_raw_audit_sha256": one.sha(one.canonical(audit)),
                "baseline_business_sha256": old["baseline_business_sha256"]})
            # The unchanged supervisor owns the hard child watchdog, exact
            # reset, journal terminalization and one-use-per-ID policy.
            one.run_one(ratification_private)
            entries, state = _reconcile_pending_id(
                entries, _read_journal(plan_sha, old)[1],
                plan_sha, old, bound, old_sha)
            batch = state["pending_batch"]
            require(batch is not None, "batch_disappeared_after_one_id")
        status = ("stopped_on_failed_id_no_replay" if state["stopped_failure"]
                  else "completed_requested_ids")
        _append(entries, plan_sha, {
            "kind": "batch_end", "batch_number": batch["batch_number"],
            "start_index": batch["start_index"],
            "completed_count": batch["completed"],
            "next_index": state["next_index"], "status": status})
        entries, state = _read_journal(plan_sha, old)
        return _finalize_receipt(batch["batch_number"], entries, state,
                                 plan_sha, old_sha)


def audit(ratification_private: Path) -> dict:
    _plan, old, bound, old_sha = validate_plan(ratification_private)
    plan_sha = one.sha(PRIVATE_PLAN.read_bytes())
    entries, state = _read_journal(plan_sha, old)
    for number in range(len(state["closed_batches"])):
        private_path, public_path = _receipt_paths(number)
        require(private_path.is_file() and public_path.is_file(),
                "closed_batch_receipt_missing")
        _finalize_receipt(number, entries, state, plan_sha, old_sha)
    current, _ = lane.audit_controls(one.RUN_DIR, bound)
    require(current["completed_task_count"] == state["next_index"],
            "batch_audit_current_receipt_count_mismatch")
    for event in entries:
        if event["kind"] not in ("id_completed", "id_failed"):
            continue
        index = event["task_index"]
        result, result_sha = _read_private(
            one.SUPERVISION / f"{index:03d}-result.private.json")
        require(result_sha == event["supervisor_result_sha256"] and
                result.get("task_index") == index and
                result.get("task_id") == old["task_roster"][index]["task_id"] and
                result.get("official_final_admitted") == 0 and
                result.get("provider_or_gui_replay_authorized") is False,
                "batch_audit_supervisor_result_bytes_changed")
        if event["kind"] == "id_completed":
            require(result.get("status") ==
                    "one_id_completed_and_raw_receipts_independently_audited" and
                    result.get("post_attempt_baseline_exact") is True and
                    index < current["completed_task_count"] and
                    current["validated_tasks"][index]["task_id"] ==
                    old["task_roster"][index]["task_id"],
                    "batch_audit_historical_completion_changed")
            prefix = {**current,
                      "completed_task_count": index + 1,
                      "validated_tasks": current["validated_tasks"][:index + 1],
                      "pending_intent": False,
                      "terminal_failure": False,
                      "all_100_controls_independently_validated": False,
                      "unissued_v06_proof_material": [],
                      "proof_files_issued": False}
            require(one.sha(one.canonical(prefix)) == event["raw_audit_sha256"],
                    "batch_audit_historical_raw_receipt_digest_changed")
        else:
            require(result.get("status") in (
                "one_id_terminal_no_replay_exactly_reset",
                "manual_review_required_no_replay") and
                state["stopped_failure"],
                "batch_audit_historical_terminal_changed")
    return {"status": "source_bound_controls_only_not_official_admission",
            "completed_current_controls": state["next_index"],
            "closed_batch_count": len(state["closed_batches"]),
            "pending_batch": state["pending_batch"] is not None,
            "pending_id": state["pending_id"] is not None,
            "terminal_failure": state["stopped_failure"],
            "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit", "run-batch"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--max-new-ids", type=int)
    parser.add_argument("--resume-pending", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(args.ratification_private)
    elif args.action == "audit":
        result = audit(args.ratification_private)
    else:
        require(args.execute is True and args.max_new_ids is not None,
                "explicit_batch_budget_and_execute_required")
        result = run_batch(args.ratification_private,
                           max_new_ids=args.max_new_ids,
                           resume_pending=args.resume_pending)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
