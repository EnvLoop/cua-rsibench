"""Explicit source-bound supplement for one pre-edit Magento v2 modal stop.

The frozen v2 files are never modified. This pre-result adapter gives the
original v2 reconciler one narrowly scoped compatibility classification only
after independently bound modal/material evidence has been checked. It is not
an already-existing v2 classification, model result, or final admission.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from tools import audit_magento_v2_modal_stop_v1 as stop_audit
from tools import magento_resumable_100_v2 as v2


ROOT = v2.ROOT
SCHEMA = "envloop-magento-v2-modal-supplement-private-v1"
PUBLIC_SCHEMA = "envloop-magento-v2-modal-supplement-source-public-v1"
COMPAT_CLASS = "known_neutral_cms_menu_timeout_before_edit"
SUPPLEMENT_CLASS = "supplemental_release_modal_pre_edit_timeout"
CASE_INDEX = 14
STOP_PUBLIC = ROOT / "docs/evidence/magento-v2-modal-stop-2026-09-28.json"
SOURCE_PUBLIC = ROOT / "docs/evidence/magento-v2-modal-supplement-source-2026-09-28.json"
AUDITOR_SOURCE = ROOT / "tools/audit_magento_v2_modal_supplement_v1.py"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "supplement_json_object_required")
    return value, sha(raw)


def write_new(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def source_receipt() -> dict:
    public, public_sha = read_json(SOURCE_PUBLIC)
    stop_public, stop_public_sha = read_json(STOP_PUBLIC)
    require(public.get("schema") == PUBLIC_SCHEMA and
            public.get("status") == "proposed_before_cleanup_retry_or_model_result" and
            public.get("supplemental_classification") == SUPPLEMENT_CLASS and
            public.get("v2_internal_compatibility_classification") == COMPAT_CLASS and
            public.get("original_v2_class_did_not_match_stopped_stderr") is True and
            public.get("scope_case_ordinal") == 15 and
            public.get("source_sha256") == sha(Path(__file__).read_bytes()) and
            public.get("independent_auditor_sha256") ==
            sha(AUDITOR_SOURCE.read_bytes()) and
            public.get("modal_stop_public_sha256") == stop_public_sha and
            public.get("frozen_v2_private_sha256") ==
            stop_public.get("freeze_v2_sha256") and
            public.get("frozen_v2_code_sha256s") == {
                name: sha((ROOT / name).read_bytes()) for name in v2.CODE_FILES} and
            public.get("modal_stop_private_sha256") ==
            stop_public.get("private_audit_sha256") and
            public.get("original_stopped_journal_sha256") ==
            stop_public.get("journal_sha256") and
            public.get("first_controls_retained") == 14 and
            public.get("cleanup_authorized") is False and
            public.get("retry_authorized") is False and
            public.get("model_calls") == public.get("official_final_admitted") == 0 and
            stop_public.get("cleanup_authorized") is False and
            stop_public.get("retry_authorized") is False,
            "published_modal_supplement_source_or_stop_evidence_changed")
    return {"source_public": public, "source_public_sha256": public_sha,
            "stop_public": stop_public, "stop_public_sha256": stop_public_sha}


def context(*, plan: Path, plan_sha256: str, source: Path,
            parent_freeze: Path, freeze_v2: Path, run_dir: Path) -> dict:
    require(run_dir.resolve().is_relative_to((ROOT / "work").resolve()) and
            all(path.resolve().is_relative_to((ROOT / "work").resolve())
                for path in (plan, source, parent_freeze, freeze_v2)),
            "supplement_input_outside_evaluator_private_work")
    published = source_receipt()
    frozen, parent, freeze_sha = v2.validate_freeze(
        freeze_v2, parent_freeze, plan, plan_sha256, source)
    cases = v2.validate_plan(plan, plan_sha256)
    journal = run_dir / "journal.private.jsonl"
    events = v2.read_journal(journal)
    v2.validate_run_header(events, freeze_sha, frozen)
    v2.validate_case_sequence(events, cases)
    stop_path = run_dir / "modal-stop-audit.private.json"
    stop, stop_sha = read_json(stop_path)
    require(stop_sha == published["stop_public"].get("private_audit_sha256") and
            stop.get("schema") == stop_audit.SCHEMA and
            stop.get("case_index") == CASE_INDEX and
            stop.get("freeze_v2_sha256") == freeze_sha and
            stop.get("plan_sha256") == plan_sha256 and
            stop.get("source_sha256") ==
            sha(Path(stop_audit.__file__).read_bytes()) and
            stop.get("cleanup_authorized") is False and
            stop.get("retry_authorized") is False and
            stop.get("model_calls") == stop.get("official_final_admitted") == 0,
            "original_modal_stop_audit_or_frozen_v2_identity_changed")
    return {"plan": plan, "plan_sha256": plan_sha256, "source": source,
            "parent_freeze": parent_freeze, "freeze_v2": freeze_v2,
            "run_dir": run_dir, "frozen": frozen, "parent": parent,
            "freeze_sha256": freeze_sha, "cases": cases,
            "journal": journal, "events": events,
            "stop": stop, "stop_sha256": stop_sha,
            **published}


def _first_fourteen_receipts(ctx: dict) -> str:
    completed = [row for row in ctx["events"] if row.get("event") == "case_completed"]
    require(len(completed) >= 14 and
            [row.get("index") for row in completed[:14]] == list(range(14)),
            "first_fourteen_frozen_controls_not_contiguous")
    receipts = []
    for index in range(14):
        event = completed[index]
        digest = v2.verify_finished_attempt(
            ctx["run_dir"], ctx["events"], index, event["attempt"],
            ctx["cases"][index], ctx["parent"]["runtime_fingerprint_sha256"])
        require(event.get("calibration_sha256") == digest,
                "first_fourteen_original_control_receipt_changed")
        receipts.append(digest)
    return sha(("\n".join(receipts) + "\n").encode())


def _post_stop_ui_evidence(run_dir: Path) -> dict[str, str]:
    observations = (
        ("modal-ui-readonly-20260928", "dashboard.private.png", False),
        ("modal-ui-click-readonly-20260928", "after.private.png", True),
    )
    hashes = {}
    for dirname, screenshot, clicked in observations:
        folder = run_dir / dirname
        receipt, receipt_sha = read_json(folder / "receipt.private.json")
        require(receipt.get("business_edits") == 0 and
                receipt.get("screenshot_sha256") ==
                sha((folder / screenshot).read_bytes()) and
                (not clicked or (receipt.get("menu_clicked") is True and
                                 receipt.get("error_type") is None)),
                "post_stop_ui_observation_or_zero_business_edit_proof_changed")
        hashes[dirname] = receipt_sha
    return hashes


def _original_stop_prefix(ctx: dict) -> tuple[int, str]:
    raw = ctx["journal"].read_bytes()
    expected = ctx["stop"]["journal_sha256"]
    if sha(raw) == expected:
        return len(raw), expected
    # A later cleanup/resume may append; the original stopped prefix must
    # still be byte-identical. Its length is frozen before any such action.
    freeze, _ = read_json(ctx["run_dir"] / "modal-supplement-freeze.private.json")
    length = freeze["original_stopped_journal_length"]
    require(type(length) is int and length > 0 and
            sha(raw[:length]) == expected and
            len(raw) >= length,
            "original_stopped_v2_journal_prefix_changed")
    return length, expected


def prepare_freeze(ctx: dict) -> dict:
    events = ctx["events"]
    completed = [row for row in events if row.get("event") == "case_completed"]
    require(len(completed) == CASE_INDEX and
            events[-1].get("event") == "attempt_stopped" and
            events[-1].get("index") == CASE_INDEX and
            not any(row.get("event") in ("attempt_reconciled", "run_completed")
                    for row in events),
            "supplement_must_precede_any_v2_cleanup_retry_or_result")
    scoped = [row for row in v2.case_events(events, CASE_INDEX)
              if row.get("attempt") == 0]
    raw_class = v2._known_neutral_timeout(
        v2.attempt_dir(ctx["run_dir"], CASE_INDEX, 0), CASE_INDEX, scoped)
    require(raw_class is None,
            "old_frozen_v2_class_already_covers_this_stop_no_supplement_needed")
    try:
        v2._retryable_interruption(scoped)
    except ValueError:
        pass
    else:
        raise ValueError("old_frozen_v2_retry_already_authorized")
    length, prefix_sha = _original_stop_prefix(ctx)
    require(prefix_sha == ctx["stop"]["journal_sha256"],
            "supplement_stop_journal_changed")
    ui_receipts = _post_stop_ui_evidence(ctx["run_dir"])
    require(ui_receipts == ctx["source_public"][
                "post_stop_ui_observation_sha256s"] and
            prefix_sha == ctx["source_public"]["original_stopped_journal_sha256"],
            "published_pre_result_modal_or_post_stop_ui_commitment_changed")
    return {"schema": SCHEMA,
            "status": "proposed_source_bound_one_case_pre_result_extension",
            "case_index": CASE_INDEX,
            "task_id": ctx["cases"][CASE_INDEX]["task_id"],
            "package_sha256": ctx["cases"][CASE_INDEX]["package_sha256"],
            "supplemental_classification": SUPPLEMENT_CLASS,
            "v2_internal_compatibility_classification": COMPAT_CLASS,
            "source_public_sha256": ctx["source_public_sha256"],
            "wrapper_source_sha256": sha(Path(__file__).read_bytes()),
            "independent_auditor_sha256": sha(AUDITOR_SOURCE.read_bytes()),
            "frozen_v2_sha256": ctx["freeze_sha256"],
            "v2_code_sha256": ctx["frozen"]["code_sha256"],
            "modal_stop_private_sha256": ctx["stop_sha256"],
            "modal_stop_public_sha256": ctx["stop_public_sha256"],
            "original_stopped_journal_length": length,
            "original_stopped_journal_sha256": prefix_sha,
            "first_fourteen_calibration_sha256": _first_fourteen_receipts(ctx),
            "post_stop_ui_observation_sha256s": ui_receipts,
            "one_same_id_whole_case_retry_only": True,
            "model_calls": 0, "official_final_admitted": 0}


def validate_supplement_freeze(ctx: dict) -> tuple[dict, str]:
    value, digest = read_json(ctx["run_dir"] /
                              "modal-supplement-freeze.private.json")
    require(value.get("schema") == SCHEMA and
            value.get("status") ==
            "proposed_source_bound_one_case_pre_result_extension" and
            value.get("case_index") == CASE_INDEX and
            value.get("task_id") == ctx["cases"][CASE_INDEX]["task_id"] and
            value.get("package_sha256") ==
            ctx["cases"][CASE_INDEX]["package_sha256"] and
            value.get("supplemental_classification") == SUPPLEMENT_CLASS and
            value.get("v2_internal_compatibility_classification") == COMPAT_CLASS and
            value.get("source_public_sha256") == ctx["source_public_sha256"] and
            value.get("wrapper_source_sha256") == sha(Path(__file__).read_bytes()) and
            value.get("independent_auditor_sha256") ==
            sha(AUDITOR_SOURCE.read_bytes()) and
            value.get("frozen_v2_sha256") == ctx["freeze_sha256"] and
            value.get("v2_code_sha256") == ctx["frozen"]["code_sha256"] and
            value.get("modal_stop_private_sha256") == ctx["stop_sha256"] and
            value.get("modal_stop_public_sha256") == ctx["stop_public_sha256"] and
            value.get("original_stopped_journal_sha256") ==
            ctx["stop"]["journal_sha256"] and
            value.get("first_fourteen_calibration_sha256") ==
            _first_fourteen_receipts(ctx) and
            value.get("post_stop_ui_observation_sha256s") ==
            _post_stop_ui_evidence(ctx["run_dir"]) ==
            ctx["source_public"]["post_stop_ui_observation_sha256s"] and
            value.get("one_same_id_whole_case_retry_only") is True and
            value.get("model_calls") == value.get("official_final_admitted") == 0,
            "supplemental_source_freeze_or_first_fourteen_changed")
    _original_stop_prefix(ctx)
    return value, digest


def _supplemental_classifier(ctx: dict, frozen: dict, original):
    expected = v2.attempt_dir(ctx["run_dir"], CASE_INDEX, 0)
    stopped = ctx["stop"]

    def classify(base: Path, index: int, scoped: list[dict]) -> str | None:
        prior = original(base, index, scoped)
        if prior is not None or index != CASE_INDEX or base.resolve() != expected.resolve():
            return prior
        failed = [row for row in scoped if row.get("event") == "step_finished"
                  and row.get("exit_code") != 0]
        steps = [row.get("step") for row in scoped
                 if row.get("event") == "step_intent"]
        pair = base / f"case-{CASE_INDEX:03d}" / "positive"
        stderr_path = pair / "positive-neutral-stderr.private.bin"
        process_path = pair / "positive-neutral-process.private.json"
        if not (len(failed) == 1 and failed[0].get("step") == "positive-neutral" and
                steps == ["positive-prepare", "positive-seed", "positive-neutral"] and
                stderr_path.is_file() and process_path.is_file() and
                not (pair / "neutral/private-after.json").exists() and
                not (pair / "neutral/result.json").exists() and
                not (pair / "gui-positive/result.json").exists() and
                not any(row.get("event") == "step_intent" and
                        row.get("step") == "positive-gui" for row in scoped)):
            return None
        stderr = stderr_path.read_bytes()
        process, process_sha = read_json(process_path)
        require(sha(stderr) == stopped["stderr_sha256"] ==
                failed[0].get("stderr_sha256") and
                process_sha == stopped["process_sha256"] and
                process.get("exit_code") == failed[0].get("exit_code") and
                stop_audit.is_premutation_modal_timeout(stderr) and
                frozen["original_stopped_journal_sha256"] ==
                stopped["journal_sha256"],
                "supplemental_one_case_modal_bytes_or_pre_edit_boundary_changed")
        return COMPAT_CLASS

    return classify


@contextmanager
def explicit_source_bound_v2_classifier(ctx: dict, frozen: dict):
    """The only runtime adaptation; source/public/private hashes bind it."""
    original = v2._known_neutral_timeout
    replacement = _supplemental_classifier(ctx, frozen, original)
    v2._known_neutral_timeout = replacement
    try:
        yield
    finally:
        v2._known_neutral_timeout = original


def fresh_modal_witness(ctx: dict) -> tuple[dict, str]:
    current, _ = stop_audit.audit(
        plan=ctx["plan"], plan_sha256=ctx["plan_sha256"],
        source=ctx["source"], parent_freeze=ctx["parent_freeze"],
        freeze_v2=ctx["freeze_v2"], run_dir=ctx["run_dir"])
    old = ctx["stop"]
    for key in ("case_index", "task_id", "package_sha256", "plan_sha256",
                "freeze_v2_sha256", "journal_sha256", "process_sha256",
                "stderr_sha256", "prepare_sha256", "seed_sha256",
                "pre_gui_snapshot_sha256", "material_witness",
                "cron_config_sha256", "price_shape_sha256"):
        require(current.get(key) == old.get(key),
                "fresh_modal_material_or_pair_identity_changed_after_stop")
    current["cleanup_authorized"] = False
    current["retry_authorized"] = False
    return current, sha(v2.encode(current))


def _paths(ctx: dict) -> dict[str, Path]:
    root = ctx["run_dir"]
    return {
        "freeze": root / "modal-supplement-freeze.private.json",
        "fresh": root / "modal-supplement-fresh-audit.private.json",
        "intent": root / "modal-supplement-cleanup-intent.private.json",
        "receipt": root / "modal-supplement-cleanup-receipt.private.json",
        "v2_audit": v2.attempt_dir(root, CASE_INDEX, 0) /
                    "reconciliation-audit.private.json",
        "v2_cleanup": v2.attempt_dir(root, CASE_INDEX, 0) /
                      "reconciliation.private.json",
    }


def prepare(ctx: dict) -> dict:
    paths = _paths(ctx)
    require(not any(path.exists() for path in paths.values()),
            "supplement_must_be_frozen_before_any_reconciliation")
    value = prepare_freeze(ctx)
    digest = write_new(paths["freeze"], value)
    return {"status": "source_bound_supplement_frozen_no_cleanup_or_retry",
            "supplement_freeze_sha256": digest, "official_final_admitted": 0}


def audit_live(ctx: dict) -> dict:
    frozen, frozen_sha = validate_supplement_freeze(ctx)
    paths = _paths(ctx)
    require(not paths["v2_audit"].exists() and
            not paths["intent"].exists() and
            not paths["receipt"].exists(),
            "modal_supplement_audit_is_not_a_retry")
    current, witness_sha = fresh_modal_witness(ctx)
    if paths["fresh"].exists():
        saved, _ = read_json(paths["fresh"])
        require(saved.get("fresh_material_witness_sha256") == witness_sha and
                saved.get("supplement_freeze_sha256") == frozen_sha,
                "existing_fresh_modal_audit_differs")
    else:
        write_new(paths["fresh"], {
            "schema": "envloop-magento-v2-modal-supplement-fresh-audit-v1",
            "supplement_freeze_sha256": frozen_sha,
            "fresh_material_witness_sha256": witness_sha,
            "material_witness": current["material_witness"],
            "cleanup_authorized": False, "retry_authorized": False,
            "model_calls": 0, "official_final_admitted": 0})
    with explicit_source_bound_v2_classifier(ctx, frozen):
        result = v2.reconcile_attempt(
            ctx["plan"], ctx["plan_sha256"], ctx["source"],
            ctx["parent_freeze"], ctx["freeze_v2"], ctx["run_dir"], mode="audit")
    v2_audit, _ = read_json(paths["v2_audit"])
    require(v2_audit.get("classification") == COMPAT_CLASS and
            v2_audit.get("case_index") == CASE_INDEX and
            v2_audit.get("material_witness", {}).get("material_equal_exact") is True and
            v2_audit.get("material_witness", {}).get("allowed_volatile_fields") == [] and
            v2_audit.get("material_witness", {}).get("material_current_snapshot") ==
            ctx["stop"]["material_witness"]["material_current_snapshot"] and
            result.get("official_final_admitted") == 0,
            "v2_audit_did_not_record_scoped_compatibility_class")
    return {"status": "fresh_modal_and_v2_reconciliation_audited_no_cleanup",
            "supplemental_classification": SUPPLEMENT_CLASS,
            "v2_internal_compatibility_classification": COMPAT_CLASS,
            "official_final_admitted": 0}


def cleanup(ctx: dict) -> dict:
    frozen, frozen_sha = validate_supplement_freeze(ctx)
    paths = _paths(ctx)
    require(paths["v2_audit"].is_file() and paths["fresh"].is_file(),
            "fresh_source_bound_and_v2_audits_required_before_cleanup")
    fresh, fresh_sha = read_json(paths["fresh"])
    v2_audit, v2_audit_sha = read_json(paths["v2_audit"])
    require(fresh.get("supplement_freeze_sha256") == frozen_sha and
            fresh.get("material_witness") == ctx["stop"]["material_witness"] and
            v2_audit.get("classification") == COMPAT_CLASS and
            v2_audit.get("case_index") == CASE_INDEX,
            "supplemental_pre_cleanup_audit_chain_changed")
    if not paths["v2_cleanup"].exists():
        current, witness_sha = fresh_modal_witness(ctx)
        require(current["material_witness"] == fresh["material_witness"] and
                witness_sha == fresh["fresh_material_witness_sha256"],
                "current_modal_pair_changed_before_cleanup")
    if paths["intent"].exists():
        intent, intent_sha = read_json(paths["intent"])
        require(intent.get("supplement_freeze_sha256") == frozen_sha and
                intent.get("fresh_audit_sha256") == fresh_sha and
                intent.get("v2_audit_sha256") == v2_audit_sha and
                intent.get("case_index") == CASE_INDEX,
                "existing_supplemental_cleanup_intent_changed")
    else:
        intent_sha = write_new(paths["intent"], {
            "schema": "envloop-magento-v2-modal-supplement-cleanup-intent-v1",
            "case_index": CASE_INDEX,
            "supplement_freeze_sha256": frozen_sha,
            "fresh_audit_sha256": fresh_sha,
            "v2_audit_sha256": v2_audit_sha,
            "original_stopped_journal_sha256":
            frozen["original_stopped_journal_sha256"],
            "supplemental_classification": SUPPLEMENT_CLASS,
            "v2_internal_compatibility_classification": COMPAT_CLASS,
            "model_calls": 0, "official_final_admitted": 0})
    with explicit_source_bound_v2_classifier(ctx, frozen):
        v2_result = v2.reconcile_attempt(
            ctx["plan"], ctx["plan_sha256"], ctx["source"],
            ctx["parent_freeze"], ctx["freeze_v2"], ctx["run_dir"], mode="cleanup")
    v2_cleanup, v2_cleanup_sha = read_json(paths["v2_cleanup"])
    require(v2_cleanup.get("case_index") == CASE_INDEX and
            v2_cleanup.get("status") ==
            "exact_pair_retired_for_one_whole_case_retry" and
            v2_cleanup.get("both_containers_absent") is True and
            v2_cleanup.get("audit_sha256") == v2_audit_sha and
            v2_result.get("official_final_admitted") == 0,
            "frozen_v2_exact_pair_cleanup_did_not_complete")
    record = {"schema": "envloop-magento-v2-modal-supplement-cleanup-receipt-v1",
              "case_index": CASE_INDEX,
              "supplement_freeze_sha256": frozen_sha,
              "supplement_cleanup_intent_sha256": intent_sha,
              "v2_cleanup_sha256": v2_cleanup_sha,
              "v2_audit_sha256": v2_audit_sha,
              "both_containers_absent": True,
              "one_same_id_retry_only": True,
              "model_calls": 0, "official_final_admitted": 0}
    if paths["receipt"].exists():
        saved, digest = read_json(paths["receipt"])
        require(saved == record, "existing_supplemental_cleanup_receipt_changed")
    else:
        digest = write_new(paths["receipt"], record)
    return {"status": "exact_pair_retired_one_same_id_retry_available",
            "supplement_cleanup_receipt_sha256": digest,
            "official_final_admitted": 0}


def require_cleanup_lineage(ctx: dict) -> dict:
    frozen, frozen_sha = validate_supplement_freeze(ctx)
    paths = _paths(ctx)
    fresh, fresh_sha = read_json(paths["fresh"])
    intent, intent_sha = read_json(paths["intent"])
    receipt, receipt_sha = read_json(paths["receipt"])
    v2_audit, v2_audit_sha = read_json(paths["v2_audit"])
    v2_cleanup, v2_cleanup_sha = read_json(paths["v2_cleanup"])
    reconciled = [row for row in ctx["events"]
                  if row.get("event") == "attempt_reconciled" and
                  row.get("index") == CASE_INDEX]
    require(len(reconciled) == 1 and
            reconciled[0].get("classification") == COMPAT_CLASS and
            reconciled[0].get("reconciliation_sha256") == v2_cleanup_sha and
            reconciled[0].get("audit_sha256") == v2_audit_sha and
            frozen["original_stopped_journal_sha256"] ==
            ctx["stop"]["journal_sha256"] and
            fresh.get("supplement_freeze_sha256") == frozen_sha and
            fresh.get("material_witness") == ctx["stop"]["material_witness"] and
            intent.get("supplement_freeze_sha256") == frozen_sha and
            intent.get("fresh_audit_sha256") == fresh_sha and
            intent.get("v2_audit_sha256") == v2_audit_sha and
            intent.get("supplemental_classification") == SUPPLEMENT_CLASS and
            receipt.get("supplement_freeze_sha256") == frozen_sha and
            receipt.get("supplement_cleanup_intent_sha256") == intent_sha and
            receipt.get("v2_cleanup_sha256") == v2_cleanup_sha and
            receipt.get("v2_audit_sha256") == v2_audit_sha and
            receipt.get("both_containers_absent") is True and
            v2_audit.get("classification") == COMPAT_CLASS and
            v2_cleanup.get("both_containers_absent") is True and
            receipt.get("model_calls") == receipt.get("official_final_admitted") == 0,
            "supplemental_modal_cleanup_or_v2_reconciliation_lineage_incomplete")
    return {"supplement_freeze_sha256": frozen_sha,
            "supplement_cleanup_receipt_sha256": receipt_sha,
            "first_fourteen_calibration_sha256":
            frozen["first_fourteen_calibration_sha256"],
            "wrapper_source_sha256": frozen["wrapper_source_sha256"],
            "independent_auditor_sha256": frozen["independent_auditor_sha256"]}


def resume(ctx: dict) -> dict:
    require_cleanup_lineage(ctx)
    frozen, _ = validate_supplement_freeze(ctx)
    with explicit_source_bound_v2_classifier(ctx, frozen):
        result = v2.run_campaign(
            ctx["plan"], ctx["plan_sha256"], ctx["source"],
            ctx["parent_freeze"], ctx["freeze_v2"], ctx["run_dir"],
            resume=True)
    require(result.get("official_final_admitted") == 0,
            "v2_resume_claimed_an_official_final_task")
    return {"status": "v2_with_explicit_one_case_modal_supplement_resumed",
            "runner_status": result["status"], "official_final_admitted": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "audit-live",
                                           "cleanup", "resume"))
    for key in ("plan", "source", "parent-freeze", "freeze-v2", "run-dir"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--execute-cleanup", action="store_true")
    parser.add_argument("--execute-resume", action="store_true")
    args = parser.parse_args()
    ctx = context(plan=args.plan, plan_sha256=args.plan_sha256,
                  source=args.source, parent_freeze=args.parent_freeze,
                  freeze_v2=args.freeze_v2, run_dir=args.run_dir)
    if args.action == "prepare":
        result = prepare(ctx)
    elif args.action == "audit-live":
        result = audit_live(ctx)
    elif args.action == "cleanup":
        require(args.execute_cleanup, "explicit_execute_cleanup_required")
        result = cleanup(ctx)
    else:
        require(args.execute_resume, "explicit_execute_resume_required")
        result = resume(ctx)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
