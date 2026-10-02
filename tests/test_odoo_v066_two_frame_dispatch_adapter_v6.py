"""Offline mutation tests for the bounded Odoo v6 RFQ dispatch guard."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from enterprise_fallback.odoo18.odoo_v066_scale_exact_return_adapter import (
    OdooV066ScaleExactReturnAdapter,
)
from enterprise_fallback.odoo18.odoo_v066_two_frame_dispatch_adapter_v6 import (
    ALTERNATE, OBSERVED, OdooV066TwoFrameDispatchAdapterV6,
)


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class Page:
    viewport_size = {"width": 1440, "height": 1000}

    def __init__(self, url: str, screens: list[bytes], controls: list[dict]):
        self.url = url
        self.screens = iter(screens)
        self.controls = iter(controls)

    def screenshot(self, *, type: str) -> bytes:
        return next(self.screens)

    def evaluate(self, _script: str, _target: dict) -> dict:
        return next(self.controls)


class TwoFrameDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        image = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for point in ((41, 419), (132, 419)):
            image.putpixel(point, (235, 237, 240))
        alternate = image.copy()
        for point in ((41, 419), (132, 419)):
            alternate.putpixel(point, (235, 237, 239))
        third = image.copy()
        third.putpixel((800, 800), (0, 0, 0))
        self.observed = png(image)
        self.alternate = png(alternate)
        self.third = png(third)
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

    def run_guard(self, first: bytes, second: bytes | None,
                  *, controls: list[dict] | None = None,
                  action: dict | None = None) -> tuple[bool, object, list[int]]:
        page = Page(self.url, [first] + ([second] if second is not None else []),
                    controls or [self.control, self.control])
        adapter = OdooV066TwoFrameDispatchAdapterV6(
            page, task_id=self.observation.task_id,
            task_binding_sha256=self.observation.task_binding_sha256,
            instruction="synthetic")
        adapter.latest = self.observation
        adapter.latest_url = self.url
        adapter.observed_target_control = self.control
        adapter._pending_dispatch_action = action or self.action
        indexes: list[int] = []

        def sink(index: int, raw: bytes) -> dict:
            indexes.append(index)
            return {"path": f"frames/guard-{index:04d}.png",
                    "sha256": sha256(raw).hexdigest()}

        adapter.frame_guard_sink = sink

        def six_alternates(current, observation, *, stage):
            self.assertEqual(stage, "dispatch")
            for index in range(6):
                ref = current.frame_guard_sink(
                    len(current.frame_guard_samples), self.alternate)
                current.frame_guard_samples.append({
                    "step": current.step, "stage": "dispatch",
                    "sample": index,
                    "observed_frame_sha256":
                        observation.screenshot["sha256"],
                    "observed_frame_id_sha256":
                        sha256(observation.frame_id.encode()).hexdigest(),
                    "sampled_frame_ref": ref,
                    "classification":
                        "one_recurring_micro_raster_alternate",
                })
            return False

        with patch.object(OdooV066ScaleExactReturnAdapter,
                          "_frame_current", new=six_alternates):
            result = adapter._frame_current(
                self.observation, stage="dispatch")
        return result, adapter, indexes

    def test_exact_observed_return_is_confirmed_twice(self) -> None:
        result, adapter, indexes = self.run_guard(
            self.observed, self.observed)
        self.assertTrue(result)
        self.assertEqual(indexes, list(range(8)))
        self.assertEqual(adapter._physical_guard_receipt["classification"],
                         OBSERVED)
        self.assertEqual([sample["classification"] for sample in
                          adapter.frame_guard_samples[-2:]],
                         ["two_frame_candidate_observed", OBSERVED])

    def test_single_alternate_is_confirmed_twice(self) -> None:
        result, adapter, indexes = self.run_guard(
            self.alternate, self.alternate)
        self.assertTrue(result)
        self.assertEqual(indexes, list(range(8)))
        self.assertEqual(adapter._physical_guard_receipt["classification"],
                         ALTERNATE)

    def test_third_first_frame_fails_closed(self) -> None:
        result, adapter, indexes = self.run_guard(self.third, None)
        self.assertFalse(result)
        self.assertIsNone(adapter._physical_guard_receipt)
        self.assertEqual(indexes, list(range(7)))
        self.assertEqual(adapter.frame_guard_samples[-1]["classification"],
                         "third_or_material_frame_rejected")

    def test_second_frame_switch_fails_closed(self) -> None:
        result, adapter, indexes = self.run_guard(
            self.observed, self.alternate)
        self.assertFalse(result)
        self.assertIsNone(adapter._physical_guard_receipt)
        self.assertEqual(indexes, list(range(8)))
        self.assertEqual(adapter.frame_guard_samples[-1]["classification"],
                         "two_frame_confirmation_rejected")

    def test_target_control_or_frame_binding_change_fails_closed(self) -> None:
        changed = {**self.control, "label": "Another control"}
        result, adapter, _ = self.run_guard(
            self.observed, self.observed,
            controls=[self.control, changed])
        self.assertFalse(result)
        self.assertIsNone(adapter._physical_guard_receipt)
        result, adapter, indexes = self.run_guard(
            self.observed, self.observed,
            action={**self.action, "frame_id": "old-frame"})
        self.assertFalse(result)
        self.assertEqual(indexes, [])


if __name__ == "__main__":
    unittest.main()
