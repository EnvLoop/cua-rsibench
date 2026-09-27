"""One-time shared-base 20-task selection execution under its own budget owner.

This controller never opens a final task. Cell workers drive original software
and return private native evidence. Every worker callback is reserved and
hashed before dispatch; invoice/local-meter reconciliation is required before
the strict shared-base receipt can be admitted. Live execution remains gated
by the frozen six-cell study and a cell-owned worker implementation.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Callable

from . import full_study_budget_v1 as dollars
from . import full_study_matrix_v1 as matrix
from . import full_study_selection_environment_v1 as environment
from . import full_study_shared_base_selection_v1 as shared
from . import full_study_selection_paid_coverage_v1 as paid_coverage
from . import scale_final_v06 as cell_final
from .scale_vision_proxy import MODEL, TinkerVisionBackend, digest as vision_digest
from .scale_final_v06 import is_hash


SCHEMA = "cua-full-study-shared-base-execution-v1"
ATTEMPT_PREFIX = "base-selection-"
MAX_PRIVATE_BYTES = 16_000_000


class SharedBaseExecutionError(ValueError):
    """Fixed local labels; never include private tasks or provider response."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise SharedBaseExecutionError(code)


def _canonical(value: object) -> bytes:
    return shared._canonical(value)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _money(value: object) -> Decimal:
    _require(type(value) is str, "shared_base_amount_invalid")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise SharedBaseExecutionError("shared_base_amount_invalid") from None
    _require(amount.is_finite() and amount >= 0 and
             -amount.as_tuple().exponent <= 9,
             "shared_base_amount_invalid")
    return amount


def _write_new(path: Path, raw: bytes) -> dict:
    _require(not path.exists() and not path.is_symlink() and
             0 < len(raw) <= MAX_PRIVATE_BYTES and
             path.parent.is_dir() and not path.parent.is_symlink() and
             path.parent.stat().st_mode & 0o077 == 0,
             "shared_base_private_output_unsafe")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": path.name, "sha256": _sha(raw)}


def _verify_base_freeze(study, cell: dict) -> dict:
    """Reopen the cell's preregistered base checkpoint freeze receipt."""
    entries = [row for row in study.manifest["cells"]
               if row["cell_id"] == cell["cell_id"]]
    _require(len(entries) == 1,
             "shared_base_manifest_missing")
    manifest_path, raw = cell_final.evidence_file(
        Path(study.manifest_path).parent, entries[0]["base_manifest"],
        "shared base manifest")
    _require(_sha(raw) == cell["base_manifest_sha256"],
             "shared_base_manifest_changed")
    manifest = json.loads(raw)
    checkpoint = manifest["bindings"]["checkpoint"]
    _require(checkpoint["model"] == MODEL and
             checkpoint["sha256"] == cell["base_checkpoint_sha256"],
             "shared_base_checkpoint_model_or_binding_changed")
    _, freeze_raw = cell_final.evidence_file(
        manifest_path.parent, checkpoint["freeze_receipt"],
        "shared base checkpoint freeze receipt")
    freeze = json.loads(freeze_raw)
    _require(freeze == {
        "schema": cell_final.FREEZE_SCHEMA,
        "cell_id": cell["cell_id"],
        "researcher_id": "shared-base",
        "role": "base",
        "checkpoint_sha256": cell["base_checkpoint_sha256"],
        "selection_frozen": True,
    }, "shared_base_checkpoint_freeze_receipt_changed")
    return {"path": str(manifest_path),
            "manifest_sha256": _sha(raw),
            "freeze_receipt_sha256": _sha(freeze_raw)}


class SharedBaseSession:
    """A small cell-owned budget/observation session, never a researcher."""

    def __init__(self, study, cell_id: str):
        _require(cell_id in matrix.CELLS and
                 hasattr(study, "ratification") and
                 hasattr(study, "public_witness_sha256") and
                 is_hash(study.public_witness_sha256),
                 "shared_base_real_six_cell_freeze_required")
        self.study = study
        self.cell_id = cell_id
        self.cell = next(row for row in study.plan["cells"]
                         if row["cell_id"] == cell_id)
        self.base_freeze = _verify_base_freeze(study, self.cell)
        self.owner = cell_id + ":shared-base"
        self.attempt_id = ATTEMPT_PREFIX + cell_id
        views = study.task_views(cell_id)
        self.views = {"train": list(views["train"]),
                      "selection": list(views["selection"])}
        selection = list(self.views["selection"])
        _require(len(selection) == matrix.SELECTION_PER_CELL and
                 len({row["task_id"] for row in selection}) ==
                 matrix.SELECTION_PER_CELL and
                 _sha(cell_final.json_bytes(selection)) ==
                 self.cell["selection_identities_sha256"],
                 "shared_base_selection_view_changed")
        self.started = {
            "attempt_id": self.attempt_id,
            "checkpoint_path_sha256": self.cell[
                "base_checkpoint_sha256"],
            "selection_tasks": selection,
            "selection_identities_sha256": _sha(_canonical(selection)),
            "task_count": matrix.SELECTION_PER_CELL,
        }
        self.intent = {
            "cell_id": cell_id, "researcher_id": "shared-base",
            "storage_application_usd_cap":
                self.cell["base_selection_cost_upper_bound_usd"],
            "e2b_usd_cap": self.cell[
                "base_selection_cost_upper_bound_usd"],
        }
        self.directory = shared.receipt_path(study, cell_id).parent
        work = Path(study.repo_root) / "work"
        _require(work.is_dir() and not work.is_symlink() and
                 not self.directory.exists() and
                 self.directory.resolve().is_relative_to(work.resolve()),
                 "shared_base_cell_execution_already_exists")
        self.directory.mkdir(mode=0o700, parents=True)
        self.directory.chmod(0o700)
        (self.directory / "paid").mkdir(mode=0o700)
        self.budget = dollars.StudyBudgetLedger(
            work / "full-study-budget.jsonl", study.plan)
        _require(self.owner in self.budget.limits and
                 not self.budget.owner_attempts(self.owner),
                 "shared_base_prior_paid_attempts_require_reconciliation")
        self.started_at = time.monotonic()
        self.completed_paid: dict[str, dict] = {}

    def _events(self, kind: str):
        if kind == "selection_started":
            return [{"data": {**self.started,
                              "selection_tasks": None}}]
        return []

    def _train_context(self, _path):
        raise SharedBaseExecutionError("shared_base_train_context_forbidden")

    def _check_time(self) -> None:
        _require(time.monotonic() - self.started_at <=
                 matrix.CAMPAIGN_HOURS * 3600,
                 "shared_base_selection_time_exhausted")

    def _envelope(self, *, attempt_id: str, category: str,
                  worker_request: dict,
                  worker_request_ref: dict) -> dict:
        task_id = worker_request.get("task_id")
        by_id = {row["task_id"]: row["package_sha256"]
                 for row in self.started["selection_tasks"]}
        if task_id is not None:
            _require(task_id in by_id and
                     worker_request.get("package_sha256") ==
                     by_id[task_id] and
                     worker_request.get("checkpoint_path_sha256") ==
                     self.started["checkpoint_path_sha256"],
                     "shared_base_worker_task_or_checkpoint_changed")
        elif category == "tinker":
            _require(worker_request.get("checkpoint_path_sha256") ==
                     self.started["checkpoint_path_sha256"],
                     "shared_base_sampler_setup_unbound")
        else:
            _require(worker_request.get("selection_tasks") ==
                     self.started["selection_tasks"] and
                     worker_request.get("selection_identities_sha256") ==
                     self.started["selection_identities_sha256"],
                     "shared_base_environment_batch_unbound")
        frame_sha = worker_request.get("frame_sha256")
        _require((frame_sha is None if category != "tinker" else
                  task_id is None or is_hash(frame_sha)),
                 "shared_base_worker_frame_unbound")
        return {
            "schema": "cua-full-study-shared-base-paid-request-v1",
            "cell_id": self.cell_id,
            "selection_attempt": self.attempt_id,
            "selection_identities_sha256": self.started[
                "selection_identities_sha256"],
            "selection_tasks": (self.started["selection_tasks"] if
                                task_id is None and category != "tinker" else
                                None),
            "task_id": task_id,
            "package_sha256": by_id[task_id] if task_id is not None else None,
            "checkpoint_path_sha256": self.started[
                "checkpoint_path_sha256"],
            "base_model": MODEL,
            "split": "selection", "category": category,
            "frame_sha256": frame_sha,
            "runtime_sha256": self.cell["matched_bindings"]["runtime"],
            "action_profile": "scale-action-profile-v0.6.6",
            "worker_request_ref": worker_request_ref,
        }

    def dispatch_paid(self, *, attempt_id: str, category: str,
                      work: object, request: object, reserve_usd: str,
                      resource_reservation: dict[str, str],
                      provider: Callable[[object], object]) -> dict:
        """Reserve the exact worker request once; never replay uncertainty."""
        self._check_time()
        _require(type(attempt_id) is str and
                 attempt_id.startswith(self.attempt_id + "-") and
                 dollars.ATTEMPT.fullmatch(attempt_id) is not None and
                 attempt_id not in self.completed_paid and
                 category in {"tinker", environment.category(self.cell_id)} and
                 type(request) is dict and type(work) is dict and
                 callable(provider) and
                 _money(reserve_usd) > 0 and
                 type(resource_reservation) is dict and
                 (resource_reservation == {} if category != "e2b" else
                  set(resource_reservation) == {
                      "e2b_sandbox_hours", "e2b_peak_concurrency"}),
                 "shared_base_paid_dispatch_contract_invalid")
        prior = self.budget.owner_attempts(self.owner)
        committed = sum((_money(row["actual_usd"] if row["status"] ==
                                "settled" else row["reserved_usd"])
                         for row in prior.values() if row["category"] !=
                         "shared_base_final"), Decimal(0))
        _require(committed + _money(reserve_usd) <= _money(
            self.cell["base_selection_cost_upper_bound_usd"]),
            "shared_base_selection_separate_reserve_exhausted")
        raw_ref = _write_new(
            self.directory / "paid" /
            (attempt_id + ".worker-request.private.json"),
            _canonical(request))
        raw_ref["path"] = "paid/" + raw_ref["path"]
        envelope = self._envelope(
            attempt_id=attempt_id, category=category,
            worker_request=request, worker_request_ref=raw_ref)
        envelope_ref = _write_new(
            self.directory / "paid" /
            (attempt_id + ".request.private.json"), _canonical(envelope))
        envelope_ref["path"] = "paid/" + envelope_ref["path"]
        self.budget.reserve(attempt_id, self.owner, category,
                            reserve_usd, envelope_ref["sha256"])
        self.budget.mark_dispatched(attempt_id, envelope_ref["sha256"])
        try:
            result = provider(request)
            _require(type(result) is dict,
                     "shared_base_worker_paid_result_not_object")
            worker_result_ref = _write_new(
                self.directory / "paid" /
                (attempt_id + ".worker-result.private.json"),
                _canonical(result))
            worker_result_ref["path"] = "paid/" + worker_result_ref["path"]
            status = result.get("status")
            _require(status is None or type(status) is str,
                     "shared_base_worker_paid_status_invalid")
            normalized = {
                "schema": shared.PAID_RESULT_SCHEMA,
                "attempt_id": attempt_id, "category": category,
                "status": status,
                "selection_attempt": self.attempt_id,
                "task_id": envelope["task_id"],
                "checkpoint_path_sha256": self.started[
                    "checkpoint_path_sha256"],
                "worker_result_ref": worker_result_ref,
            }
            result_ref = _write_new(
                self.directory / "paid" /
                (attempt_id + ".result.private.json"),
                _canonical(normalized))
            result_ref["path"] = "paid/" + result_ref["path"]
            self.completed_paid[attempt_id] = {
                "attempt_id": attempt_id, "category": category,
                "request_ref": envelope_ref, "result_ref": result_ref,
                "worker_result_ref": worker_result_ref,
                "worker_request_ref": raw_ref,
                "reserve_usd": reserve_usd,
                "worker_result_sha256": worker_result_ref["sha256"],
                "worker_work_sha256": _sha(_canonical(work)),
            }
            return {"attempt_id": attempt_id, "result": result,
                    "result_sha256": worker_result_ref["sha256"],
                    "billing_state":
                        "awaiting_provider_usage_reconciliation"}
        except Exception:
            self.budget.mark_uncertain(attempt_id, "provider")
            raise SharedBaseExecutionError(
                "shared_base_paid_response_uncertain_no_replay") from None

    def reconcile_all(self, usage_reconciler: Callable[[dict], dict]) -> list[dict]:
        """Settle completed paid calls only from trusted account/local evidence."""
        _require(callable(usage_reconciler),
                 "shared_base_usage_reconciler_required")
        refs = []
        attempts = self.budget.owner_attempts(self.owner)
        _require(set(attempts) == set(self.completed_paid),
                 "shared_base_unowned_or_uncertain_paid_attempt")
        for attempt_id, item in self.completed_paid.items():
            record = attempts[attempt_id]
            _require(record["status"] in {"dispatched", "settled"},
                     "shared_base_paid_attempt_unresolved")
            source = usage_reconciler(dict(item))
            _require(type(source) is dict and set(source) == {
                "actual_usd", "invoice_basis", "provider_invoice_usd",
                "source_bytes"} and
                type(source["source_bytes"]) is bytes and
                bool(source["source_bytes"]),
                "shared_base_usage_source_invalid")
            actual = _money(source["actual_usd"])
            _require(actual <= _money(item["reserve_usd"]),
                     "shared_base_paid_amount_over_reserved")
            basis = ("self_hosted_nominal_meter" if item["category"] ==
                     "storage_application" else "provider_invoice")
            _require(source["invoice_basis"] == basis and
                     source["provider_invoice_usd"] ==
                     (None if basis == "self_hosted_nominal_meter" else
                      source["actual_usd"]),
                     "shared_base_invoice_basis_invalid")
            source_path = (self.directory / "paid" /
                           (attempt_id + ".source.private.json"))
            if source_path.exists():
                source_ref = {"path": "paid/" + source_path.name,
                              "sha256": _sha(shared._private_bytes(
                                  source_path, self.directory))}
                _require(source_ref["sha256"] ==
                         _sha(source["source_bytes"]),
                         "shared_base_usage_source_changed")
            else:
                source_ref = _write_new(source_path,
                                        source["source_bytes"])
                source_ref["path"] = "paid/" + source_ref["path"]
            usage = {
                "schema": shared.USAGE_SCHEMA,
                "attempt_id": attempt_id,
                "category": item["category"],
                "actual_usd": source["actual_usd"],
                "invoice_basis": basis,
                "provider_invoice_usd": source["provider_invoice_usd"],
                "source_ref": source_ref,
            }
            usage_path = (self.directory / "paid" /
                          (attempt_id + ".usage.private.json"))
            if usage_path.exists():
                usage_ref = {"path": "paid/" + usage_path.name,
                             "sha256": _sha(shared._private_bytes(
                                 usage_path, self.directory))}
                _require(shared._canonical(usage) ==
                         shared._private_bytes(usage_path, self.directory),
                         "shared_base_usage_receipt_changed")
            else:
                usage_ref = _write_new(usage_path, _canonical(usage))
                usage_ref["path"] = "paid/" + usage_ref["path"]
            self.budget.settle(attempt_id, source["actual_usd"],
                               usage_ref["sha256"])
            refs.append({"attempt_id": attempt_id,
                         "category": item["category"],
                         "request_ref": item["request_ref"],
                         "result_ref": item["result_ref"],
                         "usage_ref": usage_ref})
        return refs


def _native_json(root: Path, path: Path, expected_sha: str | None = None) -> dict:
    raw = shared._private_bytes(path, root)
    _require(expected_sha is None or _sha(raw) == expected_sha,
             "shared_base_native_artifact_changed")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SharedBaseExecutionError(
            "shared_base_native_json_invalid") from None
    _require(type(value) in (dict, list),
             "shared_base_native_json_invalid")
    return value


def _store(root: Path, relative: str, raw: bytes) -> dict:
    path = root / relative
    if not path.parent.exists():
        path.parent.mkdir(mode=0o700, parents=True)
    _require(path.parent.resolve().is_relative_to(root.resolve()) and
             not any(parent.is_symlink() for parent in
                     [path.parent, *path.parent.parents]
                     if parent.resolve().is_relative_to(root.resolve())),
             "shared_base_private_output_unsafe")
    path.parent.chmod(0o700)
    ref = _write_new(path, raw)
    ref["path"] = relative
    return ref


def _copy(root: Path, source: Path, relative: str,
          expected_sha: str | None = None) -> dict:
    raw = shared._private_bytes(source, root)
    _require(expected_sha is None or _sha(raw) == expected_sha,
             "shared_base_native_artifact_changed")
    return _store(root, relative, raw)


def _native_ref(root: Path, source: Path,
                expected_sha: str | None = None) -> dict:
    raw = shared._private_bytes(source, root)
    _require(expected_sha is None or _sha(raw) == expected_sha,
             "shared_base_native_artifact_changed")
    return {"path": source.relative_to(root).as_posix(),
            "sha256": _sha(raw)}


def _project_task(session: SharedBaseSession, ordinal: int,
                  identity: dict, *, score: int, native_worker_ref: dict,
                  saved_path: Path, saved_sha: str,
                  verifier_path: Path, verifier_sha: str,
                  reset_path: Path, reset_sha: str,
                  baseline_path: Path, baseline_sha: str,
                  restored_path: Path, restored_sha: str,
                  frames: list[tuple[Path, str]],
                  actions: list[dict], tinker_ids: list[str],
                  environment_id: str, readback: bool,
                  native_save: bool) -> tuple[dict, dict]:
    root = session.directory
    task = f"tasks/task-{ordinal:03d}"
    common = {"task_id": identity["task_id"],
              "package_sha256": identity["package_sha256"]}
    _require(score in (0, 1) and type(score) is int and
             readback is True and type(native_save) is bool and
             type(actions) is list and bool(actions) and
             type(tinker_ids) is list and bool(tinker_ids) and
             all(call in session.completed_paid for call in
                 tinker_ids + [environment_id]),
             "shared_base_native_task_or_paid_missing")
    _native_json(root, saved_path, saved_sha)
    native_verifier = _native_json(root, verifier_path, verifier_sha)
    native_reset = _native_json(root, reset_path, reset_sha)
    _require(native_verifier.get("score") == score and
             native_verifier.get("independent_of_actor",
                 native_verifier.get("independent_select_only")) is True and
             (native_reset.get("state_equivalence_pass",
                 native_reset.get("post_database_filestore_exact")) is True),
             "shared_base_native_verifier_or_reset_failed")
    saved_artifact_ref = _copy(
        root, saved_path, task + "/native-saved-artifact.private.json",
        saved_sha)
    baseline_ref = _copy(root, baseline_path,
                         task + "/baseline-state.private.json",
                         baseline_sha)
    restored_ref = _copy(root, restored_path,
                         task + "/restored-state.private.json",
                         restored_sha)
    _require(baseline_ref["sha256"] == restored_ref["sha256"],
             "shared_base_native_reset_bytes_differ")
    frame_refs = []
    for index, (path, expected_sha) in enumerate(frames):
        frame = _copy(root, path, task + f"/frame-{index:03d}.png",
                      expected_sha)
        _require(shared._private_bytes(root / frame["path"], root).startswith(
            b"\x89PNG\r\n\x1a\n"), "shared_base_native_frame_not_png")
        frame_refs.append(frame)
    frame_shas = {ref["sha256"] for ref in frame_refs}
    _require(all(type(row) is dict and
                 row.get("step") == index and
                 row.get("frame_sha256") in frame_shas and
                 is_hash(row.get("model_result_sha256")) and
                 row.get("current_frame_checked") is True and
                 (row.get("action_type") is None or
                  type(row["action_type"]) is str)
                 for index, row in enumerate(actions)),
             "shared_base_native_action_trace_unbound")
    action_ref = _store(root, task + "/actions.private.json",
                        _canonical(actions))
    saved_ref = _store(root, task + "/saved.private.json", _canonical({
        "schema": shared.SAVED_SCHEMA, **common,
        "readback_performed": readback,
        "native_save_observed": native_save,
        "saved_artifact_ref": saved_artifact_ref,
        "saved_artifact_sha256": saved_artifact_ref["sha256"],
    }))
    verifier_ref = _store(root, task + "/verifier.private.json",
                          _canonical({
        "schema": shared.VERIFIER_SCHEMA, **common,
        "score": score, "independent_of_actor": True,
        # Native oracles combine target and no-regression failures. A failed
        # combined oracle is conservatively reported as both failed.
        "target_state_pass": bool(score),
        "no_regression_checked": True,
        "no_regression_pass": bool(score),
        "evaluated_saved_artifact_sha256": saved_artifact_ref["sha256"],
        "verifier_sha256": session.cell["matched_bindings"]["verifier"],
    }))
    reset_ref = _store(root, task + "/reset.private.json", _canonical({
        "schema": shared.RESET_SCHEMA, **common,
        "fresh_environment": True,
        "state_equivalence_pass": True,
        "used_environment_terminated": True,
        "baseline_state_ref": baseline_ref,
        "restored_state_ref": restored_ref,
    }))
    gui_ref = _store(root, task + "/gui-trace.private.json", _canonical({
        "schema": shared.TRACE_SCHEMA, **common,
        "checkpoint_sha256": session.started["checkpoint_path_sha256"],
        "original_software_gui": True,
        "observation_kind": "screenshot",
        "current_frame_rechecked": True,
        "frame_refs": frame_refs,
        "action_trace_ref": action_ref,
        "model_sample_count": len(actions),
        "validated_gui_action_count": sum(
            row["action_type"] is not None for row in actions),
    }))
    row = {**common,
           "checkpoint_sha256": session.started["checkpoint_path_sha256"],
           "score": score, "saved_state_ref": saved_ref,
           "verifier_ref": verifier_ref, "reset_ref": reset_ref,
           "gui_trace_ref": gui_ref,
           "native_worker_ref": native_worker_ref,
           "tinker_paid_attempt_ids": tinker_ids,
           "environment_paid_attempt_id": environment_id}
    result_row = {**common, "score": score,
                  "saved_state_sha256": saved_ref["sha256"],
                  "verifier_receipt_sha256": verifier_ref["sha256"],
                  "reset_receipt_sha256": reset_ref["sha256"]}
    return row, result_row


def _project_gitlab(session: SharedBaseSession,
                    native: dict) -> tuple[list[dict], list[dict], dict]:
    root = session.directory
    native_root = root / "native"
    batch_path = native_root / "batch.private.json"
    batch = _native_json(root, batch_path,
                         native.get("batch_receipt_sha256"))
    ledger_path = native_root / "task-ledger.private.json"
    ledger = _native_json(root, ledger_path,
                          native.get("task_ledger_sha256"))
    _require(batch.get("task_count") == 20 and
             batch.get("checkpoint_path_sha256") ==
             session.started["checkpoint_path_sha256"] and
             ledger.get("selection_attempt") == session.attempt_id and
             ledger.get("selection_identities_sha256") ==
             session.started["selection_identities_sha256"] and
             type(ledger.get("tasks")) is list and
             len(ledger["tasks"]) == 20,
             "shared_base_gitlab_native_batch_unbound")
    rows, results = [], []
    for ordinal, (identity, entry) in enumerate(zip(
            session.started["selection_tasks"], ledger["tasks"]), 1):
        task_dir = native_root / f"task-{ordinal:03d}"
        task_path = task_dir / "task.private.json"
        task = _native_json(root, task_path,
                            entry["task_receipt_ref"]["sha256"])
        _require(task.get("task_id") == identity["task_id"] and
                 task.get("package_sha256") == identity["package_sha256"] and
                 task.get("score") in (0, 1) and
                 task.get("paid_attempt_ids") ==
                 [entry["application_paid_attempt_id"],
                  *entry["qwen_paid_attempt_ids"]],
                 "shared_base_gitlab_native_task_unbound")
        def source(key):
            reference = task[key]
            return task_dir / reference["path"], reference["sha256"]
        saved_path, saved_sha = source("saved_state_ref")
        native_saved = _native_json(root, saved_path, saved_sha)
        verifier_path, verifier_sha = source("verifier_ref")
        reset_path, reset_sha = source("reset_ref")
        reset = _native_json(root, reset_path, reset_sha)
        baseline = reset["baseline_state_ref"]
        restored = reset["restored_state_ref"]
        trace_path, trace_sha = source("action_trace_ref")
        trace = _native_json(root, trace_path, trace_sha)
        frames = [(task_dir / ref["path"], ref["sha256"])
                  for ref in task["frame_refs"]]
        actions = [{"step": index,
                    "frame_sha256": frame[1],
                    "model_result_sha256": sample["paid_result_sha256"],
                    "action_type": (sample["action"]["type"] if
                                    sample.get("action") else None),
                    "current_frame_checked": True}
                   for index, (frame, sample) in enumerate(zip(frames, trace))]
        _require(len(trace) == len(frames) == len(actions) and
                 [row.get("paid_attempt_id") for row in trace] ==
                 entry["qwen_paid_attempt_ids"] and
                 native_saved.get("original_gitlab_ce") is True and
                 native_saved.get("postgresql_and_git_readback") is True and
                 native_saved.get("independent_score", {}).get("checks_passed")
                 == bool(task["score"]) and
                 reset.get("used_clone_terminated") is True,
                 "shared_base_gitlab_saved_or_trace_unbound")
        row, result = _project_task(
            session, ordinal, identity, score=task["score"],
            native_worker_ref=_native_ref(root, task_path),
            saved_path=saved_path, saved_sha=saved_sha,
            verifier_path=verifier_path, verifier_sha=verifier_sha,
            reset_path=reset_path, reset_sha=reset_sha,
            baseline_path=task_dir / baseline["path"],
            baseline_sha=baseline["sha256"],
            restored_path=task_dir / restored["path"],
            restored_sha=restored["sha256"],
            frames=frames, actions=actions,
            tinker_ids=entry["qwen_paid_attempt_ids"],
            environment_id=entry["application_paid_attempt_id"],
            readback=True, native_save=True)
        rows.append(row)
        results.append(result)
    return rows, results, {"native_batch_ref": _native_ref(root, batch_path),
                           "native_task_ledger_ref":
                               _native_ref(root, ledger_path)}


def _project_odoo(session: SharedBaseSession,
                  native: dict) -> tuple[list[dict], list[dict], dict]:
    root = session.directory
    native_root = root / "native"
    ledger_path = native_root / "task-ledger.private.json"
    ledger = _native_json(root, ledger_path,
                          native.get("task_ledger_sha256"))
    runtime_path = native_root / "local-runtime.private.json"
    runtime = _native_json(root, runtime_path,
                           native.get("local_runtime_receipt_sha256"))
    _require(runtime.get("services_restored_to_initial_state") is True and
             runtime.get("final_database_snapshot_equal") is True and
             runtime.get("final_physical_filestore_equal") is True,
             "shared_base_odoo_batch_cold_reset_unbound")
    entries = ledger.get("rows")
    _require(type(entries) is list and len(entries) == 20 and
             ledger.get("selection_attempt") == session.attempt_id and
             ledger.get("checkpoint_sha256") ==
             session.started["checkpoint_path_sha256"] and
             ledger.get("selection_identities_sha256") ==
             session.started["selection_identities_sha256"],
             "shared_base_odoo_native_batch_unbound")
    batch_env = session.attempt_id + "-local-service"
    rows, results = [], []
    for ordinal, (identity, entry) in enumerate(zip(
            session.started["selection_tasks"], entries), 1):
        task_dir = native_root / "tasks" / f"task-{ordinal:03d}"
        _require(entry.get("task_id") == identity["task_id"] and
                 entry.get("package_sha256") ==
                 identity["package_sha256"] and
                 entry.get("score") in (0, 1) and
                 type(entry.get("sample_paid_attempt_ids")) is list and
                 bool(entry["sample_paid_attempt_ids"]),
                 "shared_base_odoo_native_task_unbound")
        saved_path = task_dir / "saved-state.private.json"
        native_saved = _native_json(root, saved_path,
                                    entry["saved_state_sha256"])
        verifier_path = task_dir / "verifier.private.json"
        reset_path = task_dir / "reset.private.json"
        reset = _native_json(root, reset_path,
                             entry["reset_receipt_sha256"])
        frame_manifest = _native_json(root,
            task_dir / "frames.private.json", entry["frames_sha256"])
        native_actions = _native_json(root,
            task_dir / "actions.private.json", entry["actions_sha256"])
        usage = _native_json(root, task_dir / "usage.private.json",
                             entry["usage_sha256"])
        _require(type(frame_manifest) is list and
                 type(native_actions) is list and
                 type(usage.get("samples")) is list and
                 len(usage["samples"]) == entry["sample_count"] and
                 len(frame_manifest) == entry["frame_count"] and
                 len(frame_manifest) >= len(usage["samples"]) and
                 native_saved.get("gui_reload_frame_sha256") is not None and
                 reset.get("pre_database_filestore_exact") is True and
                 reset.get("post_database_filestore_exact") is True,
                 "shared_base_odoo_saved_or_trace_unbound")
        frames = [(task_dir / frame["path"], frame["sha256"])
                  for frame in frame_manifest]
        native_by_step = {row["step"]: row for row in native_actions}
        actions = []
        for index, sample in enumerate(usage["samples"]):
            step = sample["step"]
            _require(step == index and
                     sample["paid_attempt_id"] ==
                     entry["sample_paid_attempt_ids"][index] and
                     is_hash(sample.get("model_text_sha256")) and
                     frame_manifest[index]["sha256"] ==
                     frames[index][1],
                     "shared_base_odoo_sample_frame_changed")
            action = native_by_step.get(step)
            actions.append({
                "step": index, "frame_sha256": frames[index][1],
                "model_result_sha256": sample["model_text_sha256"],
                "action_type": (action["action_type"] if action else None),
                "current_frame_checked": True})
        _require(set(native_by_step) <= set(range(len(actions))) and
                 all(row["frame_sha256"] == frames[row["step"]][1]
                     for row in native_actions),
                 "shared_base_odoo_action_frame_changed")
        baseline = reset["baseline_semantic_ref"]
        restored = reset["restored_semantic_ref"]
        row, result = _project_task(
            session, ordinal, identity, score=entry["score"],
            native_worker_ref=_native_ref(root, ledger_path),
            saved_path=saved_path, saved_sha=entry["saved_state_sha256"],
            verifier_path=verifier_path,
            verifier_sha=entry["verifier_receipt_sha256"],
            reset_path=reset_path, reset_sha=entry["reset_receipt_sha256"],
            baseline_path=task_dir / baseline["path"],
            baseline_sha=baseline["sha256"],
            restored_path=task_dir / restored["path"],
            restored_sha=restored["sha256"],
            frames=frames, actions=actions,
            tinker_ids=entry["sample_paid_attempt_ids"],
            environment_id=batch_env, readback=True,
            native_save=bool(entry["score"]))
        rows.append(row)
        results.append(result)
    return rows, results, {
        "native_task_ledger_ref": _native_ref(root, ledger_path),
        "native_runtime_ref": _native_ref(root, runtime_path)}


def execute_shared_base(study, cell_id: str,
                        run_native: Callable[[SharedBaseSession, Path], dict],
                        usage_reconciler: Callable[[dict], dict]) -> dict:
    """Run once, reconcile every paid call, then admit one immutable receipt."""
    _require(cell_id in {"gitlab", "odoo-community"} and
             callable(run_native) and callable(usage_reconciler),
             "shared_base_cell_runner_missing")
    session = SharedBaseSession(study, cell_id)
    native = run_native(session, session.directory / "native")
    _require(type(native) is dict and
             type(native.get("result")) is dict and
             native["result"].get("cell_id") == cell_id and
             native["result"].get("checkpoint_sha256") ==
             session.started["checkpoint_path_sha256"] and
             native["result"].get("evaluator_isolated") is True and
             native.get("paid_attempt_ids") ==
             list(session.completed_paid) and
             len(session.completed_paid) >= 21,
             "shared_base_native_result_or_paid_unbound")
    paid_refs = session.reconcile_all(usage_reconciler)
    projector = (_project_gitlab if cell_id == "gitlab" else _project_odoo)
    rows, result_rows, source = projector(session, native)
    _require(len(rows) == len(result_rows) == 20 and
             [(row["task_id"], row["package_sha256"], row["score"])
              for row in native["result"]["tasks"]] ==
             [(row["task_id"], row["package_sha256"], row["score"])
              for row in result_rows],
             "shared_base_native_result_rows_changed")
    root = session.directory
    native_batch_ref = _store(root, "native-batch.private.json",
                              _canonical({
        "schema": "cua-full-study-shared-base-native-batch-v1",
        "cell_id": cell_id,
        "checkpoint_sha256": session.started["checkpoint_path_sha256"],
        "task_count": 20,
        "native_source_refs": source,
    }))
    result_ref = _store(root, "selection-result.private.json", _canonical({
        "schema": "cua-full-study-selection-saved-result-v1",
        "cell_id": cell_id,
        "checkpoint_sha256": session.started["checkpoint_path_sha256"],
        "evaluator_isolated": True, "tasks": result_rows,
    }))
    ledger_ref = _store(root, "task-ledger.private.json", _canonical({
        "schema": shared.LEDGER_SCHEMA, "cell_id": cell_id,
        "checkpoint_sha256": session.started["checkpoint_path_sha256"],
        "selection_identities_sha256": session.cell[
            "selection_identities_sha256"],
        "task_count": 20, "tasks": rows,
    }))
    paid_calls = []
    for ref in paid_refs:
        request, _ = shared._json_ref(root, ref["request_ref"])
        result, _ = shared._json_ref(root, ref["result_ref"])
        paid_calls.append({"attempt_id": ref["attempt_id"],
                           "category": ref["category"],
                           "request": request,
                           "result_present": True,
                           "result_status": result["status"]})
    coverage = paid_coverage.validate(
        cell_id=cell_id, attempt_id=session.attempt_id,
        checkpoint_sha256=session.started["checkpoint_path_sha256"],
        selection_tasks=session.started["selection_tasks"],
        selection_identities_sha256=session.started[
            "selection_identities_sha256"],
        paid_calls=paid_calls,
        related_paid_attempt_ids=set(session.completed_paid))
    receipt = {
        "schema": shared.RECEIPT_SCHEMA,
        "study_id": study.plan["study_id"],
        "cell_id": cell_id, "plan_sha256": study.plan_sha256,
        "base_manifest_sha256": session.cell["base_manifest_sha256"],
        "base_checkpoint_sha256": session.started[
            "checkpoint_path_sha256"],
        "base_model": MODEL,
        "base_freeze_receipt_sha256": session.base_freeze[
            "freeze_receipt_sha256"],
        "selection_identities_sha256": session.cell[
            "selection_identities_sha256"],
        "action_profile": "scale-action-profile-v0.6.6",
        "source_bindings": {**session.cell["matched_bindings"],
                            "adapter": study.ratification[
                                "cell_profiles"][cell_id]["adapter_sha256"]},
        "original_software_gui": True, "evaluator_isolated": True,
        "result_ref": result_ref, "task_ledger_ref": ledger_ref,
        "native_batch_ref": native_batch_ref,
        "executor_source_sha256": _sha(Path(__file__).read_bytes()),
        "paid_attempt_refs": paid_refs,
        "paid_attempt_ids": list(session.completed_paid),
        "environment_category": environment.category(cell_id),
        "selection_attempt": session.attempt_id,
        "paid_coverage_sha256": coverage["coverage_sha256"],
        "official_final_tasks_observed": 0,
    }
    path = shared.receipt_path(study, cell_id)
    _write_new(path, _canonical(receipt))
    admitted = study.admit_shared_base_selection(cell_id, path)
    return {**admitted, "receipt_path": str(path),
            "paid_attempt_count": len(paid_refs),
            "environment_category": environment.category(cell_id)}


def run_gitlab_shared_base(study, usage_reconciler: Callable[[dict], dict],
                           *, worker_factory=None,
                           sampler_factory=None) -> dict:
    """Run the original GitLab CE selection worker on the frozen base model."""
    from gitlab_world import selection_worker_v066 as gitlab

    class BaseWorker(gitlab.GitLabSelectionWorker):
        def _resolve_checkpoint_path(self, session, checkpoint_sha256):
            _require(checkpoint_sha256 == session.cell[
                "base_checkpoint_sha256"] and
                session.base_freeze["freeze_receipt_sha256"] ==
                _verify_base_freeze(session.study, session.cell)[
                    "freeze_receipt_sha256"],
                "shared_base_gitlab_checkpoint_freeze_changed")
            return MODEL

    class BaseSampler(gitlab._RealTinkerSampler):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # TinkerVisionBackend.from_service(..., checkpoint=None) opens
            # create_sampling_client(base_model=MODEL); the private manifest
            # checkpoint SHA remains a separate frozen study binding.
            self.checkpoint_path = None

        def __call__(self, request, prompt):
            result = super().__call__(request, prompt)
            _require(self.backend.identity.get("sampling_kind") == "base" and
                     self.backend.identity.get("checkpoint_sha256") ==
                     vision_digest(MODEL) and
                     self.backend.sampling_client.get_base_model() == MODEL,
                     "shared_base_gitlab_provider_model_changed")
            return result

    def run_native(session: SharedBaseSession, out_dir: Path) -> dict:
        worker = (worker_factory() if worker_factory is not None else
                  BaseWorker(enable_live=True))
        _require(worker.cell_id == "gitlab" and
                 worker.runtime_sha256 ==
                 session.cell["matched_bindings"]["runtime"] and
                 worker.verifier_sha256 ==
                 session.cell["matched_bindings"]["verifier"],
                 "shared_base_gitlab_worker_source_changed")
        frozen_cell, _ = worker._require_frozen(session, session.started)
        training, policy, _ = worker._policy(session, frozen_cell)
        vision = worker._load_vision()
        sampler = (sampler_factory(session, policy, vision) if
                   sampler_factory is not None else BaseSampler(
            checkpoint_path=MODEL,
            checkpoint_sha256=session.started["checkpoint_path_sha256"],
            vision=vision, seed=policy["seed"],
            temperature=policy["temperature"],
            max_output_tokens=policy["max_output_tokens"],
            campaign_metadata={
                "purpose": "envloop-full-study-shared-base-gitlab-v066",
                "study_id": study.plan["study_id"],
                "cell_id": "gitlab", "researcher_id": "shared-base",
                "split": "selection", "base_model": MODEL,
            }))
        completed = False
        try:
            native = worker.run_attempt(
                session=session, started=session.started,
                out_dir=out_dir, sampler_provider=sampler)
            completed = True
            return native
        finally:
            sampler.close(success=completed)

    return execute_shared_base(study, "gitlab", run_native,
                               usage_reconciler)


def run_odoo_shared_base(study, usage_reconciler: Callable[[dict], dict],
                         *, worker_dir: Path,
                         local_cost_authority_path: Path,
                         local_cost_authority_sha256: str,
                         worker_factory=None) -> dict:
    """Run the source-bound Odoo worker in its explicit base-model mode."""
    from enterprise_fallback.odoo18 import selection_worker_v066 as odoo

    def run_native(session: SharedBaseSession, out_dir: Path) -> dict:
        config_ref = study.manifest["configurations"]["student"]
        config_path, raw = cell_final.evidence_file(
            Path(study.manifest_path).parent, config_ref,
            "shared base student configuration")
        config = json.loads(raw)
        _, training_raw = cell_final.evidence_file(
            config_path.parent, config["assets"]["training"],
            "shared base student training asset")
        _, frozen_training_sha = study.student_training_configuration()
        _require(_sha(training_raw) == frozen_training_sha,
                 "shared_base_odoo_training_asset_changed")
        kwargs = {
            "worker_dir": Path(worker_dir),
            "private_output_root": session.directory,
            "ratification_path": study.ratification_path,
            "ratification_sha256": study.ratification_sha256,
            "expected_runtime_sha256": session.cell[
                "matched_bindings"]["runtime"],
            "expected_verifier_sha256": session.cell[
                "matched_bindings"]["verifier"],
            "local_cost_authority_path": Path(local_cost_authority_path),
            "local_cost_authority_sha256":
                local_cost_authority_sha256,
            "allow_base_model": True,
            "expected_base_checkpoint_sha256": session.started[
                "checkpoint_path_sha256"],
            "enable_live": True,
        }
        worker = (worker_factory(**kwargs) if worker_factory is not None else
                  odoo.OdooSelectionWorker(**kwargs))
        _require(worker.cell_id == "odoo-community" and
                 worker.runtime_sha256 ==
                 session.cell["matched_bindings"]["runtime"] and
                 worker.verifier_sha256 ==
                 session.cell["matched_bindings"]["verifier"],
                 "shared_base_odoo_worker_source_changed")
        return worker.run_selection(
            started=session.started, checkpoint_path=MODEL,
            student_config_raw=training_raw,
            student_config_sha256=frozen_training_sha,
            out_dir=out_dir, dispatch_paid=session.dispatch_paid,
            base_mode=True)

    return execute_shared_base(study, "odoo-community", run_native,
                               usage_reconciler)


__all__ = ["SharedBaseSession", "SharedBaseExecutionError",
           "execute_shared_base", "run_gitlab_shared_base",
           "run_odoo_shared_base"]
