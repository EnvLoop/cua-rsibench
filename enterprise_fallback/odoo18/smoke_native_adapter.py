"""Static-browser acceptance of the shared action contract Odoo adapter."""

from __future__ import annotations

import json

from cursibench.scale_action_contract import ContractError, VERSION
from odoo_native_adapter import OdooNativeAdapter, VIEWPORT


def _action(observation, kind: str, **extra) -> dict:
    return {"version": VERSION, "task_id": observation.task_id,
            "task_binding_sha256": observation.task_binding_sha256,
            "step": observation.step, "frame_id": observation.frame_id,
            "type": kind, "memory": "static control", **extra}


def smoke() -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport=VIEWPORT)
            page.set_content("""<button onclick="document.querySelector('#count').textContent='1'">Increment</button>
                <input aria-label="Customer reference"><span id="count">0</span>""")
            adapter = OdooNativeAdapter(page, task_id="odoo-static-contract",
                                        task_binding_sha256="a" * 64,
                                        instruction="Click Increment and fill Customer reference.")
            observation, rendered = adapter.observe()
            click_ref = next(row.ref for row in observation.controls if row.label == "Increment")
            click = _action(observation, "click", target={"ref": click_ref})
            adapter.dispatch(click)
            if page.locator("#count").inner_text() != "1":
                raise RuntimeError("Validated click was not dispatched")
            try:
                adapter.dispatch(click)
            except ContractError as error:
                replay_rejected = error.code == "stale_frame"
            else:
                replay_rejected = False
            if not replay_rejected:
                raise RuntimeError("A used frame was replayable")
            observation, _ = adapter.observe(memory="Counter is now 1.")
            field_ref = next(row.ref for row in observation.controls
                             if row.label == "Customer reference")
            typed = _action(observation, "type", target={"ref": field_ref},
                            text="CPO-VALID", mode="fill")
            adapter.dispatch(typed)
            if page.get_by_role("textbox", name="Customer reference").input_value() != "CPO-VALID":
                raise RuntimeError("Validated fill did not persist in native input")
            observation, _ = adapter.observe()
            stale = _action(observation, "finish")
            page.locator("#count").evaluate("el => el.textContent = '2'")
            try:
                adapter.dispatch(stale)
            except ContractError as error:
                external_change_rejected = error.code == "stale_frame"
            else:
                external_change_rejected = False
            if not external_change_rejected:
                raise RuntimeError("A changed screenshot did not invalidate the frame")
            observation, _ = adapter.observe()
            adapter.dispatch(_action(observation, "finish"))
            return {"schema": "envloop-odoo-native-adapter-static-smoke-v1",
                    "status": "passed", "contract_version": VERSION,
                    "screenshot_rendered": bool(rendered["image_bytes"]),
                    "visible_controls_present": len(observation.controls) >= 2,
                    "ref_click_applied": True, "ref_fill_applied": True,
                    "used_frame_replay_rejected": replay_rejected,
                    "external_visual_change_rejected": external_change_rejected,
                    "model_calls": 0, "odoo_application_calls": 0}
        finally:
            browser.close()


if __name__ == "__main__":
    print(json.dumps(smoke(), indent=2))
