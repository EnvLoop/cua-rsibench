"""Two additional, unsealed Odoo Community development workflow families.

The fixture writer uses XML-RPC before the baseline is frozen. Actors only use
the native web GUI; verification is owned by the separate SELECT-only reader.
No case in this module is an official final task.
"""

from __future__ import annotations

import base64
import io
import json
import secrets
from datetime import date, timedelta

from factory import PRIVATE, OdooRPC, catalog


def sales_candidates() -> list[dict]:
    products = catalog()
    out = []
    for idx in range(20):
        case_id = f"ELSQ-{idx + 1:04d}"
        lines = []
        for pos in range(3):
            product = products[(idx * 3 + pos * 7) % len(products)]
            qty = 4 + (idx * 5 + pos * 3) % 27
            price = round(27.50 + (idx % 9) * 7.25 + pos * 3.50, 2)
            discount = (0, 5, 10, 15)[(idx + pos) % 4]
            initial = {"qty": qty, "price": price, "discount": discount}
            if pos == idx % 3:
                initial = dict(initial)
                if idx % 2:
                    initial["price"] = round(price + 4.75, 2)
                else:
                    initial["qty"] += 2
            if idx >= 3 and pos == (idx + 1) % 3:
                initial = dict(initial)
                initial["price"] = round(price + 3.25, 2)
            if idx >= 8 and idx % 3 == 0 and pos == (idx + 2) % 3:
                initial = dict(initial)
                initial["qty"] += 1
            lines.append({"sku": product["sku"], "expected": {"qty": qty, "price": price,
                          "discount": discount}, "initial": initial})
        reference = f"CPO-2025-{idx + 391:05d}"
        out.append({
            "id": case_id, "family": "sales_quote_customer_po", "customer": f"Crestview Customer {idx + 1:02d}",
            "customer_reference": reference, "initial_customer_reference": f"CPO-DRAFT-{idx + 391:05d}",
            "lines": lines,
            "prompt": (f"In Sales, open quotation {case_id}. Reconcile its three lines and customer "
                       "reference with the attached synthetic customer purchase order. Preserve the "
                       "customer, quotation state, all other quotations and their attachments."),
        })
    return out


def crm_candidates() -> list[dict]:
    stages = ("Qualified", "Proposition", "Negotiation")
    out = []
    for idx in range(20):
        case_id = f"ELCRM-{idx + 1:04d}"
        closing = (date(2025, 11, 1) + timedelta(days=7 * idx)).isoformat()
        expected = {
            "stage_name": stages[idx % len(stages)],
            "salesperson_index": idx % 3,
            "revenue": float(12500 + idx * 2750),
            "deadline": closing,
            "priority": str(1 + idx % 3),
        }
        initial = dict(expected)
        initial["stage_name"] = "New"
        initial["salesperson_index"] = (idx + 1) % 3
        initial["revenue"] = expected["revenue"] + 1800
        initial["deadline"] = (date.fromisoformat(closing) + timedelta(days=14)).isoformat()
        initial["priority"] = "0"
        out.append({
            "id": case_id, "family": "crm_opportunity_handoff", "customer": f"Crestview Customer {idx + 1:02d}",
            "expected": expected, "initial": initial,
            "prompt": (f"In CRM, open opportunity {case_id}. Follow the attached synthetic sales "
                       "handoff memo to update stage, salesperson, forecast revenue, expected closing "
                       "date and priority. Preserve the customer, opportunity notes, all other "
                       "opportunities and attachments."),
        })
    return out


def source_pdf(title: str, case_id: str, customer: str, rows: list[tuple[str, str]]) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter, invariant=1)
    pdf.setTitle(f"{case_id} synthetic {title.lower()}")
    pdf.setAuthor("EnvLoop benchmark development fixture")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, 738, title)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, 718, "SYNTHETIC BENCHMARK DOCUMENT - NOT A REAL CUSTOMER RECORD")
    pdf.drawString(48, 690, f"Case: {case_id}")
    pdf.drawString(48, 674, f"Customer: {customer}")
    y = 640
    for label, value in rows:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(48, y, label)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(210, y, value)
        y -= 24
    pdf.setFont("Helvetica", 8)
    pdf.drawString(48, 46, "Source values: original EnvLoop synthetic fixture")
    pdf.save()
    return buffer.getvalue()


def sales_pdf(case: dict) -> bytes:
    rows = [("Customer PO reference", case["customer_reference"])]
    for position, line in enumerate(case["lines"], 1):
        expected = line["expected"]
        rows.append((f"Line {position} / {line['sku']}",
                     f"qty {expected['qty']} / USD {expected['price']:.2f} / discount {expected['discount']}%"))
    return source_pdf("CUSTOMER PURCHASE ORDER", case["id"], case["customer"], rows)


def crm_pdf(case: dict, salesperson_names: list[str]) -> bytes:
    expected = case["expected"]
    rows = [
        ("Pipeline stage", expected["stage_name"]),
        ("Assigned salesperson", salesperson_names[expected["salesperson_index"]]),
        ("Forecast revenue", f"USD {expected['revenue']:,.2f}"),
        ("Expected closing", expected["deadline"]),
        ("Priority", {"1": "Medium", "2": "High", "3": "Very High"}[expected["priority"]]),
    ]
    return source_pdf("SALES OPPORTUNITY HANDOFF", case["id"], case["customer"], rows)


def attach(rpc: OdooRPC, model: str, record_id: int, name: str, data: bytes) -> None:
    rpc.call("ir.attachment", "create", {
        "name": name, "description": "Synthetic benchmark source document",
        "type": "binary", "res_model": model, "res_id": record_id,
        "datas": base64.b64encode(data).decode(),
    })


def seed_sales_and_crm(rpc: OdooRPC, product_ids: dict[str, int], company_id: int) -> dict:
    customer_ids = {}
    for index in range(20):
        name = f"Crestview Customer {index + 1:02d}"
        customer_ids[name] = rpc.call("res.partner", "create", {
            "name": name, "is_company": True,
            "comment": "Synthetic benchmark customer; no real commercial relationship.",
        })
    sales_gold = {}
    for case in sales_candidates():
        commands = []
        for line in case["lines"]:
            commands.append((0, 0, {
                "product_id": product_ids[line["sku"]],
                "product_uom_qty": line["initial"]["qty"],
                "price_unit": line["initial"]["price"],
                "discount": line["initial"]["discount"],
            }))
        order_id = rpc.call("sale.order", "create", {
            "name": case["id"], "origin": "ENVLOOP-SALES-DEV",
            "partner_id": customer_ids[case["customer"]],
            "client_order_ref": case["initial_customer_reference"],
            "order_line": commands,
        })
        attach(rpc, "sale.order", order_id, f"{case['id']}-customer-po.pdf", sales_pdf(case))
        line_rows = rpc.call("sale.order.line", "search_read", [["order_id", "=", order_id]],
                             fields=["id", "product_id"], order="id")
        if len(line_rows) != 3:
            raise RuntimeError(f"Expected three sales lines on {case['id']}")
        sales_gold[case["id"]] = {
            "order_id": order_id, "customer_id": customer_ids[case["customer"]],
            "customer_reference": case["customer_reference"],
            "lines": [{"line_id": row["id"], "product_id": product_ids[line["sku"]],
                       "expected": line["expected"]}
                      for row, line in zip(line_rows, case["lines"])],
        }

    sales_users = []
    sales_names = ["Avery Lane", "Morgan Ellis", "Riley Chen"]
    group = rpc.call("res.groups", "search", [["category_id.name", "=", "Sales"]], limit=1)
    for idx, name in enumerate(sales_names):
        values = {"name": name, "login": f"envloop.sales.{idx + 1}@example.invalid",
                  "password": secrets.token_urlsafe(24), "company_id": company_id,
                  "company_ids": [(6, 0, [company_id])]}
        if group:
            values["groups_id"] = [(6, 0, group)]
        sales_users.append(rpc.call("res.users", "create", values))
    stage_map = {}
    for name in ("New", "Qualified", "Proposition", "Negotiation"):
        found = rpc.call("crm.stage", "search", [["name", "=", name]], limit=1)
        stage_map[name] = found[0] if found else rpc.call("crm.stage", "create", {"name": name})
    crm_gold = {}
    for case in crm_candidates():
        initial = case["initial"]
        lead_id = rpc.call("crm.lead", "create", {
            "name": case["id"], "type": "opportunity",
            "partner_id": customer_ids[case["customer"]],
            "description": "Synthetic intake: preserve this original opportunity note.",
            "stage_id": stage_map[initial["stage_name"]],
            "user_id": sales_users[initial["salesperson_index"]],
            "expected_revenue": initial["revenue"],
            "date_deadline": initial["deadline"],
            "priority": initial["priority"],
        })
        attach(rpc, "crm.lead", lead_id, f"{case['id']}-handoff.pdf", crm_pdf(case, sales_names))
        expected = case["expected"]
        crm_gold[case["id"]] = {
            "lead_id": lead_id, "customer_id": customer_ids[case["customer"]],
            "expected": {"stage_id": stage_map[expected["stage_name"]],
                         "user_id": sales_users[expected["salesperson_index"]],
                         "revenue": expected["revenue"],
                         "deadline": expected["deadline"],
                         "priority": expected["priority"]},
        }
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "sales_gold.json").write_text(json.dumps(sales_gold, indent=2) + "\n")
    (PRIVATE / "crm_gold.json").write_text(json.dumps(crm_gold, indent=2) + "\n")
    return {"sales_quotes": len(sales_gold), "crm_opportunities": len(crm_gold),
            "synthetic_customers": len(customer_ids), "synthetic_salespeople": len(sales_users)}
