"""Read-only audit of the retained second selection GUI control failure.

The old and new attempts remain private and immutable. This source-bound
auditor verifies the new attempt's action/guard chain, native source frame,
post-intent failure, saved reset, worker lease, and separate batch identity.
It never authorizes replay or an official/model result.
"""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from PIL import Image

from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-selection-post-intent-stale-incident-v1"
FROZEN_SOURCE_REVISION = "037bc5d69f6dcd41cf84988e6e47fe45d4ad29b5"
FROZEN_SOURCE_FREEZE_SHA256 = "cf1344cf5a8640cec013ec982000b20852a78f6a611e1e9c2b3e8a499ee087ee"
PIXELS = {(41, 419), (132, 419)}
FROM_RGB = (235, 237, 239)
TO_RGB = (235, 237, 240)


class PostIntentAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PostIntentAuditError(code)


def _sha(path: Path) -> str:
    protocol._private(path)
    return sha256(path.read_bytes()).hexdigest()


def _ref(attempt: Path, reference: dict) -> Path:
    require(type(reference) is dict and
            type(reference.get("path")) is str and
            type(reference.get("sha256")) is str and
            not Path(reference["path"]).is_absolute() and
            ".." not in Path(reference["path"]).parts,
            "post_intent_reference_unsafe")
    path = attempt / reference["path"]
    require(_sha(path) == reference["sha256"],
            "post_intent_reference_hash_changed")
    return path


def _two_pinned_pixels(observed_path: Path, current_path: Path) -> bool:
    with Image.open(observed_path) as source, Image.open(current_path) as now:
        if (source.format != "PNG" or now.format != "PNG" or
                source.mode != "RGB" or now.mode != "RGB"):
            return False
        a, b = source.copy(), now.copy()
    if a.size != b.size or a.size != (1440, 1000):
        return False
    changed = {}
    for y in range(a.height):
        for x in range(a.width):
            first, second = a.getpixel((x, y)), b.getpixel((x, y))
            if first != second:
                changed[(x, y)] = (first, second)
                if len(changed) > 2:
                    return False
    return (set(changed) == PIXELS and
            all(pair == (FROM_RGB, TO_RGB) for pair in changed.values()))


def _lease(worker_private: Path, intent_path: Path,
           failure_path: Path) -> str:
    events_path = worker_private / "worker-lease-events.jsonl"
    protocol._private(events_path)
    rows = [json.loads(line) for line in events_path.read_text().splitlines()]
    started = datetime.fromisoformat(
        protocol.private_json(intent_path)["started_at_utc"])
    failed = datetime.fromtimestamp(failure_path.stat().st_mtime, timezone.utc)
    pairs = []
    for index, row in enumerate(rows):
        if row.get("event") != "acquired" or row.get("operation") != \
                controller.LEASE_OPERATION:
            continue
        acquire = datetime.fromisoformat(row["at_utc"])
        if acquire > started:
            continue
        release = next((later for later in rows[index + 1:]
                        if later.get("event") == "released" and
                        later.get("operation") == controller.LEASE_OPERATION and
                        later.get("pid") == row.get("pid")), None)
        if release and datetime.fromisoformat(release["at_utc"]) >= failed:
            pairs.append((acquire, release))
    require(len(pairs) == 1,
            "post_intent_worker_lease_not_unique_or_unreleased")
    return _sha(events_path)


def _services_exited(worker: Path) -> bool:
    process = subprocess.run(
        ["docker", "compose", "--env-file", ".env", "ps", "--all",
         "--format", "json"], cwd=worker, check=True,
        capture_output=True, text=True)
    rows = [json.loads(line) for line in process.stdout.splitlines() if line]
    return {row.get("Service") for row in rows} == {"db", "web"} and all(
        row.get("State") == "exited" and row.get("ExitCode") == 0
        for row in rows)


def _locks_free(worker_private: Path) -> bool:
    for path in (worker_private / "worker-operation.lock",
                 worker_private / "v066_scale_controls" /
                 "scale-run-coordinator.lock"):
        protocol._private(path)
        descriptor = os.open(path, os.O_RDONLY)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        finally:
            os.close(descriptor)
    return True


def _historical_plan(*, repo: Path, private_plan_path: Path,
                     public_plan_path: Path,
                     source_freeze_path: Path) -> dict:
    frozen = protocol.public_json(source_freeze_path)
    require(protocol.digest(source_freeze_path.read_bytes()) ==
            FROZEN_SOURCE_FREEZE_SHA256 and
            frozen.get("schema") == protocol.SOURCE_FREEZE_SCHEMA and
            frozen.get("status") ==
            "frozen_after_selection_blank_compose_service_fix" and
            frozen.get("ratification_sha256") == protocol.RATIFICATION_SHA and
            frozen.get("official_final_tasks_admitted") == 0 and
            frozen.get("model_attempts") == 0,
            "post_intent_historical_source_freeze_changed")
    for relative, expected in frozen["source_sha256s"].items():
        blob = subprocess.run(
            ["git", "show", f"{FROZEN_SOURCE_REVISION}:{relative}"],
            cwd=repo, capture_output=True, check=True).stdout
        require(protocol.digest(blob) == expected,
                "post_intent_frozen_source_blob_changed")
    plan = protocol.private_json(private_plan_path)
    public = protocol.public_json(public_plan_path)
    require(plan.get("schema") == protocol.PRIVATE_PLAN_SCHEMA and
            plan.get("split") == "selection" and
            plan.get("task_count") == 20 and
            len(plan.get("tasks", [])) == 20 and
            len({row["task_id"] for row in plan["tasks"]}) == 20 and
            plan.get("source_freeze_sha256") ==
            FROZEN_SOURCE_FREEZE_SHA256 and
            plan.get("source_sha256s") == frozen["source_sha256s"] and
            plan.get("frame_guard_amendment") ==
            protocol.EXACT_RETURN_AMENDMENT and
            public.get("private_plan_sha256") == _sha(private_plan_path) and
            public.get("candidate_count") == 20 and
            public.get("official_final_tasks_admitted") == 0,
            "post_intent_historical_plan_changed")
    return plan


def audit(*, repo: Path, worker: Path, run_dir: Path, old_run_dir: Path,
          private_plan_path: Path, public_plan_path: Path,
          source_freeze_path: Path, incident_public_path: Path,
          verify_services: bool = False) -> dict:
    worker = Path(worker).resolve()
    private = protocol._worker_split(worker, "selection")
    plan = _historical_plan(
        repo=Path(repo).resolve(), private_plan_path=private_plan_path,
        public_plan_path=public_plan_path,
        source_freeze_path=source_freeze_path)
    protocol._private(run_dir, directory=True)
    require(run_dir.parent.resolve() ==
            (private / "v066_scale_controls").resolve() and
            run_dir.resolve() != old_run_dir.resolve(),
            "post_intent_new_run_directory_invalid")
    batch_path = run_dir / "batch-intent.private.json"
    batch = protocol.private_json(batch_path)
    require(batch.get("schema") == protocol.BATCH_SCHEMA and
            batch.get("split") == "selection" and
            batch.get("private_plan_sha256") ==
            _sha(private_plan_path) and
            batch.get("source_freeze_sha256") ==
            protocol.digest(source_freeze_path.read_bytes()) and
            batch.get("expected_case_count") == 20 and
            batch.get("official_final_tasks_admitted") == 0 and
            batch.get("model_attempts") == 0,
            "post_intent_batch_source_or_count_unbound")
    independent._selection_retry_gate_independent(
        worker_private=private, plan=plan, batch_intent=batch,
        private_plan_path=private_plan_path,
        source_freeze_path=source_freeze_path,
        incident_public_path=incident_public_path,
        old_run_dir=old_run_dir)
    journal_path = run_dir / "journal.private.jsonl"
    rows, tail, count = controller.read_journal(journal_path)
    first = plan["tasks"][0]
    require(count == 2 and
            [row.get("event") for row in rows] ==
            ["case_started", "case_failed"] and
            all(row.get("ordinal") == 0 and
                row.get("task_id") == first["task_id"] and
                row.get("package_sha256") == first["package_sha256"] and
                row.get("attempt_dir") == "attempt-000" for row in rows),
            "post_intent_journal_chain_changed")
    attempt = run_dir / "attempt-000"
    protocol._private(attempt, directory=True)
    intent_path = attempt / "intent.private.json"
    intent = protocol.private_json(intent_path)
    failure_path = attempt / "failure.private.json"
    failure = protocol.private_json(failure_path)
    require(intent.get("status") ==
            "durable_before_first_docker_or_gui_action" and
            intent.get("task_id") == first["task_id"] and
            intent.get("package_sha256") == first["package_sha256"] and
            intent.get("source_freeze_sha256") ==
            plan["source_freeze_sha256"] and
            failure == {
                "schema": protocol.CASE_SCHEMA,
                "status": "failed_preserve_original_attempt_manual_review_required",
                "stage": "positive_gui", "error_type": "ContractError",
                "error_code": "stale_frame", "reset_exact": True,
                "services_restored": True,
                "official_final_tasks_admitted": 0,
                "model_attempts": 0,
            } and
            not (attempt / "attempt.private.json").exists() and
            not (attempt / "positive_sql.json").exists() and
            not (attempt / "negative_sql.json").exists(),
            "post_intent_failure_phase_or_scope_changed")
    trace_path = attempt / "gui_trace.json"
    trace = protocol.private_json(trace_path)
    actions = trace.get("actions")
    guards = trace.get("exact_return_guard_samples")
    require(trace.get("schema") == controller.TRACE_SCHEMA and
            trace.get("task_binding_sha256") ==
            first["task_binding_sha256"] and
            trace.get("sft_examples_written") == 0 and
            trace.get("pre_intent_rejections") == [] and
            type(actions) is list and len(actions) == 8 and
            type(guards) is list and len(guards) == 23,
            "post_intent_trace_counts_or_boundary_changed")
    for step, action in enumerate(actions):
        frame = _ref(attempt, action["frame"])
        intent_file = attempt / "actions" / f"step-{step:03d}-intent.private.json"
        result_file = attempt / "actions" / f"step-{step:03d}-result.private.json"
        saved_intent = protocol.private_json(intent_file)
        result = protocol.private_json(result_file)
        require(action.get("step") == step and
                action.get("phase") == "positive" and
                saved_intent.get("step") == step and
                saved_intent.get("phase") == "positive" and
                saved_intent.get("dispatch_state") ==
                "intent_durable_before_gui_action" and
                saved_intent.get("frame_sha256") == _sha(frame) and
                result.get("intent_sha256") == _sha(intent_file) and
                result.get("applied_action") ==
                saved_intent.get("normalized_action") and
                result.get("contract_receipt") ==
                action.get("contract_receipt") and
                action.get("contract_receipt", {}).get("screenshot", {}).get(
                    "sha256") == _sha(frame),
                "post_intent_completed_action_chain_changed")
        parse, dispatch = guards[2 * step: 2 * step + 2]
        for stage, sample in (("parse", parse), ("dispatch", dispatch)):
            require(sample.get("sampled_frame_ref", {}).get("path") ==
                    f"frames/guard-{2 * step + (stage == 'dispatch'):04d}.png",
                    "post_intent_guard_sample_path_changed")
            sample_file = _ref(attempt, sample["sampled_frame_ref"])
            require(sample.get("step") == step and
                    sample.get("stage") == stage and
                    sample.get("sample") == 0 and
                    sample.get("classification") == "exact_return" and
                    sample.get("observed_frame_sha256") == _sha(frame) and
                    _sha(sample_file) == _sha(frame),
                    "post_intent_prior_action_not_exact_guarded")
    source = protocol.private_json(attempt / "source_evidence.json")
    require(source.get("schema") ==
            "envloop-odoo-v066-native-source-presentation-v1" and
            source.get("task_id") == first["task_id"] and
            source.get("source_asset_sha256") ==
            first["source_asset_sha256"] and
            source.get("source_label") == first["source_label"] and
            source.get("source_opened_via_v066_gui_actions") is True and
            source.get("source_frame_sha256") ==
            actions[5]["frame"]["sha256"],
            "post_intent_native_source_frame_unbound")
    step = 8
    step_frame = attempt / "frames/step-008.png"
    step_intent_path = attempt / "actions/step-008-intent.private.json"
    step_intent = protocol.private_json(step_intent_path)
    require(_sha(step_frame) == step_intent.get("frame_sha256") and
            step_intent.get("step") == step and
            step_intent.get("phase") == "positive" and
            step_intent.get("dispatch_state") ==
            "intent_durable_before_gui_action" and
            step_intent.get("normalized_action", {}).get("type") ==
            "double_click" and
            step_intent.get("normalized_action", {}).get("target") ==
            {"x": 508, "y": 479} and
            not (attempt / "actions/step-008-result.private.json").exists() and
            not (attempt / "actions/step-008-rejection.private.json").exists(),
            "post_intent_step_eight_dispatch_boundary_changed")
    parse = guards[16]
    require(parse.get("sampled_frame_ref", {}).get("path") ==
            "frames/guard-0016.png" and
            parse.get("step") == 8 and parse.get("stage") == "parse" and
            parse.get("sample") == 0 and
            parse.get("classification") == "exact_return" and
            parse.get("observed_frame_sha256") == _sha(step_frame) and
            _sha(_ref(attempt, parse["sampled_frame_ref"])) == _sha(step_frame),
            "post_intent_step_eight_parse_not_exact")
    alternate = None
    for index, sample in enumerate(guards[17:], start=17):
        require(sample.get("sampled_frame_ref", {}).get("path") ==
                f"frames/guard-{index:04d}.png",
                "post_intent_guard_sample_path_changed")
        sample_path = _ref(attempt, sample["sampled_frame_ref"])
        require(sample.get("step") == 8 and
                sample.get("stage") == "dispatch" and
                sample.get("sample") == index - 17 and
                sample.get("observed_frame_sha256") == _sha(step_frame) and
                sample.get("observed_frame_id_sha256") ==
                protocol.digest(step_intent["frame_id"].encode()) and
                sample.get("classification") ==
                "one_recurring_micro_raster_alternate" and
                _two_pinned_pixels(step_frame, sample_path),
                "post_intent_dispatch_sample_not_pinned_alternate")
        if alternate is None:
            alternate = _sha(sample_path)
        require(_sha(sample_path) == alternate,
                "post_intent_dispatch_third_frame_present")
    baseline = protocol.private_json(private / "baseline_snapshot.json")
    frozen = protocol.private_json(
        private / "baseline-filestore-manifest.json")
    require(protocol.private_json(attempt / "baseline_sql.json") == baseline and
            protocol.private_json(attempt / "restored_sql.json") == baseline and
            protocol.private_json(attempt / "restored_filestore.json") == frozen,
            "post_intent_saved_full_reset_not_exact")
    for name in ("pre_restore.json", "post_restore.json"):
        receipt = protocol.private_json(attempt / name)
        require(receipt.get("status") == "restored" and
                receipt.get("business_snapshot_equal") is True and
                receipt.get("physical_filestore_equal_before_web_restart")
                is True and
                receipt.get("db_sha256") == plan["checkpoint"]["db_sha256"] and
                receipt.get("filestore_sha256") ==
                plan["checkpoint"]["filestore_sha256"],
                "post_intent_restore_receipt_inexact")
    lease_sha = _lease(private, intent_path, failure_path)
    service_state = _services_exited(worker) if verify_services else None
    lock_state = _locks_free(private)
    require(lock_state, "post_intent_worker_or_coordinator_lock_busy")
    if verify_services:
        require(service_state is True,
                "post_intent_selection_services_not_exited")
    old_journal_sha = _sha(old_run_dir / "journal.private.jsonl")
    return {
        "schema": SCHEMA,
        "status": "post_intent_exact_return_exhausted_before_double_click_dispatch",
        "frozen_source_revision": FROZEN_SOURCE_REVISION,
        "source_freeze_sha256": protocol.digest(source_freeze_path.read_bytes()),
        "private_plan_sha256": _sha(private_plan_path),
        "batch_intent_sha256": _sha(batch_path),
        "journal_sha256": _sha(journal_path),
        "journal_tail_sha256": tail,
        "old_journal_sha256": old_journal_sha,
        "journal_payload_sha_reused_across_distinct_runs":
            old_journal_sha == _sha(journal_path),
        "separate_batch_intent_and_attempt_hashes_required_for_run_identity": True,
        "private_attempt_intent_sha256": _sha(intent_path),
        "private_failure_sha256": _sha(failure_path),
        "private_gui_trace_sha256": _sha(trace_path),
        "private_step_eight_intent_sha256": _sha(step_intent_path),
        "native_source_pdf_visible_in_gui": True,
        "completed_source_and_navigation_gui_actions": 8,
        "pre_intent_rejections": 0,
        "post_intent_dispatch_guard_samples": 6,
        "post_intent_mouse_action_dispatched": False,
        "post_intent_result_receipt_exists": False,
        "pinned_alternate_pixel_count": 2,
        "saved_sql_and_full_filestore_equal_frozen_baseline": True,
        "worker_lease_events_sha256": lease_sha,
        "worker_lease_acquired_and_released": True,
        "selection_services_exited_zero": service_state,
        "selection_worker_locks_free": lock_state,
        "old_and_new_failed_attempts_preserved": True,
        "automatic_replay_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--old-run-dir", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--incident-public", type=Path, required=True)
    parser.add_argument("--verify-services", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(
            repo=args.repo, worker=args.worker, run_dir=args.run_dir,
            old_run_dir=args.old_run_dir,
            private_plan_path=args.private_plan,
            public_plan_path=args.public_plan,
            source_freeze_path=args.source_freeze,
            incident_public_path=args.incident_public,
            verify_services=args.verify_services), sort_keys=True))
    except (PostIntentAuditError, protocol.ScaleProtocolError,
            controller.ScaleControlError,
            independent.ScaleAuditError) as error:
        parser.exit(2, str(error) + "\n")
