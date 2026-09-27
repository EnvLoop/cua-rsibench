"""Proposed v0.6.6 Odoo train-only browser action adapter.

This leaves the historical native adapter and the v0.6.5 official runner
unchanged. A future runner must explicitly select this profile and satisfy
the separate six-cell freeze before any final dispatch.
"""

from __future__ import annotations

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_contract_v066 import public_receipt, validate_action
from cursibench.scale_action_output_v066 import (
    normalize_model_action, render_for_model,
)

from .odoo_native_adapter import OdooNativeAdapter, VIEWPORT, _digest


class OdooV066TrainAdapter(OdooNativeAdapter):
    def observe_for_model(self, *, memory: str = ""):
        observation, _historical_payload = self.observe(memory=memory)
        return observation, render_for_model(observation)

    def parse_current_action(self, raw: str) -> dict:
        observation = self.latest
        if observation is None or self.page.url != self.latest_url or _digest(
                self.page.screenshot(type="png")) != observation.screenshot["sha256"]:
            raise ContractError("stale_frame")
        return normalize_model_action(raw, observation,
                                      current_frame_id=observation.frame_id)

    def dispatch(self, raw_action: str | dict) -> dict:
        self._within_budget()
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        if (self.page.url != self.latest_url or
                _digest(self.page.screenshot(type="png"))
                != observation.screenshot["sha256"]):
            self.latest = None
            raise ContractError("stale_frame")
        action = validate_action(raw_action, observation,
                                 current_frame_id=observation.frame_id)
        kind = action["type"]
        if kind in ("click", "double_click"):
            x, y = self._point(action["target"])
            if kind == "click":
                self.page.mouse.click(x, y)
            else:
                self.page.mouse.dblclick(x, y)
        elif kind == "type":
            if "target" in action:
                x, y = self._point(action["target"])
                self.page.mouse.click(x, y)
                if action["mode"] == "fill":
                    self.page.keyboard.press("Meta+A")
            elif action["mode"] != "insert":
                raise ContractError("invalid_action")
            self.page.keyboard.insert_text(action["text"])
        elif kind == "key":
            if "target" in action:
                x, y = self._point(action["target"])
                self.page.mouse.click(x, y)
            self.page.keyboard.press(action["key"])
        elif kind == "scroll":
            if "target" in action:
                x, y = self._point(action["target"])
                self.page.mouse.move(x, y)
            self.page.mouse.wheel(action["dx"], action["dy"])
        elif kind == "drag":
            start = self._point(action["from"])
            end = self._point(action["to"])
            self.page.mouse.move(*start)
            self.page.mouse.down()
            self.page.mouse.move(*end, steps=8)
            self.page.mouse.up()
        elif kind == "wait":
            self.page.wait_for_timeout(action["duration_ms"])
        elif kind == "finish":
            self.finished = True
        receipt = public_receipt(observation, action=action)
        self.latest = None
        self.latest_url = None
        self.previous_result = {"status": "applied", "code": "ok"}
        self.step += 1
        return {"action": action, "public_contract_receipt": receipt,
                "finished": self.finished}


__all__ = ["OdooV066TrainAdapter", "VIEWPORT"]
