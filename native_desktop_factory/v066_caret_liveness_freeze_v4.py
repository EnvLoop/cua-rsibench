"""Freeze a prospective Desktop caret-liveness source epoch before any retry.

This records one-use eligibility and an exact source binding; it does not
dispatch a sandbox or authorize a model result.  A separately audited fresh
positive/near-miss/cold-reset trio remains required for the failed logical ID.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .v066_caret_liveness_audit_v4 import _write_new


V4_SOURCE = (
    "native_desktop_factory/qwen_v066_adapter_v4.py",
    "native_desktop_factory/v066_caret_liveness_audit_v4.py",
    "native_desktop_factory/v066_caret_liveness_freeze_v4.py",
    "tests/test_native_desktop_v066_caret_liveness_v4.py",
)


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def build(*, repo: Path, old_runtime_freeze: Path,
          private_audit: Path, public_audit: Path) -> tuple[dict, dict]:
    old_raw = old_runtime_freeze.read_bytes()
    old = json.loads(old_raw)
    source = old.get("source_sha256s")
    if (old.get("schema") !=
            "cua-native-wdi-v066-day-rollover-runtime-freeze-v1" or
            type(source) is not dict or len(source) != 35 or
            old.get("official_final_admissions") != 0):
        raise ValueError("Historical 35-source Desktop freeze changed")
    for name, expected in source.items():
        candidate = repo / name
        path = candidate.resolve()
        if not path.is_relative_to(repo.resolve()) or candidate.is_symlink():
            raise ValueError("Historical source escaped repository")
        if _digest(path.read_bytes()) != expected:
            raise ValueError("Historical Desktop source changed after freeze")
    audit_raw = private_audit.read_bytes()
    audit = json.loads(audit_raw)
    public_raw = public_audit.read_bytes()
    public = json.loads(public_raw)
    if (audit.get("schema") !=
            "cua-native-wdi-v066-caret-liveness-private-audit-v4" or
            audit.get("status") !=
            "counterfactual_frame_guard_only_no_control_admission" or
            audit.get("at_most_one_fresh_full_trio_retry_eligible") is not True or
            audit.get("retry_dispatch_authorized") is not False or
            audit.get("official_final_admissions") != 0 or
            public.get("schema") !=
            "cua-native-wdi-v066-caret-liveness-public-audit-v4" or
            public.get("private_audit_sha256") != _digest(audit_raw) or
            public.get("official_final_admissions") != 0):
        raise ValueError("Pre-result liveness audit changed")
    new = {name: _digest((repo / name).read_bytes()) for name in V4_SOURCE}
    if (public.get("v4_adapter_sha256") != new[V4_SOURCE[0]] or
            public.get("v4_audit_source_sha256") != new[V4_SOURCE[1]]):
        raise ValueError("Public audit no longer binds v4 source")
    private = {
        "schema": "cua-native-wdi-v066-caret-liveness-source-freeze-private-v4",
        "status": "frozen_pre_result_no_dispatch_authority",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "historical_35_source_freeze_sha256": _digest(old_raw),
        "historical_35_sources_reopened": len(source),
        "v4_source_sha256s": new,
        "private_audit_sha256": _digest(audit_raw),
        "public_audit_sha256": _digest(public_raw),
        "old_batch_run_receipt_sha256": audit[
            "old_batch_run_receipt_sha256"],
        "old_failed_receipt_sha256": audit["old_failed_receipt_sha256"],
        "eligible_private_task_id": audit["private_task_id"],
        "maximum_fresh_full_trio_retries_for_this_failed_id": 1,
        "old_positive_and_partial_near_miss_retained": True,
        "requires_new_v4_controller_and_independent_saved_state_audit": True,
        "requires_new_six_cell_ratification_before_campaign": True,
        "same_id_retry_dispatch_authorized": False,
        "new_e2b_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public_freeze = {
        "schema": "cua-native-wdi-v066-caret-liveness-source-freeze-public-v4",
        "status": private["status"],
        "historical_35_source_freeze_sha256": _digest(old_raw),
        "historical_35_sources_reopened": len(source),
        "v4_source_sha256s": new,
        "public_audit_sha256": _digest(public_raw),
        "eligible_failed_logical_id_count": 1,
        "maximum_fresh_full_trio_retries_per_failed_id": 1,
        "old_positive_and_partial_near_miss_retained": True,
        "requires_new_v4_controller_and_independent_saved_state_audit": True,
        "requires_new_six_cell_ratification_before_campaign": True,
        "same_id_retry_dispatch_authorized": False,
        "new_e2b_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public_freeze


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "old-runtime-freeze", "private-audit",
                 "public-audit", "private-out", "public-out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Exclusive v4 source-freeze paths required")
    private, public = build(
        repo=args.repo, old_runtime_freeze=args.old_runtime_freeze,
        private_audit=args.private_audit, public_audit=args.public_audit)
    public["private_freeze_sha256"] = _write_new(
        args.private_out, private, private=True)
    _write_new(args.public_out, public, private=False)
    print(json.dumps({key: public[key] for key in (
        "status", "eligible_failed_logical_id_count",
        "same_id_retry_dispatch_authorized", "official_final_admissions")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
