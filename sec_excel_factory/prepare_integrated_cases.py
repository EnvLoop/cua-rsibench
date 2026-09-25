"""Prepare filing-pinned Excel-web candidates from frozen SEC companyfacts.

This tool only prepares private candidate inputs. It neither opens Excel nor
admits a task. SEC source facts and modeled scenario assumptions are separate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import gzip
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RAW = HERE / "sources/raw"
PINS = {
    "AAPL": ("apple-companyfacts.json.gz", "73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43"),
    "MSFT": ("microsoft-companyfacts.json.gz", "f8aae2965b20ad0df44bdf7ccbedf797d275b6b8dc030154a7a311361bb7246f"),
}
TAGS = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "operating_income": "OperatingIncomeLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capital_expenditures": "PaymentsToAcquirePropertyPlantAndEquipment",
    "cost_of_sales": "CostOfGoodsAndServicesSold",
    "assets": "Assets",
    "liabilities": "Liabilities",
    "equity": "StockholdersEquity",
    "inventory": "InventoryNet",
    "trade_payables": "AccountsPayableCurrent",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
}
FLOW = frozenset(list(TAGS)[:5])
STOCK = frozenset(set(TAGS) - FLOW)
Q3_METRICS = ("revenue", "operating_income", "operating_cash_flow", "capital_expenditures", "cost_of_sales")
SPLIT_YEARS = {
    "train_candidate": {2019, 2020},
    "selection_candidate": {2021, 2022},
    "final_candidate": {2023, 2024, 2025, 2026},
}
COUNTS = {"train_candidate": 20, "selection_candidate": 20, "final_candidate": 100}


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_data(ticker: str) -> dict:
    filename, expected = PINS[ticker]
    raw = gzip.decompress((RAW / filename).read_bytes())
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f"source hash changed: {ticker}")
    data = json.loads(raw)
    if data.get("cik") not in {320193, 789019}:
        raise ValueError(f"source CIK mismatch: {ticker}")
    return data


def facts(data: dict, metric: str) -> list[dict]:
    result = data["facts"]["us-gaap"].get(TAGS[metric], {}).get("units", {}).get("USD", [])
    return result if isinstance(result, list) else []


def days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def original_annual_anchors(data: dict) -> list[dict]:
    candidates = [r for r in facts(data, "revenue") if
                  r.get("form") == "10-K" and r.get("fp") == "FY"
                  and r.get("fy") in range(2019, 2027)
                  and r.get("end", "").startswith(str(r.get("fy")))
                  and r.get("start") and 330 <= days(r["start"], r["end"]) <= 381]
    by_year: dict[int, list[dict]] = {}
    for row in candidates:
        by_year.setdefault(row["fy"], []).append(row)
    result = []
    for year, rows in sorted(by_year.items()):
        originals = sorted(rows, key=lambda r: (r["filed"], r["accn"]))
        chosen = originals[0]
        if any(r["accn"] == chosen["accn"] and r["end"] != chosen["end"] for r in originals):
            raise ValueError(f"ambiguous annual anchor for {year}")
        result.append(chosen)
    return result


def exact_one(rows: list[dict], *, label: str) -> dict:
    unique = {digest(r): r for r in rows}
    if len(unique) != 1:
        raise ValueError(f"ambiguous/missing SEC fact {label}: {len(unique)}")
    return next(iter(unique.values()))


def row_record(row: dict, ticker: str, metric: str) -> dict:
    return {
        "id": digest({"ticker": ticker, "metric": metric, "source_record": row})[:20],
        "ticker": ticker, "metric": metric, "concept": TAGS[metric],
        "start": row.get("start", ""), "end": row["end"],
        "filed": row["filed"], "form": row["form"], "accession": row["accn"],
        "fy": row.get("fy"), "fp": row.get("fp"), "frame": row.get("frame", ""),
        "unit": "USD", "value": row["val"],
    }


def package(data: dict, ticker: str, annual: dict) -> dict:
    year = annual["fy"]
    start, end, annual_acc = annual["start"], annual["end"], annual["accn"]
    q3_candidates = [r for r in facts(data, "revenue") if
                     r.get("form") == "10-Q" and r.get("fp") == "Q3" and r.get("fy") == year
                     and r.get("start") == start and r.get("end", "") < end
                     and 220 <= days(start, r["end"]) <= 300]
    q3 = sorted(q3_candidates, key=lambda r: (r["filed"], r["accn"]))[0]
    q3_acc = q3["accn"]
    canonical: dict[str, dict] = {}
    annual_rows: list[dict] = []
    q3_rows: list[dict] = []
    for metric in TAGS:
        for row in facts(data, metric):
            if row.get("accn") == annual_acc and row.get("form") == "10-K":
                annual_rows.append(row_record(row, ticker, metric))
            if row.get("accn") == q3_acc and row.get("form") == "10-Q":
                q3_rows.append(row_record(row, ticker, metric))
        source = [r for r in facts(data, metric) if
                  r.get("accn") == annual_acc and r.get("form") == "10-K"
                  and r.get("filed") == annual["filed"] and r.get("end") == end
                  and (r.get("start") == start if metric in FLOW else "start" not in r)]
        selected = exact_one(source, label=f"{ticker}/{year}/{metric}/annual")
        canonical[f"annual:{metric}"] = row_record(selected, ticker, metric)
    for metric in Q3_METRICS:
        source = [r for r in facts(data, metric) if
                  r.get("accn") == q3_acc and r.get("form") == "10-Q"
                  and r.get("filed") == q3["filed"] and r.get("end") == q3["end"]
                  and r.get("start") == start]
        selected = exact_one(source, label=f"{ticker}/{year}/{metric}/q3-ytd")
        canonical[f"q3:{metric}"] = row_record(selected, ticker, metric)
    def unique_rows(rows: list[dict]) -> list[dict]:
        return sorted({r["id"]: r for r in rows}.values(),
                      key=lambda r: (r["metric"], r["end"], r["start"], r["id"]))
    arows, qrows = unique_rows(annual_rows), unique_rows(q3_rows)
    for record in canonical.values():
        if record["id"] not in {r["id"] for r in (arows if record["form"] == "10-K" else qrows)}:
            raise ValueError("canonical record not in raw source rows")
    return {
        "schema": "sec-integrated-source-package-v1", "ticker": ticker,
        "entity_name": data["entityName"], "cik": data["cik"], "fiscal_year": year,
        "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{data['cik']:010d}.json",
        "source_raw_sha256": PINS[ticker][1],
        "annual_accession": annual_acc, "annual_filed": annual["filed"],
        "q3_accession": q3_acc, "q3_filed": q3["filed"],
        "annual_start": start, "annual_end": end, "q3_end": q3["end"],
        "fiscal_days": days(start, end), "q3_days": days(start, q3["end"]),
        "canonical": canonical, "annual_rows": arows, "q3_rows": qrows,
    }


def packages() -> list[dict]:
    out = []
    for ticker in PINS:
        data = source_data(ticker)
        for anchor in original_annual_anchors(data):
            try:
                out.append(package(data, ticker, anchor))
            except (IndexError, ValueError, KeyError):
                continue
    return sorted(out, key=lambda p: (p["fiscal_year"], p["ticker"]))


def allocate_cases(source_packages: list[dict]) -> list[dict]:
    grouped = {}
    for split, years in SPLIT_YEARS.items():
        grouped[split] = [p for p in source_packages if p["fiscal_year"] in years]
        if not grouped[split]:
            raise ValueError(f"no source packages in {split}")
    seen = set()
    for split, items in grouped.items():
        for item in items:
            key = (item["annual_accession"], item["q3_accession"])
            if key in seen:
                raise ValueError(f"source filing pair reused across splits: {split}")
            seen.add(key)
    out = []
    for split, count in COUNTS.items():
        items = grouped[split]
        for index in range(count):
            pack = items[index % len(items)]
            iteration = index // len(items)
            fault_count = 6 + (iteration % 4)
            scenario = {"inventory_shock_m": float(50 + 29 * iteration + 13 * (index % 5)),
                        "payables_shock_m": float(-40 - 17 * iteration - 11 * (index % 7)),
                        "capex_multiplier": round(0.86 + (iteration % 11) * 0.037, 3)}
            case_id = f"{split[:1]}-{pack['ticker'].lower()}-{pack['fiscal_year']}-{iteration:03d}"
            out.append({"schema": "sec-integrated-case-v1", "case_id": case_id,
                        "split": split, "template_group": f"integrated-v1-{split}",
                        "source_group": f"{pack['ticker']}:{pack['annual_accession']}:{pack['q3_accession']}",
                        "entity_group": pack["cik"], "source_package": pack,
                        "scenario": scenario, "fault_count": fault_count,
                        "fault_offset": (7 * iteration + index) % 19,
                        "admission_status": "offline_candidate_only"})
    if len(out) != 140 or len({c["case_id"] for c in out}) != 140:
        raise ValueError("case count or identity mismatch")
    accessions = {}
    for case in out:
        for accession in (case["source_package"]["annual_accession"], case["source_package"]["q3_accession"]):
            previous = accessions.setdefault(accession, case["split"])
            if previous != case["split"]:
                raise ValueError("source accession crosses split")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    source_packages = packages()
    cases = allocate_cases(source_packages)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(cases, separators=(",", ":")) + "\n")
    per_split = {}
    for split in COUNTS:
        these = [c for c in cases if c["split"] == split]
        per_split[split] = {"candidate_count": len(these),
                            "distinct_source_filing_pairs": len({c["source_group"] for c in these}),
                            "distinct_issuers": len({c["entity_group"] for c in these}),
                            "template_groups": len({c["template_group"] for c in these}),
                            "fiscal_years": sorted({c["source_package"]["fiscal_year"] for c in these})}
    report = {"schema": "sec-integrated-candidate-inventory-v1",
              "scope": "offline source and task-design candidates only; no Excel-web GUI or hidden-final admission",
              "source": "hash-pinned SEC companyfacts snapshots for AAPL and MSFT",
              "source_packages": len(source_packages), "counts": per_split,
              "source_accession_split_overlap": 0,
              "candidate_identity_commitment_sha256": digest([c["case_id"] for c in cases]),
              "limitations": ["Only two issuer families", "The same issuer and the same calculation template recur across splits", "Some final-source facts and fault shapes appeared in public development prototypes", "No final item is sealed or GUI-admitted"]}
    args.public_out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"source_packages": len(source_packages), "counts": per_split}, sort_keys=True))


if __name__ == "__main__":
    main()
