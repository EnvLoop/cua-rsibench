"""Offline, evaluator-only semantic review of four SEC transfer source bundles.

Reads saved primary-document, filing-index, and CompanyFacts bytes. Emits private
per-source field locators and a field-limited public commitment. No network,
workbook, browser, model, or benchmark admission occurs here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from lxml import html


CASH_TAGS = {
    "operating": "NetCashProvidedByUsedInOperatingActivities",
    "investing": "NetCashProvidedByUsedInInvestingActivities",
    "financing": "NetCashProvidedByUsedInFinancingActivities",
    "fx": "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "net_change": "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
    "beginning": "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "ending": "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
}
INTEREST_TAGS = {
    "operating_income": "OperatingIncomeLoss",
    "cash_from_operations": "NetCashProvidedByUsedInOperatingActivities",
}
NEGATIVE_CASH_FIELDS = {"investing", "financing", "fx", "net_change"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain(node) -> str:
    return " ".join(" ".join(node.itertext()).split())


def number(node) -> float:
    raw = "".join(node.itertext()).strip()
    clean = re.sub(r"[^0-9.]", "", raw)
    value = float(clean)
    return -value if node.get("sign") == "-" else value


def context_map(tree) -> dict:
    out = {}
    for node in tree.xpath('//*[name()="xbrli:context"]'):
        def child(name):
            found = node.xpath(f'.//*[name()="xbrli:{name}"]')
            return found[0].text if found else None
        out[node.get("id")] = {
            "start": child("startdate"),
            "end": child("enddate") or child("instant"),
            "dimensional": bool(node.xpath('.//*[contains(name(),"member")]')),
        }
    return out


def fact_match(
    tree, contexts: dict, companyfacts: dict, accession: str, *, tag: str,
    expected: float, end: str, start: str | None = None,
    row_contains: str | None = None, allow_dimensions: bool = False,
) -> dict:
    matches = []
    for node in tree.xpath('//*[name()="ix:nonfraction"]'):
        if node.get("name") != f"us-gaap:{tag}" or node.get("unitref") != "usd" or node.get("scale") != "6":
            continue
        ctx = contexts.get(node.get("contextref"), {})
        if ctx.get("end") != end or ctx.get("start") != start:
            continue
        if ctx.get("dimensional") and not allow_dimensions:
            continue
        try:
            observed = number(node)
        except ValueError:
            continue
        if abs(observed - expected) > 0.00001:
            continue
        row = node.xpath("ancestor::tr[1]")
        row_text = plain(row[0]) if row else ""
        if row_contains and row_contains.lower() not in row_text.lower():
            continue
        matches.append((node, ctx, row_text))
    if not matches:
        raise ValueError(f"source field absent or ambiguous: {tag} {end} {start} {expected}")
    # Identical repeated XBRL instances are acceptable; retain one exact row locator.
    node, ctx, row_text = matches[0]
    entries = (
        companyfacts.get("facts", {}).get("us-gaap", {}).get(tag, {})
        .get("units", {}).get("USD", [])
    )
    expected_usd = round(expected * 1_000_000)
    cf_match = any(
        item.get("accn") == accession
        and item.get("form") == "10-K"
        and item.get("end") == end
        and item.get("start") == start
        and item.get("val") == expected_usd
        for item in entries
    )
    return {
        "tag": f"us-gaap:{tag}",
        "ix_id": node.get("id"),
        "context_ref": node.get("contextref"),
        "context": ctx,
        "unit": "USD millions",
        "signed_value": expected,
        "row_sha256": sha(row_text.encode()) if row_text else None,
        "companyfacts_same_accession_exact_value": cf_match,
        "companyfacts_limitation": (
            "dimension-specific note fact not represented in CompanyFacts"
            if allow_dimensions and not cf_match else None
        ),
    }


def row_for(table, label: str):
    rows = [r for r in table.xpath(".//tr") if plain(r).startswith(label)]
    if len(rows) != 1:
        raise ValueError(f"expected one note row for {label}, found {len(rows)}")
    return rows[0], plain(rows[0])


def nums(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def check_identity(i: int, rec: dict, raw: dict, tree, companyfacts: dict) -> dict:
    index = raw["index"].decode(errors="replace")
    dei = {
        node.get("name"): plain(node)
        for node in tree.xpath('//*[name()="ix:nonnumeric"]')
        if (node.get("name") or "").startswith("dei:")
    }
    checks = {
        "index_has_accession": rec["accession"] in index,
        "index_has_primary_document": rec["primary_document"] in index,
        "index_has_form_10k": "10-K" in index,
        "filing_dei_form_10k": dei.get("dei:DocumentType") == "10-K",
        "filing_dei_cik_match": dei.get("dei:EntityCentralIndexKey") == str(rec["issuer_cik"]).zfill(10),
        "companyfacts_cik_match": companyfacts.get("cik") == int(rec["issuer_cik"]),
        "filing_period_end_year_match": rec["report_period"][:4] in dei.get("dei:DocumentPeriodEndDate", ""),
    }
    if not all(checks.values()):
        raise ValueError(f"source {i}: filing identity/form mismatch: {checks}")
    return checks


def cash_review(i: int, rec: dict, tree, contexts: dict, companyfacts: dict) -> tuple[list, list]:
    periods = []
    checks = []
    for p in rec["periods"]:
        end = p["period_end"]
        dur_start = next(
            (
                c["start"] for c in contexts.values()
                if c["end"] == end and c["start"] and not c["dimensional"]
            ),
            None,
        )
        if not dur_start:
            raise ValueError(f"source {i}: annual start unavailable")
        fields = {}
        for field, tag in CASH_TAGS.items():
            if field == "beginning":
                prev_end = next(
                    (q["period_end"] for q in rec["periods"] if q["ending"] == p["beginning"] and q["period_end"] < end),
                    None,
                )
                if not prev_end:
                    from datetime import timedelta
                    prev_end = (datetime.fromisoformat(dur_start) - timedelta(days=1)).date().isoformat()
                field_end, field_start = prev_end, None
                row_contains = "beginning"
            elif field in ("ending", "cash"):
                field_end, field_start = end, None
                row_contains = "end of" if field == "ending" else "Cash and cash equivalents"
            else:
                field_end, field_start = end, dur_start
                row_contains = None
            fields[field] = fact_match(
                tree, contexts, companyfacts, rec["accession"], tag=tag,
                expected=p[field], end=field_end, start=field_start,
                row_contains=row_contains,
            )
            if not fields[field]["companyfacts_same_accession_exact_value"]:
                raise ValueError(f"source {i}: CompanyFacts disagreement for {field} {end}")
        if i == 0 or p["restricted"] != 0:
            restricted_tag = "RestrictedCashAndCashEquivalents" if i == 0 else "RestrictedCash"
            fields["restricted"] = fact_match(
                tree, contexts, companyfacts, rec["accession"], tag=restricted_tag,
                expected=p["restricted"], end=end,
            )
            if not fields["restricted"]["companyfacts_same_accession_exact_value"]:
                raise ValueError(f"source {i}: restricted-cash CompanyFacts disagreement {end}")
        else:
            fields["restricted"] = {
                "derivation": "cash-flow ending total minus same-date balance-sheet cash",
                "signed_value": p["restricted"],
                "direct_restricted_fact": False,
            }
        equations = {
            "flow_components_equal_net_change": abs(sum(p[x] for x in ("operating", "investing", "financing", "fx")) - p["net_change"]) < 0.00001,
            "beginning_plus_net_change_equals_ending": abs(p["beginning"] + p["net_change"] - p["ending"]) < 0.00001,
            "ending_equals_cash_plus_restricted": abs(p["cash"] + p["restricted"] - p["ending"]) < 0.00001,
        }
        if not all(equations.values()):
            raise ValueError(f"source {i}: cash identity disagreement {end}")
        periods.append({"period_end": end, "period_start": dur_start, "fields": fields, "equations": equations})
        checks.extend(equations)
    return periods, checks


def interest_review(i: int, rec: dict, tree, contexts: dict, companyfacts: dict) -> tuple[list, list]:
    periods = []
    checks = []
    for p in rec["periods"]:
        end = p["period_end"]
        dur_start = next(
            (c["start"] for c in contexts.values() if c["end"] == end and c["start"] and not c["dimensional"]),
            None,
        )
        if not dur_start:
            raise ValueError(f"source {i}: annual start unavailable")
        fields = {}
        for field, tag in INTEREST_TAGS.items():
            fields[field] = fact_match(
                tree, contexts, companyfacts, rec["accession"], tag=tag,
                expected=p[field], start=dur_start, end=end,
            )
        interest_tag = "InterestExpenseNonoperating" if i == 2 else "InterestExpense"
        fields["interest_expense_abs"] = fact_match(
            tree, contexts, companyfacts, rec["accession"], tag=interest_tag,
            expected=p["interest_expense_abs"], start=dur_start, end=end,
            row_contains="Interest expense",
        )
        if any(not v["companyfacts_same_accession_exact_value"] for v in fields.values()):
            raise ValueError(f"source {i}: CompanyFacts disagreement for annual operating/interest/CFO")
        if i == 2:
            fields["debt_principal_total"] = fact_match(
                tree, contexts, companyfacts, rec["accession"],
                tag="DebtInstrumentCarryingAmount", expected=p["debt_principal_total"],
                end=end, row_contains="Total debt, principal amount",
            )
            if not fields["debt_principal_total"]["companyfacts_same_accession_exact_value"]:
                raise ValueError("source 2: CompanyFacts debt-principal disagreement")
        periods.append({"period_end": end, "period_start": dur_start, "fields": fields})
    if i == 2:
        tables = [
            t for t in tree.xpath("//table")
            if "Total core debt" in plain(t) and "Total DFS related debt" in plain(t)
            and "January 30, 2026" in plain(t) and "January 31, 2025" in plain(t)
        ]
        if len(tables) != 1:
            raise ValueError("source 2: uniquely dated debt breakdown absent")
        table = tables[0]
        rows = []
        for label in ("Total core debt", "Total DFS related debt", "Other", "Total debt, principal amount"):
            _, txt = row_for(table, label)
            rows.append({"label": label, "values": nums(txt[len(label):]), "row_sha256": sha(txt.encode())})
        for col, p in ((0, rec["periods"][0]), (2, rec["periods"][1])):
            actual = [row["values"][col] for row in rows[:3]]
            if actual != list(map(float, p["debt_principal_components"])):
                raise ValueError("source 2: component row mismatch")
            if sum(actual) != p["debt_principal_total"] or rows[3]["values"][col] != p["debt_principal_total"]:
                raise ValueError("source 2: debt principal sum mismatch")
            periods[0 if col == 0 else 1]["debt_note_rows"] = rows
            checks.append("dated_core_plus_dfs_plus_other_equals_direct_principal")
    else:
        tables = [
            t for t in tree.xpath("//table")
            if "Senior notes due 2025" in plain(t)
            and "Senior notes due 2032" in plain(t)
            and "Total senior notes" in plain(t)
            and "Principal As of December 31, 2025 2024" in plain(t)
        ]
        if len(tables) != 1:
            raise ValueError("source 3: uniquely dated senior-note table absent")
        table = tables[0]
        debt_rows = []
        for label in ("Senior notes due 2025", "Senior notes due 2027", "Senior notes due 2031", "Senior notes due 2032"):
            node, txt = row_for(table, label)
            debt_rows.append({"label": label, "row_sha256": sha(txt.encode()), "text": txt, "node": node})
        if not debt_rows[0]["text"].endswith("— $ 500.0"):
            raise ValueError("source 3: first-year zero is not in the 2025 column")
        if not debt_rows[3]["text"].endswith("500.0 —"):
            raise ValueError("source 3: second-year zero is not in the 2024 column")
        for idx, p in enumerate(rec["periods"]):
            for j, expected in enumerate(p["debt_principal_components"]):
                row = debt_rows[j]
                if expected == 0:
                    if "—" not in row["text"]:
                        raise ValueError("source 3: absent zero/dash principal")
                    other_end = rec["periods"][1 - idx]["period_end"]
                    other_val = rec["periods"][1 - idx]["debt_principal_components"][j]
                    other = fact_match(
                        tree, contexts, companyfacts, rec["accession"],
                        tag="DebtInstrumentFaceAmount", expected=other_val,
                        end=other_end, allow_dimensions=True,
                    )
                    if not other["ix_id"]:
                        raise ValueError("source 3: opposite-year note amount absent")
                else:
                    found = fact_match(
                        tree, contexts, companyfacts, rec["accession"],
                        tag="DebtInstrumentFaceAmount", expected=expected,
                        end=p["period_end"], allow_dimensions=True,
                    )
                    if not any(n.get("id") == found["ix_id"] for n in row["node"].xpath('.//*[name()="ix:nonfraction"]')):
                        raise ValueError("source 3: matched note amount belongs to wrong instrument row")
            if sum(p["debt_principal_components"]) != p["debt_principal_total"]:
                raise ValueError("source 3: debt principal arithmetic mismatch")
            periods[idx]["debt_note_row_sha256"] = [r["row_sha256"] for r in debt_rows]
            checks.append("four_instrument_faces_sum_to_principal")
        _, costs = row_for(table, "Less: unamortized issuance costs")
        _, carrying = row_for(table, "Total senior notes")
        cost_vals = nums(costs)
        carrying_vals = nums(carrying)
        if len(cost_vals) < 2 or len(carrying_vals) < 2:
            raise ValueError("source 3: debt costs/carrying rows absent")
        for idx, p in enumerate(rec["periods"]):
            if abs(p["debt_principal_total"] - cost_vals[idx] - carrying_vals[idx]) > 0.00001:
                raise ValueError("source 3: principal-to-carrying reconciliation mismatch")
            periods[idx]["carrying_reconciliation"] = {
                "unamortized_cost": cost_vals[idx],
                "carrying_value": carrying_vals[idx],
                "cost_row_sha256": sha(costs.encode()),
                "carrying_row_sha256": sha(carrying.encode()),
            }
            checks.append("principal_minus_unamortized_cost_equals_carrying_value")
    return periods, checks


def write_private(path: Path, obj: dict) -> bytes:
    data = (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=Path, required=True)
    ap.add_argument("--raw-dir", type=Path, required=True)
    ap.add_argument("--salt", type=Path, required=True)
    ap.add_argument("--private-out", type=Path, required=True)
    ap.add_argument("--public-out", type=Path, required=True)
    args = ap.parse_args()
    pilot_bytes = args.pilot.read_bytes()
    pilot = json.loads(pilot_bytes)
    manifest_bytes = (args.raw_dir / "capture-manifest.private.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if len(pilot["records"]) != 4 or len(manifest["sources"]) != 4:
        raise ValueError("expected exactly four source bundles")
    salt = args.salt.read_bytes()
    if not salt:
        raise ValueError("private commitment salt absent")
    commitments = []
    reviewed = []
    for i, rec in enumerate(pilot["records"]):
        raw = {
            kind: (args.raw_dir / f"source-{i:02d}-{suffix}").read_bytes()
            for kind, suffix in (("index", "index.html"), ("10k", "10k.html"), ("companyfacts", "companyfacts.json"))
        }
        source_manifest = manifest["sources"][i]
        if source_manifest["source_index"] != i or source_manifest["accession"] != rec["accession"]:
            raise ValueError(f"source {i}: capture manifest identity mismatch")
        for kind, content in raw.items():
            if source_manifest["response"][kind]["sha256"] != sha(content):
                raise ValueError(f"source {i}: raw {kind} SHA mismatch")
        tree = html.fromstring(raw["10k"])
        contexts = context_map(tree)
        companyfacts = json.loads(raw["companyfacts"])
        identity = check_identity(i, rec, raw, tree, companyfacts)
        if rec["template_family"].endswith("cash_reconciliation_distinct_v1"):
            periods, equations = cash_review(i, rec, tree, contexts, companyfacts)
        elif rec["template_family"].endswith("interest_coverage_distinct_v1"):
            periods, equations = interest_review(i, rec, tree, contexts, companyfacts)
        else:
            raise ValueError(f"source {i}: unreviewed template family")
        review = {
            "schema": "envloop.sec_transfer_semantic_review.v1",
            "source_index": i,
            "status": "accepted_for_train_source_transfer_only",
            "not_benchmark_task_admission": True,
            "raw_sha256": {kind: sha(content) for kind, content in raw.items()},
            "pilot_sha256": sha(pilot_bytes),
            "manifest_sha256": sha(manifest_bytes),
            "identity": {
                "issuer_name": rec["issuer_name"],
                "issuer_cik": rec["issuer_cik"],
                "accession": rec["accession"],
                "filing_date": rec["filing_date"],
                "report_period": rec["report_period"],
                "checks": identity,
            },
            "annual_periods": periods,
            "equation_checks": equations,
            "limitations": [
                "Source-only semantic review; no spreadsheet, GUI, model, or task admission.",
                "CompanyFacts omits dimension-specific debt-note components where noted.",
                "A zero restricted-cash balance may be derived from an exact total-minus-cash identity.",
            ],
        }
        encoded = write_private(args.private_out / f"source-{i:02d}-review.private.json", review)
        commitments.append(sha(salt + encoded))
        reviewed.append({"source_index": i, "period_count": len(periods), "field_count": sum(len(p["fields"]) for p in periods)})
    aggregate = {
        "schema": "envloop.sec_transfer_semantic_aggregate.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "four saved official SEC 10-K/index/CompanyFacts bundles; training-source transfer only",
        "source_count_reviewed": 4,
        "source_count_accepted": 4,
        "source_count_rejected": 0,
        "source_count_pending": 0,
        "annual_period_count": sum(x["period_count"] for x in reviewed),
        "field_count_reviewed": sum(x["field_count"] for x in reviewed),
        "review_commitments_sha256": commitments,
        "checks": [
            "filing identity, accession, form and original raw-byte SHA",
            "two annual contexts and USD-million scale/sign",
            "same-accession CompanyFacts where non-dimensional facts exist",
            "cash-flow, restricted-cash, interest and debt-principal/carrying identities",
        ],
        "caveats": [
            "No issuer, accession, document name, account identifier, or private graph is disclosed.",
            "This is source availability and semantic review, not task admission or a model result.",
            "One zero restricted-cash field is derived from exact total-minus-cash figures.",
            "Dimension-specific debt-note amounts are supported by original filing rows, not CompanyFacts.",
        ],
        "official_task_admission_count": 0,
    }
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "accepted": aggregate["source_count_accepted"],
        "reviewed_fields": aggregate["field_count_reviewed"],
        "official_task_admissions": 0,
        "public_out": str(args.public_out),
    }))


if __name__ == "__main__":
    main()
