"""Persist child stdout/stderr before a v4d controller may classify an attempt.

This module has no provider-create entrypoint. A future source-frozen controller
can use ``invoke_child_durable`` instead of the v3 buffered subprocess helper.
The byte streams and terminal metadata are private, exclusive, and fsynced
before the helper returns any status to its caller.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

from .v066_day_rollover_continuation_v3 import _sync_dir, _terminate_group, _write_new
from .v066_final_freeze import LEASE_SECONDS, digest

CHILD_MODULE = "native_desktop_factory.v066_day_rollover_durable_child_v4d"


def _flag(command: list[str], name: str) -> str:
    try:
        return command[command.index(name) + 1]
    except (ValueError, IndexError):
        raise ValueError(f"v4d child command lacks {name}") from None


def _attempt_dir(command: list[str]) -> Path:
    if len(command) < 3 or command[1:3] != ["-m", CHILD_MODULE]:
        raise ValueError("Only the source-bound v4d child may be launched")
    root = Path(_flag(command, "--attempts-root")).resolve()
    task_id = _flag(command, "--task-id")
    attempt = _flag(command, "--attempt")
    if (task_id in ("", ".", "..") or "/" in task_id or "\\" in task_id or
            attempt not in ("positive", "near-miss", "cold-reset")):
        raise ValueError("v4d child attempt path is not a roster leaf")
    path = (root / task_id / attempt).resolve()
    if (not path.is_relative_to(root) or not path.is_dir() or
            path.is_symlink() or path.stat().st_mode & 0o077 or
            not (path / "budget.json").is_file() or
            not (path / "intent.json").is_file()):
        raise ValueError("v4d child lacks exclusive private precreate intent")
    return path


def _invoke_to_files(command: list[str], attempt_dir: Path,
                     timeout_seconds: int) -> tuple[int | None, str, str, bool]:
    if timeout_seconds < 1:
        raise ValueError("Positive v4d child timeout required")
    stdout_path = attempt_dir / "child.stdout"
    stderr_path = attempt_dir / "child.stderr"
    terminal_path = attempt_dir / "child-output.json"
    if any(path.exists() for path in (stdout_path, stderr_path, terminal_path)):
        raise ValueError("v4d child output already exists; replay refused")
    out_fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    err_fd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    process = None
    timed_out = False
    spawn_error_type = None
    with os.fdopen(out_fd, "wb") as out_stream, os.fdopen(err_fd, "wb") as err_stream:
        try:
            process = subprocess.Popen(command, stdout=out_stream,
                                       stderr=err_stream, start_new_session=True)
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_group(process)
        except BaseException as exc:
            spawn_error_type = type(exc).__name__
            if process is not None:
                _terminate_group(process)
        finally:
            out_stream.flush()
            err_stream.flush()
            os.fsync(out_stream.fileno())
            os.fsync(err_stream.fileno())
    _sync_dir(attempt_dir)
    stdout_raw = stdout_path.read_bytes()
    stderr_raw = stderr_path.read_bytes()
    code = process.returncode if process is not None else None
    terminal = {
        "schema": "cua-native-wdi-v066-v4d-private-child-output-v1",
        "status": "terminal_output_fsynced_before_classification",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": code,
        "timed_out": timed_out,
        "spawn_error_type": spawn_error_type,
        "stdout_sha256": digest(stdout_raw),
        "stderr_sha256": digest(stderr_raw),
        "stdout_bytes": len(stdout_raw),
        "stderr_bytes": len(stderr_raw),
    }
    _write_new(terminal_path, terminal)
    return code, stdout_raw.decode("utf-8", errors="replace"), \
        stderr_raw.decode("utf-8", errors="replace"), timed_out


def invoke_child_durable(command: list[str]) -> tuple[int | None, str, str, bool]:
    """Drop-in for v3's _invoke_child, with private durable child output."""
    return _invoke_to_files(command, _attempt_dir(command), LEASE_SECONDS + 120)
