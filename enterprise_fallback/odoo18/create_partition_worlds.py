"""Bootstrap three isolated local Odoo candidate worlds without printing secrets.

The live master seed, full task manifest, gold, actor credentials, database
dump and filestore archive stay under ignored local paths. Public receipts
contain hashes and counts only. A successful bootstrap is *not* task admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from factory import CODE_DIR
from partition_factory import SPLIT_COUNTS

WORKERS = CODE_DIR / "partition_workers"
PORTS = {"train": 8092, "selection": 8093, "evaluation_candidate": 8094}
PROJECTS = {"train": "envloop-odoo-train-v1",
            "selection": "envloop-odoo-selection-v1",
            "evaluation_candidate": "envloop-odoo-evaluation-v1"}


def _master_seed() -> str:
    WORKERS.mkdir(parents=True, exist_ok=True)
    path = WORKERS / "master-seed.txt"
    if not path.exists():
        path.write_text(secrets.token_hex(32) + "\n")
        path.chmod(0o600)
    value = path.read_text().strip()
    if len(value) < 32:
        raise RuntimeError("Private master seed is too short")
    return value


def bootstrap_one(split: str, master_seed: str) -> dict:
    worker = WORKERS / split
    worker.mkdir(parents=True, exist_ok=True)
    compose = worker / "compose.yaml"
    source_compose = CODE_DIR / "compose.yaml"
    if compose.exists() and compose.read_bytes() != source_compose.read_bytes():
        raise RuntimeError(f"Worker Compose digest drift: {split}")
    if not compose.exists():
        shutil.copyfile(source_compose, compose)
    prior = worker / "private" / "checkpoint_receipt.json"
    if prior.exists():
        raise RuntimeError(f"World {split} already has a checkpoint; refusing to reseed")
    env = os.environ.copy()
    env.update({"ENVLOOP_ODOO_WORKER_DIR": str(worker),
                "ODOO_PARTITION": split, "ODOO_WORLD_SEED": master_seed,
                "ODOO_PORT": str(PORTS[split]), "ODOO_PROJECT": PROJECTS[split]})
    try:
        completed = subprocess.run([sys.executable, str(CODE_DIR / "bootstrap.py")],
                                   cwd=CODE_DIR, env=env, check=True,
                                   capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        log = worker / "bootstrap-error.log"
        log.write_text(error.stderr)
        log.chmod(0o600)
        raise RuntimeError(f"Partition bootstrap failed; private diagnostic: {log}") from None
    report = json.loads(completed.stdout)
    receipt = report["fixture"]
    return {"split": split, "project": PROJECTS[split], "port": PORTS[split],
            "status": report["status"], "candidate_cases": sum(receipt["family_counts"].values()),
            "family_counts": receipt["family_counts"],
            "seed_sha256": receipt["master_seed_sha256"],
            "case_manifest_sha256": receipt["case_manifest_sha256"],
            "source_hash_manifest_sha256": receipt["source_hash_manifest_sha256"],
            "task_set_manifest_sha256": receipt["task_set_manifest_sha256"],
            "role_policy_sha256": receipt["role_policy_sha256"],
            "pinned_code_and_runtime_sha256": receipt["pinned_code_and_runtime_sha256"],
            "db_checkpoint_sha256": report["checkpoint"]["db_sha256"],
            "filestore_checkpoint_sha256": report["checkpoint"]["filestore_sha256"],
            "full_filestore_file_count": report["checkpoint"]["filestore_file_count"],
            "snapshot_counts": report["evaluator_scope_counts"],
            "role_scoped_actor_without_admin_group": receipt["actor_administrator_group_absent"],
            "official_final_tasks_admitted": 0}


def run(splits: list[str]) -> dict:
    seed = _master_seed()
    if any(part not in SPLIT_COUNTS for part in splits):
        raise ValueError("Unknown partition")
    report = {"schema": "envloop-odoo-isolated-partition-worlds-v1",
              "status": "candidate_bootstrap_not_gui_admission",
              "master_seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
              "worlds": []}
    for split in splits:
        row = bootstrap_one(split, seed)
        report["worlds"].append(row)
        public = WORKERS / "partition-worlds-receipt.json"
        public.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"split": split, "status": row["status"],
                          "candidate_cases": row["candidate_cases"],
                          "official_final_tasks_admitted": 0}), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=list(SPLIT_COUNTS), action="append")
    arguments = parser.parse_args()
    run(arguments.split or list(SPLIT_COUNTS))
