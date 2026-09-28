"""V2 read-only audit of full v0.6.6 envelopes and saved train OOXML.

The source-bound v1 auditor compared a normalized action to the minimal GUI
script dict, omitting the v0.6.6 task/frame/step envelope. It remains intact.
This separate pre-SFT auditor validates both the envelope and script fields
against the same retained raw frames, then independently scores saved files.
"""

from __future__ import annotations

import json
from pathlib import Path

from cursibench.scale_action_contract import VERSION

from . import (qwen_v066_adapter, v066_profile_scope_analysis as scope,
               v066_scoped_calc_writer_train_demo as demo,
               v066_scoped_calc_writer_train_demo_audit as historical_audit,
               v066_scoped_profile_guard as guard)
from .v066_final_control_audit import _bound_file
from .v066_final_freeze import digest
from .v066_scoped_profile_reference import validate_reference
from .verify import verify


def _action_envelope_matches(*, step: dict, normalized: dict,
                             expected: dict, package: dict,
                             index: int) -> bool:
    envelope = {"version", "task_id", "task_binding_sha256",
                "frame_id", "step", "memory"}
    projected = {key: normalized.get(key) for key in expected}
    return (
        set(normalized) == set(expected) | envelope and
        projected == expected and
        normalized.get("version") == VERSION and
        normalized.get("task_id") == package["task_id"] and
        normalized.get("task_binding_sha256") ==
        package["package_sha256"] and
        normalized.get("step") == index and
        normalized.get("memory") == "" and
        type(normalized.get("frame_id")) is str and
        digest(normalized["frame_id"].encode()) ==
        step.get("frame_id_sha256") and
        step.get("normalized_action_sha256") == digest(json.dumps(
            normalized, sort_keys=True,
            separators=(",", ":")).encode()))


def audit_one(*, output_root: Path, kind: str,
              scoped_reference: Path, guest_public: Path,
              reservation_path: Path) -> dict:
    package, oracle, baseline, _instruction, _filename = demo._source(kind)
    reference, reference_sha = validate_reference(scoped_reference)
    expected_profile = reference["applications"][kind]
    root = output_root / kind
    intent_raw = (root / "intent.json").read_bytes()
    receipt_raw = (root / "receipt.json").read_bytes()
    intent, receipt = json.loads(intent_raw), json.loads(receipt_raw)
    reservation_raw = reservation_path.read_bytes()
    reservation_sha = digest(reservation_raw)
    reservation = json.loads(reservation_raw)
    if (reservation.get("schema") != demo.RESERVATION_SCHEMA or
            reservation.get("status") !=
            "reserved_before_two_public_train_gui_creates" or
            reservation.get("demo_source_sha256") !=
            digest(Path(demo.__file__).read_bytes()) or
            reservation.get("demo_audit_source_sha256") !=
            digest(Path(historical_audit.__file__).read_bytes())):
        raise ValueError("Original Calc/Writer demo source freeze changed")
    if (intent.get("schema") !=
            "cua-native-wdi-v066-calc-writer-train-demo-intent-v1" or
            intent.get("kind") != kind or intent.get("split") != "train" or
            intent.get("package_sha256") != package["package_sha256"] or
            intent.get("demo_source_sha256") !=
            digest(Path(demo.__file__).read_bytes()) or
            intent.get("scoped_reference_sha256") != reference_sha or
            intent.get("reservation_sha256") != reservation_sha or
            intent.get("automatic_replay_authorized") is not False or
            receipt.get("schema") !=
            "cua-native-wdi-gui-development-attempt-v1" or
            receipt.get("purpose") !=
            "v066_scoped_public_train_calc_writer_gui_positive_no_model" or
            receipt.get("kind") != kind or receipt.get("split") != "train" or
            receipt.get("status") != "train_gui_positive_passed" or
            receipt.get("package_sha256") != package["package_sha256"] or
            receipt.get("input_sha256") != digest(baseline) or
            receipt.get("demo_source_sha256") !=
            digest(Path(demo.__file__).read_bytes()) or
            receipt.get("action_adapter_sha256") !=
            digest(Path(qwen_v066_adapter.__file__).read_bytes()) or
            receipt.get("profile_guard_source_sha256") !=
            digest(Path(guard.__file__).read_bytes()) or
            receipt.get("scoped_reference_sha256") != reference_sha or
            receipt.get("reservation_sha256") != reservation_sha or
            receipt.get("guest_identity_public_sha256") !=
            digest(guest_public.read_bytes()) or
            receipt.get("guest_content_attested") is not True or
            receipt.get("fresh_profile_absent") is not True or
            type(receipt.get("trusted_setup_ready")) is not dict or
            receipt.get("task_profile_scoped_attested") is not True or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            receipt.get("official_final_model_attempts") != 0 or
            receipt.get("official_final_admissions") != 0):
        raise ValueError("Calc/Writer train source, profile, or cleanup changed")
    snapshots = receipt.get("task_profile_scoped_snapshots", [])
    if len(snapshots) != 2:
        raise ValueError("Calc/Writer raw profile pair absent")
    for index, snapshot in enumerate(snapshots):
        if snapshot.get("label") != ("first", "second")[index]:
            raise ValueError("Calc/Writer raw profile order changed")
        manifest = _bound_file(output_root, snapshot["manifest"])
        registry = _bound_file(output_root, snapshot["registry"])
        _bound_file(output_root, snapshot["visible_frame"])
        if scope.scoped_profile(json.loads(manifest), registry) != expected_profile:
            raise ValueError("Calc/Writer profile differs from public train reference")
    actions = demo.actor_actions(kind, oracle)
    applied = receipt.get("normalized_actor_actions", [])
    if (len(applied) != len(actions) or
            receipt.get("actor_gui_actions") != len(actions)):
        raise ValueError("Calc/Writer public-train action count changed")
    for index, (step, expected) in enumerate(zip(applied, actions)):
        observed = _bound_file(output_root, step["observation"])
        predispatch = _bound_file(output_root, step["predispatch"])
        normalized = step.get("normalized_action")
        if type(normalized) is not dict:
            raise ValueError("v0.6.6 normalized action object missing")
        if (step.get("step") != index or step.get("status") != "applied" or
                not _action_envelope_matches(
                    step=step, normalized=normalized,
                    expected=expected, package=package, index=index) or
                step.get("dispatch_type") != expected["type"] or
                step.get("script_payload_sha256") != digest(json.dumps(
                    expected, separators=(",", ":")).encode()) or
                qwen_v066_adapter.prior.application_frame_digest(observed) !=
                qwen_v066_adapter.prior.application_frame_digest(predispatch)):
            raise ValueError("Calc/Writer action lacks current-frame proof")
    for row in receipt.get("physical_frame_resamples", []):
        _bound_file(output_root, row["observed"])
        _bound_file(output_root, row["changed"])
    saved = _bound_file(output_root, receipt["saved_artifact"])
    independent = verify(baseline, saved, oracle)
    if (saved == baseline or independent.get("passed") is not True or
            independent != receipt.get("independent_saved_verifier") or
            receipt.get("saved_sha256") != digest(saved)):
        raise ValueError("Calc/Writer independently saved OOXML verdict changed")
    return {"kind": kind,
            "intent_sha256": digest(intent_raw),
            "receipt_sha256": digest(receipt_raw),
            "sandbox_id_sha256": receipt["sandbox_id_sha256"],
            "applied_current_frame_actions": len(actions),
            "saved_artifact_verifier_passed": True}


def audit_both(*, output_root: Path, scoped_reference: Path,
               guest_public: Path,
               reservation_path: Path) -> tuple[dict, dict]:
    run_raw = (output_root / "run-receipt.json").read_bytes()
    journal = json.loads(run_raw)
    if (journal.get("schema") !=
            "cua-native-wdi-v066-calc-writer-train-demo-run-v1" or
            journal.get("status") !=
            "two_public_train_gui_positives_pending_audit" or
            journal.get("demo_source_sha256") !=
            digest(Path(demo.__file__).read_bytes()) or
            journal.get("reservation_sha256") !=
            digest(reservation_path.read_bytes()) or
            len(journal.get("attempts", [])) != 2 or
            any(row.get("status") != "train_gui_positive_passed"
                for row in journal["attempts"])):
        raise ValueError("Calc/Writer train demo journal incomplete")
    rows = [audit_one(
        output_root=output_root, kind=kind,
        scoped_reference=scoped_reference,
        guest_public=guest_public,
        reservation_path=reservation_path)
            for kind in demo.KINDS]
    for expected_kind, outcome, audited in zip(
            demo.KINDS, journal["attempts"], rows):
        if (outcome.get("kind") != expected_kind or
                outcome.get("receipt_sha256") != audited["receipt_sha256"] or
                outcome.get("cleanup_verified") is not True):
            raise ValueError("Calc/Writer serial journal disagrees with raw receipt")
    if len({row["sandbox_id_sha256"] for row in rows}) != 2:
        raise ValueError("Calc/Writer demos reused an E2B guest")
    private = {
        "schema": "cua-native-wdi-v066-calc-writer-train-demo-audit-v2-private-v1",
        "status": "two_distinct_train_gui_positives_passed",
        "run_journal_sha256": digest(run_raw),
        "historical_auditor_source_sha256": digest(
            Path(historical_audit.__file__).read_bytes()),
        "v2_auditor_source_sha256": digest(Path(__file__).read_bytes()),
        "demos": rows,
        "official_final_admissions": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-calc-writer-train-demo-audit-v2-public-v1",
        "status": private["status"],
        "distinct_public_train_workflows": 2,
        "distinct_e2b_guests": 2,
        "current_frame_actions_total": sum(
            row["applied_current_frame_actions"] for row in rows),
        "actor_saved_xlsx_and_docx_independently_verified": True,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
