"""Pre-result, train-only Qwen3.8 GUI SFT diagnostic.

This is deliberately separate from the 24 frozen researcher campaigns. It
cannot use their selection or final tasks, cannot admit a task, and cannot
claim application success from teacher-forced action comparisons.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import importlib
import json
from itertools import combinations
from pathlib import Path
import re
from typing import Callable

from . import scale_action_output_v066 as output_v066
from .scale_action_contract import ContractError
from .full_study_teacher_adapter_v1 import _render_turns


MODEL = "Qwen/Qwen3.8-27B"
ACTION_PROFILE = "scale-action-profile-v0.6.6"
PREREG_RELATIVE = "runtime/qwen38-vision/real-gui-diagnostic-prereg-v1.json"
PREREG_SHA256 = "8011469aca87ff324c4e1e66b317c9e3ad8e9ff21dd7d9762f3c2fbc18daf9b2"
SOURCE_SCHEMA = "cua-qwen38-real-gui-diagnostic-sources-v1"
PLAN_SCHEMA = "cua-qwen38-real-gui-diagnostic-plan-v1"
PUBLIC_PROPOSAL_SCHEMA = "cua-qwen38-real-gui-diagnostic-proposal-public-v1"
SOURCE_MODULES = {
    "desktop_impress_v066": (
        "impress", "tools.export_desktop_v066_train_sft_v1"),
    "desktop_calc_v066": (
        "calc", "tools.export_desktop_v066_calc_train_sft_v1"),
    "desktop_writer_v066": (
        "writer", "tools.export_desktop_v066_writer_train_sft_v1"),
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_SOURCES = 12
MAX_PRIVATE_BYTES = 8_000_000


class DiagnosticError(ValueError):
    """Fixed error labels; never include private instructions or model text."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DiagnosticError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def private_json(path: Path, work: Path) -> tuple[dict, bytes]:
    source = Path(path)
    require(source.is_file() and not source.is_symlink() and
            source.resolve().is_relative_to(work.resolve()) and
            source.stat().st_mode & 0o077 == 0 and
            0 < source.stat().st_size <= MAX_PRIVATE_BYTES,
            "diagnostic_private_source_missing_or_unsafe")
    raw = source.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DiagnosticError("diagnostic_private_json_invalid") from None
    require(type(value) is dict, "diagnostic_private_object_required")
    return value, raw


def load_prereg(repo_root: Path) -> tuple[dict, str]:
    path = Path(repo_root) / PREREG_RELATIVE
    require(path.is_file() and not path.is_symlink(),
            "diagnostic_prereg_missing")
    raw = path.read_bytes()
    require(digest(raw) == PREREG_SHA256,
            "diagnostic_prereg_source_changed")
    value = json.loads(raw)
    require(value["schema"] ==
            "cua-qwen38-real-gui-diagnostic-prereg-v1" and
            value["status"] == "pre_result_diagnostic_only" and
            value["model"] == MODEL and
            value["action_profile"] == ACTION_PROFILE and
            value["eligible_split"] == "train" and
            value["formal_selection_or_final_tasks_allowed"] is False and
            value["automatic_replay_after_uncertain_call"] is False and
            value["pricing_quote_is_dispatch_gate"] is False and
            value["provider_invoice_required_for_cost_claim"] is True and
            value["optimizer_steps"] == 64 and
            value["batch_size"] == 2 and
            value["state_save_after_steps"] == [16, 32, 48, 64],
            "diagnostic_prereg_contract_invalid")
    return value, digest(raw)


def load_sources(repo_root: Path, manifest_path: Path,
                 ratification_path: Path) -> tuple[list[dict], str, str]:
    """Reopen only allowlisted real v0.6.6 train GUI source adapters."""
    root = Path(repo_root).resolve()
    manifest, raw = private_json(manifest_path, root / "work")
    rows = manifest.get("sources")
    require(set(manifest) == {"schema", "sources"} and
            manifest["schema"] == SOURCE_SCHEMA and
            type(rows) is list and 0 < len(rows) <= MAX_SOURCES,
            "diagnostic_sources_manifest_invalid")
    from native_desktop_factory.v066_final_freeze import validate_ratification
    _ratification, rat_sha = validate_ratification(ratification_path)
    seen_tasks = set()
    episodes = []
    for row in rows:
        require(type(row) is dict and set(row) == {
            "kind", "episode_dir", "public_receipt"} and
            row["kind"] in SOURCE_MODULES and
            type(row["episode_dir"]) is str and
            type(row["public_receipt"]) is dict and
            set(row["public_receipt"]) == {"path", "sha256"} and
            type(row["public_receipt"]["path"]) is str and
            type(row["public_receipt"]["sha256"]) is str and
            HASH.fullmatch(row["public_receipt"]["sha256"]) is not None,
            "diagnostic_source_descriptor_invalid")
        workflow, module_name = SOURCE_MODULES[row["kind"]]
        module_path = root / (module_name.replace(".", "/") + ".py")
        require(module_path.is_file() and not module_path.is_symlink(),
                "diagnostic_source_adapter_not_available")
        module = importlib.import_module(module_name)
        require(Path(module.__file__).resolve() == module_path.resolve() and
                callable(getattr(module, "source_bound_steps", None)),
                "diagnostic_source_adapter_not_rooted")
        relative = Path(row["public_receipt"]["path"])
        require(not relative.is_absolute() and len(relative.parts) == 3 and
                relative.parts[:2] == ("docs", "evidence") and
                relative.suffix == ".json" and
                ".." not in relative.parts,
                "diagnostic_public_source_reference_unsafe")
        public_path = root / relative
        require(public_path.is_file() and not public_path.is_symlink() and
                digest(public_path.read_bytes()) ==
                row["public_receipt"]["sha256"],
                "diagnostic_public_source_changed")
        public = json.loads(public_path.read_bytes())
        require(type(public) is dict and
                public.get("status") ==
                "evaluator_scripted_public_train_gui_rendered_offline" and
                public.get("cell_id") == "desktop-native" and
                public.get("model") == MODEL and
                public.get("action_profile") == ACTION_PROFILE and
                public.get("ratification_sha256") == rat_sha and
                public.get("exporter_source_sha256") ==
                digest(module_path.read_bytes()) and
                public.get("provider_calls") == 0 and
                public.get("benchmark_score") is None and
                public.get("official_final_admissions") == 0,
                "diagnostic_public_source_not_train_only")
        episode_dir = Path(row["episode_dir"])
        require(episode_dir.is_absolute() and episode_dir.is_dir() and
                not episode_dir.is_symlink() and
                episode_dir.stat().st_mode & 0o077 == 0,
                "diagnostic_raw_episode_missing_or_unsafe")
        source, turns = module.source_bound_steps(episode_dir)
        task_id, package_sha = source.get("task_id"), source.get("package_sha256")
        require(type(task_id) is str and task_id and
                "-official-" not in task_id and
                "-selection-" not in task_id and
                task_id not in seen_tasks and
                type(package_sha) is str and HASH.fullmatch(package_sha) and
                source.get("gui_receipt_sha256") ==
                public.get("source_gui_receipt_sha256") and
                source.get("saved_artifact_sha256") ==
                public.get("saved_artifact_sha256") and
                type(turns) is list and
                len(turns) == public.get("real_gui_train_turns") and
                len(turns) >= 5 and
                len(source.get("source_frames", [])) == len(turns),
                "diagnostic_real_gui_source_not_independently_bound")
        seen_tasks.add(task_id)
        for step, turn in enumerate(turns):
            observation = turn.get("observation") if type(turn) is dict else None
            action = turn.get("action") if type(turn) is dict else None
            require(observation is not None and
                    observation.task_id == task_id and
                    observation.task_binding_sha256 == package_sha and
                    observation.step == step and
                    type(action) is dict and
                    action.get("type") in {
                        "click", "double_click", "key", "type", "wait",
                        "scroll", "fill", "drag", "finish"} and
                    digest(observation.screenshot_bytes) ==
                    source["source_frames"][step]["image_sha256"],
                    "diagnostic_source_turn_frame_or_action_changed")
            output_v066.normalize_model_action(
                canonical(action).decode().strip(), observation,
                current_frame_id=observation.frame_id)
        episodes.append({
            "kind": row["kind"], "workflow": workflow,
            "task_id": task_id, "package_sha256": package_sha,
            "episode_dir": str(episode_dir),
            "public_receipt_path": relative.as_posix(),
            "public_receipt_sha256": row["public_receipt"]["sha256"],
            "source_gui_receipt_sha256": source["gui_receipt_sha256"],
            "source_adapter_sha256": digest(module_path.read_bytes()),
            "saved_artifact_sha256": source["saved_artifact_sha256"],
            "turns": turns,
        })
    return episodes, digest(raw), rat_sha


def split_tasks(episodes: list[dict], prereg: dict) -> tuple[list[int], list[int]]:
    """Choose a task-disjoint holdout without reading action labels/scores."""
    required = prereg["minimum_distinct_tasks"]
    workflows = {row["workflow"] for row in episodes}
    require(len(episodes) >= required and
            len(workflows) >= prereg["minimum_distinct_workflows"],
            "diagnostic_distinct_train_workflows_not_ready")
    denominator = prereg["holdout_fraction_denominator"]
    numerator = prereg["holdout_fraction_numerator"]
    count = max(1, (len(episodes) * numerator + denominator - 1) // denominator)
    candidates = list(combinations(range(len(episodes)), count))
    seed = prereg["split_seed"]
    candidates.sort(key=lambda indexes: digest(canonical({
        "seed": seed,
        "tasks": sorted((episodes[index]["task_id"],
                         episodes[index]["package_sha256"])
                        for index in indexes)})))
    for holdout in candidates:
        holdout_set = set(holdout)
        train = [index for index in range(len(episodes))
                 if index not in holdout_set]
        if (sum(len(episodes[index]["turns"]) for index in holdout) >=
                prereg["minimum_holdout_turns"] and
            sum(len(episodes[index]["turns"]) for index in train) >=
                prereg["minimum_training_turns"] and
            len({episodes[index]["workflow"] for index in train}) >= 2):
            return train, list(holdout)
    raise DiagnosticError("diagnostic_task_disjoint_holdout_not_ready")


def schedule(train_lengths: list[int], prereg: dict) -> list[list[int]]:
    require(len(train_lengths) >= prereg["minimum_training_turns"] and
            all(type(value) is int and 0 < value <= 32768
                for value in train_lengths),
            "diagnostic_train_datum_tokens_invalid")
    total = prereg["optimizer_steps"] * prereg["batch_size"]
    require(total >= len(train_lengths),
            "diagnostic_schedule_cannot_cover_training_turns")
    order = []
    epoch = 0
    while len(order) < total:
        group = sorted(range(len(train_lengths)), key=lambda index: digest(
            canonical({"seed": prereg["split_seed"],
                       "epoch": epoch, "index": index})))
        order.extend(group)
        epoch += 1
    order = order[:total]
    require(set(order) == set(range(len(train_lengths))),
            "diagnostic_schedule_omits_train_turn")
    batch_size = prereg["batch_size"]
    return [order[index:index + batch_size]
            for index in range(0, total, batch_size)]


def nominal_quote(train_lengths: list[int], holdout_prompt_lengths: list[int],
                  batches: list[list[int]], prereg: dict) -> str:
    require(len(holdout_prompt_lengths) >= prereg["minimum_holdout_turns"] and
            all(type(value) is int and 0 < value <= 32768
                for value in holdout_prompt_lengths),
            "diagnostic_holdout_prompt_tokens_invalid")
    train_tokens = sum(train_lengths[index] for batch in batches
                       for index in batch)
    # Two identical prompt sets: one base, one final LoRA checkpoint.
    prefill = 2 * sum(holdout_prompt_lengths)
    sampled = (2 * len(holdout_prompt_lengths) *
               prereg["sampling_max_tokens"])
    rate = lambda key: Decimal(prereg[key])
    quote = ((Decimal(train_tokens) * rate(
        "train_usd_per_million_tokens") +
        Decimal(prefill) * rate("prefill_usd_per_million_tokens") +
        Decimal(sampled) * rate("sample_usd_per_million_tokens")) /
        Decimal(1_000_000) * rate("billing_multiplier_upper"))
    rounded = quote.quantize(Decimal("0.000000001"),
                             rounding=ROUND_CEILING)
    require(Decimal(0) < rounded, "diagnostic_nominal_quote_invalid")
    return str(rounded)


def materialize_plan(repo_root: Path, manifest_path: Path,
                     ratification_path: Path,
                     renderer_loader: Callable[[], object]) -> tuple:
    """Reopen source bytes and render both splits without provider access."""
    root = Path(repo_root).resolve()
    prereg, prereg_sha = load_prereg(root)
    episodes, manifest_sha, rat_sha = load_sources(
        root, manifest_path, ratification_path)
    train_tasks, holdout_tasks = split_tasks(episodes, prereg)
    vision = renderer_loader()
    require(vision.identity.get("model") == MODEL and
            vision.identity.get("renderer") ==
            "qwen3_5_disable_thinking" and
            vision.identity.get("image_processor") ==
            "Qwen2VLImageProcessorPil",
            "diagnostic_renderer_identity_invalid")
    train_refs = [[index, step] for index in train_tasks
                  for step in range(len(episodes[index]["turns"]))]
    holdout_refs = [[index, step] for index in holdout_tasks
                    for step in range(len(episodes[index]["turns"]))]
    def render(refs):
        turns = [episodes[index]["turns"][step] for index, step in refs]
        task_ids = [episodes[index]["task_id"] for index in
                    sorted({index for index, _ in refs})]
        receipts = [episodes[index]["source_gui_receipt_sha256"]
                    for index in sorted({index for index, _ in refs})]
        return _render_turns("desktop-native", task_ids, receipts,
                             turns, vision)
    train_batch, holdout_batch = render(train_refs), render(holdout_refs)
    train_lengths = train_batch.receipt["datum_token_lengths"]
    holdout_lengths = holdout_batch.receipt["prompt_token_lengths"]
    batches = schedule(train_lengths, prereg)
    quote = nominal_quote(train_lengths, holdout_lengths,
                          batches, prereg)
    source_rows = [{key: value for key, value in row.items()
                    if key != "turns"} for row in episodes]
    plan = {
        "schema": PLAN_SCHEMA,
        "status": "eligible_pending_immutable_public_freeze",
        "prereg_sha256": prereg_sha,
        "sources_manifest_sha256": manifest_sha,
        "ratification_sha256": rat_sha,
        "model": MODEL, "action_profile": ACTION_PROFILE,
        "source_rows": source_rows,
        "train_source_indexes": train_tasks,
        "holdout_source_indexes": holdout_tasks,
        "train_turn_refs": train_refs,
        "holdout_turn_refs": holdout_refs,
        "train_render_receipt_sha256": digest(canonical(train_batch.receipt)),
        "holdout_render_receipt_sha256": digest(canonical(
            holdout_batch.receipt)),
        "renderer_identity": vision.identity,
        "training_datum_lengths": train_lengths,
        "holdout_prompt_lengths": holdout_lengths,
        "batches": batches,
        "scheduled_train_tokens": sum(train_lengths[index]
                                      for batch in batches for index in batch),
        "nominal_quote_usd": quote,
        "provider_invoice_usd": None,
        "benchmark_score": None,
    }
    proposal = {
        "schema": PUBLIC_PROPOSAL_SCHEMA,
        "status": "awaiting_reviewer_freeze_no_paid_calls",
        "plan_sha256": digest(canonical(plan)),
        "prereg_sha256": prereg_sha,
        "sources_manifest_sha256": manifest_sha,
        "ratification_sha256": rat_sha,
        "source_workflow_counts": dict(sorted(Counter(
            row["workflow"] for row in episodes).items())),
        "train_task_count": len(train_tasks),
        "holdout_task_count": len(holdout_tasks),
        "train_turn_count": len(train_refs),
        "holdout_turn_count": len(holdout_refs),
        "optimizer_steps": prereg["optimizer_steps"],
        "batch_size": prereg["batch_size"],
        "scheduled_train_tokens": plan["scheduled_train_tokens"],
        "nominal_quote_usd": quote,
        "pricing_quote_is_dispatch_gate": False,
        "provider_invoice_usd": None,
        "provider_calls": 0,
        "selection_tasks_used": 0,
        "final_tasks_used": 0,
        "benchmark_score": None,
    }
    holdout_turns = [episodes[index]["turns"][step]
                     for index, step in holdout_refs]
    return (plan, proposal, train_batch, holdout_batch,
            holdout_turns, vision)


def prepare_plan(repo_root: Path, manifest_path: Path,
                 ratification_path: Path,
                 renderer_loader: Callable[[], object]) -> tuple[dict, dict]:
    """Return a private exact plan and a field-limited public proposal."""
    plan, proposal, *_ = materialize_plan(
        repo_root, manifest_path, ratification_path, renderer_loader)
    return plan, proposal


def score_action_text(text: str, observation, reference: dict) -> dict:
    """Teacher-forced next-action agreement; never an application score."""
    require(type(text) is str and type(reference) is dict,
            "diagnostic_sample_or_reference_invalid")
    try:
        parsed = output_v066.normalize_model_action(
            text, observation, current_frame_id=observation.frame_id)
    except ContractError as exc:
        return {"format_valid": False, "action_type_match": False,
                "payload_exact_match": False,
                "error_type": type(exc).__name__}
    payload = {key: value for key, value in parsed.items()
               if key not in {"version", "task_id", "task_binding_sha256",
                              "step", "frame_id", "memory"}}
    target = {key: value for key, value in reference.items()
              if key not in {"version", "task_id", "task_binding_sha256",
                             "step", "frame_id", "memory"}}
    return {"format_valid": True,
            "action_type_match": payload.get("type") == target.get("type"),
            "payload_exact_match": payload == target,
            "error_type": None}


__all__ = ["DiagnosticError", "load_prereg", "load_sources", "split_tasks",
           "schedule", "nominal_quote", "materialize_plan", "prepare_plan",
           "score_action_text", "canonical", "digest"]
