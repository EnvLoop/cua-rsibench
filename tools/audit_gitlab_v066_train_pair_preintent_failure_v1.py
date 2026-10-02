"""Audit the first GitLab train GUI pair's pre-intent interruption.

This only reads the frozen train plan, private attempt, and current original
GitLab PostgreSQL/Git snapshot. It never starts a model or changes GitLab.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from gitlab_world import reset, runtime, verify
from gitlab_world import v066_train_gui_pair as pair


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_OUT = ROOT / "docs/evidence/gitlab-v066-train-preintent-interruption-2026-09-28.json"
SCHEMA = "envloop-gitlab-v066-train-preintent-interruption-audit-v1"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def private_json(path: Path) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(runtime.PRIVATE.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            "private_gitlab_failure_evidence_missing_or_unsafe")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "private_gitlab_failure_json_required")
    return value, sha256(raw).hexdigest()


def audit(ratification: Path) -> dict:
    plan, _original, _task, plan_sha = pair.validate_plan(ratification)
    run = pair.RUN_DIR
    require(run.is_dir() and not run.is_symlink() and
            run.stat().st_mode & 0o077 == 0,
            "original_gitlab_failed_run_directory_missing")
    failure, failure_sha = private_json(run / "failure.private.json")
    intent, intent_sha = private_json(run / "positive-intent.private.json")
    require(failure.get("schema") == "envloop-gitlab-v066-train-pair-failure-v1" and
            failure.get("reason_type") == "ContractError" and
            failure.get("positive_teacher_calls") == 0 and
            failure.get("provider_replay_authorized") is False and
            failure.get("official_final_admitted") == 0 and
            intent.get("schema") == "envloop-gitlab-v066-train-arm-intent-v1" and
            intent.get("arm") == "positive" and
            intent.get("plan_sha256") == plan_sha and
            intent.get("provider_replay_authorized") is False,
            "original_gitlab_failure_or_intent_changed")
    require(not (run / "run.private.json").exists() and
            not (run / "negative-intent.private.json").exists() and
            not (run / "negative").exists() and
            not (run / "positive" / "episode.private.json").exists() and
            not list((run / "positive" / "frames").glob("*.png")) and
            not list((run / "positive-provider").glob("*")),
            "first_gitlab_attempt_not_zero_provider_intent_and_zero_action")
    baseline = reset._baseline()
    current = verify.state_snapshot()
    frozen = reset._state()
    pre_demo, pre_demo_sha = private_json(runtime.PRIVATE / "demo-prestop.json")
    current_demo = runtime.proof(runtime.DEMO)
    world = runtime.proof(runtime.WORLD)
    require(current == baseline and
            frozen["baseline_business_sha256"] == baseline["business_sha256"] and
            world["running"] is True and world["health"] == "healthy" and
            runtime.stable_identity(current_demo) == runtime.stable_identity(pre_demo) and
            current_demo["running"] is False,
            "gitlab_post_failure_original_world_reset_or_demo_identity_changed")
    return {
        "schema": SCHEMA,
        "status": "first_train_gui_attempt_stopped_before_frame_and_provider_post",
        "cell_id": "gitlab", "partition": "train",
        "private_plan_sha256": plan_sha,
        "source_bundle_sha256": plan["source_bundle_sha256"],
        "failure_receipt_sha256": failure_sha,
        "arm_intent_sha256": intent_sha,
        "preserved_demo_pre_stop_sha256": pre_demo_sha,
        "recorded_exception_type": "ContractError",
        "exception_subtype_durably_recorded": False,
        "model_request_intents": 0,
        "model_request_bodies": 0,
        "model_responses": 0,
        "actor_frames": 0,
        "actor_actions": 0,
        "negative_arm_started": False,
        "post_failure_postgresql_git_state_exact_to_frozen_baseline": True,
        "business_baseline_sha256": baseline["business_sha256"],
        "post_failure_business_sha256": current["business_sha256"],
        "preserved_demo_identity_unchanged": True,
        "disposable_world_healthy_after_reset": True,
        "cold_clone_generation_after_failure": frozen["clone_generation"],
        "provider_replay_authorized": False,
        "tinker_sft_eligible_episodes": 0,
        "official_final_admitted": 0,
        "audit_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratification-private", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.ratification_private)
    require(not PUBLIC_OUT.exists(), "fresh_public_failure_audit_required")
    descriptor = os.open(PUBLIC_OUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(pair.canonical(result))
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"],
                      "model_request_intents": 0,
                      "actor_actions": 0,
                      "post_failure_baseline_exact": True,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
