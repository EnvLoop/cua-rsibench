"""Independent saved-state audit for a parse-border v5 Odoo GUI case.

The signed historical saved-state checks remain intact. The additive parse
auditor reopens every observed and physical PNG and independently verifies
the narrow v5 exception. This file never executes a GUI.
"""

from __future__ import annotations

from pathlib import Path

from enterprise_fallback.odoo18.partition_factory import source_asset
from enterprise_fallback.odoo18 import v066_requalification_pilot as pilot
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_current_candidate_case_v5 as case_path
from tools import audit_odoo_v066_parse_border_no_gui_gate_v5 as gate_audit
from tools import audit_odoo_v066_parse_border_v5 as parse_audit
from tools import odoo_v066_parse_border_source_v5 as source
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_parse_border_plan_v5 as plan_v5

EPOCH_CASE_AUDIT_SCHEMA = "envloop-odoo-v066-parse-border-case-independent-audit-v5"
require = independent.require
_time = independent._time
_lease = independent._lease
REFS = independent.REFS
_action_chain = independent._action_chain
GOLD_FILES = independent.GOLD_FILES

def audit_current_case(*, plan: dict, row: dict, attempt: Path,
               worker_private: Path) -> dict:
    attempt = Path(attempt)
    protocol._private(attempt, directory=True)
    raw_path = attempt / "attempt.private.json"
    receipt = protocol.private_json(raw_path)
    require(receipt.get("schema") == case_path.EPOCH_CASE_SCHEMA and
            receipt.get("status") == case_path.EPOCH_CASE_STATUS and
            receipt.get("split") == plan["split"] and
            receipt.get("family") == row["family"] and
            receipt.get("task_id") == row["task_id"] and
            receipt.get("package_sha256") == row["package_sha256"] and
            receipt.get("task_binding_sha256") ==
            row["task_binding_sha256"] and
            receipt.get("source_freeze_sha256") ==
            plan["source_freeze_sha256"] and
            receipt.get("epoch_source_freeze_sha256") ==
            row["epoch_source_freeze_sha256"] and
            receipt.get("plan_sha256") == protocol.digest(protocol.canonical(plan)) and
            receipt.get("current_candidate_private_sha256") ==
            plan["current_candidate_private_sha256"] and
            receipt.get("historical_ratification_sha256") ==
            plan["historical_ratification_sha256"] and
            receipt.get("no_gui_gate_sha256") == row["no_gui_gate_sha256"] and
            receipt.get("run_nonce_sha256") == row["run_nonce_sha256"] and
            receipt.get("official_final_tasks_admitted") == 0 and
            receipt.get("model_attempts") == 0 and
            receipt.get("service_state_restored_receipt") is True and
            type(receipt.get("worker_pid")) is int and
            type(receipt.get("refs")) is dict and
            set(receipt["refs"]) == REFS,
            "scale_case_receipt_identity_or_refs_invalid")
    initial = protocol.private_json(attempt / "intent.private.json")
    require(initial.get("schema") == case_path.INTENT_SCHEMA and
            initial.get("task_id") == row["task_id"] and
            initial.get("package_sha256") == row["package_sha256"] and
            initial.get("current_candidate_private_sha256") ==
            plan["current_candidate_private_sha256"] and
            initial.get("epoch_source_freeze_sha256") ==
            row["epoch_source_freeze_sha256"] and
            initial.get("no_gui_gate_sha256") == row["no_gui_gate_sha256"] and
            initial.get("run_nonce_sha256") == row["run_nonce_sha256"],
            "epoch_case_initial_intent_not_bound")
    start, finish = _time(receipt.get("started_at_utc")), _time(
        receipt.get("finished_at_utc"))
    stamps = receipt.get("stage_timestamps")
    require(type(stamps) is dict and set(stamps) == set(controller.STAGES),
            "scale_case_stage_times_missing")
    ordered = [_time(stamps[key]) for key in controller.STAGES]
    require(start <= ordered[0] and
            all(left <= right for left, right in zip(ordered, ordered[1:])) and
            ordered[-1] <= finish and
            receipt.get("lease_operation") == controller.LEASE_OPERATION and
            _lease(worker_private / "worker-lease-events.jsonl",
                   receipt["worker_pid"], start, finish),
            "scale_case_worker_lease_or_phase_order_invalid")
    refs = receipt["refs"]
    artifacts = {}
    for name, ref in refs.items():
        if name.endswith("frame"):
            pilot._ref(attempt, ref, image=True)
        else:
            artifacts[name] = pilot._artifact_json(attempt, ref)
    trace = artifacts["gui_trace"]
    positive_actions, negative_actions, rejected = _action_chain(
        attempt, trace, row, require_exact_return_guard=False,
        require_pinned_profile=True)
    parse_result = parse_audit.audit_trace(attempt, trace, row)
    require(parse_result["actions"] == positive_actions + negative_actions,
            "parse_border_v5_action_count_unbound")
    require(refs["source_frame"]["sha256"] in {
        action["frame"]["sha256"] for action in trace["actions"]},
        "scale_source_not_in_native_gui_trace")
    source = artifacts["source_evidence"]
    require(source.get("schema") ==
            "envloop-odoo-v066-native-source-presentation-v1" and
            source.get("task_id") == row["task_id"] and
            source.get("source_asset_sha256") == row["source_asset_sha256"] and
            source.get("source_label") == row["source_label"] and
            source.get("source_frame_sha256") == refs["source_frame"]["sha256"] and
            source.get("source_opened_via_v066_gui_actions") is True,
            "scale_source_gui_presentation_unbound")
    checkpoint = plan["checkpoint"]
    for name in ("pre_restore", "post_restore"):
        reset = artifacts[name]
        require(reset.get("status") == "restored" and
                reset.get("business_snapshot_equal") is True and
                reset.get("physical_filestore_equal_before_web_restart") is True and
                reset.get("db_sha256") == checkpoint["db_sha256"] and
                reset.get("filestore_sha256") == checkpoint["filestore_sha256"],
                "scale_case_full_physical_reset_invalid")
    baseline_path = worker_private / "baseline_snapshot.json"
    baseline = protocol.private_json(baseline_path)
    frozen_path = worker_private / "baseline-filestore-manifest.json"
    frozen = protocol.private_json(frozen_path)
    require(protocol.digest(baseline_path.read_bytes()) ==
            checkpoint["baseline_snapshot_sha256"] and
            protocol.digest(frozen_path.read_bytes()) ==
            checkpoint["baseline_filestore_manifest_sha256"] and
            artifacts["baseline_sql"] == baseline and
            artifacts["restored_sql"] == baseline,
            "scale_case_baseline_or_restored_sql_changed")
    world = protocol.private_json(worker_private / "partition_cases.json")
    cases = [case for family in protocol.FAMILIES
             for case in world["cases"][family]
             if case["id"] == row["task_id"]]
    require(len(cases) == 1 and cases[0]["family"] == row["family"] and
            protocol.digest(source_asset(cases[0], world)) ==
            row["source_asset_sha256"],
            "scale_case_world_source_changed")
    gold = protocol.private_json(worker_private / GOLD_FILES[row["family"]])
    require(row["task_id"] in gold, "scale_case_gold_missing")
    target = gold[row["task_id"]]
    protected_count = 3 * protocol.SPLITS[plan["split"]][2] + 1
    require(len({item["checksum"] for item in baseline["attachments"]}) ==
            protected_count,
            "scale_case_protected_attachment_count_changed")
    source_paths = {str(item["id"]):
                    f"{item['checksum'][:2]}/{item['checksum']}"
                    for item in baseline["attachments"]}
    baseline_score = pilot._pure_score(
        row["family"], row["task_id"], target,
        baseline, baseline, frozen, frozen, source_paths)
    positive = pilot._pure_score(
        row["family"], row["task_id"], target,
        baseline, artifacts["positive_sql"], frozen,
        artifacts["positive_filestore"],
        artifacts["positive_store_paths"])
    negative = pilot._pure_score(
        row["family"], row["task_id"], target,
        baseline, artifacts["negative_sql"], frozen,
        artifacts["negative_filestore"],
        artifacts["negative_store_paths"])
    from enterprise_fallback.odoo18.sweep_partition import NEGATIVE_CODES
    from enterprise_fallback.odoo18.verify import protected_source_file_differences
    require(baseline_score["reward"] == 0.0 and
            positive["reward"] == 1.0 and
            positive["difference_codes"] == [] and
            negative["reward"] == 0.0 and
            negative["difference_codes"] ==
            [NEGATIVE_CODES[row["family"]]] and
            positive["protected_source_files_checked"] == protected_count and
            negative["protected_source_files_checked"] == protected_count and
            protected_source_file_differences(
                baseline, frozen, artifacts["restored_filestore"]) == [] and
            artifacts["positive_sql"] != baseline and
            artifacts["negative_sql"] != artifacts["positive_sql"],
            "scale_case_independent_saved_state_or_negative_invalid")
    return {
        "schema": EPOCH_CASE_AUDIT_SCHEMA,
        "status": "parse_border_v5_raw_gui_semantics_verified_source_visual_review_pending",
        "split": plan["split"],
        "family": row["family"],
        "task_id": row["task_id"],
        "package_sha256": row["package_sha256"],
        "private_attempt_sha256": protocol.digest(raw_path.read_bytes()),
        "positive_gui_actions": positive_actions,
        "negative_gui_actions": negative_actions,
        "pre_intent_rejections": rejected,
        "pinned_border_parse_exceptions":
            parse_result["pinned_border_parse_exceptions"],
        "independent_baseline_reward": baseline_score["reward"],
        "independent_positive_reward": positive["reward"],
        "independent_wrong_object_reward": negative["reward"],
        "protected_source_files_checked": protected_count,
        "full_pre_web_filestore_reset_exact": True,
        "protected_post_web_source_bytes_equal": True,
        "source_visual_review_pending": True,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def audit_one_batch(*, worker_dir: Path, historical_root: Path,
                    prior_private_plan: Path, prior_public_plan: Path,
                    private_plan: Path, public_plan: Path,
                    old_private_plan: Path, old_public_plan: Path) -> dict:
    """Reopen a one-case batch only after its lease and GUI have ended."""
    from tools import odoo_v066_parse_border_one_selection_v5 as runner
    worker = Path(worker_dir).resolve()
    source.validate()
    plan_v5.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan,
        private_plan=private_plan, public_plan=public_plan,
        allow_current_run=True)
    plan = protocol.private_json(private_plan)
    worker_private = protocol._worker_split(worker, "selection")
    run_dir = (worker_private / "v066_scale_controls" /
               plan["fresh_run_directory_name"])
    protocol._private(run_dir, directory=True)
    gate = gate_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        private_plan=private_plan, public_plan=public_plan,
        old_private_plan=old_private_plan, old_public_plan=old_public_plan,
        allow_current_run=True)
    batch_path = run_dir / "batch-intent.private.json"
    batch = protocol.private_json(batch_path)
    batch_sha = epoch.digest(batch_path)
    require(batch.get("schema") == runner.BATCH_SCHEMA and
            batch.get("status") ==
            "durable_before_first_original_odoo_service_call" and
            batch.get("split") == "selection" and
            batch.get("private_plan_sha256") == epoch.digest(private_plan) and
            batch.get("public_plan_sha256") == epoch.digest(public_plan) and
            batch.get("current_candidate_private_sha256") ==
            plan["current_candidate_private_sha256"] and
            batch.get("historical_ratification_sha256") ==
            plan["historical_ratification_sha256"] and
            batch.get("source_freeze_sha256") ==
            plan["source_freeze_sha256"] and
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
            "epoch_batch_intent_or_gate_unbound")
    journal_path = run_dir / "journal.private.jsonl"
    events, _tail, count = controller.read_journal(journal_path)
    first = plan["tasks"][0]
    require(count == 2 and
            [event.get("event") for event in events] ==
            ["case_started", "case_completed"] and
            all(event.get("ordinal") == 0 and
                event.get("task_id") == first["task_id"] and
                event.get("package_sha256") == first["package_sha256"] and
                event.get("attempt_dir") == "attempt-000" and
                event.get("run_intent_sha256") == batch_sha
                for event in events) and
            events[-1].get("attempt_receipt_sha256") ==
            epoch.digest(run_dir / "attempt-000/attempt.private.json"),
            "epoch_batch_journal_or_attempt_changed")
    row = dict(first)
    row.update({
        "epoch_source_freeze_sha256": source.digest(source.FREEZE),
        "no_gui_gate_sha256": gate["gate_sha256"],
        "run_nonce_sha256": protocol.digest(bytes.fromhex(
            plan["run_nonce_hex"])),
    })
    case_result = audit_current_case(
        plan=plan, row=row, attempt=run_dir / "attempt-000",
        worker_private=worker_private)
    require(case_result["independent_baseline_reward"] == 0.0 and
            case_result["independent_positive_reward"] == 1.0 and
            case_result["independent_wrong_object_reward"] == 0.0 and
            case_result["full_pre_web_filestore_reset_exact"] is True and
            case_result["source_visual_review_pending"] is True,
            "epoch_batch_saved_semantics_not_qualified")
    return {
        "schema": "envloop-odoo-v066-parse-border-one-selection-audit-v5",
        "status": "one_raw_parse_border_control_independently_verified_visual_review_pending",
        "private_plan_sha256": epoch.digest(private_plan),
        "batch_intent_sha256": batch_sha,
        "journal_sha256": epoch.digest(journal_path),
        "attempt_receipt_sha256": epoch.digest(
            run_dir / "attempt-000/attempt.private.json"),
        "current_candidate_private_sha256":
            plan["current_candidate_private_sha256"],
        "retained_terminal_selection_failures": 4,
        "pinned_border_parse_exceptions":
            case_result["pinned_border_parse_exceptions"],
        "independently_verified_raw_selection_controls": 1,
        "source_visual_reviews_pending": 1,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
