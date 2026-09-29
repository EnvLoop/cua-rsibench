"""Independent saved-OOXML and scoped-profile audit of a future fresh 100.

This checks every raw profile capture, source-bound E2B receipt, positive,
near-miss, and cold reset. It never converts provisional controls into an
official model result or a six-cell qualified manifest by itself.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
import json
from pathlib import Path

from . import (qwen_v066_adapter, v066_profile_scope_analysis as scope,
               v066_scoped_profile_final_attempt as attempt_module,
               v066_scoped_profile_guard as guard)
from .v066_caret_full100_preflight import _read_only_storage
from .v066_final_control_audit import _bound_file, _validate_trio
from .v066_final_freeze import digest, intent_budget
from .v066_scoped_profile_bridge import validate as validate_bridge
from .v066_scoped_profile_reference import (
    validate_reference, workflow_kind,
)


ATTEMPTS = ("positive", "near-miss", "cold-reset")


def _profile_receipt(*, candidate_root: Path, attempts_root: Path,
                     task_id: str, workflow: str,
                     reference: dict, reference_sha: str,
                     runtime_sha: str, bridge_sha: str) -> list[str]:
    kind = workflow_kind(workflow)
    expected = reference["applications"][kind]
    sandbox_ids = []
    for attempt in ATTEMPTS:
        path = attempts_root / task_id / attempt
        intent = json.loads((path / "intent.json").read_bytes())
        receipt = json.loads((path / "receipt.json").read_bytes())
        if (intent.get("scoped_reference_sha256") != reference_sha or
                intent.get("scoped_runtime_freeze_sha256") != runtime_sha or
                intent.get("three_root_bridge_sha256") != bridge_sha or
                receipt.get("runner_sha256") !=
                digest(Path(attempt_module.__file__).read_bytes()) or
                receipt.get("profile_scope_guard_source_sha256") !=
                digest(Path(guard.__file__).read_bytes()) or
                receipt.get("native_adapter_sha256") !=
                digest(Path(qwen_v066_adapter.__file__).read_bytes()) or
                receipt.get("profile_reference_private_sha256") !=
                reference_sha or
                receipt.get("scoped_runtime_freeze_sha256") != runtime_sha or
                receipt.get("three_root_bridge_sha256") != bridge_sha or
                receipt.get("profile_application_kind") != kind or
                receipt.get("task_profile_scoped_attested") is not True or
                receipt.get("task_profile_scoped_self_stable") is not True or
                receipt.get("task_profile_scoped_matches_public_train") is not True or
                receipt.get("task_profile_scoped_sha256") != expected or
                len(receipt.get("task_profile_scoped_snapshots", [])) != 2):
            raise ValueError("Fresh scoped-control source or profile guard invalid")
        scoped_values = []
        tip_days = []
        for index, snapshot in enumerate(receipt["task_profile_scoped_snapshots"]):
            label = ("first", "second")[index]
            if snapshot.get("label") != label:
                raise ValueError("Scoped raw profile capture order changed")
            manifest = _bound_file(attempts_root, snapshot["manifest"])
            registry = _bound_file(attempts_root, snapshot["registry"])
            _bound_file(attempts_root, snapshot["visible_frame"])
            if (snapshot.get("profile_probe_script_sha256") !=
                    digest(guard.runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())):
                raise ValueError("Scoped raw profile probe source changed")
            scoped = scope.scoped_profile(json.loads(manifest), registry)
            if scoped != snapshot.get("scoped_profile_sha256"):
                raise ValueError("Scoped raw profile recalculation disagrees")
            scoped_values.append(scoped)
            if reference.get("current_public_tip_day") is not None:
                tip_days.append(scope.tip_calendar_day(registry))
        if scoped_values != [expected, expected]:
            raise ValueError("Scoped raw profile is not the public-train reference")
        day_floor = reference.get("current_public_tip_day")
        if day_floor is not None:
            if (reference.get("prior_public_tip_day") != day_floor - 1 or
                    tip_days != [receipt.get("task_profile_tip_calendar_day")] * 2 or
                    receipt.get("task_profile_tip_day_reference_floor") != day_floor or
                    receipt.get("task_profile_tip_day_matches_guest_clock") is not True or
                    len(receipt.get("guest_calendar_probes", [])) != 2):
                raise ValueError("Guest calendar bound to prior public train day is absent")
            guest_days = set()
            for label, probe in zip(("before", "after"),
                                    receipt["guest_calendar_probes"]):
                raw = _bound_file(attempts_root, probe["raw"])
                values = raw.decode().splitlines()
                if len(values) != 2 or probe.get("label") != label:
                    raise ValueError("Raw guest UTC/local date probe changed")
                parsed = [(date.fromisoformat(item) - date(1970, 1, 1)).days
                          for item in values]
                if parsed != [probe.get("utc_day"), probe.get("local_day")]:
                    raise ValueError("Guest calendar receipt differs from raw date")
                guest_days.update(parsed)
            if tip_days[0] < day_floor or tip_days[0] not in guest_days:
                raise ValueError("LibreOffice tip day differs from guest UTC/local day")
        sandbox_ids.append(receipt["sandbox_id_sha256"])
    if len(set(sandbox_ids)) != len(ATTEMPTS):
        raise ValueError("Scoped positive, near-miss, and reset reused a guest")
    return sandbox_ids


def audit(*, candidate_root: Path, attempts_root: Path,
          original_root: Path, failed_root: Path,
          bridge_path: Path, runtime_freeze: Path,
          action_ratification: Path, new_lane_reservation: Path,
          public_calibration: Path, private_calibration_audit: Path,
          scoped_reference: Path, failed_private_stop: Path,
          failed_public_interruption: Path,
          private_map: Path, profile_private: Path,
          guest_public: Path, fair_public: Path) -> tuple[dict, dict]:
    _bridge, bridge_sha = validate_bridge(
        bridge_path=bridge_path,
        candidate_root=candidate_root,
        original_root=original_root, failed_root=failed_root,
        fresh_root=attempts_root,
        action_ratification=action_ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference,
        runtime_freeze=runtime_freeze,
        new_lane_reservation=new_lane_reservation,
        failed_private_stop=failed_private_stop,
        failed_public_interruption=failed_public_interruption,
        profile_private=profile_private,
        guest_public=guest_public, fair_public=fair_public)
    reference, reference_sha = validate_reference(scoped_reference)
    if intent_budget(attempts_root)["existing_intents"] != 300:
        raise ValueError("Fresh scoped 100x3 intent denominator incomplete")
    storage = _read_only_storage(attempts_root)
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    final = [row for row in json.loads(inventory_raw)["tasks"]
             if row["split"] == "final_candidate"]
    if len(final) != 100 or len({row["task_id"] for row in final}) != 100:
        raise ValueError("Fresh scoped final source denominator changed")
    salt = json.loads(private_map.read_bytes()).get("variant_salt")
    if type(salt) is not str or len(salt) < 32:
        raise ValueError("Independent saved-OOXML scorer salt missing")
    common = {
        "profile_sha": digest(profile_private.read_bytes()),
        "guest_sha": digest(guest_public.read_bytes()),
        "private_salt": salt,
        "ratification_sha": digest(action_ratification.read_bytes()),
        "reservation_sha": digest(new_lane_reservation.read_bytes()),
    }
    runtime_sha = digest(runtime_freeze.read_bytes())
    passed, invalid, sandbox_ids = [], [], set()
    for row in final:
        try:
            fair = _validate_trio(
                candidate_root, attempts_root, row, **common)
            ids = _profile_receipt(
                candidate_root=candidate_root,
                attempts_root=attempts_root,
                task_id=row["task_id"], workflow=row["workflow"],
                reference=reference, reference_sha=reference_sha,
                runtime_sha=runtime_sha, bridge_sha=bridge_sha)
            if any(item in sandbox_ids for item in ids):
                raise ValueError("Fresh scoped guests reused across task IDs")
            sandbox_ids.update(ids)
            passed.append(fair)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            invalid.append({"private_task_id": row["task_id"],
                            "reason_type": type(exc).__name__})
    if len(sandbox_ids) != 300 or invalid:
        raise ValueError("One or more fresh scoped task trios failed independent audit")
    old_ids = {json.loads(path.read_bytes())["sandbox_id_sha256"]
               for root in (original_root, failed_root)
               for path in root.glob("*/*/receipt.json")}
    if sandbox_ids & old_ids:
        raise ValueError("Fresh scoped guest reused a historical sandbox")
    private = {
        "schema": "cua-native-wdi-v066-scoped-final-control-audit-private-v1",
        "status": "100_provisional_scoped_gui_trios_not_official",
        "candidate_inventory_sha256": digest(inventory_raw),
        "bridge_sha256": bridge_sha,
        "runtime_freeze_sha256": runtime_sha,
        "reference_sha256": reference_sha,
        "independently_verified_trios": passed,
        "fresh_distinct_sandbox_count": len(sandbox_ids),
        "raw_evidence_storage": storage,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-scoped-final-control-audit-public-v1",
        "status": "provisional_controls_only_not_six_cell_admission",
        "candidate_final_count": 100,
        "independently_verified_gui_trios": len(passed),
        "fresh_distinct_sandbox_count": len(sandbox_ids),
        "raw_profile_and_frame_bytes_reopened": True,
        "saved_artifacts_independently_verified": True,
        "bridge_sha256": bridge_sha,
        "runtime_freeze_sha256": runtime_sha,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public
