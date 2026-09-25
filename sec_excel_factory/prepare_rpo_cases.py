"""Prepare four public development RPO/contract-liability Excel cases.

These use authentic SEC accession-bound records in the published source
expansion. Forecast shares and haircuts are explicitly synthetic assumptions.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("GOOGL", "ORCL", "NVDA", "DIS")
REVENUE = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues")
TAGS = {
    "total": "ContractWithCustomerLiability",
    "current": "ContractWithCustomerLiabilityCurrent",
    "noncurrent": "ContractWithCustomerLiabilityNoncurrent",
    "rpo": "RevenueRemainingPerformanceObligation",
    "recognized": "ContractWithCustomerLiabilityRevenueRecognized",
    "assets_current": "AssetsCurrent",
    "liabilities_current": "LiabilitiesCurrent",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def exact(records: list[dict], concept: str, end: str, *, start: str | None = None) -> dict | None:
    rows = [r for r in records if r["concept"] == concept and r["end"] == end
            and (r["start"] == start if start is not None else not r["start"])]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError(f"ambiguous_sec_record:{concept}:{end}:{start}:{len(rows)}")
    return rows[0]


def make_case(ticker: str, source_report: dict) -> dict:
    path = HERE / "sources/expansion" / f"{ticker.lower()}-fy2024-10k.json"
    summary = next(r for r in source_report["sources"] if r["ticker"] == ticker)
    if digest(path.read_bytes()) != summary["excerpt_sha256"]:
        raise ValueError(f"source_excerpt_hash_changed:{ticker}")
    source = json.loads(path.read_text())
    if source["filing_accession"] != summary["filing_accession"]:
        raise ValueError("source_filing_changed")
    records = source["records"]
    current_end = source["filing_period_end"]
    revenues = [r for r in records if r["concept"] in REVENUE and r["end"] == current_end
                and r["start"]]
    preferred = REVENUE[0] if any(r["concept"] == REVENUE[0] for r in revenues) else REVENUE[1]
    rev = [r for r in revenues if r["concept"] == preferred]
    if len(rev) != 1:
        raise ValueError(f"annual_revenue_ambiguity:{ticker}")
    annual_start = rev[0]["start"]
    prior_ends = sorted({r["end"] for r in records if r["concept"] in
                         (TAGS["current"], TAGS["total"], TAGS["noncurrent"])
                         and r["end"] < current_end})
    if not prior_ends:
        raise ValueError(f"opening_contract_liability_missing:{ticker}")
    prior_end = prior_ends[-1]
    canonical = {"revenue": rev[0]}
    # A prior revenue flow has its own fiscal start, unlike a stock fact.
    prior_rev = [r for r in records if r["concept"] == preferred and r["end"] == prior_end and r["start"]]
    if len(prior_rev) != 1:
        raise ValueError(f"prior_revenue_ambiguity:{ticker}")
    canonical["revenue_prior"] = prior_rev[0]
    for key, tag in TAGS.items():
        if key == "recognized":
            canonical[key] = exact(records, tag, current_end, start=annual_start)
        else:
            canonical[key] = exact(records, tag, current_end)
        if key in {"total", "current", "noncurrent"}:
            canonical[f"prior_{key}"] = exact(records, tag, prior_end)
    required = ("rpo", "recognized", "current", "assets_current", "liabilities_current", "cash")
    if any(canonical.get(key) is None for key in required):
        raise ValueError(f"required_rpo_facts_missing:{ticker}")
    for prefix in ("", "prior_"):
        if canonical[prefix + "total"] is None and canonical[prefix + "noncurrent"] is None:
            raise ValueError(f"total_or_noncurrent_missing:{ticker}:{prefix}")
        if canonical[prefix + "current"] is None:
            raise ValueError(f"current_liability_missing:{ticker}:{prefix}")
    return {"schema": "sec-rpo-audit-case-v1", "case_id": f"rpo-{ticker.lower()}-fy2024",
            "status": "public_development_case_only", "ticker": ticker,
            "source_excerpt_path": f"sec_excel_factory/sources/expansion/{ticker.lower()}-fy2024-10k.json",
            "source_excerpt_sha256": summary["excerpt_sha256"],
            "source_raw_json_sha256": source["source_raw_json_sha256"],
            "cik": source["cik"], "filing_accession": source["filing_accession"],
            "filing_index_url": source["filing_index_url"],
            "annual_start": annual_start, "annual_end": current_end,
            "prior_end": prior_end, "canonical": canonical,
            "records": records,
            "scenario": {"rpo_haircut": 0.12 if ticker != "NVDA" else 0.18,
                         "next12_recognition_share": 0.45 if ticker != "DIS" else 0.38}}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-report", type=Path, required=True)
    p.add_argument("--private-out", type=Path, required=True)
    p.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    source_report = json.loads(args.source_report.read_text())
    cases = [make_case(ticker, source_report) for ticker in TICKERS]
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(cases, separators=(",", ":")) + "\n")
    public = {"schema": "sec-rpo-public-development-inventory-v1",
              "status": "four source-distinct public development cases; zero hidden or GUI admission",
              "distinct_issuer_families": len({c["cik"] for c in cases}),
              "distinct_annual_accessions": len({c["filing_accession"] for c in cases}),
              "structural_workflow": "contract liability classification, recognition, RPO scenario, and liquidity coverage",
              "source_excerpt_sha256": {c["ticker"]: c["source_excerpt_sha256"] for c in cases},
              "official_final_credit": 0}
    args.public_out.write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "issuers": [c["ticker"] for c in cases]}))


if __name__ == "__main__":
    main()
