"""Independent readback and exact review for the public-train calibration.

The review path may issue one private three-guest permit but never creates a
sandbox. The saved-state audit reopens raw train frames, positive OOXML files,
profile evidence, cold reset bytes, cleanup, and source-bound lease intents.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path

from . import v066_scoped_calc_writer_train_demo as demo
from . import v066_scoped_calc_writer_train_demo_audit_v2 as demo_audit
from .budget_ledger import audit as budget_audit
from .post_enter_train_probe_v1 import SAMPLE_DELAYS_MS
from .qwen_v064_adapter import application_frame_digest
from .reconcile_interrupted_sweep import active_hashes
from .v066_scoped_profile_reference import validate_reference
from .v066_storage_budget import audit as storage_audit
from .v066_post_enter_train_calibration_v1 import (
    LANE_CAP_USD, LEASE_SECONDS, PERMIT_SCHEMA, _private,
    _write_new, digest, validate_source,
)


REVIEW_SCHEMA = "cua-native-wdi-v066-post-enter-train-review-private-v1"


def _budget_summary(value: dict) -> dict:
    budget = budget_audit(
        Path(value["work_root"]), proposed_new_sandboxes=3,
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=LANE_CAP_USD)
    if budget["within_cap"] is not True:
        raise ValueError("Train calibration three-guest lane no longer fits")
    return {name: budget[name] for name in (
        "past_attempt_or_batch_count", "past_conservative_reserved_usd",
        "proposed_reserved_usd", "combined_reserved_usd", "within_cap",
    )}


def review(*, freeze_path: Path, review_path: Path,
           permit_path: Path, active_probe=active_hashes) -> dict:
    value = validate_source(freeze_path)
    output = Path(value["output_root"])
    if (review_path.exists() or review_path.is_symlink() or
            permit_path.exists() or permit_path.is_symlink() or
            review_path == permit_path or output.exists() or
            output.is_symlink()):
        raise ValueError("Exclusive calibration review/permit/output required")
    active, count = active_probe()
    if active or count:
        raise ValueError("Provider active before independent train review")
    storage = storage_audit(output.parent)
    if storage["dispatch_storage_ready"] is not True:
        raise ValueError("Raw frame storage unavailable before train review")
    budget = _budget_summary(value)
    review_value = {
        "schema": REVIEW_SCHEMA,
        "status": "accepted_exact_three_train_guests_without_provider_create",
        "freeze_sha256": digest(_private(freeze_path)),
        "source_sha256s": value["source_sha256s"],
        "output_root": value["output_root"],
        "guest_count": 3,
        "provider_active_at_review": 0,
        "storage_ready_at_review": True,
        "budget_before_three_guests": budget,
        "same_intent_replay_authorized": False,
        "official_final_admissions": 0,
    }
    review_sha = _write_new(review_path, review_value)
    permit = {
        "schema": PERMIT_SCHEMA,
        "status": "reviewed_exact_three_train_guests",
        "freeze_sha256": review_value["freeze_sha256"],
        "source_sha256s": value["source_sha256s"],
        "output_root": value["output_root"],
        "guest_count": 3,
        "review_path": str(review_path.resolve()),
        "review_sha256": review_sha,
        "budget_before_three_guests": budget,
        "same_intent_replay_authorized": False,
        "dispatch_authorized": True,
        "official_final_admissions": 0,
    }
    permit_sha = _write_new(permit_path, permit)
    return {"status": "private_train_permit_written_without_provider_create",
            "review_sha256": review_sha, "permit_sha256": permit_sha,
            "official_final_admissions": 0}


def checked_permit(*, freeze_path: Path, permit_path: Path,
                   value: dict) -> dict:
    permit = json.loads(_private(permit_path))
    review_path = Path(permit.get("review_path", ""))
    if not review_path.is_absolute():
        raise ValueError("Absolute independent train review path required")
    review_raw = _private(review_path)
    review_value = json.loads(review_raw)
    budget = _budget_summary(value)
    if (permit.get("schema") != PERMIT_SCHEMA or
            permit.get("status") != "reviewed_exact_three_train_guests" or
            permit.get("freeze_sha256") != digest(_private(freeze_path)) or
            permit.get("source_sha256s") != value["source_sha256s"] or
            permit.get("output_root") != value["output_root"] or
            permit.get("guest_count") != 3 or
            permit.get("review_sha256") != digest(review_raw) or
            permit.get("budget_before_three_guests") != budget or
            permit.get("same_intent_replay_authorized") is not False or
            permit.get("dispatch_authorized") is not True or
            review_value.get("schema") != REVIEW_SCHEMA or
            review_value.get("status") !=
                "accepted_exact_three_train_guests_without_provider_create" or
            review_value.get("freeze_sha256") != permit["freeze_sha256"] or
            review_value.get("source_sha256s") != value["source_sha256s"] or
            review_value.get("output_root") != value["output_root"] or
            review_value.get("guest_count") != 3 or
            review_value.get("budget_before_three_guests") != budget or
            review_value.get("provider_active_at_review") != 0 or
            review_value.get("storage_ready_at_review") is not True or
            review_value.get("same_intent_replay_authorized") is not False or
            permit.get("official_final_admissions") != 0 or
            review_value.get("official_final_admissions") != 0):
        raise ValueError("Train calibration independent permit changed")
    return permit


def _bound(root: Path, ref: dict) -> bytes:
    relative = ref.get("private_path")
    if type(relative) is not str:
        raise ValueError("Private calibration frame path missing")
    path = (root / relative).resolve()
    if (not path.is_relative_to(root.resolve()) or not path.is_file() or
            path.is_symlink() or path.stat().st_mode & 0o077):
        raise ValueError("Private calibration frame absent or unsafe")
    raw = path.read_bytes()
    if len(raw) != ref.get("bytes") or digest(raw) != ref.get("sha256"):
        raise ValueError("Private calibration frame changed")
    return raw


def _post_enter_samples(*, output_root: Path) -> dict:
    path = output_root / "calc/post-enter-samples.ndjson"
    lines = _private(path).splitlines()
    if len(lines) != 2 * len(SAMPLE_DELAYS_MS):
        raise ValueError("Two full train Enter sample windows required")
    records = [json.loads(raw) for raw in lines]
    distinct_frames = set()
    for ordinal in (0, 1):
        group = records[ordinal * 5:(ordinal + 1) * 5]
        if ([row.get("enter_ordinal") for row in group] != [ordinal] * 5 or
                [row.get("sample") for row in group] != list(range(5)) or
                [row.get("requested_delay_ms_before_sample") for row in group]
                != list(SAMPLE_DELAYS_MS)):
            raise ValueError("Post-Enter sample order or fixed bound changed")
        application = []
        window = []
        for row in group:
            raw = _bound(output_root, row["frame"])
            if (row.get("schema") !=
                    "cua-native-wdi-v066-post-enter-train-sample-v1" or
                    row.get("full_frame_sha256") != digest(raw) or
                    row.get("application_frame_sha256") !=
                        application_frame_digest(raw) or
                    row.get("document_window_stable") is not True or
                    type(row.get("monotonic_before_ns")) is not int or
                    type(row.get("monotonic_after_ns")) is not int or
                    row["monotonic_after_ns"] < row["monotonic_before_ns"] or
                    row.get("elapsed_since_enter_ns", -1) < 0 or
                    row["elapsed_since_enter_ns"] > 10_000_000_000):
                raise ValueError("Post-Enter timestamp/frame/window evidence changed")
            application.append(row["application_frame_sha256"])
            window.append(row["window_id_after_sha256"])
            distinct_frames.add(row["full_frame_sha256"])
        transitions = []
        for frame_sha in application:
            if not transitions or frame_sha != transitions[-1]:
                transitions.append(frame_sha)
        if (len(set(window)) != 1 or
                any(group[index + 1]["monotonic_before_ns"] <
                    group[index]["monotonic_after_ns"] for index in range(4)) or
                application[-2] != application[-1] or
                len(transitions) > 2 or
                len(transitions) != len(set(transitions)) or
                group[-1]["elapsed_since_enter_ns"] <
                    sum(SAMPLE_DELAYS_MS) * 1_000_000):
            raise ValueError("Modal, reordered, or oscillating train calibration")
    return {"enter_windows": 2, "raw_frames": len(records),
            "distinct_full_frames": len(distinct_frames),
            "private_sample_ledger_sha256": digest(_private(path))}


def audit(*, freeze_path: Path, run_path: Path) -> dict:
    value = validate_source(freeze_path)
    output_root = Path(value["output_root"])
    run = json.loads(_private(run_path))
    if (run.get("schema") !=
            "cua-native-wdi-v066-post-enter-train-calibration-run-private-v1" or
            run.get("status") not in
                ("started", "three_train_guests_independently_audited") or
            run.get("freeze_sha256") != digest(_private(freeze_path)) or
            run.get("output_root") != value["output_root"] or
            run.get("guest_count_planned") != 3 or
            run.get("official_final_admissions") != 0):
        raise ValueError("Root-owned train calibration run changed")
    # Re-open the unchanged original train positives and scored OOXML bytes.
    demos, _public = demo_audit.audit_both(
        output_root=output_root,
        scoped_reference=Path(value["scoped_reference"]),
        guest_public=Path(value["guest_public"]),
        reservation_path=Path(value["reservation_path"]))
    samples = _post_enter_samples(output_root=output_root)
    cold_dir = output_root / "cold-reset"
    intent_raw = _private(cold_dir / "intent.json")
    receipt_raw = _private(cold_dir / "receipt.json")
    intent, receipt = json.loads(intent_raw), json.loads(receipt_raw)
    package, _oracle, baseline, _instruction, _filename = demo._source("calc")
    if (intent.get("schema") !=
            "cua-native-wdi-v066-post-enter-train-cold-intent-v1" or
            intent.get("status") != "recorded_before_provider_create" or
            intent.get("split") != "train" or
            intent.get("package_sha256") != package["package_sha256"] or
            intent.get("input_sha256") != digest(baseline) or
            intent.get("freeze_sha256") != digest(_private(freeze_path)) or
            intent.get("permit_sha256") != run.get("permit_sha256") or
            intent.get("lease_seconds") != LEASE_SECONDS or
            intent.get("same_intent_replay_authorized") is not False or
            receipt.get("schema") !=
                "cua-native-wdi-v066-post-enter-train-cold-receipt-v1" or
            receipt.get("status") != "cold_reset_observed" or
            receipt.get("split") != "train" or
            receipt.get("package_sha256") != package["package_sha256"] or
            receipt.get("input_sha256") != digest(baseline) or
            receipt.get("intent_sha256") != digest(intent_raw) or
            receipt.get("guest_content_attested") is not True or
            receipt.get("fresh_profile_absent") is not True or
            receipt.get("task_profile_scoped_attested") is not True or
            receipt.get("restored_state_sha256") != digest(baseline) or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            receipt.get("official_final_admissions") != 0):
        raise ValueError("Fresh train Calc reset or original bytes changed")
    _bound(output_root, receipt["cold_observation"])
    if _bound(output_root, receipt["restored_artifact"]) != baseline:
        raise ValueError("Fresh reset saved OOXML differs from original source")
    from . import v066_profile_scope_analysis as scope
    reference, _sha = validate_reference(Path(value["scoped_reference"]))
    for snapshot in receipt.get("task_profile_scoped_snapshots", []):
        manifest = json.loads(_bound(output_root, snapshot["manifest"]))
        registry = _bound(output_root, snapshot["registry"])
        _bound(output_root, snapshot["visible_frame"])
        if scope.scoped_profile(manifest, registry) != reference["applications"]["calc"]:
            raise ValueError("Fresh reset Calc profile differs from train reference")
    if len(receipt.get("task_profile_scoped_snapshots", [])) != 2:
        raise ValueError("Fresh reset profile pair missing")
    sandbox_ids = [row["sandbox_id_sha256"] for row in demos["demos"]]
    sandbox_ids.append(receipt.get("sandbox_id_sha256"))
    if None in sandbox_ids or len(set(sandbox_ids)) != 3:
        raise ValueError("Train positive and reset guests were not distinct")
    ledger = storage_audit(output_root, verify_all_bytes=True)
    active, count = active_hashes()
    if active or count or ledger["unresolved_write_count"]:
        raise ValueError("Train raw evidence or provider cleanup not reconciled")
    return {
        "schema": "cua-native-wdi-v066-post-enter-train-calibration-audit-public-v1",
        "status": "three_public_train_guests_saved_state_and_reset_audited",
        "source_scope": "public_train_only",
        "positive_saved_workflows": 2,
        "post_enter_windows": samples["enter_windows"],
        "post_enter_raw_frames": samples["raw_frames"],
        "distinct_sandbox_guests": 3,
        "calc_cold_reset_original_bytes_verified": True,
        "provider_active_after": 0,
        "private_sample_ledger_sha256": samples["private_sample_ledger_sha256"],
        "full_lease_intents_charged": 3,
        "same_intent_replay_authorized": False,
        "official_final_admissions": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("review", "audit"))
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--review-out", type=Path)
    parser.add_argument("--permit-out", type=Path)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    if args.mode == "review":
        if args.review_out is None or args.permit_out is None:
            raise ValueError("Exact private review and permit paths required")
        result = review(
            freeze_path=args.freeze,
            review_path=args.review_out, permit_path=args.permit_out)
    else:
        if args.run is None:
            raise ValueError("Root-owned train run path required")
        result = audit(freeze_path=args.freeze, run_path=args.run)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
