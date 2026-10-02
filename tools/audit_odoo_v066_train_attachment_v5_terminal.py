"""Read-only independent audit of the terminal v5 train PDF-viewer attempt."""

from __future__ import annotations

import argparse
from hashlib import sha1
import json
from pathlib import Path

from enterprise_fallback.odoo18.partition_factory import source_asset
from tools import audit_odoo_v066_train_attachment_calibration_v5 as prior
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v5 as run


SCHEMA = "envloop-odoo-train-attachment-v5-terminal-audit-v1"
VISUAL_SCHEMA = "envloop-odoo-train-attachment-v5-terminal-visual-review-v1"


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
        failure.get("stage") == "source_gui" and
        failure.get("error_type") == "ContractError" and
        failure.get("error_code") == "stale_frame" and
        failure.get("run_nonce_sha256") == nonce_sha and
        failure.get("reset_exact") is True and
        failure.get("services_restored") is True and
        failure.get("model_attempts") == 0 and
        failure.get("official_final_tasks_admitted") == 0 and
        not (out / "attempt.private.json").exists(),
        "terminal_v5_identity_or_outcome_invalid")
    readiness = prior._json(out / "db_readiness.json")
    prior.require(
        readiness.get("status") == "postgres_health_and_select_1_ready" and
        readiness.get("query") == "SELECT 1" and
        type(readiness.get("probe_count")) is int and
        1 <= readiness["probe_count"] <= run.READINESS_MAX_PROBES and
        readiness.get("observations", [])[-1].get("psql_exit_code") == 0,
        "terminal_v5_db_readiness_invalid")
    baseline = prior._json(private / "baseline_snapshot.json")
    frozen_files = prior._json(private / "baseline-filestore-manifest.json")
    for name in ("pre_restore", "post_restore"):
        reset = prior._json(out / f"{name}.json")
        prior.require(
            reset.get("status") == "restored" and
            reset.get("business_snapshot_equal") is True and
            reset.get("physical_filestore_equal_before_web_restart") is True and
            reset.get("db_sha256") == freeze["checkpoint"]["db_sha256"] and
            reset.get("filestore_sha256") ==
                freeze["checkpoint"]["filestore_sha256"],
            "terminal_v5_cold_reset_invalid")
    prior.require(
        prior._json(out / "baseline_sql.json") == baseline and
        prior._json(out / "restored_sql.json") == baseline and
        prior._json(out / "restored_filestore.json") == frozen_files and
        not any((out / name).exists() for name in
                ("positive_sql.json", "negative_sql.json",
                 "positive_reload_frame.png", "negative_reload_frame.png")),
        "terminal_v5_full_state_or_phase_boundary_invalid")
    world = prior._json(private / "partition_cases.json")
    source = source_asset(case, world)
    checksum = sha1(source).hexdigest()
    attachment = [row for row in baseline["attachments"]
                  if row.get("name") == f"{case['id']}-source.pdf"]
    prior.require(
        len(attachment) == 1 and
        attachment[0].get("checksum") == checksum and
        attachment[0].get("file_size") == len(source) and
        frozen_files.get("filestore/bench/" + checksum[:2] + "/" +
                         checksum) == protocol.digest(source) and
        protocol.digest(source) == freeze["source_asset_sha256"],
        "terminal_v5_source_pdf_not_physically_bound")
    trace_path = out / "gui_trace.json"
    trace = prior._json(trace_path)
    actions, samples = trace.get("actions"), trace.get("guard_samples")
    prior.require(
        trace.get("task_binding_sha256") == freeze["task_package_sha256"] and
        trace.get("sft_examples_written") == 0 and
        trace.get("pre_intent_rejections") == [] and
        type(actions) is list and len(actions) == 6 and
        type(samples) is list and len(samples) == 20,
        "terminal_v5_gui_trace_invalid")
    frames: dict[int, bytes] = {}
    intents: dict[int, dict] = {}
    for step in range(7):
        path = out / "frames" / f"step-{step:03d}.png"
        ref = {"path": f"frames/step-{step:03d}.png",
               "sha256": protocol.digest(path.read_bytes())}
        _path, frames[step] = prior._ref(out, ref, image=True)
        intent_path = out / "actions" / f"step-{step:03d}-intent.private.json"
        action_intent = prior._json(intent_path)
        intents[step] = action_intent
        prior.require(
            action_intent.get("step") == step and
            action_intent.get("phase") == "positive" and
            action_intent.get("task_id") == case["id"] and
            action_intent.get("task_binding_sha256") ==
                freeze["task_package_sha256"] and
            action_intent.get("frame_sha256") == ref["sha256"],
            "terminal_v5_action_intent_changed")
        result_path = out / "actions" / f"step-{step:03d}-result.private.json"
        if step < 6:
            result = prior._json(result_path)
            action = actions[step]
            prior.require(
                action.get("step") == step and
                action.get("phase") == "positive" and
                action.get("frame") == ref and
                result.get("intent_sha256") ==
                    protocol.digest(intent_path.read_bytes()) and
                result.get("applied_action") ==
                    action_intent.get("normalized_action") and
                result.get("contract_receipt") ==
                    action.get("contract_receipt") and
                action.get("contract_receipt", {}).get("error_code") is None,
                "terminal_v5_completed_action_changed")
        else:
            prior.require(
                not result_path.exists() and
                action_intent.get("normalized_action", {}).get("type") ==
                    "click" and
                action_intent.get("normalized_action", {}).get("target") ==
                    {"x": 1413, "y": 23} and
                action_intent.get("observed_target_control") is None and
                action_intent.get("observed_url", "").endswith(
                    "/odoo/purchase/1"),
                "terminal_v5_failed_viewer_close_boundary_changed")
    # Exact source-link route guard, including both final physical frames.
    _refs, link_count = prior._guard(
        out, actions[4], intents[4],
        prior._json(out / "actions/step-004-result.private.json"),
        f"{case['id']}-source.pdf", samples)
    prior.require(
        link_count == 1 and
        intents[3].get("observed_target_control", {}).get("label") ==
            "Attach files" and
        intents[4].get("observed_target_control", {}).get("label") ==
            f"{case['id']}-source.pdf" and
        intents[5].get("normalized_action", {}).get("type") == "wait" and
        frames[5] == frames[6],
        "terminal_v5_source_route_or_stable_viewer_invalid")
    for step in (0, 1, 2, 5, 6):
        pair = [sample for sample in samples if sample.get("step") == step]
        prior.require(
            len(pair) == 2 and
            [sample.get("stage") for sample in pair] ==
                ["parse", "dispatch"] and
            all(sample.get("sample") == 0 and
                sample.get("classification") == "exact_return"
                for sample in pair),
            "terminal_v5_guard_sequence_changed")
        for sample in pair:
            _path, guard = prior._ref(
                out, sample["sampled_frame_ref"], image=True)
            prior.require(guard == frames[step],
                          "terminal_v5_guard_frame_changed")
    attach_samples = [sample for sample in samples if sample.get("step") == 3]
    prior.require(
        len(attach_samples) == 4 and
        [sample.get("stage") for sample in attach_samples] ==
            ["parse", "dispatch", "dispatch_final", "dispatch_final"] and
        [sample.get("classification") for sample in attach_samples] ==
            ["exact_return", "exact_return",
             "two_frame_candidate_observed", "two_frame_observed_confirmed"],
        "terminal_v5_attach_button_v6_guard_changed")
    for sample in attach_samples:
        _path, guard = prior._ref(
            out, sample["sampled_frame_ref"], image=True)
        prior.require(guard == frames[3],
                      "terminal_v5_attach_button_frame_changed")
    observed_guards = {str(prior._ref(
        out, sample["sampled_frame_ref"], image=True)[0])
        for sample in samples}
    disk_guards = {str(path) for path in
                   (out / "frames").glob("guard-*.png")}
    prior.require(
        observed_guards == disk_guards and
        {path.name for path in (out / "frames").glob("*.png")} ==
            {f"step-{step:03d}.png" for step in range(7)} |
            {f"guard-{index:04d}.png" for index in range(20)},
        "terminal_v5_physical_frame_set_changed")
    review_path = out / "independent_visual_review.private.json"
    review = prior._json(review_path)
    prior.require(
        review.get("schema") == VISUAL_SCHEMA and
        review.get("decision") ==
            "source_pdf_visible_in_original_odoo_viewer" and
        review.get("reviewer_role") ==
            "independent_visual_source_reviewer" and
        review.get("source_frame_sha256") ==
            protocol.digest(frames[5]) and
        review.get("failed_close_frame_sha256") ==
            protocol.digest(frames[6]) and
        review.get("source_asset_sha256") ==
            freeze["source_asset_sha256"] and
        review.get("source_pdf_pages_visually_reviewed") == 1 and
        review.get("visible_heading_and_three_line_table_match_source") is True and
        review.get("source_values_published") is False,
        "terminal_v5_independent_visual_review_missing")
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
                  "terminal_v5_lease_or_service_cleanup_invalid")
    prior.require(
        type(review.get("reviewer_id_sha256")) is str and
        prior.HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
        prior._time(review.get("reviewed_at_utc")) >=
            prior._time(pairs[0][1]["at_utc"]),
        "terminal_v5_visual_review_not_independent_and_post_run")
    return {
        "schema": SCHEMA,
        "status": "train_only_source_viewed_terminal_before_saved_repair",
        "public_freeze_sha256":
            protocol.digest(Path(public_freeze_path).read_bytes()),
        "private_freeze_sha256":
            protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_intent_sha256": protocol.digest(intent_path.read_bytes()),
        "private_failure_sha256": protocol.digest(failure_path.read_bytes()),
        "private_gui_trace_sha256": protocol.digest(trace_path.read_bytes()),
        "private_visual_review_sha256": protocol.digest(review_path.read_bytes()),
        "failed_close_intent_sha256": protocol.digest(
            (out / "actions/step-006-intent.private.json").read_bytes()),
        "terminal_stage": "source_gui",
        "terminal_error_code": "stale_frame",
        "completed_gui_actions": 6,
        "failed_close_intents_without_dispatch_result": 1,
        "native_source_link_dispatches_checked": 1,
        "physical_guard_pngs_checked": 20,
        "source_pdf_physically_bound_at_baseline": True,
        "source_pdf_viewed_in_original_odoo_gui": True,
        "viewer_observed_and_failed_close_frames_byte_equal": True,
        "failed_close_guard_frames_exact_return": True,
        "positive_or_negative_saved_repair_exists": False,
        "full_pre_and_post_cold_reset_exact": True,
        "full_post_filestore_manifest_exact": True,
        "worker_lease_released": True,
        "worker_services_cold_after_attempt": True,
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
