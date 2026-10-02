"""Read-only forensic receipt for the first stopped Desktop v4e batch.

This audit never creates a sandbox or replays an intent. Its public output
contains aggregate counts and hashes, not evaluator-private task identities.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path

from PIL import Image, ImageChops

from native_desktop_factory.reconcile_interrupted_sweep import active_hashes


FREEZE_SHA256 = "a092226191ca5afc418d3c3075395e2b79c1f01131edb012120f6b7dbc80ec34"
PUBLIC_FREEZE_SHA256 = "f25c0c631b42483608b95b3e68b605ee89ec06c3a8fc8c73701f5836308c17b5"
PERMIT_SHA256 = "470dbd8354463a5c74e5e33e12b187c649248247b5f683c1252f59804aa734bd"


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def private(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private Desktop evidence absent or unsafe")
    return path.read_bytes()


def checked(value: bool, label: str) -> None:
    if not value:
        raise ValueError(label)


def application_image(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as opened:
        checked(opened.size == (1280, 800), "Unexpected Desktop frame size")
        return opened.convert("RGB").crop((0, 27, 1280, 780))


def inspect(freeze_path: Path) -> dict:
    freeze_raw = private(freeze_path)
    checked(digest(freeze_raw) == FREEZE_SHA256, "Main v5 freeze changed")
    freeze = json.loads(freeze_raw)
    public_path = Path(freeze["public_path"])
    public_raw = public_path.read_bytes()
    public = json.loads(public_raw)
    checked(digest(public_raw) == PUBLIC_FREEZE_SHA256 and
            public.get("private_freeze_sha256") == FREEZE_SHA256 and
            public.get("dispatch_authorized") is False and
            freeze.get("dispatch_authorized") is False and
            freeze.get("same_intent_replay_authorized") is False,
            "Main v5 public/source boundary changed")
    repo = public_path.parents[2]
    checked(len(freeze["source_sha256s"]) == 6 and all(
        digest((repo / name).read_bytes()) == expected
        for name, expected in freeze["source_sha256s"].items()),
        "Main v5 frozen evaluator source changed")
    old_raw = private(Path(freeze["v4d_freeze_path"]))
    checked(digest(old_raw) == freeze["v4d_freeze_sha256"],
            "Retained v4d private freeze changed")
    old = json.loads(old_raw)
    v4c = json.loads(private(Path(old["v4c_freeze_path"])))
    v3 = json.loads(private(Path(v4c["v3_freeze_path"])))
    v2 = json.loads(private(Path(v3["base_freeze_path"])))
    inventory_raw = Path(v2["paths"]["candidate_root"],
                         "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    rows = sorted(
        (row for row in inventory["tasks"] if row["split"] == "final_candidate"),
        key=lambda row: (row["source_groups"], row["workflow"]),
    )
    roster = [row["task_id"] for row in rows]
    checked(len(rows) == 100 and len(set(roster)) == 100 and
            digest(inventory_raw) == freeze["candidate_inventory_sha256"] and
            digest((json.dumps(roster, separators=(",", ":")) + "\n").encode()) ==
            freeze["sorted_final_roster_sha256"],
            "Frozen sorted candidate inventory changed")
    root = Path(freeze["new_attempts_root"])
    run_dir = root.parent / "v066-v4e-root-owned-runs" / "batch-0001"
    checked(root.is_dir() and not root.is_symlink() and
            run_dir.is_dir() and not run_dir.is_symlink() and
            {p.name for p in root.iterdir()} ==
                {roster[12], "storage-ledger.sqlite3"} and
            {p.name for p in (root / roster[12]).iterdir()} == {"positive"},
            "First fifth-root task is not the exact isolated partial")
    attempt = root / roster[12] / "positive"
    checked(not (root / roster[11]).exists() and
            not (attempt.parent / "near-miss").exists() and
            not (attempt.parent / "cold-reset").exists(),
            "Stopped Desktop task was replayed or cloned")
    journal_raw = private(run_dir / "run-receipt.json")
    journal = json.loads(journal_raw)
    permit_path = Path(journal["permit_path"])
    permit_raw = private(permit_path)
    permit = json.loads(permit_raw)
    review_raw = private(Path(permit["independent_review_path"]))
    review = json.loads(review_raw)
    selected_sha = digest((json.dumps([roster[12]], separators=(",", ":")) + "\n").encode())
    checked(digest(permit_raw) == PERMIT_SHA256 and
            journal.get("status") == "stopped_for_reconciliation" and
            journal.get("schema") == "cua-native-wdi-v066-v4e-bounded-run-private-v1" and
            journal.get("selected_private_task_ids") == [roster[12]] and
            journal.get("permit_sha256") == PERMIT_SHA256 and
            journal.get("official_final_admissions") == 0 and
            journal.get("official_final_model_attempts") == 0 and
            len(journal.get("task_outcomes", [])) == 1 and
            permit.get("selected_private_task_ids_sha256") == selected_sha and
            permit.get("mode") == "untouched" and
            permit.get("batch_number") == 1 and
            permit.get("maximum_new_ids") == 1 and
            permit.get("freeze_sha256") == FREEZE_SHA256 and
            permit.get("independent_review_sha256") == digest(review_raw) and
            review.get("selected_private_task_ids_sha256") == selected_sha and
            review.get("provider_active_at_review") == 0,
            "First root-owned batch or exact reviewed permit changed")
    outcome = journal["task_outcomes"][0]
    checked(outcome.get("private_task_id") == roster[12] and
            outcome.get("status") == "stopped_after_invalid_or_uncertain_attempt" and
            len(outcome.get("attempts", [])) == 1,
            "Stopped task outcome changed")
    result = outcome["attempts"][0]
    raw = {name: private(attempt / name) for name in (
        "budget.json", "intent.json", "child-started.json", "child-output.json",
        "child.stdout", "child.stderr", "receipt.json", "probe-step-12-00.json",
    )}
    budget, intent, started, child_output, receipt, probe = (
        json.loads(raw[name]) for name in (
            "budget.json", "intent.json", "child-started.json",
            "child-output.json", "receipt.json", "probe-step-12-00.json",
        )
    )
    checked(budget.get("five_root_budget", {}).get("historical_four_root_intents") == 56 and
            budget["five_root_budget"].get("combined_full_lease_intents") == 57 and
            budget.get("provider_active_before_intent") == 0 and
            budget.get("storage_dispatch_ready") is True and
            intent.get("task_id") == roster[12] and
            intent.get("attempt") == "positive" and
            intent.get("package_sha256") == rows[12]["package_sha256"] and
            intent.get("precreate_budget_sha256") == digest(raw["budget.json"]) and
            intent.get("same_intent_replay_authorized") is False and
            intent.get("v4e_permit_sha256") == PERMIT_SHA256 and
            started.get("status") == "consumed_before_original_evaluator" and
            started.get("intent_sha256") == digest(raw["intent.json"]) and
            started.get("freeze_sha256") == FREEZE_SHA256 and
            started.get("permit_sha256") == PERMIT_SHA256,
            "Paid intent or one-shot child marker changed")
    checked(child_output.get("schema") ==
                "cua-native-wdi-v066-v4d-private-child-output-v1" and
            child_output.get("status") ==
                "terminal_output_fsynced_before_classification" and
            child_output.get("exit_code") == 2 and
            child_output.get("timed_out") is False and
            child_output.get("spawn_error_type") is None and
            child_output.get("stdout_sha256") == digest(raw["child.stdout"]) and
            child_output.get("stderr_sha256") == digest(raw["child.stderr"]) and
            receipt.get("status") == "control_failed_or_infrastructure_invalid" and
            receipt.get("stage") == "current_frame_gui" and
            receipt.get("error_type") == "MaterialFrameDrift" and
            receipt.get("contract_error_code") == "stale_frame" and
            receipt.get("guest_content_attested") is True and
            receipt.get("task_profile_attested") is True and
            receipt.get("kill_returned") is True and
            receipt.get("is_running_after_kill") is False and
            receipt.get("sandbox_id_sha256") and
            receipt.get("expected_actor_action_count") == 25 and
            len(receipt.get("actor_steps", [])) == 12 and
            all(row.get("step") == index and row.get("status") == "applied"
                for index, row in enumerate(receipt["actor_steps"])) and
            "saved_artifact" not in receipt and "fair_verifier" not in receipt and
            result.get("attempt") == "positive" and
            result.get("status") == receipt["status"] and
            result.get("exit_code") == 2 and
            result.get("cleanup_verified") is True and
            result.get("child_process_exited") is True and
            result.get("receipt_sha256") == digest(raw["receipt.json"]) and
            result.get("child_output_sha256") == digest(raw["child-output.json"]),
            "Durable child, stopped GUI stage, or cleanup evidence changed")
    frame_raw = private(attempt / "frame-12-0.png")
    sample_raw = private(attempt / "probe-step-12-00-00.png")
    first, second = application_image(frame_raw), application_image(sample_raw)
    difference = ImageChops.difference(first, second)
    bounds = difference.getbbox()
    checked(probe.get("schema") ==
                "cua-native-wdi-v066-internal-caret-probe-private-v4" and
            probe.get("status") == "rejected_material_or_third_state" and
            probe.get("step") == 12 and
            probe.get("observed_sha256") == digest(frame_raw) and
            probe.get("sample_frames", [{}])[0].get("sha256") == digest(sample_raw) and
            len(probe.get("sample_frames", [])) == 1 and
            probe.get("sample_application_sha256s") == [digest(second.tobytes())] and
            bounds is not None and bounds[2] - bounds[0] > 1,
            "Raw frame/probe no longer support material-drift classification")
    active, active_count = active_hashes()
    checked(not active and active_count == 0, "Provider cleanup is not active-zero")
    return {
        "schema": "cua-native-wdi-v066-first-v4e-terminal-public-v1",
        "status": "one_partial_evaluator_task_quarantined",
        "source_freeze_public_sha256": PUBLIC_FREEZE_SHA256,
        "source_freeze_private_sha256": FREEZE_SHA256,
        "reviewed_one_batch_permit_sha256": PERMIT_SHA256,
        "root_owned_batch_receipt_sha256": digest(journal_raw),
        "one_shot_child_marker_sha256": digest(raw["child-started.json"]),
        "durable_child_output_sha256": digest(raw["child-output.json"]),
        "private_attempt_receipt_sha256": digest(raw["receipt.json"]),
        "private_probe_manifest_sha256": digest(raw["probe-step-12-00.json"]),
        "retained_historical_complete_trios": 8,
        "retained_historical_partial_logical_ids": 4,
        "new_positive_intents": 1,
        "new_near_negative_intents": 0,
        "new_cold_reset_intents": 0,
        "five_root_full_lease_intents_charged": 57,
        "new_task_provisional_complete": False,
        "positive_control_stage": "current_frame_gui",
        "positive_control_error_type": "MaterialFrameDrift",
        "positive_control_contract_error_code": "stale_frame",
        "actor_actions_applied_before_stop": 12,
        "expected_actor_actions": 25,
        "saved_artifact_scored": False,
        "raw_application_frame_changed": True,
        "raw_frame_difference_wider_than_single_caret_column": True,
        "child_exit_code": 2,
        "child_timed_out": False,
        "sandbox_created_and_attested": True,
        "sandbox_kill_returned": True,
        "sandbox_is_running_after_kill": False,
        "provider_active_sandboxes_at_audit": 0,
        "same_intent_replay_authorized": False,
        "current_v4e_continuation_authorized": False,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
        "actual_provider_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    value = inspect(args.freeze)
    output = args.public_out
    if output.exists() or output.is_symlink():
        raise ValueError("Exclusive public output path required")
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": value["status"],
                      "public_receipt_sha256": digest(raw),
                      "official_final_admissions": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
