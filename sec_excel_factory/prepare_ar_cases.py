"""Prepare public receivables/allowance development cases from SEC facts."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("PFE", "ORCL", "AMZN")
SHARED = {"net_ar": "AccountsReceivableNetCurrent",
          "allowance": "AllowanceForDoubtfulAccountsReceivableCurrent",
          "ocf": "NetCashProvidedByUsedInOperatingActivities",
          "current_assets": "AssetsCurrent"}
FLOWS = {"ocf", "revenue"}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def one(rows: list[dict], label: str) -> dict:
    if len(rows) != 1:
        raise ValueError(f"source_fact_not_unique:{label}:{len(rows)}")
    return rows[0]


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/ar" / f"{ticker.lower()}-end2024-ar.json"
    summary = next(r for r in report["sources"] if r["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != summary["excerpt_sha256"]:
        raise ValueError(f"ar_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    previous = sorted({r["end"] for r in source["records"]
                       if r["concept"] == SHARED["net_ar"] and r["end"] < end and not r["start"]})
    if not previous:
        raise ValueError(f"prior_receivable_balance_missing:{ticker}")
    prior_end = previous[-1]
    concepts = SHARED | {"revenue": source["revenue_concept"]}
    canonical = {}
    current_starts = set()
    for year, period_end in (("prior", prior_end), ("current", end)):
        starts = set()
        for metric, concept in concepts.items():
            record = one([r for r in source["records"] if r["concept"] == concept
                          and r["end"] == period_end
                          and bool(r["start"]) == (metric in FLOWS)],
                         f"{ticker}:{year}:{metric}")
            canonical[f"{year}:{metric}"] = record
            if metric in FLOWS:
                starts.add(record["start"])
                if not 330 <= (date.fromisoformat(period_end) - date.fromisoformat(record["start"])).days + 1 <= 381:
                    raise ValueError(f"not_annual_flow:{ticker}:{year}:{metric}")
        if len(starts) != 1:
            raise ValueError(f"flow_starts_disagree:{ticker}:{year}")
        if year == "current":
            current_starts = starts
    i = TICKERS.index(ticker)
    prior_days = (date.fromisoformat(prior_end)
                  - date.fromisoformat(canonical["prior:revenue"]["start"])).days + 1
    current_days = (date.fromisoformat(end) - date.fromisoformat(next(iter(current_starts)))).days + 1
    return {"schema": "sec-receivable-allowance-case-v1",
            "case_id": f"ar-{ticker.lower()}-end2024", "status": "public_development_only",
            "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/ar/{ticker.lower()}-end2024-ar.json",
            "source_excerpt_sha256": summary["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "revenue_concept": source["revenue_concept"],
            "annual_start": next(iter(current_starts)), "annual_end": end,
            "prior_end": prior_end, "prior_fiscal_days": prior_days,
            "current_fiscal_days": current_days,
            "records": source["records"], "canonical": canonical,
            "scenario": {"incremental_reserve_rate": round(0.012 + i * 0.006, 3),
                         "modeled_cash_realization_fraction": round(0.35 + i * 0.10, 3)}}


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
        "schema": "sec-ar-public-development-inventory-v1",
        "status": "three public development cases, zero hidden or Excel-web admissions",
        "structural_workflow": "net/gross receivables, doubtful-account allowance, DSO, and synthetic reserve stress",
        "issuer_families": 3, "original_10k_accessions": 3,
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": list(TICKERS)}))


if __name__ == "__main__":
    main()
