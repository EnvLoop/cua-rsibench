"""Audit and publish aggregate-only evidence for five public-train GUI smokes."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from .budget_ledger import audit as budget_audit
from .v066_train_primitive_smoke import _train_package
from .verify import verify


def digest(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def audit(work_root: Path) -> dict:
    package, oracle, baseline, _instruction, _filename = _train_package()
    paths = [work_root / "gui-diagnostics" /
             f"v066-train-primitive-smoke-{i:03d}" for i in (1, 2, 3, 4, 5)]
    records = []
    for index, path in enumerate(paths, 1):
        raw = (path / "receipt.json").read_bytes()
        row = json.loads(raw)
        if (row.get("schema") != "cua-native-wdi-gui-development-attempt-v1"
                or row.get("purpose") != "v066_public_train_primitive_smoke_no_model"
                or row.get("split") != "train"
                or row.get("task_id") != package["task_id"]
                or row.get("input_sha256") != digest(baseline)
                or row.get("official_final_model_attempts") != 0
                or row.get("official_final_admissions") != 0
                or row.get("guest_content_attested") is not True
                or row.get("is_running_after_kill") is not False
                or row.get("kill_returned") is not True
                or row.get("provider_billed_usd") is not None):
            raise ValueError("A train-only E2B receipt changed or lacks cleanup")
        for step in row["steps"]:
            if (step.get("status") != "applied"
                    or step.get("dispatch_type") != step.get("action_type")
                    or not step.get("observation_frame_id_sha256")
                    or not step.get("predispatch_screenshot_sha256")):
                raise ValueError("Current-frame GUI action proof incomplete")
            if not any(digest(frame.read_bytes()) == step["observation_screenshot_sha256"]
                       for frame in path.glob(f"frame-{step['step']:02d}*.png")):
                raise ValueError("The private screenshot for an actor step changed")
            if index in (4, 5):
                predispatch = path / step["predispatch_screenshot_file"]
                if digest(predispatch.read_bytes()) != step["predispatch_screenshot_sha256"]:
                    raise ValueError("A retained private predispatch frame changed")
        expected_failures = {1: ("PhysicalFrameDrift", 1),
                             4: ("PhysicalFrameDrift", 13),
                             5: ("ReadError", 3)}
        if index in expected_failures:
            error, applied = expected_failures[index]
            if (row["status"] != "train_primitive_smoke_failed"
                    or row.get("error_type") != error
                    or len(row["steps"]) != applied):
                raise ValueError("A preserved physical/provider failure changed")
        elif index in (2, 3):
            saved = (path / "saved.pptx").read_bytes()
            result = verify(baseline, saved, oracle)
            if (row["status"] != "train_primitive_smoke_passed"
                    or result.get("passed") is not True
                    or result != row.get("train_saved_artifact_verifier")
                    or digest(saved) != row.get("saved_sha256")):
                raise ValueError("Saved positive training artifact did not independently reverify")
        records.append((raw, row))
    successful = records[2][1]
    actual_action_hashes = {step["action_payload_sha256"] for step in successful["steps"]}
    expected_chord_hashes = {digest(json.dumps({"type": "key", "key": chord},
                                              separators=(",", ":"))) for chord in
                             ("Control+F", "Control+H", "Control+End", "Shift+End")}
    if len(successful["steps"]) != 16 or not expected_chord_hashes <= actual_action_hashes:
        raise ValueError("The positive v0.6.6 smoke did not apply all four new chords")
    if len({row["sandbox_id_sha256"] for _, row in records}) != 5:
        raise ValueError("A train-only Desktop sandbox was reused")
    budget = budget_audit(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=600,
                          max_lane_reserved_usd=Decimal("40"))
    if (not budget["within_cap"] or budget["past_conservative_reserved_usd"] !=
            "39.99444444444444444444444444"):
        raise ValueError("Conservative E2B lane reservation no longer matches the five smokes")
    return {
        "schema": "cua-native-wdi-v066-train-primitive-live-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Five evaluator-scripted E2B smokes on one public Impress train fixture; no Tinker/model or hidden final task.",
        "attempt_count": len(records),
        "distinct_sandbox_count": len({row["sandbox_id_sha256"] for _, row in records}),
        "status_counts": dict(sorted(Counter(row["status"] for _, row in records).items())),
        "failure_error_type_counts": dict(sorted(Counter(
            row.get("error_type") for _, row in records if row.get("error_type")).items())),
        "guest_content_attested_count": sum(row["guest_content_attested"] for _, row in records),
        "terminated_sandbox_count": sum(row["is_running_after_kill"] is False for _, row in records),
        "applied_gui_actions_total": sum(len(row["steps"]) for _, row in records),
        "successful_chord_smoke_attempt_index": 3,
        "successful_chord_smoke_applied_gui_actions": len(successful["steps"]),
        "successful_chord_smoke_current_frame_predispatch_checks": len(successful["steps"]),
        "successful_chord_smoke_new_explicit_key_chords_applied": 4,
        "successful_chord_smoke_native_double_click_applied": sum(
            step["action_type"] == "double_click" for step in successful["steps"]),
        "successful_chord_smoke_focused_insert_applied": sum(
            step["action_type"] == "type" for step in successful["steps"]),
        "successful_chord_smoke_raw_predispatch_frames_retained": False,
        "raw_predispatch_frames_retained_on_later_failed_attempts": sum(
            len(row["steps"]) for _, row in records[3:]),
        "saved_train_positive_artifacts_reverified": 2,
        "v066_full_action_validator_sha256": successful["v066_full_action_validator_sha256"],
        "v066_model_output_adapter_sha256": successful["v066_model_output_adapter_sha256"],
        "v066_native_adapter_sha256": successful["v066_native_adapter_sha256"],
        "successful_train_runner_sha256": successful["runner_sha256"],
        "private_receipt_sha256s": [digest(raw) for raw, _ in records],
        "conservative_full_lease_reserve_added_usd": "0.8333333333333333333333333333",
        "native_development_lane_reserved_usd_after": budget["past_conservative_reserved_usd"],
        "native_development_lane_cap_usd": budget["lane_usd_cap"],
        "actual_provider_billed_usd": None,
        "complete_train_positive_with_raw_predispatch_frames": 0,
        "v066_live_final_gui_trios": 0,
        "official_full_study_desktop_admissions": 0,
        "official_hidden_final_model_attempts": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite a public smoke aggregate")
    result = audit(args.work_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "attempt_count", "successful_chord_smoke_applied_gui_actions",
        "saved_train_positive_artifacts_reverified",
        "official_full_study_desktop_admissions")}, sort_keys=True))


if __name__ == "__main__":
    main()
