"""One evaluator-only final-candidate LibreOffice profile baseline.

This performs a neutral native GUI open, with no model action and no oracle
readback. The final package, screenshot and per-ID receipt remain private.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

if __package__:
    from .budget_ledger import audit as audit_budget
    from .gui_control_shell import wait_for_document_ready
    from .profile_canonical import canonical_profile_tree
    from .runtime_fingerprint_probe import PROFILE_FILE_PROBE
else:
    from budget_ledger import audit as audit_budget
    from gui_control_shell import wait_for_document_ready
    from profile_canonical import canonical_profile_tree
    from runtime_fingerprint_probe import PROFILE_FILE_PROBE


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def preflight(package_dir: Path, candidate_root: Path) -> tuple[dict, Path, bytes]:
    package_dir, candidate_root = package_dir.resolve(), candidate_root.resolve()
    if not package_dir.is_relative_to(candidate_root / "final_candidate"):
        raise ValueError("Only private final-candidate packages may be baselined")
    package_raw = (package_dir / "package.json").read_bytes()
    package = json.loads(package_raw)
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    matching = [row for row in inventory["tasks"] if row["task_id"] == package.get("task_id")]
    if (inventory.get("design_revision") != "v2-distinct-structures"
            or len(matching) != 1 or matching[0] != package
            or package.get("split") != "final_candidate"
            or package_dir.parent != candidate_root / "final_candidate"):
        raise ValueError("Private final inventory binding changed")
    if package.get("workflow") == "impress-deck" and "normalization" not in package:
        raise ValueError("Final Impress input is not neutrally normalized")
    artifacts = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
                 *package_dir.glob("*.docx")]
    if len(artifacts) != 1:
        raise ValueError("Expected one bound native Office input")
    baseline = artifacts[0].read_bytes()
    if digest(baseline) != package["input_sha256"]:
        raise ValueError("Final input bytes differ from private inventory")
    return package, artifacts[0], baseline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--expected-runtime-manifest", type=Path, required=True)
    parser.add_argument("--lease-seconds", type=int, default=120)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal, default=Decimal("40"))
    args = parser.parse_args()
    if args.out_dir.exists():
        raise ValueError("Refusing to overwrite a final profile baseline attempt")
    if (args.out_dir.parent.resolve() != (args.work_root / "gui-diagnostics").resolve()
            or not args.out_dir.name.startswith("profile-baseline-")):
        raise ValueError("Output must be in the profile-baseline ledger namespace")
    if not 120 <= args.lease_seconds <= 600:
        raise ValueError("Profile baseline lease is out of bound")
    package, artifact, baseline = preflight(args.package, args.candidate_root)
    runtime_raw = args.expected_runtime_manifest.read_bytes()
    runtime = json.loads(runtime_raw)
    if (runtime.get("schema") != "cua-native-wdi-desktop-runtime-fingerprint-public-v1"
            or runtime.get("distinct_sandboxes") != 2):
        raise ValueError("Runtime reference is not the two-sandbox audit")
    budget = audit_budget(args.work_root, proposed_new_sandboxes=1,
                          proposed_lease_seconds=args.lease_seconds,
                          max_lane_reserved_usd=args.max_lane_reserved_usd)
    if not budget["within_cap"] or not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B credential or native lane lease reservation missing")
    args.out_dir.mkdir(parents=True)
    receipt = {
        "schema": "cua-native-wdi-profile-baseline-v1", "status": "started",
        "task_id": package["task_id"], "split": "final_candidate",
        "workflow": package["workflow"], "input_sha256": digest(baseline),
        "package_sha256": package["package_sha256"],
        "runtime_reference_sha256": digest(runtime_raw),
        "profile_probe_script_sha256": digest(PROFILE_FILE_PROBE.encode()),
        "lease_seconds": args.lease_seconds,
        "reserved_full_lease_usd": budget["proposed_reserved_usd"],
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "profile_snapshot_sha256s": [], "actual_billed_usd": None,
        "stage": "pre_provider",
    }

    def persist():
        (args.out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    persist()
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        receipt["stage"] = "create_desktop"
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=args.lease_seconds, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version,
        }
        if (info.template_id != runtime["provider_template_id"]
                or info.envd_version != runtime["provider_envd_version"]
                or info.cpu_count != runtime["provider_resource_shape"]["vcpu"]
                or info.memory_mb != runtime["provider_resource_shape"]["memory_mb"]):
            raise ValueError("Native Desktop provider shape/template drifted")
        receipt["stage"] = "fresh_runtime_probe"
        probe = sandbox.commands.run("libreoffice --version; sha256sum /usr/bin/libreoffice")
        if (probe.exit_code != 0
                or runtime["after_open_libreoffice_version"] not in probe.stdout
                or runtime["after_open_libreoffice_executable_sha256"] not in probe.stdout):
            raise ValueError("LibreOffice executable or version drifted")
        receipt["libreoffice_runtime_probe_sha256"] = digest(probe.stdout.encode())
        profile_absent = sandbox.commands.run("test ! -e /home/user/.config/libreoffice/4/user")
        if profile_absent.exit_code != 0:
            raise ValueError("Fresh LibreOffice user profile was already present")
        receipt["fresh_profile_absent"] = True
        remote = "/home/user/" + artifact.name
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Trusted final input staging changed bytes")
        sandbox.files.write("/tmp/native-profile-file-probe.py", PROFILE_FILE_PROBE.encode())
        receipt["stage"] = "neutral_gui_open"
        sandbox.open(remote)
        try:
            receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox, artifact.name)
        except TimeoutError:
            frame = bytes(sandbox.screenshot())
            (args.out_dir / "document-ready-timeout.png").write_bytes(frame)
            receipt["document_ready_timeout_screenshot_sha256"] = digest(frame)
            window = sandbox.commands.run(
                "xdotool getactivewindow getwindowname 2>/dev/null || true")
            receipt["document_ready_timeout_window_title_private"] = window.stdout.strip()[:200]
            persist()
            raise
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        frame = bytes(sandbox.screenshot())
        (args.out_dir / "neutral-open.png").write_bytes(frame)
        receipt["neutral_open_screenshot_sha256"] = digest(frame)

        def snapshot() -> str:
            result = sandbox.commands.run("python3 /tmp/native-profile-file-probe.py")
            if result.exit_code != 0:
                raise ValueError("Read-only profile-file manifest failed")
            rows = json.loads(result.stdout)
            registry = bytes(sandbox.files.read(
                "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
                format="bytes"))
            return canonical_profile_tree(rows, registry)

        receipt["stage"] = "profile_stability_check"
        stable = False
        for _ in range(4):
            observed = snapshot()
            receipt["profile_snapshot_sha256s"].append(observed)
            persist()
            if len(receipt["profile_snapshot_sha256s"]) >= 2 and observed == receipt["profile_snapshot_sha256s"][-2]:
                stable = True
                break
            time.sleep(1)
        if not stable:
            raise ValueError("Neutral profile did not stabilize within four reads")
        receipt["canonical_profile_sha256"] = observed
        latest = bytes(sandbox.files.read(remote, format="bytes"))
        if latest != baseline:
            raise ValueError("Neutral open altered input artifact bytes")
        receipt["input_unchanged_after_open"] = True
        receipt["status"] = "profile_baseline_observed"
    except Exception as exc:
        receipt["status"] = "profile_baseline_failed"
        receipt["error_type"] = type(exc).__name__
        receipt["error_message_private"] = str(exc)[:500]
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=8))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if receipt["status"] == "profile_baseline_observed" and receipt.get("is_running_after_kill") is False:
            receipt["status"] = "profile_baseline_passed"
        persist()
    print(json.dumps({
        "status": receipt["status"], "error_type": receipt.get("error_type"),
        "sandbox_terminated": receipt.get("is_running_after_kill") is False,
        "profile_snapshot_count": len(receipt["profile_snapshot_sha256s"]),
    }, sort_keys=True))
    return 0 if receipt["status"] == "profile_baseline_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
