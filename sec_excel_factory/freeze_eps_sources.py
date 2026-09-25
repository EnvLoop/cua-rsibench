"""Freeze mixed-unit FY EPS and shareholder-return disclosures for four issuers."""

from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TICKERS = ("GOOGL", "NVDA", "META", "KO")
TAGS = {
    "NetIncomeLoss": "USD",
    "WeightedAverageNumberOfSharesOutstandingBasic": "shares",
    "WeightedAverageNumberOfDilutedSharesOutstanding": "shares",
    "EarningsPerShareBasic": "USD/shares",
    "EarningsPerShareDiluted": "USD/shares",
    "PaymentsForRepurchaseOfCommonStock": "USD",
    "PaymentsOfDividends": "USD",
}


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def freeze(raw_dir: Path, source_report_path: Path, out_dir: Path) -> dict:
    report = json.loads(source_report_path.read_text())
    direct = {r["ticker"]: r for r in
              json.loads((HERE / "candidate_audit_fetched_2026-09-24.json").read_text())["results"]}
    upstream = {r["ticker"]: r for r in report["sources"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ticker in TICKERS:
        source = upstream[ticker]
        cik, accession = source["cik"], source["filing_accession"]
        raw = gzip.decompress((raw_dir / f"CIK{cik:010d}-companyfacts.json.gz").read_bytes())
        if digest(raw) != direct[ticker]["sha256_raw_json"] or digest(raw) != source["raw_sec_json_sha256"]:
            raise ValueError(f"prior_direct_sec_source_hash_changed:{ticker}")
        sec = json.loads(raw)
        if sec.get("cik") != cik:
            raise ValueError(f"cik_changed:{ticker}")
        facts = []
        for tag, unit in TAGS.items():
            for item in sec["facts"]["us-gaap"].get(tag, {}).get("units", {}).get(unit, []):
                if (item.get("accn") != accession or item.get("form") != "10-K"
                        or item.get("filed") != source["filing_filed"]):
                    continue
                record = {"id": digest(json.dumps((tag, unit, item), sort_keys=True,
                                                  separators=(",", ":")).encode())[:20],
                          "concept": tag, "unit": unit, "start": item.get("start", ""),
                          "end": item["end"], "value": item["val"], "accession": item["accn"],
                          "filed": item["filed"], "form": item["form"], "fy": item.get("fy"),
                          "fp": item.get("fp"), "frame": item.get("frame", "")}
                facts.append(record)
        facts = sorted({r["id"]: r for r in facts}.values(),
                       key=lambda r: (r["concept"], r["end"], r["start"], r["id"]))
        if len({r["concept"] for r in facts}) != len(TAGS):
            raise ValueError(f"one_of_seven_concepts_missing:{ticker}")
        excerpt = {"schema": "sec-mixed-unit-eps-source-v1",
                   "status": "public_development_source_only",
                   "ticker": ticker, "cik": cik, "entity_name": sec["entityName"],
                   "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                   "source_raw_json_sha256": digest(raw),
                   "filing_index_url": source["filing_index_url"],
                   "filing_accession": accession, "filing_filed": source["filing_filed"],
                   "filing_period_end": source["filing_period_end"],
                   "filing_fiscal_year": source["filing_fiscal_year"],
                   "records": facts}
        target = out_dir / f"{ticker.lower()}-end2024-eps.json"
        target.write_text(json.dumps(excerpt, indent=2) + "\n")
        rows.append({"ticker": ticker, "cik": cik, "original_accession": accession,
                     "records": len(facts), "units": sorted({r["unit"] for r in facts}),
                     "raw_json_sha256": digest(raw), "excerpt_sha256": digest(target.read_bytes())})
    return {"schema": "sec-eps-source-expansion-v1", "date": "2026-09-25",
            "status": "four public mixed-unit source excerpts; no hidden or GUI admission",
            "issuers": len(rows), "original_accessions": len({r["original_accession"] for r in rows}),
            "total_fact_rows": sum(r["records"] for r in rows),
            "units": sorted({unit for r in rows for unit in r["units"]}),
            "sources": rows}


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
