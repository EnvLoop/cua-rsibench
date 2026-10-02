"""Train route token is durable before dispatch; price nonclaims cannot fall back."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18.odoo_native_adapter import VISIBLE_CONTROLS_JS
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v2 import (
    ATTACHMENT_LOOKUP_JS,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v3 import (
    VIEWER_LOOKUP_JS,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v5 import (
    PRICE_EDITOR_LOOKUP_JS,
)
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v1 import (
    OdooV066TrainRouteRouterV1, PRICE_ROUTE_DIAGNOSTIC_JS,
)
from tests.test_odoo_v066_train_price_corner_route_v5 import (
    ALTERNATE, OBSERVED, TARGETS, THIRD,
)
from tools import record_odoo_v066_train_gui_v1 as recorder
from tools.audit_odoo_v066_train_attachment_calibration_v9 import (
    CalibrationAuditError, _route_binding,
)
from tools.odoo_v066_train_route_journal_v1 import RouteAwareHoldoutJournal


class PriceMouse:
    def __init__(self, page):
        self.page = page

    def dblclick(self, x, y):
        self.page.clicks.append((x, y))
        if self.page.attempt_dir is not None:
            intent = self.page.attempt_dir / "actions/step-000-intent.private.json"
            self.page.intent_existed_at_click = intent.is_file()
            if intent.is_file():
                self.page.intent_at_click = json.loads(intent.read_bytes())


class PricePage:
    viewport_size = {"width": 1440, "height": 1000}
    url = "http://127.0.0.1:8069/odoo/purchase/123"

    def __init__(self):
        self.frames = [OBSERVED, OBSERVED] + [ALTERNATE] * 20
        self.strict_identity = True
        self.diagnostic_reason = "ready"
        self.clicks = []
        self.mouse = PriceMouse(self)
        self.attempt_dir = None
        self.intent_existed_at_click = False
        self.intent_at_click = None

    def screenshot(self, *, type):
        assert type == "png"
        return self.frames.pop(0) if self.frames else ALTERNATE

    def evaluate(self, script, args=None):
        if script == VISIBLE_CONTROLS_JS:
            return []
        if script in (ATTACHMENT_LOOKUP_JS, VIEWER_LOOKUP_JS):
            return None
        if script == PRICE_ROUTE_DIAGNOSTIC_JS:
            reason = self.diagnostic_reason
            return {"status": "ready" if reason == "ready" else "nonclaim",
                    "reason_code": reason,
                    "visible_price_input_count": 1}
        if script == PRICE_EDITOR_LOOKUP_JS:
            if not self.strict_identity:
                return None
            target = args["target"]
            bounds = [782, 465, 836, 493]
            return {
                "rfq_id": args["rfq_id"],
                "route_path": args["route_path"],
                "sku": args["sku"],
                "initial_price": args["price"],
                "row_bounds": [16, 460, 1424, 545],
                "product_cell_bounds": [16, 460, 758, 545],
                "cell_bounds": [758, 460, 861, 545],
                "editor_bounds": bounds,
                "editor_tag": "input", "editor_type": "text",
                "focused": True, "modal_absent": True,
                "product_cell_sku_seen": True,
                "editor_readonly": False,
                "target_inside": target is None or
                    (bounds[0] <= target["x"] <= bounds[2] and
                     bounds[1] <= target["y"] <= bounds[3]),
            }
        raise AssertionError("unexpected UI query")

    def wait_for_timeout(self, _duration):
        pass


class PriceLocator:
    def bounding_box(self):
        return {"x": 782, "y": 465, "width": 54, "height": 28}


class WrongLocator:
    def bounding_box(self):
        return {"x": 880, "y": 465, "width": 40, "height": 28}


class RouteRouterTests(unittest.TestCase):
    def setup_attempt(self):
        temp = tempfile.TemporaryDirectory()
        out = Path(temp.name) / "attempt"
        out.mkdir(mode=0o700)
        page = PricePage()
        page.attempt_dir = out
        adapter = OdooV066TrainRouteRouterV1(
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

    def test_claim_token_in_intent_before_double_click_and_audited(self):
        temp, out, page, adapter, journal = self.setup_attempt()
        with temp:
            journal.act("double_click", phase="positive", locator=PriceLocator())
            self.assertEqual(page.clicks, [(809, 479)])
            self.assertTrue(page.intent_existed_at_click)
            intent = page.intent_at_click
            self.assertEqual(intent["route_kind"], "price_editor")
            self.assertEqual(intent["route_token"],
                             json.loads((out / intent["route_claim_ref"]["path"])
                                        .read_bytes())["route_token"])
            result = json.loads((out / "actions/step-000-result.private.json")
                                .read_bytes())
            kind, refs = _route_binding(out, journal.trace[0], intent, result)
            self.assertEqual(kind, "price_editor")
            self.assertEqual(len(refs), 2)
            self.assertEqual(journal.sft, [])

    def test_missing_price_identity_is_reason_coded_pre_intent_rejection(self):
        temp, out, page, adapter, journal = self.setup_attempt()
        with temp:
            page.strict_identity = False
            page.diagnostic_reason = "product_cell_sku_missing"
            with self.assertRaises(ContractError):
                journal.act("double_click", phase="positive",
                            locator=PriceLocator())
            self.assertEqual(page.clicks, [])
            self.assertFalse(any((out / "actions").glob("*-intent.private.json")))
            self.assertEqual(len(journal.pre_intent_rejections), 3)
            for ref in journal.pre_intent_rejections:
                rejection = json.loads((out / ref["path"]).read_bytes())
                self.assertFalse(rejection["pre_dispatch_intent_created"])
                self.assertFalse(rejection["gui_action_dispatched"])
                decision = json.loads((out / rejection["route_decision_ref"]["path"])
                                      .read_bytes())
                self.assertEqual(decision["status"], "nonclaim")
                self.assertEqual(decision["reason_code"],
                                 "product_cell_sku_missing")

    def test_wrong_route_token_fails_before_mouse(self):
        temp, out, page, adapter, _journal = self.setup_attempt()
        with temp:
            observation, _rendered = adapter.observe_for_model()
            action = adapter.parse_current_action(json.dumps({
                "type": "double_click", "target": {"x": 809, "y": 479}}))
            self.assertEqual(observation.step, 0)
            with self.assertRaises(ContractError):
                adapter.dispatch(action, route_token="0" * 64)
            self.assertEqual(page.clicks, [])

    def test_auditor_rejects_changed_intent_token_or_route_kind(self):
        temp, out, _page, _adapter, journal = self.setup_attempt()
        with temp:
            journal.act("double_click", phase="positive", locator=PriceLocator())
            intent = json.loads((out / "actions/step-000-intent.private.json")
                                .read_bytes())
            result = json.loads((out / "actions/step-000-result.private.json")
                                .read_bytes())
            with self.assertRaises(CalibrationAuditError):
                _route_binding(out, journal.trace[0],
                               {**intent, "route_token": "0" * 64}, result)
            with self.assertRaises(CalibrationAuditError):
                _route_binding(out,
                               {**journal.trace[0],
                                "route_kind": "generic_rfq"}, intent, result)

    def test_wrong_price_target_is_durable_nonclaim_before_intent(self):
        temp, out, page, _adapter, journal = self.setup_attempt()
        with temp:
            with self.assertRaises(ContractError):
                journal.act("double_click", phase="positive",
                            locator=WrongLocator())
            self.assertEqual(page.clicks, [])
            self.assertFalse(any((out / "actions").glob("*-intent.private.json")))
            rejection = json.loads((out / journal.pre_intent_rejections[0]["path"])
                                   .read_bytes())
            decision = json.loads((out / rejection["route_decision_ref"]["path"])
                                  .read_bytes())
            self.assertEqual(decision["reason_code"],
                             "target_outside_price_editor")

    def test_ready_diagnostic_without_strict_identity_has_reason(self):
        temp, out, page, _adapter, journal = self.setup_attempt()
        with temp:
            page.strict_identity = False
            with self.assertRaises(ContractError):
                journal.act("double_click", phase="positive",
                            locator=PriceLocator())
            rejection = json.loads((out / journal.pre_intent_rejections[0]["path"])
                                   .read_bytes())
            probe = json.loads((out / rejection["route_probe_ref"]["path"])
                               .read_bytes())
            self.assertEqual(probe["status"], "nonclaim")
            self.assertEqual(probe["reason_code"],
                             "strict_identity_missing")

    def test_third_raster_is_reason_coded_before_intent(self):
        temp, out, page, adapter, _journal = self.setup_attempt()
        with temp:
            page.frames = [OBSERVED, OBSERVED] + [THIRD] * 20
            adapter.observe_for_model()
            with self.assertRaises(ContractError):
                adapter.parse_current_action(json.dumps({
                    "type": "double_click",
                    "target": {"x": 809, "y": 479}}))
            self.assertEqual(page.clicks, [])
            self.assertFalse(any((out / "actions").glob("*-intent.private.json")))
            decision = json.loads((out / adapter.latest_route_decision_ref["path"])
                                  .read_bytes())
            self.assertEqual(decision["reason_code"],
                             "physical_or_identity_guard_rejected")

    def test_generic_wait_has_distinct_durable_route(self):
        temp, out, page, _adapter, journal = self.setup_attempt()
        with temp:
            page.frames = [OBSERVED] * 20
            journal.act("wait", phase="positive", duration_ms=100)
            intent = json.loads((out / "actions/step-000-intent.private.json")
                                .read_bytes())
            result = json.loads((out / "actions/step-000-result.private.json")
                                .read_bytes())
            self.assertEqual(intent["route_kind"], "generic_rfq")
            kind, _refs = _route_binding(
                out, journal.trace[0], intent, result)
            self.assertEqual(kind, "generic_rfq")
            self.assertEqual(page.clicks, [])


if __name__ == "__main__":
    unittest.main()
