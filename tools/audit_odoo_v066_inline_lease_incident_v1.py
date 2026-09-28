"""Read-only incident audit for the first split-wide Odoo train control.

The frozen v1 controller independently audited a complete raw attempt while
still holding its worker lease. The saved journal must retain both the start
and failure rows. This audit checks raw state after release; it does not query
current live Odoo state or authorize reclassification by itself.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_audit_v1 as independent
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-inline-lease-audit-order-incident-v1"
OLD_SOURCE_REVISION = "f5fdd5d08646f72fbe4acf45188f76f6fc33308c"
OLD_FILES = (
    "tools/odoo_v066_scale_protocol_v1.py",
    "tools/odoo_v066_scale_controller_v1.py",
    "tools/odoo_v066_scale_audit_v1.py",
)


class IncidentAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise IncidentAuditError(code)


def old_blob(repo: Path, relative: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{OLD_SOURCE_REVISION}:{relative}"],
        cwd=repo, capture_output=True, check=True)
    return process.stdout


def audit(*, repo: Path, run_dir: Path, worker_private: Path,
          old_private_plan: Path, old_public_plan: Path,
          old_source_freeze: Path) -> tuple[dict, dict]:
    root = Path(repo).resolve()
    run_dir = Path(run_dir)
    protocol._private(run_dir, directory=True)
    private = protocol.private_json(old_private_plan)
    public = protocol.public_json(old_public_plan)
    freeze = protocol.public_json(old_source_freeze)
    raw_freeze = old_source_freeze.read_bytes()
    require(private.get("schema") == protocol.PRIVATE_PLAN_SCHEMA and
            private.get("split") == "train" and
            private.get("task_count") == 19 and
            private.get("source_freeze_sha256") == protocol.digest(raw_freeze) and
            public.get("private_plan_sha256") ==
            protocol.digest(old_private_plan.read_bytes()) and
            freeze.get("schema") == protocol.SOURCE_FREEZE_SCHEMA and
            freeze.get("official_final_tasks_admitted") == 0 and
            freeze.get("model_attempts") == 0,
            "old_split_plan_or_freeze_unbound")
    for relative in OLD_FILES:
        require(protocol.digest(old_blob(root, relative)) ==
                freeze["source_sha256s"].get(relative),
                "old_frozen_source_blob_changed")
    intent_path = run_dir / "batch-intent.private.json"
    intent = protocol.private_json(intent_path)
    require(intent.get("schema") == protocol.BATCH_SCHEMA and
            intent.get("split") == "train" and
            intent.get("private_plan_sha256") ==
            protocol.digest(old_private_plan.read_bytes()) and
            intent.get("source_freeze_sha256") == protocol.digest(raw_freeze) and
            intent.get("expected_case_count") == 19,
            "old_batch_intent_unbound")
    journal_path = run_dir / "journal.private.jsonl"
    rows, tail, length = controller.read_journal(journal_path)
    first = private["tasks"][0]
    require(length == 2 and
            [row.get("event") for row in rows] ==
            ["case_started", "case_failed"] and
            [row.get("ordinal") for row in rows] == [0, 0] and
            all(row.get("task_id") == first["task_id"] and
                row.get("package_sha256") == first["package_sha256"] and
                row.get("attempt_dir") == "attempt-000" for row in rows),
            "old_failure_journal_not_preserved")
    attempt = run_dir / "attempt-000"
    protocol._private(attempt, directory=True)
    require(not (attempt / "failure.private.json").exists() and
            (attempt / "attempt.private.json").is_file(),
            "old_actor_control_not_complete")
    derived = independent.audit_case(
        plan=private, row=first, attempt=attempt,
        worker_private=worker_private)
    require(derived.get("status") ==
            "current_profile_raw_gui_semantics_verified_source_visual_review_pending" and
            derived.get("independent_positive_reward") == 1.0 and
            derived.get("independent_wrong_object_reward") == 0.0 and
            derived.get("full_pre_web_filestore_reset_exact") is True and
            derived.get("protected_post_web_source_bytes_equal") is True and
            derived.get("official_final_tasks_admitted") == 0,
            "old_actor_evidence_not_independently_verified_after_lease")
    old_controller = old_blob(root, "tools/odoo_v066_scale_controller_v1.py")
    old_auditor = old_blob(root, "tools/odoo_v066_scale_audit_v1.py")
    require(b"with lease.exclusive_worker_operation(LEASE_OPERATION):" in old_controller and
            b"independent.audit_case(" in old_controller and
            b"later.get(\"event\") == \"released\"" in old_auditor,
            "old_inline_audit_lease_timing_not_source_bound")
    private_report = {
        "schema": SCHEMA,
        "status": "complete_actor_control_old_inline_lease_audit_failed",
        "task_id": first["task_id"],
        "package_sha256": first["package_sha256"],
        "task_binding_sha256": first["task_binding_sha256"],
        "old_private_plan_sha256": protocol.digest(old_private_plan.read_bytes()),
        "old_source_freeze_sha256": protocol.digest(raw_freeze),
        "batch_intent_sha256": protocol.digest(intent_path.read_bytes()),
        "journal_sha256": protocol.digest(journal_path.read_bytes()),
        "journal_tail_sha256": tail,
        "old_attempt_sha256": derived["private_attempt_sha256"],
        "independent_case_audit": derived,
        "failed_journal_rows_retained": 2,
        "current_live_sql_and_full_filestore_baseline_queried": False,
        "reclassification_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public_report = {
        "schema": SCHEMA,
        "status": "complete_actor_control_audited_after_lease_release_reclassification_pending",
        "old_source_revision": OLD_SOURCE_REVISION,
        "old_source_freeze_sha256": private_report["old_source_freeze_sha256"],
        "old_private_plan_sha256": private_report["old_private_plan_sha256"],
        "batch_intent_sha256": private_report["batch_intent_sha256"],
        "journal_sha256": private_report["journal_sha256"],
        "journal_tail_sha256": private_report["journal_tail_sha256"],
        "old_attempt_sha256": private_report["old_attempt_sha256"],
        "private_incident_audit_sha256":
            protocol.digest(protocol.canonical(private_report)),
        "saved_actor_positive_reward": derived["independent_positive_reward"],
        "saved_wrong_object_reward": derived["independent_wrong_object_reward"],
        "saved_full_pre_web_filestore_reset_exact": True,
        "saved_protected_post_web_sources_equal": True,
        "source_visual_review_pending": True,
        "original_case_failed_journal_row_retained": True,
        "current_live_sql_and_full_filestore_baseline_queried": False,
        "reclassification_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
        "incident_auditor_sha256": protocol.digest(Path(__file__).read_bytes()),
    }
    return private_report, public_report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--worker-private", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    parser.add_argument("--old-source-freeze", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        private, public = audit(
            repo=args.repo, run_dir=args.run_dir,
            worker_private=args.worker_private,
            old_private_plan=args.old_private_plan,
            old_public_plan=args.old_public_plan,
            old_source_freeze=args.old_source_freeze)
        protocol.write_new(args.private_out, private, private=True)
        protocol.write_new(args.public_out, public, private=False)
    except Exception as error:
        print(json.dumps({"schema": SCHEMA,
                          "status": "incident_audit_refused",
                          "error_type": type(error).__name__,
                          "official_final_tasks_admitted": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(public, sort_keys=True))
