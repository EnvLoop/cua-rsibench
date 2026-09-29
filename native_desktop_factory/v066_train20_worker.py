"""Resumable real-GUI collection of original WDI Desktop train demonstrations.

Only the 15 preregistered SFT identities are dispatchable here. Five holdout
identities remain untouched for later paired base/LoRA model trials. This
evaluator-scripted collection makes no model call and yields no benchmark score.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import time

from cursibench.scale_action_contract import ContractError

from . import admit, qwen_v066_adapter, runtime_fingerprint_probe
from . import v066_scoped_profile_guard as profile_guard
from .gui_control_shell import wait_for_document_ready
from .reconcile_interrupted_sweep import active_hashes
from .v066_scoped_profile_reference import workflow_kind
from .v066_storage_budget import audit as storage_audit, reserve_and_write
from .verify import verify
from .v066_train20_plan import (
    LEASE_SECONDS, MAX_INTENTS, actions_for_train, digest, encode,
    validate_plan, _write_new,
)


INTENT_SCHEMA = "cua-native-wdi-v066-train20-gui-intent-v1"
RECEIPT_SCHEMA = "cua-native-wdi-v066-train20-gui-attempt-v1"
MAX_ACTIONS = 32


class RecordingDesktop:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.last_screenshot = b""

    def screenshot(self):
        self.last_screenshot = bytes(self.sandbox.screenshot())
        return self.last_screenshot

    def __getattr__(self, name):
        return getattr(self.sandbox, name)


def ac_power_ready() -> bool:
    result = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                            text=True, check=False, timeout=10)
    return result.returncode == 0 and "Now drawing from 'AC Power'" in result.stdout


def host_power_snapshot() -> dict:
    """Retain a bounded host power observation before a paid train intent."""
    result = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                            text=True, check=False, timeout=10)
    raw = result.stdout.encode()
    source = ("AC Power" if "Now drawing from 'AC Power'" in result.stdout
              else "Battery Power" if "Now drawing from 'Battery Power'"
              in result.stdout else None)
    matches = re.findall(r"\b([0-9]{1,3})%", result.stdout)
    if (result.returncode != 0 or source is None or
            len(matches) != 1 or not 0 <= int(matches[0]) <= 100 or
            len(raw) > 4096):
        raise ValueError("Host power telemetry is unavailable")
    return {"source": source, "battery_percent": int(matches[0]),
            "probe_sha256": digest(raw),
            "captured_utc": datetime.now(timezone.utc).isoformat()}


def _persist_receipt(path: Path, value: dict) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    temp = path.with_name("receipt-next.json")
    with temp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temp.chmod(0o600)
    os.replace(temp, path)


def _preflight(*, root: Path, task_id: str, plan: dict,
               require_ac: bool = True, require_provider: bool = True) -> None:
    if task_id not in plan["sft_task_ids"] or task_id in plan["holdout_task_ids"]:
        raise ValueError("Holdout or nontrain identity is not SFT-dispatchable")
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Private evidence root is not a directory")
    if (root / task_id).exists() or (root / task_id).is_symlink():
        raise ValueError("Existing ID intent cannot be replayed automatically")
    if len(list(root.glob("*/intent.json"))) >= MAX_INTENTS:
        raise ValueError("Twenty full-lease intent envelope exhausted")
    if require_ac and not ac_power_ready():
        raise ValueError("Mac is not on AC power before a paid E2B create")
    if require_provider:
        if not os.environ.get("E2B_API_KEY"):
            raise ValueError("E2B credential is missing")
        active, count = active_hashes()
        if active or count:
            raise ValueError("E2B account is not active-zero before train create")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    if storage_audit(root)["dispatch_storage_ready"] is not True:
        raise ValueError("Raw frame storage or free-space floor blocks dispatch")


def create_intent(*, root: Path, row: dict, plan: dict, plan_sha: str,
                  require_ac: bool = True, require_provider: bool = True,
                  battery_authorized: bool = False) -> Path:
    """Write one exclusive, source-bound intent only after all pre-create gates."""
    task_id = row["task_id"]
    _preflight(root=root, task_id=task_id, plan=plan,
               require_ac=require_ac, require_provider=require_provider)
    if type(battery_authorized) is not bool or (battery_authorized and require_ac):
        raise ValueError("Battery authorization and AC policy conflict")
    power = (host_power_snapshot() if require_provider else
             {"source": "test_unverified", "battery_percent": None,
              "probe_sha256": None, "captured_utc": None})
    if (require_provider and power["source"] == "Battery Power" and
            not battery_authorized):
        raise ValueError("Battery execution lacks explicit authorization")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    out = root / task_id
    out.mkdir(mode=0o700)
    intent = {
        "schema": INTENT_SCHEMA, "status": "recorded_before_provider_create",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "split": "train", "diagnostic_role": "sft_source",
        "task_id": task_id, "package_sha256": row["package_sha256"],
        "input_sha256": row["input_sha256"],
        "action_script_sha256": row["action_script_sha256"],
        "plan_sha256": plan_sha,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "lease_seconds": LEASE_SECONDS, "max_actions": MAX_ACTIONS,
        "planned_full_lease_usd_upper": str(
            Decimal(plan["planning_usd_per_hour_upper"]) *
            Decimal(LEASE_SECONDS) / Decimal(3600)),
        "automatic_replay_authorized": False,
        "battery_authorized": battery_authorized,
        "host_power_before_intent": power,
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0, "official_model_results": 0,
    }
    _write_new(out / "intent.json", encode(intent), 0o600)
    return out


def execute_one(*, candidate_root: Path, evidence_root: Path,
                row: dict, plan: dict, plan_sha: str, guest_public: Path,
                scoped_reference: Path, sandbox_factory=None) -> dict:
    """Run one existing intent; a second call is refused by receipt existence."""
    task_id = row["task_id"]
    out = evidence_root / task_id
    intent_raw = (out / "intent.json").read_bytes()
    intent = json.loads(intent_raw)
    if ((out / "receipt.json").exists() or
            intent.get("schema") != INTENT_SCHEMA or
            intent.get("task_id") != task_id or
            intent.get("plan_sha256") != plan_sha or
            intent.get("package_sha256") != row["package_sha256"] or
            intent.get("runner_sha256") != digest(Path(__file__).read_bytes()) or
            intent.get("lease_seconds") != LEASE_SECONDS or
            intent.get("automatic_replay_authorized") is not False):
        raise ValueError("One-use source-bound train intent changed or consumed")
    power = intent.get("host_power_before_intent")
    if (type(intent.get("battery_authorized")) is not bool or
            type(power) is not dict or
            power.get("source") not in
            ("AC Power", "Battery Power", "test_unverified") or
            (sandbox_factory is None and power.get("source") == "test_unverified") or
            (power.get("source") == "Battery Power" and
             intent["battery_authorized"] is not True)):
        raise ValueError("Train intent lacks authorized power telemetry")
    inventory_row = next((item for item in plan["train_rows"]
                          if item["task_id"] == task_id), None)
    if row != inventory_row or task_id not in plan["sft_task_ids"]:
        raise ValueError("Original train identity differs from frozen SFT plan")
    package_manifest = json.loads((candidate_root / row["relative_package_path"] /
                                   "package.json").read_bytes())
    if (package_manifest.get("task_id") != task_id or
            package_manifest.get("split") != "train" or
            package_manifest.get("package_sha256") != row["package_sha256"] or
            package_manifest.get("oracle_sha256") != row["oracle_sha256"] or
            package_manifest.get("actor_task_sha256") !=
            row["instruction_sha256"] or
            package_manifest.get("workflow") != row["workflow"] or
            package_manifest.get("source_groups") != [row["source_group"]]):
        raise ValueError("Original train source package changed before create")
    package_dir, baseline, oracle = admit._package(candidate_root, package_manifest)
    actions = actions_for_train(package_manifest, oracle)
    if (digest(encode(actions)) != row["action_script_sha256"] or
            digest(baseline) != row["input_sha256"]):
        raise ValueError("Original train action or input changed before create")
    artifacts = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
                 *package_dir.glob("*.docx")]
    if len(artifacts) != 1:
        raise ValueError("Original WDI train task requires one input")
    instruction = (package_dir / "actor_task.txt").read_text()
    guest_raw = guest_public.read_bytes()
    guest = json.loads(guest_raw)
    receipt = {
        "schema": RECEIPT_SCHEMA, "status": "started", "stage": "pre_provider",
        "split": "train", "purpose": "evaluator_scripted_sft_source_no_model",
        "task_id": task_id, "package_sha256": row["package_sha256"],
        "input_sha256": row["input_sha256"],
        "action_script_sha256": row["action_script_sha256"],
        "intent_sha256": digest(intent_raw), "plan_sha256": plan_sha,
        "battery_authorized": intent["battery_authorized"],
        "host_power_before_intent": power,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "adapter_sha256": digest(Path(qwen_v066_adapter.__file__).read_bytes()),
        "profile_guard_sha256": digest(Path(profile_guard.__file__).read_bytes()),
        "guest_identity_public_sha256": digest(guest_raw),
        "scoped_reference_sha256": plan["scoped_reference_sha256"],
        "sdk_version": importlib.metadata.version("e2b-desktop")
            if sandbox_factory is None else "fake-test-only",
        "provider_kind": "e2b_desktop" if sandbox_factory is None else "fake_test_only",
        "sandbox_timeout_seconds": LEASE_SECONDS,
        "expected_actor_action_count": len(actions),
        "actor_steps": [], "physical_frame_resamples": [],
        "official_final_admissions": 0, "official_model_results": 0,
        "actual_provider_billed_usd": None,
    }
    receipt_path = out / "receipt.json"

    def persist() -> None:
        _persist_receipt(receipt_path, receipt)

    persist()
    sandbox = None
    try:
        if sandbox_factory is None:
            from e2b_desktop import Sandbox
            sandbox_factory = Sandbox.create
        receipt["stage"] = "create_desktop"
        persist()
        sandbox = sandbox_factory(
            template="desktop", resolution=(1280, 800),
            timeout=LEASE_SECONDS, allow_internet_access=False,
            metadata={"envloop_purpose": "v066-original-train20-sft-source"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version}
        if (info.template_id != guest["provider_template_id"] or
                info.envd_version != guest["provider_envd_version"] or
                info.cpu_count != guest["provider_shape"]["vcpu"] or
                info.memory_mb != guest["provider_shape"]["memory_mb"]):
            raise ValueError("E2B Desktop template or shape changed")
        receipt["stage"] = "guest_content_attestation"
        persist()
        sandbox.files.write("/tmp/native-guest-content-probe-train20.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        probe = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-train20.py",
            timeout=450, request_timeout=480)
        if probe.exit_code != 0:
            raise ValueError("Scoped guest-content probe failed")
        observed = json.loads(probe.stdout)
        if (observed.get("content_tree_sha256") != guest["static_content_sha256"] or
                observed.get("counts") != guest["static_content_counts"] or
                observed.get("kernel") != guest["kernel_identity"] or
                observed.get("excluded_paths") !=
                guest["static_content_excluded_paths"]):
            raise ValueError("Scoped guest-content identity changed")
        receipt["guest_content_attested"] = True
        if sandbox.commands.run(
                "test ! -e /home/user/.config/libreoffice/4/user").exit_code != 0:
            raise ValueError("Fresh LibreOffice profile already exists")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + artifacts[0].name
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Trusted original train input staging changed")
        receipt["stage"] = "trusted_open_and_scoped_profile"
        persist()
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(
            sandbox, artifacts[0].name)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        profile_guard.attest(
            sandbox=sandbox, attempts_root=evidence_root, out=out,
            app_kind=workflow_kind(row["workflow"]),
            reference_path=scoped_reference, receipt=receipt, persist=persist)
        recorder = RecordingDesktop(sandbox)
        previous = None
        for step, minimal in enumerate(actions):
            receipt["stage"] = "actor_current_frame_gui"
            payload = json.dumps(minimal, separators=(",", ":"))
            for frame_attempt in range(5):
                frame = qwen_v066_adapter.observe(
                    recorder, task_id=task_id,
                    task_binding_sha256=row["package_sha256"],
                    instruction=instruction, step=step,
                    previous_action_result=previous, max_actions=MAX_ACTIONS)
                frame_ref = reserve_and_write(
                    evidence_root, out / f"frame-{step:02d}-{frame_attempt}.png",
                    frame.screenshot_bytes)
                try:
                    action = qwen_v066_adapter.parse_current_action(
                        payload, frame, recorder)
                    break
                except qwen_v066_adapter.PhysicalFrameDrift:
                    drift_ref = reserve_and_write(
                        evidence_root,
                        out / f"drift-{step:02d}-{frame_attempt}.png",
                        recorder.last_screenshot)
                    receipt["physical_frame_resamples"].append({
                        "step": step, "frame_attempt": frame_attempt,
                        "observed": frame_ref, "changed": drift_ref})
                    persist()
                    time.sleep(1)
            else:
                raise qwen_v066_adapter.PhysicalFrameDrift()
            pred_ref = reserve_and_write(
                evidence_root,
                out / f"predispatch-{step:02d}-{frame_attempt}.png",
                recorder.last_screenshot)
            record = {
                "step": step, "frame_attempt": frame_attempt,
                "frame_id_sha256": digest(frame.frame_id.encode()),
                "observation": frame_ref, "predispatch": pred_ref,
                "normalized_action": action,
                "normalized_action_sha256": digest(encode(action)),
                "action_payload_sha256": digest(payload.encode()),
                "status": "validated_pre_dispatch",
            }
            receipt["actor_steps"].append(record)
            persist()
            record["dispatch_type"] = qwen_v066_adapter.dispatch(sandbox, action)
            record["status"] = "applied"
            persist()
            previous = {"status": "applied", "code": "ok"}
        receipt["stage"] = "saved_artifact_readback"
        persist()
        saved = bytes(sandbox.files.read(remote, format="bytes"))
        suffix = artifacts[0].suffix
        receipt["saved_artifact"] = reserve_and_write(
            evidence_root, out / ("saved" + suffix), saved)
        receipt["saved_sha256"] = digest(saved)
        receipt["independent_saved_verifier"] = verify(baseline, saved, oracle)
        if (saved == baseline or
                receipt["independent_saved_verifier"].get("passed") is not True):
            raise ValueError("Original train saved OOXML positive did not verify")
        receipt["status"] = "train_gui_positive_passed_before_teardown"
    except Exception as exc:
        receipt["status"] = "train_gui_failed_or_infrastructure_invalid"
        receipt["error_type"] = type(exc).__name__
        if isinstance(exc, ContractError):
            receipt["contract_error_code"] = exc.code
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(
                    sandbox.is_running(request_timeout=12))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if receipt.get("is_running_after_kill") is not False:
            receipt["status"] = "cleanup_unverified"
        elif receipt["status"] == "train_gui_positive_passed_before_teardown":
            receipt["status"] = "train_gui_positive_passed"
        persist()
    return receipt


def collect(*, repo_root: Path, candidate_root: Path, evidence_root: Path,
            plan_path: Path, guest_public: Path, scoped_reference: Path,
            ratification: Path, max_new: int,
            enable_paid_train20: bool = False,
            battery_authorized: bool = False) -> dict:
    if enable_paid_train20 is not True or not 1 <= max_new <= 15:
        raise ValueError("Explicit paid train20 enablement and 1–15 cap required")
    plan, plan_sha = validate_plan(
        private_path=plan_path, repo_root=repo_root,
        candidate_root=candidate_root, guest_public=guest_public,
        scoped_reference=scoped_reference, ratification=ratification)
    from .v066_train20_audit import audit_one
    result = {"schema": "cua-native-wdi-v066-train20-collector-summary-v1",
              "status": "started", "plan_sha256": plan_sha,
              "existing_accepted": 0, "new_accepted": 0,
              "stopped_task_id_sha256": None,
              "official_final_admissions": 0, "official_model_results": 0}
    by_id = {row["task_id"]: row for row in plan["train_rows"]}
    used_sandbox_ids: set[str] = set()
    for task_id in plan["sft_task_ids"]:
        row = by_id[task_id]
        out = evidence_root / task_id
        if out.exists() or out.is_symlink():
            accepted = audit_one(candidate_root=candidate_root,
                                 evidence_root=evidence_root,
                                 plan=plan, plan_sha=plan_sha, row=row,
                                 scoped_reference=scoped_reference,
                                 require_real_provider=True)
            if accepted["sandbox_id_sha256"] in used_sandbox_ids:
                raise ValueError("Two train IDs reused an E2B guest")
            used_sandbox_ids.add(accepted["sandbox_id_sha256"])
            result["existing_accepted"] += 1
            continue
        if result["new_accepted"] >= max_new:
            result["status"] = "bounded_pause_after_accepted_ids"
            break
        create_intent(root=evidence_root, row=row, plan=plan,
                      plan_sha=plan_sha, require_ac=not battery_authorized,
                      battery_authorized=battery_authorized)
        receipt = execute_one(
            candidate_root=candidate_root, evidence_root=evidence_root,
            row=row, plan=plan, plan_sha=plan_sha,
            guest_public=guest_public,
            scoped_reference=scoped_reference)
        if receipt["status"] != "train_gui_positive_passed":
            result["status"] = "stopped_after_failed_or_uncertain_id"
            result["stopped_task_id_sha256"] = digest(task_id.encode())
            break
        try:
            accepted = audit_one(candidate_root=candidate_root,
                                 evidence_root=evidence_root,
                                 plan=plan, plan_sha=plan_sha, row=row,
                                 scoped_reference=scoped_reference,
                                 require_real_provider=True)
            if accepted["sandbox_id_sha256"] in used_sandbox_ids:
                raise ValueError("Two train IDs reused an E2B guest")
            used_sandbox_ids.add(accepted["sandbox_id_sha256"])
        except (OSError, ValueError, TypeError, KeyError):
            result["status"] = "stopped_after_independent_audit_failure"
            result["stopped_task_id_sha256"] = digest(task_id.encode())
            break
        result["new_accepted"] += 1
    else:
        result["status"] = "all_15_sft_sources_independently_audited"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--guest-public", type=Path, required=True)
    parser.add_argument("--scoped-reference", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--max-new", type=int, default=1)
    parser.add_argument("--enable-paid-train20", action="store_true")
    parser.add_argument("--battery-authorized", action="store_true")
    args = parser.parse_args()
    result = collect(
        repo_root=args.repo_root, candidate_root=args.candidate_root,
        evidence_root=args.evidence_root, plan_path=args.plan,
        guest_public=args.guest_public,
        scoped_reference=args.scoped_reference,
        ratification=args.ratification, max_new=args.max_new,
        enable_paid_train20=args.enable_paid_train20,
        battery_authorized=args.battery_authorized)
    print(json.dumps(result, sort_keys=True))
    if result["status"].startswith("stopped_after"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
