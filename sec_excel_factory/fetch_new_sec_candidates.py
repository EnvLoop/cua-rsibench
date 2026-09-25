"""Fetch ten extra companyfacts snapshots as unverified source candidates.

Unlike the earlier sixteen, these have no prior direct-SEC raw hash. They must
not be called authenticated source facts until a non-proxy original SEC filing
index and representative values are independently checked for each accession.
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


HERE = Path(__file__).resolve().parent
CONTACT = re.compile(r"^[^\s]+(?: [^\s]+)+.*[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    if args.delay < 1:
        raise ValueError("proxy fetch limited to <=1 request/s")
    agent = os.environ.get("SEC_USER_AGENT", "")
    if not CONTACT.search(agent):
        raise ValueError("SEC_USER_AGENT must identify an organization and reachable contact")
    manifest_path = HERE / "new_issuer_candidates.json"
    manifest = json.loads(manifest_path.read_text())
    candidates = manifest["candidates"]
    if len(candidates) != 10 or len({x["cik"] for x in candidates}) != 10:
        raise ValueError("expected exactly ten distinct issuer candidates")
    args.out.mkdir(parents=True, exist_ok=True)
    controls = []
    for ticker, (cik, _) in CONTROLS.items():
        time.sleep(args.delay)
        data, wrapper, raw = retrieve(cik, agent)
        control_check(ticker, data)
        if sha256(raw).hexdigest() != prior_direct_sec_hash(ticker):
            raise ValueError(f"transport_control_sha256_failure:{ticker}")
        controls.append({"ticker": ticker, "raw_sec_sha256": sha256(raw).hexdigest()})
    results = []
    for candidate in candidates:
        time.sleep(args.delay)
        ticker, cik = candidate["ticker"], candidate["cik"]
        data, wrapper, raw = retrieve(cik, agent)
        target = args.out / f"CIK{cik:010d}-companyfacts.json.gz"
        target.write_bytes(gzip.compress(raw, mtime=0))
        results.append({"ticker": ticker, "cik": cik,
                        "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                        "entity_name_from_proxy_payload": data["entityName"],
                        "raw_sec_sha256_candidate": sha256(raw).hexdigest(),
                        "proxy_wrapper_sha256": sha256(wrapper).hexdigest(),
                        "snapshot_gzip_sha256": sha256(target.read_bytes()).hexdigest(),
                        "status": "pending_non_proxy_official_filing_index_and_value_crosscheck"})
        print(f"{ticker}: fetched candidate {len(raw)} bytes; official filing check pending", flush=True)
    receipt = {"schema": "sec-ten-source-capture-candidate-v1",
               "captured_at_utc": datetime.now(timezone.utc).isoformat(),
               "candidate_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
               "controls": controls, "sources": results,
               "source_families_accepted": 0, "official_benchmark_admissions": 0}
    (args.out / "candidate-capture-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"fetched_candidates": len(results), "accepted_source_families": 0}))


if __name__ == "__main__":
    main()
