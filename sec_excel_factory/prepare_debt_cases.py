"""Prepare five public development cash/debt maturity stress cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("PFE", "COST", "WMT", "GOOGL", "CRM")
TAGS = {
    "current_long_term_debt": "LongTermDebtCurrent",
    "noncurrent_long_term_debt": "LongTermDebtNoncurrent",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capital_expenditures": "PaymentsToAcquirePropertyPlantAndEquipment",
    "current_assets": "AssetsCurrent",
    "current_liabilities": "LiabilitiesCurrent",
}
FLOW = {"operating_cash_flow", "capital_expenditures"}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/expansion" / f"{ticker.lower()}-end2024-10k.json"
    summary = next(row for row in report["sources"] if row["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != summary["excerpt_sha256"]:
        raise ValueError(f"source_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    canonical = {}
    starts = set()
    for key, tag in TAGS.items():
        matches = [r for r in source["records"] if r["concept"] == tag and r["end"] == end
                   and bool(r["start"]) == (key in FLOW)]
        if len(matches) != 1:
            raise ValueError(f"source_fact_missing_or_ambiguous:{ticker}:{key}:{len(matches)}")
        canonical[key] = matches[0]
        if key in FLOW:
            starts.add(matches[0]["start"])
    if len(starts) != 1:
        raise ValueError(f"source_flow_starts_disagree:{ticker}")
    start = next(iter(starts))
    if not 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 381:
        raise ValueError(f"not_annual_cash_flow:{ticker}")
    return {"schema": "sec-debt-capacity-case-v1", "case_id": f"debt-{ticker.lower()}-end2024",
            "status": "public_development_only", "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/expansion/{ticker.lower()}-end2024-10k.json",
            "source_excerpt_sha256": summary["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "annual_start": start, "annual_end": end,
            "records": source["records"], "canonical": canonical,
            "scenario": {"refinance_share": round(0.55 + 0.07 * TICKERS.index(ticker), 3),
                         "incremental_interest_rate": round(0.0275 + 0.004 * TICKERS.index(ticker), 4)}}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-report", type=Path, required=True)
    p.add_argument("--private-out", type=Path, required=True)
    p.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    report = json.loads(args.source_report.read_text())
    cases = [make_case(ticker, report) for ticker in TICKERS]
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(cases, separators=(",", ":")) + "\n")
    args.public_out.write_text(json.dumps({
        "schema": "sec-debt-public-development-inventory-v1",
        "status": "five public development cases, zero hidden or Excel-web admissions",
        "structural_workflow": "current versus noncurrent reported long-term debt, cash capacity, and synthetic refinance stress",
        "issuer_families": len({c["cik"] for c in cases}),
        "original_10k_accessions": len({c["filing_accession"] for c in cases}),
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": [c["ticker"] for c in cases]}))


if __name__ == "__main__":
    main()
