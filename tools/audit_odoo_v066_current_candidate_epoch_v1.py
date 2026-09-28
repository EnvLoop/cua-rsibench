"""Independent read-only audit of Odoo current-candidate evaluator plans.

The audit reopens split-private rosters and the historical plans. It cannot
turn a source epoch into a GUI result, official admission, or campaign gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import propose_odoo_v066_candidate_control_adoption_v1 as proposal
from tools import odoo_v066_current_candidate_epoch_v1 as epoch


AUDIT_SCHEMA = "envloop-odoo-v066-current-candidate-evaluator-plan-audit-v1"


class EpochAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise EpochAuditError(code)


def audit(*, split: str, worker_dir: Path, private_path: Path,
          public_path: Path, old_private_path: Path,
          old_public_path: Path,
          allow_current_run: bool = False) -> dict:
    require(split in ("selection", "official_hidden") and
            worker_dir.name == split, "epoch_audit_split_invalid")
    adoption = proposal.inspect()
    published_adoption = protocol.public_json(epoch.ADOPTION_PUBLIC)
    require(adoption == published_adoption,
            "epoch_audit_adoption_proposal_changed")
    freeze, freeze_sha = protocol.validate_source_freeze(epoch.SOURCE_FREEZE)
    require(freeze_sha == adoption["odoo_validator_source_freeze_sha256"],
            "epoch_audit_source_freeze_changed")
    old = protocol.validate_split_plan(
        split=split, private_path=old_private_path,
        public_path=old_public_path, source_freeze_path=epoch.SOURCE_FREEZE)
    old_public = protocol.public_json(old_public_path)
    historical = adoption["historical_split_plans"][split]
    require(epoch.digest(old_private_path) == historical["private_sha256"] and
            epoch.digest(old_public_path) == historical["public_sha256"] and
            old["ratification_sha256"] ==
            historical["historical_ratification_sha256"],
            "epoch_audit_historical_plan_changed")
    private = protocol.private_json(private_path)
    public = protocol.public_json(public_path)
    nonce = private.get("run_nonce_hex")
    require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{32}", nonce) is not None and
            private_path.parent.resolve() ==
            (protocol._worker_split(worker_dir, split) /
             "v066_current_candidate_epoch").resolve() and
            private_path.name == f"{split}-20260929.private.json" and
            public_path.parent.resolve() == proposal.EVIDENCE.resolve() and
            epoch.digest(private_path) == public.get("private_plan_sha256") and
            public.get("run_nonce_sha256") ==
            protocol.digest(bytes.fromhex(nonce)),
            "epoch_audit_private_public_nonce_unbound")
    expected_source = {relative: freeze["source_sha256s"][relative]
                       for relative in epoch.REQUIRED_SOURCE}
    expected_gate = {
        "schema": epoch.GATE_SCHEMA,
        "status": "required_not_run",
        "worker_split": split,
        "no_gui_actions": True,
        "current_sql_snapshot_exact_frozen_baseline_required": True,
        "full_physical_filestore_manifest_exact_frozen_baseline_required": True,
        "original_worker_exclusive_lease_required": True,
        "stopped_service_state_before_and_after_required": True,
        "all_three_retained_failures_reaudited_before_selection_gate":
            split == "selection",
        "live_gate_receipt_sha256": None,
    }
    shared = {
        "status": epoch.STATUS,
        "as_of_date": epoch.DATE,
        "split": split,
        "cell": "odoo-community",
        "current_candidate_adoption_sha256": epoch.digest(epoch.ADOPTION_PUBLIC),
        "current_candidate_private_sha256":
            adoption["current_six_cell_candidate_private_sha256"],
        "current_candidate_public_sha256":
            adoption["current_six_cell_candidate_public_sha256"],
        "historical_ratification_sha256": old["ratification_sha256"],
        "historical_private_plan_sha256": epoch.digest(old_private_path),
        "historical_public_plan_sha256": epoch.digest(old_public_path),
        "source_freeze_sha256": freeze_sha,
        "required_actor_validator_pinned_border_source_sha256s":
            expected_source,
        "retained_terminal_failure_public_sha256s":
            adoption["retained_terminal_failure_public_sha256s"],
        "no_gui_current_baseline_gate": expected_gate,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    require(private.get("schema") == epoch.PRIVATE_SCHEMA and
            public.get("schema") == epoch.PUBLIC_SCHEMA and
            all(private.get(k) == v and public.get(k) == v
                for k, v in shared.items()) and
            private.get("source_sha256s") == freeze["source_sha256s"] and
            private.get("fresh_run_directory_name") ==
            f"current-candidate-{nonce}" and
            private.get("task_count") == old["task_count"] and
            private.get("world_case_count") == old["world_case_count"] and
            private.get("checkpoint") == old["checkpoint"] and
            private.get("task_set_manifest_sha256") ==
            old["task_set_manifest_sha256"] and
            private.get("physical_dispatch_profile") ==
            freeze["physical_dispatch_profile"] and
            private.get("validator_amendment") ==
            freeze["validator_amendment"] and
            private.get("tasks") == old["tasks"] and
            public.get("candidate_count") == old["task_count"] and
            public.get("family_candidate_counts") ==
            old_public["family_candidate_counts"] and
            public.get("fresh_current_profile_gui_controls") == 0 and
            public.get("researcher_campaigns") == 0,
            "epoch_audit_plan_fields_or_task_roster_changed")
    epoch._validate_task_assets(worker_dir, old)
    epoch._fresh_nonce(worker_dir, nonce,
                       allow_current_run=allow_current_run)
    require(public.get("historical_ratification_sha256") !=
            public.get("current_candidate_private_sha256") and
            public["retained_terminal_failure_public_sha256s"] ==
            {label: epoch.digest(proposal.EVIDENCE / name)
             for label, name, _ in proposal.FAILURES},
            "epoch_audit_historical_boundary_or_failures_changed")
    # A public receipt must be a strict field-limited projection, with no
    # task IDs, instructions, gold, credentials, or private run nonce.
    allowed_public = {
        "schema", "status", "as_of_date", "split", "cell",
        "private_plan_sha256", "run_nonce_sha256",
        "current_candidate_adoption_sha256",
        "current_candidate_private_sha256",
        "current_candidate_public_sha256",
        "historical_ratification_sha256", "historical_private_plan_sha256",
        "historical_public_plan_sha256", "source_freeze_sha256",
        "required_actor_validator_pinned_border_source_sha256s",
        "retained_terminal_failure_public_sha256s", "candidate_count",
        "family_candidate_counts", "no_gui_current_baseline_gate",
        "fresh_current_profile_gui_controls", "automatic_replay_authorized",
        "control_dispatch_authorized", "campaign_dispatch_authorized",
        "official_final_tasks_admitted", "researcher_campaigns", "model_attempts",
    }
    require(set(public) == allowed_public and
            nonce not in public_path.read_text(encoding="utf-8") and
            not any(row["task_id"] in public_path.read_text(encoding="utf-8")
                    for row in private["tasks"]),
            "epoch_audit_public_hidden_material_leak")
    counts = dict(Counter(row["family"] for row in private["tasks"]))
    require(counts == public["family_candidate_counts"],
            "epoch_audit_family_counts_changed")
    return {
        "schema": AUDIT_SCHEMA,
        "status": "source_only_evaluator_epoch_independently_verified_no_dispatch",
        "split": split,
        "private_plan_sha256": epoch.digest(private_path),
        "public_plan_sha256": epoch.digest(public_path),
        "source_freeze_sha256": freeze_sha,
        "current_candidate_private_sha256":
            adoption["current_six_cell_candidate_private_sha256"],
        "historical_ratification_sha256": old["ratification_sha256"],
        "candidate_count": old["task_count"],
        "retained_terminal_selection_failures": 3,
        "current_sql_full_filestore_gate_passed": False,
        "fresh_current_profile_gui_controls": 0,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("selection", "official_hidden"),
                        required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--private-plan", type=Path, required=True)
    parser.add_argument("--public-plan", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    args = parser.parse_args()
    value = audit(split=args.split, worker_dir=args.worker_dir,
                  private_path=args.private_plan,
                  public_path=args.public_plan,
                  old_private_path=args.old_private_plan,
                  old_public_path=args.old_public_plan)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
