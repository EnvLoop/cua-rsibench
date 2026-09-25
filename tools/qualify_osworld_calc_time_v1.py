"""Calibrate one pinned OSWorld Calc task through an actual E2B desktop GUI.

This is a development control, not a final-task admission runner. It keeps the
third-party workbook and screenshots in an ignored private output directory.
The actor uses only E2B Desktop mouse/keyboard methods. Trusted setup injects
the workbook; trusted evaluation reads the saved file before OSWorld postconfig.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import time
import types
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


TASK_ID = "357ef137-7eeb-4c80-a3bb-0951f26a8aff"
SOURCE_COMMIT = "b138d348256078fa634fc3b73567a7337c793e6b"
DATASET_COMMIT = "1e112283c4ecb08d6fed8069bca7de74fa2f12aa"
TASK_CONFIG_SHA256 = "c7cb07720392d1fd5da5aa323e989d8e9d772de02b8317b0f05370d6ab896511"
ASSET_SHA256 = "a6f792dd99a2251bf7f2ed1f55896e3588718a4a53d291ecc5db25a5b3ac8b17"
TABLE_PY_SHA256 = "f41cf46df90a764705bb85727b3a0a612e9ff7bfa2629cdf40d6feab76d6e5fe"
UTILS_PY_SHA256 = "45aa2e44248a549d1c0462179f9ae0d0429d5077900c7dc1fa447aa0b136c577"
TASK_PATH = Path("evaluation_examples/examples/libreoffice_calc") / f"{TASK_ID}.json"
REMOTE_FILE = "/home/user/Multiply_Time_Number.xlsx"
TARGET_CELL = "E3"
TARGET_VALUE = 191.6667
FORMULA = "=D3*F3*24"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def pinned_source(source_root: Path) -> dict:
    commit = subprocess.check_output(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip()
    require(commit == SOURCE_COMMIT, "OSWorld source commit changed")
    paths = {
        "task_config": source_root / TASK_PATH,
        "table_py": source_root / "desktop_env/evaluators/metrics/table.py",
        "utils_py": source_root / "desktop_env/evaluators/metrics/utils.py",
    }
    expected = {"task_config": TASK_CONFIG_SHA256,
                "table_py": TABLE_PY_SHA256, "utils_py": UTILS_PY_SHA256}
    for key, path in paths.items():
        require(path.is_file() and sha(path.read_bytes()) == expected[key],
                f"pinned {key} bytes changed")
    task = json.loads(paths["task_config"].read_text())
    require(task["id"] == TASK_ID and task["evaluator"]["func"] == "compare_table",
            "task identity or evaluator changed")
    require(task["evaluator"]["result"] == {
        "type": "vm_file", "path": REMOTE_FILE, "dest": "Multiply_Time_Number.xlsx"},
        "result target changed")
    rules = task["evaluator"]["options"]["rules"]
    require(rules == [{"type": "check_cell", "sheet_idx": 0,
                       "coordinate": TARGET_CELL,
                       "props": {"value": {"method": "approx:0.001",
                                            "ref": TARGET_VALUE}}}],
            "published evaluator rule changed")
    return {"source_commit": commit, "dataset_commit": DATASET_COMMIT,
            "task_config_sha256": expected["task_config"],
            "table_py_sha256": expected["table_py"],
            "utils_py_sha256": expected["utils_py"]}


def read_cells(raw: bytes) -> dict:
    """Read all cell contents with stdlib OOXML; ignore serializer style IDs."""
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        require(book.testzip() is None, "invalid XLSX ZIP")
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            strings = ["".join(node.text or "" for node in si.findall(".//m:t", NS))
                       for si in root.findall("m:si", NS)]
        sheets = {}
        for name in sorted(path for path in book.namelist()
                           if path.startswith("xl/worksheets/sheet") and path.endswith(".xml")):
            root = ET.fromstring(book.read(name))
            cells = {}
            for cell in root.findall(".//m:sheetData/m:row/m:c", NS):
                address = cell.get("r")
                formula = cell.find("m:f", NS)
                value = cell.find("m:v", NS)
                inline = cell.find("m:is", NS)
                if not address:
                    continue
                scalar = value.text if value is not None else None
                if cell.get("t") == "s" and scalar is not None:
                    scalar = strings[int(scalar)]
                elif inline is not None:
                    scalar = "".join(node.text or "" for node in inline.findall(".//m:t", NS))
                if scalar is not None or formula is not None:
                    cells[address] = {"formula": formula.text if formula is not None else None,
                                      "value": scalar}
            sheets[name] = cells
    require(sheets, "no XLSX worksheet content")
    return sheets


def _same_scalar(left: object, right: object) -> bool:
    if left == right:
        return True
    try:
        return abs(float(left) - float(right)) <= 1e-9
    except (TypeError, ValueError):
        return False


def semantic_check(baseline: bytes, saved: bytes, *, attempt: str) -> dict:
    require(attempt in ("positive", "wrong-cell"), "unknown attempt type")
    before, after = read_cells(baseline), read_cells(saved)
    require(set(before) == set(after) and len(before) == 1,
            "worksheet structure changed")
    sheet = next(iter(before))
    before_cells, after_cells = before[sheet], after[sheet]
    changed = []
    for address in sorted(set(before_cells) | set(after_cells)):
        left, right = before_cells.get(address), after_cells.get(address)
        if left is None or right is None or left["formula"] != right["formula"] or not _same_scalar(left["value"], right["value"]):
            changed.append(address)
    target = after_cells.get(TARGET_CELL)
    target_value = None
    if target is not None:
        try:
            target_value = float(target["value"])
        except (TypeError, ValueError):
            pass
    target_passed = (target is not None and target["formula"] == FORMULA[1:]
                     and target_value is not None
                     and abs(target_value - TARGET_VALUE) <= 0.001)
    preservation_passed = changed == [TARGET_CELL]
    return {"changed_cells": changed, "target_value": target_value,
            "target_formula_matches": bool(target and target["formula"] == FORMULA[1:]),
            "target_passed": target_passed,
            "cell_value_formula_preservation_passed": preservation_passed,
            "independent_accept": attempt == "positive" and target_passed and preservation_passed}


def official_score(source_root: Path, saved_path: Path) -> float:
    """Load exact pinned upstream table evaluator without unrelated package imports."""
    metrics = source_root / "desktop_env/evaluators/metrics"
    for name, path in (("desktop_env", source_root / "desktop_env"),
                       ("desktop_env.evaluators", source_root / "desktop_env/evaluators"),
                       ("desktop_env.evaluators.metrics", metrics)):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    name = "desktop_env.evaluators.metrics.table"
    spec = importlib.util.spec_from_file_location(name, metrics / "table.py")
    require(spec is not None and spec.loader is not None, "upstream evaluator unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    task = json.loads((source_root / TASK_PATH).read_text())
    return float(module.compare_table(str(saved_path), **task["evaluator"]["options"]))


def active_window_title(sandbox) -> str:
    probe = sandbox.commands.run("xdotool getactivewindow getwindowname")
    require(probe.exit_code == 0, "cannot inspect visible active window")
    return probe.stdout.strip()


def wait_for_workbook(sandbox, *, seconds: int = 45) -> str:
    """Wait for actual Calc window, not a desktop or splash-screen timer."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        search = sandbox.commands.run(
            "xdotool search --name 'Multiply_Time_Number.xlsx - LibreOffice Calc' | head -1")
        if search.exit_code == 0 and search.stdout.strip():
            time.sleep(2)
            return active_window_title(sandbox)
        time.sleep(1)
    raise TimeoutError("Calc workbook window never became visible")


def execute(source_root: Path, asset_path: Path, output_dir: Path, attempt: str) -> dict:
    import importlib.metadata
    from e2b_desktop import Sandbox

    source = pinned_source(source_root)
    asset = asset_path.read_bytes()
    require(sha(asset) == ASSET_SHA256, "third-party input asset changed")
    require(attempt in ("positive", "wrong-cell"), "unknown attempt type")
    require(not output_dir.exists(), "attempt output already exists")
    output_dir.mkdir(parents=True)
    receipt = {"schema": "envloop-osworld-calc-time-development-control-v1",
               "task_id": TASK_ID, "status": "started", "attempt": attempt,
               "source": source, "asset_sha256": ASSET_SHA256,
               "e2b_desktop_version": importlib.metadata.version("e2b-desktop"),
               "actions": [], "screenshots": {}}
    sandbox = None

    def save_receipt() -> None:
        (output_dir / "receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    def screen(label: str) -> None:
        raw = bytes(sandbox.screenshot())
        (output_dir / f"{label}.png").write_bytes(raw)
        receipt["screenshots"][label] = sha(raw)

    try:
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=540, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = sha(sandbox.sandbox_id.encode())
        probe = sandbox.commands.run("libreoffice --version; sha256sum /usr/bin/libreoffice")
        require(probe.exit_code == 0 and "LibreOffice 7.3.7.2" in probe.stdout,
                "native application identity changed")
        receipt["native_application_probe"] = probe.stdout.strip()
        sandbox.files.write(REMOTE_FILE, asset)
        staged = bytes(sandbox.files.read(REMOTE_FILE, format="bytes"))
        require(staged == asset, "trusted setup upload/readback changed")
        receipt["baseline_state_sha256"] = sha(staged)
        receipt["baseline_target_empty"] = TARGET_CELL not in next(iter(read_cells(staged).values()))
        require(receipt["baseline_target_empty"], "baseline target not empty")
        sandbox.open(REMOTE_FILE)
        receipt["first_visible_window_title"] = wait_for_workbook(sandbox)
        screen("opened")
        if "Tip of the Day" in receipt["first_visible_window_title"]:
            sandbox.left_click(880, 535)  # First-run LibreOffice modal.
            receipt["actions"].append({"type": "click", "x": 880, "y": 535,
                                       "purpose": "dismiss_first_run_tip"})
            time.sleep(1)
        require("Multiply_Time_Number.xlsx - LibreOffice Calc" in active_window_title(sandbox),
                "workbook is not the active visible window")
        screen("ready")
        address = TARGET_CELL if attempt == "positive" else "E4"
        sandbox.left_click(54, 171)  # Calc's visible Name Box.
        sandbox.press(["ctrl", "a"])
        sandbox.write(address)
        sandbox.press("enter")
        time.sleep(0.3)
        receipt["actions"].extend([
            {"type": "click", "x": 54, "y": 171, "purpose": "name_box"},
            {"type": "press", "keys": ["ctrl", "a"]},
            {"type": "write", "text": address, "purpose": "selected_cell_address"},
            {"type": "press", "keys": ["enter"]},
        ])
        screen("cell_selected")
        sandbox.write(FORMULA)
        receipt["actions"].append({"type": "write", "sha256": sha(FORMULA.encode()),
                                   "chars": len(FORMULA)})
        sandbox.press("enter")
        receipt["actions"].append({"type": "press", "keys": ["enter"]})
        screen("edited_unsaved")
        sandbox.press(["ctrl", "s"])
        receipt["actions"].append({"type": "press", "keys": ["ctrl", "s"]})
        time.sleep(1.5)
        receipt["save_window_title"] = active_window_title(sandbox)
        screen("save_dialog")
        if "Confirm File Format" in receipt["save_window_title"]:
            sandbox.left_click(776, 519)  # Explicitly retain XLSX format.
            receipt["actions"].append({"type": "click", "x": 776, "y": 519,
                                       "purpose": "retain_xlsx_format"})
            time.sleep(2)
        require("Multiply_Time_Number.xlsx - LibreOffice Calc" in active_window_title(sandbox),
                "workbook did not return after save")
        screen("saved")
        saved = bytes(sandbox.files.read(REMOTE_FILE, format="bytes"))
        (output_dir / "saved.xlsx").write_bytes(saved)
        receipt["saved_state_sha256"] = sha(saved)
        receipt["pre_postconfig_saved_state_changed"] = saved != asset
        require(saved != asset, "GUI edit was not saved before evaluator postconfig")
        semantic = semantic_check(asset, saved, attempt=attempt)
        receipt["independent_verifier"] = semantic
        receipt["upstream_compare_table_score"] = official_score(source_root, output_dir / "saved.xlsx")
        expected_score = 1.0 if attempt == "positive" else 0.0
        require(receipt["upstream_compare_table_score"] == expected_score,
                "published evaluator did not discriminate this control")
        require(semantic["independent_accept"] == (attempt == "positive"),
                "independent saved-state guard did not discriminate this control")
        receipt["status"] = "control_passed"
    except Exception as error:
        receipt["status"] = "control_failed"
        receipt["error_type"] = type(error).__name__
        raise
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=8))
            except Exception as error:
                receipt["kill_check_error_type"] = type(error).__name__
            if receipt.get("is_running_after_kill") is not False:
                receipt["status"] = "control_failed_cleanup_unknown"
        save_receipt()
    require(receipt["status"] == "control_passed", "sandbox cleanup was not verified")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempt", choices=("positive", "wrong-cell"), required=True)
    args = parser.parse_args()
    receipt = execute(args.source_root, args.asset, args.out, args.attempt)
    print(json.dumps({"status": receipt["status"], "attempt": args.attempt,
                      "official_score": receipt.get("upstream_compare_table_score"),
                      "independent_accept": receipt.get("independent_verifier", {}).get("independent_accept"),
                      "receipt_sha256": sha((args.out / "receipt.json").read_bytes())}))


if __name__ == "__main__":
    main()
