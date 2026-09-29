"""Prospective Desktop v0.6.6 two-observation caret-liveness adapter.

This is an additive, pre-result source epoch.  The historical v3 adapter and
its receipts remain byte-identical.  A one-pixel shape alone is never enough:
the unchanged application image must reappear in a second independent GUI
observation before a subsequent identical caret state can be accepted.  No
document, oracle, task ID, or provider-specific state is consulted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from weakref import WeakKeyDictionary

from cursibench.scale_action_output_v066 import normalize_model_action

from . import qwen_v066_adapter as v3


observe = v3.observe
dispatch = v3.dispatch
render_for_model = v3.render_for_model
PhysicalFrameDrift = v3.PhysicalFrameDrift


@dataclass(frozen=True)
class _Pending:
    step: int
    action_sha256: str
    observed_application_sha256: str
    alternate_application_sha256: str


_pending: WeakKeyDictionary = WeakKeyDictionary()


def _application_sha(raw: bytes) -> str:
    return v3.prior.application_frame_digest(raw)


def _report_drift(current: bytes, on_stale_frame) -> None:
    if on_stale_frame is not None:
        on_stale_frame(current)
    raise PhysicalFrameDrift()


def parse_current_action(raw: str, observation, sandbox, *, on_stale_frame=None):
    """Require exact return, or prove a two-state blink across observations.

    The first changed predispatch frame follows the v3 bounded exact-return
    probe.  If that probe never returns, one narrow alternate is remembered.
    The next observation must independently show the original application
    pixels again, with no GUI action in between.  Its direct predispatch frame
    may then be that same alternate.  A persistent one-pixel edit cannot meet
    this A/B/A/B condition, while a third or material state fails closed.
    """
    action_sha = sha256(raw.encode()).hexdigest()
    first = observation.screenshot_bytes
    expected = _application_sha(first)
    pending = _pending.pop(sandbox, None)
    if pending is not None and pending.step == observation.step:
        current = bytes(sandbox.screenshot())
        actual = _application_sha(current)
        if (pending.action_sha256 != action_sha or
                pending.observed_application_sha256 != expected):
            _report_drift(current, on_stale_frame)
        if actual == expected:
            return normalize_model_action(
                raw, observation, current_frame_id=observation.frame_id)
        if (actual == pending.alternate_application_sha256 and
                v3._single_caret_column(first, current)):
            return normalize_model_action(
                raw, observation, current_frame_id=observation.frame_id)
        _report_drift(current, on_stale_frame)
    try:
        return v3.parse_current_action(
            raw, observation, sandbox, on_stale_frame=on_stale_frame)
    except PhysicalFrameDrift:
        current = getattr(sandbox, "last_screenshot", None)
        if (type(current) is bytes and
                v3._single_caret_column(first, current)):
            _pending[sandbox] = _Pending(
                step=observation.step, action_sha256=action_sha,
                observed_application_sha256=expected,
                alternate_application_sha256=_application_sha(current))
        raise


__all__ = ["observe", "render_for_model", "parse_current_action",
           "dispatch", "PhysicalFrameDrift"]
