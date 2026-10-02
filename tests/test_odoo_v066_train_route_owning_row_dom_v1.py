"""The editor-owning row resolves nested RFQ rows without weakening identity."""

from __future__ import annotations

import unittest

from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v5 import (
    _price_identity,
)
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v1 import (
    PRICE_ROUTE_DIAGNOSTIC_JS,
)
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v2 import (
    PRICE_EDITOR_OWNING_ROW_JS,
)


SKU = "EL-TRN-C98D176352-018"
PRICE = "176.52"
RFQ = "ELPO-TRN-0001"
ROUTE = "/odoo/purchase/123"
URL = "http://example.test" + ROUTE
HTML = f"""<html><body style="margin:0"><div class="o_form_view">
<h1>{RFQ}</h1>
<table style="position:absolute;left:16px;top:460px;width:1400px">
 <tbody><tr id="outer"><td colspan="3">
  <table><tbody><tr id="owning" style="height:85px">
   <td name="product_id" style="width:740px">[{SKU}] pallet wrap</td>
   <td name="price_unit" style="width:104px">
    <input id="price" value="{PRICE}" style="width:90px;height:26px">
   </td><td style="width:550px">15%</td>
  </tr></tbody></table>
 </td></tr></tbody>
</table></div></body></html>"""


class OwningRowDomTests(unittest.TestCase):
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

    def args(self, target=None):
        return {"rfq_id": RFQ, "route_path": ROUTE,
                "sku": SKU, "price": PRICE, "target": target}

    def lookup(self, target=None):
        return self.page.evaluate(PRICE_EDITOR_OWNING_ROW_JS,
                                  self.args(target))

    def test_old_global_row_search_nonunique_new_owner_ready(self):
        old = self.page.evaluate(PRICE_ROUTE_DIAGNOSTIC_JS,
                                 {key: value for key, value in self.args().items()
                                  if key != "target"})
        self.assertEqual(old["reason_code"], "sku_row_not_unique")
        result = self.lookup()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["visible_price_input_count"], 1)
        self.assertIsNotNone(_price_identity(result["identity"]))
        box = result["identity"]["editor_bounds"]
        point = {"x": int((box[0] + box[2]) / 2),
                 "y": int((box[1] + box[3]) / 2)}
        self.assertEqual(self.lookup(point)["status"], "ready")
        self.assertEqual(self.lookup({"x": 1200, "y": point["y"]})
                         ["reason_code"], "target_not_editor")

    def test_wrong_product_cell_duplicate_input_modal_and_route_fail(self):
        self.page.locator('td[name="product_id"]').evaluate(
            "el => el.textContent = 'wrong product'")
        self.page.locator('td[name="price_unit"]').evaluate(
            f"el => el.insertAdjacentHTML('beforeend', '<span>{SKU}</span>')")
        self.assertEqual(self.lookup()["reason_code"],
                         "product_cell_sku_missing")
        self.page.locator('td[name="product_id"]').evaluate(
            f"el => el.textContent = '[{SKU}] pallet wrap'")
        self.page.locator('td[name="price_unit"] span').evaluate(
            "el => el.remove()")
        self.page.locator('td[name="price_unit"]').evaluate(
            "el => el.insertAdjacentHTML('beforeend', "
            "`<input value='176.52' style='width:90px;height:26px'>`)")
        self.assertEqual(self.lookup()["reason_code"],
                         "price_editor_not_unique")
        self.page.locator('td[name="price_unit"] input').last.evaluate(
            "el => el.remove()")
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend', "
                           "`<dialog open style='width:200px;height:100px'>"
                           "Confirm</dialog>`)")
        self.assertEqual(self.lookup()["reason_code"], "modal_present")
        self.page.locator("dialog").evaluate("el => el.remove()")
        self.page.evaluate("history.pushState({}, '', '/odoo/purchase/124')")
        self.assertEqual(self.lookup()["reason_code"], "wrong_route")


if __name__ == "__main__":
    unittest.main()
