"""Trusted, neutral LibreOffice save to prepare a development-only PPTX baseline.

The current python-pptx file is first opened and saved without task edits in
the pinned desktop.  A *different* fresh sandbox later runs actor controls.
This is not an actor action or a benchmark result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not os.getenv("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY missing")
    if args.out.exists() or args.input.suffix != ".pptx":
        raise ValueError("Require a new output directory and PPTX input")
    args.out.mkdir(parents=True)
    from e2b_desktop import Sandbox
    sandbox = None
    receipt = {"schema": "cua-native-impress-trusted-normalization-v1", "status": "started",
               "original_sha256": digest(args.input.read_bytes())}
    remote = "/home/user/" + args.input.name
    try:
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=600, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        probe = sandbox.commands.run("libreoffice --version; sha256sum /usr/bin/libreoffice")
        if probe.exit_code != 0 or "LibreOffice 7.3.7.2" not in probe.stdout:
            raise ValueError("Unexpected LibreOffice runtime")
        receipt["runtime_probe"] = probe.stdout.strip()
        baseline = args.input.read_bytes()
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Trusted upload changed bytes")
        sandbox.open(remote)
        title = ""
        for _ in range(30):
            time.sleep(1)
            title = sandbox.commands.run("xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()
            if title.startswith("Tip of the Day") or "LibreOffice Impress" in title:
                break
        if not title:
            raise TimeoutError("Impress window never became active")
        time.sleep(3)
        title = sandbox.commands.run("xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()
        if title.startswith("Tip of the Day"):
            sandbox.left_click(880, 535)
            time.sleep(1)
        receipt["opened_window"] = sandbox.commands.run("xdotool getactivewindow getwindowname").stdout.strip()
        if "LibreOffice Impress" not in receipt["opened_window"]:
            raise ValueError("PPTX did not open in Impress")
        (args.out / "opened.png").write_bytes(bytes(sandbox.screenshot()))
        sandbox.press(["ctrl", "s"])
        time.sleep(2)
        title = sandbox.commands.run("xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()
        if title.startswith("Tip of the Day"):
            sandbox.left_click(880, 535)
            time.sleep(1)
            sandbox.press(["ctrl", "s"])
            time.sleep(2)
            title = sandbox.commands.run("xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()
        if title == "Confirm File Format":
            sandbox.left_click(790, 519)
            time.sleep(3)
        (args.out / "after-save.png").write_bytes(bytes(sandbox.screenshot()))
        receipt["saved_window"] = sandbox.commands.run("xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()
        if "LibreOffice Impress" not in receipt["saved_window"]:
            raise ValueError("PPTX did not return from save")
        normalized = bytes(sandbox.files.read(remote, format="bytes"))
        if normalized == baseline:
            raise ValueError("No native reserialization observed")
        (args.out / "normalized.pptx").write_bytes(normalized)
        receipt["normalized_sha256"] = digest(normalized)
        receipt["status"] = "neutral_save_observed"
    except Exception as exc:
        receipt["status"] = "error"
        receipt["error_type"] = type(exc).__name__
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
        (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if receipt["status"] != "neutral_save_observed":
        raise ValueError("Neutral normalization cleanup failed")
    print(json.dumps({"status": receipt["status"], "original_sha256": receipt["original_sha256"],
                      "normalized_sha256": receipt["normalized_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
