"""Proposed shared v0.6.6 GitLab GUI mapping for train-only pilots.

This module does not select a task, call a provider, or change the historical
v0.6.4 runner. A future live pilot must bind a train task, cold reset, actor
role, model request and independent saved-state verifier separately. The
candidate shared-source hash is checked at every public action boundary.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from cursibench import shared_action_bundle_v066
from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_contract_v066 import (
    public_receipt, validate_action,
)
from cursibench.scale_action_output_v066 import (
    normalize_model_action, render_for_model,
)

from . import vision_actor as prior


PROPOSED_SHARED_BUNDLE_SHA256 = (
    "60f1fc50990118da44c11df3d54b05e0ddf709464401308d9d8c9fa61cd43041"
)
TRAIN_ONLY = True

# Reuse the frozen browser-origin guard and observation construction. Only the
# action profile and its GUI dispatch mapping differ from the historical actor.
Frame = prior.Frame
capture = prior.capture
install_local_guard = prior.install_local_guard
local_origin = prior.local_origin


def assert_shared_stack() -> dict:
    historical = prior.assert_shared_stack()
    bundle = shared_action_bundle_v066.build(Path(__file__).resolve().parents[1])
    if bundle["bundle_sha256"] != PROPOSED_SHARED_BUNDLE_SHA256:
        raise RuntimeError("proposed GitLab v0.6.6 shared action source changed")
    return {"historical_source_sha256s": historical,
            "proposed_v066_bundle_sha256": bundle["bundle_sha256"]}


def _require_train(partition: str) -> None:
    if partition != "train":
        raise ContractError("invalid_action")


def model_request(frame: Frame, *, task_partition: str) -> dict[str, bytes | str]:
    _require_train(task_partition)
    assert_shared_stack()
    return render_for_model(frame.observation)


async def _current(page, frame: Frame, action: dict) -> None:
    # The historical check compares the exact observed screenshot bytes, URL,
    # visible ref labels/roles and underlying DOM-node identities. Repeat the
    # pixel check after its ref enumeration, directly before dispatch.
    projected = ({**action, "type": "click"}
                 if action["type"] == "double_click" else
                 {"type": "wait"}
                 if action["type"] == "type" and "target" not in action else
                 action)
    if not await prior._fresh(page, frame, projected):
        raise ContractError("stale_frame")
    if page.url != frame.page_url or not local_origin(page.url):
        raise ContractError("stale_frame")
    image = await page.screenshot(type="png", full_page=False,
                                  animations="disabled",
                                  mask=[page.locator('input[type="password"]')])
    if (page.url != frame.page_url or not local_origin(page.url) or
            hashlib.sha256(image).hexdigest()
            != frame.observation.screenshot["sha256"]):
        raise ContractError("stale_frame")


async def validate_and_dispatch(page, raw_model_action: str,
                                frame: Frame, *, task_partition: str) -> tuple[dict, dict]:
    """Validate one model response and dispatch one current-frame GUI action."""
    _require_train(task_partition)
    assert_shared_stack()
    action = normalize_model_action(raw_model_action, frame.observation,
                                    current_frame_id=frame.observation.frame_id)
    checked = validate_action(action, frame.observation,
                              current_frame_id=frame.observation.frame_id)
    kind = checked["type"]
    if kind not in {"click", "double_click", "type", "key", "scroll", "drag",
                    "wait", "finish"}:
        raise ContractError("invalid_action")
    await _current(page, frame, checked)

    if kind == "finish":
        pass
    elif kind == "wait":
        await page.wait_for_timeout(checked["duration_ms"])
    elif kind in ("click", "double_click"):
        target = checked["target"]
        if "ref" in target:
            handle = frame.handles[target["ref"]]
            if kind == "double_click":
                await handle.dblclick(timeout=15000)
            else:
                await handle.click(timeout=15000)
        elif kind == "double_click":
            await page.mouse.dblclick(target["x"], target["y"])
        else:
            await page.mouse.click(target["x"], target["y"])
    elif kind == "type":
        if "target" not in checked:
            if checked["mode"] != "insert":
                raise ContractError("invalid_action")
            await page.keyboard.insert_text(checked["text"])
        else:
            target = checked["target"]
            if "ref" in target:
                handle = frame.handles[target["ref"]]
                if checked["mode"] == "fill":
                    await handle.fill(checked["text"], timeout=15000)
                else:
                    await handle.focus()
                    await page.keyboard.insert_text(checked["text"])
            else:
                await page.mouse.click(target["x"], target["y"])
                if checked["mode"] == "fill":
                    await page.keyboard.press("ControlOrMeta+A")
                await page.keyboard.insert_text(checked["text"])
    elif kind == "key":
        if "target" in checked:
            target = checked["target"]
            if "ref" in target:
                await frame.handles[target["ref"]].focus()
            else:
                await page.mouse.click(target["x"], target["y"])
        # The shared validator checked historical and four new chords.
        await page.keyboard.press(checked["key"])
    elif kind == "scroll":
        if "target" in checked:
            target = checked["target"]
            if "ref" in target:
                await frame.handles[target["ref"]].hover()
            else:
                await page.mouse.move(target["x"], target["y"])
        await page.mouse.wheel(checked["dx"], checked["dy"])
    elif kind == "drag":
        x1, y1 = await prior._point(page, checked["from"], frame.handles)
        x2, y2 = await prior._point(page, checked["to"], frame.handles)
        await page.mouse.move(x1, y1)
        await page.mouse.down()
        await page.mouse.move(x2, y2, steps=8)
        await page.mouse.up()

    return ({"status": "applied", "code": "ok"},
            public_receipt(frame.observation, action=checked))


__all__ = ["Frame", "capture", "install_local_guard", "local_origin",
           "assert_shared_stack", "model_request", "validate_and_dispatch"]
