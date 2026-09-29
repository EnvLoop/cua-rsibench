"""Synthetic native-row DOM checks for the train price-editor identity."""

from __future__ import annotations

import unittest

from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v4 import (
    PRICE_EDITOR_LOOKUP_JS,
)


SKU = "EL-TRN-C98D176352-018"
PRICE = "176.52"
URL = "http://example.test/odoo/purchase/123"
HTML = f"""<html><body style="margin:0">
<div class="o_form_view">
  <table style="position:absolute;left:16px;top:460px;width:1400px">
    <tbody><tr style="height:85px">
      <td name="product_id" style="width:740px">[{SKU}] pallet wrap</td>
      <td name="price_unit" style="width:104px">
        <input id="price" value="{PRICE}" style="width:90px;height:26px">
      </td><td style="width:550px">15%</td>
    </tr></tbody>
  </table>
</div></body></html>"""


class PriceEditorDomTests(unittest.TestCase):
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
        self.page.locator("#price").focus()

    def tearDown(self):
        self.page.close()

    def lookup(self, target=None):
        return self.page.evaluate(PRICE_EDITOR_LOOKUP_JS, {
            "sku": SKU, "price": PRICE, "target": target})

    def test_unique_focused_sku_price_and_hit(self):
        observed = self.lookup()
        self.assertIsNotNone(observed)
        self.assertEqual(observed["sku"], SKU)
        bounds = observed["editor_bounds"]
        target = {"x": int((bounds[0] + bounds[2]) / 2),
                  "y": int((bounds[1] + bounds[3]) / 2)}
        self.assertTrue(self.lookup(target)["target_inside"])
        self.assertFalse(self.lookup({"x": 1200, "y": target["y"]})
                         ["target_inside"])

    def test_wrong_row_value_modal_viewer_or_ambiguity_fails(self):
        self.page.locator('td[name="product_id"]').evaluate(
            "el => el.textContent = 'other SKU'")
        self.assertIsNone(self.lookup())
        self.page.locator('td[name="product_id"]').evaluate(
            f"el => el.textContent = '[{SKU}] pallet wrap'")
        self.page.locator("#price").fill("999.99")
        self.assertIsNone(self.lookup())
        self.page.locator("#price").fill(PRICE)
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', "
                           "`<div class='modal show' "
                           "style='position:fixed;left:200px;top:200px;"
                           "width:200px;height:100px'></div>`)")
        self.assertIsNone(self.lookup())
        self.page.locator(".modal").evaluate("el => el.remove()")
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', "
                           "`<iframe class='o-FileViewer-view'></iframe>`)")
        self.assertIsNone(self.lookup())
        self.page.locator("iframe").evaluate("el => el.remove()")
        self.page.evaluate("document.querySelector('tbody')"
                           ".insertAdjacentHTML('beforeend', "
                           f"`<tr><td name='product_id'>{SKU}</td>"
                           "<td name='price_unit'><input value='176.52'>"
                           "</td></tr>`)")
        self.assertIsNone(self.lookup())


if __name__ == "__main__":
    unittest.main()
