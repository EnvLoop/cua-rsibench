"""Train-only, source-neutral Odoo attachment-link calibration adapter.

This adapter does not alter or authorize a selection/hidden evaluator. It
keeps the v0.6.6 screenshot/action contract and limits its special guard to a
visible, unique ``*-source.pdf`` link in the native attachment tray.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractError, validate_action
from cursibench.scale_action_output_v066 import normalize_model_action

from .odoo_native_adapter import _digest
from .odoo_v066_scale_exact_return_adapter import (
    MAX_EXACT_RETURN_SAMPLES, OdooV066ScaleExactReturnAdapter,
    _micro_raster_alternate,
)


PROFILE = "train-only-visible-attachment-route-2026-09-29-v1"
ROUTE = re.compile(r"/odoo/(purchase|sales|crm)/[0-9]+\Z")

# This is observation of the visible page, not an actor tool or selector-based
# click. The click itself still goes through the validated coordinate action.
# Select the smallest exact-text element to avoid a broad ancestor absorbing a
# second attachment. Hit-testing rejects overlays and moved targets.
ATTACHMENT_LOOKUP_JS = r"""({label, target}) => {
  if (!/^\/odoo\/(purchase|sales|crm)\/[0-9]+$/.test(location.pathname) ||
      document.querySelector('iframe.o-FileViewer-view')) return null;
  const exact = Array.from(document.querySelectorAll('body *')).filter(el => {
    const text = (el.innerText || '').trim().replace(/\s+/g, ' ');
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return text === label && r.width > 2 && r.height > 2 &&
      r.left >= 0 && r.top >= 0 && r.right <= innerWidth &&
      r.bottom <= innerHeight && s.visibility !== 'hidden' &&
      s.display !== 'none' && s.pointerEvents !== 'none';
  });
  if (!exact.length) return null;
  const minimal = exact.filter(el => !exact.some(other =>
    other !== el && el.contains(other)));
  if (minimal.length !== 1) return null;
  const el = minimal[0], r = el.getBoundingClientRect();
  const hit = target ? document.elementFromPoint(target.x, target.y) : null;
  return {
    label: (el.innerText || '').trim().replace(/\s+/g, ' '),
    tag: el.tagName.toLowerCase(),
    role: el.getAttribute('role') || '',
    title: el.getAttribute('title') || '',
    bounds: [r.left, r.top, r.right, r.bottom],
    target_inside: !target ||
      (r.left <= target.x && target.x <= r.right &&
       r.top <= target.y && target.y <= r.bottom &&
       !!hit && (el === hit || el.contains(hit) || hit.contains(el)))
  };
}"""


def _identity(raw: object) -> dict | None:
    if (type(raw) is not dict or
            set(raw) != {"label", "tag", "role", "title", "bounds",
                         "target_inside"} or
            type(raw["label"]) is not str or
            type(raw["tag"]) is not str or
            type(raw["role"]) is not str or
            type(raw["title"]) is not str or
            type(raw["bounds"]) is not list or
            len(raw["bounds"]) != 4 or
            any(type(value) not in (int, float) for value in raw["bounds"]) or
            raw["target_inside"] is not True):
        return None
    return {key: raw[key] for key in
            ("label", "tag", "role", "title", "bounds")}


class OdooV066TrainAttachmentRouteAdapterV1(OdooV066ScaleExactReturnAdapter):
    """Allow a bounded raster alternate only for the observed PDF link."""

    def __init__(self, *args, expected_attachment_label: str, **kwargs):
        super().__init__(*args, **kwargs)
        if (expected_attachment_label != f"{self.task_id}-source.pdf" or
                not expected_attachment_label.isascii()):
            raise ValueError("train attachment label must bind to task ID")
        self.expected_attachment_label = expected_attachment_label
        self.observed_attachment: dict | None = None
        self.observed_target_control: dict | None = None
        self.observed_attachment_frame_id: str | None = None
        self._pending_action: dict | None = None
        self._parsed_action: dict | None = None
        self._parse_guard: dict | None = None
        self._physical_guard: dict | None = None

    def observe_for_model(self, *, memory: str = ""):
        observation, rendered = super().observe_for_model(memory=memory)
        self.observed_attachment = self.page.evaluate(
            ATTACHMENT_LOOKUP_JS,
            {"label": self.expected_attachment_label, "target": None})
        self.observed_target_control = _identity(self.observed_attachment)
        self.observed_attachment_frame_id = observation.frame_id
        return observation, rendered

    def _lookup(self, target: dict) -> dict | None:
        return _identity(self.page.evaluate(
            ATTACHMENT_LOOKUP_JS,
            {"label": self.expected_attachment_label, "target": target}))

    def _is_link_action(self, observation, action: dict | None) -> bool:
        if (type(action) is not dict or action.get("type") != "click" or
                action.get("task_id") != self.task_id or
                action.get("task_binding_sha256") !=
                self.task_binding_sha256 or
                action.get("frame_id") != observation.frame_id or
                self.latest is not observation or
                self.observed_attachment_frame_id != observation.frame_id or
                self.page.url != self.latest_url or
                ROUTE.fullmatch(urlsplit(self.page.url).path) is None):
            return False
        target = action.get("target")
        if (type(target) is not dict or set(target) != {"x", "y"} or
                any(type(target[key]) is not int for key in ("x", "y"))):
            return False
        observed = _identity(self.observed_attachment)
        return (observed is not None and
                observed["label"] == self.expected_attachment_label and
                self._lookup(target) == observed)

    def _record_final(self, observation, stage: str, index: int,
                      raw: bytes, classification: str) -> dict:
        if self.frame_guard_sink is None:
            raise ContractError("invalid_observation")
        ref = self.frame_guard_sink(len(self.frame_guard_samples), raw)
        if type(ref) is not dict or ref.get("sha256") != _digest(raw):
            raise ContractError("invalid_observation")
        self.frame_guard_samples.append({
            "step": self.step, "stage": stage + "_final", "sample": index,
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
            "sampled_frame_ref": ref, "classification": classification,
        })
        return ref

    def _frame_current(self, observation, *, stage: str) -> bool:
        start = len(self.frame_guard_samples)
        exact = super()._frame_current(observation, stage=stage)
        samples = self.frame_guard_samples[start:]
        action = self._pending_action
        if not self._is_link_action(observation, action):
            return exact
        # No widening for an unrelated route or target. A failing base guard
        # may be recovered only from six copies of the one frozen alternate.
        alternate_sha = None
        if not exact:
            if (len(samples) != MAX_EXACT_RETURN_SAMPLES or
                    any(item.get("classification") !=
                        "one_recurring_micro_raster_alternate"
                        for item in samples) or
                    len({item["sampled_frame_ref"]["sha256"]
                         for item in samples}) != 1):
                return False
            alternate_sha = samples[-1]["sampled_frame_ref"]["sha256"]
        elif len(samples) != 1 or samples[0].get("classification") != "exact_return":
            return False
        target = action["target"]
        observed = _identity(self.observed_attachment)
        if observed is None or self._lookup(target) != observed:
            return False
        first = self.page.screenshot(type="png")
        if first == observation.screenshot_bytes:
            member = "observed"
        elif (_micro_raster_alternate(observation.screenshot_bytes, first) and
              (alternate_sha is None or _digest(first) == alternate_sha)):
            member = "alternate"
        else:
            member = None
        first_ref = self._record_final(
            observation, stage, len(samples), first,
            "candidate_" + member if member else "third_or_material_rejected")
        if member is None or self.page.url != self.latest_url:
            return False
        second = self.page.screenshot(type="png")
        current = self._lookup(target)
        accepted = (second == first and current == observed and
                    self.page.url == self.latest_url and
                    self.latest is observation and
                    self.observed_attachment_frame_id == observation.frame_id)
        second_ref = self._record_final(
            observation, stage, len(samples) + 1, second,
            ("two_frame_" + member + "_confirmed" if accepted else
             "two_frame_confirmation_rejected"))
        if not accepted:
            return False
        receipt = {
            "profile": PROFILE, "stage": stage,
            "classification": "two_frame_" + member + "_confirmed",
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
            "observed_url": self.latest_url,
            "physical_url": self.page.url,
            "source_label_sha256":
                _digest(self.expected_attachment_label.encode()),
            "target_point": target,
            "target_identity": observed,
            "base_sample_count": len(samples),
            "first_final_frame_ref": first_ref,
            "second_final_frame_ref": second_ref,
        }
        if stage == "parse":
            self._parse_guard = receipt
        else:
            self._physical_guard = receipt
        return True

    def parse_current_action(self, raw: str) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        action = normalize_model_action(
            raw, observation, current_frame_id=observation.frame_id)
        self._parse_guard = None
        self._pending_action = action
        try:
            if not self._frame_current(observation, stage="parse"):
                raise ContractError("stale_frame")
            self._parsed_action = action
            return action
        finally:
            self._pending_action = None

    def dispatch(self, raw_action: str | dict) -> dict:
        observation = self.latest
        if observation is None or self._parsed_action is None:
            raise ContractError("stale_frame")
        action = validate_action(
            raw_action, observation, current_frame_id=observation.frame_id)
        if action != self._parsed_action:
            raise ContractError("stale_frame")
        self._physical_guard = None
        self._pending_action = action
        try:
            applied = super().dispatch(action)
            if self._parse_guard is not None:
                if self._physical_guard is None:
                    raise ContractError("stale_frame")
                applied["public_contract_receipt"]["attachment_parse_guard"] = (
                    self._parse_guard)
                applied["public_contract_receipt"]["attachment_dispatch_guard"] = (
                    self._physical_guard)
            return applied
        finally:
            self._pending_action = None
            self._parsed_action = None
            self._parse_guard = None


__all__ = ["OdooV066TrainAttachmentRouteAdapterV1", "PROFILE",
           "ATTACHMENT_LOOKUP_JS"]
