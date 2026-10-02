"""Audit terminal v7 child evidence; separately reconcile missing supervision.

This tool never invokes a GUI, task runner, provider, supervisor, reset, or
Docker mutation. The original v7 supervisor/public outputs stay absent. Its
optional finalize action creates a distinct, owner-only interruption receipt,
with both original exit status and watchdog outcome explicitly unknown.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import audit_gitlab_v6_train_post_terminal_20260930 as saved


PLAN_SHA256 = "028e9a92387f1005ae925f77fff867ca2801283ec27509bf87f0dd105f2b4730"
PUBLIC_PLAN_SHA256 = "46788ae9150d0c25c0880e2f7b3291a22b9820828cc525c23f66e61f4b150770"
INTENT_SHA256 = "3edf1ab48db7eefc0c91924c6b7afbdf6ebcde792c63e3ce951481dea723292d"
CHILD_SHA256 = "bc140add160b1c275ccbb487fe8cd98708789d6f874af190bc8639f9a34391d6"
SAVED_AUDITOR_SHA256 = "300928a6e17a7c1a91610e3ee6bd37f1bb7c2d6a6a3c612a619296aca9a8b395"
TERMINAL_CONTROL_SHA256 = "e27b0d0828075f2ada6efbe117fb7e339b93725e2d93b8f42278f581fc36ecf8"
RESET_STATE_SHA256 = "2d008e933292d65c861fef320878ed96b964fc7229ef2d43bb7a9f171ec49b0c"
RUN_RELATIVE = "work/gitlab-full-world/v066-new-train-diagnostic-v7-20260930"
PUBLIC_PLAN_RELATIVE = "docs/evidence/gitlab-v066-new-train-diagnostic-v7-source-freeze-2026-09-30.json"
PUBLIC_RESULT_RELATIVE = "docs/evidence/gitlab-v066-new-train-diagnostic-v7-outcome-2026-09-30.json"
TERMINAL_CONTROL_RELATIVE = "docs/evidence/gitlab-v066-current-thirteen-id-terminal-controls-2026-09-29.json"
SOURCE_FILES = (
    "gitlab_world/v066_new_train_diagnostic_v7.py",
    "tests/test_gitlab_v066_new_train_diagnostic_v7.py",
    "docs/FULL_STUDY_GITLAB_V066_NEW_TRAIN_DIAGNOSTIC_V7_2026-09-30.md",
    "gitlab_world/v066_new_train_diagnostic_v6.py",
    "tools/audit_gitlab_v6_train_post_terminal_20260930.py",
    "gitlab_world/gui_controls.py", "gitlab_world/operators.py",
    "gitlab_world/verify.py", "gitlab_world/reset.py", "gitlab_world/runtime.py",
)
FRAME_ROLES = ("policy.png", "issue-before.png", "issue-after.png")
CASE_NAMES = ("positive-1", "wrong-historical-issue", "positive-2")

digest = saved.digest
canonical = saved.canonical
need = saved.need
private = saved.private


def manifest(root: Path) -> dict:
    """Bind every existing private artifact, including stdout and the lock."""
    need(root.is_dir() and not root.is_symlink() and
         stat.S_IMODE(root.stat().st_mode) == 0o700, "v7_run_root_not_private")
    rows = []
    for path in sorted(root.rglob("*")):
        need(not path.is_symlink(), "v7_artifact_symlink")
        mode = stat.S_IMODE(path.stat().st_mode)
        need((path.is_dir() and mode == 0o700) or
             (path.is_file() and mode == 0o600), "v7_artifact_mode_not_exact")
        row = {"path": str(path.relative_to(root)), "mode": mode,
               "type": "directory" if path.is_dir() else "file"}
        if path.is_file():
            raw = path.read_bytes()
            row.update(sha256=digest(raw), bytes=len(raw))
        rows.append(row)
    return {"entries": rows, "sha256": digest(canonical(rows))}


def source_and_intent(repo: Path, root: Path) -> tuple[dict, dict, dict]:
    plan_raw, plan = private(root / "source-freeze.private.json")
    intent_raw, intent = private(root / "intent.private.json")
    child_raw, child = private(root / "child-result.private.json")
    public_raw = (repo / PUBLIC_PLAN_RELATIVE).read_bytes()
    public = json.loads(public_raw)
    need(digest(plan_raw) == PLAN_SHA256 and
         digest(intent_raw) == INTENT_SHA256 and digest(child_raw) == CHILD_SHA256 and
         digest(public_raw) == PUBLIC_PLAN_SHA256 and
         public.get("private_plan_sha256") == PLAN_SHA256 and
         set(plan.get("source_sha256s", {})) == set(SOURCE_FILES) and
         all(digest((repo / name).read_bytes()) == plan["source_sha256s"][name]
             for name in SOURCE_FILES) and
         plan.get("source_bundle_sha256") == digest(canonical(plan["source_sha256s"])) and
         digest(Path(saved.__file__).read_bytes()) == SAVED_AUDITOR_SHA256,
         "v7_frozen_source_plan_or_evidence_changed")
    need(plan.get("schema") == "envloop-gitlab-v066-new-train-diagnostic-v7-private-plan-v1" and
         plan.get("selected_train_ordinal") == 3 and
         plan.get("same_v6_or_terminal_final_identity_replay_authorized") is False and
         intent.get("schema") == "envloop-gitlab-v066-new-train-diagnostic-v7-private-intent-v1" and
         intent.get("source_freeze_sha256") == PLAN_SHA256 and
         intent.get("reviewed_public_freeze_sha256") == PUBLIC_PLAN_SHA256 and
         intent.get("intent_nonce") == plan.get("intent_nonce") and
         intent.get("intent_nonce_sha256") == plan.get("intent_nonce_sha256") and
         digest(intent["intent_nonce"].encode()) == plan.get("intent_nonce_sha256") and
         intent.get("train_task_id") == plan.get("train_task_id") and
         intent.get("train_task_package_sha256") == plan.get("train_task_package_sha256") and
         intent.get("partition") == "train" and
         intent.get("same_v6_or_terminal_final_identity_replay_authorized") is False and
         child.get("schema") == "envloop-gitlab-v066-new-train-diagnostic-v7-private-child-v1" and
         child.get("status") == "three_train_gui_cases_saved_pending_supervisor_review" and
         child.get("source_freeze_sha256") == PLAN_SHA256 and
         child.get("intent_sha256") == INTENT_SHA256 and
         child.get("intent_nonce_sha256") == plan.get("intent_nonce_sha256") and
         child.get("train_task_package_sha256") == plan.get("train_task_package_sha256") and
         child.get("completed_cases") == 3 and child.get("scores") == [1.0, 0.0, 1.0] and
         len(child.get("case_receipt_sha256s", [])) == 3 and
         all(obj.get("provider_calls") == obj.get("selection_or_final_tasks_dispatched") == 0
             for obj in (plan, intent, child)) and
         plan.get("official_final_admitted") == child.get("official_final_admitted") == 0,
         "v7_consumed_intent_or_child_binding_changed")
    world_raw, world = private(repo / "work/gitlab-full-world/world-private.json")
    baseline_raw, _ = private(repo / "work/gitlab-full-world/baseline-persisted-state.json")
    need(digest(world_raw) == plan["original_world_sha256"] and
         digest(baseline_raw) == plan["original_baseline_sha256"], "v7_world_or_baseline_changed")
    matches = [t for t in world["tasks"] if t["task_id"] == plan["train_task_id"]]
    need(len(matches) == 1 and matches[0]["partition"] == "train" and
         digest(canonical(matches[0])) == plan["train_task_package_sha256"],
         "v7_train_package_changed")
    return plan, child, matches[0]


def frame_and_log_audit(root: Path, child: dict) -> dict:
    from PIL import Image
    count = 0
    blocked_schemes = set()
    for index, name in enumerate(CASE_NAMES):
        folder = root / "cases" / f"{index:02d}-{name}"
        _, receipt = private(folder / "case-receipt.private.json")
        gui = receipt["gui"]
        screens = gui["screenshots_sha256"]
        need(gui.get("screenshots_owner_only_from_creation") is True and
             gui.get("frame_sequence") == [
                 {"role": role, "sha256": screens[role]} for role in FRAME_ROLES],
             "v7_frame_order_or_route_guard_changed")
        blocked = gui.get("blocked_external_request_schemes")
        need(type(blocked) is list and all(type(item) is str for item in blocked) and
             blocked == sorted(set(blocked)), "v7_blocked_route_record_changed")
        blocked_schemes.update(blocked)
        for role in FRAME_ROLES:
            path = folder / role
            need(stat.S_IMODE(path.stat().st_mode) == 0o600 and
                 path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "v7_png_not_owner_only")
            with Image.open(path) as image:
                need(image.format == "PNG" and image.width == 1440 and image.height >= 1000,
                     "v7_png_dimensions_changed")
                image.verify()
            count += 1
        forensic = receipt["forensics"]
        need(forensic.get("docker_logs_exit_code") == 0 and
             forensic.get("docker_inspect_state_exit_code") == 0 and
             forensic.get("docker_logs_error_type") is None and
             forensic.get("docker_inspect_state_error_type") is None,
             "v7_raw_forensic_capture_failed")
    stdout = root / "child.stdout.private.log"
    stderr = root / "child.stderr.private.log"
    need(stdout.is_file() and stderr.is_file() and stderr.read_bytes() == b"",
         "v7_child_logs_missing_or_nonempty_stderr")
    value = json.loads(stdout.read_bytes())
    need(value == {"status": child["status"], "child_result_sha256": CHILD_SHA256},
         "v7_child_stdout_not_bound_to_terminal_result")
    return {"validated_owner_only_pngs": count, "frame_order_reopened": True,
            "saved_external_route_guard_blocked_schemes": sorted(blocked_schemes),
            "child_stdout_sha256": digest(stdout.read_bytes()),
            "child_stderr_sha256": digest(stderr.read_bytes()),
            "child_stderr_empty": True}


def assert_no_original_results(repo: Path, root: Path) -> None:
    targets = (root / "supervisor-result.private.json", repo / PUBLIC_RESULT_RELATIVE)
    need(all(not path.exists() and not path.is_symlink() for path in targets),
         "v7_original_result_now_present")


def read_only_source_and_live(repo: Path, ratification: Path, *, check_live: bool) -> dict:
    """Use frozen original functions only for read-only validation and scoring."""
    script = r'''
import json, sys
from pathlib import Path
from gitlab_world import v066_new_train_diagnostic_v7 as d
rat=Path(sys.argv[1]); check_live=sys.argv[2]=='1'
d.validate_freeze(rat)
parent=d.terminal.audit(rat)
assert parent['status']=='terminal_failure_no_replay'
assert parent['completed_current_controls']==13
assert parent['pending_batch'] is False and parent['pending_id'] is False
assert parent['official_final_admitted']==0
_, _, task=d.validate_freeze(rat)
scores=[]
for index, (name, _, expected) in enumerate(d.CASES):
    folder=d.CASES_DIR/f'{index:02d}-{name}'
    receipt=json.loads((folder/'case-receipt.private.json').read_bytes())
    before=json.loads((folder/'before.private.json').read_bytes())
    after=json.loads((folder/'after.private.json').read_bytes())
    score=d.previous.score_saved_case(task,before,after,negative=expected==0.0)
    assert score==receipt['score'] and score['score']==expected
    scores.append(score['score'])
if check_live:
    old=d.terminal.validate_freeze(rat)[1]['old']
    baseline=d.lane.assert_live_world(old)
    assert d.verify.state_snapshot()==baseline
print(json.dumps({'source_and_v6_forensic_boundary_validated':True,
  'original_audit_status':d.audit(rat)['status'],
  'completed_original_terminal_controls':13,
  'oracle_saved_scores':scores,'live_exact_baseline':True if check_live else None},sort_keys=True))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src") + os.pathsep + str(repo)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(ratification), "1" if check_live else "0"],
                            cwd=repo, env=env, capture_output=True, text=True,
                            timeout=240)
    need(result.returncode == 0, "v7_original_source_or_live_validation_failed")
    value = json.loads(result.stdout)
    need(value["original_audit_status"] == "pending_v7_intent_no_replay" and
         value["oracle_saved_scores"] == [1.0, 0.0, 1.0], "v7_original_audit_boundary_changed")
    return value


def no_matching_processes() -> None:
    listing = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True,
                             text=True, timeout=10, check=True).stdout.splitlines()
    pattern = re.compile(r"(?:^|\s)(?:-m\s+gitlab_world\.v066_new_train_diagnostic_v7|"
                         r"\S*/v066_new_train_diagnostic_v7\.py)(?:\s|$)")
    need(not any(pattern.search(row) for row in listing), "v7_original_process_still_running")


def audit(*, repo: Path, ratification: Path, check_live: bool = True) -> dict:
    need(repo.is_absolute() and repo.is_dir(), "original_evaluator_repo_required")
    root = repo / RUN_RELATIVE
    assert_no_original_results(repo, root)
    no_matching_processes()
    before_manifest = manifest(root)
    plan, child, task = source_and_intent(repo, root)
    cases = saved.saved_case_trio(repo, root, child, task)
    frames = frame_and_log_audit(root, child)
    reset_raw, reset_state = private(repo / "work/gitlab-full-world/cow-reset-state.json")
    need(digest(reset_raw) == RESET_STATE_SHA256 and
         reset_state.get("last_readback_equal") is True, "v7_last_reset_state_changed")
    last = json.loads((root / "cases/02-positive-2/case-receipt.private.json").read_bytes())
    need(last["reset_receipt"]["generation"] == reset_state["clone_generation"],
         "v7_last_reset_generation_not_current")
    need(digest((repo / TERMINAL_CONTROL_RELATIVE).read_bytes()) == TERMINAL_CONTROL_SHA256,
         "v7_index13_terminal_public_boundary_changed")
    source = read_only_source_and_live(repo, ratification, check_live=check_live)
    assert_no_original_results(repo, root)
    no_matching_processes()
    need(manifest(root) == before_manifest, "v7_evidence_changed_during_read_only_audit")
    reconciliation = root / "interruption-reconciliation.private.json"
    reconciliation_sha = None
    if reconciliation.exists():
        raw, receipt = private(reconciliation)
        need(receipt.get("schema") ==
             "envloop-gitlab-v066-v7-interruption-reconciliation-private-v1" and
             receipt.get("terminal_child_result_sha256") == CHILD_SHA256 and
             receipt.get("one_use_intent_sha256") == INTENT_SHA256 and
             receipt.get("original_supervisor_evidence_reconstructed") is False and
             receipt.get("same_intent_replay_authorized") is False and
             receipt.get("success_claim_authorized") is False and
             receipt.get("official_final_admitted") == 0,
             "v7_existing_separate_reconciliation_changed")
        reconciliation_sha = digest(raw)
    return {
        "schema": "envloop-gitlab-v066-v7-interruption-audit-public-v1",
        "status": "terminal_child_evidence_reopened_original_supervision_missing_no_replay",
        "source_freeze_public_sha256": PUBLIC_PLAN_SHA256,
        "private_plan_sha256": PLAN_SHA256,
        "one_use_intent_sha256": INTENT_SHA256,
        "terminal_child_result_sha256": CHILD_SHA256,
        "audit_tool_sha256": digest(Path(__file__).read_bytes()),
        "existing_private_artifact_manifest_sha256": before_manifest["sha256"],
        "existing_private_artifact_entries": len(before_manifest["entries"]),
        "partition": "train", "saved_child_case_scores": cases["scores"],
        "independent_postgres_git_wrong_object_delta_rederived": True,
        "scorer_reopened_against_saved_states": True,
        "saved_before_and_restored_exact_baseline": True,
        "consecutive_exact_cold_reset_generations": cases["reset_generation_count"],
        "latest_saved_reset_is_current": True,
        "saved_raw_docker_log_and_state_files": cases["raw_docker_log_and_state_files"],
        **frames,
        "saved_post_reset_states_running_healthy_no_oom": True,
        "source_and_v6_forensic_boundary_validated": source["source_and_v6_forensic_boundary_validated"],
        "original_terminal_controls_unchanged": source["completed_original_terminal_controls"],
        "original_index13_terminal_boundary_sha256": TERMINAL_CONTROL_SHA256,
        "matching_original_processes_at_audit": 0,
        "live_original_postgres_git_exact_baseline": source["live_exact_baseline"],
        "original_supervisor_result_present": False,
        "original_public_outcome_present": False,
        "original_audit_status": source["original_audit_status"],
        "original_supervisor_exit_code": None,
        "original_watchdog_timed_out": None,
        "original_process_group_termination_receipt_available": False,
        "separate_reconciliation_executed": reconciliation_sha is not None,
        "separate_reconciliation_receipt_sha256": reconciliation_sha,
        "same_intent_replay_authorized": False,
        "success_claim_authorized": False,
        "provider_calls": 0, "selection_or_final_tasks_dispatched": 0,
        "official_final_admitted": 0,
    }


def write_new(path: Path, raw: bytes, mode: int) -> None:
    """Never overwrite; link a complete file with its final mode atomically."""
    need(path.parent.is_dir() and not path.parent.is_symlink() and
         not path.exists() and not path.is_symlink(), "receipt_path_not_new")
    with NamedTemporaryFile(dir=path.parent, prefix=".v7-reconcile-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), mode)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def existing_diagnostic_lock(root: Path):
    """Acquire the original lock without creating or writing any artifact."""
    descriptor = os.open(root / ".diagnostic.lock", os.O_RDONLY |
                         getattr(os, "O_NOFOLLOW", 0))
    try:
        mode = os.fstat(descriptor).st_mode
        need(stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o600,
             "v7_original_diagnostic_lock_not_private")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def finalize(*, repo: Path, ratification: Path, reviewed_tool_sha256: str,
             reviewed_audit: Path, reviewed_audit_sha256: str) -> dict:
    need(reviewed_tool_sha256 == digest(Path(__file__).read_bytes()),
         "reviewed_reconciliation_tool_sha256_required")
    raw = reviewed_audit.read_bytes()
    need(digest(raw) == reviewed_audit_sha256, "reviewed_interruption_audit_sha256_required")
    reviewed = json.loads(raw)
    with existing_diagnostic_lock(repo / RUN_RELATIVE):
        return _finalize_locked(repo=repo, ratification=ratification,
                                reviewed=reviewed,
                                reviewed_tool_sha256=reviewed_tool_sha256,
                                reviewed_audit_sha256=reviewed_audit_sha256)


def _finalize_locked(*, repo: Path, ratification: Path, reviewed: dict,
                     reviewed_tool_sha256: str, reviewed_audit_sha256: str) -> dict:
    current = audit(repo=repo, ratification=ratification, check_live=True)
    need(current == reviewed and current["live_original_postgres_git_exact_baseline"] is True,
         "reviewed_interruption_audit_no_longer_current")
    receipt = {
        "schema": "envloop-gitlab-v066-v7-interruption-reconciliation-private-v1",
        "status": "saved_terminal_child_reconciled_missing_original_supervision_no_replay",
        "reconciled_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_audit_sha256": reviewed_audit_sha256,
        "reviewed_tool_sha256": reviewed_tool_sha256,
        "terminal_child_result_sha256": CHILD_SHA256,
        "one_use_intent_sha256": INTENT_SHA256,
        "original_supervisor_evidence_reconstructed": False,
        "original_supervisor_exit_code": None,
        "original_watchdog_timed_out": None,
        "original_process_group_termination_receipt_available": False,
        "original_supervisor_result_created": False,
        "original_public_outcome_created": False,
        "live_exact_baseline_at_reconciliation": True,
        "saved_child_case_scores": [1.0, 0.0, 1.0],
        "same_intent_replay_authorized": False,
        "gui_or_task_dispatches": 0, "provider_calls": 0,
        "selection_or_final_tasks_dispatched": 0, "official_final_admitted": 0,
        "success_claim_authorized": False,
    }
    root = repo / RUN_RELATIVE
    target = root / "interruption-reconciliation.private.json"
    no_matching_processes()
    assert_no_original_results(repo, root)
    write_new(target, canonical(receipt) + b"\n", 0o600)
    return {"status": receipt["status"], "separate_receipt_sha256": digest(target.read_bytes()),
            "original_supervisor_evidence_reconstructed": False,
            "same_intent_replay_authorized": False, "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "finalize"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--public-output", type=Path)
    parser.add_argument("--reviewed-tool-sha256", default="")
    parser.add_argument("--reviewed-audit", type=Path)
    parser.add_argument("--reviewed-audit-sha256", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "audit":
        need(not args.execute, "audit_is_read_only")
        result = audit(repo=args.repo, ratification=args.ratification_private)
        if args.public_output:
            need(not args.public_output.resolve().is_relative_to(args.repo.resolve()),
                 "public_audit_must_not_write_original_evaluator")
            write_new(args.public_output, canonical(result) + b"\n", 0o644)
    else:
        need(args.execute and args.reviewed_audit is not None and not args.public_output,
             "finalize_requires_reviewed_tool_and_audit_explicit_execute")
        result = finalize(repo=args.repo, ratification=args.ratification_private,
                          reviewed_tool_sha256=args.reviewed_tool_sha256,
                          reviewed_audit=args.reviewed_audit,
                          reviewed_audit_sha256=args.reviewed_audit_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
