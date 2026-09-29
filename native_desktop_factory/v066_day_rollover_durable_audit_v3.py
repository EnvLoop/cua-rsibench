"""Read-only audit of additive Desktop v3 precreate durability evidence.

The existing independent attrition auditor separately reopens all GUI frames,
saved artifacts, near misses, and fresh resets. This auditor verifies each
newly accepted attempt's precreate budget/intent/child source binding.
"""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

from .v066_final_freeze import LEASE_SECONDS, digest


ATTEMPTS = ("positive", "near-miss", "cold-reset")


def audit(*, attempts_root: Path, roster: list[dict],
          initial_accepted: int, prior_intents: int,
          wrapper_sha: str) -> dict:
    if (len(roster) != 100 or not 7 <= initial_accepted <= 98 or
            prior_intents != 24 or len(wrapper_sha) != 64):
        raise ValueError("Desktop v3 durability audit denominator changed")
    checked = 0
    for index in range(9, 9 + initial_accepted - 7):
        task_id = roster[index]["task_id"]
        for offset, attempt in enumerate(ATTEMPTS):
            root = attempts_root / task_id / attempt
            budget_path = root / "budget.json"
            intent_path = root / "intent.json"
            receipt_path = root / "receipt.json"
            if any(not path.is_file() or path.is_symlink() or
                   path.stat().st_mode & 0o077
                   for path in (budget_path, intent_path, receipt_path)):
                raise ValueError("Durable private attempt evidence missing")
            budget_raw = budget_path.read_bytes()
            budget = json.loads(budget_raw)
            intent = json.loads(intent_path.read_bytes())
            receipt = json.loads(receipt_path.read_bytes())
            expected_all_roots = 51 + 3 * (index - 9) + offset
            expected_fresh_root = 25 + 3 * (index - 9) + offset
            try:
                reserved = Decimal(budget["four_root_budget"][
                    "combined_conservative_reserved_usd"])
            except (KeyError, ValueError, TypeError):
                raise ValueError("Precreate four-root reserved cost missing") from None
            if (budget.get("schema") !=
                    "cua-native-wdi-v066-precreate-budget-private-v3" or
                    budget.get("status") != "fsynced_before_provider_create" or
                    budget.get("task_id") != task_id or
                    budget.get("attempt") != attempt or
                    budget.get("provider_active_before_intent") != 0 or
                    budget.get("storage_dispatch_ready") is not True or
                    budget.get("credential_present") is not True or
                    budget.get("sdk_versions") != {
                        "e2b-desktop": "2.2.0", "e2b": "2.51.0",
                        "Pillow": "11.3.0"} or
                    budget.get("four_root_budget", {}).get(
                        "combined_full_lease_intents") != expected_all_roots or
                    reserved != Decimal(expected_all_roots) / Decimal(6) or
                    budget.get("fresh_lane_budget", {}).get(
                        "combined_intents") != expected_fresh_root or
                    budget.get("power", {}).get("source") not in
                        ("AC Power", "Battery Power") or
                    not budget.get("power", {}).get("observed_utc") or
                    intent.get("schema") !=
                        "cua-native-wdi-v066-final-control-intent-v1" or
                    intent.get("task_id") != task_id or
                    intent.get("attempt") != attempt or
                    intent.get("lease_seconds") != LEASE_SECONDS or
                    intent.get("precreate_budget_sha256") != digest(budget_raw) or
                    intent.get("durable_child_wrapper_sha256") != wrapper_sha or
                    receipt.get("task_id") != task_id or
                    receipt.get("attempt") != attempt or
                    receipt.get("status") != (
                        "cold_reset_observed" if attempt == "cold-reset"
                        else "control_passed")):
                raise ValueError("v3 precreate budget, intent, or receipt changed")
            checked += 1
    return {"schema": "cua-native-wdi-v066-durable-continuation-audit-v3",
            "new_complete_trios": initial_accepted - 7,
            "new_durable_attempts_reopened": checked,
            "quarantined_original_task_ids_retained": 2,
            "official_final_admissions": 0}
