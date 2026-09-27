"""Admit an observed profile only after the full E2B lease and provider check.

The original cleanup-uncertain receipt is never modified. Reconciliation proves
that its acknowledged sandbox is no longer active after the full lease plus a
grace period; it does not reinterpret a model or profile-content failure.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

if __package__:
    from .reconcile_interrupted_sweep import active_hashes
else:
    from reconcile_interrupted_sweep import active_hashes


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reconcile(receipt_path: Path, *, grace_seconds: int) -> dict:
    if not 60 <= grace_seconds <= 600 or not os.environ.get("E2B_API_KEY"):
        raise ValueError("Grace bound or E2B credential missing")
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if (receipt.get("schema") != "cua-native-wdi-profile-baseline-v1"
            or receipt.get("status") != "profile_baseline_observed"
            or receipt.get("canonical_profile_sha256") is None
            or receipt.get("input_unchanged_after_open") is not True
            or receipt.get("sandbox_id_sha256") is None
            or receipt.get("kill_error_type") is None):
        raise ValueError("Not a complete profile with uncertain teardown")
    metadata = receipt_path.parent.stat()
    created_at = getattr(metadata, "st_birthtime", metadata.st_ctime)
    lease_ends_at = created_at + receipt["lease_seconds"]
    checked_at = time.time()
    if checked_at < lease_ends_at + grace_seconds:
        raise ValueError("Full server lease plus grace has not matured")
    running_hashes, account_running = active_hashes()
    if receipt["sandbox_id_sha256"] in running_hashes:
        raise ValueError("Original cleanup-uncertain sandbox is still running")
    return {
        "schema": "cua-native-wdi-profile-baseline-cleanup-reconciliation-v1",
        "status": "reconciled_terminated_after_full_lease",
        "private_task_id": receipt["task_id"],
        "original_receipt_sha256": digest(raw),
        "sandbox_id_sha256": receipt["sandbox_id_sha256"],
        "canonical_profile_sha256": receipt["canonical_profile_sha256"],
        "original_kill_error_type": receipt["kill_error_type"],
        "server_lease_seconds": receipt["lease_seconds"],
        "grace_seconds": grace_seconds,
        "elapsed_since_directory_creation_seconds": round(checked_at - created_at, 3),
        "account_running_sandboxes_at_check": account_running,
        "specific_sandbox_running_at_check": False,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "actual_billed_usd": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--grace-seconds", type=int, default=90)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite cleanup reconciliation")
    result = reconcile(args.receipt, grace_seconds=args.grace_seconds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "specific_sandbox_running_at_check": False,
                      "account_running_sandboxes_at_check": result["account_running_sandboxes_at_check"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
