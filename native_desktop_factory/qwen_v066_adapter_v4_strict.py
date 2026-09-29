"""Fail-closed v4 caret adapter for the bounded evaluator retry loop.

The frozen v4 prototype recognizes A/B/A/B across two observations.  This
wrapper distinguishes the one permitted *pending caret* retry from a material,
third-state, changed-action, or persistent-edit drift.  The paid worker may
resample only the former; all other drift ends that disposable attempt.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

from cursibench.scale_action_contract import ContractError

from . import qwen_v066_adapter_v4 as prototype
from .v066_storage_budget import reserve_and_write


observe = prototype.observe
dispatch = prototype.dispatch
render_for_model = prototype.render_for_model
PhysicalFrameDrift = prototype.PhysicalFrameDrift


class MaterialFrameDrift(ContractError):
    def __init__(self):
        super().__init__("stale_frame")


def _record_probe(*, sandbox, observation, raw: str,
                  screenshots: list[bytes], permitted: bool) -> None:
    root_text = os.environ.get("ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT")
    attempt_text = os.environ.get("ENVLOOP_DESKTOP_V4_ATTEMPT_DIR")
    if not root_text or not attempt_text:
        if os.environ.get("ENVLOOP_DESKTOP_V4_FREEZE"):
            raise MaterialFrameDrift()
        return  # Offline unit probes have no paid attempt root.
    root, attempt_dir = Path(root_text).resolve(), Path(attempt_text).resolve()
    if (not attempt_dir.is_relative_to(root) or
            attempt_dir.parent.parent != root or
            not attempt_dir.is_dir()):
        raise MaterialFrameDrift()
    counters = getattr(sandbox, "_v4_probe_attempts", {})
    number = counters.get(observation.step, 0)
    if number >= 5:
        raise MaterialFrameDrift()
    counters[observation.step] = number + 1
    sandbox._v4_probe_attempts = counters
    stem = f"probe-step-{observation.step:02d}-{number:02d}"
    samples = []
    for index, data in enumerate(screenshots):
        samples.append(reserve_and_write(
            root, attempt_dir / f"{stem}-{index:02d}.png", data))
    manifest = {
        "schema": "cua-native-wdi-v066-internal-caret-probe-private-v4",
        "status": ("pending_exact_alternate" if permitted else
                   "rejected_material_or_third_state"),
        "step": observation.step,
        "frame_attempt": number,
        "action_sha256": sha256(raw.encode()).hexdigest(),
        "observed_sha256": sha256(observation.screenshot_bytes).hexdigest(),
        "sample_frames": samples,
        "sample_application_sha256s": [
            prototype._application_sha(data) for data in screenshots],
    }
    reserve_and_write(
        root, attempt_dir / f"{stem}.json",
        (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode())


def parse_current_action(raw, observation, sandbox, *, on_stale_frame=None):
    screenshots: list[bytes] = []
    original_screenshot = sandbox.screenshot

    def capture() -> bytes:
        data = bytes(original_screenshot())
        screenshots.append(data)
        return data

    try:
        with patch.object(sandbox, "screenshot", capture):
            return prototype.parse_current_action(
                raw, observation, sandbox, on_stale_frame=on_stale_frame)
    except PhysicalFrameDrift:
        # The frozen prototype remembers only the final screenshot.  An early
        # B→C probe can otherwise be mistaken for six stable C probes when
        # both B and C are one-column caret shapes relative to A.  Require
        # the direct predispatch frame plus all five bounded internal probes
        # to be the exact same application image before allowing an outer
        # observation retry.  Persist every internal raw probe for audit.
        pending = prototype._pending.get(sandbox)
        permitted = (pending is not None and
                     len(screenshots) ==
                     1 + len(prototype.v3._CARET_PROBE_DELAYS_SECONDS) and
                     all(prototype._application_sha(data) ==
                         pending.alternate_application_sha256
                         for data in screenshots) and
                     all(prototype.v3._single_caret_column(
                         observation.screenshot_bytes, data)
                         for data in screenshots))
        try:
            _record_probe(sandbox=sandbox, observation=observation,
                          raw=raw, screenshots=screenshots,
                          permitted=permitted)
        except Exception:
            prototype._pending.pop(sandbox, None)
            raise MaterialFrameDrift() from None
        if permitted:
            raise
        prototype._pending.pop(sandbox, None)
        raise MaterialFrameDrift() from None


__all__ = ["observe", "render_for_model", "parse_current_action",
           "dispatch", "PhysicalFrameDrift", "MaterialFrameDrift"]
