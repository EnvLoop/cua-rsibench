"""Reproduce the v8 unclaimed-price generic parse/dispatch split offline."""

from __future__ import annotations

from hashlib import sha256
import json
import unittest

from cursibench.scale_action_contract import ContractError, make_observation
from enterprise_fallback.odoo18.odoo_v066_scale_pinned_border_adapter import (
    TARGET_ELEMENT_JS,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v5 import (
    OdooV066TrainAttachmentRouteAdapterV5,
)
from tests.test_odoo_v066_train_price_corner_route_v5 import (
    ALTERNATE, OBSERVED, TARGETS,
)


class UnclaimedPricePage:
    viewport_size = {"width": 1440, "height": 1000}
    url = "http://127.0.0.1:8069/odoo/purchase/123"

    def __init__(self):
        self.frames = [OBSERVED, ALTERNATE]
        self.mouse_clicks = []

    def screenshot(self, *, type):
        return self.frames.pop(0) if self.frames else ALTERNATE

    def evaluate(self, script, _args):
        if script == TARGET_ELEMENT_JS:
            return {
                "ref": "c039", "role": "input", "label": "",
                "visible": True, "enabled": True,
                "purchase_rfq_view": True,
                "bounds": [763, 468, 856, 490],
            }
        raise AssertionError("unexpected route lookup")

    def wait_for_timeout(self, _duration):
        pass


class PriceFallbackDiagnosisTests(unittest.TestCase):
    def test_unclaimed_editor_exact_parse_then_alternate_dispatch_rejects(self):
        page = UnclaimedPricePage()
        adapter = OdooV066TrainAttachmentRouteAdapterV5(
            page, task_id="ELPO-TRN-0001",
            task_binding_sha256="a" * 64,
            instruction="train-only",
            expected_attachment_label="ELPO-TRN-0001-source.pdf",
            expected_price_targets=TARGETS)
        adapter.step = 8
        observation = make_observation(
            task_id=adapter.task_id,
            task_binding_sha256=adapter.task_binding_sha256,
            instruction="train-only", step=8,
            screenshot_bytes=OBSERVED,
            previous_action_result={"status": "applied", "code": "ok"})
        adapter.latest = observation
        adapter.latest_url = page.url
        adapter.current_price_target = TARGETS[0]
        adapter.observed_price_editor = None
        adapter.observed_price_frame_id = observation.frame_id
        saved = []

        def sink(index, raw):
            saved.append(raw)
            return {"path": f"frames/guard-{index:04d}.png",
                    "sha256": sha256(raw).hexdigest()}

        adapter.frame_guard_sink = sink
        raw = json.dumps({"type": "double_click",
                          "target": {"x": 809, "y": 479}})
        action = adapter.parse_current_action(raw)
        self.assertEqual(action["type"], "double_click")
        self.assertIsNone(adapter._parsed_price_edit)
        self.assertEqual(adapter.frame_guard_samples[0]["stage"], "parse")
        self.assertEqual(adapter.frame_guard_samples[0]["classification"],
                         "exact_return")
        with self.assertRaises(ContractError) as caught:
            adapter.dispatch(action)
        self.assertEqual(caught.exception.code, "stale_frame")
        self.assertEqual([sample["stage"] for sample in
                          adapter.frame_guard_samples],
                         ["parse", "dispatch"])
        self.assertEqual(adapter.frame_guard_samples[-1]["classification"],
                         "third_or_material_frame_rejected")
        self.assertEqual(saved, [OBSERVED, ALTERNATE])


if __name__ == "__main__":
    unittest.main()
