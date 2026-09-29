"""Synthetic browser proof that price-route nonclaims have precise reasons."""

from __future__ import annotations

import unittest

from enterprise_fallback.odoo18.odoo_v066_train_route_router_v1 import (
    PRICE_ROUTE_DIAGNOSTIC_JS,
)
from tests.test_odoo_v066_train_price_corner_dom_v2 import (
    HTML, PRICE, RFQ_ID, ROUTE_PATH, SKU, URL,
)


class RouteProbeDomTests(unittest.TestCase):
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

    def reason(self):
        return self.page.evaluate(PRICE_ROUTE_DIAGNOSTIC_JS, {
            "rfq_id": RFQ_ID, "route_path": ROUTE_PATH,
            "sku": SKU, "price": PRICE})["reason_code"]

    def test_ready_and_wrong_order_or_product_cell(self):
        self.assertEqual(self.reason(), "ready")
        self.page.locator("h1").evaluate(
            "el => el.textContent = 'ELPO-TRN-0099'")
        self.assertEqual(self.reason(), "rfq_token_missing")
        self.page.locator("h1").evaluate(
            f"el => el.textContent = '{RFQ_ID}'")
        self.page.locator('td[name="product_id"]').evaluate(
            "el => el.textContent = 'wrong product'")
        self.page.locator('td[name="price_unit"]').evaluate(
            f"el => el.insertAdjacentHTML('beforeend', '<span>{SKU}</span>')")
        self.assertEqual(self.reason(), "product_cell_sku_missing")

    def test_modal_readonly_value_focus_and_viewer_reasons(self):
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', "
                           "`<dialog open style='width:200px;height:100px'>"
                           "Confirm</dialog>`)")
        self.assertEqual(self.reason(), "modal_present")
        self.page.locator("dialog").evaluate("el => el.remove()")
        self.page.locator("#price").evaluate("el => el.readOnly = true")
        self.assertEqual(self.reason(), "price_editor_not_writable")
        self.page.locator("#price").evaluate("el => el.readOnly = false")
        self.page.locator("#price").fill("999.99")
        self.assertEqual(self.reason(), "initial_price_mismatch")
        self.page.locator("#price").fill(PRICE)
        self.page.locator("#price").evaluate("el => el.blur()")
        self.assertEqual(self.reason(), "editor_unfocused")
        self.page.locator("#price").focus()
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', "
                           "`<iframe class='o-FileViewer-view'></iframe>`)")
        self.assertEqual(self.reason(), "viewer_present")


if __name__ == "__main__":
    unittest.main()
