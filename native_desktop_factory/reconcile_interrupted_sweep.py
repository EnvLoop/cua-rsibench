"""Reconcile a stopped E2B sweep without replaying uncertain create calls.

No-ID create failures remain uncertain until the last attempted server lease
plus a grace interval has elapsed. Known hashed sandbox IDs are checked against
the provider's active list without publishing raw IDs. This tool does not create
or retry a sandbox; a separate health probe follows only after reconciliation.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def recent_attempts(run_dir: Path, attempts_root: Path) -> list[dict]:
    cutoff = run_dir.stat().st_birthtime
    rows = []
    for path in attempts_root.glob("*/*"):
        if not path.is_dir() or path.name not in ("positive", "near-miss", "cold-reset"):
            continue
        birth = path.stat().st_birthtime
        if birth < cutoff:
            continue
        receipt_path = path / "receipt.json"
        receipt = json.loads(receipt_path.read_bytes()) if receipt_path.is_file() else {}
        rows.append({"private_task_id": path.parent.name, "attempt": path.name,
                     "directory_birth_unix": birth,
                     "receipt_sha256": digest(receipt_path.read_bytes()) if receipt_path.is_file() else None,
                     "status": receipt.get("status", "missing_receipt"),
                     "error_type": receipt.get("error_type"),
                     "sandbox_id_sha256": receipt.get("sandbox_id_sha256"),
                     "kill_returned": receipt.get("kill_returned"),
                     "is_running_after_kill": receipt.get("is_running_after_kill"),
                     "lease_seconds": receipt.get("sandbox_timeout_seconds", 300)})
    return sorted(rows, key=lambda row: (row["directory_birth_unix"], row["private_task_id"], row["attempt"]))


def active_hashes() -> tuple[set[str], int]:
    from e2b import Sandbox
    from e2b.sandbox.sandbox_api import SandboxQuery
    from e2b.api.client.models.sandbox_state import SandboxState

    paginator = Sandbox.list(query=SandboxQuery(state=[SandboxState.RUNNING]),
                             limit=100, request_timeout=12)
    hashes = set()
    total = 0
    while paginator.has_next:
        rows = paginator.next_items()
        total += len(rows)
        hashes.update(digest(row.sandbox_id.encode()) for row in rows)
        if total > 1000:
            raise ValueError("Active sandbox pagination exceeded audit bound")
    return hashes, total


def reconcile(run_dir: Path, attempts_root: Path, *, grace_seconds: int,
              query_provider: bool) -> dict:
    if not 60 <= grace_seconds <= 600:
        raise ValueError("Grace interval out of bound")
    journal_raw = (run_dir / "run-receipt.json").read_bytes()
    journal = json.loads(journal_raw)
    if journal.get("schema") != "cua-native-wdi-final-gui-sweep-v1" or journal.get("status") != "started":
        raise ValueError("Expected the preserved interrupted sweep journal")
    attempts = recent_attempts(run_dir, attempts_root)
    if not attempts:
        raise ValueError("No attempted E2B sandbox calls found")
    max_expiry = max(row["directory_birth_unix"] + row["lease_seconds"] for row in attempts)
    now = time.time()
    matured = now >= max_expiry + grace_seconds
    observed_active, account_running = set(), None
    query_error_type = None
    if query_provider:
        if not os.environ.get("E2B_API_KEY"):
            raise ValueError("E2B_API_KEY missing")
        try:
            observed_active, account_running = active_hashes()
        except Exception as exc:
            query_error_type = type(exc).__name__
    known = {row["sandbox_id_sha256"] for row in attempts if row["sandbox_id_sha256"]}
    known_active = sorted(known & observed_active) if query_error_type is None and query_provider else []
    unknown_ids = sum(row["sandbox_id_sha256"] is None for row in attempts)
    inconclusive_cleanup = sum(row["sandbox_id_sha256"] is not None and row["is_running_after_kill"] is not False
                               for row in attempts)
    reserve = sum(row["lease_seconds"] for row in attempts) / 3600  # conservative $1/h.
    return {
        "schema": "cua-native-wdi-interrupted-sweep-reconciliation-v1",
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "run_journal_sha256": digest(journal_raw),
        "run_journal_status": journal["status"],
        "reason_for_interruption": "consecutive_pre_or_early_sandbox_ConnectError",
        "new_attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(Counter(row["status"] for row in attempts).items())),
        "error_type_counts": dict(sorted(Counter(row["error_type"] for row in attempts if row["error_type"]).items())),
        "attempts_without_sandbox_id_count": unknown_ids,
        "known_id_cleanup_inconclusive_count": inconclusive_cleanup,
        "known_active_matching_count": len(known_active),
        "account_running_total_at_query": account_running,
        "provider_list_error_type": query_error_type,
        "maximum_server_lease_plus_grace_utc": datetime.fromtimestamp(max_expiry+grace_seconds,timezone.utc).isoformat(),
        "all_unknown_leases_elapsed": matured,
        "max_resource_class_planning_usd_per_hour": 1.0,
        "conservative_attempted_lease_reserve_usd": round(reserve, 6),
        "actual_billed_usd": None,
        "ready_for_separate_health_probe": matured and query_provider and query_error_type is None and not known_active,
        "task_attempts_private": attempts,
        "note": "No task or model score is inferred from a ConnectError. Failed/uncertain receipts remain immutable and require controlled recovery after a separate health probe.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--grace-seconds", type=int, default=90)
    parser.add_argument("--query-provider", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite reconciliation evidence")
    result = reconcile(args.run_dir, args.attempts_root,
                       grace_seconds=args.grace_seconds,
                       query_provider=args.query_provider)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "new_attempt_count", "error_type_counts", "attempts_without_sandbox_id_count",
        "known_id_cleanup_inconclusive_count", "known_active_matching_count",
        "all_unknown_leases_elapsed", "ready_for_separate_health_probe",
        "conservative_attempted_lease_reserve_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
