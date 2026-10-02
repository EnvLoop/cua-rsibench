"""Audit one new disjoint GitLab train pair with exact target-shape prompts."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from gitlab_world import reset, runtime, verify
from gitlab_world import v066_train_gui_pair as prior
from gitlab_world import v066_train_target_shape_v1 as amended
from tools import audit_gitlab_v066_train_gui_pair as original_auditor


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_OUT = runtime.PRIVATE / "v066-target-shape-train-audit.private.json"
PUBLIC_OUT = ROOT / "docs/evidence/gitlab-v066-target-shape-train-result-2026-09-28.json"
SUCCESS_SCHEMA = "envloop-gitlab-v066-target-shape-train-success-audit-v1"
FAILURE_SCHEMA = "envloop-gitlab-v066-target-shape-train-failure-audit-v1"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def private_data(path: Path) -> tuple[object, str]:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(runtime.PRIVATE.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            "new_train_private_evidence_missing_or_unsafe")
    raw = path.read_bytes()
    value = json.loads(raw)
    return value, sha256(raw).hexdigest()


def private_json(path: Path) -> tuple[dict, str]:
    value, digest = private_data(path)
    require(type(value) is dict, "new_train_private_json_required")
    return value, digest


def common(ratification: Path) -> tuple[dict, dict, dict, str, str]:
    plan, original, task, plan_sha = amended.validate_plan(ratification)
    execute, execute_sha = private_json(amended.EXECUTE_INTENT)
    require(execute.get("schema") == amended.EXECUTE_SCHEMA and
            execute.get("plan_sha256") == plan_sha and
            execute.get("run_dir_name") == amended.RUN_DIR.name and
            execute.get("new_train_task_id") == task["task_id"] and
            execute.get("previous_paid_failure_audit_sha256") ==
            plan["previous_paid_failure_audit_sha256"] and
            execute.get("provider_replay_authorized") is False and
            execute.get("official_final_admitted") == 0 and
            amended.RUN_DIR.is_dir() and
            amended.RUN_DIR.stat().st_mode & 0o077 == 0,
            "new_train_attempt_not_bound_to_separate_source_plan")
    return plan, original, task, plan_sha, execute_sha


def capture_rejections() -> dict[str, int]:
    counts = {}
    for arm in ("positive", "negative"):
        rows = sorted(amended.RUN_DIR.glob(f"capture-reject-{arm}-*.private.json"))
        require(len(rows) <= amended.preintent.MAX_PRE_INTENT_CAPTURES and
                [path.name for path in rows] == [
                    f"capture-reject-{arm}-{index:02d}.private.json"
                    for index in range(1, len(rows) + 1)],
                "new_train_preintent_capture_bound_changed")
        for index, path in enumerate(rows, 1):
            value, _ = private_json(path)
            require(value.get("schema") ==
                    "envloop-gitlab-v066-preintent-capture-reject-v1" and
                    value.get("arm") == arm and value.get("step") == 0 and
                    value.get("attempt") == index and
                    value.get("reason") == "stale_frame" and
                    value.get("provider_intent_exists") is False and
                    value.get("actor_frame_or_action_exists") is False and
                    value.get("replay_of_provider_call") is False,
                    "new_train_preintent_capture_receipt_changed")
        counts[arm] = len(rows)
    return counts


def request_counts(task: dict, *, verify_full_prompt: bool) -> dict:
    intents = requests = responses = frames = 0
    input_tokens = output_tokens = 0
    for arm in ("positive", "negative"):
        provider = amended.RUN_DIR / (arm + "-provider")
        arm_frames = amended.RUN_DIR / arm / "frames"
        these_requests = sorted(provider.glob("step-*-request.private.json"))
        intents += len(list(provider.glob("step-*-intent.private.json")))
        requests += len(these_requests)
        responses += len(list(provider.glob("step-*-response.private.json")))
        frames += len(list(arm_frames.glob("step-*.png")))
        for path in these_requests:
            request, _ = private_json(path)
            user = json.loads(request["user_text"])
            instruction = json.loads(user["model_instruction"])
            require(request.get("model") == amended.teacher.matrix.TEACHER and
                    user.get("task_instruction") == task["visible_instruction"] and
                    user.get("arm") == arm and
                    instruction.get("contract", "").startswith(
                        amended.TARGET_SHAPE_RULE) and
                    instruction.get("task_instruction") ==
                    task["visible_instruction"],
                    "paid_new_train_request_missing_exact_target_shape_prompt")
            if verify_full_prompt:
                step = int(path.name.split("-")[1])
                trace, _ = private_data(
                    amended.RUN_DIR / arm / "actions.private.json")
                require(type(trace) is list and step < len(trace),
                        "accepted_train_trace_missing_for_prompt_reconstruction")
                image = (arm_frames / f"step-{step:03d}.png").read_bytes()
                observation = original_auditor._observation(trace[step], image)
                require(user["model_instruction"] ==
                        amended.strict_render(observation)["instruction"],
                        "paid_new_train_prompt_differs_from_current_frame")
        for response_path in provider.glob("step-*-response.private.json"):
            response, _ = private_json(response_path)
            usage = response.get("receipt", {}).get("usage", {})
            if type(usage.get("input_tokens")) is int:
                input_tokens += usage["input_tokens"]
            if type(usage.get("output_tokens")) is int:
                output_tokens += usage["output_tokens"]
    return {"provider_intents": intents, "provider_requests": requests,
            "provider_responses": responses, "raw_frames": frames,
            "provider_reported_input_tokens": input_tokens,
            "provider_reported_output_tokens": output_tokens,
            "actual_provider_billed_usd": None}


def exact_current_baseline() -> tuple[bool, str | None]:
    try:
        baseline = reset._baseline()
        current = verify.state_snapshot()
        state = reset._state()
        world = runtime.proof(runtime.WORLD)
        exact = (current == baseline and
                 state["baseline_business_sha256"] ==
                 baseline["business_sha256"] and
                 world["running"] is True and world["health"] == "healthy")
        return exact, current["business_sha256"]
    except Exception:
        return False, None


def audit_success(ratification: Path) -> tuple[dict, dict]:
    plan, _original, task, plan_sha, execute_sha = common(ratification)
    require((amended.RUN_DIR / "run.private.json").is_file() and
            not (amended.RUN_DIR / "failure.private.json").exists(),
            "new_train_pair_not_complete_for_success_audit")
    original_run = prior.RUN_DIR
    original_validate = prior.validate_plan
    prior.RUN_DIR = amended.RUN_DIR
    prior.validate_plan = amended.validate_plan
    try:
        private, public = original_auditor.audit(ratification)
    finally:
        prior.validate_plan = original_validate
        prior.RUN_DIR = original_run
    usage = request_counts(task, verify_full_prompt=True)
    exact, digest = exact_current_baseline()
    require(exact, "new_train_pair_post_audit_baseline_not_exact")
    private.update({
        "amendment_schema": SUCCESS_SCHEMA,
        "amendment_plan_sha256": plan_sha,
        "amendment_execute_intent_sha256": execute_sha,
        "prior_paid_failure_audit_sha256":
            plan["previous_paid_failure_audit_sha256"],
        "pre_intent_capture_rejections": capture_rejections(),
        "provider_accounting": usage,
        "post_attempt_business_sha256": digest,
    })
    public.update({
        "schema": SUCCESS_SCHEMA,
        "status": "one_new_disjoint_train_pair_passed_target_shape_amendment",
        "amendment_plan_sha256": plan_sha,
        "amendment_execute_intent_sha256": execute_sha,
        "prior_paid_failure_audit_sha256":
            plan["previous_paid_failure_audit_sha256"],
        "pre_intent_capture_rejections": capture_rejections(),
        **usage,
        "provider_replay_authorized": False,
        "post_attempt_baseline_exact": True,
        "post_attempt_business_sha256": digest,
        "official_final_admitted": 0,
    })
    return private, public


def audit_failure(ratification: Path) -> tuple[dict, dict]:
    plan, _original, task, plan_sha, execute_sha = common(ratification)
    failure, failure_sha = private_json(
        amended.RUN_DIR / "failure.private.json")
    require(failure.get("schema") ==
            "envloop-gitlab-v066-train-pair-failure-v1" and
            failure.get("provider_replay_authorized") is False and
            failure.get("official_final_admitted") == 0 and
            not (amended.RUN_DIR / "run.private.json").exists(),
            "new_train_failure_not_retained_unqualified")
    usage = request_counts(task, verify_full_prompt=False)
    exact, digest = exact_current_baseline()
    private = {
        "schema": FAILURE_SCHEMA,
        "status": "new_disjoint_train_pair_failed_unqualified_no_replay",
        "amendment_plan_sha256": plan_sha,
        "amendment_execute_intent_sha256": execute_sha,
        "prior_paid_failure_audit_sha256":
            plan["previous_paid_failure_audit_sha256"],
        "failure_receipt_sha256": failure_sha,
        "reason_type": failure.get("reason_type"),
        "recorded_positive_teacher_calls":
            failure.get("positive_teacher_calls"),
        "pre_intent_capture_rejections": capture_rejections(),
        **usage,
        "post_failure_baseline_exact": exact,
        "post_failure_business_sha256": digest,
        "provider_replay_authorized": False,
        "tinker_sft_eligible_episodes": 0,
        "official_final_admitted": 0,
    }
    return private, dict(private)


def write_new(path: Path, value: dict, mode: int) -> str:
    require(not path.exists() and not path.is_symlink(),
            "fresh_disjoint_train_audit_output_required")
    raw = prior.canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratification-private", type=Path, required=True)
    args = parser.parse_args()
    if (amended.RUN_DIR / "run.private.json").exists():
        private, public = audit_success(args.ratification_private)
    else:
        private, public = audit_failure(args.ratification_private)
    private_sha = write_new(PRIVATE_OUT, private, 0o600)
    public["private_audit_sha256"] = private_sha
    write_new(PUBLIC_OUT, public, 0o644)
    print(json.dumps({
        "status": public["status"],
        "provider_intents": public["provider_intents"],
        "positive_eligible_for_tinker_gui_sft":
            public.get("positive_eligible_for_tinker_gui_sft", False),
        "official_final_admitted": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
