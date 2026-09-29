"""Recorded host power telemetry for the dated Odoo evaluator-only amendment.

The operator authorized a battery-powered run on 29 September 2026. A valid
power sample is required for provenance, but neither AC nor an arbitrary
battery percentage is required. This module never authorizes a campaign.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
import subprocess


POWER_SCHEMA = "envloop-odoo-v066-evaluator-host-power-sample-v2"
SOURCES = {"AC Power", "Battery Power"}


class PowerSampleError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PowerSampleError(code)


def parse(raw: str) -> tuple[str, int]:
    require(type(raw) is str and 0 < len(raw) <= 8192,
            "power_sample_raw_pmset_invalid")
    source = re.search(r"(?m)^Now drawing from '([^']+)'\s*$", raw)
    levels = re.findall(r"(?m)^\s*-InternalBattery-\d+.*?\b(\d{1,3})%;", raw)
    require(source is not None and source.group(1) in SOURCES and
            len(levels) == 1, "power_sample_source_or_level_unrecognized")
    percent = int(levels[0])
    require(0 <= percent <= 100, "power_sample_percent_out_of_range")
    return source.group(1), percent


def capture() -> dict:
    result = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                            text=True, check=True, timeout=10)
    raw = result.stdout
    source, percent = parse(raw)
    return {
        "schema": POWER_SCHEMA,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "battery_percent": percent,
        "raw_pmset_stdout": raw,
        "raw_pmset_stdout_sha256": sha256(raw.encode()).hexdigest(),
        "battery_operation_authorized_by_user_on": "2026-09-29",
    }


def validate(sample: dict) -> datetime:
    require(type(sample) is dict and set(sample) == {
        "schema", "captured_at_utc", "source", "battery_percent",
        "raw_pmset_stdout", "raw_pmset_stdout_sha256",
        "battery_operation_authorized_by_user_on"},
        "power_sample_fields_invalid")
    source, percent = parse(sample["raw_pmset_stdout"])
    require(sample["schema"] == POWER_SCHEMA and
            sample["source"] == source and
            type(sample["battery_percent"]) is int and
            sample["battery_percent"] == percent and
            sample["raw_pmset_stdout_sha256"] ==
            sha256(sample["raw_pmset_stdout"].encode()).hexdigest() and
            sample["battery_operation_authorized_by_user_on"] == "2026-09-29",
            "power_sample_parse_or_digest_mismatch")
    try:
        at = datetime.fromisoformat(sample["captured_at_utc"])
    except (TypeError, ValueError) as exc:
        raise PowerSampleError("power_sample_time_invalid") from exc
    require(at.tzinfo is not None and at.utcoffset() is not None and
            at.utcoffset().total_seconds() == 0,
            "power_sample_time_not_utc")
    return at
