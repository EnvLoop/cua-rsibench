"""Publish source-bound GitLab train teacher-worker *offline* evidence only."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from gitlab_world import teacher_episode_worker_v066 as worker


ROOT = Path(__file__).resolve().parents[1]
TEST = "tests/test_gitlab_teacher_episode_worker_v066.py"
OUTPUT = ROOT / "docs/evidence/gitlab-v066-teacher-worker-offline-2026-09-28.json"


def digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("public_worker_source_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    with tempfile.TemporaryDirectory(prefix="gitlab-teacher-no-docker-") as tmp:
        bin_dir = Path(tmp)
        marker = bin_dir / "forbidden-command-called"
        for name in ("docker", "colima"):
            executable = bin_dir / name
            executable.write_text(
                '#!/bin/sh\nprintf x >> "$GITLAB_TEST_EXEC_MARKER"\nexit 97\n')
            executable.chmod(0o700)
        result = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_gitlab_teacher_episode_worker_v066", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=90,
            env={**os.environ,
                 "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "src"),
                 "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                 "GITLAB_TEST_EXEC_MARKER": str(marker),
                 "OPENAI_API_KEY": ""},
            check=False)
        if marker.exists():
            raise ValueError("gitlab_teacher_test_reached_docker_or_colima")
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in ", output)
    if result.returncode or match is None or "\nOK\n" not in output:
        raise ValueError("gitlab_teacher_worker_synthetic_tests_failed")
    return {
        "schema": "envloop-gitlab-v066-teacher-worker-offline-v1",
        "status": "implemented_fake_provider_only_not_live",
        "cell_id": "gitlab",
        "action_profile": worker.ACTION_PROFILE_VERSION,
        "original_software": "GitLab CE 18.5",
        "original_surface": worker.GitLabTrainEpisodeWorker.original_surface,
        "requires_e2b": worker.GitLabTrainEpisodeWorker.requires_e2b,
        "live_default_enabled": False,
        "train_partition_only": True,
        "independent_readback": "PostgreSQL and Git",
        "cold_reset": "immutable-volume overlayfs before and after",
        "runtime_sha256": worker.runtime_sha256(),
        "verifier_sha256": worker.verifier_sha256(),
        "adapter_sha256": worker.adapter_sha256(),
        "runtime_source_sha256s": worker.source_hashes(),
        "test_source_sha256": digest(ROOT / TEST),
        "receipt_builder_sha256": digest(
            ROOT / "tools/build_gitlab_teacher_worker_offline_v066.py"),
        "test_count": int(match.group(1)),
        "test_status": "passed_synthetic_only",
        "provider_calls": 0,
        "e2b_calls": 0,
        "docker_calls": 0,
        "live_teacher_episodes": 0,
        "official_final_admissions": 0,
        "researcher_campaigns": 0,
    }


def main() -> None:
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise FileExistsError("gitlab_teacher_offline_receipt_already_exists")
    evidence = build()
    OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: evidence[key] for key in (
        "test_count", "provider_calls", "e2b_calls", "docker_calls",
        "live_teacher_episodes", "official_final_admissions")}, sort_keys=True))


if __name__ == "__main__":
    main()
