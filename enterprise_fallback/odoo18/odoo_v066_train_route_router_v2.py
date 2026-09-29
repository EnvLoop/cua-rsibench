"""Train-only price route anchored to the editor's own table row.

The v9 token/journal protocol and exact task, RFQ, product, price, target and
physical-frame guards remain unchanged. Only the global SKU-row search is
replaced by one visible price input and its nearest owning table row.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractError

from .odoo_native_adapter import _digest
from .odoo_v066_train_attachment_route_adapter_v3 import (
    OdooV066TrainAttachmentRouteAdapterV3,
)
from .odoo_v066_train_attachment_route_adapter_v5 import _price_identity
from .odoo_v066_train_route_router_v1 import OdooV066TrainRouteRouterV1


PROBE_SCHEMA = "envloop-odoo-train-price-route-probe-v2"


PRICE_EDITOR_OWNING_ROW_JS = r"""({rfq_id, route_path, sku, price, target}) => {
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && r.right > 0 && r.bottom > 0 &&
      r.left < innerWidth && r.top < innerHeight &&
      s.display !== 'none' && s.visibility !== 'hidden';
  };
  const candidates = Array.from(document.querySelectorAll(
    'td[name="price_unit"] input')).filter(visible);
  const fail = reason_code => ({status:'nonclaim', reason_code,
    visible_price_input_count:candidates.length});
  if (location.pathname !== route_path) return fail('wrong_route');
  if (document.querySelector('iframe.o-FileViewer-view'))
    return fail('viewer_present');
  const form = document.querySelector('.o_form_view');
  if (!form) return fail('form_missing');
  const ids = (form.innerText || '').match(/[A-Z0-9-]+/g) || [];
  if (!ids.includes(rfq_id)) return fail('rfq_token_missing');
  if (Array.from(document.querySelectorAll(
      '.modal.show, .o_dialog, [role="dialog"], dialog[open], '
      + '[aria-modal="true"]')).some(visible)) return fail('modal_present');
  if (candidates.length !== 1) return fail('price_editor_not_unique');
  const editor = candidates[0];
  const cell = editor.closest('td[name="price_unit"]');
  const row = cell && cell.closest('tr');
  if (!cell || !row || !visible(cell) || !visible(row) ||
      cell.parentElement !== row || !form.contains(row))
    return fail('editor_owning_row_missing');
  const products = Array.from(row.children).filter(el =>
    el.matches('td[name="product_id"]') && visible(el));
  if (products.length !== 1) return fail('product_cell_not_unique');
  const productText = (products[0].innerText || '') + ' ' +
    Array.from(products[0].querySelectorAll('input')).map(el =>
      el.value || '').join(' ');
  if (!((productText.match(/[A-Z0-9-]+/g) || []).includes(sku)))
    return fail('product_cell_sku_missing');
  const cellEditors = Array.from(cell.querySelectorAll('input')).filter(visible);
  if (cellEditors.length !== 1 || cellEditors[0] !== editor)
    return fail('editor_cell_ambiguous');
  if (editor.disabled || editor.readOnly ||
      !['text', 'number', 'search'].includes(editor.type))
    return fail('price_editor_not_writable');
  const value = Number(editor.value.trim());
  if (!Number.isFinite(value) || value.toFixed(2) !== price)
    return fail('initial_price_mismatch');
  if (document.activeElement !== editor) return fail('editor_unfocused');
  if (target && document.elementFromPoint(target.x, target.y) !== editor)
    return fail('target_not_editor');
  const bounds = el => {
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom];
  };
  return {status:'ready', reason_code:'ready',
    visible_price_input_count:1,
    identity:{
      rfq_id, route_path, sku, initial_price:price,
      row_bounds:bounds(row), product_cell_bounds:bounds(products[0]),
      cell_bounds:bounds(cell), editor_bounds:bounds(editor),
      editor_tag:editor.tagName.toLowerCase(), editor_type:editor.type || '',
      focused:true, modal_absent:true, product_cell_sku_seen:true,
      editor_readonly:false, target_inside:true
    }
  };
}"""


class OdooV066TrainRouteRouterV2(OdooV066TrainRouteRouterV1):
    """Retain the explicit route token, changing only editor row ownership."""

    def observe_for_model(self, *, memory: str = ""):
        observation, rendered = (
            OdooV066TrainAttachmentRouteAdapterV3.observe_for_model(
                self, memory=memory))
        self.observation_serial += 1
        path = urlsplit(self.page.url).path
        matches = [row for row in self.expected_price_targets
                   if row["route_path"] == path]
        selected = matches[0] if len(matches) == 1 else None
        self.current_price_target = selected
        if selected is None:
            diagnostic = {"status": "nonclaim",
                          "reason_code": "not_frozen_train_rfq",
                          "visible_price_input_count": 0}
        else:
            diagnostic = self.page.evaluate(PRICE_EDITOR_OWNING_ROW_JS, {
                "rfq_id": selected["rfq_id"],
                "route_path": selected["route_path"],
                "sku": selected["sku"],
                "price": selected["initial_price"],
                "target": None})
        if (type(diagnostic) is not dict or
                diagnostic.get("status") not in ("ready", "nonclaim") or
                type(diagnostic.get("reason_code")) is not str or
                type(diagnostic.get("visible_price_input_count")) is not int or
                not 0 <= diagnostic["visible_price_input_count"] <= 128):
            raise ContractError("invalid_observation")
        raw_identity = (diagnostic.get("identity")
                        if diagnostic["status"] == "ready" else None)
        identity = _price_identity(raw_identity)
        if diagnostic["status"] == "ready" and identity is None:
            diagnostic = {"status": "nonclaim",
                          "reason_code": "owning_row_identity_invalid",
                          "visible_price_input_count":
                              diagnostic["visible_price_input_count"]}
        # The inherited v8 guard normalizes this raw identity itself; retain
        # target_inside for that exact check, then compare normalized copies.
        self.observed_price_editor = raw_identity if identity is not None else None
        self.observed_price_frame_id = observation.frame_id
        payload = {
            "schema": PROBE_SCHEMA, "step": observation.step,
            "observation_serial": self.observation_serial,
            "task_binding_sha256": self.task_binding_sha256,
            "frame_id_sha256": _digest(observation.frame_id.encode()),
            "frame_sha256": observation.screenshot["sha256"],
            "observed_url": self.latest_url,
            "price_phase": selected["phase"] if selected else None,
            "rfq_id_sha256": _digest(selected["rfq_id"].encode())
                if selected else None,
            "sku_sha256": _digest(selected["sku"].encode())
                if selected else None,
            "initial_price_sha256":
                _digest(selected["initial_price"].encode())
                if selected else None,
            "strict_price_identity_present": identity is not None,
            "status": diagnostic["status"],
            "reason_code": diagnostic["reason_code"],
            "visible_price_input_count":
                diagnostic["visible_price_input_count"],
        }
        self.latest_route_probe = payload
        self.latest_route_probe_ref = self._save(
            self.route_probe_sink, payload, category="probe")
        self.parsed_route_claim = None
        self.parsed_route_claim_ref = None
        self.latest_route_decision_ref = None
        return observation, rendered

    def _lookup_price(self, target: dict) -> dict | None:
        selected = self.current_price_target
        if selected is None:
            return None
        result = self.page.evaluate(PRICE_EDITOR_OWNING_ROW_JS, {
            "rfq_id": selected["rfq_id"],
            "route_path": selected["route_path"],
            "sku": selected["sku"],
            "price": selected["initial_price"],
            "target": target})
        if type(result) is not dict or result.get("status") != "ready":
            return None
        return _price_identity(result.get("identity"))


__all__ = ["OdooV066TrainRouteRouterV2", "PROBE_SCHEMA",
           "PRICE_EDITOR_OWNING_ROW_JS"]
