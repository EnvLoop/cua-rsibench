"""Run only archived pre-action transport failures after a healthy E2B probe."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

if __package__:
    from . import calibrate_sweep
else:
    import calibrate_sweep


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-ledger", type=Path, required=True)
    parser.add_argument("--health-probe", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--run-output", type=Path, required=True)
    parser.add_argument("--max-tasks", type=int, default=3)
    parser.add_argument("--max-new-sandboxes", type=int, default=9)
    parser.add_argument("--max-estimated-usd", type=Decimal, default=Decimal("0.75"))
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--max-wall-seconds", type=int, default=1800)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    ledger = json.loads(args.recovery_ledger.read_bytes())
    health_raw = args.health_probe.read_bytes()
    health = json.loads(health_raw)
    if ledger.get("status") != "archived_ready_for_one_controlled_retry_each":
        raise ValueError("Pre-action failures were not safely archived")
    if ledger.get("health_probe_sha256") != digest(health_raw) or health.get("ready_to_resume_paid_gui_dispatch") is not True:
        raise ValueError("Recovery ledger does not bind a healthy E2B probe")
    ids = {row["private_task_id"] for row in ledger["attempts"]}
    if len(ids) != len(ledger["attempts"]):
        raise ValueError("Multiple failed attempts in one task need manual review")
    result = calibrate_sweep.execute(
        args.candidate_root, args.attempts_root, args.run_output,
        max_tasks=args.max_tasks, max_new_sandboxes=args.max_new_sandboxes,
        lease_seconds=300, max_estimated_usd=args.max_estimated_usd,
        usd_per_hour_upper=Decimal("1.00"), concurrency=args.concurrency,
        max_wall_seconds=args.max_wall_seconds, dry_run=not args.execute,
        max_infrastructure_create_errors=2,
        health_probe=args.health_probe, only_task_ids=ids)
    print(json.dumps({"status": result["status"],
                      "planned_task_count": result["planned_task_count"],
                      "started_attempts": result["actual_started_attempts"],
                      "gui_control_passed_tasks": sum(x.get("status") == "gui_controls_passed" for x in result["results"]),
                      "circuit_breaker": result.get("circuit_breaker")}, sort_keys=True))


if __name__ == "__main__":
    main()
