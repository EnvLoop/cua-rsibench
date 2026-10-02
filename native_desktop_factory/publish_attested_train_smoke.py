"""Publish aggregate-only Qwen v0.6.4 Desktop attestation development evidence."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .budget_ledger import audit as audit_budget
else:
    from budget_ledger import audit as audit_budget


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aggregate(attempt_dirs: list[Path], work_root: Path) -> dict:
    if len(attempt_dirs) != 6 or len({str(p.resolve()) for p in attempt_dirs}) != 6:
        raise ValueError("Exactly six distinct preserved attested smoke directories required")
    private_raw = [(path / "receipt.json").read_bytes() for path in attempt_dirs]
    rows = [json.loads(raw) for raw in private_raw]
    if any(row.get("schema") != "cua-native-wdi-gui-development-attempt-v1"
           or row.get("attempt") != "qwen_v064_nonfinal_smoke"
           or row.get("split") != "train"
           or row.get("is_running_after_kill") is not False
           or row.get("tinker_session_closed") is not True
           or row.get("guest_content_attested") is not True
           or row.get("fresh_libreoffice_profile_absent") is not True
           for row in rows):
        raise ValueError("Attested smoke is not completed, nonfinal and torn down")
    if len({row.get("sandbox_id_sha256") for row in rows}) != 6:
        raise ValueError("Attested smokes did not use six distinct sandboxes")
    identity_binding = {row["expected_guest_identity_manifest_sha256"] for row in rows}
    profile_binding = {row["expected_profile_manifest_sha256"] for row in rows}
    if len(identity_binding) != 1 or len(profile_binding) != 1:
        raise ValueError("Attested smokes used different frozen guest/profile references")
    ledger = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not ledger["within_cap"]:
        raise ValueError("Desktop development lane reserve exceeded cap")
    return {
        "schema": "cua-native-wdi-attested-qwen-v064-train-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Six bounded Qwen3.8-27B development attempts on one training-only native Calc package after independent guest-content and task-bound profile checks. No final-candidate model attempt or official result.",
        "attempt_count": len(rows),
        "private_receipt_sha256s": [digest(raw) for raw in private_raw],
        "expected_guest_identity_manifest_sha256": next(iter(identity_binding)),
        "expected_profile_manifest_sha256": next(iter(profile_binding)),
        "all_sandbox_terminations_verified": True,
        "all_tinker_sessions_closed": True,
        "guest_content_attestation_pass_count": sum(row.get("guest_content_attested") is True for row in rows),
        "fresh_profile_absence_pass_count": sum(row.get("fresh_libreoffice_profile_absent") is True for row in rows),
        "task_bound_canonical_profile_pass_count": sum(row.get("task_bound_profile_attested") is True for row in rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "private_setup_error_type_counts": dict(sorted(Counter(
            row.get("error_type") for row in rows if row.get("error_type")).items())),
        "completed_multimodal_samples": sum(
            result.get("status") == "completed"
            for row in rows for result in row.get("sampling", [])),
        "returned_image_token_counts": [
            result.get("usage", {}).get("image_tokens")
            for row in rows for result in row.get("sampling", [])
            if result.get("status") == "completed"],
        "applied_gui_actions": sum(
            action.get("status") == "applied"
            for row in rows for action in row.get("actions", [])),
        "rejected_action_code_counts": dict(sorted(Counter(
            action.get("error_code") for row in rows for action in row.get("actions", [])
            if action.get("status") == "rejected").items())),
        "physical_stale_recheck_screenshot_count": sum(
            len(row.get("stale_recheck_screenshots", [])) for row in rows),
        "saved_training_artifact_changed_count": sum(row.get("saved_changed") is True for row in rows),
        "latest_shared_action_parser_sha256": rows[-1]["shared_action_parser_sha256"],
        "latest_shared_v064_adapter_sha256": rows[-1]["shared_v064_adapter_sha256"],
        "latest_native_adapter_source_sha256": rows[-1]["native_adapter_source_sha256"],
        "latest_runner_source_sha256": rows[-1]["runner_source_sha256"],
        "provider_template_id": rows[-1]["provider_sandbox_info"]["template_id"],
        "provider_envd_version": rows[-1]["provider_sandbox_info"]["envd_version"],
        "official_full_study_desktop_admissions": 0,
        "official_full_study_desktop_model_results": 0,
        "native_lane_full_server_lease_reserve_usd": ledger["past_conservative_reserved_usd"],
        "native_lane_cap_usd": ledger["lane_usd_cap"],
        "actual_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", type=Path, action="append", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite attested smoke aggregate")
    result = aggregate(args.attempt_dir, args.work_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "attempt_count", "task_bound_canonical_profile_pass_count",
        "completed_multimodal_samples", "applied_gui_actions",
        "physical_stale_recheck_screenshot_count",
        "native_lane_full_server_lease_reserve_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
