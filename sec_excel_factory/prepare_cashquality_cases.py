"""Prepare five public SEC cash-flow quality development cases."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("META", "CRM", "COST", "KO", "NFLX")
TAGS = {"net_income": "NetIncomeLoss",
        "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
        "depreciation_amortization": "DepreciationDepletionAndAmortization",
        "share_based_compensation": "ShareBasedCompensation",
        "capital_expenditures": "PaymentsToAcquirePropertyPlantAndEquipment",
        "repurchases": "PaymentsForRepurchaseOfCommonStock"}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def one(rows: list[dict], label: str) -> dict:
    if len(rows) != 1:
        raise ValueError(f"source_fact_not_unique:{label}:{len(rows)}")
    return rows[0]


def make_case(ticker: str, report: dict) -> dict:
    path = HERE / "sources/cashquality" / f"{ticker.lower()}-end2024-cashquality.json"
    summary = next(r for r in report["sources"] if r["ticker"] == ticker)
    raw = path.read_bytes()
    if digest(raw) != summary["excerpt_sha256"]:
        raise ValueError(f"cashquality_excerpt_hash_changed:{ticker}")
    source = json.loads(raw)
    end = source["filing_period_end"]
    previous = sorted({r["end"] for r in source["records"]
                       if r["concept"] == TAGS["net_income"] and r["end"] < end})
    if not previous:
        raise ValueError(f"prior_period_missing:{ticker}")
    prior_end = previous[-1]
    canonical = {}
    annual_start = None
    for year, period_end in (("prior", prior_end), ("current", end)):
        starts = set()
        for key, concept in TAGS.items():
            r = one([r for r in source["records"] if r["concept"] == concept
                     and r["end"] == period_end and r["start"]],
                    f"{ticker}:{year}:{key}")
            canonical[f"{year}:{key}"] = r
            starts.add(r["start"])
            if not 330 <= (date.fromisoformat(period_end) - date.fromisoformat(r["start"])).days + 1 <= 381:
                raise ValueError(f"not_annual_flow:{ticker}:{year}:{key}")
        if len(starts) != 1:
            raise ValueError(f"source_flow_starts_disagree:{ticker}:{year}")
        if year == "current":
            annual_start = next(iter(starts))
    current_ocf_m = canonical["current:operating_cash_flow"]["value"] / 1_000_000
    i = TICKERS.index(ticker)
    return {"schema": "sec-cashquality-case-v1", "case_id": f"cashquality-{ticker.lower()}-end2024",
            "status": "public_development_only", "ticker": ticker, "cik": source["cik"],
            "source_excerpt_path": f"sec_excel_factory/sources/cashquality/{ticker.lower()}-end2024-cashquality.json",
            "source_excerpt_sha256": summary["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "filing_fiscal_year": source["filing_fiscal_year"],
            "annual_start": annual_start, "annual_end": end, "prior_end": prior_end,
            "records": source["records"], "canonical": canonical,
            "scenario": {"capex_increase_fraction": round(0.12 + 0.035 * i, 3),
                         "working_capital_cash_drag_m": round(current_ocf_m * (0.04 + 0.007 * i), 1)}}


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
        "schema": "sec-cashquality-public-development-inventory-v1",
        "status": "five public development cases, zero hidden or Excel-web admissions",
        "structural_workflow": "net income to operating-cash-flow noncash residual, reinvestment, and synthetic cash drag",
        "issuer_families": 5, "original_10k_accessions": 5,
        "excerpt_sha256_by_ticker": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
        "official_final_credit": 0}, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": list(TICKERS)}))


if __name__ == "__main__":
    main()
