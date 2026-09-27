"""Publish source-bound *offline* shared-base selection protocol evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evidence/shared-base-selection-gate-offline-2026-09-28.json"
SOURCES = (
    "src/cursibench/full_study_pre_campaign_v1.py",
    "src/cursibench/full_study_matrix_v1.py",
    "src/cursibench/full_study_budget_v1.py",
    "src/cursibench/full_study_shared_base_selection_v1.py",
    "src/cursibench/full_study_selection_paid_coverage_v1.py",
    "src/cursibench/full_study_selection_environment_v1.py",
    "src/cursibench/full_study_campaign_dispatch_v1.py",
    "tools/full_study_campaign_dispatch_v1.py",
)
TESTS = (
    "tests/test_full_study_matrix_v1.py",
    "tests/test_full_study_budget_v1.py",
    "tests/test_full_study_shared_base_selection_v1.py",
    "tests/test_full_study_campaign_dispatch_v1.py",
    "tests/shared_base_selection_fixture.py",
)
TEST_MODULES = (
    "tests.test_full_study_matrix_v1",
    "tests.test_full_study_budget_v1",
    "tests.test_full_study_shared_base_selection_v1",
    "tests.test_full_study_campaign_dispatch_v1",
)


def digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("shared_base_source_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    with tempfile.TemporaryDirectory(prefix="shared-base-no-docker-") as tmp:
        bin_dir = Path(tmp)
        marker = bin_dir / "forbidden-command-called"
        for name in ("docker", "colima"):
            executable = bin_dir / name
            executable.write_text(
                '#!/bin/sh\nprintf x >> "$SHARED_BASE_TEST_EXEC_MARKER"\nexit 97\n')
            executable.chmod(0o700)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *TEST_MODULES, "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
            env={**os.environ,
                 "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "src"),
                 "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                 "SHARED_BASE_TEST_EXEC_MARKER": str(marker),
                 "TINKER_API_KEY": "", "OPENAI_API_KEY": ""},
            check=False)
        if marker.exists():
            raise ValueError("shared_base_test_reached_docker_or_colima")
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in ", output)
    if result.returncode or match is None or "\nOK\n" not in output:
        raise ValueError("shared_base_offline_tests_failed")
    return {
        "schema": "cua-full-study-shared-base-selection-offline-evidence-v1",
        "status": "protocol_gate_fake_provider_only_not_executed",
        "shared_base_selection_receipt_schema":
            "cua-full-study-shared-base-selection-receipt-v1",
        "reserved_shared_base_final_cells": 6,
        "separately_reserved_shared_base_selection_cells": 6,
        "researcher_campaign_count_declared": 24,
        "selection_task_count_per_cell": 20,
        "one_receipt_sha_reused_by_researchers_per_cell": 4,
        "per_cell_selection_bound":
            "full_frozen_100_task_base_final_cost_maximum",
        "source_sha256s": {path: digest(ROOT / path) for path in SOURCES},
        "test_source_sha256s": {path: digest(ROOT / path) for path in TESTS},
        "builder_sha256": digest(
            ROOT / "tools/build_shared_base_selection_gate_offline_v1.py"),
        "synthetic_test_count": int(match.group(1)),
        "docker_calls": 0, "e2b_calls": 0,
        "external_provider_calls": 0,
        "real_shared_base_selection_receipts": 0,
        "real_researcher_campaigns": 0,
        "official_final_model_attempts": 0,
    }


def main() -> None:
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise FileExistsError("shared_base_offline_evidence_already_exists")
    value = build()
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value[key] for key in (
        "synthetic_test_count", "real_shared_base_selection_receipts",
        "real_researcher_campaigns", "official_final_model_attempts")},
        sort_keys=True))


if __name__ == "__main__":
    main()
