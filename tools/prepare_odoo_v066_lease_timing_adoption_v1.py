"""Prepare a pre-result old-to-new Odoo source adoption without GUI replay.

The preserved first split-wide train attempt is independently auditable after
its worker lease released, but its old journal retains `case_failed`. This
preparer binds old and corrected source/plan bytes to a future explicit live
baseline reconciliation. It never changes the journal or starts Docker.
"""

from __future__ import annotations

from pathlib import Path

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_scale_controller_v1 as controller


SCHEMA = "envloop-odoo-v066-lease-audit-source-adoption-v1"
PUBLIC_SCHEMA = "envloop-odoo-v066-lease-audit-source-adoption-public-v1"


class AdoptionError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise AdoptionError(code)


def build(*, old_private_plan: Path, old_public_plan: Path,
          old_source_freeze: Path, new_private_plan: Path,
          new_public_plan: Path, new_source_freeze: Path,
          incident_private: Path, incident_public: Path,
          run_dir: Path) -> tuple[dict, dict]:
    old = protocol.private_json(old_private_plan)
    new = protocol.validate_split_plan(
        split="train", private_path=new_private_plan,
        public_path=new_public_plan,
        source_freeze_path=new_source_freeze)
    old_public = protocol.public_json(old_public_plan)
    old_freeze = protocol.public_json(old_source_freeze)
    new_freeze = protocol.public_json(new_source_freeze)
    incident = protocol.public_json(incident_public)
    incident_private_value = protocol.private_json(incident_private)
    run_dir = Path(run_dir)
    protocol._private(run_dir, directory=True)
    journal_rows, tail, count = controller.read_journal(
        run_dir / "journal.private.jsonl")
    attempt_path = run_dir / "attempt-000" / "attempt.private.json"
    protocol._private(attempt_path)
    require(old.get("schema") == protocol.PRIVATE_PLAN_SCHEMA and
            old.get("split") == new.get("split") == "train" and
            old.get("tasks") == new.get("tasks") and
            old.get("checkpoint") == new.get("checkpoint") and
            old.get("task_count") == new.get("task_count") == 19 and
            old_public.get("private_plan_sha256") ==
            protocol.digest(old_private_plan.read_bytes()) and
            old.get("source_freeze_sha256") ==
            protocol.digest(old_source_freeze.read_bytes()) and
            old_freeze.get("schema") == protocol.SOURCE_FREEZE_SCHEMA and
            new_freeze.get("old_source_freeze_sha256") ==
            protocol.digest(old_source_freeze.read_bytes()) and
            new_freeze.get("incident_public_sha256") ==
            protocol.digest(incident_public.read_bytes()) and
            incident.get("schema") ==
            "envloop-odoo-v066-inline-lease-audit-order-incident-v1" and
            incident.get("status") ==
            "complete_actor_control_audited_after_lease_release_reclassification_pending" and
            incident.get("old_private_plan_sha256") ==
            protocol.digest(old_private_plan.read_bytes()) and
            incident.get("old_source_freeze_sha256") ==
            protocol.digest(old_source_freeze.read_bytes()) and
            incident.get("old_attempt_sha256") ==
            protocol.digest(attempt_path.read_bytes()) and
            incident.get("private_incident_audit_sha256") ==
            protocol.digest(protocol.canonical(incident_private_value)) and
            count == 2 and [row["event"] for row in journal_rows] ==
            ["case_started", "case_failed"] and
            tail == incident.get("journal_tail_sha256") and
            incident.get("reclassification_authorized") is False and
            incident.get("current_live_sql_and_full_filestore_baseline_queried")
            is False,
            "old_complete_attempt_or_pre_result_adoption_invalid")
    changed = {"tools/odoo_v066_scale_protocol_v1.py",
               "tools/odoo_v066_scale_controller_v1.py",
               "tools/odoo_v066_scale_audit_v1.py",
               "tools/audit_odoo_v066_inline_lease_incident_v1.py",
               "tools/prepare_odoo_v066_lease_timing_adoption_v1.py"}
    common = set(old_freeze.get("source_sha256s", {})) - changed
    require(common and all(old_freeze["source_sha256s"][name] ==
                           new_freeze["source_sha256s"].get(name)
                           for name in common),
            "odoo_actor_action_or_verifier_source_changed")
    private = {
        "schema": SCHEMA,
        "status": "prepared_for_manual_live_baseline_reconciliation",
        "split": "train",
        "ordinal": 0,
        "task_id": old["tasks"][0]["task_id"],
        "package_sha256": old["tasks"][0]["package_sha256"],
        "old_private_plan_sha256": protocol.digest(old_private_plan.read_bytes()),
        "new_private_plan_sha256": protocol.digest(new_private_plan.read_bytes()),
        "old_source_freeze_sha256": protocol.digest(old_source_freeze.read_bytes()),
        "new_source_freeze_sha256": protocol.digest(new_source_freeze.read_bytes()),
        "incident_public_sha256": protocol.digest(incident_public.read_bytes()),
        "incident_private_sha256": protocol.digest(incident_private.read_bytes()),
        "old_batch_intent_sha256": incident["batch_intent_sha256"],
        "old_journal_sha256": incident["journal_sha256"],
        "old_journal_tail_sha256": tail,
        "old_attempt_sha256": incident["old_attempt_sha256"],
        "actor_action_verifier_runtime_bytes_identical": True,
        "current_live_baseline_query_required_before_reclassification": True,
        "original_case_failed_event_retained": True,
        "gui_replay_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_adoption_prepared_current_baseline_and_reclassification_pending",
        "old_source_freeze_sha256": private["old_source_freeze_sha256"],
        "new_source_freeze_sha256": private["new_source_freeze_sha256"],
        "old_private_plan_sha256": private["old_private_plan_sha256"],
        "new_private_plan_sha256": private["new_private_plan_sha256"],
        "incident_public_sha256": private["incident_public_sha256"],
        "private_adoption_sha256": protocol.digest(protocol.canonical(private)),
        "same_train_19_task_identities_and_checkpoints": True,
        "actor_action_verifier_runtime_bytes_identical": True,
        "current_live_baseline_query_complete": False,
        "case_reclassified_after_lease_release": False,
        "gui_replay_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    return private, public


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old_private_plan", "old_public_plan", "old_source_freeze",
                 "new_private_plan", "new_public_plan", "new_source_freeze",
                 "incident_private", "incident_public", "run_dir"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        private, public = build(**{name: getattr(args, name) for name in (
            "old_private_plan", "old_public_plan", "old_source_freeze",
            "new_private_plan", "new_public_plan", "new_source_freeze",
            "incident_private", "incident_public", "run_dir")})
        protocol.write_new(args.private_out, private, private=True)
        protocol.write_new(args.public_out, public, private=False)
    except Exception as error:
        print(json.dumps({"schema": PUBLIC_SCHEMA,
                          "status": "adoption_preparation_refused",
                          "error_type": type(error).__name__,
                          "official_final_tasks_admitted": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(public, sort_keys=True))
