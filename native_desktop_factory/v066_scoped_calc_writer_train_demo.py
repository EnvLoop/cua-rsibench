"""Two distinct v0.6.6 public-train Calc/Writer GUI positive demonstrations.

Both use only current screenshots plus the shared bounded GUI action contract.
Trusted setup stages a pinned public train OOXML input; actor actions never
read package contents or use document APIs. Raw observation/predispatch PNGs,
normalized action JSON, actor-saved readback, and independent verifier output
remain evaluator-private. Each create has a source-bound full-lease intent.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import json
import os
from pathlib import Path
import time

from . import qwen_v066_adapter, runtime_fingerprint_probe
from . import v066_scoped_profile_guard as scoped_guard
from . import v066_train_profile_cross_guest as public_sources
from .budget_ledger import audit as budget_audit
from .gui_control_shell import wait_for_document_ready
from .reconcile_interrupted_sweep import active_hashes
from .v066_final_freeze import digest
from .v066_scoped_profile_reference import validate_reference
from .v066_storage_budget import audit as storage_audit, reserve_and_write
from .verify import verify


KINDS = ("calc", "writer")
LEASE_SECONDS = 600
DIAGNOSTIC_CAP_USD = Decimal("43")
MAX_ACTIONS = 32
RESERVATION_SCHEMA = "cua-native-wdi-v066-calc-writer-train-demo-reservation-v1"


class RecordingDesktop:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.last_screenshot = b""

    def screenshot(self):
        self.last_screenshot = bytes(self.sandbox.screenshot())
        return self.last_screenshot

    def __getattr__(self, name):
        return getattr(self.sandbox, name)


def _source(kind: str) -> tuple[dict, dict, bytes, str, str]:
    if kind not in KINDS:
        raise ValueError("Only public train Calc and Writer demos are allowed")
    package, baseline, filename = public_sources._source(kind)
    directory = (Path(public_sources.__file__).with_name("dev-fixtures") /
                 public_sources.FIXTURES[kind])
    oracle = json.loads((directory / "oracle.json").read_bytes())
    instruction = (directory / "actor_task.txt").read_text()
    if len(oracle.get("targets", {})) != 1:
        raise ValueError("Pinned public train demo target changed")
    return package, oracle, baseline, instruction, filename


def actor_actions(kind: str, oracle: dict) -> list[dict]:
    if kind == "calc":
        formula = next(iter(oracle["targets"].values()))["formula"]
        if not formula.startswith("="):
            raise ValueError("Pinned public train Calc formula changed")
        return [
            {"type": "click", "target": {"x": 258, "y": 767}},
            {"type": "wait", "duration_ms": 1500},
            {"type": "click", "target": {"x": 52, "y": 170}},
            {"type": "key", "key": "Control+A"},
            {"type": "type", "text": "B4", "mode": "insert"},
            {"type": "key", "key": "Enter"},
            {"type": "type", "text": formula.replace("!", "."),
             "mode": "insert"},
            {"type": "key", "key": "Enter"},
            {"type": "key", "key": "Control+S"},
            {"type": "wait", "duration_ms": 2000},
            {"type": "click", "target": {"x": 789, "y": 519}},
            {"type": "wait", "duration_ms": 1000},
        ]
    if kind == "writer":
        replacement = next(iter(oracle["targets"].values()))
        if not replacement.startswith("FINDING 1:"):
            raise ValueError("Pinned public train Writer target changed")
        return [
            {"type": "click", "target": {"x": 416, "y": 681}},
            {"type": "key", "key": "Home"},
            {"type": "key", "key": "Shift+End"},
            {"type": "type", "text": replacement, "mode": "insert"},
            {"type": "key", "key": "Control+S"},
            {"type": "wait", "duration_ms": 2000},
            {"type": "click", "target": {"x": 789, "y": 518}},
            {"type": "wait", "duration_ms": 1000},
        ]
    raise ValueError("Unsupported public train demo")


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def reservation_payload(*, work_root: Path, guest_public: Path,
                        scoped_reference: Path) -> dict:
    reference, reference_sha = validate_reference(scoped_reference)
    if not all(kind in reference["applications"] for kind in KINDS):
        raise ValueError("Calc/Writer public-train references missing")
    budget = budget_audit(
        work_root, proposed_new_sandboxes=2,
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=DIAGNOSTIC_CAP_USD)
    if not budget["within_cap"]:
        raise ValueError("Two public-train demo leases exceed diagnostic cap")
    return {
        "schema": RESERVATION_SCHEMA,
        "status": "reserved_before_two_public_train_gui_creates",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "demo_source_sha256": digest(Path(__file__).read_bytes()),
        "demo_audit_source_sha256": digest(Path(__file__).with_name(
            "v066_scoped_calc_writer_train_demo_audit.py").read_bytes()),
        "profile_guard_source_sha256": digest(
            Path(scoped_guard.__file__).read_bytes()),
        "action_adapter_sha256": digest(
            Path(qwen_v066_adapter.__file__).read_bytes()),
        "public_source_factory_sha256": digest(
            Path(public_sources.__file__).read_bytes()),
        "scoped_reference_sha256": reference_sha,
        "guest_identity_public_sha256": digest(guest_public.read_bytes()),
        "public_train_package_sha256s": {
            kind: _source(kind)[0]["package_sha256"] for kind in KINDS},
        "past_conservative_reserved_usd":
            budget["past_conservative_reserved_usd"],
        "maximum_new_intents": 2,
        "lease_seconds_each": LEASE_SECONDS,
        "planned_two_full_lease_reserved_usd": str(
            Decimal(budget["past_conservative_reserved_usd"]) +
            Decimal(2 * LEASE_SECONDS) / Decimal(3600)),
        "diagnostic_cap_usd": str(DIAGNOSTIC_CAP_USD),
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }


def prepare_reservation(*, path: Path, work_root: Path,
                        guest_public: Path, scoped_reference: Path) -> dict:
    if path.exists() or path.is_symlink():
        raise ValueError("New exclusive Calc/Writer demo reservation required")
    value = reservation_payload(
        work_root=work_root, guest_public=guest_public,
        scoped_reference=scoped_reference)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_new(path, (json.dumps(value, sort_keys=True,
                                 separators=(",", ":")) + "\n").encode())
    return value


def _validate_reservation(*, path: Path, work_root: Path,
                          guest_public: Path, scoped_reference: Path) -> str:
    raw = path.read_bytes()
    value = json.loads(raw)
    expected = reservation_payload(
        work_root=work_root, guest_public=guest_public,
        scoped_reference=scoped_reference)
    # The ledger grows after the first guest, so its before/after cost fields
    # are checked against the original reservation rather than recomputed.
    for key in ("recorded_utc", "past_conservative_reserved_usd",
                "planned_two_full_lease_reserved_usd"):
        expected.pop(key)
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("Calc/Writer source-bound demo reservation changed")
    if (value.get("planned_two_full_lease_reserved_usd") != str(
            Decimal(value["past_conservative_reserved_usd"]) +
            Decimal(2 * LEASE_SECONDS) / Decimal(3600))):
        raise ValueError("Calc/Writer full-lease reservation changed")
    recorded = datetime.fromisoformat(value["recorded_utc"])
    if (recorded.tzinfo is None or
            recorded.astimezone(timezone.utc) > datetime.now(timezone.utc)):
        raise ValueError("Calc/Writer reservation time invalid")
    return digest(raw)


def run_one(*, kind: str, output_root: Path, work_root: Path,
            guest_public: Path, scoped_reference: Path,
            reservation_path: Path) -> dict:
    package, oracle, baseline, instruction, filename = _source(kind)
    output = output_root / kind
    if (output.exists() or output.is_symlink() or
            not output.resolve().is_relative_to(
                (work_root / "gui-diagnostics").resolve())):
        raise ValueError("New private public-train demo output required")
    reservation_sha = _validate_reservation(
        path=reservation_path, work_root=work_root,
        guest_public=guest_public, scoped_reference=scoped_reference)
    prior = {path.parent.name for path in output_root.glob("*/intent.json")}
    if prior != ({"calc"} if kind == "writer" else set()):
        raise ValueError("Calc/Writer demo order or prior intent changed")
    if kind == "writer":
        earlier = json.loads((output_root / "calc/receipt.json").read_bytes())
        if (earlier.get("status") != "train_gui_positive_passed" or
                earlier.get("kill_returned") is not True or
                earlier.get("is_running_after_kill") is not False):
            raise ValueError("Calc train demo did not pass before Writer")
    budget = budget_audit(
        work_root, proposed_new_sandboxes=1,
        proposed_lease_seconds=LEASE_SECONDS,
        max_lane_reserved_usd=DIAGNOSTIC_CAP_USD)
    if not budget["within_cap"] or not os.environ.get("E2B_API_KEY"):
        raise ValueError("Calc/Writer demo diagnostic budget or credential absent")
    active, count = active_hashes()
    if active or count:
        raise ValueError("Provider not active-zero before public train demo")
    guest_raw = guest_public.read_bytes()
    guest = json.loads(guest_raw)
    if (guest.get("schema") !=
            "cua-native-wdi-guest-content-identity-public-v1" or
            guest.get("scoped_guest_content_identity_passed") is not True or
            guest.get("guest_content_probe_script_sha256") !=
            digest(runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())):
        raise ValueError("Public scoped guest identity changed")
    reference, reference_sha = validate_reference(scoped_reference)
    if kind not in reference["applications"]:
        raise ValueError("Public-train application reference missing")
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    if not storage_audit(output_root)["dispatch_storage_ready"]:
        raise ValueError("Raw public-train frame storage blocked")
    intent = {
        "schema": "cua-native-wdi-v066-calc-writer-train-demo-intent-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "kind": kind, "split": "train",
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "demo_source_sha256": digest(Path(__file__).read_bytes()),
        "scoped_reference_sha256": reference_sha,
        "reservation_sha256": reservation_sha,
        "lease_seconds": LEASE_SECONDS,
        "automatic_replay_authorized": False,
        "official_model_results": 0,
    }
    _write_new(output / "intent.json",
               (json.dumps(intent, sort_keys=True) + "\n").encode())
    receipt = {
        "schema": "cua-native-wdi-gui-development-attempt-v1",
        "purpose": "v066_scoped_public_train_calc_writer_gui_positive_no_model",
        "status": "started", "stage": "pre_provider",
        "split": "train", "kind": kind,
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "sandbox_timeout_seconds": LEASE_SECONDS,
        "provider_running_before_create": count,
        "demo_source_sha256": digest(Path(__file__).read_bytes()),
        "action_adapter_sha256": digest(
            Path(qwen_v066_adapter.__file__).read_bytes()),
        "profile_guard_source_sha256": digest(
            Path(scoped_guard.__file__).read_bytes()),
        "scoped_reference_sha256": reference_sha,
        "reservation_sha256": reservation_sha,
        "guest_identity_public_sha256": digest(guest_raw),
        "normalized_actor_actions": [],
        "physical_frame_resamples": [],
        "actor_gui_actions": 0,
        "provider_billed_usd": None,
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
        sandbox = Sandbox.create(
            template="desktop", resolution=(1280, 800),
            timeout=LEASE_SECONDS, allow_internet_access=False,
            metadata={"envloop_purpose": "v066-scoped-public-train-gui-demo"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version}
        if (info.template_id != guest["provider_template_id"] or
                info.envd_version != guest["provider_envd_version"] or
                info.cpu_count != guest["provider_shape"]["vcpu"] or
                info.memory_mb != guest["provider_shape"]["memory_mb"]):
            raise ValueError("Provider Desktop shape/template changed")
        receipt["stage"] = "scoped_guest_content_attestation"
        persist()
        sandbox.files.write("/tmp/native-guest-content-probe-train-demo.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        run = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-train-demo.py",
            timeout=450, request_timeout=480)
        if run.exit_code != 0:
            raise ValueError("Scoped guest-content probe failed")
        observed = json.loads(run.stdout)
        if (observed.get("content_tree_sha256") !=
                guest["static_content_sha256"] or
                observed.get("counts") != guest["static_content_counts"] or
                observed.get("kernel") != guest["kernel_identity"] or
                observed.get("excluded_paths") !=
                guest["static_content_excluded_paths"]):
            raise ValueError("Scoped guest-content identity differs")
        receipt["guest_content_attested"] = True
        if sandbox.commands.run(
                "test ! -e /home/user/.config/libreoffice/4/user").exit_code != 0:
            raise ValueError("Fresh LibreOffice profile already exists")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + filename
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Public train input staging changed")
        receipt["stage"] = "trusted_public_train_open"
        persist()
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(
            sandbox, filename)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        scoped_guard.attest(
            sandbox=sandbox, attempts_root=output_root, out=output,
            app_kind=kind, reference_path=scoped_reference,
            receipt=receipt, persist=persist)
        recorder = RecordingDesktop(sandbox)
        previous = None
        actions = actor_actions(kind, oracle)
        if not 1 <= len(actions) <= MAX_ACTIONS:
            raise ValueError("Public train GUI demonstration action count changed")
        for step, minimal in enumerate(actions):
            receipt["stage"] = "actor_current_frame_gui"
            payload = json.dumps(minimal, separators=(",", ":"))
            for frame_attempt in range(5):
                frame = qwen_v066_adapter.observe(
                    recorder, task_id=package["task_id"],
                    task_binding_sha256=package["package_sha256"],
                    instruction=instruction, step=step,
                    previous_action_result=previous, max_actions=MAX_ACTIONS)
                observed_frame = reserve_and_write(
                    output_root,
                    output / f"frame-{step:02d}-{frame_attempt}.png",
                    frame.screenshot_bytes)
                try:
                    action = qwen_v066_adapter.parse_current_action(
                        payload, frame, recorder)
                    break
                except qwen_v066_adapter.PhysicalFrameDrift:
                    changed = reserve_and_write(
                        output_root,
                        output / f"drift-{step:02d}-{frame_attempt}.png",
                        recorder.last_screenshot)
                    receipt["physical_frame_resamples"].append({
                        "step": step, "frame_attempt": frame_attempt,
                        "observed": observed_frame, "changed": changed})
                    persist()
                    time.sleep(1)
            else:
                raise qwen_v066_adapter.PhysicalFrameDrift()
            predispatch = reserve_and_write(
                output_root,
                output / f"predispatch-{step:02d}-{frame_attempt}.png",
                recorder.last_screenshot)
            row = {
                "step": step,
                "frame_id_sha256": digest(frame.frame_id.encode()),
                "observation": observed_frame,
                "predispatch": predispatch,
                "normalized_action": action,
                "normalized_action_sha256": digest(
                    json.dumps(action, sort_keys=True,
                               separators=(",", ":")).encode()),
                "script_payload_sha256": digest(payload.encode()),
                "status": "validated_pre_dispatch",
            }
            receipt["normalized_actor_actions"].append(row)
            persist()
            row["dispatch_type"] = qwen_v066_adapter.dispatch(
                sandbox, action)
            row["status"] = "applied"
            receipt["actor_gui_actions"] += 1
            persist()
            previous = {"status": "applied", "code": "ok"}
        receipt["stage"] = "saved_artifact_readback"
        persist()
        saved = bytes(sandbox.files.read(remote, format="bytes"))
        suffix = ".xlsx" if kind == "calc" else ".docx"
        receipt["saved_artifact"] = reserve_and_write(
            output_root, output / ("saved" + suffix), saved)
        fair = verify(baseline, saved, oracle)
        receipt["saved_sha256"] = digest(saved)
        receipt["independent_saved_verifier"] = fair
        if saved == baseline or fair.get("passed") is not True:
            raise ValueError("Public train saved OOXML positive did not verify")
        receipt["status"] = "train_gui_positive_passed"
    except Exception as exc:
        receipt["status"] = "train_gui_positive_failed"
        receipt["error_type"] = type(exc).__name__
        receipt["error_message_private"] = str(exc)[:240]
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
        persist()
    return receipt


def run_both(*, output_root: Path, work_root: Path,
             guest_public: Path, scoped_reference: Path,
             reservation_path: Path,
             enable_paid_train_demos: bool = False) -> dict:
    if enable_paid_train_demos is not True:
        raise ValueError("Paid public-train Calc/Writer demos are disabled")
    if output_root.exists() or output_root.is_symlink():
        raise ValueError("New Calc/Writer public-train root required")
    _validate_reservation(
        path=reservation_path, work_root=work_root,
        guest_public=guest_public, scoped_reference=scoped_reference)
    output_root.mkdir(parents=True, mode=0o700)
    output_root.chmod(0o700)
    journal = {
        "schema": "cua-native-wdi-v066-calc-writer-train-demo-run-v1",
        "status": "started",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "demo_source_sha256": digest(Path(__file__).read_bytes()),
        "reservation_sha256": digest(reservation_path.read_bytes()),
        "attempts": [], "automatic_retry_authorized": False,
        "official_final_admissions": 0,
    }

    def persist():
        path = output_root / "run-receipt.json"
        path.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)

    persist()
    for kind in KINDS:
        try:
            result = run_one(
                kind=kind, output_root=output_root,
                work_root=work_root, guest_public=guest_public,
                scoped_reference=scoped_reference,
                reservation_path=reservation_path)
            row = {"kind": kind, "status": result["status"],
                   "receipt_sha256": digest(
                       (output_root / kind / "receipt.json").read_bytes()),
                   "cleanup_verified": result.get(
                       "is_running_after_kill") is False}
        except Exception as exc:
            row = {"kind": kind,
                   "status": "precreate_or_worker_exception",
                   "error_type": type(exc).__name__,
                   "receipt_sha256": None, "cleanup_verified": False}
        journal["attempts"].append(row)
        persist()
        if (row["status"] != "train_gui_positive_passed" or
                not row["cleanup_verified"]):
            journal["status"] = "stopped_for_reconciliation"
            break
    else:
        journal["status"] = "two_public_train_gui_positives_pending_audit"
    journal["finished_utc"] = datetime.now(timezone.utc).isoformat()
    persist()
    return journal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare-reservation", "run"),
                        required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--guest-public", type=Path, required=True)
    parser.add_argument("--scoped-reference", type=Path, required=True)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--enable-paid-train-demos", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare-reservation":
        value = prepare_reservation(
            path=args.reservation, work_root=args.work_root,
            guest_public=args.guest_public,
            scoped_reference=args.scoped_reference)
        print(json.dumps({
            "status": value["status"],
            "reservation_sha256": digest(args.reservation.read_bytes()),
            "maximum_new_intents": 2,
            "planned_two_full_lease_reserved_usd":
                value["planned_two_full_lease_reserved_usd"],
            "official_final_admissions": 0,
        }, sort_keys=True))
    else:
        if args.output_root is None:
            raise ValueError("New Calc/Writer train demo root required")
        result = run_both(
            output_root=args.output_root, work_root=args.work_root,
            guest_public=args.guest_public,
            scoped_reference=args.scoped_reference,
            reservation_path=args.reservation,
            enable_paid_train_demos=args.enable_paid_train_demos)
        print(json.dumps({
            "status": result["status"],
            "attempts_recorded": len(result["attempts"]),
            "passed_public_train_workflows": sum(
                row["status"] == "train_gui_positive_passed"
                for row in result["attempts"]),
            "run_journal_sha256": digest(
                (args.output_root / "run-receipt.json").read_bytes()),
            "official_final_admissions": 0,
        }, sort_keys=True))
        if result["status"] != "two_public_train_gui_positives_pending_audit":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
