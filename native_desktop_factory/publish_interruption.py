"""Aggregate-only evidence for interrupted pre-action E2B ConnectErrors."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def summarize(run_dir: Path, reconciliation: Path, health_probe: Path,
              recovery: Path, admission_snapshot: Path, attempts_root: Path) -> dict:
    journal_raw = (run_dir / "run-receipt.json").read_bytes()
    recon_raw, health_raw, recovery_raw = (reconciliation.read_bytes(),
                                           health_probe.read_bytes(), recovery.read_bytes())
    journal, recon, health, archive = (json.loads(journal_raw), json.loads(recon_raw),
                                       json.loads(health_raw), json.loads(recovery_raw))
    before = json.loads(admission_snapshot.read_bytes())
    if recon["run_journal_sha256"] != digest(journal_raw) or recon["ready_for_separate_health_probe"] is not True:
        raise ValueError("Interrupted journal/reconciliation not bound")
    if health.get("status") != "healthy_and_terminated" or health.get("reconciliation_sha256") != digest(recon_raw):
        raise ValueError("Separate health probe did not bind reconciliation")
    if archive.get("status") != "archived_ready_for_one_controlled_retry_each" or archive.get("health_probe_sha256") != digest(health_raw):
        raise ValueError("Controlled recovery ledger not bound")
    if len(archive["attempts"]) != recon["error_type_counts"].get("ConnectError"):
        raise ValueError("Not every ConnectError was archived")
    for row in archive["attempts"]:
        path = attempts_root / row["archive_relative"] / "receipt.json"
        if digest(path.read_bytes()) != row["original_receipt_sha256"]:
            raise ValueError("Archived infrastructure receipt missing or changed")
    if (before["qualified_final_count"], before["missing_receipt_count"], before["invalid_receipt_count"]) != (12, 88, 0):
        raise ValueError("Admission snapshot after archive differs")
    return {
        "schema": "cua-native-wdi-e2b-interruption-public-audit-v1",
        "checked_date": "2026-09-25",
        "interrupted_run_journal_sha256": digest(journal_raw),
        "reconciliation_sha256": digest(recon_raw),
        "separate_health_probe_sha256": digest(health_raw),
        "controlled_recovery_ledger_sha256": digest(recovery_raw),
        "post_archive_admission_snapshot_sha256": digest(admission_snapshot.read_bytes()),
        "new_attempt_count_at_interrupt": recon["new_attempt_count"],
        "pre_or_early_sandbox_connect_error_count": recon["error_type_counts"]["ConnectError"],
        "create_attempts_without_sandbox_id_count": recon["attempts_without_sandbox_id_count"],
        "known_id_cleanup_inconclusive_count": recon["known_id_cleanup_inconclusive_count"],
        "known_active_sandbox_matches_after_lease_and_grace": recon["known_active_matching_count"],
        "server_lease_plus_grace_elapsed_before_retry": recon["all_unknown_leases_elapsed"],
        "archived_infrastructure_invalid_attempt_count": len(archive["attempts"]),
        "separate_health_probe_status": health["status"],
        "health_probe_provider_template_id": health["provider_sandbox_info"]["template_id"],
        "health_probe_provider_vcpu": health["provider_sandbox_info"]["vcpu"],
        "health_probe_provider_memory_mb": health["provider_sandbox_info"]["memory_mb"],
        "gui_control_passed_count_at_archive": before["qualified_final_count"],
        "gui_control_missing_count_at_archive": before["missing_receipt_count"],
        "gui_control_invalid_count_at_archive": before["invalid_receipt_count"],
        "interrupted_run_original_planned_usd_ceiling": journal["caps"]["max_estimated_usd"],
        "interrupted_run_conservative_started_lease_reserve_usd":
            recon["conservative_attempted_lease_reserve_usd"],
        "provider_actual_billed_usd": None,
        "classification": "infrastructure_invalid_not_model_failure",
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
        "note": "The provider did not expose a per-batch invoice through these SDK receipts. One controlled retry per archived pre-action error is permitted only after the bound health probe; original failed evidence remains preserved.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--health-probe", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--admission-snapshot", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite public interruption audit")
    result = summarize(args.run_dir, args.reconciliation, args.health_probe,
                       args.recovery, args.admission_snapshot, args.attempts_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["classification"],
                      "archived_invalid_attempts": result["archived_infrastructure_invalid_attempt_count"],
                      "health": result["separate_health_probe_status"],
                      "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
