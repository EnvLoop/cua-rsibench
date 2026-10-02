"""Durable receipt adapter for the unchanged scoped Desktop paid child.

The original evaluator source and its historical receipt hash remain frozen.
This adapter synchronizes each receipt update before the original child can
advance to its next operation, including the update immediately before E2B
create. It does not alter the evaluator, actor script, scorer, or provider API.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from . import v066_scoped_profile_final_attempt as original


_WRITE_TEXT = Path.write_text


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_write_text(path: Path, data: str, *args, **kwargs) -> int:
    """Preserve the original write API while syncing every paid receipt."""
    written = _WRITE_TEXT(path, data, *args, **kwargs)
    if path.name == "receipt.json":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_directory(path.parent)
    return written


def main() -> None:
    with patch.object(Path, "write_text", durable_write_text):
        original.main()


if __name__ == "__main__":
    main()
