"""Additive two-frame RFQ dispatch guard after the preserved v5 failure.

Only a purchase-RFQ click may use the exact observed PNG or the single proven
two-pixel alternate. Two final full screenshots must agree immediately before
dispatch; task, frame, URL, and visible target control stay bound. All v4/v5
adapter source remains unchanged.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractError

from .odoo_native_adapter import _digest
from .odoo_v066_scale_exact_return_adapter import (
    MAX_EXACT_RETURN_SAMPLES, OdooV066ScaleExactReturnAdapter,
    _micro_raster_alternate,
)
from .odoo_v066_scale_parse_border_adapter_v5 import (
    OdooV066ScaleParseBorderAdapterV5,
)
from .odoo_v066_scale_pinned_border_adapter import (
    PIXELS, TARGET_ELEMENT_JS, _target_outside_pinned_border,
)


PROFILE = "rfq-two-frame-final-dispatch-2026-09-29-v6"
OBSERVED = "two_frame_observed_confirmed"
ALTERNATE = "two_frame_alternate_confirmed"


def _member(observation, png: bytes, alternate_sha: str | None) -> str | None:
    if png == observation.screenshot_bytes:
        return "observed"
    if (alternate_sha is not None and _digest(png) == alternate_sha and
            _micro_raster_alternate(observation.screenshot_bytes, png)):
        return "alternate"
    return None


class OdooV066TwoFrameDispatchAdapterV6(OdooV066ScaleParseBorderAdapterV5):
    """Keep v5 parse; narrowly repair the RFQ click dispatch final read."""

    def _record_final(self, observation, *, sample: int, png: bytes,
                      classification: str) -> dict:
        sink = self.frame_guard_sink
        if sink is None:
            raise ContractError("invalid_observation")
        ref = sink(len(self.frame_guard_samples), png)
        if type(ref) is not dict or ref.get("sha256") != _digest(png):
            raise ContractError("invalid_observation")
        self.frame_guard_samples.append({
            "step": self.step,
            "stage": "dispatch_final",
            "sample": sample,
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256":
                _digest(observation.frame_id.encode()),
            "sampled_frame_ref": ref,
            "classification": classification,
        })
        return ref

    def _frame_current(self, observation, *, stage: str) -> bool:
        if stage != "dispatch":
            return super()._frame_current(observation, stage=stage)
        action = self._pending_dispatch_action
        latest = self.latest_url
        if (type(action) is not dict or action.get("type") != "click" or
                type(latest) is not str or
                re.fullmatch(r"/odoo/purchase/[0-9]+",
                             urlsplit(latest).path) is None):
            return super()._frame_current(observation, stage=stage)
        self._physical_guard_receipt = None
        target = action.get("target")
        if (type(target) is not dict or set(target) != {"x", "y"} or
                observation.task_id != self.task_id or
                observation.task_binding_sha256 !=
                self.task_binding_sha256 or
                action.get("task_id") != self.task_id or
                action.get("task_binding_sha256") !=
                self.task_binding_sha256 or
                action.get("frame_id") != observation.frame_id or
                self.latest is not observation or
                self.page.url != latest):
            return False
        start = len(self.frame_guard_samples)
        exact = OdooV066ScaleExactReturnAdapter._frame_current(
            self, observation, stage="dispatch")
        samples = self.frame_guard_samples[start:]
        if self.page.url != latest:
            return False
        alternate_sha = None
        if exact:
            if (not samples or samples[-1].get("classification") !=
                    "exact_return"):
                return False
        else:
            if (len(samples) != MAX_EXACT_RETURN_SAMPLES or
                    any(sample.get("classification") !=
                        "one_recurring_micro_raster_alternate"
                        for sample in samples) or
                    len({sample["sampled_frame_ref"]["sha256"]
                         for sample in samples}) != 1):
                return False
            alternate_sha = samples[-1]["sampled_frame_ref"]["sha256"]
        before = self.page.evaluate(TARGET_ELEMENT_JS, target)
        if (not _target_outside_pinned_border(
                action, before, self.observed_target_control,
                observation) or self.page.url != latest):
            return False
        first_png = self.page.screenshot(type="png")
        first_member = _member(observation, first_png, alternate_sha)
        first_ref = self._record_final(
            observation, sample=len(samples), png=first_png,
            classification=("two_frame_candidate_" + first_member
                            if first_member is not None else
                            "third_or_material_frame_rejected"))
        if first_member is None or self.page.url != latest:
            return False
        second_png = self.page.screenshot(type="png")
        second_member = _member(observation, second_png, alternate_sha)
        after = self.page.evaluate(TARGET_ELEMENT_JS, target)
        accepted = (
            second_member == first_member and
            second_png == first_png and self.page.url == latest and
            observation.task_id == self.task_id and
            observation.task_binding_sha256 ==
            self.task_binding_sha256 and
            action.get("frame_id") == observation.frame_id and
            before == after and
            _target_outside_pinned_border(
                action, after, self.observed_target_control,
                observation))
        second_ref = self._record_final(
            observation, sample=len(samples) + 1, png=second_png,
            classification=(
                (OBSERVED if first_member == "observed" else ALTERNATE)
                if accepted else "two_frame_confirmation_rejected"))
        if not accepted:
            return False
        self._physical_guard_receipt = {
            "profile": PROFILE,
            "classification": (OBSERVED if first_member == "observed"
                               else ALTERNATE),
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256":
                _digest(observation.frame_id.encode()),
            "observed_url": latest,
            "physical_url": self.page.url,
            "target_point": target,
            "target_control_before": before,
            "target_control_after": after,
            "target_control": after,
            "base_dispatch_samples": len(samples),
            "first_final_frame_ref": first_ref,
            "second_final_frame_ref": second_ref,
            "physical_frame_ref": second_ref,
            "pinned_pixel_coordinates": [list(point) for point in PIXELS],
        }
        return True


__all__ = ["OdooV066TwoFrameDispatchAdapterV6", "PROFILE",
           "OBSERVED", "ALTERNATE"]
