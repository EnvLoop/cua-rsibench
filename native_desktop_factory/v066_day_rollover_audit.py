"""Independent raw-byte audit of the Desktop Sep 28/29 UI date rollover.

All references come from public training guests. The two failed final-control
guests are reopened only to explain their pre-action interruption; they are
never admitted or used as a model result. This module never creates a sandbox.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

from . import (v066_profile_scope_analysis as scope,
               v066_public_calc_profile_probe as calc_probe)
from .v066_caret_full100_preflight import _tree_digest
from .profile_canonical import canonical_registry
from .v066_final_freeze import digest
from .v066_storage_budget import audit as storage_audit


OLD_LABELS = {"calc-second": "calc", "writer-first": "writer",
              "writer-second": "writer", "impress-first": "impress",
              "impress-second": "impress"}
TIP_VALUE = re.compile(
    rb'(<prop[^>]*name="LastTipOfTheDayShown"[^>]*><value>)'
    rb'([0-9]{5})(</value></prop>)')


def _tip_day(registry: bytes) -> tuple[int, bytes]:
    canonical = canonical_registry(registry)
    matches = TIP_VALUE.findall(canonical)
    if len(matches) != 1:
        raise ValueError("Exactly one LibreOffice tip calendar day is required")
    day = int(matches[0][1])
    if not scope.TIP_DAY_MIN <= day <= scope.TIP_DAY_MAX:
        raise ValueError("LibreOffice tip day outside the frozen date range")
    return day, TIP_VALUE.sub(rb'\g<1><calendar-day>\g<3>', canonical)


def _capture(directory: Path, snapshot: dict, *, final: bool = False) -> tuple[str, bytes, dict]:
    label = snapshot["label"]
    manifest = (directory / f"profile-{label}.manifest.json").read_bytes()
    registry = (directory / f"profile-{label}.registry.xml").read_bytes()
    if final:
        frame = (directory / f"profile-{label}.png").read_bytes()
        if (snapshot["manifest"]["sha256"] != digest(manifest) or
                snapshot["registry"]["sha256"] != digest(registry) or
                not frame or snapshot["visible_frame"]["sha256"] !=
                digest(frame)):
            raise ValueError("Failed-final raw profile capture changed")
    elif (snapshot.get("manifest_sha256") != digest(manifest) or
          snapshot.get("registry_sha256") != digest(registry)):
        raise ValueError("Public-train raw profile capture changed")
    rows = json.loads(manifest)
    return scope.scoped_profile(rows, registry), registry, {
        row["path"]: row["sha256"] for row in rows
        if row["path"] != "registrymodifications.xcu"}


def _train(directory: Path, *, expected_receipt_sha: str,
           expected_intent_sha: str | None = None) -> tuple[str, bytes, dict, str]:
    receipt_raw = (directory / "receipt.json").read_bytes()
    if digest(receipt_raw) != expected_receipt_sha:
        raise ValueError("Preserved public-train receipt changed")
    receipt = json.loads(receipt_raw)
    if (receipt.get("split") != "train" or
            receipt.get("status") not in
            {"train_profile_captured", "profile_diagnostic_captured"} or
            receipt.get("guest_content_attested") is not True or
            receipt.get("input_unchanged_after_open") is not True or
            receipt.get("actor_gui_actions") != 0 or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            len(receipt.get("profile_snapshots", [])) != 4):
        raise ValueError("Public-train neutral capture or cleanup changed")
    if expected_intent_sha is not None and digest(
            (directory / "intent.json").read_bytes()) != expected_intent_sha:
        raise ValueError("Preserved public-train intent changed")
    if digest((directory / "neutral-open.png").read_bytes()) != receipt.get(
            "neutral_open_screenshot_sha256"):
        raise ValueError("Public-train visible neutral frame changed")
    fingerprints, registries, files = [], [], []
    for snapshot in receipt["profile_snapshots"]:
        fingerprint, registry, manifest_files = _capture(directory, snapshot)
        fingerprints.append(fingerprint)
        registries.append(registry)
        files.append(manifest_files)
    if len(set(fingerprints)) != 1 or any(item != files[0] for item in files):
        raise ValueError("Public-train profile did not settle")
    return fingerprints[0], registries[1], files[0], receipt["sandbox_id_sha256"]


def audit(*, prior_calc: Path, old_five_root: Path,
          old_five_audit: Path, current_calc: Path,
          current_reservation: Path,
          failed_scoped_root: Path, failed_run_journal: Path,
          candidate_root: Path) -> tuple[dict, dict]:
    previous = json.loads(old_five_audit.read_bytes())
    if (previous.get("status") != "three_app_pairs_passed" or
            previous.get("provider_active_zero_after") is not True or
            previous.get("distinct_sandbox_count") != 6 or
            len(previous.get("per_guest", [])) != 5 or
            set(row["label"] for row in previous["per_guest"]) !=
            set(OLD_LABELS)):
        raise ValueError("Historical public-train six-guest audit changed")
    prior_fp, prior_registry, prior_files, prior_id = _train(
        prior_calc, expected_receipt_sha=previous["prior_calc_receipt_sha256"])
    groups: dict[str, list[str]] = defaultdict(list)
    groups["calc"].append(prior_fp)
    ids = {prior_id}
    for row in previous["per_guest"]:
        label = row["label"]
        fingerprint, _registry, _files, sandbox_id = _train(
            old_five_root / label,
            expected_receipt_sha=row["receipt_sha256"],
            expected_intent_sha=row["intent_sha256"])
        if sandbox_id != row["sandbox_id_sha256"] or sandbox_id in ids:
            raise ValueError("Historical public-train sandbox identity changed")
        ids.add(sandbox_id)
        groups[OLD_LABELS[label]].append(fingerprint)
    if (len(ids) != 6 or set(groups) != {"calc", "writer", "impress"} or
            any(len(values) != 2 or values[0] != values[1]
                for values in groups.values())):
        raise ValueError("New scope breaks same-application public-train pairs")
    current_intent_raw = (current_calc / "intent.json").read_bytes()
    current_receipt_raw = (current_calc / "receipt.json").read_bytes()
    current_intent = json.loads(current_intent_raw)
    current_receipt = json.loads(current_receipt_raw)
    if (current_intent.get("split") != "train" or
            current_intent.get("automatic_replay_authorized") is not False or
            current_intent.get("source_sha256") !=
            digest(Path(calc_probe.__file__).read_bytes()) or
            current_intent.get("reservation_sha256") !=
            digest(current_reservation.read_bytes()) or
            current_receipt.get("source_sha256") !=
            digest(Path(calc_probe.__file__).read_bytes()) or
            current_receipt.get("reservation_sha256") !=
            digest(current_reservation.read_bytes()) or
            current_receipt.get("official_final_model_attempts") != 0 or
            current_receipt.get("package_sha256") !=
            json.loads((prior_calc / "receipt.json").read_bytes())[
                "package_sha256"]):
        raise ValueError("Current-day public Calc source changed")
    current_fp, current_registry, current_files, current_id = _train(
        current_calc, expected_receipt_sha=digest(current_receipt_raw),
        expected_intent_sha=digest(current_intent_raw))
    if current_id in ids or current_fp != groups["calc"][0] or (
            current_files != prior_files):
        raise ValueError("Current public Calc is not the same scoped training guest")
    old_day, old_masked = _tip_day(prior_registry)
    new_day, new_masked = _tip_day(current_registry)
    if new_day != old_day + 1 or old_masked != new_masked:
        raise ValueError("Public Calc date rollover changed another registry field")
    captured = datetime.fromisoformat(current_receipt["profile_snapshots"][1][
        "captured_utc"]).astimezone(timezone.utc).date()
    if (captured - date(1970, 1, 1)).days != new_day:
        raise ValueError("Current public Calc tip day does not match capture date")

    run_raw = failed_run_journal.read_bytes()
    run = json.loads(run_raw)
    failed_ids = {row["private_task_id"] for row in run["task_outcomes"]
                  if row.get("status") ==
                  "stopped_after_invalid_or_uncertain_attempt"}
    if (run.get("status") != "stopped_for_reconciliation" or
            len(run.get("selected_private_task_ids", [])) != 100 or
            failed_ids != set(run["selected_private_task_ids"][:2]) or
            run.get("official_final_model_attempts") != 0 or
            run.get("official_final_admissions") != 0):
        raise ValueError("Failed scoped run is not the frozen first-two interruption")
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    final = {row["task_id"]: row for row in inventory["tasks"]
             if row.get("split") == "final_candidate"}
    if len(final) != 100 or not failed_ids <= set(final):
        raise ValueError("Failed scoped IDs differ from frozen 100")
    storage_audit(failed_scoped_root, verify_all_bytes=True)
    failed_receipts = []
    failed_sandbox_ids = set()
    for task_id in sorted(failed_ids):
        directory = failed_scoped_root / task_id / "positive"
        receipt_raw = (directory / "receipt.json").read_bytes()
        receipt = json.loads(receipt_raw)
        intent = json.loads((directory / "intent.json").read_bytes())
        if (receipt.get("package_sha256") != final[task_id]["package_sha256"] or
                receipt.get("status") != "control_failed_or_infrastructure_invalid" or
                receipt.get("error_type") != "ScopedProfileDrift" or
                receipt.get("guest_content_attested") is not True or
                receipt.get("task_profile_scoped_self_stable") is not True or
                receipt.get("task_profile_scoped_matches_public_train") is not False or
                receipt.get("actor_steps") != [] or
                receipt.get("kill_returned") is not True or
                receipt.get("is_running_after_kill") is not False or
                receipt.get("official_hidden_final_model_attempts") != 0 or
                intent.get("task_id") != task_id or
                len(receipt.get("task_profile_scoped_snapshots", [])) != 2):
            raise ValueError("Failed final guest did more than a neutral profile check")
        values = []
        files = []
        for snapshot in receipt["task_profile_scoped_snapshots"]:
            fingerprint, registry, manifest_files = _capture(
                directory, snapshot, final=True)
            day, _masked = _tip_day(registry)
            captured_day = (datetime.fromisoformat(
                snapshot["captured_utc"]).astimezone(timezone.utc).date() -
                date(1970, 1, 1)).days
            if day != new_day or captured_day != day:
                raise ValueError("Failed final guest did not share current public day")
            values.append(fingerprint)
            files.append(manifest_files)
        if values != [current_fp, current_fp] or files != [current_files] * 2:
            raise ValueError("Failed final differs from public Calc after date mask")
        sandbox_id = receipt["sandbox_id_sha256"]
        if sandbox_id in ids or sandbox_id in failed_sandbox_ids:
            raise ValueError("Public/final E2B guest was reused")
        failed_sandbox_ids.add(sandbox_id)
        failed_receipts.append(digest(receipt_raw))
    private = {
        "schema": "cua-native-wdi-v066-day-rollover-raw-audit-private-v1",
        "status": "public_train_date_rollover_corroborated_final_failures_retained",
        "audit_source_sha256": digest(Path(__file__).read_bytes()),
        "scoped_analysis_source_sha256": digest(Path(scope.__file__).read_bytes()),
        "old_six_train_audit_sha256": digest(old_five_audit.read_bytes()),
        "prior_public_train_tree_sha256": _tree_digest(prior_calc)[0],
        "old_five_public_train_tree_sha256": _tree_digest(old_five_root)[0],
        "current_public_train_tree_sha256": _tree_digest(current_calc)[0],
        "failed_scoped_attempt_tree_sha256": _tree_digest(failed_scoped_root)[0],
        "current_public_train_receipt_sha256": digest(current_receipt_raw),
        "current_public_train_intent_sha256": digest(current_intent_raw),
        "failed_scoped_run_journal_sha256": digest(run_raw),
        "failed_scoped_receipt_sha256s": sorted(failed_receipts),
        "old_tip_day": old_day,
        "current_tip_day": new_day,
        "old_six_same_application_pairs_passed": 3,
        "current_day_train_equal_under_new_scope": True,
        "canonical_public_train_equal_after_tip_day_mask": True,
        "failed_final_guests_diagnosed_no_actions": 2,
        "old_six_public_sandbox_count": 6,
        "new_public_sandbox_count": 1,
        "failed_final_sandbox_count": 2,
        "scoped_reference_application_sha256s": {
            kind: values[0] for kind, values in groups.items()},
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-day-rollover-raw-audit-public-v1",
        "status": "pre_result_environment_date_amendment_not_final_admission",
        "old_six_same_application_pairs_passed": 3,
        "current_day_public_train_neutral_guests_passed": 1,
        "failed_final_pre_action_guests_retained": 2,
        "changed_registry_property": "LastTipOfTheDayShown",
        "calendar_day_increment": 1,
        "nonregistry_files_identical": True,
        "other_canonical_public_train_registry_fields_identical": True,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
