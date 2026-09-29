"""Read-only audit of a completed prefix in a running fresh Desktop sweep."""

from __future__ import annotations

import json
from pathlib import Path

from .v066_day_rollover_reference import validate as validate_reference
from .v066_final_control_audit import _validate_trio
from .v066_final_freeze import digest
from .v066_scoped_profile_bridge import validate as validate_bridge
from .v066_scoped_profile_final_audit import _profile_receipt


def audit(*, candidate_root: Path, attempts_root: Path,
          run_journal: Path, first_count: int,
          original_root: Path, failed_root: Path,
          bridge_path: Path, runtime_freeze: Path,
          action_ratification: Path, reservation: Path,
          public_day_audit: Path, private_day_audit: Path,
          reference_path: Path, failed_private_stop: Path,
          failed_public_interruption: Path,
          private_map: Path, profile_private: Path,
          guest_public: Path, fair_public: Path) -> tuple[dict, dict]:
    if not 1 <= first_count <= 100:
        raise ValueError("Bounded completed-prefix audit required")
    validate_bridge(
        bridge_path=bridge_path, candidate_root=candidate_root,
        original_root=original_root, failed_root=failed_root,
        fresh_root=attempts_root, action_ratification=action_ratification,
        public_calibration=public_day_audit,
        private_calibration_audit=private_day_audit,
        scoped_reference=reference_path, runtime_freeze=runtime_freeze,
        new_lane_reservation=reservation,
        failed_private_stop=failed_private_stop,
        failed_public_interruption=failed_public_interruption,
        profile_private=profile_private, guest_public=guest_public,
        fair_public=fair_public)
    reference, reference_sha = validate_reference(
        path=reference_path, private_audit=private_day_audit,
        public_audit=public_day_audit)
    run_raw = run_journal.read_bytes()
    run = json.loads(run_raw)
    if (run.get("schema") != "cua-native-wdi-v066-final-rerun-private-v1" or
            run.get("plan", {}).get("candidate_final_count") != 100 or
            len(run.get("selected_private_task_ids", [])) != 100 or
            run.get("official_final_model_attempts") != 0 or
            run.get("official_final_admissions") != 0):
        raise ValueError("Running prospective 100-case journal changed")
    prefix = run["selected_private_task_ids"][:first_count]
    complete = {row["private_task_id"] for row in run["task_outcomes"]
                if row.get("status") == "provisional_trio_complete"}
    if not set(prefix) <= complete or len(prefix) != len(set(prefix)):
        raise ValueError("Requested first tasks are not complete trios")
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    rows = {row["task_id"]: row for row in inventory["tasks"]
            if row.get("split") == "final_candidate"}
    if len(rows) != 100 or not set(prefix) <= set(rows):
        raise ValueError("Completed prefix differs from candidate source")
    salt = json.loads(private_map.read_bytes()).get("variant_salt")
    if type(salt) is not str or len(salt) < 32:
        raise ValueError("Independent OOXML scorer salt absent")
    common = {"profile_sha": digest(profile_private.read_bytes()),
              "guest_sha": digest(guest_public.read_bytes()),
              "private_salt": salt,
              "ratification_sha": digest(action_ratification.read_bytes()),
              "reservation_sha": digest(reservation.read_bytes())}
    record = []
    sandbox_ids = set()
    for task_id in prefix:
        row = rows[task_id]
        fair = _validate_trio(candidate_root, attempts_root, row, **common)
        ids = _profile_receipt(
            candidate_root=candidate_root, attempts_root=attempts_root,
            task_id=task_id, workflow=row["workflow"],
            reference=reference, reference_sha=reference_sha,
            runtime_sha=digest(runtime_freeze.read_bytes()),
            bridge_sha=digest(bridge_path.read_bytes()))
        if any(item in sandbox_ids for item in ids):
            raise ValueError("Completed prefix reused an E2B guest")
        sandbox_ids.update(ids)
        record.append(fair)
    old_ids = {json.loads(path.read_bytes()).get("sandbox_id_sha256")
               for root in (original_root, failed_root)
               for path in root.glob("*/*/receipt.json")}
    if sandbox_ids & old_ids or len(sandbox_ids) != first_count * 3:
        raise ValueError("A fresh date-amended sandbox reused historical state")
    private = {
        "schema": "cua-native-wdi-v066-day-rollover-prefix-audit-private-v1",
        "status": "provisional_evaluator_controls_independently_reopened",
        "auditor_source_sha256": digest(Path(__file__).read_bytes()),
        "run_journal_snapshot_sha256": digest(run_raw),
        "bridge_sha256": digest(bridge_path.read_bytes()),
        "runtime_freeze_sha256": digest(runtime_freeze.read_bytes()),
        "completed_prefix": record,
        "distinct_fresh_sandbox_count": len(sandbox_ids),
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-day-rollover-prefix-audit-public-v1",
        "status": "provisional_controls_only_not_six_cell_admission",
        "candidate_final_count": 100,
        "independently_reopened_completed_trios": first_count,
        "positive_saved_artifacts_verified": first_count,
        "near_miss_saved_artifacts_rejected": first_count,
        "fresh_cold_resets_verified": first_count,
        "guest_calendar_bound_attempts": len(sandbox_ids),
        "distinct_fresh_sandboxes": len(sandbox_ids),
        "bridge_sha256": private["bridge_sha256"],
        "runtime_freeze_sha256": private["runtime_freeze_sha256"],
        "auditor_source_sha256": private["auditor_source_sha256"],
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
