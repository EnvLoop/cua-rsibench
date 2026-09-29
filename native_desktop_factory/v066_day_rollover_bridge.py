"""Four-root full-lease bridge for the post-rollover fresh Desktop 100.

Historical 22, halted caret 2, and failed scoped 2 intents stay immutable.
The new epoch reserves another 300 ten-minute evaluator guests. Neither this
bridge nor its validator dispatches a model or admits a final task.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path

from .reconcile_interrupted_sweep import active_hashes
from .v066_caret_full100_preflight import _private, _tree_digest
from .v066_day_rollover_reference import validate as validate_reference
from .v066_day_rollover_runtime_freeze import validate as validate_runtime
from .v066_final_freeze import (LANE_CAP_USD, LEASE_SECONDS,
                                MAX_SANDBOX_COUNT, digest, intent_budget,
                                validate_lane)


SCHEMA = "cua-native-wdi-v066-day-rollover-four-root-bridge-v1"
OLD_COUNTS = (22, 2, 2)
FRESH_PLANNED = 300


def combined_budget(*, original_root: Path, failed_root: Path,
                    failed_scoped_root: Path, fresh_root: Path,
                    proposed_fresh_intents: int) -> dict:
    roots = (original_root, failed_root, failed_scoped_root, fresh_root)
    if (any(root.name != "v066-final-gui" or root.is_symlink()
            for root in roots) or
            len({root.resolve() for root in roots}) != 4 or
            any(a.resolve().is_relative_to(b.resolve())
                for a in roots for b in roots if a != b) or
            (fresh_root.exists() and not _private(fresh_root, directory=True))):
        raise ValueError("Four private E2B attempt roots are not isolated")
    counts = tuple(intent_budget(root)["existing_intents"] for root in roots)
    if (counts[:3] != OLD_COUNTS or counts[3] > FRESH_PLANNED or
            type(proposed_fresh_intents) is not int or
            not 0 <= proposed_fresh_intents <= FRESH_PLANNED - counts[3]):
        raise ValueError("Historical or fresh full-lease intent count changed")
    total = sum(counts) + proposed_fresh_intents
    reserved = Decimal(total * LEASE_SECONDS) / Decimal(3600)
    if total > MAX_SANDBOX_COUNT or reserved > LANE_CAP_USD:
        raise ValueError("Four-root full-lease reservation exceeds $60")
    return {"historical_counts": list(counts[:3]),
            "fresh_existing_intents": counts[3],
            "fresh_proposed_intents": proposed_fresh_intents,
            "combined_full_lease_intents": total,
            "combined_conservative_reserved_usd": str(reserved),
            "lane_cap_usd": str(LANE_CAP_USD),
            "actual_provider_billed_usd": None}


def build(*, candidate_root: Path, original_root: Path,
          failed_root: Path, failed_scoped_root: Path,
          fresh_root: Path, old_scoped_bridge: Path,
          failed_scoped_run_journal: Path,
          prior_calc_root: Path, old_five_root: Path,
          current_calc_root: Path,
          action_ratification: Path, new_lane_reservation: Path,
          private_day_audit: Path, public_day_audit: Path,
          new_reference: Path, runtime_freeze: Path,
          profile_private: Path, guest_public: Path,
          fair_public: Path) -> dict:
    lane = validate_lane(
        ratification=action_ratification,
        reservation=new_lane_reservation,
        candidate_root=candidate_root, guest_public=guest_public,
        profile_private=profile_private, fair_public=fair_public)
    _reference, reference_sha = validate_reference(
        path=new_reference, private_audit=private_day_audit,
        public_audit=public_day_audit)
    _runtime, runtime_sha = validate_runtime(
        path=runtime_freeze, candidate_root=candidate_root,
        guest_public=guest_public, profile_private=profile_private,
        fair_public=fair_public, action_ratification=action_ratification,
        new_lane_reservation=new_lane_reservation,
        private_day_audit=private_day_audit,
        public_day_audit=public_day_audit, new_reference=new_reference)
    audit = json.loads(private_day_audit.read_bytes())
    public = json.loads(public_day_audit.read_bytes())
    if (audit.get("status") !=
            "public_train_date_rollover_corroborated_final_failures_retained" or
            public.get("private_independent_audit_sha256") !=
            digest(private_day_audit.read_bytes()) or
            digest(failed_scoped_run_journal.read_bytes()) !=
            audit.get("failed_scoped_run_journal_sha256")):
        raise ValueError("Date and failed scoped lineage changed")
    old_bridge = json.loads(old_scoped_bridge.read_bytes())
    if (old_bridge.get("schema") !=
            "cua-native-wdi-v066-scoped-profile-three-root-bridge-v1" or
            old_bridge.get("status") !=
            "reserved_before_first_scoped_final_create" or
            old_bridge.get("original_attempts_root") !=
            str(original_root.resolve()) or
            old_bridge.get("halted_amended_attempts_root") !=
            str(failed_root.resolve()) or
            old_bridge.get("fresh_scoped_attempts_root") !=
            str(failed_scoped_root.resolve()) or
            old_bridge.get("historical_original_intents") != OLD_COUNTS[0] or
            old_bridge.get("halted_amended_intents") != OLD_COUNTS[1] or
            old_bridge.get("official_final_admissions") != 0):
        raise ValueError("Earlier scoped source bridge changed")
    original_sha, _ = _tree_digest(original_root)
    halted_sha, _ = _tree_digest(failed_root)
    scoped_sha, _ = _tree_digest(failed_scoped_root)
    if (original_sha != old_bridge["original_attempt_tree_sha256"] or
            halted_sha != old_bridge["halted_amended_tree_sha256"] or
            scoped_sha != audit["failed_scoped_attempt_tree_sha256"] or
            _tree_digest(prior_calc_root)[0] !=
            audit["prior_public_train_tree_sha256"] or
            _tree_digest(old_five_root)[0] !=
            audit["old_five_public_train_tree_sha256"] or
            _tree_digest(current_calc_root)[0] !=
            audit["current_public_train_tree_sha256"]):
        raise ValueError("Retained E2B raw evidence changed")
    budget = combined_budget(
        original_root=original_root, failed_root=failed_root,
        failed_scoped_root=failed_scoped_root, fresh_root=fresh_root,
        proposed_fresh_intents=FRESH_PLANNED -
        intent_budget(fresh_root)["existing_intents"])
    if (budget["combined_full_lease_intents"] != 326 or
            lane["lane_cap_usd"] != "60"):
        raise ValueError("Four-root 326-lease projection changed")
    return {
        "schema": SCHEMA,
        "status": "reserved_before_fresh_date_amended_final_create",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_inventory_sha256": lane["source_bindings"][
            "candidate_inventory_sha256"],
        "original_attempts_root": str(original_root.resolve()),
        "halted_amended_attempts_root": str(failed_root.resolve()),
        "failed_scoped_attempts_root": str(failed_scoped_root.resolve()),
        "fresh_date_amended_attempts_root": str(fresh_root.resolve()),
        "old_scoped_bridge_path": str(old_scoped_bridge.resolve()),
        "failed_scoped_run_journal_path": str(
            failed_scoped_run_journal.resolve()),
        "prior_calc_root": str(prior_calc_root.resolve()),
        "old_five_root": str(old_five_root.resolve()),
        "current_calc_root": str(current_calc_root.resolve()),
        "old_scoped_bridge_sha256": digest(old_scoped_bridge.read_bytes()),
        "original_attempt_tree_sha256": original_sha,
        "halted_amended_tree_sha256": halted_sha,
        "failed_scoped_tree_sha256": scoped_sha,
        "private_day_audit_sha256": digest(private_day_audit.read_bytes()),
        "public_day_audit_sha256": digest(public_day_audit.read_bytes()),
        "new_reference_sha256": reference_sha,
        "runtime_freeze_sha256": runtime_sha,
        "new_lane_reservation_sha256":
            digest(new_lane_reservation.read_bytes()),
        "action_ratification_sha256":
            digest(action_ratification.read_bytes()),
        "historical_intent_counts": list(OLD_COUNTS),
        "fresh_intents_planned": FRESH_PLANNED,
        "combined_full_lease_intents_planned": 326,
        "combined_conservative_reserved_usd":
            budget["combined_conservative_reserved_usd"],
        "lane_cap_usd": "60",
        "provider_active_before": 0,
        "automatic_replay_authorized": False,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }


def prepare(*, path: Path, active_probe=active_hashes, **kwargs) -> dict:
    if (path.exists() or path.is_symlink() or
            kwargs["fresh_root"].exists()):
        raise ValueError("New unused four-root bridge and attempt root required")
    value = build(**kwargs)
    active, count = active_probe()
    if active or count:
        raise ValueError("Provider has active E2B guests before four-root bridge")
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"bridge_sha256": digest(raw),
            "full_lease_intents_planned": 326,
            "reserved_usd": value["combined_conservative_reserved_usd"],
            "official_final_admissions": 0}


def validate(*, bridge_path: Path, candidate_root: Path,
             original_root: Path, failed_root: Path,
             fresh_root: Path, action_ratification: Path,
             public_calibration: Path, private_calibration_audit: Path,
             scoped_reference: Path, runtime_freeze: Path,
             new_lane_reservation: Path, profile_private: Path,
             guest_public: Path, fair_public: Path) -> tuple[dict, str]:
    if not _private(bridge_path, directory=False):
        raise ValueError("Private four-root bridge absent")
    raw = bridge_path.read_bytes()
    value = json.loads(raw)
    expected = build(
        candidate_root=candidate_root,
        original_root=original_root, failed_root=failed_root,
        failed_scoped_root=Path(value["failed_scoped_attempts_root"]),
        fresh_root=fresh_root,
        old_scoped_bridge=Path(value["old_scoped_bridge_path"]),
        failed_scoped_run_journal=Path(
            value["failed_scoped_run_journal_path"]),
        prior_calc_root=Path(value["prior_calc_root"]),
        old_five_root=Path(value["old_five_root"]),
        current_calc_root=Path(value["current_calc_root"]),
        action_ratification=action_ratification,
        new_lane_reservation=new_lane_reservation,
        private_day_audit=private_calibration_audit,
        public_day_audit=public_calibration,
        new_reference=scoped_reference,
        runtime_freeze=runtime_freeze,
        profile_private=profile_private, guest_public=guest_public,
        fair_public=fair_public)
    expected.pop("recorded_utc")
    if (set(value) != set(expected) | {"recorded_utc"} or
            any(value.get(key) != item for key, item in expected.items())):
        raise ValueError("Four-root date-amended source or evidence changed")
    try:
        recorded = datetime.fromisoformat(value["recorded_utc"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("Four-root bridge timestamp invalid") from None
    if recorded.tzinfo is None or recorded > datetime.now(timezone.utc):
        raise ValueError("Four-root bridge timestamp invalid")
    return value, digest(raw)
