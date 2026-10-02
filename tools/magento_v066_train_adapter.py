"""Proposed v0.6.6 Magento GUI mapping for disposable train pilots.

The original v0.6.3 pilot and its source hashes remain untouched. This module
contains no runner, task selection, provider call or hidden-final read path.
"""

from __future__ import annotations

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_contract_v066 import NEW_KEY_CHORDS, validate_action
from cursibench.scale_action_output_v066 import normalize_model_action, render_for_model
from tools import run_magento_model_pilot_v063 as prior


async def _current(page, observation, frame_url: str, action: dict | None = None,
                   handles: dict | None = None) -> None:
    same, _reason = await prior._same_pixels(page, observation, frame_url)
    if not same:
        raise ContractError("stale_frame")
    if action is not None:
        # v0.6.3's identity check handles click, type, key and scroll refs.
        # A double-click has the identical target semantics as a click.
        projected = ({**action, "type": "click"}
                     if action["type"] == "double_click" else
                     {"type": "wait"}
                     if action["type"] == "type" and "target" not in action
                     else action)
        if not await prior._same_visible_refs(page, projected, observation,
                                              handles or {}):
            raise ContractError("stale_frame")


async def parse_current_action(raw: str, observation, page,
                               frame_url: str) -> dict:
    await _current(page, observation, frame_url)
    return normalize_model_action(raw, observation,
                                  current_frame_id=observation.frame_id)


async def dispatch_current_action(page, action: dict, observation,
                                  handles: dict, frame_url: str) -> dict:
    checked = validate_action(action, observation,
                              current_frame_id=observation.frame_id)
    await _current(page, observation, frame_url, checked, handles)
    # Ref identity may have required another DOM read. Check the observed
    # pixels once more immediately before the sole GUI dispatch path.
    await _current(page, observation, frame_url)
    kind = checked["type"]
    if kind == "double_click":
        target = checked["target"]
        if "ref" in target:
            await handles[target["ref"]].dblclick(timeout=15000)
        else:
            await page.mouse.dblclick(target["x"], target["y"])
    elif kind == "type" and "target" not in checked:
        if checked["mode"] != "insert":
            raise ContractError("invalid_action")
        await page.keyboard.insert_text(checked["text"])
    elif kind == "key" and checked["key"] in NEW_KEY_CHORDS:
        if "target" in checked:
            target = checked["target"]
            if "ref" in target:
                await handles[target["ref"]].focus()
            else:
                await page.mouse.click(target["x"], target["y"])
        await page.keyboard.press(checked["key"])
    else:
        return await prior.host.dispatch_action(page, checked, observation,
                                                handles)
    try:
        await page.wait_for_load_state("networkidle", timeout=60000)
    except Exception as exc:
        if type(exc).__name__ == "TimeoutError":
            raise prior.host.PilotError("action_timeout") from None
        raise
    return {"status": "applied", "code": "ok"}


__all__ = ["render_for_model", "parse_current_action",
           "dispatch_current_action"]
