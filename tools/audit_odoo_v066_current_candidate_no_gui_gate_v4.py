"""Independently audit the dated DB-readiness Odoo baseline gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_current_candidate_epoch_v1 as plan_audit
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_current_candidate_no_gui_gate_v4 as gate
from tools import odoo_v066_current_candidate_no_gui_gate_v3 as prior_gate
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_db_readiness_source_v4 as amendment
from tools import odoo_v066_retained_lease_prefix_v3 as retained
from tools import odoo_v066_scale_protocol_v1 as protocol


AUDIT_SCHEMA = "envloop-odoo-v066-current-candidate-no-gui-gate-audit-v4"
PUBLIC_AUDIT = (
    protocol.ROOT / "docs/evidence" /
    "odoo-v066-current-candidate-selection-no-gui-db-ready-gate-audit-2026-09-29.json"
)


class GateAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise GateAuditError(code)


def _readiness(value: object) -> None:
    """Validate a successful bounded native health and verifier SQL trace."""
    require(type(value) is dict and
            value.get("status") == "postgres_health_and_select_1_ready" and
            value.get("timeout_seconds") == gate.READINESS_TIMEOUT_S and
            value.get("probe_timeout_seconds") ==
            gate.READINESS_PROBE_TIMEOUT_S and
            value.get("query") == gate.PSQL_READY_QUERY and
            type(value.get("probe_count")) is int and
            1 <= value["probe_count"] <= gate.READINESS_MAX_PROBES and
            type(value.get("elapsed_milliseconds")) is int and
            0 <= value["elapsed_milliseconds"] <=
            (gate.READINESS_TIMEOUT_S + gate.READINESS_PROBE_TIMEOUT_S) * 1000 and
            type(value.get("observations")) is list and
            len(value["observations"]) == value["probe_count"],
            "gate_audit_db_readiness_bounds_invalid")
    for index, row in enumerate(value["observations"], start=1):
        require(type(row) is dict and row.get("attempt") == index and
                type(row.get("services")) is list and
                row["services"] in ([], ["db"]) and
                (row.get("compose_ps_exit_code") is None or
                 type(row["compose_ps_exit_code"]) is int) and
                (row.get("pg_isready_exit_code") is None or
                 type(row["pg_isready_exit_code"]) is int) and
                (row.get("psql_exit_code") is None or
                 type(row["psql_exit_code"]) is int),
                "gate_audit_db_readiness_probe_invalid")
    last = value["observations"][-1]
    require(last["services"] == ["db"] and
            last["compose_ps_exit_code"] == 0 and
            last["pg_isready_exit_code"] == 0 and
            last["psql_exit_code"] == 0 and
            last.get("probe_timeout") is not True and
            last.get("psql_stdout_sha256") ==
            sha256(gate.PSQL_READY_STDOUT.encode()).hexdigest(),
            "gate_audit_db_readiness_select_1_unverified")


def audit(*, worker_dir: Path, historical_root: Path,
          private_plan: Path, public_plan: Path,
          old_private_plan: Path, old_public_plan: Path,
          allow_current_run: bool = False) -> dict:
    amendment.validate()
    worker = Path(worker_dir).resolve()
    plan_audit.audit(
        split="selection", worker_dir=worker,
        private_path=private_plan, public_path=public_plan,
        old_private_path=old_private_plan, old_public_path=old_public_plan,
        allow_current_run=allow_current_run)
    plan = protocol.private_json(private_plan)
    private = protocol._worker_split(worker, "selection")
    directory = private / "v066_current_candidate_epoch"
    require(not any((directory / name).exists() or
                    (directory / name).is_symlink()
                    for name in (prior_gate.GATE_FILE, prior_gate.SQL_FILE,
                                 prior_gate.FILES_FILE)),
            "gate_audit_prior_v3_output_present")
    receipt_path = directory / gate.GATE_FILE
    sql_path = directory / gate.SQL_FILE
    files_path = directory / gate.FILES_FILE
    receipt = protocol.private_json(receipt_path)
    sql = protocol.private_json(sql_path)
    files = protocol.private_json(files_path)
    frozen_sql = protocol.private_json(private / "baseline_snapshot.json")
    frozen_files = protocol.private_json(
        private / "baseline-filestore-manifest.json")
    require(receipt.get("schema") == gate.GATE_SCHEMA and
            receipt.get("runtime_source_freeze_sha256") ==
            amendment.digest(amendment.FREEZE) and
            receipt.get("status") == gate.GATE_STATUS and
            receipt.get("selection_private_plan_sha256") ==
            epoch.digest(private_plan) and
            receipt.get("selection_public_plan_sha256") ==
            epoch.digest(public_plan) and
            receipt.get("current_candidate_private_sha256") ==
            plan["current_candidate_private_sha256"] and
            receipt.get("source_freeze_sha256") ==
            plan["source_freeze_sha256"] and
            receipt.get("run_nonce_sha256") ==
            protocol.digest(bytes.fromhex(plan["run_nonce_hex"])) and
            receipt.get("retained_terminal_failure_public_sha256s") ==
            plan["retained_terminal_failure_public_sha256s"] and
            receipt.get("current_sql_sha256") == epoch.digest(sql_path) and
            receipt.get("current_full_filestore_sha256") ==
            epoch.digest(files_path) and
            sql == frozen_sql and files == frozen_files and
            receipt.get("service_state_restored_stopped") is True and
            receipt.get("prior_v3_gate_sql_filestore_outputs_absent") is True and
            receipt.get("no_gui_actions") is True and
            receipt.get("control_dispatch_authorized") is False and
            receipt.get("campaign_dispatch_authorized") is False and
            receipt.get("official_final_tasks_admitted") == 0 and
            receipt.get("model_attempts") == 0,
            "gate_audit_receipt_or_full_baseline_inexact")
    _readiness(receipt.get("db_readiness"))
    entry = power.validate(receipt.get("host_power_entry"))
    exit_time = power.validate(receipt.get("host_power_exit"))
    require(entry <= exit_time, "gate_audit_power_samples_out_of_order")
    events_path = private / "worker-lease-events.jsonl"
    protocol._private(events_path)
    events_raw = events_path.read_bytes()
    prefix_bytes = receipt.get("worker_lease_events_bytes")
    require(type(prefix_bytes) is int and 0 < prefix_bytes <= len(events_raw) and
            events_raw[prefix_bytes - 1:prefix_bytes] == b"\n" and
            sha256(events_raw[:prefix_bytes]).hexdigest() ==
            receipt.get("worker_lease_events_sha256"),
            "gate_audit_worker_lease_prefix_changed")
    events = [json.loads(line) for line in
              events_raw[:prefix_bytes].splitlines()]
    require(len(events) >= 2 and
            events[-2].get("event") == "acquired" and
            events[-1].get("event") == "released" and
            events[-2].get("operation") ==
            events[-1].get("operation") == gate.GATE_OPERATION and
            type(events[-2].get("pid")) is int and
            events[-2]["pid"] == events[-1].get("pid"),
            "gate_audit_original_worker_lease_not_released")
    # Reopen the three original failure directories through their independent
    # source-bound auditors; the live service-state check is read-only.
    failures, prefixes = retained.reaudit_retained(
        worker=worker, historical_root=historical_root)
    require(failures == receipt["retained_terminal_failure_public_sha256s"] and
            prefixes == receipt.get("retained_historical_lease_prefixes"),
            "gate_audit_retained_failures_changed")
    return {
        "schema": AUDIT_SCHEMA,
        "status": "no_gui_current_sql_full_filestore_gate_independently_verified",
        "gate_sha256": epoch.digest(receipt_path),
        "runtime_source_freeze_sha256": amendment.digest(amendment.FREEZE),
        "host_power_entry_source": receipt["host_power_entry"]["source"],
        "host_power_exit_source": receipt["host_power_exit"]["source"],
        "private_plan_sha256": epoch.digest(private_plan),
        "current_sql_sha256": epoch.digest(sql_path),
        "current_full_filestore_sha256": epoch.digest(files_path),
        "db_readiness_probe_count": receipt["db_readiness"]["probe_count"],
        "db_readiness_elapsed_milliseconds":
            receipt["db_readiness"]["elapsed_milliseconds"],
        "retained_terminal_selection_failures": 3,
        "source_visual_review_pending": True,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    parser.add_argument("--write-public-audit", action="store_true")
    args = parser.parse_args()
    value = audit(worker_dir=args.worker_dir,
                  historical_root=args.historical_root,
                  private_plan=args.private_plan,
                  public_plan=args.public_plan,
                  old_private_plan=args.old_private_plan,
                  old_public_plan=args.old_public_plan)
    if args.write_public_audit:
        require(not PUBLIC_AUDIT.exists() and not PUBLIC_AUDIT.is_symlink(),
                "gate_audit_public_receipt_already_exists")
        protocol.write_new(PUBLIC_AUDIT, value, private=False)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
