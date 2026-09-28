"""Read-only, field-limited public receipt for the completed Odoo train reconcile.

The reconciler already made the live SQL and full physical filestore query.
This auditor checks its saved bytes, old/new source lineage, retained failure,
and append-only journal. It does not query live Odoo, replay a GUI, or dispatch
any model/provider work. No task identity or private path enters the result.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-odoo-v066-train-post-live-reclassification-public-v1"
OLD_REVISION = "f5fdd5d08646f72fbe4acf45188f76f6fc33308c"
CORRECTED_REVISION = "19d9ce9b1aaeca86266ec0d1bb18b3ef744c50ae"
EVENTS = ("case_started", "case_failed",
          "case_reclassified_after_lease_release")


class ReclassificationAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ReclassificationAuditError(code)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def _private(path: Path, *, directory: bool = False) -> None:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "post_reclass_private_path_missing_or_permissive")


def _json(path: Path, *, private: bool = True) -> dict:
    if private:
        _private(path)
    else:
        require(path.is_file() and not path.is_symlink(),
                "post_reclass_public_reference_missing")
    require(path.stat().st_size <= 16_000_000,
            "post_reclass_json_oversized")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReclassificationAuditError("post_reclass_json_invalid") from None
    require(type(value) is dict, "post_reclass_json_invalid")
    return value


def _source_at_revision(revision: str, freeze: dict) -> None:
    """Prove the frozen sources against committed bytes, not today's edits."""
    hashes = freeze.get("source_sha256s")
    require(type(hashes) is dict and hashes and
            all(type(name) is str and type(value) is str and
                re.fullmatch(r"[0-9a-f]{64}", value) for name, value in hashes.items()),
            "post_reclass_source_freeze_invalid")
    for name, expected in hashes.items():
        require(not name.startswith("/") and
                all(part not in ("", ".", "..") for part in name.split("/")),
                "post_reclass_source_path_unsafe")
        found = subprocess.run(
            ["git", "show", f"{revision}:{name}"], cwd=ROOT,
            capture_output=True, check=False)
        require(found.returncode == 0 and digest(found.stdout) == expected,
                "post_reclass_historical_source_blob_changed")


def _journal(path: Path, *, old_journal_sha: str,
             old_tail_sha: str, task: dict, attempt_sha: str,
             authority_sha: str) -> tuple[str, str]:
    _private(path)
    lines = path.read_bytes().splitlines(keepends=True)
    require(len(lines) == 3 and all(line.endswith(b"\n") for line in lines),
            "post_reclass_journal_event_count_invalid")
    require(digest(b"".join(lines[:2])) == old_journal_sha,
            "post_reclass_retained_old_journal_changed")
    previous = "0" * 64
    rows = []
    for sequence, line in enumerate(lines):
        try:
            row = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ReclassificationAuditError(
                "post_reclass_journal_json_invalid") from None
        require(type(row) is dict, "post_reclass_journal_json_invalid")
        claimed = row.pop("row_sha256", None)
        require(row.get("schema") ==
                "envloop-odoo-v066-scale-control-journal-event-v1" and
                row.get("sequence") == sequence and
                row.get("previous_sha256") == previous and
                claimed == digest(canonical(row)),
                "post_reclass_journal_hash_chain_invalid")
        require(row.get("event") == EVENTS[sequence] and
                row.get("ordinal") == 0 and
                row.get("task_id") == task.get("task_id") and
                row.get("package_sha256") == task.get("package_sha256") and
                row.get("attempt_dir") == "attempt-000",
                "post_reclass_journal_identity_or_order_invalid")
        row["row_sha256"] = claimed
        rows.append(row)
        previous = claimed
    require(rows[1]["row_sha256"] == old_tail_sha and
            rows[2].get("authority_sha256") == authority_sha and
            rows[2].get("attempt_receipt_sha256") == attempt_sha,
            "post_reclass_journal_reclassification_unbound")
    return digest(b"".join(lines)), previous


def _baseline(run_dir: Path, worker_private: Path,
              checkpoint: dict) -> str:
    check_path = run_dir / "current-baseline-check.private.json"
    sql_path = run_dir / "current-baseline-sql.private.json"
    files_path = run_dir / "current-baseline-filestore.private.json"
    frozen_sql_path = worker_private / "baseline_snapshot.json"
    frozen_files_path = worker_private / "baseline-filestore-manifest.json"
    check = _json(check_path)
    sql = _json(sql_path)
    files = _json(files_path)
    frozen_sql = _json(frozen_sql_path)
    frozen_files = _json(frozen_files_path)
    require(check.get("schema") ==
            "envloop-odoo-v066-current-baseline-check-v1" and
            check.get("status") ==
            "current_sql_and_full_filestore_equal_frozen_baseline" and
            check.get("sql_snapshot_sha256") == digest(sql_path.read_bytes()) and
            check.get("filestore_manifest_sha256") ==
            digest(files_path.read_bytes()) and
            check.get("frozen_sql_baseline_sha256") ==
            digest(frozen_sql_path.read_bytes()) ==
            checkpoint.get("baseline_snapshot_sha256") and
            check.get("frozen_filestore_manifest_sha256") ==
            digest(frozen_files_path.read_bytes()) ==
            checkpoint.get("baseline_filestore_manifest_sha256") and
            sql == frozen_sql and files == frozen_files and
            check.get("original_service_state_restored") is True and
            check.get("current_baseline_checked_after_old_lease_release")
            is True and check.get("official_final_tasks_admitted") == 0,
            "post_reclass_current_baseline_not_bound_or_exact")
    return digest(check_path.read_bytes())


def audit(*, run_dir: Path, worker_private: Path,
          old_private_plan: Path, new_private_plan: Path,
          adoption_private: Path, incident_private: Path,
          incident_public: Path, old_source_freeze: Path,
          new_source_freeze: Path) -> dict:
    run_dir, worker_private = Path(run_dir), Path(worker_private)
    _private(run_dir, directory=True)
    _private(worker_private, directory=True)
    require(worker_private.name == "private" and
            worker_private.parent.name == "train" and
            run_dir.parent.resolve() ==
            (worker_private / "v066_scale_controls").resolve(),
            "post_reclass_original_train_run_not_selected")
    old = _json(old_private_plan)
    new = _json(new_private_plan)
    adoption = _json(adoption_private)
    incident_raw = _json(incident_private)
    incident = _json(incident_public, private=False)
    old_freeze = _json(old_source_freeze, private=False)
    new_freeze = _json(new_source_freeze, private=False)
    old_plan_sha = digest(old_private_plan.read_bytes())
    new_plan_sha = digest(new_private_plan.read_bytes())
    old_freeze_sha = digest(old_source_freeze.read_bytes())
    new_freeze_sha = digest(new_source_freeze.read_bytes())
    incident_sha = digest(incident_public.read_bytes())
    require(old.get("schema") == new.get("schema") ==
            "envloop-odoo-v066-split-gui-control-plan-v1" and
            old.get("split") == new.get("split") == "train" and
            old.get("task_count") == new.get("task_count") == 19 and
            old.get("tasks") == new.get("tasks") and
            old.get("checkpoint") == new.get("checkpoint") and
            old.get("source_freeze_sha256") == old_freeze_sha and
            new.get("source_freeze_sha256") == new_freeze_sha and
            old.get("source_sha256s") == old_freeze.get("source_sha256s") and
            new.get("source_sha256s") == new_freeze.get("source_sha256s") and
            old.get("ratification_sha256") ==
            new.get("ratification_sha256") ==
            old_freeze.get("ratification_sha256") ==
            new_freeze.get("ratification_sha256") and
            old_freeze.get("schema") == new_freeze.get("schema") ==
            "envloop-odoo-v066-scale-gui-source-freeze-v1" and
            incident.get("old_source_revision") == OLD_REVISION and
            new_freeze.get("old_source_freeze_sha256") == old_freeze_sha and
            new_freeze.get("incident_public_sha256") == incident_sha,
            "post_reclass_old_new_source_or_plan_unbound")
    _source_at_revision(OLD_REVISION, old_freeze)
    _source_at_revision(CORRECTED_REVISION, new_freeze)
    require(adoption.get("schema") ==
            "envloop-odoo-v066-lease-audit-source-adoption-v1" and
            adoption.get("status") ==
            "prepared_for_manual_live_baseline_reconciliation" and
            adoption.get("old_private_plan_sha256") == old_plan_sha and
            adoption.get("new_private_plan_sha256") == new_plan_sha and
            adoption.get("old_source_freeze_sha256") == old_freeze_sha and
            adoption.get("new_source_freeze_sha256") == new_freeze_sha and
            adoption.get("incident_public_sha256") == incident_sha and
            adoption.get("incident_private_sha256") ==
            digest(incident_private.read_bytes()) and
            adoption.get("original_case_failed_event_retained") is True and
            adoption.get("gui_replay_authorized") is False and
            adoption.get("actor_action_verifier_runtime_bytes_identical")
            is True and
            adoption.get("current_live_baseline_query_required_before_reclassification")
            is True and
            adoption.get("official_final_tasks_admitted") == 0 and
            adoption.get("model_attempts") == 0 and
            incident.get("schema") ==
            "envloop-odoo-v066-inline-lease-audit-order-incident-v1" and
            incident.get("status") ==
            "complete_actor_control_audited_after_lease_release_reclassification_pending" and
            incident.get("reclassification_authorized") is False and
            incident.get("current_live_sql_and_full_filestore_baseline_queried")
            is False and
            incident.get("private_incident_audit_sha256") ==
            digest(canonical(incident_raw)) and
            incident.get("old_attempt_sha256") ==
            adoption.get("old_attempt_sha256") and
            incident.get("journal_sha256") ==
            adoption.get("old_journal_sha256") and
            incident.get("journal_tail_sha256") ==
            adoption.get("old_journal_tail_sha256"),
            "post_reclass_adoption_or_incident_unbound")
    old_case_audit = incident_raw.get("independent_case_audit")
    require(type(old_case_audit) is dict and
            old_case_audit.get("private_attempt_sha256") ==
            adoption["old_attempt_sha256"] and
            old_case_audit.get("independent_baseline_reward") == 0.0 and
            old_case_audit.get("independent_positive_reward") == 1.0 and
            old_case_audit.get("independent_wrong_object_reward") == 0.0 and
            old_case_audit.get("full_pre_web_filestore_reset_exact") is True and
            old_case_audit.get("protected_post_web_source_bytes_equal") is True and
            old_case_audit.get("source_visual_review_pending") is True,
            "post_reclass_saved_attempt_audit_unbound")
    attempt_path = run_dir / "attempt-000" / "attempt.private.json"
    _private(attempt_path)
    intent_path = run_dir / "batch-intent.private.json"
    _private(intent_path)
    require(digest(attempt_path.read_bytes()) ==
            adoption["old_attempt_sha256"] and
            not (run_dir / "attempt-000" / "failure.private.json").exists() and
            digest(intent_path.read_bytes()) ==
            adoption.get("old_batch_intent_sha256"),
            "post_reclass_original_attempt_or_intent_changed")
    check_sha = _baseline(run_dir, worker_private, new["checkpoint"])
    authority_path = run_dir / "reclassification.private.json"
    authority = _json(authority_path)
    authority_sha = digest(authority_path.read_bytes())
    task = old["tasks"][0]
    require(authority.get("schema") ==
            "envloop-odoo-v066-manual-lease-reclassification-v1" and
            authority.get("status") ==
            "approved_after_current_live_baseline_and_post_lease_audit" and
            authority.get("ordinal") == 0 and
            authority.get("task_id") == task["task_id"] and
            authority.get("package_sha256") == task["package_sha256"] and
            authority.get("old_attempt_sha256") ==
            adoption["old_attempt_sha256"] and
            authority.get("old_private_plan_sha256") == old_plan_sha and
            authority.get("new_private_plan_sha256") == new_plan_sha and
            authority.get("old_source_freeze_sha256") == old_freeze_sha and
            authority.get("new_source_freeze_sha256") == new_freeze_sha and
            authority.get("incident_public_sha256") == incident_sha and
            authority.get("current_baseline_check_sha256") == check_sha and
            authority.get("replay_of_original_gui_attempt") is False and
            authority.get("original_case_failed_event_retained") is True and
            authority.get("official_final_tasks_admitted") == 0,
            "post_reclass_authority_unbound")
    journal_sha, tail = _journal(
        run_dir / "journal.private.jsonl",
        old_journal_sha=adoption["old_journal_sha256"],
        old_tail_sha=adoption["old_journal_tail_sha256"],
        task=task, attempt_sha=adoption["old_attempt_sha256"],
        authority_sha=authority_sha)
    return {
        "schema": SCHEMA,
        "status": "completed_train_raw_case_reclassified_after_live_baseline_check",
        "split": "train",
        "completed_raw_case_count": 1,
        "current_sql_equal_frozen_baseline": True,
        "current_full_physical_filestore_equal_frozen_baseline": True,
        "original_service_state_restored": True,
        "original_case_failed_event_retained": True,
        "original_gui_attempt_replayed": False,
        "saved_attempt_positive_reward": 1.0,
        "saved_attempt_wrong_object_reward": 0.0,
        "saved_attempt_full_reset_exact": True,
        "source_visual_review_pending": True,
        "old_source_revision": OLD_REVISION,
        "corrected_source_revision": CORRECTED_REVISION,
        "old_source_freeze_sha256": old_freeze_sha,
        "corrected_source_freeze_sha256": new_freeze_sha,
        "old_private_plan_sha256": old_plan_sha,
        "corrected_private_plan_sha256": new_plan_sha,
        "incident_public_sha256": incident_sha,
        "private_adoption_sha256": digest(adoption_private.read_bytes()),
        "old_attempt_sha256": adoption["old_attempt_sha256"],
        "current_baseline_check_sha256": check_sha,
        "private_reclassification_authority_sha256": authority_sha,
        "journal_sha256": journal_sha,
        "journal_tail_sha256": tail,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run_dir", "worker_private", "old_private_plan",
                 "new_private_plan", "adoption_private", "incident_private",
                 "incident_public", "old_source_freeze", "new_source_freeze"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path,
                            required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(**{name: getattr(args, name) for name in (
            "run_dir", "worker_private", "old_private_plan",
            "new_private_plan", "adoption_private", "incident_private",
            "incident_public", "old_source_freeze", "new_source_freeze")})
        raw = canonical(result)
        descriptor = os.open(args.public_out,
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except (ReclassificationAuditError, OSError, KeyError, TypeError):
        print(json.dumps({"schema": SCHEMA,
                          "status": "post_reclassification_audit_refused",
                          "official_final_tasks_admitted": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps({"schema": result["schema"],
                      "status": result["status"],
                      "completed_raw_case_count": 1,
                      "official_final_tasks_admitted": 0}, sort_keys=True))
