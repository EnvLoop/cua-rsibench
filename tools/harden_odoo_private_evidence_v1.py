"""Owner-only, evidence-preserving Odoo private-tree mode repair.

No Docker/browser/provider calls. The three cooperating Odoo worker locks are
held across the snapshot, chmod, and byte-for-byte verification. The pre-change
journal is written mode 0600 before the first chmod; failures retain it.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat


SPLITS = ("train", "selection", "official_hidden")
APPROVED_COMPOSE_SHA256 = "b68c4907d640d61c199893dd26fd065b8fdc3123d0e85fc5ae374b23aae4ba58"
SCHEMA = "envloop-odoo-private-evidence-mode-hardening-v1"


class HardeningError(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise HardeningError(reason)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot(path: Path, root: Path) -> dict:
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and
            (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) and
            info.st_uid == os.getuid(), "unsafe_or_foreign_private_path")
    is_dir = stat.S_ISDIR(info.st_mode)
    require(not (is_dir and os.path.ismount(path)), "private_path_is_mountpoint")
    if is_dir:
        names = sorted(entry.name for entry in path.iterdir())
        content_sha = hashlib.sha256("\0".join(names).encode()).hexdigest()
    else:
        content_sha = sha256_file(path)
    return {
        "relative_path": str(path.relative_to(root)),
        "kind": "directory" if is_dir else "file",
        "mode_before": format(stat.S_IMODE(info.st_mode), "04o"),
        "mode_after_target": "0700" if is_dir else "0600",
        "size_bytes": info.st_size,
        "sha256": content_sha,
        "sha256_basis": "sorted_direct_entry_names_nul_v1" if is_dir else "file_bytes",
        "device": info.st_dev,
        "inode": info.st_ino,
    }


def _check_same(path: Path, root: Path, row: dict, *, after: bool) -> None:
    current = _snapshot(path, root)
    for key in ("relative_path", "kind", "size_bytes", "sha256",
                "sha256_basis", "device", "inode"):
        require(current[key] == row[key], "private_evidence_path_or_bytes_changed")
    expected = row["mode_after_target"] if after else row["mode_before"]
    require(current["mode_before"] == expected,
            "private_evidence_mode_changed_during_hardening")


def _check_no_bind_mount(compose: Path, root: Path) -> str:
    require(compose.is_file() and not compose.is_symlink() and
            sha256_file(compose) == APPROVED_COMPOSE_SHA256,
            "odoo_compose_source_not_approved")
    text = compose.read_text()
    # The approved file has named Docker volumes only. This textual check
    # additionally blocks a future host bind without a new reviewed digest.
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("- ")]
    volume_lines = [line[2:] for line in lines if ":/" in line]
    require(set(volume_lines) == {"pgdata:/var/lib/postgresql/data",
                                  "filestore:/var/lib/odoo"} and
            "type: bind" not in text and
            "partition_workers" not in text and
            not any(os.path.ismount(root / split / "private") for split in SPLITS),
            "odoo_private_tree_bind_mount_not_excluded")
    return sha256_file(compose)


def _event_log_balanced(path: Path) -> bool:
    require(path.is_file() and not path.is_symlink(), "worker_lease_log_missing")
    balances = {}
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            raise HardeningError("worker_lease_log_invalid") from None
        require(type(event) is dict and
                event.get("event") in ("acquired", "released") and
                event.get("operation") and type(event.get("pid")) is int,
                "worker_lease_log_invalid")
        key = (event["pid"], event["operation"])
        balances[key] = balances.get(key, 0) + (1 if event["event"] == "acquired" else -1)
        require(balances[key] >= 0, "worker_lease_log_unbalanced")
    return bool(balances) and all(value == 0 for value in balances.values())


def _hold_idle_locks(stack: ExitStack, root: Path) -> None:
    for split in SPLITS:
        private = root / split / "private"
        lock = private / "worker-operation.lock"
        require(private.is_dir() and not private.is_symlink() and
                lock.is_file() and not lock.is_symlink(),
                "odoo_private_worker_or_lock_missing")
        fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        stack.callback(os.close, fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HardeningError("odoo_worker_lease_active") from None
        stack.callback(fcntl.flock, fd, fcntl.LOCK_UN)
        require(lock.stat().st_size == 0 and
                _event_log_balanced(private / "worker-lease-events.jsonl"),
                "odoo_worker_not_cleanly_idle")


def _write_private(path: Path, value: dict) -> str:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not parent.is_symlink() and
            stat.S_IMODE(parent.stat().st_mode) & 0o077 == 0 and
            parent.stat().st_uid == os.getuid(),
            "hardening_journal_parent_not_private")
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    require(stat.S_IMODE(path.stat().st_mode) == 0o600,
            "hardening_journal_mode_invalid")
    return hashlib.sha256(raw).hexdigest()


def harden(workers_root: Path, *, journal_before: Path,
           journal_after: Path, compose: Path) -> dict:
    root = Path(workers_root).absolute()
    require(root.is_dir() and not root.is_symlink() and
            not journal_before.exists() and not journal_after.exists() and
            journal_before != journal_after,
            "hardening_paths_invalid")
    compose_sha = _check_no_bind_mount(Path(compose), root)
    with ExitStack() as stack:
        _hold_idle_locks(stack, root)
        affected = []
        by_split = {}
        for split in SPLITS:
            private = root / split / "private"
            counts = {"directories": 0, "files": 0}
            for path in (private, *private.rglob("*")):
                row = _snapshot(path, root)
                if int(row["mode_before"], 8) & 0o077:
                    affected.append(row)
                    counts["directories" if row["kind"] == "directory" else "files"] += 1
            by_split[split] = counts
        require(len(affected) == 54 and
                by_split == {
                    "train": {"directories": 8, "files": 23},
                    "selection": {"directories": 3, "files": 8},
                    "official_hidden": {"directories": 4, "files": 8},
                }, "unexpected_private_mode_inventory")
        before = {
            "schema": SCHEMA, "phase": "snapshot_before_first_chmod",
            "compose_sha256": compose_sha,
            "three_worker_leases_held_idle": True,
            "affected_by_split": by_split,
            "affected_paths": affected,
        }
        before_sha = _write_private(journal_before, before)
        # Recheck each inode and byte hash immediately before its mode change.
        # Files first, then deepest directories, so every parent remains traversable.
        ordered = sorted(affected, key=lambda row: (
            row["kind"] == "directory",
            -len(Path(row["relative_path"]).parts)))
        for row in ordered:
            path = root / row["relative_path"]
            _check_same(path, root, row, after=False)
            os.chmod(path, int(row["mode_after_target"], 8))
            _check_same(path, root, row, after=True)
        for row in affected:
            _check_same(root / row["relative_path"], root, row, after=True)
        remaining = {"directories": 0, "files": 0}
        for split in SPLITS:
            private = root / split / "private"
            for path in (private, *private.rglob("*")):
                row = _snapshot(path, root)
                if int(row["mode_before"], 8) & 0o077:
                    remaining["directories" if row["kind"] == "directory" else "files"] += 1
        require(remaining == {"directories": 0, "files": 0},
                "private_mode_hardening_incomplete")
        after = {
            "schema": SCHEMA, "phase": "verified_after_chmod",
            "before_journal_sha256": before_sha,
            "compose_sha256": compose_sha,
            "affected_by_split": by_split,
            "affected_paths_verified_byte_identical": len(affected),
            "remaining_permissive_modes": remaining,
            "three_worker_leases_held_idle_through_verification": True,
        }
        after_sha = _write_private(journal_after, after)
    return {
        "schema": SCHEMA,
        "status": "owner_only_modes_and_affected_bytes_verified",
        "affected_by_split": by_split,
        "affected_paths_verified_byte_identical": len(affected),
        "remaining_permissive_modes": remaining,
        "before_journal_sha256": before_sha,
        "after_journal_sha256": after_sha,
        "compose_sha256": compose_sha,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers-root", type=Path, required=True)
    parser.add_argument("--compose", type=Path, required=True)
    parser.add_argument("--journal-before", type=Path, required=True)
    parser.add_argument("--journal-after", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    require(args.execute, "explicit_execute_flag_required")
    print(json.dumps(harden(args.workers_root, journal_before=args.journal_before,
                            journal_after=args.journal_after, compose=args.compose),
                     sort_keys=True))
