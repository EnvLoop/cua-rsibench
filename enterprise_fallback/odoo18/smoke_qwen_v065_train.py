"""Bounded Qwen3.8 v0.6.5 model actions in the original Odoo train GUI.

Trusted setup/reset and SQL scoring stay on the host. The student receives
only current screenshots, visible controls and one train instruction. The
private journal preserves model text; public evidence is aggregate-only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

from cursibench import scale_action_contract, scale_action_output_v062
from cursibench import scale_action_output_v064, scale_action_output_v065
from cursibench.scale_action_contract import ContractError
from cursibench.scale_vision_proxy import (
    Limits as VisionLimits, QwenVisionRenderer, TinkerVisionBackend,
    VisionSamplingAdapter, campaign_metadata,
    public_receipt as sampling_public_receipt,
)
from factory import PRIVATE, local_config
from gui_controls import browser_login
from odoo_native_adapter import OdooNativeAdapter, VIEWPORT
from reset import restore
from verify import score
from worker_lease import exclusive_worker_operation


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_digest(module) -> str:
    return digest(Path(module.__file__).read_bytes())


def smoke(output: Path, *, max_actions: int = 2, max_samples: int = 3) -> dict:
    from playwright.sync_api import sync_playwright

    if (not 1 <= max_actions <= max_samples <= 5
            or not os.environ.get("TINKER_API_KEY")):
        raise ValueError("Bounded sample cap or Tinker credential missing")
    if output.exists() or output.parent.resolve() != PRIVATE.resolve():
        raise ValueError("Private output must be a new train-worker directory")
    with exclusive_worker_operation("smoke_odoo_v065_train"):
        config = local_config()
        if config.get("ODOO_PARTITION") != "train":
            raise ValueError("v0.6.5 smoke is restricted to an isolated train worker")
        world_raw = (PRIVATE / "partition_cases.json").read_bytes()
        world = json.loads(world_raw)
        case = world["cases"]["purchase"][0]
        task_set_raw = (PRIVATE / "task_set_manifest.json").read_bytes()
        task_sets = json.loads(task_set_raw)
        matches = [row for row in task_sets["train"] if row["task_id"] == case["id"]]
        if len(matches) != 1 or len(task_sets["train"]) != 20:
            raise ValueError("Train case does not match the private 20-task set")
        credentials = json.loads((PRIVATE / "actor_credentials.json").read_bytes())
        output.mkdir(mode=0o700)
        receipt = {
            "schema": "envloop-odoo-qwen-v065-native-train-smoke-v1",
            "status": "started", "failure_class": None,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "partition": "train", "private_task_id": case["id"],
            "package_sha256": matches[0]["package_sha256"],
            "train_world_sha256": digest(world_raw),
            "task_set_manifest_sha256": digest(task_set_raw),
            "model": "Qwen/Qwen3.8-27B", "max_actions": max_actions,
            "max_samples": max_samples, "sampling_output_tokens_cap": 512,
            "sampling_request_timeout_seconds": 120,
            "shared_full_action_validator_sha256": source_digest(scale_action_contract),
            "shared_minimal_v062_sha256": source_digest(scale_action_output_v062),
            "shared_minimal_v064_sha256": source_digest(scale_action_output_v064),
            "selected_v065_sha256": source_digest(scale_action_output_v065),
            "odoo_native_adapter_sha256": digest(Path(__file__).with_name(
                "odoo_native_adapter.py").read_bytes()),
            "train_runner_sha256": digest(Path(__file__).read_bytes()),
            "observations": [], "samples": [], "actions": [],
            "provider_billed_usd": None, "official_hidden_used": False,
            "official_model_result_count": 0,
        }

        def persist():
            (output / "receipt.json").write_text(json.dumps(
                receipt, indent=2, sort_keys=True) + "\n")

        persist()
        service = None
        browser = None
        reset_after = None
        try:
            receipt["stage"] = "restore_train_world"
            before = restore()
            receipt["pre_model_full_reset_exact"] = bool(
                before["business_snapshot_equal"] and
                before["physical_filestore_equal_before_web_restart"])
            if not receipt["pre_model_full_reset_exact"]:
                raise RuntimeError("Train database/filestore reset was not exact")
            baseline = score(case["id"])
            receipt["train_baseline_reward_zero"] = baseline["reward"] == 0.0
            if not receipt["train_baseline_reward_zero"]:
                raise RuntimeError("Train task unexpectedly solved before model")
            with sync_playwright() as playwright:
                receipt["stage"] = "trusted_browser_setup"
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport=VIEWPORT)
                browser_login(page, int(config["ODOO_PORT"]),
                              credentials["password"], credentials["login"])
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                page.get_by_role("searchbox").wait_for()
                adapter = OdooNativeAdapter(
                    page, task_id=case["id"],
                    task_binding_sha256=matches[0]["package_sha256"],
                    instruction=case["prompt"])
                receipt["stage"] = "initialize_qwen_base_sampler"
                import tinker
                renderer = QwenVisionRenderer.load()
                receipt["renderer_identity"] = renderer.identity
                service = tinker.ServiceClient(user_metadata=campaign_metadata(
                    "odoo-v065-train-smoke"))
                backend = TinkerVisionBackend.from_service(service, renderer)
                sampler = VisionSamplingAdapter(
                    backend, output / "sampler-journal",
                    limits=VisionLimits(max_actions=max_samples, output_tokens=512,
                                        request_timeout_seconds=120))
                receipt["sampling_binding_sha256"] = sampler.binding_sha256
                persist()
                memory = ""
                for sample_index in range(max_samples):
                    receipt["stage"] = "model_observation"
                    observation, _ = adapter.observe(memory=memory)
                    frame = observation.screenshot_bytes
                    (output / f"frame-{sample_index}.png").write_bytes(frame)
                    receipt["observations"].append({
                        "step": observation.step,
                        "frame_sha256": digest(frame),
                        "visible_control_count": len(observation.controls),
                        "frame_id_sha256": digest(observation.frame_id.encode()),
                    })
                    rendered = scale_action_output_v065.render_for_model(observation)
                    request_id = "odoo-v065-" + secrets.token_hex(16)
                    receipt["samples"].append({
                        "request_id_sha256": digest(request_id.encode()),
                        "status": "intent_recorded_before_dispatch",
                    })
                    persist()
                    receipt["stage"] = "tinker_sampling"
                    result = sampler.sample(request_id=request_id, **rendered)
                    receipt["samples"][-1] = sampling_public_receipt(result)
                    persist()
                    if result["status"] != "completed":
                        receipt["status"] = "provider_sampling_error"
                        receipt["failure_class"] = "provider"
                        receipt["provider_error_subtype"] = result.get("error_subtype")
                        break
                    receipt["stage"] = "validate_model_action"
                    try:
                        action = scale_action_output_v065.normalize_model_action(
                            result["text"], observation,
                            current_frame_id=observation.frame_id)
                    except ContractError as exc:
                        receipt["actions"].append({
                            "step": observation.step, "status": "model_output_rejected",
                            "error_code": exc.code,
                        })
                        receipt["status"] = "model_output_rejected"
                        receipt["failure_class"] = "model_interface"
                        break
                    receipt["stage"] = "native_gui_dispatch"
                    try:
                        applied = adapter.dispatch(action)
                    except ContractError as exc:
                        receipt["actions"].append({
                            "step": observation.step, "status": "environment_dispatch_rejected",
                            "error_code": exc.code,
                        })
                        receipt["status"] = "environment_dispatch_rejected"
                        receipt["failure_class"] = "environment"
                        break
                    receipt["actions"].append({
                        "step": observation.step, "status": "applied",
                        "type": action["type"],
                        "target_kind": ("ref" if "target" in action and
                                        "ref" in action["target"] else
                                        "coordinate" if "target" in action else None),
                        "public_contract_receipt": applied["public_contract_receipt"],
                    })
                    persist()
                    memory = action["memory"]
                    if applied["finished"]:
                        receipt["status"] = "model_finished"
                        break
                    if len([row for row in receipt["actions"] if row["status"] == "applied"]) >= max_actions:
                        receipt["status"] = "action_budget_reached"
                        break
                else:
                    receipt["status"] = "sample_budget_reached"
                browser.close()
                browser = None
            receipt["stage"] = "independent_train_readback"
            after_model = score(case["id"])
            receipt["train_reward_after_model"] = after_model["reward"]
        except Exception as exc:
            receipt["status"] = "infrastructure_or_runner_error"
            receipt["failure_class"] = "infrastructure"
            receipt["error_type"] = type(exc).__name__
            receipt["error_message_private"] = str(exc)[:400]
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception as exc:
                    receipt["browser_close_error_type"] = type(exc).__name__
            if service is not None:
                try:
                    service.close("success" if receipt["status"] not in (
                        "provider_sampling_error", "infrastructure_or_runner_error")
                        else "errored").result(timeout=30)
                    receipt["tinker_session_closed"] = True
                except Exception as exc:
                    receipt["tinker_close_error_type"] = type(exc).__name__
            try:
                reset_after = restore()
                receipt["post_model_full_reset_exact"] = bool(
                    reset_after["business_snapshot_equal"] and
                    reset_after["physical_filestore_equal_before_web_restart"])
            except Exception as exc:
                receipt["post_reset_error_type"] = type(exc).__name__
                receipt["post_model_full_reset_exact"] = False
            if not receipt.get("post_model_full_reset_exact"):
                receipt["status"] = "infrastructure_or_runner_error"
                receipt["failure_class"] = "infrastructure"
            receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
            persist()
        print(json.dumps({
            "status": receipt["status"],
            "failure_class": receipt["failure_class"],
            "completed_samples": sum(row.get("status") == "completed"
                                     for row in receipt["samples"]),
            "applied_gui_actions": sum(row.get("status") == "applied"
                                       for row in receipt["actions"]),
            "post_model_reset_exact": receipt.get("post_model_full_reset_exact"),
        }, sort_keys=True))
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-actions", type=int, default=2)
    parser.add_argument("--max-samples", type=int, default=3)
    args = parser.parse_args()
    receipt = smoke(args.out_dir, max_actions=args.max_actions,
                    max_samples=args.max_samples)
    return 0 if (receipt.get("post_model_full_reset_exact") and
                 receipt.get("failure_class") is None and
                 any(row.get("status") == "applied" for row in receipt["actions"])) else 2


if __name__ == "__main__":
    raise SystemExit(main())
