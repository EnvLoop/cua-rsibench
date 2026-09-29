"""Independent second-person review of four frozen SEC TRAIN sources.

This source does not import the author's extraction, workbook builder, or
scorer. It rediscovers filing tables by text and XBRL tags, selects facts by
period/entity/dimension context, and compares every used field afterward.
The public receipt contains no issuer IDs or financial answers.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

from lxml import html


YEARS = (2024, 2025)
PENSION_KEYS = (
    "opening_assets", "actual_return", "employer_contributions",
    "participant_contributions", "benefits_paid", "settlements",
    "closing_assets", "obligation", "reported_funded", "other_disclosed",
)
BANK_TAGS = {
    "interest_income": "InterestAndDividendIncomeOperating",
    "interest_expense": "InterestExpenseOperating",
    "reported_net_interest": "InterestIncomeExpenseNet",
    "interest_bearing_deposits": "InterestBearingDepositLiabilities",
    "total_deposits": "Deposits",
}
PENSION_LABELS = {
    "opening_assets": ("beginning balance at fair value",
                       "fair value of plan assets at january 1"),
    "actual_return": ("actual return on plan assets",),
    "employer_contributions": ("company contributions",),
    "participant_contributions": ("plan participant contributions",
                                  "plan participants’ contributions"),
    "benefits_paid": ("benefits paid",),
    "settlements": ("settlements",),
    "closing_assets": ("ending balance at fair value",
                       "fair value of plan assets at december 31"),
    "obligation": ("ending balance", "benefit obligation at december 31"),
    "reported_funded": ("net amount recognized",
                        "funded status at december 31"),
}
BANK_LABELS = {
    "interest_income": ("total interest income",),
    "interest_expense": ("total interest expense",),
    "reported_net_interest": ("net interest income",),
    "interest_bearing_deposits": ("interest-bearing deposits",
                                  "total interest-bearing deposits"),
    "total_deposits": ("total deposits",),
    "average_interest_bearing_deposits": ("interest-bearing deposits",
                                          "total interest-bearing deposits"),
}
NUMBER = re.compile(r"(?<![A-Za-z0-9])\(?\d[\d,]*(?:\.\d+)?\)?")


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def norm(element) -> str:
    return " ".join(" ".join(element.itertext()).split())


def rows(table) -> list:
    return table.xpath(".//tr")


def row_by_label(table, labels: tuple[str, ...], *, start: int = 0,
                 end: int | None = None, optional: bool = False):
    found = [(index, row) for index, row in enumerate(rows(table))
             if start <= index < (end if end is not None else len(rows(table)))
             and any(norm(row).lower().startswith(label) for label in labels)]
    if not found and optional:
        return None
    need(len(found) == 1, "source_row_not_unique:" + labels[0])
    return found[0]


def find_table(tree, predicate, label: str):
    tables = tree.xpath("//table")
    found = [(index, table) for index, table in enumerate(tables)
             if predicate(table)]
    need(len(found) == 1, "source_table_not_unique:" + label)
    return found[0]


def contexts(tree) -> dict[str, dict]:
    result = {}
    for context in tree.xpath('//*[name()="xbrli:context" and @id]'):
        cid = context.get("id")
        entity = context.xpath('.//*[name()="xbrli:identifier"]')
        need(len(entity) == 1 and entity[0].text, "context_entity_missing")
        values = {}
        for name in ("instant", "startdate", "enddate"):
            matches = context.xpath(f'.//*[name()="xbrli:{name}"]')
            if matches:
                need(len(matches) == 1 and matches[0].text,
                     "context_period_ambiguous")
                values[name] = matches[0].text
        values["members"] = tuple(norm(member)
                                  for member in context.xpath(
                                      './/*[contains(name(),"explicitmember")]'))
        values["entity"] = entity[0].text.strip()
        result[cid] = values
    return result


def context_matches(context: dict, *, year: int, kind: str,
                    scope: str) -> bool:
    if kind == "opening":
        period = context.get("instant") == f"{year - 1}-12-31"
    elif kind == "instant":
        period = context.get("instant") == f"{year}-12-31"
    else:
        period = (context.get("startdate") == f"{year}-01-01" and
                  context.get("enddate") == f"{year}-12-31")
    members = context["members"]
    if scope == "bank":
        return period and not members
    pension = any("PensionPlansDefinedBenefitMember" in item
                  for item in members)
    us = any("country:US" in item for item in members)
    return period and pension and (us if scope == "us_pension" else not us)


def decode(node, *, outflow: bool = False) -> tuple[Decimal | None, str]:
    need(node.get("unitref") == "usd", "fact_not_usd")
    raw = "".join(node.itertext()).strip()
    if node.get("xsi:nil") == "true" or not raw:
        return None, "not_separately_reported"
    need(node.get("scale") == "6", "fact_not_usd_millions")
    if raw in {"—", "–", "-"}:
        return Decimal(0), "disclosed_dash"
    cleaned = raw.replace("$", "").replace(",", "").strip()
    parenthesized = cleaned.startswith("(") and cleaned.endswith(")")
    amount = Decimal(cleaned.strip("() "))
    if node.get("sign") == "-" or parenthesized or outflow:
        amount = -abs(amount)
    return amount, "reported"


def node_for(row, context_map: dict, *, year: int, kind: str,
             scope: str, expected_tag: str | None = None):
    found = []
    for node in row.xpath('.//*[name()="ix:nonfraction"]'):
        cid = node.get("contextref")
        if cid not in context_map or not context_matches(
                context_map[cid], year=year, kind=kind, scope=scope):
            continue
        if expected_tag is not None and node.get("name") != expected_tag:
            continue
        found.append(node)
    need(len(found) == 1, "scoped_fact_not_unique:" +
         (expected_tag or norm(row)[:40]))
    return found[0]


def fact(table, row_index: int, context_map: dict, *, year: int,
         kind: str, scope: str, outflow: bool = False,
         expected_tag: str | None = None) -> dict:
    row = rows(table)[row_index]
    node = node_for(row, context_map, year=year, kind=kind,
                    scope=scope, expected_tag=expected_tag)
    value, presence = decode(node, outflow=outflow)
    return {"value": value, "presence": presence,
            "tag": node.get("name"), "context_ref": node.get("contextref"),
            "context": context_map[node.get("contextref")],
            "row_sha256": digest(norm(row).encode()),
            "row_index": row_index}


def omitted() -> dict:
    return {"value": None, "presence": "not_separately_reported",
            "tag": None, "context_ref": None, "context": None,
            "row_sha256": None, "row_index": None}


def signed(value: Decimal | None) -> Decimal:
    return Decimal(0) if value is None else value


def pension_fields(tree, context_map: dict, *, scope: str,
                   year: int) -> tuple[dict, dict]:
    table_index, table = find_table(
        tree, lambda t: all(token in norm(t).lower() for token in
                            ("change in plan assets", "actual return on plan assets",
                             "benefit obligation")), "pension_rollforward")
    text = norm(table).lower()
    need("2024" in text[:450] and "2025" in text[:450] and
         "pension" in text[:450], "pension_scope_header_missing")
    plan_header = row_by_label(table, ("change in plan assets",))[0]
    closing_row = row_by_label(table, PENSION_LABELS["closing_assets"],
                               start=plan_header + 1)[0]
    field_rows = {}
    for key, labels in PENSION_LABELS.items():
        if key == "obligation":
            hit = row_by_label(table, labels, end=plan_header)
        elif key == "reported_funded":
            hit = row_by_label(table, labels, start=closing_row + 1,
                               optional=True)
            if hit is None:
                hit = row_by_label(table, labels, start=closing_row)
        else:
            hit = row_by_label(table, labels,
                               start=plan_header + 1,
                               end=closing_row + 1,
                               optional=key in ("employer_contributions",
                                                "settlements"))
        field_rows[key] = None if hit is None else hit[0]
    values = {}
    for key, row_index in field_rows.items():
        if row_index is None:
            values[key] = omitted()
            continue
        kind = ("opening" if key == "opening_assets" else
                "instant" if key in ("closing_assets", "obligation",
                                     "reported_funded") else "duration")
        values[key] = fact(
            table, row_index, context_map, year=year, kind=kind,
            scope=scope, outflow=key in ("benefits_paid", "settlements"))
    identified = {index for index in field_rows.values() if index is not None}
    extras = []
    for index in range(plan_header + 1, closing_row):
        if index in identified:
            continue
        row = rows(table)[index]
        matching = [node for node in row.xpath('.//*[name()="ix:nonfraction"]')
                    if node.get("contextref") in context_map and
                    context_matches(context_map[node.get("contextref")],
                                    year=year, kind="duration", scope=scope)]
        if not matching:
            continue
        need(len(matching) == 1, "other_pension_activity_ambiguous")
        extras.append(fact(table, index, context_map,
                           year=year, kind="duration", scope=scope))
    need(len(extras) >= 1, "pension_other_activity_missing")
    values["other_disclosed"] = {
        "value": sum((signed(item["value"]) for item in extras), Decimal(0)),
        "presence": "derived_from_disclosed_rows", "components": extras,
        "context_ref": f"table {table_index} rows " +
            ",".join(str(item["row_index"]) for item in extras),
        "row_sha256": digest("|".join(item["row_sha256"] for item in extras).encode()),
    }
    required = ("opening_assets", "actual_return", "benefits_paid",
                "closing_assets", "obligation", "reported_funded")
    need(all(values[key]["value"] is not None for key in required),
         "required_pension_fact_missing")
    asset = sum((signed(values[key]["value"]) for key in PENSION_KEYS
                 if key not in ("closing_assets", "obligation", "reported_funded")),
                Decimal(0))
    need(asset == values["closing_assets"]["value"] and
         values["closing_assets"]["value"] - values["obligation"]["value"] ==
            values["reported_funded"]["value"],
         "pension_rollforward_or_funded_status_mismatch")
    return values, {"table_index": table_index, "scope": scope,
                    "other_component_count": len(extras)}


def companyfacts_bank_match(companyfacts: dict, accession: str, year: int,
                            tag: str, value: Decimal, kind: str) -> None:
    concept = companyfacts.get("facts", {}).get("us-gaap", {}).get(tag)
    need(concept is not None, "bank_companyfacts_concept_missing")
    matches = [item for item in concept.get("units", {}).get("USD", [])
               if item.get("accn") == accession and item.get("form") == "10-K"
               and item.get("end") == f"{year}-12-31"
               and (item.get("start") == f"{year}-01-01"
                    if kind == "duration" else not item.get("start"))
               and Decimal(item.get("val", "NaN")) == value * 1_000_000]
    need(len(matches) >= 1, "bank_companyfacts_same_accession_full_period_mismatch")


def bank_fields(tree, context_map: dict, companyfacts: dict,
                accession: str, *, year: int) -> tuple[dict, dict]:
    tabs = tree.xpath("//table")
    tagset = lambda table: {node.get("name") for node in table.xpath(
        './/*[name()="ix:nonfraction"]')}
    statement_idx, statement = find_table(
        tree, lambda t: all("us-gaap:" + tag in tagset(t) for tag in
                            ("InterestAndDividendIncomeOperating",
                             "InterestExpenseOperating", "InterestIncomeExpenseNet"))
        and "total interest income" in norm(t).lower()
        and "net interest income" in norm(t).lower(), "bank_income_statement")
    deposit_idx, deposit = find_table(
        tree, lambda t: {"us-gaap:InterestBearingDepositLiabilities",
                         "us-gaap:Deposits"} <= tagset(t)
        and "noninterest-bearing deposits" in norm(t).lower(),
        "bank_closing_deposits")
    average_idx, average = find_table(
        tree, lambda t: (
            ("average balance" in norm(t)[:300].lower() and
             "average interest rates" in norm(t)[:300].lower() and
             "total interest-bearing deposits" in norm(t).lower()) or
            ("components of net interest income" in norm(t).lower() and
             "average balances" in norm(t).lower() and
             "interest-bearing deposits" in norm(t).lower())),
        "bank_annual_average")
    for table in (statement, deposit, average):
        header = norm(table)[:500].lower()
        need("2024" in header and "2025" in header,
             "bank_year_header_missing")
    need("in millions" in norm(average)[:500].lower(),
         "bank_average_unit_missing")
    values = {}
    for key, tag in BANK_TAGS.items():
        table = (statement if key in ("interest_income", "interest_expense",
                                     "reported_net_interest") else deposit)
        row_candidates = [(index, row) for index, row in enumerate(rows(table))
                          if any(norm(row).lower().startswith(label)
                                 for label in BANK_LABELS[key]) and
                          any(node.get("name") == "us-gaap:" + tag for node in
                              row.xpath('.//*[name()="ix:nonfraction"]'))]
        need(len(row_candidates) == 1, "bank_tagged_source_row_not_unique:" + key)
        row_index, row = row_candidates[0]
        kind = ("duration" if table is statement else "instant")
        item = fact(table, row_index, context_map, year=year,
                    kind=kind, scope="bank", expected_tag="us-gaap:" + tag)
        need(item["value"] is not None and item["value"] >= 0,
             "bank_required_fact_nonpositive_or_missing")
        companyfacts_bank_match(companyfacts, accession, year, tag,
                                item["value"], kind)
        values[key] = item
    average_row_index, average_row = row_by_label(
        average, BANK_LABELS["average_interest_bearing_deposits"])
    need(not average_row.xpath('.//*[name()="ix:nonfraction"]'),
         "bank_average_source_unexpectedly_tagged")
    label = ("total interest-bearing deposits" if norm(average_row).lower().startswith(
             "total") else "interest-bearing deposits")
    suffix = norm(average_row)[len(label):]
    parsed = [Decimal(match.group().strip("() ").replace(",", ""))
              for match in NUMBER.finditer(suffix)]
    if "average interest rates" in norm(average)[:300].lower():
        position = 0 if year == 2025 else 3
    else:
        position = 0 if year == 2025 else 1
    need(position < len(parsed), "bank_average_year_value_missing")
    values["average_interest_bearing_deposits"] = {
        "value": parsed[position], "presence": "reported_untagged_table",
        "tag": None, "context_ref": f"table {average_idx} row {average_row_index}",
        "context": None, "row_sha256": digest(norm(average_row).encode()),
        "row_index": average_row_index,
    }
    need(values["interest_income"]["value"] -
         values["interest_expense"]["value"] ==
         values["reported_net_interest"]["value"] and
         Decimal(0) < values["interest_bearing_deposits"]["value"] <
            values["total_deposits"]["value"] and
         values["average_interest_bearing_deposits"]["value"] > 0,
         "bank_interest_or_deposit_reconciliation_failed")
    return values, {"statement_table": statement_idx,
                    "deposit_table": deposit_idx,
                    "average_table": average_idx}


def compare_author(independent: dict, author: dict, *, profile: str,
                   year: int) -> tuple[int, list[dict]]:
    expected = (PENSION_KEYS if profile == "pension" else
                (*BANK_TAGS, "average_interest_bearing_deposits"))
    need(set(author) == set(expected), "author_field_keys_changed")
    count = 0
    scope_mismatches = []
    for key in expected:
        own = independent[key]
        prior = author[key]
        prior_value = prior.get("value")
        own_value = own["value"]
        need((prior_value is None and own_value is None) or
             (prior_value is not None and own_value is not None and
              Decimal(str(prior_value)) == own_value),
             f"source_value_mismatch:{profile}:{year}:{key}")
        need(prior.get("presence") == own["presence"] and
             prior.get("ixbrl_tag") == own.get("tag") and
             prior.get("context_ref") == own.get("context_ref") and
             prior.get("row_sha256") == own.get("row_sha256"),
             f"source_locator_or_presence_mismatch:{profile}:{year}:{key}")
        if own.get("context") is not None:
            period = prior.get("context_period")
            need(period is not None and all(period.get(name) == own["context"].get(name)
                        for name in ("instant", "startdate", "enddate")),
                 f"source_period_mismatch:{profile}:{year}:{key}")
            if period.get("dimension_member_count") != len(own["context"]["members"]):
                scope_mismatches.append({
                    "profile": profile, "year": year, "field": key,
                    "author_dimension_member_count":
                        period.get("dimension_member_count"),
                    "actual_dimension_member_count":
                        len(own["context"]["members"]),
                })
        if key == "other_disclosed":
            need(len(prior.get("components", [])) == len(own["components"]),
                 "pension_other_component_count_mismatch")
            for left, right in zip(own["components"], prior["components"]):
                need(Decimal(str(right.get("value") if right.get("value") is not None
                                 else 0)) == signed(left["value"]) and
                     right.get("row_sha256") == left["row_sha256"],
                     "pension_other_component_value_mismatch")
        count += 1
    return count, scope_mismatches


def verify_case(root: Path, plan_record: dict, author_case: dict,
                index: int) -> tuple[dict, dict]:
    raw_case = (root / "source-case.private.json").read_bytes()
    source = json.loads(raw_case)
    identity = source["identity"]
    need(source.get("source_index") == index and identity == plan_record and
         source.get("semantic_fact_review_completed") is False and
         source.get("excel_web_admitted") is False,
         "frozen_train_source_or_identity_changed")
    for kind, record in source["response"].items():
        filename = {"10k": "10k.html", "support": "support.html",
                    "companyfacts": "companyfacts.json", "index": "index.html",
                    "submissions": "submissions.json"}[kind]
        raw = (root / filename).read_bytes()
        need(digest(raw) == record["sha256"] and len(raw) == record["bytes"]
             and record["status"] == 200 and
             urlparse(record["url"]).netloc in ("www.sec.gov", "data.sec.gov"),
             "original_sec_response_hash_or_origin_changed")
    companyfacts = json.loads((root / "companyfacts.json").read_bytes())
    submissions = json.loads((root / "submissions.json").read_bytes())
    need(companyfacts.get("cik") == identity["issuer_cik"] and
         int(submissions.get("cik", "-1")) == identity["issuer_cik"],
         "companyfacts_or_submissions_issuer_mismatch")
    profile = "pension" if index in (2, 3) else "bank"
    document = "10k" if profile == "pension" else "support"
    document_url = source["urls"][document]
    archive_fragment = "/" + identity["accession"].replace("-", "") + "/"
    need(archive_fragment in document_url and
         str(identity["issuer_cik"]) in document_url and
         author_case["source"]["original_sec_url"] == document_url,
         "source_document_or_accession_mismatch")
    index_tree = html.fromstring((root / "index.html").read_bytes())
    basename = document_url.rsplit("/", 1)[1]
    need(any(basename in node.get("href", "")
             for node in index_tree.xpath("//a[@href]")),
         "source_document_not_in_same_accession_index")
    tree = html.fromstring((root / (document + ".html")).read_bytes())
    primary = (tree if document == "10k" else
               html.fromstring((root / "10k.html").read_bytes()))
    context_map = contexts(tree)
    if not context_map:
        context_map = contexts(primary)
    need(context_map and all(int(value["entity"].lstrip("0") or "0") ==
                             identity["issuer_cik"]
                             for value in context_map.values()),
         "source_xbrl_context_entity_mismatch")
    periods = []
    field_count = 0
    scope_mismatches = []
    for position, year in enumerate(YEARS):
        own, source_meta = (pension_fields(tree, context_map,
                                           scope="us_pension" if index == 3
                                           else "pension", year=year)
                            if profile == "pension" else
                            bank_fields(tree, context_map, companyfacts,
                                        identity["accession"], year=year))
        author_period = author_case["periods"][position]
        need(author_period.get("period_end") == f"{year}-12-31",
             "author_period_order_mismatch")
        checked_count, mismatches = compare_author(
            own, author_period["fields"], profile=profile, year=year)
        field_count += checked_count
        scope_mismatches.extend(mismatches)
        periods.append({"year": year,
                        "fields": {key: {"value": None if item["value"] is None
                                         else str(item["value"]),
                                         "presence": item["presence"],
                                         "tag": item.get("tag"),
                                         "context_ref": item.get("context_ref"),
                                         "row_sha256": item.get("row_sha256")}
                                   for key, item in own.items()},
                        "source_meta": source_meta})
    if profile == "pension":
        need(periods[0]["fields"]["closing_assets"]["value"] ==
             periods[1]["fields"]["opening_assets"]["value"],
             "pension_cross_year_carry_mismatch")
    return ({"case_index": index, "profile": profile,
             "issuer_cik": identity["issuer_cik"],
             "accession": identity["accession"],
             "source_document_sha256": source["response"][document]["sha256"],
             "companyfacts_sha256": source["response"]["companyfacts"]["sha256"],
             "field_count": field_count, "periods": periods,
             "scope_metadata_mismatches": scope_mismatches},
            {"profile": profile, "fields_checked": field_count,
             "scope_metadata_mismatch_count": len(scope_mismatches),
             "companyfacts_same_accession_checks": (10 if profile == "bank" else 0),
             "dimensioned_pension_facts_not_in_companyfacts": profile == "pension"})


def audit(*, raw_root: Path, source_plan: Path,
          author_review: Path) -> tuple[dict, dict]:
    plan_raw = source_plan.read_bytes()
    plan = json.loads(plan_raw)
    author_raw = author_review.read_bytes()
    author = json.loads(author_raw)
    need(plan.get("schema") ==
         "envloop.sec_excel_train_22_raw_source_plan.private.v1" and
         len(plan.get("records", [])) == 22 and
         author.get("source_plan_sha256") == digest(plan_raw) and
         len(author.get("cases", [])) == 4,
         "frozen_train_plan_or_author_review_shape_changed")
    cases = []
    aggregates = []
    for index in (2, 3, 4, 5):
        author_case = next((item for item in author["cases"]
                            if item.get("case_index") == index), None)
        need(author_case is not None, "author_case_missing")
        private, public = verify_case(
            raw_root / f"source-{index:02}",
            plan["records"][index], author_case, index)
        cases.append(private)
        aggregates.append(public)
    need(len({row["issuer_cik"] for row in cases}) == 4 and
         Counter(row["profile"] for row in cases) ==
            {"pension": 2, "bank": 2},
         "issuer_or_graph_family_reused")
    mismatches = sum(item["scope_metadata_mismatch_count"]
                     for item in aggregates)
    all_fields = [field for case in cases for period in case["periods"]
                  for field in period["fields"].values()]
    private = {
        "schema": "envloop.sec_excel_train_next_four_second_person.private.v1",
        "status": ("source_values_match_scope_metadata_correction_required"
                   if mismatches else "independent_original_source_field_review_passed"),
        "source_plan_sha256": digest(plan_raw),
        "author_review_sha256": digest(author_raw),
        "cases": cases,
        "official_final_admissions": 0,
    }
    public = {
        "schema": "envloop.sec_excel_train_next_four_second_person.public.v1",
        "status": private["status"],
        "source_plan_sha256": private["source_plan_sha256"],
        "author_review_sha256": private["author_review_sha256"],
        "raw_source_bundles_reopened": 4,
        "distinct_issuers": 4,
        "pension_graphs": 2,
        "bank_graphs": 2,
        "fiscal_years_checked": [2024, 2025],
        "numeric_and_presence_fields_compared": sum(
            item["fields_checked"] for item in aggregates),
        "fields_with_numeric_values": sum(
            field["value"] is not None for field in all_fields),
        "not_separately_reported_fields": sum(
            field["presence"] == "not_separately_reported"
            for field in all_fields),
        "disclosed_dash_fields": sum(
            field["presence"] == "disclosed_dash"
            for field in all_fields),
        "bank_same_accession_companyfacts_checks": sum(
            item["companyfacts_same_accession_checks"]
            for item in aggregates),
        "pension_dimensioned_facts_not_claimed_companyfacts_verified": True,
        "bank_annual_average_facts_untagged_table_only": True,
        "pension_unreported_separate_from_filed_zero": True,
        "sign_and_scope_conventions_checked": True,
        "scope_dimension_metadata_mismatches": mismatches,
        "mismatches": mismatches,
        "excel_web_gui_controls": 0,
        "model_calls": 0,
        "official_final_admissions": 0,
    }
    return private, public


def write_new(path: Path, value: dict, *, public: bool) -> str:
    raw = (json.dumps(value, sort_keys=True,
                      indent=2 if public else None,
                      separators=None if public else (",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not public:
        path.parent.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o644 if public else 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--author-review", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Exclusive second-person audit outputs required")
    private, public = audit(
        raw_root=args.raw_root, source_plan=args.source_plan,
        author_review=args.author_review)
    private_sha = write_new(args.private_out, private, public=False)
    public["private_independent_audit_sha256"] = private_sha
    public_sha = write_new(args.public_out, public, public=True)
    print(json.dumps({"status": public["status"],
                      "public_sha256": public_sha,
                      "fields_compared": public["numeric_and_presence_fields_compared"],
                      "mismatches": public["mismatches"]}, sort_keys=True))


if __name__ == "__main__":
    main()
