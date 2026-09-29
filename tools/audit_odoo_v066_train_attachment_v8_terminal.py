"""Read-only independent audit of the terminal v8 train dispatch attempt."""

from __future__ import annotations

import argparse
from hashlib import sha1
import json
from pathlib import Path

from enterprise_fallback.odoo18.partition_factory import source_asset
from tools import audit_odoo_v066_train_attachment_calibration_v8 as prior
from tools.audit_odoo_v066_train_attachment_v6_terminal import (
    ALTERNATE_POINTS, ALTERNATE_RGB_PAIRS, _pixel_changes,
)
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v8 as run


SCHEMA = "envloop-odoo-train-attachment-v8-terminal-audit-v1"
VISUAL_SCHEMA = "envloop-odoo-train-attachment-v8-terminal-visual-review-v1"


def audit(*, worker_dir: Path, accepted_audit_path: Path,
          private_freeze_path: Path, public_freeze_path: Path) -> dict:
    worker, private, freeze, case, _wrong = run._verify_freeze(
        worker_dir, accepted_audit_path, private_freeze_path,
        public_freeze_path)
    out = private / "v066_attachment_route_calibration" / run.RUN_NAME
    prior._private(out, directory=True)
    intent_path, failure_path = (out / "intent.private.json",
                                 out / "failure.private.json")
    intent, failure = prior._json(intent_path), prior._json(failure_path)
    nonce_sha = protocol.digest(freeze["run_nonce"].encode())
    prior.require(
        intent.get("schema") == run.SCHEMA and
        intent.get("status") == "durable_before_first_docker_or_gui_action" and
        intent.get("split") == "train" and
        intent.get("family") == "purchase" and
        intent.get("task_package_sha256") == freeze["task_package_sha256"] and
        intent.get("private_freeze_sha256") ==
            protocol.digest(Path(private_freeze_path).read_bytes()) and
        intent.get("public_freeze_sha256") ==
            protocol.digest(Path(public_freeze_path).read_bytes()) and
        intent.get("run_nonce_sha256") == nonce_sha and
        intent.get("selection_or_hidden_dispatch_authorized") is False and
        intent.get("model_attempts") == 0 and
        intent.get("official_final_tasks_admitted") == 0 and
        failure.get("schema") == run.RECEIPT_SCHEMA and
        failure.get("status") == "terminal_failure_no_automatic_replay" and
        failure.get("stage") == "positive_gui" and
        failure.get("error_type") == "ContractError" and
        failure.get("error_code") == "stale_frame" and
        failure.get("run_nonce_sha256") == nonce_sha and
        failure.get("reset_exact") is True and
        failure.get("services_restored") is True and
        failure.get("model_attempts") == 0 and
        failure.get("official_final_tasks_admitted") == 0 and
        not (out / "attempt.private.json").exists(),
        "terminal_v8_identity_or_outcome_invalid")
    readiness = prior._json(out / "db_readiness.json")
    prior.require(readiness.get("status") ==
                  "postgres_health_and_select_1_ready" and
                  readiness.get("query") == "SELECT 1" and
                  readiness.get("observations", [])[-1].get("psql_exit_code") == 0,
                  "terminal_v8_db_readiness_invalid")
    baseline = prior._json(private / "baseline_snapshot.json")
    frozen_files = prior._json(private / "baseline-filestore-manifest.json")
    for name in ("pre_restore", "post_restore"):
        reset = prior._json(out / f"{name}.json")
        prior.require(reset.get("status") == "restored" and
                      reset.get("business_snapshot_equal") is True and
                      reset.get("physical_filestore_equal_before_web_restart") is True and
                      reset.get("db_sha256") == freeze["checkpoint"]["db_sha256"] and
                      reset.get("filestore_sha256") ==
                      freeze["checkpoint"]["filestore_sha256"],
                      "terminal_v8_cold_reset_invalid")
    prior.require(
        prior._json(out / "baseline_sql.json") == baseline and
        prior._json(out / "restored_sql.json") == baseline and
        prior._json(out / "restored_filestore.json") == frozen_files and
        not any((out / name).exists() for name in
                ("positive_sql.json", "negative_sql.json",
                 "positive_reload_frame.png", "negative_reload_frame.png")),
        "terminal_v8_full_state_or_phase_boundary_invalid")
    world = prior._json(private / "partition_cases.json")
    source = source_asset(case, world)
    checksum = sha1(source).hexdigest()
    attachments = [row for row in baseline["attachments"]
                   if row.get("name") == f"{case['id']}-source.pdf"]
    prior.require(
        len(attachments) == 1 and
        attachments[0].get("checksum") == checksum and
        attachments[0].get("file_size") == len(source) and
        frozen_files.get("filestore/bench/" + checksum[:2] + "/" +
                         checksum) == protocol.digest(source) and
        protocol.digest(source) == freeze["source_asset_sha256"],
        "terminal_v8_source_pdf_not_physically_bound")
    trace_path = out / "gui_trace.json"
    trace = prior._json(trace_path)
    actions, samples = trace.get("actions"), trace.get("guard_samples")
    rejected_refs = trace.get("pre_intent_rejections")
    prior.require(
        trace.get("task_binding_sha256") == freeze["task_package_sha256"] and
        trace.get("sft_examples_written") == 0 and
        type(actions) is list and len(actions) == 8 and
        type(samples) is list and len(samples) == 32 and
        type(rejected_refs) is list and len(rejected_refs) == 1,
        "terminal_v8_gui_trace_invalid")
    frames = {}
    intents = {}
    link_count = viewer_count = 0
    for step in range(8):
        path = out / "frames" / f"step-{step:03d}.png"
        ref = {"path": f"frames/step-{step:03d}.png",
               "sha256": protocol.digest(path.read_bytes())}
        _path, frames[step] = prior._ref(out, ref, image=True)
        action_intent_path = out / "actions" / f"step-{step:03d}-intent.private.json"
        action_intent = prior._json(action_intent_path)
        intents[step] = action_intent
        action_result = prior._json(
            out / "actions" / f"step-{step:03d}-result.private.json")
        action = actions[step]
        prior.require(
            action_intent.get("step") == step and
            action_intent.get("phase") == action.get("phase") == "positive" and
            action_intent.get("task_id") == case["id"] and
            action_intent.get("task_binding_sha256") ==
                freeze["task_package_sha256"] and
            action_intent.get("frame_sha256") == ref["sha256"] and
            action.get("step") == step and action.get("frame") == ref and
            action_result.get("intent_sha256") ==
                protocol.digest(action_intent_path.read_bytes()) and
            action_result.get("applied_action") ==
                action_intent.get("normalized_action") and
            action_result.get("contract_receipt") ==
                action.get("contract_receipt") and
            action.get("contract_receipt", {}).get("error_code") is None,
            "terminal_v8_completed_action_changed")
        _refs, count = prior._guard(
            out, action, action_intent, action_result,
            f"{case['id']}-source.pdf", samples)
        link_count += count
        _refs, count = prior._viewer_guard(
            out, action, action_intent, action_result,
            f"{case['id']}-source.pdf", samples)
        viewer_count += count
        prior.require(
            action["contract_receipt"].get("price_parse_guard") is None and
            action["contract_receipt"].get("price_dispatch_guard") is None,
            "terminal_v8_price_guard_dispatched_before_failure")
    prior.require(
        link_count == viewer_count == 1 and
        actions[6]["contract_receipt"].get("viewer_return_guard", {}).get(
            "classification") == "original_rfq_return_confirmed" and
        intents[7].get("normalized_action", {}).get("type") == "click" and
        intents[7].get("observed_target_control", {}).get("role") == "td" and
        intents[7].get("observed_target_control", {}).get(
            "purchase_rfq_view") is True and
        actions[7]["contract_receipt"].get(
            "physical_dispatch_guard", {}).get("classification") ==
            "two_frame_observed_confirmed",
        "terminal_v8_viewer_return_or_price_click_invalid")
    for sample in samples:
        prior._ref(out, sample["sampled_frame_ref"], image=True)
    disk_guards = {str(path) for path in (out / "frames").glob("guard-*.png")}
    sample_guards = {str(prior._ref(
        out, sample["sampled_frame_ref"], image=True)[0]) for sample in samples}
    prior.require(sample_guards == disk_guards and len(disk_guards) == 32,
                  "terminal_v8_guard_png_set_changed")
    rejection_ref = rejected_refs[0]
    prior.require(rejection_ref.get("path") ==
                  "actions/step-008-rejection.private.json",
                  "terminal_v8_pre_intent_rejection_ref_invalid")
    rejection = prior._artifact(out, rejection_ref)
    first_assistant = prior._artifact(out, rejection["assistant_action_ref"])
    initial_observed = prior._ref(out, rejection["observed_frame_ref"],
                                  image=True)[1]
    initial_current = prior._ref(out, rejection["current_frame_ref"],
                                 image=True)[1]
    prior.require(
        rejection.get("schema") ==
            "envloop-odoo-v066-pre-intent-frame-rejection-v1" and
        rejection.get("phase") == "positive" and
        rejection.get("step") == 8 and
        rejection.get("observation_attempt") == 0 and
        rejection.get("error_code") == "stale_frame" and
        rejection.get("pre_dispatch_intent_created") is False and
        rejection.get("gui_action_dispatched") is False and
        first_assistant.get("type") == "double_click" and
        type(first_assistant.get("target")) is dict and
        not (out / "actions/step-008-intent.private.json").exists(),
        "terminal_v8_first_observation_boundary_invalid")
    resample_intent_path = out / "actions/step-008-resample-01-intent.private.json"
    resample_intent = prior._json(resample_intent_path)
    resample_observed = prior._ref(
        out, resample_intent["frame_ref"], image=True)[1]
    second_assistant = prior._artifact(
        out, resample_intent["assistant_action_ref"])
    prior.require(
        resample_intent.get("schema") ==
            "envloop-odoo-v066-pre-dispatch-action-intent-v1" and
        resample_intent.get("phase") == "positive" and
        resample_intent.get("step") == 8 and
        resample_intent.get("pre_intent_stale_resamples") == 1 and
        resample_intent.get("dispatch_state") ==
            "intent_durable_before_gui_action" and
        resample_intent.get("task_id") == case["id"] and
        resample_intent.get("task_binding_sha256") ==
            freeze["task_package_sha256"] and
        resample_intent.get("frame_sha256") ==
            protocol.digest(resample_observed) and
        resample_intent.get("normalized_action", {}).get("type") ==
            "double_click" and
        resample_intent.get("normalized_action", {}).get("target") ==
            first_assistant["target"] == second_assistant.get("target") and
        resample_intent.get("observed_target_control", {}).get("role") ==
            "input" and
        resample_intent.get("observed_target_control", {}).get(
            "purchase_rfq_view") is True and
        not (out / "actions/step-008-resample-01-result.private.json").exists(),
        "terminal_v8_durable_intent_or_missing_result_invalid")
    step8 = [sample for sample in samples if sample.get("step") == 8]
    prior.require(
        len(step8) == 3 and
        [sample.get("stage") for sample in step8] ==
            ["parse", "parse", "dispatch"] and
        [sample.get("classification") for sample in step8] ==
            ["third_or_material_frame_rejected", "exact_return",
             "third_or_material_frame_rejected"] and
        not any("price" in sample.get("stage", "") for sample in step8),
        "terminal_v8_price_route_guard_not_absent")
    first_guard = prior._ref(out, step8[0]["sampled_frame_ref"], image=True)[1]
    parsed_guard = prior._ref(out, step8[1]["sampled_frame_ref"], image=True)[1]
    dispatch_guard = prior._ref(out, step8[2]["sampled_frame_ref"], image=True)[1]
    prior.require(first_guard == initial_current and
                  parsed_guard == resample_observed and
                  initial_observed == dispatch_guard and
                  initial_current == resample_observed,
                  "terminal_v8_two_state_route_sequence_invalid")
    bbox, changes = _pixel_changes(initial_observed, initial_current)
    prior.require(bbox == (16, 861, 18, 864) and
                  set(changes) == ALTERNATE_POINTS and
                  set(changes.values()) == ALTERNATE_RGB_PAIRS and
                  not (bbox[0] <= first_assistant["target"]["x"] < bbox[2]
                       and bbox[1] <= first_assistant["target"]["y"] < bbox[3]),
                  "terminal_v8_raster_pair_not_exact_corner")
    review_path = out / "independent_visual_review.private.json"
    review = prior._json(review_path)
    prior.require(
        review.get("schema") == VISUAL_SCHEMA and
        review.get("decision") ==
            "source_pdf_and_returned_rfq_visible_before_price_dispatch_rejection" and
        review.get("source_frame_sha256") ==
            protocol.digest(prior._ref(out, actions[5]["frame"], image=True)[1]) and
        review.get("post_close_rfq_frame_sha256") ==
            protocol.digest(frames[7]) and
        review.get("price_editor_observation_sha256") ==
            protocol.digest(resample_observed) and
        review.get("source_asset_sha256") ==
            freeze["source_asset_sha256"] and
        review.get("source_pdf_pages_visually_reviewed") == 1 and
        review.get("visible_heading_and_three_line_table_match_source") is True and
        review.get("native_rfq_visible_after_viewer_close") is True and
        review.get("selected_price_cell_visible_before_dispatch_rejection") is True and
        review.get("source_values_published") is False,
        "terminal_v8_independent_visual_review_missing")
    rows = [json.loads(row) for row in
            (private / "worker-lease-events.jsonl").read_bytes().splitlines()]
    leases = [row for row in rows if row.get("operation") ==
              "v066_train_attachment_calibration"]
    intent_time = prior._time(intent["started_at_utc"])
    pairs = [(a, b) for a, b in zip(leases, leases[1:])
             if a.get("event") == "acquired" and
             b.get("event") == "released" and
             a.get("pid") == b.get("pid") and
             prior._time(a["at_utc"]) <= intent_time <=
                 prior._time(b["at_utc"])]
    prior.require(len(pairs) == 1 and run._running(worker) == set(),
                  "terminal_v8_lease_or_service_cleanup_invalid")
    prior.require(
        type(review.get("reviewer_id_sha256")) is str and
        prior.HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
        prior._time(review.get("reviewed_at_utc")) >=
            prior._time(pairs[0][1]["at_utc"]),
        "terminal_v8_visual_review_not_independent_and_post_run")
    return {
        "schema": SCHEMA,
        "status": "train_only_price_dispatch_rejected_after_generic_parse",
        "public_freeze_sha256":
            protocol.digest(Path(public_freeze_path).read_bytes()),
        "private_freeze_sha256":
            protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_intent_sha256": protocol.digest(intent_path.read_bytes()),
        "private_failure_sha256": protocol.digest(failure_path.read_bytes()),
        "private_gui_trace_sha256": protocol.digest(trace_path.read_bytes()),
        "private_visual_review_sha256": protocol.digest(review_path.read_bytes()),
        "price_action_intent_sha256":
            protocol.digest(resample_intent_path.read_bytes()),
        "terminal_stage": "positive_gui", "terminal_error_code": "stale_frame",
        "completed_gui_actions": 8,
        "source_pdf_link_and_viewer_close_dispatches_checked": 2,
        "original_rfq_return_confirmed": True,
        "first_price_cell_click_dispatched": True,
        "price_double_click_first_observation_pre_intent_rejected": True,
        "price_double_click_resample_intent_durable": True,
        "price_double_click_result_recorded": False,
        "price_route_guard_samples_recorded": 0,
        "generic_parse_exact_return_recorded": True,
        "generic_dispatch_material_rejection_recorded": True,
        "two_raster_states_only": True,
        "raster_alternate_changed_pixel_count": 4,
        "raster_alternate_bbox_xyxy": [16, 861, 18, 864],
        "physical_guard_pngs_checked": 32,
        "source_pdf_viewed_in_original_odoo_gui": True,
        "positive_or_negative_saved_repair_exists": False,
        "full_pre_and_post_cold_reset_exact": True,
        "full_post_filestore_manifest_exact": True,
        "worker_lease_released": True,
        "worker_services_cold_after_attempt": True,
        "selection_or_hidden_values_read": False,
        "model_attempts": 0, "train_controls_qualified": 0,
        "official_final_tasks_admitted": 0,
        "same_run_id_replay_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--accepted-audit", type=Path, required=True)
    parser.add_argument("--private-freeze", type=Path, required=True)
    parser.add_argument("--public-freeze", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(worker_dir=args.worker_dir,
                   accepted_audit_path=args.accepted_audit,
                   private_freeze_path=args.private_freeze,
                   public_freeze_path=args.public_freeze)
    protocol.write_new(args.public_out, result, private=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
