"""Independent read-only audit of prospective v0.6.6 final Desktop controls.

This never produces a `cua-final-cell-v0.6` qualified manifest or model score.
Its private ledger checks saved OOXML and raw frame bytes per ID; its public
receipt contains only aggregate counts, hashes, and explicit global blockers.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from . import admit
from .calibrate_sweep import actor_script
from .official_saved_verifier import verify_official
from .v066_control_plan import compile_script
from .v066_final_freeze import digest, intent_budget, validate_lane
from .v066_storage_budget import audit as storage_audit


ATTEMPTS = ("positive", "near-miss", "cold-reset")


def _bound_file(root: Path, record: dict) -> bytes:
    relative = record.get("private_path")
    if type(relative) is not str:
        raise ValueError("Raw private GUI evidence path is missing")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Raw private GUI evidence escaped or disappeared")
    raw = path.read_bytes()
    if len(raw) != record.get("bytes") or digest(raw) != record.get("sha256"):
        raise ValueError("Raw private GUI evidence digest changed")
    return raw


def _validate_trio(candidate_root: Path, attempts_root: Path, row: dict,
                   *, profile_sha: str, guest_sha: str, private_salt: str,
                   ratification_sha: str, reservation_sha: str) -> dict:
    package_dir, baseline, oracle = admit._package(candidate_root, row)
    task_id = row["task_id"]
    records, receipt_hashes = {}, {}
    sandbox_ids = set()
    for attempt in ATTEMPTS:
        path = attempts_root / task_id / attempt
        intent_raw = (path / "intent.json").read_bytes()
        receipt_raw = (path / "receipt.json").read_bytes()
        intent, receipt = json.loads(intent_raw), json.loads(receipt_raw)
        expected_status = "cold_reset_observed" if attempt == "cold-reset" else "control_passed"
        if (intent.get("schema") != "cua-native-wdi-v066-final-control-intent-v1"
                or intent.get("task_id") != task_id
                or intent.get("attempt") != attempt
                or intent.get("package_sha256") != row["package_sha256"]
                or intent.get("ratification_sha256") != ratification_sha
                or intent.get("reservation_sha256") != reservation_sha
                or receipt.get("schema") != "cua-native-wdi-v066-gui-control-attempt-v1"
                or receipt.get("status") != expected_status
                or receipt.get("task_id") != task_id
                or receipt.get("attempt") != attempt
                or receipt.get("package_sha256") != row["package_sha256"]
                or receipt.get("input_sha256") != digest(baseline)
                or receipt.get("ratification_sha256") != ratification_sha
                or receipt.get("lane_reservation_sha256") != reservation_sha
                or receipt.get("task_profile_private_manifest_sha256") != profile_sha
                or receipt.get("guest_identity_public_sha256") != guest_sha
                or receipt.get("guest_content_attested") is not True
                or receipt.get("task_profile_attested") is not True
                or receipt.get("kill_returned") is not True
                or receipt.get("is_running_after_kill") is not False
                or receipt.get("official_hidden_final_model_attempts") != 0):
            raise ValueError("A prospective control lacks exact runtime/action/cleanup binding")
        sandbox_id = receipt.get("sandbox_id_sha256")
        if not sandbox_id or sandbox_id in sandbox_ids:
            raise ValueError("Fresh positive/near-miss/cold sandboxes were not distinct")
        sandbox_ids.add(sandbox_id)
        expected_script = actor_script(package_dir, oracle, attempt)
        expected_actions, _guards = compile_script(expected_script)
        if (receipt.get("evaluator_script_sha256") != digest(expected_script.encode())
                or receipt.get("expected_actor_action_count") != len(expected_actions)):
            raise ValueError("Evaluator GUI script was changed after freeze")
        steps = receipt.get("actor_steps", [])
        if len(steps) != len(expected_actions):
            raise ValueError("Prospective GUI did not apply every action")
        for index, (step, action) in enumerate(zip(steps, expected_actions)):
            expected_payload = json.dumps(action, separators=(",", ":"))
            if (step.get("step") != index or step.get("status") != "applied"
                    or step.get("action_type") != action["type"]
                    or step.get("dispatch_type") != action["type"]
                    or step.get("action_payload_sha256") != digest(expected_payload.encode())
                    or not step.get("frame_id_sha256")):
                raise ValueError("A current-frame GUI action is absent or changed")
            _bound_file(attempts_root, step["observation"])
            _bound_file(attempts_root, step["predispatch"])
        if attempt != "cold-reset":
            artifact = receipt.get("saved_artifact")
            saved = _bound_file(attempts_root, artifact)
            fair = verify_official(baseline, saved, oracle, private_salt=private_salt)
            expected_pass = attempt == "positive"
            if (saved == baseline or fair != receipt.get("fair_verifier")
                    or fair["passed"] is not expected_pass
                    or (not expected_pass and (not fair["errors"] or
                        any(not error.startswith("target_") for error in fair["errors"])))):
                raise ValueError("Independent saved-OOXML target/no-regression scorer disagrees")
        else:
            _bound_file(attempts_root, receipt["cold_observation"])
            if receipt.get("restored_state_sha256") != digest(baseline):
                raise ValueError("A fresh guest did not restore the original OOXML input")
        records[attempt] = receipt
        receipt_hashes[attempt] = digest(receipt_raw)
    return {"private_task_id": task_id,
            "package_sha256": row["package_sha256"],
            "receipt_sha256s": receipt_hashes,
            "sandbox_id_sha256s": sorted(sandbox_ids),
            "prospective_controls_passed": True}


def audit(*, candidate_root: Path, attempts_root: Path, private_map: Path,
          profile_private: Path, guest_public: Path, fair_public: Path,
          ratification: Path, reservation: Path) -> tuple[dict, dict]:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    if len(final) != 100:
        raise ValueError("The final 100-task denominator changed")
    budget = intent_budget(attempts_root)
    storage = storage_audit(attempts_root, verify_all_bytes=True)
    frozen = ratification.is_file() and reservation.is_file()
    if frozen:
        validate_lane(ratification=ratification, reservation=reservation,
                      candidate_root=candidate_root, guest_public=guest_public,
                      profile_private=profile_private, fair_public=fair_public)
    salt = json.loads(private_map.read_bytes()).get("variant_salt")
    if not isinstance(salt, str) or len(salt) < 32:
        raise ValueError("Evaluator-private semantic salt missing")
    admitted, missing, invalid = [], [], []
    for row in final:
        directory = attempts_root / row["task_id"]
        if not directory.exists() or any(not (directory / name / "receipt.json").is_file()
                                         for name in ATTEMPTS):
            missing.append(row["task_id"])
            continue
        if not frozen:
            invalid.append({"private_task_id": row["task_id"],
                            "reason": "six_cell_profile_or_separate_lane_not_ratified"})
            continue
        try:
            admitted.append(_validate_trio(
                candidate_root, attempts_root, row,
                profile_sha=digest(profile_private.read_bytes()),
                guest_sha=digest(guest_public.read_bytes()),
                private_salt=salt,
                ratification_sha=digest(ratification.read_bytes()),
                reservation_sha=digest(reservation.read_bytes())))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            invalid.append({"private_task_id": row["task_id"],
                            "reason": type(exc).__name__})
    private = {
        "schema": "cua-native-wdi-v066-final-control-audit-private-v1",
        "candidate_inventory_sha256": digest(inventory_raw),
        "common_profile_and_lane_ratified": frozen,
        "prospective_passed_trios": admitted,
        "missing_private_task_ids": missing,
        "invalid_private_task_rows": invalid,
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-final-control-audit-public-v1",
        "checked_date": "2026-09-27",
        "candidate_inventory_sha256": digest(inventory_raw),
        "candidate_final_count": 100,
        "prospective_gui_trios_independently_accepted": len(admitted),
        "missing_gui_trios": len(missing),
        "invalid_gui_trios": len(invalid),
        "common_profile_and_lane_ratified": frozen,
        "full_six_cell_pre_campaign_freeze_completed": False,
        "separate_final_control_intent_budget": budget,
        "private_raw_frame_storage_budget": storage,
        "status": "blocked_before_full_study_final_cell_manifest",
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
        "actual_provider_billed_usd": None,
    }
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("candidate-root", "attempts-root", "private-map",
                  "profile-private", "guest-public", "fair-public",
                  "ratification", "reservation", "private-out", "public-out"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Refusing to overwrite v0.6.6 final-control audit evidence")
    private, public = audit(
        candidate_root=args.candidate_root, attempts_root=args.attempts_root,
        private_map=args.private_map, profile_private=args.profile_private,
        guest_public=args.guest_public, fair_public=args.fair_public,
        ratification=args.ratification, reservation=args.reservation)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
    args.private_out.chmod(0o600)
    public["private_detailed_audit_sha256"] = digest(args.private_out.read_bytes())
    args.public_out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: public[key] for key in (
        "candidate_final_count", "prospective_gui_trios_independently_accepted",
        "missing_gui_trios", "invalid_gui_trios",
        "official_full_study_admitted_final_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
