"""Source-frozen, bounded continuation of the audited GitLab v3 branch.

The original failed tenth first attempt remains terminal in the original run.
Only the audited v3 fresh-clone branch may continue, beginning at index 10.
Every later identity gets one supervised child and no automatic replay.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import sys

from . import prospective_final_controls_v066 as lane
from . import v066_infra_requalification_v1 as recovery
from . import v066_supervised_final_one_v1 as one


ROOT = Path(__file__).resolve().parents[1]
BRANCH = recovery.BRANCH
CONTINUATION = BRANCH / "continuation-v1-20260929"
SUPERVISION = CONTINUATION / "supervision"
BATCHES = CONTINUATION / "batches"
PRIVATE_FREEZE = CONTINUATION / "source-freeze.private.json"
PUBLIC_FREEZE = ROOT / "docs/evidence/gitlab-v066-requalified-continuation-source-freeze-2026-09-29.json"
V3_OUTCOME_PUBLIC_SHA256 = "8f00ef0a0b00bccf121e64b4d1c091407e776d9166a493f62f6355754aa7931b"
V3_SOURCE_PUBLIC_SHA256 = "5f5910fd5795ecd498049b6f731e8a469e68fe8cbdffee6513b83eae889f5eb5"
START_INDEX = 10
START_EVENTS = 20
MAX_BATCH = 5
PRIVATE_SCHEMA = "envloop-gitlab-v066-requalified-continuation-source-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-requalified-continuation-source-public-v1"
SUPERVISOR_INTENT_SCHEMA = "envloop-gitlab-v066-requalified-continuation-intent-private-v1"
SUPERVISOR_RESULT_SCHEMA = "envloop-gitlab-v066-requalified-continuation-result-private-v1"
BATCH_EVENT_SCHEMA = "envloop-gitlab-v066-requalified-continuation-batch-event-private-v1"
BATCH_RECEIPT_SCHEMA = "envloop-gitlab-v066-requalified-continuation-batch-receipt-private-v1"
BATCH_PUBLIC_SCHEMA = "envloop-gitlab-v066-requalified-continuation-batch-receipt-public-v1"
SOURCE_FILES = (
    "gitlab_world/v066_requalified_continuation_v1.py",
    "tests/test_gitlab_v066_requalified_continuation.py",
    "docs/FULL_STUDY_GITLAB_V066_REQUALIFIED_CONTINUATION_2026-09-29.md",
)


class ContinuationError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ContinuationError(code)


def _read_private(path: Path) -> tuple[dict, str]:
    return one.private_json(path)


def _source_hashes() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _source_bundle() -> str:
    return one.sha(one.canonical(_source_hashes()))


def _v3_context(ratification_private: Path) -> dict:
    """Reopen v3 raw evidence without Docker or trusting a status label."""
    v3_private, original, audited, _public = recovery.validate_freeze(
        ratification_private)
    old = original["old"]
    old_sha = original["old_sha"]
    require(one.sha(recovery.PUBLIC_FREEZE.read_bytes()) ==
            V3_SOURCE_PUBLIC_SHA256 and
            one.sha(recovery.PUBLIC_OUTCOME.read_bytes()) ==
            V3_OUTCOME_PUBLIC_SHA256 and
            v3_private["original_full_failed_journal_sha256"] ==
            original["journal_full_sha256"] and
            v3_private["original_failed_partial_attempt_manifest_sha256"] ==
            original["failed_attempt_manifest_sha256"],
            "v3_public_source_or_original_failure_changed")
    outcome = json.loads(recovery.PUBLIC_OUTCOME.read_bytes())
    result, result_sha = _read_private(
        recovery.SUPERVISION / "009-result.private.json")
    intent, intent_sha = _read_private(
        recovery.SUPERVISION / "009-intent.private.json")
    saved_audit, saved_audit_sha = _read_private(recovery.PRIVATE_OUTCOME)
    require(outcome.get("schema") == recovery.OUTCOME_SCHEMA and
            outcome.get("status") == "same_identity_fresh_clone_requalified" and
            outcome.get("branch_completed_controls") == START_INDEX and
            outcome.get("original_completed_controls") == START_INDEX - 1 and
            outcome.get("original_terminal_failure_retained") is True and
            outcome.get("continuation_dispatch_authorized") is False and
            outcome.get("private_audit_sha256") == saved_audit_sha and
            outcome.get("source_freeze_sha256") == V3_SOURCE_PUBLIC_SHA256 and
            result.get("schema") == recovery.RESULT_SCHEMA and
            result.get("status") == "same_identity_fresh_clone_requalified" and
            result.get("task_index") == START_INDEX - 1 and
            result.get("task_id") == old["task_roster"][START_INDEX - 1]["task_id"] and
            result.get("original_100_id_plan_sha256") == old_sha and
            result.get("original_failed_result_sha256") ==
            original["failed_result_sha256"] and
            result.get("post_attempt_baseline_exact") is True and
            result.get("child", {}).get("child_terminated") is True and
            result["child"].get("process_group_terminated") is True and
            result["child"].get("group_survivor_observed_after_child_wait") is False and
            result["child"].get("timed_out") is False and
            result["child"].get("exit_code") == 0 and
            result.get("automatic_same_id_replay") is False and
            result.get("official_final_admitted") == 0 and
            intent.get("schema") == recovery.INTENT_SCHEMA and
            intent.get("task_index") == START_INDEX - 1 and
            intent.get("task_id") == result["task_id"] and
            intent.get("source_freeze_sha256") ==
            one.sha(recovery.PRIVATE_FREEZE.read_bytes()) and
            saved_audit.get("schema") == recovery.AUDIT_SCHEMA and
            saved_audit.get("status") == "same_identity_fresh_clone_requalified" and
            saved_audit.get("requalification_result_sha256") == result_sha and
            saved_audit.get("original_full_failed_journal_sha256") ==
            original["journal_full_sha256"] and
            saved_audit.get("original_failed_result_sha256") ==
            original["failed_result_sha256"] and
            saved_audit.get("branch_completed_controls") == START_INDEX and
            saved_audit.get("continuation_dispatch_authorized") is False and
            saved_audit.get("official_final_admitted") == 0,
            "v3_retry_result_or_independent_audit_changed")
    journal_raw = (BRANCH / "journal.private.jsonl").read_bytes()
    lines = journal_raw.splitlines(keepends=True)
    entries = lane.read_journal(BRANCH, old_sha)
    state = lane.journal_state(entries, old)
    require(len(lines) == len(entries) and len(lines) >= START_EVENTS and
            all(line.endswith(b"\n") for line in lines) and
            len(audited["validated_tasks"]) >= START_INDEX and
            audited["validated_tasks"][START_INDEX - 1]["task_id"] ==
            result["task_id"] and
            entries[START_EVENTS - 1]["kind"] == "terminal" and
            entries[START_EVENTS - 1]["status"] == "control_passed" and
            entries[START_EVENTS - 1]["task_index"] == START_INDEX - 1 and
            state["next_index"] >= START_INDEX and
            audited["completed_task_count"] == state["next_index"],
            "v3_ten_control_prefix_or_branch_journal_changed")
    prefix = b"".join(lines[:START_EVENTS])
    tenth_manifest = recovery._tree_manifest(BRANCH / "attempts" / "009")
    ten_rows_sha = one.sha(one.canonical(audited["validated_tasks"][:START_INDEX]))
    if audited["completed_task_count"] == START_INDEX:
        require(audited["pending_intent"] is False and
                audited["terminal_failure"] is False and
                saved_audit.get("branch_raw_audit_sha256") ==
                one.sha(one.canonical(audited)) ==
                result.get("raw_audit", {}).get("audit_private_sha256"),
                "v3_saved_ten_raw_audit_changed")
    return {
        "old": old, "bound": original["bound"], "old_sha": old_sha,
        "original": original, "audited": audited, "journal_state": state,
        "v3_result_sha256": result_sha, "v3_intent_sha256": intent_sha,
        "v3_private_audit_sha256": saved_audit_sha,
        "v3_public_outcome_sha256": V3_OUTCOME_PUBLIC_SHA256,
        "v3_private_freeze_sha256": one.sha(recovery.PRIVATE_FREEZE.read_bytes()),
        "v3_public_freeze_sha256": V3_SOURCE_PUBLIC_SHA256,
        "ten_journal_prefix_sha256": one.sha(prefix),
        "ten_journal_prefix": prefix,
        "tenth_attempt_manifest_sha256": tenth_manifest,
        "ten_validated_rows_sha256": ten_rows_sha,
    }


def _public_freeze(private: dict, private_sha: str) -> dict:
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_ten_controls_no_continuation_dispatched",
        "private_freeze_sha256": private_sha,
        "source_bundle_sha256": private["source_bundle_sha256"],
        "original_100_id_plan_sha256": private["original_100_id_plan_sha256"],
        "original_failed_journal_sha256": private["original_failed_journal_sha256"],
        "original_failed_attempt_manifest_sha256":
            private["original_failed_attempt_manifest_sha256"],
        "v3_public_outcome_sha256": private["v3_public_outcome_sha256"],
        "v3_private_audit_sha256": private["v3_private_audit_sha256"],
        "ten_journal_prefix_sha256": private["ten_journal_prefix_sha256"],
        "ten_validated_rows_sha256": private["ten_validated_rows_sha256"],
        "completed_current_profile_controls": START_INDEX,
        "remaining_original_roster_controls": 100 - START_INDEX,
        "max_new_ids_per_batch": MAX_BATCH,
        "one_child_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
        "automatic_same_id_replay": False,
        "model_calls": 0, "official_final_admitted": 0,
    }


def freeze(ratification_private: Path) -> dict:
    require(not CONTINUATION.exists() and not CONTINUATION.is_symlink() and
            not PUBLIC_FREEZE.exists(), "fresh_continuation_source_freeze_required")
    context = _v3_context(ratification_private)
    require(context["journal_state"]["next_index"] == START_INDEX and
            context["journal_state"]["pending"] is None and
            not context["journal_state"]["failed"],
            "continuation_freeze_requires_clean_ten_prefix")
    source_sha256s = _source_hashes()
    CONTINUATION.mkdir(mode=0o700)
    SUPERVISION.mkdir(mode=0o700)
    BATCHES.mkdir(mode=0o700)
    private = {
        "schema": PRIVATE_SCHEMA,
        "status": "source_frozen_ten_controls_no_continuation_dispatched",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "original_100_id_plan_sha256": context["old_sha"],
        "original_failed_journal_sha256":
            context["original"]["journal_full_sha256"],
        "original_failed_result_sha256":
            context["original"]["failed_result_sha256"],
        "original_failed_attempt_manifest_sha256":
            context["original"]["failed_attempt_manifest_sha256"],
        "v3_public_outcome_sha256": context["v3_public_outcome_sha256"],
        "v3_private_audit_sha256": context["v3_private_audit_sha256"],
        "v3_result_sha256": context["v3_result_sha256"],
        "v3_intent_sha256": context["v3_intent_sha256"],
        "v3_private_freeze_sha256": context["v3_private_freeze_sha256"],
        "v3_public_freeze_sha256": context["v3_public_freeze_sha256"],
        "ten_journal_prefix_sha256": context["ten_journal_prefix_sha256"],
        "tenth_attempt_manifest_sha256":
            context["tenth_attempt_manifest_sha256"],
        "ten_validated_rows_sha256": context["ten_validated_rows_sha256"],
        "source_sha256s": source_sha256s,
        "source_bundle_sha256": one.sha(one.canonical(source_sha256s)),
        "start_index": START_INDEX, "end_exclusive": 100,
        "max_new_ids_per_batch": MAX_BATCH,
        "one_child_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
        "group_term_grace_seconds": recovery.GROUP_TERM_GRACE_SECONDS,
        "group_kill_grace_seconds": recovery.GROUP_KILL_GRACE_SECONDS,
        "automatic_same_id_replay": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    private_sha = one.write_new(PRIVATE_FREEZE, private)
    public = _public_freeze(private, private_sha)
    one.write_new(PUBLIC_FREEZE, public, 0o644)
    return public


def validate_freeze(ratification_private: Path) -> tuple[dict, dict, dict]:
    context = _v3_context(ratification_private)
    private, private_sha = _read_private(PRIVATE_FREEZE)
    require(private.get("schema") == PRIVATE_SCHEMA and
            private.get("status") ==
            "source_frozen_ten_controls_no_continuation_dispatched" and
            private.get("original_100_id_plan_sha256") == context["old_sha"] and
            private.get("original_failed_journal_sha256") ==
            context["original"]["journal_full_sha256"] and
            private.get("original_failed_result_sha256") ==
            context["original"]["failed_result_sha256"] and
            private.get("original_failed_attempt_manifest_sha256") ==
            context["original"]["failed_attempt_manifest_sha256"] and
            all(private.get(key) == context[key] for key in (
                "v3_public_outcome_sha256", "v3_private_audit_sha256",
                "v3_result_sha256", "v3_intent_sha256",
                "v3_private_freeze_sha256", "v3_public_freeze_sha256",
                "ten_journal_prefix_sha256", "tenth_attempt_manifest_sha256",
                "ten_validated_rows_sha256")) and
            private.get("source_sha256s") == _source_hashes() and
            private.get("source_bundle_sha256") == _source_bundle() and
            private.get("start_index") == START_INDEX and
            private.get("end_exclusive") == 100 and
            private.get("max_new_ids_per_batch") == MAX_BATCH and
            private.get("one_child_watchdog_seconds") ==
            one.CHILD_TIMEOUT_SECONDS and
            private.get("group_term_grace_seconds") ==
            recovery.GROUP_TERM_GRACE_SECONDS and
            private.get("group_kill_grace_seconds") ==
            recovery.GROUP_KILL_GRACE_SECONDS and
            private.get("automatic_same_id_replay") is False and
            private.get("model_calls") ==
            private.get("official_final_admitted") == 0 and
            json.loads(PUBLIC_FREEZE.read_bytes()) ==
            _public_freeze(private, private_sha) and
            (BRANCH / "journal.private.jsonl").read_bytes().startswith(
                context["ten_journal_prefix"]) and
            CONTINUATION.is_dir() and not CONTINUATION.is_symlink() and
            CONTINUATION.stat().st_mode & 0o077 == 0 and
            SUPERVISION.is_dir() and not SUPERVISION.is_symlink() and
            SUPERVISION.stat().st_mode & 0o077 == 0 and
            BATCHES.is_dir() and not BATCHES.is_symlink() and
            BATCHES.stat().st_mode & 0o077 == 0,
            "continuation_source_or_ten_prefix_changed")
    try:
        frozen = datetime.fromisoformat(private["frozen_utc"])
    except (KeyError, TypeError, ValueError):
        raise ContinuationError("continuation_freeze_time_invalid") from None
    require(frozen.tzinfo is not None and
            frozen.astimezone(timezone.utc) <= datetime.now(timezone.utc),
            "continuation_freeze_time_invalid")
    return private, context, context["audited"]


def _reviewed_public_digest(given: str) -> str:
    actual = one.sha(PUBLIC_FREEZE.read_bytes())
    require(given == actual, "explicit_reviewed_continuation_freeze_sha256_required")
    return actual


def _batch_journal(plan_sha: str, old: dict) -> tuple[list[dict], dict]:
    path = BATCHES / "journal.private.jsonl"
    state = {"next_index": START_INDEX, "closed_batches": [],
             "pending_batch": None, "pending_id": None,
             "stopped_failure": False}
    if not path.exists():
        return [], state
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0,
            "continuation_batch_journal_not_private")
    raw = path.read_bytes()
    require(raw.endswith(b"\n"), "continuation_batch_journal_incomplete_tail")
    entries = []
    previous = "0" * 64
    for seq, line in enumerate(raw.splitlines(), 1):
        entry = json.loads(line)
        require(type(entry) is dict and
                entry.get("schema") == BATCH_EVENT_SCHEMA and
                entry.get("seq") == seq and
                entry.get("plan_sha256") == plan_sha and
                entry.get("previous_sha256") == previous and
                entry.get("entry_sha256") == one.sha(one.canonical({
                    key: value for key, value in entry.items()
                    if key != "entry_sha256"})),
                "continuation_batch_journal_chain_changed")
        kind = entry.get("kind")
        batch = state["pending_batch"]
        if kind == "batch_start":
            require(batch is None and not state["stopped_failure"] and
                    state["next_index"] < 100 and
                    entry.get("batch_number") == len(state["closed_batches"]) and
                    entry.get("start_index") == state["next_index"] and
                    type(entry.get("max_new_ids")) is int and
                    1 <= entry["max_new_ids"] <= min(
                        MAX_BATCH, 100 - state["next_index"]) and
                    entry.get("source_freeze_sha256") == plan_sha and
                    entry.get("automatic_same_id_replay") is False,
                    "continuation_batch_start_or_budget_invalid")
            state["pending_batch"] = {
                "batch_number": entry["batch_number"],
                "start_index": entry["start_index"],
                "max_new_ids": entry["max_new_ids"],
                "completed": 0,
                "start_entry_sha256": entry["entry_sha256"],
            }
        elif kind == "id_intent":
            require(batch is not None and state["pending_id"] is None and
                    batch["completed"] < batch["max_new_ids"] and
                    entry.get("batch_number") == batch["batch_number"] and
                    entry.get("task_index") == state["next_index"] and
                    entry.get("task_id") ==
                    old["task_roster"][state["next_index"]]["task_id"] and
                    entry.get("package_sha256") ==
                    old["task_roster"][state["next_index"]]["package_sha256"] and
                    lane.scale_final_v06.is_hash(
                        entry.get("pre_id_raw_audit_sha256")) and
                    entry.get("baseline_business_sha256") ==
                    old["baseline_business_sha256"] and
                    entry.get("source_freeze_sha256") == plan_sha,
                    "continuation_batch_id_intent_invalid")
            state["pending_id"] = entry
        elif kind == "id_completed":
            require(batch is not None and state["pending_id"] is not None and
                    entry.get("batch_number") == batch["batch_number"] and
                    entry.get("task_index") == state["next_index"] and
                    entry.get("task_id") == state["pending_id"]["task_id"] and
                    all(lane.scale_final_v06.is_hash(entry.get(key)) for key in
                        ("supervisor_result_sha256", "raw_audit_sha256")) and
                    entry.get("baseline_business_sha256") ==
                    old["baseline_business_sha256"],
                    "continuation_batch_completion_invalid")
            batch["completed"] += 1
            state["next_index"] += 1
            state["pending_id"] = None
        elif kind == "id_failed":
            require(batch is not None and state["pending_id"] is not None and
                    entry.get("batch_number") == batch["batch_number"] and
                    entry.get("task_index") == state["next_index"] and
                    entry.get("task_id") == state["pending_id"]["task_id"] and
                    lane.scale_final_v06.is_hash(
                        entry.get("supervisor_result_sha256")) and
                    entry.get("no_replay") is True,
                    "continuation_batch_failure_invalid")
            state["pending_id"] = None
            state["stopped_failure"] = True
        elif kind == "batch_end":
            require(batch is not None and state["pending_id"] is None and
                    entry.get("batch_number") == batch["batch_number"] and
                    entry.get("start_index") == batch["start_index"] and
                    entry.get("completed_count") == batch["completed"] and
                    entry.get("next_index") == state["next_index"] and
                    ((entry.get("status") == "completed_requested_ids" and
                      batch["completed"] == batch["max_new_ids"] and
                      not state["stopped_failure"]) or
                     (entry.get("status") == "stopped_on_failed_id_no_replay" and
                      state["stopped_failure"])),
                    "continuation_batch_end_invalid")
            state["closed_batches"].append({
                **batch, "status": entry["status"],
                "end_entry_sha256": entry["entry_sha256"],
            })
            state["pending_batch"] = None
        else:
            raise ContinuationError("continuation_batch_event_unknown")
        entries.append(entry)
        previous = entry["entry_sha256"]
    return entries, state


def _append_batch(entries: list[dict], plan_sha: str, payload: dict) -> dict:
    path = BATCHES / "journal.private.jsonl"
    require(not path.is_symlink() and
            (not path.exists() or path.stat().st_mode & 0o077 == 0),
            "continuation_batch_journal_output_not_private")
    event = {
        "schema": BATCH_EVENT_SCHEMA, "seq": len(entries) + 1,
        "plan_sha256": plan_sha,
        "previous_sha256": entries[-1]["entry_sha256"] if entries else "0" * 64,
        **payload,
    }
    event["entry_sha256"] = one.sha(one.canonical(event))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(one.canonical(event) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    entries.append(event)
    return event


@contextmanager
def _locked(path: Path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        require(stat.S_ISREG(os.fstat(descriptor).st_mode) and
                os.fstat(descriptor).st_mode & 0o077 == 0,
                "continuation_lock_not_private")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _prefix_audit(current: dict, count: int) -> dict:
    require(START_INDEX <= count <= current["completed_task_count"],
            "continuation_audit_prefix_count_invalid")
    if count == current["completed_task_count"] and count == 100:
        return current
    return {
        **current,
        "completed_task_count": count,
        "validated_tasks": current["validated_tasks"][:count],
        "pending_intent": False,
        "terminal_failure": False,
        "all_100_controls_independently_validated": False,
        "unissued_v06_proof_material": [],
        "proof_files_issued": False,
    }


def _check_branch_index(context: dict, index: int, *, clean: bool) -> dict:
    audited = context["audited"]
    state = context["journal_state"]
    require(audited["completed_task_count"] == index and
            state["next_index"] == index and
            one.sha(one.canonical(audited["validated_tasks"][:START_INDEX])) ==
            context["ten_validated_rows_sha256"] and
            not state["failed"] and
            (not clean or state["pending"] is None),
            "continuation_branch_progress_or_prefix_changed")
    return audited


def _terminalize_branch(context: dict, index: int, *, elapsed: float,
                        error_type: str) -> bool:
    old = context["old"]
    old_sha = context["old_sha"]
    entries = lane.read_journal(BRANCH, old_sha)
    state = lane.journal_state(entries, old)
    if state["failed"]:
        return state["next_index"] == index
    if state["next_index"] != index:
        return False
    item = old["task_roster"][index]
    path = BRANCH / "journal.private.jsonl"
    if state["pending"] is None:
        lane.append_event(path, old_sha, entries, {
            "kind": "intent", "task_index": index,
            "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "source_bundle_sha256": old["source_bundle_sha256"],
            "official_final_admitted": 0,
        })
    lane.append_event(path, old_sha, entries, {
        "kind": "terminal", "task_index": index,
        "task_id": item["task_id"], "status": "control_failed",
        "error_type": error_type, "wall_seconds": round(max(0.0, elapsed), 3),
        "trio_receipt_sha256": None, "official_final_admitted": 0,
    })
    after = lane.journal_state(lane.read_journal(BRANCH, old_sha), old)
    return after["failed"] is True and after["pending"] is None and \
        after["next_index"] == index


def _child_run(ratification_private: Path, index: int,
               reviewed_digest: str) -> dict:
    _reviewed_public_digest(reviewed_digest)
    _private, context, _audited = validate_freeze(ratification_private)
    old = context["old"]
    plan_sha = one.sha(PRIVATE_FREEZE.read_bytes())
    _entries, batch = _batch_journal(plan_sha, old)
    intent, _ = _read_private(
        SUPERVISION / f"{index:03d}-intent.private.json")
    require(START_INDEX <= index < 100 and
            batch["pending_id"] is not None and
            batch["pending_id"]["task_index"] == index and
            batch["next_index"] == index and
            intent.get("schema") == SUPERVISOR_INTENT_SCHEMA and
            intent.get("task_index") == index and
            intent.get("task_id") == old["task_roster"][index]["task_id"] and
            intent.get("package_sha256") ==
            old["task_roster"][index]["package_sha256"] and
            intent.get("supervisor_pid") == os.getppid() and
            intent.get("source_freeze_sha256") == plan_sha and
            intent.get("reviewed_public_freeze_sha256") == reviewed_digest and
            intent.get("automatic_same_id_replay") is False and
            not (SUPERVISION / f"{index:03d}-result.private.json").exists() and
            not (BRANCH / "attempts" / f"{index:03d}").exists(),
            "continuation_child_intent_or_branch_changed")
    _check_branch_index(context, index, clean=True)
    return asyncio.run(lane.run_loop(
        BRANCH, context["bound"], max_tasks=1,
        execute_one=lane.live_one, readiness=lane.assert_live_world))


def _run_one(ratification_private: Path, index: int,
             reviewed_digest: str) -> dict:
    _reviewed_public_digest(reviewed_digest)
    with _locked(SUPERVISION / ".supervisor.lock"):
        _private, context, _audited = validate_freeze(ratification_private)
        old = context["old"]
        old_sha = context["old_sha"]
        plan_sha = one.sha(PRIVATE_FREEZE.read_bytes())
        _events, batch = _batch_journal(plan_sha, old)
        intent_path = SUPERVISION / f"{index:03d}-intent.private.json"
        result_path = SUPERVISION / f"{index:03d}-result.private.json"
        require(START_INDEX <= index < 100 and
                batch["pending_id"] is not None and
                batch["pending_id"]["task_index"] == index and
                batch["next_index"] == index and
                not intent_path.exists() and not result_path.exists() and
                not (BRANCH / "attempts" / f"{index:03d}").exists(),
                "continuation_one_id_already_issued_or_uncertain")
        _check_branch_index(context, index, clean=True)
        lane.assert_live_world(old)
        item = old["task_roster"][index]
        one.write_new(intent_path, {
            "schema": SUPERVISOR_INTENT_SCHEMA,
            "source_freeze_sha256": plan_sha,
            "reviewed_public_freeze_sha256": reviewed_digest,
            "original_100_id_plan_sha256": old_sha,
            "v3_result_sha256": context["v3_result_sha256"],
            "task_index": index, "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "supervisor_pid": os.getpid(),
            "one_child_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
            "automatic_same_id_replay": False,
            "model_calls": 0, "official_final_admitted": 0,
        })
        argv = [
            sys.executable, "-m",
            "gitlab_world.v066_requalified_continuation_v1",
            "child-run", "--ratification-private", str(ratification_private),
            "--index", str(index),
            "--public-freeze-sha256", reviewed_digest, "--execute",
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
        try:
            child = recovery._confirm_child_process_group(one.supervise_child(
                argv, cwd=ROOT, env=env,
                stdout_path=SUPERVISION / f"{index:03d}-child.stdout.private.log",
                stderr_path=SUPERVISION / f"{index:03d}-child.stderr.private.log",
                timeout_seconds=one.CHILD_TIMEOUT_SECONDS,
                grace_seconds=one.TERM_GRACE_SECONDS))
        except Exception as exc:
            child = {
                "timed_out": False, "sigkill_used": False,
                "child_terminated": False, "process_group_terminated": False,
                "child_pid": None, "exit_code": None,
                "elapsed_seconds": 0.0, "termination_unconfirmed": True,
                "launch_or_supervision_error_type": type(exc).__name__,
            }
        status = "manual_review_required_no_replay"
        terminal = None
        cleanup = None
        raw_audit = None
        if child["child_terminated"]:
            try:
                _fresh_private, fresh, audited = validate_freeze(
                    ratification_private)
                current = fresh["journal_state"]
                passed = (
                    not child["timed_out"] and child["exit_code"] == 0 and
                    child.get("process_group_terminated") is True and
                    child.get("group_survivor_observed_after_child_wait") is False and
                    current["next_index"] == index + 1 and
                    current["pending"] is None and not current["failed"] and
                    audited["completed_task_count"] == index + 1 and
                    one.sha(one.canonical(audited["validated_tasks"][:START_INDEX])) ==
                    context["ten_validated_rows_sha256"])
            except Exception as exc:
                passed = False
                raw_audit = {"raw_audit_error_type": type(exc).__name__}
            if passed:
                try:
                    lane.assert_live_world(old)
                except Exception as exc:
                    raw_audit = {"baseline_error_type": type(exc).__name__}
                else:
                    status = "one_id_completed_and_raw_receipts_independently_audited"
                    raw_audit = {
                        "completed_task_count": index + 1,
                        "audit_private_sha256": one.sha(one.canonical(audited)),
                        "all_current_raw_receipts_reopened": True,
                    }
                    cleanup = {
                        "cold_reset_exact": True,
                        "mode": "three_case_resets_independently_verified",
                    }
            if status != "one_id_completed_and_raw_receipts_independently_audited":
                try:
                    terminal = {"terminal_failure": _terminalize_branch(
                        context, index, elapsed=child["elapsed_seconds"],
                        error_type=("SupervisedProcessTimeout"
                                    if child["timed_out"] else
                                    "SurvivingProcessGroupAfterChildExit"
                                    if child.get("group_survivor_observed_after_child_wait")
                                    else "SupervisedChildNonpassingExit"))}
                except Exception as exc:
                    terminal = {"terminal_failure": False,
                                "journal_error_type": type(exc).__name__}
                try:
                    cleanup = one.exact_cold_reset()
                except Exception as exc:
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
                if (terminal["terminal_failure"] is True and
                        cleanup.get("cold_reset_exact") is True):
                    status = "one_id_terminal_no_replay_exactly_reset"
        else:
            raw_audit = {"error_type": "child_process_group_not_confirmed_terminated"}
            cleanup = {"cold_reset_exact": False,
                       "error_type": "live_child_may_still_mutate_world"}
        result = {
            "schema": SUPERVISOR_RESULT_SCHEMA, "status": status,
            "source_freeze_sha256": plan_sha,
            "reviewed_public_freeze_sha256": reviewed_digest,
            "original_100_id_plan_sha256": old_sha,
            "v3_result_sha256": context["v3_result_sha256"],
            "task_index": index, "task_id": item["task_id"],
            "child": child, "journal_reconciliation": terminal,
            "cleanup": cleanup, "raw_audit": raw_audit,
            "post_attempt_baseline_exact":
                bool(cleanup and cleanup.get("cold_reset_exact")),
            "automatic_same_id_replay": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
        result_sha = one.write_new(result_path, result)
        return {"status": status, "task_index": index,
                "private_result_sha256": result_sha,
                "post_attempt_baseline_exact":
                result["post_attempt_baseline_exact"],
                "official_final_admitted": 0}


def _verify_passed(index: int, context: dict,
                   current_audit: dict) -> tuple[str, str]:
    result, result_sha = _read_private(
        SUPERVISION / f"{index:03d}-result.private.json")
    intent, _ = _read_private(
        SUPERVISION / f"{index:03d}-intent.private.json")
    expected_audit = _prefix_audit(current_audit, index + 1)
    expected_audit_sha = one.sha(one.canonical(expected_audit))
    child = result.get("child", {})
    require(result.get("schema") == SUPERVISOR_RESULT_SCHEMA and
            result.get("status") ==
            "one_id_completed_and_raw_receipts_independently_audited" and
            result.get("task_index") == index and
            result.get("task_id") ==
            context["old"]["task_roster"][index]["task_id"] and
            result.get("source_freeze_sha256") ==
            one.sha(PRIVATE_FREEZE.read_bytes()) and
            result.get("reviewed_public_freeze_sha256") ==
            one.sha(PUBLIC_FREEZE.read_bytes()) and
            result.get("original_100_id_plan_sha256") ==
            context["old_sha"] and
            result.get("v3_result_sha256") == context["v3_result_sha256"] and
            result.get("post_attempt_baseline_exact") is True and
            result.get("cleanup", {}).get("cold_reset_exact") is True and
            result.get("raw_audit") == {
                "completed_task_count": index + 1,
                "audit_private_sha256": expected_audit_sha,
                "all_current_raw_receipts_reopened": True,
            } and
            child.get("child_terminated") is True and
            child.get("process_group_terminated") is True and
            child.get("group_survivor_observed_after_child_wait") is False and
            child.get("timed_out") is False and
            child.get("exit_code") == 0 and
            intent.get("schema") == SUPERVISOR_INTENT_SCHEMA and
            intent.get("task_index") == index and
            intent.get("task_id") == result["task_id"] and
            intent.get("source_freeze_sha256") ==
            result["source_freeze_sha256"] and
            intent.get("automatic_same_id_replay") is False and
            result.get("automatic_same_id_replay") is False and
            result.get("model_calls") ==
            result.get("official_final_admitted") == 0 and
            current_audit["validated_tasks"][index]["task_id"] ==
            result["task_id"],
            "continuation_supervised_id_or_raw_audit_changed")
    return result_sha, expected_audit_sha


def _verify_failed(index: int, context: dict) -> str:
    result, result_sha = _read_private(
        SUPERVISION / f"{index:03d}-result.private.json")
    intent, _ = _read_private(
        SUPERVISION / f"{index:03d}-intent.private.json")
    status = result.get("status")
    require(result.get("schema") == SUPERVISOR_RESULT_SCHEMA and
            status in ("one_id_terminal_no_replay_exactly_reset",
                       "manual_review_required_no_replay") and
            result.get("task_index") == index and
            result.get("task_id") ==
            context["old"]["task_roster"][index]["task_id"] and
            result.get("source_freeze_sha256") ==
            one.sha(PRIVATE_FREEZE.read_bytes()) and
            result.get("v3_result_sha256") == context["v3_result_sha256"] and
            result.get("automatic_same_id_replay") is False and
            result.get("official_final_admitted") == 0 and
            intent.get("schema") == SUPERVISOR_INTENT_SCHEMA and
            intent.get("task_index") == index and
            intent.get("task_id") == result["task_id"] and
            context["journal_state"]["next_index"] in (index, index + 1),
            "continuation_failed_id_receipt_changed")
    if status == "one_id_terminal_no_replay_exactly_reset":
        require(result.get("post_attempt_baseline_exact") is True and
                result.get("cleanup", {}).get("cold_reset_exact") is True and
                result.get("journal_reconciliation", {}).get(
                    "terminal_failure") is True and
                result.get("child", {}).get("child_terminated") is True and
                result["child"].get("process_group_terminated") is True and
                context["journal_state"]["failed"] is True and
                context["journal_state"]["next_index"] == index,
                "continuation_terminal_cleanup_or_journal_changed")
    return result_sha


def _reconcile_pending_id(entries: list[dict], state: dict,
                          plan_sha: str, context: dict) -> tuple[list[dict], dict]:
    intent = state["pending_id"]
    if intent is None:
        return entries, state
    index = intent["task_index"]
    require((SUPERVISION / f"{index:03d}-result.private.json").is_file(),
            "pending_continuation_id_without_result_manual_review_no_replay")
    try:
        result_sha, audit_sha = _verify_passed(index, context,
                                                context["audited"])
    except Exception:
        result_sha = _verify_failed(index, context)
        _append_batch(entries, plan_sha, {
            "kind": "id_failed",
            "batch_number": intent["batch_number"],
            "task_index": index, "task_id": intent["task_id"],
            "supervisor_result_sha256": result_sha,
            "no_replay": True,
        })
    else:
        _append_batch(entries, plan_sha, {
            "kind": "id_completed",
            "batch_number": intent["batch_number"],
            "task_index": index, "task_id": intent["task_id"],
            "supervisor_result_sha256": result_sha,
            "raw_audit_sha256": audit_sha,
            "baseline_business_sha256":
                context["old"]["baseline_business_sha256"],
        })
    return _batch_journal(plan_sha, context["old"])


def _receipt_paths(number: int) -> tuple[Path, Path]:
    return (
        BATCHES / f"batch-{number:03d}-receipt.private.json",
        ROOT / "docs/evidence" /
        f"gitlab-v066-requalified-continuation-batch-{number:03d}-2026-09-29.json",
    )


def _finalize_receipt(number: int, entries: list[dict], state: dict,
                      plan_sha: str, old_sha: str,
                      *, publish: bool) -> dict:
    closed = state["closed_batches"][number]
    private_path, public_path = _receipt_paths(number)
    in_batch = [entry for entry in entries
                if entry.get("batch_number") == number]
    result_hashes = [entry["supervisor_result_sha256"]
                     for entry in in_batch
                     if entry["kind"] in ("id_completed", "id_failed")]
    private = {
        "schema": BATCH_RECEIPT_SCHEMA,
        "status": closed["status"],
        "batch_number": number, "plan_sha256": plan_sha,
        "original_100_id_plan_sha256": old_sha,
        "v3_public_outcome_sha256": V3_OUTCOME_PUBLIC_SHA256,
        "start_index": closed["start_index"],
        "max_new_ids": closed["max_new_ids"],
        "completed_count": closed["completed"],
        "next_index": closed["start_index"] + closed["completed"],
        "terminal_journal_entry_sha256": closed["end_entry_sha256"],
        "supervisor_result_sha256s": result_hashes,
        "automatic_same_id_replay": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    if private_path.exists():
        saved, private_sha = _read_private(private_path)
        require(saved == private, "continuation_private_batch_receipt_changed")
    else:
        require(publish, "continuation_closed_batch_private_receipt_missing")
        private_sha = one.write_new(private_path, private)
    public = {
        "schema": BATCH_PUBLIC_SCHEMA,
        "status": closed["status"],
        "batch_number": number, "private_receipt_sha256": private_sha,
        "source_freeze_sha256": one.sha(PUBLIC_FREEZE.read_bytes()),
        "v3_public_outcome_sha256": V3_OUTCOME_PUBLIC_SHA256,
        "start_index": closed["start_index"],
        "completed_count": closed["completed"],
        "next_index": private["next_index"],
        "remaining_original_roster_controls": 100 - private["next_index"],
        "terminal_journal_entry_sha256": closed["end_entry_sha256"],
        "model_calls": 0, "official_final_admitted": 0,
    }
    if public_path.exists():
        require(json.loads(public_path.read_bytes()) == public,
                "continuation_public_batch_receipt_changed")
    else:
        require(publish, "continuation_closed_batch_public_receipt_missing")
        one.write_new(public_path, public, 0o644)
    return public


def run_batch(ratification_private: Path, reviewed_digest: str,
              *, max_new_ids: int, resume_pending: bool = False) -> dict:
    _reviewed_public_digest(reviewed_digest)
    require(type(max_new_ids) is int and 1 <= max_new_ids <= MAX_BATCH,
            "explicit_bounded_continuation_batch_required")
    _private, context, _audited = validate_freeze(ratification_private)
    plan_sha = one.sha(PRIVATE_FREEZE.read_bytes())
    with _locked(BATCHES / ".batch.lock"):
        entries, state = _batch_journal(plan_sha, context["old"])
        for number in range(len(state["closed_batches"])):
            _finalize_receipt(number, entries, state, plan_sha,
                              context["old_sha"], publish=False)
        if state["pending_batch"] is not None:
            require(resume_pending and
                    state["pending_batch"]["max_new_ids"] == max_new_ids,
                    "pending_continuation_batch_requires_exact_resume")
            entries, state = _reconcile_pending_id(
                entries, state, plan_sha, context)
            batch = state["pending_batch"]
        else:
            require(not resume_pending and not state["stopped_failure"] and
                    state["next_index"] < 100 and
                    max_new_ids <= 100 - state["next_index"],
                    "continuation_batch_stopped_or_budget_exceeds_roster")
            _check_branch_index(context, state["next_index"], clean=True)
            lane.assert_live_world(context["old"])
            number = len(state["closed_batches"])
            _append_batch(entries, plan_sha, {
                "kind": "batch_start", "batch_number": number,
                "start_index": state["next_index"],
                "max_new_ids": max_new_ids,
                "source_freeze_sha256": plan_sha,
                "automatic_same_id_replay": False,
            })
            entries, state = _batch_journal(plan_sha, context["old"])
            batch = state["pending_batch"]
        require(batch is not None,
                "continuation_pending_batch_disappeared")
        while batch["completed"] < batch["max_new_ids"] and \
                not state["stopped_failure"]:
            index = state["next_index"]
            require(state["pending_id"] is None and index < 100,
                    "continuation_pending_id_cannot_replay")
            _private, context, audited = validate_freeze(
                ratification_private)
            _check_branch_index(context, index, clean=True)
            lane.assert_live_world(context["old"])
            require(not (SUPERVISION /
                         f"{index:03d}-intent.private.json").exists() and
                    not (SUPERVISION /
                         f"{index:03d}-result.private.json").exists() and
                    not (BRANCH / "attempts" /
                         f"{index:03d}").exists(),
                    "continuation_same_id_already_dispatched_or_uncertain")
            item = context["old"]["task_roster"][index]
            _append_batch(entries, plan_sha, {
                "kind": "id_intent", "batch_number": batch["batch_number"],
                "task_index": index, "task_id": item["task_id"],
                "package_sha256": item["package_sha256"],
                "pre_id_raw_audit_sha256":
                    one.sha(one.canonical(audited)),
                "baseline_business_sha256":
                    context["old"]["baseline_business_sha256"],
                "source_freeze_sha256": plan_sha,
            })
            _run_one(ratification_private, index, reviewed_digest)
            _private, context, _audited = validate_freeze(
                ratification_private)
            entries, state = _reconcile_pending_id(
                entries, _batch_journal(plan_sha, context["old"])[1],
                plan_sha, context)
            batch = state["pending_batch"]
            require(batch is not None,
                    "continuation_batch_disappeared_after_id")
        status = ("stopped_on_failed_id_no_replay"
                  if state["stopped_failure"] else "completed_requested_ids")
        _append_batch(entries, plan_sha, {
            "kind": "batch_end", "batch_number": batch["batch_number"],
            "start_index": batch["start_index"],
            "completed_count": batch["completed"],
            "next_index": state["next_index"], "status": status,
        })
        entries, state = _batch_journal(plan_sha, context["old"])
        return _finalize_receipt(batch["batch_number"], entries, state,
                                 plan_sha, context["old_sha"], publish=True)


def audit(ratification_private: Path) -> dict:
    _private, context, current = validate_freeze(ratification_private)
    plan_sha = one.sha(PRIVATE_FREEZE.read_bytes())
    entries, state = _batch_journal(plan_sha, context["old"])
    for number in range(len(state["closed_batches"])):
        _finalize_receipt(number, entries, state, plan_sha,
                          context["old_sha"], publish=False)
    for entry in entries:
        if entry["kind"] == "id_intent":
            index = entry["task_index"]
            before = _prefix_audit(current, index)
            require(entry["pre_id_raw_audit_sha256"] ==
                    one.sha(one.canonical(before)),
                    "continuation_pre_id_raw_audit_changed")
        elif entry["kind"] == "id_completed":
            index = entry["task_index"]
            result_sha, audit_sha = _verify_passed(index, context, current)
            require(entry["supervisor_result_sha256"] == result_sha and
                    entry["raw_audit_sha256"] == audit_sha,
                    "continuation_historical_pass_evidence_changed")
        elif entry["kind"] == "id_failed":
            index = entry["task_index"]
            result_sha = _verify_failed(index, context)
            require(entry["supervisor_result_sha256"] == result_sha and
                    state["stopped_failure"],
                    "continuation_historical_failure_changed")
    require(current["completed_task_count"] == state["next_index"] or
            (state["pending_id"] is not None and
             current["completed_task_count"] in
             (state["next_index"], state["next_index"] + 1)) or
            (state["stopped_failure"] and
             current["completed_task_count"] == state["next_index"] + 1),
            "continuation_batch_and_branch_progress_diverged")
    return {
        "status": ("terminal_failure_no_replay" if state["stopped_failure"]
                   else "pending_or_uncertain_no_replay"
                   if state["pending_batch"] is not None
                   else "source_bound_controls_only_not_official_admission"),
        "completed_current_controls": state["next_index"],
        "remaining_original_roster_controls": 100 - state["next_index"],
        "closed_batch_count": len(state["closed_batches"]),
        "pending_batch": state["pending_batch"] is not None,
        "pending_id": state["pending_id"] is not None,
        "original_terminal_failure_retained": True,
        "v3_requalification_retained": True,
        "all_100_controls_independently_reopened":
            state["next_index"] == 100 and
            state["pending_batch"] is None and
            not state["stopped_failure"] and
            current["all_100_controls_independently_validated"] is True,
        "model_calls": 0, "official_final_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "freeze", "preflight", "child-run", "run-batch", "audit"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--public-freeze-sha256", default="")
    parser.add_argument("--index", type=int)
    parser.add_argument("--max-new-ids", type=int)
    parser.add_argument("--resume-pending", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        require(not args.execute and args.max_new_ids is None and
                args.index is None, "continuation_freeze_is_offline_only")
        result = freeze(args.ratification_private)
    elif args.action == "preflight":
        require(not args.execute, "continuation_preflight_is_read_only")
        private, context, _audited = validate_freeze(
            args.ratification_private)
        _entries, state = _batch_journal(
            one.sha(PRIVATE_FREEZE.read_bytes()), context["old"])
        result = {
            "status": "source_frozen_preflight_only",
            "source_bundle_sha256": private["source_bundle_sha256"],
            "completed_current_controls": context["audited"]["completed_task_count"],
            "next_batch_index": state["next_index"],
            "pending_batch": state["pending_batch"] is not None,
            "pending_id": state["pending_id"] is not None,
            "original_terminal_failure_retained": True,
            "official_final_admitted": 0,
        }
    elif args.action == "child-run":
        require(args.execute and args.index is not None and
                args.max_new_ids is None,
                "continuation_child_requires_supervisor_execute")
        result = _child_run(args.ratification_private, args.index,
                            args.public_freeze_sha256)
    elif args.action == "run-batch":
        require(args.execute and args.max_new_ids is not None and
                args.index is None,
                "continuation_batch_requires_explicit_budget_and_execute")
        result = run_batch(
            args.ratification_private, args.public_freeze_sha256,
            max_new_ids=args.max_new_ids,
            resume_pending=args.resume_pending)
    else:
        require(not args.execute, "continuation_audit_is_read_only")
        result = audit(args.ratification_private)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
