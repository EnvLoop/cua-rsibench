"""Prospective offline scoring amendment for archived Qwen real-GUI frames.

The paid v1 run and its immutable source freeze remain unchanged. A future paid
runner must explicitly bind this module under a new public freeze before use.
No provider or application action is available from this module.
"""

from __future__ import annotations

from dataclasses import replace
import time

from . import qwen38_real_gui_diagnostic_v1 as original
from .scale_action_contract import Observation


class ScoringV2Error(ValueError):
    """Fixed error codes only; model text never appears in exceptions."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ScoringV2Error(code)


def reissue_archived_frame(observation: Observation) -> Observation:
    """Refresh only timestamps for offline comparison of one saved frame.

    The exact task, package, screenshot, instruction, step, prior result,
    frame ID and action contract remain as rendered for the model. Never pass
    this copy to a live GUI dispatcher.
    """
    _require(type(observation) is Observation,
             "diagnostic_v2_observation_invalid")
    now = time.monotonic()
    return replace(
        observation, issued_at=now,
        expires_at=now + observation.limits.frame_ttl_seconds)


def score_archived_action_text(
        text: str, observation: Observation, reference: dict) -> dict:
    """Use the strict v1 action parser on an exactly reissued saved frame."""
    _require(type(text) is str and type(reference) is dict,
             "diagnostic_v2_sample_or_reference_invalid")
    return original.score_action_text(
        text, reissue_archived_frame(observation), reference)


def score_live_action_text(
        text: str, observation: Observation, reference: dict) -> dict:
    """Fail before parsing if a live frame expired, rather than score zero."""
    _require(type(observation) is Observation and
             type(text) is str and type(reference) is dict,
             "diagnostic_v2_sample_or_reference_invalid")
    now = time.monotonic()
    _require(observation.issued_at <= now <= observation.expires_at,
             "diagnostic_v2_live_frame_expired")
    return original.score_action_text(text, observation, reference)


__all__ = ["ScoringV2Error", "reissue_archived_frame",
           "score_archived_action_text", "score_live_action_text"]
