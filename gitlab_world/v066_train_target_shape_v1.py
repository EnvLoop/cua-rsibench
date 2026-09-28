"""One disjoint GitLab train pair with an explicit JSON target-shape prompt.

This is a new train task, never a replay of either prior failed attempt.
The common v0.6.6 action parser, GUI dispatcher, saved-state verifier, and
cold reset remain unchanged. No selection or final task is read by the actor.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path

from cursibench import full_study_teacher_adapter_v1 as teacher
from . import bootstrap, factory, reset, runtime
from . import teacher_episode_worker_v066 as worker
from . import v066_train_gui_pair as prior
from . import v066_train_preintent_resample_v1 as preintent


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-gitlab-v066-target-shape-train-plan-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-target-shape-train-plan-public-v1"
EXECUTE_SCHEMA = "envloop-gitlab-v066-target-shape-train-execute-v1"
PLAN = runtime.PRIVATE / "v066-target-shape-train-plan.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-target-shape-train-plan-2026-09-28.json"
EXECUTE_INTENT = runtime.PRIVATE / "v066-target-shape-train-execute.private.json"
RUN_DIR = runtime.PRIVATE / "v066-one-train-gui-pair-target-shape-20260928"
PREVIOUS_RESULT = ROOT / "docs/evidence/gitlab-v066-train-preintent-resample-result-2026-09-28.json"
FORENSIC = ROOT / "docs/evidence/gitlab-v066-target-shape-failure-2026-09-28.json"
TARGET_SHAPE_RULE = (
    "TARGET SHAPE RULE: target must be a JSON object, never a bare string. "
    "For a visible control, put its exact current enabled ref string under "
    "the object's ref key. Alternatively use an object with integer x and y "
    "coordinates inside the current screenshot. Do not copy any placeholder "
    "or invent a ref. This rule applies to click, type, drag, and targeted "
    "key or scroll actions. "
)
SOURCE_FILES = (
    "gitlab_world/v066_train_target_shape_v1.py",
    "tools/audit_gitlab_v066_train_target_shape_v1.py",
    "docs/FULL_STUDY_GITLAB_V066_TARGET_SHAPE_TRAIN_AMENDMENT_2026-09-28.md",
    "gitlab_world/v066_train_preintent_resample_v1.py",
    "tools/audit_gitlab_v066_target_shape_failure_v1.py",
)
ORIGINAL_VALIDATE = prior.validate_plan
ORIGINAL_RENDER = prior.render_for_model


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def sources() -> dict[str, str]:
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def validate_preintent(ratification: Path) -> tuple[dict, str]:
    """Preserve the old plan validator during the independent audit hook."""
    active = prior.validate_plan
    prior.validate_plan = ORIGINAL_VALIDATE
    try:
        return preintent.validate_plan(ratification)
    finally:
        prior.validate_plan = active


def previous_result() -> tuple[dict, str]:
    raw = PREVIOUS_RESULT.read_bytes()
    value = json.loads(raw)
    require(value.get("schema") ==
            "envloop-gitlab-v066-train-preintent-resample-failure-audit-v1" and
            value.get("status") ==
            "second_train_only_attempt_failed_unqualified_no_replay" and
            value.get("provider_intents") == 1 and
            value.get("provider_requests") == 1 and
            value.get("provider_responses") == 1 and
            value.get("post_failure_baseline_exact") is True and
            value.get("tinker_sft_eligible_episodes") == 0 and
            value.get("official_final_admitted") == 0 and
            value.get("provider_replay_authorized") is False,
            "previous_paid_train_response_not_retained_unqualified")
    return value, sha(raw)


def paid_shape_forensic(previous_sha: str) -> tuple[dict, str]:
    raw = FORENSIC.read_bytes()
    value = json.loads(raw)
    require(value.get("schema") ==
            "envloop-gitlab-v066-paid-target-shape-forensic-v1" and
            value.get("prior_failure_audit_sha256") == previous_sha and
            value.get("response_target_value_type") == "bare_string" and
            value.get("response_target_was_current_visible_ref") is True and
            value.get("validator_requires_target_object") is True and
            value.get("accepted_actor_actions") == 0 and
            value.get("independent_post_failure_reset_exact") is True and
            value.get("provider_replay_authorized") is False and
            value.get("official_final_admitted") == 0 and
            value.get("auditor_source_sha256") ==
            sha((ROOT / "tools/audit_gitlab_v066_target_shape_failure_v1.py").read_bytes()),
            "paid_target_shape_forensic_changed")
    return value, sha(raw)


def second_train_task() -> tuple[dict, dict]:
    first, first_binding = prior._train_task()
    world = json.loads(bootstrap.WORLD_FILE.read_bytes())
    matches = sorted((row for row in world["tasks"]
                      if row["partition"] == "train" and
                      row["template_group"] == "issue_label_from_alert"),
                     key=lambda row: row["task_id"])
    require(len(matches) == 5 and len([row for row in world["tasks"]
                                      if row["partition"] == "train"]) == 20 and
            matches[0] == first and
            matches[1]["task_id"] != first["task_id"] and
            matches[1]["project_family"] != first["project_family"] and
            matches[1]["source_family"] != first["source_family"],
            "new_train_task_not_project_and_source_disjoint")
    original = matches[1]
    binding = {
        "task_id": original["task_id"],
        "package_sha256": factory.sha256(factory.canonical(original)),
        "visible_instruction": original["prompt"],
    }
    require(binding["task_id"] != first_binding["task_id"],
            "previous_paid_task_replay_forbidden")
    return original, binding


def strict_render(observation):
    rendered = ORIGINAL_RENDER(observation)
    instruction = json.loads(rendered["instruction"])
    require(type(instruction) is dict and
            type(instruction.get("contract")) is str and
            TARGET_SHAPE_RULE not in instruction["contract"],
            "original_action_prompt_changed_or_doubly_amended")
    instruction["contract"] = TARGET_SHAPE_RULE + instruction["contract"]
    rewritten = json.dumps(instruction, ensure_ascii=False,
                           sort_keys=True, separators=(",", ":"))
    require(len(rewritten.encode()) <= 16_384 and
            rendered["image_bytes"] == observation.screenshot_bytes,
            "train_target_shape_prompt_or_current_image_invalid")
    return {**rendered, "instruction": rewritten}


def freeze(ratification: Path) -> dict:
    old, _first, _old_binding, old_sha = ORIGINAL_VALIDATE(ratification)
    _preintent_plan, preintent_sha = validate_preintent(ratification)
    previous, previous_sha = previous_result()
    _forensic, forensic_sha = paid_shape_forensic(previous_sha)
    original, binding = second_train_task()
    require(not PLAN.exists() and not PUBLIC_PLAN.exists() and
            not EXECUTE_INTENT.exists() and not RUN_DIR.exists() and
            reset._baseline() == worker.verify.state_snapshot(),
            "fresh_disjoint_train_plan_or_exact_baseline_missing")
    source = sources()
    value = {
        "schema": SCHEMA,
        "status": "source_frozen_new_train_task_no_model_request_yet",
        "cell_id": "gitlab", "partition": "train",
        "task_id": binding["task_id"],
        "package_sha256": binding["package_sha256"],
        "visible_instruction_sha256": sha(binding["visible_instruction"].encode()),
        "original_train_task_sha256": factory.sha256(factory.canonical(original)),
        "world_sha256": sha(bootstrap.WORLD_FILE.read_bytes()),
        "baseline_sha256": sha((runtime.PRIVATE / "baseline-persisted-state.json").read_bytes()),
        "ratification_sha256": old["ratification_sha256"],
        "prior_train_plan_sha256": old_sha,
        "preintent_plan_sha256": preintent_sha,
        "previous_paid_failure_audit_sha256": previous_sha,
        "paid_target_shape_forensic_sha256": forensic_sha,
        "previous_paid_failure_receipt_sha256": previous["failure_receipt_sha256"],
        "worker_runtime_sha256": worker.runtime_sha256(),
        "worker_verifier_sha256": worker.verifier_sha256(),
        "adapter_sha256": worker.adapter_sha256(),
        "prompt_rule_sha256": sha(TARGET_SHAPE_RULE.encode()),
        "source_sha256s": source,
        "source_bundle_sha256": sha(prior.canonical(source)),
        "teacher_model": teacher.matrix.TEACHER,
        "max_actions_per_arm": prior.MAX_ACTIONS_PER_ARM,
        "max_wall_seconds_per_arm": prior.WALL_SECONDS_PER_ARM,
        "one_new_positive_and_one_wrong_priority_negative": True,
        "provider_replay_authorized": False,
        "selection_final_content_exposed_to_actor": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    plan_sha = prior.write_new(PLAN, value)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_disjoint_train_target_shape_trial_not_run",
        "cell_id": "gitlab", "partition": "train",
        "private_plan_sha256": plan_sha,
        "source_bundle_sha256": value["source_bundle_sha256"],
        "previous_paid_failure_audit_sha256": previous_sha,
        "paid_target_shape_forensic_sha256": forensic_sha,
        "prompt_rule_sha256": value["prompt_rule_sha256"],
        "new_task_project_and_source_disjoint_from_failed_task": True,
        "max_actions_per_arm": prior.MAX_ACTIONS_PER_ARM,
        "max_wall_seconds_per_arm": prior.WALL_SECONDS_PER_ARM,
        "provider_replay_authorized": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    fd = os.open(PUBLIC_PLAN, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(prior.canonical(public))
        stream.flush()
        os.fsync(stream.fileno())
    return public


def validate_plan(ratification: Path) -> tuple[dict, dict, dict, str]:
    old, _first, _old_binding, old_sha = ORIGINAL_VALIDATE(ratification)
    _preintent, preintent_sha = validate_preintent(ratification)
    previous, previous_sha = previous_result()
    _forensic, forensic_sha = paid_shape_forensic(previous_sha)
    original, binding = second_train_task()
    plan, plan_sha = prior._private_json(PLAN)
    public = json.loads(PUBLIC_PLAN.read_bytes())
    source = sources()
    require(plan.get("schema") == SCHEMA and
            plan.get("status") == "source_frozen_new_train_task_no_model_request_yet" and
            plan.get("cell_id") == "gitlab" and plan.get("partition") == "train" and
            plan.get("task_id") == binding["task_id"] and
            plan.get("package_sha256") == binding["package_sha256"] and
            plan.get("visible_instruction_sha256") ==
            sha(binding["visible_instruction"].encode()) and
            plan.get("original_train_task_sha256") ==
            factory.sha256(factory.canonical(original)) and
            plan.get("world_sha256") == sha(bootstrap.WORLD_FILE.read_bytes()) and
            plan.get("baseline_sha256") ==
            sha((runtime.PRIVATE / "baseline-persisted-state.json").read_bytes()) and
            plan.get("ratification_sha256") == old["ratification_sha256"] and
            plan.get("prior_train_plan_sha256") == old_sha and
            plan.get("preintent_plan_sha256") == preintent_sha and
            plan.get("previous_paid_failure_audit_sha256") == previous_sha and
            plan.get("paid_target_shape_forensic_sha256") == forensic_sha and
            plan.get("previous_paid_failure_receipt_sha256") ==
            previous["failure_receipt_sha256"] and
            plan.get("worker_runtime_sha256") == worker.runtime_sha256() and
            plan.get("worker_verifier_sha256") == worker.verifier_sha256() and
            plan.get("adapter_sha256") == worker.adapter_sha256() and
            plan.get("prompt_rule_sha256") == sha(TARGET_SHAPE_RULE.encode()) and
            plan.get("source_sha256s") == source and
            plan.get("source_bundle_sha256") == sha(prior.canonical(source)) and
            plan.get("teacher_model") == teacher.matrix.TEACHER and
            plan.get("max_actions_per_arm") == prior.MAX_ACTIONS_PER_ARM and
            plan.get("max_wall_seconds_per_arm") == prior.WALL_SECONDS_PER_ARM and
            plan.get("one_new_positive_and_one_wrong_priority_negative") is True and
            plan.get("provider_replay_authorized") is False and
            plan.get("selection_final_content_exposed_to_actor") is False and
            plan.get("model_calls") == plan.get("official_final_admitted") == 0 and
            public.get("schema") == PUBLIC_SCHEMA and
            public.get("private_plan_sha256") == plan_sha and
            public.get("source_bundle_sha256") == plan["source_bundle_sha256"] and
            public.get("prompt_rule_sha256") == plan["prompt_rule_sha256"] and
            public.get("model_calls") == public.get("official_final_admitted") == 0,
            "source_bound_disjoint_target_shape_train_plan_changed")
    return plan, original, binding, plan_sha


@contextmanager
def scoped_train_amendment():
    original_preintent_run = preintent.RUN_DIR
    original_render = prior.render_for_model
    preintent.RUN_DIR = RUN_DIR
    prior.render_for_model = strict_render
    try:
        with preintent.scoped_first_capture_resampling():
            yield
    finally:
        prior.render_for_model = original_render
        preintent.RUN_DIR = original_preintent_run


def record(ratification: Path) -> dict:
    plan, original, task, plan_sha = validate_plan(ratification)
    require(not RUN_DIR.exists() and not EXECUTE_INTENT.exists() and
            reset._baseline() == worker.verify.state_snapshot() and
            bool(os.environ.get("OPENAI_API_KEY")),
            "fresh_new_train_run_baseline_or_teacher_route_missing")
    prior.write_new(EXECUTE_INTENT, {
        "schema": EXECUTE_SCHEMA,
        "plan_sha256": plan_sha,
        "run_dir_name": RUN_DIR.name,
        "new_train_task_id": task["task_id"],
        "previous_paid_failure_audit_sha256":
            plan["previous_paid_failure_audit_sha256"],
        "provider_replay_authorized": False,
        "official_final_admitted": 0,
    })
    with scoped_train_amendment():
        RUN_DIR.mkdir(mode=0o700)
        positive = RUN_DIR / "positive"
        positive.mkdir(mode=0o700)
        (positive / "frames").mkdir(mode=0o700)
        positive_sampler = prior.SolSampler(arm="positive")
        positive_sampler.directory.mkdir(mode=0o700)
        instance = worker.GitLabTrainEpisodeWorker(
            private_output_root=RUN_DIR,
            ratification_path=ratification,
            ratification_sha256=plan["ratification_sha256"],
            expected_runtime_sha256=plan["worker_runtime_sha256"],
            expected_verifier_sha256=plan["worker_verifier_sha256"],
            enable_live=True,
        )
        prior.write_new(RUN_DIR / "positive-intent.private.json", {
            "schema": "envloop-gitlab-v066-train-arm-intent-v1",
            "arm": "positive", "task_id": task["task_id"],
            "plan_sha256": plan_sha,
            "provider_replay_authorized": False,
        })
        try:
            result = instance.run_episode(
                task=task, out_dir=positive,
                sample_teacher=positive_sampler.sample,
                dispatch_e2b=lambda **_kwargs: (_ for _ in ()).throw(
                    prior.PairError("self_hosted_gitlab_has_no_e2b_lease")),
            )
            teacher._verify_episode(
                positive, result, cell_id="gitlab", task=task,
                runtime_sha=plan["worker_runtime_sha256"],
                adapter_sha=plan["adapter_sha256"],
                verifier_sha=plan["worker_verifier_sha256"],
                turns=positive_sampler.turns, e2b_attempt_ids=[], requires_e2b=False,
            )
            prior.write_new(RUN_DIR / "negative-intent.private.json", {
                "schema": "envloop-gitlab-v066-train-arm-intent-v1",
                "arm": "negative", "task_id": task["task_id"],
                "plan_sha256": plan_sha,
                "provider_replay_authorized": False,
            })
            negative_sampler = prior.SolSampler(arm="negative")
            negative = prior._negative_arm(task, original, negative_sampler)
            receipt = {
                "schema": prior.RUN_SCHEMA,
                "status": "two_train_gui_arms_recorded_pending_independent_audit",
                "plan_sha256": plan_sha,
                "positive_episode_sha256": result["episode_receipt_sha256"],
                "negative_episode_sha256": negative["receipt_sha256"],
                "positive_action_count": len(positive_sampler.turns),
                "negative_action_count": len(negative_sampler.turns),
                "teacher_model": teacher.matrix.TEACHER,
                "provider_usage": positive_sampler.provider_usage +
                                  negative_sampler.provider_usage,
                "official_final_admitted": 0,
                "tinker_sft_eligible": False,
            }
            digest = prior.write_new(RUN_DIR / "run.private.json", receipt)
            return {"status": receipt["status"],
                    "private_run_sha256": digest,
                    "positive_action_count": receipt["positive_action_count"],
                    "negative_action_count": receipt["negative_action_count"],
                    "tinker_sft_eligible": False,
                    "official_final_admitted": 0}
        except BaseException as exc:
            if not (RUN_DIR / "failure.private.json").exists():
                prior.write_new(RUN_DIR / "failure.private.json", {
                    "schema": "envloop-gitlab-v066-train-pair-failure-v1",
                    "reason_type": type(exc).__name__,
                    "positive_teacher_calls": len(positive_sampler.turns),
                    "provider_replay_authorized": False,
                    "official_final_admitted": 0,
                })
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "record"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "record":
        require(args.execute, "explicit_new_train_task_execute_required")
        result = record(args.ratification_private)
    else:
        result = freeze(args.ratification_private)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
