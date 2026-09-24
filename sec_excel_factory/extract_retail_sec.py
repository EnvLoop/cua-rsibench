"""Freeze authentic retail working-capital facts and distractors from SEC snapshots.

The downloaded full companyfacts responses stay in ignored ``work/``. This
extractor pins their raw hashes and writes a small, redistributable development
excerpt. It never substitutes estimates or generated financial figures.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ISSUERS = {
    "COST": {
        "cik": 909832,
        "raw_sha256": "71a4fd99c86f27c3aa27b8f05b3a9705c16f0060b425395bb1a367ce239b7d1f",
        "filing_2023": "0000909832-23-000042",
        "filing_2024": "0000909832-24-000049",
        "ends": {"2022": "2022-08-28", "2023": "2023-09-03", "2024": "2024-09-01"},
        "flow_tag": "CostOfGoodsAndServicesSold",
    },
    "WMT": {
        "cik": 104169,
        "raw_sha256": "54ec3fbf36dc203dd00a0333396b3df2b6695ecdf6cbb19b6ec41b053d86b517",
        "filing_2023": "0000104169-23-000020",
        "filing_2024": "0000104169-24-000056",
        "ends": {"2022": "2022-01-31", "2023": "2023-01-31", "2024": "2024-01-31"},
        "flow_tag": "CostOfRevenue",
    },
}
CONCEPTS = {
    "Revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Inventory": "InventoryNet",
    "Trade payables": "AccountsPayableCurrent",
}


def _read(snapshot_dir: Path, spec: dict) -> dict:
    path = snapshot_dir / f"CIK{spec['cik']:010d}-companyfacts.json.gz"
    raw = gzip.decompress(path.read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    if digest != spec["raw_sha256"]:
        raise ValueError(f"snapshot_hash_mismatch:{spec['cik']}:{digest}")
    data = json.loads(raw)
    if data.get("cik") != spec["cik"]:
        raise ValueError(f"snapshot_cik_mismatch:{spec['cik']}")
    return data


def _record(ticker: str, metric: str, concept: str, fact: dict) -> dict:
    identity = {key: fact.get(key) for key in ("start", "end", "val", "accn", "form", "filed", "frame")}
    record_id = hashlib.sha256(f"{ticker}:{concept}:{json.dumps(identity, sort_keys=True)}".encode()).hexdigest()[:16]
    return {
        "id": record_id,
        "issuer": ticker,
        "metric": metric,
        "concept": concept,
        "start": fact.get("start", ""),
        "end": fact["end"],
        "filed": fact["filed"],
        "form": fact["form"],
        "accession": fact["accn"],
        "fy": fact.get("fy", ""),
        "fp": fact.get("fp", ""),
        "frame": fact.get("frame", ""),
        "unit": "USD",
        "value": fact["val"],
    }


def extract(snapshot_dir: Path) -> dict:
    records: dict[str, dict] = {}
    source_meta = []
    for ticker, spec in ISSUERS.items():
        data = _read(snapshot_dir, spec)
        source_meta.append({
            "ticker": ticker,
            "entity_name": data["entityName"],
            "cik": spec["cik"],
            "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{spec['cik']:010d}.json",
            "sha256_raw_json": spec["raw_sha256"],
        })
        concepts = CONCEPTS | {"Cost of sales": spec["flow_tag"]}
        for metric, concept in concepts.items():
            facts = data["facts"]["us-gaap"][concept]["units"]["USD"]
            years = ("2023", "2024") if metric in ("Revenue", "Cost of sales") else ("2022", "2023", "2024")
            for year in years:
                end = spec["ends"][year]
                accession = spec["filing_2023"] if year == "2022" else spec["filing_2024"]
                chosen = [fact for fact in facts if fact.get("end") == end
                          and fact.get("accn") == accession and fact.get("form") == "10-K"
                          and (bool(fact.get("start")) == (metric in ("Revenue", "Cost of sales")))]
                distinct = {json.dumps(fact, sort_keys=True) for fact in chosen}
                if len(distinct) != 1:
                    raise ValueError(f"canonical_fact_ambiguous:{ticker}:{metric}:{year}:{len(distinct)}")
                truth = chosen[0]
                same_end = [fact for fact in facts if fact.get("end") == end and fact.get("accn") != accession
                            and fact.get("form") in ("10-K", "10-Q") and fact.get("filed", "") <= "2025-12-31"]
                nearby = [fact for fact in facts if fact.get("end", "").startswith(year)
                          and fact.get("end") != end and fact.get("form") == "10-Q"
                          and fact.get("filed", "") <= "2025-12-31"]
                same_end.sort(key=lambda fact: (fact.get("filed", ""), fact.get("accn", "")), reverse=True)
                nearby.sort(key=lambda fact: (fact.get("end", ""), fact.get("filed", "")), reverse=True)
                prior_original = [fact for fact in same_end if fact.get("accn") == spec["filing_2023"]]
                for fact in [truth, *prior_original[:1], *same_end[:3], *nearby[:2]]:
                    row = _record(ticker, metric, concept, fact)
                    records[row["id"]] = row
    rows = sorted(records.values(), key=lambda row: (row["issuer"], row["metric"], row["end"], row["filed"], row["id"]))
    return {"schema": "sec-retail-working-capital-source-v1", "snapshot_date": "2026-09-24",
            "source_meta": source_meta, "records": rows,
            "scope_note": "All rows are unmodified SEC companyfacts observations. The excerpt and its published builder are development-only and ineligible for an official hidden final set."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "sources/retail_excerpt.json")
    args = parser.parse_args()
    excerpt = extract(args.snapshots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(excerpt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"records": len(excerpt["records"]), "issuers": len(excerpt["source_meta"])}))


if __name__ == "__main__":
    main()
