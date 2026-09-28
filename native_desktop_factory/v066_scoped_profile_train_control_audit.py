"""Independent public-train GUI positive/near/reset and saved PPTX audit."""

from __future__ import annotations

import json
from pathlib import Path

from . import (qwen_v066_adapter, v066_profile_scope_analysis as scope,
               v066_scoped_profile_guard as guard,
               v066_scoped_profile_train_control as train)
from .v066_final_control_audit import _bound_file
from .v066_final_freeze import digest
from .v066_scoped_profile_reference import validate_reference
from .verify import verify


ATTEMPTS = ("positive", "near-miss", "cold-reset")


def audit_one(*, output_root: Path, attempt: str,
              scoped_reference: Path, guest_public: Path,
              diagnostic_reservation: Path) -> dict:
    if attempt not in ATTEMPTS:
        raise ValueError("Unknown public-train GUI control polarity")
    package, oracle, baseline, _instruction, _filename = train._train_package()
    reference, reference_sha = validate_reference(scoped_reference)
    expected_profile = reference["applications"]["impress"]
    path = output_root / attempt
    intent_raw = (path / "intent.json").read_bytes()
    receipt_raw = (path / "receipt.json").read_bytes()
    intent, receipt = json.loads(intent_raw), json.loads(receipt_raw)
    expected_status = ("cold_reset_observed" if attempt == "cold-reset"
                       else "train_scoped_control_passed")
    if (intent.get("schema") !=
            "cua-native-wdi-v066-scoped-profile-train-control-intent-v1" or
            intent.get("attempt") != attempt or
            intent.get("split") != "train" or
            intent.get("package_sha256") != package["package_sha256"] or
            intent.get("runner_sha256") !=
            digest(Path(train.__file__).read_bytes()) or
            intent.get("profile_reference_sha256") != reference_sha or
            intent.get("diagnostic_reservation_sha256") !=
            digest(diagnostic_reservation.read_bytes()) or
            intent.get("automatic_replay_authorized") is not False or
            receipt.get("schema") !=
            "cua-native-wdi-gui-development-attempt-v1" or
            receipt.get("purpose") !=
            "v066_scoped_profile_public_train_gui_control_no_model" or
            receipt.get("status") != expected_status or
            receipt.get("split") != "train" or
            receipt.get("attempt") != attempt or
            receipt.get("package_sha256") != package["package_sha256"] or
            receipt.get("input_sha256") != digest(baseline) or
            receipt.get("runner_sha256") !=
            digest(Path(train.__file__).read_bytes()) or
            receipt.get("v066_native_adapter_sha256") !=
            digest(Path(qwen_v066_adapter.__file__).read_bytes()) or
            receipt.get("profile_scope_guard_source_sha256") !=
            digest(Path(guard.__file__).read_bytes()) or
            receipt.get("profile_reference_private_sha256") != reference_sha or
            receipt.get("expected_guest_identity_public_sha256") !=
            digest(guest_public.read_bytes()) or
            receipt.get("guest_content_attested") is not True or
            receipt.get("task_profile_scoped_attested") is not True or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            receipt.get("official_final_model_attempts") != 0 or
            receipt.get("official_final_admissions") != 0):
        raise ValueError("Public-train scoped control source or cleanup changed")
    snapshots = receipt.get("task_profile_scoped_snapshots", [])
    if len(snapshots) != 2:
        raise ValueError("Raw public-train profile snapshots are incomplete")
    for index, snapshot in enumerate(snapshots):
        if snapshot.get("label") != ("first", "second")[index]:
            raise ValueError("Raw public-train profile order changed")
        manifest = _bound_file(output_root, snapshot["manifest"])
        registry = _bound_file(output_root, snapshot["registry"])
        _bound_file(output_root, snapshot["visible_frame"])
        if scope.scoped_profile(json.loads(manifest), registry) != expected_profile:
            raise ValueError("Raw public-train profile differs from train reference")
    steps = receipt.get("steps", [])
    if attempt == "cold-reset":
        if steps or receipt.get("restored_state_sha256") != digest(baseline):
            raise ValueError("Fresh public-train reset changed input or acted")
        _bound_file(output_root, receipt["cold_observation"])
    else:
        replacement = (next(iter(oracle["targets"].values()))
                       if attempt == "positive" else
                       "INTENTIONALLY_WRONG_TRAIN_SIGNAL")
        expected_actions = train._script(replacement)
        if len(steps) != len(expected_actions):
            raise ValueError("Public-train GUI actor action count changed")
        for index, (step, action) in enumerate(zip(steps, expected_actions)):
            payload = json.dumps(action, separators=(",", ":"))
            observed = _bound_file(output_root, step["observation"])
            predispatch = _bound_file(output_root, step["predispatch"])
            if (step.get("step") != index or
                    step.get("status") != "applied" or
                    step.get("action_type") != action["type"] or
                    step.get("dispatch_type") != action["type"] or
                    step.get("action_payload_sha256") != digest(payload.encode()) or
                    qwen_v066_adapter.prior.application_frame_digest(observed) !=
                    qwen_v066_adapter.prior.application_frame_digest(predispatch)):
                raise ValueError("Public-train GUI action lacked current-frame proof")
        for row in receipt.get("physical_frame_resamples", []):
            _bound_file(output_root, row["observed"])
            _bound_file(output_root, row["changed"])
        saved = _bound_file(output_root, receipt["saved_artifact"])
        fair = verify(baseline, saved, oracle)
        expected_pass = attempt == "positive"
        if (saved == baseline or
                fair != receipt.get("train_saved_artifact_verifier") or
                fair["passed"] is not expected_pass or
                (not expected_pass and (not fair["errors"] or
                    any(not item.startswith("target_") for item in
                        fair["errors"])))):
            raise ValueError("Public-train saved PPTX verifier disagreed")
    return {"attempt": attempt,
            "receipt_sha256": digest(receipt_raw),
            "intent_sha256": digest(intent_raw),
            "sandbox_id_sha256": receipt["sandbox_id_sha256"],
            "applied_actor_actions": len(steps),
            "saved_verifier_passed": attempt == "positive"}


def audit_trio(*, output_root: Path, scoped_reference: Path,
               guest_public: Path,
               diagnostic_reservation: Path) -> tuple[dict, dict]:
    rows = [audit_one(
        output_root=output_root, attempt=attempt,
        scoped_reference=scoped_reference, guest_public=guest_public,
        diagnostic_reservation=diagnostic_reservation)
            for attempt in ATTEMPTS]
    if len({row["sandbox_id_sha256"] for row in rows}) != 3:
        raise ValueError("Public-train GUI controls reused an E2B guest")
    private = {
        "schema": "cua-native-wdi-v066-scoped-profile-train-trio-audit-private-v1",
        "status": "public_train_gui_positive_near_reset_passed",
        "controls": rows,
        "official_final_admissions": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-scoped-profile-train-trio-audit-public-v1",
        "status": private["status"],
        "distinct_train_guests": 3,
        "positive_saved_artifact_passed": True,
        "near_miss_target_only_rejected": True,
        "fresh_reset_input_restored": True,
        "raw_observation_predispatch_profiles_reopened": True,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
