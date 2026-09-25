"""Four-family, entity-disjoint Odoo candidate worlds.

The master seed and complete case manifests remain local and ignored by Git.
This factory does not admit tasks: admission requires a separate per-case GUI,
negative-control, persisted-state and cold-reset receipt.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import math
import random
import secrets
from datetime import date, timedelta

from factory import (CATALOG, CODE_DIR, PRIVATE, SOURCE, OdooRPC,
                     confirmation, sha256_bytes)
from multifamily import attach, crm_pdf, sales_pdf

SPLIT_COUNTS = {"train": 5, "selection": 5, "evaluation_candidate": 25}
FAMILIES = ("purchase", "inventory", "sales", "crm")
PREFIX = {"train": "TRN", "selection": "SEL", "evaluation_candidate": "EVC"}
ROLE_GROUP_XMLIDS = ("base.group_user", "purchase.group_purchase_user",
                     "stock.group_stock_manager",
                     "sales_team.group_sale_salesman_all_leads")
# Odoo Community's pinned purchase form exposes quantity and unit price in the
# editable native RFQ line grid. Promised date is preserved by the oracle, but
# excluded from candidate repairs until a native GUI date editor is qualified.
EVALUATION_PURCHASE_FAULTS = (
    ("two-line-prices", ((0, "price"), (2, "price"))),
    ("two-line-quantities", ((0, "qty"), (2, "qty"))),
    ("cross-line-quantity-and-price", ((1, "qty"), (2, "price"))),
    ("cross-line-price-and-quantity", ((0, "price"), (1, "qty"))),
    ("three-line-price-quantity-price", ((0, "price"), (1, "qty"), (2, "price"))),
    ("three-line-quantity-price-quantity", ((0, "qty"), (1, "price"), (2, "qty"))),
    ("two-line-full-repair", ((0, "price"), (0, "qty"), (2, "price"), (2, "qty"))),
    ("three-line-full-repair", ((0, "price"), (1, "qty"), (1, "price"),
                                (2, "qty"), (2, "price"))),
)

TEMPLATE_SIGNATURES = {
    "purchase": {
        "train": {"source": "supplier_confirmation_pdf", "target": "single_line_unit_price"},
        "selection": {"source": "supplier_confirmation_pdf", "target": "same_line_price_and_quantity"},
        "evaluation_candidate": {"source": "supplier_confirmation_pdf",
                                 "target": "cross_line_two_or_three_line_reconciliation"},
    },
    "inventory": {
        "train": {"source": "product_purchase_planning_note", "formula": "mean_weekly_demand"},
        "selection": {"source": "product_purchase_planning_note", "formula": "peak_weekly_demand"},
        "evaluation_candidate": {"source": "product_purchase_planning_note",
                                 "formula": "weighted_recent_demand_with_seasonal_uplift"},
    },
    "sales": {
        "train": {"source": "customer_po_pdf", "target": "reference_plus_single_price"},
        "selection": {"source": "customer_po_pdf", "target": "reference_plus_single_quantity"},
        "evaluation_candidate": {"source": "customer_po_pdf",
                                 "target": "reference_plus_cross_line_mixed_faults"},
    },
    "crm": {
        "train": {"source": "opportunity_handoff_pdf", "target": "stage_and_owner"},
        "selection": {"source": "opportunity_handoff_pdf", "target": "revenue_date_priority"},
        "evaluation_candidate": {"source": "opportunity_handoff_pdf",
                                 "target": "stage_owner_revenue_date_priority"},
    },
}


def _identity(family: str, split: str, tag: str, index: int) -> dict:
    signature = {"workflow": family, **TEMPLATE_SIGNATURES[family][split]}
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:16]
    return {"template_signature": signature,
            "template_group": f"odoo-causal-{key}",
            "instance_group": f"odoo-instance-{tag}-{family}-{index + 1:04d}"}


def _rng(master_seed: str, split: str, family: str) -> random.Random:
    digest = hashlib.sha256(f"{master_seed}:{split}:{family}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def candidate_world(master_seed: str, split: str) -> dict:
    """Return exactly 5/5/25 cases per family, with split-specific entities.

    The four workflow applications recur across splits, while the causal
    correction templates differ: simpler train/selection transformations
    cannot share a template group with the final multi-field transfer set.
    The case values, entity identities and source documents differ by split.
    """
    if split not in SPLIT_COUNTS:
        raise ValueError(f"Unknown split: {split}")
    if len(master_seed) < 32:
        raise ValueError("A private seed of at least 32 characters is required")
    count = SPLIT_COUNTS[split]
    code = PREFIX[split]
    tag = hashlib.sha256(f"{master_seed}:{split}:namespace".encode()).hexdigest()[:10].upper()
    product_count = max(32, 4 * count)
    products = []
    for index in range(product_count):
        noun, title = CATALOG[index % len(CATALOG)]
        products.append({"sku": f"EL-{code}-{tag}-{index + 1:03d}",
                         "name": f"{title} / lot {code}-{index + 1:03d}"})
    vendors = [f"{code} Supplier {tag} {i + 1:02d}" for i in range(count)]
    customers = [f"{code} Customer {tag} {i + 1:02d}" for i in range(count)]
    salespeople = [f"{code} Sales {tag} {i + 1:02d}" for i in range(3)]
    cases: dict[str, list[dict]] = {family: [] for family in FAMILIES}

    rng = _rng(master_seed, split, "purchase")
    for index in range(count):
        case_id = f"ELPO-{code}-{index + 1:04d}"
        if split == "train":
            pattern = "single-line-price"
            faults = ((index % 3, "price"),)
        elif split == "selection":
            pattern = "same-line-price-and-quantity"
            faults = ((index % 3, "price"), (index % 3, "qty"))
        else:
            pattern, faults = EVALUATION_PURCHASE_FAULTS[index % len(EVALUATION_PURCHASE_FAULTS)]
        lines = []
        for position, product in enumerate(rng.sample(products, 3)):
            promised = date(2026, 1, 15) + timedelta(days=rng.randint(3, 75))
            expected = {"qty": rng.randint(5, 42),
                        "price": round(rng.uniform(17.50, 218.50), 2),
                        "date": promised.isoformat()}
            initial = dict(expected)
            if (position, "qty") in faults:
                initial["qty"] += rng.choice((3, 4, 6))
            if (position, "price") in faults:
                initial["price"] = round(expected["price"] + rng.choice((3.75, 5.25, 8.50)), 2)
            lines.append({"sku": product["sku"], "name": product["name"],
                          "expected": expected, "initial": initial})
        cases["purchase"].append({
            "id": case_id, "family": "purchase", "partition": split,
            **_identity("purchase", split, tag, index),
            "vendor": vendors[index], "pattern": pattern,
            "order_date": "2026-01-05", "lines": lines,
            "prompt": (f"In Purchase, reconcile RFQ {case_id} against its attached supplier "
                       "confirmation PDF. Correct all mismatched quantities and unit prices "
                       "on the three lines. Preserve promised dates, supplier, RFQ state, "
                       "source document and all unrelated records."),
        })

    rng = _rng(master_seed, split, "inventory")
    for index in range(count):
        case_id = f"ELRP-{code}-{index + 1:04d}"
        product = products[index]
        weeks = [rng.randint(4, 29) for _ in range(4)]
        lead = rng.choice((7, 14, 21, 28))
        safety = rng.randint(2, 12)
        pack = rng.choice((4, 6, 8, 12))
        uplift = (5, 10, 15, 20)[index % 4]
        if split == "train":
            demand_basis = sum(weeks) / 4
            formula = "mean weekly demand"
        elif split == "selection":
            demand_basis = max(weeks)
            formula = "highest of the four weekly counts"
        else:
            weighted = sum((position + 1) * week for position, week in enumerate(weeks)) / 10
            demand_basis = weighted * (100 + uplift) / 100
            formula = ("recency-weighted weekly demand "
                       "(week 1 + 2 x week 2 + 3 x week 3 + 4 x week 4) / 10 "
                       f"with an additional {uplift}% seasonal uplift")
        minimum = math.ceil(demand_basis * lead / 7) + safety
        maximum = minimum + 2 * pack
        cases["inventory"].append({
            "id": case_id, "family": "inventory", "partition": split,
            **_identity("inventory", split, tag, index),
            "sku": product["sku"],
            "formula_inputs": {"weeks": weeks, "lead_days": lead,
                               "safety_stock": safety, "case_pack": pack,
                               "seasonal_uplift_pct": uplift if split == "evaluation_candidate" else 0},
            "source_note": ("Synthetic four-week demand counts: " + ", ".join(map(str, weeks)) +
                            f" units. Supplier lead: {lead} days. Safety stock: {safety} units. "
                            f"Case pack: {pack} units. Planning rule: minimum is ceil({formula} "
                            "x lead days / 7) plus safety stock; maximum is "
                            "minimum plus two case packs."),
            "expected": {"minimum": minimum, "maximum": maximum},
            "initial": {"minimum": minimum + rng.randint(2, 4),
                        "maximum": maximum - rng.randint(2, 4)},
            "prompt": (f"In Inventory, read the Purchase planning note for {product['sku']}; "
                       "calculate and update only its WH/Stock replenishment minimum and "
                       "maximum. Preserve the note, other rules and all other records."),
        })

    rng = _rng(master_seed, split, "sales")
    for index in range(count):
        case_id = f"ELSQ-{code}-{index + 1:04d}"
        lines = []
        picked = rng.sample(products, 3)
        for position, product in enumerate(picked):
            expected = {"qty": rng.randint(3, 38),
                        "price": round(rng.uniform(24, 270), 2),
                        "discount": rng.choice((0, 5, 10, 15))}
            initial = dict(expected)
            if split == "train" and position == index % 3:
                initial["price"] = round(expected["price"] + 4.75, 2)
            elif split == "selection" and position == index % 3:
                initial["qty"] += 2
            elif split == "evaluation_candidate":
                if position == index % 3:
                    initial["qty"] += 2
                elif position == (index + 1) % 3:
                    initial["price"] = round(expected["price"] + 4.75, 2)
                elif index % 4 == 0:
                    initial["qty"] += 1
            lines.append({"sku": product["sku"], "expected": expected, "initial": initial})
        reference = f"CPO-{code}-{tag}-{index + 1:04d}"
        cases["sales"].append({
            "id": case_id, "family": "sales", "partition": split,
            **_identity("sales", split, tag, index),
            "customer": customers[index], "customer_reference": reference,
            "initial_customer_reference": f"DRAFT-{reference}", "lines": lines,
            "prompt": (f"In Sales, reconcile quotation {case_id} with the attached customer "
                       "purchase order PDF. Correct the customer reference and every line "
                       "quantity or price mismatch. Preserve the customer, discounts, quote "
                       "state, source document and unrelated records."),
        })

    rng = _rng(master_seed, split, "crm")
    for index in range(count):
        case_id = f"ELCRM-{code}-{index + 1:04d}"
        closing = (date(2026, 3, 1) + timedelta(days=rng.randint(7, 180))).isoformat()
        expected = {"stage_name": ("Qualified", "Proposition", "Negotiation")[index % 3],
                    "salesperson_index": index % 3,
                    "revenue": float(rng.randrange(12_000, 170_000, 250)),
                    "deadline": closing, "priority": str(1 + index % 3)}
        initial = dict(expected)
        if split in ("train", "evaluation_candidate"):
            initial.update({"stage_name": "New", "salesperson_index": (index + 1) % 3})
        if split in ("selection", "evaluation_candidate"):
            initial.update({"revenue": expected["revenue"] + 1_800,
                            "deadline": (date.fromisoformat(closing)
                                         + timedelta(days=14)).isoformat(),
                            "priority": "0"})
        cases["crm"].append({
            "id": case_id, "family": "crm", "partition": split,
            **_identity("crm", split, tag, index),
            "customer": customers[index], "salesperson_names": salespeople,
            "expected": expected, "initial": initial,
            "prompt": (f"In CRM, follow the attached sales handoff PDF for opportunity {case_id}. "
                       "Repair stage, assigned salesperson, forecast revenue, closing date "
                       "and priority. Preserve customer, notes, source document and all "
                       "unrelated opportunities."),
        })
    return {"split": split, "namespace": tag, "products": products,
            "vendors": vendors, "customers": customers, "salespeople": salespeople,
            "cases": cases}


def split_audit(master_seed: str) -> dict:
    worlds = {part: candidate_world(master_seed, part) for part in SPLIT_COUNTS}
    identifiers = {}
    for part, world in worlds.items():
        rows = [case for family in FAMILIES for case in world["cases"][family]]
        source_hashes = {sha256_bytes(source_asset(case, world)) for case in rows}
        identifiers[part] = {
            "ids": {case["id"] for case in rows},
            "partners": set(world["vendors"] + world["customers"]),
            "skus": {row["sku"] for row in world["products"]},
            "source_names": {f"{case['id']}-source.pdf" for case in rows
                             if case["family"] != "inventory"},
            "source_notes": {case["source_note"] for case in world["cases"]["inventory"]},
            "source_sha256": source_hashes,
            "salespeople": set(world["salespeople"]),
            "template_groups": {case["template_group"] for case in rows},
            "causal_signatures": {json.dumps(case["template_signature"], sort_keys=True)
                                  for case in rows},
            "instance_groups": {case["instance_group"] for case in rows},
        }
    overlaps = {}
    parts = list(SPLIT_COUNTS)
    for index, left in enumerate(parts):
        for right in parts[index + 1:]:
            overlaps[f"{left}:{right}"] = {
                key: len(identifiers[left][key] & identifiers[right][key])
                for key in identifiers[left]
            }
    return {"family_counts": {part: {family: len(world["cases"][family])
                                    for family in FAMILIES} for part, world in worlds.items()},
            "overlaps": overlaps,
            "entity_disjoint": all(value == 0 for pair in overlaps.values()
                                   for value in pair.values()),
            "template_generalization": "held_out_causal_templates_within_four_workflows",
            "template_signatures": {
                part: {family: TEMPLATE_SIGNATURES[family][part] for family in FAMILIES}
                for part in SPLIT_COUNTS}}


def source_asset(case: dict, world: dict) -> bytes:
    if case["family"] == "purchase":
        return confirmation(case)
    if case["family"] == "inventory":
        return case["source_note"].encode()
    if case["family"] == "sales":
        return sales_pdf(case)
    if case["family"] == "crm":
        return crm_pdf(case, world["salespeople"])
    raise ValueError("Unknown task family")


def scale_final_task_sets(master_seed: str) -> dict[str, list[dict]]:
    """Expose exact identity rows for the existing v0.6 split validator.

    This proves only split identity invariants, never GUI qualification.
    """
    out = {"train": [], "selection": [], "official": []}
    for split in SPLIT_COUNTS:
        world = candidate_world(master_seed, split)
        destination = "official" if split == "evaluation_candidate" else split
        for family in FAMILIES:
            for case in world["cases"][family]:
                asset = source_asset(case, world)
                source_hash = sha256_bytes(asset)
                package_hash = sha256_bytes(
                    json.dumps(case, sort_keys=True).encode() + b"\n" + asset)
                out[destination].append({
                    "task_id": case["id"], "package_sha256": package_hash,
                    "source_groups": [f"odoo-source-{source_hash}"],
                    "template_group": case["template_group"],
                    "instance_group": case["instance_group"],
                })
    return out


def validate_scale_splits(task_sets: dict[str, list[dict]]) -> None:
    validator = CODE_DIR.parents[1] / "src/cursibench/scale_final_v06.py"
    spec = importlib.util.spec_from_file_location("odoo_scale_final_v06", validator)
    if spec is None or spec.loader is None:
        raise RuntimeError("Existing v0.6 split validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if len(module.validate_splits(task_sets)) != 100:
        raise RuntimeError("v0.6 split validator did not accept the 100 identities")


def _xml_group(rpc: OdooRPC, module: str, name: str) -> int:
    rows = rpc.call("ir.model.data", "search_read",
                    [["module", "=", module], ["name", "=", name]],
                    fields=["res_id"], limit=1)
    if not rows:
        raise RuntimeError(f"Missing Odoo ACL group {module}.{name}")
    return rows[0]["res_id"]


def seed_partition(split: str, master_seed: str) -> dict:
    """Seed one fresh Compose project; save complete oracle only under private/."""
    world = candidate_world(master_seed, split)
    count = SPLIT_COUNTS[split]
    audit = split_audit(master_seed)
    if not audit["entity_disjoint"]:
        raise RuntimeError("Partition entity overlap")
    rpc = OdooRPC()
    company_id = rpc.call("res.company", "search_read", [], fields=["id"], limit=1)[0]["id"]
    rpc.call("res.company", "write", [company_id], {"name": "Crestview Operations (Synthetic)"})
    usd = rpc.call("res.currency", "search", [["name", "=", "USD"]], limit=1)[0]
    rpc.call("res.company", "write", [company_id], {"currency_id": usd})
    vendors = {name: rpc.call("res.partner", "create", {
        "name": name, "supplier_rank": 1,
        "comment": "Synthetic benchmark supplier; no real commercial relationship."})
        for name in world["vendors"]}
    customers = {name: rpc.call("res.partner", "create", {
        "name": name, "is_company": True,
        "comment": "Synthetic benchmark customer; no real commercial relationship."})
        for name in world["customers"]}
    products = {}
    uoms = {}
    for item in world["products"]:
        product_id = rpc.call("product.product", "create", {
            "name": item["name"], "default_code": item["sku"],
            "type": "consu", "is_storable": True, "purchase_ok": True,
            "sale_ok": True, "standard_price": 12.0, "list_price": 30.0})
        products[item["sku"]] = product_id
        uoms[item["sku"]] = rpc.call("product.product", "read", [product_id],
                                      fields=["uom_po_id"])[0]["uom_po_id"][0]

    group_ids = [_xml_group(rpc, *xmlid.split(".", 1)) for xmlid in ROLE_GROUP_XMLIDS]
    admin_group = _xml_group(rpc, "base", "group_system")
    actor_password = secrets.token_urlsafe(32)
    actor_login = f"envloop.actor.{PREFIX[split].lower()}.{world['namespace'].lower()}@example.invalid"
    actor_id = rpc.call("res.users", "create", {
        "name": f"{PREFIX[split]} Benchmark Operator", "login": actor_login,
        "email": f"benchmark-operator-{PREFIX[split].lower()}@example.invalid",
        "password": actor_password, "company_id": company_id,
        "company_ids": [(6, 0, [company_id])], "groups_id": [(6, 0, group_ids)]})
    actor_groups = rpc.call("res.users", "read", [actor_id], fields=["groups_id"])[0]["groups_id"]
    if admin_group in actor_groups or not set(group_ids).issubset(actor_groups):
        raise RuntimeError("Role-scoped actor ACL failed closed")
    salespeople = []
    for name in world["salespeople"]:
        salespeople.append(rpc.call("res.users", "create", {
            "name": name, "login": f"envloop.sales.{PREFIX[split].lower()}.{len(salespeople)+1}@example.invalid",
            "password": secrets.token_urlsafe(32), "company_id": company_id,
            "company_ids": [(6, 0, [company_id])],
            "groups_id": [(6, 0, [_xml_group(rpc, "base", "group_user"),
                                    _xml_group(rpc, "sales_team", "group_sale_salesman")])] }))
    stage_ids = {}
    for name in ("New", "Qualified", "Proposition", "Negotiation"):
        found = rpc.call("crm.stage", "search", [["name", "=", name]], limit=1)
        stage_ids[name] = found[0] if found else rpc.call("crm.stage", "create", {"name": name})
    warehouse = rpc.call("stock.warehouse", "search_read", [["company_id", "=", company_id]],
                         fields=["id", "lot_stock_id"], limit=1)[0]
    location_id = warehouse["lot_stock_id"][0]
    purchase_gold, inventory_gold, sales_gold, crm_gold = {}, {}, {}, {}
    source_hashes = {}

    for case in world["cases"]["purchase"]:
        commands = []
        for line in case["lines"]:
            initial = line["initial"]
            commands.append((0, 0, {
                "name": f"{line['sku']} - {line['name']}",
                "product_id": products[line["sku"]], "product_uom": uoms[line["sku"]],
                "product_qty": initial["qty"], "price_unit": initial["price"],
                "date_planned": initial["date"] + " 12:00:00"}))
        order_id = rpc.call("purchase.order", "create", {
            "name": case["id"], "origin": "ENVLOOP-DEV",
            "partner_id": vendors[case["vendor"]],
            "date_order": case["order_date"] + " 09:00:00",
            "currency_id": usd, "order_line": commands})
        pdf = confirmation(case)
        attach(rpc, "purchase.order", order_id, f"{case['id']}-source.pdf", pdf)
        source_hashes[case["id"]] = sha256_bytes(pdf)
        rows = rpc.call("purchase.order.line", "search_read", [["order_id", "=", order_id]],
                        fields=["id"], order="id")
        if len(rows) != 3:
            raise RuntimeError(f"Incorrect purchase line count: {case['id']}")
        purchase_gold[case["id"]] = {"order_id": order_id,
            "partner_id": vendors[case["vendor"]], "state": "draft",
            "lines": [{"line_id": row["id"], "product_id": products[line["sku"]],
                       "expected": line["expected"], "initial": line["initial"]}
                      for row, line in zip(rows, case["lines"])]}

    for case in world["cases"]["inventory"]:
        product_id = products[case["sku"]]
        rpc.call("product.product", "write", [product_id],
                 {"description_purchase": case["source_note"]})
        rule_id = rpc.call("stock.warehouse.orderpoint", "create", {
            "product_id": product_id, "location_id": location_id,
            "warehouse_id": warehouse["id"], "company_id": company_id,
            "product_min_qty": case["initial"]["minimum"],
            "product_max_qty": case["initial"]["maximum"],
            "qty_multiple": 1, "trigger": "manual"})
        inventory_gold[case["id"]] = {"rule_id": rule_id, "product_id": product_id,
            "location_id": location_id, "expected": case["expected"],
            "initial": case["initial"]}
        source_hashes[case["id"]] = sha256_bytes(case["source_note"].encode())

    for case in world["cases"]["sales"]:
        commands = [(0, 0, {
            "product_id": products[line["sku"]],
            "product_uom_qty": line["initial"]["qty"],
            "price_unit": line["initial"]["price"],
            "discount": line["initial"]["discount"]}) for line in case["lines"]]
        order_id = rpc.call("sale.order", "create", {
            "name": case["id"], "origin": "ENVLOOP-SALES-DEV",
            "partner_id": customers[case["customer"]],
            "client_order_ref": case["initial_customer_reference"],
            "order_line": commands})
        pdf = sales_pdf(case)
        attach(rpc, "sale.order", order_id, f"{case['id']}-source.pdf", pdf)
        source_hashes[case["id"]] = sha256_bytes(pdf)
        rows = rpc.call("sale.order.line", "search_read", [["order_id", "=", order_id]],
                        fields=["id"], order="id")
        if len(rows) != 3:
            raise RuntimeError(f"Incorrect sales line count: {case['id']}")
        sales_gold[case["id"]] = {"order_id": order_id,
            "customer_id": customers[case["customer"]],
            "customer_reference": case["customer_reference"],
            "lines": [{"line_id": row["id"], "product_id": products[line["sku"]],
                       "expected": line["expected"]}
                      for row, line in zip(rows, case["lines"])]}

    for case in world["cases"]["crm"]:
        initial = case["initial"]
        lead_id = rpc.call("crm.lead", "create", {
            "name": case["id"], "type": "opportunity",
            "partner_id": customers[case["customer"]],
            "description": "Synthetic intake: preserve this original opportunity note.",
            "stage_id": stage_ids[initial["stage_name"]],
            "user_id": salespeople[initial["salesperson_index"]],
            "expected_revenue": initial["revenue"],
            "date_deadline": initial["deadline"], "priority": initial["priority"]})
        pdf = crm_pdf(case, world["salespeople"])
        attach(rpc, "crm.lead", lead_id, f"{case['id']}-source.pdf", pdf)
        source_hashes[case["id"]] = sha256_bytes(pdf)
        expected = case["expected"]
        crm_gold[case["id"]] = {"lead_id": lead_id,
            "customer_id": customers[case["customer"]],
            "expected": {"stage_id": stage_ids[expected["stage_name"]],
                         "user_id": salespeople[expected["salesperson_index"]],
                         "revenue": expected["revenue"],
                         "deadline": expected["deadline"],
                         "priority": expected["priority"]}}

    sec = SOURCE.read_bytes()
    attach(rpc, "res.company", company_id,
           "Public-SEC-retailer-companyfacts-excerpt.json", sec)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    task_set_manifest = scale_final_task_sets(master_seed)
    validate_scale_splits(task_set_manifest)
    for filename, payload in (("development_gold.json", purchase_gold),
                              ("replenishment_gold.json", inventory_gold),
                              ("sales_gold.json", sales_gold),
                              ("crm_gold.json", crm_gold),
                              ("partition_cases.json", world),
                              ("source_hashes.json", source_hashes),
                              ("task_set_manifest.json", task_set_manifest)):
        path = PRIVATE / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)
    credentials_path = PRIVATE / "actor_credentials.json"
    credentials_path.write_text(json.dumps({"login": actor_login,
                                            "password": actor_password}) + "\n")
    credentials_path.chmod(0o600)
    expected_counts = {
        "orders": count, "lines": 3 * count,
        "attachments": 3 * count + 1,
        "vendors": count, "products": len(products), "orderpoints": count,
        "sales_orders": count, "sales_lines": 3 * count, "crm_leads": count,
        "customers": count, "salespeople": 4,
        "global_business_identity": 15,
    }
    role_policy = {"required_group_xmlids": list(ROLE_GROUP_XMLIDS),
                   "forbidden_group_xmlids": ["base.group_system"],
                   "email_domain": "example.invalid"}
    pinned_files = {name: sha256_bytes((CODE_DIR / name).read_bytes())
                    for name in ("bootstrap.py", "create_partition_worlds.py",
                                 "partition_factory.py", "verify.py", "reset.py",
                                 "gui_controls.py", "sweep_partition.py",
                                 "worker_lease.py", "audit_partition_receipts.py",
                                 "record_train_trace.py",
                                 "compose.yaml")}
    receipt = {"schema": "envloop-odoo-partition-candidate-v1",
        "status": "seeded_unsealed_candidate_not_gui_admitted",
        "partition": split, "source_type": "synthetic_operational_plus_public_sec_reference",
        "master_seed_sha256": sha256_bytes(master_seed.encode()),
        "case_manifest_sha256": sha256_bytes(json.dumps(world, sort_keys=True).encode()),
        "source_hash_manifest_sha256": sha256_bytes(json.dumps(source_hashes, sort_keys=True).encode()),
        "task_set_manifest_sha256": sha256_bytes(json.dumps(task_set_manifest, sort_keys=True).encode()),
        "role_policy_sha256": sha256_bytes(json.dumps(role_policy, sort_keys=True).encode()),
        "pinned_code_and_runtime_sha256": pinned_files,
        "sec_reference_sha256": sha256_bytes(sec),
        "entity_disjoint_audit": audit,
        "family_counts": {family: len(world["cases"][family]) for family in FAMILIES},
        "expected_snapshot_counts": expected_counts,
        "actor_id": actor_id,
        "actor_role_group_ids": group_ids,
        "actor_administrator_group_absent": admin_group not in actor_groups,
        "official_final_tasks_admitted": 0}
    (PRIVATE / "partition_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
