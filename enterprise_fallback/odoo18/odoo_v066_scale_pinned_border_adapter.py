"""Dated physical-dispatch rule for one audited Odoo RFQ tab-border flicker.

Parsing always needs the exact observed PNG. Dispatch may use one recurring
alternate only after six bounded samples prove the two fixed border pixels
and a current visible target control outside that border. Both physical PNGs
remain private; every dispatch receipt states which physical rule was used.
"""

from __future__ import annotations

from cursibench.scale_action_contract import ContractError, validate_action

from .odoo_native_adapter import _digest
from .odoo_v066_scale_exact_return_adapter import (
    MAX_EXACT_RETURN_SAMPLES, OdooV066ScaleExactReturnAdapter,
)


PROFILE = "pinned-noninteractive-border-dispatch-2026-09-29"
CLASSIFICATION = "pinned_border_equivalence_accepted"
PIXELS = ((41, 419), (132, 419))


TARGET_ELEMENT_JS = """({x, y}) => {
  const hit = document.elementFromPoint(x, y);
  const el = hit && hit.closest('[data-envloop-ref]');
  if (!el || el.disabled) return null;
  const rect = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  return {
    ref: el.getAttribute('data-envloop-ref'),
    role: (el.getAttribute('role') || el.tagName.toLowerCase()).slice(0, 80),
    label: (el.getAttribute('aria-label') || el.getAttribute('title') ||
      el.getAttribute('placeholder') || el.innerText ||
      el.getAttribute('name') || '').trim().replace(/\\s+/g, ' ').slice(0, 220),
    visible: rect.width > 2 && rect.height > 2 &&
      style.display !== 'none' && style.visibility !== 'hidden',
    bounds: [rect.left, rect.top, rect.right, rect.bottom]
  };
}"""


def _target_outside_pinned_border(action: dict, current_control: dict | None,
                                  observation) -> bool:
    if action.get("type") not in ("click", "double_click", "type"):
        return False
    target = action.get("target")
    if type(target) is not dict or set(target) != {"x", "y"}:
        return False
    x, y = target["x"], target["y"]
    if type(x) is not int or type(y) is not int or any(
            abs(x - px) <= 8 and abs(y - py) <= 8 for px, py in PIXELS):
        return False
    if type(current_control) is not dict or not current_control.get("visible"):
        return False
    bounds = current_control.get("bounds")
    if (type(bounds) is not list or len(bounds) != 4 or
            not all(isinstance(value, (int, float)) for value in bounds) or
            not (bounds[0] <= x <= bounds[2] and
                 bounds[1] <= y <= bounds[3]) or
            any(bounds[0] - 8 <= px <= bounds[2] + 8 and
                bounds[1] - 8 <= py <= bounds[3] + 8
                for px, py in PIXELS)):
        return False
    matching = [control for control in observation.controls
                if control.ref == current_control.get("ref") and
                control.role == current_control.get("role") and
                control.label == current_control.get("label") and
                control.visible and control.enabled]
    return len(matching) == 1


class OdooV066ScalePinnedBorderAdapter(OdooV066ScaleExactReturnAdapter):
    """Allow only the frozen border alternate at the physical dispatch gate."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_dispatch_action: dict | None = None
        self._physical_guard_receipt: dict | None = None

    def _frame_current(self, observation, *, stage: str) -> bool:
        start = len(self.frame_guard_samples)
        exact = super()._frame_current(observation, stage=stage)
        samples = self.frame_guard_samples[start:]
        if stage != "dispatch":
            return exact
        if exact:
            last = samples[-1]
            self._physical_guard_receipt = {
                "profile": PROFILE,
                "classification": "exact_physical_frame",
                "observed_frame_sha256": observation.screenshot["sha256"],
                "physical_frame_ref": last["sampled_frame_ref"],
                "observed_frame_id_sha256":
                    _digest(observation.frame_id.encode()),
                "target_control": None,
                "pinned_pixel_coordinates": [],
            }
            return True
        self._physical_guard_receipt = None
        action = self._pending_dispatch_action
        if (action is None or len(samples) != MAX_EXACT_RETURN_SAMPLES or
                self.page.url != self.latest_url or
                observation.task_id != self.task_id or
                observation.task_binding_sha256 != self.task_binding_sha256 or
                any(sample.get("classification") !=
                    "one_recurring_micro_raster_alternate"
                    for sample in samples) or
                len({sample["sampled_frame_ref"]["sha256"]
                     for sample in samples}) != 1):
            return False
        target = action.get("target")
        if type(target) is not dict or set(target) != {"x", "y"}:
            return False
        current = self.page.evaluate(TARGET_ELEMENT_JS, target)
        if not _target_outside_pinned_border(action, current, observation):
            return False
        last = samples[-1]
        last["classification"] = CLASSIFICATION
        self._physical_guard_receipt = {
            "profile": PROFILE,
            "classification": CLASSIFICATION,
            "observed_frame_sha256": observation.screenshot["sha256"],
            "physical_frame_ref": last["sampled_frame_ref"],
            "observed_frame_id_sha256":
                _digest(observation.frame_id.encode()),
            "target_control": current,
            "pinned_pixel_coordinates": [list(point) for point in PIXELS],
        }
        return True

    def dispatch(self, raw_action: str | dict) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        self._pending_dispatch_action = validate_action(
            raw_action, observation, current_frame_id=observation.frame_id)
        self._physical_guard_receipt = None
        try:
            applied = super().dispatch(self._pending_dispatch_action)
            if self._physical_guard_receipt is None:
                raise ContractError("stale_frame")
            applied["public_contract_receipt"]["physical_dispatch_guard"] = (
                self._physical_guard_receipt)
            return applied
        finally:
            self._pending_dispatch_action = None


__all__ = ["OdooV066ScalePinnedBorderAdapter", "PROFILE", "CLASSIFICATION"]
