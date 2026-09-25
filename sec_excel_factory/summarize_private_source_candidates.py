"""Summarize unverified private SEC candidate coverage without admitting sources.

The input and detailed output stay evaluator-held. This only indexes facts from
proxy-delivered companyfacts; it never substitutes for original-filing checks.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def original_filing_candidate(data: dict, cik: int) -> dict | None:
    assets = data["facts"].get("us-gaap", {}).get("Assets", {}).get("units", {}).get("USD", [])
    anchors = [r for r in assets if r.get("form") == "10-K" and not r.get("start")
               and r.get("end", "").startswith("2024-") and "2024-01-01" <= r.get("filed", "") <= "2025-06-30"]
    if not anchors:
        return None
    newest_end = max(r["end"] for r in anchors)
    matches = [r for r in anchors if r["end"] == newest_end]
    chosen = min(matches, key=lambda r: (r["filed"], r["accn"]))
    acc = chosen["accn"]
    facts = defaultdict(list)
    for concept, item in data["facts"]["us-gaap"].items():
        for r in item.get("units", {}).get("USD", []):
            if r.get("accn") == acc and r.get("form") == "10-K" and r.get("filed") == chosen["filed"]:
                facts[concept].append(r)
    current = {concept for concept, rows in facts.items() if any(r.get("end") == newest_end for r in rows)}
    two_period = {concept for concept, rows in facts.items()
                  if any(r.get("end") == newest_end for r in rows)
                  and any(r.get("end", "") < newest_end for r in rows)}
    return {"accession_candidate": acc, "filing_date_candidate": chosen["filed"],
            "period_end_candidate": newest_end,
            "filing_index_url_candidate":
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.html",
            "current_period_usd_concepts_in_proxy_payload": len(current),
            "two_period_usd_concepts_in_proxy_payload": len(two_period),
            "current_concepts_in_proxy_payload": sorted(current),
            "two_period_concepts_in_proxy_payload": sorted(two_period)}


def summarize(manifest_path: Path, snapshot_dir: Path, detailed_out: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    receipt = json.loads((snapshot_dir / "private-candidate-capture-receipt.json").read_text())
    rows_by_ticker = {r["ticker"]: r for r in receipt["sources"]}
    rows = []
    for candidate in manifest["candidates"]:
        ticker, cik = candidate["ticker"], int(candidate["cik"])
        captured = rows_by_ticker.get(ticker)
        if not captured or "local_snapshot_sha256" not in captured:
            rows.append({"ticker": ticker, "cik_from_untrusted_index": cik,
                         "status": "no_candidate_snapshot"})
            continue
        compressed = (snapshot_dir / f"CIK{cik:010d}-companyfacts.json.gz").read_bytes()
        if digest(compressed) != captured["local_snapshot_sha256"]:
            raise ValueError(f"candidate_snapshot_hash_changed:{ticker}")
        raw = gzip.decompress(compressed)
        if digest(raw) != captured["proxy_delivered_body_sha256"]:
            raise ValueError(f"candidate_proxy_body_hash_changed:{ticker}")
        data = json.loads(raw)
        if data["cik"] != cik:
            raise ValueError(f"candidate_cik_mismatch:{ticker}")
        filing = original_filing_candidate(data, cik)
        rows.append({"ticker": ticker, "cik_from_untrusted_index": cik,
                     "status": "proxy_sourced_candidate_pending_nonproxy_official_verification"
                     if filing else "no_2024_original_10k_candidate_in_proxy_payload",
                     "proxy_raw_body_sha256": digest(raw), "original_10k_candidate": filing})
    detailed = {"schema": "sec-private-proxy-source-coverage-v1",
                "status": "unverified evaluator-held candidates only; no official admission",
                "source_identity_manifest_sha256": digest(manifest_path.read_bytes()),
                "candidate_rows": rows, "independently_verified_source_families": 0,
                "official_benchmark_admissions": 0}
    detailed_out.parent.mkdir(parents=True, exist_ok=True)
    detailed_out.write_text(json.dumps(detailed, indent=2) + "\n")
    counts = Counter(r["status"] for r in rows)
    available = [r["original_10k_candidate"] for r in rows if r.get("original_10k_candidate")]
    return {"schema": "sec-private-proxy-source-coverage-aggregate-v1",
            "status": "unverified candidates only",
            "candidate_identities": len(rows), "proxy_snapshots_saved": len(rows) - counts["no_candidate_snapshot"],
            "original_10k_candidates_from_proxy": len(available),
            "candidate_10k_current_concepts_ge_30": sum(r["current_period_usd_concepts_in_proxy_payload"] >= 30 for r in available),
            "candidate_10k_two_period_concepts_ge_12": sum(r["two_period_usd_concepts_in_proxy_payload"] >= 12 for r in available),
            "independently_verified_source_families": 0,
            "official_benchmark_admissions": 0,
            "detailed_evaluator_only_path": str(detailed_out)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--snapshot-dir", type=Path, required=True)
    p.add_argument("--detailed-out", type=Path, required=True)
    p.add_argument("--aggregate-out", type=Path, required=True)
    args = p.parse_args()
    aggregate = summarize(args.manifest, args.snapshot_dir, args.detailed_out)
    args.aggregate_out.parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_out.write_text(json.dumps(aggregate, indent=2) + "\n")
    print(json.dumps({k: v for k, v in aggregate.items() if k not in {"detailed_evaluator_only_path", "schema"}}))


if __name__ == "__main__":
    main()
