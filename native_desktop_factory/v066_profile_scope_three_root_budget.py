"""Read-only three-root budget plan for a future scoped-profile Desktop epoch.

The original 22 attempts, stopped amended two, and a prospective fresh 300
remain separate. This module never moves evidence, records a paid intent,
changes a scorer, or admits a final task. A future active bridge additionally
requires train calibration, new source freeze, and evaluator review.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from . import (qwen_v066_adapter, v066_profile_scope_analysis,
               v066_train_profile_cross_guest,
               v066_train_profile_cross_guest_audit)
from .v066_caret_full100_preflight import (
    OLD_INTENTS, _private, _read_only_storage, _read_private,
    _tree_digest, audit_retained_original,
)
from .v066_final_freeze import (
    LANE_CAP_USD, LEASE_SECONDS, MAX_SANDBOX_COUNT,
    digest, intent_budget,
)


FAILED_AMENDED_INTENTS = 2
FUTURE_FRESH_INTENTS = 300
TOTAL_PROSPECTIVE_INTENTS = OLD_INTENTS + FAILED_AMENDED_INTENTS + FUTURE_FRESH_INTENTS


def combined_budget(*, original_root: Path, failed_root: Path,
                    future_root: Path,
                    proposed_future_intents: int) -> dict:
    roots = [Path(original_root), Path(failed_root), Path(future_root)]
    if (any(root.name != "v066-final-gui" or root.is_symlink()
            for root in roots) or
            len({root.resolve() for root in roots}) != 3 or
            any(a.resolve().is_relative_to(b.resolve())
                for a in roots for b in roots if a != b) or
            (future_root.exists() and
             not _private(future_root, directory=True))):
        raise ValueError("Three private control roots are not isolated")
    old = intent_budget(original_root)["existing_intents"]
    failed = intent_budget(failed_root)["existing_intents"]
    future = intent_budget(future_root)["existing_intents"]
    if (old != OLD_INTENTS or failed != FAILED_AMENDED_INTENTS or
            future > FUTURE_FRESH_INTENTS or
            type(proposed_future_intents) is not int or
            not 0 <= proposed_future_intents <=
            FUTURE_FRESH_INTENTS - future):
        raise ValueError("Historical or future full-lease count changed")
    total = old + failed + future + proposed_future_intents
    reserve = Decimal(total * LEASE_SECONDS) / Decimal(3600)
    if total > MAX_SANDBOX_COUNT or reserve > LANE_CAP_USD:
        raise ValueError("Existing $60 full-lease cap exceeded")
    return {"historical_original_intents": old,
            "halted_amended_intents": failed,
            "future_intents_existing": future,
            "future_intents_proposed": proposed_future_intents,
            "combined_full_lease_intents": total,
            "combined_conservative_reserved_usd": str(reserve),
            "existing_lane_cap_usd": str(LANE_CAP_USD),
            "remaining_lease_intents_at_cap": MAX_SANDBOX_COUNT - total,
            "actual_provider_billed_usd": None}


def inspect(*, candidate_root: Path, original_root: Path,
            failed_root: Path, future_root: Path,
            old_run_journal: Path, old_ratification: Path,
            old_reservation: Path,
            failed_run_journal: Path,
            failed_ratification: Path,
            failed_reservation: Path,
            failed_private_stop: Path,
            failed_public_interruption: Path) -> tuple[dict, dict]:
    if future_root.exists() or future_root.is_symlink():
        raise ValueError("Prospective new full100 root must be unused")
    old = audit_retained_original(
        candidate_root=candidate_root, original_root=original_root,
        old_run_journal=old_run_journal,
        old_ratification=old_ratification,
        old_reservation=old_reservation)
    if (not _private(failed_root, directory=True) or
            failed_root.name != "v066-final-gui"):
        raise ValueError("Halted amended root missing or public")
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    final = {row["task_id"]: row for row in inventory["tasks"]
             if row.get("split") == "final_candidate"}
    if len(final) != 100 or digest(inventory_raw) != old[
            "candidate_inventory_sha256"]:
        raise ValueError("Three-root final source inventory changed")
    rat_sha = digest(failed_ratification.read_bytes())
    reservation_sha = digest(failed_reservation.read_bytes())
    adapter_sha = digest(Path(qwen_v066_adapter.__file__).read_bytes())
    runner_sha = digest(Path(__file__).with_name(
        "v066_final_control_attempt.py").read_bytes())
    receipt_bindings = []
    sandbox_ids = set()
    for path in sorted(failed_root.glob("*/*/receipt.json")):
        receipt, raw = _read_private(path)
        intent, intent_raw = _read_private(path.with_name("intent.json"))
        task_id = path.parent.parent.name
        sandbox_id = receipt.get("sandbox_id_sha256")
        if (task_id not in final or path.parent.name != "positive" or
                receipt.get("task_id") != task_id or
                intent.get("task_id") != task_id or
                intent.get("attempt") != "positive" or
                receipt.get("attempt") != "positive" or
                receipt.get("package_sha256") !=
                final[task_id]["package_sha256"] or
                intent.get("package_sha256") !=
                final[task_id]["package_sha256"] or
                intent.get("ratification_sha256") != rat_sha or
                intent.get("reservation_sha256") != reservation_sha or
                receipt.get("ratification_sha256") != rat_sha or
                receipt.get("lane_reservation_sha256") != reservation_sha or
                receipt.get("native_adapter_sha256") != adapter_sha or
                receipt.get("runner_sha256") != runner_sha or
                receipt.get("status") !=
                "control_failed_or_infrastructure_invalid" or
                receipt.get("stage") != "guest_content_attestation" or
                receipt.get("error_type") != "ValueError" or
                receipt.get("guest_content_attested") is not True or
                receipt.get("fresh_profile_absent") is not True or
                receipt.get("task_profile_attested") is not None or
                receipt.get("actor_steps") != [] or
                receipt.get("kill_returned") is not True or
                receipt.get("is_running_after_kill") is not False or
                receipt.get("official_hidden_final_model_attempts") != 0 or
                type(sandbox_id) is not str or len(sandbox_id) != 64 or
                sandbox_id in sandbox_ids):
            raise ValueError("Halted amended attempt source or cleanup changed")
        sandbox_ids.add(sandbox_id)
        receipt_bindings.append({"private_task_id": task_id,
                                 "intent_sha256": digest(intent_raw),
                                 "receipt_sha256": digest(raw),
                                 "sandbox_id_sha256": sandbox_id})
    if len(receipt_bindings) != FAILED_AMENDED_INTENTS:
        raise ValueError("Expected exactly two halted amended attempts")
    run, run_raw = _read_private(failed_run_journal)
    outcomes = Counter(row.get("status") for row in
                       run.get("task_outcomes", []))
    if (run.get("schema") !=
            "cua-native-wdi-v066-final-rerun-private-v1" or
            run.get("status") != "stopped_for_reconciliation" or
            run.get("ratification_sha256") != rat_sha or
            run.get("reservation_sha256") != reservation_sha or
            outcomes != Counter({
                "stopped_after_invalid_or_uncertain_attempt": 2,
                "stopped_before_next_create": 98}) or
            run.get("official_final_model_attempts") != 0 or
            run.get("official_final_admissions") != 0):
        raise ValueError("Halted amended run journal changed")
    stop, stop_raw = _read_private(failed_private_stop)
    public = json.loads(failed_public_interruption.read_bytes())
    if (public.get("schema") !=
            "cua-native-wdi-v066-caret-full100-interruption-public-v1" or
            public.get("private_stop_reconciliation_sha256") !=
            digest(stop_raw) or
            public.get("private_run_journal_sha256") != digest(run_raw) or
            stop.get("schema") !=
            "cua-native-wdi-v066-caret-full100-stop-private-v1" or
            stop.get("old_full_lease_intents") != OLD_INTENTS or
            stop.get("new_full_lease_intents") != FAILED_AMENDED_INTENTS or
            stop.get("run_journal_sha256") != digest(run_raw) or
            stop.get("original_attempt_tree_sha256") !=
            old["original_attempt_tree_sha256"] or
            stop.get("provider_active_sandboxes_after") != 0 or
            {row["receipt_sha256"] for row in stop.get("new_attempts", [])} !=
            {row["receipt_sha256"] for row in receipt_bindings}):
        raise ValueError("Public/private halted lineage changed")
    storage = _read_only_storage(failed_root)
    if (storage["verified_raw_evidence_rows"] != 0 or
            storage["reserved_evidence_bytes"] != 0):
        raise ValueError("Halted control raw evidence changed")
    failed_tree_sha, failed_tree_files = _tree_digest(failed_root)
    budget = combined_budget(
        original_root=original_root, failed_root=failed_root,
        future_root=future_root,
        proposed_future_intents=FUTURE_FRESH_INTENTS)
    private = {
        "schema": "cua-native-wdi-v066-three-root-budget-plan-private-v1",
        "status": "future_profile_scope_epoch_not_ratified",
        "candidate_inventory_sha256": digest(inventory_raw),
        "old_evidence": old,
        "halted_amended_attempt_bindings": receipt_bindings,
        "halted_amended_run_journal_sha256": digest(run_raw),
        "halted_amended_stop_sha256": digest(stop_raw),
        "halted_amended_tree_sha256": failed_tree_sha,
        "halted_amended_tree_files": failed_tree_files,
        "halted_amended_storage": storage,
        "scoped_analysis_source_sha256": digest(
            Path(v066_profile_scope_analysis.__file__).read_bytes()),
        "train_calibration_source_sha256": digest(
            Path(v066_train_profile_cross_guest.__file__).read_bytes()),
        "train_calibration_audit_source_sha256": digest(
            Path(v066_train_profile_cross_guest_audit.__file__).read_bytes()),
        "budget": budget,
        "active_paid_bridge_recorded": False,
        "official_final_admissions": 0,
    }
    aggregate = {
        "schema": "cua-native-wdi-v066-three-root-budget-plan-public-v1",
        "status": private["status"],
        "candidate_inventory_sha256": private["candidate_inventory_sha256"],
        "old_attempt_tree_sha256": old["original_attempt_tree_sha256"],
        "halted_amended_tree_sha256": failed_tree_sha,
        "halted_amended_run_journal_sha256": digest(run_raw),
        "halted_amended_stop_sha256": digest(stop_raw),
        "historical_original_intents": OLD_INTENTS,
        "halted_amended_intents": FAILED_AMENDED_INTENTS,
        "future_fresh_full100_intents_planned": FUTURE_FRESH_INTENTS,
        "combined_full_lease_intents": budget[
            "combined_full_lease_intents"],
        "combined_conservative_reserved_usd": budget[
            "combined_conservative_reserved_usd"],
        "existing_lane_cap_usd": budget["existing_lane_cap_usd"],
        "active_paid_bridge_recorded": False,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, aggregate
