"""Bounded, train-only no-action screenshot probe after Calc Enter.

The proxy delegates every GUI action to a real or fake Desktop sandbox. It
only inserts screenshot/window observations after Enter. It neither repairs
the application nor dispatches a second action while the frame is changing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from .qwen_v064_adapter import application_frame_digest
from .v066_storage_budget import reserve_and_write


SAMPLE_DELAYS_MS = (0, 250, 250, 250, 250)
MAX_PROBE_WALL_MS = 10_000


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _append_fsynced(path: Path, row: dict) -> None:
    raw = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
    first_write = not path.exists()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if first_write:
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)


class PostEnterProbeProxy:
    def __init__(self, sandbox, *, storage_root: Path, output: Path,
                 document_filename: str, clock=time.monotonic_ns,
                 sleep=time.sleep):
        if (not output.is_dir() or output.is_symlink() or
                output.resolve().parent != storage_root.resolve() or
                not document_filename.lower().endswith(".xlsx")):
            raise ValueError("Train-only Calc probe root or document invalid")
        self.sandbox = sandbox
        self.storage_root = storage_root
        self.output = output
        self.document_filename = document_filename
        self.clock = clock
        self.sleep = sleep
        self.enter_count = 0

    def __getattr__(self, name):
        return getattr(self.sandbox, name)

    def press(self, key):
        if str(key).lower() not in ("enter", "return"):
            return self.sandbox.press(key)
        if self.enter_count >= 2:
            raise ValueError("At most two frozen public-train Enter probes")
        prior_id = self.sandbox.get_current_window_id()
        prior_title = self.sandbox.get_window_title(prior_id)
        if self.document_filename not in prior_title:
            raise ValueError("Calc document window absent before Enter")
        result = self.sandbox.press(key)
        ordinal = self.enter_count
        self.enter_count += 1
        start_ns = self.clock()
        application_hashes = []
        for sample, delay_ms in enumerate(SAMPLE_DELAYS_MS):
            if delay_ms:
                self.sleep(delay_ms / 1000)
            before_ns = self.clock()
            first_id = self.sandbox.get_current_window_id()
            first_title = self.sandbox.get_window_title(first_id)
            raw = bytes(self.sandbox.screenshot())
            second_id = self.sandbox.get_current_window_id()
            second_title = self.sandbox.get_window_title(second_id)
            after_ns = self.clock()
            path = self.output / f"post-enter-{ordinal:02d}-{sample:02d}.png"
            ref = reserve_and_write(self.storage_root, path, raw)
            row = {
                "schema": "cua-native-wdi-v066-post-enter-train-sample-v1",
                "enter_ordinal": ordinal, "sample": sample,
                "requested_delay_ms_before_sample": delay_ms,
                "captured_utc": datetime.now(timezone.utc).isoformat(),
                "monotonic_before_ns": before_ns,
                "monotonic_after_ns": after_ns,
                "elapsed_since_enter_ns": after_ns - start_ns,
                "frame": ref,
                "full_frame_sha256": digest(raw),
                "application_frame_sha256": application_frame_digest(raw),
                "window_id_before_sha256": digest(first_id.encode()),
                "window_id_after_sha256": digest(second_id.encode()),
                "window_title_before_sha256": digest(first_title.encode()),
                "window_title_after_sha256": digest(second_title.encode()),
                "document_window_stable": (
                    first_id == second_id == prior_id and
                    self.document_filename in first_title and
                    self.document_filename in second_title),
            }
            _append_fsynced(self.output / "post-enter-samples.ndjson", row)
            application_hashes.append(row["application_frame_sha256"])
            if (not row["document_window_stable"] or
                    before_ns < start_ns or after_ns < before_ns or
                    after_ns - start_ns > MAX_PROBE_WALL_MS * 1_000_000):
                raise ValueError("Post-Enter modal/window/time boundary changed")
        distinct_transitions = []
        for frame_sha in application_hashes:
            if not distinct_transitions or frame_sha != distinct_transitions[-1]:
                distinct_transitions.append(frame_sha)
        if (application_hashes[-2] != application_hashes[-1] or
                len(distinct_transitions) > 2 or
                len(distinct_transitions) != len(set(distinct_transitions)) or
                after_ns - start_ns < sum(SAMPLE_DELAYS_MS) * 1_000_000):
            raise ValueError("Post-Enter frame oscillated or had no exact settle")
        return result
