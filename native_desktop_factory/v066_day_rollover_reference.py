"""New public-train Desktop profile reference after the calendar-day amendment."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from . import v066_profile_scope_analysis as scope
from . import v066_scoped_profile_reference as original_reference
from .v066_final_freeze import digest


def build(*, private_audit: Path, public_audit: Path) -> dict:
    raw = private_audit.read_bytes()
    evidence = json.loads(raw)
    public_raw = public_audit.read_bytes()
    public = json.loads(public_raw)
    if (evidence.get("schema") !=
            "cua-native-wdi-v066-day-rollover-raw-audit-private-v1" or
            evidence.get("status") !=
            "public_train_date_rollover_corroborated_final_failures_retained" or
            evidence.get("audit_source_sha256") != digest(
                Path(__file__).with_name("v066_day_rollover_audit.py").read_bytes()) or
            evidence.get("scoped_analysis_source_sha256") !=
            digest(Path(scope.__file__).read_bytes()) or
            evidence.get("old_six_same_application_pairs_passed") != 3 or
            evidence.get("current_day_train_equal_under_new_scope") is not True or
            evidence.get("canonical_public_train_equal_after_tip_day_mask") is not True or
            evidence.get("failed_final_guests_diagnosed_no_actions") != 2 or
            evidence.get("current_tip_day") != evidence.get("old_tip_day", -2) + 1 or
            evidence.get("official_final_admissions") != 0 or
            evidence.get("official_model_results") != 0 or
            public.get("schema") !=
            "cua-native-wdi-v066-day-rollover-raw-audit-public-v1" or
            public.get("private_independent_audit_sha256") != digest(raw) or
            public.get("official_final_admissions") != 0):
        raise ValueError("Current-day public train corroboration not independently bound")
    applications = evidence.get("scoped_reference_application_sha256s")
    if (type(applications) is not dict or
            set(applications) != {"calc", "writer", "impress"} or
            any(type(value) is not str or len(value) != 64
                for value in applications.values())):
        raise ValueError("Three public-train application references missing")
    return {
        "schema": original_reference.SCHEMA,
        "status": "frozen_public_train_profiles_before_final_attempts",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "reference_builder_source_sha256": digest(
            Path(original_reference.__file__).read_bytes()),
        "profile_scope_source_sha256": digest(Path(scope.__file__).read_bytes()),
        "day_rollover_reference_source_sha256": digest(Path(__file__).read_bytes()),
        "day_rollover_private_audit_sha256": digest(raw),
        "day_rollover_public_audit_sha256": digest(public_raw),
        "distinct_public_train_guest_count": 6,
        "same_app_cross_guest_pairs_passed": 3,
        "additional_current_day_public_train_guest_count": 1,
        "prior_public_tip_day": evidence["old_tip_day"],
        "current_public_tip_day": evidence["current_tip_day"],
        "negative_controls_passed": True,
        "applications": applications,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }


def write(*, path: Path, private_audit: Path, public_audit: Path) -> dict:
    if path.exists() or path.is_symlink():
        raise ValueError("New private date-rollover reference path required")
    value = build(private_audit=private_audit, public_audit=public_audit)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"reference_sha256": digest(raw), "official_final_admissions": 0}


def validate(*, path: Path, private_audit: Path,
             public_audit: Path) -> tuple[dict, str]:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077):
        raise ValueError("Private day-rollover reference absent")
    value, sha = original_reference.validate_reference(path)
    expected = build(private_audit=private_audit, public_audit=public_audit)
    expected.pop("recorded_utc")
    if (set(value) != set(expected) | {"recorded_utc"} or
            any(value.get(key) != item for key, item in expected.items())):
        raise ValueError("Date-rollover reference source or evidence changed")
    try:
        recorded = datetime.fromisoformat(value["recorded_utc"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Date-rollover reference timestamp invalid") from None
    if recorded.tzinfo is None or recorded > datetime.now(timezone.utc):
        raise ValueError("Date-rollover reference timestamp invalid")
    return value, sha
