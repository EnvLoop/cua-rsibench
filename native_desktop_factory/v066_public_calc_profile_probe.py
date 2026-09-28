"""One bounded public-train Calc guest for raw LibreOffice profile diagnosis.

This stages a fixed public train workbook, performs no actor GUI edit and no
model call, and never opens a final package. Four raw file manifests and
registry XML captures remain evaluator-private. A source-bound intent is
written before one E2B create; any failed or uncertain create consumes its
full lease and is never retried automatically.
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

from . import profile_canonical, qwen_v066_adapter, runtime_fingerprint_probe
from .budget_ledger import audit as budget_audit
from .factory import json_bytes
from .gui_control_shell import wait_for_document_ready
from .reconcile_interrupted_sweep import active_hashes
from .v066_final_freeze import digest, validate_ratification


PUBLIC_CALC = (Path(__file__).with_name("dev-fixtures") /
               "wdi-native-mex-calc-growth")
SNAPSHOTS = (("first", 0), ("second", 1),
             ("settled_early", 3), ("settled_late", 4))


def public_train_source() -> tuple[dict, bytes, str]:
    root = PUBLIC_CALC.resolve()
    package = json.loads((root / "package.json").read_bytes())
    oracle_raw = (root / "oracle.json").read_bytes()
    actor_raw = (root / "actor_task.txt").read_bytes()
    files = list(root.glob("*.xlsx"))
    if (len(files) != 1 or package.get("split") != "train" or
            package.get("workflow") != "calc-growth" or
            digest(json_bytes({key: value for key, value in package.items()
                               if key != "package_sha256"})) !=
            package.get("package_sha256") or
            package.get("oracle_sha256") != digest(oracle_raw) or
            package.get("actor_task_sha256") != digest(actor_raw) or
            json.loads(oracle_raw).get("split") != "train" or
            json.loads(oracle_raw).get("task_id") !=
            package.get("task_id") or
            json.loads(oracle_raw).get("input_sha256") !=
            package.get("input_sha256")):
        raise ValueError("Only the pinned public Calc train source is allowed")
    raw = files[0].read_bytes()
    if package.get("input_sha256") != digest(raw):
        raise ValueError("Public Calc train input changed")
    return package, raw, files[0].name


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _snapshot(sandbox, output: Path, label: str,
              started: float) -> dict:
    command = sandbox.commands.run(
        "python3 /tmp/native-profile-file-probe-caret-calc.py")
    if command.exit_code != 0:
        raise ValueError("Public Calc profile-file probe failed")
    raw_manifest = command.stdout.encode()
    rows = json.loads(raw_manifest)
    if type(rows) is not list or len(rows) > 500:
        raise ValueError("Public Calc profile manifest is unbounded")
    registry = bytes(sandbox.files.read(
        "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
        format="bytes"))
    if len(raw_manifest) > 4_000_000 or len(registry) > 4_000_000:
        raise ValueError("Public Calc raw profile capture is unbounded")
    canonical = profile_canonical.canonical_profile_tree(rows, registry)
    _write_new(output / f"profile-{label}.manifest.json", raw_manifest)
    _write_new(output / f"profile-{label}.registry.xml", registry)
    return {"label": label,
            "captured_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds_after_open": round(time.monotonic() - started, 3),
            "file_count": len(rows),
            "manifest_sha256": digest(raw_manifest),
            "registry_sha256": digest(registry),
            "canonical_profile_sha256": canonical}


def execute(*, output: Path, work_root: Path,
            guest_identity_public: Path, ratification: Path,
            diagnostic_reservation: Path,
            lease_seconds: int = 600,
            max_lane_reserved_usd: Decimal = Decimal("41")) -> dict:
    if (output.exists() or output.is_symlink() or
            not output.resolve().is_relative_to(
                (work_root / "gui-diagnostics").resolve()) or
            not 300 <= lease_seconds <= 600):
        raise ValueError("New private bounded public Calc output required")
    package, baseline, filename = public_train_source()
    guest_raw = guest_identity_public.read_bytes()
    guest = json.loads(guest_raw)
    if (guest.get("schema") !=
            "cua-native-wdi-guest-content-identity-public-v1" or
            guest.get("scoped_guest_content_identity_passed") is not True or
            guest.get("guest_content_probe_script_sha256") !=
            digest(runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())):
        raise ValueError("Scoped public guest identity changed")
    _, rat_sha = validate_ratification(ratification)
    source_sha = digest(Path(__file__).read_bytes())
    adapter_sha = digest(Path(qwen_v066_adapter.__file__).read_bytes())
    reservation_raw = diagnostic_reservation.read_bytes()
    reservation = json.loads(reservation_raw)
    budget = budget_audit(
        work_root, proposed_new_sandboxes=1,
        proposed_lease_seconds=lease_seconds,
        max_lane_reserved_usd=max_lane_reserved_usd)
    expected = {
        "schema": "cua-native-wdi-v066-public-calc-profile-diagnostic-reservation-v1",
        "status": "reserved_before_single_paid_public_train_create",
        "probe_source_sha256": source_sha,
        "amended_desktop_adapter_sha256": adapter_sha,
        "new_six_cell_ratification_sha256": rat_sha,
        "public_train_package_sha256": package["package_sha256"],
        "guest_identity_public_sha256": digest(guest_raw),
        "past_conservative_reserved_usd":
            budget["past_conservative_reserved_usd"],
        "new_lease_seconds_reserved": lease_seconds,
        "new_sandbox_intents_reserved": 1,
        "combined_conservative_reserved_usd":
            budget["combined_reserved_usd"],
        "diagnostic_cap_usd": str(max_lane_reserved_usd),
        "actual_provider_billed_usd": None,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    if (not budget["within_cap"] or
            any(reservation.get(key) != value for key, value in
                expected.items()) or
            type(reservation.get("recorded_utc")) is not str):
        raise ValueError("Source-bound public Calc diagnostic reserve missing")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("Private E2B credential missing")
    active, count = active_hashes()
    if active or count:
        raise ValueError("E2B account is not active-zero")
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    intent = {
        "schema": "cua-native-wdi-v066-public-calc-profile-diagnostic-intent-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "split": "train",
        "package_sha256": package["package_sha256"],
        "input_sha256": digest(baseline),
        "lease_seconds": lease_seconds,
        "source_sha256": source_sha,
        "reservation_sha256": digest(reservation_raw),
        "automatic_replay_authorized": False,
        "official_model_results": 0,
    }
    _write_new(output / "intent.json",
               (json.dumps(intent, sort_keys=True) + "\n").encode())
    receipt = {
        "schema": "cua-native-wdi-gui-development-attempt-v1",
        "purpose": "v066_public_train_calc_profile_diagnostic_no_model",
        "split": "train", "status": "started", "stage": "pre_provider",
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "sandbox_timeout_seconds": lease_seconds,
        "provider_running_before_create": count,
        "source_sha256": source_sha,
        "adapter_sha256": adapter_sha,
        "ratification_sha256": rat_sha,
        "reservation_sha256": digest(reservation_raw),
        "guest_identity_public_sha256": digest(guest_raw),
        "input_sha256": digest(baseline),
        "package_sha256": package["package_sha256"],
        "profile_probe_script_sha256":
            digest(runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode()),
        "profile_snapshots": [],
        "actor_gui_actions": 0,
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
            metadata={"envloop_purpose": "v066-public-train-calc-profile-diagnostic"})
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
        sandbox.files.write("/tmp/native-guest-content-probe-caret-calc.py",
                            runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())
        guest_run = sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-caret-calc.py",
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
        remote = "/home/user/" + filename
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Public Calc train input staging changed")
        sandbox.files.write("/tmp/native-profile-file-probe-caret-calc.py",
                            runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())
        receipt["stage"] = "trusted_public_calc_open"
        persist()
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox, filename)
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
        values = [row["canonical_profile_sha256"]
                  for row in receipt["profile_snapshots"]]
        receipt["first_second_canonical_equal"] = values[0] == values[1]
        receipt["settled_canonical_equal"] = values[2] == values[3]
        receipt["first_settled_canonical_equal"] = values[0] == values[3]
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Public Calc neutral open changed input")
        receipt["input_unchanged_after_open"] = True
        receipt["status"] = "profile_diagnostic_captured"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
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
    parser.add_argument("--guest-identity-public", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    parser.add_argument("--diagnostic-reservation", type=Path, required=True)
    parser.add_argument("--lease-seconds", type=int, default=600)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal,
                        default=Decimal("41"))
    args = parser.parse_args()
    result = execute(output=args.out, work_root=args.work_root,
                     guest_identity_public=args.guest_identity_public,
                     ratification=args.ratification,
                     diagnostic_reservation=args.diagnostic_reservation,
                     lease_seconds=args.lease_seconds,
                     max_lane_reserved_usd=args.max_lane_reserved_usd)
    print(json.dumps({
        "status": result["status"], "stage": result["stage"],
        "error_type": result.get("error_type"),
        "profile_snapshots": len(result["profile_snapshots"]),
        "first_second_equal": result.get("first_second_canonical_equal"),
        "settled_equal": result.get("settled_canonical_equal"),
        "kill_returned": result.get("kill_returned"),
        "running_after_kill": result.get("is_running_after_kill"),
        "receipt_sha256": digest((args.out / "receipt.json").read_bytes()),
        "official_final_admissions": 0,
    }, sort_keys=True))
    if result["status"] != "profile_diagnostic_captured":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
