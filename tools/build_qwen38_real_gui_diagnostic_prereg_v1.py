"""Publish the source-bound blocked-before-paid Qwen GUI diagnostic prereg.

This reopens private real-GUI train evidence, then runs only fake-provider
tests with Python socket connections blocked and no inherited credentials.
It never constructs a Tinker client or a benchmark score.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from cursibench import qwen38_real_gui_diagnostic_v1 as diagnostic


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evidence/qwen38-real-gui-diagnostic-prereg-2026-09-28.json"
SCHEMA = "envloop-qwen38-real-gui-diagnostic-prereg-public-v1"
IMPRESS_RECEIPT = (
    "docs/evidence/desktop-v066-public-train-sft-render-2026-09-28.json")
RATIFICATION_RECEIPT = (
    "docs/evidence/full-study-v066-caret-amended-control-ratification-2026-09-28.json")
SOURCES = (
    "src/cursibench/qwen38_real_gui_diagnostic_v1.py",
    "src/cursibench/qwen38_real_gui_diagnostic_run_v1.py",
    "src/cursibench/qwen38_real_gui_diagnostic_usage_v1.py",
    "tools/run_qwen38_real_gui_diagnostic_v1.py",
    "tools/audit_qwen38_real_gui_diagnostic_usage_v1.py",
    "tools/export_desktop_v066_train_sft_v1.py",
    "src/cursibench/scale_action_output_v066.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "runtime/qwen38-vision/real-gui-diagnostic-prereg-v1.json",
    "tests/test_qwen38_real_gui_diagnostic_v1.py",
    "tests/test_qwen38_real_gui_diagnostic_usage_v1.py",
    "tests/test_qwen38_real_gui_diagnostic_prereg_evidence_v1.py",
)
TEST_MODULES = (
    "tests.test_qwen38_real_gui_diagnostic_v1",
    "tests.test_qwen38_real_gui_diagnostic_usage_v1",
)
TEST_COUNT = 16
BLOCKED_MANIFEST_SHA256 = (
    "8baaf0167a4faafec1b689e406babac601ad192a9d5a8ca8a4bbb2e36bb4686c")
RATIFICATION_SHA256 = (
    "49f6a047313c4b1c30fbe357677dbf33cb692614d7e273fe57b088e435c46359")


def _sha(relative: str) -> str:
    path = ROOT / relative
    diagnostic.require(path.is_file() and not path.is_symlink(),
                       "diagnostic_prereg_public_source_missing")
    return diagnostic.digest(path.read_bytes())


def focused_fake_tests() -> int:
    with tempfile.TemporaryDirectory(prefix="qwen-real-gui-prereg-") as tmp:
        guard = Path(tmp) / "sitecustomize.py"
        guard.write_text(
            "import socket\n"
            "def _blocked(*args, **kwargs):\n"
            "    raise RuntimeError('offline_suite_network_attempt')\n"
            "socket.socket.connect = _blocked\n"
            "socket.socket.connect_ex = _blocked\n")
        env = {
            "HOME": tmp, "XDG_CONFIG_HOME": tmp, "TMPDIR": tmp,
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.pathsep.join((tmp, str(ROOT),
                                            str(ROOT / "src"))),
            "PYTHONNOUSERSITE": "1", "PYTHONWARNINGS": "ignore",
        }
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *TEST_MODULES],
            cwd=ROOT, env=env, capture_output=True, text=True,
            timeout=120, check=False)
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in [0-9.]+s", output)
    diagnostic.require(result.returncode == 0 and match is not None and
                       output.rstrip().endswith("OK") and
                       "offline_suite_network_attempt" not in output and
                       int(match.group(1)) == TEST_COUNT,
                       "diagnostic_prereg_fake_tests_failed")
    return TEST_COUNT


def expected_receipt() -> dict:
    prereg, prereg_sha = diagnostic.load_prereg(ROOT)
    return {
        "schema": SCHEMA,
        "status": "one_real_gui_train_source_validated_blocked_before_paid",
        "model": diagnostic.MODEL,
        "action_profile": diagnostic.ACTION_PROFILE,
        "prereg_sha256": prereg_sha,
        "source_manifest_sha256": BLOCKED_MANIFEST_SHA256,
        "ratification_sha256": RATIFICATION_SHA256,
        "validated_train_source_workflows": {"impress": 1},
        "validated_train_source_tasks": 1,
        "required_distinct_train_tasks": prereg["minimum_distinct_tasks"],
        "required_distinct_train_workflows": prereg[
            "minimum_distinct_workflows"],
        "optimizer_steps_preregistered": prereg["optimizer_steps"],
        "batch_size_preregistered": prereg["batch_size"],
        "pricing_quote_is_dispatch_gate": False,
        "provider_invoice_required_for_cost_claim": True,
        "cost_audit_status": "pending_no_paid_diagnostic_run",
        "blocked_reason": "diagnostic_distinct_train_workflows_not_ready",
        "impress_public_train_render_receipt": {
            "path": IMPRESS_RECEIPT, "sha256": _sha(IMPRESS_RECEIPT)},
        "caret_amended_public_ratification_receipt": {
            "path": RATIFICATION_RECEIPT,
            "sha256": _sha(RATIFICATION_RECEIPT)},
        "source_sha256s": {name: _sha(name) for name in SOURCES},
        "builder_sha256": _sha(
            "tools/build_qwen38_real_gui_diagnostic_prereg_v1.py"),
        "fake_provider_test_count": TEST_COUNT,
        "python_socket_connections_permitted_during_tests": False,
        "provider_credentials_supplied_to_tests": False,
        "paid_tinker_calls": 0,
        "selection_tasks_used": 0,
        "final_tasks_used": 0,
        "official_researcher_campaigns": 0,
        "official_model_outcomes": 0,
        "benchmark_score": None,
    }


def audit_receipt(value: object) -> dict:
    diagnostic.require(type(value) is dict and
                       value == expected_receipt(),
                       "diagnostic_prereg_public_receipt_or_source_changed")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    args = parser.parse_args()
    diagnostic.require(not OUTPUT.exists() and not OUTPUT.is_symlink(),
                       "diagnostic_prereg_public_output_exists")
    prereg, _ = diagnostic.load_prereg(ROOT)
    episodes, manifest_sha, rat_sha = diagnostic.load_sources(
        ROOT, args.sources, args.ratification)
    try:
        diagnostic.split_tasks(episodes, prereg)
    except diagnostic.DiagnosticError as exc:
        diagnostic.require(str(exc) ==
                           "diagnostic_distinct_train_workflows_not_ready",
                           "diagnostic_prereg_unexpected_blocker")
    else:
        raise diagnostic.DiagnosticError(
            "diagnostic_prereg_now_ready_requires_new_dated_evidence")
    counts = dict(sorted(Counter(row["workflow"]
                                 for row in episodes).items()))
    diagnostic.require(manifest_sha == BLOCKED_MANIFEST_SHA256 and
                       rat_sha == RATIFICATION_SHA256 and
                       counts == {"impress": 1},
                       "diagnostic_prereg_source_binding_changed")
    focused_fake_tests()
    value = expected_receipt()
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    audit_receipt(json.loads(OUTPUT.read_bytes()))
    print(json.dumps({"status": value["status"],
                      "validated_train_source_tasks": 1,
                      "fake_provider_test_count": TEST_COUNT,
                      "paid_tinker_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
