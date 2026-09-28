"""Audit one preserved failed original Odoo train pilot without live services.

Reads saved private train evidence and immutable Git objects. The only output is
a public, aggregate JSON receipt on stdout. It never starts Docker, a browser,
or a provider, and it does not write to the train worker or attempted run.
"""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess


SCHEMA = "envloop-odoo-v066-failed-train-pilot-source-bound-audit-v1"
OLD_REVISION = "0f31866c72eb2c36a61313c27531983f636f438f"
OLD_RECORDER = "tools/record_odoo_v066_train_gui_v1.py"
OLD_VERIFIER = "enterprise_fallback/odoo18/verify.py"
OLD_PILOT_AUDITOR = "enterprise_fallback/odoo18/v066_requalification_pilot.py"
FREEZE_SCHEMA = "envloop-odoo-v066-train-recorder-code-freeze-v1"
PLAN_SCHEMA = "envloop-odoo-v066-prospective-gui-requalification-plan-v1"
BINDING_SCHEMA = "envloop-odoo-v066-train-pilot-binding-v1"
START_SCHEMA = "envloop-odoo-v066-train-gui-recorder-v1"
TRACE_SCHEMA = "envloop-odoo-v066-gui-control-trace-v1"
INTENT_SCHEMA = "envloop-odoo-v066-pre-dispatch-action-intent-v1"
RESULT_SCHEMA = "envloop-odoo-v066-dispatch-result-v1"

COMMON_SOURCE_FILES = {
    "full_action_validator_v06": "src/cursibench/scale_action_contract.py",
    "full_action_extension_v066": "src/cursibench/scale_action_contract_v066.py",
    "minimal_output_v065_dependency": "src/cursibench/scale_action_output_v065.py",
    "minimal_output_v066": "src/cursibench/scale_action_output_v066.py",
    "qwen_vision_proxy": "src/cursibench/scale_vision_proxy.py",
}


class AuditError(RuntimeError):
    """A saved claim is missing or inconsistent with source-bound bytes."""


def need(condition: bool, code: str) -> None:
    if not condition:
        raise AuditError(code)


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def raw_file(path: Path) -> bytes:
    need(path.is_file() and not path.is_symlink(), "missing_or_linked_evidence")
    need(path.stat().st_size <= 32_000_000, "oversized_evidence")
    return path.read_bytes()


def json_file(path: Path) -> dict:
    try:
        value = json.loads(raw_file(path))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError("invalid_evidence_json") from exc
    need(type(value) is dict, "invalid_evidence_json_shape")
    return value


def git_blob(repo: Path, revision: str, relative: str) -> bytes:
    need(re.fullmatch(r"[0-9a-f]{40}", revision) is not None,
         "invalid_old_revision")
    need(relative and not Path(relative).is_absolute() and
         ".." not in Path(relative).parts, "invalid_source_reference")
    proc = subprocess.run(["git", "show", f"{revision}:{relative}"],
                          cwd=repo, capture_output=True, check=False)
    need(proc.returncode == 0, "old_git_source_unavailable")
    return proc.stdout


def pure_old_verifier(source: bytes) -> dict:
    """Load only source-bound pure functions, with no module import side effects."""
    names = {"keyed", "global_identity_differences", "evaluate",
             "protected_source_file_differences",
             "protected_source_store_path_differences"}
    tree = ast.parse(source, filename=OLD_VERIFIER)
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    need({node.name for node in selected} == names,
         "old_pure_verifier_functions_missing")
    isolated = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace: dict = {}
    exec(compile(isolated, OLD_VERIFIER, "exec"), namespace)
    return namespace


def evidence_ref(attempt: Path, ref: dict, expected: str) -> str:
    need(type(ref) is dict and ref.get("path") == expected and
         type(ref.get("sha256")) is str, "action_reference_invalid")
    path = attempt / expected
    need(digest(raw_file(path)) == ref["sha256"],
         "action_reference_sha_mismatch")
    return ref["sha256"]


def audit(*, attempt: Path, train_private: Path, binding_path: Path,
          private_plan_path: Path, public_plan_path: Path, freeze_path: Path,
          repo: Path, revision: str = OLD_REVISION) -> dict:
    need(not attempt.is_symlink() and not train_private.is_symlink(),
         "linked_private_evidence")
    attempt = attempt.resolve(strict=True)
    train_private = train_private.resolve(strict=True)
    repo = repo.resolve(strict=True)
    need(attempt.parent.parent == train_private and
         attempt.parent.name == "v066_requalification_runs" and
         train_private.name == "private" and
         train_private.parent.name == "train", "attempt_not_train_private")
    freeze_raw = raw_file(freeze_path)
    freeze = json_file(freeze_path)
    public_raw = raw_file(public_plan_path)
    public = json_file(public_plan_path)
    private_raw = raw_file(private_plan_path)
    plan = json_file(private_plan_path)
    binding_raw = raw_file(binding_path)
    binding = json_file(binding_path)
    recorder_source = git_blob(repo, revision, OLD_RECORDER)
    verifier_source = git_blob(repo, revision, OLD_VERIFIER)
    pilot_auditor_source = git_blob(repo, revision, OLD_PILOT_AUDITOR)

    need(freeze.get("schema") == FREEZE_SCHEMA and
         freeze.get("status") == "frozen_before_first_live_train_gui_attempt" and
         freeze.get("live_gui_attempts_before_freeze") == 0 and
         freeze.get("provider_calls_before_freeze") == 0 and
         freeze.get("official_final_tasks_admitted") == 0 and
         freeze.get("recorder_source_sha256") == digest(recorder_source) and
         freeze.get("train_pilot_binding_sha256") == digest(binding_raw) and
         freeze.get("private_plan_sha256") == digest(private_raw) and
         freeze.get("public_plan_sha256") == digest(public_raw) and
         freeze.get("pilot_auditor_source_sha256") == digest(pilot_auditor_source),
         "old_code_freeze_unbound")
    need(plan.get("schema") == PLAN_SCHEMA and
         plan.get("official_final_tasks_admitted") == 0 and
         plan.get("model_attempts") == 0 and
         plan.get("ratification_sha256") == freeze.get("ratification_sha256") and
         public.get("schema") ==
         "envloop-odoo-v066-prospective-gui-requalification-public-v1" and
         public.get("private_plan_sha256") == digest(private_raw) and
         public.get("new_six_cell_ratification_sha256") ==
         freeze.get("ratification_sha256") and
         public.get("candidate_counts") ==
         {"train": 20, "selection": 20, "official_hidden": 100} and
         public.get("pilot_receipt_present") is False and
         public.get("official_final_tasks_admitted") == 0 and
         binding.get("schema") == BINDING_SCHEMA and
         binding.get("status") == "train_only_no_gui_attempt" and
         binding.get("selection_or_hidden_task_values_included") is False and
         binding.get("private_plan_sha256") == digest(private_raw) and
         binding.get("public_plan_sha256") == digest(public_raw) and
         binding.get("ratification_sha256") == freeze.get("ratification_sha256") and
         binding.get("pilot_auditor_source_sha256") ==
         digest(pilot_auditor_source) and
         binding.get("official_final_tasks_admitted") == 0,
         "old_private_train_binding_or_plan_invalid")
    task = binding.get("task")
    need(type(task) is dict and task.get("split") == "train" and
         task.get("family") == "purchase" and
         plan.get("pilot") == {"split": "train",
                              "task_binding_sha256": task.get("task_binding_sha256"),
                              "task_id": task.get("task_id")} and
         [row for row in plan["tasks"]["train"]
          if row.get("task_id") == task.get("task_id")] == [task] and
         binding.get("checkpoint") == plan["checkpoints"]["train"] and
         binding.get("odoo_source_sha256s") == plan.get("odoo_source_sha256s") and
         binding.get("common_action_source_sha256s") ==
         plan.get("common_action_source_sha256s"),
         "old_train_pilot_projection_invalid")
    for relative, expected in binding["odoo_source_sha256s"].items():
        need(digest(git_blob(repo, revision, relative)) == expected,
             "old_odoo_source_mismatch")
    need(binding["odoo_source_sha256s"].get(OLD_VERIFIER) ==
         digest(verifier_source), "old_verifier_source_mismatch")
    need(set(binding["common_action_source_sha256s"]) ==
         set(COMMON_SOURCE_FILES), "old_common_source_set_invalid")
    for key, relative in COMMON_SOURCE_FILES.items():
        need(digest(git_blob(repo, revision, relative)) ==
             binding["common_action_source_sha256s"][key],
             "old_common_source_mismatch")
    for file_name, checkpoint_key in (
        ("baseline.pgcustom", "db_sha256"),
        ("baseline-filestore.tgz", "filestore_sha256"),
        ("baseline_snapshot.json", "baseline_snapshot_sha256"),
        ("baseline-filestore-manifest.json", "baseline_filestore_manifest_sha256"),
    ):
        need(digest(raw_file(train_private / file_name)) ==
             binding["checkpoint"][checkpoint_key],
             "old_train_checkpoint_mismatch")

    start_raw = raw_file(attempt / "intent.private.json")
    start = json_file(attempt / "intent.private.json")
    failure_raw = raw_file(attempt / "failure.private.json")
    failure = json_file(attempt / "failure.private.json")
    trace_raw = raw_file(attempt / "gui_trace.json")
    trace = json_file(attempt / "gui_trace.json")
    need(start.get("schema") == START_SCHEMA and
         start.get("status") == "reserved_before_first_docker_or_gui_action" and
         start.get("binding_sha256") == digest(binding_raw) and
         start.get("public_plan_sha256") == digest(public_raw) and
         start.get("recorder_source_sha256") == digest(recorder_source) and
         start.get("task_binding_sha256") == task["task_binding_sha256"] and
         start.get("official_final_tasks_admitted") == 0 and
         start.get("model_attempts") == 0 and
         failure.get("schema") == START_SCHEMA and
         failure.get("status") ==
         "failed_preserve_original_attempt_no_automatic_retry" and
         failure.get("stage") == "negative_gui" and
         failure.get("error_type") == "ContractError" and
         failure.get("reset_exact") is True and
         failure.get("services_restored") is True and
         failure.get("official_final_tasks_admitted") == 0 and
         failure.get("model_attempts") == 0 and
         trace.get("schema") == TRACE_SCHEMA and
         trace.get("task_binding_sha256") == task["task_binding_sha256"],
         "saved_start_failure_or_trace_invalid")
    need("error_code" not in failure and "error_message" not in failure,
         "failure_subtype_must_be_reassessed")
    need({path.name for path in attempt.iterdir()} == {
             "actions", "frames", "intent.private.json", "failure.private.json",
             "gui_trace.json", "pre_restore.json", "baseline_sql.json",
             "positive_reload_frame.png", "positive_sql.json",
             "positive_filestore.json", "positive_store_paths.json",
             "online_positive_score.private.json", "post_restore.json",
             "restored_sql.json", "restored_filestore.json"},
         "failed_attempt_file_inventory_changed")

    actions_dir = attempt / "actions"
    frames_dir = attempt / "frames"
    need(actions_dir.is_dir() and frames_dir.is_dir() and
         not actions_dir.is_symlink() and not frames_dir.is_symlink(),
         "saved_action_or_frame_directory_missing")
    expected_actions = set()
    expected_frames = set()
    for step in range(17):
        stem = f"step-{step:03d}"
        expected_frames.add(stem + ".png")
        expected_actions.update(stem + suffix for suffix in
                                ("-instruction.txt", "-visible.txt",
                                 "-assistant.json"))
        if step < 16:
            expected_actions.update(stem + suffix for suffix in
                                    ("-intent.private.json",
                                     "-result.private.json"))
    need({path.name for path in actions_dir.iterdir()} == expected_actions and
         {path.name for path in frames_dir.iterdir()} == expected_frames and
         len(trace.get("actions", [])) == 16,
         "saved_step_inventory_invalid")
    need(type(trace["actions"]) is list, "trace_actions_invalid")
    frame_ids = set()
    for step in range(16):
        stem = f"step-{step:03d}"
        intent_name = f"actions/{stem}-intent.private.json"
        result_name = f"actions/{stem}-result.private.json"
        intent = json_file(attempt / intent_name)
        result = json_file(attempt / result_name)
        assistant = json_file(attempt / "actions" / f"{stem}-assistant.json")
        trace_row = trace["actions"][step]
        phase = "positive" if step < 12 else "negative"
        normalized = intent.get("normalized_action")
        need(type(normalized) is dict and
             all(normalized.get(key) == value
                 for key, value in assistant.items()) and
             normalized.get("step") == step and
             normalized.get("frame_id") == intent.get("frame_id") and
             normalized.get("task_id") == task["task_id"] and
             normalized.get("task_binding_sha256") == task["package_sha256"],
             "saved_assistant_normalization_invalid")
        need(intent.get("schema") == INTENT_SCHEMA and
             intent.get("dispatch_state") == "intent_durable_before_gui_action" and
             intent.get("step") == step and intent.get("phase") == phase and
             intent.get("task_id") == task["task_id"] and
             intent.get("task_binding_sha256") == task["package_sha256"] and
             result.get("schema") == RESULT_SCHEMA and
             result.get("step") == step and result.get("phase") == phase and
             result.get("intent_sha256") == digest(raw_file(attempt / intent_name)) and
             result.get("applied_action") == intent.get("normalized_action") and
             trace_row.get("step") == step and trace_row.get("phase") == phase and
             trace_row.get("contract_receipt") == result.get("contract_receipt"),
             "intent_result_or_trace_chain_invalid")
        for field, suffix in (
            ("frame_ref", f"frames/{stem}.png"),
            ("instruction_ref", f"actions/{stem}-instruction.txt"),
            ("visible_text_ref", f"actions/{stem}-visible.txt"),
            ("assistant_action_ref", f"actions/{stem}-assistant.json"),
        ):
            evidence_ref(attempt, intent[field], suffix)
        frame_sha = intent["frame_ref"]["sha256"]
        receipt = result["contract_receipt"]
        need(intent.get("frame_sha256") == frame_sha and
             type(intent.get("frame_id")) is str and
             receipt.get("frame_id_sha256") ==
             digest(intent["frame_id"].encode()) and
             receipt.get("screenshot", {}).get("sha256") == frame_sha and
             receipt.get("screenshot", {}).get("bytes") ==
             (attempt / "frames" / f"{stem}.png").stat().st_size and
             receipt.get("action_type") == normalized["type"] and
             receipt.get("task_binding_sha256") ==
             task["package_sha256"] and
             receipt.get("task_id_sha256") ==
             digest(task["task_id"].encode()) and
             receipt.get("step") == step and
             trace_row.get("frame") == intent["frame_ref"],
             "frame_contract_chain_invalid")
        frame_ids.add(intent["frame_id"])
    need(len(frame_ids) == 16, "duplicate_dispatched_frame_ids")
    final_frame_raw = raw_file(frames_dir / "step-016.png")
    final_assistant_raw = raw_file(actions_dir / "step-016-assistant.json")
    positive_reload_raw = raw_file(attempt / "positive_reload_frame.png")
    need(final_frame_raw.startswith(b"\x89PNG\r\n\x1a\n") and
         positive_reload_raw.startswith(b"\x89PNG\r\n\x1a\n") and
         type(json_file(actions_dir / "step-016-assistant.json")) is dict and
         not (actions_dir / "step-016-intent.private.json").exists() and
         not (actions_dir / "step-016-result.private.json").exists(),
         "final_frame_or_pre_intent_boundary_invalid")

    baseline = json_file(train_private / "baseline_snapshot.json")
    need(json_file(attempt / "baseline_sql.json") == baseline,
         "saved_baseline_sql_mismatch")
    gold = json_file(train_private / "development_gold.json")
    need(task["task_id"] in gold, "train_pilot_gold_missing")
    pure = pure_old_verifier(verifier_source)
    positive = json_file(attempt / "positive_sql.json")
    evaluated = pure["evaluate"](task["task_id"], gold[task["task_id"]],
                                 baseline, positive)
    online_positive = json_file(attempt / "online_positive_score.private.json")
    need(evaluated["reward"] == 1.0 and
         evaluated["difference_codes"] == [] and
         evaluated == {key: online_positive.get(key) for key in evaluated} and
         online_positive.get("protected_source_files_checked") ==
         len(baseline["attachments"]),
         "positive_sql_pure_verifier_failed")
    frozen_files = json_file(train_private / "baseline-filestore-manifest.json")
    positive_files = json_file(attempt / "positive_filestore.json")
    positive_paths = json_file(attempt / "positive_store_paths.json")
    need(pure["protected_source_file_differences"](
             baseline, frozen_files, positive_files) == [] and
         pure["protected_source_store_path_differences"](
             baseline, positive_paths) == [],
         "positive_source_filestore_or_paths_failed")
    pre = json_file(attempt / "pre_restore.json")
    post = json_file(attempt / "post_restore.json")
    restored = json_file(attempt / "restored_sql.json")
    restored_files = json_file(attempt / "restored_filestore.json")
    need(pre.get("status") == "restored" and
         pre.get("business_snapshot_equal") is True and
         pre.get("physical_filestore_equal_before_web_restart") is True and
         post.get("status") == "restored" and
         post.get("business_snapshot_equal") is True and
         post.get("physical_filestore_equal_before_web_restart") is True and
         restored == baseline and
         pure["protected_source_file_differences"](
             baseline, frozen_files, restored_files) == [],
         "post_reset_saved_state_inexact")

    action_hashes = {path.name: digest(raw_file(path))
                     for path in actions_dir.iterdir()}
    frame_hashes = {path.name: digest(raw_file(path))
                    for path in frames_dir.iterdir()}
    return {
        "schema": SCHEMA,
        "status": "source_bound_failed_train_pilot_pre_intent",
        "old_source_revision": revision,
        "auditor_source_sha256": digest(raw_file(Path(__file__))),
        "old_code_freeze_sha256": digest(freeze_raw),
        "old_recorder_source_sha256": digest(recorder_source),
        "old_pure_verifier_source_sha256": digest(verifier_source),
        "private_train_plan_sha256": digest(private_raw),
        "train_only_binding_sha256": digest(binding_raw),
        "public_plan_sha256": digest(public_raw),
        "start_intent_sha256": digest(start_raw),
        "failure_receipt_sha256": digest(failure_raw),
        "gui_trace_sha256": digest(trace_raw),
        "saved_action_manifest_sha256": digest(canonical(action_hashes)),
        "saved_frame_manifest_sha256": digest(canonical(frame_hashes)),
        "unmatched_final_frame_sha256": digest(final_frame_raw),
        "unmatched_final_assistant_sha256": digest(final_assistant_raw),
        "positive_reload_frame_sha256": digest(positive_reload_raw),
        "positive_sql_sha256": digest(raw_file(attempt / "positive_sql.json")),
        "positive_filestore_sha256": digest(
            raw_file(attempt / "positive_filestore.json")),
        "positive_source_store_paths_sha256": digest(
            raw_file(attempt / "positive_store_paths.json")),
        "post_restore_receipt_sha256": digest(
            raw_file(attempt / "post_restore.json")),
        "restored_sql_sha256": digest(raw_file(attempt / "restored_sql.json")),
        "restored_filestore_sha256": digest(
            raw_file(attempt / "restored_filestore.json")),
        "matched_intent_result_steps": 16,
        "captured_assistant_actions": 17,
        "captured_frames": 17,
        "unmatched_final_step_index": 16,
        "positive_pure_verifier_reward": 1.0,
        "positive_protected_filestore_verified": True,
        "positive_source_store_paths_verified": True,
        "post_reset_sql_equals_frozen_baseline": True,
        "post_reset_protected_filestore_verified": True,
        "post_reset_receipt_exact": True,
        "services_restored_receipt_true": True,
        "failure_error_type": "ContractError",
        "specific_contract_error_code_verified": False,
        "pilot_passed": False,
        "sft_candidate_file_present": False,
        "model_attempts": 0,
        "official_final_tasks_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("attempt", "train-private", "binding", "private-plan",
                 "public-plan", "freeze", "repo"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--old-revision", default=OLD_REVISION)
    args = parser.parse_args()
    receipt = audit(attempt=args.attempt, train_private=args.train_private,
                    binding_path=args.binding, private_plan_path=args.private_plan,
                    public_plan_path=args.public_plan, freeze_path=args.freeze,
                    repo=args.repo, revision=args.old_revision)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
