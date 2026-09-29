"""Fresh stopped-state Odoo baseline gate for the two-frame v6 epoch."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from tools import audit_odoo_v066_parse_border_dispatch_failure_20260929 as failure_audit
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_current_candidate_no_gui_gate_v4 as prior_gate
from tools import odoo_v066_two_frame_plan_v6 as plan_v6
from tools import odoo_v066_two_frame_source_v6 as source
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import record_odoo_v066_train_gui_v1 as train_recorder


SCHEMA = "envloop-odoo-v066-two-frame-current-baseline-gate-v6"
STATUS = "current_sql_and_full_filestore_exact_two_frame_v6_no_gui"
GATE_OPERATION = "v066_two_frame_v6_no_gui_gate"
INTENT_FILE = "selection-two-frame-v6-no-gui-intent.private.json"
GATE_FILE = "selection-two-frame-v6-no-gui-gate.private.json"
SQL_FILE = "selection-two-frame-v6-current-sql.private.json"
FILES_FILE = "selection-two-frame-v6-current-filestore.private.json"


class ParseGateError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ParseGateError(code)


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "parse_gate_artifact_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def collect(worker: Path) -> tuple[dict, dict, dict, str, int]:
    private = protocol._worker_split(worker, "selection")
    root = private / "v066_scale_controls"
    factory, _gui, reset, verify, lease = controller._modules(worker)
    sql = files = readiness = None
    restored = False
    with controller._run_lock(root):
        with lease.exclusive_worker_operation(GATE_OPERATION):
            need(controller._running_services_without_compose_blank(worker)
                 == set(), "parse_gate_original_services_not_cold")
            try:
                train_recorder._compose(worker, "up", "-d", "db")
                readiness = prior_gate._wait_db_ready(worker)
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
    need(type(sql) is dict and type(files) is dict and
         type(readiness) is dict and restored,
         "parse_gate_live_readback_or_restore_failed")
    return sql, files, readiness, digest(events), events.stat().st_size


def prepare(*, worker_dir: Path, historical_root: Path,
            prior_v4_private_plan: Path, prior_v4_public_plan: Path,
            old_private_plan: Path, old_public_plan: Path,
            prior_v5_private_plan: Path, prior_v5_public_plan: Path,
            private_freeze: Path,
            private_plan: Path, public_plan: Path,
            execute_baseline_check: bool) -> dict:
    need(execute_baseline_check,
         "parse_gate_requires_explicit_execute_baseline_check")
    source.validate()
    worker = worker_dir.resolve()
    need(os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
         "parse_gate_original_selection_worker_not_selected")
    plan = plan_v6.audit(
        worker_dir=worker,
        prior_private_plan=prior_v5_private_plan,
        prior_public_plan=prior_v5_public_plan,
        private_freeze=private_freeze,
        private_plan=private_plan, public_plan=public_plan)
    prior = failure_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_v4_private_plan,
        prior_public_plan=prior_v4_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan,
        private_plan=prior_v5_private_plan,
        public_plan=prior_v5_public_plan)
    private = protocol._worker_split(worker, "selection")
    out = private / "v066_two_frame_v6"
    protocol._private(out, directory=True)
    gate, sql_path, files_path = (out / GATE_FILE, out / SQL_FILE,
                                  out / FILES_FILE)
    intent_path = out / INTENT_FILE
    new_plan = protocol.private_json(private_plan)
    run = private / "v066_scale_controls" / new_plan["fresh_run_directory_name"]
    need(not any(path.exists() or path.is_symlink()
                 for path in (intent_path, gate, sql_path, files_path, run)),
         "parse_gate_output_or_future_run_already_exists")
    power_entry = power.capture()
    protocol.write_new(intent_path, {
        "schema": "envloop-odoo-v066-two-frame-no-gui-intent-v6",
        "status": "durable_before_first_original_odoo_service_call",
        "plan_sha256": plan["private_plan_sha256"],
        "source_freeze_sha256": source.digest(source.FREEZE),
        "private_source_freeze_sha256": digest(private_freeze),
        "prior_failure_receipt_sha256":
            prior["failure_receipt_sha256"],
        "host_power_pre_intent": power_entry,
        "automatic_replay_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }, private=True)
    sql, files, readiness, lease_sha, lease_bytes = collect(worker)
    need(sql == protocol.private_json(private / "baseline_snapshot.json") and
         files == protocol.private_json(
             private / "baseline-filestore-manifest.json"),
         "parse_gate_current_sql_or_full_filestore_not_exact")
    after = failure_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_v4_private_plan,
        prior_public_plan=prior_v4_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan,
        private_plan=prior_v5_private_plan,
        public_plan=prior_v5_public_plan)
    need(after == prior, "parse_gate_prior_failure_changed_during_check")
    power_exit = power.capture()
    need(power.validate(power_entry) <= power.validate(power_exit),
         "parse_gate_power_samples_out_of_order")
    protocol.write_new(sql_path, sql, private=True)
    protocol.write_new(files_path, files, private=True)
    receipt = {
        "schema": SCHEMA,
        "status": STATUS,
        "plan_sha256": plan["private_plan_sha256"],
        "public_plan_sha256": plan["public_plan_sha256"],
        "two_frame_v6_source_freeze_sha256": source.digest(source.FREEZE),
        "two_frame_v6_private_source_freeze_sha256":
            digest(private_freeze),
        "prior_failure_receipt_sha256": prior["failure_receipt_sha256"],
        "prior_no_gui_gate_sha256": prior["prior_no_gui_gate_sha256"],
        "pre_service_intent_sha256": digest(intent_path),
        "current_sql_sha256": digest(sql_path),
        "current_full_filestore_sha256": digest(files_path),
        "worker_lease_events_prefix_sha256": lease_sha,
        "worker_lease_events_prefix_bytes": lease_bytes,
        "db_readiness": readiness,
        "host_power_entry": power_entry,
        "host_power_exit": power_exit,
        "original_worker_services_restored_stopped": True,
        "no_gui_actions": True,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    protocol.write_new(gate, receipt, private=True)
    return {"status": STATUS, "gate_sha256": digest(gate),
            "current_sql_sha256": receipt["current_sql_sha256"],
            "current_full_filestore_sha256":
                receipt["current_full_filestore_sha256"],
            "official_final_tasks_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("worker-dir", "historical-root", "prior-v4-private-plan",
                 "prior-v4-public-plan", "old-private-plan", "old-public-plan",
                 "prior-v5-private-plan", "prior-v5-public-plan",
                 "private-freeze", "private-plan", "public-plan"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--execute-baseline-check", action="store_true")
    args = parser.parse_args()
    values = vars(args)
    execute = values.pop("execute_baseline_check")
    result = prepare(**values, execute_baseline_check=execute)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
