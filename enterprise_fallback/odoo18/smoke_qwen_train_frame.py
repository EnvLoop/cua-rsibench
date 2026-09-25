"""One bounded paid Qwen3.8 image/action sample on a train-only Odoo frame.

No model action is dispatched. The full provider response remains in the
private exactly-once journal; the public receipt contains allowlisted usage,
hashes, action-schema status and reset evidence only. No hidden final frame,
task prompt, gold, credential or application API enters this request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cursibench.scale_action_contract import ContractError, validate_action
from cursibench.scale_vision_proxy import (
    Limits as VisionLimits, QwenVisionRenderer, TinkerVisionBackend,
    VisionSamplingAdapter, campaign_metadata,
    public_receipt as sampling_public_receipt,
)
from factory import PRIVATE, local_config
from gui_controls import browser_login
from odoo_native_adapter import OdooNativeAdapter, VIEWPORT, public_binding
from reset import restore
from worker_lease import exclusive_worker_operation


def smoke(output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    if not os.environ.get("TINKER_API_KEY"):
        raise RuntimeError("TINKER_API_KEY is required; no provider call made")
    with exclusive_worker_operation("smoke_qwen_train_frame"):
        config = local_config()
        if config.get("ODOO_PARTITION") != "train":
            raise RuntimeError("Paid smoke is restricted to the train-only Odoo worker")
        world = json.loads((PRIVATE / "partition_cases.json").read_text())
        case = world["cases"]["purchase"][0]
        task_sets = json.loads((PRIVATE / "task_set_manifest.json").read_text())
        binding = next(row["package_sha256"] for row in task_sets["train"]
                       if row["task_id"] == case["id"])
        credentials = json.loads((PRIVATE / "actor_credentials.json").read_text())
        before = restore()
        if not before["business_snapshot_equal"] or not before["physical_filestore_equal_before_web_restart"]:
            raise RuntimeError("Train worker was not restored before paid sampling")
        provider_result = None
        action_status = "not_sampled"
        action_error = None
        service = None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport=VIEWPORT)
                    browser_login(page, int(config["ODOO_PORT"]),
                                  credentials["password"], credentials["login"])
                    page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/purchase")
                    page.get_by_role("searchbox").wait_for()
                    adapter = OdooNativeAdapter(page, task_id=case["id"],
                        task_binding_sha256=binding, instruction=case["prompt"])
                    observation, rendered = adapter.observe()
                    import tinker

                    renderer = QwenVisionRenderer.load()
                    service = tinker.ServiceClient(user_metadata=campaign_metadata(
                        "odoo-train-frame-smoke"))
                    backend = TinkerVisionBackend.from_service(service, renderer)
                    sampler = VisionSamplingAdapter(
                        backend, PRIVATE / "qwen_train_frame_smoke_journal",
                        limits=VisionLimits(max_actions=1, output_tokens=256,
                                            request_timeout_seconds=120))
                    provider_result = sampler.sample(
                        request_id="odoo-train-frame-smoke-v1-20260925",
                        image_bytes=rendered["image_bytes"],
                        instruction=rendered["instruction"],
                        visible_text=rendered["visible_text"])
                    if provider_result["status"] == "completed":
                        try:
                            validate_action(provider_result["text"], observation,
                                            current_frame_id=observation.frame_id)
                            action_status = "valid_not_dispatched"
                        except ContractError as error:
                            action_status = "rejected_not_dispatched"
                            action_error = error.code
                    else:
                        action_status = "provider_error_no_action"
                finally:
                    browser.close()
        finally:
            if service is not None:
                try:
                    service.close("success" if provider_result and provider_result["status"] == "completed"
                                  else "errored").result(timeout=30)
                except Exception:
                    pass
            after = restore()
        if provider_result is None:
            raise RuntimeError("Provider returned no accountable result")
        public = {"schema": "envloop-odoo-qwen38-train-frame-smoke-v1",
            "status": "sampled" if provider_result["status"] == "completed" else "provider_error",
            "partition": "train_only", "official_hidden_task_used": False,
            "model_actions_dispatched": 0,
            "student": "Qwen/Qwen3.8-27B",
            "model_action_schema_status": action_status,
            "model_action_error_code": action_error,
            "sampling": sampling_public_receipt(provider_result),
            "odoo_binding": public_binding(),
            "post_sample_database_filestore_reset_exact": (
                after["business_snapshot_equal"]
                and after["physical_filestore_equal_before_web_restart"]),
            "host_only_gold_or_sql_in_model_input": False,
            "provider_cost_usd": None}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(public, indent=2) + "\n")
        if public["status"] != "sampled" or not public["post_sample_database_filestore_reset_exact"]:
            raise RuntimeError("Bounded Qwen train-frame smoke did not complete cleanly")
        return public


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = smoke(args.output)
    print(json.dumps({key: result[key] for key in (
        "status", "partition", "official_hidden_task_used",
        "model_action_schema_status", "post_sample_database_filestore_reset_exact")}, indent=2))
