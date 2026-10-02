"""Independently audit the dated battery-authorized Odoo baseline gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_current_candidate_epoch_v1 as plan_audit
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_current_candidate_no_gui_gate_v2 as gate
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_battery_authorized_source_v2 as amendment
from tools import odoo_v066_scale_protocol_v1 as protocol


AUDIT_SCHEMA = "envloop-odoo-v066-current-candidate-no-gui-gate-audit-v2"


class GateAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise GateAuditError(code)


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
            receipt.get("no_gui_actions") is True and
            receipt.get("control_dispatch_authorized") is False and
            receipt.get("campaign_dispatch_authorized") is False and
            receipt.get("official_final_tasks_admitted") == 0 and
            receipt.get("model_attempts") == 0,
            "gate_audit_receipt_or_full_baseline_inexact")
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
    failures = gate._reaudit_failures(worker=worker,
                                     historical_root=historical_root)
    require(failures == receipt["retained_terminal_failure_public_sha256s"],
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
    args = parser.parse_args()
    value = audit(worker_dir=args.worker_dir,
                  historical_root=args.historical_root,
                  private_plan=args.private_plan,
                  public_plan=args.public_plan,
                  old_private_plan=args.old_private_plan,
                  old_public_plan=args.old_public_plan)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
