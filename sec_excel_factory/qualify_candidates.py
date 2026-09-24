"""Audit frozen SEC companyfacts snapshots before building more Excel fixtures.

The default run is offline. Optional fetching needs SEC_USER_AGENT set to an
organization and reachable contact, and deliberately runs at <= 2 requests/s.
This qualifies *source data*, not a finished or Excel-web-admitted workbook.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from extract_sec import METRICS


HERE = Path(__file__).resolve().parent
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FLOW = {"Revenue", "Operating income", "Operating cash flow", "Capital expenditures"}
STOCK = {"Assets", "Liabilities", "Equity"}
TARGET_YEARS = (2023, 2024)
MAX_FILED = "2025-06-30"
CONTACT_PATTERN = re.compile(r"^[^\s]+(?: [^\s]+)+.*[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def annual(fact: dict) -> bool:
    try:
        days = (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
    except (KeyError, TypeError, ValueError):
        return False
    return 330 <= days <= 380


def base_fact(fact: dict, accn: str, filed: str, end: str) -> bool:
    return (
        fact.get("accn") == accn
        and fact.get("filed") == filed
        and fact.get("form") == "10-K"
        and fact.get("fy") == 2024
        and fact.get("fp") == "FY"
        and fact.get("end") == end
    )


def unique_facts(items: list[dict]) -> list[dict]:
    """Collapse exact API duplicates, preserving conflicting values for rejection."""
    seen: dict[str, dict] = {}
    for item in items:
        key = json.dumps(item, sort_keys=True, separators=(",", ":"))
        seen[key] = item
    return list(seen.values())


def get_usd(data: dict, tag: str) -> tuple[list[dict], list[str]]:
    concept = data.get("facts", {}).get("us-gaap", {}).get(tag)
    if not isinstance(concept, dict):
        return [], []
    units = concept.get("units", {})
    if not isinstance(units, dict):
        return [], []
    facts = units.get("USD", [])
    return (facts if isinstance(facts, list) else []), sorted(units)


def accession_candidates(data: dict) -> list[tuple[str, str, str]]:
    rows, _ = get_usd(data, METRICS["Revenue"])
    return sorted({
        (f["accn"], f["filed"], f["end"])
        for f in rows
        if f.get("form") == "10-K"
        and f.get("fy") == 2024
        and f.get("fp") == "FY"
        and f.get("end", "").startswith("2024-")
        and f.get("filed", "") <= MAX_FILED
        and annual(f)
        and isinstance(f.get("accn"), str)
        and isinstance(f.get("filed"), str)
    }, key=lambda x: (x[1], x[0], x[2]))


def qualify_filing(data: dict, accn: str, filed: str, end_2024: str) -> dict:
    revenue, _ = get_usd(data, METRICS["Revenue"])
    earlier = sorted({
        f["end"] for f in revenue
        if base_fact(f, accn, filed, f.get("end", ""))
        and f.get("end", "").startswith("2023-")
        and annual(f)
        and 330 <= (date.fromisoformat(end_2024) - date.fromisoformat(f["end"])).days <= 380
    })
    if len(earlier) != 1:
        return {"status": "rejected", "reason_codes": ["ambiguous_or_missing_2023_year_end"],
                "detail": {"2023_end_candidates": earlier}, "accession": accn}

    ends = {2023: earlier[0], 2024: end_2024}
    selected: dict[str, dict] = {}
    reasons: list[str] = []
    detail: dict[str, object] = {}
    starts: dict[int, set[str]] = {2023: set(), 2024: set()}
    for label, tag in METRICS.items():
        rows, available_units = get_usd(data, tag)
        if not rows:
            reasons.append(f"missing_usd_concept:{tag}")
            detail[f"{label}:units"] = available_units
            continue
        for year in TARGET_YEARS:
            matches = unique_facts([
                f for f in rows
                if base_fact(f, accn, filed, ends[year])
                and (annual(f) if label in FLOW else "start" not in f)
            ])
            if len(matches) != 1:
                reasons.append(f"non_unique_annual_fact:{year}:{tag}")
                detail[f"{label}:{year}:candidate_count"] = len(matches)
                continue
            fact = matches[0]
            if not isinstance(fact.get("val"), (int, float)) or isinstance(fact.get("val"), bool):
                reasons.append(f"non_numeric_value:{year}:{tag}")
                continue
            if label in FLOW:
                starts[year].add(fact["start"])
            selected[f"{year}:{label}"] = {
                "concept": tag, "unit": "USD", "value": fact["val"],
                "start": fact.get("start"), "end": fact["end"],
                "form": fact["form"], "accession": fact["accn"],
                "filed": fact["filed"], "fy": fact["fy"], "fp": fact["fp"],
            }
    for year in TARGET_YEARS:
        if len(starts[year]) > 1:
            reasons.append(f"flow_start_mismatch:{year}")
            detail[f"{year}:flow_starts"] = sorted(starts[year])
        try:
            assets = selected[f"{year}:Assets"]["value"]
            liabilities = selected[f"{year}:Liabilities"]["value"]
            equity = selected[f"{year}:Equity"]["value"]
        except KeyError:
            continue
        gap = assets - liabilities - equity
        detail[f"{year}:balance_gap_usd"] = gap
        # Each public XBRL value may be rounded to USD millions.
        if abs(gap) > 1_500_000:
            reasons.append(f"balance_sheet_gap:{year}")
    if reasons:
        return {"status": "rejected", "reason_codes": sorted(set(reasons)),
                "detail": detail, "accession": accn, "filed": filed, "year_ends": ends}
    return {"status": "eligible_source", "reason_codes": [], "accession": accn,
            "filed": filed, "year_ends": ends, "selected_facts": selected,
            "balance_gaps_usd": {str(year): detail[f"{year}:balance_gap_usd"] for year in TARGET_YEARS}}


def complexity_profile(data: dict, selected: dict) -> dict:
    accn = selected["accession"]
    year_ends = selected["year_ends"]
    other_filing_facts = 0
    quarterly_nearby = 0
    mixed_unit_concepts = 0
    total_usd_facts = 0
    for tag in METRICS.values():
        rows, units = get_usd(data, tag)
        total_usd_facts += len(rows)
        mixed_unit_concepts += len(units) > 1
        for row in rows:
            if row.get("end") in year_ends.values() and row.get("accn") != accn:
                other_filing_facts += 1
            if row.get("form") in ("10-Q", "10-Q/A") and row.get("end", "")[:4] in ("2023", "2024"):
                quarterly_nearby += 1
    return {
        "fiscal_year_end_months": sorted({end[5:7] for end in year_ends.values()}),
        "same_end_other_accession_fact_count": other_filing_facts,
        "nearby_quarterly_fact_count": quarterly_nearby,
        "required_concepts_with_multiple_units": mixed_unit_concepts,
        "required_concept_usd_fact_count": total_usd_facts,
        "note": "Source-data complexity indicators only; no workbook-family or GUI difficulty claim.",
    }


def qualify_snapshot(data: dict, candidate: dict, raw_sha256: str) -> dict:
    cik = candidate["cik"]
    result = {"ticker": candidate["ticker"], "cik": cik,
              "source_url": URL.format(cik=cik), "sha256_raw_json": raw_sha256,
              "industry_hypothesis": candidate["industry_hypothesis"],
              "task_shape_hypothesis": candidate["task_shape_hypothesis"]}
    if data.get("cik") != cik:
        return result | {"status": "rejected", "reason_codes": ["cik_mismatch"],
                         "actual_cik": data.get("cik")}
    filings = accession_candidates(data)
    if not filings:
        return result | {"status": "rejected", "reason_codes": ["no_fy2024_10k_revenue_anchor"]}
    attempts = [qualify_filing(data, *filing) for filing in filings]
    eligible = [attempt for attempt in attempts if attempt["status"] == "eligible_source"]
    if not eligible:
        return result | {"status": "rejected", "reason_codes": sorted({
            code for attempt in attempts for code in attempt["reason_codes"]}),
            "filing_attempts": attempts}
    chosen = eligible[0]  # Earliest complete original FY2024 Form 10-K.
    return result | chosen | {"entity_name": data.get("entityName"),
                              "complexity_profile": complexity_profile(data, chosen)}


def read_snapshot(path: Path) -> tuple[dict, str, str]:
    compressed = path.read_bytes()
    raw = gzip.decompress(compressed) if path.suffix == ".gz" else compressed
    return json.loads(raw), sha256(raw), sha256(compressed)


def fetch_one(cik: int, user_agent: str, path: Path, delay: float) -> None:
    url = URL.format(cik=cik)
    for attempt in range(3):
        time.sleep(delay)
        request = urllib.request.Request(url, headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                parsed = json.loads(body)
                if parsed.get("cik") != cik:
                    raise ValueError("CIK mismatch in fetched response")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(gzip.compress(body, mtime=0))
                return
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            time.sleep(min(float(retry_after), 30.0) if retry_after.isdigit() else 2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def audit(candidates_path: Path, snapshots_dir: Path, *, fetch: bool = False,
          user_agent: str = "", max_fetch: int = 20, delay: float = 0.5) -> dict:
    candidate_raw = candidates_path.read_bytes()
    manifest = json.loads(candidate_raw)
    candidates = manifest["candidates"]
    if len(candidates) > 20 or len(candidates) < 1:
        raise ValueError("Candidate list must be a bounded set of 1-20 issuers")
    if len({c["cik"] for c in candidates}) != len(candidates):
        raise ValueError("Duplicate CIK in candidate list")
    if fetch and not CONTACT_PATTERN.search(user_agent):
        raise ValueError("SEC_USER_AGENT must contain an organization and reachable contact email")
    if fetch and (not 1 <= max_fetch <= 20 or delay < 0.5):
        raise ValueError("Fetch is capped at 20 issuers and at most 2 requests/second")
    results = []
    fetch_count = 0
    for candidate in candidates:
        filename = candidate.get("snapshot", f"CIK{candidate['cik']:010d}-companyfacts.json.gz")
        path = snapshots_dir / filename
        if not path.exists() and fetch and fetch_count < max_fetch:
            fetch_count += 1
            try:
                fetch_one(candidate["cik"], user_agent, path, delay)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                results.append({"ticker": candidate["ticker"], "cik": candidate["cik"],
                                "status": "fetch_error", "reason_codes": [type(exc).__name__],
                                "source_url": URL.format(cik=candidate["cik"])})
                continue
        if not path.exists():
            results.append({"ticker": candidate["ticker"], "cik": candidate["cik"],
                            "status": "pending_snapshot", "reason_codes": [],
                            "source_url": URL.format(cik=candidate["cik"])})
            continue
        try:
            data, raw_hash, file_hash = read_snapshot(path)
            result = qualify_snapshot(data, candidate, raw_hash)
            result["snapshot_path"] = path.relative_to(HERE).as_posix() if path.is_relative_to(HERE) else str(path)
            result["sha256_snapshot_file"] = file_hash
            results.append(result)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            results.append({"ticker": candidate["ticker"], "cik": candidate["cik"],
                            "status": "rejected", "reason_codes": ["invalid_snapshot"],
                            "error_type": type(exc).__name__,
                            "source_url": URL.format(cik=candidate["cik"])})
    counts = dict(sorted(Counter(row["status"] for row in results).items()))
    return {
        "schema": "sec-excel-candidate-audit-v1",
        "candidate_manifest_sha256": sha256(candidate_raw),
        "identity_source": manifest["identity_source"],
        "target_fiscal_years": list(TARGET_YEARS),
        "required_us_gaap_concepts": METRICS,
        "selection_policy": "An exact USD fact for each of seven tags and each year, from one original FY2024 10-K accession; FY2023/FY2024 issuer-specific end dates, 330-380 day flows, instant stocks, common start date/filed date, and assets=liabilities+equity within USD 1.5m.",
        "counts": {"candidates": len(candidates), "snapshots_audited": sum(r["status"] in ("eligible_source", "rejected") for r in results),
                   "eligible_sources": counts.get("eligible_source", 0),
                   "rejected_sources": counts.get("rejected", 0),
                   "pending_snapshots": counts.get("pending_snapshot", 0),
                   "fetch_errors": counts.get("fetch_error", 0)},
        "results": results,
        "scope_note": "Eligible means source facts qualify. No additional workbook, independent workbook family, Excel-web round trip, or benchmark score was created by this audit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=HERE / "candidate_issuers.json")
    parser.add_argument("--snapshots", type=Path, default=HERE / "sources" / "raw")
    parser.add_argument("--output", type=Path, default=HERE / "candidate_audit.json")
    parser.add_argument("--fetch", action="store_true", help="fetch missing snapshots with declared SEC_USER_AGENT")
    parser.add_argument("--max-fetch", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    report = audit(args.candidates, args.snapshots, fetch=args.fetch,
                   user_agent=os.environ.get("SEC_USER_AGENT", ""),
                   max_fetch=args.max_fetch, delay=args.delay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
