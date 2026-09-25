"""Deterministic development candidates for a real Odoo Community instance.

All purchase records are synthetic.  The separate SEC attachment is a verbatim
public historical excerpt and is never represented as an internal supplier file.
This module intentionally produces unsealed candidates, not official final tasks.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import random
import xmlrpc.client
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRIVATE = HERE / "private"
SOURCE = REPO / "sec_excel_factory/sources/retail_excerpt.json"
BASE_URL = "http://127.0.0.1:8078"
SEED = 907731

VENDORS = [
    "Harborline Industrial", "Meridian Parts Group", "Northbridge Supply",
    "Pinecrest Logistics", "Granite Bay Components", "Redwood MRO",
    "Anchor Point Distribution", "Alder Technical Supply", "Brightwater Tools",
    "Crossfield Materials", "Delta Ridge Supply", "Evermark Industrial",
    "Ferry Road Components", "Glenfield Trade", "Highland Depot",
    "Inlet Technical", "Juniper Materials", "Kestrel Distribution",
    "Longshore Components", "Mason Bay Supply", "Oakfield MRO",
    "Portside Trade", "Riverbend Industrial", "Summit Parts",
]

CATALOG = [
    ("SCANNER", "handheld warehouse scanner"),
    ("WRAP", "pallet stretch wrap"),
    ("LABEL", "thermal shipping label roll"),
    ("GLOVE", "cut-resistant work glove"),
    ("FILTER", "air intake filter"),
    ("BEARING", "sealed roller bearing"),
    ("SEAL", "industrial gasket seal"),
    ("SENSOR", "forklift proximity sensor"),
]

# Deliberate case patterns: some require one-field repair, others require
# multi-line reconciliation.  These are not independent hidden templates.
FAULT_PATTERNS = [
    ("unit-price", ((0, "price"),)),
    ("quantity", ((0, "qty"),)),
    ("delivery-date", ((0, "date"),)),
    ("price-and-quantity", ((1, "price"), (1, "qty"))),
    ("two-line-prices", ((0, "price"), (2, "price"))),
    ("quantity-and-date", ((0, "qty"), (2, "date"))),
    ("cross-line", ((1, "price"), (2, "qty"))),
    ("three-line-reconciliation", ((0, "price"), (1, "qty"), (2, "date"))),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def catalog() -> list[dict]:
    products = []
    for family, title in CATALOG:
        for variant in range(1, 7):
            products.append({
                "sku": f"EL-{family}-{variant:02d}",
                "name": f"{title} / specification {variant:02d}",
            })
    return products


def candidates() -> list[dict]:
    rng = random.Random(SEED)
    products = catalog()
    result = []
    for idx in range(120):
        number = idx + 1
        vendor = VENDORS[idx % len(VENDORS)]
        pattern_name, faults = FAULT_PATTERNS[idx % len(FAULT_PATTERNS)]
        base_day = date(2025, 3, 1) + timedelta(days=(idx * 7) % 180)
        chosen = rng.sample(products, 3)
        lines = []
        for pos, product in enumerate(chosen):
            expected_qty = 6 + ((idx + pos * 9) % 31)
            expected_price = round(18.5 + (idx % 13) * 6.75 + pos * 4.25, 2)
            expected_date = (base_day + timedelta(days=10 + pos * 3)).isoformat()
            actual_qty = expected_qty
            actual_price = expected_price
            actual_date = expected_date
            if (pos, "qty") in faults:
                actual_qty += 3 + (idx % 4)
            if (pos, "price") in faults:
                actual_price = round(expected_price + 4.5 + (idx % 5) * 1.25, 2)
            if (pos, "date") in faults:
                actual_date = (date.fromisoformat(expected_date) + timedelta(days=4)).isoformat()
            lines.append({
                "sku": product["sku"], "name": product["name"],
                "expected": {"qty": expected_qty, "price": expected_price, "date": expected_date},
                "initial": {"qty": actual_qty, "price": actual_price, "date": actual_date},
            })
        result.append({
            "id": f"ELPO-{number:04d}",
            "partition": "selection_candidate" if idx < 20 else "unsealed_scale_candidate",
            "pattern": pattern_name,
            "vendor": vendor,
            "order_date": base_day.isoformat(),
            "lines": lines,
            "prompt": (
                f"In Purchase, open RFQ ELPO-{number:04d} and reconcile its three "
                "lines against the attached supplier confirmation. Correct every "
                "mismatch in quantity, unit price, or promised date. Leave the "
                "vendor, all unrelated RFQs, and the RFQ state unchanged."
            ),
        })
    return result


def replenishment_candidates() -> list[dict]:
    """A distinct, cross-screen Inventory planning family (20 dev cases)."""
    result = []
    for idx, product in enumerate(catalog()[:20]):
        week_counts = [5 + (idx * 3 + week * 5) % 11 for week in range(4)]
        lead_days = [7, 14, 21][idx % 3]
        safety = 3 + idx % 6
        case_pack = [4, 6, 8][idx % 3]
        minimum = math.ceil(sum(week_counts) / 4 * lead_days / 7) + safety
        maximum = minimum + 2 * case_pack
        initial_min = minimum + 2 + idx % 3
        initial_max = maximum - 2 - idx % 4
        result.append({
            "id": f"ELRP-{idx + 1:04d}",
            "sku": product["sku"],
            "family": "inventory_replenishment",
            "source_note": (
                "Synthetic four-week demand counts: " + ", ".join(map(str, week_counts)) +
                f" units. Supplier lead: {lead_days} days. Safety stock: {safety} units. "
                f"Case pack: {case_pack} units. Planning rule: minimum is ceil(mean "
                "weekly demand x lead days / 7) plus safety stock; maximum is "
                "minimum plus two case packs."
            ),
            "expected": {"minimum": minimum, "maximum": maximum},
            "initial": {"minimum": initial_min, "maximum": initial_max},
            "prompt": (
                f"In Inventory, find product {product['sku']} and read its Purchase "
                "planning note. Compute the stated minimum and maximum, then "
                "update its WH/Stock replenishment rule. Do not change the "
                "product note, any other rule, or any RFQ."
            ),
        })
    return result


def train_world_candidates(world_seed: int, count: int = 40) -> list[dict]:
    """Generate undeployed train-only entities in a separate world namespace.

    The eventual study must bootstrap these into a distinct ODOO_PROJECT and
    seal the evaluation seed after a protocol freeze.  No generated case here
    is an official hidden evaluation identity.
    """
    rng = random.Random(world_seed)
    tag = hashlib.sha256(str(world_seed).encode()).hexdigest()[:8].upper()
    vendors = [f"Training Supplier {tag}-{i:02d}" for i in range(1, 17)]
    products = [f"TRN-{tag}-{i:03d}" for i in range(1, 33)]
    result = []
    for idx in range(count):
        lines = []
        for pos, sku in enumerate(rng.sample(products, 3)):
            qty = rng.randint(4, 45)
            price = round(rng.uniform(11, 130), 2)
            promised = (date(2025, 9, 1) + timedelta(days=rng.randint(7, 90))).isoformat()
            initial = {"qty": qty, "price": price, "date": promised}
            if pos == idx % 3:
                initial = {"qty": qty, "price": round(price + 3.75, 2), "date": promised}
            lines.append({
                "sku": sku, "name": f"training component {sku}",
                "expected": {"qty": qty, "price": price, "date": promised},
                "initial": initial,
            })
        result.append({
            "id": f"ELTR-{tag}-{idx + 1:04d}",
            "partition": "train_only_generator_not_deployed",
            "world_seed": world_seed,
            "vendor": vendors[idx % len(vendors)],
            "order_date": "2025-09-01",
            "lines": lines,
        })
    return result


def split_audit(world_seed: int = 20260925) -> dict:
    """Expose overlap so public development partitions cannot be called hidden."""
    all_cases = candidates()
    train = train_world_candidates(world_seed)

    def dims(rows: list[dict]) -> dict[str, set[str]]:
        return {
            "ids": {c["id"] for c in rows},
            "vendors": {c["vendor"] for c in rows},
            "skus": {line["sku"] for c in rows for line in c["lines"]},
            "patterns": {c["pattern"] for c in rows if "pattern" in c},
        }

    a, b, t = (dims(all_cases[:20]), dims(all_cases[20:]), dims(train))
    return {
        "train_selection_overlap": {key: len(t[key] & a[key]) for key in a},
        "train_scale_overlap": {key: len(t[key] & b[key]) for key in a},
        "selection_scale_overlap": {key: len(a[key] & b[key]) for key in a},
        "official_entity_and_pattern_disjoint_gate": False,
    }


def proposed_clustered_split(world_seed: int) -> dict[str, list[dict]]:
    """Undeployed, entity-disjoint 40/20/100 RFQ blueprint.

    Every five cases share one vendor inside a split.  Vendor and SKU pools do
    not cross splits.  The eight fault templates DO cross splits, so this is a
    within-template generalization design, not novel-template evaluation.
    """
    rng = random.Random(world_seed)
    tag = hashlib.sha256(f"clustered:{world_seed}".encode()).hexdigest()[:8].upper()
    layout = (("train", 40, 8, 12), ("selection", 20, 4, 12),
              ("evaluation_candidate_unsealed", 100, 20, 36))
    result = {}
    for part, n_cases, n_vendors, n_products in layout:
        code = {"train": "TRN", "selection": "SEL",
                "evaluation_candidate_unsealed": "EVC"}[part]
        vendors = [f"{code} Synthetic Supplier {tag}-{i:02d}" for i in range(1, n_vendors + 1)]
        products = [f"{code}-{tag}-{i:03d}" for i in range(1, n_products + 1)]
        rows = []
        for idx in range(n_cases):
            pattern, faults = FAULT_PATTERNS[idx % len(FAULT_PATTERNS)]
            lines = []
            for pos, sku in enumerate(rng.sample(products, 3)):
                qty = rng.randint(5, 35)
                price = round(rng.uniform(15, 135), 2)
                promised = date(2025, 10, 1) + timedelta(days=rng.randint(7, 90))
                initial = {"qty": qty, "price": price, "date": promised.isoformat()}
                if (pos, "qty") in faults:
                    initial["qty"] += 4
                if (pos, "price") in faults:
                    initial["price"] = round(price + 5.25, 2)
                if (pos, "date") in faults:
                    initial["date"] = (promised + timedelta(days=5)).isoformat()
                lines.append({
                    "sku": sku, "name": f"synthetic industrial component {sku}",
                    "expected": {"qty": qty, "price": price, "date": promised.isoformat()},
                    "initial": initial,
                })
            rows.append({
                "id": f"{code}-{tag}-{idx + 1:04d}",
                "partition": part,
                "vendor": vendors[idx % n_vendors],
                "pattern": pattern,
                "order_date": "2025-10-01",
                "lines": lines,
            })
        result[part] = rows
    return result


def confirmation(case: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter, invariant=1)
    width, height = letter
    pdf.setTitle(f"{case['id']} synthetic supplier confirmation")
    pdf.setAuthor("EnvLoop benchmark development fixture")
    pdf.setFillColor(colors.HexColor("#17243A"))
    pdf.rect(0, height - 110, width, 110, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(48, height - 58, "SUPPLIER CONFIRMATION")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, height - 82, "SYNTHETIC BENCHMARK DOCUMENT - NOT A REAL COMMERCIAL ORDER")
    pdf.setFillColor(colors.HexColor("#17243A"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48, height - 150, f"RFQ  {case['id']}")
    pdf.drawString(300, height - 150, f"Issued  {case['order_date']}")
    pdf.drawString(48, height - 174, f"Supplier  {case['vendor']}")
    pdf.setFillColor(colors.HexColor("#EAF0F5"))
    pdf.rect(48, height - 225, width - 96, 26, stroke=0, fill=1)
    pdf.setFillColor(colors.HexColor("#17243A"))
    pdf.setFont("Helvetica-Bold", 8)
    for x, label in ((56, "LINE"), (90, "SKU"), (200, "DESCRIPTION"),
                     (390, "QTY"), (430, "UNIT USD"), (495, "PROMISED")):
        pdf.drawString(x, height - 215, label)
    for pos, line in enumerate(case["lines"], 1):
        y = height - 250 - (pos - 1) * 35
        expected = line["expected"]
        pdf.setFont("Helvetica", 8)
        for x, value in ((56, str(pos)), (90, line["sku"]),
                         (200, line["name"].replace("specification", "spec")),
                         (390, str(expected["qty"])),
                         (430, f"{expected['price']:.2f}"), (495, expected["date"])):
            pdf.drawString(x, y, value)
        pdf.setStrokeColor(colors.HexColor("#D5DEE7"))
        pdf.line(48, y - 10, width - 48, y - 10)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, height - 405, "Reconcile only this RFQ with the confirmed line values above.")
    pdf.drawString(48, height - 424, "The reference and supplier identity must stay unchanged.")
    pdf.setFillColor(colors.HexColor("#66788A"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(48, 38, "EnvLoop development-only fixture | Source values: synthetic")
    pdf.save()
    return output.getvalue()


def local_config() -> dict[str, str]:
    env = HERE / ".env"
    if not env.exists():
        raise RuntimeError("Create ignored .env from .env.example before seeding")
    return dict(line.split("=", 1) for line in env.read_text().splitlines() if "=" in line)


class OdooRPC:
    def __init__(self, base_url: str | None = None):
        cfg = local_config()
        if base_url is None:
            base_url = f"http://127.0.0.1:{cfg.get('ODOO_PORT', '8078')}"
        self.password = cfg["ODOO_ADMIN_PASSWORD"]
        common = xmlrpc.client.ServerProxy(base_url + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate("bench", "admin", self.password, {})
        if not self.uid:
            raise RuntimeError("Local Odoo admin authentication failed")
        self.models = xmlrpc.client.ServerProxy(base_url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model: str, method: str, *args, **kwargs):
        return self.models.execute_kw("bench", self.uid, self.password, model, method, list(args), kwargs)


def seed() -> dict:
    rpc = OdooRPC()
    existing = rpc.call("purchase.order", "search", [["origin", "=", "ENVLOOP-DEV"]], limit=1)
    if existing:
        raise RuntimeError("Fixture already exists; restore the baseline instead of double-seeding")
    company = rpc.call("res.company", "search_read", [], fields=["id"], limit=1)[0]
    company_id = company["id"]
    rpc.call("res.company", "write", [company_id], {"name": "Crestview Operations (Synthetic)"})
    usd = rpc.call("res.currency", "search", [["name", "=", "USD"]], limit=1)[0]
    rpc.call("res.company", "write", [company_id], {"currency_id": usd})
    vendor_ids = {}
    for name in VENDORS:
        vendor_ids[name] = rpc.call("res.partner", "create", {
            "name": name, "supplier_rank": 1,
            "comment": "Synthetic benchmark supplier; no real commercial relationship.",
        })
    product_ids = {}
    uom_ids = {}
    for item in catalog():
        product_id = rpc.call("product.product", "create", {
            "name": item["name"], "default_code": item["sku"],
            "type": "consu", "is_storable": True, "purchase_ok": True,
            "sale_ok": True, "standard_price": 12.0, "list_price": 30.0,
        })
        product_ids[item["sku"]] = product_id
        uom_ids[item["sku"]] = rpc.call("product.product", "read", [product_id], fields=["uom_po_id"])[0]["uom_po_id"][0]
    gold = {}
    for case in candidates():
        cmds = []
        for line in case["lines"]:
            initial = line["initial"]
            cmds.append((0, 0, {
                "name": f"{line['sku']} — {line['name']}",
                "product_id": product_ids[line["sku"]],
                "product_uom": uom_ids[line["sku"]],
                "product_qty": initial["qty"],
                "price_unit": initial["price"],
                "date_planned": initial["date"] + " 12:00:00",
            }))
        order_id = rpc.call("purchase.order", "create", {
            "name": case["id"],
            "origin": "ENVLOOP-DEV",
            "partner_id": vendor_ids[case["vendor"]],
            "date_order": case["order_date"] + " 09:00:00",
            "currency_id": usd,
            "order_line": cmds,
        })
        rpc.call("ir.attachment", "create", {
            "name": f"{case['id']}-supplier-confirmation.pdf",
            "description": "Synthetic supplier confirmation for a development candidate",
            "type": "binary", "res_model": "purchase.order", "res_id": order_id,
            "datas": base64.b64encode(confirmation(case)).decode(),
        })
        line_rows = rpc.call("purchase.order.line", "search_read", [["order_id", "=", order_id]],
                             fields=["id", "product_id"], order="id")
        if len(line_rows) != 3:
            raise RuntimeError(f"Expected three lines on {case['id']}")
        gold[case["id"]] = {
            "order_id": order_id,
            "partner_id": vendor_ids[case["vendor"]],
            "state": "draft",
            "lines": [{
                "line_id": row["id"],
                "product_id": product_ids[line["sku"]],
                "expected": line["expected"],
                "initial": line["initial"],
            } for row, line in zip(line_rows, case["lines"])],
        }
    source = SOURCE.read_bytes()
    rpc.call("ir.attachment", "create", {
        "name": "Public-SEC-retailer-companyfacts-excerpt.json",
        "description": (
            "112 unmodified public SEC companyfacts observations for Costco and Walmart. "
            "Historical reference only; all Odoo procurement records are synthetic."
        ),
        "type": "binary", "res_model": "res.company", "res_id": company_id,
        "datas": base64.b64encode(source).decode(),
    })
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "development_gold.json").write_text(json.dumps(gold, indent=2) + "\n")
    repl_gold = seed_replenishment(rpc, product_ids, company_id)
    from multifamily import seed_sales_and_crm
    extra = seed_sales_and_crm(rpc, product_ids, company_id)
    public = {
        "status": "unsealed_development_candidates_not_gui_admitted",
        "application": "Odoo Community 18.0-20260908",
        "synthetic_vendors": len(vendor_ids),
        "synthetic_products": len(product_ids),
        "synthetic_rfqs": len(gold),
        "synthetic_confirmations": len(gold),
        "replenishment_candidates": len(repl_gold),
        **extra,
        "selection_candidates": 20,
        "unsealed_scale_candidates": 100,
        "train_only_generator_candidates_not_deployed": 40,
        "split_audit": split_audit(),
        "official_final_tasks": 0,
        "sec_reference_records": len(json.loads(source)["records"]),
        "sec_reference_sha256": sha256_bytes(source),
        "patterns": {name: sum(c["pattern"] == name for c in candidates()) for name, _ in FAULT_PATTERNS},
        "candidate_ids": [c["id"] for c in candidates()],
    }
    (PRIVATE / "seed_receipt.json").write_text(json.dumps(public, indent=2) + "\n")
    return public


def seed_replenishment(rpc: OdooRPC, product_ids: dict[str, int], company_id: int) -> dict:
    """Seed orderpoint rules after products exist; used by fresh and legacy worlds."""
    warehouse = rpc.call("stock.warehouse", "search_read", [["company_id", "=", company_id]],
                         fields=["id", "lot_stock_id"], limit=1)[0]
    location_id = warehouse["lot_stock_id"][0]
    gold = {}
    for case in replenishment_candidates():
        product_id = product_ids[case["sku"]]
        rpc.call("product.product", "write", [product_id], {"description_purchase": case["source_note"]})
        row_id = rpc.call("stock.warehouse.orderpoint", "create", {
            "product_id": product_id,
            "location_id": location_id,
            "warehouse_id": warehouse["id"],
            "company_id": company_id,
            "product_min_qty": case["initial"]["minimum"],
            "product_max_qty": case["initial"]["maximum"],
            "qty_multiple": 1,
            "trigger": "manual",
        })
        gold[case["id"]] = {
            "rule_id": row_id, "product_id": product_id,
            "location_id": location_id,
            "expected": case["expected"], "initial": case["initial"],
        }
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "replenishment_gold.json").write_text(json.dumps(gold, indent=2) + "\n")
    return gold


if __name__ == "__main__":
    print(json.dumps(seed(), indent=2))
