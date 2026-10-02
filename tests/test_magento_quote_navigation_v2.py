"""Actual browser navigation regression; no Magento/model/network account."""
import asyncio
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
from playwright.async_api import async_playwright,TimeoutError as PlaywrightTimeout
from tools import qualify_magento_original_catalog_v1 as old_quote
from magento_catalog_factory import native_quote_navigation_v2 as fixed
from magento_catalog_factory import native_surface_workers_v1 as old_workers,native_surface_workers_v2 as workers
from magento_catalog_factory import native_queue_runtime_v2 as old_queue,native_queue_runtime_v3 as queue
from magento_catalog_factory import native_surface_facade_v1 as old_facade,native_surface_facade_v2 as facade

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/edit':
            self.server.editor_requests+=1;time.sleep(.6)
            html='<h1 class="page-title">Synthetic local quote</h1><button>Edit with Page Builder</button><div>Observed exact test quote</div>'
        elif self.path=='/pages':
            html='''<h1>Pages</h1><input id="fulltext"><table class="data-grid"><tbody><tr><td>Synthetic local quote
            <button class="action-select" onclick="document.getElementById('edit').hidden=false">Actions</button>
            <a hidden id="edit" href="/edit">Edit</a></td></tr></tbody></table>'''
        else:
            html='''<div id="menu-magento-backend-content"><a href="#">Content</a></div>
            <div data-ui-id="menu-magento-cms-cms-page"><a href="/pages">Pages</a></div>'''
        data=html.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass

class QuoteNavigationTests(unittest.TestCase):
    def test_editor_heading_settles_after_single_click_without_replaying_navigation(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.editor_requests=0
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as temp:
            case={'quote_page_title':'Synthetic local quote','quote_page_body':'Observed exact test quote',
                'quote_page_body_sha256':sha256(b'Observed exact test quote').hexdigest()}
            async def exercise():
                async with async_playwright() as playwright:
                    browser=await playwright.chromium.launch(headless=True)
                    try:
                        page=await browser.new_page();page.set_default_timeout(250)
                        await page.goto(f'http://127.0.0.1:{server.server_port}/')
                        with self.assertRaises(PlaywrightTimeout):
                            await old_quote.read_quote_in_gui(page,case,Path(temp))
                        await page.close()
                        before=server.editor_requests
                        page=await browser.new_page();page.set_default_timeout(250)
                        await page.goto(f'http://127.0.0.1:{server.server_port}/')
                        result=await fixed.read_quote_in_gui(page,case,Path(temp))
                        self.assertTrue(result['quote_visible_in_native_cms'])
                        self.assertEqual(result['quote_body_sha256'],case['quote_page_body_sha256'])
                        self.assertEqual(server.editor_requests-before,1)
                        self.assertTrue((Path(temp)/'private-quote-page.png').is_file())
                    finally:await browser.close()
            asyncio.run(exercise())

    def test_old_globals_policy_scorer_reset_and_queue_stay_unchanged(self):
        old=old_workers.public_binding();new=workers.public_binding()
        self.assertEqual(old['binding_sha256'],'c6dddc008803c1552108dd493bed755e6383d749560c15185e908299454466f2')
        self.assertFalse(new['actor_sampler_scorer_reset_changed'])
        for key in ['policy_sha256','max_actions','actor_seconds','owned_lifecycle_seconds']:
            self.assertEqual(new[key],old[key])
        self.assertIs(queue._impl.original_run_task,old_queue.original_run_task)
        self.assertIs(facade.ReferenceSampler,old_facade.ReferenceSampler)
        self.assertIsNot(fixed.read_quote_in_gui,old_quote.read_quote_in_gui)
        self.assertIs(fixed.dedicated_open.__wrapped__.__globals__['CommandJournal'],fixed.actor.NativeCommandJournal)
        self.assertIs(fixed.dedicated.DedicatedMagentoTrainRuntime.open_case.__wrapped__.__globals__['original_gui'],old_quote)
        mro=queue.Runtime.__mro__
        self.assertLess(mro.index(queue._impl.Runtime),mro.index(fixed.Runtime))
        self.assertIn('magento_catalog_factory/native_quote_navigation_v2.py',new['source_sha256s'])

if __name__=='__main__':unittest.main()
