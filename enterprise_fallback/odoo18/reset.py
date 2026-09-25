"""Cold checkpoint and full DB/filestore restore for a single local worker.

This intentionally stops the Odoo web process during both operations.  A
future multi-worker study must assign a distinct ODOO_PROJECT and port to each
worker, with a separate checkpoint and evaluator namespace per project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
import xmlrpc.client
from pathlib import Path

from factory import HERE, PRIVATE, local_config
from verify import snapshot
from worker_lease import exclusive_worker_operation

ODOO_IMAGE = "odoo@sha256:478065867b945579649373aa4cca3b56f7b74daf0522e5fdf85e7d1262e11d39"
FILESTORE_SCAN = (
    "import hashlib,json,os; root='/filestore'; out={}; "
    "[(out.__setitem__(os.path.relpath(os.path.join(base,name),root), "
    "hashlib.sha256(open(os.path.join(base,name),'rb').read()).hexdigest())) "
    "for base,dirs,files in os.walk(root) for name in files]; "
    "print(json.dumps(out,sort_keys=True))"
)


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=HERE, check=True, **kwargs)


def compose(*args: str) -> list[str]:
    return ["docker", "compose", "--env-file", ".env", *args]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def filestore_manifest(volume: str) -> dict[str, str]:
    result = run(["docker", "run", "--rm", "--volume", f"{volume}:/filestore:ro",
                  "--entrypoint", "python3", ODOO_IMAGE, "-c", FILESTORE_SCAN],
                 capture_output=True, text=True)
    return json.loads(result.stdout)


def wait_web(timeout_s: int = 90) -> None:
    port = int(local_config().get("ODOO_PORT", "8078"))
    url = f"http://127.0.0.1:{port}/web/login"
    until = time.monotonic() + timeout_s
    while time.monotonic() < until:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    common = xmlrpc.client.ServerProxy(
                        f"http://127.0.0.1:{port}/xmlrpc/2/common", allow_none=True
                    )
                    version = common.version()
                    if str(version.get("server_version", "")).startswith("18.0"):
                        return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Odoo web login did not become ready")


def checkpoint() -> dict:
    with exclusive_worker_operation("checkpoint"):
        return _checkpoint_unlocked()


def _checkpoint_unlocked() -> dict:
    PRIVATE.mkdir(exist_ok=True)
    db_dump = PRIVATE / "baseline.pgcustom"
    fs_dump = PRIVATE / "baseline-filestore.tgz"
    if db_dump.exists() or fs_dump.exists():
        raise RuntimeError("Existing checkpoint cannot be overwritten")
    expected = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
    before = snapshot()
    if before != expected:
        raise RuntimeError("The database no longer matches its frozen baseline")
    project = local_config().get("ODOO_PROJECT", "envloop-odoo-fallback")
    volume = project + "_filestore"
    run(compose("stop", "web"), capture_output=True, text=True)
    try:
        manifest = filestore_manifest(volume)
        (PRIVATE / "baseline-filestore-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        with db_dump.open("wb") as out:
            run(compose("exec", "-T", "db", "pg_dump", "-U", "odoo", "-d", "bench", "-Fc"), stdout=out)
        with fs_dump.open("wb") as out:
            run(["docker", "run", "--rm", "--volume", f"{volume}:/filestore:ro",
                 "--entrypoint", "tar", ODOO_IMAGE, "-C", "/filestore", "-czf", "-", "."], stdout=out)
    finally:
        run(compose("up", "-d", "web"), capture_output=True, text=True)
        wait_web()
    receipt = {
        "status": "isolated_local_checkpoint",
        "db_sha256": file_hash(db_dump),
        "filestore_sha256": file_hash(fs_dump),
        "db_bytes": db_dump.stat().st_size,
        "filestore_bytes": fs_dump.stat().st_size,
        "filestore_file_count": len(manifest),
        "filestore_manifest_sha256": file_hash(PRIVATE / "baseline-filestore-manifest.json"),
        "post_restart_business_snapshot_equal": snapshot() == expected,
    }
    (PRIVATE / "checkpoint_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def restore() -> dict:
    with exclusive_worker_operation("restore"):
        return _restore_unlocked()


def _restore_unlocked() -> dict:
    db_dump = PRIVATE / "baseline.pgcustom"
    fs_dump = PRIVATE / "baseline-filestore.tgz"
    receipt = json.loads((PRIVATE / "checkpoint_receipt.json").read_text())
    if file_hash(db_dump) != receipt["db_sha256"] or file_hash(fs_dump) != receipt["filestore_sha256"]:
        raise RuntimeError("Checkpoint digest mismatch; refusing restore")
    expected = json.loads((PRIVATE / "baseline_snapshot.json").read_text())
    project = local_config().get("ODOO_PROJECT", "envloop-odoo-fallback")
    volume = project + "_filestore"
    manifest_path = PRIVATE / "baseline-filestore-manifest.json"
    if file_hash(manifest_path) != receipt["filestore_manifest_sha256"]:
        raise RuntimeError("Filestore manifest digest mismatch; refusing restore")
    expected_files = json.loads(manifest_path.read_text())
    run(compose("stop", "web"), capture_output=True, text=True)
    try:
        run(compose("exec", "-T", "db", "dropdb", "-U", "odoo", "--if-exists", "bench"), capture_output=True)
        run(compose("exec", "-T", "db", "createdb", "-U", "odoo", "bench"), capture_output=True)
        with db_dump.open("rb") as source:
            run(compose("exec", "-T", "db", "pg_restore", "-U", "odoo", "-d", "bench", "--no-owner"),
                stdin=source, capture_output=True)
        with fs_dump.open("rb") as source:
            run(["docker", "run", "--rm", "-i", "--volume", f"{volume}:/filestore",
                 "--entrypoint", "sh", ODOO_IMAGE, "-c",
                 "find /filestore -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf - -C /filestore"],
                stdin=source, capture_output=True)
        files_equal = filestore_manifest(volume) == expected_files
        if not files_equal:
            raise RuntimeError("Physical filestore contents differ from the frozen manifest")
    finally:
        run(compose("up", "-d", "web"), capture_output=True, text=True)
        wait_web()
    observed = snapshot()
    result = {
        "status": "restored" if observed == expected else "restore_mismatch",
        "business_snapshot_equal": observed == expected,
        "physical_filestore_equal_before_web_restart": files_equal,
        "db_sha256": receipt["db_sha256"],
        "filestore_sha256": receipt["filestore_sha256"],
    }
    if observed != expected:
        raise RuntimeError(json.dumps(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["checkpoint", "restore"])
    args = parser.parse_args()
    print(json.dumps(checkpoint() if args.action == "checkpoint" else restore(), indent=2))
