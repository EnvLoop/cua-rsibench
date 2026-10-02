"""One prospective final GUI control with a public-train scoped profile.

This process never calls a model. Trusted setup may inspect the private oracle
and stage its input; the actor path only uses screenshots and E2B GUI methods.
This is a new source epoch; the historical v0.6.6 runner and receipts remain
unchanged. It refuses a create without source ratification, a new private
application reference, per-attempt intent, and the host-space floor.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

from cursibench.scale_action_contract import ContractError

from . import admit, qwen_v066_adapter, runtime_fingerprint_probe
from . import v066_scoped_profile_guard as scoped_guard
from .v066_scoped_profile_bridge import validate as validate_bridge
from .v066_scoped_profile_reference import (
    validate_reference, workflow_kind,
)
from .calibrate_sweep import actor_script
from .final_admission_preflight_v065 import _shell_key
from .gui_control_shell import wait_for_document_ready
from .official_saved_verifier import verify_official
from .v066_control_plan import ALLOWED_SCRIPT_KEYS, compile_script
from .v066_final_freeze import (LEASE_SECONDS, digest, validate_lane,
                                intent_budget)
from .v066_storage_budget import audit as storage_audit, reserve_and_write


ATTEMPTS = ("positive", "near-miss", "cold-reset")
MAX_ACTIONS = 90


class RecordingDesktop:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.last_screenshot = b""

    def screenshot(self):
        self.last_screenshot = bytes(self.sandbox.screenshot())
        return self.last_screenshot

    def __getattr__(self, name):
        return getattr(self.sandbox, name)


def _operations(script: str):
    """Keep trusted guards in exact order while splitting bounded GUI waits."""
    compile_script(script)  # Exact script grammar and overall 90-action cap.
    for line in script.splitlines():
        name, separator, value = line.partition(" ")
        if name in ("click", "double"):
            x, y = (int(part) for part in value.split(","))
            yield "actor", {"type": "double_click" if name == "double" else "click",
                            "target": {"x": x, "y": y}}
        elif name == "press":
            key = _shell_key(value.split(","))
            if key not in ALLOWED_SCRIPT_KEYS:
                raise ValueError("Unapproved evaluator key chord")
            yield "actor", {"type": "key", "key": key}
        elif name == "write":
            yield "actor", {"type": "type", "text": value, "mode": "insert"}
        elif name == "wait":
            remaining = int(float(value) * 1000)
            while remaining:
                duration = min(2000, remaining)
                yield "actor", {"type": "wait", "duration_ms": duration}
                remaining -= duration
        else:
            yield name, value if separator else None


def _assert_window(sandbox, fragment: str) -> str:
    for _ in range(8):
        result = sandbox.commands.run(
            "xdotool getactivewindow getwindowname 2>/dev/null || true")
        title = result.stdout.strip()
        if fragment in title:
            return title
        time.sleep(0.4)
    raise ValueError("Trusted visible-window guard failed")


def execute(*, candidate_root: Path, attempts_root: Path, task_id: str,
            attempt: str, private_map: Path, profile_private: Path,
            guest_public: Path, fair_public: Path, ratification: Path,
            reservation: Path, scoped_reference: Path,
            runtime_freeze: Path, three_root_bridge: Path,
            original_root: Path, failed_root: Path,
            public_calibration: Path, private_calibration_audit: Path,
            failed_private_stop: Path,
            failed_public_interruption: Path,
            enable_paid_scoped_final: bool = False) -> dict:
    if enable_paid_scoped_final is not True:
        raise ValueError("Scoped final control is disabled before source freeze")
    validate_bridge(
        bridge_path=three_root_bridge,
        candidate_root=candidate_root,
        original_root=original_root,
        failed_root=failed_root,
        fresh_root=attempts_root,
        action_ratification=ratification,
        public_calibration=public_calibration,
        private_calibration_audit=private_calibration_audit,
        scoped_reference=scoped_reference,
        runtime_freeze=runtime_freeze,
        new_lane_reservation=reservation,
        failed_private_stop=failed_private_stop,
        failed_public_interruption=failed_public_interruption,
        profile_private=profile_private,
        guest_public=guest_public,
        fair_public=fair_public)
    if attempt not in ATTEMPTS:
        raise ValueError("Unknown prospective control polarity")
    lane = validate_lane(
        ratification=ratification, reservation=reservation,
        candidate_root=candidate_root, guest_public=guest_public,
        profile_private=profile_private, fair_public=fair_public)
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    matches = [row for row in inventory["tasks"]
               if row["split"] == "final_candidate" and row["task_id"] == task_id]
    if len(matches) != 1:
        raise ValueError("Final task absent from the private frozen inventory")
    row = matches[0]
    package_dir, baseline, oracle = admit._package(candidate_root, row)
    paths = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
             *package_dir.glob("*.docx")]
    if len(paths) != 1:
        raise ValueError("Prospective task must stage exactly one OOXML input")
    profile_manifest = json.loads(profile_private.read_bytes())
    profiles = [item for item in profile_manifest["accepted"]
                if item["private_task_id"] == task_id and
                item["package_sha256"] == row["package_sha256"]]
    if len(profiles) != 1:
        raise ValueError("Task-specific neutral LibreOffice baseline is missing")
    reference, reference_sha = validate_reference(scoped_reference)
    app_kind = workflow_kind(row["workflow"])
    if app_kind not in reference["applications"]:
        raise ValueError("Public train application profile reference absent")
    mapping = json.loads(private_map.read_bytes())
    private_salt = mapping.get("variant_salt")
    if not isinstance(private_salt, str) or len(private_salt) < 32:
        raise ValueError("Evaluator-private fair-scorer salt missing")
    guest = json.loads(guest_public.read_bytes())
    script = actor_script(package_dir, oracle, attempt)
    expected_actions, _guards = compile_script(script)
    if attempt == "cold-reset" and expected_actions:
        raise ValueError("Cold reset must have no actor actions")
    out = attempts_root / task_id / attempt
    intent_path = out / "intent.json"
    if (out.resolve().parent.parent != attempts_root.resolve()
            or not intent_path.is_file() or (out / "receipt.json").exists()):
        raise ValueError("An immutable per-ID intent is required before provider create")
    intent = json.loads(intent_path.read_bytes())
    if (intent.get("schema") != "cua-native-wdi-v066-final-control-intent-v1"
            or intent.get("task_id") != task_id or intent.get("attempt") != attempt
            or intent.get("package_sha256") != row["package_sha256"]
            or intent.get("lease_seconds") != LEASE_SECONDS
            or intent.get("ratification_sha256") != digest(ratification.read_bytes())
            or intent.get("reservation_sha256") != digest(reservation.read_bytes())
            or intent.get("scoped_reference_sha256") !=
            digest(scoped_reference.read_bytes())
            or intent.get("scoped_runtime_freeze_sha256") !=
            digest(runtime_freeze.read_bytes())
            or intent.get("three_root_bridge_sha256") !=
            digest(three_root_bridge.read_bytes())):
        raise ValueError("Prospective E2B create intent changed")
    if (storage_audit(attempts_root)["dispatch_storage_ready"] is not True
            or intent_budget(attempts_root)["combined_intents"] >
            lane["maximum_attempt_count_including_manual_recovery"]):
        raise ValueError("Separate lane or host storage is not ready")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential missing")
    receipt = {
        "schema": "cua-native-wdi-v066-gui-control-attempt-v1",
        "status": "started", "stage": "pre_provider", "task_id": task_id,
        "attempt": attempt, "split": "final_candidate",
        "input_sha256": digest(baseline),
        "package_sha256": row["package_sha256"],
        "evaluator_script_sha256": digest(script.encode()),
        "expected_actor_action_count": len(expected_actions),
        "sandbox_timeout_seconds": LEASE_SECONDS,
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "ratification_sha256": digest(ratification.read_bytes()),
        "lane_reservation_sha256": digest(reservation.read_bytes()),
        "task_profile_private_manifest_sha256": digest(profile_private.read_bytes()),
        "profile_reference_private_sha256": reference_sha,
        "profile_scope_guard_source_sha256": digest(Path(scoped_guard.__file__).read_bytes()),
        "profile_application_kind": app_kind,
        "scoped_runtime_freeze_sha256": digest(runtime_freeze.read_bytes()),
        "three_root_bridge_sha256": digest(three_root_bridge.read_bytes()),
        "guest_identity_public_sha256": digest(guest_public.read_bytes()),
        "fair_scorer_public_sha256": digest(fair_public.read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "native_adapter_sha256": digest(Path(qwen_v066_adapter.__file__).read_bytes()),
        "actor_steps": [], "physical_frame_resamples": [],
        "trusted_ui_guards": [], "trusted_screenshots": [],
        "actual_provider_billed_usd": None,
        "official_hidden_final_model_attempts": 0,
        "official_final_admissions": 0,
    }

    def persist():
        path = out / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)

    persist()
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        receipt["stage"] = "create_desktop"
        persist()
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=LEASE_SECONDS, allow_internet_access=False,
                                 metadata={"envloop_purpose": "v066-final-evaluator-control"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version,
        }
        if (info.template_id != guest["provider_template_id"]
                or info.envd_version != guest["provider_envd_version"]
                or info.cpu_count != guest["provider_shape"]["vcpu"]
                or info.memory_mb != guest["provider_shape"]["memory_mb"]):
            raise ValueError("Provider E2B Desktop resource/image reference changed")
        receipt["stage"] = "guest_content_attestation"
        persist()
        sandbox.files.write("/tmp/native-guest-content-probe-v066.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        run = sandbox.commands.run("sudo -n python3 /tmp/native-guest-content-probe-v066.py",
                                   timeout=450, request_timeout=480)
        if run.exit_code != 0:
            raise ValueError("Scoped guest-content probe failed")
        observed_guest = json.loads(run.stdout)
        if (observed_guest.get("content_tree_sha256") != guest["static_content_sha256"]
                or observed_guest.get("counts") != guest["static_content_counts"]
                or observed_guest.get("kernel") != guest["kernel_identity"]
                or observed_guest.get("excluded_paths") != guest["static_content_excluded_paths"]):
            raise ValueError("Guest content differs from the frozen reference")
        receipt["guest_content_sha256"] = observed_guest["content_tree_sha256"]
        receipt["guest_content_attested"] = True
        run = sandbox.commands.run("test ! -e /home/user/.config/libreoffice/4/user")
        if run.exit_code != 0:
            raise ValueError("Fresh LibreOffice profile was already present")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + paths[0].name
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Trusted staged input differs from final package")
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox, paths[0].name)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        scoped_guard.attest(
            sandbox=sandbox, attempts_root=attempts_root, out=out,
            app_kind=app_kind, reference_path=scoped_reference,
            receipt=receipt, persist=persist)

        if attempt != "cold-reset":
            recorder = RecordingDesktop(sandbox)
            previous = None
            step_index = 0
            readback_seen = False
            for operation, value in _operations(script):
                if operation == "actor":
                    minimal_raw = json.dumps(value, separators=(",", ":"))
                    for frame_attempt in range(5):
                        receipt["stage"] = "current_frame_gui"
                        frame = qwen_v066_adapter.observe(
                            recorder, task_id=task_id,
                            task_binding_sha256=row["package_sha256"],
                            instruction=(package_dir / "actor_task.txt").read_text(),
                            step=step_index, previous_action_result=previous,
                            max_actions=MAX_ACTIONS)
                        observed = reserve_and_write(
                            attempts_root, out / f"frame-{step_index:02d}-{frame_attempt}.png",
                            frame.screenshot_bytes)
                        try:
                            action = qwen_v066_adapter.parse_current_action(
                                minimal_raw, frame, recorder)
                            break
                        except qwen_v066_adapter.PhysicalFrameDrift:
                            changed = reserve_and_write(
                                attempts_root,
                                out / f"drift-{step_index:02d}-{frame_attempt}.png",
                                recorder.last_screenshot)
                            receipt["physical_frame_resamples"].append({
                                "step": step_index, "attempt": frame_attempt,
                                "observed": observed, "changed": changed,
                            })
                            persist()
                            time.sleep(1)
                    else:
                        raise qwen_v066_adapter.PhysicalFrameDrift()
                    predispatch = reserve_and_write(
                        attempts_root,
                        out / f"predispatch-{step_index:02d}-{frame_attempt}.png",
                        recorder.last_screenshot)
                    step_row = {
                        "step": step_index,
                        "frame_id_sha256": digest(frame.frame_id.encode()),
                        "observation": observed, "predispatch": predispatch,
                        "action_type": action["type"],
                        "action_payload_sha256": digest(minimal_raw.encode()),
                        "status": "validated_pre_dispatch",
                    }
                    receipt["actor_steps"].append(step_row)
                    persist()
                    step_row["dispatch_type"] = qwen_v066_adapter.dispatch(sandbox, action)
                    step_row["status"] = "applied"
                    step_index += 1
                    previous = {"status": "applied", "code": "ok"}
                    persist()
                elif operation == "assert_window":
                    title = _assert_window(sandbox, value)
                    receipt["trusted_ui_guards"].append({
                        "expected_sha256": digest(value.encode()),
                        "observed_sha256": digest(title.encode()), "passed": True})
                    persist()
                elif operation == "screen":
                    raw = bytes(sandbox.screenshot())
                    saved_frame = reserve_and_write(
                        attempts_root, out / f"guard-{value}.png", raw)
                    receipt["trusted_screenshots"].append(saved_frame)
                    persist()
                elif operation == "readback":
                    saved = bytes(sandbox.files.read(remote, format="bytes"))
                    saved_ref = reserve_and_write(
                        attempts_root, out / ("saved" + paths[0].suffix), saved)
                    score = verify_official(baseline, saved, oracle,
                                            private_salt=private_salt)
                    expected = attempt == "positive"
                    if (digest(saved) == digest(baseline)
                            or score["passed"] is not expected
                            or (not expected and (not score["errors"] or
                                any(not error.startswith("target_") for error in score["errors"])))):
                        raise ValueError("Independent saved-artifact control polarity failed")
                    receipt["saved_artifact"] = saved_ref
                    receipt["fair_verifier"] = score
                    readback_seen = True
                    persist()
                elif operation == "stop":
                    break
                else:
                    raise ValueError("Unexpected evaluator shell operation")
            if step_index != len(expected_actions) or not readback_seen:
                raise ValueError("Prospective GUI control missed an action or readback")
            receipt["status"] = "control_passed_before_teardown"
        else:
            cold_frame = bytes(sandbox.screenshot())
            receipt["cold_observation"] = reserve_and_write(
                attempts_root, out / "cold-neutral-open.png", cold_frame)
            restored = bytes(sandbox.files.read(remote, format="bytes"))
            if restored != baseline:
                raise ValueError("Fresh guest did not restore original OOXML bytes")
            receipt["restored_state_sha256"] = digest(restored)
            receipt["status"] = "cold_reset_observed_before_teardown"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        if isinstance(exc, ContractError):
            receipt["contract_error_code"] = exc.code
        receipt["status"] = "control_failed_or_infrastructure_invalid"
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if receipt.get("is_running_after_kill") is not False:
            receipt["status"] = "cleanup_unverified"
        elif receipt["status"] == "control_passed_before_teardown":
            receipt["status"] = "control_passed"
        elif receipt["status"] == "cold_reset_observed_before_teardown":
            receipt["status"] = "cold_reset_observed"
        persist()
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("candidate-root", "attempts-root", "task-id", "attempt",
                  "private-map", "profile-private", "guest-public", "fair-public",
                  "ratification", "reservation", "scoped-reference",
                  "runtime-freeze", "three-root-bridge", "original-root",
                  "failed-root", "public-calibration",
                  "private-calibration-audit", "failed-private-stop",
                  "failed-public-interruption"):
        parser.add_argument("--" + field, type=Path if field not in
                            ("task-id", "attempt") else str, required=True)
    parser.add_argument("--enable-paid-scoped-final", action="store_true")
    args = parser.parse_args()
    result = execute(candidate_root=args.candidate_root,
                     attempts_root=args.attempts_root,
                     task_id=args.task_id, attempt=args.attempt,
                     private_map=args.private_map,
                     profile_private=args.profile_private,
                     guest_public=args.guest_public,
                     fair_public=args.fair_public,
                     ratification=args.ratification,
                     reservation=args.reservation,
                     scoped_reference=args.scoped_reference,
                     runtime_freeze=args.runtime_freeze,
                     three_root_bridge=args.three_root_bridge,
                     original_root=args.original_root,
                     failed_root=args.failed_root,
                     public_calibration=args.public_calibration,
                     private_calibration_audit=args.private_calibration_audit,
                     failed_private_stop=args.failed_private_stop,
                     failed_public_interruption=args.failed_public_interruption,
                     enable_paid_scoped_final=args.enable_paid_scoped_final)
    print(json.dumps({
        "status": result["status"], "error_type": result.get("error_type"),
        "sandbox_id_observed": bool(result.get("sandbox_id_sha256")),
        "actor_actions_applied": sum(step["status"] == "applied"
                                     for step in result["actor_steps"]),
        "guest_attested": result.get("guest_content_attested", False),
        "cleanup_verified": result.get("is_running_after_kill") is False,
    }, sort_keys=True))
    if result["status"] not in ("control_passed", "cold_reset_observed"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
