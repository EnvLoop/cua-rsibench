"""Read-only independent audit of the terminal v6 train price-edit attempt."""

from __future__ import annotations

import argparse
from hashlib import sha1
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageChops

from enterprise_fallback.odoo18.partition_factory import source_asset
from tools import audit_odoo_v066_train_attachment_calibration_v6 as prior
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v6 as run


SCHEMA = "envloop-odoo-train-attachment-v6-terminal-audit-v1"
VISUAL_SCHEMA = "envloop-odoo-train-attachment-v6-terminal-visual-review-v1"
ALTERNATE_POINTS = {(16, 861), (17, 861), (16, 863), (17, 863)}
ALTERNATE_RGB_PAIRS = {
    frozenset(((226, 230, 234), (226, 229, 234))),
    frozenset(((249, 250, 250), (250, 250, 251))),
    frozenset(((246, 247, 248), (246, 247, 249))),
    frozenset(((229, 233, 236), (230, 233, 236))),
}


def _pixel_changes(a: bytes, b: bytes) -> tuple[tuple[int, int, int, int], dict]:
    with Image.open(BytesIO(a)) as image_a, Image.open(BytesIO(b)) as image_b:
        if (image_a.format != "PNG" or image_b.format != "PNG" or
                image_a.size != image_b.size or
                image_a.size != (1440, 1000)):
            raise prior.CalibrationAuditError("terminal_v6_png_geometry_invalid")
        first, second = image_a.convert("RGB"), image_b.convert("RGB")
    bbox = ImageChops.difference(first, second).getbbox()
    prior.require(bbox is not None, "terminal_v6_alternate_not_distinct")
    changes = {}
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            aa, bb = first.getpixel((x, y)), second.getpixel((x, y))
            if aa != bb:
                changes[(x, y)] = frozenset((aa, bb))
    return bbox, changes


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
        "terminal_v6_identity_or_outcome_invalid")
    readiness = prior._json(out / "db_readiness.json")
    prior.require(readiness.get("status") ==
                  "postgres_health_and_select_1_ready" and
                  readiness.get("query") == "SELECT 1" and
                  readiness.get("observations", [])[-1].get("psql_exit_code") == 0,
                  "terminal_v6_db_readiness_invalid")
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
                      "terminal_v6_cold_reset_invalid")
    prior.require(
        prior._json(out / "baseline_sql.json") == baseline and
        prior._json(out / "restored_sql.json") == baseline and
        prior._json(out / "restored_filestore.json") == frozen_files and
        not any((out / name).exists() for name in
                ("positive_sql.json", "negative_sql.json",
                 "positive_reload_frame.png", "negative_reload_frame.png")),
        "terminal_v6_full_state_or_phase_boundary_invalid")
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
        "terminal_v6_source_pdf_not_physically_bound")
    trace_path = out / "gui_trace.json"
    trace = prior._json(trace_path)
    actions = trace.get("actions")
    samples = trace.get("guard_samples")
    rejected_refs = trace.get("pre_intent_rejections")
    prior.require(
        trace.get("task_binding_sha256") == freeze["task_package_sha256"] and
        trace.get("sft_examples_written") == 0 and
        type(actions) is list and len(actions) == 8 and
        type(samples) is list and len(samples) == 32 and
        type(rejected_refs) is list and len(rejected_refs) == 3,
        "terminal_v6_gui_trace_invalid")
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
            "terminal_v6_completed_action_changed")
        _refs, count = prior._guard(
            out, action, action_intent, action_result,
            f"{case['id']}-source.pdf", samples)
        link_count += count
        _refs, count = prior._viewer_guard(
            out, action, action_intent, action_result,
            f"{case['id']}-source.pdf", samples)
        viewer_count += count
    price_target = intents[7].get("observed_target_control")
    prior.require(
        link_count == viewer_count == 1 and
        actions[6]["contract_receipt"].get("viewer_return_guard", {}).get(
            "classification") == "original_rfq_return_confirmed" and
        intents[7].get("normalized_action", {}).get("type") == "click" and
        type(price_target) is dict and
        price_target.get("role") == "td" and
        price_target.get("purchase_rfq_view") is True and
        actions[7]["contract_receipt"].get(
            "physical_dispatch_guard", {}).get("classification") ==
            "two_frame_observed_confirmed",
        "terminal_v6_viewer_return_or_price_click_invalid")
    for sample in samples:
        prior._ref(out, sample["sampled_frame_ref"], image=True)
    disk_guards = {str(path) for path in (out / "frames").glob("guard-*.png")}
    sample_guards = {str(prior._ref(
        out, sample["sampled_frame_ref"], image=True)[0]) for sample in samples}
    prior.require(sample_guards == disk_guards and len(disk_guards) == 32,
                  "terminal_v6_guard_png_set_changed")
    prior.require(
        not any((out / "actions" / f"step-008-{suffix}").exists()
                for suffix in ("intent.private.json", "result.private.json")),
        "terminal_v6_price_double_click_dispatched")
    expected_rejection_names = (
        "step-008-rejection.private.json",
        "step-008-resample-01-rejection.private.json",
        "step-008-resample-02-rejection.private.json",
    )
    observed_hashes = set()
    current_hashes = set()
    assistant_hashes = set()
    frame_ids = set()
    target = None
    for index, name in enumerate(expected_rejection_names):
        ref = rejected_refs[index]
        prior.require(ref.get("path") == "actions/" + name,
                      "terminal_v6_rejection_order_changed")
        rejection = prior._artifact(out, ref)
        prior.require(
            rejection.get("schema") ==
                "envloop-odoo-v066-pre-intent-frame-rejection-v1" and
            rejection.get("step") == 8 and
            rejection.get("phase") == "positive" and
            rejection.get("error_code") == "stale_frame" and
            rejection.get("observation_attempt") == index and
            rejection.get("pre_dispatch_intent_created") is False and
            rejection.get("gui_action_dispatched") is False,
            "terminal_v6_rejection_not_pre_intent")
        assistant = prior._artifact(out, rejection["assistant_action_ref"])
        prior.require(assistant.get("type") == "double_click" and
                      type(assistant.get("target")) is dict and
                      set(assistant["target"]) == {"x", "y"},
                      "terminal_v6_rejected_action_changed")
        if target is None:
            target = assistant["target"]
        prior.require(assistant["target"] == target,
                      "terminal_v6_resample_action_changed")
        assistant_hashes.add(rejection["assistant_action_ref"]["sha256"])
        frame_ids.add(rejection["frame_id_sha256"])
        observed = prior._ref(out, rejection["observed_frame_ref"], image=True)[1]
        current = prior._ref(out, rejection["current_frame_ref"], image=True)[1]
        observed_hashes.add(protocol.digest(observed))
        current_hashes.add(protocol.digest(current))
        bbox, changes = _pixel_changes(observed, current)
        prior.require(
            bbox == (16, 861, 18, 864) and
            set(changes) == ALTERNATE_POINTS and
            set(changes.values()) == ALTERNATE_RGB_PAIRS and
            not (bbox[0] <= target["x"] < bbox[2] and
                 bbox[1] <= target["y"] < bbox[3]),
            "terminal_v6_raster_alternate_not_exact_four_pixel_corner")
    prior.require(
        len(assistant_hashes) == 1 and len(frame_ids) == 3 and
        len(observed_hashes) == len(current_hashes) == 2 and
        observed_hashes == current_hashes and
        len({sample.get("step") for sample in samples if
             sample.get("stage") == "parse" and
             sample.get("step") == 8}) == 1 and
        len([sample for sample in samples if sample.get("step") == 8]) == 3 and
        all(sample.get("classification") ==
            "third_or_material_frame_rejected"
            for sample in samples if sample.get("step") == 8),
        "terminal_v6_two_state_pre_intent_rejections_changed")
    review_path = out / "independent_visual_review.private.json"
    review = prior._json(review_path)
    prior.require(
        review.get("schema") == VISUAL_SCHEMA and
        review.get("decision") ==
            "source_pdf_and_returned_rfq_visible_before_price_edit_rejection" and
        review.get("source_frame_sha256") ==
            protocol.digest(frames[5]) and
        review.get("post_close_rfq_frame_sha256") ==
            protocol.digest(frames[7]) and
        review.get("first_price_edit_observation_sha256") in
            observed_hashes and
        review.get("source_asset_sha256") ==
            freeze["source_asset_sha256"] and
        review.get("source_pdf_pages_visually_reviewed") == 1 and
        review.get("visible_heading_and_three_line_table_match_source") is True and
        review.get("native_rfq_visible_after_viewer_close") is True and
        review.get("selected_price_cell_visible_before_rejected_double_click") is True and
        review.get("source_values_published") is False,
        "terminal_v6_visual_review_missing")
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
                  "terminal_v6_lease_or_service_cleanup_invalid")
    prior.require(
        type(review.get("reviewer_id_sha256")) is str and
        prior.HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
        prior._time(review.get("reviewed_at_utc")) >=
            prior._time(pairs[0][1]["at_utc"]),
        "terminal_v6_visual_review_not_independent_and_post_run")
    return {
        "schema": SCHEMA,
        "status": "train_only_viewer_closed_price_edit_pre_intent_rejected",
        "public_freeze_sha256":
            protocol.digest(Path(public_freeze_path).read_bytes()),
        "private_freeze_sha256":
            protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_intent_sha256": protocol.digest(intent_path.read_bytes()),
        "private_failure_sha256": protocol.digest(failure_path.read_bytes()),
        "private_gui_trace_sha256": protocol.digest(trace_path.read_bytes()),
        "private_visual_review_sha256": protocol.digest(review_path.read_bytes()),
        "terminal_stage": "positive_gui", "terminal_error_code": "stale_frame",
        "completed_gui_actions": 8,
        "source_pdf_link_and_viewer_close_dispatches_checked": 2,
        "original_rfq_return_confirmed": True,
        "first_price_cell_click_dispatched": True,
        "price_double_click_intent_or_dispatch_created": False,
        "pre_intent_rejections_checked": 3,
        "two_raster_states_only": True,
        "raster_alternate_changed_pixel_count": 4,
        "raster_alternate_bbox_xyxy": [16, 861, 18, 864],
        "raster_alternate_far_from_action_target": True,
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
