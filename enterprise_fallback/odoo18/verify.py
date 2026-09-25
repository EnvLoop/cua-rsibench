"""Evaluator-owned PostgreSQL readback for the Odoo development RFQ family.

The actor uses the Odoo GUI.  This verifier connects as a SELECT-only database
role, reads persisted rows, and never calls Odoo RPC or trusts browser text.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from factory import HERE, PRIVATE

SQL = r"""
SELECT json_build_object(
  'orders', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT id, name, origin, partner_id, state, currency_id,
             to_char(date_order, 'YYYY-MM-DD HH24:MI:SS') AS date_order
      FROM purchase_order WHERE origin = 'ENVLOOP-DEV'
    ) x
  ),
  'lines', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT l.id, l.order_id, l.product_id, l.name,
             l.product_qty::text AS qty, l.price_unit::text AS price,
             to_char(l.date_planned, 'YYYY-MM-DD') AS date
      FROM purchase_order_line l
      JOIN purchase_order o ON o.id = l.order_id
      WHERE o.origin = 'ENVLOOP-DEV'
    ) x
  ),
  'attachments', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT a.id, a.res_model, a.res_id, a.name, a.checksum, a.file_size
      FROM ir_attachment a
      WHERE (a.res_model = 'purchase.order' AND a.res_id IN
              (SELECT id FROM purchase_order WHERE origin = 'ENVLOOP-DEV'))
         OR a.name = 'Public-SEC-retailer-companyfacts-excerpt.json'
    ) x
  ),
  'vendors', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT id, name, supplier_rank, comment, active
      FROM res_partner
      WHERE comment LIKE '%Synthetic benchmark supplier%'
    ) x
  ),
  'products', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT p.id, p.default_code, t.name, t.type, t.active,
             t.list_price::text AS list_price, t.description_purchase
      FROM product_product p
      JOIN product_template t ON t.id = p.product_tmpl_id
      WHERE p.default_code LIKE 'EL-%'
    ) x
  ),
  'orderpoints', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT r.id, r.product_id, r.location_id, r.warehouse_id, r.company_id,
             r.product_min_qty::text AS minimum,
             r.product_max_qty::text AS maximum,
             r.qty_multiple::text AS multiple, r.trigger
      FROM stock_warehouse_orderpoint r
      JOIN product_product p ON p.id = r.product_id
      WHERE p.default_code LIKE 'EL-%'
    ) x
  )
);
"""


def snapshot() -> dict:
    cmd = [
        "docker", "compose", "--env-file", ".env", "exec", "-T", "db",
        "psql", "-U", "bench_verify", "-d", "bench", "-At",
        "-v", "ON_ERROR_STOP=1", "-c", SQL,
    ]
    result = subprocess.run(cmd, cwd=HERE, check=True, capture_output=True, text=True)
    return json.loads(result.stdout.strip())


def keyed(rows: list[dict]) -> dict[int, dict]:
    return {row["id"]: row for row in rows}


def freeze() -> dict:
    PRIVATE.mkdir(exist_ok=True)
    path = PRIVATE / "baseline_snapshot.json"
    if path.exists():
        raise RuntimeError("Baseline already frozen; do not overwrite after an attempt")
    snap = snapshot()
    counts = {key: len(value) for key, value in snap.items()}
    expected_counts = {"orders": 120, "lines": 360, "attachments": 121,
                       "vendors": 24, "products": 48, "orderpoints": 20}
    if counts != expected_counts:
        raise RuntimeError(f"Incomplete fixture: {counts}, expected {expected_counts}")
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
    return counts


def evaluate(case_id: str, target: dict, baseline: dict, observed: dict) -> dict:
    differences = []
    for group in ("orders", "attachments", "vendors", "products", "orderpoints"):
        if keyed(observed[group]) != keyed(baseline[group]):
            differences.append(f"{group}_changed_or_missing")
    baseline_lines = keyed(baseline["lines"])
    observed_lines = keyed(observed["lines"])
    if baseline_lines.keys() != observed_lines.keys():
        differences.append("line_identity_set_changed")
    target_ids = {line["line_id"] for line in target["lines"]}
    for line_id, reference in baseline_lines.items():
        current = observed_lines.get(line_id)
        if current is None:
            continue
        if line_id not in target_ids:
            if current != reference:
                differences.append("unrelated_order_line_changed")
            continue
        gold_line = next(row for row in target["lines"] if row["line_id"] == line_id)
        if current["product_id"] != gold_line["product_id"] or current["name"] != reference["name"]:
            differences.append("target_line_identity_or_description_changed")
        expected = gold_line["expected"]
        if float(current["qty"]) != expected["qty"]:
            differences.append("target_quantity_mismatch")
        if round(float(current["price"]), 2) != expected["price"]:
            differences.append("target_unit_price_mismatch")
        if current["date"] != expected["date"]:
            differences.append("target_promised_date_mismatch")
    differences = sorted(set(differences))
    return {
        "case_id": case_id,
        "status": "development_control_not_official_final",
        "reward": 1.0 if not differences else 0.0,
        "checks_passed": not differences,
        "difference_codes": differences,
    }


def evaluate_replenishment(case_id: str, target: dict, baseline: dict, observed: dict) -> dict:
    differences = []
    for group in ("orders", "lines", "attachments", "vendors", "products"):
        if keyed(observed[group]) != keyed(baseline[group]):
            differences.append(f"{group}_changed_or_missing")
    base_rules = keyed(baseline["orderpoints"])
    actual_rules = keyed(observed["orderpoints"])
    if base_rules.keys() != actual_rules.keys():
        differences.append("replenishment_rule_identity_set_changed")
    for rule_id, original in base_rules.items():
        current = actual_rules.get(rule_id)
        if current is None:
            continue
        if rule_id != target["rule_id"]:
            if current != original:
                differences.append("unrelated_replenishment_rule_changed")
            continue
        for key in ("product_id", "location_id", "warehouse_id", "company_id", "multiple", "trigger"):
            if current[key] != original[key]:
                differences.append("target_rule_identity_or_policy_changed")
        if float(current["minimum"]) != target["expected"]["minimum"]:
            differences.append("target_minimum_mismatch")
        if float(current["maximum"]) != target["expected"]["maximum"]:
            differences.append("target_maximum_mismatch")
    differences = sorted(set(differences))
    return {
        "case_id": case_id,
        "status": "development_control_not_official_final",
        "reward": 1.0 if not differences else 0.0,
        "checks_passed": not differences,
        "difference_codes": differences,
    }


def score(case_id: str) -> dict:
    if case_id.startswith("ELRP-"):
        gold = json.loads((PRIVATE / "replenishment_gold.json").read_text())
        if case_id not in gold:
            raise ValueError(f"Unknown replenishment case {case_id}")
        baseline = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
        return evaluate_replenishment(case_id, gold[case_id], baseline, snapshot())
    gold = json.loads((PRIVATE / "development_gold.json").read_text())
    if case_id not in gold:
        raise ValueError(f"Unknown development case {case_id}")
    baseline = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
    return evaluate(case_id, gold[case_id], baseline, snapshot())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "score"])
    parser.add_argument("case_id", nargs="?")
    args = parser.parse_args()
    if args.action == "freeze":
        print(json.dumps(freeze(), indent=2))
    else:
        if not args.case_id:
            parser.error("score requires a case ID")
        print(json.dumps(score(args.case_id), indent=2))
