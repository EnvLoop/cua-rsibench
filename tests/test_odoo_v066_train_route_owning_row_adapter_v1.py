"""The owning-row router preserves the v9 route-token boundary."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v5 import PRICE_EDITOR_LOOKUP_JS
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v2 import (
    OdooV066TrainRouteRouterV2, PRICE_EDITOR_OWNING_ROW_JS,
)
from tests.test_odoo_v066_train_route_router_v1 import PriceLocator, PricePage, TARGETS
from tools import record_odoo_v066_train_gui_v1 as recorder
from tools.audit_odoo_v066_train_attachment_calibration_v10 import _route_binding
from tools.odoo_v066_train_route_journal_v1 import RouteAwareHoldoutJournal


class OwningPricePage(PricePage):
    def __init__(self, phase="positive"):
        super().__init__()
        selected = next(row for row in TARGETS if row["phase"] == phase)
        self.url = "http://127.0.0.1:8069" + selected["route_path"]
        self.owning_reason = "ready"

    def evaluate(self, script, args=None):
        if script == PRICE_EDITOR_OWNING_ROW_JS:
            if self.owning_reason != "ready":
                return {"status": "nonclaim", "reason_code": self.owning_reason,
                        "visible_price_input_count": 1}
            identity = super().evaluate(PRICE_EDITOR_LOOKUP_JS, args)
            if identity is None:
                return {"status": "nonclaim",
                        "reason_code": "owning_row_identity_invalid",
                        "visible_price_input_count": 1}
            return {"status": "ready", "reason_code": "ready",
                    "visible_price_input_count": 1, "identity": identity}
        return super().evaluate(script, args)


class OwningRouteTests(unittest.TestCase):
    def setup_attempt(self, phase="positive"):
        temp = tempfile.TemporaryDirectory()
        out = Path(temp.name) / "attempt"
        out.mkdir(mode=0o700)
        page = OwningPricePage(phase)
        page.attempt_dir = out
        adapter = OdooV066TrainRouteRouterV2(
            page, task_id="ELPO-TRN-0001",
            task_binding_sha256="a" * 64,
            instruction="train-only",
            expected_attachment_label="ELPO-TRN-0001-source.pdf",
            expected_price_targets=TARGETS)
        journal = RouteAwareHoldoutJournal(adapter, page, out)
        routes = out / "routes"
        routes.mkdir(mode=0o700)

        def sink(prefix):
            def save(serial, value):
                ref = recorder._artifact(
                    routes, f"{prefix}-{serial:04d}.json", value)
                ref["path"] = "routes/" + ref["path"]
                return ref
            return save

        adapter.route_probe_sink = sink("probe")
        adapter.route_decision_sink = sink("decision")

        def save_frame(index, raw):
            ref = recorder._artifact(
                out / "frames", f"guard-{index:04d}.png", raw)
            ref["path"] = "frames/" + ref["path"]
            return ref

        adapter.frame_guard_sink = save_frame
        return temp, out, page, adapter, journal

    def test_positive_and_negative_tokens_keep_owning_row_probe(self):
        for phase in ("positive", "negative"):
            with self.subTest(phase=phase):
                temp, out, page, adapter, journal = self.setup_attempt(phase)
                with temp:
                    journal.act("double_click", phase=phase,
                                locator=PriceLocator())
                    self.assertEqual(page.clicks, [(809, 479)])
                    self.assertTrue(page.intent_existed_at_click)
                    intent = json.loads((out / "actions/step-000-intent.private.json").read_bytes())
                    result = json.loads((out / "actions/step-000-result.private.json").read_bytes())
                    probe = json.loads((out / intent["route_probe_ref"]["path"]).read_bytes())
                    self.assertEqual(probe["schema"],
                                     "envloop-odoo-train-price-route-probe-v2")
                    self.assertEqual(probe["price_phase"], phase)
                    self.assertEqual(probe["status"], "ready")
                    kind, _refs = _route_binding(out, journal.trace[0],
                                                 intent, result)
                    self.assertEqual(kind, "price_editor")
                    self.assertEqual(adapter.step, 1)

    def test_missing_owner_or_wrong_product_fails_before_intent(self):
        for reason in ("editor_owning_row_missing",
                       "product_cell_sku_missing",
                       "price_editor_not_unique"):
            with self.subTest(reason=reason):
                temp, out, page, _adapter, journal = self.setup_attempt()
                with temp:
                    page.owning_reason = reason
                    with self.assertRaises(ContractError):
                        journal.act("double_click", phase="positive",
                                    locator=PriceLocator())
                    self.assertEqual(page.clicks, [])
                    self.assertFalse(any((out / "actions").glob("*-intent.private.json")))
                    self.assertEqual(len(journal.pre_intent_rejections), 3)
                    for ref in journal.pre_intent_rejections:
                        rejection = json.loads((out / ref["path"]).read_bytes())
                        decision = json.loads((out / rejection["route_decision_ref"]["path"])
                                              .read_bytes())
                        self.assertEqual(decision["status"], "nonclaim")
                        self.assertEqual(decision["reason_code"], reason)


if __name__ == "__main__":
    unittest.main()
