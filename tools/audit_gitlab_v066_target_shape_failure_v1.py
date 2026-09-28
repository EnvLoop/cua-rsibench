"""Classify the paid GitLab train response without exposing private task data."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re

from cursibench import scale_action_contract, scale_action_output_v066
from cursibench.scale_action_output_v062 import _parse_one_object
from cursibench.scale_action_output_v065 import _normalize_one_fence


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "work/gitlab-full-world/v066-one-train-gui-pair-preintent-20260928"
AUDIT = ROOT / "docs/evidence/gitlab-v066-train-preintent-resample-result-2026-09-28.json"
PUBLIC_OUT = ROOT / "docs/evidence/gitlab-v066-target-shape-failure-2026-09-28.json"


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def read_private(path: Path) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(RUN.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            "private_paid_train_request_or_response_missing")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, "private_paid_train_json_required")
    return value, sha256(raw).hexdigest()


def audit() -> dict:
    prior_raw = AUDIT.read_bytes()
    prior = json.loads(prior_raw)
    require(prior.get("status") ==
            "second_train_only_attempt_failed_unqualified_no_replay" and
            prior.get("provider_intents") ==
            prior.get("provider_requests") ==
            prior.get("provider_responses") ==
            prior.get("raw_frames") == 1 and
            prior.get("post_failure_baseline_exact") is True and
            prior.get("tinker_sft_eligible_episodes") == 0,
            "paid_train_failure_not_independently_unqualified")
    provider = RUN / "positive-provider"
    request, request_sha = read_private(
        provider / "step-000-request.private.json")
    response, response_sha = read_private(
        provider / "step-000-response.private.json")
    intent, intent_sha = read_private(
        provider / "step-000-intent.private.json")
    user = json.loads(request["user_text"])
    model_instruction = json.loads(user["model_instruction"])
    action = _parse_one_object(_normalize_one_fence(response["text"]))
    target = action.get("target")
    refs = set(re.findall(r"\bc\d{3}\b", user["visible_text"]))
    usage = response.get("receipt", {}).get("usage", {})
    require(intent.get("request_sha256") == request_sha and
            intent.get("provider_replay_authorized") is False and
            response.get("receipt", {}).get("reported_model") ==
            request.get("model") and
            response.get("receipt", {}).get("status") == "completed" and
            user.get("arm") == "positive" and
            model_instruction.get("contract", "").find(
                "a ref copied verbatim") >= 0 and
            action.get("type") == "click" and
            set(action) == {"type", "target"} and
            type(target) is str and target in refs and
            len(refs) > 0 and
            type(usage.get("input_tokens")) is int and
            type(usage.get("output_tokens")) is int and
            not (RUN / "positive" / "actions.private.json").exists() and
            not (RUN / "negative-intent.private.json").exists(),
            "paid_train_response_not_bare_visible_ref_without_dispatch")
    return {
        "schema": "envloop-gitlab-v066-paid-target-shape-forensic-v1",
        "status": "one_paid_train_response_rejected_before_gui_dispatch",
        "prior_failure_audit_sha256": sha256(prior_raw).hexdigest(),
        "private_request_sha256": request_sha,
        "private_response_sha256": response_sha,
        "private_provider_intent_sha256": intent_sha,
        "model": request["model"],
        "current_visible_ref_count": len(refs),
        "response_action_type": "click",
        "response_target_value_type": "bare_string",
        "response_target_was_current_visible_ref": True,
        "validator_requires_target_object": True,
        "validator_source_sha256": sha256(
            Path(scale_action_contract.__file__).read_bytes()).hexdigest(),
        "normalizer_source_sha256": sha256(
            Path(scale_action_output_v066.__file__).read_bytes()).hexdigest(),
        "accepted_actor_actions": 0,
        "independent_post_failure_reset_exact": True,
        "provider_reported_input_tokens": usage["input_tokens"],
        "provider_reported_output_tokens": usage["output_tokens"],
        "actual_provider_billed_usd": None,
        "provider_replay_authorized": False,
        "tinker_sft_eligible_episodes": 0,
        "official_final_admitted": 0,
        "auditor_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    result = audit()
    require(not PUBLIC_OUT.exists(), "fresh_paid_target_shape_forensic_required")
    fd = os.open(PUBLIC_OUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(json.dumps(result, sort_keys=True,
                                separators=(",", ":")).encode())
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"],
                      "response_target_value_type": "bare_string",
                      "accepted_actor_actions": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
