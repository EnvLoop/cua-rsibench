"""The four-pixel train price-editor route is narrow and fail-closed."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v4 import (
    OdooV066TrainAttachmentRouteAdapterV4, PRICE_EDITOR_LOOKUP_JS,
    _decorative_corner_alternate,
)


SKU = "EL-TRN-C98D176352-018"
PRICE = "176.52"


def png(image):
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


image = Image.new("RGB", (1440, 1000), (255, 255, 255))
for xy, color in (
        ((16, 861), (226, 230, 234)),
        ((17, 861), (249, 250, 250)),
        ((16, 863), (246, 247, 248)),
        ((17, 863), (229, 233, 236))):
    image.putpixel(xy, color)
OBSERVED = png(image)
for xy, color in (
        ((16, 861), (226, 229, 234)),
        ((17, 861), (250, 250, 251)),
        ((16, 863), (246, 247, 249)),
        ((17, 863), (230, 233, 236))):
    image.putpixel(xy, color)
ALTERNATE = png(image)
image.putpixel((800, 800), (0, 0, 0))
THIRD = png(image)


class Mouse:
    def __init__(self, page):
        self.page = page

    def dblclick(self, x, y):
        self.page.double_clicks.append((x, y))


class PricePage:
    viewport_size = {"width": 1440, "height": 1000}

    def __init__(self, screenshots=None):
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.screenshots = list(screenshots or [ALTERNATE] * 6)
        self.last_frame = self.screenshots[-1]
        self.source_sku = SKU
        self.value = PRICE
        self.modal = False
        self.viewer = False
        self.focused = True
        self.ambiguous = False
        self.moved = False
        self.hit = True
        self.double_clicks = []
        self.mouse = Mouse(self)

    def screenshot(self, *, type):
        assert type == "png"
        return self.screenshots.pop(0) if self.screenshots else self.last_frame

    def wait_for_timeout(self, _duration):
        pass

    def evaluate(self, script, args):
        if script != PRICE_EDITOR_LOOKUP_JS:
            raise AssertionError("price guard must not query another UI route")
        if (self.modal or self.viewer or self.ambiguous or
                self.source_sku != args["sku"] or
                self.value != args["price"] or not self.focused):
            return None
        bounds = [782, 465, 835, 490]
        if self.moved:
            bounds = [880, 465, 933, 490]
        target = args["target"]
        return {
            "sku": args["sku"], "initial_price": args["price"],
            "row_bounds": [16, 460, 1424, 545],
            "cell_bounds": [758, 460, 861, 545],
            "editor_bounds": bounds,
            "editor_tag": "input", "editor_type": "text",
            "focused": True, "modal_absent": True,
            "target_inside": target is None or
                (self.hit and bounds[0] <= target["x"] <= bounds[2]
                 and bounds[1] <= target["y"] <= bounds[3]),
        }


class PriceCornerRouteTests(unittest.TestCase):
    def setup_adapter(self, frames=None):
        page = PricePage(frames)
        adapter = OdooV066TrainAttachmentRouteAdapterV4(
            page, task_id="ELPO-TRN-0001",
            task_binding_sha256="a" * 64,
            instruction="train-only",
            expected_attachment_label="ELPO-TRN-0001-source.pdf",
            expected_price_sku=SKU,
            expected_initial_price=PRICE)
        adapter.step = 8
        observation = make_observation(
            task_id=adapter.task_id,
            task_binding_sha256=adapter.task_binding_sha256,
            instruction="train-only", step=8,
            screenshot_bytes=OBSERVED,
            previous_action_result={"status": "applied", "code": "ok"})
        adapter.latest = observation
        adapter.latest_url = page.url
        adapter.observed_price_editor = page.evaluate(
            PRICE_EDITOR_LOOKUP_JS,
            {"sku": SKU, "price": PRICE, "target": None})
        adapter.observed_price_frame_id = observation.frame_id
        saved = []

        def sink(index, raw):
            self.assertEqual(index, len(saved))
            saved.append(raw)
            return {"path": f"frames/guard-{index:04d}.png",
                    "sha256": sha256(raw).hexdigest()}

        adapter.frame_guard_sink = sink
        raw = json.dumps({"type": "double_click",
                          "target": {"x": 809, "y": 479}})
        return page, adapter, observation, raw, saved

    def test_exact_four_pixel_two_state_parse_and_dispatch(self):
        self.assertTrue(_decorative_corner_alternate(OBSERVED, ALTERNATE))
        self.assertTrue(_decorative_corner_alternate(ALTERNATE, OBSERVED))
        self.assertFalse(_decorative_corner_alternate(OBSERVED, THIRD))
        page, adapter, _observation, raw, saved = self.setup_adapter()
        action = adapter.parse_current_action(raw)
        result = adapter.dispatch(action)
        self.assertEqual(page.double_clicks, [(809, 479)])
        self.assertEqual(saved, [ALTERNATE] * 6)
        receipt = result["public_contract_receipt"]
        self.assertEqual(receipt["price_parse_guard"]["classification"],
                         "two_frame_corner_alternate_confirmed")
        self.assertEqual(receipt["price_dispatch_guard"]["classification"],
                         "two_frame_corner_alternate_confirmed")
        self.assertEqual(adapter.step, 9)

    def test_wrong_target_third_state_modal_or_dom_change_fail_before_click(self):
        for change in ("wrong_target", "third", "modal", "viewer",
                       "sku", "price", "focus", "ambiguous", "moved", "hit"):
            with self.subTest(change=change):
                frames = [THIRD] if change == "third" else None
                page, adapter, _observation, raw, _saved = self.setup_adapter(frames)
                if change == "wrong_target":
                    raw = json.dumps({"type": "double_click",
                                      "target": {"x": 900, "y": 479}})
                elif change in ("modal", "viewer", "ambiguous", "moved"):
                    setattr(page, change, True)
                elif change == "sku":
                    page.source_sku = "EL-TRN-OTHER-001"
                elif change == "price":
                    page.value = "999.99"
                elif change == "focus":
                    page.focused = False
                elif change == "hit":
                    page.hit = False
                with self.assertRaises(ContractError):
                    adapter.parse_current_action(raw)
                self.assertEqual(page.double_clicks, [])

    def test_unstable_first_or_second_final_fails_before_click(self):
        for frames in ([ALTERNATE, OBSERVED],
                       [ALTERNATE, ALTERNATE, OBSERVED]):
            with self.subTest(frames=len(frames)):
                page, adapter, _observation, raw, _saved = self.setup_adapter(frames)
                with self.assertRaises(ContractError):
                    adapter.parse_current_action(raw)
                self.assertEqual(page.double_clicks, [])

    def test_changed_target_or_frame_between_parse_and_dispatch_fails(self):
        for change in ("modal", "moved", "third", "frame_id"):
            with self.subTest(change=change):
                page, adapter, _observation, raw, _saved = self.setup_adapter()
                action = adapter.parse_current_action(raw)
                if change in ("modal", "moved"):
                    setattr(page, change, True)
                elif change == "third":
                    page.screenshots = [THIRD]
                else:
                    adapter.observed_price_frame_id = "old-frame"
                with self.assertRaises(ContractError):
                    adapter.dispatch(action)
                self.assertEqual(page.double_clicks, [])


if __name__ == "__main__":
    unittest.main()
