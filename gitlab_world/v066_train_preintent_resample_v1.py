"""Separately frozen, train-only GitLab capture resampling amendment.

The original failed pair, its source plan, worker, and independent verifier
remain byte unchanged. Only step-zero frame capture may be repeated before
that arm has a provider intent or an actor action. This does not retry a
provider request, dispatch, saved-state readback, or final task.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from cursibench.scale_action_contract import ContractError

from . import reset, runtime, teacher_episode_worker_v066 as worker
from . import v066_train_gui_pair as prior


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-gitlab-v066-train-preintent-resample-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-train-preintent-resample-public-v1"
EXECUTE_SCHEMA = "envloop-gitlab-v066-train-preintent-resample-execute-v1"
PLAN = runtime.PRIVATE / "v066-train-preintent-resample-plan.private.json"
PUBLIC_PLAN = ROOT / "docs/evidence/gitlab-v066-train-preintent-resample-plan-2026-09-28.json"
EXECUTE_INTENT = runtime.PRIVATE / "v066-train-preintent-resample-execute.private.json"
RUN_DIR = runtime.PRIVATE / "v066-one-train-gui-pair-preintent-20260928"
INTERRUPTION = ROOT / "docs/evidence/gitlab-v066-train-preintent-interruption-2026-09-28.json"
MAX_PRE_INTENT_CAPTURES = 5
SOURCE_FILES = (
    "gitlab_world/v066_train_preintent_resample_v1.py",
    "tools/audit_gitlab_v066_train_preintent_resample_v1.py",
    "tools/audit_gitlab_v066_train_pair_preintent_failure_v1.py",
    "docs/FULL_STUDY_GITLAB_V066_PREINTENT_AMENDMENT_2026-09-28.md",
)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def sources() -> dict[str, str]:
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def interruption() -> tuple[dict, str]:
    raw = INTERRUPTION.read_bytes()
    value = json.loads(raw)
    require(value.get("schema") ==
            "envloop-gitlab-v066-train-preintent-interruption-audit-v1" and
            value.get("status") ==
            "first_train_gui_attempt_stopped_before_frame_and_provider_post" and
            value.get("model_request_intents") == 0 and
            value.get("model_request_bodies") == 0 and
            value.get("model_responses") == 0 and
            value.get("actor_frames") == 0 and
            value.get("actor_actions") == 0 and
            value.get("post_failure_postgresql_git_state_exact_to_frozen_baseline")
            is True and
            value.get("provider_replay_authorized") is False and
            value.get("official_final_admitted") == 0,
            "prior_train_attempt_not_proven_pre_intent_and_exact_reset")
    return value, sha(raw)


def freeze(ratification: Path) -> dict:
    old_plan, _original, _task, old_plan_sha = prior.validate_plan(ratification)
    previous, previous_sha = interruption()
    require(previous["private_plan_sha256"] == old_plan_sha and
            previous["source_bundle_sha256"] == old_plan["source_bundle_sha256"] and
            not PLAN.exists() and not PUBLIC_PLAN.exists() and
            not EXECUTE_INTENT.exists() and not RUN_DIR.exists() and
            reset._baseline() == worker.verify.state_snapshot(),
            "fresh_train_preintent_amendment_or_exact_current_baseline_missing")
    source = sources()
    value = {
        "schema": SCHEMA,
        "status": "separately_frozen_before_second_train_only_attempt",
        "partition": "train", "cell_id": "gitlab",
        "prior_private_plan_sha256": old_plan_sha,
        "prior_failed_run_receipt_sha256": previous["failure_receipt_sha256"],
        "prior_interruption_audit_sha256": previous_sha,
        "prior_source_bundle_sha256": old_plan["source_bundle_sha256"],
        "ratification_sha256": old_plan["ratification_sha256"],
        "source_sha256s": source,
        "source_bundle_sha256": sha(prior.canonical(source)),
        "run_dir_name": RUN_DIR.name,
        "max_step_zero_capture_attempts_per_arm": MAX_PRE_INTENT_CAPTURES,
        "capture_retry_only_before_arm_first_provider_intent": True,
        "capture_retry_only_before_arm_first_actor_action": True,
        "provider_replay_authorized": False,
        "selection_final_content_exposed_to_actor": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    digest = prior.write_new(PLAN, value)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_train_only_preintent_amendment_no_second_attempt_yet",
        "cell_id": "gitlab", "partition": "train",
        "private_plan_sha256": digest,
        "prior_private_plan_sha256": old_plan_sha,
        "prior_interruption_audit_sha256": previous_sha,
        "source_bundle_sha256": value["source_bundle_sha256"],
        "max_step_zero_capture_attempts_per_arm": MAX_PRE_INTENT_CAPTURES,
        "provider_replay_authorized": False,
        "model_calls": 0, "official_final_admitted": 0,
    }
    descriptor = os.open(PUBLIC_PLAN, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(prior.canonical(public))
        stream.flush()
        os.fsync(stream.fileno())
    return public


def validate_plan(ratification: Path) -> tuple[dict, str]:
    old_plan, _original, _task, old_plan_sha = prior.validate_plan(ratification)
    previous, previous_sha = interruption()
    plan, plan_sha = prior._private_json(PLAN)
    public = json.loads(PUBLIC_PLAN.read_bytes())
    source = sources()
    require(plan.get("schema") == SCHEMA and
            plan.get("status") ==
            "separately_frozen_before_second_train_only_attempt" and
            plan.get("partition") == "train" and
            plan.get("cell_id") == "gitlab" and
            plan.get("prior_private_plan_sha256") == old_plan_sha and
            plan.get("prior_failed_run_receipt_sha256") ==
            previous["failure_receipt_sha256"] and
            plan.get("prior_interruption_audit_sha256") == previous_sha and
            plan.get("prior_source_bundle_sha256") ==
            old_plan["source_bundle_sha256"] and
            plan.get("ratification_sha256") == old_plan["ratification_sha256"] and
            plan.get("source_sha256s") == source and
            plan.get("source_bundle_sha256") == sha(prior.canonical(source)) and
            plan.get("run_dir_name") == RUN_DIR.name and
            plan.get("max_step_zero_capture_attempts_per_arm") ==
            MAX_PRE_INTENT_CAPTURES and
            plan.get("capture_retry_only_before_arm_first_provider_intent")
            is True and
            plan.get("capture_retry_only_before_arm_first_actor_action")
            is True and
            plan.get("provider_replay_authorized") is False and
            plan.get("selection_final_content_exposed_to_actor") is False and
            plan.get("model_calls") == plan.get("official_final_admitted") == 0 and
            public.get("schema") == PUBLIC_SCHEMA and
            public.get("private_plan_sha256") == plan_sha and
            public.get("source_bundle_sha256") == plan["source_bundle_sha256"] and
            public.get("model_calls") == public.get("official_final_admitted") == 0,
            "source_bound_train_preintent_amendment_changed")
    return plan, plan_sha


@contextmanager
def scoped_first_capture_resampling():
    """Temporarily amend only this process's fresh train-pair run."""
    original_run = prior.RUN_DIR
    original_observe = worker._RealGitLabSession.observe

    def observe(self, *, memory: str):
        if self.step != 0:
            return original_observe(self, memory=memory)
        arm = "negative" if (RUN_DIR / "negative-intent.private.json").exists() else "positive"
        provider = RUN_DIR / (arm + "-provider")
        frames = RUN_DIR / arm / "frames"
        for attempt in range(1, MAX_PRE_INTENT_CAPTURES + 1):
            require(not list(provider.glob("*-intent.private.json")) and
                    not list(provider.glob("*-request.private.json")) and
                    not list(provider.glob("*-response.private.json")) and
                    not list(frames.glob("*.png")),
                    "capture_resampling_forbidden_after_provider_or_actor_intent")
            try:
                observed = original_observe(self, memory=memory)
                if self.current_frame_id() != observed.frame_id:
                    raise ContractError("stale_frame")
                return observed
            except ContractError as exc:
                if str(exc) != "stale_frame":
                    raise
                prior.write_new(RUN_DIR / f"capture-reject-{arm}-{attempt:02d}.private.json", {
                    "schema": "envloop-gitlab-v066-preintent-capture-reject-v1",
                    "arm": arm, "step": 0, "attempt": attempt,
                    "reason": "stale_frame",
                    "provider_intent_exists": False,
                    "actor_frame_or_action_exists": False,
                    "replay_of_provider_call": False,
                })
                if attempt == MAX_PRE_INTENT_CAPTURES:
                    raise
                time.sleep(min(0.25 * attempt, 1.0))
        raise AssertionError("bounded capture loop exhausted")

    prior.RUN_DIR = RUN_DIR
    worker._RealGitLabSession.observe = observe
    try:
        yield
    finally:
        worker._RealGitLabSession.observe = original_observe
        prior.RUN_DIR = original_run


def record(ratification: Path) -> dict:
    plan, plan_sha = validate_plan(ratification)
    require(not RUN_DIR.exists() and not EXECUTE_INTENT.exists() and
            reset._baseline() == worker.verify.state_snapshot() and
            bool(os.environ.get("OPENAI_API_KEY")),
            "fresh_preintent_train_run_baseline_or_teacher_route_missing")
    prior.write_new(EXECUTE_INTENT, {
        "schema": EXECUTE_SCHEMA,
        "amendment_plan_sha256": plan_sha,
        "prior_interruption_audit_sha256":
            plan["prior_interruption_audit_sha256"],
        "run_dir_name": RUN_DIR.name,
        "provider_replay_authorized": False,
        "official_final_admitted": 0,
    })
    with scoped_first_capture_resampling():
        return prior.record(ratification)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "record"))
    parser.add_argument("--ratification-private", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "record":
        require(args.execute, "explicit_second_train_pair_execute_required")
        result = record(args.ratification_private)
    else:
        result = freeze(args.ratification_private)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
