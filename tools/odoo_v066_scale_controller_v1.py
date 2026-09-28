"""Resumable evaluator-only original Odoo v0.6.6 remaining-train/selection/final GUI controls.

The runner is disabled without --execute and an exact pre-result source freeze.
Each task gets a fresh immutable intent before Docker, a fresh isolated restore,
positive source/GUI repair, wrong-object negative, saved SQL/physical source
readback, and exact cold reset. It never samples a model or emits SFT data.
A partial or failed task blocks resume; no automatic replay exists.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_scale_recipes_v1 as recipes
from tools import record_odoo_v066_train_gui_v1 as train_recorder


LEASE_OPERATION = "v066_scale_gui"
CASE_STATUS = "raw_gui_positive_negative_reset_complete_source_review_pending"
INTENT_SCHEMA = "envloop-odoo-v066-scale-case-intent-v1"
JOURNAL_SCHEMA = "envloop-odoo-v066-scale-control-journal-event-v1"
TRACE_SCHEMA = "envloop-odoo-v066-gui-control-trace-v1"
STAGES = ("pre_restore", "source_observed", "positive_reload",
          "positive_sql", "negative_reload", "negative_sql", "post_restore")


class ScaleControlError(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ScaleControlError(reason)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save(path: Path, value: object) -> dict:
    return train_recorder._artifact(path.parent, path.name, value)


def _event(path: Path, raw: dict) -> str:
    previous = read_journal(path)[1]
    count = read_journal(path)[2]
    payload = {"schema": JOURNAL_SCHEMA, "sequence": count,
               "previous_sha256": previous, **raw}
    row_hash = protocol.digest(protocol.canonical(payload))
    line = protocol.canonical({**payload, "row_sha256": row_hash})
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    return row_hash


def read_journal(path: Path) -> tuple[list[dict], str, int]:
    if not path.exists():
        return [], "0" * 64, 0
    protocol._private(path)
    rows = []
    previous = "0" * 64
    for sequence, line in enumerate(path.read_bytes().splitlines()):
        try:
            row = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ScaleControlError("scale_journal_invalid_json") from None
        row_hash = row.pop("row_sha256", None)
        require(row.get("schema") == JOURNAL_SCHEMA and
                row.get("sequence") == sequence and
                row.get("previous_sha256") == previous and
                row_hash == protocol.digest(protocol.canonical(row)),
                "scale_journal_hash_chain_changed")
        row["row_sha256"] = row_hash
        rows.append(row)
        previous = row_hash
    return rows, previous, len(rows)


def next_case_index(run_dir: Path, plan: dict) -> int:
    rows, _last, _count = read_journal(run_dir / "journal.private.jsonl")
    completed = 0
    pending = None
    failed = None
    for event in rows:
        kind = event.get("event")
        ordinal = event.get("ordinal")
        require(type(ordinal) is int and 0 <= ordinal < plan["task_count"],
                "scale_journal_ordinal_invalid")
        task = plan["tasks"][ordinal]
        require(event.get("task_id") == task["task_id"] and
                event.get("package_sha256") == task["package_sha256"],
                "scale_journal_task_identity_changed")
        if kind == "case_started":
            require(pending is None and failed is None and
                    ordinal == completed and
                    event.get("attempt_dir") == f"attempt-{ordinal:03d}",
                    "scale_journal_started_out_of_order")
            pending = event
        elif kind == "case_completed":
            require(pending is not None and ordinal == completed and
                    event.get("attempt_dir") == pending["attempt_dir"],
                    "scale_journal_completion_without_start")
            receipt = run_dir / pending["attempt_dir"] / "attempt.private.json"
            protocol._private(receipt)
            require(protocol.digest(receipt.read_bytes()) ==
                    event.get("attempt_receipt_sha256"),
                    "scale_completed_case_receipt_changed")
            completed += 1
            pending = None
        elif kind == "case_failed":
            require(pending is not None and failed is None and
                    ordinal == completed and
                    event.get("attempt_dir") == pending["attempt_dir"],
                    "scale_failed_case_without_start")
            failed = event
            pending = None
        elif kind == "case_reclassified_after_lease_release":
            require(failed is not None and pending is None and
                    ordinal == completed and
                    event.get("attempt_dir") == failed["attempt_dir"],
                    "scale_reclassification_without_retained_failure")
            authority_path = run_dir / "reclassification.private.json"
            authority = protocol.private_json(authority_path)
            receipt_path = (run_dir / failed["attempt_dir"] /
                            "attempt.private.json")
            protocol._private(receipt_path)
            require(authority.get("schema") ==
                    "envloop-odoo-v066-manual-lease-reclassification-v1" and
                    authority.get("status") ==
                    "approved_after_current_live_baseline_and_post_lease_audit" and
                    authority.get("ordinal") == ordinal and
                    authority.get("task_id") == task["task_id"] and
                    authority.get("package_sha256") == task["package_sha256"] and
                    authority.get("new_private_plan_sha256") ==
                    protocol.digest(protocol.canonical(plan)) and
                    authority.get("old_attempt_sha256") ==
                    protocol.digest(receipt_path.read_bytes()) and
                    event.get("authority_sha256") ==
                    protocol.digest(authority_path.read_bytes()) and
                    event.get("attempt_receipt_sha256") ==
                    authority["old_attempt_sha256"],
                    "scale_reclassification_authority_or_saved_attempt_invalid")
            baseline_path = run_dir / "current-baseline-check.private.json"
            baseline = protocol.private_json(baseline_path)
            sql_path = run_dir / "current-baseline-sql.private.json"
            filestore_path = run_dir / "current-baseline-filestore.private.json"
            protocol._private(sql_path)
            protocol._private(filestore_path)
            require(authority.get("current_baseline_check_sha256") ==
                    protocol.digest(baseline_path.read_bytes()) and
                    baseline.get("schema") ==
                    "envloop-odoo-v066-current-baseline-check-v1" and
                    baseline.get("status") ==
                    "current_sql_and_full_filestore_equal_frozen_baseline" and
                    baseline.get("sql_snapshot_sha256") ==
                    protocol.digest(sql_path.read_bytes()) and
                    baseline.get("filestore_manifest_sha256") ==
                    protocol.digest(filestore_path.read_bytes()) and
                    baseline.get("original_service_state_restored") is True and
                    baseline.get("current_baseline_checked_after_old_lease_release")
                    is True and
                    baseline.get("official_final_tasks_admitted") == 0,
                    "scale_reclassification_current_baseline_missing")
            completed += 1
            failed = None
        else:
            raise ScaleControlError("scale_journal_event_unknown")
    require(pending is None, "scale_partial_case_requires_manual_reconciliation")
    require(failed is None, "scale_failed_case_requires_manual_reconciliation")
    return completed


class HoldoutJournal(train_recorder.ActionJournal):
    """Keep raw evaluator actions, never build train/SFT material."""

    def act(self, *args, **kwargs):
        frame = super().act(*args, **kwargs)
        self.sft.clear()
        return frame


def _preflight(*, split: str, worker_dir: Path, private_plan_path: Path,
               public_plan_path: Path, source_freeze_path: Path,
               run_dir: Path, resume: bool) -> tuple[dict, Path]:
    require(split in protocol.SPLITS, "scale_split_invalid")
    worker = Path(worker_dir).resolve()
    require(worker.name == split and
            os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "scale_original_worker_not_selected")
    private = protocol._worker_split(worker, split)
    plan = protocol.validate_split_plan(
        split=split, private_path=private_plan_path,
        public_path=public_plan_path,
        source_freeze_path=source_freeze_path)
    root = private / "v066_scale_controls"
    require(run_dir.parent.resolve() == root.resolve() and
            not run_dir.is_symlink(), "scale_run_directory_unsafe")
    require((run_dir.is_dir() and resume) or
            (not run_dir.exists() and not resume),
            "scale_resume_flag_or_run_directory_invalid")
    world = protocol.private_json(private / "partition_cases.json")
    source_hashes = protocol.private_json(private / "source_hashes.json")
    checkpoint = protocol.private_json(private / "checkpoint_receipt.json")
    require(world.get("split") == split and
            len(source_hashes) == plan["world_case_count"] and
            checkpoint.get("db_sha256") == plan["checkpoint"]["db_sha256"] and
            checkpoint.get("filestore_sha256") ==
            plan["checkpoint"]["filestore_sha256"] and
            protocol.digest((private / "baseline.pgcustom").read_bytes()) ==
            checkpoint["db_sha256"] and
            protocol.digest((private / "baseline-filestore.tgz").read_bytes()) ==
            checkpoint["filestore_sha256"],
            "scale_worker_source_or_checkpoint_changed")
    by_id = {case["id"]: (family, case)
             for family in protocol.FAMILIES
             for case in world["cases"][family]}
    require(len(by_id) == plan["world_case_count"],
            "scale_private_case_count_changed")
    from enterprise_fallback.odoo18.partition_factory import source_asset
    for row in plan["tasks"]:
        family, case = by_id[row["task_id"]]
        asset = source_asset(case, world)
        package_sha = protocol.digest(
            json.dumps(case, sort_keys=True).encode() + b"\n" + asset)
        require(family == row["family"] and
                source_hashes[row["task_id"]] ==
                row["source_asset_sha256"] == protocol.digest(asset) and
                package_sha == row["package_sha256"] and
                protocol.digest(case["prompt"].encode()) ==
                row["visible_instruction_sha256"],
                "scale_private_case_binding_changed")
    return plan, private


def _modules(worker: Path):
    source_dir = protocol.ROOT / "enterprise_fallback/odoo18"
    for name in ("factory", "gui_controls", "reset", "verify", "worker_lease"):
        loaded = sys.modules.get(name)
        require(loaded is None or Path(loaded.__file__).resolve() ==
                source_dir / (name + ".py"),
                "scale_odoo_module_identity_conflict")
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    import factory
    import gui_controls
    import reset
    import verify
    import worker_lease
    require(factory.HERE == worker and factory.PRIVATE == worker / "private" and
            gui_controls.PRIVATE == worker / "private" and
            reset.PRIVATE == worker / "private" and
            verify.PRIVATE == worker / "private" and
            worker_lease.PRIVATE == worker / "private" and
            factory.local_config().get("ODOO_PARTITION") == worker.name,
            "scale_original_module_boundary_invalid")
    return factory, gui_controls, reset, verify, worker_lease


def _capture(out: Path, name: str, page) -> dict:
    return _save(out / name, page.screenshot(type="png"))


def _case_evidence(*, run_dir: Path, ordinal: int, row: dict,
                   case: dict, wrong: dict, family: str,
                   modules) -> dict:
    from playwright.sync_api import sync_playwright
    from enterprise_fallback.odoo18.odoo_v066_train_adapter import (
        OdooV066TrainAdapter, VIEWPORT)
    factory, gui_controls, reset, verify, _lease = modules
    private = factory.PRIVATE
    attempt = run_dir / f"attempt-{ordinal:03d}"
    require(not attempt.exists(), "scale_attempt_refuses_reuse")
    attempt.mkdir(mode=0o700)
    _save(attempt / "intent.private.json", {
        "schema": INTENT_SCHEMA,
        "status": "durable_before_first_docker_or_gui_action",
        "split": factory.local_config()["ODOO_PARTITION"],
        "task_id": row["task_id"],
        "package_sha256": row["package_sha256"],
        "task_binding_sha256": row["task_binding_sha256"],
        "source_freeze_sha256": row["source_freeze_sha256"],
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
        "started_at_utc": utc(),
    })
    started = utc()
    start_clock = time.monotonic()
    running_before: set[str] = set()
    services_ready = False
    browser = None
    journal = None
    failure = None
    failure_stage = None
    receipt_result = None
    refs = {}
    stamps = {}
    reset_exact = False
    services_restored = False
    try:
        running_before = train_recorder._running(factory.HERE)
        if not {"db", "web"} <= running_before:
            train_recorder._compose(factory.HERE, "up", "-d", "db", "web")
        services_ready = True
        refs["pre_restore"] = _save(attempt / "pre_restore.json", reset.restore())
        stamps["pre_restore"] = utc()
        baseline = verify.snapshot()
        refs["baseline_sql"] = _save(attempt / "baseline_sql.json", baseline)
        require(baseline == protocol.private_json(private / "baseline_snapshot.json") and
                verify.score(case["id"])["reward"] == 0.0,
                "scale_unsolved_exact_baseline_missing")
        credentials = protocol.private_json(private / "actor_credentials.json")
        config = factory.local_config()
        volume = config["ODOO_PROJECT"] + "_filestore"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport=VIEWPORT)
            gui_controls.browser_login(page, int(config["ODOO_PORT"]),
                                       credentials["password"],
                                       credentials["login"])
            page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}" +
                      recipes.ROUTES[family])
            adapter = OdooV066TrainAdapter(
                page, task_id=case["id"],
                task_binding_sha256=row["package_sha256"],
                instruction=case["prompt"])
            journal = HoldoutJournal(adapter, page, attempt)
            failure_stage = "source_gui"
            source_frame, source_label = recipes.show_source(
                page, journal, family, case, int(config["ODOO_PORT"]))
            refs["source_frame"] = source_frame
            refs["source_evidence"] = _save(attempt / "source_evidence.json", {
                "schema": "envloop-odoo-v066-native-source-presentation-v1",
                "task_id": case["id"],
                "source_asset_sha256": row["source_asset_sha256"],
                "source_label": source_label,
                "source_frame_sha256": source_frame["sha256"],
                "source_opened_via_v066_gui_actions": True,
            })
            stamps["source_observed"] = utc()
            failure_stage = "positive_gui"
            recipes.apply_positive(page, journal, family,
                                   case, int(config["ODOO_PORT"]))
            page.reload()
            refs["positive_reload_frame"] = _capture(
                attempt, "positive_reload_frame.png", page)
            stamps["positive_reload"] = utc()
            refs["positive_sql"] = _save(
                attempt / "positive_sql.json", verify.snapshot())
            refs["positive_filestore"] = _save(
                attempt / "positive_filestore.json",
                reset.filestore_manifest(volume))
            refs["positive_store_paths"] = _save(
                attempt / "positive_store_paths.json",
                verify.attachment_store_paths(baseline))
            positive = verify.score(case["id"])
            _save(attempt / "online_positive_score.private.json", positive)
            require(positive["reward"] == 1.0 and
                    positive["difference_codes"] == [],
                    "scale_positive_saved_state_failed")
            stamps["positive_sql"] = utc()
            failure_stage = "negative_gui"
            recipes.apply_negative(page, journal, family,
                                   wrong, int(config["ODOO_PORT"]))
            page.reload()
            refs["negative_reload_frame"] = _capture(
                attempt, "negative_reload_frame.png", page)
            stamps["negative_reload"] = utc()
            refs["negative_sql"] = _save(
                attempt / "negative_sql.json", verify.snapshot())
            refs["negative_filestore"] = _save(
                attempt / "negative_filestore.json",
                reset.filestore_manifest(volume))
            refs["negative_store_paths"] = _save(
                attempt / "negative_store_paths.json",
                verify.attachment_store_paths(baseline))
            negative = verify.score(case["id"])
            _save(attempt / "online_negative_score.private.json", negative)
            from enterprise_fallback.odoo18.sweep_partition import NEGATIVE_CODES
            require(negative["reward"] == 0.0 and
                    negative["difference_codes"] ==
                    [NEGATIVE_CODES[family]],
                    "scale_wrong_object_negative_failed")
            stamps["negative_sql"] = utc()
            browser.close()
            browser = None
    except BaseException as error:
        failure = error
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if services_ready:
            try:
                post = reset.restore()
                refs["post_restore"] = _save(attempt / "post_restore.json", post)
                restored = verify.snapshot()
                refs["restored_sql"] = _save(attempt / "restored_sql.json", restored)
                config = factory.local_config()
                post_files = reset.filestore_manifest(
                    config["ODOO_PROJECT"] + "_filestore")
                refs["restored_filestore"] = _save(
                    attempt / "restored_filestore.json", post_files)
                baseline = protocol.private_json(private / "baseline_snapshot.json")
                frozen_files = protocol.private_json(
                    private / "baseline-filestore-manifest.json")
                reset_exact = bool(
                    post["business_snapshot_equal"] and
                    post["physical_filestore_equal_before_web_restart"] and
                    restored == baseline and
                    verify.protected_source_file_differences(
                        baseline, frozen_files, post_files) == [])
                stamps["post_restore"] = utc()
            except BaseException as error:
                if failure is None:
                    failure = error
                    failure_stage = "post_restore"
            try:
                if "web" not in running_before:
                    train_recorder._compose(factory.HERE, "stop", "web")
                if "db" not in running_before:
                    train_recorder._compose(factory.HERE, "stop", "db")
                services_restored = (
                    train_recorder._running(factory.HERE) == running_before)
            except BaseException as error:
                if failure is None:
                    failure = error
                    failure_stage = "service_restore"
        if journal is not None:
            refs["gui_trace"] = _save(attempt / "gui_trace.json", {
                "schema": TRACE_SCHEMA,
                "task_binding_sha256": row["task_binding_sha256"],
                "actions": journal.trace,
                "pre_intent_rejections": journal.pre_intent_rejections,
                "sft_examples_written": 0,
            })
        if not reset_exact or not services_restored:
            if failure is None:
                failure = ScaleControlError("scale_reset_or_service_state_inexact")
                failure_stage = "post_restore"
        if time.monotonic() - start_clock > 720 and failure is None:
            failure = ScaleControlError("scale_task_wall_budget_exceeded")
            failure_stage = "wall_budget"
        if failure is None:
            required = {"pre_restore", "baseline_sql", "source_frame",
                        "source_evidence", "positive_reload_frame",
                        "positive_sql", "positive_filestore",
                        "positive_store_paths", "negative_reload_frame",
                        "negative_sql", "negative_filestore",
                        "negative_store_paths", "post_restore",
                        "restored_sql", "restored_filestore", "gui_trace"}
            if set(refs) != required or set(stamps) != set(STAGES):
                failure = ScaleControlError("scale_raw_evidence_incomplete")
                failure_stage = "final_evidence"
        if failure is None:
            receipt = {
                "schema": protocol.CASE_SCHEMA,
                "status": CASE_STATUS,
                "split": row["split"],
                "family": family,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "task_binding_sha256": row["task_binding_sha256"],
                "source_freeze_sha256": row["source_freeze_sha256"],
                "plan_sha256": row["cell_plan_sha256"],
                "ratification_sha256": protocol.RATIFICATION_SHA,
                "worker_pid": os.getpid(),
                "started_at_utc": started,
                "finished_at_utc": utc(),
                "lease_operation": LEASE_OPERATION,
                "stage_timestamps": stamps,
                "refs": refs,
                "service_state_restored_receipt": services_restored,
                "official_final_tasks_admitted": 0,
                "model_attempts": 0,
            }
            _save(attempt / "attempt.private.json", receipt)
            receipt_result = receipt
        else:
            _save(attempt / "failure.private.json", {
            "schema": protocol.CASE_SCHEMA,
            "status": "failed_preserve_original_attempt_manual_review_required",
            "stage": failure_stage,
            "error_type": type(failure).__name__,
            "error_code": getattr(failure, "code", None),
            "reset_exact": reset_exact,
            "services_restored": services_restored,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
            })
    if receipt_result is not None and failure is None:
        return receipt_result
    raise ScaleControlError("scale_case_failed_no_automatic_replay") from failure


@contextmanager
def _run_lock(root: Path):
    root.mkdir(mode=0o700, exist_ok=True)
    protocol._private(root, directory=True)
    lock_path = root / "scale-run-coordinator.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ScaleControlError("scale_run_coordinator_busy") from None
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def verify_reclassified_current_baseline(run_dir: Path,
                                         worker_private: Path) -> None:
    sql = protocol.private_json(run_dir / "current-baseline-sql.private.json")
    files = protocol.private_json(
        run_dir / "current-baseline-filestore.private.json")
    frozen_sql = protocol.private_json(worker_private / "baseline_snapshot.json")
    frozen_files = protocol.private_json(
        worker_private / "baseline-filestore-manifest.json")
    require(sql == frozen_sql and files == frozen_files,
            "scale_reclassified_current_baseline_artifacts_changed")


def _old_plan_adoption(*, adoption_path: Path | None,
                       old_private_plan_path: Path | None,
                       old_source_freeze_path: Path | None,
                       incident_public_path: Path | None,
                       current_plan: dict,
                       current_source_freeze_path: Path) -> tuple[dict, dict]:
    require(all(path is not None for path in (
        adoption_path, old_private_plan_path, old_source_freeze_path,
        incident_public_path)),
        "scale_old_batch_requires_source_adoption")
    adoption = protocol.private_json(adoption_path)
    old = protocol.private_json(old_private_plan_path)
    old_freeze = protocol.public_json(old_source_freeze_path)
    new_freeze = protocol.public_json(current_source_freeze_path)
    incident = protocol.public_json(incident_public_path)
    require(adoption.get("schema") ==
            "envloop-odoo-v066-lease-audit-source-adoption-v1" and
            adoption.get("status") == "prepared_for_manual_live_baseline_reconciliation" and
            adoption.get("old_private_plan_sha256") ==
            protocol.digest(old_private_plan_path.read_bytes()) and
            adoption.get("new_private_plan_sha256") ==
            protocol.digest(protocol.canonical(current_plan)) and
            adoption.get("old_source_freeze_sha256") ==
            protocol.digest(old_source_freeze_path.read_bytes()) and
            adoption.get("new_source_freeze_sha256") ==
            protocol.digest(current_source_freeze_path.read_bytes()) and
            adoption.get("incident_public_sha256") ==
            protocol.digest(incident_public_path.read_bytes()) and
            incident.get("schema") ==
            "envloop-odoo-v066-inline-lease-audit-order-incident-v1" and
            incident.get("status") ==
            "complete_actor_control_audited_after_lease_release_reclassification_pending" and
            incident.get("old_attempt_sha256") ==
            adoption.get("old_attempt_sha256") and
            old.get("tasks") == current_plan.get("tasks") and
            old.get("checkpoint") == current_plan.get("checkpoint") and
            old.get("split") == current_plan.get("split") and
            old.get("ratification_sha256") == current_plan.get("ratification_sha256") and
            old_freeze.get("ratification_sha256") ==
            new_freeze.get("ratification_sha256") ==
            protocol.RATIFICATION_SHA and
            adoption.get("official_final_tasks_admitted") == 0,
            "scale_old_new_source_adoption_invalid")
    changed = {"tools/odoo_v066_scale_protocol_v1.py",
               "tools/odoo_v066_scale_controller_v1.py",
               "tools/odoo_v066_scale_audit_v1.py",
               "tools/audit_odoo_v066_inline_lease_incident_v1.py"}
    common = set(old_freeze.get("source_sha256s", {})) - changed
    require(common and all(old_freeze["source_sha256s"][name] ==
                           new_freeze["source_sha256s"].get(name)
                           for name in common),
            "scale_actor_action_verifier_or_runtime_source_changed")
    return adoption, old


def reconcile_completed_failed_case(*, worker_dir: Path, run_dir: Path,
                                    old_private_plan_path: Path,
                                    old_source_freeze_path: Path,
                                    new_private_plan_path: Path,
                                    new_public_plan_path: Path,
                                    new_source_freeze_path: Path,
                                    incident_public_path: Path,
                                    adoption_path: Path) -> dict:
    """Explicit live baseline check; append reclassification, never replay GUI."""
    worker = Path(worker_dir).resolve()
    require(worker.name == "train" and
            os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "scale_reconcile_original_train_worker_not_selected")
    new_plan, private = _preflight(
        split="train", worker_dir=worker,
        private_plan_path=new_private_plan_path,
        public_plan_path=new_public_plan_path,
        source_freeze_path=new_source_freeze_path,
        run_dir=run_dir, resume=True)
    adoption, old_plan = _old_plan_adoption(
        adoption_path=adoption_path,
        old_private_plan_path=old_private_plan_path,
        old_source_freeze_path=old_source_freeze_path,
        incident_public_path=incident_public_path,
        current_plan=new_plan,
        current_source_freeze_path=new_source_freeze_path)
    factory, _gui, reset, verify, lease = _modules(worker)
    root = private / "v066_scale_controls"
    with _run_lock(root):
        journal_path = run_dir / "journal.private.jsonl"
        rows, previous_tail, length = read_journal(journal_path)
        require(length == 2 and
                [row.get("event") for row in rows] ==
                ["case_started", "case_failed"] and
                [row.get("ordinal") for row in rows] == [0, 0] and
                previous_tail == adoption["old_journal_tail_sha256"] and
                protocol.digest(journal_path.read_bytes()) ==
                adoption["old_journal_sha256"] and
                rows[0].get("task_id") == rows[1].get("task_id") ==
                new_plan["tasks"][0]["task_id"] and
                rows[0].get("attempt_dir") == rows[1].get("attempt_dir") ==
                "attempt-000",
                "scale_reconcile_old_failure_chain_changed")
        attempt = run_dir / "attempt-000"
        receipt_path = attempt / "attempt.private.json"
        protocol._private(receipt_path)
        require(protocol.digest(receipt_path.read_bytes()) ==
                adoption["old_attempt_sha256"] and
                not (attempt / "failure.private.json").exists(),
                "scale_reconcile_saved_actor_attempt_changed")
        from tools import odoo_v066_scale_audit_v1 as independent
        independent.audit_case(
            plan=old_plan, row=old_plan["tasks"][0],
            attempt=attempt, worker_private=private)
        require(not (run_dir / "current-baseline-check.private.json").exists()
                and not (run_dir / "reclassification.private.json").exists(),
                "scale_reconciliation_evidence_already_exists")
        running_before: set[str] = set()
        service_ready = False
        failure = None
        snapshot = files = None
        services_restored = False
        with lease.exclusive_worker_operation("v066_scale_reconcile"):
            try:
                running_before = train_recorder._running(worker)
                if "db" not in running_before:
                    train_recorder._compose(worker, "up", "-d", "db")
                service_ready = True
                snapshot = verify.snapshot()
                config = factory.local_config()
                files = reset.filestore_manifest(
                    config["ODOO_PROJECT"] + "_filestore")
            except BaseException as error:
                failure = error
            finally:
                if service_ready:
                    try:
                        if "db" not in running_before:
                            train_recorder._compose(worker, "stop", "db")
                        services_restored = (
                            train_recorder._running(worker) == running_before)
                    except BaseException as error:
                        services_restored = False
                        if failure is None:
                            failure = error
        if failure is not None:
            raise ScaleControlError(
                "scale_reconcile_current_baseline_query_failed") from failure
        baseline = protocol.private_json(private / "baseline_snapshot.json")
        frozen = protocol.private_json(
            private / "baseline-filestore-manifest.json")
        require(snapshot is not None and files is not None and
                snapshot == baseline and files == frozen and
                services_restored is True,
                "scale_current_sql_or_full_filestore_baseline_not_exact")
        sql_ref = _save(run_dir / "current-baseline-sql.private.json", snapshot)
        files_ref = _save(run_dir / "current-baseline-filestore.private.json", files)
        baseline_check = {
            "schema": "envloop-odoo-v066-current-baseline-check-v1",
            "status": "current_sql_and_full_filestore_equal_frozen_baseline",
            "sql_snapshot_sha256": sql_ref["sha256"],
            "filestore_manifest_sha256": files_ref["sha256"],
            "frozen_sql_baseline_sha256": protocol.digest(
                (private / "baseline_snapshot.json").read_bytes()),
            "frozen_filestore_manifest_sha256": protocol.digest(
                (private / "baseline-filestore-manifest.json").read_bytes()),
            "original_service_state_restored": services_restored,
            "current_baseline_checked_after_old_lease_release": True,
            "official_final_tasks_admitted": 0,
        }
        baseline_ref = _save(
            run_dir / "current-baseline-check.private.json", baseline_check)
        # Audit again outside every Odoo worker lease before adopting the case.
        independent.audit_case(
            plan=old_plan, row=old_plan["tasks"][0],
            attempt=attempt, worker_private=private)
        authority = {
            "schema": "envloop-odoo-v066-manual-lease-reclassification-v1",
            "status": "approved_after_current_live_baseline_and_post_lease_audit",
            "ordinal": 0,
            "task_id": old_plan["tasks"][0]["task_id"],
            "package_sha256": old_plan["tasks"][0]["package_sha256"],
            "old_attempt_sha256": adoption["old_attempt_sha256"],
            "old_private_plan_sha256": adoption["old_private_plan_sha256"],
            "new_private_plan_sha256": adoption["new_private_plan_sha256"],
            "old_source_freeze_sha256": adoption["old_source_freeze_sha256"],
            "new_source_freeze_sha256": adoption["new_source_freeze_sha256"],
            "incident_public_sha256": adoption["incident_public_sha256"],
            "current_baseline_check_sha256": baseline_ref["sha256"],
            "replay_of_original_gui_attempt": False,
            "original_case_failed_event_retained": True,
            "official_final_tasks_admitted": 0,
        }
        authority_ref = _save(
            run_dir / "reclassification.private.json", authority)
        new_tail = _event(journal_path, {
            "event": "case_reclassified_after_lease_release",
            "ordinal": 0,
            "task_id": authority["task_id"],
            "package_sha256": authority["package_sha256"],
            "attempt_dir": "attempt-000",
            "authority_sha256": authority_ref["sha256"],
            "attempt_receipt_sha256": authority["old_attempt_sha256"],
        })
        require(next_case_index(run_dir, new_plan) == 1,
                "scale_reclassified_chain_not_resumable")
        return {"schema": "envloop-odoo-v066-lease-reclassification-result-v1",
                "status": "old_complete_case_reclassified_without_gui_replay",
                "journal_tail_sha256": new_tail,
                "old_attempt_sha256": authority["old_attempt_sha256"],
                "current_baseline_check_sha256": baseline_ref["sha256"],
                "completed_raw_case_count": 1,
                "official_final_tasks_admitted": 0,
                "model_attempts": 0}


def _execute_case_then_audit_after_release(*, lease, run_dir: Path,
                                           ordinal: int, row: dict,
                                           case: dict, wrong: dict,
                                           family: str, modules,
                                           plan: dict, worker_private: Path) -> None:
    attempt_name = f"attempt-{ordinal:03d}"
    with lease.exclusive_worker_operation(LEASE_OPERATION):
        _event(run_dir / "journal.private.jsonl", {
            "event": "case_started", "ordinal": ordinal,
            "task_id": row["task_id"],
            "package_sha256": row["package_sha256"],
            "attempt_dir": attempt_name,
        })
        _case_evidence(
            run_dir=run_dir, ordinal=ordinal, row=row, case=case,
            wrong=wrong, family=family, modules=modules)
    # The release event must exist before the auditor checks the lease interval.
    from tools import odoo_v066_scale_audit_v1 as independent
    independent.audit_case(
        plan=plan, row=plan["tasks"][ordinal],
        attempt=run_dir / attempt_name,
        worker_private=worker_private)


def run(*, split: str, worker_dir: Path, private_plan_path: Path,
        public_plan_path: Path, source_freeze_path: Path,
        run_dir: Path, resume: bool, max_cases: int,
        adoption_path: Path | None = None,
        old_private_plan_path: Path | None = None,
        old_source_freeze_path: Path | None = None,
        incident_public_path: Path | None = None) -> dict:
    require(type(max_cases) is int and 1 <= max_cases <= 100,
            "scale_max_cases_invalid")
    plan, private = _preflight(
        split=split, worker_dir=worker_dir,
        private_plan_path=private_plan_path,
        public_plan_path=public_plan_path,
        source_freeze_path=source_freeze_path,
        run_dir=run_dir, resume=resume)
    worker = Path(worker_dir).resolve()
    factory, gui_controls, reset, verify, lease = _modules(worker)
    root = private / "v066_scale_controls"
    with _run_lock(root):
        adopted_old = None
        if not resume:
            run_dir.mkdir(mode=0o700)
            _save(run_dir / "batch-intent.private.json", {
                "schema": protocol.BATCH_SCHEMA,
                "status": "durable_before_first_original_odoo_service_call",
                "split": split,
                "private_plan_sha256": protocol.digest(private_plan_path.read_bytes()),
                "source_freeze_sha256": protocol.digest(
                    source_freeze_path.read_bytes()),
                "expected_case_count": plan["task_count"],
                "official_final_tasks_admitted": 0,
                "model_attempts": 0,
            })
        else:
            intent = protocol.private_json(run_dir / "batch-intent.private.json")
            require(intent.get("schema") == protocol.BATCH_SCHEMA and
                    intent.get("split") == split and
                    intent.get("expected_case_count") == plan["task_count"],
                    "scale_batch_intent_changed")
            current_binding = (
                intent.get("private_plan_sha256") ==
                protocol.digest(private_plan_path.read_bytes()) and
                intent.get("source_freeze_sha256") ==
                protocol.digest(source_freeze_path.read_bytes()))
            if not current_binding:
                adoption, adopted_old = _old_plan_adoption(
                    adoption_path=adoption_path,
                    old_private_plan_path=old_private_plan_path,
                    old_source_freeze_path=old_source_freeze_path,
                    incident_public_path=incident_public_path,
                    current_plan=plan,
                    current_source_freeze_path=source_freeze_path)
                require(intent.get("private_plan_sha256") ==
                        adoption["old_private_plan_sha256"] and
                        intent.get("source_freeze_sha256") ==
                        adoption["old_source_freeze_sha256"],
                        "scale_batch_intent_old_source_not_adopted")
        index = next_case_index(run_dir, plan)
        if resume and index:
            from tools import odoo_v066_scale_audit_v1 as independent
            journal_rows, _, _ = read_journal(
                run_dir / "journal.private.jsonl")
            reclassified = {event["ordinal"] for event in journal_rows
                            if event.get("event") ==
                            "case_reclassified_after_lease_release"}
            if reclassified:
                verify_reclassified_current_baseline(run_dir, private)
            for ordinal in range(index):
                audited_plan = (adopted_old if ordinal in reclassified
                                else plan)
                require(audited_plan is not None,
                        "scale_reclassified_case_old_plan_missing")
                independent.audit_case(
                    plan=audited_plan,
                    row=audited_plan["tasks"][ordinal],
                    attempt=run_dir / f"attempt-{ordinal:03d}",
                    worker_private=private)
        limit = min(plan["task_count"], index + max_cases)
        world = protocol.private_json(private / "partition_cases.json")
        by_id = {case["id"]: (family, case)
                 for family in protocol.FAMILIES
                 for case in world["cases"][family]}
        while index < limit:
            row = dict(plan["tasks"][index])
            row["source_freeze_sha256"] = plan["source_freeze_sha256"]
            row["cell_plan_sha256"] = protocol.digest(private_plan_path.read_bytes())
            attempt_name = f"attempt-{index:03d}"
            require(not (run_dir / attempt_name).exists(),
                    "scale_next_attempt_dir_exists_reconcile_first")
            family, case = by_id[row["task_id"]]
            wrong = next(candidate for candidate in world["cases"][family]
                         if candidate["id"] != case["id"])
            try:
                _execute_case_then_audit_after_release(
                    lease=lease, run_dir=run_dir, ordinal=index,
                    row=row, case=case, wrong=wrong, family=family,
                    modules=(factory, gui_controls, reset, verify, lease),
                    plan=plan, worker_private=private)
            except BaseException:
                _event(run_dir / "journal.private.jsonl", {
                    "event": "case_failed", "ordinal": index,
                    "task_id": row["task_id"],
                    "package_sha256": row["package_sha256"],
                    "attempt_dir": attempt_name,
                })
                raise
            _event(run_dir / "journal.private.jsonl", {
                "event": "case_completed", "ordinal": index,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "attempt_dir": attempt_name,
                "attempt_receipt_sha256": protocol.digest(
                    (run_dir / attempt_name / "attempt.private.json").read_bytes()),
            })
            index += 1
        return {"schema": protocol.BATCH_SCHEMA,
                "status": "raw_gui_controls_complete" if index == plan["task_count"]
                          else "raw_gui_controls_partial_resumable",
                "split": split,
                "completed_case_count": index,
                "expected_case_count": plan["task_count"],
                "official_final_tasks_admitted": 0,
                "model_attempts": 0}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    runner = sub.add_parser("run")
    runner.add_argument("--split", choices=tuple(protocol.SPLITS), required=True)
    runner.add_argument("--worker-dir", type=Path, required=True)
    runner.add_argument("--private-plan", type=Path, required=True)
    runner.add_argument("--public-plan", type=Path, required=True)
    runner.add_argument("--source-freeze", type=Path, required=True)
    runner.add_argument("--run-dir", type=Path, required=True)
    runner.add_argument("--resume", action="store_true")
    runner.add_argument("--max-cases", type=int, default=1)
    runner.add_argument("--adoption-private", type=Path)
    runner.add_argument("--old-private-plan", type=Path)
    runner.add_argument("--old-source-freeze", type=Path)
    runner.add_argument("--incident-public", type=Path)
    runner.add_argument("--execute", action="store_true")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--worker-dir", type=Path, required=True)
    reconcile.add_argument("--run-dir", type=Path, required=True)
    reconcile.add_argument("--old-private-plan", type=Path, required=True)
    reconcile.add_argument("--old-source-freeze", type=Path, required=True)
    reconcile.add_argument("--new-private-plan", type=Path, required=True)
    reconcile.add_argument("--new-public-plan", type=Path, required=True)
    reconcile.add_argument("--new-source-freeze", type=Path, required=True)
    reconcile.add_argument("--incident-public", type=Path, required=True)
    reconcile.add_argument("--adoption-private", type=Path, required=True)
    reconcile.add_argument("--execute-baseline-check", action="store_true")
    args = parser.parse_args()
    authorized = (args.execute if args.command == "run"
                  else args.execute_baseline_check)
    if not authorized:
        print(json.dumps({"schema": protocol.BATCH_SCHEMA,
                          "status": "refused_without_explicit_execute",
                          "official_final_tasks_admitted": 0,
                          "model_attempts": 0}, sort_keys=True))
        raise SystemExit(2)
    try:
        if args.command == "run":
            result = run(
                split=args.split, worker_dir=args.worker_dir,
                private_plan_path=args.private_plan,
                public_plan_path=args.public_plan,
                source_freeze_path=args.source_freeze,
                run_dir=args.run_dir, resume=args.resume,
                max_cases=args.max_cases,
                adoption_path=args.adoption_private,
                old_private_plan_path=args.old_private_plan,
                old_source_freeze_path=args.old_source_freeze,
                incident_public_path=args.incident_public)
        else:
            result = reconcile_completed_failed_case(
                worker_dir=args.worker_dir, run_dir=args.run_dir,
                old_private_plan_path=args.old_private_plan,
                old_source_freeze_path=args.old_source_freeze,
                new_private_plan_path=args.new_private_plan,
                new_public_plan_path=args.new_public_plan,
                new_source_freeze_path=args.new_source_freeze,
                incident_public_path=args.incident_public,
                adoption_path=args.adoption_private)
    except Exception as error:
        # Never put private task instructions/IDs or raw Playwright text on stdout.
        print(json.dumps({"schema": protocol.BATCH_SCHEMA,
                          "status": "stopped_preserve_private_attempt",
                          "error_type": type(error).__name__,
                          "official_final_tasks_admitted": 0,
                          "model_attempts": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))
