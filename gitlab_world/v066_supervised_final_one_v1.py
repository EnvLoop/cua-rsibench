"""External one-ID GitLab final-control watchdog with exact-reset recovery.

The frozen prospective controller is launched unchanged in one child process
per ID. This wrapper has no model/provider path. A child that times out or
exits uncertain is never replayed: its journal is terminalized when safe,
and the disposable GitLab world is cold-reset to its independent baseline.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from . import prospective_final_controls_v066 as lane
from . import reset, runtime, verify


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = runtime.PRIVATE
RUN_DIR = PRIVATE_ROOT / "v066-prospective-final-controls-20260928"
SUPERVISION = RUN_DIR / "supervision"
PLAN = PRIVATE_ROOT / "v066-prospective-supervised-one-plan.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-prospective-supervised-one-plan-2026-09-28.json"
ERRATUM = ROOT / "docs/evidence/gitlab-v066-prospective-wall-cap-clarification-2026-09-28.json"
PREFLIGHT_PRIVATE = PRIVATE_ROOT / "final-candidate-preflight-20260928-v2.private.json"
PREFLIGHT_PUBLIC = ROOT / "docs/evidence/gitlab-final-candidate-preflight-2026-09-28-v2.json"
RATIFICATION_PUBLIC = ROOT / "docs/evidence/full-study-v066-caret-amended-control-ratification-2026-09-28.json"
SCHEMA = "envloop-gitlab-v066-supervised-one-control-plan-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-supervised-one-control-plan-public-v1"
INTENT_SCHEMA = "envloop-gitlab-v066-supervised-one-intent-v1"
RESULT_SCHEMA = "envloop-gitlab-v066-supervised-one-result-v1"
CHILD_TIMEOUT_SECONDS = 7200
TERM_GRACE_SECONDS = 30
SOURCE_FILES = (
    "gitlab_world/v066_supervised_final_one_v1.py",
    "tests/test_gitlab_v066_supervised_final_one.py",
    "docs/FULL_STUDY_GITLAB_V066_SUPERVISED_ONE_2026-09-28.md",
    "tools/audit_gitlab_v066_wall_cap_semantics_v1.py",
    "gitlab_world/prospective_final_controls_v066.py",
    "gitlab_world/reset.py",
    "gitlab_world/runtime.py",
    "gitlab_world/verify.py",
)


class SupervisionError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise SupervisionError(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def sources() -> dict[str, str]:
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def write_new(path: Path, value: dict, mode: int = 0o600) -> str:
    require(path.parent.is_dir() and not path.parent.is_symlink() and
            ((mode == 0o600 and path.parent.stat().st_mode & 0o077 == 0) or
             (mode == 0o644 and path.parent == ROOT / "docs/evidence")) and
            not path.exists() and not path.is_symlink(),
            "supervised_one_output_not_fresh_or_private")
    raw = canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def private_json(path: Path) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(PRIVATE_ROOT.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            "supervised_one_private_receipt_missing_or_unsafe")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "supervised_one_private_receipt_not_object")
    return value, sha(raw)


def inputs(ratification_private: Path) -> dict:
    return lane.base_inputs(PRIVATE_ROOT, PREFLIGHT_PRIVATE, PREFLIGHT_PUBLIC,
                            ratification_private, RATIFICATION_PUBLIC)


def _prior_bindings(ratification_private: Path) -> tuple[dict, str, dict, str]:
    bound = inputs(ratification_private)
    old_plan, old_sha = lane.validate_plan(RUN_DIR, bound)
    erratum_raw = ERRATUM.read_bytes()
    erratum = json.loads(erratum_raw)
    require(old_plan["max_wall_seconds_per_task"] == CHILD_TIMEOUT_SECONDS and
            erratum.get("schema") ==
            "envloop-gitlab-v066-wall-cap-clarification-v1" and
            erratum.get("controller_source_sha256") ==
            sha((ROOT / "gitlab_world/prospective_final_controls_v066.py").read_bytes()) and
            erratum.get("outer_per_id_timeout_or_cancellation_present") is False,
            "original_controller_or_posthoc_wall_cap_drifted")
    return old_plan, old_sha, bound, sha(erratum_raw)


def freeze(ratification_private: Path) -> dict:
    require(not PLAN.exists() and not PUBLIC_PLAN.exists() and
            not SUPERVISION.exists(),
            "fresh_supervised_one_source_plan_required")
    old, old_sha, bound, erratum_sha = _prior_bindings(ratification_private)
    state = lane.journal_state(lane.read_journal(RUN_DIR, old_sha), old)
    require(state["next_index"] == 0 and state["pending"] is None and
            not state["failed"] and
            runtime.ACTIVE_VERSION == "v3" and
            len(old["task_roster"]) == 100,
            "supervisor_must_freeze_before_first_v066_id")
    test = subprocess.run(
        [sys.executable, "-m", "unittest",
         "tests.test_gitlab_v066_supervised_final_one"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        check=False)
    require(test.returncode == 0 and "Ran 5 tests" in test.stderr and
            "OK" in test.stderr,
            "supervised_timeout_and_exact_reset_tests_failed")
    source = sources()
    value = {
        "schema": SCHEMA,
        "status": "source_frozen_one_id_child_watchdog_no_final_control_yet",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "original_100_id_plan_sha256": old_sha,
        "original_source_bundle_sha256": old["source_bundle_sha256"],
        "ratification_private_sha256":
            sha(ratification_private.read_bytes()),
        "prior_wall_cap_erratum_sha256": erratum_sha,
        "baseline_business_sha256": bound["baseline_business_sha256"],
        "source_sha256s": source,
        "source_bundle_sha256": sha(canonical(source)),
        "one_id_per_child_process": True,
        "child_timeout_seconds": CHILD_TIMEOUT_SECONDS,
        "term_grace_seconds": TERM_GRACE_SECONDS,
        "kill_entire_child_process_group_on_timeout": True,
        "terminalize_uncertain_id_before_any_reuse": True,
        "exact_cold_reset_required_after_nonpassing_child": True,
        "simulated_test_count": 5,
        "simulated_test_stderr_sha256": sha(test.stderr.encode()),
        "model_calls": 0,
        "current_v066_control_ids": 0,
        "official_final_admitted": 0,
    }
    private_sha = write_new(PLAN, value)
    SUPERVISION.mkdir(mode=0o700)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_one_id_supervisor_not_executed",
        "private_plan_sha256": private_sha,
        "original_100_id_plan_sha256": old_sha,
        "source_bundle_sha256": value["source_bundle_sha256"],
        "prior_wall_cap_erratum_sha256": erratum_sha,
        "one_id_per_child_process": True,
        "child_timeout_seconds": CHILD_TIMEOUT_SECONDS,
        "term_grace_seconds": TERM_GRACE_SECONDS,
        "simulated_timeout_and_exact_reset_tests": 5,
        "model_calls": 0,
        "current_v066_control_ids": 0,
        "official_final_admitted": 0,
    }
    write_new(PUBLIC_PLAN, public, 0o644)
    return public


def validate_plan(ratification_private: Path) -> tuple[dict, dict, dict, str]:
    old, old_sha, bound, erratum_sha = _prior_bindings(ratification_private)
    value, digest = private_json(PLAN)
    public = json.loads(PUBLIC_PLAN.read_bytes())
    source = sources()
    require(value.get("schema") == SCHEMA and
            value.get("status") ==
            "source_frozen_one_id_child_watchdog_no_final_control_yet" and
            value.get("original_100_id_plan_sha256") == old_sha and
            value.get("original_source_bundle_sha256") ==
            old["source_bundle_sha256"] and
            value.get("ratification_private_sha256") ==
            sha(ratification_private.read_bytes()) and
            value.get("prior_wall_cap_erratum_sha256") == erratum_sha and
            value.get("baseline_business_sha256") ==
            bound["baseline_business_sha256"] and
            value.get("source_sha256s") == source and
            value.get("source_bundle_sha256") == sha(canonical(source)) and
            value.get("one_id_per_child_process") is True and
            value.get("child_timeout_seconds") == CHILD_TIMEOUT_SECONDS and
            value.get("term_grace_seconds") == TERM_GRACE_SECONDS and
            value.get("kill_entire_child_process_group_on_timeout") is True and
            value.get("terminalize_uncertain_id_before_any_reuse") is True and
            value.get("exact_cold_reset_required_after_nonpassing_child") is True and
            value.get("simulated_test_count") == 5 and
            value.get("model_calls") ==
            value.get("current_v066_control_ids") ==
            value.get("official_final_admitted") == 0 and
            public.get("schema") == PUBLIC_SCHEMA and
            public.get("private_plan_sha256") == digest and
            public.get("original_100_id_plan_sha256") == old_sha and
            public.get("source_bundle_sha256") == value["source_bundle_sha256"] and
            public.get("simulated_timeout_and_exact_reset_tests") == 5 and
            public.get("model_calls") ==
            public.get("current_v066_control_ids") ==
            public.get("official_final_admitted") == 0,
            "source_bound_supervised_one_plan_changed")
    return value, old, bound, old_sha


@contextmanager
def lock_supervisor():
    lock = SUPERVISION / ".supervisor.lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        require(os.fstat(fd).st_mode & 0o077 == 0,
                "supervised_one_lock_not_private")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def supervise_child(argv: list[str], *, cwd: Path, env: dict[str, str],
                    stdout_path: Path, stderr_path: Path,
                    timeout_seconds: float, grace_seconds: float) -> dict:
    """Bound the entire child process group; logs are evaluator-private."""
    require(timeout_seconds > 0 and grace_seconds >= 0 and
            not stdout_path.exists() and not stderr_path.exists(),
            "fresh_positive_process_deadline_and_private_logs_required")
    out_fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    err_fd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    started = time.monotonic()
    timed_out = False
    sigkill_used = False
    child_terminated = True
    with os.fdopen(out_fd, "wb") as stdout, os.fdopen(err_fd, "wb") as stderr:
        child = subprocess.Popen(argv, cwd=cwd, env=env,
                                 stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        try:
            child.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                sigkill_used = True
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child_terminated = False
    return {
        "timed_out": timed_out,
        "sigkill_used": sigkill_used,
        "child_terminated": child_terminated,
        "child_pid": child.pid,
        "exit_code": child.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout_sha256": sha(stdout_path.read_bytes()),
        "stderr_sha256": sha(stderr_path.read_bytes()),
    }


def exact_cold_reset() -> dict:
    """Recover even if a killed child removed the disposable container."""
    baseline = reset._baseline()
    state = reset._state()
    require(state["baseline_business_sha256"] == baseline["business_sha256"],
            "supervised_cleanup_seed_and_baseline_differ")
    try:
        runtime.inspect(runtime.WORLD)
    except subprocess.CalledProcessError:
        world_exists = False
    else:
        world_exists = True
    if world_exists:
        receipt = reset.reset()
        require(receipt.get("cold_reset") is True and
                receipt.get("same_business_sha256") is True,
                "supervised_cleanup_existing_world_reset_failed")
        mode = "existing_world_cold_reset"
    else:
        for role in runtime.DESTS:
            reset._unmount_and_clear(role)
            reset._mount(role, state["seed_volume_lowerdirs"][role])
        created = reset._create_case()
        mode = "missing_world_recreated_from_immutable_lowerdirs"
    current = verify.state_snapshot()
    world = runtime.proof(runtime.WORLD)
    original = json.loads((PRIVATE_ROOT / "demo-prestop.json").read_bytes())
    demo = runtime.proof(runtime.DEMO)
    require(current == baseline and
            world["running"] is True and world["health"] == "healthy" and
            world["image_id"] == runtime.IMAGE_ID and
            runtime.stable_identity(demo) == runtime.stable_identity(original) and
            demo["running"] is False,
            "supervised_cleanup_not_exact_or_original_demo_changed")
    if not world_exists:
        state["clone_generation"] += 1
        state["last_clone_container_id_sha256"] = created["container_id_sha256"]
        state["last_readback_equal"] = True
        temporary = reset.STATE_FILE.with_suffix(".supervised.tmp")
        require(not temporary.exists(), "stale_supervised_reset_state_temp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write((json.dumps(state, sort_keys=True, indent=2) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, reset.STATE_FILE)
    return {"mode": mode, "cold_reset_exact": True,
            "business_sha256": current["business_sha256"],
            "world_healthy": True,
            "preserved_demo_identity_unchanged": True}


def terminalize_uncertain(index: int, old: dict, old_sha: str,
                          *, error_type: str,
                          wall_seconds: float) -> dict:
    """Close one pending/no-intent journal case after its child has exited."""
    entries = lane.read_journal(RUN_DIR, old_sha)
    state = lane.journal_state(entries, old)
    if state["failed"]:
        return {"terminal_failure": True, "journal_action": "existing_terminal_failure"}
    if len(state["completed"]) > index:
        return {"terminal_failure": False,
                "journal_action": "completed_but_child_uncertain_manual_review"}
    require(state["next_index"] == index and
            (state["pending"] is None or
             state["pending"]["task_index"] == index),
            "uncertain_child_journal_identity_changed")
    item = old["task_roster"][index]
    journal = RUN_DIR / "journal.private.jsonl"
    if state["pending"] is None:
        lane.append_event(journal, old_sha, entries, {
            "kind": "intent", "task_index": index,
            "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "source_bundle_sha256": old["source_bundle_sha256"],
            "official_final_admitted": 0,
        })
    lane.append_event(journal, old_sha, entries, {
        "kind": "terminal", "task_index": index,
        "task_id": item["task_id"],
        "status": "control_failed", "error_type": error_type,
        "wall_seconds": round(max(0.0, wall_seconds), 3),
        "trio_receipt_sha256": None,
        "official_final_admitted": 0,
    })
    after = lane.journal_state(lane.read_journal(RUN_DIR, old_sha), old)
    require(after["failed"] and after["pending"] is None,
            "uncertain_id_not_terminalized")
    return {"terminal_failure": True,
            "journal_action": "supervisor_appended_terminal_failure"}


def child_argv(ratification_private: Path) -> list[str]:
    return [
        sys.executable, "-m", "gitlab_world.prospective_final_controls_v066",
        "run", "--private-root", str(PRIVATE_ROOT),
        "--preflight-private", str(PREFLIGHT_PRIVATE),
        "--preflight-public", str(PREFLIGHT_PUBLIC),
        "--ratification-private", str(ratification_private),
        "--ratification-public", str(RATIFICATION_PUBLIC),
        "--run-dir", str(RUN_DIR), "--max-tasks", "1", "--execute",
    ]


def _prior_supervision_complete(index: int, old_sha: str) -> None:
    for prior_index in range(index):
        receipt, _ = private_json(
            SUPERVISION / f"{prior_index:03d}-result.private.json")
        require(receipt.get("schema") == RESULT_SCHEMA and
                receipt.get("status") ==
                "one_id_completed_and_raw_receipts_independently_audited" and
                receipt.get("original_100_id_plan_sha256") == old_sha and
                receipt.get("task_index") == prior_index and
                receipt.get("post_attempt_baseline_exact") is True and
                receipt.get("official_final_admitted") == 0,
                "prior_id_supervision_receipt_not_complete")


def run_one(ratification_private: Path) -> dict:
    wrapper, old, bound, old_sha = validate_plan(ratification_private)
    with lock_supervisor():
        entries = lane.read_journal(RUN_DIR, old_sha)
        state = lane.journal_state(entries, old)
        index = state["next_index"]
        require(index < 100 and state["pending"] is None and
                not state["failed"],
                "supervised_one_requires_clean_next_id")
        _prior_supervision_complete(index, old_sha)
        lane.assert_live_world(old)
        item = old["task_roster"][index]
        intent_path = SUPERVISION / f"{index:03d}-intent.private.json"
        result_path = SUPERVISION / f"{index:03d}-result.private.json"
        require(not intent_path.exists() and not result_path.exists(),
                "same_id_supervisor_attempt_or_result_already_exists")
        write_new(intent_path, {
            "schema": INTENT_SCHEMA,
            "wrapper_plan_sha256": sha(PLAN.read_bytes()),
            "original_100_id_plan_sha256": old_sha,
            "task_index": index,
            "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "one_id_per_child_process": True,
            "child_timeout_seconds": CHILD_TIMEOUT_SECONDS,
            "provider_or_gui_replay_authorized": False,
            "official_final_admitted": 0,
        })
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
        try:
            child = supervise_child(
                child_argv(ratification_private), cwd=ROOT, env=env,
                stdout_path=SUPERVISION / f"{index:03d}-child.stdout.private.log",
                stderr_path=SUPERVISION / f"{index:03d}-child.stderr.private.log",
                timeout_seconds=CHILD_TIMEOUT_SECONDS,
                grace_seconds=TERM_GRACE_SECONDS,
            )
        except Exception as exc:
            child = {"timed_out": False, "sigkill_used": False,
                     "child_terminated": True, "child_pid": None,
                     "exit_code": None, "elapsed_seconds": 0.0,
                     "launch_or_supervision_error_type": type(exc).__name__}
        status = "manual_review_required_no_replay"
        terminal = None
        cleanup = None
        raw_audit = None
        if child["child_terminated"]:
            try:
                after_entries = lane.read_journal(RUN_DIR, old_sha)
                after = lane.journal_state(after_entries, old)
                passed = (not child["timed_out"] and child["exit_code"] == 0 and
                          after["next_index"] == index + 1 and
                          after["pending"] is None and not after["failed"])
            except Exception as exc:
                passed = False
                raw_audit = {"journal_error_type": type(exc).__name__}
            if passed:
                try:
                    private_audit, _public = lane.audit_controls(RUN_DIR, bound)
                    lane.assert_live_world(old)
                    require(private_audit["completed_task_count"] == index + 1,
                            "supervised_one_raw_receipt_audit_count_changed")
                except Exception as exc:
                    raw_audit = {"raw_receipt_error_type": type(exc).__name__}
                else:
                    status = "one_id_completed_and_raw_receipts_independently_audited"
                    raw_audit = {"completed_task_count": index + 1,
                                 "all_current_raw_receipts_reopened": True}
                    cleanup = {"cold_reset_exact": True,
                               "mode": "original_controller_three_case_resets_verified"}
            if status != "one_id_completed_and_raw_receipts_independently_audited":
                try:
                    terminal = terminalize_uncertain(
                        index, old, old_sha,
                        error_type=("SupervisedProcessTimeout" if child["timed_out"]
                                    else "SupervisedChildNonpassingExit"),
                        wall_seconds=child["elapsed_seconds"])
                except Exception as exc:
                    terminal = {"terminal_failure": False,
                                "journal_error_type": type(exc).__name__}
                try:
                    cleanup = exact_cold_reset()
                except Exception as exc:
                    cleanup = {"cold_reset_exact": False,
                               "error_type": type(exc).__name__}
                if (terminal.get("terminal_failure") is True and
                        cleanup.get("cold_reset_exact") is True):
                    status = "one_id_terminal_no_replay_exactly_reset"
        else:
            raw_audit = {"error_type": "child_process_group_not_confirmed_terminated"}
            cleanup = {"cold_reset_exact": False,
                       "error_type": "live_child_may_still_mutate_world"}
        receipt = {
            "schema": RESULT_SCHEMA,
            "status": status,
            "wrapper_plan_sha256": sha(PLAN.read_bytes()),
            "original_100_id_plan_sha256": old_sha,
            "task_index": index,
            "task_id": item["task_id"],
            "child": child,
            "journal_reconciliation": terminal,
            "cleanup": cleanup,
            "raw_audit": raw_audit,
            "post_attempt_baseline_exact":
                bool(cleanup and cleanup.get("cold_reset_exact")),
            "provider_or_gui_replay_authorized": False,
            "official_final_admitted": 0,
        }
        result_sha = write_new(result_path, receipt)
        return {"status": status, "task_index": index,
                "private_result_sha256": result_sha,
                "post_attempt_baseline_exact":
                    receipt["post_attempt_baseline_exact"],
                "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit", "run-one"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(args.ratification_private)
    elif args.action == "audit":
        wrapper, _old, _bound, _sha = validate_plan(args.ratification_private)
        result = {"status": wrapper["status"],
                  "source_bundle_sha256": wrapper["source_bundle_sha256"],
                  "current_v066_control_ids": 0,
                  "official_final_admitted": 0}
    else:
        require(args.execute, "explicit_one_id_supervised_execute_required")
        result = run_one(args.ratification_private)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
