"""Dated exact-frame-return guard for evaluator-only Odoo scale controls.

The action is parsed and dispatched only after a sampled PNG exactly matches
the model's observed PNG. The one observed two-pixel RFQ tab-border raster
alternate may be waited through; a third image, URL, or task-binding change
fails closed.
This does not weaken the v0.6.6 action validator or train-only pilot adapter.
"""

from __future__ import annotations

from io import BytesIO
from typing import Callable

from PIL import Image, ImageChops

from cursibench.scale_action_contract import ContractError

from .odoo_native_adapter import _digest
from .odoo_v066_train_adapter import OdooV066TrainAdapter


MAX_EXACT_RETURN_SAMPLES = 6
EXACT_RETURN_WAIT_MS = 40
ALLOWED_FLICKER_COORDINATES = {(41, 419), (132, 419)}
ALLOWED_FLICKER_RGB_PAIRS = {
    ((235, 237, 239), (235, 237, 240)),
    ((235, 237, 240), (235, 237, 239)),
}


def _micro_raster_alternate(observed: bytes, current: bytes) -> bool:
    try:
        with Image.open(BytesIO(observed)) as first, Image.open(BytesIO(current)) as second:
            a, b = first.convert("RGB"), second.convert("RGB")
    except (OSError, ValueError):
        return False
    if a.size != b.size or a.size != (1440, 1000):
        return False
    bbox = ImageChops.difference(a, b).getbbox()
    if bbox is None:
        return False
    changes = {}
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            old, new = a.getpixel((x, y)), b.getpixel((x, y))
            if old == new:
                continue
            changes[(x, y)] = (old, new)
            if len(changes) > 2:
                return False
    return (set(changes) == ALLOWED_FLICKER_COORDINATES and
            all(pair in ALLOWED_FLICKER_RGB_PAIRS
                for pair in changes.values()))


class OdooV066ScaleExactReturnAdapter(OdooV066TrainAdapter):
    """Record physical guard samples; never treat a micro alternate as current."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frame_guard_samples: list[dict] = []
        self.frame_guard_sink: Callable[[int, bytes], dict] | None = None
        self._guard_frame_id: str | None = None
        self._alternate_sha256: str | None = None

    def _frame_current(self, observation, *, stage: str) -> bool:
        if self.frame_guard_sink is None or stage not in ("parse", "dispatch"):
            raise ContractError("invalid_observation")
        if (observation.task_id != self.task_id or
                observation.task_binding_sha256 != self.task_binding_sha256):
            return False
        if self._guard_frame_id != observation.frame_id:
            self._guard_frame_id = observation.frame_id
            self._alternate_sha256 = None
        expected = observation.screenshot["sha256"]
        for sample in range(MAX_EXACT_RETURN_SAMPLES):
            if self.page.url != self.latest_url:
                return False
            png = self.page.screenshot(type="png")
            actual = _digest(png)
            reference = self.frame_guard_sink(len(self.frame_guard_samples), png)
            if (not isinstance(reference, dict) or
                    reference.get("sha256") != actual):
                raise ContractError("invalid_observation")
            if actual == expected:
                classification = "exact_return"
            elif (self._alternate_sha256 is None and
                  _micro_raster_alternate(observation.screenshot_bytes, png)):
                self._alternate_sha256 = actual
                classification = "one_recurring_micro_raster_alternate"
            elif actual == self._alternate_sha256:
                classification = "one_recurring_micro_raster_alternate"
            else:
                classification = "third_or_material_frame_rejected"
            self.frame_guard_samples.append({
                "step": self.step,
                "stage": stage,
                "sample": sample,
                "observed_frame_sha256": expected,
                "observed_frame_id_sha256":
                    _digest(observation.frame_id.encode()),
                "sampled_frame_ref": reference,
                "classification": classification,
            })
            if classification == "exact_return":
                return True
            if classification == "third_or_material_frame_rejected":
                return False
            if sample + 1 < MAX_EXACT_RETURN_SAMPLES:
                self.page.wait_for_timeout(EXACT_RETURN_WAIT_MS)
        return False


__all__ = ["OdooV066ScaleExactReturnAdapter", "MAX_EXACT_RETURN_SAMPLES"]
