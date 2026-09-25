"""Conservative lane-wide E2B lease budget, including failed/no-ID creates.

This is a planning reserve, not the provider invoice. Every GUI create attempt
counts its full requested server lease, even when the create acknowledgement
was lost. Neutral batch items sharing one sandbox count one batch lease.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path


RATE_USD_PER_HOUR_UPPER = Decimal("1.00")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def audit(work_root: Path, *, proposed_new_sandboxes: int,
          proposed_lease_seconds: int, max_lane_reserved_usd: Decimal) -> dict:
    if not 0 <= proposed_new_sandboxes <= 300 or not 120 <= proposed_lease_seconds <= 600:
        raise ValueError("Invalid proposed sandbox envelope")
    if max_lane_reserved_usd <= 0:
        raise ValueError("Positive lane-wide USD cap required")
    records = []
    for root_name in ("gui", "final-v2-gui"):
        root = work_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("receipt.json"):
            raw = path.read_bytes()
            try:
                receipt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if receipt.get("schema") != "cua-native-wdi-gui-development-attempt-v1":
                continue
            lease = receipt.get("sandbox_timeout_seconds", 600)  # Pre-sweeper shell pinned 600 s.
            if not isinstance(lease, int) or not 120 <= lease <= 600:
                raise ValueError("GUI attempt has invalid server lease")
            records.append({"kind": "gui_attempt", "receipt_sha256": digest(raw),
                            "lease_seconds": lease, "status": receipt.get("status"),
                            "has_sandbox_id": bool(receipt.get("sandbox_id_sha256"))})
    for name in ("batch-001", "batch-002"):
        path = work_root / "final-v2-normalization" / name / "batch-receipt.json"
        raw = path.read_bytes()
        receipt = json.loads(raw)
        if receipt.get("schema") != "cua-native-impress-batch-normalization-v1":
            raise ValueError("Neutral batch receipt changed")
        records.append({"kind": "neutral_batch", "receipt_sha256": digest(raw),
                        "lease_seconds": receipt["lease_seconds"], "status": receipt["status"],
                        "has_sandbox_id": bool(receipt.get("sandbox_id_sha256"))})
    for path in [work_root / "final-v2-normalization" / "esp-impress-1" / "receipt.json",
                 *sorted(work_root.glob("normalized-impress-neutral-*/receipt.json"))]:
        if not path.is_file():
            continue
        raw = path.read_bytes()
        receipt = json.loads(raw)
        if receipt.get("schema") != "cua-native-impress-trusted-normalization-v1":
            raise ValueError("Neutral single receipt changed")
        records.append({"kind": "neutral_single", "receipt_sha256": digest(raw),
                        "lease_seconds": 600, "status": receipt["status"],
                        "has_sandbox_id": bool(receipt.get("sandbox_id_sha256"))})
    health_path = work_root / "sweep-runs" / "full-remaining-001" / "health-probe-001.json"
    if health_path.is_file():
        raw = health_path.read_bytes()
        receipt = json.loads(raw)
        if receipt.get("schema") != "cua-native-wdi-e2b-recovery-health-probe-v1":
            raise ValueError("Health probe receipt changed")
        records.append({"kind": "health_probe", "receipt_sha256": digest(raw),
                        "lease_seconds": receipt["lease_seconds"], "status": receipt["status"],
                        "has_sandbox_id": bool(receipt.get("sandbox_id_sha256"))})
    if len({row["receipt_sha256"] for row in records}) != len(records):
        raise ValueError("A sandbox-attempt receipt was counted twice")
    past_seconds = sum(row["lease_seconds"] for row in records)
    proposed_seconds = proposed_new_sandboxes * proposed_lease_seconds
    past_usd = Decimal(past_seconds) / 3600 * RATE_USD_PER_HOUR_UPPER
    proposed_usd = Decimal(proposed_seconds) / 3600 * RATE_USD_PER_HOUR_UPPER
    total = past_usd + proposed_usd
    return {"schema": "cua-native-wdi-e2b-lane-budget-ledger-v1",
            "rate_usd_per_hour_planning_upper": str(RATE_USD_PER_HOUR_UPPER),
            "past_attempt_or_batch_count": len(records),
            "past_by_kind": dict(sorted(Counter(row["kind"] for row in records).items())),
            "past_status_counts": dict(sorted(Counter(row["status"] for row in records).items())),
            "past_no_acknowledged_sandbox_id_count": sum(not row["has_sandbox_id"] for row in records),
            "past_full_server_lease_seconds": past_seconds,
            "past_conservative_reserved_usd": str(past_usd),
            "proposed_new_sandboxes": proposed_new_sandboxes,
            "proposed_lease_seconds_each": proposed_lease_seconds,
            "proposed_reserved_usd": str(proposed_usd),
            "combined_reserved_usd": str(total),
            "lane_usd_cap": str(max_lane_reserved_usd),
            "within_cap": total <= max_lane_reserved_usd,
            "actual_billed_usd": None,
            "scope": "This WDI native desktop development lane only; not all E2B work on the account. Lease reservation is a conservative plan and not an invoice.",
            "receipt_sha256s": sorted(row["receipt_sha256"] for row in records)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--proposed-new-sandboxes", type=int, default=0)
    parser.add_argument("--proposed-lease-seconds", type=int, default=300)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal, default=Decimal("40"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite lane budget snapshot")
    result = audit(args.work_root, proposed_new_sandboxes=args.proposed_new_sandboxes,
                   proposed_lease_seconds=args.proposed_lease_seconds,
                   max_lane_reserved_usd=args.max_lane_reserved_usd)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("past_attempt_or_batch_count",
        "past_conservative_reserved_usd", "proposed_reserved_usd",
        "combined_reserved_usd", "lane_usd_cap", "within_cap")}, sort_keys=True))
    if not result["within_cap"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
