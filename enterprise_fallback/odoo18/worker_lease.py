"""Nonblocking, reentrant lease for one local Odoo worker.

All official GUI/reset/evaluator entry points must cooperate on the same
worker-private path. Contention fails closed instead of allowing a second
process to drop a database while the first observes or mutates it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import time
from typing import Iterator

from factory import PRIVATE

_NAMES = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_OWNED: dict[Path, tuple[int, int, int]] = {}


class WorkerBusyError(RuntimeError):
    pass


def _record_event(directory: Path, event: str, operation: str, pid: int) -> None:
    path = directory / "worker-lease-events.jsonl"
    row = {"event": event, "operation": operation, "pid": pid,
           "at_utc": datetime.now(timezone.utc).isoformat()}
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(handle, (json.dumps(row, sort_keys=True) + "\n").encode())
        os.fsync(handle)
    finally:
        os.close(handle)


def require_worker_lease(*, root: Path | None = None) -> None:
    directory = (root or PRIVATE).resolve()
    owner = _OWNED.get(directory / "worker-operation.lock")
    if owner is None or owner[2] != os.getpid() or owner[1] < 1:
        raise WorkerBusyError("GUI operation requires an exclusive Odoo worker lease")


@contextmanager
def exclusive_worker_operation(operation: str, *, root: Path | None = None) -> Iterator[None]:
    if not _NAMES.fullmatch(operation):
        raise ValueError("Invalid worker operation name")
    directory = (root or PRIVATE).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "worker-operation.lock"
    owner = _OWNED.get(path)
    pid = os.getpid()
    if owner is not None and owner[2] == pid:
        fd, depth, _ = owner
        _OWNED[path] = (fd, depth + 1, pid)
        try:
            yield
        finally:
            _, depth, _ = _OWNED[path]
            _OWNED[path] = (fd, depth - 1, pid)
        return
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise WorkerBusyError("Odoo worker already has an active GUI/reset operation") from None
        os.ftruncate(fd, 0)
        os.write(fd, (json.dumps({"pid": pid, "operation": operation,
                                  "started_unix": time.time()}) + "\n").encode())
        os.fsync(fd)
        _OWNED[path] = (fd, 1, pid)
        _record_event(directory, "acquired", operation, pid)
        try:
            yield
        finally:
            current = _OWNED.pop(path, None)
            if current is None or current[0] != fd:
                raise RuntimeError("Odoo worker lease state corrupted")
            _record_event(directory, "released", operation, pid)
            os.ftruncate(fd, 0)
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
