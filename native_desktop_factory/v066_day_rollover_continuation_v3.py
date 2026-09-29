"""Source-frozen, durable, bounded Desktop continuation for untouched IDs.

The original 35-file paid evaluator remains byte-identical. This additive
controller fsyncs every four-root budget and create intent before dispatching
an unchanged evaluator through a receipt-fsync adapter. It never retries the
two quarantined IDs or dispatches a model.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading

from . import v066_day_rollover_continuation_v2 as base
from .reconcile_interrupted_sweep import active_hashes
from .v066_day_rollover_bridge import combined_budget
from .v066_final_freeze import LEASE_SECONDS, digest, intent_budget
from .v066_scoped_profile_bridge import validate as validate_bridge
from .v066_storage_budget import audit as storage_audit


SCHEMA = "cua-native-wdi-v066-durable-continuation-freeze-private-v3"
PUBLIC_SCHEMA = "cua-native-wdi-v066-durable-continuation-freeze-public-v3"
RUN_SCHEMA = "cua-native-wdi-v066-durable-continuation-run-private-v3"
CHILD = "native_desktop_factory.v066_day_rollover_durable_child_v3"
ATTEMPTS = ("positive", "near-miss", "cold-reset")
SDK_VERSIONS = {"e2b-desktop": "2.2.0", "e2b": "2.51.0",
                "Pillow": "11.3.0"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path: Path, value: dict, *, public: bool = False) -> str:
    raw = (json.dumps(value, sort_keys=True,
                      indent=2 if public else None,
                      separators=None if public else (",", ":")) + "\n").encode()
    parent_existed = path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not public:
        path.parent.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o644 if public else 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_dir(path.parent)
    if not parent_existed:
        _sync_dir(path.parent.parent)
    return digest(raw)


def _private_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and not path.stat().st_mode & 0o077


def _power_snapshot() -> dict:
    observed = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                              text=True, timeout=5, check=True).stdout
    source = re.search(r"Now drawing from '([^']+)'", observed)
    battery = re.search(r"\b(\d{1,3})%;", observed)
    if not source or source.group(1) not in {"AC Power", "Battery Power"}:
        raise ValueError("Host power source was not observable before E2B intent")
    percent = int(battery.group(1)) if battery else None
    if percent is not None and percent > 100:
        raise ValueError("Invalid host battery telemetry")
    return {"observed_utc": _now(), "source": source.group(1),
            "battery_percent": percent}


def _sdk_and_credential() -> dict[str, str]:
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential absent before new intent")
    try:
        import e2b_desktop  # noqa: F401
        versions = {name: importlib.metadata.version(name)
                    for name in SDK_VERSIONS}
    except (ImportError, importlib.metadata.PackageNotFoundError):
        raise ValueError("Dedicated Desktop SDK runtime absent before new intent") from None
    if versions != SDK_VERSIONS:
        raise ValueError("Dedicated Desktop SDK versions changed before new intent")
    return versions


def _sources() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[1]
    names = (
        "native_desktop_factory/v066_day_rollover_continuation_v3.py",
        "native_desktop_factory/v066_day_rollover_durable_child_v3.py",
        "native_desktop_factory/v066_day_rollover_durable_audit_v3.py",
        "native_desktop_factory/v066_day_rollover_continuation_v2.py",
    )
    return {name: digest((repo / name).read_bytes()) for name in names}


def _verify_base_public(base_freeze: Path) -> str:
    repo = Path(__file__).resolve().parents[1]
    public_path = (repo / "docs/evidence/"
                   "native-wdi-v066-bounded-continuation-freeze-v2-2026-09-29.json")
    public = json.loads(public_path.read_bytes())
    raw = base_freeze.read_bytes()
    private = json.loads(raw)
    if (public.get("schema") !=
            "cua-native-wdi-v066-bounded-continuation-freeze-public-v2" or
            public.get("private_freeze_sha256") != digest(raw) or
            len(private.get("frozen_full100_source_sha256s", {})) != 35):
        raise ValueError("Published v2 freeze or 35-file evaluator binding changed")
    return digest(raw)


def prepare(*, base_freeze: Path, freeze: Path, public: Path) -> dict:
    if freeze.exists() or public.exists():
        raise ValueError("New exclusive v3 freeze paths required")
    base_sha = _verify_base_public(base_freeze)
    prior, progress, paths, _rows = base.validate_live(freeze_path=base_freeze)
    if (progress["independently_accepted_complete_trios"] != 7 or
            progress["quarantined_incomplete_task_ids"] != 2 or
            progress["untouched_task_ids"] != 91):
        raise ValueError("v3 source freeze must precede the first new create")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before v3 source freeze")
    from .v066_day_rollover_durable_audit_v3 import audit as audit_durable
    audit_durable(attempts_root=paths["attempts_root"], roster=_rows,
                  initial_accepted=7, prior_intents=24,
                  wrapper_sha=_sources()[
                      "native_desktop_factory/v066_day_rollover_durable_child_v3.py"])
    private = {
        "schema": SCHEMA,
        "status": "frozen_before_durable_untouched_continuation",
        "recorded_utc": _now(),
        "base_freeze_path": str(base_freeze.resolve()),
        "base_freeze_sha256": base_sha,
        "public_path": str(public.resolve()),
        "source_sha256s": _sources(),
        "initial_complete_trios": 7,
        "initial_quarantined_ids": 2,
        "untouched_ids": 91,
        "initial_all_root_full_lease_intents": 50,
        "projected_all_root_full_lease_intents": 323,
        "projected_all_root_reserved_usd": prior[
            "projected_all_root_reserved_usd"],
        "same_id_retry_authorized": False,
        "official_final_admissions": 0,
        "actual_provider_billed_usd": None,
    }
    freeze_sha = _write_new(freeze, private)
    aggregate = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_before_any_new_durable_untouched_create",
        "private_freeze_sha256": freeze_sha,
        "source_sha256s": private["source_sha256s"],
        "previous_v2_freeze_sha256": private["base_freeze_sha256"],
        "initial_complete_gui_trios_independently_audited": 7,
        "quarantined_incomplete_task_ids": 2,
        "untouched_task_ids": 91,
        "projected_all_root_full_lease_intents": 323,
        "projected_all_root_reserved_usd":
            private["projected_all_root_reserved_usd"],
        "per_attempt_budget_intent_receipt_fsync": True,
        "power_observed_before_each_new_intent": True,
        "same_id_retry_authorized": False,
        "official_final_admissions": 0,
        "actual_provider_billed_usd": None,
    }
    _write_new(public, aggregate, public=True)
    return aggregate


def validate_live(*, freeze: Path, active_run_dir: Path | None = None
                  ) -> tuple[dict, dict, dict, list[dict]]:
    if not _private_file(freeze):
        raise ValueError("Private v3 freeze absent")
    raw = freeze.read_bytes()
    frozen = json.loads(raw)
    if (frozen.get("schema") != SCHEMA or frozen.get("status") !=
            "frozen_before_durable_untouched_continuation" or
            frozen.get("source_sha256s") != _sources() or
            frozen.get("same_id_retry_authorized") is not False or
            frozen.get("official_final_admissions") != 0):
        raise ValueError("v3 continuation source or authorization changed")
    public = Path(frozen["public_path"])
    aggregate = json.loads(public.read_bytes())
    if (aggregate.get("schema") != PUBLIC_SCHEMA or
            aggregate.get("private_freeze_sha256") != digest(raw) or
            aggregate.get("source_sha256s") != frozen["source_sha256s"]):
        raise ValueError("Published v3 source freeze no longer binds private bytes")
    base_freeze = Path(frozen["base_freeze_path"])
    if (_verify_base_public(base_freeze) != frozen["base_freeze_sha256"]):
        raise ValueError("Preserved v2 freeze changed")
    prior, progress, paths, rows = base.validate_live(freeze_path=base_freeze)
    from .v066_day_rollover_durable_audit_v3 import audit as audit_durable
    audit_durable(
        attempts_root=paths["attempts_root"], roster=rows,
        initial_accepted=progress["independently_accepted_complete_trios"],
        prior_intents=24,
        wrapper_sha=frozen["source_sha256s"][
            "native_desktop_factory/v066_day_rollover_durable_child_v3.py"])
    run_root = paths["attempts_root"].parent / "v066-durable-continuation-runs"
    for receipt_path in run_root.glob("*/run-receipt.json"):
        receipt = json.loads(receipt_path.read_bytes())
        allowed = receipt.get("status") == "bounded_completed_and_audited" or (
            active_run_dir is not None and
            receipt_path.parent == active_run_dir and
            receipt.get("status") == "started")
        if (receipt.get("schema") != RUN_SCHEMA or not allowed or
                receipt.get("freeze_sha256") != digest(raw) or
                receipt.get("official_final_admissions") != 0):
            raise ValueError("A v3 continuation batch is unfinished or changed")
    return frozen, progress, paths, rows


def _terminate_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _invoke_child(command: list[str]) -> tuple[int | None, str, str, bool]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=LEASE_SECONDS + 120)
        return process.returncode, stdout, stderr, False
    except subprocess.TimeoutExpired:
        _terminate_group(process)
        return None, "", "", True
    except BaseException:
        _terminate_group(process)
        raise


def _task(*, row: dict, paths: dict[str, Path], gate: dict[str, Path],
          wrapper_sha: str, stop: threading.Event) -> dict:
    result = {"private_task_id": row["task_id"], "attempts": []}
    for attempt in ATTEMPTS:
        if stop.is_set():
            result["status"] = "stopped_before_next_create"
            return result
        _sdk_and_credential()
        power = _power_snapshot()
        active, count = active_hashes()
        if active or count:
            result["status"] = "stopped_for_provider_cleanup_audit"
            return result
        validate_bridge(
            bridge_path=gate["bridge_path"],
            candidate_root=paths["candidate_root"],
            original_root=gate["original_root"],
            failed_root=gate["failed_root"],
            fresh_root=paths["attempts_root"],
            action_ratification=paths["action_ratification"],
            public_calibration=gate["public_calibration"],
            private_calibration_audit=gate["private_calibration_audit"],
            scoped_reference=gate["scoped_reference"],
            runtime_freeze=gate["runtime_freeze"],
            new_lane_reservation=paths["reservation"],
            failed_private_stop=gate["failed_private_stop"],
            failed_public_interruption=gate["failed_public_interruption"],
            profile_private=paths["profile_private"],
            guest_public=paths["guest_public"],
            fair_public=paths["fair_public"])
        budget = combined_budget(
            original_root=paths["old_original_root"],
            failed_root=paths["old_caret_root"],
            failed_scoped_root=paths["old_failed_scoped_root"],
            fresh_root=paths["attempts_root"],
            proposed_fresh_intents=1)
        lane_budget = intent_budget(paths["attempts_root"], proposed_new=1)
        storage = storage_audit(paths["attempts_root"])
        if not storage["dispatch_storage_ready"]:
            result["status"] = "storage_budget_exhausted"
            return result
        path = paths["attempts_root"] / row["task_id"] / attempt
        if path.exists():
            result["status"] = "existing_attempt_refused"
            return result
        path.mkdir(parents=True)
        path.parent.chmod(0o700)
        path.chmod(0o700)
        _sync_dir(path.parent)
        _sync_dir(paths["attempts_root"])
        budget_receipt = {
            "schema": "cua-native-wdi-v066-precreate-budget-private-v3",
            "status": "fsynced_before_provider_create",
            "created_utc": _now(),
            "task_id": row["task_id"], "attempt": attempt,
            "four_root_budget": budget,
            "fresh_lane_budget": lane_budget,
            "storage_dispatch_ready": True,
            "sdk_versions": SDK_VERSIONS,
            "credential_present": True,
            "power": power,
            "provider_active_before_intent": 0,
            "actual_provider_billed_usd": None,
        }
        budget_sha = _write_new(path / "budget.json", budget_receipt)
        intent = {
            "schema": "cua-native-wdi-v066-final-control-intent-v1",
            "status": "recorded_before_provider_create",
            "created_utc": _now(),
            "task_id": row["task_id"], "attempt": attempt,
            "package_sha256": row["package_sha256"],
            "lease_seconds": LEASE_SECONDS,
            "ratification_sha256": digest(paths["action_ratification"].read_bytes()),
            "reservation_sha256": digest(paths["reservation"].read_bytes()),
            "scoped_reference_sha256": digest(gate["scoped_reference"].read_bytes()),
            "scoped_runtime_freeze_sha256": digest(gate["runtime_freeze"].read_bytes()),
            "three_root_bridge_sha256": digest(gate["bridge_path"].read_bytes()),
            "precreate_budget_sha256": budget_sha,
            "durable_child_wrapper_sha256": wrapper_sha,
            "actual_provider_billed_usd": None,
        }
        intent_sha = _write_new(path / "intent.json", intent)
        command = [sys.executable, "-m", CHILD,
                   "--candidate-root", str(paths["candidate_root"]),
                   "--attempts-root", str(paths["attempts_root"]),
                   "--task-id", row["task_id"], "--attempt", attempt,
                   "--private-map", str(paths["private_map"]),
                   "--profile-private", str(paths["profile_private"]),
                   "--guest-public", str(paths["guest_public"]),
                   "--fair-public", str(paths["fair_public"]),
                   "--ratification", str(paths["action_ratification"]),
                   "--reservation", str(paths["reservation"]),
                   "--scoped-reference", str(gate["scoped_reference"]),
                   "--runtime-freeze", str(gate["runtime_freeze"]),
                   "--three-root-bridge", str(gate["bridge_path"]),
                   "--original-root", str(gate["original_root"]),
                   "--failed-root", str(gate["failed_root"]),
                   "--public-calibration", str(gate["public_calibration"]),
                   "--private-calibration-audit",
                   str(gate["private_calibration_audit"]),
                   "--failed-private-stop", str(gate["failed_private_stop"]),
                   "--failed-public-interruption",
                   str(gate["failed_public_interruption"]),
                   "--enable-paid-scoped-final"]
        code, stdout, stderr, timed_out = _invoke_child(command)
        receipt_path = path / "receipt.json"
        receipt_raw = receipt_path.read_bytes() if receipt_path.is_file() else None
        try:
            receipt = json.loads(receipt_raw) if receipt_raw is not None else {}
        except (ValueError, TypeError):
            receipt = {}
        outcome = {
            "attempt": attempt, "exit_code": code,
            "intent_sha256": intent_sha,
            "budget_sha256": budget_sha,
            "receipt_sha256": digest(receipt_raw) if receipt_raw else None,
            "status": "timeout_uncertain" if timed_out else
                receipt.get("status", "missing_or_invalid_receipt"),
            "error_type": receipt.get("error_type"),
            "sandbox_id_observed": bool(receipt.get("sandbox_id_sha256")),
            "cleanup_verified": receipt.get("is_running_after_kill") is False,
            "stdout_sha256": digest(stdout.encode()),
            "stderr_sha256": digest(stderr.encode()),
            "child_process_exited": True,
        }
        result["attempts"].append(outcome)
        expected = "cold_reset_observed" if attempt == "cold-reset" else "control_passed"
        if (outcome["status"] != expected or code != 0 or
                not outcome["sandbox_id_observed"] or
                not outcome["cleanup_verified"]):
            stop.set()
            result["status"] = "stopped_after_invalid_or_uncertain_attempt"
            return result
    result["status"] = "provisional_trio_complete"
    return result


class _Interrupted(Exception):
    pass


def _on_term(_signum, _frame) -> None:
    raise _Interrupted("root process received termination signal")


def run_batch(*, freeze: Path, run_dir: Path,
              max_new_ids: int, execute: bool = False) -> dict:
    frozen, progress, paths, rows = validate_live(freeze=freeze)
    if not 1 <= max_new_ids <= 2:
        raise ValueError("One or two untouched IDs per root-owned batch required")
    eligible = [row for index, row in enumerate(rows)
                if index >= 9 and not
                (paths["attempts_root"] / row["task_id"]).exists()]
    selected = eligible[:max_new_ids]
    if not selected:
        return {"status": "all_91_untouched_id_trios_audited",
                "new_ids_selected": 0,
                "independently_accepted_complete_trios":
                    progress["independently_accepted_complete_trios"],
                "official_final_admissions": 0}
    combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"],
        proposed_fresh_intents=3 * len(selected))
    if not execute:
        return {"status": "offline_bounded_durable_continuation_plan",
                "new_ids_selected": len(selected),
                "existing_independently_accepted_trios":
                    progress["independently_accepted_complete_trios"],
                "official_final_admissions": 0}
    expected_parent = paths["attempts_root"].parent / "v066-durable-continuation-runs"
    if run_dir.exists() or run_dir.parent != expected_parent:
        raise ValueError("New private v3 bounded run directory required")
    _sdk_and_credential()
    _power_snapshot()
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero before bounded v3 batch")
    run_dir.mkdir(parents=True, mode=0o700)
    run_dir.chmod(0o700)
    _sync_dir(run_dir.parent)
    _sync_dir(run_dir.parent.parent)
    journal = {
        "schema": RUN_SCHEMA, "status": "started",
        "created_utc": _now(),
        "freeze_sha256": digest(freeze.read_bytes()),
        "selected_private_task_ids": [row["task_id"] for row in selected],
        "existing_complete_trios_before":
            progress["independently_accepted_complete_trios"],
        "task_outcomes": [], "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }
    journal_path = run_dir / "run-receipt.json"
    _write_new(journal_path, journal)
    gate = {
        "bridge_path": paths["bridge_path"],
        "original_root": paths["old_original_root"],
        "failed_root": paths["old_caret_root"],
        "public_calibration": paths["public_day_audit"],
        "private_calibration_audit": paths["private_day_audit"],
        "scoped_reference": paths["reference_path"],
        "runtime_freeze": paths["runtime_freeze"],
        "failed_private_stop": paths["failed_private_stop"],
        "failed_public_interruption": paths["failed_public_interruption"],
    }
    stop = threading.Event()
    old_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _on_term)
    try:
        for row in selected:
            outcome = _task(
                row=row, paths=paths, gate=gate,
                wrapper_sha=frozen["source_sha256s"][
                    "native_desktop_factory/v066_day_rollover_durable_child_v3.py"],
                stop=stop)
            journal["task_outcomes"].append(outcome)
            base._persist(journal_path, journal)
            if outcome.get("status") != "provisional_trio_complete":
                journal["status"] = "stopped_for_reconciliation"
                break
            active, count = active_hashes()
            if active or count:
                journal["status"] = "stopped_for_provider_cleanup_audit"
                break
            try:
                _freeze, current, _paths, _rows = validate_live(
                    freeze=freeze, active_run_dir=run_dir)
                expected_count = (journal["existing_complete_trios_before"] +
                                  len(journal["task_outcomes"]))
                if current["independently_accepted_complete_trios"] != expected_count:
                    raise ValueError("Independent audit did not accept the just-run ID")
                journal["independently_accepted_complete_trios_after"] = current[
                    "independently_accepted_complete_trios"]
                base._persist(journal_path, journal)
            except Exception as exc:
                journal["status"] = "stopped_after_independent_audit_failure"
                journal["audit_error_type"] = type(exc).__name__
                break
        else:
            journal["status"] = "bounded_completed_and_audited"
    except BaseException as exc:
        journal["status"] = "stopped_after_root_interruption"
        journal["interruption_type"] = type(exc).__name__
        journal["completed_utc"] = _now()
        base._persist(journal_path, journal)
        raise
    finally:
        signal.signal(signal.SIGTERM, old_term)
    journal["completed_utc"] = _now()
    base._persist(journal_path, journal)
    return {"status": journal["status"],
            "new_ids_selected": len(selected),
            "new_complete_trios": sum(
                row.get("status") == "provisional_trio_complete"
                for row in journal["task_outcomes"]),
            "official_final_admissions": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "plan", "run"))
    parser.add_argument("--base-freeze", type=Path)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--max-new-ids", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.base_freeze is None or args.public is None:
            raise ValueError("Preserved v2 private freeze and new v3 public path required")
        result = prepare(base_freeze=args.base_freeze, freeze=args.freeze,
                         public=args.public)
    else:
        result = run_batch(
            freeze=args.freeze, run_dir=args.run_dir or Path("unused"),
            max_new_ids=args.max_new_ids,
            execute=args.mode == "run" and args.execute)
    print(json.dumps(result, sort_keys=True))
    if result.get("status", "").startswith("stopped_"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
