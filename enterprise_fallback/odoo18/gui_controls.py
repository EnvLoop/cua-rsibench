"""Repeatable native-GUI development controls for the Sales and CRM families.

Run against an already bootstrapped, isolated worker. This uses browser clicks
for every actor mutation. The scorer itself only queries PostgreSQL as the
read-only evaluator role. Outputs are development evidence, never admission.
"""

from __future__ import annotations

import json

from factory import PRIVATE, local_config
from multifamily import crm_candidates, sales_candidates
from reset import restore
from verify import score
from worker_lease import exclusive_worker_operation, require_worker_lease


def browser_login(page, port: int, password: str, login: str = "admin") -> None:
    require_worker_lease()
    page.goto(f"http://127.0.0.1:{port}/web/login")
    page.locator('input[name="login"]').fill(login)
    page.locator('input[name="password"]').fill(password)
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url("**/odoo/**", wait_until="domcontentloaded")


def open_sales(page, port: int, case_id: str) -> None:
    require_worker_lease()
    page.goto(f"http://127.0.0.1:{port}/odoo/sales")
    # Odoo opens Sales with a default "My Quotations" facet. The benchmark
    # actor has all-document Sales access, but the seeded quotes belong to
    # synthetic salespeople; remove the default UI filter before searching.
    page.locator("small.o_facet_value").filter(has_text="My Quotations").wait_for()
    page.locator("button.o_facet_remove").first.click()
    if not page.get_by_role("cell", name=case_id, exact=True).count():
        search = page.get_by_role("searchbox")
        search.fill(case_id)
        search.press("Enter")
    page.get_by_role("cell", name=case_id, exact=True).click()
    page.wait_for_url("**/odoo/sales/*")


def open_purchase(page, port: int, case_id: str) -> None:
    require_worker_lease()
    page.goto(f"http://127.0.0.1:{port}/odoo/purchase")
    search = page.get_by_role("searchbox")
    search.fill(case_id)
    search.press("Enter")
    page.get_by_role("cell", name=case_id, exact=True).click()
    page.wait_for_url("**/odoo/purchase/*")


def save_purchase_if_pending(page) -> None:
    """Odoo sometimes autosaves an RFQ grid cell on Tab, hiding Save."""
    save = page.get_by_role("button", name="Save", exact=True)
    if save.count():
        save.click()
        save.wait_for(state="hidden")
    else:
        page.wait_for_timeout(350)


def purchase_case(page, case: dict, *, positive: bool = True) -> None:
    """Reconcile an RFQ entirely through its native three-line editor."""
    require_worker_lease()
    if not positive:
        other = case["lines"][0]
        wrong_price = round(other["initial"]["price"] + 1.25, 2)
        row = page.locator("tr").filter(has_text=other["sku"]).first
        row.locator('td[name="price_unit"]').click()
        page.locator('td[name="price_unit"] input').first.fill(str(wrong_price))
        page.locator('td[name="price_unit"] input').first.press("Tab")
        save_purchase_if_pending(page)
        page.reload()
        observed = page.locator("tr").filter(has_text=other["sku"]).first.locator(
            'td[name="price_unit"]').inner_text().strip()
        if round(float(observed), 2) != wrong_price:
            raise RuntimeError("Wrong-object purchase edit did not persist")
        return
    for line in case["lines"]:
        changed_qty = line["initial"]["qty"] != line["expected"]["qty"]
        changed_price = line["initial"]["price"] != line["expected"]["price"]
        if changed_qty:
            row = page.locator("tr").filter(has_text=line["sku"]).first
            row.locator('td[name="product_qty"]').click()
            page.locator('td[name="product_qty"] input').first.fill(str(line["expected"]["qty"]))
            page.locator('td[name="product_qty"] input').first.press("Tab")
            save_purchase_if_pending(page)
            page.reload()
            actual_qty = page.locator("tr").filter(has_text=line["sku"]).first.locator(
                'td[name="product_qty"]').inner_text().strip()
            if float(actual_qty) != line["expected"]["qty"]:
                raise RuntimeError("Purchase quantity edit did not persist")
        if changed_price or changed_qty:
            row = page.locator("tr").filter(has_text=line["sku"]).first
            row.locator('td[name="price_unit"]').click()
            page.locator('td[name="price_unit"] input').first.fill(str(line["expected"]["price"]))
            page.locator('td[name="price_unit"] input').first.press("Tab")
            save_purchase_if_pending(page)
            page.reload()
            actual_price = page.locator("tr").filter(has_text=line["sku"]).first.locator(
                'td[name="price_unit"]').inner_text().strip()
            if round(float(actual_price), 2) != line["expected"]["price"]:
                raise RuntimeError("Purchase unit price edit did not persist")


def open_inventory_note(page, port: int, case: dict) -> bool:
    """Read the actual Product > Purchase source field in the native GUI."""
    require_worker_lease()
    page.goto(f"http://127.0.0.1:{port}/odoo/action-430")
    search = page.get_by_role("searchbox")
    search.fill(case["sku"])
    search.press("Enter")
    page.get_by_text(f"[{case['sku']}]", exact=True).click()
    page.get_by_role("tab", name="Purchase").click()
    return page.locator('[name="description_purchase"] textarea').input_value() == case["source_note"]


def open_replenishment(page, port: int) -> None:
    require_worker_lease()
    page.goto(f"http://127.0.0.1:{port}/odoo/inventory")
    page.get_by_role("button", name="Operations", exact=True).click()
    page.get_by_text("Replenishment", exact=True).click()
    page.wait_for_url("**/odoo/replenishment")


def inventory_case(page, case: dict, *, positive: bool = True) -> None:
    require_worker_lease()
    row = page.locator("tr").filter(has_text=case["sku"]).first
    if positive:
        edits = (("product_min_qty", case["expected"]["minimum"]),
                 ("product_max_qty", case["expected"]["maximum"]))
    else:
        edits = (("product_min_qty", case["initial"]["minimum"] + 1),)
    for cell, value in edits:
        row.locator(f'td[name="{cell}"]').click()
        page.locator(f'td[name="{cell}"] input').first.fill(str(value))
        page.locator(f'td[name="{cell}"] input').first.press("Tab")
        page.wait_for_timeout(350)
    page.reload()
    if positive:
        row = page.locator("tr").filter(has_text=case["sku"]).first
        for cell, expected in edits:
            observed = row.locator(f'td[name="{cell}"]').inner_text().strip()
            if float(observed) != expected:
                raise RuntimeError(f"Replenishment edit did not persist: {cell}")


def open_crm(page, port: int, case_id: str) -> None:
    require_worker_lease()
    page.goto(f"http://127.0.0.1:{port}/odoo/crm")
    page.locator("button.o_facet_remove").click()
    card = page.locator("span.fw-bold.fs-5").filter(has_text=case_id)
    if not card.count():
        search = page.get_by_role("searchbox")
        search.fill(case_id)
        search.press("Enter")
    card.click()
    page.wait_for_url("**/odoo/crm/*", wait_until="domcontentloaded")


def view_attachment(page, filename: str) -> bool:
    require_worker_lease()
    page.locator("button.o-mail-Chatter-attachFiles").click()
    item = page.get_by_text(filename, exact=True)
    item.wait_for()
    item.click()
    page.locator("iframe.o-FileViewer-view").wait_for()
    preview = page.locator("iframe.o-FileViewer-view").count() == 1
    page.locator('[title="Close (Esc)"]').click()
    return preview


def sales_case(page, case: dict, *, positive: bool) -> None:
    require_worker_lease()
    page.get_by_text("Other Info", exact=True).click()
    reference = case["customer_reference"] if positive else "WRONG-OBJECT-CONTROL"
    page.locator('[name="client_order_ref"] input').fill(reference)
    if not positive:
        page.get_by_role("button", name="Save").click()
        page.get_by_role("button", name="Save").wait_for(state="hidden")
        return
    page.get_by_text("Order Lines", exact=True).click()
    for line in case["lines"]:
        if line["initial"]["qty"] != line["expected"]["qty"]:
            row = page.locator("tr").filter(has_text=line["sku"]).first
            row.locator('td[name="product_uom_qty"]').click()
            page.locator('td[name="product_uom_qty"] input').first.fill(str(line["expected"]["qty"]))
            page.locator('td[name="product_uom_qty"] input').first.press("Tab")
            page.wait_for_timeout(500)
            page.get_by_role("button", name="Save").click()
            page.get_by_role("button", name="Save").wait_for(state="hidden")
            page.reload()
            observed_qty = page.locator("tr").filter(has_text=line["sku"]).first.locator(
                'td[name="product_uom_qty"]'
            ).inner_text().strip()
            if float(observed_qty) != line["expected"]["qty"]:
                raise RuntimeError(f"Quantity edit did not persist: {observed_qty}")
        if line["initial"]["price"] != line["expected"]["price"] or \
                line["initial"]["qty"] != line["expected"]["qty"]:
            # Odoo recalculates a custom price from product list price on qty
            # change, so explicitly reconcile the source PO price afterwards.
            row = page.locator("tr").filter(has_text=line["sku"]).first
            row.locator('td[name="price_unit"]').click()
            page.locator('td[name="price_unit"] input').first.fill(str(line["expected"]["price"]))
            page.locator('td[name="price_unit"] input').first.press("Tab")
            page.wait_for_timeout(300)
            page.get_by_role("button", name="Save").click()
            page.get_by_role("button", name="Save").wait_for(state="hidden")
            page.reload()


def crm_case(page, case: dict, *, positive: bool) -> None:
    require_worker_lease()
    if positive:
        expected = case["expected"]
        initial = case["initial"]
        if initial["stage_name"] != expected["stage_name"]:
            page.locator('[name="stage_id"] button[role="radio"]').filter(
                has_text=expected["stage_name"]
            ).click()
        names = case.get("salesperson_names", ["Avery Lane", "Morgan Ellis", "Riley Chen"])
        if initial["salesperson_index"] != expected["salesperson_index"]:
            name = names[expected["salesperson_index"]]
            page.locator('[name="user_id"] input').fill(name.split()[0])
            page.get_by_role("option", name=name).click()
            # The many2one popup displays a choice before the CRM form has
            # committed it. Blur the field so the pinned Odoo form exposes
            # its manual Save control, especially for the two-field train task.
            page.locator('[name="user_id"] input').press("Tab")
            page.wait_for_timeout(400)
        if initial["revenue"] != expected["revenue"]:
            page.locator('[name="expected_revenue"] input').fill(str(expected["revenue"]))
        if initial["deadline"] != expected["deadline"]:
            month, day, year = expected["deadline"][5:7], expected["deadline"][8:10], expected["deadline"][:4]
            page.locator('[name="date_deadline"] input').fill(f"{month}/{day}/{year}")
            page.locator('[name="date_deadline"] input').press("Tab")
        if initial["priority"] != expected["priority"]:
            priority = {"1": "Medium", "2": "High", "3": "Very High"}[expected["priority"]]
            page.locator(f'[name="priority"] [aria-label="{priority}"]').click()
    else:
        current = case["initial"]["priority"]
        wrong = {"0": "Medium", "1": "High", "2": "Very High", "3": "Medium"}[current]
        page.locator(f'[name="priority"] [aria-label="{wrong}"]').click()
    page.wait_for_timeout(350)
    save = page.get_by_role("button", name="Save")
    if save.count():
        # CRM autosaves some field combinations while the button is still
        # briefly in the DOM. A disappearing Save is acceptable only when
        # the subsequent persisted-state verifier confirms every target.
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        try:
            save.click(timeout=1500)
            save.wait_for(state="hidden", timeout=1500)
        except PlaywrightTimeoutError:
            pass
    page.reload()
    if positive and case["initial"]["salesperson_index"] != case["expected"]["salesperson_index"]:
        selected = page.locator('[name="user_id"] input').input_value()
        if selected != names[case["expected"]["salesperson_index"]]:
            raise RuntimeError("CRM salesperson edit did not persist")


def run() -> dict:
    with exclusive_worker_operation("gui_controls"):
        return _run_unlocked()


def _run_unlocked() -> dict:
    from playwright.sync_api import sync_playwright

    config = local_config()
    port = int(config["ODOO_PORT"])
    password = config["ODOO_ADMIN_PASSWORD"]
    sale_case, other_sale = sales_candidates()[:2]
    crm_case_one, other_crm = crm_candidates()[:2]
    out = {"status": "development_controls_not_official_admission",
           "official_final_tasks_admitted": 0}

    out["sales_pre_reset"] = restore()
    out["sales_baseline"] = score(sale_case["id"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        browser_login(page, port, password)
        open_sales(page, port, sale_case["id"])
        out["sales_source_pdf_visible"] = view_attachment(page, f"{sale_case['id']}-customer-po.pdf")
        sales_case(page, sale_case, positive=True)
        out["sales_positive"] = score(sale_case["id"])
        open_sales(page, port, other_sale["id"])
        sales_case(page, other_sale, positive=False)
        out["sales_wrong_object_negative"] = score(sale_case["id"])
        browser.close()
    out["sales_post_reset"] = restore()
    out["sales_after_reset"] = score(sale_case["id"])

    out["crm_baseline"] = score(crm_case_one["id"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        browser_login(page, port, password)
        open_crm(page, port, crm_case_one["id"])
        out["crm_source_pdf_visible"] = view_attachment(page, f"{crm_case_one['id']}-handoff.pdf")
        crm_case(page, crm_case_one, positive=True)
        out["crm_positive"] = score(crm_case_one["id"])
        open_crm(page, port, other_crm["id"])
        crm_case(page, other_crm, positive=False)
        out["crm_wrong_object_negative"] = score(crm_case_one["id"])
        browser.close()
    out["crm_post_reset"] = restore()
    out["crm_after_reset"] = score(crm_case_one["id"])
    (PRIVATE / "gui_controls_receipt.json").write_text(json.dumps(out, indent=2) + "\n")
    assert out["sales_source_pdf_visible"] and out["crm_source_pdf_visible"]
    for family in ("sales", "crm"):
        assert out[f"{family}_baseline"]["reward"] == 0.0
        assert out[f"{family}_positive"]["reward"] == 1.0
        assert out[f"{family}_wrong_object_negative"]["reward"] == 0.0
        assert out[f"{family}_after_reset"]["reward"] == 0.0
        assert out[f"{family}_post_reset"]["business_snapshot_equal"]
        assert out[f"{family}_post_reset"]["physical_filestore_equal_before_web_restart"]
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
