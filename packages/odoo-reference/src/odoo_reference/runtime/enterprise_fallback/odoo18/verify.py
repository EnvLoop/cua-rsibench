"""Public TRAIN persisted SQL verifier. SELECT-only, no actor/API scoring."""
import json,subprocess
from decimal import Decimal,InvalidOperation
from factory import HERE,PRIVATE
from worker_lease import exclusive_worker_operation
SQL="\nSELECT json_build_object(\n  'global_business_identity', (\n    SELECT json_build_object(\n      'purchase_order', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM purchase_order),\n      'purchase_order_line', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM purchase_order_line),\n      'sale_order', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM sale_order),\n      'sale_order_line', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM sale_order_line),\n      'stock_picking', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM stock_picking),\n      'stock_move', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM stock_move),\n      'stock_move_line', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM stock_move_line),\n      'account_move', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM account_move),\n      'account_move_line', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM account_move_line),\n      'crm_lead', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM crm_lead),\n      'res_partner', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM res_partner),\n      'res_users', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM res_users),\n      'product_product', (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM product_product),\n      'stock_warehouse_orderpoint',\n        (SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json) FROM stock_warehouse_orderpoint),\n      'business_attachment', (\n        SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json)\n        FROM ir_attachment\n        WHERE res_model IN ('purchase.order', 'sale.order', 'crm.lead',\n                            'product.product', 'res.company', 'stock.picking',\n                            'account.move')\n      )\n    )\n  ),\n  'orders', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT id, name, origin, partner_id, partner_ref, state, currency_id,\n             to_char(date_order, 'YYYY-MM-DD HH24:MI:SS') AS date_order\n      FROM purchase_order \n    ) x\n  ),\n  'lines', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT l.id, l.order_id, l.product_id, l.name,\n             l.product_qty::text AS qty, l.price_unit::text AS price,\n             to_char(l.date_planned, 'YYYY-MM-DD') AS date\n      FROM purchase_order_line l\n      JOIN purchase_order o ON o.id = l.order_id\n      \n    ) x\n  ),\n  'attachments', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT a.id, a.res_model, a.res_id, a.name, a.checksum, a.file_size, a.store_fname\n      FROM ir_attachment a\n      WHERE a.res_model IN ('purchase.order','sale.order','crm.lead','product.product','res.company','stock.picking','account.move') AND a.type='binary' AND a.store_fname IS NOT NULL\n    ) x\n  ),\n  'vendors', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT id, name, supplier_rank, comment, active\n      FROM res_partner\n      \n    ) x\n  ),\n  'products', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT p.id, p.default_code, t.name, t.type, t.active,\n             t.list_price::text AS list_price, t.description_purchase\n      FROM product_product p\n      JOIN product_template t ON t.id = p.product_tmpl_id\n      \n    ) x\n  ),\n  'orderpoints', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT r.id, r.product_id, r.location_id, r.warehouse_id, r.company_id,\n             r.product_min_qty::text AS minimum,\n             r.product_max_qty::text AS maximum,\n             r.qty_multiple::text AS multiple, r.trigger\n      FROM stock_warehouse_orderpoint r\n      JOIN product_product p ON p.id = r.product_id\n      \n    ) x\n  ),\n  'sales_orders', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT id, name, origin, partner_id, state, client_order_ref, note,\n             to_char(validity_date, 'YYYY-MM-DD') AS validity_date\n      FROM sale_order \n    ) x\n  ),\n  'sales_lines', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT l.id, l.order_id, l.product_id, l.name,\n             l.product_uom_qty::text AS qty, l.price_unit::text AS price,\n             l.discount::text AS discount\n      FROM sale_order_line l\n      JOIN sale_order o ON o.id = l.order_id\n      \n    ) x\n  ),\n  'crm_leads', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT id, name, type, partner_id, user_id, team_id, stage_id,\n             expected_revenue::text AS revenue,\n             to_char(date_deadline, 'YYYY-MM-DD') AS deadline,\n             priority, email_from, phone, description, active\n      FROM crm_lead \n    ) x\n  ),\n  'customers', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT id, name, is_company, comment, active\n      FROM res_partner\n      \n    ) x\n  ),\n  'salespeople', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT u.id, p.name, u.login, u.active, u.company_id\n      FROM res_users u JOIN res_partner p ON p.id = u.partner_id\n      \n    ) x\n  ),\n  'crm_stages', (\n    SELECT COALESCE(json_agg(to_jsonb(x) ORDER BY x.id), '[]'::json)\n    FROM (\n      SELECT id, name::text AS name, sequence, is_won\n      FROM crm_stage\n    ) x\n  )\n);\n"

def snapshot() -> dict:
    with exclusive_worker_operation("snapshot"):
        return _snapshot_unlocked()

def _snapshot_unlocked() -> dict:
    cmd = [
        "docker", "compose", "--env-file", ".env", "exec", "-T", "db",
        "psql", "-U", "bench_verify", "-d", "bench", "-At",
        "-v", "ON_ERROR_STOP=1", "-c", SQL,
    ]
    result = subprocess.run(cmd, cwd=HERE, check=True, capture_output=True, text=True)
    return json.loads(result.stdout.strip())

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

def keyed(rows):
 if not isinstance(rows,list) or any(not isinstance(r,dict) or type(r.get('id')) is not int for r in rows):raise ValueError('persisted_rows_shape_invalid')
 result={r['id']:r for r in rows}
 if len(result)!=len(rows):raise ValueError('persisted_row_identity_not_unique')
 return result

def number(value):
 if isinstance(value,bool):raise ValueError('numeric_boolean_invalid')
 try:result=Decimal(str(value))
 except (InvalidOperation,ValueError):raise ValueError('numeric_value_invalid') from None
 if not result.is_finite():raise ValueError('numeric_value_nonfinite')
 return result

def evaluate(case_id,target,baseline,observed):
 differences=[]
 if not isinstance(target,dict) or type(target.get('order_id')) is not int or not target.get('lines'):raise ValueError('nonempty_unique_target_required')
 targets={r['line_id']:r for r in target['lines']}
 if len(targets)!=len(target['lines']) or any(type(i) is not int for i in targets):raise ValueError('nonempty_unique_target_required')
 for row in targets.values():
  if type(row.get('product_id')) is not int or set(row['expected'])!={'qty','price','date'}:raise ValueError('expected_comparator_schema_invalid')
  number(row['expected']['qty']);number(row['expected']['price'])
 bo,oo=keyed(baseline['orders']),keyed(observed['orders']);bl,ol=keyed(baseline['lines']),keyed(observed['lines'])
 if target['order_id'] not in bo or target['order_id'] not in oo or not targets.keys()<=bl.keys() or not targets.keys()<=ol.keys():differences.append('target_missing_from_persisted_SQL')
 if not baseline.get('global_business_identity') or baseline.get('global_business_identity')!=observed.get('global_business_identity'):differences.append('global_business_identity_changed_or_missing')
 if set(baseline)!=set(observed):differences.append('snapshot_schema_changed')
 for group in set(baseline)|set(observed):
  if group in ('global_business_identity','lines'):continue
  if keyed(baseline.get(group,[]))!=keyed(observed.get(group,[])):differences.append('protected_'+group+'_changed')
 if bl.keys()!=ol.keys():differences.append('line_identity_set_changed')
 for i,ref in bl.items():
  row=ol.get(i)
  if row is None:continue
  if i not in targets:
   if row!=ref:differences.append('unrelated_order_line_changed')
   continue
  gold=targets[i]
  if ref['order_id']!=target['order_id'] or row['order_id']!=target['order_id'] or row['product_id']!=gold['product_id'] or ref['product_id']!=gold['product_id']:differences.append('target_line_identity_changed')
  if {k:v for k,v in row.items() if k not in ('qty','price','date')}!={k:v for k,v in ref.items() if k not in ('qty','price','date')}:differences.append('target_line_protected_fields_changed')
  if number(row['qty'])!=number(gold['expected']['qty']):differences.append('target_quantity_mismatch')
  if number(row['price'])!=number(gold['expected']['price']):differences.append('target_unit_price_mismatch')
  if row['date']!=gold['expected']['date']:differences.append('target_date_mismatch')
 codes=sorted(set(differences))
 return {'case_id':case_id,'status':'public_synthetic_nontraining_control','reward':int(not codes),'difference_codes':codes}
