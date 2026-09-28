"""Evaluator-only v0.6.6 GUI recipes for Odoo selection/final controls.

Every task interaction goes through a current-frame ActionJournal. The page
routes and reloads are evaluator-owned setup/readback, not model tool access.
Known-answer values remain private and are never training examples. This file
contains no Docker, provider, or model calls.
"""

from __future__ import annotations

from typing import Any


ROUTES = {"purchase": "/odoo/purchase", "inventory": "/odoo/inventory",
          "sales": "/odoo/sales", "crm": "/odoo/crm"}


class RecipeError(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RecipeError(reason)


def _act(journal, kind: str, phase: str, *, locator=None, **fields):
    return journal.act(kind, phase=phase, locator=locator, **fields)


def _fill(journal, locator, value: Any, phase: str) -> None:
    locator.wait_for()
    _act(journal, "type", phase, locator=locator,
         text=str(value), mode="fill")


def _save(page, journal, phase: str) -> None:
    save = page.get_by_role("button", name="Save", exact=True)
    if save.count() and save.is_visible():
        _act(journal, "click", phase, locator=save)
        save.wait_for(state="hidden")
    else:
        page.wait_for_timeout(400)


def _grid_edit(page, journal, *, sku: str, cell: str,
               value: float | int, phase: str) -> None:
    row = page.locator("tr").filter(has_text=sku).first
    target = row.locator(f'td[name="{cell}"]')
    target.wait_for()
    _act(journal, "click", phase, locator=target)
    editor = page.locator(f'td[name="{cell}"] input').first
    editor.wait_for()
    page.wait_for_timeout(500)
    _act(journal, "double_click", phase, locator=editor)
    _act(journal, "key", phase, key="Meta+A")
    _act(journal, "type", phase, text=str(value), mode="insert")
    _act(journal, "key", phase, key="Tab")
    _save(page, journal, phase)
    page.reload()
    persisted = page.locator("tr").filter(has_text=sku).first.locator(
        f'td[name="{cell}"]')
    persisted.wait_for()
    require(round(float(persisted.inner_text().strip()), 2) ==
            round(float(value), 2), "native_grid_value_not_saved_after_reload")


def _open_purchase(page, journal, case: dict, port: int, phase: str) -> None:
    page.goto(f"http://127.0.0.1:{port}/odoo/purchase")
    search = page.get_by_role("searchbox")
    _fill(journal, search, case["id"], phase)
    _act(journal, "key", phase, key="Enter")
    row = page.get_by_role("cell", name=case["id"], exact=True)
    row.wait_for()
    _act(journal, "click", phase, locator=row)
    page.wait_for_url("**/odoo/purchase/*")


def _open_sales(page, journal, case: dict, port: int, phase: str) -> None:
    page.goto(f"http://127.0.0.1:{port}/odoo/sales")
    facet = page.locator("button.o_facet_remove").first
    if facet.count() and facet.is_visible():
        _act(journal, "click", phase, locator=facet)
    row = page.get_by_role("cell", name=case["id"], exact=True)
    if not row.count():
        search = page.get_by_role("searchbox")
        _fill(journal, search, case["id"], phase)
        _act(journal, "key", phase, key="Enter")
    row.wait_for()
    _act(journal, "click", phase, locator=row)
    page.wait_for_url("**/odoo/sales/*")


def _open_crm(page, journal, case: dict, port: int, phase: str) -> None:
    page.goto(f"http://127.0.0.1:{port}/odoo/crm")
    facet = page.locator("button.o_facet_remove").first
    if facet.count() and facet.is_visible():
        _act(journal, "click", phase, locator=facet)
    card = page.locator("span.fw-bold.fs-5").filter(has_text=case["id"])
    if not card.count():
        search = page.get_by_role("searchbox")
        _fill(journal, search, case["id"], phase)
        _act(journal, "key", phase, key="Enter")
    card.wait_for()
    _act(journal, "click", phase, locator=card.first)
    page.wait_for_url("**/odoo/crm/*", wait_until="domcontentloaded")


def _open_inventory_rule(page, journal, case: dict, port: int,
                         phase: str) -> None:
    page.goto(f"http://127.0.0.1:{port}/odoo/inventory")
    operations = page.get_by_role("button", name="Operations", exact=True)
    operations.wait_for()
    _act(journal, "click", phase, locator=operations)
    replenishment = page.get_by_text("Replenishment", exact=True)
    replenishment.wait_for()
    _act(journal, "click", phase, locator=replenishment)
    page.wait_for_url("**/odoo/replenishment")
    page.locator("tr").filter(has_text=case["sku"]).first.wait_for()


def open_case(page, journal, family: str, case: dict,
              port: int, phase: str) -> None:
    require(family in ROUTES and phase in ("positive", "negative"),
            "unknown_family_or_phase")
    if family == "purchase":
        _open_purchase(page, journal, case, port, phase)
    elif family == "sales":
        _open_sales(page, journal, case, port, phase)
    elif family == "crm":
        _open_crm(page, journal, case, port, phase)
    else:
        _open_inventory_rule(page, journal, case, port, phase)


def show_source(page, journal, family: str, case: dict,
                port: int) -> tuple[dict, str]:
    """Return one raw GUI source frame and its evaluator-visible label."""
    if family == "inventory":
        page.goto(f"http://127.0.0.1:{port}/odoo/action-430")
        search = page.get_by_role("searchbox")
        _fill(journal, search, case["sku"], "positive")
        _act(journal, "key", "positive", key="Enter")
        product = page.get_by_text(f"[{case['sku']}]", exact=True)
        product.wait_for()
        _act(journal, "click", "positive", locator=product)
        tab = page.get_by_role("tab", name="Purchase")
        tab.wait_for()
        _act(journal, "click", "positive", locator=tab)
        note = page.locator('[name="description_purchase"] textarea')
        note.wait_for()
        require(note.input_value() == case["source_note"],
                "native_purchase_planning_note_not_visible")
        frame = _act(journal, "wait", "positive", duration_ms=100)
        return frame, f"Purchase planning note for {case['sku']}"
    open_case(page, journal, family, case, port, "positive")
    button = page.locator("button.o-mail-Chatter-attachFiles")
    button.wait_for()
    _act(journal, "click", "positive", locator=button)
    label = f"{case['id']}-source.pdf"
    source = page.get_by_text(label, exact=True)
    source.wait_for()
    _act(journal, "click", "positive", locator=source)
    page.locator("iframe.o-FileViewer-view").wait_for()
    frame = _act(journal, "wait", "positive", duration_ms=100)
    close = page.locator('[title="Close (Esc)"]')
    _act(journal, "click", "positive", locator=close)
    close.wait_for(state="hidden")
    return frame, label


def apply_positive(page, journal, family: str,
                   case: dict, port: int) -> None:
    """Repair only the target business object through original GUI actions."""
    if family == "inventory":
        _open_inventory_rule(page, journal, case, port, "positive")
        for field, value in (("product_min_qty", case["expected"]["minimum"]),
                             ("product_max_qty", case["expected"]["maximum"])):
            _grid_edit(page, journal, sku=case["sku"], cell=field,
                       value=value, phase="positive")
        return
    if family == "purchase":
        for line in case["lines"]:
            changed_qty = line["initial"]["qty"] != line["expected"]["qty"]
            changed_price = line["initial"]["price"] != line["expected"]["price"]
            if changed_qty:
                _grid_edit(page, journal, sku=line["sku"], cell="product_qty",
                           value=line["expected"]["qty"], phase="positive")
            if changed_price or changed_qty:
                _grid_edit(page, journal, sku=line["sku"], cell="price_unit",
                           value=line["expected"]["price"], phase="positive")
        if "vendor_reference" in case:
            field = page.locator('[name="partner_ref"] input')
            _fill(journal, field, case["vendor_reference"], "positive")
            _act(journal, "key", "positive", key="Tab")
            _save(page, journal, "positive")
            page.reload()
            require(field.input_value() == case["vendor_reference"],
                    "native_vendor_reference_not_saved")
        return
    if family == "sales":
        other = page.get_by_text("Other Info", exact=True)
        _act(journal, "click", "positive", locator=other)
        _fill(journal, page.locator('[name="client_order_ref"] input'),
              case["customer_reference"], "positive")
        if "expiration_date" in case:
            value = case["expiration_date"]
            localized = f"{value[5:7]}/{value[8:10]}/{value[:4]}"
            _fill(journal, page.locator('[name="validity_date"] input'),
                  localized, "positive")
            _act(journal, "key", "positive", key="Tab")
        _save(page, journal, "positive")
        page.reload()
        lines = page.get_by_text("Order Lines", exact=True)
        _act(journal, "click", "positive", locator=lines)
        for line in case["lines"]:
            changed_qty = line["initial"]["qty"] != line["expected"]["qty"]
            changed_price = line["initial"]["price"] != line["expected"]["price"]
            if changed_qty:
                _grid_edit(page, journal, sku=line["sku"],
                           cell="product_uom_qty",
                           value=line["expected"]["qty"], phase="positive")
            if changed_price or changed_qty:
                _grid_edit(page, journal, sku=line["sku"], cell="price_unit",
                           value=line["expected"]["price"], phase="positive")
        return
    if family == "crm":
        initial, expected = case["initial"], case["expected"]
        if initial["stage_name"] != expected["stage_name"]:
            stage = page.locator('[name="stage_id"] button[role="radio"]').filter(
                has_text=expected["stage_name"])
            _act(journal, "click", "positive", locator=stage)
        if initial["salesperson_index"] != expected["salesperson_index"]:
            name = case["salesperson_names"][expected["salesperson_index"]]
            user = page.locator('[name="user_id"] input')
            _fill(journal, user, name.split()[0], "positive")
            option = page.get_by_role("option", name=name)
            option.wait_for()
            _act(journal, "click", "positive", locator=option)
            _act(journal, "key", "positive", key="Tab")
        if initial["revenue"] != expected["revenue"]:
            _fill(journal, page.locator('[name="expected_revenue"] input'),
                  expected["revenue"], "positive")
        if initial["deadline"] != expected["deadline"]:
            value = expected["deadline"]
            _fill(journal, page.locator('[name="date_deadline"] input'),
                  f"{value[5:7]}/{value[8:10]}/{value[:4]}", "positive")
            _act(journal, "key", "positive", key="Tab")
        if initial["priority"] != expected["priority"]:
            label = {"1": "Medium", "2": "High", "3": "Very High"}[
                expected["priority"]]
            _act(journal, "click", "positive", locator=page.locator(
                f'[name="priority"] [aria-label="{label}"]'))
        if "email_from" in expected:
            _fill(journal, page.locator('[name="email_from"] input'),
                  expected["email_from"], "positive")
            _fill(journal, page.locator('[name="phone"] input'),
                  expected["phone"], "positive")
            _act(journal, "key", "positive", key="Tab")
        _save(page, journal, "positive")
        page.reload()
        return
    raise RecipeError("unknown_positive_family")


def apply_negative(page, journal, family: str,
                   wrong: dict, port: int) -> None:
    """Mutate one distinct object; its target task must then score zero."""
    open_case(page, journal, family, wrong, port, "negative")
    if family == "purchase":
        line = wrong["lines"][0]
        _grid_edit(page, journal, sku=line["sku"], cell="price_unit",
                   value=round(line["initial"]["price"] + 1.25, 2),
                   phase="negative")
    elif family == "inventory":
        _grid_edit(page, journal, sku=wrong["sku"], cell="product_min_qty",
                   value=wrong["initial"]["minimum"] + 1,
                   phase="negative")
    elif family == "sales":
        _act(journal, "click", "negative", locator=page.get_by_text(
            "Other Info", exact=True))
        _fill(journal, page.locator('[name="client_order_ref"] input'),
              "WRONG-OBJECT-CONTROL", "negative")
        _save(page, journal, "negative")
        page.reload()
    elif family == "crm":
        current = wrong["initial"]["priority"]
        label = {"0": "Medium", "1": "High", "2": "Very High",
                 "3": "Medium"}[current]
        _act(journal, "click", "negative", locator=page.locator(
            f'[name="priority"] [aria-label="{label}"]'))
        _save(page, journal, "negative")
        page.reload()
    else:
        raise RecipeError("unknown_negative_family")
