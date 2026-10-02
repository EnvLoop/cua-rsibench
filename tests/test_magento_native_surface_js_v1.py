"""Actual production native getter against local synthetic Chromium DOM."""
import unittest
from playwright.async_api import async_playwright
from magento_catalog_factory.native_surface_guard_v1 import NATIVE_JS

class NativeDOMTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p=await async_playwright().start();self.browser=await self.p.chromium.launch(headless=True)
        self.page=await self.browser.new_page(viewport={'width':1440,'height':1000})
        await self.page.route('**/*',lambda r:r.fulfill(body='<html><body></body></html>',content_type='text/html'))
        await self.page.goto('http://127.0.0.1:7820/admin/catalog/product/index/')
        await self.page.set_content('''<style>body{margin:0}.admin-user{position:absolute;right:0;top:0}button{width:100px;height:40px}.modal-popup{position:absolute;left:0;top:0;background:white;width:300px;height:300px;z-index:2}</style>
        <div class="page-wrapper"><div class="page-header">Native fixture</div></div><div class="admin-user"><span class="admin-user-account-text">synthetic-admin</span><a href="/admin/auth/logout/">Logout</a></div>
        <button id="safe" style="position:absolute;left:20px;top:50px"><span>Save</span></button><input id="edit" style="position:absolute;left:20px;top:110px"><a id="external" href="https://outside.invalid">External</a>''')
    async def asyncTearDown(self):await self.browser.close();await self.p.stop()
    async def test_native_username_unique_and_account_controls_unsafe(self):
        value=await self.page.evaluate(NATIVE_JS,[])
        self.assertEqual(value['native_username'],'synthetic-admin')
        self.assertEqual(value['account_witness']['visible_count'],1)
        self.assertFalse(next(r for r in value['targets'] if r['label']=='Logout')['enabled'])
        self.assertFalse(next(r for r in value['targets'] if r['label']=='External')['enabled'])
    async def test_disabled_button_descendant_hit_cannot_bypass_current_target(self):
        await self.page.locator('#safe').evaluate('(e)=>e.disabled=true')
        value=await self.page.evaluate(NATIVE_JS,[{'x':50,'y':70}])
        self.assertFalse(value['hits'][0]['enabled']);self.assertFalse(next(r for r in value['targets'] if r['label']=='Save')['enabled'])
    async def test_topmost_modal_authority_and_background_raw_retained(self):
        await self.page.locator('body').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<div class="modal-popup _show"><button aria-disabled="true">Dialog disabled</button><button>Dialog safe</button></div>\')')
        value=await self.page.evaluate(NATIVE_JS,[])
        self.assertEqual({r['label'] for r in value['targets']},{'Dialog disabled','Dialog safe'})
        self.assertFalse(next(r for r in value['targets'] if r['label']=='Dialog disabled')['enabled'])
        self.assertTrue(any(r['label']=='Save' for r in value['outside_modal_targets']))
    async def test_native_busy_evidence_and_duplicate_account_witness(self):
        await self.page.locator('body').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<div aria-busy="true" style="width:20px;height:20px"></div><div class="admin-user"><span class="admin-user-account-text">other</span></div>\')')
        value=await self.page.evaluate(NATIVE_JS,[])
        self.assertTrue(value['busy']);self.assertEqual(value['native_username'],'');self.assertEqual(value['account_witness']['visible_count'],2)

if __name__=='__main__':unittest.main()
