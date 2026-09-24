"""Freeze a compact, auditable task slice from two downloaded SEC companyfacts files."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
METRICS = {
    "Revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Operating income": "OperatingIncomeLoss",
    "Operating cash flow": "NetCashProvidedByUsedInOperatingActivities",
    "Capital expenditures": "PaymentsToAcquirePropertyPlantAndEquipment",
    "Assets": "Assets",
    "Liabilities": "Liabilities",
    "Equity": "StockholdersEquity",
}
EXTRA_METRICS = {
    "Diluted EPS": ("EarningsPerShareDiluted", "USD/shares"),
    "Diluted shares": ("WeightedAverageNumberOfDilutedSharesOutstanding", "shares"),
}
ISSUERS = {
    "Apple": {
        "cik": 320193,
        "path": "apple-companyfacts.json.gz",
        "sha256": "73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43",
        "filing": "0000320193-24-000123",
        "periods": {"2023": "2023-09-30", "2024": "2024-09-28"},
    },
    "Microsoft": {
        "cik": 789019,
        "path": "microsoft-companyfacts.json.gz",
        "sha256": "f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f",
        "filing": "0000950170-24-087843",
        "periods": {"2023": "2023-06-30", "2024": "2024-06-30"},
    },
}


def read_source(config: dict) -> dict:
    raw = gzip.decompress((HERE / "sources" / "raw" / config["path"]).read_bytes())
    actual = hashlib.sha256(raw).hexdigest()
    if actual != config["sha256"]:
        raise ValueError(f"SEC source SHA-256 changed: {config['path']} {actual}")
    data = json.loads(raw)
    if data["cik"] != config["cik"]:
        raise ValueError(f"CIK mismatch in {config['path']}")
    return data


def is_annual(fact: dict, metric: str) -> bool:
    if metric in ("Assets", "Liabilities", "Equity"):
        return "start" not in fact
    if "start" not in fact:
        return False
    from datetime import date

    days = (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
    return 330 <= days <= 380


def build_excerpt() -> dict:
    rows: list[dict] = []
    canonical: dict[str, str] = {}
    source_meta: list[dict] = []
    for issuer, config in ISSUERS.items():
        data = read_source(config)
        source_meta.append(
            {
                "issuer": issuer,
                "entity_name": data["entityName"],
                "cik": config["cik"],
                "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{config['cik']:010d}.json",
                "sha256_raw_json": config["sha256"],
                "frozen_filing": config["filing"],
            }
        )
        for metric, concept in METRICS.items():
            facts = data["facts"]["us-gaap"][concept]["units"]["USD"]
            for year, period_end in config["periods"].items():
                chosen = [
                    x for x in facts
                    if x["accn"] == config["filing"]
                    and x["end"] == period_end
                    and x["form"] == "10-K"
                    and is_annual(x, metric)
                ]
                if len(chosen) != 1:
                    raise ValueError(f"Expected one canonical fact: {issuer} {metric} {year}: {chosen}")
                true_fact = chosen[0]
                # All distractors are authentic records from the same SEC response.
                # The same end can have quarterly/YTD and later comparative facts.
                later_or_other = [
                    x for x in facts
                    if x is not true_fact and x.get("end") == period_end
                    and x.get("form") in ("10-K", "10-K/A", "10-Q", "10-Q/A")
                    and x.get("filed", "") <= "2025-12-31"
                ]
                later_or_other.sort(key=lambda x: (x.get("filed", ""), x.get("accn", "")), reverse=True)
                nearby = [
                    x for x in facts
                    if x.get("end", "").startswith(year)
                    and x.get("end") != period_end
                    and x.get("form") == "10-Q"
                    and x.get("filed", "") <= "2025-12-31"
                ]
                nearby.sort(key=lambda x: (x.get("end", ""), x.get("filed", "")), reverse=True)
                pool = [true_fact, *later_or_other[:3], *nearby[:1]]
                seen: set[str] = set()
                for x in pool:
                    unique = json.dumps({k: x.get(k) for k in ("start", "end", "val", "accn", "form", "filed", "frame")}, sort_keys=True)
                    if unique in seen:
                        continue
                    seen.add(unique)
                    record_id = hashlib.sha256(f"{config['cik']}:{concept}:{unique}".encode()).hexdigest()[:16]
                    row = {
                        "id": record_id,
                        "issuer": issuer,
                        "cik": config["cik"],
                        "metric": metric,
                        "concept": concept,
                        "start": x.get("start", ""),
                        "end": x["end"],
                        "filed": x["filed"],
                        "form": x["form"],
                        "accession": x["accn"],
                        "fy": x.get("fy", ""),
                        "fp": x.get("fp", ""),
                        "frame": x.get("frame", ""),
                        "unit": "USD",
                        "reported_value": x["val"],
                    }
                    rows.append(row)
                    if x is true_fact:
                        canonical[f"{issuer}:{year}:{metric}"] = record_id
        # Real unit conflicts sit beside money amounts in finance exports.
        # These EPS/share facts are never eligible for the USD model, but an
        # operator must notice their unit rather than merely matching a year.
        for metric, (concept, unit) in EXTRA_METRICS.items():
            facts = data["facts"]["us-gaap"][concept]["units"][unit]
            for year, period_end in config["periods"].items():
                eligible = [
                    x for x in facts
                    if x["accn"] == config["filing"] and x["end"] == period_end
                    and x["form"] == "10-K" and is_annual(x, metric)
                ]
                nearby = [
                    x for x in facts
                    if x.get("end", "").startswith(year) and x.get("form") == "10-Q"
                    and x.get("end") != period_end
                ]
                nearby.sort(key=lambda x: (x.get("end", ""), x.get("filed", "")), reverse=True)
                for x in [*eligible[:1], *nearby[:1]]:
                    unique = json.dumps({k: x.get(k) for k in ("start", "end", "val", "accn", "form", "filed", "frame")}, sort_keys=True)
                    rows.append({
                        "id": hashlib.sha256(f"{config['cik']}:{concept}:{unique}".encode()).hexdigest()[:16],
                        "issuer": issuer,
                        "cik": config["cik"],
                        "metric": metric,
                        "concept": concept,
                        "start": x.get("start", ""),
                        "end": x["end"],
                        "filed": x["filed"],
                        "form": x["form"],
                        "accession": x["accn"],
                        "fy": x.get("fy", ""),
                        "fp": x.get("fp", ""),
                        "frame": x.get("frame", ""),
                        "unit": unit,
                        "reported_value": x["val"],
                    })
    rows.sort(key=lambda r: (r["issuer"], r["metric"], r["end"], r["filed"], r["id"]))
    if len(canonical) != 28:
        raise ValueError(f"Expected 28 canonical facts, got {len(canonical)}")
    excerpt = {
        "schema": "sec-excel-fixture-v1",
        "snapshot_date": "2026-09-24",
        "selection_cutoff": "2024-12-31; later filings remain as distractors",
        "sources": source_meta,
        "selection_policy": "For each issuer, metric and FY2023/FY2024, use the USD annual-duration (or instant balance-sheet) fact with the exact issuer-specific fiscal year-end from that issuer's FY2024 Form 10-K accession. Later filings, quarterly/YTD facts, and alternative end dates are distractors. Do not mix June and September fiscal year-ends.",
        "rows": rows,
        "canonical_record_ids": canonical,
    }
    return excerpt


def main() -> None:
    excerpt = build_excerpt()
    path = HERE / "sources" / "excerpt.json"
    path.write_text(json.dumps(excerpt, indent=2, ensure_ascii=False) + "\n")
    print(f"{path}: {len(excerpt['rows'])} authentic SEC records; 28 canonical facts")


if __name__ == "__main__":
    main()
