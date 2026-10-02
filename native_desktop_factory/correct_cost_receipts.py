"""Publish a field-limited correction to two under-reserved E2B GUI batches."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


OFFICIAL_PRICING_URL = "https://e2b.dev/pricing"
PUBLISHED_8CPU_8GIB_USD_PER_SECOND = 0.000112 + 0.000036


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def correct(batch_paths: list[Path], resource_receipt: Path) -> dict:
    if len(batch_paths) != 2:
        raise ValueError("Expected the exact two original normalization batches")
    resource_raw = resource_receipt.read_bytes()
    probe = json.loads(resource_raw)["resource_probe"]
    if probe["vcpu_visible"] != 8 or not 7 * 1024 * 1024 < probe["memory_kib_visible"] <= 8 * 1024 * 1024:
        raise ValueError("Observed desktop resource class differs from 8 vCPU / approximately 8 GiB")
    rows = []
    for path in batch_paths:
        raw = path.read_bytes()
        value = json.loads(raw)
        if value["schema"] != "cua-native-impress-batch-normalization-v1" or value["status"] != "finished":
            raise ValueError("Batch was not verified finished")
        if value["usd_per_hour_upper"] != 0.35 or value["is_running_after_kill"] is not False:
            raise ValueError("Not an affected 0.35 USD/hour batch or cleanup unverified")
        rows.append({
            "batch_receipt_sha256": digest(raw),
            "neutral_save_attempt_count": len(value["items"]),
            "adopted_count": len(value.get("adopted_task_ids", [])),
            "server_lease_seconds": value["lease_seconds"],
            "observed_client_elapsed_seconds": value["elapsed_seconds"],
            "prior_assumed_usd_per_hour": 0.35,
            "prior_reserved_usd": value["reserved_usd_upper"],
            "prior_usd_reservation_valid_upper_bound": False,
            "corrected_conservative_reserve_at_1_usd_per_hour":
                round(value["lease_seconds"] / 3600, 6),
        })
    return {"schema": "cua-native-desktop-e2b-cost-correction-v1",
            "checked_date": "2026-09-25", "official_pricing_url": OFFICIAL_PRICING_URL,
            "measured_resource_probe_receipt_sha256": digest(resource_raw),
            "measured_resource_class": probe,
            "published_8cpu_8gib_cpu_usd_per_second": 0.000112,
            "published_8cpu_8gib_ram_usd_per_second": 0.000036,
            "published_marginal_compute_usd_per_hour":
                round(PUBLISHED_8CPU_8GIB_USD_PER_SECOND * 3600, 6),
            "future_reservation_usd_per_hour": 1.0,
            "affected_batches": rows,
            "actual_billed_usd": None,
            "billing_note": "The available E2B SDK/control receipts provide runtime and resource observations, not a per-batch invoice. Actual provider billing and any plan fees, credits, or discounts are unknown and must be reconciled separately.",
            "status": "prior_usd_planning_bounds_invalid_runtime_leases_verified",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-receipt", type=Path, action="append", required=True)
    parser.add_argument("--resource-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = correct(args.batch_receipt, args.resource_receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "published_marginal_usd_per_hour": result["published_marginal_compute_usd_per_hour"],
                      "actual_billed_usd": result["actual_billed_usd"]}, sort_keys=True))


if __name__ == "__main__":
    main()
