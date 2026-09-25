"""One separately bounded E2B Desktop recovery probe after lease reconciliation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def execute(reconciliation: Path, output: Path, *, lease_seconds: int,
            max_reserved_usd: float, usd_per_hour_upper: float) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite an E2B health probe")
    evidence_raw = reconciliation.read_bytes()
    evidence = json.loads(evidence_raw)
    if evidence.get("ready_for_separate_health_probe") is not True:
        raise ValueError("Interrupted no-ID/cleanup cases are not reconciled")
    if not 120 <= lease_seconds <= 300 or usd_per_hour_upper < 0.5328:
        raise ValueError("Lease/rate bound is insufficient")
    reserve = lease_seconds / 3600 * usd_per_hour_upper
    if reserve > max_reserved_usd:
        raise ValueError("Health probe exceeds conservative USD reserve")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schema": "cua-native-wdi-e2b-recovery-health-probe-v1",
               "status": "started", "checked_utc": datetime.now(timezone.utc).isoformat(),
               "reconciliation_sha256": digest(evidence_raw),
               "sdk_version": importlib.metadata.version("e2b-desktop"),
               "lease_seconds": lease_seconds, "usd_per_hour_upper": usd_per_hour_upper,
               "reserved_usd_upper": round(reserve, 6),
               "actual_billed_usd": None}
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=lease_seconds, allow_internet_access=False,
                                 metadata={"envloop_purpose": "native-desktop-recovery-health-probe"})
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id,
            "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb,
            "envd_version": info.envd_version,
            "state": str(info.state),
        }
        if info.cpu_count > 8 or info.memory_mb > 8192:
            raise ValueError("Provider-reported Desktop shape exceeds 8-vCPU/8-GiB priced class")
        probe = sandbox.commands.run("libreoffice --version; sha256sum /usr/bin/libreoffice; nproc; awk '/MemTotal:/ {print $2}' /proc/meminfo")
        if probe.exit_code != 0 or "LibreOffice 7.3.7.2" not in probe.stdout:
            raise ValueError("Native LibreOffice runtime probe failed")
        receipt["guest_probe"] = probe.stdout.strip()
        raw = bytes(sandbox.screenshot())
        receipt["screenshot_sha256"] = digest(raw)
        receipt["status"] = "probe_checks_passed"
    except Exception as exc:
        receipt["status"] = "probe_failed"
        receipt["error_type"] = type(exc).__name__
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        receipt["completed_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["ready_to_resume_paid_gui_dispatch"] = (
            receipt["status"] == "probe_checks_passed" and
            receipt.get("kill_returned") is True and
            receipt.get("is_running_after_kill") is False
        )
        if receipt["ready_to_resume_paid_gui_dispatch"]:
            receipt["status"] = "healthy_and_terminated"
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lease-seconds", type=int, default=120)
    parser.add_argument("--max-reserved-usd", type=float, default=0.04)
    parser.add_argument("--usd-per-hour-upper", type=float, default=1.0)
    args = parser.parse_args()
    result = execute(args.reconciliation, args.out,
                     lease_seconds=args.lease_seconds,
                     max_reserved_usd=args.max_reserved_usd,
                     usd_per_hour_upper=args.usd_per_hour_upper)
    print(json.dumps({"status": result["status"],
                      "ready": result["ready_to_resume_paid_gui_dispatch"],
                      "error_type": result.get("error_type"),
                      "receipt_sha256": digest(args.out.read_bytes())}, sort_keys=True))
    if not result["ready_to_resume_paid_gui_dispatch"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
