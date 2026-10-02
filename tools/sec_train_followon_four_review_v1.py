"""TRAIN-only SEC field review for two allowance and two segment analogues.

All inputs are frozen original 10-K source bundles and the source-only plan.
This module never reads selection/final workbooks or task answers.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path

from lxml import html

from tools.sec_train_next_four_review_v1 import (
    _companyfacts_match, _hash, _ix, _need, _omitted, _period, _row, _signed,
)


GRAPH = {
    "allowance": "bank_loan_allowance_rollforward",
    "segment": "four_segment_operating_profit_and_customer_cut",
}
BANK = {
    6: {"balance_table": 60, "flow_table": 87,
        "balance_rows": {"gross_loans": 9, "allowance": 10, "net_loans": 11},
        "flow_rows": {"beginning_allowance": 4, "chargeoffs": 7,
                      "recoveries": 8, "provision": 10, "other": 11,
                      "ending_allowance": 12},
        "balance_col": {2024: 1, 2025: 0},
        "flow_col": {2024: 5, 2025: 2},
        "labels": {"gross_loans": ("Loans (a)",),
                   "allowance": ("Allowance for loan and lease losses",),
                   "net_loans": ("Net loans",),
                   "beginning_allowance": ("Beginning balance",),
                   "chargeoffs": ("Charge-offs",),
                   "recoveries": ("Recoveries",),
                   "provision": ("Provision for credit losses",),
                   "other": ("Other",),
                   "ending_allowance": ("Ending balance",)}},
    7: {"balance_table": 49, "flow_table": 72,
        "balance_rows": {"gross_loans": 11, "allowance": 12, "net_loans": 13},
        "flow_rows": {"beginning_allowance": None, "chargeoffs": None,
                      "recoveries": None, "provision": None, "other": None,
                      "ending_allowance": None},
        "balance_col": {2024: 3, 2025: 2},
        "flow_row": {2024: 75, 2025: 93},
        "flow_col": {"beginning_allowance": 0, "chargeoffs": 1,
                     "recoveries": 2, "provision": 3, "other": 4,
                     "ending_allowance": 5},
        "labels": {"gross_loans": ("Loans and leases",),
                   "allowance": ("ALLL",),
                   "net_loans": ("Loans and leases, net of ALLL",),
                   "flow_all": ("ALLL",)}},
}
SEGMENTS = {
    20: {
        "labels": ["Aerospace", "Marine Systems", "Combat Systems",
                   "Technologies"],
        "customer_labels": ["U.S. government", "U.S. commercial",
                            "Non-U.S. government", "Non-U.S. commercial"],
        "segment_table": 73,
        "sales_rows": [3, 4, 5, 6],
        "profit_rows": [3, 4, 5, 6],
        "customer_table": 45,
        "customer_rows": {2024: [16, 17, 18, 19],
                          2025: [6, 7, 8, 9]},
        "customer_total": {2024: 20, 2025: 10},
    },
    21: {
        "labels": ["Aeronautics Systems", "Defense Systems",
                   "Mission Systems", "Space Systems"],
        "customer_labels": ["U.S. government", "International",
                            "Other customers",
                            "Fourth category not separately reported"],
        "sales_table": 75, "profit_table": 71,
        "sales_rows": [4, 5, 6, 7],
        "profit_rows": [9, 16, 23, 30],
        "customer_table": 72,
        "customer_rows": {2024: [29, 30, 31],
                          2025: [29, 30, 31]},
        "customer_total": {2024: 32, 2025: 32},
    },
}


def _context_checked(item: dict, year: int, kind: str) -> None:
    period = item["context_period"]
    if kind == "opening":
        _need(period.get("instant") == f"{year - 1}-12-31",
              "opening_allowance_context_wrong_year")
    elif kind == "balance":
        _need(period.get("instant") == f"{year}-12-31",
              "balance_fact_context_wrong_year")
    else:
        _need(period.get("startdate") == f"{year}-01-01" and
              period.get("enddate") == f"{year}-12-31",
              "annual_flow_context_wrong_year")


def _bank(source_idx: int, tree) -> list[dict]:
    spec = BANK[source_idx]
    tables = tree.xpath("//table")
    balance = tables[spec["balance_table"]]
    flow = tables[spec["flow_table"]]
    balance_head = " ".join(" ".join(balance.itertext()).split())[:500]
    flow_head = " ".join(" ".join(flow.itertext()).split())
    _need("2025" in balance_head and "2024" in balance_head and
          "in millions" in balance_head.lower() and
          "2025" in flow_head and "2024" in flow_head and
          "in millions" in flow_head.lower(),
          "loan_or_allowance_filed_scope_header_changed")
    periods = []
    for year in (2024, 2025):
        facts = {}
        for key, row_idx in spec["balance_rows"].items():
            selected_col = (spec["balance_col"][year] if source_idx == 6 or
                            key == "gross_loans" else
                            (1 if year == 2024 else 0))
            facts[key] = _ix(tree, balance, row_idx,
                             selected_col,
                             spec["labels"][key])
            _context_checked(facts[key], year, "balance")
        for key in ("beginning_allowance", "chargeoffs", "recoveries",
                    "provision", "other", "ending_allowance"):
            if source_idx == 6:
                row_idx, col = (spec["flow_rows"][key],
                                spec["flow_col"][year])
                labels = spec["labels"][key]
            else:
                row_idx, col = (spec["flow_row"][year],
                                spec["flow_col"][key])
                labels = spec["labels"]["flow_all"]
            facts[key] = _ix(tree, flow, row_idx, col, labels,
                             sign_policy="outflow" if key == "chargeoffs" else "source",
                             allow_custom=key == "other")
            _context_checked(facts[key], year,
                             "opening" if key == "beginning_allowance" else
                             "balance" if key == "ending_allowance" else "flow")
        _need(all(v["value"] is not None for v in facts.values()),
              "required_allowance_fact_unreported")
        gross, allowance, net = (facts[k]["value"] for k in
                                 ("gross_loans", "allowance", "net_loans"))
        rebuilt = sum(facts[k]["value"] for k in
                      ("beginning_allowance", "chargeoffs", "recoveries",
                       "provision", "other"))
        _need(math.isclose(gross - allowance, net, abs_tol=1e-6) and
              math.isclose(rebuilt, facts["ending_allowance"]["value"],
                           abs_tol=1e-6) and
              math.isclose(allowance, facts["ending_allowance"]["value"],
                           abs_tol=1e-6),
              "loan_base_or_allowance_rollforward_does_not_reconcile")
        periods.append({"period_end": f"{year}-12-31", "fields": facts})
    _need(periods[0]["fields"]["ending_allowance"]["value"] ==
          periods[1]["fields"]["beginning_allowance"]["value"],
          "allowance_cross_year_carry_changed")
    return periods


def _segment(source_idx: int, tree) -> list[dict]:
    spec = SEGMENTS[source_idx]
    tables = tree.xpath("//table")
    segment = tables[spec.get("segment_table", spec.get("sales_table"))]
    profit_table = tables[spec.get("segment_table", spec.get("profit_table"))]
    customers = tables[spec["customer_table"]]
    for table in (segment, profit_table, customers):
        content = " ".join(" ".join(table.itertext()).split())
        _need("2025" in content and "2024" in content and
              (source_idx == 20 or "in millions" in content.lower()),
              "segment_or_customer_filed_period_unit_changed")
    periods = []
    for year in (2024, 2025):
        annual_col = 0 if year == 2025 else 1
        facts = {}
        for i, label in enumerate(spec["labels"], 1):
            sales_col = annual_col
            profit_col = annual_col + (6 if source_idx == 20 else 0)
            facts[f"segment_sales_{i}"] = _ix(
                tree, segment, spec["sales_rows"][i - 1],
                sales_col, (label,))
            facts[f"segment_profit_{i}"] = _ix(
                tree, profit_table, spec["profit_rows"][i - 1],
                profit_col, (label,))
            _context_checked(facts[f"segment_sales_{i}"], year, "flow")
            _context_checked(facts[f"segment_profit_{i}"], year, "flow")
        if source_idx == 20:
            facts["sales_adjustment"] = _ix(
                tree, segment, 7, annual_col, ("Corporate",))
            facts["profit_adjustment"] = _ix(
                tree, segment, 7, annual_col + 6, ("Corporate",))
            facts["filed_sales"] = _ix(
                tree, segment, 8, annual_col, ("Total",))
            facts["filed_profit"] = _ix(
                tree, segment, 8, annual_col + 6, ("Total",))
        else:
            facts["sales_adjustment"] = _ix(
                tree, segment, 8, annual_col,
                ("Intersegment eliminations",), sign_policy="outflow")
            components = [
                _ix(tree, profit_table, 31, annual_col,
                    ("Intersegment profit eliminations",),
                    sign_policy="outflow"),
                _ix(tree, profit_table, 33, annual_col,
                    ("FAS/CAS operating adjustment",), allow_custom=True),
                _ix(tree, profit_table, 34, annual_col,
                    ("Unallocated corporate expense",)),
            ]
            for component in components:
                _context_checked(component, year, "flow")
            facts["profit_adjustment"] = {
                "value": sum(_signed(x) for x in components),
                "presence": "derived_from_disclosed_rows",
                "components": components,
                "ixbrl_tag": None,
                "context_ref": "table 71 rows 31,33,34",
                "row_sha256": _hash("|".join(
                    x["row_sha256"] for x in components).encode()),
                "context_period": None,
            }
            facts["filed_sales"] = _ix(
                tree, segment, 9, annual_col, ("Total sales",))
            facts["filed_profit"] = _ix(
                tree, profit_table, 35, annual_col,
                ("Total operating income",))
        for key in ("sales_adjustment", "filed_sales", "filed_profit"):
            _context_checked(facts[key], year, "flow")
        if source_idx == 20:
            _context_checked(facts["profit_adjustment"], year, "flow")
        for i, label in enumerate(spec["customer_labels"][:3 if
                source_idx == 21 else 4], 1):
            row = spec["customer_rows"][year][i - 1]
            col = (4 if source_idx == 20 else
                   0 if year == 2025 else 2)
            labels = (("Total U.S. government", "U.S. government")
                      if source_idx == 20 and i == 1 else (label,))
            facts[f"customer_{i}"] = _ix(
                tree, customers, row, col, labels)
            _context_checked(facts[f"customer_{i}"], year, "flow")
        if source_idx == 21:
            facts["customer_4"] = _omitted()
        customer_total_col = (4 if source_idx == 20 else annual_col)
        customer_total = _ix(
            tree, customers, spec["customer_total"][year],
            customer_total_col,
            ("Total revenue",) if source_idx == 20 else ("Total Sales",))
        _context_checked(customer_total, year, "flow")
        _need(all(facts[f"segment_sales_{i}"]["value"] is not None and
                  facts[f"segment_profit_{i}"]["value"] is not None
                  for i in range(1, 5)) and
              all(facts[key]["value"] is not None for key in
                  ("sales_adjustment", "profit_adjustment", "filed_sales",
                   "filed_profit")),
              "required_segment_fact_not_reported")
        sales = sum(facts[f"segment_sales_{i}"]["value"] for i in range(1, 5))
        profit = sum(facts[f"segment_profit_{i}"]["value"] for i in range(1, 5))
        customer_sum = sum(_signed(facts[f"customer_{i}"])
                           for i in range(1, 5))
        _need(math.isclose(sales + facts["sales_adjustment"]["value"],
                           facts["filed_sales"]["value"], abs_tol=1e-6) and
              math.isclose(profit + facts["profit_adjustment"]["value"],
                           facts["filed_profit"]["value"], abs_tol=1e-6) and
              math.isclose(customer_sum, facts["filed_sales"]["value"],
                           abs_tol=1e-6) and
              math.isclose(customer_total["value"],
                           facts["filed_sales"]["value"], abs_tol=1e-6),
              "segment_profit_sales_or_customer_cut_does_not_reconcile")
        periods.append({"period_end": f"{year}-12-31", "fields": facts,
                        "independent_customer_total": customer_total})
    return periods


def review(source_pool: Path, source_plan: Path,
           reviewed_cards: Path) -> dict:
    plan_raw = source_plan.read_bytes()
    plan = json.loads(plan_raw)
    _need(plan.get("schema") == "envloop.sec_excel_train_22_raw_source_plan.private.v1"
          and len(plan.get("records", [])) == 22,
          "train_source_plan_shape_changed")
    cards_raw = reviewed_cards.read_bytes()
    cards = json.loads(cards_raw)
    by_graph = {c["final_graph_reservation"]: c for c in cards.get("cards", [])}
    _need(all(by_graph.get(name, {}).get("independent_skill_review") is True and
              by_graph[name]["minimum_target_edits"] <= 12
              for name in GRAPH.values()),
          "reviewed_skill_card_or_depth_missing")
    cases = []
    issuers = set()
    for idx in (6, 7, 20, 21):
        root = source_pool / f"source-{idx:02}"
        raw_case = (root / "source-case.private.json").read_bytes()
        source = json.loads(raw_case)
        identity = source["identity"]
        profile = "allowance" if idx in BANK else "segment"
        _need(source.get("source_index") == idx and
              identity == plan["records"][idx] and
              identity["final_graph_reservation"] == GRAPH[profile] and
              identity["skill_signature_sha256"] ==
              by_graph[GRAPH[profile]]["skill_signature_sha256"] and
              source.get("semantic_fact_review_completed") is False and
              source.get("excel_web_admitted") is False and
              identity["issuer_cik"] not in issuers,
              "frozen_train_source_or_graph_identity_changed")
        issuers.add(identity["issuer_cik"])
        for kind, entry in source["response"].items():
            file = {"10k": "10k.html", "support": "support.html",
                    "companyfacts": "companyfacts.json", "index": "index.html",
                    "submissions": "submissions.json"}[kind]
            raw = (root / file).read_bytes()
            _need(_hash(raw) == entry["sha256"] and
                  len(raw) == entry["bytes"] and entry["status"] == 200 and
                  entry["url"].startswith(("https://www.sec.gov/",
                                           "https://data.sec.gov/")),
                  "frozen_original_sec_response_changed")
        tree = html.fromstring((root / "10k.html").read_bytes())
        companyfacts = json.loads((root / "companyfacts.json").read_bytes())
        _need(companyfacts.get("cik") == identity["issuer_cik"],
              "companyfacts_issuer_does_not_match_original_10k")
        periods = (_bank(idx, tree) if profile == "allowance" else
                   _segment(idx, tree))
        if profile == "allowance":
            for period in periods:
                year = int(period["period_end"][:4])
                _need(all(_companyfacts_match(
                    companyfacts, identity["accession"], year,
                    period["fields"][key])
                    for key in ("gross_loans", "allowance", "net_loans",
                                "ending_allowance")),
                    "same_accession_companyfacts_loan_or_allowance_mismatch")
        else:
            for period in periods:
                year = int(period["period_end"][:4])
                _need(all(_companyfacts_match(
                    companyfacts, identity["accession"], year,
                    period["fields"][key])
                    for key in ("filed_sales", "filed_profit")),
                    "same_accession_companyfacts_consolidated_mismatch")
                _need(_companyfacts_match(
                    companyfacts, identity["accession"], year,
                    period["independent_customer_total"]),
                    "same_accession_customer_total_mismatch")
        cases.append({
            "case_index": idx, "profile": profile,
            "graph": GRAPH[profile],
            "signature_sha256": identity["skill_signature_sha256"],
            "source": {"identity": identity,
                       "original_sec_url": source["urls"]["10k"],
                       "source_case_sha256": _hash(raw_case),
                       "raw_sha256": {kind: entry["sha256"]
                                      for kind, entry in source["response"].items()},
                       **({"segment_labels": SEGMENTS[idx]["labels"],
                           "customer_labels": SEGMENTS[idx]["customer_labels"]}
                          if profile == "segment" else {})},
            "periods": periods,
            "scenario": ({"additional_provision": 140.0,
                          "gross_loan_change": -0.012}
                         if profile == "allowance" else
                         {"selected_segment_sales_change": 0.06,
                          "incremental_profit_margin": 0.14}),
            "review_status": "source_field_review_pass; independent_audit_pending",
            "excel_web_admitted": False, "official_final_admitted": False,
        })
    return {"schema": "envloop.sec_excel_train_followon_four_review.private.v1",
            "scope": "four TRAIN-only source bundles; no selection/final artifact",
            "source_plan_sha256": _hash(plan_raw),
            "skill_cards_sha256": _hash(cards_raw),
            "raw_source_root": str(source_pool),
            "cases": cases}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-pool", type=Path, required=True)
    ap.add_argument("--source-plan", type=Path, required=True)
    ap.add_argument("--reviewed-cards", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    args = ap.parse_args()
    result = review(args.source_pool, args.source_plan, args.reviewed_cards)
    args.private_out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.private_out.parent, 0o700)
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(args.private_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
    print(json.dumps({"status": "field_review_generated",
                      "train_sources": len(result["cases"]),
                      "private_review_sha256": _hash(raw),
                      "independent_audit": "pending"}))


if __name__ == "__main__":
    main()
