"""Lost read contexts can be resampled before physical IO, under one deadline."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from playwright.async_api import Error
from gitlab_world.v066_uniform_reference_controls_v16 import Locator, wait_painted_reference


class CurrentReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_navigation_during_lookup_reads_current_target(self):
        handle = SimpleNamespace(evaluate=AsyncMock(return_value=True))
        locator = SimpleNamespace(element_handles=AsyncMock(side_effect=[
            Error('Execution context was destroyed, most likely because of a navigation'), [handle]]))
        await wait_painted_reference(object(), locator, poll_seconds=0)
        self.assertEqual(locator.element_handles.await_count, 2)
        handle.evaluate.assert_awaited_once()

    async def test_navigation_during_hit_test_discards_old_handle(self):
        old = SimpleNamespace(evaluate=AsyncMock(side_effect=Error('Cannot find context with specified id')))
        current = SimpleNamespace(evaluate=AsyncMock(return_value=True))
        locator = SimpleNamespace(element_handles=AsyncMock(side_effect=[[old], [current]]))
        await wait_painted_reference(object(), locator, poll_seconds=0)
        current.evaluate.assert_awaited_once()

    async def test_closed_browser_stays_terminal_without_input(self):
        locator = SimpleNamespace(element_handles=AsyncMock(side_effect=Error('Target page, context or browser has been closed')))
        guard = SimpleNamespace(observe=AsyncMock(), dispatch=AsyncMock())
        with self.assertRaisesRegex(Error, 'closed'):
            await Locator(locator, SimpleNamespace(page=object(), guard=guard)).click()
        guard.observe.assert_not_awaited()
        guard.dispatch.assert_not_awaited()
        self.assertEqual(locator.element_handles.await_count, 1)

    async def test_continuous_navigation_has_total_deadline(self):
        locator = SimpleNamespace(element_handles=AsyncMock(side_effect=Error('Execution context was destroyed')))
        with self.assertRaisesRegex(ValueError, 'within30 seconds'):
            await wait_painted_reference(object(), locator, timeout_seconds=.005, poll_seconds=.001)
        self.assertGreater(locator.element_handles.await_count, 1)

    async def test_hung_read_cannot_extend_deadline(self):
        import asyncio
        async def hung():
            await asyncio.sleep(1)
        locator = SimpleNamespace(element_handles=hung)
        with self.assertRaisesRegex(ValueError, 'within30 seconds'):
            await wait_painted_reference(object(), locator, timeout_seconds=.005)

    async def test_ambiguous_target_never_observes_or_dispatches(self):
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[object(), object()]))
        guard = SimpleNamespace(observe=AsyncMock(), dispatch=AsyncMock())
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            await Locator(locator, SimpleNamespace(page=object(), guard=guard)).click()
        guard.observe.assert_not_awaited()
        guard.dispatch.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
