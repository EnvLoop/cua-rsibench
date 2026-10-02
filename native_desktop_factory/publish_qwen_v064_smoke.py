"""Publish an allowlisted aggregate of a private nonfinal Qwen Desktop smoke."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

if __package__:
    from .budget_ledger import audit as audit_budget
else:
    from budget_ledger import audit as audit_budget


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aggregate(receipt_path: Path, work_root: Path) -> dict:
    raw = receipt_path.read_bytes()
    private = json.loads(raw)
    samples = private.get("sampling", [])
    actions = private.get("actions", [])
    if (private.get("schema") != "cua-native-wdi-gui-development-attempt-v1"
            or private.get("attempt") != "qwen_v064_nonfinal_smoke"
            or private.get("split") not in ("train", "selection")
            or private.get("renderer_identity", {}).get("model") != "Qwen/Qwen3.8-27B"
            or len(samples) > private["max_samples"]
            or sum(row.get("status") == "applied" for row in actions) > private["max_actions"]):
        raise ValueError("Private receipt is not a bounded nonfinal v0.6.4 smoke")
    ledger = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not ledger["within_cap"]:
        raise ValueError("Post-smoke lane reserve exceeds cap")
    historical = []
    for path in sorted((work_root / "gui-diagnostics").glob("qwen-v064-train-smoke-*/receipt.json")):
        historical_raw = path.read_bytes()
        row = json.loads(historical_raw)
        if (row.get("schema") != "cua-native-wdi-gui-development-attempt-v1"
                or row.get("attempt") != "qwen_v064_nonfinal_smoke"
                or row.get("split") not in ("train", "selection")):
            raise ValueError("Historical smoke receipt is not a nonfinal attempt")
        historical.append((digest(historical_raw), row))
    if not historical or len({sha for sha, _ in historical}) != len(historical):
        raise ValueError("Historical nonfinal smoke receipts missing or duplicated")
    return {
        "schema": "cua-native-wdi-qwen-v064-nonfinal-smoke-public-v1",
        "checked_date": "2026-09-27",
        "scope": f"Latest of {len(historical)} train/selection-only development boundary smokes; no final-candidate model exposure or official full-study outcome.",
        "split": private["split"],
        "private_receipt_sha256": digest(raw),
        "historical_nonfinal_attempt_count": len(historical),
        "historical_private_receipt_sha256s": [sha for sha, _ in historical],
        "historical_attempt_status_counts": dict(sorted(Counter(
            row["status"] for _, row in historical).items())),
        "historical_completed_multimodal_samples": sum(
            sample.get("status") == "completed"
            for _, row in historical for sample in row.get("sampling", [])),
        "historical_applied_gui_actions": sum(
            action.get("status") == "applied"
            for _, row in historical for action in row.get("actions", [])),
        "historical_rejected_action_code_counts": dict(sorted(Counter(
            action.get("error_code")
            for _, row in historical for action in row.get("actions", [])
            if action.get("status") == "rejected").items())),
        "shared_action_parser_sha256": private["shared_action_parser_sha256"],
        "shared_v064_adapter_sha256": private["shared_v064_adapter_sha256"],
        "shared_vision_proxy_sha256": private["shared_vision_proxy_sha256"],
        "runner_source_sha256": private.get("runner_source_sha256"),
        "native_adapter_source_sha256": private.get("native_adapter_source_sha256"),
        "renderer_identity": private["renderer_identity"],
        "sampling_binding_sha256": private["sampling_binding_sha256"],
        "provider_template_id": private["provider_sandbox_info"]["template_id"],
        "provider_envd_version": private["provider_sandbox_info"]["envd_version"],
        "provider_resource_shape": {
            "vcpu": private["provider_sandbox_info"]["vcpu"],
            "memory_mb": private["provider_sandbox_info"]["memory_mb"],
        },
        "screenshot_size": {key: samples[0]["image"][key]
                            for key in ("width", "height", "pixels")},
        "completed_multimodal_samples": sum(row["status"] == "completed" for row in samples),
        "private_frame_screenshots_retained": len(private.get("frame_screenshots", [])),
        "sample_errors": [row.get("error_subtype") for row in samples if row["status"] != "completed"],
        "rendered_usage_not_billing": [row.get("usage") for row in samples],
        "applied_gui_action_types": [row["type"] for row in actions if row["status"] == "applied"],
        "rejected_action_codes": [row["error_code"] for row in actions if row["status"] == "rejected"],
        "saved_artifact_changed": private.get("saved_changed"),
        "development_verifier_passed": private.get("development_verifier", {}).get("passed"),
        "runner_status": private["status"],
        "sandbox_terminated": private.get("is_running_after_kill") is False,
        "tinker_session_closed": private.get("tinker_session_closed") is True,
        "e2b_full_lease_reserve_usd_for_smoke": private["e2b_lane_budget_before"]["proposed_reserved_usd"],
        "e2b_lane_full_lease_reserve_usd_after_smoke": ledger["past_conservative_reserved_usd"],
        "e2b_lane_cap_usd": ledger["lane_usd_cap"],
        "provider_billed_usd": None,
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite public aggregate")
    result = aggregate(args.receipt, args.work_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "completed_multimodal_samples", "applied_gui_action_types",
        "sandbox_terminated", "development_verifier_passed",
        "e2b_lane_full_lease_reserve_usd_after_smoke")}, sort_keys=True))


if __name__ == "__main__":
    main()
