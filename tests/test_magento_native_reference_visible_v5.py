"""A hidden sticky clone is excluded; two visible controls remain ambiguous."""
import asyncio,time,unittest
from types import SimpleNamespace
from playwright.async_api import async_playwright
from magento_catalog_factory import native_reference_bulk_price_v5 as reference

class VisibleReferenceTests(unittest.TestCase):
 def test_native_toolbar_visibility_and_ambiguity(self):
  async def run():
   async with async_playwright() as p:
    browser=await p.chromium.launch(headless=True)
    try:
     page=await browser.new_page(viewport={'width':1440,'height':1000})
     await page.set_content('<div class="action-select-wrap"><button class="action-select">Actions</button></div><div id="sticky" class="action-select-wrap" style="display:none"><button class="action-select">Actions</button></div>')
     controller=SimpleNamespace(adapter=SimpleNamespace(page=page,actor=SimpleNamespace(deadline=time.monotonic()+30)),index=0,edits=[{'sku':'MP07-36-Purple','target_price':'59.85'}],stage=4)
     observation=SimpleNamespace(screenshot={'width':1440,'height':1000})
     self.assertEqual(await page.locator('.action-select').count(),2)
     action=await reference.control_sample(controller,observation)
     self.assertEqual(action['type'],'click');self.assertEqual(controller.stage,5)
     await page.locator('#sticky').evaluate("node=>node.style.display='block'")
     controller.stage=4
     with self.assertRaisesRegex(ValueError,'reference_bulk_target_ambiguous'):
      await reference.control_sample(controller,observation)
    finally:await browser.close()
  asyncio.run(run())

if __name__=='__main__':unittest.main()
