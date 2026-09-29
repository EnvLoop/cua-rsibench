"""Owner-only source freeze and fresh same-task Odoo v6 evaluator plan.

The v5 terminal attempt is never reused. This module reads saved files only;
it does not start Docker, Odoo, a GUI, or a model.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets

from enterprise_fallback.odoo18.odoo_v066_two_frame_dispatch_adapter_v6 import (
    PROFILE,
)
from tools import audit_odoo_v066_parse_border_dispatch_failure_20260929 as failure
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_two_frame_source_v6 as source


PRIVATE_FREEZE_SCHEMA = "envloop-odoo-v066-two-frame-private-source-freeze-v6"
PRIVATE_PLAN_SCHEMA = "envloop-odoo-v066-two-frame-selection-plan-private-v6"
PUBLIC_PLAN_SCHEMA = "envloop-odoo-v066-two-frame-selection-plan-public-v6"
PLAN_STATUS = "same_task_fresh_v6_candidate_pending_no_gui_gate"
PRIVATE_FREEZE_NAME = "source-freeze-20260929.private.json"
PRIVATE_PLAN_NAME = "selection-two-frame-v6.private.json"
PUBLIC_PLAN_NAME = "odoo-v066-selection-two-frame-v6-evaluator-plan-2026-09-29.json"


class TwoFramePlanError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise TwoFramePlanError(code)


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(),
         "two_frame_plan_input_missing_or_symlink")
    return sha256(path.read_bytes()).hexdigest()


def _prior(*, worker_dir: Path, prior_private_plan: Path,
           prior_public_plan: Path) -> tuple[dict, dict, dict, str]:
    worker = worker_dir.resolve()
    private_root = protocol._worker_split(worker, "selection")
    prior = protocol.private_json(prior_private_plan)
    prior_public = protocol.public_json(prior_public_plan)
    incident = protocol.public_json(failure.PUBLIC_AUDIT)
    run = private_root / "v066_scale_controls" / prior[
        "fresh_run_directory_name"]
    failure_path = run / "attempt-000/failure.private.json"
    need(prior.get("split") == "selection" and
         prior_public.get("private_plan_sha256") ==
         digest(prior_private_plan) and
         prior.get("parse_border_v5_source_freeze_sha256") ==
         source.digest(source.previous.FREEZE) and
         incident.get("status") ==
         "original_v5_dispatch_frame_failure_independently_verified_no_replay" and
         incident.get("private_plan_sha256") ==
         digest(prior_private_plan) and
         incident.get("failure_receipt_sha256") ==
         digest(failure_path) and
         incident.get("source_freeze_sha256") ==
         source.digest(source.previous.FREEZE) and
         incident.get("failed_action_click_dispatched") is False and
         incident.get("baseline_sql_and_full_filestore_restored_exact") is True and
         incident.get("official_final_tasks_admitted") == 0,
         "two_frame_plan_prior_terminal_evidence_unbound")
    return prior, prior_public, incident, digest(failure_path)


def build_private_freeze(*, worker_dir: Path,
                         prior_private_plan: Path,
                         prior_public_plan: Path) -> dict:
    source.validate()
    prior, _public, incident, raw_failure_sha = _prior(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan)
    return {
        "schema": PRIVATE_FREEZE_SCHEMA,
        "status": "source_and_original_v5_failure_bound_before_v6_plan",
        "as_of_date": "2026-09-29",
        "public_v6_source_freeze_sha256": digest(source.FREEZE),
        "prior_v5_private_plan_sha256": digest(prior_private_plan),
        "prior_v5_public_plan_sha256": digest(prior_public_plan),
        "prior_v5_terminal_failure_receipt_sha256": raw_failure_sha,
        "prior_v5_public_failure_audit_sha256":
            digest(failure.PUBLIC_AUDIT),
        "prior_v5_lease_prefix_sha256":
            incident["worker_lease_prefix_sha256"],
        "prior_v5_no_gui_gate_sha256":
            incident["prior_no_gui_gate_sha256"],
        "current_candidate_private_sha256":
            prior["current_candidate_private_sha256"],
        "same_underlying_task_fresh_nonce_required": True,
        "prior_v5_attempt_immutable_no_replay": True,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def audit_private_freeze(*, worker_dir: Path,
                         prior_private_plan: Path,
                         prior_public_plan: Path,
                         private_freeze: Path) -> dict:
    recorded = protocol.private_json(private_freeze)
    expected = build_private_freeze(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan)
    need(recorded == expected,
         "two_frame_private_source_freeze_or_prior_failure_changed")
    return recorded


def write_private_freeze(*, worker_dir: Path,
                         prior_private_plan: Path,
                         prior_public_plan: Path,
                         private_freeze: Path) -> dict:
    private = protocol._worker_split(worker_dir, "selection")
    need(private_freeze == private / "v066_two_frame_v6" /
         PRIVATE_FREEZE_NAME and
         not private_freeze.exists() and not private_freeze.is_symlink(),
         "two_frame_private_freeze_new_split_local_path_required")
    value = build_private_freeze(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan)
    protocol.write_new(private_freeze, value, private=True)
    return {"status": value["status"],
            "private_source_freeze_sha256": digest(private_freeze),
            "official_final_tasks_admitted": 0}


def build(*, worker_dir: Path, prior_private_plan: Path,
          prior_public_plan: Path, private_freeze: Path,
          nonce: str, allow_current_run: bool = False) -> tuple[dict, dict]:
    frozen = audit_private_freeze(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        private_freeze=private_freeze)
    prior, public_prior, incident, _ = _prior(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan)
    need(type(nonce) is str and re.fullmatch(r"[0-9a-f]{32}", nonce)
         is not None and nonce != prior["run_nonce_hex"],
         "two_frame_plan_run_nonce_invalid_or_reused")
    private_root = protocol._worker_split(worker_dir, "selection")
    run_name = f"current-candidate-two-frame-v6-{nonce}"
    run = private_root / "v066_scale_controls" / run_name
    for path in (private_root / "v066_scale_controls").glob(
            "*/batch-intent.private.json"):
        if allow_current_run and path.parent == run:
            continue
        need(protocol.private_json(path).get("run_nonce_hex") != nonce,
             "two_frame_plan_nonce_reused_from_other_attempt")
    need(allow_current_run or not run.exists() and not run.is_symlink(),
         "two_frame_plan_fresh_run_already_exists")
    if allow_current_run:
        protocol._private(run, directory=True)
    private = dict(prior)
    private.update({
        "schema": PRIVATE_PLAN_SCHEMA,
        "status": PLAN_STATUS,
        "run_nonce_hex": nonce,
        "fresh_run_directory_name": run_name,
        "physical_dispatch_profile": PROFILE,
        "two_frame_v6_source_freeze_sha256": digest(source.FREEZE),
        "two_frame_v6_private_source_freeze_sha256":
            digest(private_freeze),
        "prior_v5_private_plan_sha256": digest(prior_private_plan),
        "prior_v5_public_plan_sha256": digest(prior_public_plan),
        "prior_v5_failure_receipt_sha256":
            incident["failure_receipt_sha256"],
        "prior_v5_public_failure_audit_sha256":
            digest(failure.PUBLIC_AUDIT),
        "prior_v5_no_gui_gate_sha256":
            incident["prior_no_gui_gate_sha256"],
        "same_underlying_task_new_candidate_attempt": True,
        "no_gui_current_baseline_gate": {
            "schema": "envloop-odoo-v066-two-frame-no-gui-gate-requirement-v6",
            "status": "required_not_run",
            "worker_split": "selection",
            "current_sql_and_full_filestore_exact_required": True,
            "original_worker_exclusive_lease_required": True,
            "stopped_services_before_and_after_required": True,
            "live_gate_receipt_sha256": None,
        },
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    })
    public = dict(public_prior)
    public.update({
        "schema": PUBLIC_PLAN_SCHEMA,
        "status": PLAN_STATUS,
        "private_plan_sha256": protocol.digest(protocol.canonical(private)),
        "run_nonce_sha256": protocol.digest(bytes.fromhex(nonce)),
        "physical_dispatch_profile": PROFILE,
        "two_frame_v6_source_freeze_sha256": digest(source.FREEZE),
        "two_frame_v6_private_source_freeze_sha256":
            digest(private_freeze),
        "prior_v5_private_plan_sha256": digest(prior_private_plan),
        "prior_v5_public_plan_sha256": digest(prior_public_plan),
        "prior_v5_failure_receipt_sha256":
            incident["failure_receipt_sha256"],
        "prior_v5_public_failure_audit_sha256":
            digest(failure.PUBLIC_AUDIT),
        "prior_v5_no_gui_gate_sha256":
            incident["prior_no_gui_gate_sha256"],
        "same_underlying_task_new_candidate_attempt": True,
        "no_gui_current_baseline_gate": private[
            "no_gui_current_baseline_gate"],
        "fresh_current_profile_gui_controls": 0,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "researcher_campaigns": 0,
        "model_attempts": 0,
    })
    return private, public


def audit(*, worker_dir: Path, prior_private_plan: Path,
          prior_public_plan: Path, private_freeze: Path,
          private_plan: Path, public_plan: Path,
          allow_current_run: bool = False) -> dict:
    recorded_private = protocol.private_json(private_plan)
    recorded_public = protocol.public_json(public_plan)
    expected_private, expected_public = build(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        private_freeze=private_freeze,
        nonce=recorded_private["run_nonce_hex"],
        allow_current_run=allow_current_run)
    need(recorded_private == expected_private and
         recorded_public == expected_public and
         digest(private_plan) == recorded_public["private_plan_sha256"] and
         recorded_private["run_nonce_hex"] not in
         public_plan.read_text(encoding="utf-8"),
         "two_frame_plan_private_public_or_prior_evidence_changed")
    return {
        "schema": "envloop-odoo-v066-two-frame-selection-plan-audit-v6",
        "status": "fresh_same_task_candidate_source_and_failure_verified",
        "private_plan_sha256": digest(private_plan),
        "public_plan_sha256": digest(public_plan),
        "source_freeze_sha256": digest(source.FREEZE),
        "private_source_freeze_sha256": digest(private_freeze),
        "candidate_count": len(recorded_private["tasks"]),
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def write(*, worker_dir: Path, prior_private_plan: Path,
          prior_public_plan: Path, private_freeze: Path,
          private_out: Path, public_out: Path) -> dict:
    private_root = protocol._worker_split(worker_dir, "selection")
    need(private_out == private_root / "v066_two_frame_v6" /
         PRIVATE_PLAN_NAME and
         public_out == protocol.ROOT / "docs/evidence" /
         PUBLIC_PLAN_NAME and
         not private_out.exists() and not private_out.is_symlink() and
         not public_out.exists() and not public_out.is_symlink(),
         "two_frame_plan_new_split_local_output_paths_required")
    nonce = secrets.token_hex(16)
    private, public = build(
        worker_dir=worker_dir, prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        private_freeze=private_freeze, nonce=nonce)
    protocol.write_new(private_out, private, private=True)
    protocol.write_new(public_out, public, private=False)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--prior-private-plan", type=Path, required=True)
    parser.add_argument("--prior-public-plan", type=Path, required=True)
    parser.add_argument("--private-freeze", type=Path, required=True)
    parser.add_argument("--private-out", type=Path)
    parser.add_argument("--public-out", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write-private-freeze", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    common = dict(worker_dir=args.worker_dir,
                  prior_private_plan=args.prior_private_plan,
                  prior_public_plan=args.prior_public_plan,
                  private_freeze=args.private_freeze)
    if args.write_private_freeze:
        value = write_private_freeze(**common)
    elif args.write:
        need(args.private_out is not None and args.public_out is not None,
             "two_frame_plan_output_paths_required")
        value = write(**common, private_out=args.private_out,
                      public_out=args.public_out)
    else:
        need(args.private_out is not None and args.public_out is not None,
             "two_frame_plan_saved_paths_required")
        value = audit(**common, private_plan=args.private_out,
                      public_plan=args.public_out)
    print(json.dumps({"status": value["status"],
                      "official_final_tasks_admitted": 0,
                      **({"private_plan_sha256": value["private_plan_sha256"]}
                         if "private_plan_sha256" in value else
                         {"private_source_freeze_sha256":
                          value["private_source_freeze_sha256"]})},
                     sort_keys=True))


if __name__ == "__main__":
    main()
