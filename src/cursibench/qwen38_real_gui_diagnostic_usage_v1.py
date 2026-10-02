"""Read-only attribution of later Tinker billing events to one diagnostic.

The input must be the provider's raw get_billing_usage response and a saved
official pricing table. Token counts are provider-reported; rate multiplication
is a nominal subtotal, never an invoice or available-balance statement.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

from . import qwen38_real_gui_diagnostic_v1 as diagnostic


SCHEMA = "cua-qwen38-real-gui-diagnostic-usage-audit-v1"
RUN_ID = re.compile(r"[0-9a-f]{16}\Z")
TOKEN_KINDS = {
    "training": "train",
    "sampling_prefill": "prefill",
    "sampling_sample": "sample",
}


class UsageError(ValueError):
    """Fixed labels; never display session IDs or provider response bodies."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise UsageError(code)


def _hour(value: str) -> datetime:
    require(type(value) is str, "diagnostic_usage_utc_hour_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise UsageError("diagnostic_usage_utc_hour_invalid") from None
    require(parsed.tzinfo is not None and
            parsed.utcoffset() == timedelta(0) and
            parsed.minute == parsed.second == parsed.microsecond == 0,
            "diagnostic_usage_utc_hour_invalid")
    return parsed.astimezone(timezone.utc)


def _rate(value: object) -> Decimal:
    require(type(value) is str and value.startswith("$"),
            "diagnostic_usage_official_rate_missing")
    try:
        result = Decimal(value[1:])
    except InvalidOperation:
        raise UsageError("diagnostic_usage_official_rate_invalid") from None
    require(result.is_finite() and result >= 0,
            "diagnostic_usage_official_rate_invalid")
    return result


def audit(*, usage_raw: bytes, pricing_raw: bytes, plan_sha256: str,
          window_start: str, window_end: str) -> dict:
    require(type(usage_raw) is bytes and 0 < len(usage_raw) <= 32_000_000 and
            type(pricing_raw) is bytes and 0 < len(pricing_raw) <= 8_000_000 and
            type(plan_sha256) is str and
            diagnostic.HASH.fullmatch(plan_sha256),
            "diagnostic_usage_source_or_plan_invalid")
    start, end = _hour(window_start), _hour(window_end)
    require(start < end and end - start <= timedelta(days=14),
            "diagnostic_usage_window_invalid")
    try:
        usage, pricing = json.loads(usage_raw), json.loads(pricing_raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UsageError("diagnostic_usage_json_invalid") from None
    require(type(usage) is dict and type(usage.get("data")) is list and
            type(usage.get("sessions")) is dict and
            type(pricing) is list,
            "diagnostic_usage_shape_invalid")
    rows = [row for row in pricing if type(row) is dict and
            row.get("tinker_id") == diagnostic.MODEL]
    require(len(rows) == 1 and "Vision" in str(rows[0].get("type", "")),
            "diagnostic_usage_model_rate_missing")
    rates = {name: _rate(rows[0][name]) for name in
             ("train", "prefill", "cached_prefill", "sample")}
    run_id = plan_sha256[:16]
    require(RUN_ID.fullmatch(run_id) is not None,
            "diagnostic_usage_run_id_invalid")
    tokens = {key: 0 for key in (
        "training", "sampling_prefill_uncached",
        "sampling_prefill_cached", "sampling_sample")}
    nominal = {key: Decimal(0) for key in tokens}
    matched = 0
    unpriced = 0
    estimated_cost_count = 0
    estimated_cost = Decimal(0)
    for event in usage["data"]:
        require(type(event) is dict and
                type(event.get("event_info")) is dict and
                start <= _hour(event.get("bucket_start")) <
                _hour(event.get("bucket_end")) <= end,
                "diagnostic_usage_event_invalid_or_outside_window")
        session = usage["sessions"].get(event.get("session_id"))
        metadata = (session.get("user_metadata")
                    if type(session) is dict else None)
        if (type(metadata) is not dict or
            metadata.get("purpose") != "envloop-real-gui-diagnostic-v1" or
            metadata.get("run_id") != run_id or
            metadata.get("split") != "train"):
            continue
        matched += 1
        require(event.get("base_model") == diagnostic.MODEL,
                "diagnostic_usage_matched_model_changed")
        if event.get("estimated_cost_usd") is not None:
            try:
                amount = Decimal(str(event["estimated_cost_usd"]))
            except InvalidOperation:
                raise UsageError(
                    "diagnostic_usage_provider_estimate_invalid") from None
            require(amount.is_finite() and amount >= 0,
                    "diagnostic_usage_provider_estimate_invalid")
            estimated_cost += amount
            estimated_cost_count += 1
        info = event["event_info"]
        kind = info.get("type")
        if kind not in TOKEN_KINDS:
            unpriced += 1
            continue
        count = info.get("token_count")
        require(type(count) is int and count >= 0,
                "diagnostic_usage_billed_token_count_invalid")
        if kind == "sampling_prefill":
            require(type(info.get("cached")) is bool,
                    "diagnostic_usage_prefill_cache_flag_missing")
            bucket = ("sampling_prefill_cached" if info["cached"] else
                      "sampling_prefill_uncached")
            rate = rates["cached_prefill" if info["cached"] else "prefill"]
        else:
            bucket = kind
            rate = rates[TOKEN_KINDS[kind]]
        tokens[bucket] += count
        nominal[bucket] += Decimal(count) * rate / Decimal(1_000_000)
    require(matched > 0, "diagnostic_usage_no_attributed_provider_events")
    return {
        "schema": SCHEMA,
        "status": "attributed_provider_usage_nominal_rate_not_invoice",
        "model": diagnostic.MODEL,
        "plan_sha256": plan_sha256,
        "run_id_sha256": sha256(run_id.encode()).hexdigest(),
        "window_start": window_start,
        "window_end": window_end,
        "usage_source_sha256": sha256(usage_raw).hexdigest(),
        "pricing_source_sha256": sha256(pricing_raw).hexdigest(),
        "matched_provider_event_count": matched,
        "unpriced_checkpoint_or_storage_event_count": unpriced,
        "matched_estimated_cost_field_count": estimated_cost_count,
        "provider_reported_estimated_cost_subtotal_usd": (
            str(estimated_cost) if estimated_cost_count == matched else None),
        "provider_reported_billed_tokens": tokens,
        "published_rates_usd_per_million": {
            key: str(value) for key, value in rates.items()},
        "nominal_token_rate_subtotal_usd": str(sum(
            nominal.values(), Decimal(0))),
        "provider_invoice_usd": None,
        "provider_credits_or_discounts_included": False,
        "billing_freshness_complete": None,
        "official_researcher_campaign": False,
        "benchmark_score": None,
    }


__all__ = ["UsageError", "audit"]
