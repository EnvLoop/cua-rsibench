"""Additive RFQ-border parse guard for evaluator-only Odoo GUI controls.

The v4 adapter is unchanged. Its exact parse is tried first. Only one bounded
two-pixel RFQ-tab alternate may pass before a durable action intent, and the
unchanged physical dispatch guard still decides whether to click.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_output_v066 import normalize_model_action

from .odoo_native_adapter import _digest
from .odoo_v066_scale_exact_return_adapter import (
    MAX_EXACT_RETURN_SAMPLES, _micro_raster_alternate,
)
from .odoo_v066_scale_pinned_border_adapter import (
    OdooV066ScalePinnedBorderAdapter, PIXELS, TARGET_ELEMENT_JS,
    _target_outside_pinned_border,
)


PROFILE = "pinned-noninteractive-border-parse-and-dispatch-2026-09-29-v5"
CLASSIFICATION = "pinned_border_parse_equivalence_accepted"
EXACT_CLASSIFICATION = "exact_parse_frame"


def _valid_alternate(*, observation, samples: list[dict], page_url: str,
                     latest_url: str | None, task_id: str,
                     task_binding_sha256: str, action: dict,
                     control_before: dict | None,
                     control_after: dict | None,
                     final_png: bytes) -> bool:
    """All semantic and physical pre-intent checks; no GUI action occurs."""
    if (len(samples) != MAX_EXACT_RETURN_SAMPLES or
            page_url != latest_url or
            not re.fullmatch(r"/odoo/purchase/[0-9]+",
                             urlsplit(page_url).path) or
            observation.task_id != task_id or
            observation.task_binding_sha256 != task_binding_sha256 or
            action.get("type") != "click" or
            action.get("task_id") != task_id or
            action.get("task_binding_sha256") != task_binding_sha256 or
            action.get("frame_id") != observation.frame_id or
            any(sample.get("stage") != "parse" or
                sample.get("classification") !=
                "one_recurring_micro_raster_alternate" or
                sample.get("observed_frame_sha256") !=
                observation.screenshot["sha256"] or
                sample.get("observed_frame_id_sha256") !=
                _digest(observation.frame_id.encode())
                for sample in samples)):
        return False
    sample_hashes = [sample.get("sampled_frame_ref", {}).get("sha256")
                     for sample in samples]
    if (len(set(sample_hashes)) != 1 or
            type(sample_hashes[0]) is not str or
            sample_hashes[0] == observation.screenshot["sha256"] or
            _digest(final_png) != sample_hashes[0] or
            not _micro_raster_alternate(
                observation.screenshot_bytes, final_png)):
        return False
    return _target_outside_pinned_border(
        action, control_after, control_before, observation)


class OdooV066ScaleParseBorderAdapterV5(OdooV066ScalePinnedBorderAdapter):
    """Allow one proven noninteractive border alternate at parse only."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parse_guard_receipt: dict | None = None

    def parse_current_action(self, raw: str) -> dict:
        self._parse_guard_receipt = None
        self.observed_target_control = None
        start = len(self.frame_guard_samples)
        try:
            action = super().parse_current_action(raw)
        except ContractError as error:
            if error.code != "stale_frame":
                raise
        else:
            observation = self.latest
            samples = self.frame_guard_samples[start:]
            if (observation is None or len(samples) != 1 or
                    samples[0].get("stage") != "parse" or
                    samples[0].get("classification") != "exact_return"):
                raise ContractError("stale_frame")
            self._parse_guard_receipt = {
                "profile": PROFILE,
                "classification": EXACT_CLASSIFICATION,
                "observed_frame_sha256": observation.screenshot["sha256"],
                "observed_frame_id_sha256":
                    _digest(observation.frame_id.encode()),
                "physical_frame_ref": samples[0]["sampled_frame_ref"],
                "observed_url": self.latest_url,
                "physical_url": self.page.url,
                "sample_count": 1,
                "target_point": action.get("target"),
                "target_control_before": None,
                "target_control_after": self.observed_target_control,
            }
            return action
        observation = self.latest
        samples = self.frame_guard_samples[start:]
        if observation is None or len(samples) != MAX_EXACT_RETURN_SAMPLES:
            raise ContractError("stale_frame")
        action = normalize_model_action(
            raw, observation, current_frame_id=observation.frame_id)
        target = action.get("target")
        if (action.get("type") != "click" or
                type(target) is not dict or
                set(target) != {"x", "y"} or
                type(target["x"]) is not int or
                type(target["y"]) is not int or
                any(abs(target["x"] - x) <= 8 and
                    abs(target["y"] - y) <= 8 for x, y in PIXELS)):
            raise ContractError("stale_frame")
        before = self.page.evaluate(TARGET_ELEMENT_JS, target)
        physical_url = self.page.url
        final_png = self.page.screenshot(type="png")
        after = self.page.evaluate(TARGET_ELEMENT_JS, target)
        final_ref = self.frame_guard_sink(
            len(self.frame_guard_samples), final_png)
        if (type(final_ref) is not dict or
                final_ref.get("sha256") != _digest(final_png) or
                not _valid_alternate(
                    observation=observation, samples=samples,
                    page_url=physical_url, latest_url=self.latest_url,
                    task_id=self.task_id,
                    task_binding_sha256=self.task_binding_sha256,
                    action=action, control_before=before,
                    control_after=after, final_png=final_png) or
                self.page.url != physical_url or
                _digest(self.page.screenshot(type="png")) !=
                final_ref["sha256"]):
            raise ContractError("stale_frame")
        self.observed_target_control = after
        self._parse_guard_receipt = {
            "profile": PROFILE,
            "classification": CLASSIFICATION,
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256":
                _digest(observation.frame_id.encode()),
            "physical_frame_ref": final_ref,
            "observed_url": self.latest_url,
            "physical_url": physical_url,
            "sample_count": MAX_EXACT_RETURN_SAMPLES,
            "target_point": target,
            "target_control_before": before,
            "target_control_after": after,
            "pinned_pixel_coordinates": [list(point) for point in PIXELS],
        }
        return action

    def dispatch(self, raw_action: str | dict) -> dict:
        parse = self._parse_guard_receipt
        if parse is None:
            raise ContractError("stale_frame")
        try:
            applied = super().dispatch(raw_action)
            applied["public_contract_receipt"]["parse_guard"] = parse
            return applied
        finally:
            self._parse_guard_receipt = None


__all__ = ["OdooV066ScaleParseBorderAdapterV5", "PROFILE",
           "CLASSIFICATION", "EXACT_CLASSIFICATION"]
