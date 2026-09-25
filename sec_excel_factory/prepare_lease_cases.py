"""Prepare four public development operating-lease maturity audits."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("KO", "GOOGL", "WMT", "ORCL")
TAGS = {
    "current_liability": ("OperatingLeaseLiabilityCurrent", "USD"),
    "noncurrent_liability": ("OperatingLeaseLiabilityNoncurrent", "USD"),
    "rou_asset": ("OperatingLeaseRightOfUseAsset", "USD"),
    "lease_cost": ("OperatingLeaseCost", "USD"),
    "lease_payments": ("OperatingLeasePayments", "USD"),
    "discount_rate": ("OperatingLeaseWeightedAverageDiscountRatePercent", "pure"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities", "USD"),
    "due_next12": ("LesseeOperatingLeaseLiabilityPaymentsDueNextTwelveMonths", "USD"),
    "due_year2": ("LesseeOperatingLeaseLiabilityPaymentsDueYearTwo", "USD"),
    "due_year3": ("LesseeOperatingLeaseLiabilityPaymentsDueYearThree", "USD"),
    "due_year4": ("LesseeOperatingLeaseLiabilityPaymentsDueYearFour", "USD"),
    "due_year5": ("LesseeOperatingLeaseLiabilityPaymentsDueYearFive", "USD"),
    "due_after5": ("LesseeOperatingLeaseLiabilityPaymentsDueAfterYearFive", "USD"),
    "due_total": ("LesseeOperatingLeaseLiabilityPaymentsDue", "USD"),
}
FLOWS = {"lease_cost", "lease_payments", "operating_cash_flow"}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/lease" / f"{ticker.lower()}-end2024-lease.json"
    row = next(r for r in report["sources"] if r["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != row["excerpt_sha256"]:
        raise ValueError(f"lease_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    canonical = {}
    starts = set()
    for key, (tag, unit) in TAGS.items():
        records = [r for r in source["records"] if r["concept"] == tag and r["unit"] == unit
                   and r["end"] == end and bool(r["start"]) == (key in FLOWS)]
        if len(records) != 1:
            raise ValueError(f"lease_fact_missing_or_ambiguous:{ticker}:{key}:{len(records)}")
        canonical[key] = records[0]
        if key in FLOWS:
            starts.add(records[0]["start"])
    if len(starts) != 1:
        raise ValueError(f"lease_flow_starts_disagree:{ticker}")
    start = next(iter(starts))
    if not 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 381:
        raise ValueError("not_annual_lease_flow")
    return {"schema": "sec-lease-maturity-case-v1", "case_id": f"lease-{ticker.lower()}-end2024",
            "status": "public_development_only", "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/lease/{ticker.lower()}-end2024-lease.json",
            "source_excerpt_sha256": row["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "annual_start": start, "annual_end": end,
            "records": source["records"], "canonical": canonical,
            "scenario": {"next12_payment_reduction": round(0.08 + 0.03 * TICKERS.index(ticker), 3),
                         "next12_escalation": round(0.02 + 0.005 * TICKERS.index(ticker), 3)}}


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
        "schema": "sec-lease-public-development-inventory-v1",
        "status": "four public development cases, zero hidden or Excel-web admissions",
        "structural_workflow": "six-bucket operating-lease maturity, liability/ROU reconciliation, and synthetic occupancy stress",
        "issuer_families": 4, "original_10k_accessions": 4,
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": list(TICKERS)}))


if __name__ == "__main__":
    main()
