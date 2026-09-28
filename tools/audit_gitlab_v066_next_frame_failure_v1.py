"""Classify retained GitLab train step-zero reply and missing next frame."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

from cursibench.scale_action_output_v062 import _parse_one_object
from cursibench.scale_action_output_v065 import _normalize_one_fence


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "work/gitlab-full-world/v066-one-train-gui-pair-target-shape-20260928"
AUDIT = ROOT / "docs/evidence/gitlab-v066-target-shape-train-result-2026-09-28.json"
PUBLIC = ROOT / "docs/evidence/gitlab-v066-next-frame-failure-2026-09-28.json"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def private_json(path: Path) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(RUN.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            "third_train_private_file_missing_or_unsafe")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "third_train_private_json_required")
    return value, sha256(raw).hexdigest()


def audit() -> dict:
    raw = AUDIT.read_bytes()
    prior = json.loads(raw)
    require(prior.get("status") ==
            "new_disjoint_train_pair_failed_unqualified_no_replay" and
            prior.get("provider_intents") ==
            prior.get("provider_requests") ==
            prior.get("provider_responses") ==
            prior.get("raw_frames") == 1 and
            prior.get("recorded_positive_teacher_calls") == 1 and
            prior.get("post_failure_baseline_exact") is True and
            prior.get("official_final_admitted") == 0,
            "third_train_failure_audit_changed")
    provider = RUN / "positive-provider"
    request, request_sha = private_json(
        provider / "step-000-request.private.json")
    response, response_sha = private_json(
        provider / "step-000-response.private.json")
    intent, intent_sha = private_json(
        provider / "step-000-intent.private.json")
    failure, failure_sha = private_json(RUN / "failure.private.json")
    user = json.loads(request["user_text"])
    instruction = json.loads(user["model_instruction"])
    visible = json.loads(user["visible_text"])
    action = _parse_one_object(_normalize_one_fence(response["text"]))
    target = action.get("target")
    matches = ([row for row in visible["controls"]
                if row.get("ref") == target.get("ref")]
               if type(target) is dict else [])
    require(intent.get("request_sha256") == request_sha and
            intent.get("provider_replay_authorized") is False and
            failure.get("reason_type") == "ContractError" and
            failure.get("positive_teacher_calls") == 1 and
            instruction.get("contract", "").startswith(
                "TARGET SHAPE RULE: target must be a JSON object") and
            action.get("type") == "click" and
            type(target) is dict and set(target) == {"ref"} and
            len(matches) == 1 and matches[0].get("role") == "link" and
            not (provider / "step-001-intent.private.json").exists() and
            not (RUN / "positive" / "frames" / "step-001.png").exists() and
            not (RUN / "positive" / "actions.private.json").exists() and
            not (RUN / "positive" / "episode.private.json").exists(),
            "third_train_reply_or_next_frame_shape_changed")
    return {
        "schema": "envloop-gitlab-v066-next-frame-failure-forensic-v1",
        "status": "first_response_well_shaped_next_frame_not_retained",
        "independent_failure_audit_sha256": sha256(raw).hexdigest(),
        "private_request_sha256": request_sha,
        "private_response_sha256": response_sha,
        "private_provider_intent_sha256": intent_sha,
        "private_failure_sha256": failure_sha,
        "first_model_action_type": "click",
        "first_target_type": "object_with_current_visible_ref",
        "first_target_control_role": "link",
        "normalized_teacher_turns_recorded_by_failure_receipt": 1,
        "step_one_provider_intents": 0,
        "step_one_saved_raw_frames": 0,
        "durable_gui_dispatch_acknowledgment_present": False,
        "page_transition_vs_animation_independently_distinguishable": False,
        "post_failure_business_reset_exact": True,
        "provider_or_gui_replay_authorized": False,
        "tinker_sft_eligible_episodes": 0,
        "official_final_admitted": 0,
        "auditor_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    result = audit()
    require(not PUBLIC.exists(), "fresh_next_frame_forensic_required")
    fd = os.open(PUBLIC, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(json.dumps(result, sort_keys=True,
                                separators=(",", ":")).encode())
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"],
                      "step_one_provider_intents": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
