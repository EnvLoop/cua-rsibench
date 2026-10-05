"""Pre-result cell-neutral v0.6.6 minimal GUI action output.

All v0.6.5 JSON/fence/alias behavior is preserved. Three bounded GUI additions
support native Office calibration: double-click, four explicit key chords,
and focused insert (no target). Full trusted metadata and current-frame checks
are performed by scale_action_contract_v066; old contracts are unchanged.
"""

from __future__ import annotations

import json

from . import scale_action_contract as base
from .scale_action_contract_v066 import NEW_KEY_CHORDS, validate_action
from .scale_action_output_v062 import _parse_one_object
from .scale_action_output_v065 import (
    MODEL_ACTION_CONTRACT as V065_CONTRACT,
    _normalize_one_fence,
    normalize_model_action as _normalize_v065,
)


OUTPUT_VERSION = "scale-action-output-v0.6.6"
MODEL_ACTION_CONTRACT = (
    V065_CONTRACT + " Also allowed as one current-frame GUI action: "
    "double_click {target}; key Control+F, Control+H, Control+End or Shift+End; "
    'and type {text,mode:"insert"} without target to enter text into the '
    "currently focused GUI control. A targetless fill is invalid. "
    "These additions do not allow shell, URL, selector, file or application API actions."
)


def render_for_model(observation: base.Observation) -> dict[str, bytes | str]:
    proxy = base.render_for_proxy(observation)
    instruction = json.dumps({
        "output_version": OUTPUT_VERSION,
        "contract": MODEL_ACTION_CONTRACT,
        "max_actions": observation.limits.max_step,
        "task_instruction": observation.instruction,
        "previous_action_result": observation.previous_action_result,
        "memory": observation.memory,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(instruction.encode("utf-8")) > 16_384:
        raise base.ContractError("invalid_observation")
    return {"image_bytes": proxy["image_bytes"],
            "instruction": instruction, "visible_text": proxy["visible_text"]}


def normalize_model_action(raw: str, observation: base.Observation, *,
                           current_frame_id: str) -> dict:
    payload = _parse_one_object(_normalize_one_fence(raw))
    if "action" in payload:
        if "type" in payload or type(payload["action"]) is not str:
            raise base.ContractError("invalid_action")
        payload["type"] = payload.pop("action")
    kind = payload.get("type")
    new_kind = kind == "double_click"
    new_key = (kind == "key" and type(payload.get("key")) is str
               and payload["key"] in NEW_KEY_CHORDS)
    focused_insert = kind == "type" and "target" not in payload
    if not (new_kind or new_key or focused_insert):
        return _normalize_v065(raw, observation,
                               current_frame_id=current_frame_id)
    required = ({"type", "target"} if new_kind else
                {"type", "key"} if new_key else
                {"type", "text", "mode"})
    permitted = required | {"memory"} | ({"target"} if new_key else set())
    if not required <= set(payload) or not set(payload) <= permitted:
        raise base.ContractError("invalid_action")
    if focused_insert and payload.get("mode") != "insert":
        raise base.ContractError("invalid_action")
    full = {
        "version": base.VERSION,
        "task_id": observation.task_id,
        "task_binding_sha256": observation.task_binding_sha256,
        "step": observation.step,
        "frame_id": observation.frame_id,
        "memory": observation.memory,
        **payload,
    }
    return validate_action(full, observation,
                           current_frame_id=current_frame_id)
