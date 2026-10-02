"""No-model, train-only Odoo GUI smoke for the proposed v0.6.6 profile.

The trusted controller chooses one public-training RFQ and its known correction,
but every actor edit goes through a fresh screenshot, the shared action parser,
and Odoo's v0.6.6 mouse/keyboard dispatcher. The independent verifier reads
persisted business state and protected source files after the browser closes.
This entry point never opens selection or hidden-final packages or a provider.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from cursibench.scale_action_contract import ContractError
from cursibench import scale_action_contract, scale_action_contract_v066
from cursibench import scale_action_output_v066
from enterprise_fallback.odoo18 import odoo_v066_train_adapter
from factory import HERE, PRIVATE, local_config
from gui_controls import browser_login
from reset import restore
from verify import score
from worker_lease import exclusive_worker_operation


SCHEMA = "envloop-odoo-v066-native-train-gui-smoke-v1"
MAX_ACTIONS = 12
WALL_SECONDS = 420


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _save(path: Path, raw: bytes) -> None:
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(handle, raw)
        os.fsync(handle)
    finally:
        os.close(handle)


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", "--env-file", ".env", *args],
                          cwd=HERE, check=True, capture_output=True, text=True)


def _running_services() -> set[str]:
    result = _compose("ps", "--status", "running", "--services")
    return set(result.stdout.splitlines())


def _source_hashes() -> dict[str, str]:
    paths = {
        "smoke": Path(__file__),
        "odoo_v066_adapter": Path(odoo_v066_train_adapter.__file__),
        "odoo_native_adapter": Path(odoo_v066_train_adapter.__file__).with_name(
            "odoo_native_adapter.py"),
        "full_validator_v066": Path(scale_action_contract_v066.__file__),
        "minimal_output_v066": Path(scale_action_output_v066.__file__),
        "base_contract": Path(scale_action_contract.__file__),
        "pinned_compose": HERE / "compose.yaml",
        "independent_verifier": Path(__file__).with_name("verify.py"),
        "checkpoint_restore": Path(__file__).with_name("reset.py"),
    }
    return {name: sha(path.read_bytes()) for name, path in paths.items()}


def _train_case() -> tuple[dict, str, str, str]:
    config = local_config()
    if config.get("ODOO_PARTITION") != "train" or HERE.name != "train":
        raise ValueError("Only the isolated original Odoo train worker is allowed")
    world_raw = (PRIVATE / "partition_cases.json").read_bytes()
    task_sets_raw = (PRIVATE / "task_set_manifest.json").read_bytes()
    world = json.loads(world_raw)
    task_sets = json.loads(task_sets_raw)
    case = world["cases"]["purchase"][0]
    if len(task_sets["train"]) != 20:
        raise ValueError("The train partition must contain exactly 20 tasks")
    matches = [row for row in task_sets["train"] if row["task_id"] == case["id"]]
    if len(matches) != 1:
        raise ValueError("Training case/package binding mismatch")
    changed = [(line, key) for line in case["lines"]
               for key in ("qty", "price", "date")
               if line["initial"][key] != line["expected"][key]]
    if len(changed) != 1 or changed[0][1] != "price":
        raise ValueError("Expected a one-price training-only control")
    return (case, matches[0]["package_sha256"], sha(world_raw),
            sha(task_sets_raw))


def smoke(output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    os.umask(0o077)
    output = output.resolve()
    if output.exists() or output.parent != PRIVATE.resolve():
        raise ValueError("New private output directory must be under train worker")

    with exclusive_worker_operation("smoke_odoo_v066_train"):
        case, package_sha, world_sha, task_set_sha = _train_case()
        config = local_config()
        credentials = json.loads((PRIVATE / "actor_credentials.json").read_bytes())
        was_running = _running_services()
        output.mkdir(mode=0o700)
        receipt = {
            "schema": SCHEMA, "status": "started", "stage": "startup",
            "failure_class": None,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "partition": "train_only", "private_task_id": case["id"],
            "private_package_sha256": package_sha,
            "private_train_world_sha256": world_sha,
            "private_task_set_sha256": task_set_sha,
            "action_profile": "scale-action-profile-v0.6.6",
            "minimal_output_version": "scale-action-output-v0.6.6",
            "source_sha256": _source_hashes(),
            "max_actions": MAX_ACTIONS, "wall_seconds": WALL_SECONDS,
            "provider_calls": 0, "model_calls": 0,
            "official_final_tasks_observed": 0,
            "observations": [], "actions": [],
            "worker_services_running_before": sorted(was_running),
        }

        def persist() -> None:
            path = output / "receipt.json"
            raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
            tmp = output / "receipt.json.tmp"
            with tmp.open("wb") as stream:
                os.chmod(tmp, 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)

        persist()
        browser = None
        started = time.monotonic()
        try:
            receipt["stage"] = "start_pinned_train_worker"
            if not {"db", "web"} <= was_running:
                _compose("up", "-d", "db", "web")
            receipt["stage"] = "cold_restore_before"
            before = restore()
            receipt["pre_full_reset_exact"] = bool(
                before["business_snapshot_equal"] and
                before["physical_filestore_equal_before_web_restart"])
            if not receipt["pre_full_reset_exact"]:
                raise RuntimeError("Train checkpoint restore was inexact")
            baseline = score(case["id"])
            receipt["independent_baseline_unsolved"] = baseline["reward"] == 0.0
            if not receipt["independent_baseline_unsolved"]:
                raise RuntimeError("Train case was solved at baseline")

            with sync_playwright() as playwright:
                receipt["stage"] = "native_gui"
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport=odoo_v066_train_adapter.VIEWPORT)
                browser_login(page, int(config["ODOO_PORT"]),
                              credentials["password"], credentials["login"])
                # The starting application route is trusted environment setup;
                # all task navigation/editing below is GUI action dispatch.
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                page.get_by_role("searchbox").wait_for()
                adapter = odoo_v066_train_adapter.OdooV066TrainAdapter(
                    page, task_id=case["id"],
                    task_binding_sha256=package_sha,
                    instruction=case["prompt"])

                def act(kind: str, *, ref: str | None = None,
                        locator=None, **fields) -> None:
                    if len(receipt["actions"]) >= MAX_ACTIONS or time.monotonic() - started > WALL_SECONDS:
                        raise RuntimeError("Bounded train smoke budget exceeded")
                    # Only stale-frame rejections before mouse/keyboard
                    # dispatch may be retried, each on a newly observed frame.
                    # Odoo's inline editor occasionally repaints while the
                    # cursor settles. All rejected frames stay in the journal.
                    for retry in range(3):
                        if time.monotonic() - started > WALL_SECONDS:
                            raise RuntimeError("Bounded train smoke wall time exceeded")
                        box = locator.bounding_box() if locator is not None else None
                        if locator is not None and box is None:
                            raise RuntimeError("Visible GUI target has no box")
                        obs, rendered = adapter.observe_for_model()
                        frame_path = output / f"frame-{len(receipt['observations']):02d}.png"
                        _save(frame_path, obs.screenshot_bytes)
                        receipt["observations"].append({
                            "step": obs.step,
                            "frame_sha256": sha(obs.screenshot_bytes),
                            "frame_id_sha256": sha(obs.frame_id.encode()),
                            "visible_control_count": len(obs.controls),
                            "renderer_instruction_sha256": sha(rendered["instruction"].encode()),
                            "renderer_image_sha256": sha(rendered["image_bytes"]),
                        })
                        payload = {"type": kind, **fields}
                        if ref is not None:
                            matches = [row for row in obs.controls if row.ref == ref]
                            if len(matches) != 1:
                                raise RuntimeError("Requested visible GUI ref absent")
                            payload["target"] = {"ref": ref}
                        elif locator is not None:
                            payload["target"] = {
                                "x": int(box["x"] + box["width"] / 2),
                                "y": int(box["y"] + box["height"] / 2),
                            }
                        raw = json.dumps(payload, separators=(",", ":"))
                        try:
                            action = adapter.parse_current_action(raw)
                            applied = adapter.dispatch(action)
                        except ContractError as exc:
                            current = page.screenshot(type="png")
                            diagnostic = output / f"rejected-step-{obs.step:02d}-{retry}.png"
                            _save(diagnostic, current)
                            receipt.setdefault("rejected_actions", []).append({
                                "step": obs.step, "kind": kind,
                                "code": exc.code,
                                "observed_frame_sha256": sha(obs.screenshot_bytes),
                                "current_frame_sha256": sha(current),
                            })
                            persist()
                            if exc.code != "stale_frame" or retry == 2:
                                raise
                            page.wait_for_timeout(150)
                            continue
                        receipt["actions"].append({
                            "step": obs.step, "type": kind,
                            "target_kind": ("ref" if ref is not None else
                                            "coordinate" if locator is not None else None),
                            "pre_dispatch_frame_sha256": sha(obs.screenshot_bytes),
                            "public_contract_receipt": applied["public_contract_receipt"],
                        })
                        persist()
                        return

                # Search and open the one training RFQ through current-frame
                # browser controls. The host chooses targets as a known-answer
                # controller; the actor path receives only the GUI surface.
                observation, _ = adapter.observe_for_model()
                search = next(row.ref for row in observation.controls
                              if row.role == "searchbox")
                act("type", ref=search, text=case["id"], mode="fill")
                act("key", key="Enter")
                page.get_by_role("cell", name=case["id"], exact=True).wait_for()
                observation, _ = adapter.observe_for_model()
                row_ref = next(row.ref for row in observation.controls
                               if row.role == "td" and row.label == case["id"])
                act("click", ref=row_ref)
                page.wait_for_url("**/odoo/purchase/*")

                changed_line = next(line for line in case["lines"]
                                    if line["initial"]["price"] != line["expected"]["price"])
                price_cell = page.locator("tr").filter(
                    has_text=changed_line["sku"]).first.locator('td[name="price_unit"]')
                price_cell.wait_for()
                # Odoo enters its inline editor on one click. A subsequent
                # double click inside the *visible input* tests the new GUI
                # primitive without assuming that double-clicking the static
                # table cell enters edit mode on this pinned Odoo version.
                act("click", locator=price_cell)
                editor = page.locator('td[name="price_unit"] input').first
                editor.wait_for()
                page.wait_for_timeout(700)
                act("double_click", locator=editor)
                active = page.evaluate("() => ({tag: document.activeElement?.tagName, name: document.activeElement?.getAttribute('name')})")
                receipt["editor_focus_after_double_click"] = active
                if active["tag"] != "INPUT":
                    raise RuntimeError("Native price editor did not receive focus")
                act("key", key="Meta+A")
                act("type", text=str(changed_line["expected"]["price"]), mode="insert")
                act("key", key="Tab")
                page.wait_for_timeout(500)
                save = page.get_by_role("button", name="Save", exact=True)
                if save.count() and save.is_visible():
                    act("click", locator=save)
                    save.wait_for(state="hidden")
                else:
                    page.wait_for_timeout(350)
                page.reload()
                reloaded_price = page.locator("tr").filter(
                    has_text=changed_line["sku"]).first.locator('td[name="price_unit"]')
                reloaded_price.wait_for()
                receipt["gui_price_persisted_after_reload"] = (
                    round(float(reloaded_price.inner_text().strip()), 2)
                    == round(changed_line["expected"]["price"], 2))
                persist()
                browser.close()
                browser = None

            receipt["stage"] = "independent_persisted_readback"
            after = score(case["id"])
            receipt["independent_positive_reward_one"] = after["reward"] == 1.0
            receipt["independent_checks_passed"] = after["checks_passed"]
            receipt["independent_difference_codes"] = after["difference_codes"]
            receipt["status"] = "passed" if receipt["independent_positive_reward_one"] else "verifier_failed"
            if receipt["status"] != "passed":
                receipt["failure_class"] = "business_state"
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["failure_class"] = "infrastructure_or_controller"
            receipt["error_type"] = type(exc).__name__
            receipt["error_message_private"] = str(exc)[:400]
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception as exc:
                    receipt["browser_close_error_type"] = type(exc).__name__
            try:
                receipt["stage"] = "cold_restore_after"
                after_restore = restore()
                receipt["post_full_reset_exact"] = bool(
                    after_restore["business_snapshot_equal"] and
                    after_restore["physical_filestore_equal_before_web_restart"])
            except Exception as exc:
                receipt["post_full_reset_exact"] = False
                receipt["post_reset_error_type"] = type(exc).__name__
            try:
                if "web" not in was_running:
                    _compose("stop", "web")
                if "db" not in was_running:
                    _compose("stop", "db")
                receipt["worker_services_restored_to_initial_state"] = (
                    _running_services() == was_running)
            except Exception as exc:
                receipt["worker_services_restored_to_initial_state"] = False
                receipt["worker_stop_error_type"] = type(exc).__name__
            if not receipt.get("post_full_reset_exact") or not receipt.get(
                    "worker_services_restored_to_initial_state"):
                receipt["status"] = "failed"
                receipt["failure_class"] = "infrastructure_or_controller"
            receipt["stage"] = "complete"
            receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
            persist()
        print(json.dumps({
            "status": receipt["status"],
            "failure_class": receipt["failure_class"],
            "validated_gui_actions": len(receipt["actions"]),
            "independent_positive_reward_one": receipt.get("independent_positive_reward_one"),
            "pre_full_reset_exact": receipt.get("pre_full_reset_exact"),
            "post_full_reset_exact": receipt.get("post_full_reset_exact"),
            "worker_services_restored": receipt.get("worker_services_restored_to_initial_state"),
        }, sort_keys=True))
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt = smoke(args.out_dir)
    return 0 if receipt["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
