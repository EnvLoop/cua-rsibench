"""Offline safety boundaries for the additive Odoo parse-stage exception."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from enterprise_fallback.odoo18.odoo_v066_scale_parse_border_adapter_v5 import (
    OdooV066ScaleParseBorderAdapterV5, _valid_alternate,
)
from enterprise_fallback.odoo18.odoo_v066_scale_pinned_border_adapter import (
    OdooV066ScalePinnedBorderAdapter,
)
from enterprise_fallback.odoo18 import odoo_v066_scale_parse_border_adapter_v5 as module
from cursibench.scale_action_contract import ContractError


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class ParseBorderTests(unittest.TestCase):
    def setUp(self) -> None:
        first = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for point in ((41, 419), (132, 419)):
            first.putpixel(point, (235, 237, 239))
        second = first.copy()
        for point in ((41, 419), (132, 419)):
            second.putpixel(point, (235, 237, 240))
        self.observed = png(first)
        self.physical = png(second)
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.control = {
            "ref": "c100", "role": "button", "label": "Attach Files",
            "visible": True, "enabled": True, "purchase_rfq_view": True,
            "bounds": [1280, 850, 1335, 885],
        }
        self.observation = SimpleNamespace(
            task_id="synthetic-id", task_binding_sha256="a" * 64,
            frame_id="synthetic-frame",
            screenshot={"sha256": sha256(self.observed).hexdigest()},
            screenshot_bytes=self.observed,
            controls=[SimpleNamespace(ref="c100", role="button",
                                      label="Attach Files", visible=True,
                                      enabled=True)],
        )
        self.action = {
            "type": "click", "target": {"x": 1307, "y": 868},
            "task_id": self.observation.task_id,
            "task_binding_sha256": self.observation.task_binding_sha256,
            "frame_id": self.observation.frame_id,
        }
        self.samples = [
            {"stage": "parse", "sample": i,
             "classification": "one_recurring_micro_raster_alternate",
             "observed_frame_sha256":
                 self.observation.screenshot["sha256"],
             "observed_frame_id_sha256":
                 sha256(self.observation.frame_id.encode()).hexdigest(),
             "sampled_frame_ref": {
                 "sha256": sha256(self.physical).hexdigest(),
             }} for i in range(6)]

    def check(self, **changes) -> bool:
        values = {
            "observation": self.observation,
            "samples": self.samples,
            "page_url": self.url,
            "latest_url": self.url,
            "task_id": self.observation.task_id,
            "task_binding_sha256": self.observation.task_binding_sha256,
            "action": self.action,
            "control_before": self.control,
            "control_after": self.control,
            "final_png": self.physical,
        }
        values.update(changes)
        return _valid_alternate(**values)

    def test_two_pixel_purchase_click_is_eligible_before_intent(self) -> None:
        self.assertTrue(self.check())

    def test_third_pixel_and_nonrecurring_sample_rejected(self) -> None:
        third = Image.open(BytesIO(self.physical)).copy()
        third.putpixel((800, 800), (0, 0, 0))
        self.assertFalse(self.check(final_png=png(third)))
        samples = [dict(row) for row in self.samples]
        samples[-1]["sampled_frame_ref"] = {"sha256": "0" * 64}
        self.assertFalse(self.check(samples=samples))

    def test_url_task_and_frame_changes_rejected(self) -> None:
        self.assertFalse(self.check(page_url=self.url + "/other"))
        self.assertFalse(self.check(page_url="http://127.0.0.1:8069/odoo/sales/123",
                                    latest_url="http://127.0.0.1:8069/odoo/sales/123"))
        self.assertFalse(self.check(task_binding_sha256="b" * 64))
        self.assertFalse(self.check(action={**self.action, "frame_id": "old"}))

    def test_target_identity_visibility_and_geometry_rejected(self) -> None:
        self.assertFalse(self.check(control_after={**self.control, "ref": "c101"}))
        self.assertFalse(self.check(control_after={**self.control, "enabled": False}))
        self.assertFalse(self.check(control_after={**self.control,
                                                  "bounds": [1200, 850, 1335, 885]}))
        self.assertFalse(self.check(action={**self.action,
                                            "target": {"x": 41, "y": 419}}))

    def test_only_purchase_click_exception(self) -> None:
        self.assertFalse(self.check(action={**self.action, "type": "type"}))
        self.assertFalse(self.check(action={**self.action, "target": {"ref": "c100"}}))
        self.assertFalse(self.check(samples=self.samples[:-1]))

    def test_adapter_records_exception_before_physical_dispatch(self) -> None:
        class Page:
            viewport_size = {"width": 1440, "height": 1000}

            def __init__(self, owner):
                self.owner = owner
                self.url = owner.url

            def screenshot(self, *, type):
                return self.owner.physical

            def evaluate(self, _script, _target):
                return self.owner.control

        adapter = OdooV066ScaleParseBorderAdapterV5(
            Page(self), task_id=self.observation.task_id,
            task_binding_sha256=self.observation.task_binding_sha256,
            instruction="synthetic")
        adapter.latest = self.observation
        adapter.latest_url = self.url
        adapter.frame_guard_sink = lambda _index, raw: {
            "path": "frames/physical.png", "sha256": sha256(raw).hexdigest()}

        def stale(original, _raw):
            original.frame_guard_samples.extend(self.samples)
            raise ContractError("stale_frame")

        with patch.object(OdooV066ScalePinnedBorderAdapter,
                          "parse_current_action", new=stale), \
             patch.object(module, "normalize_model_action",
                          return_value=self.action):
            self.assertEqual(adapter.parse_current_action("{}"), self.action)
        self.assertEqual(adapter._parse_guard_receipt["classification"],
                         module.CLASSIFICATION)
        self.assertEqual(adapter.observed_target_control, self.control)
        with patch.object(OdooV066ScalePinnedBorderAdapter, "dispatch",
                          return_value={"public_contract_receipt": {},
                                        "action": self.action}):
            applied = adapter.dispatch(self.action)
        self.assertEqual(applied["public_contract_receipt"]["parse_guard"]
                         ["classification"], module.CLASSIFICATION)
        self.assertIsNone(adapter._parse_guard_receipt)

    def test_adapter_never_parses_a_third_physical_image(self) -> None:
        class Page:
            viewport_size = {"width": 1440, "height": 1000}

            def __init__(self, owner):
                self.owner = owner
                self.url = owner.url

            def screenshot(self, *, type):
                third = Image.open(BytesIO(self.owner.physical)).copy()
                third.putpixel((800, 800), (0, 0, 0))
                return png(third)

            def evaluate(self, _script, _target):
                return self.owner.control

        adapter = OdooV066ScaleParseBorderAdapterV5(
            Page(self), task_id=self.observation.task_id,
            task_binding_sha256=self.observation.task_binding_sha256,
            instruction="synthetic")
        adapter.latest = self.observation
        adapter.latest_url = self.url
        adapter.frame_guard_sink = lambda _index, raw: {
            "path": "frames/physical.png", "sha256": sha256(raw).hexdigest()}

        def stale(original, _raw):
            original.frame_guard_samples.extend(self.samples)
            raise ContractError("stale_frame")

        with patch.object(OdooV066ScalePinnedBorderAdapter,
                          "parse_current_action", new=stale), \
             patch.object(module, "normalize_model_action",
                          return_value=self.action):
            with self.assertRaises(ContractError):
                adapter.parse_current_action("{}")
        self.assertIsNone(adapter._parse_guard_receipt)


if __name__ == "__main__":
    unittest.main()
