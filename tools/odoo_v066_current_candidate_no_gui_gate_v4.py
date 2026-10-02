"""Dated Odoo selection baseline gate with bounded database readiness.

The gate independently re-audits all three failed GUI controls, acquires the
original selection worker lease, waits for the PostgreSQL health probe and a
read-only verifier connection, then reads current SQL and every physical
filestore entry. It restores the stopped service state before writing any
owner-only receipt. A passing receipt cannot authorize a GUI or campaign.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time

from tools import audit_odoo_v066_current_candidate_epoch_v1 as plan_audit
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_db_readiness_source_v4 as amendment
from tools import odoo_v066_retained_lease_prefix_v3 as retained
from tools import odoo_v066_current_candidate_no_gui_gate_v3 as prior_gate
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import record_odoo_v066_train_gui_v1 as train_recorder


GATE_OPERATION = "v066_current_candidate_selection_no_gui_db_ready_v4"
GATE_STATUS = "current_sql_and_full_filestore_exact_db_ready_no_gui_v4"
GATE_SCHEMA = "envloop-odoo-v066-current-candidate-no-gui-baseline-gate-v4"
GATE_FILE = "selection-20260929-no-gui-gate-db-ready-v4.private.json"
SQL_FILE = "selection-20260929-current-sql-db-ready-v4.private.json"
FILES_FILE = "selection-20260929-current-filestore-db-ready-v4.private.json"
READINESS_TIMEOUT_S = 60
READINESS_PROBE_TIMEOUT_S = 5
READINESS_POLL_S = 1
READINESS_MAX_PROBES = 30
PSQL_READY_QUERY = "SELECT 1"
PSQL_READY_STDOUT = "1\n"


class NoGuiGateError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise NoGuiGateError(code)


def _reaudit_failures(*, worker: Path, historical_root: Path
                      ) -> tuple[dict[str, str], dict]:
    return retained.reaudit_retained(
        worker=worker, historical_root=historical_root)


def _db_probe(worker: Path, *args: str,
              timeout_s: float) -> subprocess.CompletedProcess:
    """Run only Compose status, native PostgreSQL health, or SELECT 1."""
    return subprocess.run(
        ["docker", "compose", "--env-file", ".env", *args],
        cwd=worker, capture_output=True, text=True, check=False,
        timeout=timeout_s)


def _wait_db_ready(worker: Path, *, clock=None, sleeper=None,
                   probe=None) -> dict:
    """Bound both each probe and the whole health/SQL readiness window."""
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    probe = probe or _db_probe
    started = clock()
    deadline = started + READINESS_TIMEOUT_S
    observations: list[dict] = []
    for attempt in range(1, READINESS_MAX_PROBES + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            break
        row: dict = {"attempt": attempt, "services": [],
                     "pg_isready_exit_code": None,
                     "psql_exit_code": None}
        try:
            result = probe(worker, "ps", "--status", "running", "--services",
                           timeout_s=min(READINESS_PROBE_TIMEOUT_S, remaining))
            row["compose_ps_exit_code"] = result.returncode
            if result.returncode == 0:
                services = {part.strip() for part in result.stdout.splitlines()
                            if part.strip()}
                require(services <= {"db"},
                        "no_gui_gate_unexpected_service_started")
                row["services"] = sorted(services)
                if services == {"db"}:
                    remaining = deadline - clock()
                    if remaining > 0:
                        health = probe(
                            worker, "exec", "-T", "db", "pg_isready",
                            "-U", "odoo", "-d", "postgres",
                            timeout_s=min(READINESS_PROBE_TIMEOUT_S, remaining))
                        row["pg_isready_exit_code"] = health.returncode
                        if health.returncode == 0:
                            remaining = deadline - clock()
                            if remaining > 0:
                                sql_probe = probe(
                                    worker, "exec", "-T", "db", "psql",
                                    "-U", "bench_verify", "-d", "bench",
                                    "-At", "-v", "ON_ERROR_STOP=1", "-c",
                                    PSQL_READY_QUERY,
                                    timeout_s=min(READINESS_PROBE_TIMEOUT_S,
                                                  remaining))
                                row["psql_exit_code"] = sql_probe.returncode
                                if sql_probe.returncode == 0:
                                    require(sql_probe.stdout == PSQL_READY_STDOUT,
                                            "no_gui_gate_readiness_sql_unexpected_output")
                                    row["psql_stdout_sha256"] = sha256(
                                        sql_probe.stdout.encode()).hexdigest()
                                    observations.append(row)
                                    return {
                                        "status": "postgres_health_and_select_1_ready",
                                        "timeout_seconds": READINESS_TIMEOUT_S,
                                        "probe_timeout_seconds":
                                            READINESS_PROBE_TIMEOUT_S,
                                        "probe_count": attempt,
                                        "elapsed_milliseconds":
                                            round((clock() - started) * 1000),
                                        "observations": observations,
                                        "query": PSQL_READY_QUERY,
                                    }
        except subprocess.TimeoutExpired:
            row["probe_timeout"] = True
        except OSError as error:
            raise NoGuiGateError(
                "no_gui_gate_db_probe_execution_failed") from error
        observations.append(row)
        remaining = deadline - clock()
        if remaining <= 0:
            break
        sleeper(min(READINESS_POLL_S, remaining))
    raise NoGuiGateError("no_gui_gate_db_readiness_timeout_no_receipt")


def _collect_live_baseline(worker: Path) -> tuple[dict, dict, str, int, bool, dict]:
    """Acquire original worker lease; always stop DB before returning."""
    private = protocol._worker_split(worker, "selection")
    root = private / "v066_scale_controls"
    factory, _gui, reset, verify, lease = controller._modules(worker)
    sql = files = readiness = None
    restored = False
    with controller._run_lock(root):
        with lease.exclusive_worker_operation(GATE_OPERATION):
            require(controller._running_services_without_compose_blank(worker)
                    == set(), "no_gui_gate_selection_services_not_cold")
            try:
                train_recorder._compose(worker, "up", "-d", "db")
                readiness = _wait_db_ready(worker)
                sql = verify.snapshot()
                config = factory.local_config()
                files = reset.filestore_manifest(
                    config["ODOO_PROJECT"] + "_filestore")
            finally:
                train_recorder._compose(worker, "stop", "db")
                restored = (controller._running_services_without_compose_blank(
                    worker) == set())
    events = private / "worker-lease-events.jsonl"
    protocol._private(events)
    require(type(sql) is dict and type(files) is dict and
            type(readiness) is dict and restored,
            "no_gui_gate_live_readback_or_service_restore_failed")
    return (sql, files, epoch.digest(events), events.stat().st_size,
            restored, readiness)


def prepare(*, worker_dir: Path, historical_root: Path,
            private_plan: Path, public_plan: Path,
            old_private_plan: Path, old_public_plan: Path,
            execute_baseline_check: bool) -> dict:
    require(execute_baseline_check, "no_gui_gate_requires_explicit_execute")
    amendment.validate()
    power_entry = power.capture()
    worker = Path(worker_dir).resolve()
    require(os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "no_gui_gate_original_selection_worker_not_selected")
    plan_audit.audit(
        split="selection", worker_dir=worker,
        private_path=private_plan, public_path=public_plan,
        old_private_path=old_private_plan, old_public_path=old_public_plan)
    plan = protocol.private_json(private_plan)
    private = protocol._worker_split(worker, "selection")
    out = private / "v066_current_candidate_epoch"
    protocol._private(out, directory=True)
    gate_path, sql_path, files_path = (out / GATE_FILE, out / SQL_FILE,
                                       out / FILES_FILE)
    require(not any((out / name).exists() or (out / name).is_symlink()
                    for name in (prior_gate.GATE_FILE, prior_gate.SQL_FILE,
                                 prior_gate.FILES_FILE)),
            "no_gui_gate_prior_v3_output_present")
    require(not any(p.exists() or p.is_symlink()
                    for p in (gate_path, sql_path, files_path)) and
            not (private / "v066_scale_controls" /
                 plan["fresh_run_directory_name"]).exists(),
            "no_gui_gate_output_or_future_run_already_exists")
    before, before_prefixes = _reaudit_failures(
        worker=worker, historical_root=historical_root)
    require(before == plan["retained_terminal_failure_public_sha256s"],
            "no_gui_gate_failure_hashes_changed")
    sql, files, events_sha, events_bytes, restored, readiness = (
        _collect_live_baseline(worker))
    baseline_sql = protocol.private_json(private / "baseline_snapshot.json")
    baseline_files = protocol.private_json(
        private / "baseline-filestore-manifest.json")
    require(sql == baseline_sql and files == baseline_files and restored,
            "no_gui_gate_current_sql_or_full_filestore_not_exact")
    after, after_prefixes = _reaudit_failures(
        worker=worker, historical_root=historical_root)
    require(after == before and after_prefixes == before_prefixes,
            "no_gui_gate_failures_changed_during_check")
    power_exit = power.capture()
    require(power.validate(power_entry) <= power.validate(power_exit),
            "no_gui_gate_power_samples_out_of_order")
    protocol.write_new(sql_path, sql, private=True)
    protocol.write_new(files_path, files, private=True)
    receipt = {
        "schema": GATE_SCHEMA,
        "status": GATE_STATUS,
        "runtime_source_freeze_sha256": amendment.digest(amendment.FREEZE),
        "host_power_entry": power_entry,
        "host_power_exit": power_exit,
        "selection_private_plan_sha256": epoch.digest(private_plan),
        "selection_public_plan_sha256": epoch.digest(public_plan),
        "current_candidate_private_sha256":
            plan["current_candidate_private_sha256"],
        "source_freeze_sha256": plan["source_freeze_sha256"],
        "run_nonce_sha256": protocol.digest(bytes.fromhex(
            plan["run_nonce_hex"])),
        "retained_terminal_failure_public_sha256s": after,
        "retained_historical_lease_prefixes": after_prefixes,
        "current_sql_sha256": epoch.digest(sql_path),
        "current_full_filestore_sha256": epoch.digest(files_path),
        "worker_lease_events_sha256": events_sha,
        "worker_lease_events_bytes": events_bytes,
        "db_readiness": readiness,
        "prior_v3_gate_sql_filestore_outputs_absent": True,
        "service_state_restored_stopped": True,
        "no_gui_actions": True,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    protocol.write_new(gate_path, receipt, private=True)
    return {"schema": GATE_SCHEMA,
            "status": GATE_STATUS,
            "gate_sha256": epoch.digest(gate_path),
            "current_sql_sha256": receipt["current_sql_sha256"],
            "current_full_filestore_sha256":
                receipt["current_full_filestore_sha256"],
            "control_dispatch_authorized": False,
            "official_final_tasks_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    parser.add_argument("--execute-baseline-check", action="store_true")
    args = parser.parse_args()
    value = prepare(worker_dir=args.worker_dir,
                    historical_root=args.historical_root,
                    private_plan=args.private_plan,
                    public_plan=args.public_plan,
                    old_private_plan=args.old_private_plan,
                    old_public_plan=args.old_public_plan,
                    execute_baseline_check=args.execute_baseline_check)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
