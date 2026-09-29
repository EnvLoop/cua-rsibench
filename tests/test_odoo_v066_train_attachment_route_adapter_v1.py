"""Train-only attachment guard rejects unstable frames and wrong link identity."""

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
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v1 import (
    OdooV066TrainAttachmentRouteAdapterV1,
)


def png(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class Page:
    viewport_size = {"width": 1440, "height": 1000}

    def __init__(self, screens: list[bytes], identities: list[dict | None]):
        self.url = "http://127.0.0.1:8069/odoo/purchase/123"
        self.screens = iter(screens)
        self.identities = iter(identities)

    def screenshot(self, *, type: str) -> bytes:
        return next(self.screens)

    def evaluate(self, _script: str, _arg: dict) -> dict | None:
        return next(self.identities)


class AttachmentGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        observed = Image.new("RGB", (1440, 1000), (255, 255, 255))
        for point in ((41, 419), (132, 419)):
            observed.putpixel(point, (235, 237, 240))
        alternate = observed.copy()
        for point in ((41, 419), (132, 419)):
            alternate.putpixel(point, (235, 237, 239))
        third = observed.copy()
        third.putpixel((800, 800), (0, 0, 0))
        self.observed = png(observed)
        self.alternate = png(alternate)
        self.third = png(third)
        self.label = "ELPO-TRN-0001-source.pdf"
        self.identity = {
            "label": self.label, "tag": "span", "role": "",
            "title": "", "bounds": [69, 953, 260, 988],
            "target_inside": True,
        }
        self.observation = SimpleNamespace(
            task_id="ELPO-TRN-0001", task_binding_sha256="a" * 64,
            frame_id="train-frame", screenshot_bytes=self.observed,
            screenshot={"sha256": sha256(self.observed).hexdigest()},
        )
        self.action = {
            "type": "click", "target": {"x": 161, "y": 969},
            "task_id": self.observation.task_id,
            "task_binding_sha256": self.observation.task_binding_sha256,
            "frame_id": self.observation.frame_id,
        }

    def run_guard(self, *, exact: bool, first: bytes,
                  second: bytes | None, identities: list[dict | None] | None = None,
                  action: dict | None = None, route: str | None = None):
        page = Page([first] + ([] if second is None else [second]),
                    identities or [self.identity] * 3)
        if route is not None:
            page.url = route
        adapter = OdooV066TrainAttachmentRouteAdapterV1(
            page, task_id=self.observation.task_id,
            task_binding_sha256=self.observation.task_binding_sha256,
            instruction="train-only", expected_attachment_label=self.label)
        adapter.latest = self.observation
        adapter.latest_url = page.url
        adapter.observed_attachment = self.identity
        adapter.observed_attachment_frame_id = self.observation.frame_id
        adapter._pending_action = action or self.action
        saved: list[bytes] = []

        def sink(index: int, raw: bytes) -> dict:
            self.assertEqual(index, len(saved))
            saved.append(raw)
            return {"path": f"frames/guard-{index:04d}.png",
                    "sha256": sha256(raw).hexdigest()}

        adapter.frame_guard_sink = sink

        def base(current, observation, *, stage):
            samples = [self.observed] if exact else [self.alternate] * 6
            for index, raw in enumerate(samples):
                ref = current.frame_guard_sink(
                    len(current.frame_guard_samples), raw)
                current.frame_guard_samples.append({
                    "step": current.step, "stage": stage, "sample": index,
                    "observed_frame_sha256":
                        observation.screenshot["sha256"],
                    "observed_frame_id_sha256":
                        sha256(observation.frame_id.encode()).hexdigest(),
                    "sampled_frame_ref": ref,
                    "classification": ("exact_return" if exact else
                                       "one_recurring_micro_raster_alternate"),
                })
            return exact

        with patch.object(OdooV066ScaleExactReturnAdapter,
                          "_frame_current", new=base):
            result = adapter._frame_current(
                self.observation, stage="dispatch")
        return result, adapter, saved

    def test_exact_train_link_and_recurring_border_alternate(self):
        for exact, frame, expected in (
                (True, self.observed, "two_frame_observed_confirmed"),
                (False, self.alternate, "two_frame_alternate_confirmed")):
            with self.subTest(exact=exact):
                passed, adapter, saved = self.run_guard(
                    exact=exact, first=frame, second=frame)
                self.assertTrue(passed)
                self.assertEqual(len(saved), 3 if exact else 8)
                self.assertEqual(adapter._physical_guard["classification"],
                                 expected)
                self.assertEqual(adapter._physical_guard["target_identity"]
                                 ["label"], self.label)

    def test_wrong_link_and_moved_target_fail_closed(self):
        wrong = {**self.identity, "label": "another-source.pdf"}
        moved = {**self.identity, "bounds": [70, 953, 261, 988]}
        for altered in (wrong, moved, None):
            with self.subTest(altered=altered):
                passed, adapter, saved = self.run_guard(
                    exact=False, first=self.alternate, second=None,
                    identities=[altered])
                self.assertFalse(passed)
                self.assertIsNone(adapter._physical_guard)
                self.assertEqual(len(saved), 6)

    def test_material_frame_and_second_frame_switch_fail_closed(self):
        passed, adapter, saved = self.run_guard(
            exact=False, first=self.third, second=None)
        self.assertFalse(passed)
        self.assertIsNone(adapter._physical_guard)
        self.assertEqual(len(saved), 7)
        passed, adapter, saved = self.run_guard(
            exact=False, first=self.alternate, second=self.observed)
        self.assertFalse(passed)
        self.assertIsNone(adapter._physical_guard)
        self.assertEqual(len(saved), 8)

    def test_task_frame_and_route_bindings_fail_closed(self):
        for action, route in (
            ({**self.action, "frame_id": "old-frame"}, None),
            ({**self.action, "task_id": "other-train"}, None),
            (self.action, "http://127.0.0.1:8069/odoo/action-430"),
        ):
            with self.subTest(action=action, route=route):
                passed, adapter, saved = self.run_guard(
                    exact=False, first=self.alternate, second=None,
                    action=action, route=route)
                self.assertFalse(passed)
                self.assertEqual(len(saved), 6)

    def test_same_visible_link_rule_covers_other_original_pdf_routes(self):
        for family in ("sales", "crm"):
            with self.subTest(family=family):
                route = f"http://127.0.0.1:8069/odoo/{family}/123"
                passed, adapter, _saved = self.run_guard(
                    exact=False, first=self.alternate,
                    second=self.alternate, route=route)
                self.assertTrue(passed)
                self.assertEqual(adapter._physical_guard["target_identity"]
                                 ["label"], self.label)

    def test_bad_source_label_is_rejected(self):
        page = Page([], [])
        with self.assertRaisesRegex(ValueError, "label must bind"):
            OdooV066TrainAttachmentRouteAdapterV1(
                page, task_id="ELPO-TRN-0001", task_binding_sha256="a" * 64,
                instruction="train-only",
                expected_attachment_label="ELPO-SEL-0001-source.pdf")


if __name__ == "__main__":
    unittest.main()
