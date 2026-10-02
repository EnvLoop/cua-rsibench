"""Independent final 100-case audit for the dated Magento modal supplement.

The underlying frozen v2 audit is rerun under the separately source-bound,
one-case compatibility adapter. This file rechecks the raw stopped attempt and
sidecar lineage itself. It never creates a score, cleanup, retry, or admission.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tools import audit_magento_v2_modal_stop_v1 as stop_audit
from tools import magento_resumable_100_v2 as v2
from tools import magento_v2_modal_supplement_v1 as supplement


ROOT = v2.ROOT
SCHEMA = "envloop-magento-v2-modal-supplement-100-audit-private-v1"
PUBLIC_SCHEMA = "envloop-magento-v2-modal-supplement-100-audit-public-v1"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _independent_raw_modal_check(ctx: dict, freeze: dict) -> dict:
    index = supplement.CASE_INDEX
    previous = v2.attempt_dir(ctx["run_dir"], index, 0)
    scoped = [row for row in v2.case_events(ctx["events"], index)
              if row.get("attempt") == 0 and row.get("event") not in (
                  "reconciliation_cleanup_intent", "cleanup_step_intent",
                  "cleanup_step_finished", "attempt_reconciled")]
    failed = [row for row in scoped if row.get("event") == "step_finished"
              and row.get("exit_code") != 0]
    steps = [row.get("step") for row in scoped
             if row.get("event") == "step_intent"]
    pair = previous / f"case-{index:03d}" / "positive"
    stderr = (pair / "positive-neutral-stderr.private.bin").read_bytes()
    process, process_sha = supplement.read_json(
        pair / "positive-neutral-process.private.json")
    require(len(failed) == 1 and failed[0].get("step") == "positive-neutral" and
            steps == ["positive-prepare", "positive-seed", "positive-neutral"] and
            failed[0].get("exit_code") != 0 and
            failed[0].get("stderr_sha256") == supplement.sha(stderr) ==
            ctx["stop"]["stderr_sha256"] and
            process_sha == ctx["stop"]["process_sha256"] and
            process.get("exit_code") == failed[0]["exit_code"] and
            stop_audit.is_premutation_modal_timeout(stderr) and
            not (pair / "neutral/private-after.json").exists() and
            not (pair / "neutral/result.json").exists() and
            not (pair / "gui-positive/result.json").exists() and
            not any(row.get("event") == "step_intent" and
                    row.get("step") == "positive-gui" for row in scoped) and
            freeze["original_stopped_journal_sha256"] ==
            ctx["stop"]["journal_sha256"],
            "independent_modal_stderr_or_pre_edit_boundary_changed")
    return {"stderr_sha256": supplement.sha(stderr),
            "process_sha256": process_sha,
            "source_first_attempt_index": index,
            "supplemental_classification": supplement.SUPPLEMENT_CLASS}


def audit(*, plan: Path, plan_sha256: str, source: Path,
          parent_freeze: Path, freeze_v2: Path, run_dir: Path) -> tuple[dict, dict]:
    ctx = supplement.context(plan=plan, plan_sha256=plan_sha256,
                             source=source, parent_freeze=parent_freeze,
                             freeze_v2=freeze_v2, run_dir=run_dir)
    frozen, frozen_sha = supplement.validate_supplement_freeze(ctx)
    lineage = supplement.require_cleanup_lineage(ctx)
    raw_modal = _independent_raw_modal_check(ctx, frozen)
    first_fourteen = supplement._first_fourteen_receipts(ctx)
    require(first_fourteen == frozen["first_fourteen_calibration_sha256"],
            "independent_original_first_fourteen_receipts_changed")
    # Explicit, source-bound compatibility scope. The unchanged v2 final
    # auditor itself still checks all 100 positive/negative/reset receipts.
    with supplement.explicit_source_bound_v2_classifier(ctx, frozen):
        original = v2.audit_campaign(plan, plan_sha256, source,
                                     parent_freeze, freeze_v2, run_dir)
    classes = original["invalid_attempts_by_classification"]
    require(original.get("distinct_candidate_controls") == 100 and
            original.get("positive_saved_state_pass") == 100 and
            original.get("wrong_variant_saved_state_rejected") == 100 and
            original.get("fresh_clone_material_reset_pass") == 100 and
            original.get("bounded_invalid_infrastructure_retries") == 1 and
            classes == {supplement.COMPAT_CLASS: 1} and
            original.get("historical_controls_reused") == 0 and
            original.get("model_calls") ==
            original.get("official_final_admitted") == 0,
            "frozen_v2_final_audit_not_exactly_100_with_one_scoped_retry")
    original_sha = supplement.sha(v2.encode(original))
    private = {"schema": SCHEMA,
               "status": "100_controls_under_explicit_pre_result_v2_supplement",
               "supplement_freeze_sha256": frozen_sha,
               "supplement_cleanup_receipt_sha256":
               lineage["supplement_cleanup_receipt_sha256"],
               "wrapper_source_sha256": lineage["wrapper_source_sha256"],
               "independent_auditor_source_sha256":
               supplement.sha(Path(__file__).read_bytes()),
               "frozen_v2_sha256": ctx["freeze_sha256"],
               "original_stopped_journal_sha256":
               frozen["original_stopped_journal_sha256"],
               "first_fourteen_calibration_sha256": first_fourteen,
               "modal_raw": raw_modal,
               "v2_final_audit": original,
               "v2_final_audit_sha256": original_sha,
               "model_calls": 0, "official_final_admitted": 0}
    public = {"schema": PUBLIC_SCHEMA,
              "status": "100_evaluator_controls_under_dated_v2_supplement_not_officially_admitted",
              "scope_case_ordinal": 15,
              "supplemental_classification": supplement.SUPPLEMENT_CLASS,
              "v2_internal_compatibility_classification": supplement.COMPAT_CLASS,
              "frozen_v2_sha256": ctx["freeze_sha256"],
              "supplement_freeze_sha256": frozen_sha,
              "supplement_cleanup_receipt_sha256":
              lineage["supplement_cleanup_receipt_sha256"],
              "wrapper_source_sha256": lineage["wrapper_source_sha256"],
              "independent_auditor_source_sha256":
              private["independent_auditor_source_sha256"],
              "original_stopped_journal_sha256":
              frozen["original_stopped_journal_sha256"],
              "first_fourteen_calibration_sha256": first_fourteen,
              "v2_final_audit_sha256": original_sha,
              "journal_sha256": original["journal_sha256"],
              "distinct_evaluator_controls": 100,
              "retained_invalid_attempts": 1,
              "one_same_id_whole_case_infrastructure_retry": 1,
              "model_calls": 0, "official_final_admitted": 0}
    return private, public


def _write_new(path: Path, value: dict, mode: int) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return supplement.sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("plan", "source", "parent-freeze", "freeze-v2",
                "run-dir", "private-out", "public-out"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    private_out, public_out = args.private_out.absolute(), args.public_out.absolute()
    require(private_out.parent.resolve().is_relative_to(
                (ROOT / "work").resolve()) and
            public_out.parent.resolve() == (ROOT / "docs/evidence").resolve() and
            not private_out.exists() and not public_out.exists(),
            "fresh_private_and_public_supplement_final_audit_paths_required")
    private, public = audit(
        plan=args.plan, plan_sha256=args.plan_sha256,
        source=args.source, parent_freeze=args.parent_freeze,
        freeze_v2=args.freeze_v2, run_dir=args.run_dir)
    private_sha = _write_new(private_out, private, 0o600)
    public["private_audit_sha256"] = private_sha
    _write_new(public_out, public, 0o644)
    print(json.dumps({"status": public["status"],
                      "distinct_evaluator_controls": 100,
                      "retained_invalid_attempts": 1,
                      "model_calls": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
