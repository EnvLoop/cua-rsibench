"""Prepare public goodwill/intangible-asset audit development cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("PFE", "NVDA", "META")
STOCK = {"goodwill": "Goodwill", "intangibles": "IntangibleAssetsNetExcludingGoodwill",
         "assets": "Assets"}
FLOW = {"acquired_goodwill": "GoodwillAcquiredDuringPeriod",
        "amortization": "AmortizationOfIntangibleAssets", "net_income": "NetIncomeLoss"}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def one(rows: list[dict], label: str) -> dict:
    if len(rows) != 1:
        raise ValueError(f"source_fact_not_unique:{label}:{len(rows)}")
    return rows[0]


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/goodwill" / f"{ticker.lower()}-end2024-goodwill.json"
    summary = next(row for row in report["sources"] if row["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != summary["excerpt_sha256"]:
        raise ValueError(f"goodwill_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    previous = sorted({r["end"] for r in source["records"]
                       if r["concept"] == "Goodwill" and r["end"] < end and not r["start"]})
    if not previous:
        raise ValueError(f"prior_balance_missing:{ticker}")
    prior_end = previous[-1]
    canonical = {}
    for year, period_end in (("prior", prior_end), ("current", end)):
        for key, concept in STOCK.items():
            canonical[f"{year}:{key}"] = one([r for r in source["records"]
                                               if r["concept"] == concept and r["end"] == period_end
                                               and not r["start"]], f"{ticker}:{year}:{key}")
    starts = set()
    for key, concept in FLOW.items():
        record = one([r for r in source["records"] if r["concept"] == concept
                      and r["end"] == end and r["start"]], f"{ticker}:{key}")
        canonical[key] = record
        starts.add(record["start"])
    if len(starts) != 1:
        raise ValueError(f"current_annual_starts_disagree:{ticker}")
    start = next(iter(starts))
    if not 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 381:
        raise ValueError("not_annual_filing_duration")
    i = TICKERS.index(ticker)
    return {"schema": "sec-goodwill-audit-case-v1", "case_id": f"goodwill-{ticker.lower()}-end2024",
            "status": "public_development_only", "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/goodwill/{ticker.lower()}-end2024-goodwill.json",
            "source_excerpt_sha256": summary["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "annual_start": start, "annual_end": end, "prior_end": prior_end,
            "records": source["records"], "canonical": canonical,
            "scenario": {"goodwill_write_down_fraction": round(0.07 + i * 0.03, 3),
                         "incremental_amortization_m": float(200 + i * 150)}}


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
        "schema": "sec-goodwill-public-development-inventory-v1",
        "status": "three public development cases, zero hidden or Excel-web admissions",
        "structural_workflow": "goodwill acquisition residual, intangible carrying values, and synthetic impairment/amortization stress",
        "issuer_families": 3, "original_10k_accessions": 3,
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": list(TICKERS)}))


if __name__ == "__main__":
    main()
