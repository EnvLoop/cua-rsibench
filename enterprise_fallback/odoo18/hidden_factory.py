"""Evaluator-private Odoo final candidates with unseen causal rules/actions.

The exposed evaluation-candidate pool is permanently development-only. A new
secret seed and these four real business-rule/action changes generate a fresh
hidden pool; no gold or source values belong in researcher-facing artifacts.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from datetime import date, timedelta

from factory import sha256_bytes
from partition_factory import FAMILIES, candidate_world, scale_final_task_sets

HIDDEN_SIGNATURES = {
    "purchase": {"workflow": "purchase", "source": "revision_controlled_supplier_acknowledgement",
                 "decision_rule": "latest_authoritative_revision_over_superseded_ack",
                 "required_actions": "cross_line_reconciliation_plus_vendor_reference"},
    "inventory": {"workflow": "inventory", "source": "product_purchase_service_level_note",
                  "decision_rule": "lead_time_mean_plus_service_factor_demand_range_safety_stock",
                  "required_actions": "compute_and_save_min_max"},
    "sales": {"workflow": "sales", "source": "customer_po_with_quote_expiration",
              "decision_rule": "customer_deadline_controls_quote_expiry",
              "required_actions": "reference_multiline_prices_quantities_and_validity_date"},
    "crm": {"workflow": "crm", "source": "verified_contact_sales_handoff",
            "decision_rule": "verified_contact_supersedes_intake_contact",
            "required_actions": "full_handoff_plus_email_and_phone"},
}


def _rename(value):
    if isinstance(value, str):
        return value.replace("EVC", "HID")
    if isinstance(value, list):
        return [_rename(item) for item in value]
    if isinstance(value, dict):
        return {key: _rename(item) for key, item in value.items()}
    return value


def hidden_candidate_world(hidden_seed: str) -> dict:
    if len(hidden_seed) < 32:
        raise ValueError("A private hidden seed of at least 32 characters is required")
    world = _rename(candidate_world(hidden_seed, "evaluation_candidate"))
    world["split"] = "official_hidden"
    tag = world["namespace"]
    for family in FAMILIES:
        signature = HIDDEN_SIGNATURES[family]
        template_hash = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()[:16]
        for index, case in enumerate(world["cases"][family]):
            case["id"] = case["id"].replace("-HID-", f"-HID-{tag}-", 1)
            case.update({"partition": "official_hidden", "hidden_variant": "causal_v2",
                         "template_signature": signature,
                         "template_group": f"odoo-causal-{template_hash}",
                         "instance_group": f"odoo-instance-{tag}-hidden-{family}-{index + 1:04d}"})

    for index, case in enumerate(world["cases"]["purchase"]):
        reference = f"VR-HID-{tag}-{index + 1:04d}"
        case["vendor_reference"] = reference
        case["initial_vendor_reference"] = f"DRAFT-{reference}"
        case["revision_rule"] = {"superseded": "A", "authoritative": "B"}
        case["prompt"] = (
            f"In Purchase, inspect the revision-controlled supplier acknowledgement attached "
            f"to RFQ {case['id']}. Revision A is superseded; Revision B governs. Reconcile its "
            "three line quantities and unit prices to Revision B and set the vendor reference "
            "printed there. Preserve promised dates, vendor, RFQ state, source and unrelated records."
        )

    for index, case in enumerate(world["cases"]["inventory"]):
        params = case["formula_inputs"]
        weeks = params["weeks"]
        lead_weeks = params["lead_days"] / 7
        service_factor = (1.0, 1.25, 1.5, 1.75)[index % 4]
        mean = sum(weeks) / 4
        demand_range = max(weeks) - min(weeks)
        minimum = math.ceil(mean * lead_weeks
                            + service_factor * demand_range * math.sqrt(lead_weeks))
        minimum += params["safety_stock"]
        maximum = minimum + 3 * params["case_pack"]
        params["service_factor"] = service_factor
        params["seasonal_uplift_pct"] = 0
        case["expected"] = {"minimum": minimum, "maximum": maximum}
        case["initial"] = {"minimum": minimum + 3 + index % 3,
                           "maximum": maximum - 3 - index % 3}
        case["source_note"] = (
            "Synthetic service-level planning memo. Four weekly demand counts (oldest to newest): "
            + ", ".join(map(str, weeks)) + ". "
            f"Supplier lead time: {params['lead_days']} days. Safety stock floor: "
            f"{params['safety_stock']} units. Case pack: {params['case_pack']} units. "
            f"Approved service factor: {service_factor:.2f}. "
            "Minimum = ceil(mean weekly demand x lead weeks + service factor x "
            "(maximum weekly count - minimum weekly count) x sqrt(lead weeks)) "
            "+ safety stock floor. Maximum = minimum + three case packs. "
            "Use this variability policy, not an earlier seasonal-weighted forecast."
        )
        case["prompt"] = (
            f"In Inventory, read the approved service-level Purchase planning memo for "
            f"{case['sku']}. Calculate and save its WH/Stock replenishment minimum and maximum "
            "under the stated variability policy. Preserve the memo and all unrelated records."
        )

    for index, case in enumerate(world["cases"]["sales"]):
        expiration = date(2027, 1, 15) + timedelta(days=index * 3)
        case["expiration_date"] = expiration.isoformat()
        case["initial_expiration_date"] = (expiration + timedelta(days=14)).isoformat()
        case["prompt"] = (
            f"In Sales, reconcile quotation {case['id']} with the attached customer purchase "
            "order. Correct the customer PO reference and all mismatched line quantities and "
            "prices, then set the quotation expiration to the customer deadline stated in "
            "the PO. Preserve discounts, customer, draft state, source and unrelated records."
        )

    for index, case in enumerate(world["cases"]["crm"]):
        verified_email = f"contact-{tag.lower()}-{index + 1:03d}@example.invalid"
        verified_phone = f"+1 555 01{index + 1:02d}"
        case["expected"].update({"email_from": verified_email, "phone": verified_phone})
        case["initial"].update({
            "email_from": f"intake-{tag.lower()}-{index + 1:03d}@example.invalid",
            "phone": f"+1 555 09{index + 1:02d}"})
        case["prompt"] = (
            f"In CRM, follow the verified sales handoff for opportunity {case['id']}. "
            "Reconcile stage, assigned salesperson, forecast revenue, closing date and "
            "priority, and replace the unverified intake email and phone with the confirmed "
            "contact channels. Preserve customer, notes, source and unrelated opportunities."
        )
    return world


def _document(title: str, case: dict, sections: list[tuple[str, list[str]]]) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter, invariant=1)
    pdf.setTitle(f"{case['id']} synthetic {title.lower()}")
    pdf.setAuthor("EnvLoop original synthetic benchmark fixture")
    pdf.setFillColorRGB(0.06, 0.12, 0.20)
    pdf.rect(0, 700, 612, 92, stroke=0, fill=1)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(42, 751, title)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42, 729, "SYNTHETIC BENCHMARK DOCUMENT - NOT A REAL BUSINESS RECORD")
    pdf.setFillColorRGB(0.06, 0.12, 0.20)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(42, 680, f"Case {case['id']}")
    y = 650
    for heading, lines in sections:
        pdf.setFillColorRGB(0.89, 0.93, 0.97)
        pdf.rect(42, y - 4, 528, 23, stroke=0, fill=1)
        pdf.setFillColorRGB(0.06, 0.12, 0.20)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y + 4, heading)
        y -= 28
        pdf.setFont("Helvetica", 8.5)
        for line in lines:
            pdf.drawString(50, y, line[:112])
            y -= 17
        y -= 13
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42, 38, "Source facts: original synthetic EnvLoop fixture | Follow current approved section")
    pdf.save()
    return output.getvalue()


def hidden_source_asset(case: dict, world: dict) -> bytes:
    family = case["family"]
    if family == "inventory":
        return case["source_note"].encode()
    if family == "purchase":
        old = [f"{line['sku']} | qty {line['initial']['qty']} | USD {line['initial']['price']:.2f}"
               for line in case["lines"]]
        current = [f"{line['sku']} | qty {line['expected']['qty']} | USD {line['expected']['price']:.2f}"
                   for line in case["lines"]]
        return _document("SUPPLIER ACKNOWLEDGEMENT", case, [
            ("Revision A - SUPERSEDED", ["Do not use this superseded acknowledgement.", *old]),
            ("Revision B - CURRENT / APPROVED", [
                f"Vendor reference: {case['vendor_reference']}",
                "Revision B replaces all Revision A line values.", *current]),
            ("Dispatch note", ["Preserve the existing promised dates and supplier identity."]),
        ])
    if family == "sales":
        lines = [f"{line['sku']} | qty {line['expected']['qty']} | USD {line['expected']['price']:.2f}"
                 for line in case["lines"]]
        return _document("CUSTOMER PURCHASE ORDER", case, [
            ("Commercial control", [f"Customer PO reference: {case['customer_reference']}",
                                    f"Quotation must expire: {case['expiration_date']}",
                                    "The customer deadline controls quotation validity."]),
            ("Approved line schedule", lines),
            ("Preservation", ["Existing line discounts and customer identity remain in force."]),
        ])
    if family == "crm":
        expected = case["expected"]
        return _document("VERIFIED SALES HANDOFF", case, [
            ("Pipeline decision", [
                f"Stage: {expected['stage_name']}",
                f"Owner: {world['salespeople'][expected['salesperson_index']]}",
                f"Forecast revenue: USD {expected['revenue']:,.2f}",
                f"Expected closing: {expected['deadline']}",
                f"Priority: { {'1':'Medium','2':'High','3':'Very High'}[expected['priority']] }",
            ]),
            ("Verified contact channels", [
                f"Email: {expected['email_from']}", f"Phone: {expected['phone']}",
                "These verified channels supersede the initial intake values.",
            ]),
        ])
    raise ValueError("Unknown hidden source family")


def hidden_task_sets(train_seed: str, hidden_seed: str) -> dict[str, list[dict]]:
    from partition_factory import source_asset, validate_scale_splits

    ordinary = scale_final_task_sets(train_seed)
    world = hidden_candidate_world(hidden_seed)
    official = []
    for family in FAMILIES:
        for case in world["cases"][family]:
            asset = source_asset(case, world)
            source_hash = sha256_bytes(asset)
            package_hash = sha256_bytes(json.dumps(case, sort_keys=True).encode() + b"\n" + asset)
            official.append({"task_id": case["id"], "package_sha256": package_hash,
                             "source_groups": [f"odoo-source-{source_hash}"],
                             "template_group": case["template_group"],
                             "instance_group": case["instance_group"]})
    task_sets = {"train": ordinary["train"], "selection": ordinary["selection"],
                 "official": official}
    validate_scale_splits(task_sets)
    return task_sets


def hidden_split_audit(train_seed: str, hidden_seed: str) -> dict:
    from partition_factory import source_asset

    worlds = {"train": candidate_world(train_seed, "train"),
              "selection": candidate_world(train_seed, "selection"),
              "exposed_development_evaluation": candidate_world(train_seed, "evaluation_candidate"),
              "official_hidden": hidden_candidate_world(hidden_seed)}
    dims = {}
    for name, world in worlds.items():
        cases = [case for family in FAMILIES for case in world["cases"][family]]
        dims[name] = {
            "task_ids": {case["id"] for case in cases},
            "partners": set(world["vendors"] + world["customers"]),
            "skus": {item["sku"] for item in world["products"]},
            "salespeople": set(world["salespeople"]),
            "source_sha256": {sha256_bytes(source_asset(case, world)) for case in cases},
            "template_groups": {case["template_group"] for case in cases},
            "causal_signatures": {json.dumps(case["template_signature"], sort_keys=True)
                                  for case in cases},
            "instance_groups": {case["instance_group"] for case in cases},
        }
    hidden = dims["official_hidden"]
    overlaps = {name: {key: len(values[key] & hidden[key]) for key in hidden}
                for name, values in dims.items() if name != "official_hidden"}
    return {"hidden_candidate_cases": 100,
            "hidden_causal_signatures": HIDDEN_SIGNATURES,
            "overlap_with_hidden": overlaps,
            "strict_identity_source_template_disjoint": all(
                value == 0 for group in overlaps.values() for value in group.values()),
            "development_pool_quarantined": True}
