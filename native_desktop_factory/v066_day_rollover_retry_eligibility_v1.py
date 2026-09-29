"""Pre-result, evaluator-only eligibility record for two fresh-clone retries.

This records a conditional rule before any retry create. It never dispatches a
sandbox, replays an old lease, or authorizes a model/final-task result. A new
sidecar root, source freeze, and independent cross-root audit are still needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .reconcile_interrupted_sweep import active_hashes
from .v066_day_rollover_continuation_v2 import (
    _reconciliation, validate_live,
)
from .v066_final_freeze import digest


def _write_new(path: Path, value: dict, *, private: bool) -> str:
    rendered = (json.dumps(value, sort_keys=True, separators=(",", ":"))
                if private else json.dumps(value, indent=2, sort_keys=True))
    raw = (rendered + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True,
                      mode=0o700 if private else 0o755)
    if private:
        path.parent.chmod(0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600 if private else 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def build(*, continuation_freeze: Path) -> tuple[dict, dict]:
    frozen, status, paths, rows = validate_live(freeze_path=continuation_freeze)
    _intent, reconciliation = _reconciliation(
        paths, [row["task_id"] for row in rows])
    if (status["independently_accepted_complete_trios"] != 7 or
            status["quarantined_incomplete_task_ids"] != 2 or
            status["untouched_task_ids"] != 91 or
            reconciliation["provider_active_after_count"] != 0):
        raise ValueError("Fresh-clone eligibility is not pre-result 7/2/91")
    root = paths["attempts_root"]
    first = json.loads((root / rows[7]["task_id"] /
                        "near-miss/receipt.json").read_bytes())
    second = json.loads((root / rows[8]["task_id"] /
                         "positive/receipt.json").read_bytes())
    if (first.get("status") != "started" or
            second.get("status") != "started" or
            first.get("is_running_after_kill") is not None or
            second.get("is_running_after_kill") is not None or
            first.get("saved_artifact") is not None or
            first.get("fair_verifier") is not None or
            not second.get("saved_artifact") or
            second.get("fair_verifier", {}).get("passed") is not True or
            first.get("official_hidden_final_model_attempts") != 0 or
            second.get("official_hidden_final_model_attempts") != 0 or
            any(path.stat().st_mode & 0o077 for path in (
                root / rows[7]["task_id"] / "near-miss/receipt.json",
                root / rows[8]["task_id"] / "positive/receipt.json"))):
        raise ValueError("Two interrupted first attempts are not evaluator-only")
    private = {
        "schema": "cua-native-wdi-v066-fresh-clone-retry-eligibility-private-v1",
        "status": "conditional_pre_result_evaluator_only_not_dispatch_authority",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "continuation_freeze_sha256": digest(continuation_freeze.read_bytes()),
        "same_logical_task_ids_private": [rows[7]["task_id"],
                                          rows[8]["task_id"]],
        "first_attempt_receipt_sha256s": [
            digest((root / rows[7]["task_id"] /
                    "near-miss/receipt.json").read_bytes()),
            digest((root / rows[8]["task_id"] /
                    "positive/receipt.json").read_bytes())],
        "first_attempts_retained_and_charged": 2,
        "partial_near_miss_saved_artifact_absent": True,
        "scripted_positive_saved_verdict_observed_private": True,
        "model_or_researcher_result_observed": False,
        "provider_active_after_reconciliation": 0,
        "one_fresh_full_trio_per_quarantined_id_proposed": True,
        "additional_full_lease_intents_proposed": 6,
        "projected_all_root_full_lease_intents_if_separately_authorized": 329,
        "projected_reserved_usd_if_separately_authorized":
            "54.83333333333333333333333333",
        "requires_new_sidecar_bridge_and_source_freeze": True,
        "same_id_retry_dispatch_authorized": False,
        "automatic_replay_authorized": False,
        "new_e2b_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-fresh-clone-retry-eligibility-public-v1",
        "status": private["status"],
        "quarantined_logical_task_count": 2,
        "first_attempts_retained_and_charged": 2,
        "partial_near_miss_saved_artifact_absent": True,
        "scripted_positive_saved_verdict_observed_evaluator_private": True,
        "model_or_researcher_result_observed": False,
        "one_fresh_full_trio_per_id_proposed": True,
        "additional_full_lease_intents_proposed": 6,
        "projected_all_root_full_lease_intents_if_separately_authorized": 329,
        "projected_reserved_usd_if_separately_authorized":
            private["projected_reserved_usd_if_separately_authorized"],
        "requires_new_sidecar_bridge_and_source_freeze": True,
        "same_id_retry_dispatch_authorized": False,
        "automatic_replay_authorized": False,
        "new_paid_guest_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public


def write(*, continuation_freeze: Path,
          private_out: Path, public_out: Path) -> dict:
    if private_out.exists() or public_out.exists():
        raise ValueError("Exclusive retry eligibility paths required")
    private, public = build(continuation_freeze=continuation_freeze)
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider must be active-zero for retry eligibility freeze")
    public["eligibility_source_sha256"] = digest(Path(__file__).read_bytes())
    public["continuation_freeze_sha256"] = private[
        "continuation_freeze_sha256"]
    public["private_eligibility_sha256"] = _write_new(
        private_out, private, private=True)
    _write_new(public_out, public, private=False)
    return public
