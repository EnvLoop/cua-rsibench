"""Synthetic-only private receipt factory for shared-base protocol tests."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from cursibench import full_study_shared_base_selection_v1 as shared
from cursibench import full_study_selection_environment_v1 as environment


def _write(path: Path, raw: bytes) -> dict:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)
    return {"path": path.name, "sha256": shared._sha(raw)}


def _json(path: Path, value: object) -> dict:
    return _write(path, shared._canonical(value))


def build(study, budget, cell_id: str, *, winning_indices=()) -> Path:
    """Fake provider receipts exercise validation; never model or app calls."""
    receipt_path = shared.receipt_path(study, cell_id)
    if receipt_path.exists():
        return receipt_path
    root = receipt_path.parent
    root.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    (root / "paid").mkdir(mode=0o700)
    cell = next(row for row in study.plan["cells"]
                if row["cell_id"] == cell_id)
    identities = list(study.task_views(cell_id)["selection"])
    checkpoint = cell["base_checkpoint_sha256"]
    environment_category = environment.category(cell_id)
    source_bindings = {**cell["matched_bindings"],
                       "adapter": study.ratification[
                           "cell_profiles"][cell_id]["adapter_sha256"]}
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, "PNG")
    image = stream.getvalue()
    task_rows, score_rows, paid_refs, paid_ids = [], [], [], []
    for index, identity in enumerate(identities):
        task_id = identity["task_id"]
        package = identity["package_sha256"]
        score = int(index in winning_indices)
        folder = root / f"task-{index + 1:03d}"
        folder.mkdir(mode=0o700)
        frame = _write(folder / "frame.png", image)
        frame["path"] = folder.name + "/" + frame["path"]
        artifact = _write(folder / "artifact.bin",
                          ("synthetic saved " + task_id).encode())
        artifact["path"] = folder.name + "/" + artifact["path"]
        common = {"task_id": task_id, "package_sha256": package}
        saved = _json(folder / "saved.json", {
            "schema": shared.SAVED_SCHEMA, **common,
            "readback_performed": True,
            "saved_artifact_ref": artifact,
            "saved_artifact_sha256": artifact["sha256"],
        })
        verifier = _json(folder / "verifier.json", {
            "schema": shared.VERIFIER_SCHEMA, **common,
            "score": score, "independent_of_actor": True,
            "no_regression_checked": True,
            "verifier_sha256": cell["matched_bindings"]["verifier"],
        })
        baseline = _write(folder / "baseline.bin", b"synthetic baseline")
        restored = _write(folder / "restored.bin", b"synthetic baseline")
        baseline["path"] = folder.name + "/" + baseline["path"]
        restored["path"] = folder.name + "/" + restored["path"]
        reset = _json(folder / "reset.json", {
            "schema": shared.RESET_SCHEMA, **common,
            "fresh_environment": True,
            "state_equivalence_pass": True,
            "used_environment_terminated": True,
            "baseline_state_ref": baseline,
            "restored_state_ref": restored,
        })
        trace = _json(folder / "gui-trace.json", {
            "schema": shared.TRACE_SCHEMA, **common,
            "checkpoint_sha256": checkpoint,
            "original_software_gui": True,
            "observation_kind": "screenshot",
            "current_frame_rechecked": True,
            "frame_refs": [frame],
            "model_sample_count": 1,
            "validated_gui_action_count": 1,
        })
        for reference in (saved, verifier, reset, trace):
            reference["path"] = folder.name + "/" + reference["path"]
        tinker_id = f"base-{cell_id}-t-{index + 1:03d}"
        env_id = f"base-{cell_id}-env-{index + 1:03d}"
        task_rows.append({
            **common, "checkpoint_sha256": checkpoint,
            "score": score, "saved_state_ref": saved,
            "verifier_ref": verifier, "reset_ref": reset,
            "gui_trace_ref": trace,
            "tinker_paid_attempt_ids": [tinker_id],
            "environment_paid_attempt_id": env_id,
        })
        score_rows.append({**common, "score": score,
                           "saved_state_sha256": saved["sha256"],
                           "verifier_receipt_sha256": verifier["sha256"],
                           "reset_receipt_sha256": reset["sha256"]})
        for attempt_id, category in ((tinker_id, "tinker"),
                                     (env_id, environment_category)):
            request = {
                "schema": "cua-full-study-shared-base-paid-request-v1",
                "cell_id": cell_id, **common,
                "checkpoint_sha256": checkpoint,
                "split": "selection", "category": category,
                "frame_sha256": (frame["sha256"] if category == "tinker"
                                     else None),
                "runtime_sha256": cell["matched_bindings"]["runtime"],
                "action_profile": "scale-action-profile-v0.6.6",
            }
            request_ref = _json(root / "paid" /
                                f"{attempt_id}.request.json", request)
            request_ref["path"] = "paid/" + request_ref["path"]
            source_ref = _json(root / "paid" /
                               f"{attempt_id}.source.json", {
                "schema": "synthetic-test-usage-source-v1",
                "attempt_id": attempt_id,
                "no_real_provider_call": True})
            source_ref["path"] = "paid/" + source_ref["path"]
            basis = ("self_hosted_nominal_meter" if category ==
                     "storage_application" else "provider_invoice")
            usage_ref = _json(root / "paid" /
                              f"{attempt_id}.usage.json", {
                "schema": shared.USAGE_SCHEMA,
                "attempt_id": attempt_id, "category": category,
                "actual_usd": "0.005", "invoice_basis": basis,
                "provider_invoice_usd": (None if basis ==
                                         "self_hosted_nominal_meter" else
                                         "0.005"),
                "source_ref": source_ref,
            })
            usage_ref["path"] = "paid/" + usage_ref["path"]
            owner = f"{cell_id}:shared-base"
            budget.reserve(attempt_id, owner, category, "0.01",
                           request_ref["sha256"])
            budget.mark_dispatched(attempt_id, request_ref["sha256"])
            budget.settle(attempt_id, "0.005", usage_ref["sha256"])
            paid_ids.append(attempt_id)
            paid_refs.append({"attempt_id": attempt_id,
                              "category": category,
                              "request_ref": request_ref,
                              "usage_ref": usage_ref})
    result_ref = _json(root / "selection-result.private.json", {
        "schema": "cua-full-study-selection-saved-result-v1",
        "cell_id": cell_id,
        "checkpoint_sha256": checkpoint,
        "evaluator_isolated": True, "tasks": score_rows,
    })
    ledger_ref = _json(root / "task-ledger.private.json", {
        "schema": shared.LEDGER_SCHEMA, "cell_id": cell_id,
        "checkpoint_sha256": checkpoint,
        "selection_identities_sha256":
            cell["selection_identities_sha256"],
        "task_count": 20, "tasks": task_rows,
    })
    _json(receipt_path, {
        "schema": shared.RECEIPT_SCHEMA,
        "study_id": study.plan["study_id"],
        "cell_id": cell_id,
        "plan_sha256": study.plan_sha256,
        "base_manifest_sha256": cell["base_manifest_sha256"],
        "base_checkpoint_sha256": checkpoint,
        "selection_identities_sha256":
            cell["selection_identities_sha256"],
        "action_profile": "scale-action-profile-v0.6.6",
        "source_bindings": source_bindings,
        "original_software_gui": True,
        "evaluator_isolated": True,
        "result_ref": result_ref,
        "task_ledger_ref": ledger_ref,
        "paid_attempt_refs": paid_refs,
        "paid_attempt_ids": paid_ids,
        "environment_category": environment_category,
        "official_final_tasks_observed": 0,
    })
    return receipt_path
