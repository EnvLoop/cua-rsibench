"""Bind the four debt-face rows in one TRAIN-only SEC source to saved 10-K bytes.

This adds evaluator-private evidence to the earlier semantic review. It neither
opens any final workbook nor changes that review's frozen bytes.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from lxml import html


LABELS = ("Senior notes due 2025", "Senior notes due 2027",
          "Senior notes due 2031", "Senior notes due 2032")


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _plain(node) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _number(node) -> float:
    text = "".join(node.itertext()).strip().replace(",", "")
    value = float("".join(c for c in text if c.isdigit() or c == "."))
    return -value if node.get("sign") == "-" else value


def extend(pilot_path: Path, raw_dir: Path, review_path: Path) -> dict:
    pilot_raw = pilot_path.read_bytes()
    pilot = json.loads(pilot_raw)
    record = pilot["records"][3]
    if not record["template_family"].endswith("interest_coverage_distinct_v1"):
        raise ValueError("wrong_train_source_profile")
    review_raw = review_path.read_bytes()
    review = json.loads(review_raw)
    filing_raw = (raw_dir / "source-03-10k.html").read_bytes()
    if (review["source_index"] != 3 or review["pilot_sha256"] != _digest(pilot_raw)
            or review["raw_sha256"]["10k"] != _digest(filing_raw)
            or review["identity"]["accession"] != record["accession"]):
        raise ValueError("source_identity_or_raw_hash_changed")
    tree = html.fromstring(filing_raw)
    tables = [table for table in tree.xpath("//table")
              if all(label in _plain(table) for label in (LABELS[0], LABELS[-1],
                                                        "Total senior notes"))
              and "Principal As of December 31, 2025 2024" in _plain(table)]
    if len(tables) != 1:
        raise ValueError("original_debt_note_table_not_unique")
    table = tables[0]
    rows = []
    for j, label in enumerate(LABELS):
        found = [row for row in table.xpath(".//tr") if _plain(row).startswith(label)]
        if len(found) != 1:
            raise ValueError("original_instrument_row_not_unique")
        row = found[0]
        row_text = _plain(row)
        row_sha = _digest(row_text.encode())
        if any(period["debt_note_row_sha256"][j] != row_sha
               for period in review["annual_periods"]):
            raise ValueError("source_review_row_hash_changed")
        values = []
        for period_index, period in enumerate(record["periods"]):
            expected = float(period["debt_principal_components"][j])
            end = period["period_end"]
            matched = []
            for node in row.xpath('.//*[name()="ix:nonfraction"]'):
                if (node.get("name") != "us-gaap:DebtInstrumentFaceAmount"
                        or node.get("scale") != "6" or node.get("unitref") != "usd"):
                    continue
                context_id = node.get("contextref")
                context = tree.xpath(
                    '//*[name()="xbrli:context" and @id=$cid]', cid=context_id)
                if len(context) != 1:
                    raise ValueError("source_context_not_unique")
                ends = context[0].xpath('.//*[name()="xbrli:instant"]')
                if (len(ends) != 1 or ends[0].text != end
                        or not context[0].xpath('.//*[contains(name(),"member")]')):
                    continue
                try:
                    observed = _number(node)
                except ValueError:
                    continue
                if abs(observed - expected) < 1e-9:
                    matched.append({"ix_id": node.get("id"),
                                    "context_ref": context_id,
                                    "unit": "USD millions", "signed_value": expected})
            if expected:
                if len(matched) != 1:
                    raise ValueError("source_debt_face_value_or_context_ambiguous")
                values.append(matched[0])
            else:
                if matched or "—" not in row_text:
                    raise ValueError("source_zero_dash_not_supported")
                if ((j == 0 and period_index == 0 and
                     not row_text.endswith("— $ 500.0")) or
                    (j == 3 and period_index == 1 and
                     not row_text.endswith("500.0 —"))):
                    raise ValueError("source_zero_dash_wrong_period")
                values.append({"ix_id": None, "context_ref": None,
                               "unit": "USD millions", "signed_value": 0.0,
                               "derivation": "dated original note table dash"})
        rows.append({"label": label, "row_sha256": row_sha, "period_values": values})
    for i, period in enumerate(record["periods"]):
        if sum(row["period_values"][i]["signed_value"] for row in rows) != period["debt_principal_total"]:
            raise ValueError("gross_principal_component_sum_changed")
        reconcile = review["annual_periods"][i]["carrying_reconciliation"]
        if abs(period["debt_principal_total"] - reconcile["unamortized_cost"]
               - reconcile["carrying_value"]) > 1e-9:
            raise ValueError("gross_principal_carrying_bridge_changed")
    return {"schema": "envloop.sec_four_train_debt_face_extension.private.v1",
            "scope": "original SEC train source 03 only; no final task or workbook",
            "pilot_sha256": _digest(pilot_raw), "original_10k_sha256": _digest(filing_raw),
            "prior_semantic_review_sha256": _digest(review_raw),
            "identity": {"issuer_cik": record["issuer_cik"],
                         "accession": record["accession"]},
            "period_end": [period["period_end"] for period in record["periods"]],
            "rows": rows,
            "source_context_audit": "one original inline-XBRL face fact per nonzero instrument-year; dated note dash for zeros"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=Path, required=True)
    ap.add_argument("--raw-dir", type=Path, required=True)
    ap.add_argument("--review", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    args = ap.parse_args()
    result = extend(args.pilot, args.raw_dir, args.review)
    args.private_out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(args.private_out.parent, 0o700)
    args.private_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    os.chmod(args.private_out, 0o600)
    print(json.dumps({"status": "source_extension_verified",
                      "row_count": len(result["rows"]),
                      "period_count": len(result["period_end"]),
                      "extension_sha256": _digest(args.private_out.read_bytes())}))


if __name__ == "__main__":
    main()
