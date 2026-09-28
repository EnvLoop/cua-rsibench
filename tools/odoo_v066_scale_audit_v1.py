"""Read-only independent Odoo v0.6.6 selection/final GUI-control audit.

Reopens raw evaluator-private screenshots/actions, SELECT-only SQL snapshots,
physical source files, cold restores and worker leases. Derives positive and
wrong-object negative results through the pure frozen verifier functions. It
never calls Docker/browser/provider/model and never admits an official task.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import stat

from enterprise_fallback.odoo18 import v066_requalification_pilot as pilot
from enterprise_fallback.odoo18.partition_factory import source_asset
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_scale_controller_v1 as controller


AUDIT_SCHEMA = "envloop-odoo-v066-scale-gui-control-audit-v1"
CASE_AUDIT_SCHEMA = "envloop-odoo-v066-scale-case-independent-audit-v1"
REFS = frozenset({
    "pre_restore", "baseline_sql", "source_frame", "source_evidence",
    "positive_reload_frame", "positive_sql", "positive_filestore",
    "positive_store_paths", "negative_reload_frame", "negative_sql",
    "negative_filestore", "negative_store_paths", "post_restore",
    "restored_sql", "restored_filestore", "gui_trace",
})
GOLD_FILES = {"purchase": "development_gold.json",
              "inventory": "replenishment_gold.json",
              "sales": "sales_gold.json", "crm": "crm_gold.json"}


class ScaleAuditError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ScaleAuditError(reason)


def _time(raw: object) -> datetime:
    try:
        value = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ScaleAuditError("scale_audit_time_invalid") from None
    require(value.tzinfo is not None, "scale_audit_time_invalid")
    return value


def _lease(events_path: Path, pid: int, start: datetime,
           finish: datetime) -> bool:
    protocol._private(events_path)
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    for index, event in enumerate(events):
        if (event.get("operation") != controller.LEASE_OPERATION or
                event.get("event") != "acquired" or event.get("pid") != pid or
                _time(event.get("at_utc")) > start):
            continue
        release = next((later for later in events[index + 1:]
                        if later.get("operation") == controller.LEASE_OPERATION and
                        later.get("event") == "released" and
                        later.get("pid") == pid), None)
        if release is None or _time(release.get("at_utc")) < finish:
            continue
        if any(start <= _time(other.get("at_utc")) <= finish and
               (other.get("pid") != pid or
                other.get("operation") != controller.LEASE_OPERATION)
               for other in events):
            return False
        return True
    return False


def _action_chain(attempt: Path, trace: dict, row: dict) -> tuple[int, int, int]:
    actions = trace.get("actions")
    rejections = trace.get("pre_intent_rejections")
    require(trace.get("schema") == controller.TRACE_SCHEMA and
            trace.get("task_binding_sha256") == row["task_binding_sha256"] and
            trace.get("sft_examples_written") == 0 and
            not (attempt / "sft_candidate.private.json").exists() and
            type(actions) is list and 2 <= len(actions) <= 90 and
            type(rejections) is list,
            "scale_gui_trace_or_holdout_boundary_invalid")
    positive = negative = 0
    frame_hashes = set()
    result_files = sorted((attempt / "actions").glob("*-result.private.json"))
    require(len(result_files) == len(actions),
            "scale_action_result_count_changed")
    results = [protocol.private_json(path) for path in result_files]
    for step, (action, result) in enumerate(zip(actions, results)):
        require(action.get("step") == step and
                action.get("phase") in ("positive", "negative") and
                result.get("step") == step and
                result.get("phase") == action["phase"] and
                result.get("contract_receipt") == action.get("contract_receipt"),
                "scale_action_trace_result_mismatch")
        _, frame_raw = pilot._ref(attempt, action["frame"], image=True)
        frame_sha = protocol.digest(frame_raw)
        frame_hashes.add(frame_sha)
        contract = action["contract_receipt"]
        require(contract.get("action_profile") ==
                "scale-action-profile-v0.6.6" and
                contract.get("task_binding_sha256") == row["package_sha256"] and
                contract.get("task_id_sha256") ==
                protocol.digest(row["task_id"].encode()) and
                contract.get("step") == step and
                contract.get("screenshot", {}).get("sha256") == frame_sha and
                contract.get("screenshot", {}).get("width") == 1440 and
                contract.get("screenshot", {}).get("height") == 1000 and
                contract.get("error_code") is None,
                "scale_current_frame_contract_receipt_invalid")
        intent_sha = result.get("intent_sha256")
        candidates = sorted((attempt / "actions").glob(
            f"step-{step:03d}*-intent.private.json"))
        require(len(candidates) == 1 and
                protocol.digest(candidates[0].read_bytes()) == intent_sha,
                "scale_pre_dispatch_intent_missing_or_ambiguous")
        intent = protocol.private_json(candidates[0])
        require(intent.get("phase") == action["phase"] and
                intent.get("step") == step and
                intent.get("task_id") == row["task_id"] and
                intent.get("task_binding_sha256") ==
                row["package_sha256"] and
                intent.get("frame_sha256") == frame_sha and
                intent.get("normalized_action") == result.get("applied_action") and
                intent.get("dispatch_state") ==
                "intent_durable_before_gui_action",
                "scale_normalized_action_not_bound_to_intent")
        if action["phase"] == "positive":
            require(negative == 0, "scale_action_phase_order_invalid")
            positive += 1
        else:
            negative += 1
    for reference in rejections:
        rejected = pilot._artifact_json(attempt, reference)
        require(rejected.get("schema") ==
                "envloop-odoo-v066-pre-intent-frame-rejection-v1" and
                rejected.get("error_code") == "stale_frame" and
                rejected.get("pre_dispatch_intent_created") is False and
                rejected.get("gui_action_dispatched") is False,
                "scale_pre_intent_rejection_invalid")
        pilot._ref(attempt, rejected["observed_frame_ref"], image=True)
        pilot._ref(attempt, rejected["assistant_action_ref"])
    require(positive > 0 and negative > 0,
            "scale_positive_or_negative_gui_phase_missing")
    return positive, negative, len(rejections)


def audit_case(*, plan: dict, row: dict, attempt: Path,
               worker_private: Path) -> dict:
    attempt = Path(attempt)
    protocol._private(attempt, directory=True)
    raw_path = attempt / "attempt.private.json"
    receipt = protocol.private_json(raw_path)
    require(receipt.get("schema") == protocol.CASE_SCHEMA and
            receipt.get("status") == controller.CASE_STATUS and
            receipt.get("split") == plan["split"] and
            receipt.get("family") == row["family"] and
            receipt.get("task_id") == row["task_id"] and
            receipt.get("package_sha256") == row["package_sha256"] and
            receipt.get("task_binding_sha256") ==
            row["task_binding_sha256"] and
            receipt.get("source_freeze_sha256") ==
            plan["source_freeze_sha256"] and
            receipt.get("plan_sha256") == protocol.digest(protocol.canonical(plan)) and
            receipt.get("ratification_sha256") == protocol.RATIFICATION_SHA and
            receipt.get("official_final_tasks_admitted") == 0 and
            receipt.get("model_attempts") == 0 and
            receipt.get("service_state_restored_receipt") is True and
            type(receipt.get("worker_pid")) is int and
            type(receipt.get("refs")) is dict and
            set(receipt["refs"]) == REFS,
            "scale_case_receipt_identity_or_refs_invalid")
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
        attempt, trace, row)
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
        "schema": CASE_AUDIT_SCHEMA,
        "status": "current_profile_raw_gui_semantics_verified_source_visual_review_pending",
        "split": plan["split"],
        "family": row["family"],
        "task_id": row["task_id"],
        "package_sha256": row["package_sha256"],
        "private_attempt_sha256": protocol.digest(raw_path.read_bytes()),
        "positive_gui_actions": positive_actions,
        "negative_gui_actions": negative_actions,
        "pre_intent_rejections": rejected,
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


def audit_batch(*, split: str, worker_dir: Path, private_plan_path: Path,
                public_plan_path: Path, source_freeze_path: Path,
                run_dir: Path, adoption_path: Path | None = None,
                old_private_plan_path: Path | None = None,
                old_source_freeze_path: Path | None = None,
                incident_public_path: Path | None = None) -> tuple[dict, dict]:
    plan = protocol.validate_split_plan(
        split=split, private_path=private_plan_path,
        public_path=public_plan_path,
        source_freeze_path=source_freeze_path)
    worker = Path(worker_dir).resolve()
    private = protocol._worker_split(worker, split)
    run_dir = Path(run_dir)
    protocol._private(run_dir, directory=True)
    intent = protocol.private_json(run_dir / "batch-intent.private.json")
    require(intent.get("schema") == protocol.BATCH_SCHEMA and
            intent.get("split") == split and
            intent.get("expected_case_count") == plan["task_count"],
            "scale_batch_intent_unbound")
    old_plan = None
    current_binding = (intent.get("private_plan_sha256") ==
                       protocol.digest(private_plan_path.read_bytes()) and
                       intent.get("source_freeze_sha256") ==
                       protocol.digest(source_freeze_path.read_bytes()))
    if not current_binding:
        adoption, old_plan = controller._old_plan_adoption(
            adoption_path=adoption_path,
            old_private_plan_path=old_private_plan_path,
            old_source_freeze_path=old_source_freeze_path,
            incident_public_path=incident_public_path,
            current_plan=plan,
            current_source_freeze_path=source_freeze_path)
        require(intent.get("private_plan_sha256") ==
                adoption["old_private_plan_sha256"] and
                intent.get("source_freeze_sha256") ==
                adoption["old_source_freeze_sha256"],
                "scale_batch_intent_old_source_not_adopted")
    completed = controller.next_case_index(run_dir, plan)
    journal_rows, _, _ = controller.read_journal(
        run_dir / "journal.private.jsonl")
    reclassified = {event["ordinal"] for event in journal_rows
                    if event.get("event") ==
                    "case_reclassified_after_lease_release"}
    if reclassified:
        controller.verify_reclassified_current_baseline(run_dir, private)
    rows = []
    for ordinal in range(completed):
        selected = old_plan if ordinal in reclassified else plan
        require(selected is not None,
                "scale_reclassified_case_old_plan_missing")
        rows.append(audit_case(
            plan=selected, row=selected["tasks"][ordinal],
            attempt=run_dir / f"attempt-{ordinal:03d}",
            worker_private=private))
    counts = Counter(row["family"] for row in rows)
    raw_report = {
        "schema": AUDIT_SCHEMA,
        "status": ("all_raw_split_controls_semantically_verified"
                   if completed == plan["task_count"] else
                   "raw_split_controls_partial"),
        "split": split,
        "source_freeze_sha256": plan["source_freeze_sha256"],
        "private_plan_sha256": protocol.digest(private_plan_path.read_bytes()),
        "batch_intent_sha256": protocol.digest(
            (run_dir / "batch-intent.private.json").read_bytes()),
        "journal_sha256": protocol.digest(
            (run_dir / "journal.private.jsonl").read_bytes())
            if (run_dir / "journal.private.jsonl").is_file() else None,
        "completed_independently_verified_cases": completed,
        "expected_case_count": plan["task_count"],
        "verified_family_counts": dict(counts),
        "per_id": rows,
        "source_visual_reviews_pending": completed,
        "reclassified_without_gui_replay_count": len(reclassified),
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public = {
        "schema": "envloop-odoo-v066-scale-gui-control-audit-public-v1",
        "status": raw_report["status"],
        "split": split,
        "source_freeze_sha256": plan["source_freeze_sha256"],
        "private_audit_sha256": protocol.digest(protocol.canonical(raw_report)),
        "completed_independently_verified_cases": completed,
        "expected_case_count": plan["task_count"],
        "verified_family_counts": dict(counts),
        "source_visual_reviews_pending": completed,
        "reclassified_without_gui_replay_count": len(reclassified),
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    return raw_report, public


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(protocol.SPLITS), required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--adoption-private", type=Path)
    parser.add_argument("--old-private-plan", type=Path)
    parser.add_argument("--old-source-freeze", type=Path)
    parser.add_argument("--incident-public", type=Path)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        private, public = audit_batch(
            split=args.split, worker_dir=args.worker_dir,
            private_plan_path=args.private_plan,
            public_plan_path=args.public_plan,
            source_freeze_path=args.source_freeze,
            run_dir=args.run_dir,
            adoption_path=args.adoption_private,
            old_private_plan_path=args.old_private_plan,
            old_source_freeze_path=args.old_source_freeze,
            incident_public_path=args.incident_public)
        protocol.write_new(args.private_out, private=True, value=private)
        protocol.write_new(args.public_out, private=False, value=public)
    except Exception as error:
        print(json.dumps({"schema": AUDIT_SCHEMA,
                          "status": "raw_control_audit_refused",
                          "error_type": type(error).__name__,
                          "official_final_tasks_admitted": 0,
                          "model_attempts": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(public, sort_keys=True))
