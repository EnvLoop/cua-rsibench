"""Proposed v0.6.6 GUI mapping for the PowerPoint-web E2B *train* pilot.

This module cannot start a sandbox or sample a model. Its historical v0.6.5
runner remains unchanged. Any future runner must still perform train-package,
cloud-source, lease, saved-artifact and independent-oracle checks.
"""

from __future__ import annotations

import hashlib
import time

from cursibench.scale_action_contract import ContractError, Observation
from cursibench.scale_action_contract_v066 import NEW_KEY_CHORDS, validate_action
from cursibench.scale_action_output_v066 import normalize_model_action, render_for_model
from tools import office_web_e2b_train_runner_v1 as prior


EXTRA_KEYS = {
    "Control+F": ["ctrl", "f"],
    "Control+H": ["ctrl", "h"],
    "Control+End": ["ctrl", "end"],
    "Shift+End": ["shift", "end"],
}
assert set(EXTRA_KEYS) == NEW_KEY_CHORDS


def _same_frame(sandbox, observation: Observation) -> None:
    if (hashlib.sha256(bytes(sandbox.screenshot())).hexdigest()
            != observation.screenshot["sha256"]):
        raise ContractError("stale_frame")
    if time.monotonic() > observation.expires_at:
        raise ContractError("expired_frame")


def parse_current_action(raw: str, observation: Observation, sandbox) -> dict:
    _same_frame(sandbox, observation)
    return normalize_model_action(raw, observation,
                                  current_frame_id=observation.frame_id)


def dispatch_current_action(sandbox, action: dict,
                            observation: Observation) -> str:
    """Recheck pixels and schema immediately before one GUI primitive."""
    checked = validate_action(action, observation,
                              current_frame_id=observation.frame_id)
    _same_frame(sandbox, observation)
    kind = checked["type"]
    if kind == "double_click":
        sandbox.move_mouse(*prior.point(checked["target"]))
        # e2b-desktop 2.2.0 treats x=0 or y=0 as absent. Move first, then
        # click without coordinates, just as the historical single-click path.
        sandbox.double_click()
    elif kind == "type" and "target" not in checked:
        if checked["mode"] != "insert":
            raise ContractError("invalid_action")
        sandbox.write(checked["text"])
    elif kind == "key" and checked["key"] in EXTRA_KEYS:
        if "target" in checked:
            prior.click_point(sandbox, checked["target"])
        sandbox.press(EXTRA_KEYS[checked["key"]])
    else:
        prior.dispatch(sandbox, checked)
    return kind


__all__ = ["render_for_model", "parse_current_action", "dispatch_current_action"]
