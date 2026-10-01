"""Reference choice checks; no native benchmark or provider execution."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from gitlab_world.v066_uniform_train_qualification_v12 import wait_painted_reference


class PaintedReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_clipped_target_waits_for_actual_native_hit(self):
        page = SimpleNamespace(wait_for_timeout=AsyncMock())
        handle = SimpleNamespace(evaluate=AsyncMock(side_effect=[False, False, True]))
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[handle]))
        await wait_painted_reference(page, locator)
        self.assertEqual(handle.evaluate.await_count, 3)
        self.assertEqual(page.wait_for_timeout.await_count, 2)
        self.assertIn('elementFromPoint', handle.evaluate.await_args.args[0])

    async def test_duplicate_native_target_is_not_guessed(self):
        page = SimpleNamespace(wait_for_timeout=AsyncMock())
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[object(), object()]))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            await wait_painted_reference(page, locator)
        page.wait_for_timeout.assert_not_awaited()

    async def test_never_painted_native_target_stops_without_input(self):
        page = SimpleNamespace(wait_for_timeout=AsyncMock())
        handle = SimpleNamespace(evaluate=AsyncMock(return_value=False))
        locator = SimpleNamespace(element_handles=AsyncMock(return_value=[handle]))
        with self.assertRaisesRegex(ValueError, 'within30 seconds'):
            await wait_painted_reference(page, locator)
        self.assertEqual(page.wait_for_timeout.await_count, 300)
        self.assertFalse(hasattr(page, 'mouse'))


if __name__ == '__main__':
    unittest.main()
