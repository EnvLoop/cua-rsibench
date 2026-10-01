import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from playwright.async_api import Error
from gitlab_world import v066_uniform_reference_controls_v18 as reference

PAINTED = {'bounds': [10, 20, 100, 30], 'tag': 'INPUT', 'role': 'combobox', 'type': 'text', 'documentReady': 'complete'}


class CurrentHydrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_visible_field_is_not_immediately_selected(self):
        handle = SimpleNamespace(evaluate=AsyncMock(side_effect=[PAINTED, None, PAINTED, PAINTED, PAINTED, PAINTED, PAINTED, PAINTED]))
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[handle]))
        await reference.wait_painted_reference(object(), locator, timeout_seconds=.3, poll_seconds=.005, stable_seconds=.015)
        self.assertGreaterEqual(handle.evaluate.await_count, 5)

    async def test_lost_context_is_only_resampled_before_native_io(self):
        handle = SimpleNamespace(evaluate=AsyncMock(return_value=PAINTED))
        locator = SimpleNamespace(element_handles=AsyncMock(side_effect=[Error('Execution context was destroyed'), [handle], [handle], [handle]]))
        await reference.wait_painted_reference(object(), locator, timeout_seconds=.2, poll_seconds=0, stable_seconds=0)
        self.assertEqual(locator.element_handles.await_count, 3)

    async def test_unstable_target_stops_under_total_deadline(self):
        handle = SimpleNamespace(evaluate=AsyncMock(return_value=None))
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[handle]))
        with self.assertRaisesRegex(ValueError, 'stable within30 seconds'):
            await reference.wait_painted_reference(object(), locator, timeout_seconds=.005, poll_seconds=.001)

    async def choose(self, model_visible):
        handle = SimpleNamespace(bounding_box=AsyncMock(return_value={'x': 10, 'y': 20, 'width': 100, 'height': 30}), get_attribute=AsyncMock(return_value='g69'))
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[handle]))
        controls = [SimpleNamespace(ref='g69', visible=True, enabled=True)] if model_visible else []
        observation = SimpleNamespace(controls=controls, frame_id='fresh')
        guard = SimpleNamespace(observe=AsyncMock(return_value=SimpleNamespace(observation=observation)), dispatch=AsyncMock(return_value={'status': 'applied', 'code': 'ok'}))
        def normalized(raw, *args, **kwargs):
            import json
            return json.loads(raw)
        with patch.object(reference, 'wait_painted_reference', AsyncMock()), patch.object(reference, 'normalize_model_action', normalized):
            await reference.Locator(locator, SimpleNamespace(page=object(), guard=guard)).fill('visible search')
        guard.dispatch.assert_awaited_once()
        return guard.dispatch.await_args.args[0]['target']

    async def test_only_model_visible_native_reference_is_used(self):
        self.assertEqual(await self.choose(True), {'ref': 'g69'})

    async def test_unlabelled_current_field_uses_physical_coordinates(self):
        self.assertEqual(await self.choose(False), {'x': 60, 'y': 35})


if __name__ == '__main__':
    unittest.main()
