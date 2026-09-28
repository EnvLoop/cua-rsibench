"""Independently reopen one completed Qwen real-GUI diagnostic; no provider IO.

The output deliberately excludes task identities, instructions, raw actions,
screenshots, model text, checkpoint paths, sessions and credentials. This is a
development diagnostic, never a formal researcher campaign or task score.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import importlib
import json
from pathlib import Path
import subprocess

from cursibench.scale_action_contract import ContractError
from cursibench.scale_action_output_v066 import normalize_model_action


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
WITNESS_RELATIVE = "docs/evidence/qwen38-real-gui-diagnostic-freeze.json"
PREREG_RELATIVE = "runtime/qwen38-vision/real-gui-diagnostic-prereg-v1.json"
SOURCE_MODULES = {
    "desktop_impress_v066": ("impress", "tools.export_desktop_v066_train_sft_v1"),
    "desktop_calc_v066": ("calc", "tools.export_desktop_v066_calc_train_sft_v1"),
    "desktop_writer_v066": ("writer", "tools.export_desktop_v066_writer_train_sft_v1"),
}


class AuditError(ValueError):
    """Only fixed, non-sensitive failure codes are permitted."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def private_bytes(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0 and
            0 < path.stat().st_size <= 32_000_000,
            "private_evidence_missing_or_unsafe")
    return path.read_bytes()


def parse(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AuditError("evidence_json_invalid") from None
    require(type(value) is dict, "evidence_object_required")
    return value


def frozen_witness(commit: str) -> tuple[dict, str]:
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit),
            "public_freeze_commit_invalid")
    completed = subprocess.run(
        ["git", "-C", str(PUBLIC_ROOT), "show",
         f"{commit}:{WITNESS_RELATIVE}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    require(completed.returncode == 0 and 0 < len(completed.stdout) < 100_000,
            "public_freeze_git_object_missing")
    raw = completed.stdout
    require((PUBLIC_ROOT / WITNESS_RELATIVE).read_bytes() == raw,
            "public_freeze_checkout_differs_from_commit")
    value = parse(raw)
    require(value.get("status") == "frozen_before_diagnostic_paid_dispatch" and
            value.get("diagnostic_only") is True and
            value.get("selection_and_final_task_access") is False and
            value.get("paid_diagnostic_calls_before_freeze") == 0,
            "public_freeze_invalid")
    return value, digest(raw)


def source_turns(plan: dict, manifest: dict, public_root: Path) -> list[list[dict]]:
    rows = plan.get("source_rows")
    descriptors = manifest.get("sources")
    require(type(rows) is list and len(rows) == 3 and
            type(descriptors) is list and len(descriptors) == len(rows),
            "source_manifest_or_plan_invalid")
    found = []
    task_ids = set()
    for row, descriptor in zip(rows, descriptors):
        require(type(row) is dict and type(descriptor) is dict and
                descriptor.get("kind") == row.get("kind") and
                descriptor.get("episode_dir") == row.get("episode_dir") and
                descriptor.get("public_receipt") == {
                    "path": row.get("public_receipt_path"),
                    "sha256": row.get("public_receipt_sha256")},
                "source_manifest_descriptor_changed")
        require(row["kind"] in SOURCE_MODULES,
                "source_adapter_not_allowlisted")
        workflow, module_name = SOURCE_MODULES[row["kind"]]
        require(row.get("workflow") == workflow,
                "source_workflow_changed")
        module = importlib.import_module(module_name)
        module_path = public_root / (module_name.replace(".", "/") + ".py")
        require(Path(module.__file__).resolve() == module_path.resolve() and
                digest(module_path.read_bytes()) ==
                row.get("source_adapter_sha256"),
                "source_adapter_changed")
        receipt_path = public_root / row["public_receipt_path"]
        require(receipt_path.is_file() and not receipt_path.is_symlink() and
                digest(receipt_path.read_bytes()) ==
                row["public_receipt_sha256"],
                "source_public_receipt_changed")
        receipt = parse(receipt_path.read_bytes())
        require(receipt.get("status") ==
                "evaluator_scripted_public_train_gui_rendered_offline" and
                receipt.get("provider_calls") == 0 and
                receipt.get("official_final_admissions") == 0,
                "source_not_public_train_only")
        source, turns = module.source_bound_steps(Path(row["episode_dir"]))
        require(source.get("task_id") == row.get("task_id") and
                source.get("task_id") not in task_ids and
                source.get("package_sha256") == row.get("package_sha256") and
                source.get("gui_receipt_sha256") ==
                row.get("source_gui_receipt_sha256") and
                source.get("saved_artifact_sha256") ==
                row.get("saved_artifact_sha256") and
                type(turns) is list and
                len(turns) == receipt.get("real_gui_train_turns"),
                "source_episode_not_reproducible")
        task_ids.add(source["task_id"])
        found.append(turns)
    return found


def reference_score(text: str, turn: dict) -> dict:
    observation = turn["observation"]
    try:
        action = normalize_model_action(
            text, observation, current_frame_id=observation.frame_id)
    except ContractError as exc:
        return {"format_valid": False, "action_type_match": False,
                "payload_exact_match": False,
                "error_type": type(exc).__name__}
    excluded = {"version", "task_id", "task_binding_sha256", "step",
                "frame_id", "memory"}
    observed = {k: v for k, v in action.items() if k not in excluded}
    reference = {k: v for k, v in turn["action"].items()
                 if k not in excluded}
    return {"format_valid": True,
            "action_type_match": observed.get("type") == reference.get("type"),
            "payload_exact_match": observed == reference,
            "error_type": None}


def independently_summarize(pairs: list[dict]) -> dict:
    require(bool(pairs), "matched_pairs_missing")
    summary = {"holdout_turns": len(pairs)}
    for metric in ("format_valid", "action_type_match", "payload_exact_match"):
        for kind in ("base", "lora"):
            summary[f"{kind}_{metric}"] = sum(bool(row[kind][metric])
                                               for row in pairs)
        summary[f"paired_{metric}_gain"] = sum(
            row["lora"][metric] and not row["base"][metric]
            for row in pairs)
        summary[f"paired_{metric}_loss"] = sum(
            row["base"][metric] and not row["lora"][metric]
            for row in pairs)
    non_wait = [row for row in pairs if row["reference_type"] != "wait"]
    summary["non_wait_reference_turns"] = len(non_wait)
    for kind in ("base", "lora"):
        for metric in ("action_type_match", "payload_exact_match"):
            summary[f"{kind}_non_wait_{metric}"] = sum(
                bool(row[kind][metric]) for row in non_wait)
    return summary


def audit(*, private_root: Path, run_dir: Path, commit: str) -> dict:
    plan_path = private_root / "work/full-study/qwen38-real-gui-diagnostic-plan-20260928.private.json"
    manifest_path = private_root / "work/full-study/qwen38-real-gui-diagnostic-sources-20260928.private.json"
    ratification_path = private_root / "work/full-study/v066-caret-amended-control-ratification-20260928.private.json"
    require(run_dir.resolve().is_relative_to((private_root / "work").resolve())
            and run_dir.is_dir() and not run_dir.is_symlink() and
            run_dir.stat().st_mode & 0o077 == 0,
            "run_directory_missing_or_unsafe")
    plan_raw = private_bytes(plan_path)
    manifest_raw = private_bytes(manifest_path)
    ratification_raw = private_bytes(ratification_path)
    plan, manifest = parse(plan_raw), parse(manifest_raw)
    require(plan_raw == canonical(plan) and
            plan.get("schema") == "cua-qwen38-real-gui-diagnostic-plan-v1" and
            plan.get("sources_manifest_sha256") == digest(manifest_raw) and
            plan.get("ratification_sha256") == digest(ratification_raw) and
            plan.get("model") == "Qwen/Qwen3.8-27B" and
            plan.get("action_profile") == "scale-action-profile-v0.6.6",
            "private_plan_or_source_binding_invalid")
    prereg_raw = (PUBLIC_ROOT / PREREG_RELATIVE).read_bytes()
    prereg = parse(prereg_raw)
    require(digest(prereg_raw) == plan.get("prereg_sha256") and
            prereg.get("eligible_split") == "train" and
            prereg.get("formal_selection_or_final_tasks_allowed") is False,
            "preregistration_changed")
    witness, witness_sha = frozen_witness(commit)
    plan_sha = digest(plan_raw)
    require(witness.get("plan_sha256") == plan_sha and
            witness.get("prereg_sha256") == digest(prereg_raw) and
            witness.get("student_model") == plan["model"] and
            witness.get("optimizer_steps") == 64,
            "public_freeze_does_not_bind_plan")
    sources = source_turns(plan, manifest, PUBLIC_ROOT)
    train_indexes = plan.get("train_source_indexes")
    holdout_indexes = plan.get("holdout_source_indexes")
    require(type(train_indexes) is list and type(holdout_indexes) is list and
            len(train_indexes) == 2 and len(holdout_indexes) == 1 and
            set(train_indexes).isdisjoint(holdout_indexes) and
            set(train_indexes + holdout_indexes) == set(range(len(sources))) and
            len({plan["source_rows"][i]["workflow"] for i in train_indexes}) == 2,
            "task_disjoint_split_invalid")
    train_refs = [[i, step] for i in train_indexes
                  for step in range(len(sources[i]))]
    holdout_refs = [[i, step] for i in holdout_indexes
                    for step in range(len(sources[i]))]
    require(plan.get("train_turn_refs") == train_refs and
            plan.get("holdout_turn_refs") == holdout_refs and
            len(train_refs) >= prereg["minimum_training_turns"] and
            len(holdout_refs) >= prereg["minimum_holdout_turns"],
            "turn_partition_invalid")
    lengths, prompt_lengths, batches = (
        plan["training_datum_lengths"], plan["holdout_prompt_lengths"],
        plan["batches"])
    require(len(lengths) == len(train_refs) and
            len(prompt_lengths) == len(holdout_refs) and
            len(batches) == prereg["optimizer_steps"] == 64 and
            all(type(batch) is list and len(batch) == 2 and
                all(type(i) is int and 0 <= i < len(lengths) for i in batch)
                for batch in batches) and
            {i for batch in batches for i in batch} == set(range(len(lengths))) and
            sum(lengths[i] for batch in batches for i in batch) ==
            plan["scheduled_train_tokens"],
            "training_schedule_invalid")

    journal_raw = private_bytes(run_dir / "events.private.jsonl")
    try:
        events = [json.loads(line) for line in journal_raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AuditError("journal_invalid_json") from None
    require(bool(events), "journal_empty")
    previous = None
    operations = {}
    for index, event in enumerate(events):
        require(type(event) is dict and event.get("previous") == previous and
                event.get("hash") == digest(canonical({
                    k: v for k, v in event.items() if k != "hash"})),
                "journal_hash_chain_invalid")
        previous = event["hash"]
        if index == 0:
            require(event.get("kind") == "header" and
                    event.get("data", {}).get("plan_sha256") == plan_sha and
                    event.get("data", {}).get(
                        "immutable_public_witness_sha256") == witness_sha and
                    event.get("data", {}).get("official_campaign") is False,
                    "journal_header_not_bound")
            continue
        op = event.get("operation")
        require(type(op) is int and op > 0 and
                event.get("sequence") == index and
                event.get("kind") in {"intent", "completed", "uncertain"},
                "journal_event_invalid")
        if event["kind"] == "intent":
            require(op == len(operations) + 1,
                    "journal_operation_order_invalid")
            raw = private_bytes(run_dir / f"operation-{op:04d}.request.private.json")
            require(digest(raw) == event.get("data", {}).get("request_sha256"),
                    "journal_request_bytes_changed")
            operations[op] = {"name": event["data"]["name"],
                              "intent_epoch_seconds": event["data"].get(
                                  "epoch_seconds"),
                              "request": parse(raw), "terminal": None}
        else:
            require(op in operations and operations[op]["terminal"] is None and
                    event["kind"] == "completed",
                    "journal_uncertain_or_duplicate_terminal")
            raw = private_bytes(run_dir / f"operation-{op:04d}.result.private.json")
            require(digest(raw) == event.get("data", {}).get("result_sha256"),
                    "journal_result_bytes_changed")
            operations[op]["terminal"] = parse(raw)
    require(all(row["terminal"] is not None for row in operations.values()),
            "diagnostic_run_not_terminal")
    expected_names = ["service_open", "train_client_open"]
    for step in range(1, 65):
        expected_names.extend(("forward_backward", "optimizer_step"))
        if step in (16, 32, 48, 64):
            expected_names.append("save_optimizer_state")
    expected_names.extend(("save_sampler_weights", "base_sampler_open",
                           "lora_sampler_open"))
    expected_names.extend(["matched_sample"] * (2 * len(holdout_refs)))
    expected_names.append("service_close")
    ordered = [operations[i] for i in range(1, len(operations) + 1)]
    require([row["name"] for row in ordered] == expected_names,
            "provider_operation_sequence_invalid")
    cursor = 2
    for step, batch in enumerate(batches, 1):
        forward, optim = ordered[cursor:cursor + 2]
        require(forward["request"] == {
            "step": step, "batch_indexes": batch,
            "datum_token_lengths": [lengths[i] for i in batch],
            "train_render_receipt_sha256": plan["train_render_receipt_sha256"]
        } and forward["terminal"].get("status") == "completed" and
            optim["request"] == {"step": step,
                                 "learning_rate": prereg["learning_rate"]} and
            optim["terminal"].get("status") == "completed",
            "provider_training_step_not_bound")
        cursor += 2
        if step in (16, 32, 48, 64):
            row = ordered[cursor]
            require(row["request"] == {"step": step} and
                    row["terminal"].get("status") == "completed" and
                    type(row["terminal"].get("checkpoint_path")) is str,
                    "optimizer_state_save_not_bound")
            cursor += 1
    sampler = ordered[cursor]
    require(sampler["request"] == {"step": 64} and
            sampler["terminal"].get("status") == "completed" and
            type(sampler["terminal"].get("checkpoint_path")) is str,
            "final_sampler_save_invalid")
    checkpoint_sha = digest(sampler["terminal"]["checkpoint_path"].encode())
    cursor += 1
    require(ordered[cursor]["request"] == {"model": plan["model"]} and
            ordered[cursor]["terminal"].get("reported_base_model") ==
            plan["model"] and
            ordered[cursor + 1]["request"] == {
                "checkpoint_path_sha256": checkpoint_sha} and
            ordered[cursor + 1]["terminal"].get("reported_base_model") ==
            plan["model"], "matched_sampler_open_invalid")
    cursor += 2
    pairs = []
    expiration_pairs = []
    sample_tokens = 0
    output_token_lengths = []
    output_prefixes = Counter()
    direct_json_shapes = Counter()
    corrected_errors = Counter()
    for index, (source_index, source_step) in enumerate(holdout_refs):
        scored = {}
        expired_scored = {}
        order = ("base", "lora") if index % 2 == 0 else ("lora", "base")
        for kind in order:
            row = ordered[cursor]
            request, response = row["request"], row["terminal"]
            require(request == {
                "holdout_ordinal": index, "kind": kind,
                "prompt_length": prompt_lengths[index],
                "holdout_render_receipt_sha256":
                    plan["holdout_render_receipt_sha256"],
                "max_tokens": prereg["sampling_max_tokens"],
                "temperature": prereg["sampling_temperature"],
                "seed": prereg["sampling_seed"]} and
                response.get("status") == "completed" and
                type(response.get("text")) is str and
                type(response.get("output_tokens")) is int and
                0 <= response["output_tokens"] <=
                prereg["sampling_max_tokens"],
                "matched_sample_request_or_response_invalid")
            sample_tokens += response["output_tokens"]
            output_token_lengths.append(response["output_tokens"])
            raw_text = response["text"]
            trimmed = raw_text.lstrip()
            output_prefixes[
                "json_object" if trimmed.startswith("{") else
                "code_fence" if trimmed.startswith("```") else
                "think_tag" if trimmed.startswith("<think>") else
                "other"] += 1
            try:
                parsed_text = json.loads(raw_text)
                direct_json_shapes[
                    "object" if type(parsed_text) is dict else "other_json"] += 1
            except json.JSONDecodeError:
                direct_json_shapes["not_direct_json"] += 1
            turn = sources[source_index][source_step]
            scored[kind] = reference_score(raw_text, turn)
            if not scored[kind]["format_valid"]:
                corrected_errors[scored[kind]["error_type"]] += 1
            expired_observation = replace(turn["observation"],
                                          issued_at=0.0, expires_at=1.0)
            expired_scored[kind] = reference_score(
                raw_text, {**turn, "observation": expired_observation})
            cursor += 1
        reference_type = sources[source_index][source_step]["action"]["type"]
        pairs.append({"reference_type": reference_type, **scored})
        expiration_pairs.append({"reference_type": reference_type,
                                 **expired_scored})
    require(ordered[cursor]["request"] == {"status": "success"} and
            ordered[cursor]["terminal"].get("status") == "closed" and
            cursor + 1 == len(ordered), "service_close_invalid")
    result_raw = private_bytes(run_dir / "diagnostic-result.private.json")
    result = parse(result_raw)
    summary = independently_summarize(pairs)
    expiration_summary = independently_summarize(expiration_pairs)
    require(result.get("schema") ==
            "cua-qwen38-real-gui-diagnostic-result-private-v1" and
            result.get("status") ==
            "train_domain_action_format_diagnostic_completed" and
            result.get("plan_sha256") == plan_sha and
            result.get("checkpoint_path_sha256") == checkpoint_sha and
            result.get("checkpoint_path") == sampler["terminal"]["checkpoint_path"],
            "private_result_identity_or_checkpoint_changed")
    require(type(result.get("per_turn")) is list and
            len(result["per_turn"]) == len(expiration_pairs),
            "private_result_pair_count_differs")
    for pair_index, (saved_pair, reopened_pair) in enumerate(
            zip(result["per_turn"], expiration_pairs)):
        require(saved_pair == reopened_pair,
                f"private_result_pair_{pair_index:02d}_not_explained_by_expiry")
    require(result.get("summary") == expiration_summary,
            "private_result_summary_not_explained_by_expiry")
    first_intent_at = ordered[0]["intent_epoch_seconds"]
    first_sample_at = next(row["intent_epoch_seconds"] for row in ordered
                           if row["name"] == "matched_sample")
    frame_ttl = sources[holdout_refs[0][0]][holdout_refs[0][1]][
        "observation"].limits.frame_ttl_seconds
    require(type(first_intent_at) is int and
            type(first_sample_at) is int and
            first_sample_at - first_intent_at > frame_ttl and
            all(row[kind]["error_type"] == "ContractError"
                for row in expiration_pairs for kind in ("base", "lora")),
            "saved_scoring_expiry_cause_unproven")
    require(result.get("usage") == {
                "scheduled_training_tokens": plan["scheduled_train_tokens"],
                "rendered_sampling_prompt_tokens": 2 * sum(prompt_lengths),
                "observed_sample_output_tokens": sample_tokens,
                "provider_billed_tokens": None,
            }, "private_result_usage_differs")
    require(result.get("provider_invoice_usd") is None and
            result.get("application_success_estimate") is None and
            result.get("benchmark_score") is None,
            "private_result_forbidden_score_or_cost_present")
    return {
        "schema": "cua-qwen38-real-gui-independent-result-audit-public-v1",
        "status": "original_saved_scores_invalid_due_to_expired_frame_offline_rescore",
        "independent_auditor_source_sha256": digest(Path(__file__).read_bytes()),
        "public_freeze_commit": commit,
        "public_freeze_sha256": witness_sha,
        "plan_sha256": plan_sha,
        "prereg_sha256": digest(prereg_raw),
        "sources_manifest_sha256": digest(manifest_raw),
        "journal_sha256": digest(journal_raw),
        "private_result_sha256": digest(result_raw),
        "source_workflows": dict(sorted(Counter(
            row["workflow"] for row in plan["source_rows"]).items())),
        "train_task_count": len(train_indexes),
        "train_turn_count": len(train_refs),
        "holdout_task_count": len(holdout_indexes),
        "holdout_turn_count": len(holdout_refs),
        "task_disjoint_within_public_train": True,
        "optimizer_steps": 64,
        "batch_size": 2,
        "optimizer_state_saves_completed": 4,
        "final_sampler_weights_saved": True,
        "final_sampler_checkpoint_sha256": checkpoint_sha,
        "base_and_lora_samplers_opened": True,
        "service_close_completed": True,
        "completed_provider_operations": len(ordered),
        "uncertain_or_open_provider_operations": 0,
        "scheduled_training_tokens": plan["scheduled_train_tokens"],
        "rendered_sampling_prompt_tokens": 2 * sum(prompt_lengths),
        "observed_sample_output_tokens": sample_tokens,
        "sample_output_token_min": min(output_token_lengths),
        "sample_output_token_max": max(output_token_lengths),
        "sample_output_at_max_tokens": sum(
            length == prereg["sampling_max_tokens"]
            for length in output_token_lengths),
        "sample_prefix_categories": dict(sorted(output_prefixes.items())),
        "sample_direct_json_shapes": dict(sorted(direct_json_shapes.items())),
        "corrected_parser_error_types": dict(sorted(corrected_errors.items())),
        "first_provider_intent_to_first_sample_seconds":
            first_sample_at - first_intent_at,
        "live_frame_ttl_seconds": frame_ttl,
        "original_saved_scores_valid": False,
        "offline_rescore_from_same_saved_sample_texts": True,
        "new_provider_calls_for_correction": 0,
        "provider_billed_tokens": None,
        "nominal_planning_quote_usd": plan["nominal_quote_usd"],
        "provider_invoice_usd": None,
        "billing_freshness_complete": None,
        "selection_tasks_used": 0,
        "final_tasks_used": 0,
        "official_researcher_campaigns": 0,
        "application_success_estimate": None,
        "benchmark_score": None,
        "original_expired_frame_summary": expiration_summary,
        "corrected_same_sample_offline_summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--public-freeze-commit", required=True)
    args = parser.parse_args()
    try:
        result = audit(private_root=args.private_root.resolve(),
                       run_dir=args.run_dir.resolve(),
                       commit=args.public_freeze_commit)
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        print(json.dumps({
            "status": "refused",
            "reason_type": type(exc).__name__,
            "reason_code": str(exc) if isinstance(exc, AuditError) else None,
        }, sort_keys=True))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
