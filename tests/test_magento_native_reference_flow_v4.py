"""Real browser exercises every current reference stage against pinned UI shape."""
import asyncio,time,unittest
from unittest.mock import AsyncMock,patch
from types import SimpleNamespace
from playwright.async_api import async_playwright
from magento_catalog_factory import native_reference_bulk_price_v4 as reference

class FlowTests(unittest.TestCase):
    def test_missing_native_target_does_not_repeat_85_waits(self):
        async def run():
            controller=SimpleNamespace(index=0,stage=4)
            with patch.object(reference,'_original_control_sample',new=AsyncMock(return_value={'type':'wait','duration_ms':250})), \
                patch.object(reference.time,'monotonic',side_effect=[10,41]):
                self.assertEqual((await reference.control_sample(controller,None))['type'],'wait')
                with self.assertRaisesRegex(ValueError,'not_ready_within_30'):
                    await reference.control_sample(controller,None)
        asyncio.run(run())

    def test_full_reference_checkbox_actions_price_form_save_and_readback(self):
        async def run():
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True)
                try:
                    page=await browser.new_page(viewport={'width':1440,'height':1000})
                    await page.set_content('''<table class="data-grid"><tbody><tr><td class="data-grid-checkbox-cell">
                     <label class="data-grid-checkbox-cell-inner"><input type="checkbox" id="idscheck814"><label for="idscheck814" style="display:inline-block;width:20px;height:20px">check</label></label></td>
                     <td>MP07-36-Purple</td><td id="price">$68.00</td></tr></tbody></table>
                     <div class="action-select-wrap"><button class="action-select" onclick="document.getElementById('update').hidden=false">Actions</button></div>
                     <button id="update" hidden onclick="document.getElementById('form').hidden=false">Update attributes</button>
                     <div id="form" hidden><input type="checkbox" id="toggle_price" name="toggle_price" onchange="document.getElementById('amount').disabled=!this.checked"><label for="toggle_price">Change price</label>
                     <input id="amount" disabled name="attributes[price]"><button onclick="document.getElementById('price').innerText='$'+document.getElementById('amount').value;document.getElementById('form').hidden=true">Save</button></div>''')
                    controller=SimpleNamespace(adapter=SimpleNamespace(page=page,actor=SimpleNamespace(deadline=time.monotonic()+60)),
                        index=0,edits=[{'sku':'MP07-36-Purple','target_price':'59.85'}],stage=3)
                    obs=SimpleNamespace(screenshot={'width':1440,'height':1000});seen=[]
                    for _ in range(16):
                        action=await reference.control_sample(controller,obs);seen.append(action['type'])
                        if action['type']=='finish':break
                        if action['type']=='click':await page.mouse.click(action['target']['x'],action['target']['y'])
                        elif action['type']=='type':await page.locator('input[name="attributes[price]"]').fill(action['text'])
                        elif action['type']=='wait':await page.wait_for_timeout(action['duration_ms'])
                        else:self.fail('Unexpected test flow action '+action['type'])
                    self.assertEqual(seen[-1],'finish');self.assertEqual(await page.locator('#price').inner_text(),'$59.85')
                    self.assertEqual(controller.index,1)
                finally:await browser.close()
        asyncio.run(run())

if __name__=='__main__':unittest.main()
