"""Independently audit the separately frozen GitLab train capture amendment.

Success delegates every raw-frame/action/saved-state test to the original
one-pair auditor, then verifies the amendment and bounded rejected captures.
A failed second attempt is reported as unqualified without model replay.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from gitlab_world import reset, runtime, verify
from gitlab_world import v066_train_gui_pair as prior
from gitlab_world import v066_train_preintent_resample_v1 as amendment
from tools import audit_gitlab_v066_train_gui_pair as original_auditor


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_OUT = runtime.PRIVATE / "v066-train-preintent-resample-audit.private.json"
PUBLIC_OUT = ROOT / "docs/evidence/gitlab-v066-train-preintent-resample-result-2026-09-28.json"
SUCCESS_SCHEMA = "envloop-gitlab-v066-train-preintent-resample-success-audit-v1"
FAILURE_SCHEMA = "envloop-gitlab-v066-train-preintent-resample-failure-audit-v1"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def private_json(path: Path) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(runtime.PRIVATE.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            "private_train_amendment_file_missing_or_unsafe")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "private_train_amendment_json_required")
    return value, sha256(raw).hexdigest()


def retry_receipts() -> dict[str, int]:
    counts = {}
    for arm in ("positive", "negative"):
        rows = sorted(amendment.RUN_DIR.glob(f"capture-reject-{arm}-*.private.json"))
        require(len(rows) <= amendment.MAX_PRE_INTENT_CAPTURES and
                [path.name for path in rows] == [
                    f"capture-reject-{arm}-{index:02d}.private.json"
                    for index in range(1, len(rows) + 1)],
                "bounded_preintent_capture_attempts_changed")
        for index, path in enumerate(rows, 1):
            value, _digest = private_json(path)
            require(value == {
                "schema": "envloop-gitlab-v066-preintent-capture-reject-v1",
                "arm": arm, "step": 0, "attempt": index,
                "reason": "stale_frame",
                "provider_intent_exists": False,
                "actor_frame_or_action_exists": False,
                "replay_of_provider_call": False,
            }, "preintent_capture_rejection_receipt_changed")
        counts[arm] = len(rows)
    return counts


def common(ratification: Path) -> tuple[dict, str, str, dict[str, int]]:
    plan, plan_sha = amendment.validate_plan(ratification)
    execute, execute_sha = private_json(amendment.EXECUTE_INTENT)
    require(execute.get("schema") == amendment.EXECUTE_SCHEMA and
            execute.get("amendment_plan_sha256") == plan_sha and
            execute.get("prior_interruption_audit_sha256") ==
            plan["prior_interruption_audit_sha256"] and
            execute.get("run_dir_name") == amendment.RUN_DIR.name and
            execute.get("provider_replay_authorized") is False and
            execute.get("official_final_admitted") == 0 and
            amendment.RUN_DIR.is_dir() and
            amendment.RUN_DIR.stat().st_mode & 0o077 == 0,
            "fresh_second_train_attempt_not_bound_to_amendment")
    return plan, plan_sha, execute_sha, retry_receipts()


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
    plan, plan_sha, execute_sha, retries = common(ratification)
    require((amendment.RUN_DIR / "run.private.json").is_file() and
            not (amendment.RUN_DIR / "failure.private.json").exists(),
            "second_train_attempt_not_complete")
    original_run = prior.RUN_DIR
    prior.RUN_DIR = amendment.RUN_DIR
    try:
        private, public = original_auditor.audit(ratification)
    finally:
        prior.RUN_DIR = original_run
    exact, digest = exact_current_baseline()
    require(exact, "second_train_attempt_post_audit_baseline_not_exact")
    private.update({
        "amendment_schema": SUCCESS_SCHEMA,
        "amendment_plan_sha256": plan_sha,
        "amendment_execute_intent_sha256": execute_sha,
        "prior_interruption_audit_sha256":
            plan["prior_interruption_audit_sha256"],
        "pre_intent_capture_rejections": retries,
        "post_attempt_business_sha256": digest,
    })
    public.update({
        "schema": SUCCESS_SCHEMA,
        "status": "one_train_gui_pair_passed_under_separate_preintent_amendment",
        "amendment_plan_sha256": plan_sha,
        "amendment_execute_intent_sha256": execute_sha,
        "prior_interruption_audit_sha256":
            plan["prior_interruption_audit_sha256"],
        "pre_intent_capture_rejections": retries,
        "provider_replay_authorized": False,
        "post_attempt_baseline_exact": True,
        "post_attempt_business_sha256": digest,
        "official_final_admitted": 0,
    })
    return private, public


def audit_failure(ratification: Path) -> tuple[dict, dict]:
    plan, plan_sha, execute_sha, retries = common(ratification)
    failure, failure_sha = private_json(
        amendment.RUN_DIR / "failure.private.json")
    require(failure.get("schema") ==
            "envloop-gitlab-v066-train-pair-failure-v1" and
            failure.get("provider_replay_authorized") is False and
            failure.get("official_final_admitted") == 0 and
            not (amendment.RUN_DIR / "run.private.json").exists(),
            "second_train_failure_not_retained_unqualified")
    intents = requests = responses = frames = 0
    for arm in ("positive", "negative"):
        provider = amendment.RUN_DIR / (arm + "-provider")
        intents += len(list(provider.glob("*-intent.private.json")))
        requests += len(list(provider.glob("*-request.private.json")))
        responses += len(list(provider.glob("*-response.private.json")))
        frames += len(list((amendment.RUN_DIR / arm / "frames").glob("*.png")))
    exact, digest = exact_current_baseline()
    private = {
        "schema": FAILURE_SCHEMA,
        "status": "second_train_only_attempt_failed_unqualified_no_replay",
        "amendment_plan_sha256": plan_sha,
        "execute_intent_sha256": execute_sha,
        "failure_receipt_sha256": failure_sha,
        "reason_type": failure.get("reason_type"),
        "recorded_positive_teacher_calls":
            failure.get("positive_teacher_calls"),
        "provider_intents": intents, "provider_requests": requests,
        "provider_responses": responses, "raw_frames": frames,
        "pre_intent_capture_rejections": retries,
        "post_failure_baseline_exact": exact,
        "post_failure_business_sha256": digest,
        "provider_replay_authorized": False,
        "tinker_sft_eligible_episodes": 0,
        "official_final_admitted": 0,
    }
    public = {**private,
              "prior_interruption_audit_sha256":
                  plan["prior_interruption_audit_sha256"]}
    return private, public


def write_new(path: Path, value: dict, mode: int) -> str:
    require(not path.exists() and not path.is_symlink(),
            "fresh_train_amendment_audit_output_required")
    raw = prior.canonical(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratification-private", type=Path, required=True)
    args = parser.parse_args()
    if (amendment.RUN_DIR / "run.private.json").exists():
        private, public = audit_success(args.ratification_private)
    else:
        private, public = audit_failure(args.ratification_private)
    private_sha = write_new(PRIVATE_OUT, private, 0o600)
    public["private_audit_sha256"] = private_sha
    write_new(PUBLIC_OUT, public, 0o644)
    print(json.dumps({
        "status": public["status"],
        "positive_eligible_for_tinker_gui_sft":
            public.get("positive_eligible_for_tinker_gui_sft", False),
        "official_final_admitted": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
