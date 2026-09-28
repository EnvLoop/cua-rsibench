"""Current-candidate Odoo one-case evaluator action path.

The GUI recipe is copied from the signed v0.6.6 controller, with a distinct
current-candidate receipt identity. It is never called by the old runner.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_scale_recipes_v1 as recipes
from tools import record_odoo_v066_train_gui_v1 as train_recorder

EPOCH_CASE_SCHEMA = "envloop-odoo-v066-current-candidate-case-attempt-v1"
EPOCH_CASE_STATUS = "raw_gui_positive_negative_reset_complete_current_candidate_review_pending"
_scale_source_sha256 = "c4f14f2d6da7e2f6bd4810f075213d81836886eed36513bca1cccfd964dc19b3"
require = controller.require
_save = controller._save
_capture = controller._capture
HoldoutJournal = controller.HoldoutJournal
STAGES = controller.STAGES
TRACE_SCHEMA = controller.TRACE_SCHEMA
INTENT_SCHEMA = "envloop-odoo-v066-current-candidate-case-intent-v1"
LEASE_OPERATION = controller.LEASE_OPERATION
ScaleControlError = controller.ScaleControlError
utc = controller.utc

def execute_case(*, run_dir: Path, ordinal: int, row: dict,
                   case: dict, wrong: dict, family: str,
                   modules) -> dict:
    from playwright.sync_api import sync_playwright
    from enterprise_fallback.odoo18.odoo_v066_train_adapter import VIEWPORT
    from enterprise_fallback.odoo18.odoo_v066_scale_exact_return_adapter import (
        OdooV066ScaleExactReturnAdapter)
    from enterprise_fallback.odoo18.odoo_v066_scale_pinned_border_adapter import (
        OdooV066ScalePinnedBorderAdapter)
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
        "epoch_source_freeze_sha256": row["epoch_source_freeze_sha256"],
        "current_candidate_private_sha256":
            row["current_candidate_private_sha256"],
        "no_gui_gate_sha256": row["no_gui_gate_sha256"],
        "run_nonce_sha256": row["run_nonce_sha256"],
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
            adapter_class = (OdooV066ScalePinnedBorderAdapter
                             if row.get("physical_dispatch_profile") ==
                             protocol.PINNED_BORDER_PROFILE else
                             OdooV066ScaleExactReturnAdapter)
            adapter = adapter_class(
                page, task_id=case["id"],
                task_binding_sha256=row["package_sha256"],
                instruction=case["prompt"])
            journal = HoldoutJournal(adapter, page, attempt)
            def save_guard_sample(index: int, png: bytes) -> dict:
                reference = _save(
                    attempt / "frames" / f"guard-{index:04d}.png", png)
                reference["path"] = "frames/" + reference["path"]
                return reference
            adapter.frame_guard_sink = save_guard_sample
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
                "exact_return_guard_samples":
                    journal.adapter.frame_guard_samples,
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
                "schema": EPOCH_CASE_SCHEMA,
                "status": EPOCH_CASE_STATUS,
                "split": row["split"],
                "family": family,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "task_binding_sha256": row["task_binding_sha256"],
                "source_freeze_sha256": row["source_freeze_sha256"],
                "epoch_source_freeze_sha256":
                    row["epoch_source_freeze_sha256"],
                "plan_sha256": row["cell_plan_sha256"],
                "current_candidate_private_sha256": row["current_candidate_private_sha256"],
                "historical_ratification_sha256": row["historical_ratification_sha256"],
                "no_gui_gate_sha256": row["no_gui_gate_sha256"],
                "run_nonce_sha256": row["run_nonce_sha256"],
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
            "schema": EPOCH_CASE_SCHEMA,
            "status": "failed_preserve_original_attempt_manual_review_required",
            "current_candidate_private_sha256":
                row["current_candidate_private_sha256"],
            "no_gui_gate_sha256": row["no_gui_gate_sha256"],
            "run_nonce_sha256": row["run_nonce_sha256"],
            "epoch_source_freeze_sha256":
                row["epoch_source_freeze_sha256"],
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
