"""Audit the first preserved Odoo v5 terminal dispatch-frame failure.

This reopens source-bound private artifacts without starting Odoo or replaying
an action. Its public projection contains no task ID, instruction, source
document, credentials, or run nonce.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as pixels
from tools import audit_odoo_v066_parse_border_no_gui_gate_v5 as gate_audit
from tools import audit_odoo_v066_parse_border_v5 as parse_audit
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_current_candidate_case_v5 as case_path
from tools import odoo_v066_parse_border_one_selection_v5 as runner
from tools import odoo_v066_parse_border_plan_v5 as plan_v5
from tools import odoo_v066_parse_border_source_v5 as source
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-parse-border-dispatch-failure-audit-v1"
PUBLIC_AUDIT = (protocol.ROOT / "docs/evidence" /
                "odoo-v066-parse-border-v5-first-dispatch-terminal-failure-audit-2026-09-29.json")
LEASE_PREFIX_BYTES = 3442
LEASE_PREFIX_SHA256 = (
    "d89f519baffd340ac06d14ab9dce6c2b508d2e484ae46a84d15790d587e7d506"
)
LEASE_PREFIX_ROWS = 28
LEASE_PID = 55280
LEASE_ACQUIRED = "2026-09-29T07:43:17.430726+00:00"
LEASE_RELEASED = "2026-09-29T07:43:50.803563+00:00"
PINNED_SOURCE = (
    "enterprise_fallback/odoo18/odoo_v066_scale_pinned_border_adapter.py"
)


class DispatchFailureAuditError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise DispatchFailureAuditError(code)


def read(path: Path) -> dict:
    need(path.is_file() and not path.is_symlink(),
         "dispatch_failure_audit_artifact_missing")
    value = json.loads(path.read_bytes())
    need(type(value) is dict, "dispatch_failure_audit_json_invalid")
    return value


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "dispatch_failure_audit_artifact_missing")
    return sha256(path.read_bytes()).hexdigest()


def reference(attempt: Path, value: dict) -> bytes:
    try:
        return pixels.ref_bytes(attempt, value)
    except (ValueError, OSError) as error:
        raise DispatchFailureAuditError(
            "dispatch_failure_audit_reference_changed") from error


def classify_return(observed: bytes, physical_samples: list[bytes],
                    final: bytes) -> str:
    """Reject a third frame; describe the observed/alternate return exactly."""
    need(len(physical_samples) == 6 and
         len({sha256(raw).hexdigest() for raw in physical_samples}) == 1 and
         all(pixels.two_pixel_alternate(observed, raw)
             for raw in physical_samples),
         "dispatch_failure_audit_six_alternate_pngs_invalid")
    need(final == observed and final != physical_samples[0],
         "dispatch_failure_audit_final_not_exact_observed_return")
    return "exact_observed_return_after_six_identical_two_pixel_alternates"


def verify_lease_prefix(raw: bytes, *, started: datetime,
                        ended: datetime,
                        prefix_bytes: int = LEASE_PREFIX_BYTES,
                        prefix_sha256: str = LEASE_PREFIX_SHA256,
                        row_count: int = LEASE_PREFIX_ROWS,
                        pid: int = LEASE_PID,
                        acquired_at: str = LEASE_ACQUIRED,
                        released_at: str = LEASE_RELEASED) -> None:
    need(len(raw) >= prefix_bytes and raw.endswith(b"\n") and
         raw[prefix_bytes - 1:prefix_bytes] == b"\n" and
         sha256(raw[:prefix_bytes]).hexdigest() == prefix_sha256,
         "dispatch_failure_audit_lease_prefix_changed")
    original = [json.loads(line) for line in raw[:prefix_bytes].splitlines()]
    need(len(original) == row_count and
         [row.get("event") for row in original[-2:]] ==
         ["acquired", "released"] and
         all(row.get("operation") == controller.LEASE_OPERATION and
             row.get("pid") == pid for row in original[-2:]) and
         [row.get("at_utc") for row in original[-2:]] ==
         [acquired_at, released_at] and
         datetime.fromisoformat(acquired_at) <= started <=
         datetime.fromisoformat(released_at) <= ended,
         "dispatch_failure_audit_original_lease_pair_invalid")
    suffix = [json.loads(line) for line in raw[prefix_bytes:].splitlines()]
    need(len(suffix) % 2 == 0 and
         all(suffix[index].get("event") == "acquired" and
             suffix[index + 1].get("event") == "released" and
             suffix[index].get("operation") ==
             suffix[index + 1].get("operation") and
             suffix[index].get("pid") == suffix[index + 1].get("pid")
             for index in range(0, len(suffix), 2)),
         "dispatch_failure_audit_appended_lease_incomplete")


def audit(*, worker_dir: Path, historical_root: Path,
          prior_private_plan: Path, prior_public_plan: Path,
          old_private_plan: Path, old_public_plan: Path,
          private_plan: Path, public_plan: Path) -> dict:
    source.validate()
    worker = worker_dir.resolve()
    gate = gate_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan,
        private_plan=private_plan, public_plan=public_plan,
        allow_current_run=True)
    need(gate["status"] ==
         "fresh_no_gui_sql_full_filestore_gate_independently_verified",
         "dispatch_failure_audit_prior_gate_not_verified")
    plan = protocol.private_json(private_plan)
    private = protocol._worker_split(worker, "selection")
    need(digest(protocol.ROOT / PINNED_SOURCE) ==
         plan["source_sha256s"][PINNED_SOURCE],
         "dispatch_failure_audit_frozen_dispatch_source_changed")
    run = private / "v066_scale_controls" / plan["fresh_run_directory_name"]
    attempt = run / "attempt-000"
    batch_path = run / "batch-intent.private.json"
    batch = read(batch_path)
    batch_sha = digest(batch_path)
    row = plan["tasks"][0]
    need(batch.get("schema") == runner.BATCH_SCHEMA and
         batch.get("private_plan_sha256") == digest(private_plan) and
         batch.get("public_plan_sha256") == digest(public_plan) and
         batch.get("epoch_source_freeze_sha256") ==
         source.digest(source.FREEZE) and
         batch.get("parse_border_v5_source_freeze_sha256") ==
         source.digest(source.FREEZE) and
         batch.get("prior_terminal_failure_receipt_sha256") ==
         plan["prior_terminal_failure_receipt_sha256"] and
         batch.get("no_gui_gate_sha256") == gate["gate_sha256"] and
         batch.get("run_nonce_hex") == plan["run_nonce_hex"] and
         batch.get("expected_case_count") == 1 and
         batch.get("automatic_replay_authorized") is False and
         batch.get("campaign_dispatch_authorized") is False and
         batch.get("official_final_tasks_admitted") == 0 and
         batch.get("model_attempts") == 0,
         "dispatch_failure_audit_batch_intent_unbound")
    events, _tail, count = controller.read_journal(
        run / "journal.private.jsonl")
    failure_path = attempt / "failure.private.json"
    need(count == 2 and
         [event.get("event") for event in events] ==
         ["case_started", "case_failed"] and
         all(event.get("ordinal") == 0 and
             event.get("task_id") == row["task_id"] and
             event.get("package_sha256") == row["package_sha256"] and
             event.get("attempt_dir") == "attempt-000" and
             event.get("run_intent_sha256") == batch_sha
             for event in events) and
         events[-1].get("failure_receipt_sha256") ==
         digest(failure_path) and
         not (attempt / "attempt.private.json").exists(),
         "dispatch_failure_audit_terminal_journal_unbound")
    initial = read(attempt / "intent.private.json")
    failed = read(failure_path)
    need(initial.get("schema") == case_path.INTENT_SCHEMA and
         initial.get("task_id") == row["task_id"] and
         initial.get("package_sha256") == row["package_sha256"] and
         initial.get("epoch_source_freeze_sha256") ==
         source.digest(source.FREEZE) and
         initial.get("no_gui_gate_sha256") == gate["gate_sha256"] and
         initial.get("run_nonce_sha256") ==
         protocol.digest(bytes.fromhex(plan["run_nonce_hex"])) and
         failed.get("schema") == case_path.EPOCH_CASE_SCHEMA and
         failed.get("status") ==
         "failed_preserve_original_attempt_manual_review_required" and
         failed.get("stage") == "source_gui" and
         failed.get("error_type") == "ContractError" and
         failed.get("error_code") == "stale_frame" and
         failed.get("reset_exact") is True and
         failed.get("services_restored") is True and
         failed.get("no_gui_gate_sha256") == gate["gate_sha256"] and
         failed.get("run_nonce_sha256") ==
         protocol.digest(bytes.fromhex(plan["run_nonce_hex"])) and
         failed.get("official_final_tasks_admitted") == 0 and
         failed.get("model_attempts") == 0,
         "dispatch_failure_audit_attempt_or_failure_unbound")
    pre = read(attempt / "pre_restore.json")
    post = read(attempt / "post_restore.json")
    need(pre.get("business_snapshot_equal") is True and
         pre.get("physical_filestore_equal_before_web_restart") is True and
         post.get("business_snapshot_equal") is True and
         post.get("physical_filestore_equal_before_web_restart") is True and
         read(attempt / "baseline_sql.json") ==
         protocol.private_json(private / "baseline_snapshot.json") and
         read(attempt / "restored_sql.json") ==
         protocol.private_json(private / "baseline_snapshot.json") and
         read(attempt / "restored_filestore.json") ==
         protocol.private_json(private / "baseline-filestore-manifest.json") and
         controller._running_services_without_compose_blank(worker) == set(),
         "dispatch_failure_audit_reset_or_services_not_exact")
    trace = read(attempt / "gui_trace.json")
    need(trace.get("schema") == controller.TRACE_SCHEMA and
         trace.get("task_binding_sha256") == row["task_binding_sha256"] and
         trace.get("sft_examples_written") == 0 and
         trace.get("pre_intent_rejections") == [] and
         type(trace.get("actions")) is list and
         len(trace["actions"]) == 3 and
         [(action.get("phase"), action.get("step"))
          for action in trace["actions"]] ==
         [("positive", 0), ("positive", 1), ("positive", 2)],
         "dispatch_failure_audit_prior_gui_action_trace_changed")
    checked = [parse_audit.audit_action(attempt, trace, row, index)
               for index in range(3)]
    need(all(item["parse_classification"] == parse_audit.PARSE_EXACT and
             item["dispatch_classification"] == "exact_physical_frame"
             for item in checked) and
         [(sample.get("step"), sample.get("stage"),
           sample.get("sample"), sample.get("classification"))
          for sample in trace["exact_return_guard_samples"][:6]] ==
         [(step, stage, 0, "exact_return") for step in range(3)
          for stage in ("parse", "dispatch")],
         "dispatch_failure_audit_prior_gui_action_guard_changed")
    intent = read(attempt / "actions/step-003-intent.private.json")
    raw_action = read(attempt / "actions/step-003-assistant.json")
    observed = reference(attempt, intent["frame_ref"])
    action = intent["normalized_action"]
    target = action.get("target")
    control = intent.get("observed_target_control")
    controls = intent.get("observation_controls")
    need(intent.get("phase") == "positive" and
         intent.get("step") == 3 and
         intent.get("task_id") == row["task_id"] and
         intent.get("task_binding_sha256") == row["package_sha256"] and
         intent.get("dispatch_state") ==
         "intent_durable_before_gui_action" and
         intent.get("pre_intent_stale_resamples") == 0 and
         intent.get("frame_sha256") == sha256(observed).hexdigest() and
         action.get("type") == raw_action.get("type") == "click" and
         action.get("target") == raw_action.get("target") and
         type(target) is dict and set(target) == {"x", "y"} and
         type(control) is dict and control.get("visible") is True and
         control.get("enabled") is True and
         control.get("purchase_rfq_view") is True and
         type(controls) is list and
         len([item for item in controls if type(item) is dict and
              all(item.get(key) == control.get(key)
                  for key in ("ref", "role", "label")) and
              item.get("visible") is True and
              item.get("enabled") is True]) == 1 and
         type(control.get("bounds")) is list and
         len(control["bounds"]) == 4 and
         control["bounds"][0] <= target["x"] <= control["bounds"][2] and
         control["bounds"][1] <= target["y"] <= control["bounds"][3] and
         not (attempt / "actions/step-003-result.private.json").exists() and
         not (attempt / "source_evidence.json").exists() and
         not (attempt / "positive_sql.json").exists(),
         "dispatch_failure_audit_step3_intent_or_no_click_boundary_invalid")
    samples = [sample for sample in trace.get("exact_return_guard_samples", [])
               if sample.get("step") == 3]
    frame_id_sha = sha256(intent["frame_id"].encode()).hexdigest()
    need(len(trace["exact_return_guard_samples"]) == 14 and
         len(samples) == 8 and
         all(sample.get("observed_frame_sha256") ==
             sha256(observed).hexdigest() and
             sample.get("observed_frame_id_sha256") == frame_id_sha
             for sample in samples) and
         samples[0].get("stage") == "parse" and
         samples[0].get("sample") == 0 and
         samples[0].get("classification") == "exact_return" and
         reference(attempt, samples[0]["sampled_frame_ref"]) == observed and
         [(sample.get("stage"), sample.get("sample"),
           sample.get("classification")) for sample in samples[1:7]] ==
         [("dispatch", index,
           "one_recurring_micro_raster_alternate")
          for index in range(6)] and
         samples[7].get("stage") == "dispatch" and
         samples[7].get("sample") == 6 and
         samples[7].get("classification") ==
         "third_or_material_frame_rejected",
         "dispatch_failure_audit_step3_guard_sequence_changed")
    alternates = [reference(attempt, sample["sampled_frame_ref"])
                  for sample in samples[1:7]]
    final = reference(attempt, samples[7]["sampled_frame_ref"])
    classification = classify_return(observed, alternates, final)
    # The frozen pinned-border guard rejects final != last alternate before
    # OdooV066TrainAdapter.dispatch reaches the mouse.click branch.
    need(not (attempt / "actions/step-003-result.private.json").exists() and
         classification ==
         "exact_observed_return_after_six_identical_two_pixel_alternates",
         "dispatch_failure_audit_click_boundary_uncertain")
    lease = private / "worker-lease-events.jsonl"
    protocol._private(lease)
    started = datetime.fromisoformat(initial["started_at_utc"])
    ended = power.validate(events[-1]["host_power_end"])
    need(power.validate(events[0]["host_power_pre_dispatch"]) <= started,
         "dispatch_failure_audit_power_timeline_invalid")
    verify_lease_prefix(lease.read_bytes(), started=started, ended=ended)
    return {
        "schema": SCHEMA,
        "status": "original_v5_dispatch_frame_failure_independently_verified_no_replay",
        "source_freeze_sha256": source.digest(source.FREEZE),
        "private_plan_sha256": digest(private_plan),
        "prior_no_gui_gate_sha256": gate["gate_sha256"],
        "batch_intent_sha256": batch_sha,
        "journal_sha256": digest(run / "journal.private.jsonl"),
        "attempt_intent_sha256": digest(attempt / "intent.private.json"),
        "step3_durable_action_intent_sha256":
            digest(attempt / "actions/step-003-intent.private.json"),
        "failure_receipt_sha256": digest(failure_path),
        "worker_lease_prefix_sha256": LEASE_PREFIX_SHA256,
        "worker_lease_prefix_bytes": LEASE_PREFIX_BYTES,
        "completed_prior_gui_actions": 3,
        "failed_action_step": 3,
        "failed_action_stage": "source_gui",
        "failed_action_error_code": "stale_frame",
        "failed_action_intent_created": True,
        "failed_action_result_written": False,
        "failed_action_click_dispatched": False,
        "failed_action_click_basis":
            "frozen_dispatch_guard_returned_false_before_mouse_click",
        "dispatch_alternate_samples": 6,
        "alternate_difference_pixels": 2,
        "final_physical_classification": classification,
        "frozen_final_sample_label": "third_or_material_frame_rejected",
        "third_physical_image_observed": False,
        "source_document_opened": False,
        "positive_saved_state_observed": False,
        "baseline_sql_and_full_filestore_restored_exact": True,
        "original_worker_services_stopped": True,
        "original_worker_lease_released": True,
        "source_visual_review_pending": True,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("worker-dir", "historical-root", "prior-private-plan",
                 "prior-public-plan", "old-private-plan", "old-public-plan",
                 "private-plan", "public-plan"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--write-public-audit", action="store_true")
    args = parser.parse_args()
    values = vars(args)
    write = values.pop("write_public_audit")
    result = audit(**values)
    if write:
        need(not PUBLIC_AUDIT.exists() and not PUBLIC_AUDIT.is_symlink(),
             "dispatch_failure_audit_public_receipt_already_exists")
        protocol.write_new(PUBLIC_AUDIT, result, private=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
