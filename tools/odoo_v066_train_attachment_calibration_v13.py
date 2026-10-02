"""Freeze and run one original-Odoo, train-only PDF-link route calibration.

No model is called. ``prepare`` is offline; ``run --execute`` requires an
external release of the shared Docker context. A failed run is terminal.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import time

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import record_odoo_v066_train_gui_v1 as recorder


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-odoo-train-attachment-calibration-v13"
FREEZE_SCHEMA = "envloop-odoo-train-attachment-calibration-freeze-v13"
RECEIPT_SCHEMA = "envloop-odoo-train-attachment-calibration-attempt-v13"
RUN_NAME = "attachment-route-train-pilot-20260930-11"
SOURCE_FILES = (
    "tools/odoo_v066_train_rfq_flow_audit_v13.py",
    "tools/audit_odoo_v12_nonprice_border_stop_20260930.py",
    "tools/audit_odoo_v066_train_attachment_calibration_v12.py",
    "tools/odoo_v066_train_attachment_calibration_v12.py",
    "docs/evidence/odoo-v12-nonprice-border-terminal-2026-09-30.json",
    "docs/plans/2026-09-30-odoo-v13-complete-rfq-flow-design.md",
    "tests/test_odoo_v066_complete_rfq_flow_v13.py",
    "tools/odoo_v066_train_border_material_audit_v12.py",
    "tools/audit_odoo_v066_train_attachment_calibration_v10.py",
    "tools/odoo_v066_train_attachment_calibration_v10.py",
    "docs/evidence/odoo-v066-train-attachment-route-v10-terminal-2026-09-30.json",
    "docs/evidence/odoo-v11-new-top-corner-pre-intent-stop-2026-09-30.json",
    "docs/plans/2026-09-30-odoo-v12-finite-border-material-design.md",
    "tools/odoo_v066_train_attachment_calibration_v13.py",
    "tools/audit_odoo_v066_train_attachment_calibration_v13.py",
    "tools/odoo_v066_train_route_journal_v1.py",
    "tools/record_odoo_v066_train_gui_v1.py",
    "tools/odoo_v066_scale_controller_v1.py",
    "tools/odoo_v066_scale_protocol_v1.py",
    "tools/odoo_v066_scale_recipes_v1.py",
    "enterprise_fallback/odoo18/odoo_v066_train_attachment_route_adapter_v2.py",
    "enterprise_fallback/odoo18/odoo_v066_train_attachment_route_adapter_v3.py",
    "enterprise_fallback/odoo18/odoo_v066_train_attachment_route_adapter_v5.py",
    "enterprise_fallback/odoo18/odoo_v066_train_route_router_v1.py",
    "enterprise_fallback/odoo18/odoo_v066_train_route_router_v2.py",
    "enterprise_fallback/odoo18/odoo_v066_train_route_router_v4.py",
    "enterprise_fallback/odoo18/odoo_v066_train_route_router_v5.py",
    "enterprise_fallback/odoo18/odoo_v066_scale_exact_return_adapter.py",
    "enterprise_fallback/odoo18/odoo_v066_scale_pinned_border_adapter.py",
    "enterprise_fallback/odoo18/odoo_v066_scale_parse_border_adapter_v5.py",
    "enterprise_fallback/odoo18/odoo_v066_two_frame_dispatch_adapter_v6.py",
    "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "enterprise_fallback/odoo18/partition_factory.py",
    "enterprise_fallback/odoo18/hidden_factory.py",
    "enterprise_fallback/odoo18/factory.py",
    "enterprise_fallback/odoo18/compose.yaml",
    "enterprise_fallback/odoo18/gui_controls.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/worker_lease.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_action_output_v065.py",
    "src/cursibench/scale_vision_proxy.py",
)
PUBLIC_STATUS = "source_frozen_train_only_no_native_attempt"
READINESS_TIMEOUT_S = 60
READINESS_PROBE_TIMEOUT_S = 5
READINESS_MAX_PROBES = 30
READINESS_POLL_S = 1


class CalibrationError(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise CalibrationError(reason)


def _source_hashes() -> dict[str, str]:
    result = {}
    for relative in SOURCE_FILES:
        path = ROOT / relative
        require(path.is_file() and not path.is_symlink(),
                "calibration_source_missing")
        result[relative] = protocol.digest(path.read_bytes())
    return result


def _private_json(path: Path) -> dict:
    return protocol.private_json(path)


def _worker(worker_dir: Path):
    worker = Path(worker_dir).resolve()
    require(worker.name == "train" and
            os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "calibration_train_worker_not_selected")
    require((worker / "compose.yaml").is_file() and
            not (worker / "compose.yaml").is_symlink(),
            "calibration_original_worker_compose_missing")
    private = protocol._worker_split(worker, "train")
    return worker, private


def _task(private: Path, accepted_audit: dict) -> tuple[dict, dict, dict, bytes]:
    from enterprise_fallback.odoo18.partition_factory import source_asset

    require(accepted_audit.get("schema") ==
            "envloop-odoo-v066-gui-control-pilot-audit-v1" and
            accepted_audit.get("status") ==
            "fresh_train_candidate_control_derived_from_raw_evidence" and
            accepted_audit.get("fresh_train_candidate_controls_qualified") == 1 and
            accepted_audit.get("independent_positive_reward") == 1.0 and
            accepted_audit.get("independent_negative_reward") == 0.0 and
            accepted_audit.get("full_filestore_reset_before_web_restart_exact") is True,
            "accepted_train_pilot_audit_missing")
    world = _private_json(private / "partition_cases.json")
    manifest = _private_json(private / "task_set_manifest.json")
    hashes = _private_json(private / "source_hashes.json")
    require(world.get("split") == "train" and
            type(world.get("cases", {}).get("purchase")) is list,
            "calibration_train_world_invalid")
    # Train task choice predates the selection failures; never inspect the
    # selection/hidden worker to choose this case.
    case_id = "ELPO-TRN-0001"
    prior_attempt = (private / "v066_requalification_runs" /
                     "first-current-source-pilot-pre-intent-resample-01" /
                     "attempt.private.json")
    prior = _private_json(prior_attempt)
    require(prior.get("schema") == recorder.ATTEMPT_SCHEMA and
            prior.get("status") == "completed_with_raw_evaluator_evidence" and
            prior.get("split") == "train" and
            prior.get("task_id") == case_id and
            accepted_audit.get("private_attempt_sha256") ==
            protocol.digest(prior_attempt.read_bytes()),
            "accepted_train_pilot_identity_not_bound")
    matches = [case for case in world["cases"]["purchase"]
               if case.get("id") == case_id]
    require(len(matches) == 1, "accepted_train_case_missing")
    case = matches[0]
    wrong = next((candidate for candidate in world["cases"]["purchase"]
                  if candidate.get("id") != case_id), None)
    require(wrong is not None, "train_wrong_object_missing")
    source = source_asset(case, world)
    package = protocol.digest(json.dumps(case, sort_keys=True).encode() +
                              b"\n" + source)
    manifest_rows = manifest.get("train", [])
    require(len([row for row in manifest_rows
                 if row.get("task_id") == case_id and
                 row.get("package_sha256") == package]) == 1 and
            hashes.get(case_id) == protocol.digest(source) and
            len([line for line in case["lines"]
                 if line["initial"]["price"] !=
                 line["expected"]["price"]]) == 1,
            "train_case_package_or_price_fault_changed")
    return case, wrong, world, source


def _checkpoint(private: Path) -> dict:
    checkpoint = _private_json(private / "checkpoint_receipt.json")
    baseline = private / "baseline_snapshot.json"
    files = private / "baseline-filestore-manifest.json"
    require(protocol.digest((private / "baseline.pgcustom").read_bytes()) ==
            checkpoint["db_sha256"] and
            protocol.digest((private / "baseline-filestore.tgz").read_bytes()) ==
            checkpoint["filestore_sha256"] and
            protocol.digest(files.read_bytes()) ==
            checkpoint["filestore_manifest_sha256"],
            "train_checkpoint_changed")
    return {**checkpoint,
            "baseline_snapshot_sha256": protocol.digest(baseline.read_bytes())}


def _running(worker: Path) -> set[str]:
    """Train-only service probe; Compose may emit a blank line when cold."""
    result = recorder._compose(worker, "ps", "--status", "running",
                               "--services")
    return {name for line in result.stdout.splitlines()
            if (name := line.strip())}


def _wait_db_ready(worker: Path, *, clock=None, sleeper=None, probe=None) -> dict:
    """Bounded native PostgreSQL health and verifier read-only SELECT 1."""
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep

    def default_probe(*args: str, timeout_s: float):
        return subprocess.run(
            ["docker", "compose", "--env-file", ".env", *args],
            cwd=worker, capture_output=True, text=True, check=False,
            timeout=timeout_s)

    probe = probe or default_probe
    started = clock()
    deadline = started + READINESS_TIMEOUT_S
    observations = []
    for attempt in range(1, READINESS_MAX_PROBES + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            break
        row = {"attempt": attempt, "services": [],
               "pg_isready_exit_code": None, "psql_exit_code": None}
        try:
            ps = probe("ps", "--status", "running", "--services",
                       timeout_s=min(READINESS_PROBE_TIMEOUT_S, remaining))
            row["compose_ps_exit_code"] = ps.returncode
            if ps.returncode == 0:
                services = {item.strip() for item in ps.stdout.splitlines()
                            if item.strip()}
                require(services <= {"db"},
                        "train_calibration_unexpected_web_during_db_readiness")
                row["services"] = sorted(services)
                if services == {"db"}:
                    remaining = deadline - clock()
                    if remaining > 0:
                        health = probe(
                            "exec", "-T", "db", "pg_isready", "-U", "odoo",
                            "-d", "postgres",
                            timeout_s=min(READINESS_PROBE_TIMEOUT_S, remaining))
                        row["pg_isready_exit_code"] = health.returncode
                        if health.returncode == 0:
                            remaining = deadline - clock()
                            if remaining > 0:
                                sql = probe(
                                    "exec", "-T", "db", "psql", "-U",
                                    "bench_verify", "-d", "bench", "-At",
                                    "-v", "ON_ERROR_STOP=1", "-c", "SELECT 1",
                                    timeout_s=min(READINESS_PROBE_TIMEOUT_S,
                                                  remaining))
                                row["psql_exit_code"] = sql.returncode
                                if sql.returncode == 0:
                                    require(sql.stdout == "1\n",
                                            "train_calibration_ready_sql_unexpected")
                                    observations.append(row)
                                    return {
                                        "status": "postgres_health_and_select_1_ready",
                                        "query": "SELECT 1", "probe_count": attempt,
                                        "elapsed_milliseconds":
                                            round((clock() - started) * 1000),
                                        "observations": observations,
                                    }
        except subprocess.TimeoutExpired:
            row["probe_timeout"] = True
        observations.append(row)
        remaining = deadline - clock()
        if remaining <= 0:
            break
        sleeper(min(READINESS_POLL_S, remaining))
    raise CalibrationError("train_calibration_db_readiness_timeout")


def prepare(*, worker_dir: Path, accepted_audit_path: Path,
            private_freeze_path: Path, public_freeze_path: Path) -> dict:
    worker, private = _worker(worker_dir)
    accepted_path = Path(accepted_audit_path)
    require(accepted_path.is_file() and not accepted_path.is_symlink(),
            "accepted_train_audit_missing")
    accepted = json.loads(accepted_path.read_bytes())
    case, wrong, _world, source = _task(private, accepted)
    checkpoint = _checkpoint(private)
    out = private / "v066_attachment_route_calibration" / RUN_NAME
    require(not out.exists() and not out.is_symlink(),
            "train_calibration_attempt_already_exists")
    source_hashes = _source_hashes()
    run_nonce = secrets.token_hex(16)
    freeze = {
        "schema": FREEZE_SCHEMA, "status": PUBLIC_STATUS,
        "split": "train", "family": "purchase",
        "task_id": case["id"],
        "task_package_sha256": protocol.digest(
            json.dumps(case, sort_keys=True).encode() + b"\n" + source),
        "wrong_object_id_sha256": protocol.digest(wrong["id"].encode()),
        "source_asset_sha256": protocol.digest(source),
        "source_label_sha256":
            protocol.digest(f"{case['id']}-source.pdf".encode()),
        "visible_instruction_sha256": protocol.digest(case["prompt"].encode()),
        "accepted_train_audit_sha256": protocol.digest(accepted_path.read_bytes()),
        "checkpoint": checkpoint,
        "partition_cases_sha256":
            protocol.digest((private / "partition_cases.json").read_bytes()),
        "worker_env_sha256": protocol.digest((worker / ".env").read_bytes()),
        "worker_compose_sha256":
            protocol.digest((worker / "compose.yaml").read_bytes()),
        "source_hashes_sha256":
            protocol.digest((private / "source_hashes.json").read_bytes()),
        "source_files_sha256": source_hashes,
        "run_directory_name": RUN_NAME,
        "run_nonce": run_nonce,
        "selection_or_hidden_values_read": False,
        "selection_or_hidden_dispatch_authorized": False,
        "model_attempts": 0, "official_final_tasks_admitted": 0,
    }
    private_path = Path(private_freeze_path)
    public_path = Path(public_freeze_path)
    require(private_path.parent.resolve() == private.resolve() and
            not private_path.exists() and not private_path.is_symlink() and
            not public_path.exists() and not public_path.is_symlink(),
            "calibration_freeze_paths_not_fresh")
    protocol.write_new(private_path, freeze, private=True)
    public = {
        "schema": FREEZE_SCHEMA, "status": PUBLIC_STATUS,
        "split": "train", "family": "purchase",
        "private_freeze_sha256": protocol.digest(private_path.read_bytes()),
        "run_nonce_sha256": protocol.digest(run_nonce.encode()),
        "accepted_train_audit_sha256": freeze["accepted_train_audit_sha256"],
        "source_files_sha256": source_hashes,
        "selection_or_hidden_values_read": False,
        "selection_or_hidden_dispatch_authorized": False,
        "model_attempts": 0, "official_final_tasks_admitted": 0,
    }
    protocol.write_new(public_path, public, private=False)
    return public


def _verify_freeze(worker_dir: Path, accepted_audit_path: Path,
                   private_freeze_path: Path, public_freeze_path: Path):
    worker, private = _worker(worker_dir)
    freeze = _private_json(Path(private_freeze_path))
    public = json.loads(Path(public_freeze_path).read_bytes())
    accepted_path = Path(accepted_audit_path)
    accepted = json.loads(accepted_path.read_bytes())
    case, wrong, _world, source = _task(private, accepted)
    require(freeze.get("schema") == FREEZE_SCHEMA and
            freeze.get("status") == PUBLIC_STATUS and
            freeze.get("split") == "train" and
            freeze.get("family") == "purchase" and
            freeze.get("task_id") == case["id"] and
            freeze.get("task_package_sha256") == protocol.digest(
                json.dumps(case, sort_keys=True).encode() + b"\n" + source) and
            freeze.get("wrong_object_id_sha256") ==
            protocol.digest(wrong["id"].encode()) and
            freeze.get("source_asset_sha256") == protocol.digest(source) and
            freeze.get("source_label_sha256") ==
            protocol.digest(f"{case['id']}-source.pdf".encode()) and
            freeze.get("visible_instruction_sha256") ==
            protocol.digest(case["prompt"].encode()) and
            freeze.get("accepted_train_audit_sha256") ==
            protocol.digest(accepted_path.read_bytes()) and
            freeze.get("checkpoint") == _checkpoint(private) and
            freeze.get("partition_cases_sha256") == protocol.digest(
                (private / "partition_cases.json").read_bytes()) and
            freeze.get("worker_env_sha256") ==
            protocol.digest((worker / ".env").read_bytes()) and
            freeze.get("worker_compose_sha256") ==
            protocol.digest((worker / "compose.yaml").read_bytes()) and
            freeze.get("source_hashes_sha256") == protocol.digest(
                (private / "source_hashes.json").read_bytes()) and
            freeze.get("source_files_sha256") == _source_hashes() and
            freeze.get("run_directory_name") == RUN_NAME and
            type(freeze.get("run_nonce")) is str and
            re.fullmatch(r"[0-9a-f]{32}", freeze["run_nonce"]) is not None and
            freeze.get("selection_or_hidden_values_read") is False and
            freeze.get("selection_or_hidden_dispatch_authorized") is False and
            freeze.get("model_attempts") == 0 and
            freeze.get("official_final_tasks_admitted") == 0 and
            public.get("schema") == FREEZE_SCHEMA and
            public.get("status") == PUBLIC_STATUS and
            public.get("private_freeze_sha256") ==
            protocol.digest(Path(private_freeze_path).read_bytes()) and
            public.get("run_nonce_sha256") ==
            protocol.digest(freeze["run_nonce"].encode()) and
            public.get("source_files_sha256") == freeze["source_files_sha256"],
            "train_calibration_source_freeze_changed")
    return worker, private, freeze, case, wrong


def run(*, worker_dir: Path, accepted_audit_path: Path,
        private_freeze_path: Path, public_freeze_path: Path,
        execute: bool) -> dict:
    require(execute, "train_calibration_requires_execute")
    from playwright.sync_api import sync_playwright
    from enterprise_fallback.odoo18.odoo_v066_train_route_router_v5 import (
        OdooV066TrainRouteRouterV5,
    )
    from tools.odoo_v066_train_route_journal_v1 import (
        RouteAwareHoldoutJournal,
    )
    from enterprise_fallback.odoo18.odoo_v066_train_adapter import VIEWPORT
    from tools import odoo_v066_scale_controller_v1 as controller

    worker, private, freeze, case, wrong = _verify_freeze(
        worker_dir, accepted_audit_path, private_freeze_path,
        public_freeze_path)
    out = private / "v066_attachment_route_calibration" / RUN_NAME
    require(not out.exists() and not out.is_symlink(),
            "train_calibration_attempt_already_exists")
    factory, gui_controls, reset, verify, lease = controller._modules(worker)
    root = out.parent
    root.mkdir(mode=0o700, exist_ok=True)
    require(stat.S_IMODE(root.stat().st_mode) & 0o077 == 0,
            "calibration_run_root_not_private")
    with lease.exclusive_worker_operation("v066_train_attachment_calibration"):
        # The lease is held before the durable intent and every Docker call.
        _verify_freeze(worker, accepted_audit_path,
                       private_freeze_path, public_freeze_path)
        out.mkdir(mode=0o700)
        recorder._artifact(out, "intent.private.json", {
            "schema": SCHEMA,
            "status": "durable_before_first_docker_or_gui_action",
            "split": "train", "family": "purchase",
            "private_freeze_sha256": protocol.digest(
                Path(private_freeze_path).read_bytes()),
            "public_freeze_sha256": protocol.digest(
                Path(public_freeze_path).read_bytes()),
            "task_package_sha256": freeze["task_package_sha256"],
            "run_nonce_sha256": protocol.digest(freeze["run_nonce"].encode()),
            "started_at_utc": controller.utc(),
            "selection_or_hidden_dispatch_authorized": False,
            "model_attempts": 0, "official_final_tasks_admitted": 0,
        })
        started = controller.utc()
        t0 = time.monotonic()
        running_before: set[str] = set()
        services_ready = False
        service_state_observed = False
        browser = None
        journal = None
        refs: dict = {}
        stamps: dict = {}
        failure = None
        stage = "service_status"
        reset_exact = False
        services_restored = False
        try:
            running_before = _running(worker)
            service_state_observed = True
            require(running_before == set(),
                    "train_calibration_worker_services_not_cold")
            recorder._compose(worker, "up", "-d", "db")
            services_ready = True
            refs["db_readiness"] = recorder._artifact(
                out, "db_readiness.json", _wait_db_ready(worker))
            recorder._compose(worker, "up", "-d", "web")
            stage = "pre_restore"
            refs["pre_restore"] = recorder._artifact(
                out, "pre_restore.json", reset.restore())
            stamps["pre_restore"] = controller.utc()
            baseline = verify.snapshot()
            refs["baseline_sql"] = recorder._artifact(
                out, "baseline_sql.json", baseline)
            require(baseline == _private_json(private / "baseline_snapshot.json")
                    and verify.score(case["id"])["reward"] == 0.0,
                    "train_calibration_unsolved_baseline_missing")
            credentials = _private_json(private / "actor_credentials.json")
            config = factory.local_config()
            volume = config["ODOO_PROJECT"] + "_filestore"
            changed = next(line for line in case["lines"]
                           if line["initial"]["price"] !=
                           line["expected"]["price"])
            wrong_line = wrong["lines"][0]
            def route_for(rfq_id: str) -> str:
                matching = [row for row in baseline["orders"]
                            if row.get("name") == rfq_id]
                require(len(matching) == 1 and
                        type(matching[0].get("id")) is int and
                        matching[0]["id"] > 0,
                        "train_calibration_price_rfq_route_not_unique")
                return f"/odoo/purchase/{matching[0]['id']}"

            price_targets = (
                {"phase": "positive", "rfq_id": case["id"],
                 "route_path": route_for(case["id"]),
                 "sku": changed["sku"],
                 "initial_price": f"{changed['initial']['price']:.2f}"},
                {"phase": "negative", "rfq_id": wrong["id"],
                 "route_path": route_for(wrong["id"]),
                 "sku": wrong_line["sku"],
                 "initial_price": f"{wrong_line['initial']['price']:.2f}"},
            )
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport=VIEWPORT)
                gui_controls.browser_login(
                    page, int(config["ODOO_PORT"]), credentials["password"],
                    credentials["login"])
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                page.get_by_role("searchbox").wait_for()
                adapter = OdooV066TrainRouteRouterV5(
                    page, task_id=case["id"],
                    task_binding_sha256=freeze["task_package_sha256"],
                    instruction=case["prompt"],
                    expected_attachment_label=f"{case['id']}-source.pdf",
                    expected_price_targets=price_targets)
                journal = RouteAwareHoldoutJournal(adapter, page, out)

                routes = out / "routes"
                routes.mkdir(mode=0o700)

                def save_probe(serial: int, value: dict) -> dict:
                    ref = recorder._artifact(
                        routes, f"probe-{serial:04d}.json", value)
                    ref["path"] = "routes/" + ref["path"]
                    return ref

                def save_decision(serial: int, value: dict) -> dict:
                    ref = recorder._artifact(
                        routes, f"decision-{serial:04d}.json", value)
                    ref["path"] = "routes/" + ref["path"]
                    return ref

                adapter.route_probe_sink = save_probe
                adapter.route_decision_sink = save_decision

                def save_guard(index: int, raw: bytes) -> dict:
                    ref = recorder._artifact(
                        out / "frames", f"guard-{index:04d}.png", raw)
                    ref["path"] = "frames/" + ref["path"]
                    return ref

                adapter.frame_guard_sink = save_guard
                stage = "source_gui"
                recorder._open_case(page, journal, case["id"], phase="positive")
                attach = page.locator("button.o-mail-Chatter-attachFiles")
                attach.wait_for()
                journal.act("click", phase="positive", locator=attach)
                source_item = page.get_by_text(
                    f"{case['id']}-source.pdf", exact=True)
                source_item.wait_for()
                journal.act("click", phase="positive", locator=source_item)
                page.locator("iframe.o-FileViewer-view").wait_for()
                refs["source_frame"] = journal.act(
                    "wait", phase="positive", duration_ms=100,
                    memory="Read the attached source PDF in Odoo.")
                stamps["source_observed"] = controller.utc()
                close = page.locator('[title="Close (Esc)"]')
                journal.act("click", phase="positive", locator=close)
                close.wait_for(state="hidden")
                stage = "positive_gui"
                recorder._edit_price(page, journal, changed,
                                     changed["expected"]["price"],
                                     phase="positive")
                refs["positive_reload_frame"] = recorder._capture_frame(
                    out, "positive_reload_frame.png", page)
                stamps["positive_reload"] = controller.utc()
                refs["positive_sql"] = recorder._artifact(
                    out, "positive_sql.json", verify.snapshot())
                refs["positive_filestore"] = recorder._artifact(
                    out, "positive_filestore.json",
                    reset.filestore_manifest(volume))
                refs["positive_store_paths"] = recorder._artifact(
                    out, "positive_store_paths.json",
                    verify.attachment_store_paths(baseline))
                positive_score = verify.score(case["id"])
                require(positive_score["reward"] == 1.0 and
                        positive_score["difference_codes"] == [],
                        "train_calibration_positive_save_failed")
                stamps["positive_sql"] = controller.utc()
                stage = "negative_gui"
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                recorder._open_case(page, journal, wrong["id"], phase="negative")
                recorder._edit_price(
                    page, journal, wrong_line,
                    round(wrong_line["initial"]["price"] + 1.25, 2),
                    phase="negative")
                refs["negative_reload_frame"] = recorder._capture_frame(
                    out, "negative_reload_frame.png", page)
                stamps["negative_reload"] = controller.utc()
                refs["negative_sql"] = recorder._artifact(
                    out, "negative_sql.json", verify.snapshot())
                refs["negative_filestore"] = recorder._artifact(
                    out, "negative_filestore.json",
                    reset.filestore_manifest(volume))
                refs["negative_store_paths"] = recorder._artifact(
                    out, "negative_store_paths.json",
                    verify.attachment_store_paths(baseline))
                negative_score = verify.score(case["id"])
                require(negative_score["reward"] == 0.0 and
                        negative_score["difference_codes"] ==
                        ["unrelated_order_line_changed"],
                        "train_calibration_wrong_object_failed")
                stamps["negative_sql"] = controller.utc()
                browser.close()
                browser = None
        except BaseException as error:
            failure = error
            failure_stage = stage
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if services_ready:
                try:
                    refs["post_restore"] = recorder._artifact(
                        out, "post_restore.json", reset.restore())
                    refs["restored_sql"] = recorder._artifact(
                        out, "restored_sql.json", verify.snapshot())
                    config = factory.local_config()
                    refs["restored_filestore"] = recorder._artifact(
                        out, "restored_filestore.json",
                        reset.filestore_manifest(
                            config["ODOO_PROJECT"] + "_filestore"))
                    baseline = _private_json(private / "baseline_snapshot.json")
                    files = _private_json(private /
                                          "baseline-filestore-manifest.json")
                    post = _private_json(out / "post_restore.json")
                    reset_exact = bool(
                        post["business_snapshot_equal"] and
                        post["physical_filestore_equal_before_web_restart"] and
                        _private_json(out / "restored_sql.json") == baseline and
                        _private_json(out / "restored_filestore.json") == files and
                        verify.protected_source_file_differences(
                            baseline, files,
                            _private_json(out / "restored_filestore.json")) == [])
                    stamps["post_restore"] = controller.utc()
                except BaseException as error:
                    if failure is None:
                        failure = error
                        failure_stage = "post_restore"
            if service_state_observed:
                try:
                    if "web" not in running_before:
                        recorder._compose(worker, "stop", "web")
                    if "db" not in running_before:
                        recorder._compose(worker, "stop", "db")
                    services_restored = _running(worker) == running_before
                except BaseException as error:
                    if failure is None:
                        failure = error
                        failure_stage = "service_restore"
            if journal is not None:
                refs["gui_trace"] = recorder._artifact(out, "gui_trace.json", {
                    "schema": recorder.GUI_SCHEMA,
                    "task_binding_sha256": freeze["task_package_sha256"],
                    "actions": journal.trace,
                    "pre_intent_rejections": journal.pre_intent_rejections,
                    "guard_samples": journal.adapter.frame_guard_samples,
                    "sft_examples_written": 0,
                })
            if (not reset_exact or not services_restored or
                    time.monotonic() - t0 > 720) and failure is None:
                failure = CalibrationError("train_calibration_reset_or_budget_failed")
                failure_stage = "post_restore"
            if failure is None:
                try:
                    _verify_freeze(worker, accepted_audit_path,
                                   private_freeze_path, public_freeze_path)
                except Exception:
                    failure = CalibrationError("train_calibration_source_changed")
                    failure_stage = "final_source_recheck"
            if failure is None:
                required = {"db_readiness", "pre_restore", "baseline_sql", "source_frame",
                            "positive_reload_frame", "positive_sql",
                            "positive_filestore", "positive_store_paths",
                            "negative_reload_frame", "negative_sql",
                            "negative_filestore", "negative_store_paths",
                            "post_restore", "restored_sql",
                            "restored_filestore", "gui_trace"}
                if set(refs) != required or len(stamps) != 7:
                    failure = CalibrationError("train_calibration_raw_evidence_missing")
                    failure_stage = "final_evidence"
            if failure is None:
                recorder._artifact(out, "attempt.private.json", {
                    "schema": RECEIPT_SCHEMA,
                    "status": "raw_train_only_control_review_pending",
                    "split": "train", "family": "purchase",
                    "private_freeze_sha256": protocol.digest(
                        Path(private_freeze_path).read_bytes()),
                    "task_id": case["id"],
                    "task_package_sha256": freeze["task_package_sha256"],
                    "run_nonce_sha256":
                        protocol.digest(freeze["run_nonce"].encode()),
                    "worker_pid": os.getpid(),
                    "lease_operation": "v066_train_attachment_calibration",
                    "started_at_utc": started,
                    "finished_at_utc": controller.utc(),
                    "stage_timestamps": stamps,
                    "source_label": f"{case['id']}-source.pdf",
                    "refs": refs,
                    "service_state_restored_receipt": services_restored,
                    "selection_or_hidden_dispatch_authorized": False,
                    "model_attempts": 0, "official_final_tasks_admitted": 0,
                })
            else:
                recorder._artifact(out, "failure.private.json", {
                    "schema": RECEIPT_SCHEMA,
                    "status": "terminal_failure_no_automatic_replay",
                    "stage": failure_stage,
                    "run_nonce_sha256":
                        protocol.digest(freeze["run_nonce"].encode()),
                    "error_type": type(failure).__name__,
                    "error_code": getattr(failure, "code", None),
                    "reset_exact": reset_exact,
                    "services_restored": services_restored,
                    "model_attempts": 0, "official_final_tasks_admitted": 0,
                })
        if failure is not None:
            raise CalibrationError(
                "train_calibration_terminal_failure_preserve_attempt") from failure
    return {"schema": RECEIPT_SCHEMA,
            "status": "raw_train_only_control_review_pending",
            "attempt_sha256": protocol.digest(
                (out / "attempt.private.json").read_bytes()),
            "selection_or_hidden_dispatch_authorized": False,
            "model_attempts": 0, "official_final_tasks_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--accepted-audit", type=Path, required=True)
    parser.add_argument("--private-freeze", type=Path, required=True)
    parser.add_argument("--public-freeze", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    common = dict(worker_dir=args.worker_dir,
                  accepted_audit_path=args.accepted_audit,
                  private_freeze_path=args.private_freeze,
                  public_freeze_path=args.public_freeze)
    if args.mode == "prepare":
        require(not args.execute, "offline_prepare_must_not_execute")
        result = prepare(**common)
    else:
        result = run(**common, execute=args.execute)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
