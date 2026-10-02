"""Field-limited review of four TRAIN-only SEC source bundles.

This reads only the frozen raw source pool and its TRAIN source plan. It does
not open selection/final artifacts or call any model or Office application.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re

from lxml import html


GRAPH = {
    "pension": "pension_funded_status_and_asset_movement",
    "bank": "bank_net_interest_and_deposit_funding",
}
PENSION_ROWS = {
    2: {"table": 77, "cols": {2024: 1, 2025: 0},
        "rows": {"opening_assets": 17, "actual_return": 18,
                 "participant_contributions": 20, "benefits_paid": 22,
                 "closing_assets": 24, "obligation": 15,
                 "reported_funded": 30},
        "other_rows": [21, 23],
        "unreported": ["employer_contributions", "settlements"]},
    3: {"table": 125, "cols": {2024: 0, 2025: 3},
        "rows": {"opening_assets": 18, "actual_return": 19,
                 "employer_contributions": 20,
                 "participant_contributions": 21, "benefits_paid": 22,
                 "settlements": 23, "closing_assets": 26,
                 "obligation": 16, "reported_funded": 27},
        "other_rows": [24, 25], "unreported": []},
}
BANK_ROWS = {
    4: {"statement": 146, "deposit": 150, "average": 11,
        "rows": {"interest_income": 14, "interest_expense": 22,
                 "reported_net_interest": 23,
                 "interest_bearing_deposits": 22, "total_deposits": 23,
                 "average_interest_bearing_deposits": 37},
        "avg_number_col": {2024: 3, 2025: 0}},
    5: {"statement": 114, "deposit": 187, "average": 6,
        "rows": {"interest_income": 7, "interest_expense": 12,
                 "reported_net_interest": 13,
                 "interest_bearing_deposits": 8, "total_deposits": 9,
                 "average_interest_bearing_deposits": 17},
        "avg_number_col": {2024: 1, 2025: 0}},
}
BANK_LABELS = {
    "interest_income": "Total interest income",
    "interest_expense": "Total interest expense",
    "reported_net_interest": "Net interest income",
    "interest_bearing_deposits": "interest-bearing deposits",
    "total_deposits": "Total deposits",
    "average_interest_bearing_deposits": "interest-bearing deposits",
}
PENSION_LABELS = {
    "opening_assets": ("Beginning balance at fair value", "Fair value of plan assets at January 1"),
    "actual_return": ("Actual return on plan assets",),
    "employer_contributions": ("Company contributions",),
    "participant_contributions": ("Plan participants’ contributions", "Plan participant contributions"),
    "benefits_paid": ("Benefits paid",),
    "settlements": ("Settlements",),
    "closing_assets": ("Ending balance at fair value", "Fair value of plan assets at December 31"),
    "obligation": ("Ending balance", "Benefit obligation at December 31"),
    "reported_funded": ("Net amount recognized", "Funded status at December 31"),
}
NUM = re.compile(r"(?<![A-Za-z0-9])\(?\d[\d,]*(?:\.\d+)?\)?")


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _row(table, index: int, labels: tuple[str, ...]):
    rows = table.xpath(".//tr")
    _need(index < len(rows), "missing_reviewed_table_row")
    row = rows[index]
    text = " ".join(" ".join(row.itertext()).split())
    _need(any(text.lower().startswith(label.lower()) for label in labels),
          f"wrong_reviewed_row:{index}")
    return row, text


def _period(tree, context_ref: str) -> dict:
    matches = tree.xpath('//*[name()="xbrli:context" and @id=$cid]',
                         cid=context_ref)
    _need(len(matches) == 1, "ixbrl_context_not_unique")
    context = matches[0]
    period = context.xpath('.//*[name()="xbrli:period"]')
    _need(len(period) == 1, "ixbrl_period_not_unique")
    result = {}
    for key in ("instant", "startdate", "enddate"):
        elements = period[0].xpath(f'.//*[name()="xbrli:{key}"]')
        if elements:
            _need(len(elements) == 1 and elements[0].text,
                  "ixbrl_period_field_not_unique")
            result[key] = elements[0].text
    # SEC inline-XBRL responses are parsed as HTML, which lowercases
    # ``xbrldi:explicitMember`` to ``xbrldi:explicitmember``. Match the local
    # tag case-insensitively instead of relying on an XML-cased XPath name.
    members = []
    for node in context.iter():
        if (isinstance(node.tag, str) and
                node.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()
                == "explicitmember"):
            axis = node.get("dimension")
            member = " ".join(" ".join(node.itertext()).split())
            _need(bool(axis and member), "ixbrl_dimension_member_incomplete")
            members.append({"axis": axis, "member": member})
    result["dimension_member_count"] = len(members)
    result["dimension_members"] = members
    return result


def _ix(tree, table, row_idx: int, col: int, labels: tuple[str, ...],
        *, sign_policy: str = "source", allow_custom: bool = False,
        context_tree=None) -> dict:
    row, text = _row(table, row_idx, labels)
    nodes = row.xpath('.//*[name()="ix:nonfraction"]')
    _need(col < len(nodes), "reviewed_ixbrl_column_missing")
    node = nodes[col]
    _need(node.get("unitref") == "usd" and
          (node.get("scale") == "6" or node.get("xsi:nil") == "true") and
          ((node.get("name") or "").startswith("us-gaap:") or
           (allow_custom and ":" in (node.get("name") or ""))) and
          node.get("contextref"), "reviewed_fact_not_usd_millions_ixbrl")
    raw_text = "".join(node.itertext()).strip()
    if node.get("xsi:nil") == "true" or not raw_text:
        value, presence = None, "not_separately_reported"
    elif raw_text in {"—", "–", "-"}:
        value, presence = 0.0, "disclosed_dash"
    else:
        value = float(raw_text.replace(",", "").replace("$", ""))
        if node.get("sign") == "-":
            value = -value
        if sign_policy == "outflow":
            value = -abs(value)
        presence = "reported"
    return {"value": value, "presence": presence,
            "ixbrl_tag": node.get("name"),
            "context_ref": node.get("contextref"),
            "context_period": _period(context_tree if context_tree is not None
                                      else tree, node.get("contextref")),
            "row_sha256": _hash(text.encode()),
            "row_index": row_idx, "column_index": col,
            "row_label": labels[0] if text.lower().startswith(labels[0].lower())
                         else labels[-1]}


def _omitted() -> dict:
    return {"value": None, "presence": "not_separately_reported",
            "ixbrl_tag": None, "context_ref": None,
            "context_period": None, "row_sha256": None,
            "row_index": None, "column_index": None,
            "row_label": None}


def _signed(x: dict) -> float:
    return 0.0 if x["value"] is None else float(x["value"])


def _pension(source_idx: int, tree) -> list[dict]:
    spec = PENSION_ROWS[source_idx]
    tables = tree.xpath("//table")
    table = tables[spec["table"]]
    header = " ".join(" ".join(table.itertext()).split())[:400]
    _need("2024" in header and "2025" in header and
          ("Pension Other Postretirement" in header if source_idx == 2
           else "Pension Benefits OPEB" in header and "U.S. Plans" in header),
          "pension_plan_scope_header_changed")
    periods = []
    for year in (2024, 2025):
        col = spec["cols"][year]
        fields = {key: _ix(tree, table, row, col, PENSION_LABELS[key],
                           sign_policy="outflow" if key in {"benefits_paid", "settlements"}
                           else "source")
                  for key, row in spec["rows"].items()}
        for key in spec["unreported"]:
            fields[key] = _omitted()
        other = []
        for row in spec["other_rows"]:
            r = table.xpath(".//tr")[row]
            label = " ".join(" ".join(r.itertext()).split()).split("  ")[0]
            node = r.xpath('.//*[name()="ix:nonfraction"]')
            _need(col < len(node), "other_reconciliation_column_missing")
            # The row text supplies the semantic class, and the tagged cell
            # supplies its signed value and context.
            txt = " ".join(" ".join(r.itertext()).split())
            _need(any(k in txt for k in ("Spirit Acquisition", "Exchange rate adjustment",
                                            "Foreign exchange translation", "Other")),
                  "other_reconciliation_row_changed")
            disclosed = _ix(tree, table, row, col,
                            (txt.split(" ")[0],), allow_custom=True)
            context = disclosed["context_period"]
            _need(context.get("startdate") == f"{year}-01-01" and
                  context.get("enddate") == f"{year}-12-31",
                  "other_reconciliation_context_wrong_year")
            other.append(disclosed)
        fields["other_disclosed"] = {
            "value": sum(_signed(x) for x in other),
            "presence": "derived_from_disclosed_rows",
            "components": other,
            "context_ref": "table %d rows %s" %
                (spec["table"], ",".join(str(row) for row in spec["other_rows"])),
            "row_sha256": _hash("|".join(x["row_sha256"] for x in other).encode())}
        for key, fact in fields.items():
            if key == "other_disclosed" or fact["context_period"] is None:
                continue
            period = fact["context_period"]
            if key == "opening_assets":
                _need(period.get("instant") == f"{year - 1}-12-31",
                      "pension_opening_asset_context_wrong_year")
            elif key in {"closing_assets", "obligation", "reported_funded"}:
                _need(period.get("instant") == f"{year}-12-31",
                      "pension_closing_context_wrong_year")
            else:
                _need(period.get("startdate") == f"{year}-01-01" and
                      period.get("enddate") == f"{year}-12-31",
                      "pension_flow_context_wrong_year")
        for key in ("opening_assets", "actual_return", "benefits_paid",
                    "closing_assets", "obligation", "reported_funded"):
            _need(fields[key]["value"] is not None,
                  f"pension_required_fact_missing:{key}")
        assets = sum(_signed(fields[k]) for k in
                     ("opening_assets", "actual_return", "employer_contributions",
                      "participant_contributions", "benefits_paid", "settlements",
                      "other_disclosed"))
        _need(math.isclose(assets, _signed(fields["closing_assets"]), abs_tol=1e-6)
              and math.isclose(_signed(fields["closing_assets"])
                               - _signed(fields["obligation"]),
                               _signed(fields["reported_funded"]), abs_tol=1e-6),
              "pension_source_rollforward_or_funded_status_mismatch")
        periods.append({"period_end": f"{year}-12-31", "fields": fields})
    _need(_signed(periods[0]["fields"]["closing_assets"]) ==
          _signed(periods[1]["fields"]["opening_assets"]),
          "pension_cross_year_asset_carry_mismatch")
    return periods


def _average(table, table_idx: int, row_idx: int,
             number_index: int) -> dict:
    row, text = _row(table, row_idx, ("Total interest-bearing deposits",
                                       "Interest-bearing deposits"))
    label = ("Total interest-bearing deposits" if text.startswith("Total")
             else "Interest-bearing deposits")
    suffix = text[len(label):]
    values = [float(x.group().strip("()").replace(",", ""))
              for x in NUM.finditer(suffix)]
    _need(number_index < len(values), "average_deposit_column_missing")
    return {"value": values[number_index], "presence": "reported_untagged_table",
            "ixbrl_tag": None,
            "context_ref": f"table {table_idx} row {row_idx}",
            "context_period": None, "row_sha256": _hash(text.encode()),
            "row_index": row_idx, "column_index": number_index,
            "row_label": label}


def _companyfacts_match(facts: dict, accession: str, year: int,
                        field: dict) -> bool:
    tag = field["ixbrl_tag"]
    if not tag or not tag.startswith("us-gaap:"):
        return False
    concept = facts.get("facts", {}).get("us-gaap", {}).get(tag.split(":", 1)[1])
    if not concept:
        return False
    dollars = concept.get("units", {}).get("USD", [])
    return any(x.get("accn") == accession and x.get("form") == "10-K"
               and x.get("end") == f"{year}-12-31"
               and math.isclose(float(x.get("val", float("nan"))) / 1e6,
                                float(field["value"]), abs_tol=1e-6)
               for x in dollars)


def _bank(source_idx: int, tree, context_tree,
          facts: dict, accession: str) -> list[dict]:
    spec = BANK_ROWS[source_idx]
    tabs = tree.xpath("//table")
    statement, deposit, average = (tabs[spec[k]] for k in
                                   ("statement", "deposit", "average"))
    for tab in (statement, deposit, average):
        header = " ".join(" ".join(tab.itertext()).split())[:500]
        _need("2024" in header and "2025" in header,
              "bank_source_period_header_changed")
    average_header = " ".join(" ".join(average.itertext()).split())[:500]
    _need("in millions" in average_header.lower(),
          "bank_average_deposit_unit_changed")
    periods = []
    for year in (2024, 2025):
        col = 1 if year == 2024 else 0
        fields = {}
        for key in ("interest_income", "interest_expense", "reported_net_interest",
                    "interest_bearing_deposits", "total_deposits"):
            tab = statement if key in ("interest_income", "interest_expense",
                                       "reported_net_interest") else deposit
            selected_col = col + (2 if source_idx == 4 and
                                  key == "interest_bearing_deposits" else 0)
            labels = (("Total interest-bearing deposits", "Interest-bearing deposits")
                      if key == "interest_bearing_deposits" else
                      (BANK_LABELS[key],))
            fields[key] = _ix(tree, tab, spec["rows"][key], selected_col,
                              labels, context_tree=context_tree)
            period = fields[key]["context_period"]
            if key in ("interest_income", "interest_expense",
                       "reported_net_interest"):
                _need(period.get("startdate") == f"{year}-01-01" and
                      period.get("enddate") == f"{year}-12-31",
                      "bank_interest_context_wrong_year")
            else:
                _need(period.get("instant") == f"{year}-12-31",
                      "bank_deposit_context_wrong_year")
            _need(_companyfacts_match(facts, accession, year, fields[key]),
                  f"bank_same_accession_companyfacts_mismatch:{key}:{year}")
        fields["average_interest_bearing_deposits"] = _average(
            average, spec["average"],
            spec["rows"]["average_interest_bearing_deposits"],
            spec["avg_number_col"][year])
        _need(all(x["value"] is not None for x in fields.values()),
              "bank_required_fact_missing")
        _need(math.isclose(fields["interest_income"]["value"]
                           - fields["interest_expense"]["value"],
                           fields["reported_net_interest"]["value"], abs_tol=1e-6)
              and 0 < fields["interest_bearing_deposits"]["value"]
                  < fields["total_deposits"]["value"]
              and 0 < fields["average_interest_bearing_deposits"]["value"]
                  < fields["total_deposits"]["value"] * 1.2,
              "bank_interest_or_deposit_scope_reconciliation_failed")
        periods.append({"period_end": f"{year}-12-31", "fields": fields})
    return periods


def review(source_pool: Path, source_plan: Path) -> dict:
    raw_plan = source_plan.read_bytes()
    plan = json.loads(raw_plan)
    _need(plan.get("schema") == "envloop.sec_excel_train_22_raw_source_plan.private.v1"
          and len(plan.get("records", [])) == 22,
          "source_plan_shape_changed")
    cases = []
    issuers = set()
    for idx in (2, 3, 4, 5):
        root = source_pool / f"source-{idx:02}"
        raw_case = (root / "source-case.private.json").read_bytes()
        case = json.loads(raw_case)
        identity = case["identity"]
        profile = "pension" if idx in PENSION_ROWS else "bank"
        _need(case["source_index"] == idx and identity == plan["records"][idx]
              and identity["final_graph_reservation"] == GRAPH[profile]
              and case["semantic_fact_review_completed"] is False
              and case["excel_web_admitted"] is False,
              "raw_train_source_or_graph_identity_changed")
        _need(identity["issuer_cik"] not in issuers,
              "train_issuer_reused")
        issuers.add(identity["issuer_cik"])
        for kind, entry in case["response"].items():
            filename = {"10k": "10k.html", "support": "support.html",
                        "companyfacts": "companyfacts.json", "index": "index.html",
                        "submissions": "submissions.json"}[kind]
            raw = (root / filename).read_bytes()
            _need(_hash(raw) == entry["sha256"] and len(raw) == entry["bytes"]
                  and entry["status"] == 200
                  and entry["url"].startswith(("https://www.sec.gov/",
                                               "https://data.sec.gov/")),
                  "frozen_raw_sec_response_changed")
        document = "10k.html" if profile == "pension" else "support.html"
        tree = html.fromstring((root / document).read_bytes())
        facts = json.loads((root / "companyfacts.json").read_bytes())
        _need(facts.get("cik") == identity["issuer_cik"],
              "companyfacts_issuer_changed")
        context_tree = (html.fromstring((root / "10k.html").read_bytes())
                        if idx == 5 else tree)
        periods = (_pension(idx, tree) if profile == "pension" else
                   _bank(idx, tree, context_tree, facts, identity["accession"]))
        cases.append({"case_index": idx, "profile": profile,
                      "graph": GRAPH[profile],
                      "signature_sha256": identity["skill_signature_sha256"],
                      "source": {"identity": identity,
                                 "original_sec_url": case["urls"][
                                     "10k" if profile == "pension" else "support"],
                                 "indexed_primary_url": case["urls"]["10k"],
                                 "source_case_sha256": _hash(raw_case),
                                 "raw_sha256": {kind: entry["sha256"]
                                                for kind, entry in case["response"].items()},
                                 "document": document,
                                 "plan_scope": ("Pension, aggregate" if idx == 2 else
                                                "U.S. pension plans" if idx == 3 else
                                                "Consolidated bank")},
                      "periods": periods,
                      "scenario": ({"sponsor_contribution": 225.0,
                                    "return_change": -0.015,
                                    "obligation_change": 0.008}
                                   if profile == "pension" else
                                   {"deposit_rate_change_bps": 35.0}),
                      "review_status": "source_field_review_pass; independent_audit_pending",
                      "excel_web_admitted": False,
                      "official_final_admitted": False})
    return {"schema": "envloop.sec_excel_train_next_four_review.private.v1",
            "scope": "four TRAIN-only source bundles; no selection/final artifact",
            "source_plan_sha256": _hash(raw_plan),
            "raw_source_root": str(source_pool),
            "cases": cases}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-pool", type=Path, required=True)
    ap.add_argument("--source-plan", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    args = ap.parse_args()
    result = review(args.source_pool, args.source_plan)
    args.private_out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.private_out.parent, 0o700)
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(args.private_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
    print(json.dumps({"status": "field_review_generated",
                      "case_count": len(result["cases"]),
                      "private_review_sha256": _hash(raw),
                      "independent_audit": "pending"}))


if __name__ == "__main__":
    main()
