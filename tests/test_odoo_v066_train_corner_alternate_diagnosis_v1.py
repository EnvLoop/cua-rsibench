"""The saved four-pixel RFQ corner alternate remains rejected at parse."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v3 import (
    OdooV066TrainAttachmentRouteAdapterV3,
)


def png(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class AlternatingPage:
    viewport_size = {"width": 1440, "height": 1000}
    url = "http://127.0.0.1:8069/odoo/purchase/123"

    def __init__(self, alternate: bytes):
        self.alternate = alternate

    def screenshot(self, *, type):
        return self.alternate

    def wait_for_timeout(self, _duration):
        pass

    def evaluate(self, _script, _args):
        raise AssertionError("unbound target must not be queried")


class CornerAlternateDiagnosisTests(unittest.TestCase):
    def test_price_double_click_is_rejected_before_target_lookup(self):
        image = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for point, color in (
                ((16, 861), (226, 230, 234)),
                ((17, 861), (249, 250, 250)),
                ((16, 863), (246, 247, 248)),
                ((17, 863), (229, 233, 236))):
            image.putpixel(point, color)
        observed = png(image)
        for point, color in (
                ((16, 861), (226, 229, 234)),
                ((17, 861), (250, 250, 251)),
                ((16, 863), (246, 247, 249)),
                ((17, 863), (230, 233, 236))):
            image.putpixel(point, color)
        alternate = png(image)
        page = AlternatingPage(alternate)
        adapter = OdooV066TrainAttachmentRouteAdapterV3(
            page, task_id="ELPO-TRN-0001",
            task_binding_sha256="a" * 64,
            instruction="train-only",
            expected_attachment_label="ELPO-TRN-0001-source.pdf")
        adapter.step = 8
        observation = make_observation(
            task_id=adapter.task_id,
            task_binding_sha256=adapter.task_binding_sha256,
            instruction="train-only", step=8,
            screenshot_bytes=observed,
            previous_action_result={"status": "applied", "code": "ok"})
        adapter.latest = observation
        adapter.latest_url = page.url
        saved = []

        def sink(index, raw):
            saved.append(raw)
            return {"path": f"frames/guard-{index:04d}.png",
                    "sha256": sha256(raw).hexdigest()}

        adapter.frame_guard_sink = sink
        with self.assertRaises(ContractError) as caught:
            adapter.parse_current_action(json.dumps({
                "type": "double_click", "target": {"x": 809, "y": 479}}))
        self.assertEqual(caught.exception.code, "stale_frame")
        self.assertEqual(saved, [alternate])
        self.assertEqual(adapter.frame_guard_samples[0]["classification"],
                         "third_or_material_frame_rejected")


if __name__ == "__main__":
    unittest.main()
