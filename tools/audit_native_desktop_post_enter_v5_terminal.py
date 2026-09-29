"""Read-only audit of the first main-checkout public-TRAIN settle calibration.

This terminal receipt explains a stopped attempt; it never qualifies a final
task or reuses the consumed E2B intent. Run with the source commit pinned by
the public freeze and an E2B credential for the active-zero observation.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import stat

from native_desktop_factory.post_enter_train_probe_v1 import SAMPLE_DELAYS_MS
from native_desktop_factory.qwen_v064_adapter import application_frame_digest
from native_desktop_factory.reconcile_interrupted_sweep import active_hashes
from native_desktop_factory.v066_post_enter_train_calibration_v1 import (
    PERMIT_SCHEMA, validate_source,
)
from native_desktop_factory.v066_storage_budget import audit as storage_audit


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def private(path: Path, *, directory: bool = False) -> bytes:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "private_terminal_evidence_missing_or_unsafe")
    return b"" if directory else path.read_bytes()


def saved_ref(root: Path, ref: dict) -> bytes:
    require(type(ref) is dict and
            set(ref) == {"bytes", "private_path", "sha256"} and
            type(ref["private_path"]) is str,
            "terminal_frame_reference_invalid")
    target = (root / ref["private_path"]).resolve()
    require(target.is_relative_to(root.resolve()) and
            target != root.resolve(), "terminal_frame_path_escape")
    raw = private(target)
    require(len(raw) == ref["bytes"] and digest(raw) == ref["sha256"],
            "terminal_frame_bytes_changed")
    return raw


def audit(freeze_path: Path, permit_path: Path) -> dict:
    value = validate_source(freeze_path)
    # The pre-run permit's budget snapshot is intentionally historical. The
    # live ledger has a new guest after execution, so checked_permit() is a
    # dispatch gate and cannot be reused as a post-run forensic assertion.
    permit = json.loads(private(permit_path))
    review_path = Path(permit.get("review_path", ""))
    require(review_path.is_absolute(), "terminal_review_path_not_absolute")
    review_raw = private(review_path)
    review = json.loads(review_raw)
    require(
        permit.get("schema") == PERMIT_SCHEMA and
        permit.get("status") == "reviewed_exact_three_train_guests" and
        permit.get("freeze_sha256") == digest(private(freeze_path)) and
        permit.get("source_sha256s") == value["source_sha256s"] and
        permit.get("output_root") == value["output_root"] and
        permit.get("guest_count") == 3 and
        permit.get("review_sha256") == digest(review_raw) and
        permit.get("dispatch_authorized") is True and
        permit.get("same_intent_replay_authorized") is False and
        permit.get("official_final_admissions") == 0 and
        review.get("schema") ==
            "cua-native-wdi-v066-post-enter-train-review-private-v1" and
        review.get("status") ==
            "accepted_exact_three_train_guests_without_provider_create" and
        review.get("freeze_sha256") == permit["freeze_sha256"] and
        review.get("source_sha256s") == value["source_sha256s"] and
        review.get("output_root") == value["output_root"] and
        review.get("guest_count") == 3 and
        review.get("provider_active_at_review") == 0 and
        review.get("storage_ready_at_review") is True and
        review.get("budget_before_three_guests") ==
            permit.get("budget_before_three_guests") and
        review.get("budget_before_three_guests", {}).get("within_cap") is True and
        review.get("same_intent_replay_authorized") is False and
        review.get("official_final_admissions") == 0,
        "terminal_pre_run_review_or_permit_changed")
    root = Path(value["output_root"])
    private(root, directory=True)
    run_path = root.parent / (root.name + ".calibration-run.private.json")
    run_raw = private(run_path)
    run = json.loads(run_raw)
    child_raw = private(root / "run-receipt.json")
    child = json.loads(child_raw)
    calc_raw = private(root / "calc/receipt.json")
    calc = json.loads(calc_raw)
    require(
        run.get("schema") ==
            "cua-native-wdi-v066-post-enter-train-calibration-run-private-v1" and
        run.get("status") == "stopped_for_reconciliation" and
        run.get("error_type") == "ValueError" and
        run.get("freeze_sha256") == digest(private(freeze_path)) and
        run.get("permit_sha256") == digest(private(permit_path)) and
        run.get("output_root") == str(root) and
        run.get("guest_count_planned") == 3 and
        run.get("official_final_admissions") == 0 and
        child.get("schema") == "cua-native-wdi-v066-calc-writer-train-demo-run-v1" and
        child.get("status") == "stopped_for_reconciliation" and
        child.get("automatic_retry_authorized") is False and
        child.get("official_final_admissions") == 0 and
        child.get("reservation_sha256") ==
            value["reservation_sha256"] and
        len(child.get("attempts", [])) == 1 and
        child["attempts"][0].get("kind") == "calc" and
        child["attempts"][0].get("status") ==
            "train_gui_positive_failed" and
        child["attempts"][0].get("cleanup_verified") is True and
        child["attempts"][0].get("receipt_sha256") == digest(calc_raw) and
        calc.get("kind") == "calc" and
        calc.get("status") == "train_gui_positive_failed" and
        calc.get("error_type") == "ValueError" and
        calc.get("error_message_private") ==
            "Post-Enter modal/window/time boundary changed" and
        calc.get("actor_gui_actions") == 5 and
        calc.get("kill_returned") is True and
        calc.get("is_running_after_kill") is False and
        calc.get("task_profile_scoped_attested") is True and
        calc.get("guest_content_attested") is True and
        not (root / "writer").exists() and
        not (root / "cold-reset").exists() and
        not (root / "calc/saved.xlsx").exists(),
        "terminal_train_scope_or_cleanup_changed")
    ledger = storage_audit(root, verify_all_bytes=True)
    require(ledger["unresolved_write_count"] == 0 and
            ledger["retained_file_count"] > 0,
            "terminal_private_frame_ledger_unresolved")
    sample_path = root / "calc/post-enter-samples.ndjson"
    lines = private(sample_path).splitlines()
    require(len(lines) == len(SAMPLE_DELAYS_MS),
            "terminal_first_enter_sample_count_changed")
    rows = [json.loads(raw) for raw in lines]
    starts = set()
    application = []
    elapsed_ms = []
    captures_ms = []
    for expected, row in enumerate(rows):
        raw = saved_ref(root, row["frame"])
        before = row.get("monotonic_before_ns")
        after = row.get("monotonic_after_ns")
        elapsed = row.get("elapsed_since_enter_ns")
        require(
            row.get("schema") ==
                "cua-native-wdi-v066-post-enter-train-sample-v1" and
            row.get("enter_ordinal") == 0 and
            row.get("sample") == expected and
            row.get("requested_delay_ms_before_sample") ==
                SAMPLE_DELAYS_MS[expected] and
            type(before) is type(after) is type(elapsed) is int and
            before <= after and elapsed >= after - before and
            row.get("full_frame_sha256") == digest(raw) and
            row.get("application_frame_sha256") ==
                application_frame_digest(raw) and
            row.get("document_window_stable") is True and
            row.get("window_id_before_sha256") ==
                row.get("window_id_after_sha256") and
            row.get("window_title_before_sha256") ==
                row.get("window_title_after_sha256"),
            "terminal_raw_frame_or_window_changed")
        starts.add(after - elapsed)
        application.append(row["application_frame_sha256"])
        elapsed_ms.append(round(elapsed / 1_000_000, 3))
        captures_ms.append(round((after - before) / 1_000_000, 3))
        if expected:
            require(before >= rows[expected - 1]["monotonic_after_ns"],
                    "terminal_frame_order_changed")
    require(len(starts) == 1 and application[0] != application[1] and
            len(set(application[1:])) == 1 and
            elapsed_ms[-1] > 10_000 and elapsed_ms[-1] < 30_000,
            "terminal_time_cap_diagnosis_not_reproduced")
    active, count = active_hashes()
    require(not active and count == 0,
            "terminal_provider_guest_still_active")
    return {
        "schema": "envloop-native-wdi-v066-post-enter-v5-terminal-audit-v1",
        "status": "train_only_first_enter_wall_cap_exceeded_after_stable_frames",
        "source_freeze_sha256": digest(private(freeze_path)),
        "permit_sha256": digest(private(permit_path)),
        "private_run_receipt_sha256": digest(run_raw),
        "private_child_receipt_sha256": digest(child_raw),
        "private_calc_receipt_sha256": digest(calc_raw),
        "private_sample_ledger_sha256": digest(private(sample_path)),
        "first_enter_raw_frames": len(rows),
        "application_transitions": 1,
        "all_sample_window_ids_and_titles_stable": True,
        "last_sample_elapsed_ms": elapsed_ms[-1],
        "sample_capture_ms_min": min(captures_ms),
        "sample_capture_ms_max": max(captures_ms),
        "frozen_wall_cap_ms": 10_000,
        "retained_raw_files_verified": ledger["retained_file_count"],
        "unresolved_raw_writes": ledger["unresolved_write_count"],
        "calc_gui_actions_before_stop": calc["actor_gui_actions"],
        "calc_saved_positive_verified": False,
        "writer_guest_created": False,
        "cold_reset_guest_created": False,
        "calc_cleanup_verified": True,
        "provider_active_after_stop": count,
        "model_calls": 0,
        "official_final_admissions": 0,
        "same_intent_replay_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--permit", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.freeze, args.permit)
    if args.public_out.exists() or args.public_out.is_symlink():
        raise ValueError("Refusing to overwrite terminal public receipt")
    args.public_out.write_text(json.dumps(result, sort_keys=True,
                                          indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "private_run_receipt_sha256":
                          result["private_run_receipt_sha256"],
                      "official_final_admissions": 0}))


if __name__ == "__main__":
    main()
