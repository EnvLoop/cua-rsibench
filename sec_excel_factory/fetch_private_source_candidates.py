"""Acquire evaluator-held SEC companyfacts candidates through an untrusted proxy.

No source from this script is independently authenticated or benchmark-admitted.
Keep both the identity manifest and outputs in ignored evaluator-only work/.
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
import time

from fetch_public_sec_mirror import CONTROLS, control_check, prior_direct_sec_hash, retrieve


CONTACT = re.compile(r"^[^\s]+(?: [^\s]+)+.*[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
MAX_CANDIDATES = 50


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True,
                   help="Evaluator-held identity candidate list; never commit this file")
    p.add_argument("--out", type=Path, required=True,
                   help="Ignored evaluator-only destination for raw candidate snapshots")
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    if args.delay < 1:
        raise ValueError("candidate acquisition limited to <=1 request/s")
    agent = os.environ.get("SEC_USER_AGENT", "")
    if not CONTACT.search(agent):
        raise ValueError("SEC_USER_AGENT must identify an organization and reachable business contact")
    manifest = json.loads(args.manifest.read_text())
    candidates = manifest["candidates"]
    if not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError("candidate count out of bounds")
    tickers = [c["ticker"] for c in candidates]
    ciks = [int(c["cik"]) for c in candidates]
    if len(set(tickers)) != len(tickers) or len(set(ciks)) != len(ciks):
        raise ValueError("duplicate candidate ticker or CIK")
    if set(tickers) & set(CONTROLS):
        raise ValueError("pinned transport controls cannot be private candidates")
    args.out.mkdir(parents=True, exist_ok=True)
    controls = []
    for ticker, (cik, _) in CONTROLS.items():
        time.sleep(args.delay)
        parsed, wrapper, raw = retrieve(cik, agent)
        control_check(ticker, parsed)
        if digest(raw) != prior_direct_sec_hash(ticker):
            raise ValueError(f"pinned_transport_control_mismatch:{ticker}")
        controls.append({"ticker": ticker, "exact_prior_direct_sec_sha256": digest(raw),
                         "proxy_wrapper_sha256": digest(wrapper)})
    results = []
    for candidate in candidates:
        ticker, cik = candidate["ticker"], int(candidate["cik"])
        time.sleep(args.delay)
        try:
            parsed, wrapper, raw = retrieve(cik, agent)
            target = args.out / f"CIK{cik:010d}-companyfacts.json.gz"
            target.write_bytes(gzip.compress(raw, mtime=0))
            row = {"ticker": ticker, "cik_from_untrusted_index": cik,
                   "entity_name_from_proxy_payload": parsed["entityName"],
                   "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                   "proxy_wrapper_sha256": digest(wrapper),
                   "proxy_delivered_body_sha256": digest(raw),
                   "local_snapshot_sha256": digest(target.read_bytes()),
                   "us_gaap_concepts": len(parsed["facts"]["us-gaap"]),
                   "status": "proxy_sourced_candidate_pending_nonproxy_official_filing_value_verification"}
            print(f"{ticker}: candidate saved; official cross-check pending", flush=True)
        except Exception as exc:
            row = {"ticker": ticker, "cik_from_untrusted_index": cik,
                   "status": "transport_error_no_source_credit",
                   "error_type": type(exc).__name__}
            print(f"{ticker}: transport error {type(exc).__name__}", flush=True)
        results.append(row)
        receipt = {"schema": "sec-private-source-candidate-capture-v1",
                   "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                   "manifest_sha256": digest(args.manifest.read_bytes()),
                   "source_identity_tier": "untrusted proxy candidate; zero independent official source acceptance",
                   "transport_controls": controls, "sources": results,
                   "candidate_snapshots_saved": sum("local_snapshot_sha256" in r for r in results),
                   "independently_verified_source_families": 0,
                   "official_benchmark_admissions": 0}
        (args.out / "private-candidate-capture-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"attempted": len(results),
                      "saved_unverified_candidates": receipt["candidate_snapshots_saved"],
                      "independently_verified": 0}))


if __name__ == "__main__":
    main()
