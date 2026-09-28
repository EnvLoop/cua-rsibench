"""Scoped-profile public-train Impress positive, near-miss, or reset control.

This calls no model and refuses hidden final packages. Every actor action is
bound to a fresh screenshot and a predispatch screenshot; profile and GUI raw
bytes are reserved in private SQLite before writing. Saved PPTX is scored by
an independent verifier. Each polarity uses a fresh guest and full lease.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

from cursibench import scale_action_contract_v066, scale_action_output_v066
from cursibench.scale_action_contract import ContractError

from . import qwen_v066_adapter, runtime_fingerprint_probe
from . import v066_scoped_profile_guard as scoped_guard
from .budget_ledger import audit as budget_audit
from .factory import json_bytes
from .gui_control_shell import wait_for_document_ready
from .reconcile_interrupted_sweep import active_hashes
from .verify import verify
from .v066_storage_budget import audit as storage_audit, reserve_and_write
from .v066_scoped_profile_reference import validate_reference


PUBLIC_TRAIN_PACKAGE = (
    Path(__file__).with_name("dev-fixtures") /
    "wdi-native-mex-impress-deck-normalized"
)
MAX_ACTIONS = 20


def digest(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


class RecordingDesktop:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.last_screenshot = b""

    def screenshot(self):
        self.last_screenshot = bytes(self.sandbox.screenshot())
        return self.last_screenshot

    def __getattr__(self, name):
        return getattr(self.sandbox, name)


def _train_package() -> tuple[dict, dict, bytes, str, str]:
    package_dir = PUBLIC_TRAIN_PACKAGE.resolve()
    package = json.loads((package_dir / "package.json").read_bytes())
    oracle_raw = (package_dir / "oracle.json").read_bytes()
    oracle = json.loads(oracle_raw)
    actor_raw = (package_dir / "actor_task.txt").read_bytes()
    files = list(package_dir.glob("*.pptx"))
    if (len(files) != 1 or package.get("split") != "train"
            or oracle.get("split") != "train"
            or package["task_id"] != oracle["task_id"]
            or package.get("workflow") != "impress-deck"
            or package.get("package_sha256") != digest(json_bytes({
                key: value for key, value in package.items()
                if key != "package_sha256"}))
            or package["oracle_sha256"] != digest(oracle_raw)
            or package["actor_task_sha256"] != digest(actor_raw)):
        raise ValueError("Only the pinned public Impress training fixture is allowed")
    baseline = files[0].read_bytes()
    if package["input_sha256"] != digest(baseline):
        raise ValueError("Training input bytes changed")
    targets = oracle.get("targets", {})
    if len(targets) != 1 or list(targets) != ["SIGNAL_1_REVIEW_1"]:
        raise ValueError("The pinned train-only target changed")
    return package, oracle, baseline, actor_raw.decode(), files[0].name


def _script(replacement: str) -> list[dict]:
    # Coordinates are from the public development fixture's prior actual GUI
    # positive. This is a train-only adapter smoke, not a hidden evaluator.
    return [
        {"type": "click", "target": {"x": 105, "y": 420}},
        {"type": "wait", "duration_ms": 2000},
        {"type": "double_click", "target": {"x": 353, "y": 390}},
        {"type": "key", "key": "Control+A"},
        {"type": "type", "text": replacement, "mode": "insert"},
        {"type": "click", "target": {"x": 790, "y": 589}},
        {"type": "key", "key": "Control+S"},
        {"type": "wait", "duration_ms": 2000},
        {"type": "click", "target": {"x": 790, "y": 519}},
        {"type": "wait", "duration_ms": 2000},
        # Probe the four newly allowlisted chords after the save. Escape closes
        # transient find UI; navigation/selection does not edit the artifact.
        {"type": "key", "key": "Control+F"},
        {"type": "wait", "duration_ms": 1000},
        {"type": "key", "key": "Escape"},
        {"type": "key", "key": "Control+H"},
        {"type": "wait", "duration_ms": 2000},
        {"type": "key", "key": "Escape"},
        {"type": "key", "key": "Control+End"},
        {"type": "key", "key": "Shift+End"},
    ]


def execute(*, output: Path, work_root: Path, guest_identity_public: Path,
            scoped_reference: Path, diagnostic_reservation: Path,
            attempt: str, lease_seconds: int,
            max_lane_reserved_usd: Decimal) -> dict:
    package, oracle, baseline, instruction, filename = _train_package()
    if attempt not in ("positive", "near-miss", "cold-reset"):
        raise ValueError("Only train positive, near-miss, and reset are allowed")
    if output.exists() or not output.resolve().is_relative_to(
            (work_root / "gui-diagnostics").resolve()):
        raise ValueError("Private output must be new and ledger-visible")
    if not 300 <= lease_seconds <= 600:
        raise ValueError("Smoke server lease must be 300–600 seconds")
    reference, reference_sha = validate_reference(scoped_reference)
    if "impress" not in reference["applications"]:
        raise ValueError("Public-train Impress scoped reference missing")
    identity_raw = guest_identity_public.read_bytes()
    identity = json.loads(identity_raw)
    if (identity.get("schema") != "cua-native-wdi-guest-content-identity-public-v1"
            or identity.get("scoped_guest_content_identity_passed") is not True
            or identity.get("guest_content_probe_script_sha256") !=
                digest(runtime_fingerprint_probe.GUEST_CONTENT_PROBE)):
        raise ValueError("The scoped guest-content probe is not bound")
    budget = budget_audit(work_root, proposed_new_sandboxes=1,
                          proposed_lease_seconds=lease_seconds,
                          max_lane_reserved_usd=max_lane_reserved_usd)
    if not budget["within_cap"]:
        raise ValueError("The existing conservative Desktop lane is exhausted")
    reserved_raw = diagnostic_reservation.read_bytes()
    reserved = json.loads(reserved_raw)
    if (reserved.get("schema") !=
            "cua-native-wdi-v066-scoped-profile-train-controls-reservation-v1" or
            reserved.get("status") !=
            "reserved_before_public_train_gui_control_creates" or
            reserved.get("train_control_source_sha256") !=
            digest(Path(__file__).read_bytes()) or
            reserved.get("scoped_reference_sha256") != reference_sha or
            reserved.get("public_train_package_sha256") !=
            package["package_sha256"] or
            reserved.get("guest_identity_public_sha256") !=
            digest(identity_raw) or
            reserved.get("lease_seconds_each") != lease_seconds or
            reserved.get("maximum_new_attempts") != 3 or
            reserved.get("diagnostic_cap_usd") !=
            str(max_lane_reserved_usd) or
            reserved.get("planned_three_full_lease_reserved_usd") !=
            str(Decimal(reserved.get("past_conservative_reserved_usd", "-1")) +
                Decimal(3 * lease_seconds) / Decimal(3600)) or
            Decimal(budget["combined_reserved_usd"]) >
            Decimal(reserved["planned_three_full_lease_reserved_usd"]) or
            reserved.get("official_final_admissions") != 0):
        raise ValueError("Source-bound public-train GUI control reserve absent")
    required_prior = {
        "positive": set(),
        "near-miss": {"positive"},
        "cold-reset": {"positive", "near-miss"},
    }[attempt]
    existing = {path.parent.name for path in
                output.parent.glob("*/intent.json")}
    if existing != required_prior:
        raise ValueError("Train GUI polarity order or prior intent changed")
    for name in required_prior:
        prior = json.loads((output.parent / name / "receipt.json").read_bytes())
        if (prior.get("status") != "train_scoped_control_passed" or
                prior.get("kill_returned") is not True or
                prior.get("is_running_after_kill") is not False):
            raise ValueError("Earlier public-train GUI control not accepted")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential missing")
    _active, count = active_hashes()
    if _active or count:
        raise ValueError("Account has running E2B sandboxes; reconcile before smoke")

    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    if not storage_audit(output.parent)["dispatch_storage_ready"]:
        raise ValueError("Private train raw-frame storage is not ready")
    intent = {
        "schema": "cua-native-wdi-v066-scoped-profile-train-control-intent-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "attempt": attempt, "split": "train",
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "profile_reference_sha256": reference_sha,
        "diagnostic_reservation_sha256": digest(reserved_raw),
        "lease_seconds": lease_seconds,
        "automatic_replay_authorized": False,
        "official_model_results": 0,
    }
    with (output / "intent.json").open("x") as stream:
        stream.write(json.dumps(intent, sort_keys=True) + "\n")
    (output / "intent.json").chmod(0o600)
    receipt = {
        "schema": "cua-native-wdi-gui-development-attempt-v1",
        "purpose": "v066_scoped_profile_public_train_gui_control_no_model",
        "status": "started", "stage": "pre_provider",
        "split": "train", "task_id": package["task_id"],
        "attempt": attempt,
        "input_sha256": digest(baseline),
        "package_sha256": package["package_sha256"],
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "sandbox_timeout_seconds": lease_seconds,
        "provider_running_before_create": count,
        "lane_conservative_full_lease_usd_before": budget["past_conservative_reserved_usd"],
        "lane_conservative_full_lease_usd_after_reserve": budget["combined_reserved_usd"],
        "provider_billed_usd": None,
        "expected_guest_identity_public_sha256": digest(identity_raw),
        "v066_full_action_validator_sha256": digest(Path(
            scale_action_contract_v066.__file__).read_bytes()),
        "v066_model_output_adapter_sha256": digest(Path(
            scale_action_output_v066.__file__).read_bytes()),
        "v066_native_adapter_sha256": digest(Path(qwen_v066_adapter.__file__).read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "profile_scope_guard_source_sha256": digest(Path(scoped_guard.__file__).read_bytes()),
        "profile_reference_private_sha256": reference_sha,
        "diagnostic_reservation_sha256": digest(reserved_raw),
        "steps": [], "action_errors": [], "physical_frame_resamples": [],
        "official_final_model_attempts": 0,
        "official_final_admissions": 0,
    }

    def persist() -> None:
        path = output / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)

    persist()
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        receipt["stage"] = "create_desktop"
        persist()
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=lease_seconds, allow_internet_access=False,
                                 metadata={"envloop_purpose": "v066-public-train-primitive-smoke"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id)
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version,
        }
        if (info.template_id != identity["provider_template_id"]
                or info.envd_version != identity["provider_envd_version"]
                or info.cpu_count != identity["provider_shape"]["vcpu"]
                or info.memory_mb != identity["provider_shape"]["memory_mb"]):
            raise ValueError("Provider Desktop template/shape changed")
        receipt["stage"] = "guest_content_attestation"
        persist()
        sandbox.files.write("/tmp/native-guest-content-probe-v066.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        guest_run = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-v066.py",
            timeout=450, request_timeout=480)
        if guest_run.exit_code != 0:
            raise ValueError("Fresh guest-content probe failed")
        guest = json.loads(guest_run.stdout)
        if (guest.get("content_tree_sha256") != identity["static_content_sha256"]
                or guest.get("counts") != identity["static_content_counts"]
                or guest.get("kernel") != identity["kernel_identity"]
                or guest.get("excluded_paths") != identity["static_content_excluded_paths"]):
            raise ValueError("The scoped E2B guest content drifted")
        receipt["guest_content_attested"] = True
        receipt["guest_content_sha256"] = guest["content_tree_sha256"]
        run = sandbox.commands.run("test ! -e /home/user/.config/libreoffice/4/user")
        if run.exit_code != 0:
            raise ValueError("Fresh LibreOffice profile was already present")
        receipt["fresh_libreoffice_profile_absent"] = True
        remote = "/home/user/" + filename
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Staged training input differs from its package")
        receipt["stage"] = "open_public_training_document"
        persist()
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox, filename)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        scoped_guard.attest(
            sandbox=sandbox, attempts_root=output.parent, out=output,
            app_kind="impress", reference_path=scoped_reference,
            receipt=receipt, persist=persist)
        if attempt == "cold-reset":
            raw = bytes(sandbox.screenshot())
            receipt["cold_observation"] = reserve_and_write(
                output.parent, output / "cold-observation.png", raw)
            latest = bytes(sandbox.files.read(remote, format="bytes"))
            receipt["restored_state_sha256"] = digest(latest)
            if latest != baseline:
                raise ValueError("Fresh train reset did not restore input bytes")
            receipt["status"] = "cold_reset_observed"
        else:
            replacement = next(iter(oracle["targets"].values()))
            if attempt == "near-miss":
                replacement = "INTENTIONALLY_WRONG_TRAIN_SIGNAL"
            recorder = RecordingDesktop(sandbox)
            previous = None
            for step, minimal in enumerate(_script(replacement)):
                receipt["stage"] = "actor_current_frame_gui"
                minimal_raw = json.dumps(minimal, separators=(",", ":"))
                for frame_attempt in range(5):
                    frame = qwen_v066_adapter.observe(
                        recorder, task_id=package["task_id"],
                        task_binding_sha256=package["package_sha256"],
                        instruction=instruction, step=step,
                        previous_action_result=previous, max_actions=MAX_ACTIONS)
                    observed = reserve_and_write(
                        output.parent,
                        output / f"frame-{step:02d}-{frame_attempt}.png",
                        frame.screenshot_bytes)
                    try:
                        action = qwen_v066_adapter.parse_current_action(
                            minimal_raw, frame, recorder)
                        break
                    except qwen_v066_adapter.PhysicalFrameDrift:
                        changed = reserve_and_write(
                            output.parent,
                            output / f"drift-{step:02d}-{frame_attempt}.png",
                            recorder.last_screenshot)
                        receipt["physical_frame_resamples"].append({
                            "step": step, "frame_attempt": frame_attempt,
                            "observed": observed, "changed": changed,
                        })
                        persist()
                        time.sleep(1)
                else:
                    raise qwen_v066_adapter.PhysicalFrameDrift()
                predispatch = reserve_and_write(
                    output.parent,
                    output / f"predispatch-{step:02d}-{frame_attempt}.png",
                    recorder.last_screenshot)
                step_row = {
                    "step": step,
                    "observation_frame_id_sha256": digest(frame.frame_id),
                    "observation": observed,
                    "predispatch": predispatch,
                    "action_type": action["type"],
                    "action_payload_sha256": digest(minimal_raw),
                    "status": "validated_pre_dispatch",
                }
                receipt["steps"].append(step_row)
                persist()
                step_row["dispatch_type"] = qwen_v066_adapter.dispatch(
                    sandbox, action)
                step_row["status"] = "applied"
                persist()
                previous = {"status": "applied", "code": "ok"}
            receipt["stage"] = "saved_artifact_readback"
            persist()
            saved = bytes(sandbox.files.read(remote, format="bytes"))
            receipt["saved_artifact"] = reserve_and_write(
                output.parent, output / "saved.pptx", saved)
            result = verify(baseline, saved, oracle)
            receipt["saved_sha256"] = digest(saved)
            receipt["train_saved_artifact_verifier"] = result
            expected = attempt == "positive"
            if (saved == baseline or result.get("passed") is not expected or
                    (not expected and (not result.get("errors") or
                        any(not error.startswith("target_") for error in
                            result["errors"])))):
                raise ValueError("Independent train saved-artifact verdict disagrees")
            receipt["status"] = "train_scoped_control_passed"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        if isinstance(exc, ContractError):
            receipt["action_errors"].append(exc.code)
        receipt["status"] = "train_scoped_control_failed"
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if receipt.get("is_running_after_kill") is not False:
            receipt["status"] = "cleanup_unverified"
        persist()
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--guest-identity-public", type=Path, required=True)
    parser.add_argument("--scoped-reference", type=Path, required=True)
    parser.add_argument("--diagnostic-reservation", type=Path, required=True)
    parser.add_argument("--attempt", choices=("positive", "near-miss",
                                               "cold-reset"), required=True)
    parser.add_argument("--lease-seconds", type=int, default=600)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal,
                        default=Decimal("42"))
    args = parser.parse_args()
    result = execute(output=args.out, work_root=args.work_root,
                     guest_identity_public=args.guest_identity_public,
                     scoped_reference=args.scoped_reference,
                     diagnostic_reservation=args.diagnostic_reservation,
                     attempt=args.attempt,
                     lease_seconds=args.lease_seconds,
                     max_lane_reserved_usd=args.max_lane_reserved_usd)
    print(json.dumps({
        "status": result["status"], "stage": result["stage"],
        "error_type": result.get("error_type"),
        "guest_content_attested": result.get("guest_content_attested", False),
        "applied_actions": sum(row["status"] == "applied" for row in result["steps"]),
        "saved_train_verifier_passed": result.get(
            "train_saved_artifact_verifier", {}).get("passed", False),
        "is_running_after_kill": result.get("is_running_after_kill"),
        "receipt_sha256": digest((args.out / "receipt.json").read_bytes()),
    }, sort_keys=True))
    expected = ("cold_reset_observed" if args.attempt == "cold-reset"
                else "train_scoped_control_passed")
    if result["status"] != expected:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
