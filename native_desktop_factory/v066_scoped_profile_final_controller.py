"""New scoped-profile 100×3 E2B Desktop evaluator-only controller.

Old22 and halted2 evidence remain in separate immutable roots. Before every
new intent, the source bridge projects all 324 ten-minute leases under the
existing $60 ceiling. Any failed/uncertain attempt stops scheduling. No model
or official final admission is produced here.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading

from . import admit
from .reconcile_interrupted_sweep import active_hashes
from .v066_final_freeze import (INITIAL_SANDBOX_COUNT, LEASE_SECONDS,
                                MAX_SANDBOX_COUNT, digest, intent_budget,
                                prepare_lane, validate_lane)
from .v066_storage_budget import audit as storage_audit
from .v066_scoped_profile_bridge import validate as validate_bridge
from .v066_profile_scope_three_root_budget import combined_budget
from .v066_scoped_profile_reference import validate_reference
from . import (v066_scoped_profile_final_attempt as scoped_attempt,
               v066_scoped_profile_guard as scoped_guard)


ATTEMPTS = ("positive", "near-miss", "cold-reset")
CHILD = "native_desktop_factory.v066_scoped_profile_final_attempt"


def _final_rows(candidate_root: Path) -> tuple[bytes, list[dict]]:
    raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(raw)
    rows = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    if (inventory.get("design_revision") != "v2-distinct-structures"
            or len(rows) != 100 or len({row["task_id"] for row in rows}) != 100
            or len({tuple(row["source_groups"]) for row in rows}) != 25):
        raise ValueError("The frozen 100-task/25-family Desktop inventory changed")
    for row in rows:
        admit._package(candidate_root, row)
    return raw, sorted(rows, key=lambda row: (row["source_groups"], row["workflow"]))


def _existing_state(attempts_root: Path, row: dict) -> str:
    directory = attempts_root / row["task_id"]
    if not directory.exists():
        return "fresh"
    if not directory.is_dir() or {path.name for path in directory.iterdir()} != set(ATTEMPTS):
        return "partial_or_unknown"
    receipts = []
    for name in ATTEMPTS:
        path = directory / name
        try:
            intent = json.loads((path / "intent.json").read_bytes())
            receipt = json.loads((path / "receipt.json").read_bytes())
        except (OSError, ValueError, json.JSONDecodeError):
            return "partial_or_unknown"
        if (intent.get("schema") != "cua-native-wdi-v066-final-control-intent-v1"
                or intent.get("task_id") != row["task_id"]
                or intent.get("attempt") != name
                or receipt.get("schema") != "cua-native-wdi-v066-gui-control-attempt-v1"
                or receipt.get("task_id") != row["task_id"]
                or receipt.get("attempt") != name
                or receipt.get("package_sha256") != row["package_sha256"]
                or receipt.get("guest_content_attested") is not True
                or receipt.get("task_profile_attested") is not True
                or receipt.get("task_profile_scoped_attested") is not True
                or receipt.get("runner_sha256") !=
                digest(Path(scoped_attempt.__file__).read_bytes())
                or receipt.get("profile_scope_guard_source_sha256") !=
                digest(Path(scoped_guard.__file__).read_bytes())
                or receipt.get("is_running_after_kill") is not False
                or receipt.get("status") != (
                    "cold_reset_observed" if name == "cold-reset" else "control_passed")):
            return "partial_or_unknown"
        receipts.append(receipt)
    if len({receipt["sandbox_id_sha256"] for receipt in receipts}) != 3:
        return "partial_or_unknown"
    return "completed_provisional"


def plan(candidate_root: Path, attempts_root: Path, *, task_cap: int) -> tuple[list[dict], dict]:
    if not 1 <= task_cap <= 100:
        raise ValueError("Prospective task cap must be 1–100")
    raw, rows = _final_rows(candidate_root)
    states = {row["task_id"]: _existing_state(attempts_root, row) for row in rows}
    if any(state == "partial_or_unknown" for state in states.values()):
        raise ValueError("A prior v0.6.6 attempt is partial or uncertain; reconcile before dispatch")
    selected = [row for row in rows if states[row["task_id"]] == "fresh"][:task_cap]
    summary = {
        "schema": "cua-native-wdi-v066-final-rerun-plan-v1",
        "candidate_inventory_sha256": digest(raw),
        "candidate_final_count": 100,
        "candidate_source_family_count": 25,
        "provisional_completed_trios": sum(state == "completed_provisional" for state in states.values()),
        "fresh_tasks_selected": len(selected),
        "new_sandboxes_planned": 3 * len(selected),
        "new_full_lease_reserve_usd": str(
            Decimal(3 * len(selected) * LEASE_SECONDS) / Decimal(3600)),
        "official_admitted_final_count": 0,
        "official_model_result_count": 0,
    }
    return selected, summary


def _run_one_task(row: dict, *, candidate_root: Path, attempts_root: Path,
                  private_map: Path, profile_private: Path, guest_public: Path,
                  fair_public: Path, ratification: Path, reservation: Path,
                  gate: dict[str, Path],
                  stop: threading.Event, intent_lock: threading.Lock) -> dict:
    result = {"private_task_id": row["task_id"], "attempts": []}
    for attempt in ATTEMPTS:
        if stop.is_set():
            result["status"] = "stopped_before_next_create"
            return result
        path = attempts_root / row["task_id"] / attempt
        with intent_lock:
            if stop.is_set():
                result["status"] = "stopped_before_next_create"
                return result
            validate_bridge(
                bridge_path=gate["bridge_path"],
                candidate_root=candidate_root,
                original_root=gate["original_root"],
                failed_root=gate["failed_root"],
                fresh_root=attempts_root,
                action_ratification=ratification,
                public_calibration=gate["public_calibration"],
                private_calibration_audit=gate["private_calibration_audit"],
                scoped_reference=gate["scoped_reference"],
                runtime_freeze=gate["runtime_freeze"],
                new_lane_reservation=reservation,
                failed_private_stop=gate["failed_private_stop"],
                failed_public_interruption=gate["failed_public_interruption"],
                profile_private=profile_private,
                guest_public=guest_public, fair_public=fair_public)
            combined_budget(
                original_root=gate["original_root"],
                failed_root=gate["failed_root"],
                future_root=attempts_root,
                proposed_future_intents=1)
            intent_budget(attempts_root, proposed_new=1)
            if not storage_audit(attempts_root)["dispatch_storage_ready"]:
                stop.set()
                result["status"] = "storage_budget_exhausted"
                return result
            if path.exists():
                stop.set()
                result["status"] = "existing_attempt_refused"
                return result
            path.mkdir(parents=True)
            attempts_root.chmod(0o700)
            path.parent.chmod(0o700)
            path.chmod(0o700)
            intent = {
                "schema": "cua-native-wdi-v066-final-control-intent-v1",
                "status": "recorded_before_provider_create",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "task_id": row["task_id"], "attempt": attempt,
                "package_sha256": row["package_sha256"],
                "lease_seconds": LEASE_SECONDS,
                "ratification_sha256": digest(ratification.read_bytes()),
                "reservation_sha256": digest(reservation.read_bytes()),
                "scoped_reference_sha256": digest(
                    gate["scoped_reference"].read_bytes()),
                "scoped_runtime_freeze_sha256": digest(
                    gate["runtime_freeze"].read_bytes()),
                "three_root_bridge_sha256": digest(
                    gate["bridge_path"].read_bytes()),
                "actual_provider_billed_usd": None,
            }
            intent_path = path / "intent.json"
            with intent_path.open("x") as stream:
                stream.write(json.dumps(intent, indent=2, sort_keys=True) + "\n")
            intent_path.chmod(0o600)
        cmd = [sys.executable, "-m", CHILD,
               "--candidate-root", str(candidate_root),
               "--attempts-root", str(attempts_root),
               "--task-id", row["task_id"], "--attempt", attempt,
               "--private-map", str(private_map),
               "--profile-private", str(profile_private),
               "--guest-public", str(guest_public),
               "--fair-public", str(fair_public),
               "--ratification", str(ratification),
               "--reservation", str(reservation),
               "--scoped-reference", str(gate["scoped_reference"]),
               "--runtime-freeze", str(gate["runtime_freeze"]),
               "--three-root-bridge", str(gate["bridge_path"]),
               "--original-root", str(gate["original_root"]),
               "--failed-root", str(gate["failed_root"]),
               "--public-calibration", str(gate["public_calibration"]),
               "--private-calibration-audit", str(
                   gate["private_calibration_audit"]),
               "--failed-private-stop", str(gate["failed_private_stop"]),
               "--failed-public-interruption", str(
                   gate["failed_public_interruption"]),
               "--enable-paid-scoped-final"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=LEASE_SECONDS + 120, check=False)
            receipt_path = path / "receipt.json"
            receipt = json.loads(receipt_path.read_bytes()) if receipt_path.is_file() else {}
            outcome = {"attempt": attempt,
                       "exit_code": proc.returncode,
                       "receipt_sha256": digest(receipt_path.read_bytes())
                       if receipt_path.is_file() else None,
                       "status": receipt.get("status", "missing_receipt"),
                       "error_type": receipt.get("error_type"),
                       "sandbox_id_observed": bool(receipt.get("sandbox_id_sha256")),
                       "cleanup_verified": receipt.get("is_running_after_kill") is False,
                       "stdout_sha256": digest(proc.stdout.encode()),
                       "stderr_sha256": digest(proc.stderr.encode())}
        except subprocess.TimeoutExpired:
            outcome = {"attempt": attempt, "status": "timeout_uncertain",
                       "sandbox_id_observed": False, "cleanup_verified": False}
        result["attempts"].append(outcome)
        expected = "cold_reset_observed" if attempt == "cold-reset" else "control_passed"
        if (outcome["status"] != expected
                or outcome.get("exit_code") != 0
                or not outcome["sandbox_id_observed"]
                or not outcome["cleanup_verified"]):
            stop.set()
            result["status"] = "stopped_after_invalid_or_uncertain_attempt"
            return result
    result["status"] = "provisional_trio_complete"
    return result


def execute(*, candidate_root: Path, attempts_root: Path, private_map: Path,
            profile_private: Path, guest_public: Path, fair_public: Path,
            ratification: Path, reservation: Path, run_dir: Path,
            gate: dict[str, Path],
            task_cap: int, concurrency: int,
            enable_paid_scoped_final: bool = False) -> dict:
    if enable_paid_scoped_final is not True:
        raise ValueError("Scoped full100 dispatch disabled before review")
    if run_dir.exists() or not 1 <= concurrency <= 2 or task_cap != 100:
        raise ValueError("New full100 private run and concurrency 1–2 required")
    if (attempts_root.name != "v066-final-gui" or
            not run_dir.resolve().is_relative_to(attempts_root.parent.resolve()) or
            run_dir.parent.name != "v066-rerun-runs"):
        raise ValueError("Private final evidence/run roots must stay in the WDI work lane")
    lane = validate_lane(ratification=ratification, reservation=reservation,
                         candidate_root=candidate_root, guest_public=guest_public,
                         profile_private=profile_private, fair_public=fair_public)
    validate_reference(gate["scoped_reference"])
    validate_bridge(
        bridge_path=gate["bridge_path"], candidate_root=candidate_root,
        original_root=gate["original_root"],
        failed_root=gate["failed_root"], fresh_root=attempts_root,
        action_ratification=ratification,
        public_calibration=gate["public_calibration"],
        private_calibration_audit=gate["private_calibration_audit"],
        scoped_reference=gate["scoped_reference"],
        runtime_freeze=gate["runtime_freeze"],
        new_lane_reservation=reservation,
        failed_private_stop=gate["failed_private_stop"],
        failed_public_interruption=gate["failed_public_interruption"],
        profile_private=profile_private,
        guest_public=guest_public, fair_public=fair_public)
    selected, plan_summary = plan(candidate_root, attempts_root, task_cap=task_cap)
    if not selected:
        raise ValueError("No untouched v0.6.6 final task needs evaluator controls")
    if (intent_budget(attempts_root, proposed_new=3 * len(selected))["combined_intents"] >
            lane["maximum_attempt_count_including_manual_recovery"]):
        raise ValueError("Separate $60 lane cannot reserve the selected control trios")
    storage = storage_audit(attempts_root)
    if not storage["dispatch_storage_ready"]:
        raise ValueError("Raw-frame storage cap or 8-GiB free-space floor blocks dispatch")
    try:
        import e2b_desktop  # noqa: F401 - require the child's SDK before any create intent.
    except ImportError:
        raise ValueError("The complete E2B Desktop SDK is unavailable in this runner") from None
    active, active_count = active_hashes()
    if active_count or active:
        raise ValueError("Provider has active E2B sandboxes; reconcile before dispatch")
    run_dir.mkdir(parents=True)
    run_dir.chmod(0o700)
    journal = {
        "schema": "cua-native-wdi-v066-final-rerun-private-v1",
        "status": "started", "created_utc": datetime.now(timezone.utc).isoformat(),
        "plan": plan_summary, "ratification_sha256": digest(ratification.read_bytes()),
        "reservation_sha256": digest(reservation.read_bytes()),
        "scoped_reference_sha256": digest(gate["scoped_reference"].read_bytes()),
        "scoped_runtime_freeze_sha256": digest(gate["runtime_freeze"].read_bytes()),
        "three_root_bridge_sha256": digest(gate["bridge_path"].read_bytes()),
        "selected_private_task_ids": [row["task_id"] for row in selected],
        "max_concurrency": concurrency,
        "provider_active_before": active_count,
        "evidence_bytes_reserved_before": storage["reserved_evidence_bytes"],
        "task_outcomes": [], "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }
    def persist():
        path = run_dir / "run-receipt.json"
        path.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)
    persist()
    stop = threading.Event()
    intent_lock = threading.Lock()
    futures = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for row in selected:
            futures.append(pool.submit(
                _run_one_task, row, candidate_root=candidate_root,
                attempts_root=attempts_root, private_map=private_map,
                profile_private=profile_private, guest_public=guest_public,
                fair_public=fair_public, ratification=ratification,
                reservation=reservation, gate=gate,
                stop=stop, intent_lock=intent_lock))
        for future in as_completed(futures):
            try:
                outcome = future.result()
            except Exception as exc:
                stop.set()
                outcome = {"status": "controller_worker_exception",
                           "error_type": type(exc).__name__}
            journal["task_outcomes"].append(outcome)
            persist()
    journal["status"] = ("stopped_for_reconciliation" if stop.is_set() else
                         "all_selected_trios_provisional")
    journal["completed_utc"] = datetime.now(timezone.utc).isoformat()
    journal["final_intent_budget"] = intent_budget(attempts_root)
    journal["final_storage_budget"] = storage_audit(attempts_root)
    persist()
    return journal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "prepare-lane", "execute"), required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--task-cap", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--private-map", type=Path)
    parser.add_argument("--profile-private", type=Path)
    parser.add_argument("--guest-public", type=Path)
    parser.add_argument("--fair-public", type=Path)
    parser.add_argument("--ratification", type=Path)
    parser.add_argument("--reservation", type=Path)
    parser.add_argument("--run-dir", type=Path)
    for field in ("scoped-reference", "runtime-freeze", "three-root-bridge",
                  "original-root", "failed-root", "public-calibration",
                  "private-calibration-audit", "failed-private-stop",
                  "failed-public-interruption"):
        parser.add_argument("--" + field, type=Path)
    parser.add_argument("--enable-paid-scoped-final", action="store_true")
    args = parser.parse_args()
    if args.mode == "plan":
        _selected, result = plan(args.candidate_root, args.attempts_root,
                                 task_cap=args.task_cap)
    else:
        required = (args.private_map, args.profile_private, args.guest_public,
                    args.fair_public, args.ratification, args.reservation)
        if any(value is None for value in required):
            raise ValueError("Freeze, lane, source and scorer paths are required")
        if args.mode == "prepare-lane":
            if args.attempts_root.exists() and any(args.attempts_root.glob("*/*/intent.json")):
                raise ValueError("Cannot record an initial lane after a final control intent")
            result = prepare_lane(
                ratification=args.ratification, reservation=args.reservation,
                candidate_root=args.candidate_root,
                guest_public=args.guest_public,
                profile_private=args.profile_private,
                fair_public=args.fair_public)
        else:
            gate = {
                "scoped_reference": args.scoped_reference,
                "runtime_freeze": args.runtime_freeze,
                "bridge_path": args.three_root_bridge,
                "original_root": args.original_root,
                "failed_root": args.failed_root,
                "public_calibration": args.public_calibration,
                "private_calibration_audit": args.private_calibration_audit,
                "failed_private_stop": args.failed_private_stop,
                "failed_public_interruption": args.failed_public_interruption,
            }
            if args.run_dir is None or any(value is None for value in gate.values()):
                raise ValueError("New private run and scoped source gate paths required")
            result = execute(
                candidate_root=args.candidate_root,
                attempts_root=args.attempts_root,
                private_map=args.private_map,
                profile_private=args.profile_private,
                guest_public=args.guest_public, fair_public=args.fair_public,
                ratification=args.ratification, reservation=args.reservation,
                run_dir=args.run_dir, gate=gate, task_cap=args.task_cap,
                concurrency=args.concurrency,
                enable_paid_scoped_final=args.enable_paid_scoped_final)
    safe = ({key: result[key] for key in (
        "candidate_final_count", "fresh_tasks_selected",
        "new_sandboxes_planned", "official_admitted_final_count")}
        if args.mode == "plan" else
        {"mode": args.mode, "status": result["status"],
         "official_final_admissions": 0})
    print(json.dumps(safe, sort_keys=True))
    if args.mode == "execute" and result["status"] != "all_selected_trios_provisional":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
