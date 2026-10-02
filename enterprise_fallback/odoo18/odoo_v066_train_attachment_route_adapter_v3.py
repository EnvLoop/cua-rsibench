"""Train-only, exact-frame close guard for the original Odoo PDF viewer.

The RFQ and PDF-link guards from v2 remain unchanged. Only a click on the
unique observed viewer close control may use this additional route.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractError, validate_action
from cursibench.scale_action_output_v066 import normalize_model_action

from .odoo_native_adapter import _digest
from .odoo_v066_scale_exact_return_adapter import OdooV066ScaleExactReturnAdapter
from .odoo_v066_train_adapter import OdooV066TrainAdapter
from .odoo_v066_train_attachment_route_adapter_v2 import (
    OdooV066TrainAttachmentRouteAdapterV2,
)


PROFILE = "train-only-exact-pdf-viewer-close-2026-09-29-v3"
PURCHASE_ROUTE = re.compile(r"/odoo/purchase/[0-9]+\Z")
VIEWER_CLOSE_TIMEOUT_MS = 3000

# Read the current page only. The action still goes through the validated
# screenshot-bound coordinate dispatcher. A body-level filename match is not
# enough: the exact label must appear in the viewer's top bar.
VIEWER_LOOKUP_JS = r"""({label, target}) => {
  if (!/^\/odoo\/purchase\/[0-9]+$/.test(location.pathname)) return null;
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && r.right > 0 && r.bottom > 0 &&
      r.left < innerWidth && r.top < innerHeight &&
      s.display !== 'none' && s.visibility !== 'hidden';
  };
  const bounds = el => {
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom];
  };
  const frames = Array.from(document.querySelectorAll(
    'iframe.o-FileViewer-view')).filter(visible);
  if (frames.length !== 1) return null;
  const exact = Array.from(document.querySelectorAll('body *')).filter(el => {
    const text = (el.innerText || '').trim().replace(/\s+/g, ' ');
    const r = el.getBoundingClientRect();
    return text === label && visible(el) && r.top >= 0 && r.bottom <= 52;
  });
  const minimal = exact.filter(el => !exact.some(other =>
    other !== el && el.contains(other)));
  if (minimal.length !== 1) return null;
  const closes = Array.from(document.querySelectorAll(
    '[title="Close (Esc)"]')).filter(el => {
    const r = el.getBoundingClientRect();
    return visible(el) && r.top >= 0 && r.bottom <= 58 &&
      r.right > innerWidth - 55;
  });
  if (closes.length !== 1) return null;
  const close = closes[0], title = minimal[0];
  const hit = target ? document.elementFromPoint(target.x, target.y) : null;
  return {
    source_label: label,
    title_tag: title.tagName.toLowerCase(), title_bounds: bounds(title),
    close_tag: close.tagName.toLowerCase(),
    close_title: close.getAttribute('title'),
    close_bounds: bounds(close), iframe_bounds: bounds(frames[0]),
    target_inside: !target || !!hit && (hit === close || close.contains(hit))
  };
}"""

RFQ_RETURN_JS = r"""({task_id}) => {
  return /^\/odoo\/purchase\/[0-9]+$/.test(location.pathname) &&
    !document.querySelector('iframe.o-FileViewer-view') &&
    !!document.querySelector('.o_form_view') &&
    document.body.innerText.includes('Request for Quotation') &&
    document.body.innerText.includes(task_id);
}"""


def _viewer_identity(raw: object) -> dict | None:
    keys = {"source_label", "title_tag", "title_bounds", "close_tag",
            "close_title", "close_bounds", "iframe_bounds", "target_inside"}
    if (type(raw) is not dict or set(raw) != keys or
            raw.get("target_inside") is not True or
            any(type(raw.get(key)) is not str for key in
                ("source_label", "title_tag", "close_tag", "close_title")) or
            raw.get("close_title") != "Close (Esc)"):
        return None
    for key in ("title_bounds", "close_bounds", "iframe_bounds"):
        bounds = raw.get(key)
        if (type(bounds) is not list or len(bounds) != 4 or
                any(type(value) not in (int, float) for value in bounds) or
                bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
            return None
    return {key: raw[key] for key in keys if key != "target_inside"}


class OdooV066TrainAttachmentRouteAdapterV3(
        OdooV066TrainAttachmentRouteAdapterV2):
    """Add one viewer-close transition without widening RFQ dispatch."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observed_viewer: dict | None = None
        self.observed_viewer_frame_id: str | None = None
        self._pending_viewer_close: dict | None = None
        self._parsed_viewer_close: dict | None = None
        self._viewer_parse_guard: dict | None = None
        self._viewer_dispatch_guard: dict | None = None

    def observe_for_model(self, *, memory: str = ""):
        observation, rendered = super().observe_for_model(memory=memory)
        self.observed_viewer = self.page.evaluate(
            VIEWER_LOOKUP_JS,
            {"label": self.expected_attachment_label, "target": None})
        self.observed_viewer_frame_id = observation.frame_id
        return observation, rendered

    def _lookup_viewer(self, target: dict) -> dict | None:
        return _viewer_identity(self.page.evaluate(
            VIEWER_LOOKUP_JS,
            {"label": self.expected_attachment_label, "target": target}))

    def _targets_observed_viewer_close(self, action: dict | None) -> bool:
        observed = _viewer_identity(self.observed_viewer)
        if (observed is None or type(action) is not dict or
                action.get("type") != "click"):
            return False
        target = action.get("target")
        if (type(target) is not dict or set(target) != {"x", "y"} or
                any(type(target[key]) is not int for key in ("x", "y"))):
            return False
        left, top, right, bottom = observed["close_bounds"]
        return left <= target["x"] <= right and top <= target["y"] <= bottom

    def _claims_viewer_close(self, observation, action: dict | None) -> bool:
        if (type(action) is not dict or action.get("type") != "click" or
                action.get("task_id") != self.task_id or
                action.get("task_binding_sha256") !=
                self.task_binding_sha256 or
                action.get("frame_id") != observation.frame_id or
                observation.task_id != self.task_id or
                observation.task_binding_sha256 !=
                self.task_binding_sha256 or
                self.latest is not observation or
                self.observed_viewer_frame_id != observation.frame_id or
                self.page.url != self.latest_url or
                PURCHASE_ROUTE.fullmatch(urlsplit(self.page.url).path) is None):
            return False
        observed = _viewer_identity(self.observed_viewer)
        if (observed is None or
                observed["source_label"] != self.expected_attachment_label):
            return False
        return self._targets_observed_viewer_close(action)

    def _is_viewer_close(self, observation, action: dict | None) -> bool:
        return (self._claims_viewer_close(observation, action) and
                self._lookup_viewer(action["target"]) ==
                _viewer_identity(self.observed_viewer))

    def _record_viewer_final(self, observation, stage: str, sample: int,
                             raw: bytes, classification: str) -> dict:
        if self.frame_guard_sink is None:
            raise ContractError("invalid_observation")
        ref = self.frame_guard_sink(len(self.frame_guard_samples), raw)
        if type(ref) is not dict or ref.get("sha256") != _digest(raw):
            raise ContractError("invalid_observation")
        self.frame_guard_samples.append({
            "step": self.step, "stage": stage + "_viewer_final",
            "sample": sample,
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
            "sampled_frame_ref": ref, "classification": classification,
        })
        return ref

    def _frame_current(self, observation, *, stage: str) -> bool:
        if self._pending_viewer_close is None:
            return super()._frame_current(observation, stage=stage)
        if stage not in ("parse", "dispatch"):
            return False
        start = len(self.frame_guard_samples)
        exact = OdooV066ScaleExactReturnAdapter._frame_current(
            self, observation, stage=stage)
        samples = self.frame_guard_samples[start:]
        action = self._pending_viewer_close
        if (not exact or len(samples) != 1 or
                samples[0].get("classification") != "exact_return" or
                not self._is_viewer_close(observation, action)):
            return False
        observed = _viewer_identity(self.observed_viewer)
        first = self.page.screenshot(type="png")
        first_ref = self._record_viewer_final(
            observation, stage, 1, first,
            "candidate_observed" if first == observation.screenshot_bytes else
            "material_frame_rejected")
        if (first != observation.screenshot_bytes or
                self.page.url != self.latest_url):
            return False
        second = self.page.screenshot(type="png")
        accepted = (second == first and
                    self._lookup_viewer(action["target"]) == observed and
                    self.page.url == self.latest_url and
                    self.latest is observation and
                    self.observed_viewer_frame_id == observation.frame_id)
        second_ref = self._record_viewer_final(
            observation, stage, 2, second,
            "two_frame_observed_confirmed" if accepted else
            "viewer_confirmation_rejected")
        if not accepted:
            return False
        receipt = {
            "profile": PROFILE, "stage": stage,
            "classification": "two_frame_observed_confirmed",
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
            "source_label_sha256":
                _digest(self.expected_attachment_label.encode()),
            "observed_url": self.latest_url, "physical_url": self.page.url,
            "target_point": action["target"], "viewer_identity": observed,
            "base_sample_count": 1,
            "first_final_frame_ref": first_ref,
            "second_final_frame_ref": second_ref,
        }
        if stage == "parse":
            self._viewer_parse_guard = receipt
        else:
            self._viewer_dispatch_guard = receipt
        return True

    def parse_current_action(self, raw: str) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        action = normalize_model_action(
            raw, observation, current_frame_id=observation.frame_id)
        if not self._targets_observed_viewer_close(action):
            self._parsed_viewer_close = None
            return super().parse_current_action(raw)
        if not self._claims_viewer_close(observation, action):
            raise ContractError("stale_frame")
        self._viewer_parse_guard = None
        self._pending_viewer_close = action
        try:
            if not self._frame_current(observation, stage="parse"):
                raise ContractError("stale_frame")
            self._parsed_viewer_close = action
            return action
        finally:
            self._pending_viewer_close = None

    def dispatch(self, raw_action: str | dict) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        if self._parsed_viewer_close is None:
            if (type(raw_action) is dict and
                    self._targets_observed_viewer_close(raw_action)):
                raise ContractError("stale_frame")
            return super().dispatch(raw_action)
        action = validate_action(
            raw_action, observation, current_frame_id=observation.frame_id)
        if action != self._parsed_viewer_close:
            raise ContractError("stale_frame")
        expected_url = self.latest_url
        parse_guard = self._viewer_parse_guard
        if parse_guard is None:
            raise ContractError("stale_frame")
        self._viewer_dispatch_guard = None
        self._pending_viewer_close = action
        try:
            applied = OdooV066TrainAdapter.dispatch(self, action)
            dispatch_guard = self._viewer_dispatch_guard
            if dispatch_guard is None:
                raise ContractError("stale_frame")
            try:
                self.page.locator("iframe.o-FileViewer-view").wait_for(
                    state="hidden", timeout=VIEWER_CLOSE_TIMEOUT_MS)
            except Exception:
                raise ContractError("stale_frame") from None
            if (self.page.url != expected_url or
                    self.page.evaluate(RFQ_RETURN_JS,
                                       {"task_id": self.task_id}) is not True):
                raise ContractError("stale_frame")
            returned = self.page.screenshot(type="png")
            if self.frame_guard_sink is None:
                raise ContractError("invalid_observation")
            ref = self.frame_guard_sink(len(self.frame_guard_samples), returned)
            if type(ref) is not dict or ref.get("sha256") != _digest(returned):
                raise ContractError("invalid_observation")
            self.frame_guard_samples.append({
                "step": self.step - 1, "stage": "viewer_return",
                "sample": 0, "sampled_frame_ref": ref,
                "classification": "original_rfq_return_confirmed",
            })
            applied["public_contract_receipt"]["viewer_parse_guard"] = (
                parse_guard)
            applied["public_contract_receipt"]["viewer_dispatch_guard"] = (
                dispatch_guard)
            applied["public_contract_receipt"]["viewer_return_guard"] = {
                "profile": PROFILE,
                "classification": "original_rfq_return_confirmed",
                "source_label_sha256":
                    _digest(self.expected_attachment_label.encode()),
                "task_binding_sha256": self.task_binding_sha256,
                "returned_url": self.page.url,
                "post_close_frame_ref": ref,
            }
            return applied
        finally:
            self._pending_viewer_close = None
            self._parsed_viewer_close = None
            self._viewer_parse_guard = None
            self._viewer_dispatch_guard = None


__all__ = ["OdooV066TrainAttachmentRouteAdapterV3", "PROFILE",
           "VIEWER_LOOKUP_JS", "RFQ_RETURN_JS"]
