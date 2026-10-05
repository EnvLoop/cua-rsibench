"""Native Odoo browser adapter for the shared v0.6 screenshot/action contract.

Model-visible data is one current screenshot, visible control labels and the
task instruction. The model never receives Odoo RPC, SQL, gold, selectors,
files, credentials or arbitrary URL navigation. This adapter only dispatches
actions validated by ``cursibench.scale_action_contract`` against the current
frame, then invalidates that frame immediately.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from cursibench.scale_action_contract import (
    ContractError, ContractLimits, Observation, make_observation,
    public_receipt, render_for_proxy, validate_action,
)

VERSION = "odoo-native-browser-v1"
MODEL = "Qwen/Qwen3.8-27B"
RENDERER = "qwen3_5_disable_thinking"
VIEWPORT = {"width": 1440, "height": 1000}
MAX_ACTIONS = 90
WALL_SECONDS = 720

VISIBLE_CONTROLS_JS = r"""() => {
  for (const node of document.querySelectorAll('[data-envloop-ref]')) {
    node.removeAttribute('data-envloop-ref');
  }
  const nodes = Array.from(document.querySelectorAll(
    'button,a,input,textarea,[role="tab"],td[name]'));
  const filtered = nodes.filter(el => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 2 && rect.height > 2 && rect.right > 0 && rect.bottom > 0 &&
      rect.left < innerWidth && rect.top < innerHeight && style.display !== 'none' &&
      style.visibility !== 'hidden';
  }).slice(0, 128);
  return filtered.map((el, index) => {
    const ref = 'c' + String(index).padStart(3, '0');
    el.setAttribute('data-envloop-ref', ref);
    return {
      ref,
      role: (el.getAttribute('role') || el.tagName.toLowerCase()).slice(0, 80),
      label: (el.getAttribute('aria-label') || el.getAttribute('title') ||
        el.getAttribute('placeholder') || el.innerText || el.getAttribute('name') || '')
        .trim().replace(/\s+/g, ' ').slice(0, 220),
      visible: true,
      enabled: !el.disabled
    };
  });
}"""


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class OdooNativeAdapter:
    def __init__(self, page: Any, *, task_id: str, task_binding_sha256: str,
                 instruction: str, limits: ContractLimits | None = None):
        if page.viewport_size != VIEWPORT:
            raise ValueError("Odoo actor viewport must be 1440 x 1000")
        self.page = page
        self.task_id = task_id
        self.task_binding_sha256 = task_binding_sha256
        self.instruction = instruction
        self.limits = limits or ContractLimits(max_step=MAX_ACTIONS)
        self.started = time.monotonic()
        self.step = 0
        self.previous_result: dict[str, str] | None = None
        self.latest: Observation | None = None
        self.latest_url: str | None = None
        self.finished = False

    def _within_budget(self) -> None:
        if self.finished or self.step >= MAX_ACTIONS or time.monotonic() - self.started > WALL_SECONDS:
            raise ContractError("expired_frame")

    def observe(self, *, memory: str = "") -> tuple[Observation, dict[str, bytes | str]]:
        self._within_budget()
        for _ in range(8):
            controls = self.page.evaluate(VISIBLE_CONTROLS_JS)
            screenshot = self.page.screenshot(type="png")
            self.page.wait_for_timeout(120)
            if _digest(self.page.screenshot(type="png")) == _digest(screenshot):
                break
        else:
            raise ContractError("invalid_observation")
        visible_text = "\n".join(
            f"{control['role']}: {control['label']}" for control in controls
            if control["label"]
        )[:12000]
        observation = make_observation(
            task_id=self.task_id, task_binding_sha256=self.task_binding_sha256,
            instruction=self.instruction, step=self.step,
            screenshot_bytes=screenshot, a11y_text=visible_text,
            controls=controls, previous_action_result=self.previous_result,
            memory=memory, limits=self.limits,
        )
        self.latest = observation
        self.latest_url = self.page.url
        return observation, render_for_proxy(observation)

    def _point(self, target: dict) -> tuple[int, int]:
        if "ref" in target:
            locator = self.page.locator(f'[data-envloop-ref="{target["ref"]}"]')
            if locator.count() != 1 or not locator.is_visible() or not locator.is_enabled():
                raise ContractError("stale_frame")
            box = locator.bounding_box()
            if box is None:
                raise ContractError("stale_frame")
            x, y = int(box["x"] + box["width"] / 2), int(box["y"] + box["height"] / 2)
        else:
            x, y = target["x"], target["y"]
        if not 0 <= x < VIEWPORT["width"] or not 0 <= y < VIEWPORT["height"]:
            raise ContractError("stale_frame")
        return x, y

    def dispatch(self, raw_action: str | dict) -> dict:
        self._within_budget()
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        if self.page.url != self.latest_url or _digest(self.page.screenshot(type="png")) != observation.screenshot["sha256"]:
            self.latest = None
            raise ContractError("stale_frame")
        action = validate_action(raw_action, observation,
                                 current_frame_id=observation.frame_id)
        kind = action["type"]
        if kind == "click":
            x, y = self._point(action["target"])
            self.page.mouse.click(x, y)
        elif kind == "type":
            x, y = self._point(action["target"])
            self.page.mouse.click(x, y)
            if action["mode"] == "fill":
                self.page.keyboard.press("Meta+A")
            self.page.keyboard.type(action["text"])
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


def public_binding() -> dict:
    from factory import CODE_DIR
    from reset import file_hash

    paths = {"odoo_native_adapter": CODE_DIR / "odoo_native_adapter.py",
             "shared_action_contract": CODE_DIR.parents[1] / "src/cursibench/scale_action_contract.py",
             "qwen_vision_proxy": CODE_DIR.parents[1] / "src/cursibench/scale_vision_proxy.py"}
    return {"schema": "envloop-odoo-native-model-boundary-v1",
            "version": VERSION, "student_model": MODEL, "renderer": RENDERER,
            "viewport": VIEWPORT, "max_actions": MAX_ACTIONS,
            "wall_seconds": WALL_SECONDS,
            "observation_modalities": ["screenshot", "visible_control_labels"],
            "actor_actions": ["click", "type", "key", "scroll", "drag", "wait", "finish"],
            "no_actor_shell_sql_application_rpc_or_arbitrary_url": True,
            "bindings_sha256": {key: file_hash(path) for key, path in paths.items()},
            "binding_sha256": _digest(json.dumps(
                {key: file_hash(path) for key, path in paths.items()},
                sort_keys=True).encode())}
