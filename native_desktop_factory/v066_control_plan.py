"""Offline grammar plan for prospective v0.6.6 native GUI control reruns.

This checks whether each historical evaluator script can be expressed as
bounded, current-frame v0.6.6 actions. It does not create a sandbox, replay an
action, attest a guest, or admit a final task. The private output binds per-ID
scripts; the public output contains aggregate counts only.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from cursibench import scale_action_contract_v066, scale_action_output_v066
from cursibench.scale_action_contract import ContractLimits, make_observation
from cursibench.scale_action_output_v066 import normalize_model_action
from cursibench.scale_action_contract_v066 import ACTION_PROFILE_VERSION
from native_desktop_factory import qwen_v066_adapter

if __package__:
    from . import admit
    from .calibrate_sweep import actor_script
    from .final_admission_preflight_v065 import _shell_key
else:
    import admit
    from calibrate_sweep import actor_script
    from final_admission_preflight_v065 import _shell_key


MAX_ACTIONS = 90
ALLOWED_SCRIPT_KEYS = frozenset({
    "Control+A", "Control+S", "Control+F", "Control+H", "Control+End",
    "Shift+End", "Escape", "Enter", "Home",
})


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def compile_script(script: str) -> tuple[list[dict], Counter]:
    """Map evaluator shell lines to actions or strictly named trusted guards."""
    actions: list[dict] = []
    guards: Counter = Counter()
    lines = script.splitlines()
    if not lines or lines[-1] != "stop" or lines.count("stop") != 1:
        raise ValueError("A script must end with exactly one stop")
    if lines == ["stop"]:
        return [], Counter({"teardown_requests": 1})
    for line in lines:
        name, separator, value = line.partition(" ")
        if name in ("click", "double"):
            if not separator or len(value.split(",")) != 2:
                raise ValueError("Malformed GUI point")
            x, y = (int(part) for part in value.split(","))
            actions.append({"type": "double_click" if name == "double" else "click",
                            "target": {"x": x, "y": y}})
        elif name == "press":
            key = _shell_key(value.split(","))
            if key not in ALLOWED_SCRIPT_KEYS:
                raise ValueError("Evaluator script needs an unapproved key chord")
            actions.append({"type": "key", "key": key})
        elif name == "write":
            if not separator or not value:
                raise ValueError("Empty focused insertion")
            actions.append({"type": "type", "text": value, "mode": "insert"})
        elif name == "wait":
            seconds = Decimal(value)
            milliseconds = seconds * 1000
            if not milliseconds == int(milliseconds) or not 0 < milliseconds <= 10_000:
                raise ValueError("Evaluator wait is not bounded")
            remaining = int(milliseconds)
            while remaining:
                duration = min(remaining, 2_000)
                actions.append({"type": "wait", "duration_ms": duration})
                remaining -= duration
        elif name == "assert_window":
            if not separator or not value:
                raise ValueError("Empty trusted visible-window guard")
            guards["visible_window_assertions"] += 1
        elif name == "screen":
            if not separator or not value:
                raise ValueError("Empty trusted screenshot label")
            guards["evaluator_screenshots"] += 1
        elif name == "readback":
            if separator:
                raise ValueError("Readback has unexpected arguments")
            guards["saved_artifact_readbacks"] += 1
        elif name == "stop":
            if separator:
                raise ValueError("Stop has unexpected arguments")
            guards["teardown_requests"] += 1
        else:
            raise ValueError("Unrecognized evaluator shell operation")
    if len(actions) > MAX_ACTIONS or guards["saved_artifact_readbacks"] != 1:
        raise ValueError("Actor action budget or saved-artifact readback failed")
    return actions, guards


def _blank_observation():
    image = io.BytesIO()
    Image.new("RGB", (1280, 800), "white").save(image, format="PNG")
    return make_observation(
        task_id="train.offline_grammar_only", task_binding_sha256="a" * 64,
        instruction="Validate prospective GUI grammar only.", step=0,
        screenshot_bytes=image.getvalue(), controls=(),
        limits=ContractLimits(max_step=MAX_ACTIONS),
    )


def audit(candidate_root: Path, v065_public: Path) -> tuple[dict, dict]:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    prior = json.loads(v065_public.read_bytes())
    if (inventory.get("design_revision") != "v2-distinct-structures"
            or len(final) != 100
            or prior.get("candidate_inventory_sha256") != digest(inventory_raw)
            or prior.get("qualified_under_current_v065") != 0
            or prior.get("historical_gui_trios_passed") != 100):
        raise ValueError("The blocked 100-task v0.6.5 ledger changed")
    frame = _blank_observation()
    private_rows: list[dict] = []
    action_totals: Counter = Counter()
    guard_totals: Counter = Counter()
    per_app_max: dict[str, int] = {}
    for row in final:
        package_dir, _baseline, oracle = admit._package(candidate_root, row)
        app = ("Calc" if row["workflow"].startswith("calc-") else
               "Impress" if row["workflow"].startswith("impress-") else
               "Writer" if row["workflow"].startswith("writer-") else None)
        if app is None:
            raise ValueError("Unknown final application")
        attempts: dict[str, dict] = {}
        for polarity in ("positive", "near-miss"):
            script = actor_script(package_dir, oracle, polarity)
            actions, guards = compile_script(script)
            kinds = Counter()
            for action in actions:
                checked = normalize_model_action(
                    json.dumps(action, separators=(",", ":")), frame,
                    current_frame_id=frame.frame_id)
                if checked["type"] != action["type"]:
                    raise ValueError("A prospective action was not preserved")
                kinds[action["type"]] += 1
            action_totals.update(kinds)
            guard_totals.update(guards)
            per_app_max[app] = max(per_app_max.get(app, 0), len(actions))
            attempts[polarity] = {
                "historical_evaluator_script_sha256": digest(script.encode()),
                "prospective_action_count": len(actions),
                "prospective_action_kinds": dict(sorted(kinds.items())),
                "trusted_guard_counts": dict(sorted(guards.items())),
                "grammar_validated_against_synthetic_frame": True,
                "live_per_action_current_frame_proved": False,
                "live_guest_content_attested": False,
            }
        private_rows.append({
            "private_task_id": row["task_id"],
            "package_sha256": row["package_sha256"],
            "application": app,
            "positive_and_near_miss": attempts,
            "fresh_cold_reset_under_v066": False,
            "qualified_under_v066": False,
        })
    private = {
        "schema": "cua-native-wdi-v066-control-rerun-plan-private-v1",
        "status": "grammar_only_no_gui_or_guest_proof",
        "candidate_inventory_sha256": digest(inventory_raw),
        "v065_public_preflight_sha256": digest(v065_public.read_bytes()),
        "action_profile": ACTION_PROFILE_VERSION,
        "v066_full_action_validator_sha256": digest(
            Path(scale_action_contract_v066.__file__).read_bytes()),
        "v066_minimal_output_adapter_sha256": digest(
            Path(scale_action_output_v066.__file__).read_bytes()),
        "v066_native_dispatch_adapter_sha256": digest(
            Path(qwen_v066_adapter.__file__).read_bytes()),
        "per_id": private_rows,
        "official_admitted_final_count": 0,
        "official_model_result_count": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-control-rerun-plan-public-v1",
        "checked_date": "2026-09-27",
        "status": "grammar_only_no_gui_or_guest_proof",
        "candidate_inventory_sha256": digest(inventory_raw),
        "v065_public_preflight_sha256": digest(v065_public.read_bytes()),
        "action_profile": ACTION_PROFILE_VERSION,
        "v066_full_action_validator_sha256": private["v066_full_action_validator_sha256"],
        "v066_minimal_output_adapter_sha256": private["v066_minimal_output_adapter_sha256"],
        "v066_native_dispatch_adapter_sha256": private["v066_native_dispatch_adapter_sha256"],
        "candidate_final_tasks": len(final),
        "historical_gui_trios_retained": prior["historical_gui_trios_passed"],
        "prospective_positive_scripts_grammar_valid": len(final),
        "prospective_near_miss_scripts_grammar_valid": len(final),
        "prospective_action_totals_both_polarities": dict(sorted(action_totals.items())),
        "trusted_guard_totals_both_polarities": dict(sorted(guard_totals.items())),
        "max_prospective_actions_by_application": dict(sorted(per_app_max.items())),
        "v066_live_gui_trios_with_guest_attestation": 0,
        "qualified_under_v066": 0,
        "official_full_study_admitted_final_count": 0,
        "official_model_result_count": 0,
        "new_e2b_sandboxes_created_by_this_audit": 0,
        "actual_provider_billed_usd": None,
    }
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--v065-public", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Refusing to overwrite an existing control plan")
    private, public = audit(args.candidate_root, args.v065_public)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
    args.private_out.chmod(0o600)
    public["private_control_plan_sha256"] = digest(args.private_out.read_bytes())
    args.public_out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: public[key] for key in (
        "prospective_positive_scripts_grammar_valid",
        "prospective_near_miss_scripts_grammar_valid",
        "v066_live_gui_trios_with_guest_attestation",
        "qualified_under_v066",
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
