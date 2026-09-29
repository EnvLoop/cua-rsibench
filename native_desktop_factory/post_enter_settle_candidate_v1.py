"""Offline-only candidate for one material GUI transition after Enter.

This module has no sandbox or provider entry point and is not bound to a
dispatch freeze. A future runner would have to capture a *fresh* observation
after its one-second no-action wait, regenerate the next action from that
observation, and keep the existing exact predispatch check.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import qwen_v066_adapter as adapter
from .qwen_v064_adapter import application_frame_digest


WAIT_MS = 1000


@dataclass(frozen=True)
class SettledTransition:
    first_observation_application_sha256: str
    material_predispatch_application_sha256: str
    fresh_observation_application_sha256: str
    fresh_predispatch_application_sha256: str
    waited_ms: int
    next_action_requires_fresh_observation: bool = True


def validate_post_enter_transition(*, previous_action: dict,
                                   first_observation: bytes,
                                   first_predispatch: bytes,
                                   fresh_observation: bytes,
                                   fresh_predispatch: bytes,
                                   waited_ms: int) -> SettledTransition:
    """Accept one A→B, wait, B→B transition; return no executable action.

    A single-caret change belongs to the existing narrow caret guard. This
    candidate is only for a material transition after the exact Enter key.
    It never normalizes or dispatches the action proposed on the stale A frame.
    """
    if (previous_action.get("type") != "key" or
            previous_action.get("key") not in ("Enter", "Return") or
            type(waited_ms) is not int or waited_ms != WAIT_MS):
        raise ValueError("Post-Enter settle is not eligible or unbounded")
    first = application_frame_digest(first_observation)
    changed = application_frame_digest(first_predispatch)
    fresh = application_frame_digest(fresh_observation)
    predispatch = application_frame_digest(fresh_predispatch)
    if (first == changed or
            adapter._single_caret_column(first_observation, first_predispatch) or
            changed != fresh or fresh != predispatch):
        raise ValueError("Post-Enter application transition did not settle exactly")
    return SettledTransition(first, changed, fresh, predispatch, waited_ms)
