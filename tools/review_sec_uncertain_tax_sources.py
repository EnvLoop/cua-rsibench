"""Review TRAIN-only SEC uncertain-tax-position sources against filed iXBRL.

The emitted receipt is evaluator-private because it contains source identities and
the field-level answer key. This tool does not create Excel tasks or admit any
final-evaluation cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


BRIDGE_ANCHORS = (
    "aggregate changes in the balance of gross unrecognized tax benefits",
    "a reconciliation of the beginning and ending amount of unrecognized tax benefits",
)
FIELDS = {
    "opening": (r"^(?:beginning balance|balance at january 1)$", 1),
    "current_year_additions": (r"^additions based on tax positions related to the current year$", 1),
    "prior_year_additions": (r"^additions for tax positions of prior years$", 1),
    "prior_year_reductions": (r"^reductions for tax positions of prior years$", -1),
    "settlements": (r"^settlements$", -1),
    "lapse": (r"^lapse of statute of limitations$", -1),
    "closing": (r"^(?:ending balance|balance at december 31)$", 1),
}
REQUIRED = {
    "opening",
    "current_year_additions",
    "prior_year_additions",
    "prior_year_reductions",
    "settlements",
    "closing",
}
ACCRUED_TAG = "UnrecognizedTaxBenefitsIncomeTaxPenaltiesAndInterestAccrued"
EXPENSE_TAGS = (
    "UnrecognizedTaxBenefitsInterestOnIncomeTaxesExpense",
    "UnrecognizedTaxBenefitsIncomeTaxPenaltiesAndInterestExpense",
)
TEMPLATE_COMPONENTS = (
    "opening",
    "current_year_additions",
    "prior_year_additions",
    "prior_year_reductions",
    "settlements",
    "lapse",
    "translation",
    "other",
    "closing",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(node: object) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _period(context: object) -> dict[str, str]:
    period = context.find("xbrli:period")
    if period is None:
        raise ValueError("context lacks period")
    instant = period.find("xbrli:instant")
    if instant is not None:
        return {"instant": _text(instant)}
    start = period.find("xbrli:startdate")
    end = period.find("xbrli:enddate")
    if start is None or end is None:
        raise ValueError("context lacks start/end")
    return {"start": _text(start), "end": _text(end)}


def _ix_value_musd(ix: object) -> int:
    if ix.get("scale") != "6":
        raise ValueError(f"expected millions scale, got {ix.get('scale')!r}")
    val = int(_text(ix).replace(",", ""))
    if ix.get("sign") == "-":
        val = -val
    return val


def _companyfacts_match(facts: dict, accession: str, ix: object, period: dict) -> bool:
    name = ix.get("name", "")
    if not name.startswith("us-gaap:"):
        return False
    tag = name.split(":", 1)[1]
    entries = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
    expected = _ix_value_musd(ix) * 1_000_000
    for entry in entries:
        if entry.get("form") != "10-K" or entry.get("accn") != accession or entry.get("val") != expected:
            continue
        if "instant" in period and entry.get("end") == period["instant"] and not entry.get("start"):
            return True
        if entry.get("start") == period.get("start") and entry.get("end") == period.get("end"):
            return True
    return False


def _field(ix: object, document: str, context: dict, facts: dict, accession: str,
           *, row_label: str | None = None, signed: int | None = None) -> dict:
    context_ref = ix.get("contextref")
    period = _period(context[context_ref])
    match = _companyfacts_match(facts, accession, ix, period)
    if not match:
        raise ValueError(f"companyfacts mismatch: {document} {ix.get('name')} {context_ref}")
    result = {
        "document": document,
        "ixbrl_tag": ix.get("name"),
        "ixbrl_context_ref": context_ref,
        "context_period": period,
        "filed_musd": _ix_value_musd(ix),
        "companyfacts_same_accession_match": True,
    }
    if row_label is not None:
        result["table_row_label"] = row_label
    if signed is not None:
        result["bridge_signed_musd"] = signed
    return result


def _source_review(source_dir: Path, plan_record: dict) -> dict:
    source_case = json.loads((source_dir / "source-case.private.json").read_text())
    identity = source_case["identity"]
    if identity != plan_record:
        raise ValueError(f"source-plan identity mismatch for {source_dir.name}")
    if identity["final_graph_reservation"] != "uncertain_tax_position_activity_and_interest_scope":
        raise ValueError("wrong source family")
    if source_case["semantic_fact_review_completed"] is not False:
        raise ValueError("source capture must predate semantic review")
    accession = identity["accession"]
    documents: dict[str, object] = {}
    hashes: dict[str, str] = {}
    response_map = {"10k.html": "10k", "companyfacts.json": "companyfacts", "support.html": "support"}
    for file_name, response_key in response_map.items():
        path = source_dir / file_name
        if not path.exists():
            continue
        digest = _sha256(path)
        if digest != source_case["response"][response_key]["sha256"]:
            raise ValueError(f"captured raw hash drift: {path}")
        hashes[file_name] = digest
        if file_name.endswith(".html"):
            # Inline-XBRL XHTML is parsed as HTML here to normalize tag case.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                documents[file_name] = BeautifulSoup(path.read_bytes(), "lxml")
    facts_path = source_dir / "companyfacts.json"
    facts = json.loads(facts_path.read_text())
    primary = documents["10k.html"]
    contexts = {c.get("id"): c for c in primary.find_all("xbrli:context") if c.get("id")}
    if not contexts:
        raise ValueError("no primary-document XBRL contexts")

    located = []
    for document_name, soup in documents.items():
        for text_node in soup.find_all(string=True):
            content = str(text_node).lower()
            if any(anchor in content for anchor in BRIDGE_ANCHORS):
                table = text_node.find_next("table")
                if table is not None:
                    located.append((document_name, content, table))
    if len(located) != 1:
        raise ValueError(f"expected exactly one filed bridge table, got {len(located)}")
    bridge_document, anchor_text, table = located[0]
    rows: dict[str, tuple[str, list]] = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        label = _text(cells[0])
        for field, (pattern, _) in FIELDS.items():
            if re.fullmatch(pattern, label, flags=re.IGNORECASE):
                if field in rows:
                    raise ValueError(f"duplicate bridge row: {field}")
                values = tr.find_all("ix:nonfraction")
                rows[field] = (label, values)
    missing = REQUIRED - rows.keys()
    if missing:
        raise ValueError(f"missing required bridge rows: {sorted(missing)}")
    if any(len(values) < 2 for _, values in rows.values()):
        raise ValueError("bridge lacks two fully tagged periods")

    periods = []
    for column in (0, 1):
        fields = {}
        for field, (label, values) in rows.items():
            ix = values[column]
            sign = FIELDS[field][1]
            signed = _ix_value_musd(ix) * sign
            fields[field] = _field(ix, bridge_document, contexts, facts, accession,
                                   row_label=label, signed=signed)
        closing_period = fields["closing"]["context_period"]
        opening_period = fields["opening"]["context_period"]
        if "instant" not in closing_period or "instant" not in opening_period:
            raise ValueError("opening/closing must be instant values")
        period_end = closing_period["instant"]
        activity = [fields[k]["context_period"] for k in REQUIRED - {"opening", "closing"}]
        if any(p.get("end") != period_end or "start" not in p for p in activity):
            raise ValueError("activity-period mismatch")
        if len({p["start"] for p in activity}) != 1:
            raise ValueError("activity starts disagree")
        if date.fromisoformat(activity[0]["start"]) - date.fromisoformat(opening_period["instant"]) != timedelta(days=1):
            raise ValueError("opening instant is not the day before activity")
        if "lapse" in fields and fields["lapse"]["context_period"] != activity[0]:
            raise ValueError("lapse period mismatch")
        computed = (
            sum(v["bridge_signed_musd"] for k, v in fields.items() if k != "closing")
            - fields["closing"]["bridge_signed_musd"]
        )
        if computed != 0:
            raise ValueError(f"gross bridge arithmetic mismatch: {computed}")
        if column == 1 and period_end >= periods[0]["period_end"]:
            raise ValueError("prior period is not earlier")
        periods.append({
            "period_start": activity[0]["start"],
            "period_end": period_end,
            "opening_instant": opening_period["instant"],
            "fields": fields,
            "bridge_arithmetic_delta_musd": computed,
        })

    if periods[0]["fields"]["opening"]["bridge_signed_musd"] != periods[1]["fields"]["closing"]["bridge_signed_musd"]:
        raise ValueError("gross position does not carry between periods")

    for period in periods:
        current_end = period["period_end"]
        interest: dict[str, dict] = {}
        for document_name, soup in documents.items():
            for ix in soup.find_all("ix:nonfraction"):
                tag = ix.get("name", "").split(":")[-1]
                if tag not in (*EXPENSE_TAGS, ACCRUED_TAG):
                    continue
                context_ref = ix.get("contextref")
                if context_ref not in contexts:
                    continue
                ix_period = _period(contexts[context_ref])
                if ix_period.get("end", ix_period.get("instant")) != current_end:
                    continue
                if tag == ACCRUED_TAG and "instant" not in ix_period:
                    continue
                if tag in EXPENSE_TAGS and "start" not in ix_period:
                    continue
                if tag in EXPENSE_TAGS and ix_period["start"] != period["period_start"]:
                    continue
                if ix.find_parent("table") is table:
                    raise ValueError("interest/penalties field appears inside gross bridge")
                if tag in interest:
                    raise ValueError(f"duplicate tax interest field for {current_end}: {tag}")
                interest[tag] = _field(ix, document_name, contexts, facts, accession)
        if ACCRUED_TAG not in interest or len([t for t in EXPENSE_TAGS if t in interest]) != 1:
            raise ValueError(f"missing or ambiguous interest scope for {current_end}")
        period["interest_and_penalties_outside_gross_bridge"] = interest
        period["template_fields"] = {
            name: (
                {
                    "status": "reported",
                    "signed_value_musd": period["fields"][name]["bridge_signed_musd"],
                    "source_field": period["fields"][name],
                }
                if name in period["fields"]
                else {
                    "status": "not_separately_reported",
                    "signed_value_musd": None,
                    "source_field": None,
                }
            )
            for name in TEMPLATE_COMPONENTS
        }
        period["template_fields"]["accrued_interest_penalties"] = {
            "status": "reported",
            "signed_value_musd": interest[ACCRUED_TAG]["filed_musd"],
            "source_field": interest[ACCRUED_TAG],
        }
        for field_name, tag in (
            ("net_interest_expense", EXPENSE_TAGS[0]),
            ("combined_interest_penalties_expense_benefit", EXPENSE_TAGS[1]),
        ):
            period["template_fields"][field_name] = (
                {
                    "status": "reported",
                    "signed_value_musd": interest[tag]["filed_musd"],
                    "source_field": interest[tag],
                }
                if tag in interest
                else {
                    "status": "not_separately_reported",
                    "signed_value_musd": None,
                    "source_field": None,
                }
            )

    return {
        "source_index": source_case["source_index"],
        "identity": identity,
        "raw_sha256": hashes,
        "bridge_location": {
            "document": bridge_document,
            "anchor_phrase": next(a for a in BRIDGE_ANCHORS if a in anchor_text),
            "locator": "first table following anchor phrase, then row label and ixbrl context",
            "context_definition_document": "10k.html",
        },
        "periods": periods,
        "unreported_components": {
            "lapse": "filed" if "lapse" in rows else "not_separately_reported",
            "translation": "not_separately_reported",
            "other": "not_separately_reported",
        },
        "semantic_source_review": "pass",
        "excel_web_admitted": False,
        "official_final_case_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-private", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.private_plan.read_text())
    records = plan["records"][:2]
    if len(records) != 2:
        raise ValueError("expected exactly two tax-source plan records")
    reviews = [_source_review(args.raw_root / f"source-{i:02d}", r) for i, r in enumerate(records)]
    if [r["source_index"] for r in reviews] != [0, 1]:
        raise ValueError("source index drift")
    receipt = {
        "schema": "envloop.sec_tax_train_two_field_review.private.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "TRAIN-only source semantic review; no workbook, GUI, or final admission",
        "source_plan_sha256": _sha256(args.private_plan),
        "source_count": 2,
        "source_reviews": reviews,
    }
    args.output_private.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output_private, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"status": "pass", "source_count": 2, "output_private": str(args.output_private)}))


if __name__ == "__main__":
    main()
