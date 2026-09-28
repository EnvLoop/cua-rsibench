"""Freeze three application profile fingerprints from public train guests.

The six-guest raw audit is rerun before an exclusive evaluator-private record
is written. No hidden final source, model, provider, or acceptance runner is
used to select these Calc/Writer/Impress values.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from . import v066_profile_scope_analysis as scope
from . import v066_train_profile_cross_guest_audit as train_audit
from .v066_final_freeze import digest


SCHEMA = "cua-native-wdi-v066-scoped-profile-reference-private-v1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def workflow_kind(workflow: str) -> str:
    if workflow.startswith("calc-"):
        return "calc"
    if workflow == "writer-brief":
        return "writer"
    if workflow == "impress-deck":
        return "impress"
    raise ValueError("Unsupported scoped-profile application workflow")


def build(*, calibration_root: Path, prior_calc_dir: Path,
          calibration_reservation: Path,
          preserved_calibration_audit: Path) -> dict:
    private, public = train_audit.audit(
        output_root=calibration_root, prior_calc_dir=prior_calc_dir,
        reservation_path=calibration_reservation)
    if (private["status"] != "three_app_pairs_passed" or
            public["same_app_cross_guest_pairs_passed"] != 3 or
            not public["setting_recovery_and_nonregistry_negatives_passed"]):
        raise ValueError("Public train profile calibration did not pass")
    saved_raw = preserved_calibration_audit.read_bytes()
    saved = json.loads(saved_raw)
    if (saved.get("schema") != private["schema"] or
            saved.get("status") != private["status"] or
            saved.get("reservation_sha256") !=
            private["reservation_sha256"] or
            saved.get("run_journal_sha256") !=
            private["run_journal_sha256"] or
            saved.get("provider_active_zero_after") is not True or
            saved.get("official_final_admissions") != 0):
        raise ValueError("Preserved public-train raw audit changed")
    entries = {row["label"]: row for row in private["per_guest"]}
    applications = {
        "calc": entries["calc-second"]["scoped_profile_sha256"],
        "writer": entries["writer-first"]["scoped_profile_sha256"],
        "impress": entries["impress-first"]["scoped_profile_sha256"],
    }
    if (set(applications) != {"calc", "writer", "impress"} or
            any(HEX64.fullmatch(value) is None
                for value in applications.values())):
        raise ValueError("Three public application fingerprints are incomplete")
    return {"schema": SCHEMA,
            "status": "frozen_public_train_profiles_before_final_attempts",
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "reference_builder_source_sha256":
                digest(Path(__file__).read_bytes()),
            "profile_scope_source_sha256":
                digest(Path(scope.__file__).read_bytes()),
            "train_calibration_reservation_sha256":
                digest(calibration_reservation.read_bytes()),
            "train_calibration_run_journal_sha256":
                private["run_journal_sha256"],
            "train_calibration_audit_sha256": digest(saved_raw),
            "distinct_public_train_guest_count": 6,
            "same_app_cross_guest_pairs_passed": 3,
            "negative_controls_passed": True,
            "applications": applications,
            "official_final_admissions": 0,
            "official_model_results": 0}


def write(*, output: Path, calibration_root: Path,
          prior_calc_dir: Path, calibration_reservation: Path,
          preserved_calibration_audit: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Scoped public-train reference must be a new file")
    value = build(
        calibration_root=calibration_root,
        prior_calc_dir=prior_calc_dir,
        calibration_reservation=calibration_reservation,
        preserved_calibration_audit=preserved_calibration_audit)
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"schema": "cua-native-wdi-v066-scoped-profile-reference-public-v1",
            "status": "three_public_train_application_references_frozen",
            "private_reference_sha256": digest(raw),
            "distinct_public_train_guest_count": 6,
            "same_app_cross_guest_pairs_passed": 3,
            "official_final_admissions": 0,
            "official_model_results": 0}


def validate_reference(path: Path) -> tuple[dict, str]:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077):
        raise ValueError("Evaluator-private scoped profile reference absent")
    raw = path.read_bytes()
    value = json.loads(raw)
    if (value.get("schema") != SCHEMA or
            value.get("status") !=
            "frozen_public_train_profiles_before_final_attempts" or
            value.get("reference_builder_source_sha256") !=
            digest(Path(__file__).read_bytes()) or
            value.get("profile_scope_source_sha256") !=
            digest(Path(scope.__file__).read_bytes()) or
            set(value.get("applications", {})) !=
            {"calc", "writer", "impress"} or
            any(HEX64.fullmatch(item) is None
                for item in value["applications"].values()) or
            value.get("distinct_public_train_guest_count") != 6 or
            value.get("same_app_cross_guest_pairs_passed") != 3 or
            value.get("negative_controls_passed") is not True or
            value.get("official_final_admissions") != 0 or
            value.get("official_model_results") != 0):
        raise ValueError("Scoped public-train reference source or scope changed")
    return value, digest(raw)
