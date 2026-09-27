"""GitLab adapter uses the shared Qwen3.8 screenshot/action validator."""

import io
import importlib.util
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from gitlab_world import vision_actor


HAS_V064 = importlib.util.find_spec("cursibench.scale_action_output_v064") is not None


def png():
    output = io.BytesIO()
    Image.new("RGB", (128, 96), (255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


class FakeMouse:
    def __init__(self):
        self.clicks = []

    async def click(self, x, y):
        self.clicks.append((x, y))


class FakePage:
    def __init__(self, screenshot):
        self.url = "http://127.0.0.1:8014/bench-evaluation/project"
        self._screenshot = screenshot
        self.mouse = FakeMouse()

    def locator(self, selector):
        return selector

    async def screenshot(self, **kwargs):
        return self._screenshot


class FakeRoute:
    def __init__(self, url):
        self.request = type("Request", (), {"url": url})()
        self.disposition = None

    async def continue_(self):
        self.disposition = "continued"

    async def abort(self):
        self.disposition = "aborted"


class FakeContext:
    async def route(self, pattern, handler):
        self.pattern = pattern
        self.handler = handler


class GitLabVisionActorTests(unittest.IsolatedAsyncioTestCase):
    def frame(self):
        image = png()
        obs = make_observation(task_id="train-task-1",
                               task_binding_sha256="a" * 64,
                               instruction="Inspect the GitLab project.",
                               step=0, screenshot_bytes=image,
                               controls=[], memory="")
        return vision_actor.Frame(obs, {},
                                  "http://127.0.0.1:8014/bench-evaluation/project")

    @unittest.skipUnless(HAS_V064, "shared v0.6.4 output module not in this older checkout")
    def test_model_request_contains_same_png_and_shared_v064_contract(self):
        frame = self.frame()
        request = vision_actor.model_request(frame)
        self.assertEqual(request["image_bytes"], frame.observation.screenshot_bytes)
        self.assertIn("scale-action-output-v0.6.4", request["instruction"])
        self.assertNotIn("localhost", request["instruction"])

    @unittest.skipUnless(HAS_V064, "shared v0.6.4 output module not in this older checkout")
    async def test_valid_coordinate_click_dispatches_only_current_gui_frame(self):
        frame = self.frame()
        page = FakePage(frame.observation.screenshot_bytes)
        result, receipt = await vision_actor.validate_and_dispatch(
            page, json.dumps({"type": "click", "target": {"x": 20, "y": 30}}), frame)
        self.assertEqual(page.mouse.clicks, [(20, 30)])
        self.assertEqual(result, {"status": "applied", "code": "ok"})
        self.assertEqual(receipt["action_type"], "click")
        self.assertNotIn("instruction", receipt)

    @unittest.skipUnless(HAS_V064, "shared v0.6.4 output module not in this older checkout")
    async def test_stale_pixels_and_non_gui_output_fail_without_dispatch(self):
        frame = self.frame()
        page = FakePage(png())
        page._screenshot = page._screenshot[:-20] + b"different-pixels"
        with self.assertRaisesRegex(ContractError, "stale_frame"):
            await vision_actor.validate_and_dispatch(
                page, '{"type":"click","target":{"x":1,"y":1}}', frame)
        self.assertEqual(page.mouse.clicks, [])
        page._screenshot = frame.observation.screenshot_bytes
        with self.assertRaises(ContractError):
            await vision_actor.validate_and_dispatch(
                page, '{"type":"shell","cmd":"whoami"}', frame)
        self.assertEqual(page.mouse.clicks, [])

    @unittest.skipUnless(HAS_V064, "shared v0.6.4 output module not in this older checkout")
    async def test_one_unlabeled_fence_uses_shared_v064_minimal_action_path(self):
        frame = self.frame()
        page = FakePage(frame.observation.screenshot_bytes)
        result, receipt = await vision_actor.validate_and_dispatch(
            page, '```\n{"type":"click","target":{"x":10,"y":11}}\n```', frame)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(page.mouse.clicks, [(10, 11)])
        self.assertEqual(receipt["action_type"], "click")

    def test_local_origin_rejects_external_and_credentialed_urls(self):
        self.assertTrue(vision_actor.local_origin("http://127.0.0.1:8014/project"))
        self.assertFalse(vision_actor.local_origin("http://127.0.0.1:8012/project"))
        self.assertFalse(vision_actor.local_origin("https://gitlab.com/project"))
        self.assertFalse(vision_actor.local_origin("http://a:b@127.0.0.1:8014/project"))

    async def test_model_session_guard_blocks_external_requests(self):
        context = FakeContext()
        blocked = await vision_actor.install_local_guard(context)
        local = FakeRoute("http://127.0.0.1:8014/project")
        remote = FakeRoute("https://gitlab.com/project")
        await context.handler(local)
        await context.handler(remote)
        self.assertEqual((local.disposition, remote.disposition),
                         ("continued", "aborted"))
        self.assertEqual(blocked, ["gitlab.com"])


if __name__ == "__main__":
    unittest.main()
