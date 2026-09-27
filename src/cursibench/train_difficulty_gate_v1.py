"""Fail-closed, train-only difficulty screen for the proposed full study.

This module aggregates *independently scored saved-state* development attempts.
It never opens a final/selection package and cannot promote a task into the
official denominator. Cell-specific auditors remain responsible for proving
that their verifier receipts reflect the real application state.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


SCHEMA = "cua-train-difficulty-input-v1"
CONTROL_SCHEMA = "cua-train-difficulty-control-v1"
ATTEMPT_SCHEMA = "cua-train-difficulty-attempt-v1"
VERIFIER_SCHEMA = "cua-train-difficulty-verifier-v1"
OUTPUT_SCHEMA = "cua-train-difficulty-aggregate-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
ACTORS = ("base_qwen", "stronger_reference")
COMPLEXITY_KEYS = ("target_fields", "causal_steps", "distractor_objects", "screen_transitions")
# Screening rules are source-controlled, not caller-chosen after seeing results.
MIN_WORKFLOW_PAIRS = 8
MIN_WORKFLOW_FAMILIES = 2
MIN_PER_FAMILY = 2
MIN_ACTION_VALIDITY = 0.85
MAX_INFRA_FRACTION = 0.10
MAX_STRONG_TIMEOUT_FRACTION = 0.25
BASE_CEILING = 0.875
STRONG_FLOOR = 0.125


def _require(test: bool, message: str) -> None:
    if not test:
        raise ValueError(message)


def _hash(value: object, name: str) -> str:
    _require(isinstance(value, str) and HEX.fullmatch(value) is not None,
             f"{name}: lowercase SHA-256 required")
    return value


def _nonnegative(value: object, name: str) -> int:
    _require(type(value) is int and value >= 0, f"{name}: nonnegative integer required")
    return value


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path.name}: JSON object required")
    return value


def _file_ref(root: Path, value: object, name: str) -> tuple[bytes, str]:
    _require(isinstance(value, dict) and set(value) == {"path", "sha256"},
             f"{name}: exact path/SHA-256 reference required")
    rel = value["path"]
    _require(isinstance(rel, str) and rel and not Path(rel).is_absolute() and
             all(part not in ("", ".", "..") for part in Path(rel).parts),
             f"{name}: local relative path required")
    expected = _hash(value["sha256"], name)
    target = root / rel
    _require(target.is_file() and not target.is_symlink() and
             target.resolve().is_relative_to(root.resolve()),
             f"{name}: missing, symlinked, or escaping receipt")
    raw = target.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == expected,
             f"{name}: receipt hash mismatch")
    return raw, expected


def _ref(root: Path, value: object, name: str) -> tuple[dict, str]:
    raw, expected = _file_ref(root, value, name)
    parsed = json.loads(raw)
    _require(isinstance(parsed, dict), f"{name}: JSON object required")
    return parsed, expected


def _control(root: Path, task: dict) -> bool:
    receipt, _ = _ref(root, task.get("control_receipt"), "control_receipt")
    _require(receipt.get("schema") == CONTROL_SCHEMA and
             receipt.get("partition") == "train" and
             receipt.get("task_sha256") == task["task_sha256"] and
             receipt.get("verifier_sha256") == task["verifier_sha256"],
             "control receipt task, partition, or verifier mismatch")
    for role in ("positive", "near_miss", "cold_reset"):
        _hash(receipt.get(f"{role}_saved_state_sha256"), f"{role} saved state")
    # A failed control is a real rejection, never a model zero.
    return (type(receipt.get("positive_score")) is int and
            receipt["positive_score"] == 1 and
            type(receipt.get("near_miss_score")) is int and
            receipt["near_miss_score"] == 0 and
            type(receipt.get("cold_reset_score")) is int and
            receipt["cold_reset_score"] == 0 and
            receipt.get("positive_no_regression") is True and
            receipt.get("near_miss_rejected_for_intended_reason") is True)


def _attempt(root: Path, entry: dict, task: dict, profile: str,
             actor_configuration: str,
             max_actions: int, max_wall_seconds: int) -> dict:
    receipt, receipt_hash = _ref(root, entry.get("receipt"), "attempt_receipt")
    _require(receipt.get("schema") == ATTEMPT_SCHEMA and
             receipt.get("partition") == "train" and
             receipt.get("task_sha256") == task["task_sha256"] and
             receipt.get("actor") == entry.get("actor") and
             receipt.get("action_profile_sha256") == profile and
             receipt.get("actor_configuration_sha256") == actor_configuration and
             receipt.get("verifier_sha256") == task["verifier_sha256"],
             "attempt receipt task, actor, partition, action, or verifier mismatch")
    status = receipt.get("status")
    _require(status in ("scored", "infrastructure_invalid"),
             "unknown attempt status")
    actions = _nonnegative(receipt.get("action_attempts"), "action_attempts")
    valid = _nonnegative(receipt.get("valid_actions"), "valid_actions")
    wall = _nonnegative(receipt.get("wall_seconds"), "wall_seconds")
    _require(valid <= actions <= max_actions and wall <= max_wall_seconds,
             "attempt exceeds frozen action/wall envelope")
    for key in ("observation_trace_sha256", "action_trace_sha256", "reset_receipt_sha256"):
        _hash(receipt.get(key), key)
    _require(receipt.get("reset_verified") is True, "fresh reset not verified")
    if status == "infrastructure_invalid":
        _require(receipt.get("score") is None and
                 receipt.get("partial_targets") is None and
                 receipt.get("failure_class") in
                 ("provider", "transport", "environment", "verifier"),
                 "invalid attempt cannot carry a model score")
    else:
        _, saved_hash = _file_ref(root, receipt.get("saved_state"), "saved_state")
        verifier, verifier_hash = _ref(
            root, receipt.get("independent_verifier_receipt"),
            "independent_verifier_receipt")
        _require(receipt.get("saved_state_sha256") == saved_hash and
                 verifier.get("schema") == VERIFIER_SCHEMA and
                 verifier.get("partition") == "train" and
                 verifier.get("producer") == "independent_evaluator" and
                 verifier.get("task_sha256") == task["task_sha256"] and
                 verifier.get("verifier_sha256") == task["verifier_sha256"] and
                 verifier.get("saved_state_sha256") == saved_hash and
                 verifier_hash == receipt["independent_verifier_receipt"]["sha256"],
                 "saved state / independent verifier binding mismatch")
        score = receipt.get("score")
        _require(type(score) is int and score in (0, 1), "binary score required")
        partial = _nonnegative(receipt.get("partial_targets"), "partial_targets")
        total = _nonnegative(receipt.get("total_targets"), "total_targets")
        _require(total > 0 and partial <= total and
                 (score == 0 or (partial == total and
                                  receipt.get("no_regression") is True)),
                 "invalid partial/no-regression score")
        _require(type(receipt.get("no_regression")) is bool,
                 "explicit no-regression result required")
        _require(verifier.get("score") == score and
                 type(verifier.get("score")) is int and
                 verifier.get("partial_targets") == partial and
                 verifier.get("total_targets") == total and
                 verifier.get("no_regression") is receipt.get("no_regression") and
                 verifier.get("model_visible") is False,
                 "independent verifier score or visibility mismatch")
        _require(receipt.get("stop_reason") in
                 ("finish", "success", "action_limit", "wall_limit"),
                 "invalid scored stop reason")
    return {**receipt, "receipt_sha256": receipt_hash}


def _summary(pairs: list[dict], invalid_count: int) -> dict:
    n = len(pairs)
    base_wins = sum(row["base_qwen"]["score"] for row in pairs)
    strong_wins = sum(row["stronger_reference"]["score"] for row in pairs)
    attempts = [row[actor] for row in pairs for actor in ACTORS]
    actions = sum(row["action_attempts"] for row in attempts)
    valid = sum(row["valid_actions"] for row in attempts)
    strong_timeouts = sum(row["stronger_reference"]["stop_reason"] == "wall_limit"
                          for row in pairs)
    strong_action_limits = sum(row["stronger_reference"]["stop_reason"] == "action_limit"
                               for row in pairs)
    failed = [row for row in attempts if row["score"] == 0]
    actor_diagnostics = {}
    for actor in ACTORS:
        actor_attempts = [row[actor] for row in pairs]
        actor_actions = sum(row["action_attempts"] for row in actor_attempts)
        actor_valid = sum(row["valid_actions"] for row in actor_attempts)
        actor_diagnostics[actor] = {
            "scored_attempts": n,
            "successes": sum(row["score"] for row in actor_attempts),
            "valid_actions": actor_valid,
            "action_attempts": actor_actions,
            "valid_action_fraction": actor_valid / actor_actions if actor_actions else None,
            "wall_limits": sum(row["stop_reason"] == "wall_limit"
                               for row in actor_attempts),
            "action_limits": sum(row["stop_reason"] == "action_limit"
                                 for row in actor_attempts),
            "zero_score_partial_targets": sum(row["partial_targets"]
                                              for row in actor_attempts if row["score"] == 0),
            "zero_score_total_targets": sum(row["total_targets"]
                                            for row in actor_attempts if row["score"] == 0),
        }
    return {
        "paired_train_tasks": n,
        "base_successes": base_wins,
        "stronger_reference_successes": strong_wins,
        "base_success_fraction": base_wins / n if n else None,
        "stronger_reference_success_fraction": strong_wins / n if n else None,
        "reference_minus_base_fraction": (strong_wins - base_wins) / n if n else None,
        "valid_actions": valid,
        "action_attempts": actions,
        "valid_action_fraction": valid / actions if actions else None,
        "actor_diagnostics": actor_diagnostics,
        "stronger_reference_wall_limits": strong_timeouts,
        "stronger_reference_action_limits": strong_action_limits,
        "zero_score_partial_targets": sum(row["partial_targets"] for row in failed),
        "zero_score_total_targets": sum(row["total_targets"] for row in failed),
        "no_regression_failures": sum(row["no_regression"] is False for row in attempts),
        "infrastructure_invalid_attempts": invalid_count,
        "infrastructure_invalid_fraction": invalid_count / (invalid_count + 2 * n)
        if invalid_count + 2 * n else None,
    }


def evaluate(path: str | Path) -> dict:
    """Validate private train receipts and return an identifier-free aggregate."""
    path = Path(path)
    data = _json(path)
    _require(data.get("schema") == SCHEMA and data.get("partition") == "train" and
             data.get("cell_id") in
             ("powerpoint-web", "excel-web", "desktop-native", "odoo-community",
              "gitlab", "magento-admin"),
             "train-only six-cell input required")
    profile = _hash(data.get("action_profile_sha256"), "action profile")
    actor_config = data.get("actors")
    _require(isinstance(actor_config, dict) and set(actor_config) == set(ACTORS),
             "two frozen actor configurations required")
    for actor in ACTORS:
        config = actor_config[actor]
        _require(isinstance(config, dict) and
                 set(config) == {"model_id", "configuration_sha256",
                                 "prompt_sha256", "provider_route_sha256",
                                 "task_visible_only"} and
                 isinstance(config["model_id"], str) and config["model_id"] and
                 config["task_visible_only"] is True,
                 "actor model and task-only visibility required")
        for key in ("configuration_sha256", "prompt_sha256", "provider_route_sha256"):
            _hash(config[key], key)
    _require(actor_config["base_qwen"]["model_id"] == "Qwen/Qwen3.8-27B" and
             actor_config["stronger_reference"]["model_id"] in
             ("gpt-6-astra", "gpt-6-sol"),
             "declared Qwen baseline and Astra/Sol reference required")
    max_actions = _nonnegative(data.get("max_actions"), "max_actions")
    max_wall = _nonnegative(data.get("max_wall_seconds"), "max_wall_seconds")
    _require(0 < max_actions <= 1000 and 0 < max_wall <= 7200,
             "bounded action and wall envelopes required")
    minima = data.get("minimum_complexity")
    _require(isinstance(minima, dict) and set(minima) == set(COMPLEXITY_KEYS) and
             all(_nonnegative(minima[key], key) <= 1000 for key in COMPLEXITY_KEYS),
             "four predeclared complexity minima required")
    tasks = data.get("tasks")
    entries = data.get("attempts")
    _require(isinstance(tasks, list) and tasks and isinstance(entries, list),
             "nonempty train tasks and attempt list required")
    by_id = {}
    controls = {}
    complexity_mismatch = set()
    for task in tasks:
        _require(isinstance(task, dict), "task object required")
        tid = _hash(task.get("task_sha256"), "task")
        _require(tid not in by_id, "duplicate task")
        for key in ("source_family_sha256", "workflow_sha256", "verifier_sha256"):
            _hash(task.get(key), key)
        shape = task.get("complexity")
        _require(isinstance(shape, dict) and set(shape) == set(COMPLEXITY_KEYS) and
                 all(_nonnegative(shape[key], key) <= 1000 for key in COMPLEXITY_KEYS),
                 "exact train complexity vector required")
        if any(shape[key] < minima[key] for key in COMPLEXITY_KEYS):
            complexity_mismatch.add(tid)
        by_id[tid] = task
        controls[tid] = _control(path.parent, task)
    indexed: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in entries:
        _require(isinstance(entry, dict), "attempt entry object required")
        tid = _hash(entry.get("task_sha256"), "attempt task")
        actor = entry.get("actor")
        _require(tid in by_id and actor in ACTORS, "unknown task or actor")
        sequence = _nonnegative(entry.get("sequence"), "sequence")
        key = (tid, actor)
        _require(sequence == len(indexed[key]) and sequence < 2,
                 "append-only sequence with at most one infrastructure retry required")
        receipt = _attempt(path.parent, entry, by_id[tid], profile,
                           actor_config[actor]["configuration_sha256"],
                           max_actions, max_wall)
        _require((not indexed[key] or indexed[key][0]["status"] == "infrastructure_invalid") and
                 (sequence == 0 or receipt["status"] == "scored"),
                 "retry only after invalid attempt and then scored")
        indexed[key].append(receipt)
    workflows = defaultdict(list)
    invalid_by_workflow = defaultdict(int)
    invalid_classes_by_workflow = defaultdict(lambda: defaultdict(int))
    families = defaultdict(lambda: defaultdict(int))
    for tid, task in by_id.items():
        workflow = task["workflow_sha256"]
        family = task["source_family_sha256"]
        families[workflow][family] += 1
        pair = {actor: indexed[(tid, actor)][-1]
                for actor in ACTORS if indexed[(tid, actor)]}
        invalid_by_workflow[workflow] += sum(
            receipt["status"] == "infrastructure_invalid"
            for actor in ACTORS for receipt in indexed[(tid, actor)])
        for actor in ACTORS:
            for receipt in indexed[(tid, actor)]:
                if receipt["status"] == "infrastructure_invalid":
                    invalid_classes_by_workflow[workflow][receipt["failure_class"]] += 1
        if (len(pair) == 2 and all(row["status"] == "scored" for row in pair.values())
                and controls[tid] and tid not in complexity_mismatch):
            workflows[workflow].append({**pair, "source_family_sha256": family})
    rows = []
    for ordinal, workflow in enumerate(sorted(families), 1):
        pairs = workflows[workflow]
        stats = _summary(pairs, invalid_by_workflow[workflow])
        eligible_family_counts = defaultdict(int)
        paired_by_family = defaultdict(list)
        for row in pairs:
            eligible_family_counts[row["source_family_sha256"]] += 1
            paired_by_family[row["source_family_sha256"]].append(row)
        family_summaries = []
        for family_ordinal, family in enumerate(sorted(families[workflow]), 1):
            family_pairs = paired_by_family[family]
            family_summaries.append({
                "family_index": family_ordinal,
                "train_tasks": families[workflow][family],
                "paired_train_tasks": len(family_pairs),
                "base_successes": sum(row["base_qwen"]["score"]
                                      for row in family_pairs),
                "stronger_reference_successes": sum(
                    row["stronger_reference"]["score"] for row in family_pairs),
            })
        sufficient = (len(pairs) >= MIN_WORKFLOW_PAIRS and
                      sum(count >= MIN_PER_FAMILY for count in eligible_family_counts.values())
                      >= MIN_WORKFLOW_FAMILIES)
        invalid_fraction = stats["infrastructure_invalid_fraction"]
        validities = [stats["actor_diagnostics"][actor]["valid_action_fraction"]
                      for actor in ACTORS]
        failed_controls = sum(not controls[tid] for tid, task in by_id.items()
                              if task["workflow_sha256"] == workflow)
        below_complexity = sum(tid in complexity_mismatch for tid, task in by_id.items()
                               if task["workflow_sha256"] == workflow)
        if failed_controls:
            decision = "exclude_failed_control_source_families"
        elif below_complexity:
            decision = "hold_nonrepresentative_train_complexity"
        elif not sufficient:
            decision = "insufficient_train_evidence"
        elif (invalid_fraction is None or invalid_fraction > MAX_INFRA_FRACTION or
              any(value is None or value < MIN_ACTION_VALIDITY
                  for value in validities) or
              stats["stronger_reference_wall_limits"] / len(pairs) >
              MAX_STRONG_TIMEOUT_FRACTION):
            decision = "hold_interface_or_budget"
        elif (stats["base_success_fraction"] >= BASE_CEILING and
              stats["stronger_reference_success_fraction"] >= BASE_CEILING):
            decision = "exclude_workflow_ceiling"
        elif stats["stronger_reference_success_fraction"] <= STRONG_FLOOR:
            decision = "exclude_workflow_floor"
        elif (0.125 <= stats["base_success_fraction"] <= 0.75 and
              stats["stronger_reference_success_fraction"] >= 0.5 and
              stats["reference_minus_base_fraction"] >= 0.125):
            decision = "discriminative_train_screen"
        else:
            decision = "hold_ambiguous_separation"
        rows.append({"workflow_index": ordinal,
                     "source_family_count": len(families[workflow]),
                     "source_family_sizes": sorted(families[workflow].values()),
                     "source_family_summaries": family_summaries,
                     "passed_control_pairs": len(pairs),
                     "failed_control_tasks": failed_controls,
                     "failed_control_source_families": len({
                         task["source_family_sha256"] for tid, task in by_id.items()
                         if task["workflow_sha256"] == workflow and not controls[tid]}),
                     "below_complexity_minimum_tasks": below_complexity,
                     "infrastructure_failure_classes": dict(sorted(
                         invalid_classes_by_workflow[workflow].items())),
                     **stats, "decision": decision})
    return {
        "schema": OUTPUT_SCHEMA,
        "study_role": "nonfinal_train_only_screen_not_benchmark_result",
        "cell_id": data["cell_id"],
        "private_input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "gate_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "action_profile_sha256": profile,
        "actor_models": {actor: actor_config[actor]["model_id"] for actor in ACTORS},
        "actor_configuration_sha256": {
            actor: actor_config[actor]["configuration_sha256"] for actor in ACTORS},
        "declared_minimum_complexity": minima,
        "thresholds": {
            "minimum_paired_tasks_per_workflow": MIN_WORKFLOW_PAIRS,
            "minimum_families_per_workflow": MIN_WORKFLOW_FAMILIES,
            "minimum_pairs_per_family": MIN_PER_FAMILY,
            "minimum_valid_action_fraction": MIN_ACTION_VALIDITY,
            "maximum_infrastructure_invalid_fraction": MAX_INFRA_FRACTION,
            "maximum_stronger_reference_wall_limit_fraction": MAX_STRONG_TIMEOUT_FRACTION,
            "base_and_reference_ceiling_fraction": BASE_CEILING,
            "stronger_reference_floor_fraction": STRONG_FLOOR,
        },
        "train_task_count": len(tasks),
        "failed_control_tasks": sum(not passed for passed in controls.values()),
        "below_complexity_minimum_tasks": len(complexity_mismatch),
        "workflow_count": len(rows),
        "workflow_screens": rows,
        "all_observed_train_workflows_discriminative": all(
            row["decision"] == "discriminative_train_screen" for row in rows),
        "official_final_admissions": 0,
        "official_model_results": 0,
        "cell_specific_saved_state_audit_still_required": True,
    }
