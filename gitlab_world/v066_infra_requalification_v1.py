"""One explicit, source-bound GitLab infrastructure requalification.

The original terminal journal, failed attempt, supervised result, batch
receipts, and nine-ID aggregate remain immutable. This module forks only the
nine passing prefix into a new private run directory. It permits one fresh
clone attempt of the same tenth identity after an explicit public-freeze
digest acknowledgment. It does not dispatch later identities.
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
import signal
import stat
import sys
import time

from . import prospective_final_controls_v066 as lane
from . import v066_supervised_final_batch_v1 as old_batch
from . import v066_supervised_final_one_v1 as one


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = one.PRIVATE_ROOT
ORIGINAL = one.RUN_DIR
BRANCH = PRIVATE_ROOT / "v066-infra-requalification-branch-v3-20260929"
SUPERVISION = BRANCH / "supervision"
PRIVATE_FREEZE = BRANCH / "source-freeze.private.json"
PUBLIC_FREEZE = (
    ROOT / "docs/evidence/gitlab-v066-infra-requalification-v3-source-freeze-2026-09-29.json"
)
PRIVATE_OUTCOME = BRANCH / "requalification-audit.private.json"
PUBLIC_OUTCOME = (
    ROOT / "docs/evidence/gitlab-v066-infra-requalification-v3-outcome-2026-09-29.json"
)
SUPERSEDED_BRANCH = PRIVATE_ROOT / "v066-infra-requalification-branch-v2-20260929"
SUPERSEDED_PRIVATE_FREEZE_SHA256 = "029015f45aed1fe3bc55fcbc374a0e50ee31e63d112068dd538c898ae8d32508"
SUPERSEDED_PUBLIC_FREEZE_SHA256 = "00e26bf45cbd7683c7b2ebae348ee09912a2110bbe2c8fc42b8d7b8a425a4db2"
SUPERSEDED_SOURCE_BUNDLE_SHA256 = "661a7c5cd01b07f8af16f8f44e8c723ea430ef49ca0ac1363fdb163238418aac"
SUPERSEDED_PUBLIC_FREEZE = ROOT / "docs/evidence/gitlab-v066-infra-requalification-v2-source-freeze-2026-09-29.json"
NINE_PRIVATE = ORIGINAL / "current-v066-nine-id-terminal-private-audit-20260929.json"
NINE_PUBLIC = ROOT / "docs/evidence/gitlab-v066-current-nine-id-terminal-controls-2026-09-29.json"
RETRY_INDEX = 9
PREFIX_EVENTS = 18
FREEZE_SCHEMA = "envloop-gitlab-v066-infra-requalification-source-private-v3"
PUBLIC_SCHEMA = "envloop-gitlab-v066-infra-requalification-source-public-v3"
INTENT_SCHEMA = "envloop-gitlab-v066-infra-requalification-intent-private-v1"
RESULT_SCHEMA = "envloop-gitlab-v066-infra-requalification-result-private-v1"
AUDIT_SCHEMA = "envloop-gitlab-v066-infra-requalification-audit-private-v1"
OUTCOME_SCHEMA = "envloop-gitlab-v066-infra-requalification-outcome-public-v1"
SOURCE_FILES = (
    "gitlab_world/v066_infra_requalification_v1.py",
    "tests/test_gitlab_v066_infra_requalification.py",
    "docs/FULL_STUDY_GITLAB_V066_INFRA_REQUALIFICATION_2026-09-29.md",
    "docs/FULL_STUDY_GITLAB_V066_INFRA_REQUALIFICATION_V2_2026-09-29.md",
    "docs/FULL_STUDY_GITLAB_V066_INFRA_REQUALIFICATION_V3_2026-09-29.md",
)


class RecoveryError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RecoveryError(code)


def _source_hashes() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _read_private(path: Path) -> tuple[dict, str]:
    return one.private_json(path)


def _write_bytes_new(path: Path, raw: bytes, mode: int = 0o600) -> str:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return one.sha(raw)


def _tree_manifest(root: Path) -> str:
    require(root.is_dir() and not root.is_symlink() and
            root.stat().st_mode & 0o077 == 0, "private_tree_missing_or_open")
    rows = []
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), "private_tree_symlink")
        if stat.S_ISDIR(mode):
            continue
        require(stat.S_ISREG(mode) and path.stat().st_size <= 32 * 1024 * 1024,
                "private_tree_nonregular_or_oversize")
        rows.append([path.relative_to(root).as_posix(), one.sha(path.read_bytes())])
    require(bool(rows), "private_tree_empty")
    return one.sha(one.canonical(rows))


def _copy_tree(source: Path, destination: Path) -> str:
    expected = _tree_manifest(source)
    require(not destination.exists() and not destination.is_symlink(),
            "fresh_private_tree_required")
    destination.mkdir(mode=0o700)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), "private_tree_symlink")
        if stat.S_ISDIR(mode):
            target.mkdir(mode=0o700)
        else:
            require(stat.S_ISREG(mode), "private_tree_nonregular")
            _write_bytes_new(target, path.read_bytes())
    require(_tree_manifest(destination) == expected,
            "copied_private_tree_differs")
    return expected


def _original_context(ratification_private: Path) -> dict:
    _batch_plan, old, bound, old_sha = old_batch.validate_plan(
        ratification_private)
    batch_audit = old_batch.audit(ratification_private)
    require(batch_audit == {
        "status": "source_bound_controls_only_not_official_admission",
        "completed_current_controls": 9,
        "closed_batch_count": 2,
        "pending_batch": False,
        "pending_id": False,
        "terminal_failure": True,
        "official_final_admitted": 0,
    }, "original_terminal_batch_state_changed")
    journal_path = ORIGINAL / "journal.private.jsonl"
    journal_raw = journal_path.read_bytes()
    rows = journal_raw.splitlines(keepends=True)
    entries = lane.read_journal(ORIGINAL, old_sha)
    state = lane.journal_state(entries, old)
    require(len(rows) == len(entries) == PREFIX_EVENTS + 2 and
            all(row.endswith(b"\n") for row in rows) and
            state["next_index"] == RETRY_INDEX and state["pending"] is None and
            state["failed"] is True and
            entries[PREFIX_EVENTS - 1]["kind"] == "terminal" and
            entries[PREFIX_EVENTS - 1]["status"] == "control_passed" and
            entries[PREFIX_EVENTS]["kind"] == "intent" and
            entries[PREFIX_EVENTS]["task_index"] == RETRY_INDEX and
            entries[PREFIX_EVENTS + 1]["kind"] == "terminal" and
            entries[PREFIX_EVENTS + 1]["task_index"] == RETRY_INDEX and
            entries[PREFIX_EVENTS + 1]["status"] == "control_failed" and
            entries[PREFIX_EVENTS + 1]["error_type"] == "TimeoutError",
            "original_failed_journal_or_prefix_changed")
    branch_prefix = b"".join(rows[:PREFIX_EVENTS])
    prefix_state = lane.journal_state(entries[:PREFIX_EVENTS], old)
    require(prefix_state["next_index"] == RETRY_INDEX and
            prefix_state["pending"] is None and not prefix_state["failed"],
            "nine_pass_prefix_not_clean")
    old_result, old_result_sha = _read_private(
        one.SUPERVISION / f"{RETRY_INDEX:03d}-result.private.json")
    require(old_result.get("schema") == one.RESULT_SCHEMA and
            old_result.get("status") == "one_id_terminal_no_replay_exactly_reset" and
            old_result.get("task_index") == RETRY_INDEX and
            old_result.get("task_id") == old["task_roster"][RETRY_INDEX]["task_id"] and
            old_result.get("original_100_id_plan_sha256") == old_sha and
            old_result.get("child", {}).get("child_terminated") is True and
            old_result["child"].get("exit_code") == 1 and
            old_result.get("post_attempt_baseline_exact") is True and
            old_result.get("cleanup", {}).get("cold_reset_exact") is True and
            old_result.get("provider_or_gui_replay_authorized") is False and
            old_result.get("official_final_admitted") == 0,
            "original_failed_supervisor_result_changed")
    current_private, current_public = lane.audit_controls(ORIGINAL, bound)
    saved_private, saved_private_sha = _read_private(NINE_PRIVATE)
    require(saved_private == current_private and
            current_private["completed_task_count"] == RETRY_INDEX and
            current_private["terminal_failure"] is True and
            json.loads(NINE_PUBLIC.read_bytes()) ==
            {**current_public, "private_audit_sha256": saved_private_sha},
            "published_nine_control_audit_changed")
    batch_receipt, batch_receipt_sha = _read_private(
        old_batch._receipt_paths(1)[0])
    require(batch_receipt.get("status") == "stopped_on_failed_id_no_replay" and
            batch_receipt.get("completed_count") == 3 and
            batch_receipt.get("next_index") == RETRY_INDEX and
            batch_receipt.get("official_final_admitted") == 0,
            "original_failed_batch_receipt_changed")
    return {
        "old": old, "bound": bound, "old_sha": old_sha,
        "journal_full_sha256": one.sha(journal_raw),
        "journal_terminal_entry_sha256": entries[-1]["entry_sha256"],
        "journal_prefix": branch_prefix,
        "journal_prefix_sha256": one.sha(branch_prefix),
        "failed_result_sha256": old_result_sha,
        "failed_batch_receipt_sha256": batch_receipt_sha,
        "failed_batch_journal_sha256": one.sha(
            (old_batch.BATCH_DIR / "journal.private.jsonl").read_bytes()),
        "nine_private_sha256": saved_private_sha,
        "nine_public_sha256": one.sha(NINE_PUBLIC.read_bytes()),
        "nine_private": current_private,
        "failed_attempt_manifest_sha256": _tree_manifest(
            ORIGINAL / "attempts" / f"{RETRY_INDEX:03d}"),
        "plan_raw": (ORIGINAL / "plan.private.json").read_bytes(),
        "old_result": old_result,
    }


def _superseded_v2_freeze(context: dict) -> dict:
    """Bind the undispatched v2 branch without rewriting it."""
    old_private_path = SUPERSEDED_BRANCH / "source-freeze.private.json"
    old_public_path = SUPERSEDED_PUBLIC_FREEZE
    require(one.sha(old_private_path.read_bytes()) ==
            SUPERSEDED_PRIVATE_FREEZE_SHA256 and
            one.sha(old_public_path.read_bytes()) ==
            SUPERSEDED_PUBLIC_FREEZE_SHA256,
            "superseded_v2_freeze_bytes_changed")
    old_private, _ = _read_private(old_private_path)
    old_public = json.loads(old_public_path.read_bytes())
    require(old_private.get("schema") ==
            "envloop-gitlab-v066-infra-requalification-source-private-v2" and
            old_private.get("source_bundle_sha256") ==
            SUPERSEDED_SOURCE_BUNDLE_SHA256 and
            old_private.get("original_100_id_plan_sha256") ==
            context["old_sha"] and
            old_private.get("original_full_failed_journal_sha256") ==
            context["journal_full_sha256"] and
            old_private.get("branch_nine_prefix_journal_sha256") ==
            context["journal_prefix_sha256"] and
            old_private.get("status") ==
            "source_frozen_no_requalification_dispatched" and
            old_public.get("private_freeze_sha256") ==
            SUPERSEDED_PRIVATE_FREEZE_SHA256 and
            old_public.get("status") ==
            "source_frozen_no_requalification_dispatched" and
            old_public.get("continuation_dispatch_authorized") is False and
            SUPERSEDED_BRANCH.is_dir() and
            not SUPERSEDED_BRANCH.is_symlink() and
            SUPERSEDED_BRANCH.stat().st_mode & 0o077 == 0 and
            (SUPERSEDED_BRANCH / "plan.private.json").read_bytes() ==
            context["plan_raw"] and
            (SUPERSEDED_BRANCH / "journal.private.jsonl").read_bytes() ==
            context["journal_prefix"] and
            not (SUPERSEDED_BRANCH / "attempts" /
                 f"{RETRY_INDEX:03d}").exists() and
            not list((SUPERSEDED_BRANCH / "supervision").iterdir()),
            "superseded_v2_branch_was_dispatched_or_changed")
    for index in range(RETRY_INDEX):
        key = f"{index:03d}"
        require(old_private.get("branch_nine_attempt_manifests", {}).get(key) ==
                _tree_manifest(ORIGINAL / "attempts" / key) ==
                _tree_manifest(SUPERSEDED_BRANCH / "attempts" / key),
                "superseded_v2_attempt_prefix_changed")
    return {
        "superseded_v2_private_freeze_sha256":
            SUPERSEDED_PRIVATE_FREEZE_SHA256,
        "superseded_v2_public_freeze_sha256":
            SUPERSEDED_PUBLIC_FREEZE_SHA256,
    }


def _branch_audit(context: dict) -> tuple[dict, dict]:
    require(BRANCH.is_dir() and not BRANCH.is_symlink() and
            BRANCH.stat().st_mode & 0o077 == 0 and
            (BRANCH / "plan.private.json").read_bytes() == context["plan_raw"],
            "branch_private_plan_or_directory_changed")
    branch_journal = (BRANCH / "journal.private.jsonl").read_bytes()
    require(branch_journal.startswith(context["journal_prefix"]) and
            branch_journal.splitlines(keepends=True)[:PREFIX_EVENTS] ==
            context["journal_prefix"].splitlines(keepends=True),
            "branch_nine_event_prefix_changed")
    for index in range(RETRY_INDEX):
        expected = _tree_manifest(ORIGINAL / "attempts" / f"{index:03d}")
        require(_tree_manifest(BRANCH / "attempts" / f"{index:03d}") == expected,
                "branch_nine_attempt_prefix_changed")
    private, public = lane.audit_controls(BRANCH, context["bound"])
    require(private["completed_task_count"] >= RETRY_INDEX and
            private["validated_tasks"][:RETRY_INDEX] ==
            context["nine_private"]["validated_tasks"] and
            private["plan_sha256"] == context["old_sha"] and
            private["model_calls"] == private["official_final_admitted"] == 0,
            "branch_nine_raw_audit_prefix_changed")
    return private, public


def _public_freeze(private: dict, private_sha: str) -> dict:
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_no_requalification_dispatched",
        "private_freeze_sha256": private_sha,
        "superseded_v2_public_freeze_sha256":
            private["superseded_v2_public_freeze_sha256"],
        "superseded_v2_private_freeze_sha256":
            private["superseded_v2_private_freeze_sha256"],
        "source_bundle_sha256": private["source_bundle_sha256"],
        "original_100_id_plan_sha256": private["original_100_id_plan_sha256"],
        "original_full_failed_journal_sha256":
            private["original_full_failed_journal_sha256"],
        "original_failed_terminal_entry_sha256":
            private["original_failed_terminal_entry_sha256"],
        "original_failed_batch_receipt_sha256":
            private["original_failed_batch_receipt_sha256"],
        "original_nine_private_audit_sha256":
            private["original_nine_private_audit_sha256"],
        "branch_nine_prefix_journal_sha256":
            private["branch_nine_prefix_journal_sha256"],
        "completed_original_controls": RETRY_INDEX,
        "retained_original_terminal_infrastructure_failures": 1,
        "same_identity_fresh_clone_requalification_budget": 1,
        "continuation_dispatch_authorized": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }


def freeze(ratification_private: Path) -> dict:
    require(not BRANCH.exists() and not BRANCH.is_symlink() and
            not PUBLIC_FREEZE.exists(),
            "fresh_requalification_branch_and_public_freeze_required")
    context = _original_context(ratification_private)
    superseded = _superseded_v2_freeze(context)
    source_sha256s = _source_hashes()
    BRANCH.mkdir(mode=0o700)
    (BRANCH / "attempts").mkdir(mode=0o700)
    SUPERVISION.mkdir(mode=0o700)
    _write_bytes_new(BRANCH / "plan.private.json", context["plan_raw"])
    _write_bytes_new(BRANCH / "journal.private.jsonl",
                     context["journal_prefix"])
    manifests = {
        f"{index:03d}": _copy_tree(
            ORIGINAL / "attempts" / f"{index:03d}",
            BRANCH / "attempts" / f"{index:03d}")
        for index in range(RETRY_INDEX)
    }
    branch_private, _ = _branch_audit(context)
    require(branch_private["completed_task_count"] == RETRY_INDEX and
            branch_private["pending_intent"] is False and
            branch_private["terminal_failure"] is False,
            "branched_nine_prefix_not_clean")
    private = {
        "schema": FREEZE_SCHEMA,
        "status": "source_frozen_no_requalification_dispatched",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        **superseded,
        "original_100_id_plan_sha256": context["old_sha"],
        "original_full_failed_journal_sha256":
            context["journal_full_sha256"],
        "original_failed_terminal_entry_sha256":
            context["journal_terminal_entry_sha256"],
        "original_failed_result_sha256": context["failed_result_sha256"],
        "original_failed_batch_receipt_sha256":
            context["failed_batch_receipt_sha256"],
        "original_failed_batch_journal_sha256":
            context["failed_batch_journal_sha256"],
        "original_nine_private_audit_sha256":
            context["nine_private_sha256"],
        "original_nine_public_audit_sha256":
            context["nine_public_sha256"],
        "original_failed_partial_attempt_manifest_sha256":
            context["failed_attempt_manifest_sha256"],
        "branch_nine_prefix_journal_sha256":
            context["journal_prefix_sha256"],
        "branch_nine_attempt_manifests": manifests,
        "requalification_index": RETRY_INDEX,
        "requalification_task_id":
            context["old"]["task_roster"][RETRY_INDEX]["task_id"],
        "requalification_package_sha256":
            context["old"]["task_roster"][RETRY_INDEX]["package_sha256"],
        "baseline_business_sha256":
            context["old"]["baseline_business_sha256"],
        "source_sha256s": source_sha256s,
        "source_bundle_sha256": one.sha(one.canonical(source_sha256s)),
        "one_child_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
        "same_identity_fresh_clone_requalification_budget": 1,
        "branch_continuation_dispatch_authorized": False,
        "automatic_same_id_replay": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    private_sha = one.write_new(PRIVATE_FREEZE, private)
    public = _public_freeze(private, private_sha)
    one.write_new(PUBLIC_FREEZE, public, 0o644)
    return public


def validate_freeze(ratification_private: Path) -> tuple[dict, dict, dict, dict]:
    context = _original_context(ratification_private)
    superseded = _superseded_v2_freeze(context)
    private, private_sha = _read_private(PRIVATE_FREEZE)
    require(private.get("schema") == FREEZE_SCHEMA and
            private.get("status") == "source_frozen_no_requalification_dispatched" and
            private.get("superseded_v2_public_freeze_sha256") ==
            superseded["superseded_v2_public_freeze_sha256"] and
            private.get("superseded_v2_private_freeze_sha256") ==
            superseded["superseded_v2_private_freeze_sha256"] and
            private.get("original_100_id_plan_sha256") == context["old_sha"] and
            private.get("original_full_failed_journal_sha256") ==
            context["journal_full_sha256"] and
            private.get("original_failed_terminal_entry_sha256") ==
            context["journal_terminal_entry_sha256"] and
            private.get("original_failed_result_sha256") ==
            context["failed_result_sha256"] and
            private.get("original_failed_batch_receipt_sha256") ==
            context["failed_batch_receipt_sha256"] and
            private.get("original_failed_batch_journal_sha256") ==
            context["failed_batch_journal_sha256"] and
            private.get("original_nine_private_audit_sha256") ==
            context["nine_private_sha256"] and
            private.get("original_nine_public_audit_sha256") ==
            context["nine_public_sha256"] and
            private.get("original_failed_partial_attempt_manifest_sha256") ==
            context["failed_attempt_manifest_sha256"] and
            private.get("branch_nine_prefix_journal_sha256") ==
            context["journal_prefix_sha256"] and
            set(private.get("branch_nine_attempt_manifests", {})) ==
            {f"{index:03d}" for index in range(RETRY_INDEX)} and
            private.get("requalification_index") == RETRY_INDEX and
            private.get("requalification_task_id") ==
            context["old"]["task_roster"][RETRY_INDEX]["task_id"] and
            private.get("requalification_package_sha256") ==
            context["old"]["task_roster"][RETRY_INDEX]["package_sha256"] and
            private.get("baseline_business_sha256") ==
            context["old"]["baseline_business_sha256"] and
            private.get("source_sha256s") == _source_hashes() and
            private.get("source_bundle_sha256") ==
            one.sha(one.canonical(private["source_sha256s"])) and
            private.get("one_child_watchdog_seconds") ==
            one.CHILD_TIMEOUT_SECONDS and
            private.get("same_identity_fresh_clone_requalification_budget") == 1 and
            private.get("branch_continuation_dispatch_authorized") is False and
            private.get("automatic_same_id_replay") is False and
            private.get("model_calls") == private.get("official_final_admitted") == 0,
            "requalification_source_or_parent_failure_changed")
    try:
        frozen = datetime.fromisoformat(private["frozen_utc"])
    except (KeyError, TypeError, ValueError):
        raise RecoveryError("requalification_freeze_time_invalid") from None
    require(frozen.tzinfo is not None and
            frozen.astimezone(timezone.utc) <= datetime.now(timezone.utc),
            "requalification_freeze_time_invalid")
    require(json.loads(PUBLIC_FREEZE.read_bytes()) ==
            _public_freeze(private, private_sha),
            "public_requalification_freeze_changed")
    require(SUPERVISION.is_dir() and not SUPERVISION.is_symlink() and
            SUPERVISION.stat().st_mode & 0o077 == 0,
            "requalification_supervision_directory_not_private")
    require((BRANCH / "plan.private.json").read_bytes() ==
            context["plan_raw"] and
            (BRANCH / "journal.private.jsonl").read_bytes().startswith(
                context["journal_prefix"]),
            "branched_plan_or_prefix_changed")
    for index in range(RETRY_INDEX):
        key = f"{index:03d}"
        require(private.get("branch_nine_attempt_manifests", {}).get(key) ==
                _tree_manifest(ORIGINAL / "attempts" / key) ==
                _tree_manifest(BRANCH / "attempts" / key),
                "branched_attempt_manifest_changed")
    branch_private, _branch_public = _branch_audit(context)
    return private, context, branch_private, _branch_public


def _reviewed_public_digest(given: str) -> str:
    actual = one.sha(PUBLIC_FREEZE.read_bytes())
    require(given == actual,
            "explicit_reviewed_public_freeze_sha256_required")
    return actual


@contextmanager
def _lock():
    path = BRANCH / ".requalification.lock"
    descriptor = os.open(
        path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        require(stat.S_ISREG(os.fstat(descriptor).st_mode) and
                os.fstat(descriptor).st_mode & 0o077 == 0,
                "requalification_lock_not_private")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def _terminalize_branch(context: dict, *, elapsed: float,
                        error_type: str) -> bool:
    entries = lane.read_journal(BRANCH, context["old_sha"])
    state = lane.journal_state(entries, context["old"])
    if state["failed"]:
        return True
    if state["next_index"] != RETRY_INDEX:
        return False
    item = context["old"]["task_roster"][RETRY_INDEX]
    path = BRANCH / "journal.private.jsonl"
    if state["pending"] is None:
        lane.append_event(path, context["old_sha"], entries, {
            "kind": "intent", "task_index": RETRY_INDEX,
            "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "source_bundle_sha256": context["old"]["source_bundle_sha256"],
            "official_final_admitted": 0,
        })
    lane.append_event(path, context["old_sha"], entries, {
        "kind": "terminal", "task_index": RETRY_INDEX,
        "task_id": item["task_id"], "status": "control_failed",
        "error_type": error_type, "wall_seconds": round(max(0.0, elapsed), 3),
        "trio_receipt_sha256": None, "official_final_admitted": 0,
    })
    after = lane.journal_state(
        lane.read_journal(BRANCH, context["old_sha"]), context["old"])
    return after["failed"] is True and after["pending"] is None


GROUP_TERM_GRACE_SECONDS = 5.0
GROUP_KILL_GRACE_SECONDS = 5.0
GROUP_POLL_SECONDS = 0.1


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_group_gone(pgid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while _group_exists(pgid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(GROUP_POLL_SECONDS, max(0.0, deadline - time.monotonic())))
    return True


def _confirm_child_process_group(child: dict) -> dict:
    """Never infer group termination from the direct child's wait alone."""
    checked = dict(child)
    direct_terminated = checked.get("child_terminated") is True
    pgid = checked.get("child_pid")
    checked.update({
        "direct_child_terminated": direct_terminated,
        "process_group_terminated": False,
        "group_survivor_observed_after_child_wait": False,
        "post_watchdog_sigterm_used": False,
        "post_watchdog_sigkill_used": False,
        "termination_unconfirmed": True,
        "child_terminated": False,
    })
    # The inherited watchdog starts the child in a new session, so its PID is
    # its PGID. An absent or self-group PID cannot safely be signalled.
    if type(pgid) is not int or pgid <= 1 or pgid == os.getpgrp():
        return checked
    try:
        survivor = _group_exists(pgid)
        checked["group_survivor_observed_after_child_wait"] = survivor
        if survivor:
            try:
                os.killpg(pgid, signal.SIGTERM)
                checked["post_watchdog_sigterm_used"] = True
            except ProcessLookupError:
                pass
            if not _wait_group_gone(pgid, GROUP_TERM_GRACE_SECONDS):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                    checked["post_watchdog_sigkill_used"] = True
                except ProcessLookupError:
                    pass
                if not _wait_group_gone(pgid, GROUP_KILL_GRACE_SECONDS):
                    return checked
        checked["process_group_terminated"] = True
        checked["child_terminated"] = direct_terminated
        checked["termination_unconfirmed"] = not direct_terminated
    except OSError as exc:
        checked["process_group_check_error_type"] = type(exc).__name__
    return checked


def _child_run(ratification_private: Path, reviewed_digest: str) -> dict:
    _reviewed_public_digest(reviewed_digest)
    _private, context, branch_audit, _visible = validate_freeze(
        ratification_private)
    intent, _ = _read_private(
        SUPERVISION / f"{RETRY_INDEX:03d}-intent.private.json")
    entries = lane.read_journal(BRANCH, context["old_sha"])
    state = lane.journal_state(entries, context["old"])
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("task_index") == RETRY_INDEX and
            intent.get("supervisor_pid") == os.getppid() and
            intent.get("reviewed_public_freeze_sha256") == reviewed_digest and
            intent.get("original_failed_result_sha256") ==
            context["failed_result_sha256"] and
            not (BRANCH / "attempts" / f"{RETRY_INDEX:03d}").exists() and
            branch_audit["completed_task_count"] == RETRY_INDEX and
            state["next_index"] == RETRY_INDEX and
            state["pending"] is None and not state["failed"],
            "requalification_child_intent_or_branch_changed")
    return asyncio.run(lane.run_loop(
        BRANCH, context["bound"], max_tasks=1,
        execute_one=lane.live_one, readiness=lane.assert_live_world))


def run_requalification(ratification_private: Path,
                        reviewed_digest: str) -> dict:
    _reviewed_public_digest(reviewed_digest)
    with one.lock_supervisor(), _lock():
        _private, context, branch_audit, _visible = validate_freeze(
            ratification_private)
        entries = lane.read_journal(BRANCH, context["old_sha"])
        state = lane.journal_state(entries, context["old"])
        intent_path = SUPERVISION / f"{RETRY_INDEX:03d}-intent.private.json"
        result_path = SUPERVISION / f"{RETRY_INDEX:03d}-result.private.json"
        require(branch_audit["completed_task_count"] == RETRY_INDEX and
                state["next_index"] == RETRY_INDEX and
                state["pending"] is None and not state["failed"] and
                len(entries) == PREFIX_EVENTS and
                not intent_path.exists() and not result_path.exists() and
                not (BRANCH / "attempts" / f"{RETRY_INDEX:03d}").exists(),
                "same_identity_requalification_already_used_or_uncertain")
        lane.assert_live_world(context["old"])
        one.write_new(intent_path, {
            "schema": INTENT_SCHEMA,
            "source_freeze_sha256": one.sha(PRIVATE_FREEZE.read_bytes()),
            "reviewed_public_freeze_sha256": reviewed_digest,
            "original_100_id_plan_sha256": context["old_sha"],
            "original_failed_result_sha256": context["failed_result_sha256"],
            "original_failed_terminal_entry_sha256":
                context["journal_terminal_entry_sha256"],
            "task_index": RETRY_INDEX,
            "supervisor_pid": os.getpid(),
            "task_id": context["old"]["task_roster"][RETRY_INDEX]["task_id"],
            "package_sha256":
                context["old"]["task_roster"][RETRY_INDEX]["package_sha256"],
            "one_child_watchdog_seconds": one.CHILD_TIMEOUT_SECONDS,
            "same_identity_fresh_clone_attempt_number": 2,
            "automatic_same_id_replay": False,
            "model_calls": 0, "official_final_admitted": 0,
        })
        argv = [
            sys.executable, "-m",
            "gitlab_world.v066_infra_requalification_v1",
            "child-run", "--ratification-private", str(ratification_private),
            "--public-freeze-sha256", reviewed_digest, "--execute",
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
        try:
            child = _confirm_child_process_group(one.supervise_child(
                argv, cwd=ROOT, env=env,
                stdout_path=SUPERVISION / f"{RETRY_INDEX:03d}-child.stdout.private.log",
                stderr_path=SUPERVISION / f"{RETRY_INDEX:03d}-child.stderr.private.log",
                timeout_seconds=one.CHILD_TIMEOUT_SECONDS,
                grace_seconds=one.TERM_GRACE_SECONDS))
        except Exception as exc:
            child = {
                "timed_out": False, "sigkill_used": False,
                "child_terminated": False, "child_pid": None,
                "exit_code": None, "elapsed_seconds": 0.0,
                "launch_or_supervision_error_type": type(exc).__name__,
                "termination_unconfirmed": True,
            }
        status = "manual_review_required_no_replay"
        terminal = None
        cleanup = None
        raw_audit = None
        if child["child_terminated"]:
            try:
                current = lane.journal_state(
                    lane.read_journal(BRANCH, context["old_sha"]),
                    context["old"])
                passed = (not child["timed_out"] and
                          child["exit_code"] == 0 and
                          child["process_group_terminated"] is True and
                          child["group_survivor_observed_after_child_wait"] is False and
                          current["next_index"] == RETRY_INDEX + 1 and
                          current["pending"] is None and
                          not current["failed"])
            except Exception as exc:
                passed = False
                raw_audit = {"journal_error_type": type(exc).__name__}
            if passed:
                try:
                    audited, _ = lane.audit_controls(BRANCH, context["bound"])
                    lane.assert_live_world(context["old"])
                    require(audited["completed_task_count"] ==
                            RETRY_INDEX + 1 and
                            audited["validated_tasks"][:RETRY_INDEX] ==
                            context["nine_private"]["validated_tasks"],
                            "fresh_requalification_raw_audit_failed")
                except Exception as exc:
                    raw_audit = {"raw_receipt_error_type": type(exc).__name__}
                else:
                    status = "same_identity_fresh_clone_requalified"
                    raw_audit = {
                        "completed_task_count": RETRY_INDEX + 1,
                        "all_branch_raw_receipts_reopened": True,
                        "audit_private_sha256": one.sha(one.canonical(audited)),
                    }
                    cleanup = {
                        "cold_reset_exact": True,
                        "mode": "three_case_resets_independently_verified",
                    }
            if status != "same_identity_fresh_clone_requalified":
                try:
                    terminal = {
                        "terminal_failure": _terminalize_branch(
                            context, elapsed=child["elapsed_seconds"],
                            error_type=("SupervisedProcessTimeout"
                                        if child["timed_out"]
                                        else "SurvivingProcessGroupAfterChildExit"
                                        if child.get("group_survivor_observed_after_child_wait")
                                        else "SupervisedChildNonpassingExit")),
                    }
                except Exception as exc:
                    terminal = {
                        "terminal_failure": False,
                        "journal_error_type": type(exc).__name__,
                    }
                try:
                    cleanup = one.exact_cold_reset()
                except Exception as exc:
                    cleanup = {
                        "cold_reset_exact": False,
                        "error_type": type(exc).__name__,
                    }
                if (terminal["terminal_failure"] is True and
                        cleanup.get("cold_reset_exact") is True):
                    status = "requalification_terminal_no_replay_exactly_reset"
        else:
            raw_audit = {"error_type": "child_process_group_not_confirmed_terminated"}
            cleanup = {
                "cold_reset_exact": False,
                "error_type": "live_child_may_still_mutate_world",
            }
        result = {
            "schema": RESULT_SCHEMA,
            "status": status,
            "source_freeze_sha256": one.sha(PRIVATE_FREEZE.read_bytes()),
            "reviewed_public_freeze_sha256": reviewed_digest,
            "original_100_id_plan_sha256": context["old_sha"],
            "original_failed_result_sha256": context["failed_result_sha256"],
            "task_index": RETRY_INDEX,
            "task_id": context["old"]["task_roster"][RETRY_INDEX]["task_id"],
            "child": child,
            "journal_reconciliation": terminal,
            "cleanup": cleanup,
            "raw_audit": raw_audit,
            "post_attempt_baseline_exact":
                bool(cleanup and cleanup.get("cold_reset_exact")),
            "automatic_same_id_replay": False,
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
        result_sha = one.write_new(result_path, result)
        return {
            "status": status,
            "completed_branch_controls":
                RETRY_INDEX + (status == "same_identity_fresh_clone_requalified"),
            "private_result_sha256": result_sha,
            "post_attempt_baseline_exact": result["post_attempt_baseline_exact"],
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }


def audit_requalification(ratification_private: Path,
                          *, publish: bool = False) -> dict:
    _private, context, branch_audit, _visible = validate_freeze(
        ratification_private)
    intent_path = SUPERVISION / f"{RETRY_INDEX:03d}-intent.private.json"
    result_path = SUPERVISION / f"{RETRY_INDEX:03d}-result.private.json"
    if not intent_path.exists():
        require(not result_path.exists() and
                branch_audit["completed_task_count"] == RETRY_INDEX and
                branch_audit["pending_intent"] is False and
                branch_audit["terminal_failure"] is False,
                "unissued_requalification_branch_changed")
        require(not publish, "cannot_publish_undispatched_requalification")
        return {
            "status": "source_frozen_no_requalification_dispatched",
            "original_completed_controls": RETRY_INDEX,
            "original_terminal_failure_retained": True,
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
    intent, _ = _read_private(intent_path)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("task_index") == RETRY_INDEX and
            type(intent.get("supervisor_pid")) is int and
            intent["supervisor_pid"] > 0 and
            intent.get("task_id") ==
            context["old"]["task_roster"][RETRY_INDEX]["task_id"] and
            intent.get("package_sha256") ==
            context["old"]["task_roster"][RETRY_INDEX]["package_sha256"] and
            intent.get("reviewed_public_freeze_sha256") ==
            one.sha(PUBLIC_FREEZE.read_bytes()) and
            intent.get("original_failed_result_sha256") ==
            context["failed_result_sha256"] and
            intent.get("source_freeze_sha256") ==
            one.sha(PRIVATE_FREEZE.read_bytes()) and
            intent.get("same_identity_fresh_clone_attempt_number") == 2 and
            intent.get("automatic_same_id_replay") is False and
            intent.get("model_calls") == intent.get("official_final_admitted") == 0,
            "requalification_intent_changed")
    if not result_path.exists():
        require(not publish, "pending_requalification_cannot_publish")
        return {
            "status": "requalification_pending_or_uncertain_no_replay",
            "original_completed_controls": RETRY_INDEX,
            "original_terminal_failure_retained": True,
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
    result, result_sha = _read_private(result_path)
    passed = result.get("status") == "same_identity_fresh_clone_requalified"
    require(result.get("schema") == RESULT_SCHEMA and
            result.get("source_freeze_sha256") ==
            one.sha(PRIVATE_FREEZE.read_bytes()) and
            result.get("reviewed_public_freeze_sha256") ==
            intent.get("reviewed_public_freeze_sha256") and
            result.get("original_100_id_plan_sha256") == context["old_sha"] and
            result.get("original_failed_result_sha256") ==
            context["failed_result_sha256"] and
            result.get("task_index") == RETRY_INDEX and
            result.get("task_id") ==
            context["old"]["task_roster"][RETRY_INDEX]["task_id"] and
            result.get("automatic_same_id_replay") is False and
            result.get("continuation_dispatch_authorized") is False and
            result.get("model_calls") == result.get("official_final_admitted") == 0,
            "requalification_result_changed")
    if passed:
        require(result["child"].get("child_terminated") is True and
                result["child"].get("process_group_terminated") is True and
                result["child"].get("group_survivor_observed_after_child_wait") is False and
                result["child"].get("timed_out") is False and
                result["child"].get("exit_code") == 0 and
                result.get("post_attempt_baseline_exact") is True and
                branch_audit["completed_task_count"] == RETRY_INDEX + 1 and
                branch_audit["pending_intent"] is False and
                branch_audit["terminal_failure"] is False and
                result.get("raw_audit") == {
                    "completed_task_count": RETRY_INDEX + 1,
                    "all_branch_raw_receipts_reopened": True,
                    "audit_private_sha256":
                        one.sha(one.canonical(branch_audit)),
                },
                "fresh_requalification_raw_or_reset_evidence_changed")
        lane.assert_live_world(context["old"])
    elif result.get("status") == "requalification_terminal_no_replay_exactly_reset":
        require(result["child"].get("child_terminated") is True and
                result["child"].get("process_group_terminated") is True and
                (result["child"].get("timed_out") is True or
                 result["child"].get("exit_code") != 0 or
                 result["child"].get("group_survivor_observed_after_child_wait") is True) and
                result.get("post_attempt_baseline_exact") is True and
                result.get("journal_reconciliation", {}).get("terminal_failure") is True and
                branch_audit["completed_task_count"] == RETRY_INDEX and
                branch_audit["pending_intent"] is False and
                branch_audit["terminal_failure"] is True,
                "terminal_requalification_result_or_branch_changed")
        lane.assert_live_world(context["old"])
    else:
        require(result.get("status") == "manual_review_required_no_replay" and
                not publish and
                branch_audit["completed_task_count"] in (
                    RETRY_INDEX, RETRY_INDEX + 1),
                "uncertain_requalification_cannot_publish_or_continue")
    audit = {
        "schema": AUDIT_SCHEMA,
        "status": result["status"],
        "source_freeze_sha256": one.sha(PRIVATE_FREEZE.read_bytes()),
        "original_full_failed_journal_sha256":
            context["journal_full_sha256"],
        "original_failed_result_sha256": context["failed_result_sha256"],
        "requalification_result_sha256": result_sha,
        "branch_raw_audit_sha256": one.sha(one.canonical(branch_audit)),
        "branch_completed_controls": branch_audit["completed_task_count"],
        "original_terminal_failure_retained": True,
        "continuation_dispatch_authorized": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    if publish:
        if PRIVATE_OUTCOME.exists():
            saved, audit_sha = _read_private(PRIVATE_OUTCOME)
            require(saved == audit, "saved_requalification_audit_changed")
        else:
            audit_sha = one.write_new(PRIVATE_OUTCOME, audit)
        public = {
            "schema": OUTCOME_SCHEMA,
            "status": result["status"],
            "source_freeze_sha256": one.sha(PUBLIC_FREEZE.read_bytes()),
            "private_audit_sha256": audit_sha,
            "original_completed_controls": RETRY_INDEX,
            "branch_completed_controls": branch_audit["completed_task_count"],
            "original_terminal_failure_retained": True,
            "automatic_same_id_replay": False,
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
        if PUBLIC_OUTCOME.exists():
            require(json.loads(PUBLIC_OUTCOME.read_bytes()) == public,
                    "published_requalification_outcome_changed")
        else:
            one.write_new(PUBLIC_OUTCOME, public, 0o644)
    return {
        "status": result["status"],
        "branch_completed_controls": branch_audit["completed_task_count"],
        "original_terminal_failure_retained": True,
        "continuation_dispatch_authorized": False,
        "model_calls": 0, "official_final_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("freeze", "preflight", "child-run",
                           "run-requalification", "audit"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--public-freeze-sha256", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        require(not args.execute and not args.publish,
                "freeze_is_no_gui_only")
        result = freeze(args.ratification_private)
    elif args.action == "preflight":
        require(not args.execute and not args.publish,
                "preflight_is_read_only")
        private, context, branch_audit, _ = validate_freeze(
            args.ratification_private)
        result = {
            "status": "source_frozen_preflight_only",
            "source_bundle_sha256": private["source_bundle_sha256"],
            "original_terminal_failure_retained": True,
            "branch_completed_controls": branch_audit["completed_task_count"],
            "branch_pending": branch_audit["pending_intent"],
            "branch_terminal_failure": branch_audit["terminal_failure"],
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
    elif args.action == "child-run":
        require(args.execute and not args.publish,
                "child_run_requires_explicit_execute")
        result = _child_run(args.ratification_private,
                            args.public_freeze_sha256)
    elif args.action == "run-requalification":
        require(args.execute and not args.publish,
                "requalification_requires_explicit_execute")
        result = run_requalification(
            args.ratification_private, args.public_freeze_sha256)
    else:
        require(not args.execute, "audit_is_no_gui_only")
        result = audit_requalification(
            args.ratification_private, publish=args.publish)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
