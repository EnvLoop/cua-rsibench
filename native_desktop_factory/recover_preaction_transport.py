"""Archive pre-action ConnectErrors for one controlled, hash-bound retry.

Only after the interrupted run's lease reconciliation and a separate healthy
E2B create/probe may its original failed attempt directory be moved into an
immutable archive. No sandbox is created here; the next sweep writes a new
canonical attempt while the original remains inspectable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plan(reconciliation: Path, health_probe: Path, attempts_root: Path) -> list[dict]:
    recon_raw = reconciliation.read_bytes()
    health_raw = health_probe.read_bytes()
    recon, health = json.loads(recon_raw), json.loads(health_raw)
    if recon.get("ready_for_separate_health_probe") is not True:
        raise ValueError("Uncertain no-ID/cleanup leases not reconciled")
    if health.get("ready_to_resume_paid_gui_dispatch") is not True or health.get("reconciliation_sha256") != digest(recon_raw):
        raise ValueError("Separate E2B health probe absent or did not bind reconciliation")
    rows = []
    for record in recon["task_attempts_private"]:
        if record.get("error_type") != "ConnectError":
            continue
        task_id, attempt = record["private_task_id"], record["attempt"]
        original = attempts_root / task_id / attempt
        receipt_path = original / "receipt.json"
        raw = receipt_path.read_bytes()
        receipt = json.loads(raw)
        if digest(raw) != record["receipt_sha256"] or receipt.get("error_type") != "ConnectError":
            raise ValueError("Original transport receipt changed")
        if receipt.get("actor_actions") or receipt.get("staged_sha256") or receipt.get("saved_sha256"):
            raise ValueError("Transport failure occurred after actor/staging; manual review required")
        if receipt.get("status") not in ("error", "cleanup_unverified"):
            raise ValueError("Only failed pre-action attempts may be recovered")
        archive = attempts_root / task_id / "_infrastructure_invalid" / (attempt + "-" + digest(raw)[:12])
        if archive.exists():
            raise ValueError("Archived failed attempt already exists")
        rows.append({"task_id": task_id, "attempt": attempt,
                     "original": original, "archive": archive,
                     "receipt_sha256": digest(raw),
                     "sandbox_id_sha256": receipt.get("sandbox_id_sha256"),
                     "status": receipt["status"]})
    if not rows:
        raise ValueError("No reconciled pre-action transport failures to recover")
    return rows


def apply(rows: list[dict], output: Path, reconciliation: Path, health_probe: Path) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite recovery ledger")
    output.parent.mkdir(parents=True, exist_ok=True)
    ledger = {"schema": "cua-native-wdi-controlled-preaction-recovery-v1",
              "status": "started", "reconciliation_sha256": digest(reconciliation.read_bytes()),
              "health_probe_sha256": digest(health_probe.read_bytes()),
              "attempts": []}
    for row in rows:
        row["archive"].parent.mkdir(parents=True, exist_ok=True)
        row["original"].rename(row["archive"])
        if digest((row["archive"] / "receipt.json").read_bytes()) != row["receipt_sha256"]:
            ledger["status"] = "archive_hash_mismatch"
            break
        ledger["attempts"].append({
            "private_task_id": row["task_id"], "attempt": row["attempt"],
            "original_receipt_sha256": row["receipt_sha256"],
            "archive_relative": row["archive"].relative_to(row["original"].parents[1]).as_posix(),
            "sandbox_id_sha256": row["sandbox_id_sha256"],
            "original_status": row["status"],
            "recovery_status": "archived_preaction_transport_failure_no_new_sandbox_yet",
        })
        output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    if ledger["status"] == "started":
        ledger["status"] = "archived_ready_for_one_controlled_retry_each"
    output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--health-probe", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = plan(args.reconciliation, args.health_probe, args.attempts_root)
    if args.apply:
        result = apply(rows, args.out, args.reconciliation, args.health_probe)
        print(json.dumps({"status": result["status"], "archived": len(result["attempts"]),
                          "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))
    else:
        print(json.dumps({"dry_run": True, "recoverable_preaction_attempts": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
