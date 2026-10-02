"""No-provider GUI mapping tests for four proposed v0.6.6 train adapters."""

from __future__ import annotations

import asyncio
import io
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from enterprise_fallback.odoo18.odoo_v066_train_adapter import (
    OdooV066TrainAdapter, VIEWPORT,
)
from tools import excel_web_e2b_v066_train_adapter as excel
from tools import magento_v066_train_adapter as magento
from tools import office_web_e2b_v066_train_adapter as office


def image(color="white"):
    stream = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(stream, "PNG")
    return stream.getvalue()


def observation():
    return make_observation(task_id="train.synthetic",
                            task_binding_sha256="a" * 64,
                            instruction="Edit the visible train document.",
                            step=0, screenshot_bytes=image())


class FakeDesktop:
    def __init__(self):
        self.frame = image()
        self.calls = []

    def screenshot(self): return self.frame
    def move_mouse(self, x, y): self.calls.append(("move_mouse", x, y))
    def left_click(self): self.calls.append(("left_click",))
    def double_click(self): self.calls.append(("double_click",))
    def write(self, value): self.calls.append(("write", value))
    def press(self, key): self.calls.append(("press", key))


class FakeMouse:
    def __init__(self, calls): self.calls = calls
    def click(self, x, y): self.calls.append(("click", x, y))
    def dblclick(self, x, y): self.calls.append(("dblclick", x, y))
    def move(self, x, y): self.calls.append(("move", x, y))
    def wheel(self, dx, dy): self.calls.append(("wheel", dx, dy))
    def down(self): self.calls.append(("down",))
    def up(self): self.calls.append(("up",))


class FakeKeyboard:
    def __init__(self, calls): self.calls = calls
    def insert_text(self, value): self.calls.append(("insert_text", value))
    def press(self, value): self.calls.append(("press", value))


class FakeOdooPage:
    viewport_size = VIEWPORT
    url = "http://localhost:8069/odoo"

    def __init__(self):
        self.frame = image()
        self.calls = []
        self.mouse = FakeMouse(self.calls)
        self.keyboard = FakeKeyboard(self.calls)

    def evaluate(self, _script): return []
    def screenshot(self, *, type):
        assert type == "png"
        return self.frame
    def wait_for_timeout(self, duration): self.calls.append(("wait", duration))


class FakeAsyncMouse:
    def __init__(self, calls): self.calls = calls
    async def dblclick(self, x, y): self.calls.append(("dblclick", x, y))
    async def click(self, x, y): self.calls.append(("click", x, y))


class FakeAsyncKeyboard:
    def __init__(self, calls): self.calls = calls
    async def insert_text(self, value): self.calls.append(("insert_text", value))
    async def press(self, value): self.calls.append(("press", value))


class FakeMagentoPage:
    url = "http://localhost:7780/admin"

    def __init__(self):
        self.calls = []
        self.mouse = FakeAsyncMouse(self.calls)
        self.keyboard = FakeAsyncKeyboard(self.calls)
        self.frame = image()

    def locator(self, _selector): return object()
    async def screenshot(self, **_kwargs): return self.frame
    async def wait_for_load_state(self, _state, **_kwargs):
        self.calls.append(("networkidle",))


class OfficeExcelV066Tests(unittest.TestCase):
    def test_ppt_and_excel_have_same_proposed_gui_semantics(self):
        for adapter in (office, excel):
            with self.subTest(adapter=adapter.__name__):
                sandbox, frame = FakeDesktop(), observation()
                for raw in (
                    {"type": "double_click", "target": {"x": 0, "y": 0}},
                    {"type": "type", "text": "literal", "mode": "insert"},
                    {"type": "key", "key": "Control+End"},
                ):
                    action = adapter.parse_current_action(
                        json.dumps(raw), frame, sandbox)
                    adapter.dispatch_current_action(sandbox, action, frame)
                self.assertEqual(sandbox.calls, [
                    ("move_mouse", 0, 0), ("double_click",),
                    ("write", "literal"), ("press", ["ctrl", "end"]),
                ])
                self.assertEqual(json.loads(adapter.render_for_model(frame)[
                    "instruction"])["output_version"],
                    "scale-action-output-v0.6.6")

    def test_stale_and_unsupported_actions_do_not_dispatch(self):
        sandbox, frame = FakeDesktop(), observation()
        for raw in (
            {"type": "type", "text": "danger", "mode": "fill"},
            {"type": "key", "key": "Control+P"},
            {"type": "double_click", "target": {"ref": "invented"}},
        ):
            with self.assertRaises(ContractError):
                office.parse_current_action(json.dumps(raw), frame, sandbox)
        sandbox.frame = image("black")
        with self.assertRaisesRegex(ContractError, "stale_frame"):
            office.parse_current_action('{"type":"finish"}', frame, sandbox)
        self.assertEqual(sandbox.calls, [])


class OdooV066Tests(unittest.TestCase):
    def test_new_actions_dispatch_on_exact_frame_and_focused_insert_has_no_click(self):
        page = FakeOdooPage()
        adapter = OdooV066TrainAdapter(page, task_id="train.synthetic",
            task_binding_sha256="a" * 64,
            instruction="Edit the visible training page.")
        for raw in (
            {"type": "double_click", "target": {"x": 5, "y": 6}},
            {"type": "type", "text": "literal", "mode": "insert"},
            {"type": "key", "key": "Control+F"},
        ):
            frame, rendered = adapter.observe_for_model()
            self.assertEqual(json.loads(rendered["instruction"])[
                "output_version"], "scale-action-output-v0.6.6")
            full = adapter.parse_current_action(json.dumps(raw))
            receipt = adapter.dispatch(full)
            self.assertEqual(receipt["public_contract_receipt"][
                "action_profile"], "scale-action-profile-v0.6.6")
        self.assertEqual([row for row in page.calls if row[0] != "wait"], [
            ("dblclick", 5, 6), ("insert_text", "literal"),
            ("press", "Control+F"),
        ])
        with self.assertRaisesRegex(ContractError, "stale_frame"):
            adapter.dispatch(full)

    def test_changed_pixels_prevent_dispatch(self):
        page = FakeOdooPage()
        adapter = OdooV066TrainAdapter(page, task_id="train.synthetic",
            task_binding_sha256="a" * 64, instruction="Train task.")
        frame, _ = adapter.observe_for_model()
        full = adapter.parse_current_action(
            '{"type":"double_click","target":{"x":1,"y":1}}')
        page.frame = image("black")
        with self.assertRaisesRegex(ContractError, "stale_frame"):
            adapter.dispatch(full)
        self.assertEqual([row for row in page.calls if row[0] != "wait"], [])


class MagentoV066Tests(unittest.TestCase):
    def test_train_only_new_gui_paths_recheck_current_pixels(self):
        async def exercise():
            page, frame = FakeMagentoPage(), observation()
            for raw in (
                {"type": "double_click", "target": {"x": 5, "y": 6}},
                {"type": "type", "text": "literal", "mode": "insert"},
                {"type": "key", "key": "Shift+End"},
            ):
                action = await magento.parse_current_action(
                    json.dumps(raw), frame, page, page.url)
                result = await magento.dispatch_current_action(
                    page, action, frame, {}, page.url)
                self.assertEqual(result, {"status": "applied", "code": "ok"})
            self.assertEqual(page.calls, [
                ("dblclick", 5, 6), ("networkidle",),
                ("insert_text", "literal"), ("networkidle",),
                ("press", "Shift+End"), ("networkidle",),
            ])
            page.frame = image("black")
            with self.assertRaisesRegex(ContractError, "stale_frame"):
                await magento.parse_current_action(
                    '{"type":"finish"}', frame, page, page.url)
        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
