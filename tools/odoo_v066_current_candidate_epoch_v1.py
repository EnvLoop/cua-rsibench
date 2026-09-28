"""Freeze a new evaluator-only Odoo source epoch without dispatch authority.

The v0.6.6 split plans belong to an older six-cell ratification. This module
copies their already source-checked task identities into new, split-local
private plans, binding the current six-cell candidate and a fresh random run
nonce. It never edits an earlier plan or starts Odoo, Docker, GUI, or models.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets

from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import propose_odoo_v066_candidate_control_adoption_v1 as proposal


DATE = "2026-09-29"
PRIVATE_SCHEMA = "envloop-odoo-v066-current-candidate-evaluator-plan-private-v1"
PUBLIC_SCHEMA = "envloop-odoo-v066-current-candidate-evaluator-plan-public-v1"
STATUS = "source_bound_evaluator_only_pending_current_baseline_gate"
GATE_SCHEMA = "envloop-odoo-v066-current-candidate-no-gui-baseline-gate-v1"
ADOPTION_PUBLIC = (protocol.ROOT / "docs/evidence" /
                   "odoo-v066-current-candidate-control-adoption-proposal-2026-09-29.json")
SOURCE_FREEZE = proposal.FREEZE
REQUIRED_SOURCE = (
    "enterprise_fallback/odoo18/odoo_v066_scale_pinned_border_adapter.py",
    "enterprise_fallback/odoo18/odoo_v066_scale_exact_return_adapter.py",
    "src/cursibench/scale_action_contract_v066.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/worker_lease.py",
    "tools/odoo_v066_scale_controller_v1.py",
    "tools/odoo_v066_scale_audit_v1.py",
)


class EpochError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise EpochError(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "epoch_input_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def _source_and_proposal() -> tuple[dict, dict, str]:
    observed = proposal.inspect()
    published = protocol.public_json(ADOPTION_PUBLIC)
    require(published == observed and
            observed["current_six_cell_candidate_private_sha256"] ==
            "bd7225ea7b348d8a72a7e5dc951bdeacef159560b034e13c40a7680799e018a9" and
            observed["control_dispatch_authorized"] is False and
            observed["campaign_dispatch_authorized"] is False,
            "epoch_adoption_proposal_changed_or_authorized")
    freeze, freeze_sha = protocol.validate_source_freeze(SOURCE_FREEZE)
    require(freeze_sha == observed["odoo_validator_source_freeze_sha256"] and
            all(relative in freeze["source_sha256s"] for relative in REQUIRED_SOURCE),
            "epoch_validator_or_pinned_border_source_unbound")
    return observed, freeze, freeze_sha


def _validate_task_assets(worker_dir: Path, old: dict) -> None:
    from enterprise_fallback.odoo18.partition_factory import source_asset
    split = old["split"]
    private = protocol._worker_split(worker_dir, split)
    world = protocol.private_json(private / "partition_cases.json")
    hashes = protocol.private_json(private / "source_hashes.json")
    checkpoint = protocol.private_json(private / "checkpoint_receipt.json")
    bound = old["checkpoint"]
    require(world.get("split") == split and
            len(hashes) == old["world_case_count"] and
            bound["db_sha256"] == checkpoint["db_sha256"] and
            bound["filestore_sha256"] == checkpoint["filestore_sha256"] and
            bound["baseline_filestore_manifest_sha256"] ==
            checkpoint["filestore_manifest_sha256"] and
            digest(private / "baseline.pgcustom") == checkpoint["db_sha256"] and
            digest(private / "baseline-filestore.tgz") ==
            checkpoint["filestore_sha256"] and
            digest(private / "baseline_snapshot.json") ==
            bound["baseline_snapshot_sha256"] and
            digest(private / "baseline-filestore-manifest.json") ==
            bound["baseline_filestore_manifest_sha256"],
            "epoch_worker_checkpoint_or_split_changed")
    by_id = {case["id"]: case for family in protocol.FAMILIES
             for case in world["cases"][family]}
    require(len(by_id) == old["world_case_count"] and
            len({row["task_id"] for row in old["tasks"]}) ==
            old["task_count"], "epoch_private_task_roster_changed")
    for row in old["tasks"]:
        case = by_id.get(row["task_id"])
        require(case is not None and case["family"] == row["family"] and
                row["checkpoint"] == bound,
                "epoch_task_or_checkpoint_changed")
        asset = source_asset(case, world)
        package = protocol.digest(json.dumps(case, sort_keys=True).encode() +
                                  b"\n" + asset)
        require(row["package_sha256"] == package and
                row["source_asset_sha256"] == hashes[row["task_id"]] ==
                protocol.digest(asset) and
                row["visible_instruction_sha256"] ==
                protocol.digest(case["prompt"].encode()),
                "epoch_task_source_or_instruction_changed")


def _fresh_nonce(worker_dir: Path, nonce: str, *,
                 allow_current_run: bool = False) -> None:
    require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{32}", nonce) is not None,
            "epoch_run_nonce_invalid")
    private = protocol._worker_split(worker_dir, worker_dir.name)
    root = private / "v066_scale_controls"
    if root.exists():
        protocol._private(root, directory=True)
        for path in root.glob("*/batch-intent.private.json"):
            old = protocol.private_json(path)
            if allow_current_run and path.parent.name == f"current-candidate-{nonce}":
                continue
            require(old.get("run_nonce_hex") != nonce,
                    "epoch_run_nonce_reused_from_historical_attempt")
        planned_run = root / f"current-candidate-{nonce}"
        if allow_current_run:
            protocol._private(planned_run, directory=True)
        else:
            require(not planned_run.exists(),
                    "epoch_fresh_run_directory_already_exists")


def build(*, split: str, worker_dir: Path, old_private_path: Path,
          old_public_path: Path, nonce: str) -> tuple[dict, dict]:
    require(split in ("selection", "official_hidden") and
            worker_dir.name == split, "epoch_split_invalid")
    adoption, freeze, freeze_sha = _source_and_proposal()
    old = protocol.validate_split_plan(
        split=split, private_path=old_private_path,
        public_path=old_public_path, source_freeze_path=SOURCE_FREEZE)
    old_public = protocol.public_json(old_public_path)
    expected = adoption["historical_split_plans"][split]
    require(digest(old_private_path) == expected["private_sha256"] and
            digest(old_public_path) == expected["public_sha256"] and
            old["ratification_sha256"] ==
            expected["historical_ratification_sha256"] and
            old["ratification_sha256"] !=
            adoption["current_six_cell_candidate_private_sha256"] and
            old_public["fresh_current_profile_gui_controls"] == 0 and
            old["official_final_tasks_admitted"] == 0,
            "epoch_historical_split_plan_changed_or_relabelled")
    _validate_task_assets(worker_dir, old)
    _fresh_nonce(worker_dir, nonce)
    source = {relative: freeze["source_sha256s"][relative]
              for relative in REQUIRED_SOURCE}
    gate = {
        "schema": GATE_SCHEMA,
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
    private_plan = {
        "schema": PRIVATE_SCHEMA,
        "status": STATUS,
        "as_of_date": DATE,
        "split": split,
        "cell": "odoo-community",
        "current_candidate_adoption_sha256": digest(ADOPTION_PUBLIC),
        "current_candidate_private_sha256":
            adoption["current_six_cell_candidate_private_sha256"],
        "current_candidate_public_sha256":
            adoption["current_six_cell_candidate_public_sha256"],
        "historical_ratification_sha256": old["ratification_sha256"],
        "historical_private_plan_sha256": digest(old_private_path),
        "historical_public_plan_sha256": digest(old_public_path),
        "source_freeze_sha256": freeze_sha,
        "source_sha256s": freeze["source_sha256s"],
        "required_actor_validator_pinned_border_source_sha256s": source,
        "retained_terminal_failure_public_sha256s":
            adoption["retained_terminal_failure_public_sha256s"],
        "run_nonce_hex": nonce,
        "fresh_run_directory_name": f"current-candidate-{nonce}",
        "task_count": old["task_count"],
        "world_case_count": old["world_case_count"],
        "checkpoint": old["checkpoint"],
        "task_set_manifest_sha256": old["task_set_manifest_sha256"],
        "physical_dispatch_profile": freeze["physical_dispatch_profile"],
        "validator_amendment": freeze["validator_amendment"],
        "tasks": old["tasks"],
        "no_gui_current_baseline_gate": gate,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    public_plan = {
        "schema": PUBLIC_SCHEMA,
        "status": STATUS,
        "as_of_date": DATE,
        "split": split,
        "cell": "odoo-community",
        "private_plan_sha256": protocol.digest(protocol.canonical(private_plan)),
        "run_nonce_sha256": protocol.digest(bytes.fromhex(nonce)),
        "current_candidate_adoption_sha256": digest(ADOPTION_PUBLIC),
        "current_candidate_private_sha256":
            adoption["current_six_cell_candidate_private_sha256"],
        "current_candidate_public_sha256":
            adoption["current_six_cell_candidate_public_sha256"],
        "historical_ratification_sha256": old["ratification_sha256"],
        "historical_private_plan_sha256": digest(old_private_path),
        "historical_public_plan_sha256": digest(old_public_path),
        "source_freeze_sha256": freeze_sha,
        "required_actor_validator_pinned_border_source_sha256s": source,
        "retained_terminal_failure_public_sha256s":
            adoption["retained_terminal_failure_public_sha256s"],
        "candidate_count": old["task_count"],
        "family_candidate_counts": old_public["family_candidate_counts"],
        "no_gui_current_baseline_gate": gate,
        "fresh_current_profile_gui_controls": 0,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    }
    return private_plan, public_plan


def write(*, split: str, worker_dir: Path, old_private_path: Path,
          old_public_path: Path, private_out: Path,
          public_out: Path) -> dict:
    require(not private_out.exists() and not private_out.is_symlink() and
            not public_out.exists() and not public_out.is_symlink() and
            private_out.parent.resolve() ==
            (protocol._worker_split(worker_dir, split) /
             "v066_current_candidate_epoch").resolve() and
            public_out.parent.resolve() == proposal.EVIDENCE.resolve(),
            "epoch_output_path_not_new_or_split_local")
    nonce = secrets.token_hex(16)
    private, public = build(split=split, worker_dir=worker_dir,
                            old_private_path=old_private_path,
                            old_public_path=old_public_path, nonce=nonce)
    protocol.write_new(private_out, private, private=True)
    protocol.write_new(public_out, public, private=False)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("selection", "official_hidden"),
                        required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    value = write(split=args.split, worker_dir=args.worker_dir,
                  old_private_path=args.old_private_plan,
                  old_public_path=args.old_public_plan,
                  private_out=args.private_out, public_out=args.public_out)
    print(json.dumps({"status": value["status"],
                      "split": value["split"],
                      "private_plan_sha256": value["private_plan_sha256"],
                      "control_dispatch_authorized": False,
                      "official_final_tasks_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
