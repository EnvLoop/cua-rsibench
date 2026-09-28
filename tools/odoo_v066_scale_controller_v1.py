"""Resumable evaluator-only original Odoo v0.6.6 remaining-train/selection/final GUI controls.

The runner is disabled without --execute and an exact pre-result source freeze.
Each task gets a fresh immutable intent before Docker, a fresh isolated restore,
positive source/GUI repair, wrong-object negative, saved SQL/physical source
readback, and exact cold reset. It never samples a model or emits SFT data.
A partial or failed task blocks resume; no automatic replay exists.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
            require(pending is None and ordinal == completed and
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
            require(pending is not None and ordinal == completed,
                    "scale_failed_case_without_start")
            raise ScaleControlError("scale_failed_case_requires_manual_reconciliation")
        else:
            raise ScaleControlError("scale_journal_event_unknown")
    require(pending is None, "scale_partial_case_requires_manual_reconciliation")
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


def run(*, split: str, worker_dir: Path, private_plan_path: Path,
        public_plan_path: Path, source_freeze_path: Path,
        run_dir: Path, resume: bool, max_cases: int) -> dict:
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
    root.mkdir(mode=0o700, exist_ok=True)
    protocol._private(root, directory=True)
    with lease.exclusive_worker_operation(LEASE_OPERATION):
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
                    intent.get("private_plan_sha256") ==
                    protocol.digest(private_plan_path.read_bytes()) and
                    intent.get("source_freeze_sha256") ==
                    protocol.digest(source_freeze_path.read_bytes()),
                    "scale_batch_intent_changed")
        index = next_case_index(run_dir, plan)
        if resume and index:
            from tools import odoo_v066_scale_audit_v1 as independent
            for ordinal in range(index):
                independent.audit_case(
                    plan=plan, row=plan["tasks"][ordinal],
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
            _event(run_dir / "journal.private.jsonl", {
                "event": "case_started", "ordinal": index,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "attempt_dir": attempt_name,
            })
            family, case = by_id[row["task_id"]]
            wrong = next(candidate for candidate in world["cases"][family]
                         if candidate["id"] != case["id"])
            try:
                receipt = _case_evidence(
                    run_dir=run_dir, ordinal=index, row=row, case=case,
                    wrong=wrong, family=family, modules=(
                        factory, gui_controls, reset, verify, lease))
                from tools import odoo_v066_scale_audit_v1 as independent
                independent.audit_case(
                    plan=plan, row=plan["tasks"][index],
                    attempt=run_dir / attempt_name,
                    worker_private=private)
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
    runner.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"schema": protocol.BATCH_SCHEMA,
                          "status": "refused_without_explicit_execute",
                          "official_final_tasks_admitted": 0,
                          "model_attempts": 0}, sort_keys=True))
        raise SystemExit(2)
    try:
        result = run(
            split=args.split, worker_dir=args.worker_dir,
            private_plan_path=args.private_plan,
            public_plan_path=args.public_plan,
            source_freeze_path=args.source_freeze,
            run_dir=args.run_dir, resume=args.resume,
            max_cases=args.max_cases)
    except Exception as error:
        # Never put private task instructions/IDs or raw Playwright text on stdout.
        print(json.dumps({"schema": protocol.BATCH_SCHEMA,
                          "status": "stopped_preserve_private_attempt",
                          "error_type": type(error).__name__,
                          "official_final_tasks_admitted": 0,
                          "model_attempts": 0}, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))
