"""One evaluator-private profile-only probe for a halted final control ID.

This is a diagnostic of the environment, not a control replay, actor edit,
saved-artifact evaluation, or model attempt. Exactly one of the two already
failed amended final IDs is allowed. A new intent and full 600-second lease
are reserved before one E2B create; raw manifest and registry bytes are
written before canonicalization and remain private even on an exception.
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

from . import (admit, profile_canonical, qwen_v066_adapter,
               runtime_fingerprint_probe)
from .budget_ledger import audit as budget_audit
from .gui_control_shell import wait_for_document_ready
from .reconcile_interrupted_sweep import active_hashes
from .v066_final_freeze import digest, validate_lane


SNAPSHOTS = (("first", 0), ("second", 1),
             ("settled_early", 3), ("settled_late", 4))


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _failed_pair(failed_root: Path, target_task_id: str) -> tuple[dict, bytes]:
    paths = sorted(failed_root.glob("*/*/receipt.json"))
    if len(paths) != 2 or len({p.parent.parent.name for p in paths}) != 2:
        raise ValueError("Expected exactly two preserved failed final control IDs")
    selected = None
    sandbox_ids = set()
    for path in paths:
        raw = path.read_bytes()
        receipt = json.loads(raw)
        intent = json.loads(path.with_name("intent.json").read_bytes())
        if (path.parent.name != "positive" or
                receipt.get("status") !=
                "control_failed_or_infrastructure_invalid" or
                receipt.get("stage") != "guest_content_attestation" or
                receipt.get("error_type") != "ValueError" or
                receipt.get("guest_content_attested") is not True or
                receipt.get("fresh_profile_absent") is not True or
                receipt.get("task_profile_attested") is not None or
                receipt.get("actor_steps") != [] or
                receipt.get("kill_returned") is not True or
                receipt.get("is_running_after_kill") is not False or
                intent.get("task_id") != path.parent.parent.name or
                intent.get("attempt") != "positive" or
                intent.get("package_sha256") !=
                receipt.get("package_sha256") or
                receipt.get("task_id") != path.parent.parent.name or
                not receipt.get("sandbox_id_sha256") or
                receipt["sandbox_id_sha256"] in sandbox_ids):
            raise ValueError("Preserved profile-gate failures changed")
        sandbox_ids.add(receipt["sandbox_id_sha256"])
        if receipt.get("task_id") == target_task_id:
            selected = receipt, raw
    if selected is None:
        raise ValueError("Only one of two failed final IDs may be diagnosed")
    return selected


def _snapshot(sandbox, output: Path, label: str,
              started: float) -> dict:
    command = sandbox.commands.run(
        "python3 /tmp/native-profile-file-probe-failed-final.py")
    if command.exit_code != 0:
        raise ValueError("Failed-final profile-file probe command failed")
    raw_manifest = command.stdout.encode()
    if not raw_manifest or len(raw_manifest) > 4_000_000:
        raise ValueError("Failed-final raw profile manifest is unbounded")
    _write_new(output / f"profile-{label}.manifest.json", raw_manifest)
    registry = bytes(sandbox.files.read(
        "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
        format="bytes"))
    if not registry or len(registry) > 4_000_000:
        raise ValueError("Failed-final raw registry is unbounded")
    _write_new(output / f"profile-{label}.registry.xml", registry)
    record = {"label": label,
              "captured_utc": datetime.now(timezone.utc).isoformat(),
              "elapsed_seconds_after_open": round(time.monotonic() - started, 3),
              "manifest_sha256": digest(raw_manifest),
              "registry_sha256": digest(registry),
              "manifest_bytes": len(raw_manifest),
              "registry_bytes": len(registry)}
    try:
        rows = json.loads(raw_manifest)
        if type(rows) is not list or len(rows) > 500:
            raise ValueError("Failed-final profile file count unbounded")
        record["file_count"] = len(rows)
        record["canonical_profile_sha256"] = (
            profile_canonical.canonical_profile_tree(rows, registry))
    except (ValueError, TypeError, KeyError) as exc:
        record["canonical_error_type"] = type(exc).__name__
        record["canonical_error_message_private"] = str(exc)[:200]
        record["canonical_profile_sha256"] = None
    return record


def execute(*, output: Path, work_root: Path,
            candidate_root: Path, failed_root: Path,
            historical_root: Path, target_task_id: str,
            profile_private: Path,
            guest_public: Path, fair_public: Path,
            ratification: Path, final_lane_reservation: Path,
            diagnostic_reservation: Path,
            lease_seconds: int = 600,
            max_diagnostic_usd: Decimal = Decimal("41")) -> dict:
    if (output.exists() or output.is_symlink() or
            not output.resolve().is_relative_to(
                (work_root / "gui-diagnostics").resolve()) or
            lease_seconds != 600):
        raise ValueError("One new private 600-second diagnostic root required")
    failed, failed_raw = _failed_pair(failed_root, target_task_id)
    historical_path = historical_root / target_task_id / "positive/receipt.json"
    historical_raw = historical_path.read_bytes()
    historical = json.loads(historical_raw)
    if (historical.get("status") != "control_passed" or
            historical.get("task_profile_attested") is not True or
            historical.get("package_sha256") != failed["package_sha256"]):
        raise ValueError("Same task lacked an earlier profile-attested control")
    lane = validate_lane(
        ratification=ratification, reservation=final_lane_reservation,
        candidate_root=candidate_root, guest_public=guest_public,
        profile_private=profile_private, fair_public=fair_public)
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    rows = [row for row in inventory["tasks"]
            if row.get("split") == "final_candidate" and
            row.get("task_id") == target_task_id]
    if len(rows) != 1 or rows[0]["package_sha256"] != failed["package_sha256"]:
        raise ValueError("Failed final task package changed")
    row = rows[0]
    package_dir, baseline, _oracle = admit._package(candidate_root, row)
    inputs = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
              *package_dir.glob("*.docx")]
    if len(inputs) != 1:
        raise ValueError("Failed final input is not unique")
    profile_raw = profile_private.read_bytes()
    profiles = [item for item in json.loads(profile_raw)["accepted"]
                if item.get("private_task_id") == target_task_id and
                item.get("package_sha256") == row["package_sha256"]]
    if len(profiles) != 1:
        raise ValueError("Failed task profile baseline missing")
    expected_profile_sha = profiles[0]["canonical_profile_sha256"]
    if historical.get("task_profile_canonical_sha256") != expected_profile_sha:
        raise ValueError("Earlier passed control used another profile baseline")
    guest_raw = guest_public.read_bytes()
    guest = json.loads(guest_raw)
    if (guest.get("schema") !=
            "cua-native-wdi-guest-content-identity-public-v1" or
            guest.get("scoped_guest_content_identity_passed") is not True or
            guest.get("guest_content_probe_script_sha256") !=
            digest(runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())):
        raise ValueError("Scoped guest identity changed")
    budget = budget_audit(
        work_root, proposed_new_sandboxes=1,
        proposed_lease_seconds=lease_seconds,
        max_lane_reserved_usd=max_diagnostic_usd)
    source_sha = digest(Path(__file__).read_bytes())
    canonicalizer_sha = digest(Path(profile_canonical.__file__).read_bytes())
    runner_sha = digest(Path(__file__).with_name(
        "v066_final_control_attempt.py").read_bytes())
    adapter_sha = digest(Path(qwen_v066_adapter.__file__).read_bytes())
    rat_raw = ratification.read_bytes()
    final_res_raw = final_lane_reservation.read_bytes()
    if (failed.get("native_adapter_sha256") != adapter_sha or
            failed.get("runner_sha256") != runner_sha or
            failed.get("ratification_sha256") != digest(rat_raw) or
            failed.get("lane_reservation_sha256") != digest(final_res_raw)):
        raise ValueError("Failed control did not use the frozen source")
    reservation_raw = diagnostic_reservation.read_bytes()
    reservation = json.loads(reservation_raw)
    bindings = {
        "schema": "cua-native-wdi-v066-failed-final-profile-diagnostic-reservation-v1",
        "status": "reserved_before_one_profile_only_final_guest",
        "probe_source_sha256": source_sha,
        "frozen_final_runner_sha256": runner_sha,
        "profile_canonicalizer_sha256": canonicalizer_sha,
        "adapter_sha256": adapter_sha,
        "candidate_inventory_sha256": digest(inventory_raw),
        "task_id": target_task_id,
        "package_sha256": row["package_sha256"],
        "input_sha256": digest(baseline),
        "failed_amended_receipt_sha256": digest(failed_raw),
        "earlier_passed_receipt_sha256": digest(historical_raw),
        "expected_baseline_profile_sha256": expected_profile_sha,
        "profile_manifest_sha256": digest(profile_raw),
        "guest_identity_public_sha256": digest(guest_raw),
        "new_six_cell_ratification_sha256": digest(rat_raw),
        "halted_final_lane_reservation_sha256": digest(final_res_raw),
        "past_conservative_reserved_usd":
            budget["past_conservative_reserved_usd"],
        "new_lease_seconds_reserved": lease_seconds,
        "new_sandbox_intents_reserved": 1,
        "combined_conservative_reserved_usd":
            budget["combined_reserved_usd"],
        "diagnostic_cap_usd": str(max_diagnostic_usd),
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    if (not budget["within_cap"] or
            any(reservation.get(key) != value for key, value in
                bindings.items()) or
            lane["ratification_sha256"] != digest(rat_raw)):
        raise ValueError("Source-bound one-guest final profile reserve missing")
    try:
        recorded = datetime.fromisoformat(reservation["recorded_utc"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("One-guest diagnostic reservation timestamp invalid") from None
    if (recorded.tzinfo is None or
            recorded.astimezone(timezone.utc) > datetime.now(timezone.utc)):
        raise ValueError("One-guest diagnostic reservation timestamp invalid")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential missing")
    active, count = active_hashes()
    if active or count:
        raise ValueError("E2B account not active-zero before diagnostic")
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    intent = {"schema":
              "cua-native-wdi-v066-failed-final-profile-diagnostic-intent-v1",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "task_id": target_task_id,
              "package_sha256": row["package_sha256"],
              "source_sha256": source_sha,
              "diagnostic_reservation_sha256": digest(reservation_raw),
              "lease_seconds": lease_seconds,
              "automatic_replay_authorized": False,
              "actor_gui_actions_authorized": 0,
              "official_model_results": 0}
    _write_new(output / "intent.json",
               (json.dumps(intent, sort_keys=True) + "\n").encode())
    receipt = {
        "schema": "cua-native-wdi-gui-development-attempt-v1",
        "purpose": "v066_failed_final_profile_only_diagnostic_no_model",
        "split": "final_candidate", "task_id": target_task_id,
        "status": "started", "stage": "pre_provider",
        "sandbox_timeout_seconds": lease_seconds,
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "provider_running_before_create": count,
        "source_sha256": source_sha,
        "adapter_sha256": adapter_sha,
        "frozen_final_runner_sha256": runner_sha,
        "profile_canonicalizer_sha256": canonicalizer_sha,
        "reservation_sha256": digest(reservation_raw),
        "ratification_sha256": digest(rat_raw),
        "failed_amended_receipt_sha256": digest(failed_raw),
        "earlier_passed_receipt_sha256": digest(historical_raw),
        "package_sha256": row["package_sha256"],
        "input_sha256": digest(baseline),
        "expected_baseline_profile_sha256": expected_profile_sha,
        "profile_snapshots": [],
        "actor_gui_actions": 0,
        "saved_artifact_scoring_performed": False,
        "provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_final_model_attempts": 0,
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
            timeout=lease_seconds, allow_internet_access=False,
            metadata={"envloop_purpose": "v066-failed-final-profile-only-diagnostic"})
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
        sandbox.files.write("/tmp/native-guest-content-probe-failed-final.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        guest_run = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-failed-final.py",
            timeout=450, request_timeout=480)
        if guest_run.exit_code != 0:
            raise ValueError("Scoped guest-content probe failed")
        observed_guest = json.loads(guest_run.stdout)
        if (observed_guest.get("content_tree_sha256") !=
                guest["static_content_sha256"] or
                observed_guest.get("counts") !=
                guest["static_content_counts"] or
                observed_guest.get("kernel") != guest["kernel_identity"] or
                observed_guest.get("excluded_paths") !=
                guest["static_content_excluded_paths"]):
            raise ValueError("Scoped guest-content identity differs")
        receipt["guest_content_attested"] = True
        if sandbox.commands.run(
                "test ! -e /home/user/.config/libreoffice/4/user").exit_code != 0:
            raise ValueError("Fresh LibreOffice profile already exists")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + inputs[0].name
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Final input staging changed")
        sandbox.files.write("/tmp/native-profile-file-probe-failed-final.py",
                            runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())
        receipt["stage"] = "trusted_profile_only_open"
        persist()
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(
            sandbox, inputs[0].name)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        frame = bytes(sandbox.screenshot())
        _write_new(output / "neutral-open.png", frame)
        receipt["neutral_open_screenshot_sha256"] = digest(frame)
        started = time.monotonic()
        receipt["stage"] = "raw_profile_snapshots"
        persist()
        for label, delay in SNAPSHOTS:
            if delay:
                time.sleep(delay)
            receipt["profile_snapshots"].append(
                _snapshot(sandbox, output, label, started))
            persist()
        actual = [row.get("canonical_profile_sha256")
                  for row in receipt["profile_snapshots"]]
        receipt["first_second_canonical_equal"] = (
            actual[0] is not None and actual[0] == actual[1])
        receipt["first_second_match_frozen_baseline"] = (
            actual[0] == actual[1] == expected_profile_sha)
        receipt["settled_canonical_equal"] = (
            actual[2] is not None and actual[2] == actual[3])
        receipt["settled_matches_frozen_baseline"] = (
            actual[3] == expected_profile_sha)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Profile-only open changed input bytes")
        receipt["input_unchanged_after_open"] = True
        receipt["status"] = "profile_diagnostic_captured"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        receipt["error_message_private"] = str(exc)[:240]
        receipt["status"] = "profile_diagnostic_failed"
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--failed-root", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--profile-private", type=Path, required=True)
    parser.add_argument("--guest-public", type=Path, required=True)
    parser.add_argument("--fair-public", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--final-lane-reservation", type=Path, required=True)
    parser.add_argument("--diagnostic-reservation", type=Path, required=True)
    parser.add_argument("--lease-seconds", type=int, default=600)
    parser.add_argument("--max-diagnostic-usd", type=Decimal,
                        default=Decimal("41"))
    args = parser.parse_args()
    result = execute(
        output=args.out, work_root=args.work_root,
        candidate_root=args.candidate_root,
        failed_root=args.failed_root,
        historical_root=args.historical_root,
        target_task_id=args.task_id,
        profile_private=args.profile_private,
        guest_public=args.guest_public, fair_public=args.fair_public,
        ratification=args.ratification,
        final_lane_reservation=args.final_lane_reservation,
        diagnostic_reservation=args.diagnostic_reservation,
        lease_seconds=args.lease_seconds,
        max_diagnostic_usd=args.max_diagnostic_usd)
    print(json.dumps({
        "status": result["status"], "stage": result["stage"],
        "error_type": result.get("error_type"),
        "profile_snapshots": len(result["profile_snapshots"]),
        "first_second_equal": result.get("first_second_canonical_equal"),
        "first_second_match_baseline":
            result.get("first_second_match_frozen_baseline"),
        "settled_match_baseline": result.get("settled_matches_frozen_baseline"),
        "kill_returned": result.get("kill_returned"),
        "running_after_kill": result.get("is_running_after_kill"),
        "receipt_sha256": digest((args.out / "receipt.json").read_bytes()),
        "official_final_admissions": 0,
    }, sort_keys=True))
    if result["status"] != "profile_diagnostic_captured":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
