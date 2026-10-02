"""Prepare three public original-filing tax provision development cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("GOOGL", "CRM", "META")
TAGS = {
    "pretax": "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "tax_expense": "IncomeTaxExpenseBenefit",
    "current_tax": "CurrentIncomeTaxExpenseBenefit",
    "deferred_tax": "DeferredIncomeTaxExpenseBenefit",
    "cash_taxes": "IncomeTaxesPaidNet",
    "dta": "DeferredTaxAssetsNet",
}
FLOWS = set(TAGS) - {"dta"}
PRETAX_DELTA = {"GOOGL": 5000.0, "CRM": 600.0, "META": 3000.0}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def one(rows: list[dict], label: str) -> dict:
    if len(rows) != 1:
        raise ValueError(f"tax_fact_not_unique:{label}:{len(rows)}")
    return rows[0]


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/tax" / f"{ticker.lower()}-end2024-tax.json"
    summary = next(r for r in report["sources"] if r["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != summary["excerpt_sha256"]:
        raise ValueError(f"source_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    previous = sorted({r["end"] for r in source["records"]
                       if r["concept"] == TAGS["pretax"] and r["end"] < end})
    if not previous:
        raise ValueError(f"prior_period_missing:{ticker}")
    prior_end = previous[-1]
    canonical = {}
    annual_starts = set()
    for year, period_end in (("prior", prior_end), ("current", end)):
        period_starts = set()
        for key, tag in TAGS.items():
            record = one([r for r in source["records"] if r["concept"] == tag
                          and r["end"] == period_end and bool(r["start"]) == (key in FLOWS)],
                         f"{ticker}:{year}:{key}")
            canonical[f"{year}:{key}"] = record
            if key in FLOWS:
                period_starts.add(record["start"])
                if not 330 <= (date.fromisoformat(period_end) - date.fromisoformat(record["start"])).days + 1 <= 381:
                    raise ValueError(f"nonannual_tax_flow:{ticker}:{year}:{key}")
        if len(period_starts) != 1:
            raise ValueError(f"flow_start_mismatch:{ticker}:{year}")
        if year == "current":
            annual_starts = period_starts
    return {"schema": "sec-tax-provision-case-v1", "case_id": f"tax-{ticker.lower()}-end2024",
            "status": "public_development_only", "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/tax/{ticker.lower()}-end2024-tax.json",
            "source_excerpt_sha256": summary["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "annual_start": next(iter(annual_starts)), "annual_end": end,
            "prior_end": prior_end, "records": source["records"], "canonical": canonical,
            "scenario": {"pretax_delta_m": PRETAX_DELTA[ticker],
                         "effective_rate_shift": round(0.012 + 0.004 * TICKERS.index(ticker), 3)}}


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
        "schema": "sec-tax-public-development-inventory-v1",
        "status": "three public development cases, zero hidden or Excel-web admissions",
        "structural_workflow": "current/deferred tax provision, cash taxes, deferred-tax assets, and synthetic tax-rate stress",
        "issuer_families": 3, "original_10k_accessions": 3,
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": list(TICKERS)}))


if __name__ == "__main__":
    main()
