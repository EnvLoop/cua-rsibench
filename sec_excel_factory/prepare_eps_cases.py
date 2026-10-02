"""Prepare four public development mixed-unit EPS/capital-return cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("GOOGL", "NVDA", "META", "KO")
TAGS = {
    "net_income": ("NetIncomeLoss", "USD"),
    "basic_shares": ("WeightedAverageNumberOfSharesOutstandingBasic", "shares"),
    "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding", "shares"),
    "eps_basic": ("EarningsPerShareBasic", "USD/shares"),
    "eps_diluted": ("EarningsPerShareDiluted", "USD/shares"),
    "repurchases": ("PaymentsForRepurchaseOfCommonStock", "USD"),
    "dividends": ("PaymentsOfDividends", "USD"),
}
PRICES = {"GOOGL": 150.0, "NVDA": 750.0, "META": 450.0, "KO": 60.0}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def one(rows: list[dict], label: str) -> dict:
    if len(rows) != 1:
        raise ValueError(f"source_fact_not_unique:{label}:{len(rows)}")
    return rows[0]


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/eps" / f"{ticker.lower()}-end2024-eps.json"
    source_row = next(r for r in report["sources"] if r["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != source_row["excerpt_sha256"]:
        raise ValueError(f"eps_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    possible_ends = sorted({r["end"] for r in source["records"]
                            if r["concept"] == "NetIncomeLoss" and r["end"] < end})
    if not possible_ends:
        raise ValueError(f"prior_year_absent:{ticker}")
    prior_end = possible_ends[-1]
    canonical = {}
    starts = set()
    for year_key, year_end in (("prior", prior_end), ("current", end)):
        for key, (concept, unit) in TAGS.items():
            record = one([r for r in source["records"] if r["concept"] == concept
                          and r["unit"] == unit and r["end"] == year_end
                          and r["start"]], f"{ticker}:{year_key}:{key}")
            if not 330 <= (date.fromisoformat(year_end) - date.fromisoformat(record["start"])).days + 1 <= 381:
                raise ValueError(f"not_annual_flow:{ticker}:{year_key}:{key}")
            canonical[f"{year_key}:{key}"] = record
            if year_key == "current":
                starts.add(record["start"])
    if len(starts) != 1:
        raise ValueError(f"current_filing_flow_starts_disagree:{ticker}")
    return {"schema": "sec-eps-capital-return-case-v1",
            "case_id": f"eps-{ticker.lower()}-end2024", "status": "public_development_only",
            "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/eps/{ticker.lower()}-end2024-eps.json",
            "source_excerpt_sha256": source_row["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "annual_start": next(iter(starts)), "annual_end": end,
            "prior_end": prior_end, "canonical": canonical,
            "records": source["records"],
            "scenario": {"synthetic_repurchase_price_usd": PRICES[ticker],
                         "synthetic_buyback_budget_fraction": round(0.24 + 0.05 * TICKERS.index(ticker), 3)}}


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
        "schema": "sec-eps-public-development-inventory-v1",
        "status": "four public mixed-unit cases; zero hidden or Excel-web admissions",
        "structural_workflow": "reported EPS and diluted shares, shareholder cash returns, and synthetic repurchase scenario",
        "issuer_families": 4, "original_10k_accessions": 4,
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": list(TICKERS)}))


if __name__ == "__main__":
    main()
