"""Read-only v0.6.6 final-control interruption and provider lease audit.

Missing acknowledgements, ambiguous teardown, and failed GUI receipts retain
their full reserved lease. This never retries or upgrades a task to qualified.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from .reconcile_interrupted_sweep import active_hashes
from .v066_final_freeze import LEASE_SECONDS, digest, intent_budget


def audit(attempts_root: Path, *, grace_seconds: int,
          query_provider: bool) -> tuple[dict, dict]:
    if not 60 <= grace_seconds <= 600:
        raise ValueError("Lease reconciliation grace must be 60–600 seconds")
    rows = []
    for path in sorted(attempts_root.glob("*/*/intent.json")):
        intent_raw = path.read_bytes()
        intent = json.loads(intent_raw)
        if (intent.get("schema") != "cua-native-wdi-v066-final-control-intent-v1"
                or intent.get("lease_seconds") != LEASE_SECONDS):
            raise ValueError("Prospective final-control intent changed")
        receipt_path = path.with_name("receipt.json")
        receipt_raw = receipt_path.read_bytes() if receipt_path.is_file() else None
        receipt = json.loads(receipt_raw) if receipt_raw else {}
        try:
            started = datetime.fromisoformat(intent["created_utc"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("E2B create intent lacks a valid timestamp") from None
        if started.tzinfo is None:
            raise ValueError("E2B create intent timestamp is timezone-naive")
        expires = started.timestamp() + LEASE_SECONDS + grace_seconds
        rows.append({
            "private_task_id": intent["task_id"],
            "attempt": intent["attempt"],
            "intent_sha256": digest(intent_raw),
            "receipt_sha256": digest(receipt_raw) if receipt_raw else None,
            "status": receipt.get("status", "missing_receipt"),
            "error_type": receipt.get("error_type"),
            "sandbox_id_sha256": receipt.get("sandbox_id_sha256"),
            "kill_returned": receipt.get("kill_returned"),
            "is_running_after_kill": receipt.get("is_running_after_kill"),
            "lease_plus_grace_expired": datetime.now(timezone.utc).timestamp() >= expires,
        })
    active, count, provider_error = set(), None, None
    if query_provider:
        try:
            active, count = active_hashes()
        except Exception as exc:
            provider_error = type(exc).__name__
    unresolved = [row for row in rows if row["status"] not in
                  ("control_passed", "cold_reset_observed") or
                  row["is_running_after_kill"] is not False]
    known_active = [row for row in unresolved if row["sandbox_id_sha256"] in active]
    matured = all(row["lease_plus_grace_expired"] for row in unresolved)
    budget = intent_budget(attempts_root)
    private = {
        "schema": "cua-native-wdi-v066-final-control-reconciliation-private-v1",
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "attempt_rows": rows,
        "provider_active_sandbox_id_sha256s": sorted(active),
        "provider_active_error_type": provider_error,
        "provider_active_total": count,
        "known_unresolved_active_count": len(known_active),
        "all_unresolved_leases_plus_grace_expired": matured,
        "ready_for_manual_repair_review": bool(unresolved) and query_provider and
        provider_error is None and count == 0 and matured,
        "automatic_replay_authorized": False,
        "official_full_study_admissions": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-final-control-reconciliation-public-v1",
        "checked_date": "2026-09-27",
        "attempted_sandboxes": len(rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "missing_receipt_count": sum(row["receipt_sha256"] is None for row in rows),
        "no_acknowledged_sandbox_id_count": sum(row["sandbox_id_sha256"] is None for row in rows),
        "cleanup_unverified_count": sum(row["is_running_after_kill"] is not False for row in rows),
        "provider_active_total": count,
        "provider_active_error_type": provider_error,
        "known_unresolved_active_count": len(known_active),
        "all_unresolved_leases_plus_grace_expired": matured,
        "ready_for_manual_repair_review": private["ready_for_manual_repair_review"],
        "conservative_full_lease_reserved_usd": budget["combined_full_lease_reserved_usd"],
        "lane_cap_usd": budget["lane_cap_usd"],
        "actual_provider_billed_usd": None,
        "automatic_replay_authorized": False,
        "official_full_study_admissions": 0,
    }
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--grace-seconds", type=int, default=90)
    parser.add_argument("--query-provider", action="store_true")
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Refusing to overwrite reconciliation evidence")
    private, public = audit(args.attempts_root,
                            grace_seconds=args.grace_seconds,
                            query_provider=args.query_provider)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
    args.private_out.chmod(0o600)
    public["private_reconciliation_sha256"] = digest(args.private_out.read_bytes())
    args.public_out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: public[key] for key in (
        "attempted_sandboxes", "missing_receipt_count",
        "cleanup_unverified_count", "ready_for_manual_repair_review",
        "official_full_study_admissions")}, sort_keys=True))


if __name__ == "__main__":
    main()
