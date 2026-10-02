"""Read-only, source-bound audit of the retained first selection GUI failure.

This verifies the failed attempt, exact saved reset, and the two-pixel frame
flicker. It cannot reclassify the case or authorize a GUI replay. The public
result contains hashes and counters only; all task data stays in private files.
"""

from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from PIL import Image

from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-selection-exact-frame-flicker-incident-v1"
FROZEN_SOURCE_REVISION = "19d9ce9b1aaeca86266ec0d1bb18b3ef744c50ae"
EXPECTED_PIXEL_COORDINATES = {(41, 419), (132, 419)}


class SelectionIncidentError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise SelectionIncidentError(code)


def _sha(path: Path) -> str:
    protocol._private(path)
    return sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return protocol.private_json(path)


def _ref(attempt: Path, value: dict) -> Path:
    require(type(value) is dict and type(value.get("path")) is str and
            type(value.get("sha256")) is str and
            not Path(value["path"]).is_absolute() and
            ".." not in Path(value["path"]).parts,
            "incident_reference_unsafe")
    path = attempt / value["path"]
    require(_sha(path) == value["sha256"], "incident_reference_hash_changed")
    return path


def changed_pixels(left: Path, right: Path) -> dict[tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]]:
    with Image.open(left) as first, Image.open(right) as second:
        a, b = first.convert("RGB"), second.convert("RGB")
    require(a.size == b.size == (1440, 1000), "incident_frame_geometry_changed")
    return {(x, y): (a.getpixel((x, y)), b.getpixel((x, y)))
            for y in range(a.height) for x in range(a.width)
            if a.getpixel((x, y)) != b.getpixel((x, y))}


def audit_rejections(attempt: Path, trace: dict) -> tuple[int, int]:
    refs = trace.get("pre_intent_rejections")
    require(type(refs) is list and len(refs) == 3 and
            len(trace.get("actions", [])) == 3 and
            trace.get("sft_examples_written") == 0,
            "incident_trace_action_counts_changed")
    samples = []
    for index, ref in enumerate(refs):
        rejected = _json(_ref(attempt, ref))
        prefix = "step-003" + ("" if index == 0 else
                               f"-resample-{index:02d}")
        require(rejected.get("schema") ==
                "envloop-odoo-v066-pre-intent-frame-rejection-v1" and
                rejected.get("phase") == "positive" and
                rejected.get("step") == 3 and
                rejected.get("observation_attempt") == index and
                rejected.get("error_code") == "stale_frame" and
                rejected.get("pre_dispatch_intent_created") is False and
                rejected.get("gui_action_dispatched") is False and
                not (attempt / "actions" /
                     (prefix + "-intent.private.json")).exists() and
                not (attempt / "actions" /
                     (prefix + "-result.private.json")).exists(),
                "incident_rejection_not_pre_intent")
        observed = _ref(attempt, rejected["observed_frame_ref"])
        current = _ref(attempt, rejected["current_frame_ref"])
        action = json.loads(_ref(attempt,
                                 rejected["assistant_action_ref"]).read_text())
        require(action.get("type") == "click" and
                type(action.get("target")) is dict,
                "incident_rejected_action_changed")
        changes = changed_pixels(observed, current)
        require(set(changes) == EXPECTED_PIXEL_COORDINATES and
                all(a[:2] == b[:2] and abs(a[2] - b[2]) == 1
                    for a, b in changes.values()),
                "incident_stale_frame_not_two_pixel_flicker")
        samples.append(rejected)
    # Each resample captured the exact alternate image from the previous
    # pre-intent validation, so the record is a bounded A/B raster flicker.
    require(all(samples[i]["current_frame_ref"]["sha256"] ==
                samples[i + 1]["observed_frame_ref"]["sha256"]
                for i in range(2)), "incident_frame_sequence_changed")
    return len(refs), 2


def _free_lock(path: Path) -> bool:
    protocol._private(path)
    descriptor = os.open(path, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        finally:
            # Closing the descriptor releases the non-blocking read-only lock.
            pass
        return True
    finally:
        os.close(descriptor)


def _services_exited(worker: Path) -> bool:
    command = subprocess.run(
        ["docker", "compose", "--env-file", ".env", "ps", "--all",
         "--format", "json"], cwd=worker, check=True, capture_output=True,
        text=True)
    rows = [json.loads(line) for line in command.stdout.splitlines() if line]
    by_service = {row.get("Service"): row for row in rows}
    return set(by_service) == {"db", "web"} and all(
        row.get("State") == "exited" and row.get("ExitCode") == 0
        for row in by_service.values())


def audit(*, repo: Path, worker: Path, run_dir: Path,
          private_plan: Path, public_plan: Path, source_freeze: Path,
          verify_services: bool = False) -> dict:
    protocol._private(run_dir, directory=True)
    frozen = protocol.public_json(source_freeze)
    plan = _json(private_plan)
    public = protocol.public_json(public_plan)
    require(frozen.get("schema") == protocol.SOURCE_FREEZE_SCHEMA and
            frozen.get("status") ==
            "frozen_after_pre_result_lease_audit_timing_amendment" and
            plan.get("split") == "selection" and
            plan.get("task_count") == 20 and
            plan.get("source_freeze_sha256") ==
            protocol.digest(source_freeze.read_bytes()) and
            public.get("private_plan_sha256") == _sha(private_plan),
            "incident_frozen_selection_plan_unbound")
    for relative, expected in frozen["source_sha256s"].items():
        blob = subprocess.run(
            ["git", "show", f"{FROZEN_SOURCE_REVISION}:{relative}"],
            cwd=repo, capture_output=True, check=True).stdout
        require(protocol.digest(blob) == expected,
                "incident_historical_source_hash_changed")
    batch = _json(run_dir / "batch-intent.private.json")
    require(batch.get("split") == "selection" and
            batch.get("expected_case_count") == 20 and
            batch.get("private_plan_sha256") == _sha(private_plan) and
            batch.get("source_freeze_sha256") ==
            protocol.digest(source_freeze.read_bytes()) and
            batch.get("official_final_tasks_admitted") == 0 and
            batch.get("model_attempts") == 0,
            "incident_batch_intent_changed")
    rows, tail, count = controller.read_journal(
        run_dir / "journal.private.jsonl")
    first = plan["tasks"][0]
    require(count == 2 and
            [row.get("event") for row in rows] ==
            ["case_started", "case_failed"] and
            all(row.get("ordinal") == 0 and
                row.get("task_id") == first["task_id"] and
                row.get("package_sha256") == first["package_sha256"] and
                row.get("attempt_dir") == "attempt-000" for row in rows),
            "incident_journal_chain_changed")
    attempt = run_dir / "attempt-000"
    protocol._private(attempt, directory=True)
    intent = _json(attempt / "intent.private.json")
    failure = _json(attempt / "failure.private.json")
    require(intent.get("status") ==
            "durable_before_first_docker_or_gui_action" and
            intent.get("task_id") == first["task_id"] and
            intent.get("package_sha256") == first["package_sha256"] and
            failure == {
                "schema": protocol.CASE_SCHEMA,
                "status": "failed_preserve_original_attempt_manual_review_required",
                "stage": "source_gui", "error_type": "ContractError",
                "error_code": "stale_frame", "reset_exact": True,
                "services_restored": True,
                "official_final_tasks_admitted": 0, "model_attempts": 0,
            } and
            not (attempt / "attempt.private.json").exists() and
            not (attempt / "source_evidence.json").exists() and
            not (attempt / "positive_sql.json").exists() and
            not (attempt / "negative_sql.json").exists(),
            "incident_failed_before_saved_semantics_changed")
    trace = _json(attempt / "gui_trace.json")
    require(trace.get("task_binding_sha256") == first["task_binding_sha256"],
            "incident_trace_task_binding_changed")
    for step, row in enumerate(trace["actions"]):
        require(row.get("step") == step and row.get("phase") == "positive",
                "incident_successful_action_sequence_changed")
        frame = _ref(attempt, row["frame"])
        action = _json(attempt / "actions" /
                       f"step-{step:03d}-intent.private.json")
        result = _json(attempt / "actions" /
                       f"step-{step:03d}-result.private.json")
        require(action.get("normalized_action", {}).get("type") ==
                ("type", "key", "click")[step] and
                action.get("frame_sha256") == _sha(frame) and
                result.get("intent_sha256") == _sha(
                    attempt / "actions" /
                    f"step-{step:03d}-intent.private.json") and
                result.get("contract_receipt", {}).get("screenshot", {}).get(
                    "sha256") == _sha(frame),
                "incident_successful_action_not_dispatched")
    rejected, pixels = audit_rejections(attempt, trace)
    baseline = _json(worker / "private" / "baseline_snapshot.json")
    frozen_files = _json(worker / "private" /
                         "baseline-filestore-manifest.json")
    require(_json(attempt / "baseline_sql.json") == baseline and
            _json(attempt / "restored_sql.json") == baseline and
            _json(attempt / "restored_filestore.json") == frozen_files,
            "incident_saved_reset_not_frozen_baseline")
    for name in ("pre_restore.json", "post_restore.json"):
        receipt = _json(attempt / name)
        require(receipt.get("status") == "restored" and
                receipt.get("business_snapshot_equal") is True and
                receipt.get("physical_filestore_equal_before_web_restart")
                is True, "incident_restore_receipt_inexact")
    locks_free = all(_free_lock(path) for path in (
        worker / "private" / "worker-operation.lock",
        worker / "private" / "v066_scale_controls" /
        "scale-run-coordinator.lock"))
    require(locks_free, "incident_selection_worker_busy")
    exited = _services_exited(worker) if verify_services else None
    if verify_services:
        require(exited is True, "incident_service_state_not_exited")
    return {
        "schema": SCHEMA,
        "status": "failed_after_three_gui_navigation_actions_before_source_or_save",
        "old_source_revision": FROZEN_SOURCE_REVISION,
        "old_source_freeze_sha256": protocol.digest(source_freeze.read_bytes()),
        "private_plan_sha256": _sha(private_plan),
        "batch_intent_sha256": _sha(run_dir / "batch-intent.private.json"),
        "journal_sha256": _sha(run_dir / "journal.private.jsonl"),
        "journal_tail_sha256": tail,
        "private_failure_sha256": _sha(attempt / "failure.private.json"),
        "gui_trace_sha256": _sha(attempt / "gui_trace.json"),
        "successful_gui_actions": 3,
        "pre_intent_stale_frame_rejections": rejected,
        "differing_pixels_per_rejected_pair": pixels,
        "different_business_content_observed": False,
        "source_evidence_captured": False,
        "positive_or_negative_saved_state_captured": False,
        "saved_sql_and_full_filestore_equal_frozen_baseline": True,
        "selection_services_exited_zero": exited,
        "selection_worker_locks_free": locks_free,
        "old_failure_journal_retained": True,
        "replay_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--source-freeze", type=Path, required=True)
    parser.add_argument("--verify-services", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(**vars(args)), sort_keys=True))
    except (SelectionIncidentError, protocol.ScaleProtocolError,
            controller.ScaleControlError) as error:
        parser.exit(2, str(error) + "\n")
