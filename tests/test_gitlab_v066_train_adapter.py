"""Synthetic/fake-provider checks for proposed GitLab v0.6.6 GUI mapping."""

from __future__ import annotations

from dataclasses import replace
import io
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image

from cursibench import shared_action_bundle_v066
from cursibench.scale_action_contract import ContractError, make_observation
from gitlab_world import vision_actor_v066_train as candidate
from gitlab_world import vision_actor as historical


def png(color: str = "white") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (128, 96), color).save(output, "PNG")
    return output.getvalue()


class FakeProvider:
    def __init__(self, response: dict):
        self.response = response
        self.calls = 0

    def sample(self, request: dict) -> str:
        self.calls += 1
        assert request["image_bytes"] == png()
        return "```json\n" + json.dumps(self.response) + "\n```"


class FakeHandle:
    def __init__(self, events: list):
        self.events = events

    async def evaluate(self, _script, candidate):
        return self is candidate

    async def dblclick(self, **_kwargs):
        self.events.append(("ref_dblclick",))

    async def click(self, **_kwargs):
        self.events.append(("ref_click",))

    async def focus(self):
        self.events.append(("ref_focus",))


class FakeMouse:
    def __init__(self, events: list):
        self.events = events

    async def click(self, x, y):
        self.events.append(("click", x, y))

    async def dblclick(self, x, y):
        self.events.append(("dblclick", x, y))


class FakeKeyboard:
    def __init__(self, events: list):
        self.events = events

    async def insert_text(self, value):
        self.events.append(("insert_text", value))

    async def press(self, value):
        self.events.append(("press", value))


class FakePage:
    def __init__(self):
        self.url = "http://127.0.0.1:8014/train/project"
        self.events = []
        self.mouse = FakeMouse(self.events)
        self.keyboard = FakeKeyboard(self.events)
        self.frame = png()
        self.next_frame = None
        self.screenshots = 0

    def locator(self, _selector):
        return object()

    async def screenshot(self, **_kwargs):
        self.screenshots += 1
        if self.next_frame is not None and self.screenshots > 1:
            return self.next_frame
        return self.frame


def frame(*, handle: FakeHandle | None = None) -> candidate.Frame:
    controls = ([{"ref": "c001", "role": "button", "label": "Edit",
                  "visible": True, "enabled": True}] if handle else [])
    observation = make_observation(
        task_id="train.synthetic", task_binding_sha256="a" * 64,
        instruction="Edit the visible train page.", step=0,
        screenshot_bytes=png(), controls=controls,
    )
    handles = {"c001": handle} if handle else {}
    return candidate.Frame(observation, handles,
                           "http://127.0.0.1:8014/train/project")


class GitLabV066TrainAdapterTests(unittest.IsolatedAsyncioTestCase):
    def test_shared_source_binding_and_candidate_request(self):
        stack = candidate.assert_shared_stack()
        self.assertEqual(stack["proposed_v066_bundle_sha256"],
                         candidate.PROPOSED_SHARED_BUNDLE_SHA256)
        self.assertTrue(candidate.TRAIN_ONLY)
        self.assertIs(candidate.capture, historical.capture)
        self.assertIs(candidate.install_local_guard,
                      historical.install_local_guard)
        request = candidate.model_request(frame(), task_partition="train")
        self.assertEqual(request["image_bytes"], png())
        self.assertEqual(json.loads(request["instruction"])["output_version"],
                         "scale-action-output-v0.6.6")

    async def test_changed_shared_bundle_refuses_dispatch(self):
        page, observed = FakePage(), frame()
        actual = shared_action_bundle_v066.build(
            Path(candidate.__file__).resolve().parents[1])
        changed = {**actual, "bundle_sha256": "0" * 64}
        with patch.object(shared_action_bundle_v066, "build",
                          return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "source changed"):
                await candidate.validate_and_dispatch(
                    page, '{"type":"click","target":{"x":1,"y":1}}',
                    observed, task_partition="train")
        self.assertEqual(page.events, [])

    async def test_fake_provider_dispatches_new_gui_primitives_with_safe_receipts(self):
        page, observed = FakePage(), frame()
        responses = [
            {"type": "double_click", "target": {"x": 12, "y": 14}},
            {"type": "type", "text": "synthetic-private-value",
             "mode": "insert"},
            {"type": "key", "key": "Control+End"},
        ]
        for response in responses:
            provider = FakeProvider(response)
            raw = provider.sample(candidate.model_request(
                observed, task_partition="train"))
            result, receipt = await candidate.validate_and_dispatch(
                page, raw, observed, task_partition="train")
            self.assertEqual(provider.calls, 1)
            self.assertEqual(result, {"status": "applied", "code": "ok"})
            self.assertEqual(receipt["action_profile"],
                             "scale-action-profile-v0.6.6")
            self.assertEqual(receipt["action_type"], response["type"])
            self.assertNotIn("synthetic-private-value", json.dumps(receipt))
        self.assertEqual(page.events, [
            ("dblclick", 12, 14),
            ("insert_text", "synthetic-private-value"),
            ("press", "Control+End"),
        ])
        self.assertEqual(page.screenshots, 6)

    async def test_historical_click_uses_same_current_frame_and_v066_receipt(self):
        page, observed = FakePage(), frame()
        result, receipt = await candidate.validate_and_dispatch(
            page, '{"type":"click","target":{"x":7,"y":8}}', observed,
            task_partition="train")
        self.assertEqual(result["status"], "applied")
        self.assertEqual(receipt["action_profile"],
                         "scale-action-profile-v0.6.6")
        self.assertEqual(page.events, [("click", 7, 8)])

    async def test_same_ref_identity_allows_double_click(self):
        page = FakePage()
        handle = FakeHandle(page.events)
        observed = frame(handle=handle)
        descriptor = {"ref": "c001", "role": "button", "label": "Edit",
                      "visible": True, "enabled": True}
        with patch.object(historical, "visible_controls",
                          new=AsyncMock(return_value=([descriptor],
                                                      {"c001": handle}))):
            _, receipt = await candidate.validate_and_dispatch(
                page, '{"type":"double_click","target":{"ref":"c001"}}',
                observed, task_partition="train")
        self.assertEqual(page.events, [("ref_dblclick",)])
        self.assertEqual(receipt["action_type"], "double_click")

    async def test_ref_replacement_and_mid_check_pixel_change_fail_closed(self):
        page = FakePage()
        original = FakeHandle(page.events)
        observed = frame(handle=original)
        descriptor = {"ref": "c001", "role": "button", "label": "Edit",
                      "visible": True, "enabled": True}
        raw = '{"type":"double_click","target":{"ref":"c001"}}'
        with patch.object(historical, "visible_controls",
                          new=AsyncMock(return_value=([descriptor],
                                                      {"c001": FakeHandle(page.events)}))):
            with self.assertRaisesRegex(ContractError, "stale_frame"):
                await candidate.validate_and_dispatch(
                    page, raw, observed, task_partition="train")
        self.assertEqual(page.events, [])
        page.screenshots = 0
        page.next_frame = png("black")
        with patch.object(historical, "visible_controls",
                          new=AsyncMock(return_value=([descriptor],
                                                      {"c001": original}))):
            with self.assertRaisesRegex(ContractError, "stale_frame"):
                await candidate.validate_and_dispatch(
                    page, raw, observed, task_partition="train")
        self.assertEqual(page.events, [])

    async def test_stale_origin_expiry_and_unsupported_actions_never_dispatch(self):
        page, observed = FakePage(), frame()
        invalid = (
            '{"type":"shell","cmd":"whoami"}',
            '{"type":"click","target":{"x":1,"y":1},"url":"http://evil"}',
            '{"type":"key","key":"Control+P"}',
            '{"type":"type","mode":"fill","text":"bad"}',
        )
        for raw in invalid:
            with self.subTest(raw=raw):
                with self.assertRaises(ContractError):
                    await candidate.validate_and_dispatch(
                        page, raw, observed, task_partition="train")
        page.url = "https://gitlab.com/train/project"
        with self.assertRaisesRegex(ContractError, "stale_frame"):
            await candidate.validate_and_dispatch(
                page, '{"type":"wait","duration_ms":10}', observed,
                task_partition="train")
        expired = replace(observed.observation, issued_at=0.0,
                          expires_at=1.0)
        with self.assertRaisesRegex(ContractError, "expired_frame"):
            await candidate.validate_and_dispatch(
                FakePage(), '{"type":"wait","duration_ms":10}',
                replace(observed, observation=expired),
                task_partition="train")
        self.assertEqual(page.events, [])

    async def test_nontrain_partition_rejects_request_and_dispatch(self):
        page, observed = FakePage(), frame()
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            candidate.model_request(observed,
                                    task_partition="final_candidate_unsealed")
        with self.assertRaisesRegex(ContractError, "invalid_action"):
            await candidate.validate_and_dispatch(
                page, '{"type":"click","target":{"x":1,"y":1}}',
                observed, task_partition="final_candidate_unsealed")
        self.assertEqual(page.events, [])


if __name__ == "__main__":
    unittest.main()
