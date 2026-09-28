"""Read-only host-owner and Odoo worker file-access preflight after chmod."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


SPLITS = ("train", "selection", "official_hidden")
SCHEMA = "envloop-odoo-owner-read-worker-preflight-v1"
WORKER_CHECK = """from pathlib import Path
import json, os
from factory import HERE, PRIVATE, local_config
from partition_factory import validate_scale_splits
split = os.environ['ODOO_EXPECT_SPLIT']
assert local_config()['ODOO_PARTITION'] == split
assert PRIVATE == HERE / 'private'
world = json.loads((PRIVATE / 'partition_cases.json').read_text())
assert world['split'] == split
sets = json.loads((PRIVATE / 'task_set_manifest.json').read_text())
validate_scale_splits(sets)
assert len(sets['official']) == 100
"""


def audit(workers_root: Path, code_dir: Path, src_dir: Path) -> dict:
    workers_root = Path(workers_root).resolve()
    code_dir = Path(code_dir).resolve()
    src_dir = Path(src_dir).resolve()
    if not workers_root.is_dir() or not code_dir.is_dir() or not src_dir.is_dir():
        raise RuntimeError("odoo_owner_read_paths_missing")
    counts = {}
    for split in SPLITS:
        private = workers_root / split / "private"
        files = directories = bytes_read = 0
        for path in (private, *private.rglob("*")):
            info = path.lstat()
            if (path.is_symlink() or info.st_uid != os.getuid() or
                    stat.S_IMODE(info.st_mode) & 0o077):
                raise RuntimeError("odoo_private_path_not_owner_only")
            if path.is_dir():
                if not os.access(path, os.R_OK | os.X_OK):
                    raise RuntimeError("odoo_private_directory_unreadable")
                directories += 1
            elif path.is_file():
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        bytes_read += len(chunk)
                files += 1
            else:
                raise RuntimeError("odoo_private_special_file")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(code_dir), str(src_dir)))
        env["ENVLOOP_ODOO_WORKER_DIR"] = str(workers_root / split)
        env["ODOO_EXPECT_SPLIT"] = split
        result = subprocess.run([sys.executable, "-c", WORKER_CHECK], env=env,
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError("odoo_worker_python_file_preflight_failed")
        counts[split] = {"files_owner_read": files,
                         "directories_owner_traversed": directories,
                         "bytes_owner_read": bytes_read,
                         "task_manifest_official_identity_count": 100}
    return {"schema": SCHEMA,
            "status": "owner_only_and_worker_python_read_preflight_passed",
            "by_split": counts,
            "docker_calls": 0, "provider_calls": 0,
            "official_final_tasks_admitted": 0, "model_attempts": 0}


def write_private(path: Path, report: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise RuntimeError("odoo_owner_read_receipt_parent_not_private")
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers-root", type=Path, required=True)
    parser.add_argument("--code-dir", type=Path, required=True)
    parser.add_argument("--src-dir", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.workers_root, args.code_dir, args.src_dir)
    print(json.dumps({**report,
                      "private_receipt_sha256": write_private(args.private_out, report)},
                     sort_keys=True))
