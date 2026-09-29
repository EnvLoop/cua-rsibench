"""Independent read-only audit of the Odoo parse-border v5 baseline gate."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as failure_audit
from tools import audit_odoo_v066_current_candidate_no_gui_gate_v4 as prior_gate_audit
from tools import odoo_v066_battery_authorized_power_v2 as power
from tools import odoo_v066_parse_border_no_gui_gate_v5 as gate
from tools import odoo_v066_parse_border_plan_v5 as plan_v5
from tools import odoo_v066_parse_border_source_v5 as source
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-parse-border-no-gui-gate-audit-v5"
PUBLIC_AUDIT = (protocol.ROOT / "docs/evidence" /
                "odoo-v066-selection-parse-border-v5-no-gui-gate-audit-2026-09-29.json")


class ParseGateAuditError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ParseGateAuditError(code)


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "parse_gate_audit_artifact_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def audit(*, worker_dir: Path, historical_root: Path,
          prior_private_plan: Path, prior_public_plan: Path,
          old_private_plan: Path, old_public_plan: Path,
          private_plan: Path, public_plan: Path,
          allow_current_run: bool = False) -> dict:
    source.validate()
    worker = worker_dir.resolve()
    plan = plan_v5.audit(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan,
        private_plan=private_plan, public_plan=public_plan,
        allow_current_run=allow_current_run)
    failure = failure_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        private_plan=prior_private_plan, public_plan=prior_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan)
    private = protocol._worker_split(worker, "selection")
    out = private / "v066_parse_border_v5"
    receipt_path = out / gate.GATE_FILE
    intent_path = out / gate.INTENT_FILE
    sql_path = out / gate.SQL_FILE
    files_path = out / gate.FILES_FILE
    receipt = protocol.private_json(receipt_path)
    intent = protocol.private_json(intent_path)
    sql = protocol.private_json(sql_path)
    files = protocol.private_json(files_path)
    need(receipt.get("schema") == gate.SCHEMA and
         receipt.get("status") == gate.STATUS and
         receipt.get("plan_sha256") == plan["private_plan_sha256"] and
         receipt.get("public_plan_sha256") ==
         plan["public_plan_sha256"] and
         receipt.get("parse_border_v5_source_freeze_sha256") ==
         source.digest(source.FREEZE) and
         receipt.get("prior_failure_receipt_sha256") ==
         failure["failure_receipt_sha256"] and
         receipt.get("prior_no_gui_gate_sha256") ==
         failure["preceding_gate_sha256"] and
         receipt.get("pre_service_intent_sha256") ==
         digest(intent_path) and
         intent.get("schema") ==
         "envloop-odoo-v066-parse-border-no-gui-intent-v5" and
         intent.get("status") ==
         "durable_before_first_original_odoo_service_call" and
         intent.get("plan_sha256") == plan["private_plan_sha256"] and
         intent.get("source_freeze_sha256") ==
         source.digest(source.FREEZE) and
         intent.get("prior_failure_receipt_sha256") ==
         failure["failure_receipt_sha256"] and
         intent.get("automatic_replay_authorized") is False and
         intent.get("official_final_tasks_admitted") == 0 and
         intent.get("model_attempts") == 0 and
         receipt.get("current_sql_sha256") == digest(sql_path) and
         receipt.get("current_full_filestore_sha256") ==
         digest(files_path) and
         sql == protocol.private_json(private / "baseline_snapshot.json") and
         files == protocol.private_json(
             private / "baseline-filestore-manifest.json") and
         receipt.get("original_worker_services_restored_stopped") is True and
         receipt.get("no_gui_actions") is True and
         receipt.get("automatic_replay_authorized") is False and
         receipt.get("control_dispatch_authorized") is False and
         receipt.get("campaign_dispatch_authorized") is False and
         receipt.get("official_final_tasks_admitted") == 0 and
         receipt.get("model_attempts") == 0,
         "parse_gate_audit_receipt_or_baseline_changed")
    prior_gate_audit._readiness(receipt.get("db_readiness"))
    entry = power.validate(receipt.get("host_power_entry"))
    exit_time = power.validate(receipt.get("host_power_exit"))
    need(power.validate(intent["host_power_pre_intent"]) == entry and
         entry <= exit_time,
         "parse_gate_audit_power_samples_out_of_order")
    events = private / "worker-lease-events.jsonl"
    protocol._private(events)
    raw = events.read_bytes()
    size = receipt.get("worker_lease_events_prefix_bytes")
    need(type(size) is int and 0 < size <= len(raw) and
         raw[size - 1:size] == b"\n" and
         sha256(raw[:size]).hexdigest() ==
         receipt.get("worker_lease_events_prefix_sha256"),
         "parse_gate_audit_lease_prefix_changed")
    rows = [json.loads(line) for line in raw[:size].splitlines()]
    need(len(rows) >= 2 and
         [row.get("event") for row in rows[-2:]] ==
         ["acquired", "released"] and
         all(row.get("operation") == gate.GATE_OPERATION
             for row in rows[-2:]) and
         rows[-2].get("pid") == rows[-1].get("pid") and
         entry <= datetime.fromisoformat(rows[-2]["at_utc"]) <=
         datetime.fromisoformat(rows[-1]["at_utc"]) <= exit_time and
         controller._running_services_without_compose_blank(worker) == set(),
         "parse_gate_audit_lease_or_stopped_services_invalid")
    return {
        "schema": SCHEMA,
        "status": "fresh_no_gui_sql_full_filestore_gate_independently_verified",
        "gate_sha256": digest(receipt_path),
        "private_plan_sha256": plan["private_plan_sha256"],
        "parse_border_v5_source_freeze_sha256":
            receipt["parse_border_v5_source_freeze_sha256"],
        "prior_failure_receipt_sha256":
            receipt["prior_failure_receipt_sha256"],
        "current_sql_sha256": digest(sql_path),
        "current_full_filestore_sha256": digest(files_path),
        "db_readiness_probe_count": receipt["db_readiness"]["probe_count"],
        "original_worker_services_stopped": True,
        "source_visual_review_pending": True,
        "automatic_replay_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("worker-dir", "historical-root", "prior-private-plan",
                 "prior-public-plan", "old-private-plan", "old-public-plan",
                 "private-plan", "public-plan"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--write-public-audit", action="store_true")
    args = parser.parse_args()
    values = vars(args)
    write = values.pop("write_public_audit")
    result = audit(**values)
    if write:
        need(not PUBLIC_AUDIT.exists() and not PUBLIC_AUDIT.is_symlink(),
             "parse_gate_audit_public_receipt_already_exists")
        protocol.write_new(PUBLIC_AUDIT, result, private=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
