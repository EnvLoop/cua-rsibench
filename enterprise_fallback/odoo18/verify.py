"""Evaluator-owned PostgreSQL readback for four Odoo development families.

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
         OR (a.res_model = 'sale.order' AND a.res_id IN
              (SELECT id FROM sale_order WHERE origin = 'ENVLOOP-SALES-DEV'))
         OR (a.res_model = 'crm.lead' AND a.res_id IN
              (SELECT id FROM crm_lead WHERE name LIKE 'ELCRM-%'))
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
  ),
  'sales_orders', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT id, name, origin, partner_id, state, client_order_ref, note
      FROM sale_order WHERE origin = 'ENVLOOP-SALES-DEV'
    ) x
  ),
  'sales_lines', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT l.id, l.order_id, l.product_id, l.name,
             l.product_uom_qty::text AS qty, l.price_unit::text AS price,
             l.discount::text AS discount
      FROM sale_order_line l
      JOIN sale_order o ON o.id = l.order_id
      WHERE o.origin = 'ENVLOOP-SALES-DEV'
    ) x
  ),
  'crm_leads', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT id, name, type, partner_id, user_id, team_id, stage_id,
             expected_revenue::text AS revenue,
             to_char(date_deadline, 'YYYY-MM-DD') AS deadline,
             priority, description, active
      FROM crm_lead WHERE name LIKE 'ELCRM-%'
    ) x
  ),
  'customers', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT id, name, is_company, comment, active
      FROM res_partner
      WHERE comment LIKE '%Synthetic benchmark customer%'
    ) x
  ),
  'salespeople', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT u.id, p.name, u.login, u.active, u.company_id
      FROM res_users u JOIN res_partner p ON p.id = u.partner_id
      WHERE u.login LIKE 'envloop.sales.%@example.invalid'
         OR u.login LIKE 'envloop.actor.%@example.invalid'
    ) x
  ),
  'crm_stages', (
    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)
    FROM (
      SELECT id, name::text AS name, sequence, is_won
      FROM crm_stage
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
    partition_receipt = PRIVATE / "partition_receipt.json"
    if partition_receipt.exists():
        expected_counts = json.loads(partition_receipt.read_text())["expected_snapshot_counts"]
        expected_counts["crm_stages"] = counts["crm_stages"]
    else:
        expected_counts = {"orders": 120, "lines": 360, "attachments": 161,
                           "vendors": 24, "products": 48, "orderpoints": 20,
                           "sales_orders": 20, "sales_lines": 60, "crm_leads": 20,
                           "customers": 20, "salespeople": 3,
                           "crm_stages": counts["crm_stages"]}
    if counts["crm_stages"] < 4:
        raise RuntimeError("Expected at least four CRM stages")
    if counts != expected_counts:
        raise RuntimeError(f"Incomplete fixture: {counts}, expected {expected_counts}")
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
    return counts


def evaluate(case_id: str, target: dict, baseline: dict, observed: dict) -> dict:
    differences = []
    for group in ("orders", "attachments", "vendors", "products", "orderpoints",
                  "sales_orders", "sales_lines", "crm_leads", "customers",
                  "salespeople", "crm_stages"):
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
    for group in ("orders", "lines", "attachments", "vendors", "products",
                  "sales_orders", "sales_lines", "crm_leads", "customers",
                  "salespeople", "crm_stages"):
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


def evaluate_sales(case_id: str, target: dict, baseline: dict, observed: dict) -> dict:
    differences = []
    for group in ("orders", "lines", "attachments", "vendors", "products", "orderpoints",
                  "crm_leads", "customers", "salespeople", "crm_stages"):
        if keyed(observed[group]) != keyed(baseline[group]):
            differences.append(f"{group}_changed_or_missing")
    base_orders = keyed(baseline["sales_orders"])
    actual_orders = keyed(observed["sales_orders"])
    if base_orders.keys() != actual_orders.keys():
        differences.append("sales_order_identity_set_changed")
    for order_id, original in base_orders.items():
        current = actual_orders.get(order_id)
        if current is None:
            continue
        if order_id != target["order_id"]:
            if current != original:
                differences.append("unrelated_sales_order_changed")
        else:
            for key in ("name", "origin", "partner_id", "state", "note"):
                if current[key] != original[key]:
                    differences.append("target_sales_order_identity_or_state_changed")
            if current["client_order_ref"] != target["customer_reference"]:
                differences.append("target_customer_reference_mismatch")
    base_lines = keyed(baseline["sales_lines"])
    actual_lines = keyed(observed["sales_lines"])
    if base_lines.keys() != actual_lines.keys():
        differences.append("sales_line_identity_set_changed")
    gold_lines = {line["line_id"]: line for line in target["lines"]}
    for line_id, original in base_lines.items():
        current = actual_lines.get(line_id)
        if current is None:
            continue
        if line_id not in gold_lines:
            if current != original:
                differences.append("unrelated_sales_line_changed")
            continue
        expected = gold_lines[line_id]["expected"]
        for key in ("order_id", "product_id", "name"):
            if current[key] != original[key]:
                differences.append("target_sales_line_identity_changed")
        if float(current["qty"]) != expected["qty"]:
            differences.append("target_sales_quantity_mismatch")
        if round(float(current["price"]), 2) != expected["price"]:
            differences.append("target_sales_price_mismatch")
        if round(float(current["discount"]), 2) != expected["discount"]:
            differences.append("target_sales_discount_mismatch")
    return _result(case_id, differences)


def evaluate_crm(case_id: str, target: dict, baseline: dict, observed: dict) -> dict:
    differences = []
    for group in ("orders", "lines", "attachments", "vendors", "products", "orderpoints",
                  "sales_orders", "sales_lines", "customers", "salespeople", "crm_stages"):
        if keyed(observed[group]) != keyed(baseline[group]):
            differences.append(f"{group}_changed_or_missing")
    base_leads = keyed(baseline["crm_leads"])
    actual_leads = keyed(observed["crm_leads"])
    if base_leads.keys() != actual_leads.keys():
        differences.append("crm_lead_identity_set_changed")
    for lead_id, original in base_leads.items():
        current = actual_leads.get(lead_id)
        if current is None:
            continue
        if lead_id != target["lead_id"]:
            if current != original:
                differences.append("unrelated_crm_opportunity_changed")
            continue
        for key in ("name", "type", "partner_id", "team_id", "description", "active"):
            if current[key] != original[key]:
                differences.append("target_crm_identity_or_note_changed")
        expected = target["expected"]
        for key, code in (("stage_id", "target_crm_stage_mismatch"),
                          ("user_id", "target_crm_salesperson_mismatch"),
                          ("deadline", "target_crm_deadline_mismatch"),
                          ("priority", "target_crm_priority_mismatch")):
            if current[key] != expected[key]:
                differences.append(code)
        if round(float(current["revenue"]), 2) != expected["revenue"]:
            differences.append("target_crm_revenue_mismatch")
    return _result(case_id, differences)


def _result(case_id: str, differences: list[str]) -> dict:
    unique = sorted(set(differences))
    return {"case_id": case_id, "status": "development_control_not_official_final",
            "reward": 1.0 if not unique else 0.0,
            "checks_passed": not unique, "difference_codes": unique}


def protected_source_file_differences(
    baseline: dict, frozen_files: dict[str, str], actual_files: dict[str, str]
) -> list[str]:
    """Compare bytes of source PDFs/SEC JSON, ignoring Odoo's runtime asset cache.

    The pinned Odoo image stores each binary attachment at
    filestore/bench/<first-two-SHA1-chars>/<SHA1>. This was checked for all 161
    source attachments in the frozen development worker. A missing frozen path
    is a fixture error, not a zero score for an actor.
    """
    protected = {f"filestore/bench/{row['checksum'][:2]}/{row['checksum']}"
                 for row in baseline["attachments"]}
    for path in protected:
        if path not in frozen_files:
            raise RuntimeError(f"Frozen attachment file missing: {path}")
    if any(actual_files.get(path) != frozen_files[path] for path in protected):
        return ["protected_source_filestore_changed_or_missing"]
    return []


def protected_source_store_path_differences(
    baseline: dict, actual_paths: dict[str, str]
) -> list[str]:
    for row in baseline["attachments"]:
        expected = f"{row['checksum'][:2]}/{row['checksum']}"
        if actual_paths.get(str(row["id"])) != expected:
            return ["protected_source_store_path_changed_or_missing"]
    return []


def attachment_store_paths(baseline: dict) -> dict[str, str]:
    ids = sorted({int(row["id"]) for row in baseline["attachments"]})
    if not ids:
        raise RuntimeError("No protected source attachments in frozen fixture")
    sql = ("SELECT COALESCE(json_object_agg(id,store_fname)::text,'{}') "
           "FROM ir_attachment WHERE id IN (" + ",".join(map(str, ids)) + ")")
    cmd = ["docker", "compose", "--env-file", ".env", "exec", "-T", "db",
           "psql", "-U", "bench_verify", "-d", "bench", "-At",
           "-v", "ON_ERROR_STOP=1", "-c", sql]
    result = subprocess.run(cmd, cwd=HERE, check=True, capture_output=True, text=True)
    return json.loads(result.stdout.strip())


def include_physical_source_files(result: dict, baseline: dict) -> dict:
    from reset import filestore_manifest
    from factory import local_config

    frozen = json.loads((PRIVATE / "baseline-filestore-manifest.json").read_text())
    project = local_config().get("ODOO_PROJECT", "envloop-odoo-fallback")
    actual = filestore_manifest(project + "_filestore")
    differences = protected_source_file_differences(baseline, frozen, actual)
    differences += protected_source_store_path_differences(
        baseline, attachment_store_paths(baseline)
    )
    if differences:
        result["difference_codes"] = sorted(set(result["difference_codes"] + differences))
        result["reward"] = 0.0
        result["checks_passed"] = False
    result["protected_source_files_checked"] = len({row["checksum"] for row in baseline["attachments"]})
    return result


def score(case_id: str) -> dict:
    if case_id.startswith("ELSQ-"):
        gold = json.loads((PRIVATE / "sales_gold.json").read_text())
        if case_id not in gold:
            raise ValueError(f"Unknown sales case {case_id}")
        baseline = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
        return include_physical_source_files(
            evaluate_sales(case_id, gold[case_id], baseline, snapshot()), baseline
        )
    if case_id.startswith("ELCRM-"):
        gold = json.loads((PRIVATE / "crm_gold.json").read_text())
        if case_id not in gold:
            raise ValueError(f"Unknown CRM case {case_id}")
        baseline = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
        return include_physical_source_files(
            evaluate_crm(case_id, gold[case_id], baseline, snapshot()), baseline
        )
    if case_id.startswith("ELRP-"):
        gold = json.loads((PRIVATE / "replenishment_gold.json").read_text())
        if case_id not in gold:
            raise ValueError(f"Unknown replenishment case {case_id}")
        baseline = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
        return include_physical_source_files(
            evaluate_replenishment(case_id, gold[case_id], baseline, snapshot()), baseline
        )
    gold = json.loads((PRIVATE / "development_gold.json").read_text())
    if case_id not in gold:
        raise ValueError(f"Unknown development case {case_id}")
    baseline = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
    return include_physical_source_files(
        evaluate(case_id, gold[case_id], baseline, snapshot()), baseline
    )


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
