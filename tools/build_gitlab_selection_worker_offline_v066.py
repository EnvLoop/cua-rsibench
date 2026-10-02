"""Publish source-bound GitLab 20-task selection-worker offline evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from gitlab_world import selection_worker_v066 as worker


ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "tests/test_gitlab_selection_worker_v066.py",
    "tests/test_gitlab_selection_oracle_v066.py",
)
OUTPUT = ROOT / "docs/evidence/gitlab-v066-selection-worker-offline-2026-09-28.json"


def digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("public_selection_source_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    with tempfile.TemporaryDirectory(prefix="gitlab-selection-no-docker-") as tmp:
        bin_dir = Path(tmp)
        marker = bin_dir / "forbidden-command-called"
        for name in ("docker", "colima"):
            executable = bin_dir / name
            executable.write_text(
                '#!/bin/sh\nprintf x >> "$GITLAB_TEST_EXEC_MARKER"\nexit 97\n')
            executable.chmod(0o700)
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_gitlab_selection_worker_v066",
             "tests.test_gitlab_selection_oracle_v066", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
            env={**os.environ,
                 "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "src"),
                 "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                 "GITLAB_TEST_EXEC_MARKER": str(marker),
                 "TINKER_API_KEY": "", "OPENAI_API_KEY": ""},
            check=False)
        if marker.exists():
            raise ValueError("gitlab_selection_test_reached_docker_or_colima")
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in ", output)
    if result.returncode or match is None or "\nOK\n" not in output:
        raise ValueError("gitlab_selection_synthetic_tests_failed")
    return {
        "schema": "envloop-gitlab-v066-selection-worker-offline-v1",
        "status": "implemented_fake_provider_only_not_live",
        "cell_id": "gitlab",
        "action_profile": worker.ACTION_PROFILE_VERSION,
        "original_software": "GitLab CE 18.5",
        "selection_result_schema": worker.RESULT_SCHEMA,
        "private_paid_task_ledger_schema":
            "envloop-gitlab-v066-selection-paid-task-ledger-v1",
        "selection_task_count_in_fake_complete_attempt": 20,
        "task_bound_application_paid_attempts_in_fake_complete_attempt": 20,
        "task_bound_tinker_paid_attempts_in_fake_complete_attempt": 20,
        "runtime_sha256": worker.runtime_sha256(),
        "verifier_sha256": worker.verifier_sha256(),
        "adapter_sha256": worker.adapter_sha256(),
        "runtime_source_sha256s": worker.source_hashes(),
        "test_source_sha256s": {path: digest(ROOT / path) for path in TESTS},
        "receipt_builder_sha256": digest(
            ROOT / "tools/build_gitlab_selection_worker_offline_v066.py"),
        "test_count": int(match.group(1)),
        "test_status": "passed_synthetic_only",
        "docker_calls": 0,
        "e2b_calls": 0,
        "external_provider_calls": 0,
        "live_selection_attempts": 0,
        "official_final_admissions": 0,
        "researcher_campaigns": 0,
        "dispatcher_self_hosted_paid_mapping_required": True,
        "provider_invoice_reconciled": False,
    }


def main() -> None:
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise FileExistsError("gitlab_selection_offline_receipt_already_exists")
    value = build()
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value[key] for key in (
        "test_count", "docker_calls", "e2b_calls",
        "external_provider_calls", "live_selection_attempts",
        "official_final_admissions")}, sort_keys=True))


if __name__ == "__main__":
    main()
