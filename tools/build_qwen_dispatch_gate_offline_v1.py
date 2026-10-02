"""Publish a field-limited, reproducible offline Qwen dispatch-gate receipt.

The focused suite uses fake providers. Python socket connections are blocked
and provider credentials are removed before it starts. No benchmark campaign,
application, model training, or final task is opened by this builder.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evidence/qwen38-dispatch-gate-offline-2026-09-28.json"
PUBLIC_TOY = (
    "docs/evidence/tinker-qwen38-vision-clean-runtime-2026-09-28.json")
SOURCE_PATHS = (
    "src/cursibench/full_study_campaign_dispatch_v1.py",
    "src/cursibench/full_study_qwen_runtime_gate_v1.py",
    "src/cursibench/full_study_shared_base_execution_v1.py",
    "src/cursibench/full_study_shared_base_selection_v1.py",
    "tools/verify_qwen38_training_runtime_v1.py",
    "runtime/qwen38-vision/runtime-spec.json",
    "runtime/qwen38-vision/requirements.lock",
)
TEST_PATHS = (
    "tests/test_full_study_qwen_runtime_gate_v1.py",
    "tests/test_full_study_campaign_dispatch_v1.py",
    "tests/test_full_study_shared_base_selection_v1.py",
    "tests/test_full_study_shared_base_execution_v1.py",
    "tests/shared_base_selection_fixture.py",
    "tests/test_qwen_dispatch_gate_offline_evidence_v1.py",
)
TEST_MODULES = (
    "tests.test_full_study_qwen_runtime_gate_v1",
    "tests.test_full_study_campaign_dispatch_v1",
    "tests.test_full_study_shared_base_selection_v1",
    "tests.test_full_study_shared_base_execution_v1",
)
FOCUSED_TEST_COUNT = 44
SCHEMA = "cua-qwen38-dispatch-gate-offline-evidence-v1"
STATUS = "source_bound_fake_provider_pre_dispatch_tests_passed"
BUILDER = "tools/build_qwen_dispatch_gate_offline_v1.py"


class EvidenceError(ValueError):
    """Fixed diagnostic labels; no private task or provider bodies."""


def _require(value: bool, code: str) -> None:
    if not value:
        raise EvidenceError(code)


def _sha(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file() and not path.is_symlink(),
             "offline_evidence_source_missing_or_unsafe")
    return sha256(path.read_bytes()).hexdigest()


def _network_blocked_focused_suite() -> int:
    with tempfile.TemporaryDirectory(prefix="qwen-dispatch-offline-") as tmp:
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
            timeout=180, check=False)
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in [0-9.]+s", output)
    _require(result.returncode == 0 and match is not None and
             output.rstrip().endswith("OK") and
             "offline_suite_network_attempt" not in output,
             "offline_evidence_focused_suite_failed")
    count = int(match.group(1))
    _require(count == FOCUSED_TEST_COUNT,
             "offline_evidence_focused_test_count_changed")
    return count


def expected_receipt(*, focused_test_count: int) -> dict:
    _require(focused_test_count == FOCUSED_TEST_COUNT,
             "offline_evidence_focused_test_count_changed")
    return {
        "schema": SCHEMA,
        "status": STATUS,
        "public_toy_runtime_evidence": {
            "path": PUBLIC_TOY, "sha256": _sha(PUBLIC_TOY)},
        "source_sha256s": {path: _sha(path) for path in SOURCE_PATHS},
        "test_source_sha256s": {path: _sha(path) for path in TEST_PATHS},
        "builder_sha256": _sha(BUILDER),
        "focused_test_modules": list(TEST_MODULES),
        "focused_fake_provider_tests_passed": focused_test_count,
        "python_socket_connections_permitted_during_tests": False,
        "provider_credentials_supplied_to_tests": False,
        "real_provider_calls_by_builder": 0,
        "real_researcher_campaigns": 0,
        "official_final_task_admissions": 0,
        "official_final_model_outcomes": 0,
        "benchmark_score": None,
    }


def audit_receipt(receipt: object) -> dict:
    _require(type(receipt) is dict and
             receipt == expected_receipt(
                 focused_test_count=FOCUSED_TEST_COUNT),
             "offline_evidence_receipt_or_source_changed")
    return receipt


def main() -> None:
    _require(not OUTPUT.exists() and not OUTPUT.is_symlink(),
             "offline_evidence_output_exists")
    count = _network_blocked_focused_suite()
    receipt = expected_receipt(focused_test_count=count)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    audit_receipt(json.loads(OUTPUT.read_bytes()))
    print(json.dumps({"status": STATUS,
                      "focused_fake_provider_tests_passed": count,
                      "real_provider_calls_by_builder": 0},
                     sort_keys=True))


if __name__ == "__main__":
    main()
