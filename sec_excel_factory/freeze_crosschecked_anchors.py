"""Freeze only the two SEC-view-crosschecked FY source facts for ten issuers.

The other companyfacts rows remain quarantined in ignored work/. A human
reviewed original SEC filing indexes and SEC-hosted filing/annual-report views;
this script enforces their recorded CIK/accession/period and asset/revenue
values against the captured JSON. It does not scrape or attest the SEC pages.
"""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from hashlib import sha256
import gzip
import json
from pathlib import Path
from urllib.parse import urlparse

from freeze_sec_expansion import annual_anchor


HERE = Path(__file__).resolve().parent
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
    "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def usd_from_million(value: int | float) -> int:
    amount = Decimal(str(value)) * Decimal(1_000_000)
    if amount != amount.to_integral_value():
        raise ValueError("official_view_value_not_integer_usd")
    return int(amount)


def exact_one(rows: list[dict], label: str) -> dict:
    unique = {json.dumps(r, sort_keys=True): r for r in rows}
    if len(unique) != 1:
        raise ValueError(f"source_fact_not_unique:{label}:{len(unique)}")
    return next(iter(unique.values()))


def source_fact(concept: str, row: dict) -> dict:
    return {"id": digest(json.dumps((concept, row), sort_keys=True,
                                    separators=(",", ":")).encode())[:20],
            "concept": concept, "unit": "USD", "start": row.get("start", ""),
            "end": row["end"], "value": row["val"], "accession": row["accn"],
            "filed": row["filed"], "form": row["form"], "fy": row["fy"],
            "fp": row["fp"], "frame": row.get("frame", "")}


def freeze(raw_dir: Path, crosschecks_path: Path, out_dir: Path) -> dict:
    candidates_path = HERE / "new_issuer_candidates.json"
    candidates = json.loads(candidates_path.read_text())["candidates"]
    checkbook = json.loads(crosschecks_path.read_text())
    checks = {r["ticker"]: r for r in checkbook["records"]}
    receipt_path = raw_dir / "candidate-capture-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    captured = {r["ticker"]: r for r in receipt["sources"]}
    if (len(candidates), len(checks), len(captured)) != (10, 10, 10):
        raise ValueError("candidate_capture_or_manual_crosscheck_incomplete")
    if not {"AAPL", "MSFT"} <= {r["ticker"] for r in receipt["controls"]}:
        raise ValueError("known_direct_sec_transport_controls_missing")
    out_dir.mkdir(parents=True, exist_ok=True)
    result_rows = []
    for candidate in candidates:
        ticker, cik = candidate["ticker"], candidate["cik"]
        cc, cr = checks[ticker], captured[ticker]
        if (cc["cik"], cr["cik"], cr["status"]) != (
                cik, cik, "pending_non_proxy_official_filing_index_and_value_crosscheck"):
            raise ValueError(f"identity_or_capture_status_mismatch:{ticker}")
        for url_key in ("official_index_url", "official_value_view_url"):
            if urlparse(cc[url_key]).hostname != "www.sec.gov":
                raise ValueError(f"non_sec_official_view_url:{ticker}:{url_key}")
        if (f"/data/{cik}/" not in cc["official_index_url"]
                or cc["accession"].replace("-", "") not in cc["official_index_url"]):
            raise ValueError(f"filing_index_url_not_bound_to_accession:{ticker}")
        raw = gzip.decompress((raw_dir / f"CIK{cik:010d}-companyfacts.json.gz").read_bytes())
        if digest(raw) != cr["raw_sec_sha256_candidate"]:
            raise ValueError(f"proxy_capture_hash_changed:{ticker}")
        sec = json.loads(raw)
        if sec.get("cik") != cik:
            raise ValueError(f"companyfacts_cik_mismatch:{ticker}")
        accession, filed, end, fy = annual_anchor(sec)
        if (accession, filed, end, fy) != (
                cc["accession"], cc["filed"], cc["period_end"], cc["fiscal_year"]):
            raise ValueError(f"official_filing_identity_mismatch:{ticker}")
        if not 0 <= (date.fromisoformat(filed) - date.fromisoformat(end)).days <= 120:
            raise ValueError(f"not_original_filing:{ticker}")
        assets = exact_one([r for r in sec["facts"]["us-gaap"]["Assets"]["units"]["USD"]
                            if r.get("accn") == accession and r.get("filed") == filed
                            and r.get("form") == "10-K" and r.get("fy") == fy
                            and r.get("fp") == "FY" and r.get("end") == end
                            and not r.get("start")], f"{ticker}:assets")
        if assets["val"] != usd_from_million(cc["assets_usd_m"]):
            raise ValueError(f"official_assets_value_mismatch:{ticker}")
        revenue_candidates = []
        for tag in REVENUE_TAGS:
            rows = [r for r in sec["facts"]["us-gaap"].get(tag, {}).get("units", {}).get("USD", [])
                    if r.get("accn") == accession and r.get("filed") == filed
                    and r.get("form") == "10-K" and r.get("fy") == fy
                    and r.get("fp") == "FY" and r.get("end") == end and r.get("start")
                    and 330 <= (date.fromisoformat(end) - date.fromisoformat(r["start"])).days + 1 <= 381
                    and r.get("val") == usd_from_million(cc["revenue_usd_m"])]
            if rows:
                revenue_candidates = [(tag, exact_one(rows, f"{ticker}:revenue:{tag}"))]
                break
        if not revenue_candidates:
            raise ValueError(f"official_revenue_value_not_found_in_original_filing:{ticker}")
        revenue_tag, revenue = revenue_candidates[0]
        source = {"schema": "sec-two-officially-crosschecked-anchors-v1",
                  "status": "two_source_facts_manually_checked_against_non_proxy_sec_view; other_companyfacts_rows_not_admitted",
                  "ticker": ticker, "cik": cik, "entity_name": sec["entityName"],
                  "companyfacts_source_url": cr["source_url"],
                  "proxy_raw_json_sha256": digest(raw),
                  "official_index_url": cc["official_index_url"],
                  "official_value_view_url": cc["official_value_view_url"],
                  "filing_accession": accession, "filing_filed": filed,
                  "filing_period_end": end, "filing_fiscal_year": fy,
                  "facts": [source_fact("Assets", assets), source_fact(revenue_tag, revenue)]}
        path = out_dir / f"{ticker.lower()}-end2024-two-anchors.json"
        path.write_text(json.dumps(source, indent=2) + "\n")
        result_rows.append({"ticker": ticker, "cik": cik, "accession": accession,
                            "fiscal_year": fy, "filed": filed, "period_end": end,
                            "official_index_url": cc["official_index_url"],
                            "official_value_view_url": cc["official_value_view_url"],
                            "assets_usd_m": cc["assets_usd_m"],
                            "revenue_usd_m": cc["revenue_usd_m"],
                            "revenue_concept": revenue_tag,
                            "proxy_raw_json_sha256": digest(raw),
                            "two_fact_excerpt_sha256": digest(path.read_bytes())})
    return {"schema": "sec-ten-official-anchor-crosscheck-v1", "date": "2026-09-25",
            "source_tier": "SEC index plus two official-view values manually crosschecked; full proxy payload unverified",
            "new_issuer_families_with_two_verified_anchors": len(result_rows),
            "distinct_original_10k_accessions": len({r["accession"] for r in result_rows}),
            "anchor_facts_verified": len(result_rows) * 2,
            "known_full_raw_direct_hash_pinned_issuers_before_expansion": 18,
            "total_issuer_identities_with_at_least_two_official_anchors": 28,
            "full_raw_direct_hash_pinned_issuers_after_expansion": 18,
            "hidden_final_source_families_admitted": 0,
            "candidate_manifest_sha256": digest(candidates_path.read_bytes()),
            "official_crosschecks_sha256": digest(crosschecks_path.read_bytes()),
            "sources": result_rows}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--crosschecks", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = freeze(args.raw_dir, args.crosschecks, args.out_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"issuer_anchors": report["new_issuer_families_with_two_verified_anchors"],
                      "verified_facts": report["anchor_facts_verified"],
                      "full_raw_direct_hash_pinned": report["full_raw_direct_hash_pinned_issuers_after_expansion"]}))


if __name__ == "__main__":
    main()
