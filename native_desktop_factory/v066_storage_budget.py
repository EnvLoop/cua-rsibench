"""Durable private screenshot-byte and free-space gate for v0.6.6 reruns.

Every raw observation/predispatch/drift frame is reserved before writing. A
crash between reserve and write leaves an unresolved row and blocks further
dispatch; bytes are never silently released. No screenshot is discarded.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3


MAX_LANE_EVIDENCE_BYTES = 4 * 1024 ** 3
MIN_HOST_FREE_BYTES_AFTER_WRITE = 8 * 1024 ** 3


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    ledger = root / "storage-ledger.sqlite3"
    connection = sqlite3.connect(ledger, timeout=30)
    ledger.chmod(0o600)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("""CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY CHECK (id = 1), reserved_bytes INTEGER NOT NULL)""")
    connection.execute("INSERT OR IGNORE INTO budget(id,reserved_bytes) VALUES (1,0)")
    connection.execute("""CREATE TABLE IF NOT EXISTS evidence (
        path TEXT PRIMARY KEY, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('reserved','written')))""")
    connection.commit()
    return connection


def reserve_and_write(root: Path, path: Path, raw: bytes) -> dict:
    """Reserve bytes with a cross-process SQLite lock, then write one new file."""
    root = root.resolve()
    path = path.resolve()
    if not path.is_relative_to(root) or path == root or not raw:
        raise ValueError("Evidence file must be nonempty and under the private lane")
    relative = str(path.relative_to(root))
    sha = digest(raw)
    connection = _connect(root)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT bytes,sha256,status FROM evidence WHERE path=?", (relative,)).fetchone()
        if existing is not None or path.exists():
            raise ValueError("Refusing to overwrite private frame evidence")
        reserved = connection.execute(
            "SELECT reserved_bytes FROM budget WHERE id=1").fetchone()[0]
        if (reserved + len(raw) > MAX_LANE_EVIDENCE_BYTES
                or shutil.disk_usage(root).free - len(raw) <
                MIN_HOST_FREE_BYTES_AFTER_WRITE):
            raise ValueError("Private screenshot byte cap or host free-space floor reached")
        connection.execute("UPDATE budget SET reserved_bytes=? WHERE id=1",
                           (reserved + len(raw),))
        connection.execute("INSERT INTO evidence VALUES (?,?,?,?)",
                           (relative, len(raw), sha, "reserved"))
        connection.commit()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            import os
            os.fsync(stream.fileno())
        path.chmod(0o600)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE evidence SET status='written' WHERE path=?",
                           (relative,))
        connection.commit()
    finally:
        connection.close()
    return {"sha256": sha, "bytes": len(raw), "private_path": relative}


def audit(root: Path, *, verify_all_bytes: bool = False) -> dict:
    connection = _connect(root.resolve())
    try:
        rows = connection.execute(
            "SELECT path,bytes,sha256,status FROM evidence ORDER BY path").fetchall()
        reserved = connection.execute(
            "SELECT reserved_bytes FROM budget WHERE id=1").fetchone()[0]
    finally:
        connection.close()
    if reserved != sum(row[1] for row in rows) or reserved > MAX_LANE_EVIDENCE_BYTES:
        raise ValueError("Private evidence-byte ledger is inconsistent")
    unresolved = [row for row in rows if row[3] != "written"]
    if verify_all_bytes:
        for relative, size, sha, status in rows:
            path = root / relative
            if (status != "written" or not path.is_file()
                    or path.stat().st_size != size or digest(path.read_bytes()) != sha):
                raise ValueError("A retained raw private evidence file changed")
    return {
        "reserved_evidence_bytes": reserved,
        "retained_file_count": len(rows),
        "unresolved_write_count": len(unresolved),
        "evidence_cap_bytes": MAX_LANE_EVIDENCE_BYTES,
        "host_free_bytes": shutil.disk_usage(root).free,
        "host_free_floor_bytes": MIN_HOST_FREE_BYTES_AFTER_WRITE,
        "dispatch_storage_ready": not unresolved and
        shutil.disk_usage(root).free >= MIN_HOST_FREE_BYTES_AFTER_WRITE,
    }
