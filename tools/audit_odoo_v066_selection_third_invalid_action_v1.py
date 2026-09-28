"""Read-only source-bound audit of the third retained Odoo selection attempt.

This derives the frozen action-validation mismatch from the saved step-8
observation and intent, and verifies the separate gate, journal, GUI chain,
saved reset, and lease. It never authorizes replay or official admission.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from cursibench.scale_action_contract import (
    ContractError, make_observation, validate_action as base_validate)
from cursibench.scale_action_contract_v066 import validate_action as v066_validate

from tools import audit_odoo_v066_selection_post_intent_stale_v1 as previous
from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-selection-third-invalid-action-incident-v1"
FROZEN_SOURCE_REVISION = "6149bfd3914c74728ee460782be98d0993026b8"
FROZEN_FREEZE_SHA256 = "737cb124d0a4fd87235f3090bec3a71ec5a7add09aa6d9ade4220d56e73bfa36"


class ThirdIncidentError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ThirdIncidentError(code)


def _historical_plan(repo: Path, private_plan_path: Path,
                     public_plan_path: Path,
                     source_freeze_path: Path) -> dict:
    freeze = protocol.public_json(source_freeze_path)
    require(protocol.digest(source_freeze_path.read_bytes()) ==
            FROZEN_FREEZE_SHA256 and
            freeze.get("schema") == protocol.SOURCE_FREEZE_SCHEMA and
            freeze.get("status") ==
            "frozen_after_visible_control_and_final_physical_frame_audit" and
            freeze.get("physical_dispatch_profile") ==
            protocol.PINNED_BORDER_PROFILE and
            freeze.get("retained_selection_failed_controls_before_freeze") == 2 and
            freeze.get("official_final_tasks_admitted") == 0,
            "third_historical_source_freeze_changed")
    for relative, expected in freeze["source_sha256s"].items():
        blob = subprocess.run(
            ["git", "show", f"{FROZEN_SOURCE_REVISION}:{relative}"],
            cwd=repo, capture_output=True, check=True).stdout
        require(protocol.digest(blob) == expected,
                "third_historical_source_blob_changed")
    plan = protocol.private_json(private_plan_path)
    public = protocol.public_json(public_plan_path)
    require(plan.get("schema") == protocol.PRIVATE_PLAN_SCHEMA and
            plan.get("split") == "selection" and
            plan.get("task_count") == 20 and
            len(plan.get("tasks", [])) == 20 and
            len({row["task_id"] for row in plan["tasks"]}) == 20 and
            plan.get("source_freeze_sha256") == FROZEN_FREEZE_SHA256 and
            plan.get("source_sha256s") == freeze["source_sha256s"] and
            plan.get("physical_dispatch_profile") ==
            protocol.PINNED_BORDER_PROFILE and
            public.get("private_plan_sha256") ==
            previous._sha(private_plan_path) and
            public.get("candidate_count") == 20,
            "third_historical_selection_plan_changed")
    return plan


def _validation_boundary(attempt: Path, intent: dict) -> tuple[bool, bool, int]:
    action = intent["normalized_action"]
    require(action.get("type") == "double_click" and
            action.get("target") == {"x": 508, "y": 479} and
            intent.get("step") == 8 and
            intent.get("dispatch_state") ==
            "intent_durable_before_gui_action",
            "third_step_eight_intended_action_changed")
    visible_path = previous._ref(attempt, intent["visible_text_ref"])
    visible = json.loads(visible_path.read_text())
    controls = visible.get("controls")
    target = intent.get("observed_target_control")
    require(type(controls) is list and len(controls) == 79 and
            controls == intent.get("observation_controls") and
            type(target) is dict and
            len([row for row in controls if
                 row.get("ref") == target.get("ref") and
                 row.get("role") == target.get("role") and
                 row.get("label") == target.get("label") and
                 row.get("visible") is True and
                 row.get("enabled") is True]) == 1 and
            target.get("visible") is True and
            target.get("enabled") is True and
            target.get("purchase_rfq_view") is True and
            type(target.get("bounds")) is list and
            target["bounds"][0] <= 508 <= target["bounds"][2] and
            target["bounds"][1] <= 479 <= target["bounds"][3],
            "third_model_visible_target_binding_changed")
    frame_path = previous._ref(attempt, intent["frame_ref"])
    frame = frame_path.read_bytes()
    require(sha256(frame).hexdigest() == intent["frame_sha256"] ==
            visible.get("screenshot", {}).get("sha256"),
            "third_saved_observation_frame_changed")
    observation = make_observation(
        task_id=action["task_id"],
        task_binding_sha256=action["task_binding_sha256"],
        instruction="offline frozen-action validation", step=8,
        screenshot_bytes=frame, controls=controls,
        previous_action_result={"status": "applied", "code": "ok"},
        memory=action["memory"])
    observation = replace(observation, frame_id=action["frame_id"])
    base_rejected = False
    try:
        base_validate(action, observation,
                      current_frame_id=observation.frame_id)
    except ContractError as error:
        base_rejected = error.code == "invalid_action"
    extended_accepted = (
        v066_validate(action, observation,
                      current_frame_id=observation.frame_id) == action)
    require(base_rejected and extended_accepted,
            "third_validator_mismatch_not_reproduced")
    # The frozen actor imported base.validate_action before any dispatch-guard
    # call; that source-level import is verified against the frozen Git blob.
    return base_rejected, extended_accepted, len(controls)


def audit(*, repo: Path, worker: Path, run_dir: Path,
          previous_run_dir: Path, private_plan_path: Path,
          public_plan_path: Path, source_freeze_path: Path,
          previous_incident_public_path: Path,
          verify_services: bool = False) -> dict:
    repo, worker = Path(repo).resolve(), Path(worker).resolve()
    private = protocol._worker_split(worker, "selection")
    plan = _historical_plan(repo, private_plan_path, public_plan_path,
                            source_freeze_path)
    protocol._private(run_dir, directory=True)
    require(run_dir.parent.resolve() ==
            (private / "v066_scale_controls").resolve() and
            run_dir.resolve() != previous_run_dir.resolve(),
            "third_run_directory_invalid")
    batch_path = run_dir / "batch-intent.private.json"
    batch = protocol.private_json(batch_path)
    require(batch.get("schema") == protocol.BATCH_SCHEMA and
            batch.get("split") == "selection" and
            batch.get("expected_case_count") == 20 and
            batch.get("private_plan_sha256") ==
            previous._sha(private_plan_path) and
            batch.get("source_freeze_sha256") == FROZEN_FREEZE_SHA256 and
            batch.get("official_final_tasks_admitted") == 0 and
            batch.get("model_attempts") == 0,
            "third_batch_source_or_counts_changed")
    independent._pinned_retry_gate_independent(
        worker_private=private, plan=plan, batch_intent=batch,
        private_plan_path=private_plan_path,
        source_freeze_path=source_freeze_path,
        incident_public_path=previous_incident_public_path,
        old_run_dir=previous_run_dir)
    journal_path = run_dir / "journal.private.jsonl"
    rows, tail, count = controller.read_journal(journal_path)
    row = plan["tasks"][0]
    batch_sha = previous._sha(batch_path)
    require(count == 2 and
            [item.get("event") for item in rows] ==
            ["case_started", "case_failed"] and
            all(item.get("ordinal") == 0 and
                item.get("task_id") == row["task_id"] and
                item.get("package_sha256") == row["package_sha256"] and
                item.get("attempt_dir") == "attempt-000" and
                item.get("run_intent_sha256") == batch_sha for item in rows),
            "third_journal_or_run_nonce_changed")
    attempt = run_dir / "attempt-000"
    protocol._private(attempt, directory=True)
    intent_path = attempt / "intent.private.json"
    initial = protocol.private_json(intent_path)
    failure_path = attempt / "failure.private.json"
    failure = protocol.private_json(failure_path)
    require(initial.get("task_id") == row["task_id"] and
            initial.get("package_sha256") == row["package_sha256"] and
            initial.get("source_freeze_sha256") == FROZEN_FREEZE_SHA256 and
            failure == {
                "schema": protocol.CASE_SCHEMA,
                "status": "failed_preserve_original_attempt_manual_review_required",
                "stage": "positive_gui", "error_type": "ContractError",
                "error_code": "invalid_action", "reset_exact": True,
                "services_restored": True,
                "official_final_tasks_admitted": 0,
                "model_attempts": 0,
            } and
            not (attempt / "attempt.private.json").exists() and
            not (attempt / "positive_sql.json").exists() and
            not (attempt / "negative_sql.json").exists(),
            "third_failure_stage_or_saved_result_changed")
    trace_path = attempt / "gui_trace.json"
    trace = protocol.private_json(trace_path)
    actions = trace.get("actions")
    rejections = trace.get("pre_intent_rejections")
    guards = trace.get("exact_return_guard_samples")
    require(trace.get("schema") == controller.TRACE_SCHEMA and
            trace.get("task_binding_sha256") == row["task_binding_sha256"] and
            trace.get("sft_examples_written") == 0 and
            type(actions) is list and len(actions) == 8 and
            type(rejections) is list and len(rejections) == 2 and
            type(guards) is list and len(guards) == 29,
            "third_trace_counts_or_holdout_boundary_changed")
    for step, action in enumerate(actions):
        frame = previous._ref(attempt, action["frame"])
        intents = sorted((attempt / "actions").glob(
            f"step-{step:03d}*-intent.private.json"))
        results = sorted((attempt / "actions").glob(
            f"step-{step:03d}*-result.private.json"))
        require(len(intents) == len(results) == 1 and
                action.get("step") == step and
                action.get("phase") == "positive",
                "third_completed_gui_action_identity_changed")
        saved_intent = protocol.private_json(intents[0])
        saved_result = protocol.private_json(results[0])
        receipt = action.get("contract_receipt", {})
        physical = receipt.get("physical_dispatch_guard", {})
        require(saved_intent.get("frame_sha256") == previous._sha(frame) and
                saved_result.get("intent_sha256") ==
                previous._sha(intents[0]) and
                saved_result.get("applied_action") ==
                saved_intent.get("normalized_action") and
                saved_result.get("contract_receipt") == receipt and
                receipt.get("action_type") ==
                saved_intent.get("normalized_action", {}).get("type") and
                receipt.get("frame_id_sha256") ==
                protocol.digest(saved_intent["frame_id"].encode()) and
                receipt.get("screenshot", {}).get("sha256") ==
                previous._sha(frame) and
                physical.get("classification") == "exact_physical_frame" and
                physical.get("observed_frame_sha256") ==
                previous._sha(frame),
                "third_completed_gui_action_or_physical_receipt_changed")
    for reference in rejections:
        rejected = protocol.private_json(previous._ref(attempt, reference))
        require(rejected.get("schema") ==
                "envloop-odoo-v066-pre-intent-frame-rejection-v1" and
                rejected.get("step") == 3 and
                rejected.get("error_code") == "stale_frame" and
                rejected.get("pre_dispatch_intent_created") is False and
                rejected.get("gui_action_dispatched") is False,
                "third_pre_intent_rejection_or_replay_changed")
        previous._ref(attempt, rejected["observed_frame_ref"])
        previous._ref(attempt, rejected["assistant_action_ref"])
    for index, sample in enumerate(guards):
        require(sample.get("sampled_frame_ref", {}).get("path") ==
                f"frames/guard-{index:04d}.png",
                "third_guard_sample_path_changed")
        previous._ref(attempt, sample["sampled_frame_ref"])
    step_intent_path = attempt / "actions/step-008-intent.private.json"
    step_intent = protocol.private_json(step_intent_path)
    base_rejected, extended_accepted, control_count = _validation_boundary(
        attempt, step_intent)
    require(not (attempt / "actions/step-008-result.private.json").exists()
            and not any(item.get("step") == 8 and
                        item.get("stage") == "dispatch" for item in guards) and
            guards[-1].get("step") == 8 and
            guards[-1].get("stage") == "parse" and
            guards[-1].get("classification") == "exact_return" and
            guards[-1].get("observed_frame_sha256") ==
            step_intent.get("frame_sha256"),
            "third_step_eight_dispatch_guard_or_result_present")
    source = protocol.private_json(attempt / "source_evidence.json")
    require(source.get("schema") ==
            "envloop-odoo-v066-native-source-presentation-v1" and
            source.get("task_id") == row["task_id"] and
            source.get("source_asset_sha256") ==
            row["source_asset_sha256"] and
            source.get("source_label") == row["source_label"] and
            source.get("source_frame_sha256") ==
            actions[5]["frame"]["sha256"],
            "third_native_pdf_source_frame_unbound")
    baseline = protocol.private_json(private / "baseline_snapshot.json")
    frozen_files = protocol.private_json(
        private / "baseline-filestore-manifest.json")
    require(protocol.private_json(attempt / "baseline_sql.json") == baseline and
            protocol.private_json(attempt / "restored_sql.json") == baseline and
            protocol.private_json(attempt / "restored_filestore.json") ==
            frozen_files,
            "third_saved_sql_or_full_filestore_reset_inexact")
    for name in ("pre_restore.json", "post_restore.json"):
        receipt = protocol.private_json(attempt / name)
        require(receipt.get("status") == "restored" and
                receipt.get("business_snapshot_equal") is True and
                receipt.get("physical_filestore_equal_before_web_restart")
                is True and
                receipt.get("db_sha256") ==
                plan["checkpoint"]["db_sha256"] and
                receipt.get("filestore_sha256") ==
                plan["checkpoint"]["filestore_sha256"],
                "third_restore_receipt_changed")
    lease_sha = previous._lease(private, intent_path, failure_path)
    locks_free = previous._locks_free(private)
    require(locks_free, "third_worker_lock_busy")
    services_exited = (previous._services_exited(worker)
                       if verify_services else None)
    if verify_services:
        require(services_exited is True,
                "third_selection_services_not_exited")
    actor_source = subprocess.run(
        ["git", "show", FROZEN_SOURCE_REVISION + ":enterprise_fallback/odoo18/"
         "odoo_v066_scale_pinned_border_adapter.py"],
        cwd=repo, capture_output=True, check=True).stdout
    require(b"from cursibench.scale_action_contract import ContractError, validate_action"
            in actor_source and
            b"super().dispatch(self._pending_dispatch_action)" in actor_source,
            "third_frozen_actor_validator_source_not_bound")
    return {
        "schema": SCHEMA,
        "status": "post_intent_pre_dispatch_base_validator_rejected_v066_double_click",
        "frozen_source_revision": FROZEN_SOURCE_REVISION,
        "source_freeze_sha256": FROZEN_FREEZE_SHA256,
        "private_plan_sha256": previous._sha(private_plan_path),
        "batch_intent_sha256": batch_sha,
        "journal_sha256": previous._sha(journal_path),
        "journal_tail_sha256": tail,
        "journal_bound_to_batch_intent": True,
        "private_attempt_intent_sha256": previous._sha(intent_path),
        "private_failure_sha256": previous._sha(failure_path),
        "private_gui_trace_sha256": previous._sha(trace_path),
        "private_step_eight_intent_sha256": previous._sha(step_intent_path),
        "native_source_pdf_visible_in_gui": True,
        "completed_gui_actions": 8,
        "recovered_pre_intent_stale_rejections": 2,
        "model_visible_controls_at_failed_step": control_count,
        "observed_target_matches_unique_visible_enabled_control": True,
        "base_v06_rejects_saved_double_click_invalid_action": base_rejected,
        "extended_v066_accepts_saved_double_click": extended_accepted,
        "step_eight_intent_durable": True,
        "step_eight_dispatch_guard_samples": 0,
        "step_eight_mouse_action_dispatched": False,
        "saved_sql_and_full_filestore_equal_frozen_baseline": True,
        "worker_lease_events_sha256": lease_sha,
        "worker_lease_acquired_and_released": True,
        "selection_worker_locks_free": locks_free,
        "selection_services_exited_zero": services_exited,
        "all_three_failed_attempts_preserved": True,
        "automatic_replay_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--previous-run-dir", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--previous-incident-public", type=Path, required=True)
    parser.add_argument("--verify-services", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(
            repo=args.repo, worker=args.worker, run_dir=args.run_dir,
            previous_run_dir=args.previous_run_dir,
            private_plan_path=args.private_plan,
            public_plan_path=args.public_plan,
            source_freeze_path=args.source_freeze,
            previous_incident_public_path=args.previous_incident_public,
            verify_services=args.verify_services), sort_keys=True))
    except (ThirdIncidentError, protocol.ScaleProtocolError,
            controller.ScaleControlError,
            independent.ScaleAuditError) as error:
        parser.exit(2, str(error) + "\n")
