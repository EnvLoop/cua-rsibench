"""Five-root Desktop lease accounting for a fresh v4e evaluator root.

The stopped v4c intent remains charged in the immutable four-root ledger.
This module never calls E2B. It rejects a reused or nested fifth root and
counts every fsynced intent as a full 600-second lease, including failures.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from .v066_day_rollover_bridge import combined_budget as four_root_budget
from .v066_final_freeze import (LANE_CAP_USD, LEASE_SECONDS,
                                MAX_SANDBOX_COUNT, intent_budget)


def five_root_budget(*, original_root: Path, failed_root: Path,
                     failed_scoped_root: Path, date_amended_root: Path,
                     new_root: Path, proposed_new_intents: int = 0) -> dict:
    old = four_root_budget(
        original_root=original_root, failed_root=failed_root,
        failed_scoped_root=failed_scoped_root, fresh_root=date_amended_root,
        proposed_fresh_intents=0)
    roots = (original_root, failed_root, failed_scoped_root,
             date_amended_root, new_root)
    resolved = [root.resolve() for root in roots]
    if (old["historical_counts"] != [22, 2, 2] or
            old["fresh_existing_intents"] != 30 or
            old["combined_full_lease_intents"] != 56 or
            len(set(resolved)) != 5 or new_root.is_symlink() or
            any(a.is_relative_to(b) for a in resolved for b in resolved
                if a != b) or
            (new_root.exists() and
             (not new_root.is_dir() or new_root.stat().st_mode & 0o077)) or
            type(proposed_new_intents) is not int or
            not 0 <= proposed_new_intents <= 267):
        raise ValueError("Five-root historical lease ledger or isolation changed")
    new_count = intent_budget(new_root)["existing_intents"]
    if new_count > 267 or new_count + proposed_new_intents > 267:
        raise ValueError("Fresh v4e root exceeds 88 trios plus one clone")
    total = 56 + new_count + proposed_new_intents
    reserved = Decimal(total * LEASE_SECONDS) / Decimal(3600)
    if total > MAX_SANDBOX_COUNT or reserved > LANE_CAP_USD:
        raise ValueError("Five-root full-lease reservation exceeds lane cap")
    return {
        "schema": "cua-native-wdi-v066-five-root-lease-budget-v4e",
        "historical_four_root_intents": 56,
        "new_root_existing_intents": new_count,
        "new_root_proposed_intents": proposed_new_intents,
        "combined_full_lease_intents": total,
        "combined_conservative_reserved_usd": str(reserved),
        "lane_cap_usd": str(LANE_CAP_USD),
        "actual_provider_billed_usd": None,
    }
