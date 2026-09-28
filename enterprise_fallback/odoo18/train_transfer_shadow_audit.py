"""Offline Odoo SQL-verifier shadow controls for staged TRAIN analogues.

These are in-memory SQL-shaped states, not screenshots, live PostgreSQL rows,
or proof that the original Odoo GUI can complete the tasks.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from partition_factory import FAMILIES
from train_transfer_analogues import SCHEMA as STAGED_SCHEMA, _hash, _raw, source_bytes
from verify import evaluate, evaluate_crm, evaluate_replenishment, evaluate_sales


SCHEMA = "envloop-odoo-train-transfer-shadow-audit-v1"
GROUPS = ("orders", "lines", "attachments", "vendors", "products", "orderpoints",
          "sales_orders", "sales_lines", "crm_leads", "customers", "salespeople", "crm_stages")


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _blank() -> dict:
    return {name: [] for name in GROUPS}


def _purchase(case: dict) -> tuple[dict, dict, dict, dict]:
    baseline = _blank()
    baseline["orders"] = [
        {"id": 1, "name": case["id"], "partner_ref": case["initial_vendor_reference"],
         "partner_id": 101, "state": "draft"},
        {"id": 2, "name": "unrelated", "partner_ref": "KEEP", "partner_id": 102, "state": "draft"},
    ]
    target_lines = []
    for i, line in enumerate(case["lines"]):
        row = {"id": 10 + i, "order_id": 1, "product_id": 1000 + i,
               "name": line["name"], "qty": str(line["initial"]["qty"]),
               "price": str(line["initial"]["price"]), "date": line["initial"]["date"]}
        baseline["lines"].append(row)
        target_lines.append({"line_id": row["id"], "product_id": row["product_id"],
                             "expected": line["expected"]})
    baseline["lines"].append({"id": 19, "order_id": 2, "product_id": 1119,
                               "name": "unrelated", "qty": "7", "price": "9.50",
                               "date": "2027-01-01"})
    target = {"order_id": 1, "vendor_reference": case["vendor_reference"],
              "lines": target_lines}
    positive = deepcopy(baseline)
    positive["orders"][0]["partner_ref"] = case["vendor_reference"]
    for i, line in enumerate(case["lines"]):
        positive["lines"][i]["qty"] = str(line["expected"]["qty"])
        positive["lines"][i]["price"] = str(line["expected"]["price"])
    near = deepcopy(positive)
    near["orders"][0]["partner_ref"] = case["initial_vendor_reference"]
    unrelated = deepcopy(positive)
    unrelated["orders"][1]["partner_ref"] = "WRONG"
    return target, baseline, positive, {"near": near, "unrelated": unrelated}


def _inventory(case: dict) -> tuple[dict, dict, dict, dict]:
    baseline = _blank()
    baseline["orderpoints"] = [
        {"id": 1, "product_id": 101, "location_id": 3, "warehouse_id": 4,
         "company_id": 5, "multiple": "1", "trigger": "auto",
         "minimum": str(case["initial"]["minimum"]), "maximum": str(case["initial"]["maximum"])},
        {"id": 2, "product_id": 102, "location_id": 3, "warehouse_id": 4,
         "company_id": 5, "multiple": "1", "trigger": "auto",
         "minimum": "12", "maximum": "24"},
    ]
    target = {"rule_id": 1, "expected": case["expected"]}
    positive = deepcopy(baseline)
    positive["orderpoints"][0]["minimum"] = str(case["expected"]["minimum"])
    positive["orderpoints"][0]["maximum"] = str(case["expected"]["maximum"])
    near = deepcopy(positive)
    near["orderpoints"][0]["maximum"] = str(case["initial"]["maximum"])
    unrelated = deepcopy(positive)
    unrelated["orderpoints"][1]["minimum"] = "13"
    return target, baseline, positive, {"near": near, "unrelated": unrelated}


def _sales(case: dict) -> tuple[dict, dict, dict, dict]:
    baseline = _blank()
    baseline["sales_orders"] = [
        {"id": 1, "name": case["id"], "origin": "ENVLOOP-SALES-DEV",
         "partner_id": 101, "state": "draft", "note": "preserve",
         "client_order_ref": case["initial_customer_reference"],
         "validity_date": case["initial_expiration_date"]},
        {"id": 2, "name": "unrelated", "origin": "ENVLOOP-SALES-DEV",
         "partner_id": 102, "state": "draft", "note": "keep",
         "client_order_ref": "KEEP", "validity_date": "2027-06-01"},
    ]
    target_lines = []
    for i, line in enumerate(case["lines"]):
        row = {"id": 10 + i, "order_id": 1, "product_id": 1000 + i,
               "name": line["sku"], "qty": str(line["initial"]["qty"]),
               "price": str(line["initial"]["price"]),
               "discount": str(line["initial"]["discount"])}
        baseline["sales_lines"].append(row)
        target_lines.append({"line_id": row["id"], "expected": line["expected"]})
    baseline["sales_lines"].append({"id": 19, "order_id": 2, "product_id": 1119,
                                    "name": "unrelated", "qty": "7", "price": "9.50",
                                    "discount": "0"})
    target = {"order_id": 1, "customer_reference": case["customer_reference"],
              "expiration_date": case["expiration_date"], "lines": target_lines}
    positive = deepcopy(baseline)
    positive["sales_orders"][0]["client_order_ref"] = case["customer_reference"]
    positive["sales_orders"][0]["validity_date"] = case["expiration_date"]
    for i, line in enumerate(case["lines"]):
        positive["sales_lines"][i]["qty"] = str(line["expected"]["qty"])
        positive["sales_lines"][i]["price"] = str(line["expected"]["price"])
    near = deepcopy(positive)
    near["sales_orders"][0]["validity_date"] = case["initial_expiration_date"]
    unrelated = deepcopy(positive)
    unrelated["sales_orders"][1]["client_order_ref"] = "WRONG"
    return target, baseline, positive, {"near": near, "unrelated": unrelated}


def _crm(case: dict) -> tuple[dict, dict, dict, dict]:
    baseline = _blank()
    names = {"New": 1, "Qualified": 2, "Proposition": 3, "Negotiation": 4}
    original = case["initial"]
    expected = case["expected"]
    baseline["crm_leads"] = [
        {"id": 1, "name": case["id"], "type": "opportunity", "partner_id": 101,
         "team_id": 3, "description": "preserve", "active": True,
         "stage_id": names[original["stage_name"]],
         "user_id": 100 + original["salesperson_index"],
         "revenue": str(original["revenue"]), "deadline": original["deadline"],
         "priority": original["priority"], "email_from": original["email_from"],
         "phone": original["phone"]},
        {"id": 2, "name": "unrelated", "type": "opportunity", "partner_id": 102,
         "team_id": 3, "description": "keep", "active": True,
         "stage_id": 1, "user_id": 111, "revenue": "1500", "deadline": "2027-06-01",
         "priority": "1", "email_from": "keep@example.invalid", "phone": "+1 555 1000"},
    ]
    target_expected = {"stage_id": names[expected["stage_name"]],
                       "user_id": 100 + expected["salesperson_index"],
                       "revenue": expected["revenue"], "deadline": expected["deadline"],
                       "priority": expected["priority"],
                       "email_from": expected["email_from"], "phone": expected["phone"]}
    target = {"lead_id": 1, "expected": target_expected}
    positive = deepcopy(baseline)
    positive["crm_leads"][0].update({k: str(v) if k == "revenue" else v
                                      for k, v in target_expected.items()})
    near = deepcopy(positive)
    near["crm_leads"][0]["email_from"] = original["email_from"]
    unrelated = deepcopy(positive)
    unrelated["crm_leads"][1]["description"] = "WRONG"
    return target, baseline, positive, {"near": near, "unrelated": unrelated}


BUILDERS = {"purchase": (_purchase, evaluate),
            "inventory": (_inventory, evaluate_replenishment),
            "sales": (_sales, evaluate_sales),
            "crm": (_crm, evaluate_crm)}


def audit(staged: dict) -> dict:
    _require(staged.get("schema") == STAGED_SCHEMA and
             staged.get("status") == "offline_train_only_no_gui_or_model_result",
             "not an Odoo train-transfer staging record")
    world = staged["world"]
    _require(set(world["cases"]) == set(FAMILIES) and
             all(len(world["cases"][family]) == 2 for family in FAMILIES),
             "two cases per workflow required")
    counts = {"unsolved_baseline": 0, "positive_pass": 0,
              "near_miss_rejected": 0, "unrelated_change_rejected": 0}
    private_controls = []
    for family in FAMILIES:
        build, score = BUILDERS[family]
        for case in world["cases"][family]:
            target, baseline, positive, negative = build(case)
            source = bytes.fromhex(staged["source_assets_hex"][case["id"]])
            _require(source == source_bytes(case, world), "source asset bytes changed")
            results = {"baseline": score(case["id"], target, baseline, baseline),
                       "positive": score(case["id"], target, baseline, positive),
                       "near": score(case["id"], target, baseline, negative["near"]),
                       "unrelated": score(case["id"], target, baseline, negative["unrelated"])}
            _require([results[k]["reward"] for k in ("baseline", "positive", "near", "unrelated")]
                     == [0.0, 1.0, 0.0, 0.0] and
                     len(results["near"]["difference_codes"]) == 1 and
                     bool(results["unrelated"]["difference_codes"]),
                     "independent Odoo state scorer did not separate shadow controls")
            counts = {key: value + 1 for key, value in counts.items()}
            private_controls.append({"task_id": case["id"], "family": family,
                                     "source_sha256": _hash(source),
                                     "snapshot_bundle_sha256": _hash(_raw({"target": target,
                                         "baseline": baseline, "positive": positive,
                                         "negative": negative})),
                                     "scores": results})
    return {"schema": SCHEMA, "status": "synthetic_state_shadow_controls_passed",
            "staged_sha256": _hash(_raw(staged)), "counts": counts,
            "controls": private_controls, "gui_qualified_count": 0,
            "official_final_admitted": 0, "model_results": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("refusing to overwrite evidence")
    staged = json.loads(args.staged.read_bytes())
    report = audit(staged)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_bytes(_raw(report))
    args.private_out.chmod(0o600)
    public = {key: value for key, value in report.items() if key != "controls"}
    public["private_shadow_audit_sha256"] = _hash(args.private_out.read_bytes())
    public["auditor_source_sha256"] = _hash(Path(__file__).read_bytes())
    public["scoring_scope"] = "in-memory SQL-shaped shadow states; no original Odoo save or reset"
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "case_count": len(report["controls"]),
                      "gui_qualified_count": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
