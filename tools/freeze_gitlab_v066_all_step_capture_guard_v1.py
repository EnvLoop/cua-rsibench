"""Freeze a source-only GitLab all-step capture guard for independent review."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from gitlab_world import runtime


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = runtime.PRIVATE / "v066-all-step-capture-guard-plan.private.json"
PUBLIC = ROOT / "docs/evidence/gitlab-v066-all-step-capture-guard-freeze-2026-09-28.json"
LAST_FAILURE = ROOT / "docs/evidence/gitlab-v066-target-shape-train-result-2026-09-28.json"
FORENSIC = ROOT / "docs/evidence/gitlab-v066-next-frame-failure-2026-09-28.json"
FIRST_PAID = ROOT / "docs/evidence/gitlab-v066-target-shape-failure-2026-09-28.json"
FINAL_PLAN = ROOT / "docs/evidence/gitlab-v066-prospective-final-control-plan-2026-09-28.json"
SCHEMA = "envloop-gitlab-v066-all-step-capture-guard-plan-private-v1"
PUBLIC_SCHEMA = "envloop-gitlab-v066-all-step-capture-guard-freeze-public-v1"
SOURCE_FILES = (
    "gitlab_world/v066_all_step_capture_guard_v1.py",
    "tests/test_gitlab_v066_all_step_capture_guard.py",
    "tools/freeze_gitlab_v066_all_step_capture_guard_v1.py",
    "tools/audit_gitlab_v066_next_frame_failure_v1.py",
    "docs/FULL_STUDY_GITLAB_V066_ALL_STEP_CAPTURE_GUARD_2026-09-28.md",
    "gitlab_world/teacher_episode_worker_v066.py",
    "gitlab_world/vision_actor.py",
    "gitlab_world/vision_actor_v066_train.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v066.py",
)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode()


def sources() -> dict[str, str]:
    return {name: sha((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def read_public(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "guard_source_public_evidence_not_json_object")
    return value, sha(raw)


def prerequisites() -> dict:
    failed, failed_sha = read_public(LAST_FAILURE)
    forensic, forensic_sha = read_public(FORENSIC)
    earlier, earlier_sha = read_public(FIRST_PAID)
    final_plan, final_sha = read_public(FINAL_PLAN)
    require(failed.get("status") ==
            "new_disjoint_train_pair_failed_unqualified_no_replay" and
            failed.get("provider_responses") == 1 and
            failed.get("recorded_positive_teacher_calls") == 1 and
            failed.get("post_failure_baseline_exact") is True and
            failed.get("tinker_sft_eligible_episodes") == 0 and
            failed.get("official_final_admitted") == 0 and
            forensic.get("schema") ==
            "envloop-gitlab-v066-next-frame-failure-forensic-v1" and
            forensic.get("independent_failure_audit_sha256") == failed_sha and
            forensic.get("step_one_provider_intents") == 0 and
            forensic.get("step_one_saved_raw_frames") == 0 and
            forensic.get("durable_gui_dispatch_acknowledgment_present") is False and
            earlier.get("status") ==
            "one_paid_train_response_rejected_before_gui_dispatch" and
            earlier.get("official_final_admitted") == 0 and
            final_plan.get("status") ==
            "source_frozen_fresh_100_id_gui_controls_not_run" and
            final_plan.get("candidate_id_count") == 100 and
            final_plan.get("current_v066_completed_control_ids") == 0 and
            final_plan.get("official_final_admitted") == 0,
            "all_step_guard_previous_failures_or_final_boundary_changed")
    pre = json.loads((runtime.PRIVATE / "demo-prestop.json").read_bytes())
    current = runtime.proof(runtime.DEMO)
    require(runtime.stable_identity(pre) == runtime.stable_identity(current) and
            current["running"] is True and current["health"] == "healthy",
            "preserved_original_gitlab_demo_not_restored")
    try:
        runtime.inspect(runtime.WORLD)
    except subprocess.CalledProcessError:
        world_absent = True
    else:
        world_absent = False
    require(world_absent,
            "disposable_gitlab_world_must_be_absent_for_source_only_freeze")
    input_tokens = (earlier["provider_reported_input_tokens"] +
                    failed["provider_reported_input_tokens"])
    output_tokens = (earlier["provider_reported_output_tokens"] +
                     failed["provider_reported_output_tokens"])
    return {
        "last_failure_public_sha256": failed_sha,
        "next_frame_forensic_public_sha256": forensic_sha,
        "first_paid_shape_forensic_public_sha256": earlier_sha,
        "prospective_100_control_plan_public_sha256": final_sha,
        "preserved_demo_identity_sha256": sha(canonical(runtime.stable_identity(pre))),
        "previous_paid_train_responses": 2,
        "previous_provider_reported_input_tokens": input_tokens,
        "previous_provider_reported_output_tokens": output_tokens,
        "actual_provider_billed_usd": None,
    }


def write_new(path: Path, value: dict, mode: int) -> str:
    require(not path.exists() and not path.is_symlink(),
            "fresh_guard_source_freeze_output_required")
    raw = canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def freeze() -> dict:
    require(not PRIVATE.exists() and not PUBLIC.exists() and
            runtime.PRIVATE.stat().st_mode & 0o077 == 0,
            "fresh_restrictive_all_step_guard_freeze_required")
    references = prerequisites()
    test = subprocess.run(
        [sys.executable, "-m", "unittest",
         "tests.test_gitlab_v066_all_step_capture_guard"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        check=False)
    require(test.returncode == 0 and "Ran 4 tests" in test.stderr and
            "OK" in test.stderr,
            "simulated_dynamic_frame_and_no_replay_tests_failed")
    source = sources()
    private = {
        "schema": SCHEMA,
        "status": "source_frozen_for_review_no_live_guard_or_fourth_paid_call",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256s": source,
        "source_bundle_sha256": sha(canonical(source)),
        **references,
        "max_capture_attempts_per_step": 5,
        "every_step_requires_no_current_provider_or_gui_intent": True,
        "dispatch_intent_written_before_original_gui_action": True,
        "original_actor_parser_worker_bytes_unchanged": True,
        "simulated_test_count": 4,
        "simulated_test_stderr_sha256": sha(test.stderr.encode()),
        "fourth_paid_train_calls": 0,
        "current_v066_final_control_ids": 0,
        "official_final_admitted": 0,
    }
    private_sha = write_new(PRIVATE, private, 0o600)
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": "source_frozen_review_only_no_live_guard_or_final_controls",
        "private_plan_sha256": private_sha,
        "source_bundle_sha256": private["source_bundle_sha256"],
        **references,
        "max_capture_attempts_per_step": 5,
        "simulated_test_count": 4,
        "original_actor_parser_worker_bytes_unchanged": True,
        "directly_amends_prospective_final_100_controller": False,
        "fourth_paid_train_calls": 0,
        "current_v066_final_control_ids": 0,
        "official_final_admitted": 0,
    }
    write_new(PUBLIC, public, 0o644)
    return public


def audit() -> dict:
    references = prerequisites()
    raw = PRIVATE.read_bytes()
    private = json.loads(raw)
    public = json.loads(PUBLIC.read_bytes())
    source = sources()
    require(private.get("schema") == SCHEMA and
            private.get("source_sha256s") == source and
            private.get("source_bundle_sha256") == sha(canonical(source)) and
            all(private.get(key) == value for key, value in references.items()) and
            private.get("max_capture_attempts_per_step") == 5 and
            private.get("simulated_test_count") == 4 and
            private.get("fourth_paid_train_calls") == 0 and
            private.get("current_v066_final_control_ids") == 0 and
            private.get("official_final_admitted") == 0 and
            public.get("schema") == PUBLIC_SCHEMA and
            public.get("private_plan_sha256") == sha(raw) and
            public.get("source_bundle_sha256") == private["source_bundle_sha256"] and
            public.get("directly_amends_prospective_final_100_controller") is False and
            public.get("fourth_paid_train_calls") == 0 and
            public.get("current_v066_final_control_ids") == 0 and
            public.get("official_final_admitted") == 0,
            "all_step_guard_source_or_boundary_changed")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit"))
    args = parser.parse_args()
    result = freeze() if args.action == "freeze" else audit()
    print(json.dumps({"status": result["status"],
                      "private_plan_sha256": result["private_plan_sha256"],
                      "simulated_test_count": 4,
                      "fourth_paid_train_calls": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
