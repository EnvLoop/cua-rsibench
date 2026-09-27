"""Bounded, resumable evaluator-only final Desktop profile-baseline sweep.

It never samples a model or exposes a final oracle. Existing failed receipts
are preserved and are not automatically retried. A provider transport circuit
breaker stops new dispatch after repeated create failures.
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

if __package__:
    from .budget_ledger import audit as audit_budget
    from .profile_baseline_one import preflight
else:
    from budget_ledger import audit as audit_budget
    from profile_baseline_one import preflight


RUN_ID = re.compile(r"[a-z][a-z0-9-]{2,40}\Z")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inventory_and_existing(candidate_root: Path, work_root: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    if inventory.get("design_revision") != "v2-distinct-structures":
        raise ValueError("Expected v2 distinct-structure native inventory")
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    if len(final) != 100 or len({row["task_id"] for row in final}) != 100:
        raise ValueError("Expected 100 unique private final candidates")
    by_id = {row["task_id"]: [] for row in final}
    for path in sorted((work_root / "gui-diagnostics").glob("profile-baseline-*/receipt.json")):
        raw = path.read_bytes()
        receipt = json.loads(raw)
        task_id = receipt.get("task_id")
        if receipt.get("schema") != "cua-native-wdi-profile-baseline-v1" or task_id not in by_id:
            raise ValueError("Unknown or malformed existing profile baseline")
        by_id[task_id].append({"receipt": receipt, "receipt_sha256": digest(raw),
                               "path": str(path)})
    return final, by_id


def plan(candidate_root: Path, work_root: Path, *, max_new_sandboxes: int) -> tuple[list[dict], list[dict]]:
    final, existing = inventory_and_existing(candidate_root, work_root)
    selected, deferred = [], []
    for row in sorted(final, key=lambda item: (item["source_groups"], item["workflow"])):
        package_dir = candidate_root / "final_candidate" / row["task_id"]
        preflight(package_dir, candidate_root)
        attempts = existing[row["task_id"]]
        passed = [item for item in attempts if item["receipt"].get("status") == "profile_baseline_passed"
                  and item["receipt"].get("is_running_after_kill") is False]
        if passed:
            if len({item["receipt"].get("canonical_profile_sha256") for item in passed}) != 1:
                raise ValueError("Existing passed profile baselines disagree for one task")
            deferred.append({"task_id": row["task_id"], "reason": "already_passed"})
        elif attempts:
            deferred.append({"task_id": row["task_id"],
                             "reason": "existing_failed_or_uncertain_requires_reconciliation"})
        elif len(selected) >= max_new_sandboxes:
            deferred.append({"task_id": row["task_id"], "reason": "sandbox_cap"})
        else:
            selected.append(row)
    return selected, deferred


def run_one(candidate_root: Path, work_root: Path, runtime_manifest: Path,
            row: dict, *, ordinal: int, run_id: str, lease_seconds: int,
            lane_cap: Decimal) -> dict:
    output = work_root / "gui-diagnostics" / f"profile-baseline-{run_id}-{ordinal:03d}"
    cmd = [sys.executable, "-m", "native_desktop_factory.profile_baseline_one",
           "--candidate-root", str(candidate_root),
           "--package", str(candidate_root / "final_candidate" / row["task_id"]),
           "--out-dir", str(output), "--work-root", str(work_root),
           "--expected-runtime-manifest", str(runtime_manifest),
           "--lease-seconds", str(lease_seconds),
           "--max-lane-reserved-usd", str(lane_cap)]
    started = time.monotonic()
    try:
        process = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=lease_seconds + 90, check=False)
        path = output / "receipt.json"
        receipt = json.loads(path.read_bytes()) if path.is_file() else {}
        valid = (process.returncode == 0
                 and receipt.get("status") == "profile_baseline_passed"
                 and receipt.get("task_id") == row["task_id"]
                 and receipt.get("input_sha256") == row["input_sha256"]
                 and receipt.get("is_running_after_kill") is False)
        return {"task_id": row["task_id"], "workflow": row["workflow"],
                "status": "passed" if valid else "failed_or_uncertain",
                "exit_code": process.returncode,
                "child_status": receipt.get("status"),
                "child_error_type": receipt.get("error_type"),
                "sandbox_acknowledged": bool(receipt.get("sandbox_id_sha256")),
                "receipt_sha256": digest(path.read_bytes()) if path.is_file() else None,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "stdout_sha256": digest(process.stdout.encode()),
                "stderr_sha256": digest(process.stderr.encode())}
    except subprocess.TimeoutExpired:
        return {"task_id": row["task_id"], "workflow": row["workflow"],
                "status": "timeout_uncertain", "elapsed_seconds": round(time.monotonic() - started, 3),
                "server_lease_seconds": lease_seconds}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--expected-runtime-manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-new-sandboxes", type=int, required=True)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--lease-seconds", type=int, default=120)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal, default=Decimal("40"))
    args = parser.parse_args()
    if (not RUN_ID.fullmatch(args.run_id)
            or not 1 <= args.max_new_sandboxes <= 100
            or not 1 <= args.concurrency <= 3
            or not 120 <= args.lease_seconds <= 600):
        raise ValueError("Profile sweep ID or resource envelope is invalid")
    candidate_root, work_root = args.candidate_root.resolve(), args.work_root.resolve()
    runtime_manifest = args.expected_runtime_manifest.resolve()
    run_dir = work_root / "profile-sweep-runs" / args.run_id
    if run_dir.exists():
        raise ValueError("Refusing to overwrite profile sweep journal")
    selected, deferred = plan(candidate_root, work_root,
                              max_new_sandboxes=args.max_new_sandboxes)
    budget = audit_budget(work_root, proposed_new_sandboxes=len(selected),
                          proposed_lease_seconds=args.lease_seconds,
                          max_lane_reserved_usd=args.max_lane_reserved_usd)
    if not budget["within_cap"]:
        raise ValueError("Whole profile sweep exceeds native lane cap")
    run_dir.mkdir(parents=True)
    journal = {
        "schema": "cua-native-wdi-profile-baseline-sweep-v1",
        "status": "started", "started_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_inventory_sha256": digest((candidate_root / "candidate-inventory.json").read_bytes()),
        "runtime_manifest_sha256": digest(runtime_manifest.read_bytes()),
        "lease_seconds": args.lease_seconds, "concurrency": args.concurrency,
        "planned_new_sandbox_count": len(selected),
        "planned_full_lease_reserve_usd": budget["proposed_reserved_usd"],
        "combined_lane_reserve_if_all_attempted_usd": budget["combined_reserved_usd"],
        "lane_cap_usd": budget["lane_usd_cap"],
        "deferred": deferred, "attempts": [],
    }

    def persist():
        (run_dir / "run-receipt.json").write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n")

    persist()
    submitted, transport_streak, circuit_open = 0, 0, False
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {}

        def submit_next():
            nonlocal submitted
            if submitted >= len(selected) or circuit_open:
                return
            ordinal = submitted + 1
            row = selected[submitted]
            future = pool.submit(run_one, candidate_root, work_root,
                                 runtime_manifest, row, ordinal=ordinal,
                                 run_id=args.run_id, lease_seconds=args.lease_seconds,
                                 lane_cap=args.max_lane_reserved_usd)
            futures[future] = row
            submitted += 1

        for _ in range(min(args.concurrency, len(selected))):
            submit_next()
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                futures.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"status": "runner_exception", "error_type": type(exc).__name__}
                journal["attempts"].append(result)
                if (result["status"] == "failed_or_uncertain"
                        and result.get("child_error_type") in ("ConnectError", "TransportError")
                        and not result.get("sandbox_acknowledged")):
                    transport_streak += 1
                elif result["status"] == "passed":
                    transport_streak = 0
                if result["status"] in ("timeout_uncertain", "runner_exception") or transport_streak >= 3:
                    circuit_open = True
                persist()
                if len(journal["attempts"]) % 10 == 0 or result["status"] != "passed":
                    print(json.dumps({"completed": len(journal["attempts"]),
                                      "passed": sum(item["status"] == "passed" for item in journal["attempts"]),
                                      "failures": sum(item["status"] != "passed" for item in journal["attempts"]),
                                      "circuit_open": circuit_open}), flush=True)
                submit_next()
    journal["finished_utc"] = datetime.now(timezone.utc).isoformat()
    journal["not_dispatched_due_circuit"] = len(selected) - submitted
    final_after, existing_after = inventory_and_existing(candidate_root, work_root)
    journal["final_profile_baseline_pass_count"] = sum(
        any(item["receipt"].get("status") == "profile_baseline_passed"
            and item["receipt"].get("is_running_after_kill") is False
            for item in existing_after[row["task_id"]])
        for row in final_after)
    journal["status"] = ("circuit_open" if circuit_open else
                         "finished_complete" if journal["final_profile_baseline_pass_count"] == 100
                         and all(item["status"] == "passed" for item in journal["attempts"])
                         else "finished_incomplete")
    persist()
    print(json.dumps({"status": journal["status"],
                      "attempted": len(journal["attempts"]),
                      "passed": sum(item["status"] == "passed" for item in journal["attempts"]),
                      "final_profile_baseline_pass_count": journal["final_profile_baseline_pass_count"],
                      "deferred": len(deferred),
                      "journal_sha256": digest((run_dir / "run-receipt.json").read_bytes())},
                     sort_keys=True), flush=True)
    return 0 if journal["status"] == "finished_complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
