"""Current production getter sees the native grid overlay, including physical hit blocking."""
from tests.test_magento_native_surface_js_v1 import NativeDOMTests
from magento_catalog_factory.native_surface_adapter_v2 import NATIVE_JS


class GridLoadingTests(NativeDOMTests):
    async def test_real_grid_mask_is_busy_and_obscures_input_until_removed(self):
        await self.page.locator('body').evaluate('''e=>e.insertAdjacentHTML('beforeend',
            '<div class="admin__data-grid-loading-mask" style="position:fixed;inset:0;z-index:99;background:#ffffff80">Loading</div>')''')
        value = await self.page.evaluate(NATIVE_JS, [{'x': 25, 'y': 120}])
        self.assertEqual(value['busy'][0]['class_name'], 'admin__data-grid-loading-mask')
        self.assertTrue(next(row for row in value['targets'] if row['role'] == 'input')['obscured'])
        self.assertFalse(value['hits'][0]['keyboard'])
        await self.page.locator('.admin__data-grid-loading-mask').evaluate('e=>e.remove()')
        ready = await self.page.evaluate(NATIVE_JS, [{'x': 25, 'y': 120}])
        self.assertFalse(ready['busy'])
        self.assertFalse(next(row for row in ready['targets'] if row['role'] == 'input')['obscured'])
        self.assertTrue(ready['hits'][0]['keyboard'])
