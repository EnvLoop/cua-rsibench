"""Publish only aggregate evidence for three preserved v0.6.5 train smokes."""

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


def aggregate(attempt_dirs: list[Path], work_root: Path,
              provider_probe: Path) -> dict:
    if len(attempt_dirs) != 3 or len({str(path.resolve()) for path in attempt_dirs}) != 3:
        raise ValueError("Expected three distinct historical v0.6.5 train attempts")
    raws = [(path / "receipt.json").read_bytes() for path in attempt_dirs]
    rows = [json.loads(raw) for raw in raws]
    if any(row.get("schema") != "cua-native-wdi-gui-development-attempt-v1"
           or row.get("attempt") != "qwen_v065_nonfinal_smoke"
           or row.get("split") != "train"
           or row.get("selected_model_output_version") != "scale-action-output-v0.6.5"
           or row.get("renderer_identity", {}).get("model") != "Qwen/Qwen3.8-27B"
           or row.get("guest_content_attested") is not True
           or row.get("task_bound_profile_attested") is not True
           or row.get("is_running_after_kill") is not False
           or row.get("tinker_session_closed") is not True
           for row in rows):
        raise ValueError("v0.6.5 smoke lacks training/attestation/cleanup proof")
    if len({row["sandbox_id_sha256"] for row in rows}) != 3:
        raise ValueError("v0.6.5 smokes reused a sandbox")
    if len({row["expected_guest_identity_manifest_sha256"] for row in rows}) != 1 or len({
            row["expected_profile_manifest_sha256"] for row in rows}) != 1:
        raise ValueError("v0.6.5 smokes changed environment baseline")
    provider_raw = provider_probe.read_bytes()
    provider = json.loads(provider_raw)
    if (provider.get("schema") != "cua-native-wdi-v065-provider-active-v1"
            or provider.get("account_running_sandboxes") != 0
            or provider.get("running_sandbox_id_sha256s") != []):
        raise ValueError("Provider still shows active sandboxes")
    ledger = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not ledger["within_cap"]:
        raise ValueError("Native lane reserve exceeds cap")
    latest = rows[-1]
    return {
        "schema": "cua-native-wdi-qwen-v065-nonfinal-live-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Three pre-result v0.6.5 variants on one train-only native Calc task. Latest prompt removes a literal dummy ref; earlier failed variants are preserved. No final model attempt or official score.",
        "attempt_count": len(rows),
        "private_receipt_sha256s": [digest(raw) for raw in raws],
        "distinct_actor_sandboxes": 3,
        "all_guest_content_attested": True,
        "all_task_bound_profiles_attested": True,
        "all_sandboxes_terminated": True,
        "all_tinker_sessions_closed": True,
        "provider_active_probe_sha256": digest(provider_raw),
        "historical_status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "distinct_output_adapter_source_sha256s": sorted({
            row["selected_model_output_adapter_sha256"] for row in rows}),
        "latest_output_adapter_sha256": latest["selected_model_output_adapter_sha256"],
        "latest_native_desktop_adapter_sha256": latest["native_adapter_source_sha256"],
        "latest_train_runner_sha256": latest["runner_source_sha256"],
        "latest_shared_action_parser_sha256": latest["shared_action_parser_sha256"],
        "latest_renderer_identity": latest["renderer_identity"],
        "completed_multimodal_samples": sum(
            sample.get("status") == "completed"
            for row in rows for sample in row.get("sampling", [])),
        "output_token_limit_stop_count": sum(
            sample.get("stop_reason") == "length"
            for row in rows for sample in row.get("sampling", [])),
        "applied_gui_action_types": [action["type"]
            for row in rows for action in row.get("actions", [])
            if action.get("status") == "applied"],
        "rejected_action_code_counts": dict(sorted(Counter(
            action.get("error_code") for row in rows for action in row.get("actions", [])
            if action.get("status") == "rejected").items())),
        "latest_attempt_completed_samples": sum(
            sample.get("status") == "completed" for sample in latest["sampling"]),
        "latest_attempt_applied_gui_actions": sum(
            action.get("status") == "applied" for action in latest["actions"]),
        "saved_training_artifact_changed_count": sum(row.get("saved_changed") is True for row in rows),
        "official_hidden_final_model_attempts": 0,
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
    parser.add_argument("--provider-probe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite public v0.6.5 smoke aggregate")
    result = aggregate(args.attempt_dir, args.work_root, args.provider_probe)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "attempt_count", "completed_multimodal_samples",
        "latest_attempt_applied_gui_actions", "historical_status_counts",
        "native_lane_full_server_lease_reserve_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
