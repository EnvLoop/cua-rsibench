"""Native Desktop dispatcher for the proposed common v0.6.6 GUI actions.

The dated pre-result Desktop amendment below resamples one narrow two-state
caret blink. Dispatch still requires an exact return to the observed frame.
Other application changes fail closed.
The shared action parser and historical v0.6.4/v0.6.5 sources are unchanged.
"""

from __future__ import annotations

from collections import Counter
import io
import time

from PIL import Image, ImageChops, UnidentifiedImageError

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_output_v066 import normalize_model_action, render_for_model

from . import qwen_v064_adapter as prior


observe = prior.observe
PhysicalFrameDrift = prior.PhysicalFrameDrift

# All times are bounded. A return to the original application image is required;
# a stationary one-pixel document edit cannot satisfy this rule.
_CARET_PROBE_DELAYS_SECONDS = (0.15, 0.20, 0.25, 0.30, 0.35)


def _application_pixels(raw: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.size != (1280, 800):
                raise ContractError("stale_frame")
            return opened.convert("RGB").crop((0, 27, 1280, 780))
    except (UnidentifiedImageError, OSError, ValueError):
        raise ContractError("stale_frame") from None


def _single_caret_column(observed: bytes, current: bytes) -> bool:
    """Classify only a contiguous, predominantly uniform 1px caret toggle.

    This shape test is necessary but insufficient: parse_current_action also
    requires the original application image to reappear during bounded live
    resampling, with no third application state.
    """
    first = _application_pixels(observed)
    second = _application_pixels(current)
    bounds = ImageChops.difference(first, second).getbbox()
    if bounds is None:
        return False
    left, top, right, bottom = bounds
    height = bottom - top
    if right - left != 1 or not 10 <= height <= 45:
        return False
    pairs = Counter((first.getpixel((left, y)), second.getpixel((left, y)))
                    for y in range(top, bottom))
    return (all(before != after for before, after in pairs) and
            len(pairs) <= 3 and pairs.most_common(1)[0][1] >= height - 2)


def parse_current_action(raw: str, observation, sandbox, *, on_stale_frame=None):
    current = bytes(sandbox.screenshot())
    expected = prior.application_frame_digest(observation.screenshot_bytes)
    actual = prior.application_frame_digest(current)
    if actual != expected:
        if not _single_caret_column(observation.screenshot_bytes, current):
            if on_stale_frame is not None:
                on_stale_frame(current)
            raise PhysicalFrameDrift()
        alternate = actual
        for delay in _CARET_PROBE_DELAYS_SECONDS:
            time.sleep(delay)
            current = bytes(sandbox.screenshot())
            actual = prior.application_frame_digest(current)
            if actual == expected:
                break
            if actual != alternate:
                if on_stale_frame is not None:
                    on_stale_frame(current)
                raise PhysicalFrameDrift()
        else:
            if on_stale_frame is not None:
                on_stale_frame(current)
            raise PhysicalFrameDrift()
    return normalize_model_action(raw, observation,
                                  current_frame_id=observation.frame_id)


def dispatch(sandbox, action: dict) -> str:
    kind = action["type"]
    if kind == "double_click":
        sandbox.double_click(*prior._point(action["target"]))
        return kind
    if kind == "type" and "target" not in action:
        if action.get("mode") != "insert":
            raise ContractError("invalid_action")
        sandbox.write(action["text"])
        return kind
    return prior.dispatch(sandbox, action)


__all__ = ["observe", "render_for_model", "parse_current_action",
           "dispatch", "PhysicalFrameDrift"]
