"""Freeze original SEC cash-flow quality disclosures for five issuers."""

from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("META", "CRM", "COST", "KO", "NFLX")
TAGS = ("NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities",
        "DepreciationDepletionAndAmortization", "ShareBasedCompensation",
        "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForRepurchaseOfCommonStock")


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def freeze(raw_dir: Path, source_report_path: Path, out_dir: Path) -> dict:
    report = json.loads(source_report_path.read_text())
    prior = {r["ticker"]: r for r in
             json.loads((HERE / "candidate_audit_fetched_2026-09-24.json").read_text())["results"]}
    upstream = {r["ticker"]: r for r in report["sources"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for ticker in TICKERS:
        src = upstream[ticker]
        cik, acc = src["cik"], src["filing_accession"]
        raw = gzip.decompress((raw_dir / f"CIK{cik:010d}-companyfacts.json.gz").read_bytes())
        if digest(raw) != prior[ticker]["sha256_raw_json"] or digest(raw) != src["raw_sec_json_sha256"]:
            raise ValueError(f"prior_direct_sec_hash_changed:{ticker}")
        data = json.loads(raw)
        if data.get("cik") != cik:
            raise ValueError(f"cik_changed:{ticker}")
        records = []
        for concept in TAGS:
            for item in data["facts"]["us-gaap"].get(concept, {}).get("units", {}).get("USD", []):
                if (item.get("accn") != acc or item.get("form") != "10-K"
                        or item.get("filed") != src["filing_filed"]):
                    continue
                records.append({"id": digest(json.dumps((concept, item), sort_keys=True,
                                                         separators=(",", ":")).encode())[:20],
                                "concept": concept, "unit": "USD", "start": item.get("start", ""),
                                "end": item["end"], "value": item["val"], "accession": item["accn"],
                                "filed": item["filed"], "form": item["form"], "fy": item.get("fy"),
                                "fp": item.get("fp"), "frame": item.get("frame", "")})
        records = sorted({r["id"]: r for r in records}.values(),
                         key=lambda r: (r["concept"], r["end"], r["start"], r["id"]))
        if len({r["concept"] for r in records}) != len(TAGS):
            raise ValueError(f"cashquality_tag_missing:{ticker}")
        excerpt = {"schema": "sec-cashquality-source-v1", "status": "public_development_source_only",
                   "ticker": ticker, "cik": cik, "entity_name": data["entityName"],
                   "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                   "source_raw_json_sha256": digest(raw),
                   "filing_index_url": src["filing_index_url"],
                   "filing_accession": acc, "filing_filed": src["filing_filed"],
                   "filing_period_end": src["filing_period_end"],
                   "filing_fiscal_year": src["filing_fiscal_year"], "records": records}
        target = out_dir / f"{ticker.lower()}-end2024-cashquality.json"
        target.write_text(json.dumps(excerpt, indent=2) + "\n")
        summary.append({"ticker": ticker, "cik": cik, "accession": acc,
                        "records": len(records), "raw_json_sha256": digest(raw),
                        "excerpt_sha256": digest(target.read_bytes())})
    return {"schema": "sec-cashquality-source-expansion-v1", "date": "2026-09-25",
            "status": "five public original-filing source excerpts; zero hidden or GUI admission",
            "issuers": 5, "original_accessions": 5,
            "total_fact_rows": sum(r["records"] for r in summary),
            "source_units": ["USD"], "sources": summary}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--source-report", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = freeze(args.raw_dir, args.source_report, args.out_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"issuers": report["issuers"], "fact_rows": report["total_fact_rows"]}))


if __name__ == "__main__":
    main()
