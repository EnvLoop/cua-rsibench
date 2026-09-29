"""Independently reopen the terminal v4 train attachment-route attempt.

This audit is read-only except for its new, field-limited public receipt. It
never starts Docker services, replays GUI actions, or reads other partitions.
"""

from __future__ import annotations

import argparse
from hashlib import sha1
import json
from pathlib import Path

from enterprise_fallback.odoo18.partition_factory import source_asset
from tools import audit_odoo_v066_train_attachment_calibration_v4 as prior
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v4 as run


SCHEMA = "envloop-odoo-train-attachment-v4-terminal-audit-v1"


def audit(*, worker_dir: Path, accepted_audit_path: Path,
          private_freeze_path: Path, public_freeze_path: Path) -> dict:
    worker, private, freeze, case, _wrong = run._verify_freeze(
        worker_dir, accepted_audit_path, private_freeze_path,
        public_freeze_path)
    out = private / "v066_attachment_route_calibration" / run.RUN_NAME
    prior._private(out, directory=True)
    intent_path = out / "intent.private.json"
    failure_path = out / "failure.private.json"
    intent = prior._json(intent_path)
    failure = prior._json(failure_path)
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
        failure.get("error_type") == "TypeError" and
        failure.get("run_nonce_sha256") == nonce_sha and
        failure.get("reset_exact") is True and
        failure.get("services_restored") is True and
        failure.get("model_attempts") == 0 and
        failure.get("official_final_tasks_admitted") == 0 and
        not (out / "attempt.private.json").exists(),
        "terminal_v4_identity_or_outcome_invalid")
    readiness = prior._json(out / "db_readiness.json")
    prior.require(
        readiness.get("status") == "postgres_health_and_select_1_ready" and
        readiness.get("query") == "SELECT 1" and
        type(readiness.get("probe_count")) is int and
        1 <= readiness["probe_count"] <= run.READINESS_MAX_PROBES and
        readiness.get("observations", [])[-1].get("psql_exit_code") == 0,
        "terminal_v4_db_readiness_invalid")
    baseline = prior._json(private / "baseline_snapshot.json")
    frozen_files = prior._json(private / "baseline-filestore-manifest.json")
    for name in ("pre_restore", "post_restore"):
        receipt = prior._json(out / f"{name}.json")
        prior.require(
            receipt.get("status") == "restored" and
            receipt.get("business_snapshot_equal") is True and
            receipt.get("physical_filestore_equal_before_web_restart") is True and
            receipt.get("db_sha256") == freeze["checkpoint"]["db_sha256"] and
            receipt.get("filestore_sha256") ==
                freeze["checkpoint"]["filestore_sha256"],
            "terminal_v4_cold_reset_invalid")
    prior.require(
        prior._json(out / "baseline_sql.json") == baseline and
        prior._json(out / "restored_sql.json") == baseline and
        prior._json(out / "restored_filestore.json") == frozen_files and
        not any((out / name).exists() for name in
                ("positive_sql.json", "negative_sql.json",
                 "source_frame.png", "positive_reload_frame.png",
                 "negative_reload_frame.png")),
        "terminal_v4_full_state_or_phase_boundary_invalid")
    world = prior._json(private / "partition_cases.json")
    source = source_asset(case, world)
    source_rows = [row for row in baseline["attachments"]
                   if row.get("name") == f"{case['id']}-source.pdf"]
    prior.require(
        len(source_rows) == 1 and
        source_rows[0].get("checksum") == sha1(source).hexdigest() and
        source_rows[0].get("file_size") == len(source) and
        frozen_files.get("filestore/bench/" +
                         sha1(source).hexdigest()[:2] + "/" +
                         sha1(source).hexdigest()) == protocol.digest(source),
        "terminal_v4_source_pdf_not_physically_bound")
    trace_path = out / "gui_trace.json"
    trace = prior._json(trace_path)
    actions = trace.get("actions")
    samples = trace.get("guard_samples")
    prior.require(
        trace.get("task_binding_sha256") == freeze["task_package_sha256"] and
        trace.get("sft_examples_written") == 0 and
        trace.get("pre_intent_rejections") == [] and
        type(actions) is list and len(actions) == 3 and
        type(samples) is list and len(samples) == 8,
        "terminal_v4_gui_trace_invalid")
    for step in range(4):
        frame_path = out / "frames" / f"step-{step:03d}.png"
        frame_ref = {"path": f"frames/step-{step:03d}.png",
                     "sha256": protocol.digest(frame_path.read_bytes())}
        _path, frame = prior._ref(out, frame_ref, image=True)
        action_intent_path = out / "actions" / f"step-{step:03d}-intent.private.json"
        action_intent = prior._json(action_intent_path)
        prior.require(
            action_intent.get("step") == step and
            action_intent.get("phase") == "positive" and
            action_intent.get("task_id") == case["id"] and
            action_intent.get("task_binding_sha256") ==
                freeze["task_package_sha256"] and
            action_intent.get("frame_sha256") == protocol.digest(frame),
            "terminal_v4_action_intent_changed")
        result_path = out / "actions" / f"step-{step:03d}-result.private.json"
        if step < 3:
            result = prior._json(result_path)
            action = actions[step]
            prior.require(
                action.get("step") == step and
                action.get("phase") == "positive" and
                action.get("frame") == frame_ref and
                result.get("intent_sha256") ==
                    protocol.digest(action_intent_path.read_bytes()) and
                result.get("applied_action") ==
                    action_intent.get("normalized_action") and
                result.get("contract_receipt") ==
                    action.get("contract_receipt") and
                action.get("contract_receipt", {}).get("error_code") is None,
                "terminal_v4_completed_action_changed")
        else:
            prior.require(
                not result_path.exists() and
                action_intent.get("normalized_action", {}).get("type") ==
                    "click" and
                action_intent.get("observed_target_control", {}).get("label") ==
                    "Attach files" and
                action_intent.get("observed_url", "").endswith(
                    "/odoo/purchase/1"),
                "terminal_v4_failed_button_boundary_changed")
        pair = [item for item in samples if item.get("step") == step]
        prior.require(
            len(pair) == 2 and
            [item.get("stage") for item in pair] == ["parse", "dispatch"] and
            all(item.get("sample") == 0 and
                item.get("classification") == "exact_return"
                for item in pair),
            "terminal_v4_guard_sequence_changed")
        for item in pair:
            _path, guard = prior._ref(out, item["sampled_frame_ref"], image=True)
            prior.require(guard == frame,
                          "terminal_v4_guard_frame_changed")
    png_names = {path.name for path in (out / "frames").glob("*.png")}
    prior.require(png_names ==
                  {f"step-{step:03d}.png" for step in range(4)} |
                  {f"guard-{step:04d}.png" for step in range(8)},
                  "terminal_v4_frame_set_changed")
    rows = [json.loads(row) for row in
            (private / "worker-lease-events.jsonl").read_bytes().splitlines()]
    lease_rows = [row for row in rows if row.get("operation") ==
                  "v066_train_attachment_calibration"]
    intent_time = prior._time(intent["started_at_utc"])
    matching_pairs = [
        (a, b) for a, b in zip(lease_rows, lease_rows[1:])
        if a.get("event") == "acquired" and
        b.get("event") == "released" and
        a.get("pid") == b.get("pid") and
        prior._time(a["at_utc"]) <= intent_time <=
            prior._time(b["at_utc"])
    ]
    prior.require(
        len(matching_pairs) == 1 and
        run._running(worker) == set(),
        "terminal_v4_lease_or_service_cleanup_invalid")
    return {
        "schema": SCHEMA,
        "status": "train_only_terminal_before_pdf_link_and_saved_repair",
        "public_freeze_sha256":
            protocol.digest(Path(public_freeze_path).read_bytes()),
        "private_freeze_sha256":
            protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_intent_sha256": protocol.digest(intent_path.read_bytes()),
        "private_failure_sha256": protocol.digest(failure_path.read_bytes()),
        "private_gui_trace_sha256": protocol.digest(trace_path.read_bytes()),
        "failed_action_intent_sha256": protocol.digest(
            (out / "actions" / "step-003-intent.private.json").read_bytes()),
        "terminal_stage": "source_gui",
        "terminal_error_type": "TypeError",
        "completed_gui_actions": 3,
        "failed_button_intents_without_dispatch_result": 1,
        "physical_guard_pngs_checked": 8,
        "source_pdf_physically_bound_at_baseline": True,
        "source_pdf_viewed_in_gui": False,
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
