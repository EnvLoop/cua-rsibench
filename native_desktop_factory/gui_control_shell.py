"""Interactive, local-only E2B Desktop GUI calibration shell.

This tool is for *development controls* only.  It never admits a final task.
The actor interface exposes screenshot, mouse, keyboard, and visible-window
status; trusted setup uploads the input, and trusted evaluation reads the
saved artifact.  Screenshots and document bytes stay under ignored work/.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

if __package__:
    from .verify import verify
else:
    from verify import verify


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempt", choices=("positive", "near-miss", "cold-reset"), required=True)
    parser.add_argument("--candidate-calibration", action="store_true",
                        help="Explicitly allow a private final candidate for pre-result GUI qualification")
    args = parser.parse_args()
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY missing; source your private shell environment")
    if args.out.exists():
        raise ValueError("Refusing to overwrite attempt output")
    args.out.mkdir(parents=True)
    package = json.loads((args.package / "package.json").read_bytes())
    oracle = json.loads((args.package / "oracle.json").read_bytes())
    artifacts = list(args.package.glob("*.xlsx")) + list(args.package.glob("*.pptx")) + list(args.package.glob("*.docx"))
    if len(artifacts) != 1 or oracle["split"] not in ("train", "final_candidate"):
        raise ValueError("Expected one train or private final-candidate OOXML package")
    if oracle["split"] == "final_candidate" and not args.candidate_calibration:
        raise ValueError("Private final-candidate controls require --candidate-calibration")
    artifact = artifacts[0]
    baseline = artifact.read_bytes()
    if digest(baseline) != oracle["input_sha256"]:
        raise ValueError("Baseline package hash mismatch")
    remote = "/home/user/" + artifact.name
    receipt = {"schema": "cua-native-wdi-gui-development-attempt-v1", "attempt": args.attempt,
               "task_id": oracle["task_id"], "input_sha256": digest(baseline),
               "sdk_version": importlib.metadata.version("e2b-desktop"),
               "status": "started", "screenshots": {}, "actor_actions": []}
    sandbox = None

    def persist() -> None:
        (args.out / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")

    def screen(label: str) -> None:
        if not label.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid screenshot label")
        raw = bytes(sandbox.screenshot())
        (args.out / f"{label}.png").write_bytes(raw)
        receipt["screenshots"][label] = {"sha256": digest(raw), "bytes": len(raw)}
        persist()
        print(json.dumps({"screenshot": str(args.out / f"{label}.png")}), flush=True)

    def actor(action: str, value=None) -> None:
        if action == "press":
            keys = value.split(",")
            sandbox.press(keys if len(keys) > 1 else keys[0])
            receipt["actor_actions"].append({"type": "press", "keys": keys})
        elif action == "write":
            sandbox.write(value)
            receipt["actor_actions"].append({"type": "write", "sha256": digest(value.encode()), "chars": len(value)})
        elif action in ("click", "double"):
            x, y = [int(v) for v in value.split(",")]
            (sandbox.left_click if action == "click" else sandbox.double_click)(x, y)
            receipt["actor_actions"].append({"type": action, "x": x, "y": y})
        else:
            raise ValueError("Unknown actor action")
        persist()

    def readback() -> None:
        raw = bytes(sandbox.files.read(remote, format="bytes"))
        path = args.out / ("saved" + artifact.suffix)
        path.write_bytes(raw)
        result = verify(baseline, raw, oracle)
        receipt["saved_sha256"] = digest(raw)
        receipt["verifier"] = result
        persist()
        print(json.dumps({"saved_sha256": digest(raw), "verifier": result}, sort_keys=True), flush=True)

    try:
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=600, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        probe = sandbox.commands.run("libreoffice --version; sha256sum /usr/bin/libreoffice")
        if probe.exit_code != 0 or "LibreOffice 7.3.7.2" not in probe.stdout:
            raise ValueError("Unexpected LibreOffice runtime")
        receipt["runtime_probe"] = probe.stdout.strip()
        sandbox.files.write(remote, baseline)
        staged = bytes(sandbox.files.read(remote, format="bytes"))
        if staged != baseline:
            raise ValueError("Trusted setup readback differs from input")
        receipt["staged_sha256"] = digest(staged)
        persist()
        if args.attempt != "cold-reset":
            sandbox.open(remote)
            time.sleep(4)
        screen("initial")
        print("READY: screen LABEL | press KEY[,KEY] | write TEXT | click X,Y | double X,Y | wait N | status | readback | stop", flush=True)
        for line in sys.stdin:
            name, _, value = line.strip().partition(" ")
            try:
                if name == "screen":
                    screen(value)
                elif name in ("press", "write", "click", "double"):
                    actor(name, value)
                elif name == "wait":
                    time.sleep(min(max(float(value), 0.0), 10.0))
                elif name == "status":
                    result = sandbox.commands.run("xdotool getactivewindow getwindowname")
                    print(json.dumps({"window_title": result.stdout.strip(), "exit_code": result.exit_code}), flush=True)
                elif name == "readback":
                    readback()
                elif name == "stop":
                    break
                else:
                    print(json.dumps({"error": "unknown_command"}), flush=True)
            except Exception as exc:
                print(json.dumps({"error_type": type(exc).__name__, "error": str(exc)[:180]}), flush=True)
        if args.attempt == "cold-reset":
            latest = bytes(sandbox.files.read(remote, format="bytes"))
            receipt["restored_state_sha256"] = digest(latest)
            receipt["status"] = "cold_reset_observed" if latest == baseline else "cold_reset_failed"
        else:
            if "verifier" not in receipt:
                readback()
            expected = args.attempt == "positive"
            receipt["status"] = "control_passed" if receipt["verifier"]["passed"] == expected and receipt["saved_sha256"] != receipt["input_sha256"] else "control_failed"
    except Exception as exc:
        receipt["status"] = "error"
        receipt["error_type"] = type(exc).__name__
        persist()
        raise
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=8))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
            if receipt.get("is_running_after_kill") is not False:
                receipt["status"] = "cleanup_unverified"
        persist()
    print(json.dumps({"status": receipt["status"], "receipt": str(args.out / "receipt.json")}), flush=True)
    return 0 if receipt["status"] in ("control_passed", "cold_reset_observed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
