"""One train-only original Odoo v0.6.6 GUI control and SFT source recorder.

`prepare` creates a train-only projection of the frozen private plan. `record`
requires a source-bound public code freeze, a fresh private output directory,
and --execute. It is never an official/model attempt. No automatic replay.
`finalize` requires a separately written visual source-frame review and only
then seals an attempt for the independent offline pilot auditor.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-odoo-v066-train-gui-recorder-v1"
BINDING_SCHEMA = "envloop-odoo-v066-train-pilot-binding-v1"
FREEZE_SCHEMA = "envloop-odoo-v066-train-recorder-code-freeze-v1"
GUI_SCHEMA = "envloop-odoo-v066-gui-control-trace-v1"
ATTEMPT_SCHEMA = "envloop-odoo-v066-gui-control-attempt-v1"
REVIEW_SCHEMA = "envloop-odoo-v066-independent-source-frame-review-v1"
SFT_SCHEMA = "envloop-odoo-v066-exact-gui-sft-source-v1"
LEASE_OPERATION = "v066_gui_requalify"
RATIFICATION_SHA = "49f6a047313c4b1c30fbe357677dbf33cb692614d7e273fe57b088e435c46359"
CONTROLLER_SHA = hashlib.sha256(b"envloop-odoo-v066-known-answer-gui-controller-v1").hexdigest()
MAX_ACTIONS = 90
WALL_SECONDS = 720
ODOO_SOURCE_FILES = (
    "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/gui_controls.py",
    "enterprise_fallback/odoo18/worker_lease.py",
    "enterprise_fallback/odoo18/compose.yaml",
    "enterprise_fallback/odoo18/partition_factory.py",
    "enterprise_fallback/odoo18/hidden_factory.py",
)
COMMON_FILES = {
    "full_action_validator_v06": "src/cursibench/scale_action_contract.py",
    "full_action_extension_v066": "src/cursibench/scale_action_contract_v066.py",
    "minimal_output_v065_dependency": "src/cursibench/scale_action_output_v065.py",
    "minimal_output_v066": "src/cursibench/scale_action_output_v066.py",
    "qwen_vision_proxy": "src/cursibench/scale_vision_proxy.py",
}


class RecorderError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RecorderError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private(path: Path, *, directory: bool = False) -> None:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "private_recorder_path_missing_or_permissive")


def _json(path: Path, *, private: bool = True) -> dict:
    if private:
        _private(path)
    else:
        require(path.is_file() and not path.is_symlink(),
                "public_recorder_reference_missing")
    require(path.stat().st_size <= 8_000_000,
            "recorder_json_oversized")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RecorderError("recorder_json_invalid") from None
    require(type(value) is dict, "recorder_json_invalid")
    return value


def _write(path: Path, raw: bytes) -> dict:
    _private(path.parent, directory=True)
    require(not path.exists() and not path.is_symlink(),
            "recorder_refuses_overwrite")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": path.name, "sha256": sha(raw)}


def _artifact(out: Path, name: str, value: object) -> dict:
    raw = value if type(value) is bytes else canonical(value)
    return _write(out / name, raw)


def host_runtime() -> dict[str, str]:
    return {
        "python": ".".join(map(str, sys.version_info[:3])),
        "playwright": metadata.version("playwright"),
        "Pillow": metadata.version("Pillow"),
    }


def _source_hashes() -> tuple[dict, dict]:
    return ({relative: sha((ROOT / relative).read_bytes())
             for relative in ODOO_SOURCE_FILES},
            {name: sha((ROOT / relative).read_bytes())
             for name, relative in COMMON_FILES.items()})


def prepare_binding(private_plan_path: Path, public_plan_path: Path,
                    out: Path) -> dict:
    """Evaluator-side projection; the live recorder never parses all 140 IDs."""
    private = _json(private_plan_path)
    public = _json(public_plan_path, private=False)
    private_sha = sha(private_plan_path.read_bytes())
    require(private.get("schema") ==
            "envloop-odoo-v066-prospective-gui-requalification-plan-v1" and
            private.get("ratification_sha256") == RATIFICATION_SHA and
            public.get("private_plan_sha256") == private_sha and
            public.get("candidate_counts") ==
            {"train": 20, "selection": 20, "official_hidden": 100} and
            public.get("official_final_tasks_admitted") == 0 and
            private.get("official_final_tasks_admitted") == 0,
            "train_pilot_plan_unbound")
    pilot = private["pilot"]
    rows = [row for row in private["tasks"]["train"]
            if row["task_id"] == pilot["task_id"]]
    require(len(rows) == 1 and pilot["split"] == "train" and
            rows[0]["family"] == "purchase" and
            rows[0]["task_binding_sha256"] == pilot["task_binding_sha256"],
            "train_pilot_not_one_purchase_case")
    own, common = _source_hashes()
    require(private["odoo_source_sha256s"] == own and
            private["common_action_source_sha256s"] == common,
            "train_pilot_current_source_changed")
    binding = {
        "schema": BINDING_SCHEMA,
        "status": "train_only_no_gui_attempt",
        "private_plan_sha256": private_sha,
        "public_plan_sha256": sha(public_plan_path.read_bytes()),
        "ratification_sha256": RATIFICATION_SHA,
        "task": rows[0],
        "checkpoint": private["checkpoints"]["train"],
        "odoo_source_sha256s": own,
        "common_action_source_sha256s": common,
        "pilot_auditor_source_sha256": public["pilot_auditor_source_sha256"],
        "selection_or_hidden_task_values_included": False,
        "official_final_tasks_admitted": 0,
    }
    _write(out, canonical(binding))
    return {"schema": BINDING_SCHEMA, "status": binding["status"],
            "binding_sha256": sha(out.read_bytes()),
            "private_plan_sha256": private_sha,
            "selection_or_hidden_task_values_included": False,
            "official_final_tasks_admitted": 0}


def preflight(*, worker_dir: Path, binding_path: Path,
              public_plan_path: Path, freeze_path: Path,
              out_dir: Path) -> tuple[dict, dict, dict]:
    """Check all identities and bytes before opening Docker or a browser."""
    worker = Path(worker_dir).resolve()
    require(worker.name == "train" and
            os.environ.get("ENVLOOP_ODOO_WORKER_DIR") == str(worker),
            "original_train_worker_not_selected")
    private = worker / "private"
    _private(private, directory=True)
    require(out_dir.parent.resolve() == (private / "v066_requalification_runs").resolve()
            and not out_dir.exists() and not out_dir.is_symlink(),
            "fresh_train_attempt_directory_required")
    _private(Path(binding_path).parent, directory=True)
    binding = _json(binding_path)
    public = _json(public_plan_path, private=False)
    freeze = _json(freeze_path, private=False)
    own, common = _source_hashes()
    require(binding.get("schema") == BINDING_SCHEMA and
            binding.get("status") == "train_only_no_gui_attempt" and
            binding.get("ratification_sha256") == RATIFICATION_SHA and
            binding.get("selection_or_hidden_task_values_included") is False and
            binding.get("official_final_tasks_admitted") == 0 and
            binding.get("public_plan_sha256") == sha(public_plan_path.read_bytes()) and
            binding.get("private_plan_sha256") == public.get("private_plan_sha256") and
            public.get("status") == "source_bound_plan_only_no_current_gui_proofs" and
            public.get("new_six_cell_ratification_sha256") == RATIFICATION_SHA and
            public.get("pilot_receipt_present") is False and
            public.get("official_final_tasks_admitted") == 0 and
            binding.get("odoo_source_sha256s") == own and
            binding.get("common_action_source_sha256s") == common and
            public.get("pilot_auditor_source_sha256") ==
            binding.get("pilot_auditor_source_sha256") and
            freeze.get("schema") == FREEZE_SCHEMA and
            freeze.get("status") == "frozen_before_first_live_train_gui_attempt" and
            freeze.get("recorder_source_sha256") == sha(Path(__file__).read_bytes()) and
            freeze.get("train_pilot_binding_sha256") == sha(binding_path.read_bytes()) and
            freeze.get("public_plan_sha256") == sha(public_plan_path.read_bytes()) and
            freeze.get("private_plan_sha256") == binding["private_plan_sha256"] and
            freeze.get("pilot_auditor_source_sha256") ==
            public.get("pilot_auditor_source_sha256") and
            freeze.get("host_runtime") == host_runtime() and
            freeze.get("ratification_sha256") == RATIFICATION_SHA and
            freeze.get("official_final_tasks_admitted") == 0 and
            freeze.get("live_gui_attempts_before_freeze") == 0 and
            freeze.get("provider_calls_before_freeze") == 0,
            "recorder_code_or_plan_freeze_changed")
    task = binding.get("task")
    require(type(task) is dict, "train_pilot_task_missing")
    task_binding = {key: task.get(key) for key in (
        "ratification_sha256", "action_profile", "split", "task_id",
        "package_sha256", "source_asset_sha256",
        "visible_instruction_sha256", "checkpoint", "odoo_adapter_sha256")}
    require(task.get("task_binding_sha256") == sha(canonical(task_binding)) and
            task.get("ratification_sha256") == RATIFICATION_SHA and
            task.get("action_profile") == "scale-action-profile-v0.6.6" and
            task.get("split") == "train" and
            task.get("family") == "purchase" and
            task.get("checkpoint") == binding.get("checkpoint") and
            task.get("odoo_adapter_sha256") == own[ODOO_SOURCE_FILES[0]] and
            task.get("fresh_v066_gui_proof_status") == "pending" and
            binding["checkpoint"]["db_sha256"] ==
            sha((private / "baseline.pgcustom").read_bytes()) and
            binding["checkpoint"]["filestore_sha256"] ==
            sha((private / "baseline-filestore.tgz").read_bytes()) and
            binding["checkpoint"]["baseline_snapshot_sha256"] ==
            sha((private / "baseline_snapshot.json").read_bytes()) and
            binding["checkpoint"]["baseline_filestore_manifest_sha256"] ==
            sha((private / "baseline-filestore-manifest.json").read_bytes()),
            "train_pilot_task_or_checkpoint_changed")
    # Never open the cross-split task-set manifest or any other worker tree.
    world = _json(private / "partition_cases.json")
    require(world.get("split") == "train", "train_world_changed")
    matches = [case for case in world["cases"]["purchase"]
               if case.get("id") == task["task_id"]]
    require(len(matches) == 1 and len(world["cases"]["purchase"]) == 5,
            "train_pilot_case_missing")
    case = matches[0]
    from enterprise_fallback.odoo18.partition_factory import source_asset
    source = source_asset(case, world)
    package = sha(json.dumps(case, sort_keys=True).encode() + b"\n" + source)
    changes = [(line, key) for line in case["lines"]
               for key in ("qty", "price", "date")
               if line["initial"][key] != line["expected"][key]]
    require(package == task["package_sha256"] and
            sha(source) == task["source_asset_sha256"] and
            sha(case["prompt"].encode()) == task["visible_instruction_sha256"] and
            len(changes) == 1 and changes[0][1] == "price" and
            task["source_label"] == f"{case['id']}-source.pdf",
            "train_pilot_source_or_single_price_fault_changed")
    wrong = next(candidate for candidate in world["cases"]["purchase"]
                 if candidate["id"] != case["id"])
    return binding, case, wrong


class ActionJournal:
    """Write frame, rendered input and normalized action before every GUI dispatch."""

    def __init__(self, adapter, page, out: Path):
        self.adapter = adapter
        self.page = page
        self.out = out
        self.trace: list[dict] = []
        self.sft: list[dict] = []
        (out / "frames").mkdir(mode=0o700)
        (out / "actions").mkdir(mode=0o700)
        self.started = time.monotonic()

    def act(self, kind: str, *, phase: str, locator=None,
            ref: str | None = None, memory: str = "", **fields) -> dict:
        require(phase in ("positive", "negative") and
                len(self.trace) < MAX_ACTIONS and
                time.monotonic() - self.started < WALL_SECONDS,
                "train_gui_action_or_wall_budget_exceeded")
        observation, rendered = self.adapter.observe_for_model(memory=memory)
        index = len(self.trace)
        require(observation.step == index and
                type(rendered.get("instruction")) is str and
                type(rendered.get("image_bytes")) is bytes and
                rendered["image_bytes"] == observation.screenshot_bytes,
                "current_gui_observation_or_renderer_invalid")
        frame_path = self.out / "frames" / f"step-{index:03d}.png"
        frame = _write(frame_path, observation.screenshot_bytes)
        frame["path"] = "frames/" + frame["path"]
        instruction = _write(self.out / "actions" /
                             f"step-{index:03d}-instruction.txt",
                             rendered["instruction"].encode())
        instruction["path"] = "actions/" + instruction["path"]
        visible = _write(self.out / "actions" /
                         f"step-{index:03d}-visible.txt",
                         rendered["visible_text"].encode())
        visible["path"] = "actions/" + visible["path"]
        payload = {"type": kind, **fields}
        if ref is not None:
            require(len([item for item in observation.controls
                         if item.ref == ref and item.visible and item.enabled]) == 1,
                    "visible_control_ref_not_unique")
            payload["target"] = {"ref": ref}
        elif locator is not None:
            box = locator.bounding_box()
            require(box is not None and box["width"] > 0 and box["height"] > 0,
                    "gui_locator_not_visible")
            payload["target"] = {"x": int(box["x"] + box["width"] / 2),
                                 "y": int(box["y"] + box["height"] / 2)}
        raw_action = json.dumps(payload, ensure_ascii=False,
                                sort_keys=True, separators=(",", ":"))
        action_ref = _write(self.out / "actions" /
                            f"step-{index:03d}-assistant.json",
                            raw_action.encode())
        action_ref["path"] = "actions/" + action_ref["path"]
        # No dispatch occurs if parsing rejects the current frame.
        normalized = self.adapter.parse_current_action(raw_action)
        intent = {"schema": "envloop-odoo-v066-pre-dispatch-action-intent-v1",
                  "phase": phase, "step": index, "task_id": observation.task_id,
                  "task_binding_sha256": observation.task_binding_sha256,
                  "frame_id": observation.frame_id,
                  "frame_sha256": frame["sha256"],
                  "frame_ref": frame,
                  "instruction_ref": instruction,
                  "visible_text_ref": visible,
                  "assistant_action_ref": action_ref,
                  "normalized_action": normalized,
                  "dispatch_state": "intent_durable_before_gui_action"}
        intent_ref = _write(self.out / "actions" /
                            f"step-{index:03d}-intent.private.json",
                            canonical(intent))
        intent_ref["path"] = "actions/" + intent_ref["path"]
        # Any exception here is uncertain; it is retained and never retried.
        applied = self.adapter.dispatch(normalized)
        require(applied.get("action") == normalized and
                applied.get("public_contract_receipt", {}).get("screenshot", {}).get(
                    "sha256") == frame["sha256"],
                "gui_dispatch_receipt_not_bound_to_frame")
        result = {"schema": "envloop-odoo-v066-dispatch-result-v1",
                  "phase": phase, "step": index,
                  "intent_sha256": intent_ref["sha256"],
                  "applied_action": applied["action"],
                  "contract_receipt": applied["public_contract_receipt"]}
        result_ref = _write(self.out / "actions" /
                            f"step-{index:03d}-result.private.json",
                            canonical(result))
        result_ref["path"] = "actions/" + result_ref["path"]
        self.trace.append({"phase": phase, "step": index,
                           "frame": frame,
                           "contract_receipt": applied["public_contract_receipt"]})
        if phase == "positive":
            self.sft.append({"step": index, "frame": frame,
                             "rendered_instruction": instruction,
                             "visible_text": visible,
                             "assistant_action": action_ref,
                             "normalized_action_intent": intent_ref,
                             "dispatch_result": result_ref})
        return frame


def _compose(worker: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", "--env-file", ".env", *args],
                          cwd=worker, capture_output=True, text=True, check=True)


def _running(worker: Path) -> set[str]:
    return set(_compose(worker, "ps", "--status", "running",
                        "--services").stdout.splitlines())


def _open_case(page, journal: ActionJournal,
               case_id: str, *, phase: str) -> None:
    search = page.get_by_role("searchbox")
    search.wait_for()
    journal.act("type", phase=phase, locator=search,
                text=case_id, mode="fill")
    journal.act("key", phase=phase, key="Enter")
    row = page.get_by_role("cell", name=case_id, exact=True)
    row.wait_for()
    journal.act("click", phase=phase, locator=row)
    page.wait_for_url("**/odoo/purchase/*")


def _edit_price(page, journal: ActionJournal, line: dict,
                price: float, *, phase: str) -> None:
    cell = page.locator("tr").filter(has_text=line["sku"]).first.locator(
        'td[name="price_unit"]')
    cell.wait_for()
    journal.act("click", phase=phase, locator=cell)
    editor = page.locator('td[name="price_unit"] input').first
    editor.wait_for()
    page.wait_for_timeout(600)
    journal.act("double_click", phase=phase, locator=editor)
    journal.act("key", phase=phase, key="Meta+A")
    journal.act("type", phase=phase, text=str(price), mode="insert")
    journal.act("key", phase=phase, key="Tab")
    save = page.get_by_role("button", name="Save", exact=True)
    if save.count() and save.is_visible():
        journal.act("click", phase=phase, locator=save)
        save.wait_for(state="hidden")
    else:
        page.wait_for_timeout(350)
    page.reload()
    persisted = page.locator("tr").filter(has_text=line["sku"]).first.locator(
        'td[name="price_unit"]')
    persisted.wait_for()
    require(round(float(persisted.inner_text().strip()), 2) ==
            round(float(price), 2), "native_purchase_price_not_saved_after_reload")


def _capture_frame(out: Path, name: str, page) -> dict:
    return _artifact(out, name, page.screenshot(type="png"))


def _safe_failure(out: Path, stage: str, exc: BaseException,
                  *, reset_exact: bool | None, services_restored: bool | None) -> None:
    _artifact(out, "failure.private.json", {
        "schema": SCHEMA,
        "status": "failed_preserve_original_attempt_no_automatic_retry",
        "stage": stage,
        "error_type": type(exc).__name__,
        "reset_exact": reset_exact,
        "services_restored": services_restored,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    })


def record(*, worker_dir: Path, binding_path: Path,
           public_plan_path: Path, freeze_path: Path,
           out_dir: Path) -> dict:
    """Run one known-answer train control only after an explicit CLI switch."""
    from playwright.sync_api import sync_playwright
    from enterprise_fallback.odoo18.odoo_v066_train_adapter import (
        OdooV066TrainAdapter, VIEWPORT)
    # These top-level modules read ENVLOOP_ODOO_WORKER_DIR on first import.
    source_dir = ROOT / "enterprise_fallback/odoo18"
    for name in ("factory", "gui_controls", "reset", "verify", "worker_lease"):
        loaded = sys.modules.get(name)
        require(loaded is None or Path(loaded.__file__).resolve() ==
                source_dir / (name + ".py"), "odoo_module_identity_conflict")
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    import factory
    import gui_controls
    import reset
    import verify
    import worker_lease

    worker = Path(worker_dir).resolve()
    out = Path(out_dir).absolute()
    require(factory.HERE == worker and factory.PRIVATE == worker / "private" and
            gui_controls.PRIVATE == worker / "private" and
            verify.PRIVATE == worker / "private" and
            reset.PRIVATE == worker / "private" and
            worker_lease.PRIVATE == worker / "private" and
            factory.local_config().get("ODOO_PARTITION") == "train",
            "original_odoo_train_module_boundary_invalid")
    runs_root = worker / "private" / "v066_requalification_runs"
    runs_root.mkdir(mode=0o700, exist_ok=True)
    _private(runs_root, directory=True)
    with worker_lease.exclusive_worker_operation(LEASE_OPERATION):
        # Reopen every train source/checkpoint under the held worker lock.
        binding, case, wrong = preflight(
            worker_dir=worker, binding_path=binding_path,
            public_plan_path=public_plan_path, freeze_path=freeze_path,
            out_dir=out)
        task = binding["task"]
        require(not out.exists(), "recorder_refuses_existing_attempt")
        out.mkdir(mode=0o700)
        _artifact(out, "intent.private.json", {
            "schema": SCHEMA,
            "status": "reserved_before_first_docker_or_gui_action",
            "binding_sha256": sha(binding_path.read_bytes()),
            "public_plan_sha256": sha(public_plan_path.read_bytes()),
            "recorder_source_sha256": sha(Path(__file__).read_bytes()),
            "task_binding_sha256": task["task_binding_sha256"],
            "started_at_utc": utc(),
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        })
        started_utc = utc()
        started_monotonic = time.monotonic()
        stage = "service_status"
        running_before = set()
        browser = None
        refs = {}
        stages = {}
        journal = None
        reset_exact = None
        restored_services = None
        services_ready = False
        failure = None
        failure_stage = None
        try:
            running_before = _running(worker)
            if not {"db", "web"} <= running_before:
                _compose(worker, "up", "-d", "db", "web")
            services_ready = True
            stage = "pre_restore"
            refs["pre_restore"] = _artifact(out, "pre_restore.json", reset.restore())
            stages["pre_restore"] = utc()
            baseline = verify.snapshot()
            refs["baseline_sql"] = _artifact(out, "baseline_sql.json", baseline)
            frozen = _json(worker / "private" / "baseline_snapshot.json")
            require(baseline == frozen and verify.score(case["id"])["reward"] == 0.0,
                    "train_pilot_baseline_not_exact_unsolved")
            credentials = _json(worker / "private" / "actor_credentials.json")
            config = factory.local_config()
            project = config["ODOO_PROJECT"]
            volume = project + "_filestore"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport=VIEWPORT)
                gui_controls.browser_login(
                    page, int(config["ODOO_PORT"]),
                    credentials["password"], credentials["login"])
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                page.get_by_role("searchbox").wait_for()
                adapter = OdooV066TrainAdapter(
                    page, task_id=case["id"],
                    task_binding_sha256=task["package_sha256"],
                    instruction=case["prompt"])
                journal = ActionJournal(adapter, page, out)
                stage = "source_gui"
                _open_case(page, journal, case["id"], phase="positive")
                attach = page.locator("button.o-mail-Chatter-attachFiles")
                attach.wait_for()
                journal.act("click", phase="positive", locator=attach)
                source_item = page.get_by_text(task["source_label"], exact=True)
                source_item.wait_for()
                journal.act("click", phase="positive", locator=source_item)
                page.locator("iframe.o-FileViewer-view").wait_for()
                refs["source_frame"] = journal.act(
                    "wait", phase="positive", duration_ms=100,
                    memory="Read the attached supplier confirmation in Odoo.")
                stages["source_observed"] = utc()
                close = page.locator('[title="Close (Esc)"]')
                journal.act("click", phase="positive", locator=close)
                close.wait_for(state="hidden")
                stage = "positive_gui"
                changed = next(line for line in case["lines"]
                               if line["initial"]["price"] !=
                               line["expected"]["price"])
                _edit_price(page, journal, changed,
                            changed["expected"]["price"], phase="positive")
                # Browser reload is evaluator-owned readback, never actor input.
                refs["positive_reload_frame"] = _capture_frame(
                    out, "positive_reload_frame.png", page)
                stages["positive_reload"] = utc()
                stage = "positive_saved_state"
                refs["positive_sql"] = _artifact(
                    out, "positive_sql.json", verify.snapshot())
                refs["positive_filestore"] = _artifact(
                    out, "positive_filestore.json",
                    reset.filestore_manifest(volume))
                refs["positive_store_paths"] = _artifact(
                    out, "positive_store_paths.json",
                    verify.attachment_store_paths(baseline))
                positive_score = verify.score(case["id"])
                _artifact(out, "online_positive_score.private.json",
                          positive_score)
                require(positive_score["reward"] == 1.0 and
                        positive_score["difference_codes"] == [],
                        "train_pilot_positive_saved_state_failed")
                stages["positive_sql"] = utc()
                stage = "negative_gui"
                # Evaluator-controlled phase transition. The wrong-object
                # search, open and edit still use only the v0.6.6 dispatcher.
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                _open_case(page, journal,
                           wrong["id"], phase="negative")
                wrong_line = wrong["lines"][0]
                wrong_price = round(wrong_line["initial"]["price"] + 1.25, 2)
                _edit_price(page, journal, wrong_line,
                            wrong_price, phase="negative")
                refs["negative_reload_frame"] = _capture_frame(
                    out, "negative_reload_frame.png", page)
                stages["negative_reload"] = utc()
                stage = "negative_saved_state"
                refs["negative_sql"] = _artifact(
                    out, "negative_sql.json", verify.snapshot())
                refs["negative_filestore"] = _artifact(
                    out, "negative_filestore.json",
                    reset.filestore_manifest(volume))
                refs["negative_store_paths"] = _artifact(
                    out, "negative_store_paths.json",
                    verify.attachment_store_paths(baseline))
                negative_score = verify.score(case["id"])
                _artifact(out, "online_negative_score.private.json",
                          negative_score)
                require(negative_score["reward"] == 0.0 and
                        "unrelated_order_line_changed" in
                        negative_score["difference_codes"],
                        "train_pilot_wrong_object_negative_failed")
                stages["negative_sql"] = utc()
                browser.close()
                browser = None
        except BaseException as exc:
            failure = exc
            failure_stage = stage
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if services_ready:
                try:
                    stage = "post_restore"
                    refs["post_restore"] = _artifact(
                        out, "post_restore.json", reset.restore())
                    refs["restored_sql"] = _artifact(
                        out, "restored_sql.json", verify.snapshot())
                    checkpoint = binding["checkpoint"]
                    config = factory.local_config()
                    refs["restored_filestore"] = _artifact(
                        out, "restored_filestore.json",
                        reset.filestore_manifest(
                            config["ODOO_PROJECT"] + "_filestore"))
                    post = _json(out / refs["post_restore"]["path"])
                    reset_exact = bool(
                        post["business_snapshot_equal"] and
                        post["physical_filestore_equal_before_web_restart"] and
                        _json(out / refs["restored_sql"]["path"]) ==
                        _json(worker / "private" / "baseline_snapshot.json") and
                        verify.protected_source_file_differences(
                            _json(worker / "private" / "baseline_snapshot.json"),
                            _json(worker / "private" /
                                  "baseline-filestore-manifest.json"),
                            _json(out / refs["restored_filestore"]["path"])) == [] and
                        sha((worker / "private" /
                             "baseline.pgcustom").read_bytes()) ==
                        checkpoint["db_sha256"])
                    stages["post_restore"] = utc()
                except BaseException as exc:
                    reset_exact = False
                    if failure is None:
                        failure = exc
                        failure_stage = "post_restore"
                try:
                    if "web" not in running_before:
                        _compose(worker, "stop", "web")
                    if "db" not in running_before:
                        _compose(worker, "stop", "db")
                    restored_services = (_running(worker) == running_before)
                    if not restored_services and failure is None:
                        failure = RecorderError("original_service_state_not_restored")
                        failure_stage = "service_restore"
                except BaseException as exc:
                    restored_services = False
                    if failure is None:
                        failure = exc
                        failure_stage = "service_restore"
            if journal is not None:
                refs["gui_trace"] = _artifact(out, "gui_trace.json", {
                    "schema": GUI_SCHEMA,
                    "task_binding_sha256": task["task_binding_sha256"],
                    "actions": journal.trace})
            if time.monotonic() - started_monotonic > WALL_SECONDS and failure is None:
                failure = RecorderError("train_pilot_wall_budget_exceeded")
                failure_stage = "task_wall_budget"
            if not reset_exact and failure is None:
                failure = RecorderError("train_pilot_post_reset_inexact")
                failure_stage = "post_restore"
            if failure is None:
                own_now, common_now = _source_hashes()
                if (own_now != binding["odoo_source_sha256s"] or
                        common_now != binding["common_action_source_sha256s"] or
                        sha(Path(__file__).read_bytes()) !=
                        _json(freeze_path, private=False)["recorder_source_sha256"]):
                    failure = RecorderError("train_pilot_source_changed_during_attempt")
                    failure_stage = "final_source_recheck"
            if failure is None:
                required = {
                    "pre_restore", "baseline_sql", "source_frame",
                    "positive_reload_frame", "positive_sql",
                    "positive_filestore", "positive_store_paths",
                    "negative_reload_frame", "negative_sql",
                    "negative_filestore", "negative_store_paths",
                    "post_restore", "restored_sql", "restored_filestore",
                    "gui_trace"}
                if (set(refs) != required or
                        set(stages) != {"pre_restore", "source_observed",
                                        "positive_reload", "positive_sql",
                                        "negative_reload", "negative_sql",
                                        "post_restore"} or
                        restored_services is not True):
                    failure = RecorderError("train_pilot_raw_evidence_incomplete")
                    failure_stage = "final_evidence_check"
            if failure is None:
                _artifact(out, "sft_candidate.private.json", {
                    "schema": SFT_SCHEMA,
                    "status": "pending_independent_visual_and_semantic_pilot_audit",
                    "split": "train", "cell": "odoo-community",
                    "model": "Qwen/Qwen3.8-27B",
                    "action_profile": "scale-action-profile-v0.6.6",
                    "task_binding_sha256": task["task_binding_sha256"],
                    "positive_steps_only": journal.sft,
                    "selection_or_hidden_examples": 0,
                    "tinker_training_started": False})
                draft = {
                    "schema": ATTEMPT_SCHEMA,
                    "status": "awaiting_independent_source_frame_review",
                    "plan_sha256": binding["private_plan_sha256"],
                    "ratification_sha256": RATIFICATION_SHA,
                    "split": "train", "task_id": task["task_id"],
                    "package_sha256": task["package_sha256"],
                    "task_binding_sha256": task["task_binding_sha256"],
                    "worker_pid": os.getpid(),
                    "controller_id_sha256": CONTROLLER_SHA,
                    "started_at_utc": started_utc,
                    "finished_at_utc": utc(),
                    "lease_operation": LEASE_OPERATION,
                    "stage_timestamps": stages,
                    "refs": refs,
                }
                _artifact(out, "draft.private.json", draft)
            else:
                _safe_failure(out, failure_stage or stage, failure,
                              reset_exact=reset_exact,
                              services_restored=restored_services)
        if failure is not None:
            raise RecorderError("train_pilot_failed_preserved_private_attempt") from failure
        return {"schema": SCHEMA,
                "status": "raw_train_evidence_recorded_review_pending",
                "action_count": len(journal.trace),
                "positive_sft_candidate_steps": len(journal.sft),
                "post_reset_exact": reset_exact,
                "services_restored": restored_services,
                "official_final_tasks_admitted": 0,
                "model_attempts": 0}


def finalize(*, out_dir: Path, review_path: Path,
             binding_path: Path) -> dict:
    """Seal a completed raw attempt only after independent visual review."""
    out = Path(out_dir).resolve()
    _private(out, directory=True)
    require(not (out / "attempt.private.json").exists() and
            not (out / "failure.private.json").exists(),
            "pilot_attempt_already_sealed_or_failed")
    draft = _json(out / "draft.private.json")
    review = _json(review_path)
    binding = _json(binding_path)
    source = draft["refs"]["source_frame"]
    source_relative = Path(source["path"])
    require(draft.get("schema") == ATTEMPT_SCHEMA and
            draft.get("status") == "awaiting_independent_source_frame_review" and
            draft.get("task_id") == binding["task"]["task_id"] and
            draft.get("package_sha256") == binding["task"]["package_sha256"] and
            draft.get("task_binding_sha256") ==
            binding["task"]["task_binding_sha256"] and
            draft.get("plan_sha256") == binding["private_plan_sha256"] and
            not source_relative.is_absolute() and
            len(source_relative.parts) == 2 and
            source_relative.parts[0] == "frames" and
            ".." not in source_relative.parts and
            (out / source_relative).resolve().is_relative_to(out),
            "draft_or_source_frame_not_bound_to_train_pilot")
    require(review_path.parent.resolve() == out and
            review.get("schema") == REVIEW_SCHEMA and
            review.get("decision") ==
            "source_visible_in_original_odoo_gui" and
            review.get("reviewer_role") ==
            "independent_visual_source_reviewer" and
            review.get("reviewer_id_sha256") != CONTROLLER_SHA and
            review.get("source_frame_sha256") == source["sha256"] and
            review.get("source_asset_sha256") ==
            binding["task"]["source_asset_sha256"] and
            review.get("source_label") == binding["task"]["source_label"],
            "independent_visual_review_unbound")
    from datetime import datetime as _dt
    require(_dt.fromisoformat(review["reviewed_at_utc"]) >=
            _dt.fromisoformat(draft["finished_at_utc"]),
            "visual_review_precedes_attempt_completion")
    _private(out / source["path"])
    require(sha((out / source["path"]).read_bytes()) == source["sha256"],
            "source_frame_bytes_changed")
    final = {**draft,
             "status": "completed_with_raw_evaluator_evidence",
             "refs": {**draft["refs"],
                      "source_review": {"path": review_path.name,
                                        "sha256": sha(review_path.read_bytes())}}}
    _artifact(out, "attempt.private.json", final)
    return {"schema": ATTEMPT_SCHEMA,
            "status": "sealed_for_independent_offline_pilot_audit",
            "private_attempt_sha256": sha((out / "attempt.private.json").read_bytes()),
            "official_final_tasks_admitted": 0,
            "model_attempts": 0}


def _read_ref(out: Path, reference: dict) -> bytes:
    require(type(reference) is dict and set(reference) == {"path", "sha256"} and
            type(reference["path"]) is str and
            type(reference["sha256"]) is str,
            "sft_source_reference_invalid")
    relative = Path(reference["path"])
    require(not relative.is_absolute() and len(relative.parts) == 2 and
            relative.parts[0] in ("frames", "actions") and
            ".." not in relative.parts,
            "sft_source_reference_path_unsafe")
    target = out / relative
    require(target.resolve().is_relative_to(out),
            "sft_source_reference_path_unsafe")
    _private(target)
    raw = target.read_bytes()
    require(sha(raw) == reference["sha256"],
            "sft_source_reference_bytes_changed")
    return raw


def audit_sft_source(*, out_dir: Path, binding_path: Path,
                     pilot_audit_path: Path) -> dict:
    """Admit exact positive GUI turns only after independent pilot acceptance."""
    out = Path(out_dir).resolve()
    _private(out, directory=True)
    binding = _json(binding_path)
    pilot = _json(pilot_audit_path, private=False)
    candidate = _json(out / "sft_candidate.private.json")
    attempt_path = out / "attempt.private.json"
    _private(attempt_path)
    attempt_sha = sha(attempt_path.read_bytes())
    trace = _json(out / "gui_trace.json")
    steps = candidate.get("positive_steps_only")
    positive_trace = [row for row in trace.get("actions", [])
                      if row.get("phase") == "positive"]
    require(pilot.get("schema") == "envloop-odoo-v066-gui-control-pilot-audit-v1" and
            pilot.get("status") ==
            "fresh_train_candidate_control_derived_from_raw_evidence" and
            pilot.get("private_attempt_sha256") == attempt_sha and
            pilot.get("fresh_train_candidate_controls_qualified") == 1 and
            pilot.get("official_final_tasks_admitted") == 0 and
            pilot.get("model_attempts") == 0 and
            candidate.get("schema") == SFT_SCHEMA and
            candidate.get("status") ==
            "pending_independent_visual_and_semantic_pilot_audit" and
            candidate.get("split") == "train" and
            candidate.get("cell") == "odoo-community" and
            candidate.get("model") == "Qwen/Qwen3.8-27B" and
            candidate.get("action_profile") == "scale-action-profile-v0.6.6" and
            candidate.get("task_binding_sha256") ==
            binding["task"]["task_binding_sha256"] and
            candidate.get("selection_or_hidden_examples") == 0 and
            candidate.get("tinker_training_started") is False and
            type(steps) is list and steps and len(steps) == len(positive_trace) ==
            pilot.get("positive_gui_actions"),
            "exact_sft_source_or_pilot_not_admitted")
    for step, trace_row in zip(steps, positive_trace):
        require(type(step) is dict and
                set(step) == {"step", "frame", "rendered_instruction",
                              "visible_text", "assistant_action",
                              "normalized_action_intent", "dispatch_result"} and
                step["step"] == trace_row["step"] and
                step["frame"] == trace_row["frame"],
                "sft_step_or_frame_not_exact")
        frame = _read_ref(out, step["frame"])
        instruction = _read_ref(out, step["rendered_instruction"])
        assistant = _read_ref(out, step["assistant_action"])
        _read_ref(out, step["visible_text"])
        intent = json.loads(_read_ref(out, step["normalized_action_intent"]))
        result = json.loads(_read_ref(out, step["dispatch_result"]))
        action = json.loads(assistant)
        normalized = intent.get("normalized_action")
        require(frame.startswith(b"\x89PNG\r\n\x1a\n") and
                0 < len(instruction) <= 16_384 and
                type(normalized) is dict and
                intent.get("phase") == "positive" and
                result.get("phase") == "positive" and
                intent.get("frame_sha256") == step["frame"]["sha256"] and
                intent.get("task_id") == binding["task"]["task_id"] and
                intent.get("task_binding_sha256") ==
                binding["task"]["package_sha256"] and
                normalized.get("frame_id") == intent.get("frame_id") and
                all(normalized.get(key) == value for key, value in action.items()) and
                result.get("intent_sha256") ==
                step["normalized_action_intent"]["sha256"] and
                result.get("applied_action") == normalized and
                result.get("contract_receipt") ==
                trace_row["contract_receipt"] and
                trace_row["contract_receipt"].get("screenshot", {}).get(
                    "sha256") == step["frame"]["sha256"],
                "sft_action_not_exactly_dispatched")
    return {"schema": "envloop-odoo-v066-exact-gui-sft-source-audit-v1",
            "status": "exact_train_gui_sft_source_eligible_not_trained",
            "datum_count": len(steps),
            "candidate_source_sha256": sha((out / "sft_candidate.private.json").read_bytes()),
            "pilot_audit_sha256": sha(pilot_audit_path.read_bytes()),
            "selection_or_hidden_examples": 0,
            "tinker_training_started": False,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--private-plan", type=Path, required=True)
    prep.add_argument("--public-plan", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    live = commands.add_parser("record")
    live.add_argument("--worker-dir", type=Path, required=True)
    live.add_argument("--pilot-binding", type=Path, required=True)
    live.add_argument("--public-plan", type=Path, required=True)
    live.add_argument("--code-freeze", type=Path, required=True)
    live.add_argument("--out-dir", type=Path, required=True)
    live.add_argument("--execute", action="store_true")
    seal = commands.add_parser("finalize")
    seal.add_argument("--out-dir", type=Path, required=True)
    seal.add_argument("--review", type=Path, required=True)
    seal.add_argument("--pilot-binding", type=Path, required=True)
    sft = commands.add_parser("audit-sft")
    sft.add_argument("--out-dir", type=Path, required=True)
    sft.add_argument("--pilot-binding", type=Path, required=True)
    sft.add_argument("--pilot-audit", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_binding(args.private_plan, args.public_plan, args.out)
    elif args.command == "record":
        require(args.execute, "explicit_live_execute_flag_required")
        result = record(worker_dir=args.worker_dir,
                        binding_path=args.pilot_binding,
                        public_plan_path=args.public_plan,
                        freeze_path=args.code_freeze,
                        out_dir=args.out_dir)
    elif args.command == "finalize":
        result = finalize(out_dir=args.out_dir,
                          review_path=args.review,
                          binding_path=args.pilot_binding)
    else:
        result = audit_sft_source(out_dir=args.out_dir,
                                  binding_path=args.pilot_binding,
                                  pilot_audit_path=args.pilot_audit)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
