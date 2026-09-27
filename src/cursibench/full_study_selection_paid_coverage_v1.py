"""Verify paid GUI/sample coverage of every frozen selection task.

A category-level budget record is insufficient: one Tinker call cannot stand
in for 20 task rollouts. This pure pre-result audit checks all related paid
requests against the selection roster before a 20-score result is accepted.
Cell-owned saved-state and reset ledgers remain independently reviewable.
"""

from __future__ import annotations

import hashlib
import json

from . import full_study_selection_environment_v1 as environment
from .scale_final_v06 import is_hash


SCHEMA = "cua-full-study-selection-paid-task-coverage-v1"


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def validate(*, cell_id: str, attempt_id: str,
             checkpoint_sha256: str, selection_tasks: list[dict],
             selection_identities_sha256: str,
             paid_calls: list[dict],
             related_paid_attempt_ids: set[str]) -> dict:
    """Return a field-limited count/hash receipt or reject missing task work.

    ``paid_calls`` contains only completed, hash-audited requests named in the
    scored attempt. A caller must provide the complete set of paid intents
    whose attempt ID belongs to this selection attempt, preventing selective
    omission of a failed or uncertain provider call.
    """
    category = environment.category(cell_id)
    _require(type(attempt_id) is str and bool(attempt_id) and
             is_hash(checkpoint_sha256) and
             type(selection_tasks) is list and len(selection_tasks) == 20 and
             type(selection_identities_sha256) is str and
             is_hash(selection_identities_sha256) and
             hashlib.sha256(_canonical(selection_tasks)).hexdigest() ==
             selection_identities_sha256 and
             type(paid_calls) is list and paid_calls and
             type(related_paid_attempt_ids) is set,
             "selection_paid_coverage_input_invalid")
    expected = {}
    for item in selection_tasks:
        _require(type(item) is dict and
                 type(item.get("task_id")) is str and
                 is_hash(item.get("package_sha256")) and
                 item["task_id"] not in expected,
                 "selection_paid_roster_invalid")
        expected[item["task_id"]] = item["package_sha256"]
    _require(len(expected) == 20, "selection_paid_roster_invalid")
    sample_covered: set[str] = set()
    environment_covered: set[str] = set()
    sample_count = 0
    environment_count = 0
    included = set()
    for paid in paid_calls:
        _require(type(paid) is dict and set(paid) == {
            "attempt_id", "category", "request", "result_present"},
            "selection_paid_call_shape_invalid")
        paid_id = paid["attempt_id"]
        kind = paid["category"]
        request = paid["request"]
        _require(type(paid_id) is str and
                 paid_id.startswith(attempt_id + "-") and
                 paid_id not in included and
                 kind in {"tinker", category} and
                 type(request) is dict and
                 request.get("selection_attempt") == attempt_id and
                 request.get("cell_id") == cell_id and
                 paid["result_present"] is True,
                 "selection_paid_call_unbound_or_incomplete")
        included.add(paid_id)
        task_id = request.get("task_id")
        if task_id is not None:
            _require(task_id in expected and
                     request.get("package_sha256") == expected[task_id] and
                     request.get("checkpoint_path_sha256") ==
                     checkpoint_sha256,
                     "selection_paid_task_or_checkpoint_changed")
            if kind == "tinker":
                sample_covered.add(task_id)
                sample_count += 1
            else:
                environment_covered.add(task_id)
                environment_count += 1
            continue
        _require(request.get("selection_identities_sha256") ==
                 selection_identities_sha256,
                 "selection_paid_batch_identity_changed")
        if kind == "tinker":
            # A sampler setup lease is charged but gives no task credit.
            _require(request.get("checkpoint_path_sha256") ==
                     checkpoint_sha256,
                     "selection_paid_setup_checkpoint_changed")
            continue
        _require(request.get("selection_tasks") == selection_tasks,
                 "selection_paid_environment_batch_roster_changed")
        environment_covered.update(expected)
        environment_count += 1
    _require(included == related_paid_attempt_ids,
             "selection_paid_attempt_hidden_or_missing")
    _require(sample_covered == set(expected) and
             environment_covered == set(expected),
             "selection_paid_twenty_task_coverage_missing")
    projection = {
        "schema": SCHEMA, "cell_id": cell_id,
        "selection_attempt": attempt_id,
        "checkpoint_sha256": checkpoint_sha256,
        "selection_identities_sha256": selection_identities_sha256,
        "task_count": len(expected),
        "sample_paid_attempt_count": sample_count,
        "environment_paid_attempt_count": environment_count,
        "total_paid_attempt_count": len(included),
        "all_task_ids_have_sample_and_environment": True,
        "provider_invoice_verified": False,
    }
    return {**projection,
            "coverage_sha256": hashlib.sha256(_canonical(projection)).hexdigest()}
