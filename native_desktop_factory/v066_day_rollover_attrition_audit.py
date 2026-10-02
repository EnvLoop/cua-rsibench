"""Independent read-only Desktop acceptance and attrition audit.

The seven finished trios and later untouched-ID trios may be counted as
provisional evaluator controls. Two infrastructure-interrupted task IDs remain
quarantined. No model call or official final admission is inferred.
"""

from __future__ import annotations

import json
from pathlib import Path

from .v066_caret_full100_preflight import _read_only_storage
from .v066_day_rollover_reference import validate as validate_reference
from .v066_final_control_audit import _validate_trio
from .v066_final_freeze import digest
from .v066_scoped_profile_final_audit import _profile_receipt
from .v066_scoped_profile_final_controller import _existing_state, _final_rows


QUARANTINED = (7, 8)


def audit(*, candidate_root: Path, attempts_root: Path,
          old_run_journal: Path, reference_path: Path,
          private_day_audit: Path, public_day_audit: Path,
          private_map: Path, profile_private: Path,
          guest_public: Path, action_ratification: Path,
          reservation: Path, runtime_freeze: Path,
          bridge_path: Path, historical_roots: tuple[Path, ...]) -> tuple[dict, dict]:
    run_raw = old_run_journal.read_bytes()
    run = json.loads(run_raw)
    _inventory_raw, ordered = _final_rows(candidate_root)
    roster = run.get("selected_private_task_ids")
    if (run.get("status") != "started" or
            len(run.get("task_outcomes", [])) != 7 or
            any(row.get("status") != "provisional_trio_complete"
                for row in run["task_outcomes"]) or
            roster != [row["task_id"] for row in ordered] or
            run.get("official_final_model_attempts") != 0 or
            run.get("official_final_admissions") != 0):
        raise ValueError("Interrupted original 100-task roster/journal changed")
    reference, reference_sha = validate_reference(
        path=reference_path, private_audit=private_day_audit,
        public_audit=public_day_audit)
    salt = json.loads(private_map.read_bytes()).get("variant_salt")
    if type(salt) is not str or len(salt) < 32:
        raise ValueError("Independent saved-OOXML scorer salt absent")
    common = {"profile_sha": digest(profile_private.read_bytes()),
              "guest_sha": digest(guest_public.read_bytes()),
              "private_salt": salt,
              "ratification_sha": digest(action_ratification.read_bytes()),
              "reservation_sha": digest(reservation.read_bytes())}
    accepted = []
    sandbox_ids = set()
    untouched = []
    for index, row in enumerate(ordered):
        task_id = row["task_id"]
        directory = attempts_root / task_id
        if index in QUARANTINED:
            if (index == 7 and
                    {path.name for path in directory.iterdir()} !=
                    {"positive", "near-miss"} or
                    index == 8 and
                    {path.name for path in directory.iterdir()} != {"positive"}):
                raise ValueError("Quarantined first attempts changed")
            continue
        state = _existing_state(attempts_root, row)
        if state == "fresh":
            if index < 7:
                raise ValueError("A completed original prefix task disappeared")
            untouched.append(task_id)
            continue
        if state != "completed_provisional":
            raise ValueError("Another task has partial/uncertain GUI evidence")
        fair = _validate_trio(candidate_root, attempts_root, row, **common)
        ids = _profile_receipt(
            candidate_root=candidate_root,
            attempts_root=attempts_root, task_id=task_id,
            workflow=row["workflow"], reference=reference,
            reference_sha=reference_sha,
            runtime_sha=digest(runtime_freeze.read_bytes()),
            bridge_sha=digest(bridge_path.read_bytes()))
        if any(item in sandbox_ids for item in ids):
            raise ValueError("Two accepted task trios reused a sandbox")
        sandbox_ids.update(ids)
        accepted.append({"roster_index": index, **fair})
    if {row["roster_index"] for row in accepted if row["roster_index"] < 7} != set(range(7)):
        raise ValueError("Seven original complete trios were not retained")
    old_ids = {json.loads(path.read_bytes()).get("sandbox_id_sha256")
               for root in historical_roots
               for path in root.glob("*/*/receipt.json")}
    if sandbox_ids & old_ids:
        raise ValueError("Accepted Desktop guest reused an older epoch sandbox")
    storage = _read_only_storage(attempts_root)
    private = {
        "schema": "cua-native-wdi-v066-day-rollover-attrition-audit-private-v1",
        "status": "completed_controls_only_with_two_quarantined_ids",
        "old_run_journal_sha256": digest(run_raw),
        "accepted_trios": accepted,
        "quarantined_roster_indices": list(QUARANTINED),
        "untouched_private_task_ids": untouched,
        "distinct_accepted_sandbox_count": len(sandbox_ids),
        "current_raw_storage": storage,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-day-rollover-attrition-audit-public-v1",
        "status": "provisional_controls_with_infrastructure_attrition",
        "candidate_final_count": 100,
        "independently_accepted_complete_trios": len(accepted),
        "quarantined_incomplete_task_ids": 2,
        "untouched_task_ids": len(untouched),
        "distinct_accepted_sandboxes": len(sandbox_ids),
        "raw_evidence_rows_verified": storage["verified_raw_evidence_rows"],
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
