"""One source-bound, independently scored base-selection receipt per cell.

The six base selections are evaluated once, before four researcher campaigns
per cell consume their feedback. This module is a verifier and admission gate,
not a model, browser, or billing dispatcher. It never opens a final package.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import json
import os
from pathlib import Path

from . import full_study_matrix_v1 as matrix
from . import full_study_selection_environment_v1 as environment
from . import scale_final_v06 as cell_final


RECEIPT_SCHEMA = "cua-full-study-shared-base-selection-receipt-v1"
LEDGER_SCHEMA = "cua-full-study-shared-base-selection-task-ledger-v1"
SAVED_SCHEMA = "cua-full-study-shared-base-saved-state-v1"
VERIFIER_SCHEMA = "cua-full-study-shared-base-verifier-v1"
RESET_SCHEMA = "cua-full-study-shared-base-reset-v1"
TRACE_SCHEMA = "cua-full-study-shared-base-gui-trace-v1"
USAGE_SCHEMA = "cua-full-study-shared-base-usage-v1"
REGISTRY_SCHEMA = "cua-full-study-shared-base-selection-registry-v1"
MAX_BYTES = 16_000_000


class SharedBaseSelectionError(ValueError):
    """Fixed failure labels; private task data never enters error messages."""


def _require(value: bool, code: str) -> None:
    if not value:
        raise SharedBaseSelectionError(code)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash(value: object) -> bool:
    return (type(value) is str and len(value) == 64 and
            all(character in "0123456789abcdef" for character in value))


def _amount(value: object) -> Decimal:
    if type(value) is not str:
        raise SharedBaseSelectionError("base_selection_amount_invalid")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise SharedBaseSelectionError("base_selection_amount_invalid") from None
    _require(result.is_finite() and result >= 0 and
             -result.as_tuple().exponent <= 9,
             "base_selection_amount_invalid")
    return result


def receipt_path(study, cell_id: str) -> Path:
    _require(cell_id in matrix.CELLS, "base_selection_cell_invalid")
    return (Path(study.repo_root) / "work" / "shared-base-selection" /
            cell_id / "receipt.private.json")


def _private_bytes(path: Path, root: Path) -> bytes:
    target = Path(path)
    _require(target.is_file() and not target.is_symlink() and
             target.resolve().is_relative_to(root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             0 < target.stat().st_size <= MAX_BYTES,
             "base_selection_private_evidence_missing_or_unsafe")
    return target.read_bytes()


def _private_json(path: Path, root: Path) -> tuple[dict, bytes]:
    raw = _private_bytes(path, root)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SharedBaseSelectionError(
            "base_selection_private_json_invalid") from None
    _require(type(value) is dict, "base_selection_private_object_required")
    return value, raw


def _reference(root: Path, reference: object,
               *, suffix: str | None = None) -> tuple[Path, bytes]:
    _require(type(reference) is dict and
             set(reference) == {"path", "sha256"} and
             type(reference["path"]) is str and
             _hash(reference["sha256"]),
             "base_selection_reference_invalid")
    relative = Path(reference["path"])
    _require(not relative.is_absolute() and
             all(part not in {"", ".", ".."} for part in relative.parts) and
             len(relative.parts) <= 3 and
             (suffix is None or relative.suffix == suffix),
             "base_selection_reference_unsafe")
    target = root / relative
    raw = _private_bytes(target, root)
    _require(_sha(raw) == reference["sha256"],
             "base_selection_reference_bytes_changed")
    return target, raw


def _json_ref(root: Path, reference: object) -> tuple[dict, bytes]:
    _, raw = _reference(root, reference, suffix=".json")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SharedBaseSelectionError("base_selection_reference_json_invalid") from None
    _require(type(value) is dict, "base_selection_reference_object_required")
    return value, raw


def _cell(study, cell_id: str) -> dict:
    rows = [row for row in study.plan["cells"]
            if row["cell_id"] == cell_id]
    _require(len(rows) == 1, "base_selection_frozen_cell_missing")
    return rows[0]


def _task_evidence(root: Path, identity: dict, checkpoint: str,
                   row: dict, result_row: dict,
                   bindings: dict) -> tuple[list[str], str]:
    fields = {"task_id", "package_sha256", "checkpoint_sha256", "score",
              "saved_state_ref", "verifier_ref", "reset_ref",
              "gui_trace_ref", "tinker_paid_attempt_ids",
              "environment_paid_attempt_id"}
    _require(type(row) is dict and set(row) == fields and
             row["task_id"] == identity["task_id"] and
             row["package_sha256"] == identity["package_sha256"] and
             row["checkpoint_sha256"] == checkpoint and
             type(row["score"]) is int and row["score"] in (0, 1) and
             result_row == {
                 "task_id": row["task_id"],
                 "package_sha256": row["package_sha256"],
                 "score": row["score"],
                 "saved_state_sha256": row["saved_state_ref"]["sha256"],
                 "verifier_receipt_sha256": row["verifier_ref"]["sha256"],
                 "reset_receipt_sha256": row["reset_ref"]["sha256"]},
             "base_selection_task_or_saved_result_unbound")
    common = {"task_id": row["task_id"],
              "package_sha256": row["package_sha256"]}
    saved, _ = _json_ref(root, row["saved_state_ref"])
    _require(saved == {
        "schema": SAVED_SCHEMA, **common,
        "readback_performed": True,
        "saved_artifact_ref": saved.get("saved_artifact_ref"),
        "saved_artifact_sha256": saved.get("saved_artifact_sha256"),
    } and _hash(saved["saved_artifact_sha256"]) and
             saved["saved_artifact_ref"]["sha256"] ==
             saved["saved_artifact_sha256"],
             "base_selection_saved_state_not_independent")
    _reference(root, saved["saved_artifact_ref"])
    verifier, _ = _json_ref(root, row["verifier_ref"])
    _require(verifier == {
        "schema": VERIFIER_SCHEMA, **common,
        "score": row["score"],
        "independent_of_actor": True,
        "no_regression_checked": True,
        "verifier_sha256": bindings["verifier"],
    }, "base_selection_verifier_not_independent")
    reset, _ = _json_ref(root, row["reset_ref"])
    _require(type(reset) is dict and set(reset) == {
        "schema", "task_id", "package_sha256", "fresh_environment",
        "state_equivalence_pass", "used_environment_terminated",
        "baseline_state_ref", "restored_state_ref"} and
        reset["schema"] == RESET_SCHEMA and
        all(reset.get(key) == value for key, value in common.items()) and
        reset["fresh_environment"] is True and
        reset["state_equivalence_pass"] is True and
        reset["used_environment_terminated"] is True,
        "base_selection_reset_not_exact")
    _, baseline = _reference(root, reset["baseline_state_ref"])
    _, restored = _reference(root, reset["restored_state_ref"])
    _require(baseline == restored and bool(baseline),
             "base_selection_reset_bytes_differ")
    trace, _ = _json_ref(root, row["gui_trace_ref"])
    _require(type(trace) is dict and set(trace) == {
        "schema", "task_id", "package_sha256", "checkpoint_sha256",
        "original_software_gui", "observation_kind",
        "current_frame_rechecked", "frame_refs",
        "model_sample_count", "validated_gui_action_count"} and
        trace["schema"] == TRACE_SCHEMA and
        all(trace.get(key) == value for key, value in common.items()) and
        trace["checkpoint_sha256"] == checkpoint and
        trace["original_software_gui"] is True and
        trace["observation_kind"] == "screenshot" and
        trace["current_frame_rechecked"] is True and
        type(trace["frame_refs"]) is list and trace["frame_refs"] and
        type(trace["model_sample_count"]) is int and
        trace["model_sample_count"] >= 1 and
        type(trace["validated_gui_action_count"]) is int and
        0 <= trace["validated_gui_action_count"] <=
        trace["model_sample_count"],
        "base_selection_gui_trace_missing")
    for frame in trace["frame_refs"]:
        _, image = _reference(root, frame, suffix=".png")
        _require(image.startswith(b"\x89PNG\r\n\x1a\n"),
                 "base_selection_frame_not_png")
    tinker_ids = row["tinker_paid_attempt_ids"]
    environment_id = row["environment_paid_attempt_id"]
    _require(type(tinker_ids) is list and tinker_ids and
             len(tinker_ids) == len(set(tinker_ids)) and
             all(type(item) is str and item for item in tinker_ids) and
             type(environment_id) is str and environment_id,
             "base_selection_paid_task_coverage_missing")
    return tinker_ids, environment_id


def verify_receipt(study, budget, cell_id: str, source: Path,
                   *, require_registry: bool = True) -> tuple[dict, str]:
    """Reopen every task artifact and settled paid attempt before feedback."""
    expected_path = receipt_path(study, cell_id)
    work = Path(study.repo_root) / "work"
    _require(Path(source).absolute() == expected_path.absolute() and
             work.is_dir() and not work.is_symlink() and
             expected_path.parent.is_dir() and
             not expected_path.parent.is_symlink() and
             expected_path.parent.stat().st_mode & 0o077 == 0 and
             expected_path.parent.resolve().is_relative_to(work.resolve()) and
             getattr(budget, "plan_sha256", None) == study.plan_sha256,
             "base_selection_receipt_path_or_directory_invalid")
    root = expected_path.parent
    receipt, raw = _private_json(expected_path, root)
    digest = _sha(raw)
    cell = _cell(study, cell_id)
    expected = {"schema", "study_id", "cell_id", "plan_sha256",
                "base_manifest_sha256", "base_checkpoint_sha256",
                "selection_identities_sha256", "action_profile",
                "source_bindings", "original_software_gui",
                "evaluator_isolated", "result_ref", "task_ledger_ref",
                "paid_attempt_refs", "paid_attempt_ids",
                "environment_category", "official_final_tasks_observed"}
    bindings = cell["matched_bindings"]
    profile = study.ratification["cell_profiles"][cell_id]
    source_bindings = {**bindings,
                       "adapter": profile["adapter_sha256"]}
    _require(type(receipt) is dict and set(receipt) == expected and
             receipt["schema"] == RECEIPT_SCHEMA and
             receipt["study_id"] == study.plan["study_id"] and
             receipt["cell_id"] == cell_id and
             receipt["plan_sha256"] == study.plan_sha256 and
             receipt["base_manifest_sha256"] ==
             cell["base_manifest_sha256"] and
             receipt["base_checkpoint_sha256"] ==
             cell["base_checkpoint_sha256"] and
             receipt["selection_identities_sha256"] ==
             cell["selection_identities_sha256"] and
             receipt["action_profile"] ==
             "scale-action-profile-v0.6.6" and
             receipt["source_bindings"] == source_bindings and
             receipt["original_software_gui"] is True and
             receipt["evaluator_isolated"] is True and
             receipt["environment_category"] ==
             environment.category(cell_id) and
             receipt["official_final_tasks_observed"] == 0,
             "base_selection_frozen_source_or_original_gui_unbound")
    selection = list(study.task_views(cell_id)["selection"])
    _require(len(selection) == matrix.SELECTION_PER_CELL and
             _sha(cell_final.json_bytes(selection)) ==
             receipt["selection_identities_sha256"],
             "base_selection_frozen_task_view_changed")
    result, _ = _json_ref(root, receipt["result_ref"])
    _require(type(result) is dict and set(result) == {
        "schema", "cell_id", "checkpoint_sha256", "evaluator_isolated",
        "tasks"} and
        result["schema"] == "cua-full-study-selection-saved-result-v1" and
        result["cell_id"] == cell_id and
        result["checkpoint_sha256"] == cell["base_checkpoint_sha256"] and
        result["evaluator_isolated"] is True and
        type(result["tasks"]) is list and
        len(result["tasks"]) == matrix.SELECTION_PER_CELL,
        "base_selection_result_shape_or_checkpoint_invalid")
    ledger, _ = _json_ref(root, receipt["task_ledger_ref"])
    _require(type(ledger) is dict and set(ledger) == {
        "schema", "cell_id", "checkpoint_sha256",
        "selection_identities_sha256", "task_count", "tasks"} and
        ledger["schema"] == LEDGER_SCHEMA and ledger["cell_id"] == cell_id and
        ledger["checkpoint_sha256"] == cell["base_checkpoint_sha256"] and
        ledger["selection_identities_sha256"] ==
        cell["selection_identities_sha256"] and
        ledger["task_count"] == matrix.SELECTION_PER_CELL and
        type(ledger["tasks"]) is list and len(ledger["tasks"]) ==
        matrix.SELECTION_PER_CELL,
        "base_selection_task_ledger_shape_invalid")
    expected_paid = []
    paid_binding = {}
    for identity, row, score_row in zip(selection, ledger["tasks"],
                                        result["tasks"]):
        tinker_ids, environment_id = _task_evidence(
            root, identity, cell["base_checkpoint_sha256"],
            row, score_row, bindings)
        for attempt_id in tinker_ids:
            expected_paid.append(attempt_id)
            paid_binding[attempt_id] = (identity, "tinker", row)
        expected_paid.append(environment_id)
        paid_binding[environment_id] = (
            identity, environment.category(cell_id), row)
    _require(len(expected_paid) == len(set(expected_paid)) and
             receipt["paid_attempt_ids"] == expected_paid and
             type(receipt["paid_attempt_refs"]) is list and
             len(receipt["paid_attempt_refs"]) == len(expected_paid),
             "base_selection_paid_task_attempts_not_unique")
    records = budget.owner_attempts(f"{cell_id}:shared-base")
    selection_records = {attempt_id: record for attempt_id, record in
                         records.items() if record["category"] !=
                         "shared_base_final"}
    _require(set(selection_records) == set(expected_paid),
             "base_selection_paid_budget_attempts_unmatched")
    seen_paid = set()
    for paid in receipt["paid_attempt_refs"]:
        _require(type(paid) is dict and set(paid) == {
            "attempt_id", "category", "request_ref", "usage_ref"} and
            paid["attempt_id"] in paid_binding and
            paid["attempt_id"] not in seen_paid,
            "base_selection_paid_record_duplicate_or_unknown")
        attempt_id = paid["attempt_id"]
        seen_paid.add(attempt_id)
        identity, category, task_row = paid_binding[attempt_id]
        budget_row = selection_records[attempt_id]
        request, request_raw = _json_ref(root, paid["request_ref"])
        usage, usage_raw = _json_ref(root, paid["usage_ref"])
        expected_request = {
            "schema": "cua-full-study-shared-base-paid-request-v1",
            "cell_id": cell_id, "task_id": identity["task_id"],
            "package_sha256": identity["package_sha256"],
            "checkpoint_sha256": cell["base_checkpoint_sha256"],
            "split": "selection", "category": category,
            "frame_sha256": request.get("frame_sha256"),
            "runtime_sha256": bindings["runtime"],
            "action_profile": "scale-action-profile-v0.6.6",
        }
        trace, _ = _json_ref(root, task_row["gui_trace_ref"])
        frame_shas = {ref["sha256"] for ref in trace["frame_refs"]}
        _require(
            paid["category"] == category and
            request == expected_request and
            ((category == "tinker" and
              request["frame_sha256"] in frame_shas) or
             (category != "tinker" and
              request["frame_sha256"] is None)) and
            budget_row["category"] == category and
            budget_row["status"] == "settled" and
            budget_row["request_sha256"] == _sha(request_raw) and
            budget_row["work_sha256"] == _sha(request_raw) and
            budget_row["evidence_sha256"] == _sha(usage_raw),
            "base_selection_paid_request_or_budget_not_bound")
        basis = ("self_hosted_nominal_meter" if category ==
                 "storage_application" else "provider_invoice")
        invoice = (None if basis == "self_hosted_nominal_meter" else
                   usage.get("actual_usd"))
        _require(type(usage) is dict and set(usage) == {
            "schema", "attempt_id", "category", "actual_usd",
            "invoice_basis", "provider_invoice_usd",
            "source_ref"} and
            usage["schema"] == USAGE_SCHEMA and
            usage["attempt_id"] == attempt_id and
            usage["category"] == category and
            usage["invoice_basis"] == basis and
            usage["provider_invoice_usd"] == invoice and
            _amount(usage["actual_usd"]) ==
            _amount(budget_row["actual_usd"]) and
            _amount(usage["actual_usd"]) <=
            _amount(budget_row["reserved_usd"]),
            "base_selection_paid_usage_or_invoice_invalid")
        _reference(root, usage["source_ref"])
    _require(seen_paid == set(expected_paid),
             "base_selection_paid_records_incomplete")
    if require_registry:
        marker, _ = _private_json(root / "accepted.private.json", root)
        _require(marker == {
            "schema": REGISTRY_SCHEMA, "cell_id": cell_id,
            "receipt_sha256": digest},
            "base_selection_shared_receipt_registry_changed")
    return result, digest


def admit_receipt(study, budget, cell_id: str, source: Path) -> dict:
    """Write one accepted digest; all four campaigns import this same byte set."""
    result, digest = verify_receipt(
        study, budget, cell_id, source, require_registry=False)
    root = receipt_path(study, cell_id).parent
    marker_path = root / "accepted.private.json"
    lock_path = root / ".accepted.lock"
    _require(not lock_path.is_symlink(),
             "base_selection_shared_registry_lock_unsafe")
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = {"schema": REGISTRY_SCHEMA, "cell_id": cell_id,
                  "receipt_sha256": digest}
        raw = _canonical(marker)
        if marker_path.exists():
            _require(not marker_path.is_symlink() and
                     _private_bytes(marker_path, root) == raw,
                     "base_selection_shared_receipt_already_different")
        else:
            fd = os.open(marker_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
    return {"cell_id": cell_id, "shared_receipt_sha256": digest,
            "task_count": matrix.SELECTION_PER_CELL,
            "wins": sum(row["score"] for row in result["tasks"]),
            "researcher_campaigns": 0}
