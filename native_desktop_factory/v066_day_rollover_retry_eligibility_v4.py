"""Freeze one-use, full-trio retry eligibility for three retained partial IDs.

This record is separate from the 89 untouched-ID controller.  It neither
creates a sidecar guest nor grants paid dispatch; any retry needs a new isolated
root, complete positive/near-miss/reset intents, and independent readback.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from . import v066_day_rollover_continuation_v3 as v3
from . import v066_day_rollover_continuation_v4 as v4
from .v066_final_freeze import digest


def build(*, v4_freeze: Path, original_retry: Path) -> tuple[dict, dict]:
    frozen, progress, paths, rows = v4.validate_live(freeze=v4_freeze)
    old_raw = v4._private(original_retry)
    old = json.loads(old_raw)
    caret = json.loads(v4._private(Path(frozen["caret_freeze_path"])))
    previous = old.get("same_logical_task_ids_private", [])
    eligible = previous + [caret.get("eligible_private_task_id")]
    if (old.get("schema") !=
            "cua-native-wdi-v066-fresh-clone-retry-eligibility-private-v1" or
            old.get("status") !=
            "conditional_pre_result_evaluator_only_not_dispatch_authority" or
            old.get("same_id_retry_dispatch_authorized") is not False or
            old.get("one_fresh_full_trio_per_quarantined_id_proposed") is not True or
            len(previous) != 2 or
            eligible != [rows[index]["task_id"] for index in (7, 8, 10)] or
            len(set(eligible)) != 3 or
            progress["original_quarantined_task_count"] != 2 or
            progress["new_stopped_v3_partial_task_count"] != 1 or
            progress["official_final_admissions"] != 0):
        raise ValueError("Three one-use retry identities or old eligibility changed")
    root = paths["attempts_root"]
    if (set(path.name for path in (root / eligible[0]).iterdir()) !=
            {"positive", "near-miss"} or
            set(path.name for path in (root / eligible[1]).iterdir()) !=
            {"positive"} or
            set(path.name for path in (root / eligible[2]).iterdir()) !=
            {"positive", "near-miss"}):
        raise ValueError("A retained partial ID gained an attempt unexpectedly")
    if progress["v4_new_complete_trios"] != 0:
        raise ValueError("Retry eligibility must freeze before first v4 create")
    projected_total = frozen["projected_four_root_full_lease_intents"] + 9
    if projected_total != 331 or projected_total > 360:
        raise ValueError("One-use retries exceed full-lease reservation ceiling")
    private = {
        "schema": "cua-native-wdi-v066-three-partial-retry-eligibility-private-v4",
        "status": "one_use_full_trio_eligibility_no_dispatch_authority",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "v4_untouched_freeze_sha256": digest(v4._private(v4_freeze)),
        "old_two_partial_eligibility_sha256": digest(old_raw),
        "new_caret_partial_freeze_sha256":
            digest(v4._private(Path(frozen["caret_freeze_path"]))),
        "eligible_private_task_ids": eligible,
        "retained_first_eleven_task_tree_sha256s":
            frozen["first_eleven_task_tree_sha256s"],
        "historical_attempts_retained_and_charged": True,
        "maximum_new_full_trios_per_eligible_id": 1,
        "required_fresh_attempts_per_trio": list(v3.ATTEMPTS),
        "additional_full_lease_intents_if_separately_authorized": 9,
        "projected_all_root_full_lease_intents_if_all_89_and_three_retried":
            projected_total,
        "projected_reserved_usd_upper_if_separately_authorized":
            str(Decimal(projected_total) / Decimal(6)),
        "separate_sidecar_root_and_source_freeze_required": True,
        "independent_saved_state_and_reset_audit_required": True,
        "same_id_retry_dispatch_authorized": False,
        "new_e2b_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-three-partial-retry-eligibility-public-v4",
        "status": private["status"],
        "eligible_partial_logical_task_count": 3,
        "original_quarantined_task_count": 2,
        "new_stopped_v3_partial_task_count": 1,
        "historical_attempts_retained_and_charged": True,
        "maximum_new_full_trios_per_eligible_id": 1,
        "required_fresh_attempts_per_trio": list(v3.ATTEMPTS),
        "additional_full_lease_intents_if_separately_authorized": 9,
        "projected_all_root_full_lease_intents_if_all_89_and_three_retried":
            projected_total,
        "projected_reserved_usd_upper_if_separately_authorized":
            private["projected_reserved_usd_upper_if_separately_authorized"],
        "separate_sidecar_root_and_source_freeze_required": True,
        "independent_saved_state_and_reset_audit_required": True,
        "same_id_retry_dispatch_authorized": False,
        "new_e2b_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public


def write(*, v4_freeze: Path, original_retry: Path,
          private_out: Path, public_out: Path) -> dict:
    if private_out.exists() or public_out.exists():
        raise ValueError("Exclusive one-use retry eligibility paths required")
    private, public = build(v4_freeze=v4_freeze,
                            original_retry=original_retry)
    public["eligibility_source_sha256"] = digest(Path(__file__).read_bytes())
    public["private_eligibility_sha256"] = v3._write_new(private_out, private)
    v3._write_new(public_out, public, public=True)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("v4-freeze", "original-retry", "private-out", "public-out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = write(v4_freeze=args.v4_freeze,
                   original_retry=args.original_retry,
                   private_out=args.private_out,
                   public_out=args.public_out)
    print(json.dumps({key: result[key] for key in (
        "status", "eligible_partial_logical_task_count",
        "same_id_retry_dispatch_authorized", "official_final_admissions")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
