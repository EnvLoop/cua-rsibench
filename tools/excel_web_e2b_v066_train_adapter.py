"""Proposed v0.6.6 GUI mapping for Excel-web's bounded E2B train pilot.

The Office and Excel pilots share the same screenshot-only desktop primitives.
This separate import makes the cell's intended binding explicit; it does not
retroactively change any v0.6.5 run or qualify a live Excel cloud item.
"""

from __future__ import annotations

from tools.office_web_e2b_v066_train_adapter import (
    dispatch_current_action, parse_current_action, render_for_model,
)


__all__ = ["render_for_model", "parse_current_action", "dispatch_current_action"]
