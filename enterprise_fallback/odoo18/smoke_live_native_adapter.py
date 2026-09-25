"""Read-only native Odoo control smoke under the shared v0.6 model boundary.

Uses one train-only task. It navigates/searches through validated GUI actions,
then proves the independent benchmark state remains at its unsolved baseline.
No model call, hidden task, application API actor action, or evaluator gold is
sent into the model-facing observation.
"""

from __future__ import annotations

import json
from pathlib import Path

from cursibench.scale_action_contract import VERSION
from factory import PRIVATE, local_config
from gui_controls import browser_login
from odoo_native_adapter import OdooNativeAdapter, VIEWPORT, public_binding
from reset import restore
from verify import score
from worker_lease import exclusive_worker_operation


def _action(observation, kind: str, **extra) -> dict:
    return {"version": VERSION, "task_id": observation.task_id,
            "task_binding_sha256": observation.task_binding_sha256,
            "step": observation.step, "frame_id": observation.frame_id,
            "type": kind, "memory": "Find the train-only RFQ in native Purchase.", **extra}


def smoke(output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    with exclusive_worker_operation("smoke_odoo_model_boundary"):
        config = local_config()
        if config.get("ODOO_PARTITION") != "train":
            raise RuntimeError("Live model boundary smoke must use a train-only worker")
        world = json.loads((PRIVATE / "partition_cases.json").read_text())
        case = world["cases"]["purchase"][0]
        task_sets = json.loads((PRIVATE / "task_set_manifest.json").read_text())
        package = next(row["package_sha256"] for row in task_sets["train"]
                       if row["task_id"] == case["id"])
        credentials = json.loads((PRIVATE / "actor_credentials.json").read_text())
        initial = restore()
        if not initial["business_snapshot_equal"] or not initial["physical_filestore_equal_before_web_restart"]:
            raise RuntimeError("Native adapter smoke did not start at frozen baseline")
        receipts = []
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
                        task_binding_sha256=package, instruction=case["prompt"])
                    observation, rendered = adapter.observe()
                    search = next(row.ref for row in observation.controls
                                  if row.role == "searchbox")
                    receipts.append(adapter.dispatch(_action(observation, "type",
                        target={"ref": search}, text=case["id"], mode="fill")))
                    observation, _ = adapter.observe()
                    receipts.append(adapter.dispatch(_action(observation, "key", key="Enter")))
                    page.get_by_role("cell", name=case["id"], exact=True).wait_for()
                    observation, _ = adapter.observe()
                    row_ref = next(row.ref for row in observation.controls
                                   if row.role == "td" and row.label == case["id"])
                    receipts.append(adapter.dispatch(_action(observation, "click",
                        target={"ref": row_ref})))
                    page.wait_for_url("**/odoo/purchase/*")
                    native_record_visible = case["id"] in page.locator("body").inner_text()
                    screenshot_observed = bool(rendered["image_bytes"])
                    visible_controls_observed = len(observation.controls) > 0
                finally:
                    browser.close()
            baseline_reward = score(case["id"])["reward"]
        finally:
            final_restore = restore()
        result = {"schema": "envloop-odoo-native-model-boundary-live-smoke-v1",
            "status": "passed" if (native_record_visible and screenshot_observed
                                   and visible_controls_observed and baseline_reward == 0.0
                                   and final_restore["business_snapshot_equal"]
                                   and final_restore["physical_filestore_equal_before_web_restart"])
                      else "failed",
            "application": "original_odoo_community_18",
            "partition": "train_only",
            "model_calls": 0,
            "validated_gui_actions": len(receipts),
            "validated_action_types": [row["action"]["type"] for row in receipts],
            "actual_software_record_visible": native_record_visible,
            "screenshot_observed": screenshot_observed,
            "visible_controls_observed": visible_controls_observed,
            "independent_business_reward_remained_unsolved": baseline_reward == 0.0,
            "final_full_database_filestore_reset_exact": (
                final_restore["business_snapshot_equal"]
                and final_restore["physical_filestore_equal_before_web_restart"]),
            "host_only_evaluator_state_in_model_observation": False,
            "common_model_binding": public_binding(),
            "official_hidden_task_used": False}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        if result["status"] != "passed":
            raise RuntimeError("Live Odoo model boundary smoke failed")
        return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = smoke(args.output)
    print(json.dumps({key: report[key] for key in (
        "status", "partition", "model_calls", "validated_gui_actions",
        "actual_software_record_visible", "final_full_database_filestore_reset_exact")}, indent=2))
