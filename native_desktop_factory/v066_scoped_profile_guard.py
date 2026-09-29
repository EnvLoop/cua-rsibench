"""Evaluator-owned scoped LibreOffice profile guard with raw-first evidence.

The reference comes only from six public train guests. Fresh profile absence,
scoped guest-content identity, and package/readback checks remain caller gates.
Two raw profile manifests/XML files and visible screenshots are reserved in
the evaluator SQLite evidence ledger before any normalization or comparison.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import time

from . import (profile_canonical, runtime_fingerprint_probe,
               v066_profile_scope_analysis as scope)
from .v066_scoped_profile_reference import validate_reference
from .v066_storage_budget import reserve_and_write
from .v066_final_freeze import digest


class ScopedProfileDrift(ValueError):
    """A stable profile differs from the public-train application reference."""


def _guest_calendar(sandbox, *, attempts_root: Path, out: Path,
                    label: str) -> dict:
    run = sandbox.commands.run("date -u +%Y-%m-%d && date +%Y-%m-%d")
    raw = run.stdout.encode()
    values = run.stdout.splitlines()
    if run.exit_code != 0 or len(values) != 2 or len(raw) > 100:
        raise ValueError("Guest UTC/local calendar probe failed")
    try:
        days = [(date.fromisoformat(item) - date(1970, 1, 1)).days
                for item in values]
    except ValueError:
        raise ValueError("Guest UTC/local calendar probe is invalid") from None
    return {"label": label,
            "raw": reserve_and_write(
                attempts_root, out / f"guest-calendar-{label}.txt", raw),
            "utc_day": days[0], "local_day": days[1]}


def _capture(sandbox, *, attempts_root: Path, out: Path,
             label: str, started: float,
             snapshots: list[dict], persist) -> str:
    run = sandbox.commands.run(
        "python3 /tmp/native-profile-file-probe-scoped-v066.py")
    if run.exit_code != 0:
        raise ValueError("Scoped profile-file probe failed")
    manifest = run.stdout.encode()
    if not manifest or len(manifest) > 4_000_000:
        raise ValueError("Scoped raw profile manifest is unbounded")
    manifest_record = reserve_and_write(
        attempts_root, out / f"profile-{label}.manifest.json", manifest)
    registry = bytes(sandbox.files.read(
        "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
        format="bytes"))
    if not registry or len(registry) > 4_000_000:
        raise ValueError("Scoped raw registry is unbounded")
    registry_record = reserve_and_write(
        attempts_root, out / f"profile-{label}.registry.xml", registry)
    frame = bytes(sandbox.screenshot())
    if not frame or len(frame) > 4_000_000:
        raise ValueError("Scoped raw visible frame is unbounded")
    frame_record = reserve_and_write(
        attempts_root, out / f"profile-{label}.png", frame)
    record = {
        "label": label,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds_after_first_capture": round(
            time.monotonic() - started, 3),
        "manifest": manifest_record,
        "registry": registry_record,
        "visible_frame": frame_record,
        "profile_probe_script_sha256": digest(
            runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode()),
    }
    snapshots.append(record)
    persist()  # Raw paths/hashes survive a normalization exception.
    try:
        rows = json.loads(manifest)
        record["file_count"] = len(rows)
        record["strict_profile_sha256"] = (
            profile_canonical.canonical_profile_tree(rows, registry))
        record["scoped_profile_sha256"] = scope.scoped_profile(rows, registry)
    except (ValueError, TypeError, KeyError) as exc:
        record["normalization_error_type"] = type(exc).__name__
        persist()
        raise ValueError("Scoped profile normalization failed") from exc
    persist()
    return record["scoped_profile_sha256"]


def attest(*, sandbox, attempts_root: Path, out: Path,
           app_kind: str, reference_path: Path,
           receipt: dict, persist) -> str:
    reference, reference_sha = validate_reference(reference_path)
    expected = reference["applications"].get(app_kind)
    if not expected:
        raise ValueError("No public-train scoped profile for this application")
    sandbox.files.write("/tmp/native-profile-file-probe-scoped-v066.py",
                        runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())
    snapshots = receipt.setdefault("task_profile_scoped_snapshots", [])
    if snapshots:
        raise ValueError("Scoped profile evidence already exists")
    receipt["profile_reference_private_sha256"] = reference_sha
    receipt["profile_application_kind"] = app_kind
    day_floor = reference.get("current_public_tip_day")
    if day_floor is not None:
        if (type(day_floor) is not int or
                type(reference.get("prior_public_tip_day")) is not int or
                day_floor != reference["prior_public_tip_day"] + 1):
            raise ValueError("Public-train tip-day baseline is not source-bound")
        probes = receipt.setdefault("guest_calendar_probes", [])
        probes.append(_guest_calendar(
            sandbox, attempts_root=attempts_root, out=out,
            label="before"))
        persist()
    started = time.monotonic()
    first = _capture(sandbox, attempts_root=attempts_root, out=out,
                     label="first", started=started,
                     snapshots=snapshots, persist=persist)
    time.sleep(1)
    second = _capture(sandbox, attempts_root=attempts_root, out=out,
                      label="second", started=started,
                      snapshots=snapshots, persist=persist)
    if day_floor is not None:
        probes.append(_guest_calendar(
            sandbox, attempts_root=attempts_root, out=out,
            label="after"))
        first_tip = scope.tip_calendar_day(
            (out / "profile-first.registry.xml").read_bytes())
        second_tip = scope.tip_calendar_day(
            (out / "profile-second.registry.xml").read_bytes())
        guest_days = {probe[key] for probe in probes
                      for key in ("utc_day", "local_day")}
        receipt["task_profile_tip_calendar_day"] = second_tip
        receipt["task_profile_tip_day_reference_floor"] = day_floor
        receipt["task_profile_tip_day_matches_guest_clock"] = (
            first_tip == second_tip and second_tip in guest_days and
            second_tip >= day_floor)
        persist()
        if not receipt["task_profile_tip_day_matches_guest_clock"]:
            raise ScopedProfileDrift(
                "LibreOffice tip day differs from guest UTC/local calendar")
    receipt["task_profile_scoped_sha256"] = second
    receipt["task_profile_scoped_self_stable"] = first == second
    receipt["task_profile_scoped_matches_public_train"] = (
        first == second == expected)
    persist()
    if first != second or second != expected:
        raise ScopedProfileDrift("Scoped application profile changed or drifted")
    receipt["task_profile_scoped_attested"] = True
    # Compatibility with the independent frozen GUI/saved-artifact audit; the
    # new scoped audit additionally requires every raw profile record.
    receipt["task_profile_attested"] = True
    persist()
    return second
