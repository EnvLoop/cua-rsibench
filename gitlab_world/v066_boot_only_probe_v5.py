"""Source-frozen, task-free GitLab cold-boot infrastructure probe.

The frozen source can later run three disposable-world cold boots under one
supervised, no-replay intent. It never selects a task, invokes GUI actions, or
samples a model. Raw Docker startup logs and State-only inspect bytes remain
private and are saved before any failure cleanup removes a container.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys

from . import prospective_final_controls_v066 as lane
from . import reset, runtime
from . import v066_infra_recovery_v4 as parent
from . import v066_infra_requalification_v1 as recovery
from . import v066_requalified_continuation_v1 as terminal
from . import v066_supervised_final_one_v1 as one


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = runtime.PRIVATE
PROBE = PRIVATE_ROOT / "v066-boot-only-probe-v5-20260929"
CLONES = PROBE / "clones"
PRIVATE_FREEZE = PROBE / "source-freeze.private.json"
PUBLIC_FREEZE = ROOT / "docs/evidence/gitlab-v066-boot-only-probe-v5-source-freeze-2026-09-29.json"
INTENT = PROBE / "intent.private.json"
CHILD_RESULT = PROBE / "child-result.private.json"
SUPERVISOR_RESULT = PROBE / "supervisor-result.private.json"
PUBLIC_RESULT = ROOT / "docs/evidence/gitlab-v066-boot-only-probe-v5-outcome-2026-09-29.json"
SCOPE = ROOT / "docs/evidence/gitlab-v066-infra-recovery-v4-checkout-scope-2026-09-29.json"
PARENT_PUBLIC = parent.PUBLIC_PLAN
SCOPE_SHA256 = "e607549f7a9ef1103fc1a96833a95705c4dfd65ae4256fb184513c4e43b86a11"
PARENT_PUBLIC_SHA256 = "8ad1868718dfb43bd73a0cb67a17c28dea20dbd7a9fe8cc2dcbfa91822a46f73"
BOOT_CLONES = 3
CHILD_WATCHDOG_SECONDS = 3600
TERM_GRACE_SECONDS = 30
FORENSIC_COMMAND_TIMEOUT_SECONDS = 60
FREEZE_SCHEMA = "envloop-gitlab-v066-boot-only-probe-v5-source-private-v1"
PUBLIC_FREEZE_SCHEMA = "envloop-gitlab-v066-boot-only-probe-v5-source-public-v1"
INTENT_SCHEMA = "envloop-gitlab-v066-boot-only-probe-v5-intent-private-v1"
CHILD_SCHEMA = "envloop-gitlab-v066-boot-only-probe-v5-child-private-v1"
SUPERVISOR_SCHEMA = "envloop-gitlab-v066-boot-only-probe-v5-supervisor-private-v1"
PUBLIC_RESULT_SCHEMA = "envloop-gitlab-v066-boot-only-probe-v5-outcome-public-v1"
SOURCE_FILES = (
    "gitlab_world/v066_boot_only_probe_v5.py",
    "tests/test_gitlab_v066_boot_only_probe_v5.py",
    "docs/FULL_STUDY_GITLAB_V066_BOOT_ONLY_PROBE_V5_2026-09-29.md",
    "gitlab_world/reset.py",
    "gitlab_world/runtime.py",
    "gitlab_world/v066_supervised_final_one_v1.py",
    "gitlab_world/v066_infra_requalification_v1.py",
)


class ProbeError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ProbeError(code)


def _source_sha256s() -> dict[str, str]:
    return {name: one.sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def _private_json(path: Path) -> tuple[dict, str]:
    return one.private_json(path)


def _public_freeze(private: dict, private_sha: str) -> dict:
    return {
        "schema": PUBLIC_FREEZE_SCHEMA,
        "status": "source_frozen_boot_only_probe_not_dispatched",
        "private_source_freeze_sha256": private_sha,
        "source_bundle_sha256": private["source_bundle_sha256"],
        "parent_v4_public_plan_sha256": private["parent_v4_public_plan_sha256"],
        "original_evaluator_checkout_scope_sha256": private["scope_sha256"],
        "intent_nonce_sha256": private["intent_nonce_sha256"],
        "maximum_boot_clones": BOOT_CLONES,
        "child_watchdog_seconds": CHILD_WATCHDOG_SECONDS,
        "requires_raw_docker_logs_private_before_cleanup": True,
        "requires_docker_inspect_state_only_private_before_cleanup": True,
        "post_failure_exact_reset_required": True,
        "same_failed_id_replay_authorized": False,
        "task_intents": 0,
        "selection_or_final_tasks_dispatched": 0,
        "model_calls": 0,
        "official_final_admitted": 0,
    }


def _parent_bindings(ratification_private: Path) -> tuple[dict, dict]:
    require(SCOPE.is_file() and PARENT_PUBLIC.is_file(),
            "original_evaluator_scope_or_parent_plan_missing")
    require(one.sha(SCOPE.read_bytes()) == SCOPE_SHA256 and
            one.sha(PARENT_PUBLIC.read_bytes()) == PARENT_PUBLIC_SHA256,
            "reviewed_v4_scope_or_parent_public_bytes_changed")
    scope = json.loads(SCOPE.read_bytes())
    prior = parent.audit(ratification_private)
    require(scope.get("status") ==
            "source_plan_auditable_only_in_original_evaluator_worktree" and
            scope.get("original_evaluator_worktree_audit_passed") is True and
            scope.get("main_checkout_audit_passed") is False and
            scope.get("source_plan_public_sha256") ==
            one.sha(PARENT_PUBLIC.read_bytes()) and
            prior.get("status") ==
            "prospective_new_id_epoch_plan_only_no_dispatch" and
            prior.get("one_id_gui_dispatch_authorized") is False and
            prior.get("same_identity_replay_authorized") is False and
            prior.get("official_final_admitted") == 0 and
            prior.get("model_calls") == 0,
            "v4_original_evaluator_scope_or_no_dispatch_binding_changed")
    return scope, prior


def freeze(ratification_private: Path) -> dict:
    require(not PRIVATE_FREEZE.exists() and not PUBLIC_FREEZE.exists() and
            not INTENT.exists() and not SUPERVISOR_RESULT.exists(),
            "fresh_boot_probe_epoch_required")
    scope, prior = _parent_bindings(ratification_private)
    sources = _source_sha256s()
    nonce = secrets.token_hex(32)
    private = {
        "schema": FREEZE_SCHEMA,
        "status": "source_frozen_boot_only_probe_not_dispatched",
        "source_sha256s": sources,
        "source_bundle_sha256": one.sha(one.canonical(sources)),
        "parent_v4_public_plan_sha256": one.sha(PARENT_PUBLIC.read_bytes()),
        "parent_v4_epoch_sha256": prior["epoch_sha256"],
        "scope_sha256": one.sha(SCOPE.read_bytes()),
        "scope_status": scope["status"],
        "ratification_private_sha256": one.sha(ratification_private.read_bytes()),
        "intent_nonce": nonce,
        "intent_nonce_sha256": one.sha(nonce.encode()),
        "maximum_boot_clones": BOOT_CLONES,
        "child_watchdog_seconds": CHILD_WATCHDOG_SECONDS,
        "forensic_command_timeout_seconds": FORENSIC_COMMAND_TIMEOUT_SECONDS,
        "task_intents": 0,
        "selection_or_final_tasks_dispatched": 0,
        "same_failed_id_replay_authorized": False,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    PROBE.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(PROBE.stat().st_mode & 0o077 == 0,
            "boot_probe_private_directory_permissive")
    private_sha = one.write_new(PRIVATE_FREEZE, private)
    public = _public_freeze(private, private_sha)
    one.write_new(PUBLIC_FREEZE, public, 0o644)
    return public


def validate_freeze(ratification_private: Path) -> tuple[dict, str]:
    _scope, prior = _parent_bindings(ratification_private)
    private, private_sha = _private_json(PRIVATE_FREEZE)
    sources = _source_sha256s()
    require(private.get("schema") == FREEZE_SCHEMA and
            private.get("status") ==
            "source_frozen_boot_only_probe_not_dispatched" and
            private.get("source_sha256s") == sources and
            private.get("source_bundle_sha256") ==
            one.sha(one.canonical(sources)) and
            private.get("parent_v4_public_plan_sha256") ==
            one.sha(PARENT_PUBLIC.read_bytes()) and
            private.get("parent_v4_epoch_sha256") == prior["epoch_sha256"] and
            private.get("scope_sha256") == one.sha(SCOPE.read_bytes()) and
            private.get("ratification_private_sha256") ==
            one.sha(ratification_private.read_bytes()) and
            isinstance(private.get("intent_nonce"), str) and
            len(private["intent_nonce"]) == 64 and
            private.get("intent_nonce_sha256") ==
            one.sha(private["intent_nonce"].encode()) and
            private.get("maximum_boot_clones") == BOOT_CLONES and
            private.get("child_watchdog_seconds") == CHILD_WATCHDOG_SECONDS and
            private.get("forensic_command_timeout_seconds") ==
            FORENSIC_COMMAND_TIMEOUT_SECONDS and
            private.get("task_intents") == 0 and
            private.get("selection_or_final_tasks_dispatched") == 0 and
            private.get("same_failed_id_replay_authorized") is False and
            private.get("model_calls") ==
            private.get("official_final_admitted") == 0 and
            json.loads(PUBLIC_FREEZE.read_bytes()) ==
            _public_freeze(private, private_sha),
            "boot_probe_frozen_source_or_parent_changed")
    return private, private_sha


def _write_bytes_new(path: Path, raw: bytes) -> str:
    require(path.parent.is_dir() and not path.parent.is_symlink() and
            path.parent.stat().st_mode & 0o077 == 0 and
            not path.exists() and not path.is_symlink(),
            "boot_probe_raw_forensic_output_not_fresh_private")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise
    return one.sha(raw)


def _docker_forensic(command: list[str], *, timeout: int) -> tuple[bytes, bytes, int | None, str | None]:
    """Read Docker CLI bytes only; never inspect Config or environment."""
    try:
        completed = subprocess.run(
            ["docker", "--context", runtime.CONTEXT, *command],
            capture_output=True, timeout=timeout, check=False)
        return completed.stdout, completed.stderr, completed.returncode, None
    except subprocess.TimeoutExpired as exc:
        return exc.stdout or b"", exc.stderr or b"", None, "TimeoutExpired"
    except Exception as exc:
        return b"", b"", None, type(exc).__name__


def capture_startup_forensics(folder: Path) -> dict:
    """Save raw logs and State-only inspect bytes before cleanup."""
    require(folder.is_dir() and not folder.is_symlink() and
            folder.stat().st_mode & 0o077 == 0,
            "boot_probe_forensic_folder_not_private")
    log_out, log_err, log_code, log_error = _docker_forensic(
        ["logs", "--timestamps", runtime.WORLD],
        timeout=FORENSIC_COMMAND_TIMEOUT_SECONDS)
    state_out, state_err, state_code, state_error = _docker_forensic(
        ["inspect", "--format", "{{json .State}}", runtime.WORLD],
        timeout=FORENSIC_COMMAND_TIMEOUT_SECONDS)
    hashes = {
        "docker_logs_stdout": _write_bytes_new(folder / "docker-logs.stdout.private.log", log_out),
        "docker_logs_stderr": _write_bytes_new(folder / "docker-logs.stderr.private.log", log_err),
        "docker_state_stdout": _write_bytes_new(folder / "docker-state.stdout.private.json", state_out),
        "docker_state_stderr": _write_bytes_new(folder / "docker-state.stderr.private.log", state_err),
    }
    state = None
    if state_code == 0:
        try:
            state = json.loads(state_out)
        except (TypeError, ValueError):
            state_error = "StateJsonInvalid"
    if state is not None and not isinstance(state, dict):
        state = None
        state_error = "StateJsonNotObject"
    return {
        "schema": "envloop-gitlab-v066-boot-only-probe-v5-forensics-private-v1",
        "raw_file_sha256s": hashes,
        "raw_file_bytes": {
            "docker_logs_stdout": len(log_out),
            "docker_logs_stderr": len(log_err),
            "docker_state_stdout": len(state_out),
            "docker_state_stderr": len(state_err),
        },
        "docker_logs_exit_code": log_code,
        "docker_logs_error_type": log_error,
        "docker_inspect_state_exit_code": state_code,
        "docker_inspect_state_error_type": state_error,
        "state_status": state.get("Status") if state else None,
        "state_exit_code": state.get("ExitCode") if state else None,
        "state_oom_killed": state.get("OOMKilled") if state else None,
        "raw_startup_logs_saved": log_code == 0,
        "state_only_inspect_saved": state_code == 0 and state is not None,
    }


def _forensic_tree_manifest() -> list[dict]:
    """Bind even complete clone files left by a watchdog-killed child."""
    if not CLONES.exists():
        return []
    require(CLONES.is_dir() and not CLONES.is_symlink() and
            CLONES.stat().st_mode & 0o077 == 0,
            "boot_probe_forensic_tree_not_private")
    rows = []
    for path in sorted(CLONES.rglob("*")):
        require(not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
                "boot_probe_forensic_tree_symlink_or_permissive")
        if path.is_dir():
            continue
        require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
                "boot_probe_forensic_tree_nonregular_file")
        raw = path.read_bytes()
        rows.append({"path": str(path.relative_to(CLONES)),
                     "sha256": one.sha(raw), "bytes": len(raw)})
    return rows


def _child_run(ratification_private: Path, reviewed_sha: str) -> dict:
    private, freeze_sha = validate_freeze(ratification_private)
    require(reviewed_sha == one.sha(PUBLIC_FREEZE.read_bytes()),
            "reviewed_boot_probe_public_freeze_sha256_required")
    intent, intent_sha = _private_json(INTENT)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("intent_nonce") == private["intent_nonce"] and
            intent.get("source_freeze_sha256") == freeze_sha and
            intent.get("maximum_boot_clones") == BOOT_CLONES and
            intent.get("task_intents") == 0 and
            intent.get("selection_or_final_tasks_dispatched") == 0 and
            intent.get("same_failed_id_replay_authorized") is False and
            not CHILD_RESULT.exists(),
            "boot_probe_child_has_no_unique_task_free_intent")
    old = terminal.validate_freeze(ratification_private)[1]["old"]
    lane.assert_live_world(old)
    CLONES.mkdir(mode=0o700, exist_ok=False)
    records: list[dict] = []
    status = "three_boot_only_clones_exact_baseline"
    for index in range(BOOT_CLONES):
        folder = CLONES / f"{index:02d}"
        folder.mkdir(mode=0o700, exist_ok=False)
        reset_receipt = None
        error_type = None
        exact_baseline = False
        try:
            reset_receipt = reset.reset()
            lane.assert_live_world(old)
            exact_baseline = True
        except Exception as exc:
            error_type = type(exc).__name__
        forensic = capture_startup_forensics(folder)
        record = {
            "boot_index": index,
            "reset_receipt": reset_receipt,
            "exact_baseline": exact_baseline,
            "error_type": error_type,
            "forensics": forensic,
        }
        one.write_new(folder / "boot-receipt.private.json", record)
        records.append(record)
        if (not exact_baseline or
                not forensic["raw_startup_logs_saved"] or
                not forensic["state_only_inspect_saved"]):
            status = "boot_only_clone_failed_or_forensics_incomplete"
            break
    child = {
        "schema": CHILD_SCHEMA,
        "status": status,
        "source_freeze_sha256": freeze_sha,
        "intent_sha256": intent_sha,
        "intent_nonce_sha256": private["intent_nonce_sha256"],
        "completed_boot_clones": len(records),
        "boot_receipt_sha256s": [
            one.sha((CLONES / f"{index:02d}" /
                     "boot-receipt.private.json").read_bytes())
            for index in range(len(records))],
        "task_intents": 0,
        "selection_or_final_tasks_dispatched": 0,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    child_sha = one.write_new(CHILD_RESULT, child)
    return {"status": status, "child_result_sha256": child_sha}


@contextmanager
def _locked():
    path = PROBE / ".probe.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        require(stat.S_ISREG(os.fstat(descriptor).st_mode) and
                os.fstat(descriptor).st_mode & 0o077 == 0,
                "boot_probe_lock_not_private")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _public_result(supervisor: dict, supervisor_sha: str) -> dict:
    return {
        "schema": PUBLIC_RESULT_SCHEMA,
        "status": supervisor["status"],
        "source_freeze_public_sha256": one.sha(PUBLIC_FREEZE.read_bytes()),
        "supervisor_result_private_sha256": supervisor_sha,
        "intent_nonce_sha256": supervisor["intent_nonce_sha256"],
        "completed_boot_clones": supervisor["completed_boot_clones"],
        "raw_log_sha256s": supervisor["raw_log_sha256s"],
        "raw_logs_private": bool(supervisor["raw_log_sha256s"]),
        "raw_startup_logs_saved_before_cleanup":
            supervisor["raw_startup_logs_saved_before_cleanup"],
        "private_forensic_file_count":
            len(supervisor["private_forensic_tree_manifest"]),
        "private_forensic_tree_sha256":
            one.sha(one.canonical(supervisor["private_forensic_tree_manifest"])),
        "supervisor_fallback_log_capture_succeeded":
            supervisor["fallback_log_capture_succeeded"],
        "post_failure_exact_reset": supervisor["post_failure_exact_reset"],
        "final_world_exact_baseline":
            supervisor["cleanup"].get("cold_reset_exact") is True,
        "child_process_group_terminated": supervisor["child_process_group_terminated"],
        "same_failed_id_replay_authorized": False,
        "task_intents": 0,
        "selection_or_final_tasks_dispatched": 0,
        "model_calls": 0,
        "official_final_admitted": 0,
    }


def run_probe(ratification_private: Path, reviewed_sha: str) -> dict:
    private, freeze_sha = validate_freeze(ratification_private)
    require(reviewed_sha == one.sha(PUBLIC_FREEZE.read_bytes()),
            "reviewed_boot_probe_public_freeze_sha256_required")
    with _locked():
        require(not INTENT.exists() and not CHILD_RESULT.exists() and
                not SUPERVISOR_RESULT.exists() and not PUBLIC_RESULT.exists() and
                not CLONES.exists(),
                "boot_probe_intent_already_dispatched_no_replay")
        old = terminal.validate_freeze(ratification_private)[1]["old"]
        lane.assert_live_world(old)
        intent = {
            "schema": INTENT_SCHEMA,
            "intent_nonce": private["intent_nonce"],
            "intent_nonce_sha256": private["intent_nonce_sha256"],
            "source_freeze_sha256": freeze_sha,
            "reviewed_public_freeze_sha256": reviewed_sha,
            "maximum_boot_clones": BOOT_CLONES,
            "task_intents": 0,
            "selection_or_final_tasks_dispatched": 0,
            "same_failed_id_replay_authorized": False,
        }
        intent_sha = one.write_new(INTENT, intent)
        argv = [sys.executable, "-m", "gitlab_world.v066_boot_only_probe_v5",
                "child-run", "--ratification-private", str(ratification_private),
                "--reviewed-public-sha256", reviewed_sha, "--execute"]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
        try:
            child = recovery._confirm_child_process_group(one.supervise_child(
                argv, cwd=ROOT, env=env,
                stdout_path=PROBE / "child.stdout.private.log",
                stderr_path=PROBE / "child.stderr.private.log",
                timeout_seconds=CHILD_WATCHDOG_SECONDS,
                grace_seconds=TERM_GRACE_SECONDS))
        except Exception as exc:
            child = {"child_terminated": False,
                     "process_group_terminated": False,
                     "exit_code": None, "timed_out": False,
                     "supervision_error_type": type(exc).__name__}
        child_receipt = None
        child_sha = None
        if CHILD_RESULT.exists():
            child_receipt, child_sha = _private_json(CHILD_RESULT)
        complete = bool(
            child.get("child_terminated") and
            child.get("process_group_terminated") and
            not child.get("timed_out") and child.get("exit_code") == 0 and
            child_receipt and
            child_receipt.get("status") ==
            "three_boot_only_clones_exact_baseline" and
            child_receipt.get("completed_boot_clones") == BOOT_CLONES and
            child_receipt.get("intent_sha256") == intent_sha and
            child_receipt.get("source_freeze_sha256") == freeze_sha and
            child_receipt.get("intent_nonce_sha256") ==
            private["intent_nonce_sha256"])
        cleanup = None
        fallback_forensics = None
        fallback_error_type = None
        if child.get("child_terminated") and child.get("process_group_terminated"):
            if complete:
                try:
                    lane.assert_live_world(old)
                    cleanup = {"cold_reset_exact": True,
                               "mode": "three_child_resets_independently_read_back"}
                except Exception as exc:
                    complete = False
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
            if not complete:
                # A watchdog can kill a child while reset.reset() is waiting
                # for health, before the child reaches its own log capture.
                # Preserve the current container's bytes before cleanup.
                try:
                    CLONES.mkdir(mode=0o700, exist_ok=True)
                    fallback_folder = CLONES / "supervisor-fallback"
                    fallback_folder.mkdir(mode=0o700, exist_ok=False)
                    fallback_forensics = capture_startup_forensics(
                        fallback_folder)
                    one.write_new(fallback_folder / "forensic-receipt.private.json",
                                  fallback_forensics)
                except Exception as exc:
                    fallback_error_type = type(exc).__name__
                try:
                    cleanup = one.exact_cold_reset()
                except Exception as exc:
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
        else:
            cleanup = {"cold_reset_exact": False,
                       "error_type": "child_process_group_unconfirmed_no_cleanup"}
        status = ("three_boot_only_clones_exact_baseline"
                  if complete and cleanup.get("cold_reset_exact") is True else
                  "terminal_probe_failure_exactly_reset_no_replay"
                  if cleanup.get("cold_reset_exact") is True else
                  "manual_review_required_no_replay")
        raw_log_sha256s = []
        child_capture_complete = bool(
            child_receipt and child_receipt.get("completed_boot_clones", 0) > 0)
        if child_receipt:
            for index in range(child_receipt["completed_boot_clones"]):
                receipt, _ = _private_json(
                    CLONES / f"{index:02d}" / "boot-receipt.private.json")
                raw_log_sha256s.append(
                    receipt["forensics"]["raw_file_sha256s"]["docker_logs_stdout"])
                child_capture_complete = bool(
                    child_capture_complete and
                    receipt["forensics"]["raw_startup_logs_saved"] and
                    receipt["forensics"]["state_only_inspect_saved"])
        if fallback_forensics:
            raw_log_sha256s.append(
                fallback_forensics["raw_file_sha256s"]["docker_logs_stdout"])
        fallback_complete = bool(fallback_forensics and
                                 fallback_forensics["raw_startup_logs_saved"] and
                                 fallback_forensics["state_only_inspect_saved"])
        supervisor = {
            "schema": SUPERVISOR_SCHEMA,
            "status": status,
            "source_freeze_sha256": freeze_sha,
            "intent_sha256": intent_sha,
            "intent_nonce_sha256": private["intent_nonce_sha256"],
            "child": child,
            "child_result_sha256": child_sha,
            "completed_boot_clones":
                child_receipt["completed_boot_clones"] if child_receipt else 0,
            "raw_log_sha256s": raw_log_sha256s,
            "fallback_forensics": fallback_forensics,
            "fallback_error_type": fallback_error_type,
            "fallback_log_capture_succeeded":
                fallback_complete,
            "raw_startup_logs_saved_before_cleanup":
                bool(child_capture_complete or fallback_complete),
            "private_forensic_tree_manifest": _forensic_tree_manifest(),
            "cleanup": cleanup,
            "post_failure_exact_reset":
                bool(not complete and cleanup.get("cold_reset_exact") is True),
            "child_process_group_terminated":
                child.get("process_group_terminated") is True,
            "same_failed_id_replay_authorized": False,
            "task_intents": 0,
            "selection_or_final_tasks_dispatched": 0,
            "model_calls": 0,
            "official_final_admitted": 0,
        }
        supervisor_sha = one.write_new(SUPERVISOR_RESULT, supervisor)
        public = _public_result(supervisor, supervisor_sha)
        one.write_new(PUBLIC_RESULT, public, 0o644)
        return public


def audit(ratification_private: Path) -> dict:
    private, freeze_sha = validate_freeze(ratification_private)
    if not INTENT.exists():
        require(not CHILD_RESULT.exists() and not SUPERVISOR_RESULT.exists() and
                not PUBLIC_RESULT.exists() and not CLONES.exists(),
                "boot_probe_outputs_without_intent")
        return _public_freeze(private, freeze_sha)
    intent, intent_sha = _private_json(INTENT)
    require(intent.get("schema") == INTENT_SCHEMA and
            intent.get("intent_nonce") == private["intent_nonce"] and
            intent.get("source_freeze_sha256") == freeze_sha and
            intent.get("maximum_boot_clones") == BOOT_CLONES and
            intent.get("task_intents") == 0 and
            intent.get("selection_or_final_tasks_dispatched") == 0 and
            intent.get("same_failed_id_replay_authorized") is False,
            "boot_probe_intent_changed")
    if not SUPERVISOR_RESULT.exists():
        return {"status": "pending_intent_no_replay",
                "intent_nonce_sha256": private["intent_nonce_sha256"],
                "task_intents": 0, "model_calls": 0,
                "official_final_admitted": 0}
    supervisor, supervisor_sha = _private_json(SUPERVISOR_RESULT)
    require(supervisor.get("schema") == SUPERVISOR_SCHEMA and
            supervisor.get("intent_sha256") == intent_sha and
            supervisor.get("source_freeze_sha256") == freeze_sha and
            supervisor.get("intent_nonce_sha256") ==
            private["intent_nonce_sha256"] and
            supervisor.get("same_failed_id_replay_authorized") is False and
            supervisor.get("task_intents") == 0 and
            supervisor.get("selection_or_final_tasks_dispatched") == 0 and
            supervisor.get("model_calls") ==
            supervisor.get("official_final_admitted") == 0,
            "boot_probe_supervisor_result_changed")
    child_sha = supervisor.get("child_result_sha256")
    expected_raw_log_sha256s = []
    child_capture_complete = False
    if child_sha is not None:
        child, actual_sha = _private_json(CHILD_RESULT)
        require(actual_sha == child_sha and
                child.get("schema") == CHILD_SCHEMA and
                child.get("intent_sha256") == intent_sha and
                child.get("task_intents") == 0 and
                child.get("selection_or_final_tasks_dispatched") == 0 and
                child.get("model_calls") ==
                child.get("official_final_admitted") == 0 and
                child.get("completed_boot_clones") ==
                len(child.get("boot_receipt_sha256s", [])) <= BOOT_CLONES,
                "boot_probe_child_result_changed")
        child_capture_complete = child["completed_boot_clones"] > 0
        for index, expected_sha in enumerate(child["boot_receipt_sha256s"]):
            folder = CLONES / f"{index:02d}"
            receipt, receipt_sha = _private_json(
                folder / "boot-receipt.private.json")
            require(receipt_sha == expected_sha and
                    receipt.get("boot_index") == index,
                    "boot_probe_boot_receipt_changed")
            hashes = receipt["forensics"]["raw_file_sha256s"]
            sizes = receipt["forensics"]["raw_file_bytes"]
            child_capture_complete = bool(
                child_capture_complete and
                receipt["forensics"]["raw_startup_logs_saved"] and
                receipt["forensics"]["state_only_inspect_saved"])
            expected_raw_log_sha256s.append(hashes["docker_logs_stdout"])
            names = {
                "docker_logs_stdout": "docker-logs.stdout.private.log",
                "docker_logs_stderr": "docker-logs.stderr.private.log",
                "docker_state_stdout": "docker-state.stdout.private.json",
                "docker_state_stderr": "docker-state.stderr.private.log",
            }
            require(set(hashes) == set(sizes) == set(names),
                    "boot_probe_forensic_file_manifest_changed")
            for key, filename in names.items():
                path = folder / filename
                require(path.is_file() and not path.is_symlink() and
                        path.stat().st_mode & 0o077 == 0 and
                        path.stat().st_size == sizes[key] and
                        one.sha(path.read_bytes()) == hashes[key],
                        "boot_probe_raw_startup_forensic_bytes_changed")
    fallback = supervisor.get("fallback_forensics")
    if fallback is not None:
        folder = CLONES / "supervisor-fallback"
        saved, _ = _private_json(folder / "forensic-receipt.private.json")
        require(saved == fallback and
                set(fallback["raw_file_sha256s"]) ==
                set(fallback["raw_file_bytes"]) == {
                    "docker_logs_stdout", "docker_logs_stderr",
                    "docker_state_stdout", "docker_state_stderr"},
                "boot_probe_supervisor_fallback_receipt_changed")
        filenames = {
            "docker_logs_stdout": "docker-logs.stdout.private.log",
            "docker_logs_stderr": "docker-logs.stderr.private.log",
            "docker_state_stdout": "docker-state.stdout.private.json",
            "docker_state_stderr": "docker-state.stderr.private.log",
        }
        for key, filename in filenames.items():
            path = folder / filename
            require(path.is_file() and not path.is_symlink() and
                    path.stat().st_mode & 0o077 == 0 and
                    path.stat().st_size == fallback["raw_file_bytes"][key] and
                    one.sha(path.read_bytes()) == fallback["raw_file_sha256s"][key],
                    "boot_probe_fallback_raw_forensic_bytes_changed")
        expected_raw_log_sha256s.append(
            fallback["raw_file_sha256s"]["docker_logs_stdout"])
    require(supervisor.get("raw_log_sha256s") == expected_raw_log_sha256s and
            supervisor.get("private_forensic_tree_manifest") ==
            _forensic_tree_manifest() and
            supervisor.get("fallback_log_capture_succeeded") is
            bool(fallback and fallback["raw_startup_logs_saved"] and
                 fallback["state_only_inspect_saved"]) and
            supervisor.get("raw_startup_logs_saved_before_cleanup") is
            bool(child_capture_complete or
                 (fallback and fallback["raw_startup_logs_saved"] and
                  fallback["state_only_inspect_saved"])) and
            (supervisor.get("status") !=
             "three_boot_only_clones_exact_baseline" or
             (child_sha is not None and
              supervisor.get("completed_boot_clones") == BOOT_CLONES and
              supervisor.get("child_process_group_terminated") is True and
              supervisor.get("cleanup", {}).get("cold_reset_exact") is True)),
            "boot_probe_supervisor_outcome_or_raw_log_refs_changed")
    require(json.loads(PUBLIC_RESULT.read_bytes()) ==
            _public_result(supervisor, supervisor_sha),
            "boot_probe_public_outcome_changed")
    return _public_result(supervisor, supervisor_sha)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit", "child-run", "run-probe"))
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
                         "three_boot_only_clones_exact_baseline" else 1)
    else:
        require(args.execute, "probe_requires_explicit_execute")
        result = run_probe(args.ratification_private,
                           args.reviewed_public_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
