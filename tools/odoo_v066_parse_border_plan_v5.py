"""Fresh selection evaluator epoch after a preserved v4 parse-frame failure.

The same underlying task may be inspected in a new, source-frozen candidate
attempt. The old attempt and its nonce remain immutable; neither candidate
authorizes a campaign or official final task.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets

from enterprise_fallback.odoo18.odoo_v066_scale_parse_border_adapter_v5 import (
    PROFILE,
)
from tools import audit_odoo_v066_current_candidate_epoch_v1 as prior_audit
from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as failure_audit
from tools import odoo_v066_current_candidate_epoch_v1 as prior_epoch
from tools import odoo_v066_parse_border_source_v5 as source
from tools import odoo_v066_scale_protocol_v1 as protocol


PRIVATE_SCHEMA = "envloop-odoo-v066-parse-border-selection-plan-private-v5"
PUBLIC_SCHEMA = "envloop-odoo-v066-parse-border-selection-plan-public-v5"
STATUS = "source_bound_same_task_fresh_attempt_pending_no_gui_gate"
PRIVATE_NAME = "selection-parse-border-v5.private.json"
PUBLIC_NAME = "odoo-v066-selection-parse-border-v5-evaluator-plan-2026-09-29.json"


class ParsePlanError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ParsePlanError(code)


def build(*, worker_dir: Path, historical_root: Path,
          prior_private_plan: Path, prior_public_plan: Path,
          old_private_plan: Path, old_public_plan: Path,
          nonce: str, allow_current_run: bool = False) -> tuple[dict, dict]:
    source.validate()
    worker = worker_dir.resolve()
    need(worker.name == "selection", "parse_plan_original_selection_required")
    prior_audit.audit(
        split="selection", worker_dir=worker,
        private_path=prior_private_plan, public_path=prior_public_plan,
        old_private_path=old_private_plan, old_public_path=old_public_plan,
        allow_current_run=True)
    failed = failure_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        private_plan=prior_private_plan, public_plan=prior_public_plan,
        old_private_plan=old_private_plan, old_public_plan=old_public_plan)
    need(failed["status"] ==
         "one_original_current_candidate_gui_failure_independently_verified_no_replay" and
         failed["rejected_action_dispatched"] is False and
         failed["baseline_sql_and_full_filestore_restored_exact"] is True,
         "parse_plan_prior_failure_not_terminally_audited")
    need(type(nonce) is str and re.fullmatch(r"[0-9a-f]{32}", nonce)
         is not None, "parse_plan_run_nonce_invalid")
    # The v1 template builder insists its own run directory is absent. Use a
    # deterministic, disjoint template nonce so this v5 audit can still reopen
    # its source plan after the new v5 attempt exists.
    template_nonce = sha256(b"parse-v5-template" +
                            bytes.fromhex(nonce)).hexdigest()[:32]
    base, public_base = prior_epoch.build(
        split="selection", worker_dir=worker,
        old_private_path=old_private_plan,
        old_public_path=old_public_plan, nonce=template_nonce)
    previous = protocol.private_json(prior_private_plan)
    need(base["tasks"][0] == previous["tasks"][0] and
         base["current_candidate_private_sha256"] ==
         previous["current_candidate_private_sha256"] and
         nonce != previous["run_nonce_hex"],
         "parse_plan_task_or_candidate_changed")
    private = protocol._worker_split(worker, "selection")
    run_name = f"current-candidate-parse-v5-{nonce}"
    run_path = private / "v066_scale_controls" / run_name
    for path in (private / "v066_scale_controls").glob(
            "*/batch-intent.private.json"):
        if allow_current_run and path.parent == run_path:
            continue
        need(protocol.private_json(path).get("run_nonce_hex") != nonce,
             "parse_plan_run_nonce_reused")
    need(allow_current_run or
         not run_path.exists() and not run_path.is_symlink(),
         "parse_plan_fresh_run_already_exists")
    if allow_current_run:
        protocol._private(run_path, directory=True)
    base.update({
        "schema": PRIVATE_SCHEMA,
        "status": STATUS,
        "run_nonce_hex": nonce,
        "fresh_run_directory_name": run_name,
        "physical_dispatch_profile": PROFILE,
        "parse_border_v5_source_freeze_sha256": source.digest(source.FREEZE),
        "prior_current_plan_sha256": prior_epoch.digest(prior_private_plan),
        "prior_current_public_plan_sha256":
            prior_epoch.digest(prior_public_plan),
        "prior_terminal_failure_receipt_sha256":
            failed["failure_receipt_sha256"],
        "prior_terminal_failure_audit_sha256":
            prior_epoch.digest(failure_audit.PUBLIC_PATH),
        "prior_no_gui_gate_sha256": failed["preceding_gate_sha256"],
        "same_underlying_task_new_candidate_attempt": True,
    })
    public_base.update({
        "schema": PUBLIC_SCHEMA,
        "status": STATUS,
        "private_plan_sha256": protocol.digest(protocol.canonical(base)),
        "run_nonce_sha256": protocol.digest(bytes.fromhex(nonce)),
        "physical_dispatch_profile": PROFILE,
        "parse_border_v5_source_freeze_sha256": source.digest(source.FREEZE),
        "prior_current_plan_sha256": prior_epoch.digest(prior_private_plan),
        "prior_current_public_plan_sha256":
            prior_epoch.digest(prior_public_plan),
        "prior_terminal_failure_receipt_sha256":
            failed["failure_receipt_sha256"],
        "prior_terminal_failure_audit_sha256":
            prior_epoch.digest(failure_audit.PUBLIC_PATH),
        "prior_no_gui_gate_sha256": failed["preceding_gate_sha256"],
        "same_underlying_task_new_candidate_attempt": True,
    })
    return base, public_base


def audit(*, worker_dir: Path, historical_root: Path,
          prior_private_plan: Path, prior_public_plan: Path,
          old_private_plan: Path, old_public_plan: Path,
          private_plan: Path, public_plan: Path,
          allow_current_run: bool = False) -> dict:
    private = protocol.private_json(private_plan)
    public = protocol.public_json(public_plan)
    expected_private, expected_public = build(
        worker_dir=worker_dir, historical_root=historical_root,
        prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan,
        nonce=private["run_nonce_hex"],
        allow_current_run=allow_current_run)
    need(private == expected_private and public == expected_public and
         prior_epoch.digest(private_plan) == public["private_plan_sha256"] and
         private["run_nonce_hex"] not in public_plan.read_text(),
         "parse_plan_private_public_or_source_binding_changed")
    return {
        "schema": "envloop-odoo-v066-parse-border-selection-plan-audit-v5",
        "status": "same_task_new_candidate_source_and_prior_failure_verified",
        "private_plan_sha256": prior_epoch.digest(private_plan),
        "public_plan_sha256": prior_epoch.digest(public_plan),
        "parse_border_v5_source_freeze_sha256":
            private["parse_border_v5_source_freeze_sha256"],
        "prior_terminal_failure_receipt_sha256":
            private["prior_terminal_failure_receipt_sha256"],
        "candidate_count": len(private["tasks"]),
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def write(*, worker_dir: Path, historical_root: Path,
          prior_private_plan: Path, prior_public_plan: Path,
          old_private_plan: Path, old_public_plan: Path,
          private_out: Path, public_out: Path) -> dict:
    worker = worker_dir.resolve()
    private_root = protocol._worker_split(worker, "selection")
    need(private_out == private_root / "v066_parse_border_v5" / PRIVATE_NAME and
         public_out == protocol.ROOT / "docs/evidence" / PUBLIC_NAME and
         not private_out.exists() and not private_out.is_symlink() and
         not public_out.exists() and not public_out.is_symlink(),
         "parse_plan_new_split_local_output_paths_required")
    nonce = secrets.token_hex(16)
    private, public = build(
        worker_dir=worker, historical_root=historical_root,
        prior_private_plan=prior_private_plan,
        prior_public_plan=prior_public_plan,
        old_private_plan=old_private_plan,
        old_public_plan=old_public_plan, nonce=nonce)
    private_out.parent.mkdir(mode=0o700, exist_ok=True)
    protocol.write_new(private_out, private, private=True)
    protocol.write_new(public_out, public, private=False)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--prior-private-plan", type=Path, required=True)
    parser.add_argument("--prior-public-plan", type=Path, required=True)
    parser.add_argument("--old-private-plan", type=Path, required=True)
    parser.add_argument("--old-public-plan", type=Path, required=True)
    parser.add_argument("--private-out", type=Path)
    parser.add_argument("--public-out", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    common = dict(worker_dir=args.worker_dir,
                  historical_root=args.historical_root,
                  prior_private_plan=args.prior_private_plan,
                  prior_public_plan=args.prior_public_plan,
                  old_private_plan=args.old_private_plan,
                  old_public_plan=args.old_public_plan)
    if args.write:
        need(args.private_out is not None and args.public_out is not None,
             "parse_plan_output_paths_required")
        result = write(**common, private_out=args.private_out,
                       public_out=args.public_out)
    else:
        need(args.private_out is not None and args.public_out is not None,
             "parse_plan_saved_paths_required")
        result = audit(**common, private_plan=args.private_out,
                       public_plan=args.public_out)
    print(json.dumps({"status": result["status"],
                      "private_plan_sha256": result["private_plan_sha256"],
                      "official_final_tasks_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
