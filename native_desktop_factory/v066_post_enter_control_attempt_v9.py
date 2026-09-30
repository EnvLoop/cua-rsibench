"""One new source-bound Desktop selection/final control trio after TRAIN v8.

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

from . import admit, runtime_fingerprint_probe
from . import qwen_v066_adapter_v4_strict as qwen_v066_adapter
from . import v066_post_enter_epoch_v9 as epoch
from .post_enter_control_proxy_v9 import PostEnterControlProxyV9
from . import v066_scoped_profile_guard as scoped_guard
from .v066_scoped_profile_reference import (
    validate_reference, workflow_kind,
)
from .calibrate_sweep import actor_script
from .final_admission_preflight_v065 import _shell_key
from .gui_control_shell import wait_for_document_ready
from .official_saved_verifier import verify_official
from .v066_control_plan import ALLOWED_SCRIPT_KEYS, compile_script
from .v066_final_freeze import digest
LEASE_SECONDS = epoch.LEASE_SECONDS
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


def execute(*, freeze_path: Path, permit_path: Path, task_id: str,
            attempt: str, enable_paid_controls: bool = False) -> dict:
    if enable_paid_controls is not True:
        raise ValueError("Prospective v9 paid control entry is disabled")
    value = epoch.validate(freeze_path)
    rows = [row for row in value["roster"] if row["task_id"] == task_id]
    epoch.require(len(rows) == 1, "v9_task_not_in_exact_new_roster")
    row = rows[0]
    epoch.checked_permit(freeze_path, permit_path, value, row)
    epoch.checked_inflight(value, row, attempt)
    candidate_root = Path(value["candidate_root"])
    attempts_root = Path(value["attempts_root"])
    private_map = Path(value["private_map"])
    guest_public = Path(value["guest_public"])
    scoped_reference = Path(value["scoped_reference"])
    ratification = Path(value["ratification"])
    if attempt not in ATTEMPTS:
        raise ValueError("Unknown prospective control polarity")
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    matches = [row for row in inventory["tasks"]
               if row["split"] in ("selection", "final_candidate") and row["task_id"] == task_id]
    if len(matches) != 1:
        raise ValueError("Final task absent from the private frozen inventory")
    row = matches[0]
    package_dir, baseline, oracle = admit._package(candidate_root, row)
    paths = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
             *package_dir.glob("*.docx")]
    if len(paths) != 1:
        raise ValueError("Prospective task must stage exactly one OOXML input")
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
    if (intent.get("schema") != "cua-native-wdi-post-enter-control-intent-v9"
            or intent.get("task_id") != task_id or intent.get("attempt") != attempt
            or intent.get("package_sha256") != row["package_sha256"]
            or intent.get("lease_seconds") != LEASE_SECONDS
            or intent.get("source_freeze_sha256") != digest(epoch.private(freeze_path))
            or intent.get("permit_sha256") != digest(epoch.private(permit_path))):
        raise ValueError("Prospective source/one-use intent changed")
    if (storage_audit(attempts_root)["dispatch_storage_ready"] is not True or
            len(list(attempts_root.glob("*/*/intent.json"))) > 360):
        raise ValueError("Prospective raw storage/finite 120-trio bound unavailable")
    from .v066_post_enter_train_calibration_v1 import SDK_VERSIONS
    if {name: importlib.metadata.version(name) for name in SDK_VERSIONS} != SDK_VERSIONS:
        raise ValueError("Pinned Desktop SDK runtime changed")
    from .reconcile_interrupted_sweep import active_hashes
    active, count = active_hashes()
    if active or count:
        raise ValueError("Prospective one-guest create requires provider active-zero")
    # An invocation is consumed before receipt setup and provider create.
    epoch.accounting._write_new(out / "child-started.json", {
        "schema": "cua-native-wdi-post-enter-child-started-v9",
        "task_id": task_id, "attempt": attempt,
        "intent_sha256": digest(epoch.private(intent_path)),
        "source_freeze_sha256": digest(epoch.private(freeze_path)),
        "permit_sha256": digest(epoch.private(permit_path)),
        "same_intent_replay_authorized": False})
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential missing")
    receipt = {
        "schema": "cua-native-wdi-post-enter-control-attempt-v9",
        "status": "started", "stage": "pre_provider", "task_id": task_id,
        "attempt": attempt, "split": row["split"],
        "input_sha256": digest(baseline),
        "package_sha256": row["package_sha256"],
        "evaluator_script_sha256": digest(script.encode()),
        "expected_actor_action_count": len(expected_actions),
        "sandbox_timeout_seconds": LEASE_SECONDS,
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "ratification_sha256": digest(ratification.read_bytes()),
        "source_freeze_sha256": digest(epoch.private(freeze_path)),
        "permit_sha256": digest(epoch.private(permit_path)),
        "candidate_inventory_sha256": digest((candidate_root / "candidate-inventory.json").read_bytes()),
        "profile_reference_private_sha256": reference_sha,
        "profile_scope_guard_source_sha256": digest(Path(scoped_guard.__file__).read_bytes()),
        "profile_application_kind": app_kind,

        "guest_identity_public_sha256": digest(guest_public.read_bytes()),
        "max_actor_actions": epoch.MAX_ACTIONS,
        "max_actor_wall_seconds": epoch.ACTOR_WALL_SECONDS,
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
                                 metadata={"envloop_purpose": "v9-prospective-120-evaluator-controls"})
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
            actor_started = time.monotonic()
            receipt["actor_started_monotonic_ns"] = time.monotonic_ns()
            actor_sandbox = PostEnterControlProxyV9(sandbox, storage_root=attempts_root,
                attempt_dir=out, document_filename=paths[0].name)
            recorder = RecordingDesktop(actor_sandbox)
            previous = None
            step_index = 0
            readback_seen = False
            for operation, value in _operations(script):
                if time.monotonic() - actor_started > epoch.ACTOR_WALL_SECONDS:
                    raise ValueError("Uniform 720-second actor clock exhausted")
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
                    if time.monotonic() - actor_started > epoch.ACTOR_WALL_SECONDS:
                        raise ValueError("Actor clock exhausted before dispatch")
                    actor_sandbox.current_actor_step = step_index
                    step_row["dispatch_type"] = qwen_v066_adapter.dispatch(actor_sandbox, action)
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
            receipt["actor_elapsed_seconds"] = time.monotonic() - actor_started
            if receipt["actor_elapsed_seconds"] > epoch.ACTOR_WALL_SECONDS:
                raise ValueError("Uniform actor clock exhausted")
            receipt["post_enter_windows"] = actor_sandbox.enter_count
            receipt["status"] = "control_passed_before_teardown"
        else:
            cold_frame = bytes(sandbox.screenshot())
            receipt["cold_observation"] = reserve_and_write(
                attempts_root, out / "cold-neutral-open.png", cold_frame)
            restored = bytes(sandbox.files.read(remote, format="bytes"))
            if restored != baseline:
                raise ValueError("Fresh guest did not restore original OOXML bytes")
            receipt["restored_artifact"] = reserve_and_write(
                attempts_root, out / ("restored" + paths[0].suffix), restored)
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


def run_trio(*, freeze_path: Path, permit_path: Path, enable_paid_controls: bool=False):
    if enable_paid_controls is not True:
        raise ValueError("Prospective paid trio entry is disabled")
    value=epoch.validate(freeze_path);row=epoch.next_row(value)
    epoch.require(row is not None,"All 120 new control trios already complete")
    epoch.checked_permit(freeze_path,permit_path,value,row)
    root=Path(value["attempts_root"]);task=root/row["task_id"]
    epoch.require(not task.exists() and not task.is_symlink(),"Consumed or partial new task cannot be replayed")
    task.mkdir(parents=True,mode=0o700)
    os.environ["ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT"]=str(root)
    os.environ["ENVLOOP_DESKTOP_V4_FREEZE"]=str(freeze_path)
    epoch.accounting._write_new(task/"trio-started.json",{
        "schema":"cua-native-wdi-post-enter-trio-started-v9", "task_id":row["task_id"],
        "source_freeze_sha256":digest(epoch.private(freeze_path)),
        "permit_sha256":digest(epoch.private(permit_path)),"same_intent_replay_authorized":False})
    for attempt in ATTEMPTS:
        out=task/attempt;out.mkdir(mode=0o700)
        epoch.accounting._write_new(out/"intent.json",{
            "schema":"cua-native-wdi-post-enter-control-intent-v9", "task_id":row["task_id"],
            "attempt":attempt,"split":row["split"],"package_sha256":row["package_sha256"],
            "lease_seconds":LEASE_SECONDS,"source_freeze_sha256":digest(epoch.private(freeze_path)),
            "permit_sha256":digest(epoch.private(permit_path)),"same_intent_replay_authorized":False})
        os.environ["ENVLOOP_DESKTOP_V4_ATTEMPT_DIR"]=str(out)
        receipt=execute(freeze_path=freeze_path,permit_path=permit_path,task_id=row["task_id"],attempt=attempt,enable_paid_controls=True)
        expected="cold_reset_observed" if attempt=="cold-reset" else "control_passed"
        if receipt["status"]!=expected:
            raise ValueError("New prospective control failed; no subsequent create or replay")
    from .v066_post_enter_control_audit_v9 import audit_trio
    return audit_trio(value=value,row=row)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze",type=Path,required=True);p.add_argument("--permit",type=Path,required=True)
    p.add_argument("--enable-paid-controls",action="store_true");a=p.parse_args()
    result=run_trio(freeze_path=a.freeze,permit_path=a.permit,enable_paid_controls=a.enable_paid_controls)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":main()
