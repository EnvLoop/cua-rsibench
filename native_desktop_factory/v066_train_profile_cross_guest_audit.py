"""Independent read-only audit of six public-train LibreOffice guests.

The first Calc guest predates this five-guest controller. This auditor reopens
all raw capture bytes, checks same-app cross-guest scoped identity, and mutates
retained settings/recovery state/non-registry hashes in memory as negative
controls. It never changes an official final-task profile acceptance rule.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError

from . import (qwen_v066_adapter, v066_profile_scope_analysis as scope,
               v066_train_profile_cross_guest as train)
from .v066_final_freeze import digest


def _raw_capture(path: Path, snapshot: dict) -> tuple[list[dict], bytes, str]:
    label = snapshot["label"]
    manifest = (path / f"profile-{label}.manifest.json").read_bytes()
    registry = (path / f"profile-{label}.registry.xml").read_bytes()
    if (digest(manifest) != snapshot["manifest_sha256"] or
            digest(registry) != snapshot["registry_sha256"]):
        raise ValueError("Raw train profile capture changed")
    if "frame_sha256" in snapshot:
        frame = (path / f"frame-{label}.png").read_bytes()
        if (digest(frame) != snapshot["frame_sha256"] or
                len(frame) != snapshot.get("frame_bytes")):
            raise ValueError("Raw train visible frame changed")
        try:
            with Image.open(io.BytesIO(frame)) as image:
                if image.format != "PNG" or image.size != (1280, 800):
                    raise ValueError("Raw train visible frame shape changed")
        except (UnidentifiedImageError, OSError):
            raise ValueError("Raw train visible frame is invalid") from None
    rows = json.loads(manifest)
    fingerprint = scope.scoped_profile(rows, registry)
    if ("scoped_profile_sha256" in snapshot and
            snapshot["scoped_profile_sha256"] != fingerprint):
        raise ValueError("Recorded train scoped profile changed")
    return rows, registry, fingerprint


def _alter_registry(rows: list[dict], raw: bytes,
                    property_name: str) -> str:
    pattern = re.compile(
        rb'(<prop oor:name="' + property_name.encode() +
        rb'"[^>]*><value>)([^<]*)(</value></prop>)')
    if len(pattern.findall(raw)) != 1:
        raise ValueError("Negative-control setting field missing or duplicated")
    changed = pattern.sub(
        lambda match: match.group(1) + b"__negative_setting_change__" +
        match.group(3), raw)
    edited = [dict(row) for row in rows]
    for row in edited:
        if row["path"] == "registrymodifications.xcu":
            row["sha256"] = digest(changed)
            row["bytes"] = len(changed)
    return scope.scoped_profile(edited, changed)


def _negative_controls(rows: list[dict], registry: bytes) -> dict:
    original = scope.scoped_profile(rows, registry)
    setting = _alter_registry(rows, registry, "ooSetupLastVersion")
    recovery = _alter_registry(rows, registry, "DocumentState")
    edited = [dict(row) for row in rows]
    candidates = [row for row in edited
                  if row["path"] != "registrymodifications.xcu"]
    if not candidates:
        raise ValueError("No non-registry profile file to mutate")
    candidates[0]["sha256"] = (
        "0" * 64 if candidates[0]["sha256"] != "0" * 64 else "1" * 64)
    file_change = scope.scoped_profile(edited, registry)
    return {"setting_detected": setting != original,
            "recovery_state_detected": recovery != original,
            "nonregistry_file_detected": file_change != original}


def _new_guest(path: Path, *, label: str, kind: str,
               reservation_sha256: str) -> dict:
    intent_raw = (path / "intent.json").read_bytes()
    receipt_raw = (path / "receipt.json").read_bytes()
    intent, receipt = json.loads(intent_raw), json.loads(receipt_raw)
    if (intent.get("schema") !=
            "cua-native-wdi-v066-train-profile-cross-guest-intent-v1" or
            intent.get("label") != label or intent.get("kind") != kind or
            intent.get("split") != "train" or
            intent.get("package_sha256") !=
            train._source(kind)[0]["package_sha256"] or
            intent.get("calibration_source_sha256") !=
            digest(Path(train.__file__).read_bytes()) or
            intent.get("reservation_sha256") != reservation_sha256 or
            intent.get("lease_seconds") != train.LEASE_SECONDS or
            intent.get("automatic_replay_authorized") is not False or
            receipt.get("schema") != train.RECEIPT_SCHEMA or
            receipt.get("purpose") !=
            "v066_public_train_profile_cross_guest_no_model" or
            receipt.get("label") != label or receipt.get("kind") != kind or
            receipt.get("split") != "train" or
            receipt.get("status") != "train_profile_captured" or
            receipt.get("guest_content_attested") is not True or
            receipt.get("fresh_profile_absent") is not True or
            receipt.get("input_unchanged_after_open") is not True or
            receipt.get("actor_gui_actions") != 0 or
            receipt.get("official_final_model_attempts") != 0 or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            receipt.get("calibration_source_sha256") !=
            digest(Path(train.__file__).read_bytes()) or
            receipt.get("scoped_analysis_source_sha256") !=
            digest(Path(scope.__file__).read_bytes()) or
            receipt.get("reservation_sha256") != reservation_sha256 or
            receipt.get("package_sha256") !=
            train._source(kind)[0]["package_sha256"] or
            len(receipt.get("profile_snapshots", [])) != 4):
        raise ValueError("Public-train guest source, cleanup, or raw capture invalid")
    fingerprints = []
    first_rows, first_registry = None, None
    for index, snapshot in enumerate(receipt["profile_snapshots"]):
        if (snapshot.get("label") != train.SNAPSHOTS[index][0] or
                type(snapshot.get("frame_sha256")) is not str):
            raise ValueError("Public-train profile capture order changed")
        rows, registry, fingerprint = _raw_capture(path, snapshot)
        fingerprints.append(fingerprint)
        if index == 0:
            first_rows, first_registry = rows, registry
    if len(set(fingerprints)) != 1:
        raise ValueError("Scoped train profile changed within one guest")
    screenshot = (path / "neutral-open.png").read_bytes()
    if digest(screenshot) != receipt.get("neutral_open_screenshot_sha256"):
        raise ValueError("Neutral GUI screenshot changed")
    negatives = _negative_controls(first_rows, first_registry)
    if not all(negatives.values()):
        raise ValueError("Profile setting negative control was missed")
    return {"label": label, "kind": kind,
            "sandbox_id_sha256": receipt["sandbox_id_sha256"],
            "scoped_profile_sha256": fingerprints[0],
            "receipt_sha256": digest(receipt_raw),
            "intent_sha256": digest(intent_raw),
            "negative_controls": negatives}


def audit(*, output_root: Path, prior_calc_dir: Path,
          reservation_path: Path) -> tuple[dict, dict]:
    reservation_raw = reservation_path.read_bytes()
    reservation = json.loads(reservation_raw)
    if (reservation.get("schema") != train.RESERVATION_SCHEMA or
            reservation.get("calibration_source_sha256") !=
            digest(Path(train.__file__).read_bytes()) or
            reservation.get("scoped_analysis_source_sha256") !=
            digest(Path(scope.__file__).read_bytes()) or
            reservation.get("calibration_audit_source_sha256") !=
            digest(Path(__file__).read_bytes()) or
            reservation.get("desktop_adapter_sha256") !=
            digest(Path(qwen_v066_adapter.__file__).read_bytes()) or
            reservation.get("new_full_lease_intents_reserved") != len(train.PLAN)):
        raise ValueError("Public-train calibration source freeze changed")
    run_raw = (output_root / "run-receipt.json").read_bytes()
    run = json.loads(run_raw)
    if (run.get("schema") !=
            "cua-native-wdi-v066-train-profile-cross-guest-run-v1" or
            run.get("status") !=
            "all_raw_train_profiles_captured_pending_audit" or
            run.get("reservation_sha256") != digest(reservation_raw) or
            len(run.get("attempts", [])) != len(train.PLAN) or
            any(row.get("status") != "train_profile_captured"
                for row in run["attempts"])):
        raise ValueError("Public-train calibration journal incomplete")
    prior, prior_raw, prior_audit_raw = train._prior_calc(prior_calc_dir)
    if (reservation.get("prior_public_calc_receipt_sha256") !=
            digest(prior_raw) or
            reservation.get("prior_public_calc_post_audit_sha256") !=
            digest(prior_audit_raw)):
        raise ValueError("Prior public Calc guest is not bound")
    prior_fingerprints = [_raw_capture(prior_calc_dir, snap)[2]
                          for snap in prior["profile_snapshots"]]
    if len(set(prior_fingerprints)) != 1:
        raise ValueError("Prior public Calc scoped profile was not stable")
    prior_negatives = _negative_controls(*_raw_capture(
        prior_calc_dir, prior["profile_snapshots"][0])[:2])
    if not all(prior_negatives.values()):
        raise ValueError("Prior Calc negative control missed a setting")
    records = [_new_guest(output_root / label, label=label, kind=kind,
                          reservation_sha256=digest(reservation_raw))
               for label, kind in train.PLAN]
    by_label = {row["label"]: row for row in records}
    pairs = {
        "calc": [prior_fingerprints[0],
                 by_label["calc-second"]["scoped_profile_sha256"]],
        "writer": [by_label["writer-first"]["scoped_profile_sha256"],
                   by_label["writer-second"]["scoped_profile_sha256"]],
        "impress": [by_label["impress-first"]["scoped_profile_sha256"],
                    by_label["impress-second"]["scoped_profile_sha256"]],
    }
    pair_passes = {kind: left == right
                   for kind, (left, right) in pairs.items()}
    ids = {row["sandbox_id_sha256"] for row in records}
    ids.add(prior.get("sandbox_id_sha256"))
    if len(ids) != 6:
        raise ValueError("Public-train calibration guests were not distinct")
    private = {
        "schema": "cua-native-wdi-v066-train-profile-calibration-audit-private-v1",
        "status": "three_app_pairs_passed" if all(pair_passes.values()) else
                  "cross_guest_mismatch_retained_not_ratified",
        "reservation_sha256": digest(reservation_raw),
        "run_journal_sha256": digest(run_raw),
        "prior_calc_receipt_sha256": digest(prior_raw),
        "per_guest": records,
        "pair_passes": pair_passes,
        "distinct_sandbox_count": len(ids),
        "official_final_admissions": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-train-profile-calibration-audit-public-v1",
        "scope": "public_train_only_no_model_no_final_control",
        "status": private["status"],
        "public_train_guest_count": len(ids),
        "new_paid_train_guests": len(records),
        "same_app_cross_guest_pairs_tested": 3,
        "same_app_cross_guest_pairs_passed": sum(pair_passes.values()),
        "setting_recovery_and_nonregistry_negatives_passed":
            all(all(row["negative_controls"].values()) for row in records)
            and all(prior_negatives.values()),
        "calibration_source_sha256":
            reservation["calibration_source_sha256"],
        "scoped_analysis_source_sha256":
            reservation["scoped_analysis_source_sha256"],
        "reservation_sha256": digest(reservation_raw),
        "run_journal_sha256": digest(run_raw),
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
