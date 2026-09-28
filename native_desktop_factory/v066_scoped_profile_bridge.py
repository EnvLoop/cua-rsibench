"""Source-bound three-root $60 final-control bridge for a new Desktop epoch.

The original 22 and halted amended two intents remain in their own immutable
roots. This bridge prospectively charges 300 fresh ten-minute leases as well.
No file is moved, erased, or discounted; no model outcome is authorized.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .reconcile_interrupted_sweep import active_hashes
from .v066_caret_full100_preflight import _private, _tree_digest
from .v066_final_freeze import digest, validate_lane
from .v066_profile_scope_three_root_budget import (
    FUTURE_FRESH_INTENTS, combined_budget, inspect,
)
from .v066_scoped_profile_runtime_freeze import validate as validate_runtime


SCHEMA = "cua-native-wdi-v066-scoped-profile-three-root-bridge-v1"


def prepare(*, bridge_path: Path, candidate_root: Path,
            original_root: Path, failed_root: Path, fresh_root: Path,
            old_run_journal: Path, old_ratification: Path,
            old_reservation: Path, failed_run_journal: Path,
            failed_ratification: Path, failed_reservation: Path,
            failed_private_stop: Path,
            failed_public_interruption: Path,
            action_ratification: Path, public_calibration: Path,
            private_calibration_audit: Path, scoped_reference: Path,
            runtime_freeze: Path, new_lane_reservation: Path,
            profile_private: Path, guest_public: Path,
            fair_public: Path, active_probe=None) -> dict:
    if bridge_path.exists() or bridge_path.is_symlink():
        raise ValueError("New exclusive scoped three-root bridge required")
    if fresh_root.exists() or fresh_root.is_symlink():
        raise ValueError("Fresh scoped final-control root already used")
    old_failed, _public = inspect(
        candidate_root=candidate_root, original_root=original_root,
        failed_root=failed_root, future_root=fresh_root,
        old_run_journal=old_run_journal,
        old_ratification=old_ratification,
        old_reservation=old_reservation,
        failed_run_journal=failed_run_journal,
        failed_ratification=failed_ratification,
        failed_reservation=failed_reservation,
        failed_private_stop=failed_private_stop,
        failed_public_interruption=failed_public_interruption)
    _runtime, runtime_sha = validate_runtime(
        path=runtime_freeze,
        action_ratification=action_ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference)
    validate_lane(
        ratification=action_ratification,
        reservation=new_lane_reservation,
        candidate_root=candidate_root,
        guest_public=guest_public,
        profile_private=profile_private,
        fair_public=fair_public)
    probe = active_probe or active_hashes
    active, count = probe()
    if active or count:
        raise ValueError("Provider has active sandboxes before bridge")
    budget = old_failed["budget"]
    if (budget["combined_full_lease_intents"] != 324 or
            budget["combined_conservative_reserved_usd"] != "54"):
        raise ValueError("Three-root full-lease projection changed")
    value = {
        "schema": SCHEMA,
        "status": "reserved_before_first_scoped_final_create",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "original_attempts_root": str(original_root.resolve()),
        "halted_amended_attempts_root": str(failed_root.resolve()),
        "fresh_scoped_attempts_root": str(fresh_root.resolve()),
        "candidate_inventory_sha256":
            old_failed["candidate_inventory_sha256"],
        "original_attempt_tree_sha256":
            old_failed["old_evidence"]["original_attempt_tree_sha256"],
        "halted_amended_tree_sha256":
            old_failed["halted_amended_tree_sha256"],
        "halted_amended_stop_sha256":
            old_failed["halted_amended_stop_sha256"],
        "runtime_freeze_sha256": runtime_sha,
        "new_lane_reservation_sha256":
            digest(new_lane_reservation.read_bytes()),
        "scoped_reference_private_sha256":
            digest(scoped_reference.read_bytes()),
        "action_ratification_sha256":
            digest(action_ratification.read_bytes()),
        "public_calibration_sha256":
            digest(public_calibration.read_bytes()),
        "private_calibration_audit_sha256":
            digest(private_calibration_audit.read_bytes()),
        "historical_original_intents": 22,
        "halted_amended_intents": 2,
        "fresh_scoped_intents_planned": FUTURE_FRESH_INTENTS,
        "combined_full_lease_intents_planned": 324,
        "combined_conservative_reserved_usd": "54",
        "existing_final_control_lane_cap_usd": "60",
        "provider_active_before": 0,
        "automatic_replay_authorized": False,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    bridge_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    descriptor = os.open(bridge_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": value["status"],
            "bridge_sha256": digest(raw),
            "combined_full_lease_intents_planned": 324,
            "combined_conservative_reserved_usd": "54",
            "official_final_admissions": 0}


def validate(*, bridge_path: Path, candidate_root: Path,
             original_root: Path, failed_root: Path,
             fresh_root: Path, action_ratification: Path,
             public_calibration: Path,
             private_calibration_audit: Path,
             scoped_reference: Path, runtime_freeze: Path,
             new_lane_reservation: Path,
             failed_private_stop: Path,
             failed_public_interruption: Path,
             profile_private: Path, guest_public: Path,
             fair_public: Path) -> tuple[dict, str]:
    if not _private(bridge_path, directory=False):
        raise ValueError("Private scoped three-root bridge absent")
    raw = bridge_path.read_bytes()
    value = json.loads(raw)
    _runtime, runtime_sha = validate_runtime(
        path=runtime_freeze,
        action_ratification=action_ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference)
    lane = validate_lane(
        ratification=action_ratification,
        reservation=new_lane_reservation,
        candidate_root=candidate_root,
        guest_public=guest_public,
        profile_private=profile_private,
        fair_public=fair_public)
    original_sha, _old_files = _tree_digest(original_root)
    halted_sha, _halted_files = _tree_digest(failed_root)
    stop_raw = failed_private_stop.read_bytes()
    interruption = json.loads(failed_public_interruption.read_bytes())
    if (interruption.get("private_stop_reconciliation_sha256") !=
            digest(stop_raw)):
        raise ValueError("Halted control stop receipt changed")
    budget = combined_budget(
        original_root=original_root, failed_root=failed_root,
        future_root=fresh_root,
        proposed_future_intents=FUTURE_FRESH_INTENTS -
        len(list(fresh_root.glob("*/*/intent.json"))))
    expected = {
        "schema": SCHEMA,
        "status": "reserved_before_first_scoped_final_create",
        "original_attempts_root": str(original_root.resolve()),
        "halted_amended_attempts_root": str(failed_root.resolve()),
        "fresh_scoped_attempts_root": str(fresh_root.resolve()),
        "candidate_inventory_sha256": lane["source_bindings"][
            "candidate_inventory_sha256"],
        "original_attempt_tree_sha256": original_sha,
        "halted_amended_tree_sha256": halted_sha,
        "halted_amended_stop_sha256": digest(stop_raw),
        "runtime_freeze_sha256": runtime_sha,
        "new_lane_reservation_sha256":
            digest(new_lane_reservation.read_bytes()),
        "scoped_reference_private_sha256":
            digest(scoped_reference.read_bytes()),
        "action_ratification_sha256":
            digest(action_ratification.read_bytes()),
        "public_calibration_sha256":
            digest(public_calibration.read_bytes()),
        "private_calibration_audit_sha256":
            digest(private_calibration_audit.read_bytes()),
        "historical_original_intents": 22,
        "halted_amended_intents": 2,
        "fresh_scoped_intents_planned": FUTURE_FRESH_INTENTS,
        "combined_full_lease_intents_planned": 324,
        "combined_conservative_reserved_usd": "54",
        "existing_final_control_lane_cap_usd": "60",
        "provider_active_before": 0,
        "automatic_replay_authorized": False,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    if (set(value) != set(expected) | {"recorded_utc"} or
            any(value.get(key) != item for key, item in expected.items()) or
            budget["combined_full_lease_intents"] != 324 or
            budget["combined_conservative_reserved_usd"] != "54"):
        raise ValueError("Three-root scoped source or full-lease bridge changed")
    try:
        recorded = datetime.fromisoformat(value["recorded_utc"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Three-root scoped bridge time invalid") from None
    if (recorded.tzinfo is None or
            recorded.astimezone(timezone.utc) > datetime.now(timezone.utc)):
        raise ValueError("Three-root scoped bridge time invalid")
    return value, digest(raw)
