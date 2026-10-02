"""Real nested Magento-like labels remain ambiguous except exact association."""
import asyncio
from types import SimpleNamespace
import time,unittest
from playwright.async_api import async_playwright
from magento_catalog_factory import native_reference_bulk_price_v3 as reference

class CheckboxReferenceTests(unittest.TestCase):
    def test_actual_nested_labels_select_only_native_associated_checkbox(self):
        async def run():
            async with async_playwright() as playwright:
                browser=await playwright.chromium.launch(headless=True)
                try:
                    page=await browser.new_page(viewport={'width':1440,'height':1000})
                    await page.set_content('''<table class="data-grid"><tbody><tr><td class="data-grid-checkbox-cell">
                      <label class="data-grid-checkbox-cell-inner"><input type="checkbox" id="idscheck814">
                      <label for="idscheck814" style="display:inline-block;width:20px;height:20px">check</label></label></td>
                      <td>MP07-36-Purple</td><td>$68.00</td></tr></tbody></table>''')
                    self.assertEqual(await page.locator('.data-grid-checkbox-cell label').count(),2)
                    controller=SimpleNamespace(adapter=SimpleNamespace(page=page,actor=SimpleNamespace(deadline=time.monotonic()+30)),
                        index=0,edits=[{'sku':'MP07-36-Purple','target_price':'59.85'}],stage=3)
                    observation=SimpleNamespace(screenshot={'width':1440,'height':1000})
                    action=await reference.control_sample(controller,observation)
                    self.assertEqual(action['type'],'click');self.assertEqual(controller.stage,4)
                    await page.mouse.click(action['target']['x'],action['target']['y'])
                    self.assertTrue(await page.locator('#idscheck814').is_checked())
                finally:await browser.close()
        asyncio.run(run())

if __name__=='__main__':unittest.main()
