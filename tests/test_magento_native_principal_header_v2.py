"""Actual Chromium: rendered header survives scroll, target clipping does not."""
import asyncio
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
from types import SimpleNamespace
import unittest
from playwright.async_api import async_playwright
from magento_catalog_factory import native_principal_header_v2 as principal
from magento_catalog_factory.native_surface_adapter_v2 import NATIVE_JS as old_js
from magento_catalog_factory.native_surface_lease_v2 import LeaseBoundary

HTML='''<html><body style="margin:0"><div class="page-wrapper"><header class="page-header"><div class="admin-user"><span class="admin-user-account-text">admin</span></div></header>
 <button id="above" style="height:30px">Above target</button><div style="height:1800px"></div>
 <button id="below" style="height:30px">Below target</button></div></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        raw=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

class PrincipalTests(unittest.TestCase):
    def test_real_scroll_current_document_hidden_duplicates_and_original_scope_conditions(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        async def run():
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True)
                try:
                    page=await browser.new_page(viewport={'width':1440,'height':1000})
                    origin=f'http://127.0.0.1:{server.server_port}'
                    await page.goto(origin+'/admin/catalog/product_action_attribute/edit/')
                    boundary=object.__new__(LeaseBoundary);boundary.page=page;boundary.origin=origin;boundary.username='admin'
                    boundary.lease={'window_sha256':'owned-window'};boundary.operation=SimpleNamespace(active=lambda:True)
                    async def metadata():
                        value=await page.evaluate(principal.NATIVE_JS,[]);value['native_window_sha256']='owned-window';return value
                    before=await metadata();self.assertTrue(await boundary.owns(page,before));self.assertTrue(before['account_witness']['in_viewport'])
                    await page.evaluate('scrollTo(0,1500)')
                    old=await page.evaluate(old_js,[]);current=await metadata()
                    self.assertEqual(old['account_witness']['visible_count'],0)
                    self.assertTrue(principal.valid_witness(current,'admin'));self.assertTrue(await boundary.owns(page,current))
                    self.assertFalse(current['account_witness']['in_viewport']);self.assertLess(current['account_witness']['header_bounds'][1],0)
                    self.assertNotIn('Above target',[row['label'] for row in current['targets']])
                    self.assertIn('Below target',[row['label'] for row in current['targets']])
                    for change in ["document.querySelector('.admin-user').style.display='none'",
                        "document.querySelector('.admin-user').style.visibility='hidden'",
                        "document.querySelector('.admin-user').style.visibility='collapse'",
                        "document.querySelector('.admin-user').style.contentVisibility='hidden'",
                        "document.querySelector('.admin-user').style.opacity='0'",
                        "document.querySelector('.admin-user').hidden=true",
                        "document.querySelector('.admin-user').setAttribute('inert','')",
                        "document.querySelector('.admin-user').setAttribute('aria-hidden','true')",
                        "document.querySelector('.admin-user-account-text').style.cssText='display:inline-block;width:0;height:0;overflow:hidden'",
                        "document.querySelector('.admin-user-account-text').remove()",
                        "document.querySelector('.admin-user').appendChild(document.querySelector('.admin-user-account-text').cloneNode(true))",
                        "const d=document.querySelector('.admin-user-account-text').cloneNode(true);d.hidden=true;document.querySelector('.admin-user').appendChild(d)",
                        "document.querySelector('.admin-user-account-text').textContent='other-account'"]:
                        await page.goto(origin+'/admin/catalog/product_action_attribute/edit/');await page.evaluate(change)
                        value=await metadata();self.assertFalse(await boundary.owns(page,value),change)
                    await page.goto(origin+'/admin/catalog/product_action_attribute/edit/');value=await metadata()
                    for key,replacement in [('physical_url','https://foreign.example/admin'),('physical_url',origin+'/admin/auth/logout/'),
                        ('physical_url',origin+'/admin/system_account/edit/'),('top_window',False),('visible',False),('app_shell',False),
                        ('native_window_sha256','foreign-window')]:
                        self.assertFalse(await boundary.owns(page,{**value,key:replacement}),key)
                    self.assertFalse(await boundary.owns(object(),value))
                    boundary.operation=SimpleNamespace(active=lambda:False);self.assertFalse(await boundary.owns(page,value))
                finally:await browser.close()
        asyncio.run(run())

    def test_original_target_hit_focus_and_unsafe_predicates_are_byte_preserved(self):
        for start,end in [(' const visible=', ' const bounds='),(' const bounds=', ' const keyboard='),
            (' const unsafe=', ' const enabled='),(' const nodes=', ' const accountNodes='),
            (' const focus=', ' const hits='),(' const hits=', ' const busy=')]:
            original_end=' const account=' if end==' const accountNodes=' else end
            old=old_js[old_js.index(start):old_js.index(original_end)]
            new=principal.NATIVE_JS[principal.NATIVE_JS.index(start):principal.NATIVE_JS.index(end)]
            self.assertEqual(old,new)

if __name__=='__main__':unittest.main()
