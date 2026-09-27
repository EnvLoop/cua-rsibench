"""Audit 100 private final task-bound native profile baselines and publish counts.

Only the private manifest contains task IDs and profile hashes. Public output
is aggregate-only and never upgrades an official full-study admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

if __package__:
    from .budget_ledger import audit as audit_budget
    from .runtime_fingerprint_probe import PROFILE_FILE_PROBE
else:
    from budget_ledger import audit as audit_budget
    from runtime_fingerprint_probe import PROFILE_FILE_PROBE


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def audit(candidate_root: Path, work_root: Path, runtime_manifest: Path,
          reconciliation_path: Path, provider_probe_path: Path) -> tuple[dict, dict]:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    if (inventory.get("design_revision") != "v2-distinct-structures"
            or len(final) != 100 or len({row["task_id"] for row in final}) != 100):
        raise ValueError("Expected 100 distinct-template private final identities")
    runtime_raw = runtime_manifest.read_bytes()
    runtime = json.loads(runtime_raw)
    expected_runtime_sha = digest(runtime_raw)
    expected_probe_sha = digest(PROFILE_FILE_PROBE.encode())
    reconciliation_raw = reconciliation_path.read_bytes()
    reconciliation = json.loads(reconciliation_raw)
    if (reconciliation.get("schema") != "cua-native-wdi-profile-baseline-cleanup-reconciliation-v1"
            or reconciliation.get("status") != "reconciled_terminated_after_full_lease"
            or reconciliation.get("specific_sandbox_running_at_check") is not False):
        raise ValueError("Cleanup-uncertain profile baseline was not independently reconciled")
    provider_raw = provider_probe_path.read_bytes()
    provider = json.loads(provider_raw)
    if (provider.get("schema") != "cua-native-wdi-profile-final-provider-active-v1"
            or provider.get("account_running_sandboxes") != 0
            or provider.get("running_sandbox_id_sha256s") != []):
        raise ValueError("Provider still shows an active sandbox")
    attempts = []
    for path in sorted((work_root / "gui-diagnostics").glob("profile-baseline-*/receipt.json")):
        raw = path.read_bytes()
        row = json.loads(raw)
        if row.get("schema") != "cua-native-wdi-profile-baseline-v1":
            raise ValueError("Malformed profile-baseline attempt")
        attempts.append({"path": path, "receipt": row, "receipt_sha256": digest(raw)})
    by_id = {row["task_id"]: [] for row in final}
    for attempt in attempts:
        task_id = attempt["receipt"].get("task_id")
        if task_id not in by_id:
            raise ValueError("Profile attempt belongs to an unknown final task")
        by_id[task_id].append(attempt)
    accepted, historical = [], []
    for row in sorted(final, key=lambda item: item["task_id"]):
        choices = by_id[row["task_id"]]
        if not choices:
            raise ValueError("Missing task-bound profile baseline")
        for attempt in choices:
            receipt = attempt["receipt"]
            if (receipt.get("input_sha256") != row["input_sha256"]
                    or receipt.get("package_sha256") != row["package_sha256"]
                    or receipt.get("runtime_reference_sha256") != expected_runtime_sha
                    or receipt.get("profile_probe_script_sha256") != expected_probe_sha
                    or receipt.get("split") != "final_candidate"):
                raise ValueError("Profile attempt is not bound to the final package/runtime")
            historical.append(receipt["status"])
        direct = [item for item in choices
                  if item["receipt"].get("status") == "profile_baseline_passed"
                  and item["receipt"].get("is_running_after_kill") is False]
        reconciled = [item for item in choices if
                      item["receipt"].get("status") == "profile_baseline_observed"
                      and item["receipt_sha256"] == reconciliation["original_receipt_sha256"]
                      and item["receipt"].get("task_id") == reconciliation["private_task_id"]
                      and item["receipt"].get("sandbox_id_sha256") == reconciliation["sandbox_id_sha256"]
                      and item["receipt"].get("canonical_profile_sha256") == reconciliation["canonical_profile_sha256"]]
        candidates = direct + reconciled
        if len(candidates) != 1:
            raise ValueError("Final task lacks exactly one accepted profile baseline")
        chosen = candidates[0]
        receipt = chosen["receipt"]
        snapshots = receipt.get("profile_snapshot_sha256s", [])
        if (len(snapshots) < 2 or snapshots[-1] != snapshots[-2]
                or snapshots[-1] != receipt.get("canonical_profile_sha256")
                or receipt.get("fresh_profile_absent") is not True
                or receipt.get("input_unchanged_after_open") is not True
                or receipt.get("provider_sandbox_info", {}).get("template_id") != runtime["provider_template_id"]
                or receipt.get("provider_sandbox_info", {}).get("envd_version") != runtime["provider_envd_version"]
                or receipt.get("provider_sandbox_info", {}).get("vcpu") != runtime["provider_resource_shape"]["vcpu"]
                or receipt.get("provider_sandbox_info", {}).get("memory_mb") != runtime["provider_resource_shape"]["memory_mb"]):
            raise ValueError("Accepted profile baseline failed semantic/runtime checks")
        accepted.append({
            "private_task_id": row["task_id"],
            "workflow": row["workflow"],
            "source_groups": row["source_groups"],
            "package_sha256": row["package_sha256"],
            "canonical_profile_sha256": receipt["canonical_profile_sha256"],
            "receipt_sha256": chosen["receipt_sha256"],
            "sandbox_id_sha256": receipt["sandbox_id_sha256"],
            "route": "reconciled" if chosen in reconciled else "direct",
        })
    if len({row["sandbox_id_sha256"] for row in accepted}) != 100:
        raise ValueError("Accepted profile baselines reused an E2B sandbox")
    private = {
        "schema": "cua-native-wdi-private-final-profile-manifest-v1",
        "candidate_inventory_sha256": digest(inventory_raw),
        "runtime_manifest_sha256": expected_runtime_sha,
        "reconciliation_sha256": digest(reconciliation_raw),
        "provider_active_probe_sha256": digest(provider_raw),
        "accepted": accepted,
        "all_attempt_receipt_sha256s": sorted(item["receipt_sha256"] for item in attempts),
    }
    budget = audit_budget(work_root, proposed_new_sandboxes=0,
                          proposed_lease_seconds=300,
                          max_lane_reserved_usd=Decimal("40"))
    if not budget["within_cap"]:
        raise ValueError("Profile baseline lane reserve exceeded cap")
    public = {
        "schema": "cua-native-wdi-final-profile-baseline-public-v1",
        "checked_date": "2026-09-27",
        "scope": "Evaluator-only neutral GUI opens of the 100 hidden final native Office inputs; no model action, oracle inspection, or official final result.",
        "candidate_inventory_sha256": digest(inventory_raw),
        "private_profile_manifest_sha256": digest((json.dumps(private, sort_keys=True, indent=2) + "\n").encode()),
        "runtime_manifest_sha256": expected_runtime_sha,
        "cleanup_reconciliation_sha256": digest(reconciliation_raw),
        "provider_active_probe_sha256": digest(provider_raw),
        "final_candidate_count": 100,
        "task_bound_profile_baselines_qualified": len(accepted),
        "direct_baseline_count": sum(row["route"] == "direct" for row in accepted),
        "lease_reconciled_baseline_count": sum(row["route"] == "reconciled" for row in accepted),
        "distinct_accepted_sandbox_count": len({row["sandbox_id_sha256"] for row in accepted}),
        "application_counts": {
            "Calc": sum(row["workflow"].startswith("calc-") for row in accepted),
            "Impress": sum(row["workflow"].startswith("impress-") for row in accepted),
            "Writer": sum(row["workflow"].startswith("writer-") for row in accepted),
        },
        "held_out_source_family_count": len({tuple(row["source_groups"]) for row in accepted}),
        "total_historical_profile_attempt_receipts": len(attempts),
        "historical_status_counts": dict(sorted(Counter(historical).items())),
        "provider_running_sandboxes_at_final_check": 0,
        "native_lane_full_server_lease_reserve_usd": budget["past_conservative_reserved_usd"],
        "native_lane_cap_usd": budget["lane_usd_cap"],
        "actual_billed_usd": None,
        "official_full_study_desktop_admissions": 0,
        "official_full_study_desktop_model_results": 0,
    }
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--provider-active-probe", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Refusing to overwrite profile-baseline audit")
    private, public = audit(args.candidate_root, args.work_root, args.runtime_manifest,
                            args.reconciliation, args.provider_active_probe)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, sort_keys=True, indent=2) + "\n")
    if digest(args.private_out.read_bytes()) != public["private_profile_manifest_sha256"]:
        raise ValueError("Private profile manifest publication binding failed")
    args.public_out.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: public[key] for key in (
        "task_bound_profile_baselines_qualified", "direct_baseline_count",
        "lease_reconciled_baseline_count", "total_historical_profile_attempt_receipts",
        "native_lane_full_server_lease_reserve_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
