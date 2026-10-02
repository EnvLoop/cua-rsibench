"""Synthetic browser checks for the train-only PDF viewer identity read."""

from __future__ import annotations

import unittest

from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v3 import (
    VIEWER_LOOKUP_JS,
)


LABEL = "ELPO-TRN-0001-source.pdf"
URL = "http://example.test/odoo/purchase/123"
HTML = """<html><body style="margin:0">
<div style="position:fixed;top:0;left:0;width:100%;height:46px;background:#333">
  <span id="viewer-title" style="position:absolute;left:24px;top:12px;color:white">
    ELPO-TRN-0001-source.pdf</span>
  <button id="viewer-close" title="Close (Esc)"
    style="position:absolute;right:10px;top:4px;width:34px;height:36px">x</button>
</div>
<iframe class="o-FileViewer-view" style="position:fixed;left:180px;top:53px;
  width:1080px;height:897px" srcdoc="<p>PDF</p>"></iframe>
</body></html>"""


class ViewerDomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as error:
            raise unittest.SkipTest(f"local Chromium unavailable: {error}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1440,
                                                    "height": 1000})
        self.page.route(URL, lambda route: route.fulfill(
            status=200, content_type="text/html", body=HTML))
        self.page.goto(URL)

    def tearDown(self):
        self.page.close()

    def lookup(self, target=None):
        return self.page.evaluate(
            VIEWER_LOOKUP_JS, {"label": LABEL, "target": target})

    def test_unique_top_bar_title_iframe_and_close_hit(self):
        observed = self.lookup()
        self.assertIsNotNone(observed)
        self.assertEqual(observed["source_label"], LABEL)
        self.assertTrue(self.lookup({"x": 1413, "y": 23})["target_inside"])
        self.assertFalse(self.lookup({"x": 1300, "y": 23})["target_inside"])

    def test_wrong_title_missing_viewer_and_ambiguous_close_fail(self):
        self.page.evaluate("document.querySelector('#viewer-title').textContent = 'other.pdf'")
        self.assertIsNone(self.lookup())
        self.page.evaluate(
            "document.querySelector('#viewer-title').textContent = "
            "'ELPO-TRN-0001-source.pdf'")
        self.page.locator("iframe.o-FileViewer-view").evaluate(
            "element => element.remove()")
        self.assertIsNone(self.lookup())
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', "
                           "`<iframe class='o-FileViewer-view' "
                           "style='position:fixed;left:180px;top:53px;"
                           "width:1080px;height:897px'></iframe>`)")
        self.page.evaluate("document.querySelector('#viewer-close')"
                           ".insertAdjacentHTML('afterend', "
                           "`<button title='Close (Esc)' "
                           "style='position:fixed;right:40px;top:4px;"
                           "width:34px;height:36px'>x</button>`)")
        self.assertIsNone(self.lookup())


if __name__ == "__main__":
    unittest.main()
