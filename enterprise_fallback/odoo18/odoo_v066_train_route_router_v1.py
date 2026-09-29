"""Explicit train-only action routing with durable price nonclaim reasons.

An unclaimed RFQ double-click never falls through to the generic RFQ adapter.
The route token binds the parsed action to the same dispatch path; the runner's
route-aware journal writes it into the pre-dispatch intent before any mouse use.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action

from .odoo_native_adapter import _digest
from .odoo_v066_train_attachment_route_adapter_v5 import (
    OdooV066TrainAttachmentRouteAdapterV5,
)


PROBE_SCHEMA = "envloop-odoo-train-price-route-probe-v1"
DECISION_SCHEMA = "envloop-odoo-train-action-route-decision-v1"
TOKEN_SCHEMA = "envloop-odoo-train-action-route-token-v1"


PRICE_ROUTE_DIAGNOSTIC_JS = r"""({rfq_id, route_path, sku, price}) => {
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && r.right > 0 && r.bottom > 0 &&
      r.left < innerWidth && r.top < innerHeight &&
      s.display !== 'none' && s.visibility !== 'hidden';
  };
  const candidates = Array.from(document.querySelectorAll(
    'td[name="price_unit"] input')).filter(visible);
  const fail = reason_code => ({
    status: 'nonclaim', reason_code,
    visible_price_input_count: candidates.length
  });
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
  const rows = Array.from(document.querySelectorAll('tr')).filter(row =>
    visible(row) && (row.innerText || '').includes(sku));
  if (rows.length !== 1) return fail('sku_row_not_unique');
  const products = Array.from(rows[0].querySelectorAll(
    'td[name="product_id"]')).filter(visible);
  if (products.length !== 1) return fail('product_cell_not_unique');
  const productText = (products[0].innerText || '') + ' ' +
    Array.from(products[0].querySelectorAll('input')).map(el =>
      el.value || '').join(' ');
  if (!((productText.match(/[A-Z0-9-]+/g) || []).includes(sku)))
    return fail('product_cell_sku_missing');
  const cells = Array.from(rows[0].querySelectorAll(
    'td[name="price_unit"]')).filter(visible);
  if (cells.length !== 1) return fail('price_cell_not_unique');
  const editors = Array.from(cells[0].querySelectorAll('input')).filter(visible);
  if (editors.length !== 1) return fail('price_editor_not_unique');
  const editor = editors[0];
  if (editor.disabled || editor.readOnly ||
      !['text', 'number', 'search'].includes(editor.type))
    return fail('price_editor_not_writable');
  const value = Number(editor.value.trim());
  if (!Number.isFinite(value) || value.toFixed(2) !== price)
    return fail('initial_price_mismatch');
  if (document.activeElement !== editor) return fail('editor_unfocused');
  return {status:'ready', reason_code:'ready',
          visible_price_input_count:candidates.length};
}"""


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


class OdooV066TrainRouteRouterV1(OdooV066TrainAttachmentRouteAdapterV5):
    """Do not convert an unclaimed price double-click into generic dispatch."""

    def __init__(self, *args, route_probe_sink=None,
                 route_decision_sink=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.route_probe_sink = route_probe_sink
        self.route_decision_sink = route_decision_sink
        self.observation_serial = 0
        self.latest_route_probe: dict | None = None
        self.latest_route_probe_ref: dict | None = None
        self.parsed_route_claim: dict | None = None
        self.parsed_route_claim_ref: dict | None = None
        self.latest_route_decision_ref: dict | None = None

    def _save(self, sink, value: dict, *, category: str) -> dict:
        if sink is None:
            raise ContractError("invalid_observation")
        ref = sink(self.observation_serial, value)
        if (type(ref) is not dict or type(ref.get("path")) is not str or
                ref.get("sha256") != _digest(_canonical(value))):
            raise ContractError("invalid_observation")
        return ref

    def observe_for_model(self, *, memory: str = ""):
        observation, rendered = super().observe_for_model(memory=memory)
        self.observation_serial += 1
        selected = self.current_price_target
        if selected is None:
            diagnostic = {"status": "nonclaim",
                          "reason_code": "not_frozen_train_rfq",
                          "visible_price_input_count": 0}
        else:
            diagnostic = self.page.evaluate(
                PRICE_ROUTE_DIAGNOSTIC_JS, {
                    "rfq_id": selected["rfq_id"],
                    "route_path": selected["route_path"],
                    "sku": selected["sku"],
                    "price": selected["initial_price"]})
        if (type(diagnostic) is not dict or
                diagnostic.get("status") not in ("ready", "nonclaim") or
                type(diagnostic.get("reason_code")) is not str or
                type(diagnostic.get("visible_price_input_count")) is not int or
                not 0 <= diagnostic["visible_price_input_count"] <= 128):
            raise ContractError("invalid_observation")
        if (diagnostic["status"] == "ready" and
                self.observed_price_editor is None):
            diagnostic = {**diagnostic, "status": "nonclaim",
                          "reason_code": "strict_identity_missing"}
        elif (diagnostic["status"] == "nonclaim" and
              self.observed_price_editor is not None):
            diagnostic = {**diagnostic, "status": "nonclaim",
                          "reason_code": "strict_diagnostic_disagree"}
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
            "strict_price_identity_present":
                self.observed_price_editor is not None,
            **diagnostic,
        }
        self.latest_route_probe = payload
        self.latest_route_probe_ref = self._save(
            self.route_probe_sink, payload, category="probe")
        self.parsed_route_claim = None
        self.parsed_route_claim_ref = None
        self.latest_route_decision_ref = None
        return observation, rendered

    def _decision(self, observation, action: dict, *, route_kind: str,
                  status: str, reason_code: str) -> dict:
        probe_ref = self.latest_route_probe_ref
        if (probe_ref is None or self.latest_route_probe is None or
                self.latest_route_probe["frame_id_sha256"] !=
                _digest(observation.frame_id.encode())):
            raise ContractError("invalid_observation")
        token_material = {
            "schema": TOKEN_SCHEMA,
            "route_kind": route_kind,
            "task_binding_sha256": self.task_binding_sha256,
            "frame_id_sha256": _digest(observation.frame_id.encode()),
            "frame_sha256": observation.screenshot["sha256"],
            "action_sha256": _digest(_canonical(action)),
            "observed_url": self.latest_url,
            "probe_sha256": probe_ref["sha256"],
        }
        token = _digest(_canonical(token_material))
        decision = {
            **{key: value for key, value in token_material.items()
               if key != "schema"},
            "schema": DECISION_SCHEMA, "token_schema": TOKEN_SCHEMA,
            "status": status,
            "reason_code": reason_code,
            "step": observation.step,
            "observation_serial": self.observation_serial,
            "route_kind": route_kind,
            "route_token": token if status == "claimed" else None,
            "route_token_sha256": _digest(token.encode())
                if status == "claimed" else None,
            "probe_ref": probe_ref,
        }
        ref = self._save(self.route_decision_sink, decision,
                         category="decision")
        self.latest_route_decision_ref = ref
        if status == "claimed":
            self.parsed_route_claim = decision
            self.parsed_route_claim_ref = ref
        return decision

    def parse_current_action(self, raw: str) -> dict:
        observation = self.latest
        if observation is None:
            raise ContractError("stale_frame")
        action = normalize_model_action(
            raw, observation, current_frame_id=observation.frame_id)
        if action["type"] == "double_click":
            probe = self.latest_route_probe
            if (probe is None or probe.get("status") != "ready" or
                    self.observed_price_editor is None):
                reason = (probe or {}).get("reason_code", "probe_missing")
                self._decision(observation, action,
                               route_kind="price_editor", status="nonclaim",
                               reason_code=reason)
                raise ContractError("stale_frame")
            if not self._targets_observed_price_editor(action):
                self._decision(observation, action,
                               route_kind="price_editor", status="nonclaim",
                               reason_code="target_outside_price_editor")
                raise ContractError("stale_frame")
            try:
                checked = super().parse_current_action(raw)
            except ContractError:
                self._decision(observation, action,
                               route_kind="price_editor", status="nonclaim",
                               reason_code="physical_or_identity_guard_rejected")
                raise
            if (self._parsed_price_edit is None or
                    self._price_parse_guard is None):
                self._decision(observation, action,
                               route_kind="price_editor", status="nonclaim",
                               reason_code="nested_price_route_not_claimed")
                raise ContractError("stale_frame")
            kind = "price_editor"
        else:
            checked = super().parse_current_action(raw)
            kind = ("viewer_close" if self._parsed_viewer_close is not None else
                    "attachment_link" if self._parsed_action is not None else
                    "generic_rfq")
        self._decision(observation, checked, route_kind=kind,
                       status="claimed", reason_code="claimed")
        return checked

    def dispatch(self, raw_action: str | dict, *, route_token: str) -> dict:
        observation = self.latest
        claim = self.parsed_route_claim
        if (observation is None or claim is None or
                type(route_token) is not str or
                claim.get("route_token") != route_token or
                claim.get("frame_id_sha256") !=
                _digest(observation.frame_id.encode())):
            raise ContractError("stale_frame")
        action = validate_action(raw_action, observation,
                                 current_frame_id=observation.frame_id)
        if claim["action_sha256"] != _digest(_canonical(action)):
            raise ContractError("stale_frame")
        kind = claim["route_kind"]
        if ((kind == "price_editor") != (self._parsed_price_edit is not None) or
                (kind == "viewer_close") !=
                    (self._parsed_viewer_close is not None) or
                (kind == "attachment_link") !=
                    (self._parsed_action is not None)):
            raise ContractError("stale_frame")
        try:
            applied = super().dispatch(action)
            receipt = applied["public_contract_receipt"]
            required = {
                "price_editor": ("price_parse_guard", "price_dispatch_guard"),
                "viewer_close": ("viewer_parse_guard", "viewer_dispatch_guard",
                                 "viewer_return_guard"),
                "attachment_link": ("attachment_parse_guard",
                                    "attachment_dispatch_guard"),
                "generic_rfq": (),
            }[kind]
            if any(type(receipt.get(key)) is not dict for key in required):
                raise ContractError("stale_frame")
            receipt["route_kind"] = kind
            receipt["route_token_sha256"] = _digest(route_token.encode())
            receipt["route_claim_ref_sha256"] = (
                self.parsed_route_claim_ref["sha256"])
            return applied
        finally:
            self.parsed_route_claim = None
            self.parsed_route_claim_ref = None


__all__ = ["OdooV066TrainRouteRouterV1", "PROBE_SCHEMA",
           "DECISION_SCHEMA", "TOKEN_SCHEMA", "PRICE_ROUTE_DIAGNOSTIC_JS"]
