"""Append-only, evaluator-private failure ledger for the GitLab GUI sweep."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path

from . import factory, runtime


PATH = runtime.PRIVATE / "gui-sweep-failures-v3.jsonl"
SCHEMA = "envloop-gitlab-gui-sweep-failure-v1"
STATUSES = {"development_gui_trio_failed", "driver_or_environment_failed",
            "cold_reset_or_verifier_failed"}


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()


def _read_locked(stream) -> list[dict]:
    stream.seek(0)
    content = stream.read().decode()
    if content and not content.endswith("\n"):
        raise RuntimeError("GitLab failure ledger ends with an incomplete record")
    result = []
    previous = "0" * 64
    for number, line in enumerate(content.splitlines(), start=1):
        item = json.loads(line)
        if (item.get("schema") != SCHEMA or item.get("seq") != number
                or item.get("previous_sha256") != previous
                or item.get("status") not in STATUSES):
            raise RuntimeError("GitLab failure ledger chain/schema differs")
        digest = item.get("entry_sha256")
        expected = hashlib.sha256(_canonical({key: value for key, value in item.items()
                                              if key != "entry_sha256"})).hexdigest()
        if digest != expected:
            raise RuntimeError("GitLab failure ledger entry digest differs")
        result.append(item)
        previous = digest
    return result


def append(*, task_id: str, source_family_sha256: str,
           attempt_number: int, status: str, scores: list[float] | None,
           error_type: str | None, cold_reset_verified: bool) -> dict:
    if (not isinstance(task_id, str) or not task_id or
            not isinstance(source_family_sha256, str) or
            len(source_family_sha256) != 64 or status not in STATUSES or
            type(attempt_number) is not int or attempt_number <= 0 or
            type(cold_reset_verified) is not bool or
            (scores is not None and
             (type(scores) is not list or len(scores) != 3 or
              any(value not in (0.0, 1.0) for value in scores)))):
        raise ValueError("invalid GitLab failure ledger record")
    PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(PATH, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if os.fstat(descriptor).st_mode & 0o077:
            raise RuntimeError("GitLab failure ledger permissions are not restrictive")
        with os.fdopen(os.dup(descriptor), "r+b", closefd=True) as stream:
            rows = _read_locked(stream)
        prior = rows[-1]["entry_sha256"] if rows else "0" * 64
        record = {"schema": SCHEMA, "seq": len(rows) + 1,
                  "utc": datetime.now(timezone.utc).isoformat(),
                  "task_id": task_id,
                  "source_family_sha256": source_family_sha256,
                  "attempt_number": attempt_number,
                  "status": status, "scores": scores,
                  "error_type": error_type,
                  "cold_reset_verified": cold_reset_verified,
                  "previous_sha256": prior,
                  "official_final_admitted": False}
        record["entry_sha256"] = hashlib.sha256(_canonical(record)).hexdigest()
        os.write(descriptor, _canonical(record) + b"\n")
        os.fsync(descriptor)
        return {"entry_seq": record["seq"], "entry_sha256": record["entry_sha256"]}
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def audit() -> dict:
    if not PATH.exists():
        return {"schema": "envloop-gitlab-failure-ledger-public-v1",
                "entry_count": 0, "head_sha256": None,
                "all_records_hash_chained": True}
    descriptor = os.open(PATH, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            rows = _read_locked(stream)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    return {"schema": "envloop-gitlab-failure-ledger-public-v1",
            "entry_count": len(rows),
            "head_sha256": rows[-1]["entry_sha256"] if rows else None,
            "all_records_hash_chained": True}


def private_entries() -> list[dict]:
    """Read verified full entries for fail-closed index reconciliation only."""
    if not PATH.exists():
        return []
    descriptor = os.open(PATH, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            return _read_locked(stream)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
