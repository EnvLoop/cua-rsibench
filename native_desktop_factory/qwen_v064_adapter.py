"""Native Desktop action dispatch for the shared v0.6.4 GUI contract.

The model sees a screenshot and its task instruction only. This module has no
document, shell, or oracle read path; trusted setup and saved-file evaluation
belong to the caller. The caller must take a new screenshot immediately before
dispatch so an action cannot silently target an obsolete frame.
"""

from __future__ import annotations

import hashlib
import io
import time

from cursibench.scale_action_contract import ContractError, ContractLimits, make_observation
from cursibench.scale_action_output_v064 import normalize_model_action, render_for_model


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def application_frame_digest(raw: bytes) -> str:
    """Ignore only volatile XFCE clock chrome and Calc's bottom status bar.

    The E2B Desktop cell fixes 1280x800 resolution. Sheet tabs, app menus,
    document content, and modal dialogs remain in the checked region. This
    avoids spending a model resample when only the clock or status indicator
    changes while still rejecting a changed application frame.
    """
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.size != (1280, 800):
                raise ContractError("stale_frame")
            content = opened.convert("RGB").crop((0, 27, 1280, 780))
            return digest(content.tobytes())
    except (UnidentifiedImageError, OSError, ValueError):
        raise ContractError("stale_frame") from None


def observe(sandbox, *, task_id: str, task_binding_sha256: str,
            instruction: str, step: int, previous_action_result=None,
            memory: str = "", max_actions: int = 5):
    """Build a screenshot-only trusted frame; no synthetic UI refs are added."""
    screenshot = bytes(sandbox.screenshot())
    return make_observation(
        task_id=task_id, task_binding_sha256=task_binding_sha256,
        instruction=instruction, step=step, screenshot_bytes=screenshot,
        a11y_text="", dom_text="", controls=(),
        previous_action_result=previous_action_result, memory=memory,
        limits=ContractLimits(max_step=max_actions),
    )


def parse_current_action(raw: str, observation, sandbox):
    """Recheck the physical screen and current frame before returning action."""
    if application_frame_digest(bytes(sandbox.screenshot())) != application_frame_digest(
            observation.screenshot_bytes):
        raise ContractError("stale_frame")
    return normalize_model_action(raw, observation,
                                  current_frame_id=observation.frame_id)


def _point(target: dict) -> tuple[int, int]:
    # Native Desktop currently emits no accessibility refs, so the common
    # contract has already rejected them as stale. Never infer a coordinate.
    if set(target) != {"x", "y"}:
        raise ContractError("stale_frame")
    return target["x"], target["y"]


def dispatch(sandbox, action: dict) -> str:
    """Apply one validated GUI action; return a bounded public action type."""
    kind = action["type"]
    if kind == "finish":
        return kind
    if kind == "click":
        sandbox.left_click(*_point(action["target"]))
    elif kind == "type":
        if action["mode"] == "fill":
            # A pixel has no field boundary. Ctrl+A would select an entire
            # worksheet or document, so this common action needs scoped
            # accessibility controls before native Desktop can support it.
            raise ContractError("invalid_action")
        sandbox.left_click(*_point(action["target"]))
        sandbox.write(action["text"])
    elif kind == "key":
        if "target" in action:
            sandbox.left_click(*_point(action["target"]))
        parts = action["key"].replace("Control", "ctrl").replace("Meta", "ctrl").split("+")
        sandbox.press([part.lower() for part in parts] if len(parts) > 1 else parts[0].lower())
    elif kind == "scroll":
        if action["dx"]:
            # E2B Desktop's documented scroll primitive is vertical only.
            # Refuse to misexecute a horizontal action as a vertical one.
            raise ContractError("invalid_action")
        if "target" in action:
            sandbox.left_click(*_point(action["target"]))
        sandbox.scroll(direction="down" if action["dy"] > 0 else "up",
                       amount=max(1, min(20, abs(action["dy"]) // 120)))
    elif kind == "drag":
        sandbox.drag(_point(action["from"]), _point(action["to"]))
    elif kind == "wait":
        time.sleep(action["duration_ms"] / 1000)
    else:
        raise ContractError("invalid_action")
    return kind


__all__ = ["observe", "render_for_model", "parse_current_action", "dispatch"]
