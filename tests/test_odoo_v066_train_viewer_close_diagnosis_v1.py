"""Exact viewer frames do not make an unbound overlay close click safe."""

from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18.odoo_v066_scale_exact_return_adapter import (
    OdooV066ScaleExactReturnAdapter,
)
from enterprise_fallback.odoo18.odoo_v066_scale_pinned_border_adapter import (
    _target_outside_pinned_border,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v2 import (
    OdooV066TrainAttachmentRouteAdapterV2,
)


class ViewerPage:
    viewport_size = {"width": 1440, "height": 1000}

    def __init__(self) -> None:
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.screenshots = 0

    def evaluate(self, _script, _target):
        # The viewer close X is outside the RFQ data-envloop-ref controls.
        return None

    def screenshot(self, *, type):
        self.screenshots += 1
        return b"exact-stable-viewer-frame"


class ViewerCloseDiagnosisTests(unittest.TestCase):
    def test_close_control_is_not_an_rfq_target(self) -> None:
        action = {"type": "click", "target": {"x": 1413, "y": 23}}
        observation = SimpleNamespace(controls=[])
        self.assertFalse(_target_outside_pinned_border(
            action, None, None, observation))

    def test_exact_stable_viewer_frame_still_fails_rfq_dispatch_guard(self) -> None:
        page = ViewerPage()
        adapter = OdooV066TrainAttachmentRouteAdapterV2(
            page, task_id="ELPO-TRN-0001",
            task_binding_sha256="a" * 64,
            instruction="train-only",
            expected_attachment_label="ELPO-TRN-0001-source.pdf")
        raw = b"exact-stable-viewer-frame"
        observation = SimpleNamespace(
            task_id=adapter.task_id,
            task_binding_sha256=adapter.task_binding_sha256,
            frame_id="viewer-frame",
            screenshot_bytes=raw,
            screenshot={"sha256": sha256(raw).hexdigest()},
            controls=[],
        )
        adapter.latest = observation
        adapter.latest_url = page.url
        adapter._pending_dispatch_action = {
            "type": "click", "target": {"x": 1413, "y": 23},
            "task_id": adapter.task_id,
            "task_binding_sha256": adapter.task_binding_sha256,
            "frame_id": observation.frame_id,
        }
        adapter.observed_target_control = None

        def exact(current, _observation, *, stage):
            self.assertEqual(stage, "dispatch")
            current.frame_guard_samples.append({
                "stage": "dispatch", "classification": "exact_return"})
            return True

        with patch.object(OdooV066ScaleExactReturnAdapter,
                          "_frame_current", new=exact):
            self.assertFalse(adapter._frame_current(
                observation, stage="dispatch"))
        self.assertEqual(page.screenshots, 0)
        self.assertIsNone(adapter._physical_guard_receipt)


if __name__ == "__main__":
    unittest.main()
