"""Read-only private Tinker usage snapshot for later campaign cost audit.

The billing usage endpoint reports hourly organization events and may expose
user/session/project identifiers. Raw bytes stay under ignored mode-0700
work/. The public projection contains counts and hashes only. Usage estimates
are never called an invoice or an available credit balance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
from pathlib import Path

from . import full_study_tinker_preflight_v1 as private


SCHEMA = "cua-full-study-tinker-billing-snapshot-v1"
PUBLIC_SCHEMA = "cua-full-study-tinker-billing-public-snapshot-v1"


def _utc_hour(value: datetime, label: str) -> datetime:
    private.require(type(value) is datetime and value.tzinfo is not None and
                    value.utcoffset() == timedelta(0) and
                    value.minute == value.second == value.microsecond == 0,
                    f"{label}_must_be_utc_hour")
    return value.astimezone(timezone.utc)


def _window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start = _utc_hour(start, "starting_on")
    end = _utc_hour(end, "ending_before")
    now_hour = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0)
    private.require(timedelta(hours=1) <= end - start <= timedelta(days=14)
                    and end <= now_hour,
                    "billing_usage_window_invalid")
    return start, end


def _timestamp(value: object) -> datetime:
    private.require(type(value) is str,
                    "billing_event_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise private.PreflightError("billing_event_timestamp_invalid") from None
    private.require(parsed.tzinfo is not None and
                    parsed.utcoffset() == timedelta(0),
                    "billing_event_timestamp_invalid")
    return parsed.astimezone(timezone.utc)


def _validate_response(raw: bytes, start: datetime, end: datetime) -> dict:
    private.require(type(raw) is bytes and 0 < len(raw) <= 32_000_000,
                    "billing_response_size_invalid")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise private.PreflightError("billing_response_json_invalid") from None
    private.require(type(value) is dict and
                    type(value.get("data")) is list and
                    type(value.get("sessions")) is dict,
                    "billing_response_shape_invalid")
    counts: dict[str, int] = {}
    cost_fields = 0
    for event in value["data"]:
        private.require(type(event) is dict and
                        type(event.get("event_info")) is dict and
                        type(event["event_info"].get("type")) is str and
                        start <= _timestamp(event.get("bucket_start")) <
                        _timestamp(event.get("bucket_end")) <= end,
                        "billing_event_outside_requested_window")
        kind = event["event_info"]["type"]
        private.require(kind in {
            "training", "sampling_prefill", "sampling_sample",
            "checkpoint", "storage"},
            "billing_event_type_unknown")
        counts[kind] = counts.get(kind, 0) + 1
        if event.get("estimated_cost_usd") is not None:
            cost_fields += 1
    return {"event_count": len(value["data"]),
            "session_count": len(value["sessions"]),
            "event_type_counts": counts,
            "estimated_cost_field_count": cost_fields,
            "cost_data_through_present":
                value.get("cost_data_through") is not None}


def collect_read_only(repo_root: Path, output_dir: Path, *,
                      start: datetime, end: datetime,
                      service_factory=None) -> dict:
    start, end = _window(start, end)
    output = private.private_output_dir(Path(repo_root), Path(output_dir))
    if service_factory is None:
        import tinker
        service_factory = tinker.ServiceClient
    service = service_factory(user_metadata={
        "purpose": "envloop-full-study-read-only-billing-snapshot",
        "split": "none"})
    status = "errored"
    try:
        rest = service.create_rest_client()
        response = rest.get_billing_usage(start, end).result(timeout=90)
        raw = response.model_dump_json().encode() + b"\n"
        summary = _validate_response(raw, start, end)
        status = "success"
    finally:
        service.close(status).result(timeout=30)
    receipt = {
        "schema": SCHEMA,
        "starting_on": start.isoformat().replace("+00:00", "Z"),
        "ending_before": end.isoformat().replace("+00:00", "Z"),
        "tinker_sdk_version": importlib.metadata.version("tinker"),
        "response_sha256": private.sha256(raw),
        **summary,
        "read_only_provider_call_count": 1,
        "training_or_sampling_provider_calls": 0,
        "available_balance_usd": None,
        "invoice_usd": None,
        "estimated_cost_is_not_invoice": True,
    }
    private.private_write_new(output / "response.private.json", raw)
    private.private_write_new(output / "receipt.private.json",
                              private.canonical(receipt))
    return receipt


def public_summary(receipt: dict, response_raw: bytes, *,
                   private_receipt_sha256: str) -> dict:
    private.exact_hash(private_receipt_sha256, "private_receipt")
    private.require(type(receipt) is dict and receipt.get("schema") == SCHEMA and
                    receipt.get("response_sha256") == private.sha256(response_raw)
                    and receipt.get("read_only_provider_call_count") == 1 and
                    receipt.get("training_or_sampling_provider_calls") == 0 and
                    receipt.get("invoice_usd") is None and
                    receipt.get("available_balance_usd") is None and
                    receipt.get("estimated_cost_is_not_invoice") is True,
                    "billing_private_receipt_not_publishable")
    start = _timestamp(receipt.get("starting_on"))
    end = _timestamp(receipt.get("ending_before"))
    _window(start, end)
    summary = _validate_response(response_raw, start, end)
    private.require(all(receipt.get(key) == value for key, value in
                        summary.items()),
                    "billing_private_summary_changed")
    return {
        "schema": PUBLIC_SCHEMA,
        "status": "read_only_usage_counts_not_invoice",
        "starting_on": receipt["starting_on"],
        "ending_before": receipt["ending_before"],
        "tinker_sdk_version": receipt["tinker_sdk_version"],
        "response_sha256": receipt["response_sha256"],
        "private_receipt_sha256": private_receipt_sha256,
        **summary,
        "training_or_sampling_provider_calls": 0,
        "available_balance_usd": None,
        "invoice_usd": None,
    }
