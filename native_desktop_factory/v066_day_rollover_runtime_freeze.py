"""Freeze the Desktop-only date-amended evaluator before any fresh lease."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from . import v066_scoped_profile_runtime_freeze as old_freeze
from .v066_day_rollover_reference import validate as validate_reference
from .v066_final_freeze import digest, validate_lane


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = tuple(dict.fromkeys((*old_freeze.SOURCE_FILES,
    "native_desktop_factory/v066_day_rollover_audit.py",
    "native_desktop_factory/v066_day_rollover_reference.py",
    "native_desktop_factory/v066_day_rollover_runtime_freeze.py",
    "native_desktop_factory/v066_day_rollover_bridge.py")))
SCHEMA = "cua-native-wdi-v066-day-rollover-runtime-freeze-v1"


def source_hashes() -> dict[str, str]:
    return {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def build(*, candidate_root: Path, guest_public: Path,
          profile_private: Path, fair_public: Path,
          action_ratification: Path, new_lane_reservation: Path,
          private_day_audit: Path, public_day_audit: Path,
          new_reference: Path) -> dict:
    lane = validate_lane(
        ratification=action_ratification,
        reservation=new_lane_reservation,
        candidate_root=candidate_root, guest_public=guest_public,
        profile_private=profile_private, fair_public=fair_public)
    reference, reference_sha = validate_reference(
        path=new_reference, private_audit=private_day_audit,
        public_audit=public_day_audit)
    raw = private_day_audit.read_bytes()
    evidence = json.loads(raw)
    public_raw = public_day_audit.read_bytes()
    public = json.loads(public_raw)
    if (evidence.get("audit_source_sha256") != source_hashes()[
            "native_desktop_factory/v066_day_rollover_audit.py"] or
            public.get("private_independent_audit_sha256") != digest(raw) or
            reference.get("day_rollover_private_audit_sha256") != digest(raw) or
            reference.get("day_rollover_public_audit_sha256") !=
            digest(public_raw) or
            reference.get("current_public_tip_day") !=
            reference.get("prior_public_tip_day", -2) + 1 or
            lane.get("official_hidden_final_model_attempts") != 0):
        raise ValueError("Public-train date or separate lane is not source-bound")
    return {
        "schema": SCHEMA,
        "status": "ratified_before_fresh_date_amended_final_controls",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256s": source_hashes(),
        "action_ratification_sha256": digest(action_ratification.read_bytes()),
        "new_lane_reservation_sha256": digest(new_lane_reservation.read_bytes()),
        "private_day_audit_sha256": digest(raw),
        "public_day_audit_sha256": digest(public_raw),
        "new_reference_sha256": reference_sha,
        "prior_public_tip_day": reference["prior_public_tip_day"],
        "current_public_tip_day": reference["current_public_tip_day"],
        "base_and_selected_profile_identical": True,
        "hidden_final_model_attempts_before_freeze": 0,
        "official_final_admissions": 0,
    }


def write(*, path: Path, **kwargs) -> dict:
    if path.exists() or path.is_symlink():
        raise ValueError("New private date-amended runtime freeze path required")
    value = build(**kwargs)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"runtime_sha256": digest(raw), "official_final_admissions": 0}


def validate(*, path: Path, **kwargs) -> tuple[dict, str]:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077):
        raise ValueError("Private date-amended runtime freeze absent")
    raw = path.read_bytes()
    value = json.loads(raw)
    expected = build(**kwargs)
    expected.pop("recorded_utc")
    if (set(value) != set(expected) | {"recorded_utc"} or
            any(value.get(key) != item for key, item in expected.items())):
        raise ValueError("Date-amended runtime source or evidence changed")
    try:
        recorded = datetime.fromisoformat(value["recorded_utc"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("Date-amended runtime timestamp invalid") from None
    if recorded.tzinfo is None or recorded > datetime.now(timezone.utc):
        raise ValueError("Date-amended runtime timestamp invalid")
    return value, digest(raw)
