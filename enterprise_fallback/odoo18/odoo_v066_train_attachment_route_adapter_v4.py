"""Train-only, exact four-pixel price-editor alternate for one RFQ row.

The v3 viewer route and inherited v2/RFQ guards remain unchanged. This route
only applies to a double-click on the focused price editor of the frozen train
line, with one observed PNG or its exact decorative-corner alternate.
"""

from __future__ import annotations

from io import BytesIO
import re
from urllib.parse import urlsplit

from PIL import Image, ImageChops

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action

from .odoo_native_adapter import _digest
from .odoo_v066_train_adapter import OdooV066TrainAdapter
from .odoo_v066_train_attachment_route_adapter_v3 import (
    OdooV066TrainAttachmentRouteAdapterV3,
)


PROFILE = "train-only-price-editor-four-pixel-corner-2026-09-29-v4"
PURCHASE_ROUTE = re.compile(r"/odoo/purchase/[0-9]+\Z")
CORNER_POINTS = {
    (16, 861): frozenset(((226, 230, 234), (226, 229, 234))),
    (17, 861): frozenset(((249, 250, 250), (250, 250, 251))),
    (16, 863): frozenset(((246, 247, 248), (246, 247, 249))),
    (17, 863): frozenset(((229, 233, 236), (230, 233, 236))),
}

# Read the native inline editor, not a broad cell or text match. The runner
# supplies the one train line's SKU and original price from its frozen package.
PRICE_EDITOR_LOOKUP_JS = r"""({sku, price, target}) => {
  if (!/^\/odoo\/purchase\/[0-9]+$/.test(location.pathname) ||
      !document.querySelector('.o_form_view') ||
      document.querySelector('iframe.o-FileViewer-view')) return null;
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && r.right > 0 && r.bottom > 0 &&
      r.left < innerWidth && r.top < innerHeight &&
      s.display !== 'none' && s.visibility !== 'hidden';
  };
  if (Array.from(document.querySelectorAll(
      '.modal.show, .o_dialog, [role="dialog"]')).some(visible)) return null;
  const rows = Array.from(document.querySelectorAll('tr')).filter(row =>
    visible(row) && (row.innerText || '').includes(sku));
  if (rows.length !== 1) return null;
  const cells = Array.from(rows[0].querySelectorAll(
    'td[name="price_unit"]')).filter(visible);
  if (cells.length !== 1) return null;
  const editors = Array.from(cells[0].querySelectorAll('input')).filter(el =>
    visible(el) && !el.disabled);
  if (editors.length !== 1) return null;
  const editor = editors[0], value = Number(editor.value.trim());
  if (!Number.isFinite(value) || value.toFixed(2) !== price ||
      document.activeElement !== editor) return null;
  const bounds = el => {
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom];
  };
  const hit = target ? document.elementFromPoint(target.x, target.y) : null;
  return {
    sku, initial_price: price, row_bounds: bounds(rows[0]),
    cell_bounds: bounds(cells[0]), editor_bounds: bounds(editor),
    editor_tag: editor.tagName.toLowerCase(), editor_type: editor.type || '',
    focused: true, modal_absent: true,
    target_inside: !target || hit === editor
  };
}"""


def _price_identity(raw: object) -> dict | None:
    keys = {"sku", "initial_price", "row_bounds", "cell_bounds",
            "editor_bounds", "editor_tag", "editor_type", "focused",
            "modal_absent", "target_inside"}
    if (type(raw) is not dict or set(raw) != keys or
            raw.get("focused") is not True or
            raw.get("modal_absent") is not True or
            raw.get("target_inside") is not True or
            raw.get("editor_tag") != "input" or
            type(raw.get("editor_type")) is not str or
            type(raw.get("sku")) is not str or
            type(raw.get("initial_price")) is not str):
        return None
    for key in ("row_bounds", "cell_bounds", "editor_bounds"):
        bounds = raw.get(key)
        if (type(bounds) is not list or len(bounds) != 4 or
                any(type(value) not in (int, float) for value in bounds) or
                bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
            return None
    return {key: raw[key] for key in keys if key != "target_inside"}


def _decorative_corner_alternate(observed: bytes, current: bytes) -> bool:
    """Accept exactly the recorded four one-channel RFQ-corner transitions."""
    try:
        with Image.open(BytesIO(observed)) as source, \
                Image.open(BytesIO(current)) as candidate:
            if (source.format != "PNG" or candidate.format != "PNG" or
                    source.mode != candidate.mode or source.mode != "RGB" or
                    source.size != candidate.size or
                    source.size != (1440, 1000)):
                return False
            a, b = source.copy(), candidate.copy()
    except (OSError, ValueError):
        return False
    if ImageChops.difference(a, b).getbbox() != (16, 861, 18, 864):
        return False
    changed = {}
    for y in (861, 862, 863):
        for x in (16, 17):
            old, new = a.getpixel((x, y)), b.getpixel((x, y))
            if old != new:
                changed[(x, y)] = frozenset((old, new))
    return changed == CORNER_POINTS


class OdooV066TrainAttachmentRouteAdapterV4(
        OdooV066TrainAttachmentRouteAdapterV3):
    """One bounded price-editor transition; every other action delegates."""

    def __init__(self, *args, expected_price_sku: str,
                 expected_initial_price: str, **kwargs):
        super().__init__(*args, **kwargs)
        if (not re.fullmatch(r"EL-TRN-[A-Z0-9-]{8,80}",
                             expected_price_sku) or
                not re.fullmatch(r"[0-9]{1,5}\.[0-9]{2}",
                                 expected_initial_price)):
            raise ValueError("train price editor binding invalid")
        self.expected_price_sku = expected_price_sku
        self.expected_initial_price = expected_initial_price
        self.observed_price_editor: dict | None = None
        self.observed_price_frame_id: str | None = None
        self._pending_price_edit: dict | None = None
        self._parsed_price_edit: dict | None = None
        self._price_parse_guard: dict | None = None
        self._price_dispatch_guard: dict | None = None

    def observe_for_model(self, *, memory: str = ""):
        observation, rendered = super().observe_for_model(memory=memory)
        self.observed_price_editor = self.page.evaluate(
            PRICE_EDITOR_LOOKUP_JS, {
                "sku": self.expected_price_sku,
                "price": self.expected_initial_price, "target": None})
        self.observed_price_frame_id = observation.frame_id
        return observation, rendered

    def _lookup_price(self, target: dict) -> dict | None:
        return _price_identity(self.page.evaluate(
            PRICE_EDITOR_LOOKUP_JS, {
                "sku": self.expected_price_sku,
                "price": self.expected_initial_price, "target": target}))

    def _targets_observed_price_editor(self, action: dict | None) -> bool:
        observed = _price_identity(self.observed_price_editor)
        if (observed is None or type(action) is not dict or
                action.get("type") != "double_click"):
            return False
        target = action.get("target")
        if (type(target) is not dict or set(target) != {"x", "y"} or
                any(type(target[key]) is not int for key in ("x", "y"))):
            return False
        left, top, right, bottom = observed["editor_bounds"]
        return left <= target["x"] <= right and top <= target["y"] <= bottom

    def _claims_price_edit(self, observation, action: dict | None) -> bool:
        observed = _price_identity(self.observed_price_editor)
        return bool(
            self._targets_observed_price_editor(action) and
            observed is not None and
            observed["sku"] == self.expected_price_sku and
            observed["initial_price"] == self.expected_initial_price and
            action.get("task_id") == observation.task_id == self.task_id and
            action.get("task_binding_sha256") ==
                observation.task_binding_sha256 ==
                self.task_binding_sha256 and
            action.get("frame_id") == observation.frame_id ==
                self.observed_price_frame_id and
            self.latest is observation and
            self.page.url == self.latest_url and
            PURCHASE_ROUTE.fullmatch(urlsplit(self.page.url).path) is not None)

    def _is_price_edit(self, observation, action: dict | None) -> bool:
        return (self._claims_price_edit(observation, action) and
                self._lookup_price(action["target"]) ==
                _price_identity(self.observed_price_editor))

    def _save_price_frame(self, observation, stage: str, sample: int,
                          raw: bytes, classification: str) -> dict:
        if self.frame_guard_sink is None:
            raise ContractError("invalid_observation")
        ref = self.frame_guard_sink(len(self.frame_guard_samples), raw)
        if type(ref) is not dict or ref.get("sha256") != _digest(raw):
            raise ContractError("invalid_observation")
        self.frame_guard_samples.append({
            "step": self.step, "stage": stage, "sample": sample,
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
            "sampled_frame_ref": ref, "classification": classification,
        })
        return ref

    def _frame_current(self, observation, *, stage: str) -> bool:
        if self._pending_price_edit is None:
            return super()._frame_current(observation, stage=stage)
        if (self.frame_guard_sink is None or stage not in ("parse", "dispatch") or
                not self._is_price_edit(observation, self._pending_price_edit)):
            return False
        raw = self.page.screenshot(type="png")
        if raw == observation.screenshot_bytes:
            member = "observed"
        elif _decorative_corner_alternate(observation.screenshot_bytes, raw):
            member = "corner_alternate"
        else:
            member = None
        base_ref = self._save_price_frame(
            observation, stage, 0, raw,
            ("one_" + member) if member else "third_or_material_rejected")
        if member is None or self.page.url != self.latest_url:
            return False
        observed = _price_identity(self.observed_price_editor)
        if self._lookup_price(self._pending_price_edit["target"]) != observed:
            return False
        first = self.page.screenshot(type="png")
        first_ref = self._save_price_frame(
            observation, stage + "_price_final", 1, first,
            "candidate_" + member if first == raw else
            "unstable_first_final_rejected")
        if first != raw or self.page.url != self.latest_url:
            return False
        second = self.page.screenshot(type="png")
        accepted = (second == first and
                    self._lookup_price(self._pending_price_edit["target"]) ==
                    observed and
                    self.page.url == self.latest_url and
                    self.latest is observation and
                    self.observed_price_frame_id == observation.frame_id)
        second_ref = self._save_price_frame(
            observation, stage + "_price_final", 2, second,
            "two_frame_" + member + "_confirmed" if accepted else
            "unstable_second_final_rejected")
        if not accepted:
            return False
        receipt = {
            "profile": PROFILE, "stage": stage,
            "classification": "two_frame_" + member + "_confirmed",
            "observed_frame_sha256": observation.screenshot["sha256"],
            "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
            "physical_frame_sha256": _digest(raw),
            "physical_url": self.page.url, "observed_url": self.latest_url,
            "sku_sha256": _digest(self.expected_price_sku.encode()),
            "initial_price_sha256":
                _digest(self.expected_initial_price.encode()),
            "target_point": self._pending_price_edit["target"],
            "target_identity": observed,
            "base_sample_count": 1,
            "base_frame_ref": base_ref,
            "first_final_frame_ref": first_ref,
            "second_final_frame_ref": second_ref,
        }
        if stage == "parse":
            self._price_parse_guard = receipt
        else:
            self._price_dispatch_guard = receipt
        return True

    def parse_current_action(self, raw: str) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        action = normalize_model_action(
            raw, observation, current_frame_id=observation.frame_id)
        if not self._targets_observed_price_editor(action):
            self._parsed_price_edit = None
            return super().parse_current_action(raw)
        if not self._claims_price_edit(observation, action):
            raise ContractError("stale_frame")
        self._price_parse_guard = None
        self._pending_price_edit = action
        try:
            if not self._frame_current(observation, stage="parse"):
                raise ContractError("stale_frame")
            self._parsed_price_edit = action
            return action
        finally:
            self._pending_price_edit = None

    def dispatch(self, raw_action: str | dict) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        if self._parsed_price_edit is None:
            if (type(raw_action) is dict and
                    self._targets_observed_price_editor(raw_action)):
                raise ContractError("stale_frame")
            return super().dispatch(raw_action)
        action = validate_action(
            raw_action, observation, current_frame_id=observation.frame_id)
        if action != self._parsed_price_edit:
            raise ContractError("stale_frame")
        parse_guard = self._price_parse_guard
        if parse_guard is None:
            raise ContractError("stale_frame")
        self._price_dispatch_guard = None
        self._pending_price_edit = action
        try:
            applied = OdooV066TrainAdapter.dispatch(self, action)
            if self._price_dispatch_guard is None:
                raise ContractError("stale_frame")
            applied["public_contract_receipt"]["price_parse_guard"] = (
                parse_guard)
            applied["public_contract_receipt"]["price_dispatch_guard"] = (
                self._price_dispatch_guard)
            return applied
        finally:
            self._pending_price_edit = None
            self._parsed_price_edit = None
            self._price_parse_guard = None
            self._price_dispatch_guard = None


__all__ = ["OdooV066TrainAttachmentRouteAdapterV4", "PROFILE",
           "PRICE_EDITOR_LOOKUP_JS", "CORNER_POINTS",
           "_decorative_corner_alternate"]
