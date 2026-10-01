import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from playwright.async_api import Error
from magento_catalog_factory.native_surface_adapter_v2 import NativeAdapter, OriginalNativeAdapter


class NavigationReadTests(unittest.IsolatedAsyncioTestCase):
    def actor(self, observing):
        value = object.__new__(NativeAdapter)
        value._observing_native = observing
        value.clock = time.monotonic
        value.actor = SimpleNamespace(deadline=time.monotonic()+2, check=Mock())
        value.store = SimpleNamespace(json=Mock())
        value.step = 2
        return value

    async def test_lost_read_context_before_observation_is_reopened_once(self):
        value = self.actor(True)
        metadata = {'native': 'actual-current'}
        reader = AsyncMock(side_effect=[Error('Execution context was destroyed'), metadata])
        with patch('magento_catalog_factory.native_surface_adapter_v2._meta_current', reader):
            self.assertEqual(await value.meta(), metadata)
        self.assertEqual(reader.await_count, 2)
        proof = value.store.json.call_args.args[1]
        self.assertFalse(proof['native_io_replayed'])
        self.assertFalse(proof['gui_driver_called'])

    async def test_predispatch_or_keyboard_scope_error_is_never_replayed(self):
        value = self.actor(False)
        reader = AsyncMock(side_effect=Error('Execution context was destroyed'))
        with patch('magento_catalog_factory.native_surface_adapter_v2._meta_current', reader):
            with self.assertRaises(Error):
                await value.meta()
        reader.assert_awaited_once()
        value.store.json.assert_not_called()

    async def test_closed_browser_remains_terminal(self):
        value = self.actor(True)
        reader = AsyncMock(side_effect=Error('Target page, context or browser has been closed'))
        with patch('magento_catalog_factory.native_surface_adapter_v2._meta_current', reader):
            with self.assertRaises(Error):
                await value.meta()
        reader.assert_awaited_once()
        value.store.json.assert_not_called()


if __name__ == '__main__':
    unittest.main()
