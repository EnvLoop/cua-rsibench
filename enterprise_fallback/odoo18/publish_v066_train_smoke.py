"""Reduce private Odoo v0.6.6 train smoke attempts to an English public receipt.

The publisher never copies task IDs, screenshots, credentials, model prompts,
gold values, or private paths into its output. It fails closed if the successful
attempt, any frame, source binding, or exact restore claim cannot be checked.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import stat


SCHEMA = "envloop-odoo-v066-native-train-gui-smoke-v1"
PUBLIC_SCHEMA = "envloop-odoo-v066-native-train-public-v1"
SOURCES = {
    "smoke": "enterprise_fallback/odoo18/smoke_v066_train.py",
    "odoo_v066_adapter": "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "odoo_native_adapter": "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "full_validator_v066": "src/cursibench/scale_action_contract_v066.py",
    "minimal_output_v066": "src/cursibench/scale_action_output_v066.py",
    "base_contract": "src/cursibench/scale_action_contract.py",
    "pinned_compose": "enterprise_fallback/odoo18/compose.yaml",
    "independent_verifier": "enterprise_fallback/odoo18/verify.py",
    "checkpoint_restore": "enterprise_fallback/odoo18/reset.py",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _private_file(path: Path) -> bytes:
    if (not path.is_file() or path.is_symlink() or
            stat.S_IMODE(path.stat().st_mode) & 0o077):
        raise ValueError("Missing or nonprivate train smoke evidence")
    return path.read_bytes()


def aggregate(attempt_dirs: list[Path], source_root: Path) -> dict:
    if not attempt_dirs or len(set(attempt_dirs)) != len(attempt_dirs):
        raise ValueError("Expected distinct ordered train smoke attempts")
    rows = []
    receipt_hashes = []
    for directory in attempt_dirs:
        raw = _private_file(directory / "receipt.json")
        row = json.loads(raw)
        if (row.get("schema") != SCHEMA or row.get("partition") != "train_only"
                or row.get("model_calls") != 0 or row.get("provider_calls") != 0
                or row.get("official_final_tasks_observed") != 0
                or row.get("action_profile") != "scale-action-profile-v0.6.6"
                or row.get("minimal_output_version") != "scale-action-output-v0.6.6"
                or row.get("pre_full_reset_exact") is not True
                or row.get("post_full_reset_exact") is not True
                or row.get("worker_services_restored_to_initial_state") is not True
                or len(row.get("actions", [])) > row.get("max_actions", 0)
                or row.get("wall_seconds", 0) > 420):
            raise ValueError("A training attempt fails the private restore or scope gate")
        for index, observed in enumerate(row.get("observations", [])):
            frame = _private_file(directory / f"frame-{index:02d}.png")
            if digest(frame) != observed["frame_sha256"]:
                raise ValueError("Raw observed frame changed")
        observed_frames = {(obs["step"], obs["frame_sha256"],
                            obs["frame_id_sha256"])
                           for obs in row["observations"]}
        if any(action["pre_dispatch_frame_sha256"] != action[
                "public_contract_receipt"]["screenshot"]["sha256"] or
               action["public_contract_receipt"]["action_profile"]
               != "scale-action-profile-v0.6.6" or
               action["public_contract_receipt"]["action_type"] != action["type"] or
               (action["step"], action["pre_dispatch_frame_sha256"],
                action["public_contract_receipt"]["frame_id_sha256"])
               not in observed_frames
               for action in row["actions"]):
            raise ValueError("Action/frame public receipt mismatch")
        rows.append(row)
        receipt_hashes.append(digest(raw))
    if any(row["status"] == "passed" for row in rows[:-1]):
        raise ValueError("Only the final ordered development attempt may pass")
    passed = rows[-1]
    if (passed["status"] != "passed" or passed["failure_class"] is not None
            or passed.get("independent_baseline_unsolved") is not True
            or passed.get("gui_price_persisted_after_reload") is not True
            or passed.get("independent_positive_reward_one") is not True
            or passed.get("independent_checks_passed") is not True
            or passed.get("independent_difference_codes") != []
            or len(passed["actions"]) != 8
            or [a["type"] for a in passed["actions"]].count("double_click") != 1
            or not any(a["type"] == "type" and a["target_kind"] is None
                       for a in passed["actions"])):
        raise ValueError("Final current-frame GUI positive was not independently verified")
    for name, relative in SOURCES.items():
        if passed["source_sha256"].get(name) != digest(
                (source_root / relative).read_bytes()):
            raise ValueError("Successful smoke source binding changed")
    failures = Counter(row["failure_class"] for row in rows[:-1])
    if None in failures:
        raise ValueError("Earlier development failure lacks classification")
    return {
        "schema": PUBLIC_SCHEMA,
        "checked_date": "2026-09-28",
        "scope": "One original Odoo Community 18 train-only trusted-action GUI control; no provider or model call, no hidden-final observation or official result.",
        "action_profile": passed["action_profile"],
        "minimal_output_version": passed["minimal_output_version"],
        "private_receipt_sha256_by_development_attempt": receipt_hashes,
        "development_attempts": len(rows),
        "development_attempt_status_counts": dict(sorted(Counter(
            row["status"] for row in rows).items())),
        "development_failure_class_counts": dict(sorted(failures.items())),
        "attempts_are_iterative_debugging_not_repeated_identical_trials": True,
        "all_attempts_exact_pre_post_database_filestore_restore": True,
        "all_attempts_restored_worker_service_state": True,
        "successful_attempt_observed_frames": len(passed["observations"]),
        "successful_attempt_validated_gui_actions": len(passed["actions"]),
        "successful_attempt_action_types": [a["type"] for a in passed["actions"]],
        "successful_attempt_target_kinds": [a["target_kind"] for a in passed["actions"]],
        "successful_attempt_frame_rejections": len(passed.get("rejected_actions", [])),
        "successful_attempt_gui_edit_persisted_after_reload": True,
        "successful_attempt_independent_business_and_source_reward": 1.0,
        "successful_attempt_independent_no_regression_checks_passed": True,
        "source_binding_sha256": {name: passed["source_sha256"][name]
                                  for name in sorted(SOURCES)},
        "model_calls": 0,
        "provider_calls": 0,
        "official_final_tasks_observed": 0,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", action="append", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite a public Odoo smoke receipt")
    report = aggregate(args.attempt_dir, args.source_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in (
        "development_attempts", "successful_attempt_validated_gui_actions",
        "successful_attempt_independent_business_and_source_reward",
        "all_attempts_exact_pre_post_database_filestore_restore",
        "official_final_tasks_admitted")}, sort_keys=True))


if __name__ == "__main__":
    main()
