"""Reconcile one failed E2B create with no acknowledged sandbox identity."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

if __package__:
    from .reconcile_interrupted_sweep import active_hashes
else:
    from reconcile_interrupted_sweep import active_hashes


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reconcile(attempt_dir: Path, *, grace_seconds: int,
              query_provider: bool) -> dict:
    if not 60 <= grace_seconds <= 600:
        raise ValueError("Grace interval out of bound")
    receipt_raw = (attempt_dir / "receipt.json").read_bytes()
    receipt = json.loads(receipt_raw)
    if receipt.get("status") != "error" or receipt.get("error_type") != "ConnectError":
        raise ValueError("Not a failed E2B create transport receipt")
    if receipt.get("sandbox_id_sha256") or receipt.get("staged_sha256") or receipt.get("actor_actions"):
        raise ValueError("Attempt progressed beyond a no-ID pre-action create")
    lease = receipt.get("sandbox_timeout_seconds")
    if not isinstance(lease, int) or not 120 <= lease <= 600:
        raise ValueError("No bounded server lease in attempt receipt")
    expiry = attempt_dir.stat().st_birthtime + lease + grace_seconds
    elapsed = time.time() >= expiry
    error_type, account_running = None, None
    if query_provider:
        try:
            _, account_running = active_hashes()
        except Exception as exc:
            error_type = type(exc).__name__
    return {"schema": "cua-native-wdi-single-noid-create-reconciliation-v1",
            "checked_utc": datetime.now(timezone.utc).isoformat(),
            "failed_attempt_receipt_sha256": digest(receipt_raw),
            "reason": "preaction_E2B_ConnectError_no_acknowledged_sandbox_id",
            "server_lease_seconds": lease,
            "grace_seconds": grace_seconds,
            "maximum_lease_plus_grace_utc": datetime.fromtimestamp(expiry, timezone.utc).isoformat(),
            "all_unknown_leases_elapsed": elapsed,
            "account_running_total_at_query": account_running,
            "provider_list_error_type": error_type,
            "conservative_lease_reserve_at_1_usd_per_hour": round(lease / 3600, 6),
            "actual_billed_usd": None,
            "ready_for_separate_health_probe": elapsed and query_provider and error_type is None,
            "note": "No GUI action, artifact upload, model result, or task score occurred. Any server-side allocation had a bounded lease; provider billing remains unknown."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--grace-seconds", type=int, default=90)
    parser.add_argument("--query-provider", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite no-ID reconciliation evidence")
    result = reconcile(args.attempt_dir, grace_seconds=args.grace_seconds,
                       query_provider=args.query_provider)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ready": result["ready_for_separate_health_probe"],
                      "leases_elapsed": result["all_unknown_leases_elapsed"],
                      "provider_list_error_type": result["provider_list_error_type"],
                      "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
