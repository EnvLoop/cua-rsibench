"""Read-only audit of the terminal v9 TRAIN-only route nonclaim attempt."""

from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
from hashlib import sha1
import json
import os
from pathlib import Path
import stat

from enterprise_fallback.odoo18.partition_factory import source_asset
from tools import audit_odoo_v066_train_attachment_calibration_v9 as prior
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v9 as run


SCHEMA = "envloop-odoo-train-attachment-v9-terminal-audit-v1"
VISUAL_SCHEMA = "envloop-odoo-train-attachment-v9-terminal-visual-review-v1"


def _lease_free(path: Path) -> bool:
    prior.require(path.is_file() and not path.is_symlink() and
                  stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
                  "terminal_v9_worker_lock_unsafe")
    fd = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


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
        "terminal_v9_identity_or_outcome_invalid")
    readiness = prior._json(out / "db_readiness.json")
    prior.require(readiness.get("status") ==
                  "postgres_health_and_select_1_ready" and
                  readiness.get("query") == "SELECT 1" and
                  readiness.get("observations", [])[-1].get("psql_exit_code") == 0,
                  "terminal_v9_db_readiness_invalid")
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
                      "terminal_v9_cold_reset_invalid")
    prior.require(
        prior._json(out / "baseline_sql.json") == baseline and
        prior._json(out / "restored_sql.json") == baseline and
        prior._json(out / "restored_filestore.json") == frozen_files and
        not any((out / name).exists() for name in
                ("positive_sql.json", "negative_sql.json",
                 "positive_reload_frame.png", "negative_reload_frame.png")),
        "terminal_v9_full_state_or_phase_boundary_invalid")
    world = prior._json(private / "partition_cases.json")
    source = source_asset(case, world)
    checksum = sha1(source).hexdigest()
    attachment = [row for row in baseline["attachments"]
                  if row.get("name") == f"{case['id']}-source.pdf"]
    prior.require(len(attachment) == 1 and
                  attachment[0].get("checksum") == checksum and
                  attachment[0].get("file_size") == len(source) and
                  frozen_files.get("filestore/bench/" + checksum[:2] +
                                   "/" + checksum) == protocol.digest(source) and
                  protocol.digest(source) == freeze["source_asset_sha256"],
                  "terminal_v9_source_pdf_not_physically_bound")
    trace_path = out / "gui_trace.json"
    trace = prior._json(trace_path)
    actions, samples = trace.get("actions"), trace.get("guard_samples")
    rejection_refs = trace.get("pre_intent_rejections")
    prior.require(trace.get("task_binding_sha256") ==
                  freeze["task_package_sha256"] and
                  trace.get("sft_examples_written") == 0 and
                  type(actions) is list and len(actions) == 8 and
                  type(samples) is list and len(samples) == 29 and
                  type(rejection_refs) is list and len(rejection_refs) == 3,
                  "terminal_v9_gui_trace_invalid")
    frames = {}
    linked_routes: set[str] = set()
    link_count = viewer_count = 0
    for step in range(8):
        frame_path = out / "frames" / f"step-{step:03d}.png"
        frame_ref = {"path": f"frames/step-{step:03d}.png",
                     "sha256": protocol.digest(frame_path.read_bytes())}
        _path, frames[step] = prior._ref(out, frame_ref, image=True)
        action_intent_path = out / "actions" / f"step-{step:03d}-intent.private.json"
        action_intent = prior._json(action_intent_path)
        action_result = prior._json(
            out / "actions" / f"step-{step:03d}-result.private.json")
        action = actions[step]
        prior.require(action_intent.get("schema") ==
                          "envloop-odoo-v066-route-action-intent-v1" and
                      action_result.get("schema") ==
                          "envloop-odoo-v066-route-dispatch-result-v1" and
                      action_intent.get("step") ==
                          action.get("step") == step and
                      action_intent.get("phase") ==
                          action.get("phase") == "positive" and
                      action_intent.get("task_id") == case["id"] and
                      action_intent.get("task_binding_sha256") ==
                          freeze["task_package_sha256"] and
                      action_intent.get("frame_sha256") == frame_ref["sha256"] and
                      action.get("frame") == frame_ref and
                      action_result.get("intent_sha256") ==
                          protocol.digest(action_intent_path.read_bytes()) and
                      action_result.get("applied_action") ==
                          action_intent.get("normalized_action") and
                      action_result.get("contract_receipt") ==
                          action.get("contract_receipt") and
                      action.get("contract_receipt", {}).get("error_code") is None,
                      "terminal_v9_completed_action_changed")
        route_kind, route_refs = prior._route_binding(
            out, action, action_intent, action_result)
        linked_routes.update(route_refs)
        prior.require(route_kind == action.get("route_kind") and
                      route_kind != "price_editor",
                      "terminal_v9_price_route_dispatched")
        _refs, count = prior._guard(
            out, action, action_intent, action_result,
            f"{case['id']}-source.pdf", samples)
        link_count += count
        _refs, count = prior._viewer_guard(
            out, action, action_intent, action_result,
            f"{case['id']}-source.pdf", samples)
        viewer_count += count
    prior.require(link_count == viewer_count == 1 and
                  actions[6]["contract_receipt"].get(
                      "viewer_return_guard", {}).get("classification") ==
                      "original_rfq_return_confirmed" and
                  actions[7]["contract_receipt"].get(
                      "physical_dispatch_guard", {}).get("classification") ==
                      "two_frame_observed_confirmed",
                  "terminal_v9_source_or_rfq_return_invalid")
    guard_paths = set()
    for sample in samples:
        path, _png = prior._ref(out, sample["sampled_frame_ref"], image=True)
        guard_paths.add(str(path))
    disk_guards = {str(path) for path in (out / "frames").glob("guard-*.png")}
    prior.require(len(guard_paths) == 29 and guard_paths == disk_guards and
                  all(sample.get("step") < 8 for sample in samples),
                  "terminal_v9_guard_png_set_or_boundary_invalid")
    observed_sha = None
    frame_id_hashes = set()
    assistant_sha = None
    price_target = None
    for index, rejection_ref in enumerate(rejection_refs):
        expected = ("step-008-rejection.private.json" if index == 0 else
                    f"step-008-resample-{index:02d}-rejection.private.json")
        prior.require(rejection_ref.get("path") == "actions/" + expected,
                      "terminal_v9_rejection_order_invalid")
        rejection = prior._artifact(out, rejection_ref)
        probe_ref = rejection.get("route_probe_ref")
        decision_ref = rejection.get("route_decision_ref")
        prior.require(type(probe_ref) is dict and type(decision_ref) is dict and
                      rejection.get("schema") ==
                          "envloop-odoo-v066-route-pre-intent-rejection-v1" and
                      rejection.get("phase") == "positive" and
                      rejection.get("step") == 8 and
                      rejection.get("observation_attempt") == index and
                      rejection.get("error_code") == "stale_frame" and
                      rejection.get("pre_dispatch_intent_created") is False and
                      rejection.get("gui_action_dispatched") is False,
                      "terminal_v9_rejection_not_pre_intent")
        probe = prior._artifact(out, probe_ref)
        decision = prior._artifact(out, decision_ref)
        linked_routes.update((str(out / probe_ref["path"]),
                              str(out / decision_ref["path"])))
        assistant = prior._artifact(out, rejection["assistant_action_ref"])
        if assistant_sha is None:
            assistant_sha = rejection["assistant_action_ref"]["sha256"]
            price_target = assistant.get("target")
        prior.require(assistant.get("type") == "double_click" and
                      rejection["assistant_action_ref"]["sha256"] ==
                          assistant_sha and
                      assistant.get("target") == price_target and
                      type(price_target) is dict and
                      set(price_target) == {"x", "y"},
                      "terminal_v9_rejected_action_changed")
        observed = prior._ref(out, rejection["observed_frame_ref"], image=True)[1]
        current = prior._ref(out, rejection["current_frame_ref"], image=True)[1]
        frame_sha = protocol.digest(observed)
        if observed_sha is None:
            observed_sha = frame_sha
        frame_id_hashes.add(rejection["frame_id_sha256"])
        prior.require(observed == current and frame_sha == observed_sha and
                      probe.get("schema") ==
                          "envloop-odoo-train-price-route-probe-v1" and
                      probe.get("status") == "nonclaim" and
                      probe.get("reason_code") == "sku_row_not_unique" and
                      probe.get("visible_price_input_count") == 1 and
                      probe.get("strict_price_identity_present") is False and
                      probe.get("step") == 8 and
                      probe.get("observation_serial") == 9 + index and
                      probe.get("price_phase") == "positive" and
                      probe.get("task_binding_sha256") ==
                          freeze["task_package_sha256"] and
                      probe.get("frame_sha256") == frame_sha and
                      probe.get("frame_id_sha256") ==
                          rejection["frame_id_sha256"] and
                      decision.get("schema") ==
                          "envloop-odoo-train-action-route-decision-v1" and
                      decision.get("status") == "nonclaim" and
                      decision.get("reason_code") ==
                          "sku_row_not_unique" and
                      decision.get("route_kind") == "price_editor" and
                      decision.get("route_token") is None and
                      decision.get("route_token_sha256") is None and
                      decision.get("probe_ref") == probe_ref and
                      decision.get("frame_sha256") == frame_sha and
                      decision.get("frame_id_sha256") ==
                          rejection["frame_id_sha256"],
                      "terminal_v9_probe_decision_or_frame_changed")
        prefix = Path(rejection_ref["path"]).name.replace(
            "-rejection.private.json", "")
        prior.require(not (out / "actions" /
                           (prefix + "-intent.private.json")).exists() and
                      not (out / "actions" /
                           (prefix + "-result.private.json")).exists(),
                      "terminal_v9_rejected_action_has_intent_or_result")
    prior.require(len(frame_id_hashes) == 3 and
                  observed_sha == protocol.digest(
                      prior._ref(out, {
                          "path": "frames/step-008.png",
                          "sha256": observed_sha}, image=True)[1]),
                  "terminal_v9_fresh_frames_or_price_frame_changed")
    route_disk = {str(path) for path in (out / "routes").glob("*.json")}
    prior.require(len(route_disk) == 22 and route_disk == linked_routes,
                  "terminal_v9_route_file_set_changed")
    visual_path = out / "independent_visual_review.private.json"
    review = prior._json(visual_path)
    prior.require(review.get("schema") == VISUAL_SCHEMA and
                  review.get("decision") ==
                      "source_pdf_and_returned_rfq_visible_before_price_nonclaim" and
                  review.get("source_frame_sha256") ==
                      protocol.digest(frames[5]) and
                  review.get("post_close_rfq_frame_sha256") ==
                      protocol.digest(frames[7]) and
                  review.get("price_editor_observation_sha256") ==
                      observed_sha and
                  review.get("source_asset_sha256") ==
                      freeze["source_asset_sha256"] and
                  review.get("source_pdf_pages_visually_reviewed") == 1 and
                  review.get("visible_heading_and_three_line_table_match_source") is True and
                  review.get("native_rfq_visible_after_viewer_close") is True and
                  review.get("selected_price_cell_visible_before_pre_intent_rejection") is True and
                  review.get("source_values_published") is False,
                  "terminal_v9_visual_review_missing")
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
    prior.require(len(pairs) == 1 and _lease_free(private / "worker-operation.lock"),
                  "terminal_v9_lease_not_released")
    prior.require(type(review.get("reviewer_id_sha256")) is str and
                  prior.HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
                  prior._time(review.get("reviewed_at_utc")) >=
                      prior._time(pairs[0][1]["at_utc"]),
                  "terminal_v9_visual_review_not_post_run")
    return {
        "schema": SCHEMA,
        "status": "train_only_price_route_reason_coded_pre_intent_terminal",
        "public_freeze_sha256":
            protocol.digest(Path(public_freeze_path).read_bytes()),
        "private_freeze_sha256":
            protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_intent_sha256": protocol.digest(intent_path.read_bytes()),
        "private_failure_sha256": protocol.digest(failure_path.read_bytes()),
        "private_gui_trace_sha256": protocol.digest(trace_path.read_bytes()),
        "private_visual_review_sha256": protocol.digest(visual_path.read_bytes()),
        "terminal_stage": "positive_gui",
        "terminal_error_code": "stale_frame",
        "completed_gui_actions": 8,
        "source_pdf_link_and_viewer_close_dispatches_checked": 2,
        "durable_route_claims_checked": 8,
        "pre_intent_price_nonclaims_checked": 3,
        "all_price_observed_and_current_frames_byte_equal": True,
        "reason_code": "sku_row_not_unique",
        "visible_price_input_count_each_probe": 1,
        "price_double_click_intent_or_dispatch_created": False,
        "physical_guard_pngs_checked": 29,
        "source_pdf_viewed_in_original_odoo_gui": True,
        "positive_or_negative_saved_repair_exists": False,
        "full_pre_and_post_cold_reset_exact": True,
        "full_post_filestore_manifest_exact": True,
        "service_state_restored_by_runner_receipt": True,
        "docker_services_cold_independently_verified": False,
        "worker_lease_released_and_available_at_audit": True,
        "selection_or_hidden_values_read": False,
        "model_attempts": 0,
        "train_controls_qualified": 0,
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
