"""Read-only reconciliation of the failed v10 TRAIN negative price route.

The original run remains terminal. A separate visual review is required; this
auditor does not call Docker, start software, retry an action, or admit a task.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha1
import json
import os
from pathlib import Path

from enterprise_fallback.odoo18.partition_factory import source_asset
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v5 import (
    _decorative_corner_alternate,
)
from tools import audit_odoo_v066_train_attachment_calibration_v10 as prior
from tools import odoo_v066_train_attachment_calibration_v10 as run
from tools import odoo_v066_scale_protocol_v1 as protocol

SCHEMA = "envloop-odoo-train-attachment-v10-terminal-audit-v1"
VISUAL_SCHEMA = "envloop-odoo-train-attachment-v10-terminal-visual-review-v1"


def _lease_free(path: Path) -> bool:
    prior._private(path)
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


def _negative_rejections(out: Path, rejections: list[dict], samples: list[dict],
                         binding: str) -> tuple[set[str], set[str]]:
    """Derive the cause from linked raw PNGs, not the runner's error label."""
    prior.require(len(rejections) == 3, "terminal_v10_negative_rejections_missing")
    route_paths, ids = set(), set()
    pair: set[str] = set()
    for index, ref in enumerate(rejections):
        prefix = "step-016" + (f"-resample-{index:02d}" if index else "")
        prior.require(ref.get("path") == f"actions/{prefix}-rejection.private.json",
                      "terminal_v10_negative_rejection_order_invalid")
        rejection = prior._artifact(out, ref)
        prior.require(rejection.get("schema") ==
                          "envloop-odoo-v066-route-pre-intent-rejection-v1" and
                      rejection.get("phase") == "negative" and
                      rejection.get("step") == 16 and
                      rejection.get("observation_attempt") == index and
                      rejection.get("error_code") == "stale_frame" and
                      rejection.get("pre_dispatch_intent_created") is False and
                      rejection.get("gui_action_dispatched") is False,
                      "terminal_v10_negative_rejection_boundary_invalid")
        assistant = prior._artifact(out, rejection["assistant_action_ref"])
        prior.require(assistant.get("type") == "double_click" and
                      type(assistant.get("target")) is dict and
                      set(assistant["target"]) == {"x", "y"},
                      "terminal_v10_negative_action_invalid")
        observed = prior._ref(out, rejection["observed_frame_ref"], image=True)[1]
        current = prior._ref(out, rejection["current_frame_ref"], image=True)[1]
        prior.require(observed != current and
                      _decorative_corner_alternate(observed, current),
                      "terminal_v10_material_or_unproven_frame_difference")
        pair.update((protocol.digest(observed), protocol.digest(current)))
        ids.add(rejection["frame_id_sha256"])
        probe_ref, decision_ref = rejection["route_probe_ref"], rejection["route_decision_ref"]
        probe, decision = prior._artifact(out, probe_ref), prior._artifact(out, decision_ref)
        prior.require(probe.get("schema") == "envloop-odoo-train-price-route-probe-v2" and
                      probe.get("status") == probe.get("reason_code") == "ready" and
                      probe.get("visible_price_input_count") == 1 and
                      probe.get("strict_price_identity_present") is True and
                      probe.get("price_phase") == "negative" and
                      probe.get("step") == 16 and
                      probe.get("observation_serial") == 18 + index and
                      probe.get("task_binding_sha256") == binding and
                      probe.get("frame_sha256") == protocol.digest(observed) and
                      probe.get("frame_id_sha256") == rejection["frame_id_sha256"] and
                      decision.get("schema") == "envloop-odoo-train-action-route-decision-v1" and
                      decision.get("status") == "nonclaim" and
                      decision.get("reason_code") == "physical_or_identity_guard_rejected" and
                      decision.get("route_kind") == "price_editor" and
                      decision.get("route_token") is None and
                      decision.get("route_token_sha256") is None and
                      decision.get("probe_ref") == probe_ref and
                      decision.get("frame_sha256") == probe["frame_sha256"] and
                      decision.get("frame_id_sha256") == probe["frame_id_sha256"],
                      "terminal_v10_negative_probe_or_decision_invalid")
        route_paths.update(str(out / item["path"]) for item in (probe_ref, decision_ref))
        prior.require(not (out / "actions" / f"{prefix}-intent.private.json").exists() and
                      not (out / "actions" / f"{prefix}-result.private.json").exists(),
                      "terminal_v10_rejected_action_has_intent_or_result")
    neg = [row for row in samples if row.get("step") == 16]
    prior.require(len(neg) == 6 and len(pair) == 2 and len(ids) == 3,
                  "terminal_v10_negative_sample_count_invalid")
    for index in range(3):
        base, final = neg[2 * index:2 * index + 2]
        prior.require(base.get("stage") == "parse" and base.get("sample") == 0 and
                      base.get("classification") == "one_observed" and
                      final.get("stage") == "parse_price_final" and
                      final.get("sample") == 1 and
                      final.get("classification") == "unstable_first_final_rejected" and
                      base.get("observed_frame_sha256") == final.get("observed_frame_sha256") and
                      base.get("observed_frame_id_sha256") == final.get("observed_frame_id_sha256"),
                      "terminal_v10_negative_sample_sequence_invalid")
        raw = prior._ref(out, base["sampled_frame_ref"], image=True)[1]
        other = prior._ref(out, final["sampled_frame_ref"], image=True)[1]
        prior.require(protocol.digest(raw) == base["observed_frame_sha256"] and
                      protocol.digest(raw) in pair and protocol.digest(other) in pair and
                      _decorative_corner_alternate(raw, other),
                      "terminal_v10_negative_physical_frames_not_bound")
    return route_paths, pair


def audit(*, worker_dir: Path, accepted_audit_path: Path,
          private_freeze_path: Path, public_freeze_path: Path,
          review_path: Path) -> dict:
    worker, private, freeze, case, wrong = run._verify_freeze(
        worker_dir, accepted_audit_path, private_freeze_path, public_freeze_path)
    out = private / "v066_attachment_route_calibration" / run.RUN_NAME
    prior._private(out, directory=True)
    intent, failure = prior._json(out / "intent.private.json"), prior._json(out / "failure.private.json")
    nonce = protocol.digest(freeze["run_nonce"].encode())
    prior.require(intent.get("schema") == run.SCHEMA and
                  intent.get("status") == "durable_before_first_docker_or_gui_action" and
                  intent.get("split") == "train" and intent.get("family") == "purchase" and
                  intent.get("task_package_sha256") == freeze["task_package_sha256"] and
                  intent.get("private_freeze_sha256") == protocol.digest(Path(private_freeze_path).read_bytes()) and
                  intent.get("public_freeze_sha256") == protocol.digest(Path(public_freeze_path).read_bytes()) and
                  intent.get("run_nonce_sha256") == failure.get("run_nonce_sha256") == nonce and
                  failure.get("schema") == run.RECEIPT_SCHEMA and
                  failure.get("status") == "terminal_failure_no_automatic_replay" and
                  failure.get("stage") == "negative_gui" and
                  failure.get("error_type") == "ContractError" and failure.get("error_code") == "stale_frame" and
                  failure.get("reset_exact") is True and failure.get("services_restored") is True and
                  all(row.get("model_attempts") == row.get("official_final_tasks_admitted") == 0
                      for row in (intent, failure)) and
                  intent.get("selection_or_hidden_dispatch_authorized") is False and
                  not (out / "attempt.private.json").exists() and
                  not any((out / name).exists() for name in
                          ("negative_sql.json", "negative_filestore.json", "negative_store_paths.json",
                           "negative_reload_frame.png")),
                  "terminal_v10_identity_or_outcome_invalid")
    readiness = prior._json(out / "db_readiness.json")
    prior.require(readiness.get("status") == "postgres_health_and_select_1_ready" and
                  readiness.get("query") == "SELECT 1" and
                  readiness.get("observations", [])[-1].get("psql_exit_code") == 0,
                  "terminal_v10_readiness_invalid")
    baseline, frozen = prior._json(private / "baseline_snapshot.json"), prior._json(private / "baseline-filestore-manifest.json")
    for stage in ("pre_restore", "post_restore"):
        reset = prior._json(out / f"{stage}.json")
        prior.require(reset.get("status") == "restored" and
                      reset.get("business_snapshot_equal") is True and
                      reset.get("physical_filestore_equal_before_web_restart") is True and
                      reset.get("db_sha256") == freeze["checkpoint"]["db_sha256"] and
                      reset.get("filestore_sha256") == freeze["checkpoint"]["filestore_sha256"],
                      "terminal_v10_full_cold_reset_invalid")
    prior.require(prior._json(out / "baseline_sql.json") == baseline and
                  prior._json(out / "restored_sql.json") == baseline and
                  prior._json(out / "restored_filestore.json") == frozen,
                  "terminal_v10_restored_state_changed")
    gold = prior._json(private / "development_gold.json")
    score = prior._score(case["id"], gold[case["id"]], baseline,
                         prior._json(out / "positive_sql.json"), frozen,
                         prior._json(out / "positive_filestore.json"),
                         prior._json(out / "positive_store_paths.json"))
    prior.require(score == {"reward": 1.0, "difference_codes": []},
                  "terminal_v10_positive_saved_state_invalid")
    world = prior._json(private / "partition_cases.json")
    source = source_asset(case, world)
    checksum = sha1(source).hexdigest()
    matches = [row for row in baseline["attachments"] if row.get("name") == f"{case['id']}-source.pdf"]
    prior.require(len(matches) == 1 and matches[0].get("checksum") == checksum and
                  matches[0].get("file_size") == len(source) and
                  frozen.get(f"filestore/bench/{checksum[:2]}/{checksum}") == protocol.digest(source) and
                  freeze["source_asset_sha256"] == protocol.digest(source),
                  "terminal_v10_source_pdf_not_physically_bound")
    trace = prior._json(out / "gui_trace.json")
    actions, samples, rejected = trace.get("actions"), trace.get("guard_samples"), trace.get("pre_intent_rejections")
    prior.require(trace.get("schema") == "envloop-odoo-v066-gui-control-trace-v1" and
                  trace.get("task_binding_sha256") == freeze["task_package_sha256"] and
                  trace.get("sft_examples_written") == 0 and type(actions) is list and len(actions) == 16 and
                  type(samples) is list and len(samples) == 58 and type(rejected) is list and len(rejected) == 4,
                  "terminal_v10_trace_invalid")
    routes, counts = set(), {"attachment_link": 0, "viewer_close": 0, "price_editor": 0, "generic_rfq": 0}
    label = f"{case['id']}-source.pdf"
    guard_counts = [0, 0, 0]
    for index, action in enumerate(actions):
        phase = "positive" if index < 12 else "negative"
        matches = list((out / "actions").glob(f"step-{index:03d}*-intent.private.json"))
        prior.require(len(matches) == 1, "terminal_v10_action_intent_missing_or_replayed")
        ai = prior._json(matches[0])
        result = prior._json(matches[0].with_name(matches[0].name.replace("-intent.private.json", "-result.private.json")))
        prior._ref(out, action["frame"], image=True)
        prior.require(action.get("step") == ai.get("step") == index and
                      action.get("phase") == ai.get("phase") == phase and
                      ai.get("task_id") == case["id"] and ai.get("task_binding_sha256") == freeze["task_package_sha256"] and
                      ai.get("frame_sha256") == action["frame"]["sha256"] and
                      result.get("intent_sha256") == protocol.digest(matches[0].read_bytes()) and
                      result.get("applied_action") == ai.get("normalized_action") and
                      result.get("contract_receipt") == action.get("contract_receipt") and
                      action["contract_receipt"].get("error_code") is None,
                      "terminal_v10_action_or_dispatch_invalid")
        kind, refs = prior._route_binding(out, action, ai, result)
        counts[kind] += 1
        routes.update(refs)
        for n, (fn, args) in enumerate(((prior._guard, (label, samples)),
                                        (prior._viewer_guard, (label, samples)),
                                        (prior._price_guard, (case, wrong, baseline, samples)))):
            _refs, number = fn(out, action, ai, result, *args)
            guard_counts[n] += number
    prior.require(guard_counts == [1, 1, 1] and counts ==
                  {"attachment_link": 1, "viewer_close": 1, "price_editor": 1, "generic_rfq": 13},
                  "terminal_v10_completed_guard_routes_invalid")
    first = prior._artifact(out, rejected[0])
    prior.require(first.get("step") == 11 and first.get("phase") == "positive" and
                  first.get("observation_attempt") == 0 and first.get("error_code") == "stale_frame" and
                  first.get("pre_dispatch_intent_created") is False and first.get("gui_action_dispatched") is False and
                  first.get("route_decision_ref") is None and
                  not (out / "actions/step-011-intent.private.json").exists(),
                  "terminal_v10_positive_save_resample_invalid")
    for key in ("observed_frame_ref", "current_frame_ref"):
        prior._ref(out, first[key], image=True)
    prior._artifact(out, first["assistant_action_ref"])
    prior._artifact(out, first["route_probe_ref"])
    routes.add(str(out / first["route_probe_ref"]["path"]))
    extra, pair = _negative_rejections(out, rejected[1:], samples, freeze["task_package_sha256"])
    routes.update(extra)
    prior.require(routes == {str(path) for path in (out / "routes").glob("*.json")} and len(routes) == 39,
                  "terminal_v10_route_file_set_changed")
    guard_paths = {str(prior._ref(out, row["sampled_frame_ref"], image=True)[0]) for row in samples}
    prior.require(len(guard_paths) == 58 and guard_paths == {str(path) for path in (out / "frames").glob("guard-*.png")},
                  "terminal_v10_guard_file_set_changed")
    # Bind all raw bytes independently, without modifying the historical run.
    manifest = {}
    for path in sorted(out.rglob("*")):
        if path.is_dir():
            prior._private(path, directory=True)
        else:
            prior._private(path)
            manifest[str(path.relative_to(out))] = protocol.digest(path.read_bytes())
    rows = [json.loads(row) for row in (private / "worker-lease-events.jsonl").read_bytes().splitlines()]
    leases = [row for row in rows if row.get("operation") == "v066_train_attachment_calibration"]
    intent_time = prior._time(intent["started_at_utc"])
    pairs = [(a, b) for a, b in zip(leases, leases[1:]) if
             a.get("event") == "acquired" and b.get("event") == "released" and a.get("pid") == b.get("pid") and
             prior._time(a["at_utc"]) <= intent_time <= prior._time(b["at_utc"])]
    prior.require(len(pairs) == 1 and _lease_free(private / "worker-operation.lock"),
                  "terminal_v10_lease_not_released")
    review = prior._json(Path(review_path))
    prior.require(not Path(review_path).resolve().is_relative_to(out.resolve()) and
                  review.get("schema") == VISUAL_SCHEMA and
                  review.get("decision") == "positive_saved_negative_editor_visible_guard_rejected" and
                  review.get("source_frame_sha256") == manifest["frames/step-005.png"] and
                  review.get("positive_reload_frame_sha256") == manifest["positive_reload_frame.png"] and
                  review.get("negative_editor_frame_sha256") == manifest["frames/step-016.png"] and
                  review.get("source_asset_sha256") == freeze["source_asset_sha256"] and
                  review.get("source_pdf_pages_visually_reviewed") == 1 and
                  review.get("source_heading_table_and_rfq_match") is True and
                  review.get("positive_reloaded_price_matches_source") is True and
                  review.get("negative_distinct_rfq_and_selected_editor_visible") is True and
                  review.get("source_values_published") is False and
                  type(review.get("reviewer_id_sha256")) is str and
                  prior.HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
                  prior._time(review["reviewed_at_utc"]) >= prior._time(pairs[0][1]["at_utc"]),
                  "terminal_v10_separate_visual_review_missing")
    return {
        "schema": SCHEMA, "status": "train_only_positive_saved_negative_pre_intent_terminal",
        "public_freeze_sha256": protocol.digest(Path(public_freeze_path).read_bytes()),
        "private_freeze_sha256": protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_intent_sha256": manifest["intent.private.json"],
        "private_failure_sha256": manifest["failure.private.json"],
        "private_gui_trace_sha256": manifest["gui_trace.json"],
        "private_raw_file_manifest_sha256": protocol.digest(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()),
        "private_raw_files_checked": len(manifest),
        "private_visual_review_sha256": protocol.digest(Path(review_path).read_bytes()),
        "terminal_stage": "negative_gui", "terminal_error_code": "stale_frame",
        "reason_code": "known_corner_alternate_before_first_final_exact_frame",
        "completed_gui_actions": 16, "durable_route_claims_checked": 16,
        "positive_saved_state_independent_reward": score["reward"],
        "positive_source_files_and_store_paths_unchanged": True,
        "positive_price_parse_and_dispatch_exact_two_frame_guards_checked": True,
        "negative_editor_ready_probes_checked": 3,
        "negative_pre_intent_nonclaims_checked": 3,
        "negative_price_intent_or_dispatch_created": False,
        "negative_saved_state_exists": False,
        "negative_frame_pair_sha256": sorted(pair),
        "negative_changed_pixel_count": 4, "negative_diff_bbox": [16, 861, 18, 864],
        "known_corner_rgb_pairs_rederived_from_saved_pngs": True,
        "physical_guard_pngs_checked": 58,
        "source_pdf_viewed_and_saved_positive_visually_reviewed": True,
        "full_pre_and_post_cold_reset_exact": True, "full_post_filestore_manifest_exact": True,
        "service_state_restored_by_runner_receipt": True,
        "docker_services_cold_independently_verified": False,
        "worker_lease_released_and_available_at_audit": True,
        "selection_or_hidden_values_read": False, "model_attempts": 0,
        "train_controls_qualified": 0, "official_final_tasks_admitted": 0,
        "same_run_id_replay_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("worker-dir", "accepted-audit", "private-freeze", "public-freeze", "review", "public-out"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    result = audit(worker_dir=args.worker_dir, accepted_audit_path=args.accepted_audit,
                   private_freeze_path=args.private_freeze, public_freeze_path=args.public_freeze,
                   review_path=args.review)
    protocol.write_new(args.public_out, result, private=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
