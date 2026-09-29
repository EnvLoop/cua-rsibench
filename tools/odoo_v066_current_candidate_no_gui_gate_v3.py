"""Lease-prefix-amended Odoo selection baseline gate; no GUI dispatch.

The gate independently re-audits all three failed GUI controls, acquires the
original selection worker lease, starts only the database to read current SQL
and every physical filestore entry, restores the stopped service state, then
records an owner-only receipt. A passing receipt still cannot run a GUI case
or authorize any researcher campaign.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools import audit_odoo_v066_current_candidate_epoch_v1 as plan_audit
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_lease_prefix_source_v3 as amendment
from tools import odoo_v066_retained_lease_prefix_v3 as retained
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import record_odoo_v066_train_gui_v1 as train_recorder


GATE_OPERATION = "v066_current_candidate_selection_no_gui_lease_prefix_v3"
GATE_STATUS = "current_sql_and_full_filestore_exact_lease_prefix_no_gui_v3"
GATE_SCHEMA = "envloop-odoo-v066-current-candidate-no-gui-baseline-gate-v3"
GATE_FILE = "selection-20260929-no-gui-gate-lease-prefix-v3.private.json"
SQL_FILE = "selection-20260929-current-sql-lease-prefix-v3.private.json"
FILES_FILE = "selection-20260929-current-filestore-lease-prefix-v3.private.json"


class NoGuiGateError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise NoGuiGateError(code)


def _reaudit_failures(*, worker: Path, historical_root: Path
                      ) -> tuple[dict[str, str], dict]:
    return retained.reaudit_retained(
        worker=worker, historical_root=historical_root)


def _collect_live_baseline(worker: Path) -> tuple[dict, dict, str, int, bool]:
    """Acquire original worker lease; always stop DB before returning."""
    private = protocol._worker_split(worker, "selection")
    root = private / "v066_scale_controls"
    factory, _gui, reset, verify, lease = controller._modules(worker)
    sql = files = None
    restored = False
    with controller._run_lock(root):
        with lease.exclusive_worker_operation(GATE_OPERATION):
            require(controller._running_services_without_compose_blank(worker)
                    == set(), "no_gui_gate_selection_services_not_cold")
            try:
                train_recorder._compose(worker, "up", "-d", "db")
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
    require(type(sql) is dict and type(files) is dict and restored,
            "no_gui_gate_live_readback_or_service_restore_failed")
    return sql, files, epoch.digest(events), events.stat().st_size, restored


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
    require(not any(p.exists() or p.is_symlink()
                    for p in (gate_path, sql_path, files_path)) and
            not (private / "v066_scale_controls" /
                 plan["fresh_run_directory_name"]).exists(),
            "no_gui_gate_output_or_future_run_already_exists")
    before, before_prefixes = _reaudit_failures(
        worker=worker, historical_root=historical_root)
    require(before == plan["retained_terminal_failure_public_sha256s"],
            "no_gui_gate_failure_hashes_changed")
    sql, files, events_sha, events_bytes, restored = _collect_live_baseline(worker)
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
