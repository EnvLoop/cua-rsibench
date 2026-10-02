"""Freeze public SEC companyfacts delivered by a read-only web text proxy.

This is a transport fallback when SEC hosts fail TLS from the local shell. It
does not pretend the proxy response is a direct SEC download. Before accepting
new issuers, the same transport must reproduce both existing official pinned
Apple/Microsoft JSON objects exactly. It also checks pinned Costco/Walmart
excerpt records and prior source-audit filing anchors where available.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONTROLS = {
    "AAPL": (320193, "apple-companyfacts.json.gz"),
    "MSFT": (789019, "microsoft-companyfacts.json.gz"),
}
DEFAULT_TICKERS = ("COST", "WMT", "GOOGL", "META", "CRM")
HEADER = b"Markdown Content:\n"
CONTACT = re.compile(r"^[^\s]+(?: [^\s]+)+.*[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def canonical(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def retrieve(cik: int, user_agent: str, *, timeout: int = 60) -> tuple[dict, bytes, bytes]:
    sec_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    proxy_url = f"https://r.jina.ai/{sec_url}"
    completed = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                                "--user-agent", user_agent,
                                "--max-time", str(timeout), proxy_url],
                               capture_output=True, check=True)
    payload = completed.stdout
    if payload.count(HEADER) != 1:
        raise ValueError("proxy_wrapper_missing_or_ambiguous")
    prefix, body = payload.split(HEADER, 1)
    if f"URL Source: {sec_url}\n".encode() not in prefix:
        raise ValueError("proxy_source_url_mismatch")
    # The proxy adds one newline after the SEC JSON body. Both pre-existing
    # direct SEC snapshots prove that removing it recovers the exact raw bytes.
    raw_sec_body = body.removesuffix(b"\n")
    parsed = json.loads(raw_sec_body)
    if parsed.get("cik") != cik or "us-gaap" not in parsed.get("facts", {}):
        raise ValueError("invalid_companyfacts_payload")
    return parsed, payload, raw_sec_body


def control_check(ticker: str, received: dict) -> None:
    cik, filename = CONTROLS[ticker]
    local = json.loads(gzip.decompress((HERE / "sources/raw" / filename).read_bytes()))
    if received.get("cik") != cik or received != local:
        raise ValueError(f"official_pinned_control_mismatch:{ticker}")


def retail_record_matches(data: dict, ticker: str) -> int:
    excerpt = json.loads((HERE / "sources/retail_excerpt.json").read_text())
    rows = [r for r in excerpt["records"] if r["issuer"] == ticker]
    if not rows:
        raise ValueError(f"retail_excerpt_has_no_records:{ticker}")
    for row in rows:
        sec_rows = data["facts"]["us-gaap"][row["concept"]]["units"][row["unit"]]
        matches = {json.dumps(r, sort_keys=True) for r in sec_rows if
                   r.get("accn") == row["accession"] and r.get("filed") == row["filed"]
                   and r.get("form") == row["form"] and r.get("start", "") == row["start"]
                   and r.get("end") == row["end"] and r.get("fy") == row["fy"]
                   and r.get("fp") == row["fp"] and r.get("frame", "") == row["frame"]
                   and r.get("val") == row["value"]}
        if len(matches) != 1:
            raise ValueError(f"retail_source_row_mismatch:{ticker}:{row['id']}")
    return len(rows)


def prior_audit_check(data: dict, ticker: str) -> dict:
    audit = json.loads((HERE / "candidate_audit_fetched_2026-09-24.json").read_text())
    old = next((r for r in audit["results"] if r["ticker"] == ticker), None)
    if old is None or old.get("status") != "eligible_source":
        return {"prior_audit_anchor_checked": False}
    acc, filed = old["accession"], old["filed"]
    rows = data["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    matching = [r for r in rows if r.get("accn") == acc and r.get("filed") == filed
                and r.get("form") == "10-K" and r.get("end") == old["year_ends"]["2024"]]
    if not matching:
        raise ValueError(f"prior_audit_anchor_missing:{ticker}")
    return {"prior_audit_anchor_checked": True, "prior_audit_accession": acc}


def prior_direct_sec_hash(ticker: str) -> str:
    audit = json.loads((HERE / "candidate_audit_fetched_2026-09-24.json").read_text())
    entries = [r for r in audit["results"] if r["ticker"] == ticker]
    if len(entries) != 1 or "sha256_raw_json" not in entries[0]:
        raise ValueError(f"prior_direct_sec_hash_unavailable:{ticker}")
    return entries[0]["sha256_raw_json"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    if args.delay < 1 or len(args.tickers) > 10:
        raise ValueError("mirror fetch is limited to ten new issuers and <=1 request/s")
    user_agent = os.environ.get("SEC_USER_AGENT", "")
    if not CONTACT.search(user_agent):
        raise ValueError("SEC_USER_AGENT must identify an organization and reachable contact")
    selected = set(args.tickers)
    if selected & CONTROLS.keys() or len(selected) != len(args.tickers):
        raise ValueError("duplicate or control ticker in new-issuer list")
    candidates = json.loads((HERE / "candidate_issuers.json").read_text())["candidates"]
    cik_by_ticker = {r["ticker"]: r["cik"] for r in candidates}
    if not selected <= cik_by_ticker.keys():
        raise ValueError("unknown candidate ticker")
    args.out.mkdir(parents=True, exist_ok=True)
    receipts = []
    for ticker in list(CONTROLS) + args.tickers:
        time.sleep(args.delay)
        cik = CONTROLS[ticker][0] if ticker in CONTROLS else cik_by_ticker[ticker]
        data, wrapper, raw_sec_body = retrieve(cik, user_agent)
        raw_hash = sha256(raw_sec_body).hexdigest()
        if ticker in CONTROLS:
            control_check(ticker, data)
            if raw_hash != prior_direct_sec_hash(ticker):
                raise ValueError(f"official_pinned_control_bytes_mismatch:{ticker}")
            receipts.append({"ticker": ticker, "cik": cik, "role": "pinned_official_object_control",
                             "identical_to_existing_official_snapshot": True,
                             "raw_sec_body_sha256": raw_hash,
                             "canonical_json_sha256": sha256(canonical(data)).hexdigest()})
            continue
        if raw_hash != prior_direct_sec_hash(ticker):
            raise ValueError(f"proxy_raw_bytes_differ_from_prior_direct_sec_snapshot:{ticker}")
        matched_retail = retail_record_matches(data, ticker) if ticker in {"COST", "WMT"} else 0
        prior = prior_audit_check(data, ticker)
        filename = f"CIK{cik:010d}-companyfacts.json.gz"
        (args.out / filename).write_bytes(gzip.compress(raw_sec_body, mtime=0))
        receipts.append({"ticker": ticker, "cik": cik, "role": "new_public_sec_json_via_proxy",
                         "official_source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                         "transport": "r.jina.ai read-only text proxy of official SEC JSON",
                         "proxy_wrapper_sha256": sha256(wrapper).hexdigest(),
                         "raw_sec_body_sha256": raw_hash,
                         "matches_prior_direct_sec_snapshot_hash": True,
                         "canonical_json_sha256": sha256(canonical(data)).hexdigest(),
                         "snapshot_gzip_sha256": sha256((args.out / filename).read_bytes()).hexdigest(),
                         "companyfacts_us_gaap_concepts": len(data["facts"]["us-gaap"]),
                         "matched_previously_pinned_retail_facts": matched_retail,
                         **prior})
        print(f"{ticker}: {len(raw_sec_body)} original SEC JSON bytes, {matched_retail} pinned retail facts matched", flush=True)
    receipt = {"schema": "sec-public-proxy-capture-v1",
               "captured_at_utc": datetime.now(timezone.utc).isoformat(),
               "scope": "source acquisition only; no workbook or GUI admission",
               "controls": {r["ticker"]: r["identical_to_existing_official_snapshot"] for r in receipts
                            if r["role"] == "pinned_official_object_control"},
               "sources": receipts}
    batch_digest = sha256(",".join(args.tickers).encode()).hexdigest()[:12]
    (args.out / f"capture-receipt-{batch_digest}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"control_count": len(CONTROLS), "new_snapshot_count": len(args.tickers)}, sort_keys=True))


if __name__ == "__main__":
    main()
