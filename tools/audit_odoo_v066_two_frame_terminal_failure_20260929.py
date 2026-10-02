"""Read-only, field-limited audit of the retained Odoo v6 terminal control.

This auditor never starts a service, dispatches a GUI action, scores a model,
or retries the failed selection identity. It reopens the frozen original
attempt, complete saved SQL/filestore manifests, and every physical guard PNG.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image

from tools import audit_odoo_v066_two_frame_dispatch_v6 as dispatch_audit
from tools import audit_odoo_v066_two_frame_dispatch_v6a as strict_audit
from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as pixels
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_two_frame_one_selection_v6 as runner
from tools import odoo_v066_two_frame_source_v6 as source


SCHEMA = "envloop-odoo-v066-two-frame-v6-terminal-failure-independent-audit-v1"


class TerminalAuditError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise TerminalAuditError(code)


def raw(path: Path) -> bytes:
    need(path.is_file() and not path.is_symlink(), "audit_file_missing_or_symlink")
    return path.read_bytes()


def digest(path: Path) -> str:
    return sha256(raw(path)).hexdigest()


def obj(path: Path) -> dict:
    value = json.loads(raw(path))
    need(type(value) is dict, "audit_json_not_object")
    return value


def linked_png(attempt: Path, sample: dict) -> bytes:
    reference = sample.get("sampled_frame_ref")
    need(type(reference) is dict, "audit_guard_ref_missing")
    image = pixels.ref_bytes(attempt, reference)
    need(image[:8] == b"\x89PNG\r\n\x1a\n", "audit_guard_not_png")
    return image


def audit(*, worker_dir: Path, private_plan: Path,
          public_plan: Path) -> dict:
    source.validate()
    strict_audit.validate_source()
    worker = Path(worker_dir).resolve()
    need(worker.name == "selection", "audit_not_original_selection_worker")
    private = protocol._worker_split(worker, "selection")
    plan = obj(private_plan)
    public = obj(public_plan)
    need(plan.get("schema") ==
         "envloop-odoo-v066-two-frame-selection-plan-private-v6" and
         plan.get("split") == "selection" and
         plan.get("task_count") == 20 and
         len(plan.get("tasks", [])) == 20 and
         plan.get("same_underlying_task_new_candidate_attempt") is True and
         plan.get("automatic_replay_authorized") is False and
         plan.get("official_final_tasks_admitted") == 0 and
         plan.get("model_attempts") == 0 and
         public.get("private_plan_sha256") == digest(private_plan) and
         public.get("two_frame_v6_source_freeze_sha256") ==
         digest(source.FREEZE), "audit_frozen_plan_or_projection_invalid")
    row = plan["tasks"][0]
    run_dir = private / "v066_scale_controls" / plan["fresh_run_directory_name"]
    attempt = run_dir / "attempt-000"
    need(run_dir.is_dir() and attempt.is_dir() and
         not run_dir.is_symlink() and not attempt.is_symlink(),
         "audit_original_attempt_missing")
    batch_path = run_dir / "batch-intent.private.json"
    batch = obj(batch_path)
    batch_hash = digest(batch_path)
    need(batch.get("schema") == runner.BATCH_SCHEMA and
         batch.get("private_plan_sha256") == digest(private_plan) and
         batch.get("public_plan_sha256") == digest(public_plan) and
         batch.get("expected_case_count") == 1 and
         batch.get("automatic_replay_authorized") is False and
         batch.get("campaign_dispatch_authorized") is False and
         batch.get("official_final_tasks_admitted") == 0 and
         batch.get("model_attempts") == 0,
         "audit_batch_intent_unbound")
    journal_path = run_dir / "journal.private.jsonl"
    events, _tail, count = controller.read_journal(journal_path)
    failure_path = attempt / "failure.private.json"
    need(count == 2 and
         [event.get("event") for event in events] ==
         ["case_started", "case_failed"] and
         all(event.get("ordinal") == 0 and
             event.get("task_id") == row["task_id"] and
             event.get("package_sha256") == row["package_sha256"] and
             event.get("attempt_dir") == "attempt-000" and
             event.get("run_intent_sha256") == batch_hash
             for event in events) and
         events[-1].get("failure_receipt_sha256") == digest(failure_path) and
         not (attempt / "attempt.private.json").exists(),
         "audit_terminal_journal_unbound")
    failure = obj(failure_path)
    need(failure.get("schema") ==
         "envloop-odoo-v066-current-candidate-case-attempt-v6" and
         failure.get("status") ==
         "failed_preserve_original_attempt_manual_review_required" and
         failure.get("stage") == "source_gui" and
         failure.get("error_type") == "ContractError" and
         failure.get("error_code") == "stale_frame" and
         failure.get("reset_exact") is True and
         failure.get("services_restored") is True and
         failure.get("current_candidate_private_sha256") ==
         plan["current_candidate_private_sha256"] and
         failure.get("run_nonce_sha256") ==
         protocol.digest(bytes.fromhex(plan["run_nonce_hex"])) and
         failure.get("official_final_tasks_admitted") == 0 and
         failure.get("model_attempts") == 0,
         "audit_failure_receipt_unbound")

    checkpoint = plan["checkpoint"]
    frozen_sql_path = private / "baseline_snapshot.json"
    frozen_files_path = private / "baseline-filestore-manifest.json"
    need(digest(frozen_sql_path) == checkpoint["baseline_snapshot_sha256"] and
         digest(frozen_files_path) ==
         checkpoint["baseline_filestore_manifest_sha256"],
         "audit_frozen_checkpoint_changed")
    frozen_sql = obj(frozen_sql_path)
    frozen_files = obj(frozen_files_path)
    need(len(frozen_sql) == 13 and len(frozen_files) == 888 and
         obj(attempt / "baseline_sql.json") == frozen_sql and
         obj(attempt / "restored_sql.json") == frozen_sql and
         obj(attempt / "restored_filestore.json") == frozen_files,
         "audit_saved_full_sql_or_filestore_not_exact")
    for name in ("pre_restore.json", "post_restore.json"):
        receipt = obj(attempt / name)
        need(receipt.get("status") == "restored" and
             receipt.get("business_snapshot_equal") is True and
             receipt.get("physical_filestore_equal_before_web_restart") is True and
             receipt.get("db_sha256") == checkpoint["db_sha256"] and
             receipt.get("filestore_sha256") == checkpoint["filestore_sha256"],
             "audit_physical_reset_receipt_invalid")
    need(not any((attempt / name).exists() for name in (
        "source_frame.png", "source_evidence.json", "positive_sql.json",
        "negative_sql.json", "online_positive_score.private.json",
        "online_negative_score.private.json")),
         "audit_unexpected_source_or_score_after_failure")

    trace_path = attempt / "gui_trace.json"
    trace = obj(trace_path)
    actions = trace.get("actions")
    samples = trace.get("exact_return_guard_samples")
    need(trace.get("schema") == controller.TRACE_SCHEMA and
         trace.get("task_binding_sha256") == row["task_binding_sha256"] and
         trace.get("sft_examples_written") == 0 and
         type(actions) is list and type(samples) is list and
         len(actions) == 4 and len(samples) == 22 and
         trace.get("pre_intent_rejections") == [],
         "audit_incomplete_gui_trace_shape_changed")
    dispatches = []
    for step in range(4):
        audited = dispatch_audit.audit_action(attempt, trace, row, step)
        intent = obj(attempt / "actions" /
                     f"step-{step:03d}-intent.private.json")
        action = intent.get("normalized_action")
        need(type(action) is dict and
             action.get("task_id") == row["task_id"] and
             action.get("task_binding_sha256") == row["package_sha256"] and
             action.get("step") == step and
             action.get("frame_id") == intent.get("frame_id"),
             "audit_dispatched_action_task_or_frame_unbound")
        dispatches.append(audited["dispatch_classification"])
    source_tray_intent = obj(
        attempt / "actions/step-003-intent.private.json")
    need(dispatches == ["exact_physical_frame"] * 3 +
         ["two_frame_observed_confirmed"] and
         actions[3].get("phase") == "positive" and
         source_tray_intent.get("observed_target_control", {})
         .get("label") == "Attach files",
         "audit_source_attachment_open_step_unbound")
    final_intent = obj(attempt / "actions/step-004-intent.private.json")
    final_action = final_intent.get("normalized_action")
    need(type(final_action) is dict and
         final_action.get("type") == "click" and
         final_action.get("task_id") == row["task_id"] and
         final_action.get("task_binding_sha256") == row["package_sha256"] and
         final_action.get("step") == 4 and
         final_action.get("frame_id") == final_intent.get("frame_id") and
         final_intent.get("task_id") == row["task_id"] and
         final_intent.get("task_binding_sha256") ==
         row["package_sha256"] and
         final_intent.get("observed_target_control") is None and
         not (attempt / "actions/step-004-result.private.json").exists() and
         len(actions) == 4,
         "audit_source_link_intent_or_no_dispatch_changed")
    observed_path = attempt / "frames/step-004.png"
    need(final_intent.get("frame_sha256") == digest(observed_path) and
         type(final_intent.get("observed_url")) is str and
         final_intent.get("observed_url") ==
         source_tray_intent.get("observed_url"),
         "audit_source_link_observation_unbound")
    with Image.open(observed_path) as image:
        need(image.format == "PNG" and image.size == (1440, 1000),
             "audit_source_link_png_shape_changed")
    need([(sample.get("step"), sample.get("stage"),
           sample.get("classification")) for sample in samples[15:]] ==
         [(4, "parse", "exact_return")] +
         [(4, "dispatch", "one_recurring_micro_raster_alternate")] * 6 and
         all(sample.get("sample") == index for index, sample in
             enumerate(samples[16:])) and
         samples[15].get("sample") == 0 and
         all(sample.get("observed_frame_sha256") ==
             digest(observed_path) for sample in samples[15:]),
         "audit_source_link_guard_sequence_changed")
    need(linked_png(attempt, samples[15]) == raw(observed_path),
         "audit_source_link_parse_not_exact")
    alternate_pngs = [linked_png(attempt, sample)
                      for sample in samples[16:]]
    need(len({sha256(png).hexdigest() for png in alternate_pngs}) == 1 and
         all(pixels.two_pixel_alternate(raw(observed_path), png)
             for png in alternate_pngs),
         "audit_source_link_physical_frames_not_one_safe_alternate")
    need(not any(sample.get("stage") == "dispatch_final" and
                 sample.get("step") == 4 for sample in samples),
         "audit_source_link_unexpected_final_guard")
    actual_guards = {p.name for p in (attempt / "frames").iterdir()
                     if p.name.startswith("guard-")}
    expected_guards = {f"guard-{index:04d}.png"
                       for index in range(len(samples))}
    need(actual_guards == expected_guards and all(
        (attempt / "frames" / name).is_file() and
        not (attempt / "frames" / name).is_symlink()
        for name in expected_guards),
        "audit_physical_guard_sink_set_unbound")
    for sample in samples:
        linked_png(attempt, sample)

    lease_path = private / "worker-lease-events.jsonl"
    lease = raw(lease_path)
    need(lease.endswith(b"\n"), "audit_worker_lease_log_incomplete")
    lease_rows = [json.loads(line) for line in lease.splitlines()]
    acquired, released = lease_rows[-2:]
    started = datetime.fromisoformat(obj(attempt / "intent.private.json")
                                     ["started_at_utc"])
    need(acquired.get("event") == "acquired" and
         released.get("event") == "released" and
         acquired.get("operation") == controller.LEASE_OPERATION and
         released.get("operation") == controller.LEASE_OPERATION and
         acquired.get("pid") == released.get("pid") and
         acquired.get("pid") == 13314 and
         datetime.fromisoformat(acquired["at_utc"]) <= started <=
         datetime.fromisoformat(released["at_utc"]),
         "audit_worker_lease_pair_unbound")

    return {
        "schema": SCHEMA,
        "status": "terminal_source_link_pre_dispatch_stale_frame_independently_verified",
        "as_of_date": "2026-09-29",
        "audit_source_sha256": digest(Path(__file__)),
        "v6_source_freeze_sha256": digest(source.FREEZE),
        "v6a_strict_audit_freeze_sha256": digest(strict_audit.FREEZE),
        "private_plan_sha256": digest(private_plan),
        "public_plan_sha256": digest(public_plan),
        "batch_intent_sha256": batch_hash,
        "journal_sha256": digest(journal_path),
        "failure_receipt_sha256": digest(failure_path),
        "gui_trace_sha256": digest(trace_path),
        "source_link_observed_frame_sha256": digest(observed_path),
        "source_link_final_intent_sha256":
            digest(attempt / "actions/step-004-intent.private.json"),
        "dispatched_positive_source_navigation_actions": 4,
        "source_attachment_control_dispatched": True,
        "source_pdf_link_click_dispatched": False,
        "source_pdf_content_opened": False,
        "source_pdf_content_visual_review_pending": True,
        "source_link_observed_target_control_present": False,
        "source_link_guard_samples": 7,
        "source_link_stable_alternate_samples": 6,
        "source_link_third_or_material_frame_seen": False,
        "all_indexed_guard_pngs_reopened": len(samples),
        "unreferenced_guard_pngs": 0,
        "saved_sql_sections_equal_baseline": len(frozen_sql),
        "saved_full_filestore_entries_equal_baseline": len(frozen_files),
        "pre_and_post_physical_reset_receipts_exact": True,
        "worker_lease_released": True,
        "prior_retained_same_id_selection_failures_documented": 5,
        "terminal_same_id_selection_failures_documented_after_this_attempt": 6,
        "current_source_revised_terminal_failures_documented": 3,
        "fresh_positive_negative_controls_completed": 0,
        "selection_tasks_admitted_from_this_attempt": 0,
        "selection_denominator_replacement_required": True,
        "same_id_automatic_replay_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
        "live_post_exit_volume_rescan_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(worker_dir=args.worker_dir,
                           private_plan=args.private_plan,
                           public_plan=args.public_plan), sort_keys=True))


if __name__ == "__main__":
    main()
