"""One source-frozen Odoo two-frame v6 candidate GUI control.

This is a separate evaluator-only runner. It uses the frozen original GUI
recipe, emits current-candidate attempt identities, and independently audits
saved positive/negative/reset state. It never reuses an old attempt or emits a
researcher campaign or official final admission. The CLI requires --execute.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools import audit_odoo_v066_two_frame_case_v6 as case_audit
from tools import audit_odoo_v066_two_frame_no_gui_gate_v6 as gate_audit
from tools import odoo_v066_current_candidate_case_v6 as case_path
from tools import odoo_v066_two_frame_plan_v6 as plan_audit
from tools import odoo_v066_two_frame_source_v6 as source
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


BATCH_SCHEMA = "envloop-odoo-v066-two-frame-one-selection-intent-v6"
STATUS = "one_raw_two_frame_selection_control_complete_review_pending"


class CurrentControlError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise CurrentControlError(code)


def run_one(*, worker_dir: Path, historical_root: Path,
            prior_v4_private_plan: Path, prior_v4_public_plan: Path,
            old_private_plan: Path, old_public_plan: Path,
            prior_v5_private_plan: Path, prior_v5_public_plan: Path,
            private_freeze: Path,
            private_plan: Path, public_plan: Path,
            execute: bool, case_executor=None, case_auditor=None,
            batch_auditor=None) -> dict:
    require(execute, "current_control_requires_explicit_execute")
    worker = Path(worker_dir).resolve()
    require(worker.name == "selection" and
            os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "current_control_original_selection_worker_not_selected")
    source.validate()
    plan_audit.audit(
        worker_dir=worker,
        prior_private_plan=prior_v5_private_plan,
        prior_public_plan=prior_v5_public_plan,
        private_freeze=private_freeze,
        private_plan=private_plan, public_plan=public_plan)
    verified_gate = gate_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_v4_private_plan=prior_v4_private_plan,
        prior_v4_public_plan=prior_v4_public_plan,
        prior_v5_private_plan=prior_v5_private_plan,
        prior_v5_public_plan=prior_v5_public_plan,
        private_freeze=private_freeze,
        private_plan=private_plan, public_plan=public_plan,
        old_private_plan=old_private_plan, old_public_plan=old_public_plan)
    require(verified_gate["status"] ==
            "fresh_two_frame_sql_full_filestore_gate_independently_verified",
            "current_control_live_baseline_gate_not_verified")
    plan = protocol.private_json(private_plan)
    private = protocol._worker_split(worker, "selection")
    run_root = private / "v066_scale_controls"
    run_dir = run_root / plan["fresh_run_directory_name"]
    require(not run_dir.exists() and not run_dir.is_symlink(),
            "current_control_fresh_run_already_exists")
    row = dict(plan["tasks"][0])
    row.update({
        "source_freeze_sha256": plan["source_freeze_sha256"],
        "epoch_source_freeze_sha256": source.digest(source.FREEZE),
        "cell_plan_sha256": epoch.digest(private_plan),
        "physical_dispatch_profile": plan["physical_dispatch_profile"],
        "current_candidate_private_sha256":
            plan["current_candidate_private_sha256"],
        "historical_ratification_sha256":
            plan["historical_ratification_sha256"],
        "no_gui_gate_sha256": verified_gate["gate_sha256"],
        "run_nonce_sha256": protocol.digest(bytes.fromhex(
            plan["run_nonce_hex"])),
    })
    world = protocol.private_json(private / "partition_cases.json")
    family = row["family"]
    cases = world["cases"][family]
    targets = [case for case in cases if case["id"] == row["task_id"]]
    require(len(targets) == 1, "current_control_target_world_case_missing")
    wrongs = [case for case in cases if case["id"] != row["task_id"]]
    require(len(wrongs) >= 1, "current_control_wrong_object_missing")
    executor = case_executor or case_path.execute_case
    auditor = case_auditor or case_audit.audit_current_case
    factory, gui_controls, reset, verify, lease = controller._modules(worker)
    with controller._run_lock(run_root):
        require(not run_dir.exists(), "current_control_run_race")
        power_pre_intent = power.capture()
        run_dir.mkdir(mode=0o700)
        protocol.write_new(run_dir / "batch-intent.private.json", {
            "schema": BATCH_SCHEMA,
            "status": "durable_before_first_original_odoo_service_call",
            "split": "selection",
            "private_plan_sha256": epoch.digest(private_plan),
            "public_plan_sha256": epoch.digest(public_plan),
            "current_candidate_private_sha256":
                plan["current_candidate_private_sha256"],
            "historical_ratification_sha256":
                plan["historical_ratification_sha256"],
            "source_freeze_sha256": plan["source_freeze_sha256"],
            "epoch_source_freeze_sha256": source.digest(source.FREEZE),
            "prior_v5_failure_receipt_sha256":
                plan["prior_v5_failure_receipt_sha256"],
            "no_gui_gate_sha256": verified_gate["gate_sha256"],
            "two_frame_v6_source_freeze_sha256":
                source.digest(source.FREEZE),
            "two_frame_v6_private_source_freeze_sha256":
                plan_audit.digest(private_freeze),
            "host_power_pre_intent": power_pre_intent,
            "run_nonce_hex": plan["run_nonce_hex"],
            "expected_case_count": 1,
            "automatic_replay_authorized": False,
            "control_dispatch_authorized": False,
            "campaign_dispatch_authorized": False,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        }, private=True)
        batch_sha = epoch.digest(run_dir / "batch-intent.private.json")
        attempt = run_dir / "attempt-000"
        started = False
        try:
            with lease.exclusive_worker_operation(controller.LEASE_OPERATION):
                power_pre_dispatch = power.capture()
                controller._event(run_dir / "journal.private.jsonl", {
                    "host_power_pre_dispatch": power_pre_dispatch,
                    "event": "case_started", "ordinal": 0,
                    "task_id": row["task_id"],
                    "package_sha256": row["package_sha256"],
                    "attempt_dir": "attempt-000",
                    "run_intent_sha256": batch_sha,
                })
                started = True
                executor(
                    run_dir=run_dir, ordinal=0, row=row,
                    case=targets[0], wrong=wrongs[0], family=family,
                    modules=(factory, gui_controls, reset, verify, lease))
            protocol._private(attempt / "attempt.private.json")
            result = auditor(plan=plan, row=row, attempt=attempt,
                             worker_private=private)
            require(result.get("status") ==
                    "two_frame_v6_raw_gui_semantics_verified_source_visual_review_pending" and
                    result.get("independent_baseline_reward") == 0.0 and
                    result.get("independent_positive_reward") == 1.0 and
                    result.get("independent_wrong_object_reward") == 0.0 and
                    result.get("full_pre_web_filestore_reset_exact") is True and
                    result.get("protected_post_web_source_bytes_equal") is True and
                    result.get("source_visual_review_pending") is True and
                    result.get("official_final_tasks_admitted") == 0,
                    "current_control_independent_positive_negative_reset_failed")
            power_end = power.capture()
        except BaseException as error:
            try:
                power_end = power.capture()
            except BaseException as power_error:
                power_end = {"status": "host_power_end_unavailable",
                             "error_type": type(power_error).__name__}
            if not started:
                protocol.write_new(run_dir / "pre-dispatch-failure.private.json", {
                    "schema": BATCH_SCHEMA,
                    "status": "terminal_before_case_started_no_replay",
                    "batch_intent_sha256": batch_sha,
                    "run_nonce_sha256": row["run_nonce_sha256"],
                    "error_type": type(error).__name__,
                    "host_power_end": power_end,
                    "official_final_tasks_admitted": 0,
                    "model_attempts": 0,
                }, private=True)
            if started:
                failure = attempt / "failure.private.json"
                if not failure.exists():
                    attempt.mkdir(mode=0o700, exist_ok=True)
                    protocol.write_new(failure, {
                        "schema": case_path.EPOCH_CASE_SCHEMA,
                        "status": "failed_preserve_original_attempt_manual_review_required",
                        "stage": "independent_audit_or_outer_runner",
                        "error_type": type(error).__name__,
                        "current_candidate_private_sha256":
                            plan["current_candidate_private_sha256"],
                        "no_gui_gate_sha256": verified_gate["gate_sha256"],
                        "run_nonce_sha256": row["run_nonce_sha256"],
                        "official_final_tasks_admitted": 0,
                        "model_attempts": 0,
                        "host_power_end": power_end,
                    }, private=True)
                controller._event(run_dir / "journal.private.jsonl", {
                    "host_power_end": power_end,
                    "event": "case_failed", "ordinal": 0,
                    "task_id": row["task_id"],
                    "package_sha256": row["package_sha256"],
                    "attempt_dir": "attempt-000",
                    "run_intent_sha256": batch_sha,
                    "failure_receipt_sha256": epoch.digest(failure),
                })
            raise CurrentControlError(
                "current_control_failed_preserve_original_no_automatic_replay") from error
        controller._event(run_dir / "journal.private.jsonl", {
            "host_power_end": power_end,
            "event": "case_completed", "ordinal": 0,
            "task_id": row["task_id"],
            "package_sha256": row["package_sha256"],
            "attempt_dir": "attempt-000",
            "run_intent_sha256": batch_sha,
            "attempt_receipt_sha256": epoch.digest(
                attempt / "attempt.private.json"),
        })
        raw_result = {
            "schema": BATCH_SCHEMA,
            "status": STATUS,
            "batch_intent_sha256": batch_sha,
            "journal_sha256": epoch.digest(
                run_dir / "journal.private.jsonl"),
            "independently_audited_raw_cases": 1,
            "selection_candidate_count": 20,
            "source_visual_reviews_pending": 1,
            "control_dispatch_authorized": False,
            "campaign_dispatch_authorized": False,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        }
    independent = batch_auditor or case_audit.audit_one_batch
    try:
        batch_result = independent(
            worker_dir=worker, historical_root=historical_root,
            prior_v4_private_plan=prior_v4_private_plan,
            prior_v4_public_plan=prior_v4_public_plan,
            prior_v5_private_plan=prior_v5_private_plan,
            prior_v5_public_plan=prior_v5_public_plan,
            private_freeze=private_freeze,
            private_plan=private_plan, public_plan=public_plan,
            old_private_plan=old_private_plan,
            old_public_plan=old_public_plan)
        require(batch_result.get("status") ==
                "one_raw_two_frame_control_independently_verified_visual_review_pending" and
                batch_result.get("independently_verified_raw_selection_controls") == 1 and
                batch_result.get("official_final_tasks_admitted") == 0,
                "current_control_independent_batch_audit_failed")
    except BaseException as error:
        raise CurrentControlError(
            "current_control_batch_audit_failed_preserve_raw_no_replay") from error
    return {**raw_result,
            "independent_batch_audit_status": batch_result["status"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--prior-v4-private-plan", type=Path, required=True)
    parser.add_argument("--prior-v4-public-plan", type=Path, required=True)
    parser.add_argument("--prior-v5-private-plan", type=Path, required=True)
    parser.add_argument("--prior-v5-public-plan", type=Path, required=True)
    parser.add_argument("--private-freeze", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    value = run_one(worker_dir=args.worker_dir,
                    historical_root=args.historical_root,
                    prior_v4_private_plan=args.prior_v4_private_plan,
                    prior_v4_public_plan=args.prior_v4_public_plan,
                    prior_v5_private_plan=args.prior_v5_private_plan,
                    prior_v5_public_plan=args.prior_v5_public_plan,
                    private_freeze=args.private_freeze,
                    private_plan=args.private_plan,
                    public_plan=args.public_plan,
                    old_private_plan=args.old_private_plan,
                    old_public_plan=args.old_public_plan,
                    execute=args.execute)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
