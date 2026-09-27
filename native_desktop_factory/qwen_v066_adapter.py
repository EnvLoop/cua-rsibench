"""Native Desktop dispatcher for the proposed common v0.6.6 GUI actions.

It reuses the screenshot/current-frame check of the frozen development adapter
but does not change historical v0.6.4/v0.6.5 source bytes or receipts.
"""

from __future__ import annotations

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_output_v066 import normalize_model_action, render_for_model

from . import qwen_v064_adapter as prior


observe = prior.observe
PhysicalFrameDrift = prior.PhysicalFrameDrift


def parse_current_action(raw: str, observation, sandbox, *, on_stale_frame=None):
    return prior.parse_current_action(raw, observation, sandbox,
                                      on_stale_frame=on_stale_frame,
                                      normalizer=normalize_model_action)


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
