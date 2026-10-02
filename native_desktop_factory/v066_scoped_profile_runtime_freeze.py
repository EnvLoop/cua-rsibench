"""Prospective Desktop-only source freeze after public-train calibration.

The shared six-cell action protocol is unchanged. This binds the new Desktop
profile guard, final controller/attempt/audit, fair scorer dependencies, and
public-train reference before any scoped final-control create. Merely writing
the freeze does not authorize a sandbox or an official model result.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .v066_final_freeze import digest, validate_ratification
from .v066_scoped_profile_reference import validate_reference


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cua-native-wdi-v066-scoped-profile-runtime-ratification-v1"
TRAIN_TRIO_PUBLIC = (ROOT / "docs/evidence" /
    "native-wdi-v066-scoped-profile-train-trio-2026-09-28.json")
SOURCE_FILES = (
    "native_desktop_factory/admit.py",
    "native_desktop_factory/factory.py",
    "native_desktop_factory/calibrate_sweep.py",
    "native_desktop_factory/gui_control_shell.py",
    "native_desktop_factory/profile_canonical.py",
    "native_desktop_factory/runtime_fingerprint_probe.py",
    "native_desktop_factory/v066_profile_scope_analysis.py",
    "native_desktop_factory/v066_profile_scope_three_root_budget.py",
    "native_desktop_factory/v066_train_profile_cross_guest.py",
    "native_desktop_factory/v066_train_profile_cross_guest_audit.py",
    "native_desktop_factory/v066_caret_full100_preflight.py",
    "native_desktop_factory/v066_control_plan.py",
    "native_desktop_factory/v066_final_freeze.py",
    "native_desktop_factory/v066_scoped_profile_reference.py",
    "native_desktop_factory/v066_scoped_profile_guard.py",
    "native_desktop_factory/v066_scoped_profile_final_attempt.py",
    "native_desktop_factory/v066_scoped_profile_final_controller.py",
    "native_desktop_factory/v066_scoped_profile_final_audit.py",
    "native_desktop_factory/v066_scoped_profile_train_control.py",
    "native_desktop_factory/v066_scoped_profile_train_control_audit.py",
    "native_desktop_factory/v066_scoped_profile_bridge.py",
    "native_desktop_factory/v066_scoped_profile_runtime_freeze.py",
    "native_desktop_factory/v066_storage_budget.py",
    "native_desktop_factory/v066_final_control_audit.py",
    "native_desktop_factory/v066_final_control_attempt.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "native_desktop_factory/official_saved_verifier.py",
    "native_desktop_factory/verify.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_vision_proxy.py",
)


def source_hashes() -> dict[str, str]:
    return {relative: digest((ROOT / relative).read_bytes())
            for relative in SOURCE_FILES}


def build(*, action_ratification: Path,
          public_calibration: Path,
          private_calibration_audit: Path,
          scoped_reference: Path,
          train_gui_trio_private_audit: Path) -> dict:
    _action, action_sha = validate_ratification(action_ratification)
    _reference, reference_sha = validate_reference(scoped_reference)
    public_raw = public_calibration.read_bytes()
    public = json.loads(public_raw)
    private_raw = private_calibration_audit.read_bytes()
    private = json.loads(private_raw)
    trio_public_raw = TRAIN_TRIO_PUBLIC.read_bytes()
    trio_public = json.loads(trio_public_raw)
    trio_private_raw = train_gui_trio_private_audit.read_bytes()
    trio_private = json.loads(trio_private_raw)
    if (public.get("schema") !=
            "cua-native-wdi-v066-train-profile-cross-guest-public-v1" or
            public.get("status") !=
            "three_public_train_application_pairs_passed_not_final_admission" or
            public.get("same_application_cross_guest_pairs_passed") != 3 or
            public.get("private_independent_audit_sha256") !=
            digest(private_raw) or
            public.get("official_final_admissions") != 0 or
            private.get("schema") !=
            "cua-native-wdi-v066-train-profile-calibration-audit-private-v1" or
            private.get("status") != "three_app_pairs_passed" or
            private.get("provider_active_zero_after") is not True or
            private.get("official_final_admissions") != 0 or
            trio_public.get("schema") !=
            "cua-native-wdi-v066-scoped-profile-train-trio-public-v1" or
            trio_public.get("status") !=
            "public_train_gui_positive_near_reset_passed" or
            trio_public.get("private_independent_whole_trio_audit_sha256") !=
            digest(trio_private_raw) or
            trio_public.get("distinct_e2b_guests") != 3 or
            trio_public.get("official_final_admissions") != 0 or
            trio_private.get("schema") !=
            "cua-native-wdi-v066-scoped-profile-train-trio-audit-private-v1" or
            trio_private.get("status") !=
            "public_train_gui_positive_near_reset_passed" or
            trio_private.get("provider_active_zero_after") is not True or
            trio_private.get("official_final_admissions") != 0):
        raise ValueError("Six public-train guest calibration is not source-bound")
    return {
        "schema": SCHEMA,
        "status": "ratified_pre_result_after_public_train_calibration",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256s": source_hashes(),
        "action_ratification_sha256": action_sha,
        "public_calibration_sha256": digest(public_raw),
        "private_calibration_audit_sha256": digest(private_raw),
        "public_train_gui_trio_sha256": digest(trio_public_raw),
        "private_train_gui_trio_audit_sha256": digest(trio_private_raw),
        "private_train_gui_trio_audit_path": str(
            train_gui_trio_private_audit.resolve()),
        "scoped_reference_private_sha256": reference_sha,
        "base_and_selected_profile_identical": True,
        "hidden_final_model_attempts_before_ratification": 0,
        "official_final_admissions": 0,
    }


def write(*, private_path: Path, public_path: Path,
          action_ratification: Path, public_calibration: Path,
          private_calibration_audit: Path,
          scoped_reference: Path,
          train_gui_trio_private_audit: Path) -> dict:
    if (private_path.exists() or private_path.is_symlink() or
            public_path.exists() or public_path.is_symlink()):
        raise ValueError("New scoped runtime freeze paths required")
    value = build(
        action_ratification=action_ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference,
        train_gui_trio_private_audit=train_gui_trio_private_audit)
    private_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    descriptor = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    aggregate = {
        "schema": "cua-native-wdi-v066-scoped-profile-runtime-ratification-public-v1",
        "status": "source_frozen_for_evaluator_controls_not_model_outcomes",
        "private_runtime_freeze_sha256": digest(raw),
        "public_calibration_sha256": value["public_calibration_sha256"],
        "public_train_gui_trio_sha256": value["public_train_gui_trio_sha256"],
        "source_sha256s": value["source_sha256s"],
        "same_app_public_train_pairs_passed": 3,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    with public_path.open("x", encoding="utf-8") as stream:
        json.dump(aggregate, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return aggregate


def validate(*, path: Path, action_ratification: Path,
             public_calibration: Path,
             private_calibration_audit: Path,
             scoped_reference: Path) -> tuple[dict, str]:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077):
        raise ValueError("Private scoped runtime source freeze absent")
    raw = path.read_bytes()
    value = json.loads(raw)
    trio_path = value.get("private_train_gui_trio_audit_path")
    if (type(trio_path) is not str or
            not Path(trio_path).is_file() or
            Path(trio_path).is_symlink() or
            Path(trio_path).stat().st_mode & 0o077):
        raise ValueError("Private train GUI trio audit absent")
    expected = build(
        action_ratification=action_ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference,
        train_gui_trio_private_audit=Path(trio_path))
    expected.pop("recorded_utc")
    if (set(value) != set(expected) | {"recorded_utc"} or
            any(value.get(key) != item for key, item in expected.items())):
        raise ValueError("Scoped runtime source bytes or train evidence changed")
    try:
        recorded = datetime.fromisoformat(value["recorded_utc"])
    except (TypeError, ValueError):
        raise ValueError("Scoped runtime source freeze time invalid") from None
    if (recorded.tzinfo is None or
            recorded.astimezone(timezone.utc) > datetime.now(timezone.utc)):
        raise ValueError("Scoped runtime source freeze time invalid")
    return value, digest(raw)
