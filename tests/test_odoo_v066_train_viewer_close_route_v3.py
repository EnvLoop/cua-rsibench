"""Train-only PDF viewer close transition remains exact and bounded."""

from __future__ import annotations

from io import BytesIO
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v3 import (
    OdooV066TrainAttachmentRouteAdapterV3, RFQ_RETURN_JS,
    VIEWER_LOOKUP_JS,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v2 import (
    OdooV066TrainAttachmentRouteAdapterV2,
)


def png(rgb: tuple[int, int, int]) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (1440, 1000), rgb).save(stream, format="PNG")
    return stream.getvalue()


SOURCE_LABEL = "ELPO-TRN-0001-source.pdf"
VIEWER = png((255, 255, 255))
OTHER = png((240, 240, 240))
RFQ = png((248, 248, 248))


class FakeLocator:
    def __init__(self, page):
        self.page = page

    def wait_for(self, *, state, timeout):
        assert state == "hidden" and timeout == 3000
        if self.page.viewer_present:
            raise TimeoutError("viewer did not close")


class FakeMouse:
    def __init__(self, page):
        self.page = page

    def click(self, x, y):
        self.page.clicks.append((x, y))
        if self.page.close_on_click:
            self.page.viewer_present = False


class FakePage:
    viewport_size = {"width": 1440, "height": 1000}

    def __init__(self):
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.viewer_present = True
        self.source_label = SOURCE_LABEL
        self.ambiguous = False
        self.moved = False
        self.hit = True
        self.stale_image = False
        self.close_on_click = True
        self.return_rfq = True
        self.clicks = []
        self.mouse = FakeMouse(self)

    def evaluate(self, script, args):
        if script == RFQ_RETURN_JS:
            return self.return_rfq and not self.viewer_present
        if script != VIEWER_LOOKUP_JS:
            raise AssertionError("unexpected UI read")
        if not self.viewer_present or self.ambiguous:
            return None
        close = [1400, 8, 1426, 38]
        if self.moved:
            close = [1350, 8, 1376, 38]
        return {
            "source_label": self.source_label,
            "title_tag": "span", "title_bounds": [24, 13, 230, 34],
            "close_tag": "button", "close_title": "Close (Esc)",
            "close_bounds": close,
            "iframe_bounds": [180, 53, 1260, 950],
            "target_inside": args["target"] is None or
                (self.hit and close[0] <= args["target"]["x"] <= close[2]
                 and close[1] <= args["target"]["y"] <= close[3]),
        }

    def screenshot(self, *, type):
        assert type == "png"
        if not self.viewer_present:
            return RFQ
        return OTHER if self.stale_image else VIEWER

    def locator(self, selector):
        assert selector == "iframe.o-FileViewer-view"
        return FakeLocator(self)

    def wait_for_timeout(self, _duration):
        pass


class ViewerCloseRouteTests(unittest.TestCase):
    def setup_adapter(self):
        page = FakePage()
        adapter = OdooV066TrainAttachmentRouteAdapterV3(
            page, task_id="ELPO-TRN-0001",
            task_binding_sha256="a" * 64,
            instruction="train-only",
            expected_attachment_label=SOURCE_LABEL)
        adapter.step = 6
        observation = make_observation(
            task_id=adapter.task_id,
            task_binding_sha256=adapter.task_binding_sha256,
            instruction="train-only", step=6,
            screenshot_bytes=VIEWER,
            previous_action_result={"status": "applied", "code": "ok"})
        adapter.latest = observation
        adapter.latest_url = page.url
        adapter.observed_viewer = page.evaluate(
            VIEWER_LOOKUP_JS, {"label": SOURCE_LABEL, "target": None})
        adapter.observed_viewer_frame_id = observation.frame_id
        saved = []

        def sink(index, raw):
            self.assertEqual(index, len(saved))
            saved.append(raw)
            return {"path": f"frames/guard-{index:04d}.png",
                    "sha256": sha256(raw).hexdigest()}

        adapter.frame_guard_sink = sink
        raw = json.dumps({"type": "click", "target": {"x": 1413, "y": 23}})
        return page, adapter, observation, raw, saved

    def test_exact_viewer_close_and_return_to_rfq(self):
        page, adapter, _observation, raw, saved = self.setup_adapter()
        action = adapter.parse_current_action(raw)
        result = adapter.dispatch(action)
        self.assertEqual(page.clicks, [(1413, 23)])
        self.assertFalse(page.viewer_present)
        self.assertEqual(adapter.step, 7)
        self.assertEqual(len(saved), 7)  # parse 3, dispatch 3, return 1
        receipt = result["public_contract_receipt"]
        self.assertEqual(receipt["viewer_parse_guard"]["classification"],
                         "two_frame_observed_confirmed")
        self.assertEqual(receipt["viewer_dispatch_guard"]["classification"],
                         "two_frame_observed_confirmed")
        self.assertEqual(receipt["viewer_return_guard"]["classification"],
                         "original_rfq_return_confirmed")
        self.assertEqual(adapter.frame_guard_samples[-1]["stage"],
                         "viewer_return")

    def test_wrong_overlay_and_ambiguous_close_fail_before_click(self):
        for change in ("source_label", "ambiguous", "moved", "hit",
                       "viewer_present", "stale_image"):
            with self.subTest(change=change):
                page, adapter, _observation, raw, _saved = self.setup_adapter()
                if change == "source_label":
                    page.source_label = "another-source.pdf"
                elif change in ("ambiguous", "moved", "stale_image"):
                    setattr(page, change, True)
                elif change == "hit":
                    page.hit = False
                else:
                    page.viewer_present = False
                with self.assertRaises(ContractError):
                    adapter.parse_current_action(raw)
                self.assertEqual(page.clicks, [])

    def test_stale_frame_id_fails_before_click(self):
        page, adapter, observation, raw, _saved = self.setup_adapter()
        adapter.observed_viewer_frame_id = "another-frame"
        with self.assertRaises(ContractError):
            adapter.parse_current_action(raw)
        self.assertEqual(page.clicks, [])
        self.assertIs(adapter.latest, observation)

    def test_viewer_changes_between_parse_and_dispatch_fail_before_click(self):
        for change in ("source_label", "viewer_present", "stale_image"):
            with self.subTest(change=change):
                page, adapter, _observation, raw, _saved = self.setup_adapter()
                action = adapter.parse_current_action(raw)
                if change == "source_label":
                    page.source_label = "other.pdf"
                elif change == "viewer_present":
                    page.viewer_present = False
                else:
                    page.stale_image = True
                with self.assertRaises(ContractError):
                    adapter.dispatch(action)
                self.assertEqual(page.clicks, [])

    def test_viewer_must_close_and_return_to_rfq(self):
        for change in ("close_on_click", "return_rfq"):
            with self.subTest(change=change):
                page, adapter, _observation, raw, _saved = self.setup_adapter()
                setattr(page, change, False)
                action = adapter.parse_current_action(raw)
                with self.assertRaises(ContractError):
                    adapter.dispatch(action)
                self.assertEqual(page.clicks, [(1413, 23)])
                self.assertIsNone(adapter._parsed_viewer_close)

    def test_non_viewer_route_delegates_to_unchanged_parent(self):
        _page, adapter, observation, raw, _saved = self.setup_adapter()
        adapter.observed_viewer = None
        sentinel = {"parent": True}
        with patch.object(OdooV066TrainAttachmentRouteAdapterV2,
                          "parse_current_action", return_value=sentinel) as parsed:
            self.assertIs(adapter.parse_current_action(raw), sentinel)
            parsed.assert_called_once_with(raw)
        with patch.object(OdooV066TrainAttachmentRouteAdapterV2,
                          "dispatch", return_value=sentinel) as sent:
            self.assertIs(adapter.dispatch({"type": "wait"}), sentinel)
            sent.assert_called_once_with({"type": "wait"})
        self.assertIs(adapter.latest, observation)


if __name__ == "__main__":
    unittest.main()
