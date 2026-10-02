"""Publish original 10-K excerpts with calendar-2024 period ends.

The compact public excerpts are development sources, not hidden final data.
Every input JSON must match its independently recorded direct-SEC SHA-256 from
the prior source audit before any record is accepted.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import gzip
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONCEPTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
    "OperatingIncomeLoss", "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment", "CostOfGoodsAndServicesSold",
    "CostOfRevenue", "Assets", "Liabilities", "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue", "AssetsCurrent", "LiabilitiesCurrent",
    "InventoryNet", "AccountsPayableCurrent", "ContractWithCustomerLiability",
    "ContractWithCustomerLiabilityCurrent", "ContractWithCustomerLiabilityNoncurrent",
    "ContractWithCustomerLiabilityRevenueRecognized",
    "RevenueRemainingPerformanceObligation", "DeferredRevenueCurrent",
    "DeferredRevenueNoncurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent",
}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def source_map() -> list[dict]:
    candidates = json.loads((HERE / "candidate_issuers.json").read_text())["candidates"]
    direct = {row["ticker"]: row for row in
              json.loads((HERE / "candidate_audit_fetched_2026-09-24.json").read_text())["results"]}
    return [dict(candidate, prior=direct[candidate["ticker"]]) for candidate in candidates
            if candidate["ticker"] not in {"AAPL", "MSFT"}]


def annual_anchor(sec: dict) -> tuple[str, str, str, int]:
    us = sec["facts"]["us-gaap"]
    rows = us.get("Assets", {}).get("units", {}).get("USD", [])
    anchors = {(r["accn"], r["filed"], r["end"], r["fy"]) for r in rows
               if r.get("form") == "10-K" and r.get("fp") == "FY"
               and r.get("end", "").startswith("2024-") and not r.get("start")
               and 0 <= (date.fromisoformat(r["filed"]) - date.fromisoformat(r["end"])).days <= 120}
    if not anchors:
        raise ValueError("missing_original_annual_anchor_with_2024_period_end")
    first = sorted(anchors, key=lambda row: (row[1], row[0], row[2]))[0]
    if len({end for acc, _, end, _ in anchors if acc == first[0]}) != 1:
        raise ValueError("ambiguous_annual_end_in_original_filing")
    return first


def filing_excerpt(sec: dict, ticker: str, source_sha: str) -> dict:
    accession, filed, end, fiscal_year = annual_anchor(sec)
    records = []
    for concept in sorted(CONCEPTS):
        item = sec["facts"]["us-gaap"].get(concept)
        if not item:
            continue
        for row in item.get("units", {}).get("USD", []):
            if row.get("accn") != accession or row.get("filed") != filed or row.get("form") != "10-K":
                continue
            record = {"id": digest(json.dumps((concept, row), sort_keys=True, separators=(",", ":")).encode())[:20],
                      "concept": concept, "unit": "USD", "start": row.get("start", ""),
                      "end": row["end"], "value": row["val"], "accession": row["accn"],
                      "filed": row["filed"], "form": row["form"], "fy": row.get("fy"),
                      "fp": row.get("fp"), "frame": row.get("frame", "")}
            records.append(record)
    records = sorted({row["id"]: row for row in records}.values(),
                     key=lambda row: (row["concept"], row["end"], row["start"], row["id"]))
    if len(records) < 20:
        raise ValueError(f"too_few_relevant_records:{ticker}")
    source_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{sec['cik']:010d}.json"
    index_url = (f"https://www.sec.gov/Archives/edgar/data/{sec['cik']}/"
                 f"{accession.replace('-', '')}/{accession}-index.html")
    return {"schema": "sec-public-filing-excerpt-v1", "status": "public_development_source_only",
            "ticker": ticker, "entity_name": sec["entityName"], "cik": sec["cik"],
            "source_url": source_url, "source_raw_json_sha256": source_sha,
            "source_transport": "read-only text proxy; payload bytes checked against prior direct SEC SHA-256",
            "filing_index_url": index_url, "filing_index_url_status": "constructed_from_accession; only GOOGL and ORCL index pages manually opened",
            "filing_accession": accession, "filing_filed": filed, "filing_form": "10-K",
            "filing_fiscal_year": fiscal_year, "filing_period_end": end,
            "records": records}


def freeze(raw_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    all_accessions = set()
    for candidate in source_map():
        ticker, cik = candidate["ticker"], candidate["cik"]
        path = raw_dir / f"CIK{cik:010d}-companyfacts.json.gz"
        raw = gzip.decompress(path.read_bytes())
        expected = candidate["prior"].get("sha256_raw_json")
        if not expected or digest(raw) != expected:
            raise ValueError(f"prior_direct_sec_sha256_mismatch:{ticker}")
        sec = json.loads(raw)
        if sec.get("cik") != cik:
            raise ValueError(f"cik_mismatch:{ticker}")
        excerpt = filing_excerpt(sec, ticker, digest(raw))
        if excerpt["filing_accession"] in all_accessions:
            raise ValueError("duplicate_annual_accession")
        all_accessions.add(excerpt["filing_accession"])
        target = out_dir / f"{ticker.lower()}-end2024-10k.json"
        target.write_text(json.dumps(excerpt, indent=2) + "\n")
        results.append({"ticker": ticker, "cik": cik,
                        "prior_seven_tag_source_status": candidate["prior"]["status"],
                        "filing_accession": excerpt["filing_accession"],
                        "filing_filed": excerpt["filing_filed"],
                        "filing_period_end": excerpt["filing_period_end"],
                        "filing_fiscal_year": excerpt["filing_fiscal_year"],
                        "filing_index_url": excerpt["filing_index_url"],
                        "raw_sec_json_sha256": digest(raw),
                        "excerpt_sha256": digest(target.read_bytes()),
                        "fact_rows": len(excerpt["records"]),
                        "concepts": len({r["concept"] for r in excerpt["records"]})})
    report = {"schema": "sec-public-filing-expansion-v1", "date": "2026-09-25",
              "status": "verified public source excerpts; no hidden or Excel-web task admission",
              "new_issuer_families": len(results),
              "distinct_original_10k_accessions_with_2024_period_end": len(all_accessions),
              "total_pinned_fact_rows": sum(r["fact_rows"] for r in results),
              "prior_direct_sec_sha256_checks_passed": len(results),
              "prior_seven_tag_source_statuses": dict(Counter(r["prior_seven_tag_source_status"] for r in results)),
              "official_filing_pages_manually_opened": ["GOOGL", "ORCL", "HD"],
              "sources": results,
              "no_official_final_credit": True}
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = freeze(args.raw_dir, args.out_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in
                      ("new_issuer_families", "distinct_original_10k_accessions_with_2024_period_end",
                       "total_pinned_fact_rows", "prior_direct_sec_sha256_checks_passed")}, sort_keys=True))


if __name__ == "__main__":
    main()
