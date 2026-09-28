"""Synthetic-only private receipt factory for shared-base protocol tests."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from cursibench import full_study_shared_base_selection_v1 as shared
from cursibench import full_study_selection_environment_v1 as environment
from cursibench import full_study_selection_paid_coverage_v1 as paid_coverage
from cursibench.scale_vision_proxy import MODEL
from cursibench import full_study_shared_base_execution_v1 as execution


def _write(path: Path, raw: bytes) -> dict:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)
    return {"path": path.name, "sha256": shared._sha(raw)}


def _json(path: Path, value: object) -> dict:
    return _write(path, shared._canonical(value))


def build(study, budget, cell_id: str, *, winning_indices=(),
          environment_batch: bool = False,
          tinker_setup: bool = False) -> Path:
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
    selection_attempt = "base-selection-" + cell_id
    coverage_identities_sha = shared._sha(shared._canonical(identities))
    environment_category = environment.category(cell_id)
    source_bindings = {**cell["matched_bindings"],
                       "adapter": study.ratification[
                           "cell_profiles"][cell_id]["adapter_sha256"]}
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, "PNG")
    image = stream.getvalue()
    task_rows, score_rows, paid_refs, paid_ids, paid_calls = [], [], [], [], []

    def add_paid(attempt_id: str, category: str, *, task_id=None,
                 package_sha256=None, frame_sha256=None,
                 selection_tasks=None) -> None:
        worker_request = {
            "cell_id": cell_id,
            "selection_attempt": selection_attempt,
            "selection_tasks": selection_tasks,
            "task_id": task_id,
            "package_sha256": package_sha256,
            "checkpoint_path_sha256": checkpoint,
            "frame_sha256": frame_sha256,
        }
        if category == "tinker" and task_id is not None:
            worker_request["image_base64"] = base64.b64encode(image).decode()
        if category == "tinker" and cell_id == "odoo-community":
            worker_request["sampling_kind"] = "base"
            if task_id is None:
                worker_request["model"] = MODEL
        worker_request_ref = _json(root / "paid" /
                                   f"{attempt_id}.worker-request.json",
                                   worker_request)
        worker_request_ref["path"] = "paid/" + worker_request_ref["path"]
        request = {
            "schema": "cua-full-study-shared-base-paid-request-v1",
            "cell_id": cell_id,
            "selection_attempt": selection_attempt,
            "selection_identities_sha256": coverage_identities_sha,
            "selection_tasks": selection_tasks,
            "task_id": task_id,
            "package_sha256": package_sha256,
            "checkpoint_path_sha256": checkpoint,
            "base_model": MODEL,
            "split": "selection", "category": category,
            "frame_sha256": frame_sha256,
            "runtime_sha256": cell["matched_bindings"]["runtime"],
            "action_profile": "scale-action-profile-v0.6.6",
            "worker_request_ref": worker_request_ref,
            **({"qwen_runtime": {
                "runtime_spec_sha256": "d" * 64,
                "toy_public_receipt_sha256": "e" * 64,
                "runtime_gate_source_sha256": "f" * 64,
            }} if category == "tinker" else {}),
        }
        request_ref = _json(root / "paid" /
                            f"{attempt_id}.request.json", request)
        request_ref["path"] = "paid/" + request_ref["path"]
        result_status = ("completed" if category == "tinker" and
                         task_id is not None else
                         "ready" if category == "tinker" else "active")
        worker_result_ref = _json(root / "paid" /
                                  f"{attempt_id}.worker-result.json", {
            "status": result_status,
            **({"reported_model": MODEL} if
               category == "tinker" and cell_id == "gitlab" and
               task_id is not None else {}),
            "synthetic_fake_provider": True,
        })
        worker_result_ref["path"] = "paid/" + worker_result_ref["path"]
        result_ref = _json(root / "paid" /
                           f"{attempt_id}.result.json", {
            "schema": shared.PAID_RESULT_SCHEMA,
            "attempt_id": attempt_id,
            "category": category,
            "status": result_status,
            "selection_attempt": selection_attempt,
            "task_id": task_id,
            "checkpoint_path_sha256": checkpoint,
            "worker_result_ref": worker_result_ref,
        })
        result_ref["path"] = "paid/" + result_ref["path"]
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
                          "result_ref": result_ref,
                          "usage_ref": usage_ref})
        paid_calls.append({"attempt_id": attempt_id,
                           "category": category,
                           "request": request,
                           "result_present": True,
                           "result_status": result_status})
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
            "native_save_observed": True,
            "saved_artifact_ref": artifact,
            "saved_artifact_sha256": artifact["sha256"],
        })
        verifier = _json(folder / "verifier.json", {
            "schema": shared.VERIFIER_SCHEMA, **common,
            "score": score, "independent_of_actor": True,
            "target_state_pass": bool(score),
            "no_regression_checked": True,
            "no_regression_pass": True,
            "evaluated_saved_artifact_sha256": artifact["sha256"],
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
        action_trace = _json(folder / "actions.json", [{
            "step": 0, "frame_sha256": frame["sha256"],
            "model_result_sha256": shared._sha(
                ("synthetic model result " + task_id).encode()),
            "action_type": "finish",
            "current_frame_checked": True,
        }])
        action_trace["path"] = folder.name + "/" + action_trace["path"]
        trace = _json(folder / "gui-trace.json", {
            "schema": shared.TRACE_SCHEMA, **common,
            "checkpoint_sha256": checkpoint,
            "original_software_gui": True,
            "observation_kind": "screenshot",
            "current_frame_rechecked": True,
            "frame_refs": [frame],
            "action_trace_ref": action_trace,
            "model_sample_count": 1,
            "validated_gui_action_count": 1,
        })
        for reference in (saved, verifier, reset, trace):
            reference["path"] = folder.name + "/" + reference["path"]
        native = _json(folder / "native-worker.json", {
            **common, "score": score,
            "saved_state_sha256": artifact["sha256"],
            "baseline_semantic_sha256": baseline["sha256"],
            "restored_semantic_sha256": restored["sha256"],
            "synthetic_worker_evidence_only": True,
        })
        native["path"] = folder.name + "/" + native["path"]
        tinker_id = selection_attempt + f"-sample-{index + 1:03d}"
        env_id = (selection_attempt + "-env-batch" if environment_batch else
                  selection_attempt + f"-env-{index + 1:03d}")
        task_rows.append({
            **common, "checkpoint_sha256": checkpoint,
            "score": score, "saved_state_ref": saved,
            "verifier_ref": verifier, "reset_ref": reset,
            "gui_trace_ref": trace, "native_worker_ref": native,
            "tinker_paid_attempt_ids": [tinker_id],
            "environment_paid_attempt_id": env_id,
        })
        score_rows.append({**common, "score": score,
                           "saved_state_sha256": saved["sha256"],
                           "verifier_receipt_sha256": verifier["sha256"],
                           "reset_receipt_sha256": reset["sha256"]})
        add_paid(tinker_id, "tinker", task_id=task_id,
                 package_sha256=package,
                 frame_sha256=frame["sha256"])
        if not environment_batch:
            add_paid(env_id, environment_category,
                     task_id=task_id, package_sha256=package)
    if tinker_setup:
        add_paid(selection_attempt + "-sampler-setup", "tinker")
    if environment_batch:
        add_paid(selection_attempt + "-env-batch",
                 environment_category, selection_tasks=identities)
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
    fake_native_ledger = _json(root / "native-task-ledger.json", {
        "cell_id": cell_id, "rows": [
            {"task_id": row["task_id"],
             "package_sha256": row["package_sha256"],
             "score": row["score"]} for row in task_rows],
        "synthetic_worker_evidence_only": True,
    })
    native_sources = {"native_task_ledger_ref": fake_native_ledger}
    if cell_id == "gitlab":
        native_sources["native_batch_ref"] = _json(
            root / "native-gitlab-batch.json", {
                "cell_id": cell_id, "task_count": 20,
                "synthetic_worker_evidence_only": True})
    if cell_id == "odoo-community":
        native_sources["native_runtime_ref"] = _json(
            root / "native-odoo-runtime.json", {
                "services_restored_to_initial_state": True,
                "final_database_snapshot_equal": True,
                "final_physical_filestore_equal": True,
                "synthetic_worker_evidence_only": True})
    native_batch_ref = _json(root / "native-batch.private.json", {
        "schema": "cua-full-study-shared-base-native-batch-v1",
        "cell_id": cell_id, "checkpoint_sha256": checkpoint,
        "task_count": 20, "native_source_refs": native_sources,
    })
    coverage = paid_coverage.validate(
        cell_id=cell_id, attempt_id=selection_attempt,
        checkpoint_sha256=checkpoint,
        selection_tasks=identities,
        selection_identities_sha256=coverage_identities_sha,
        paid_calls=paid_calls,
        related_paid_attempt_ids=set(paid_ids))
    _json(receipt_path, {
        "schema": shared.RECEIPT_SCHEMA,
        "study_id": study.plan["study_id"],
        "cell_id": cell_id,
        "plan_sha256": study.plan_sha256,
        "base_manifest_sha256": cell["base_manifest_sha256"],
        "base_checkpoint_sha256": checkpoint,
        "base_model": MODEL,
        "base_freeze_receipt_sha256": execution._verify_base_freeze(
            study, cell)["freeze_receipt_sha256"],
        "selection_identities_sha256":
            cell["selection_identities_sha256"],
        "action_profile": "scale-action-profile-v0.6.6",
        "source_bindings": source_bindings,
        "original_software_gui": True,
        "evaluator_isolated": True,
        "result_ref": result_ref,
        "task_ledger_ref": ledger_ref,
        "native_batch_ref": native_batch_ref,
        "executor_source_sha256": shared._sha(
            Path(shared.__file__).with_name(
                "full_study_shared_base_execution_v1.py").read_bytes()),
        "paid_attempt_refs": paid_refs,
        "paid_attempt_ids": paid_ids,
        "environment_category": environment_category,
        "selection_attempt": selection_attempt,
        "paid_coverage_sha256": coverage["coverage_sha256"],
        "official_final_tasks_observed": 0,
    })
    return receipt_path
