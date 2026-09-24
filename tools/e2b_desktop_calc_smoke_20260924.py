"""One disposable E2B Desktop / LibreOffice Calc GUI smoke.

The process accepts small interactive commands so the operator can inspect each
screenshot before continuing. It never prints or persists the API key or raw
sandbox ID. Run with E2B_API_KEY set and e2b-desktop installed. Type `help` for
the command list. `stop` kills the one sandbox and checks that it is stopped.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from e2b_desktop import Sandbox


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/e2b-desktop-smoke-2026-09-24"
EVIDENCE.mkdir(parents=True, exist_ok=True)
REMOTE_XLSX = "/tmp/e2b_calc_smoke_20260924.xlsx"
EXPECTED = {"A1": "E2B Desktop smoke", "B1": "1729"}
START_MONOTONIC = time.monotonic()
receipt: dict = {
    "date_utc": datetime.now(timezone.utc).isoformat(),
    "scenario": "One E2B Desktop sandbox, GUI LibreOffice Calc, synthetic XLSX",
    "sdk": {"e2b_desktop": importlib.metadata.version("e2b-desktop")},
    "sandbox_timeout_seconds": 540,
    "expected_cells": EXPECTED,
    "screenshots": {},
    "stages": [],
    "result": "started",
}
sandbox: Sandbox | None = None


def persist() -> None:
    (EVIDENCE / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def stage(name: str, **details: object) -> None:
    receipt["stages"].append({"name": name, "seconds_since_start": round(time.monotonic() - START_MONOTONIC, 3), **details})
    persist()
    print(json.dumps({"stage": name, **details}, ensure_ascii=False), flush=True)


def screenshot(name: str) -> None:
    assert sandbox is not None
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Screenshot label must contain only letters, digits, hyphens, underscores")
    raw = bytes(sandbox.screenshot())
    path = EVIDENCE / f"{name}.png"
    path.write_bytes(raw)
    receipt["screenshots"][name] = {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    stage("screenshot", label=name, file=path.name)


def read_xlsx_cells(raw: bytes) -> dict[str, str]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in shared.findall("m:si", ns):
                strings.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
        cells: dict[str, str] = {}
        for cell in sheet.findall(".//m:sheetData/m:row/m:c", ns):
            address = cell.get("r")
            value = cell.find("m:v", ns)
            inline = cell.find("m:is", ns)
            if not address:
                continue
            if cell.get("t") == "s" and value is not None and value.text is not None:
                cells[address] = strings[int(value.text)]
            elif inline is not None:
                cells[address] = "".join(node.text or "" for node in inline.findall(".//m:t", ns))
            elif value is not None:
                cells[address] = value.text or ""
        return cells


def readback() -> None:
    assert sandbox is not None
    raw = bytes(sandbox.files.read(REMOTE_XLSX, format="bytes"))
    local = EVIDENCE / "calc-smoke.xlsx"
    local.write_bytes(raw)
    cells = read_xlsx_cells(raw)
    matches = {key: cells.get(key) == value for key, value in EXPECTED.items()}
    receipt["xlsx"] = {
        "file": local.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "parsed_cells": {key: cells.get(key) for key in EXPECTED},
        "matches_expected": matches,
        "independent_parser": "Python standard-library zipfile and ElementTree, outside sandbox",
    }
    receipt["result"] = "readback_pass" if all(matches.values()) else "readback_mismatch"
    stage("xlsx_readback", bytes=len(raw), parsed_cells=receipt["xlsx"]["parsed_cells"], matches_expected=matches)


def handle_command(line: str) -> bool:
    assert sandbox is not None
    parts = line.strip().split(maxsplit=1)
    if not parts:
        return True
    action = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if action == "help":
        print("Commands: screen LABEL | press KEY[,KEY] | write TEXT | click X,Y | wait SECONDS | status | readback | stop", flush=True)
    elif action == "screen":
        screenshot(arg)
    elif action == "press":
        keys = [key.strip() for key in arg.split(",") if key.strip()]
        if not keys:
            raise ValueError("Missing key")
        sandbox.press(keys if len(keys) > 1 else keys[0])
        stage("key_press", keys=keys)
    elif action == "write":
        sandbox.write(arg)
        stage("gui_write", length=len(arg))
    elif action == "click":
        x, y = [int(v.strip()) for v in arg.split(",")]
        sandbox.left_click(x, y)
        stage("mouse_click", x=x, y=y)
    elif action == "wait":
        delay = min(float(arg), 10.0)
        if delay < 0:
            raise ValueError("Negative wait")
        time.sleep(delay)
        stage("wait", seconds=delay)
    elif action == "status":
        result = sandbox.commands.run("xdotool getactivewindow getwindowname; pgrep -a soffice.bin | head -1; if test -f /tmp/e2b_calc_smoke_20260924.xlsx; then echo xlsx_present; else echo xlsx_absent; fi")
        stage("gui_status", exit_code=result.exit_code, output=result.stdout.strip()[:300])
    elif action == "readback":
        readback()
    elif action == "stop":
        return False
    else:
        raise ValueError("Unknown command")
    return True


def main() -> int:
    global sandbox
    persist()
    try:
        # At most one create call. Server-side timeout bounds an interrupted run.
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800), timeout=540, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = hashlib.sha256(sandbox.sandbox_id.encode()).hexdigest()
        stage("sandbox_created", id_sha256=receipt["sandbox_id_sha256"], is_running=sandbox.is_running(request_timeout=8))
        probe = sandbox.commands.run("command -v libreoffice; libreoffice --version; ls /usr/share/applications/libreoffice-calc.desktop")
        stage("app_probe", exit_code=probe.exit_code, output=probe.stdout.strip()[:300])
        if probe.exit_code != 0:
            receipt["result"] = "libreoffice_unavailable"
            return 2
        screenshot("desktop-created")
        sandbox.launch("libreoffice-calc")
        time.sleep(4)
        stage("calc_launch_requested")
        screenshot("calc-open")
        print("READY: inspect calc-open.png, then send interactive commands. Type help or stop.", flush=True)
        while True:
            line = sys.stdin.readline()
            if not line:
                stage("stdin_closed")
                break
            try:
                if not handle_command(line):
                    break
            except Exception as error:
                stage("command_error", type=type(error).__name__)
        return 0 if receipt.get("result") == "readback_pass" else 2
    except Exception as error:
        # The exception class is useful for triage; exception text may contain IDs.
        receipt["result"] = "error"
        stage("error", type=type(error).__name__)
        return 2
    finally:
        if sandbox is not None:
            try:
                receipt["is_running_before_kill"] = sandbox.is_running(request_timeout=8)
            except Exception as error:
                receipt["is_running_before_kill_error_type"] = type(error).__name__
            try:
                receipt["kill_returned"] = sandbox.kill()
                stage("sandbox_killed", kill_returned=receipt["kill_returned"])
            except Exception as error:
                receipt["kill_error_type"] = type(error).__name__
                stage("sandbox_kill_error", type=type(error).__name__)
            try:
                receipt["is_running_after_kill"] = sandbox.is_running(request_timeout=8)
                stage("termination_checked", is_running=receipt["is_running_after_kill"])
            except Exception as error:
                receipt["is_running_after_kill_error_type"] = type(error).__name__
                stage("termination_check_error", type=type(error).__name__)
        receipt["duration_seconds"] = round(time.monotonic() - START_MONOTONIC, 3)
        persist()


if __name__ == "__main__":
    raise SystemExit(main())
