"""Re-audit retained selection failures against append-only worker leases.

The original incident JSON files signed the complete lease journal at their
respective times. Later, legitimate leases append to that same journal. This
adapter proves each old SHA is an exact, newline-terminated prefix ending in
the incident's own release, then checks every newer row as a complete lease
pair. The old auditors, attempts, and published incident JSON stay unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from tools import audit_odoo_v066_selection_flicker_v1 as first
from tools import audit_odoo_v066_selection_post_intent_stale_v1 as second
from tools import audit_odoo_v066_selection_third_invalid_action_v1 as third
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


class HistoricalLeaseError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise HistoricalLeaseError(code)


def _row(line: bytes) -> dict:
    def no_duplicate_keys(items: list[tuple[str, object]]) -> dict:
        value = {}
        for key, item in items:
            require(key not in value, "historical_lease_duplicate_json_key")
            value[key] = item
        return value

    require(line.endswith(b"\n") and line != b"\n",
            "historical_lease_incomplete_or_blank_row")
    try:
        value = json.loads(line, object_pairs_hook=no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HistoricalLeaseError("historical_lease_invalid_json") from error
    require(type(value) is dict and
            line == (json.dumps(value, sort_keys=True) + "\n").encode(),
            "historical_lease_noncanonical_row")
    require(set(value) == {"event", "operation", "pid", "at_utc"} and
            value["event"] in ("acquired", "released") and
            type(value["operation"]) is str and
            re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value["operation"])
            is not None and type(value["pid"]) is int and value["pid"] > 0 and
            type(value["at_utc"]) is str,
            "historical_lease_invalid_event_fields")
    try:
        at = datetime.fromisoformat(value["at_utc"])
    except ValueError as error:
        raise HistoricalLeaseError("historical_lease_invalid_timestamp") from error
    require(at.tzinfo is not None and at.utcoffset() == timedelta(0),
            "historical_lease_not_utc")
    return value


def _pairs(rows: list[dict]) -> None:
    require(len(rows) >= 2 and len(rows) % 2 == 0,
            "historical_lease_unpaired_rows")
    last_time = None
    for offset in range(0, len(rows), 2):
        acquire, release = rows[offset:offset + 2]
        begin = datetime.fromisoformat(acquire["at_utc"])
        end = datetime.fromisoformat(release["at_utc"])
        require(acquire["event"] == "acquired" and
                release["event"] == "released" and
                acquire["operation"] == release["operation"] and
                acquire["pid"] == release["pid"] and
                begin <= end and
                (last_time is None or last_time <= begin),
                "historical_lease_pair_or_order_invalid")
        last_time = end


def inspect_prefix(*, worker_private: Path, published_sha256: str,
                   intent_path: Path, failure_path: Path) -> dict:
    """Prove an old incident SHA and its release in the current exact log."""
    require(type(published_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", published_sha256) is not None,
            "historical_lease_published_sha_invalid")
    events_path = worker_private / "worker-lease-events.jsonl"
    protocol._private(events_path)
    raw = events_path.read_bytes()
    require(raw.endswith(b"\n"), "historical_lease_current_log_truncated")
    lines = raw.splitlines(keepends=True)
    rows = [_row(line) for line in lines]
    _pairs(rows)
    offset = 0
    matches = []
    for index, line in enumerate(lines, start=1):
        offset += len(line)
        if sha256(raw[:offset]).hexdigest() == published_sha256:
            matches.append((index, offset))
    require(len(matches) == 1,
            "historical_lease_published_prefix_changed")
    prefix_rows, prefix_bytes = matches[0]
    require(prefix_rows >= 2 and prefix_rows % 2 == 0,
            "historical_lease_prefix_does_not_end_in_release")
    acquire, release = rows[prefix_rows - 2:prefix_rows]
    require(acquire["event"] == "acquired" and
            release["event"] == "released" and
            acquire["operation"] == release["operation"] ==
            controller.LEASE_OPERATION and
            acquire["pid"] == release["pid"],
            "historical_lease_original_pair_not_at_prefix_end")
    intent = protocol.private_json(intent_path)
    protocol._private(failure_path)
    try:
        started = datetime.fromisoformat(intent["started_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise HistoricalLeaseError("historical_lease_intent_time_invalid") from error
    failed = datetime.fromtimestamp(failure_path.stat().st_mtime,
                                    timezone.utc)
    begin = datetime.fromisoformat(acquire["at_utc"])
    end = datetime.fromisoformat(release["at_utc"])
    require(started.tzinfo is not None and
            started.utcoffset() == timedelta(0) and
            begin <= started <= failed <= end,
            "historical_lease_original_pair_not_bound_to_attempt")
    matching = [index for index in range(0, prefix_rows, 2)
                if rows[index]["operation"] == controller.LEASE_OPERATION and
                datetime.fromisoformat(rows[index]["at_utc"]) <= started and
                datetime.fromisoformat(rows[index + 1]["at_utc"]) >= failed]
    require(matching == [prefix_rows - 2],
            "historical_lease_original_pair_not_unique")
    # _pairs validated the whole current log, including every appended row.
    # The prefix terminates on a pair boundary, so the suffix is fully paired.
    return {
        "published_prefix_sha256": published_sha256,
        "published_prefix_bytes": prefix_bytes,
        "published_prefix_rows": prefix_rows,
        "appended_complete_lease_pairs": (len(rows) - prefix_rows) // 2,
        "current_full_log_sha256": sha256(raw).hexdigest(),
        "current_full_log_bytes": len(raw),
    }


def reaudit_retained(*, worker: Path,
                     historical_root: Path) -> tuple[dict[str, str], dict]:
    """Reopen all three old auditors and compare every immutable field."""
    worker = Path(worker).resolve()
    private = protocol._worker_split(worker, "selection")
    evidence = protocol.ROOT / "docs/evidence"
    run_root = private / "v066_scale_controls"
    first_dir = run_root / "controls-20260928-v1"
    second_dir = run_root / "controls-20260929-exact-return-01"
    third_dir = run_root / "controls-20260929-pinned-border-01"
    paths = {
        "first": evidence /
        "odoo-v066-selection-first-exact-frame-flicker-incident-2026-09-28.json",
        "second": evidence /
        "odoo-v066-selection-second-post-intent-stale-2026-09-29.json",
        "third": evidence /
        "odoo-v066-selection-third-validator-mismatch-2026-09-29.json",
    }
    derived = {
        "first": first.audit(
            repo=protocol.ROOT, worker=worker, run_dir=first_dir,
            private_plan=historical_root / "selection/plan-lease-amended.private.json",
            public_plan=evidence /
            "odoo-v066-selection-control-plan-lease-amended-2026-09-28.json",
            source_freeze=evidence /
            "odoo-v066-scale-control-lease-amended-source-freeze-2026-09-28.json",
            verify_services=True),
        "second": second.audit(
            repo=protocol.ROOT, worker=worker, run_dir=second_dir,
            old_run_dir=first_dir,
            private_plan_path=historical_root /
            "selection/plan-exact-frame-return-blank-compose-20260929.private.json",
            public_plan_path=evidence /
            "odoo-v066-selection-control-plan-exact-frame-return-blank-compose-2026-09-29.json",
            source_freeze_path=evidence /
            "odoo-v066-scale-exact-frame-return-blank-compose-source-freeze-2026-09-29.json",
            incident_public_path=paths["first"], verify_services=True),
        "third": third.audit(
            repo=protocol.ROOT, worker=worker, run_dir=third_dir,
            previous_run_dir=second_dir,
            private_plan_path=historical_root /
            "selection/plan-pinned-border-rfq-view-20260929.private.json",
            public_plan_path=evidence /
            "odoo-v066-selection-control-plan-pinned-border-rfq-view-2026-09-29.json",
            source_freeze_path=evidence /
            "odoo-v066-scale-pinned-border-rfq-view-source-freeze-2026-09-29.json",
            previous_incident_public_path=paths["second"],
            verify_services=True),
    }
    prefixes = {}
    for label in ("second", "third"):
        published = protocol.public_json(paths[label])
        attempt = (second_dir if label == "second" else third_dir) / "attempt-000"
        binding = inspect_prefix(
            worker_private=private,
            published_sha256=published["worker_lease_events_sha256"],
            intent_path=attempt / "intent.private.json",
            failure_path=attempt / "failure.private.json")
        require(derived[label].get("worker_lease_events_sha256") ==
                binding["current_full_log_sha256"],
                "historical_lease_changed_during_original_audit")
        # Only replace the explicitly mutable whole-log digest, after proving
        # its published value is the exact original newline-bound prefix.
        derived[label] = {**derived[label],
                          "worker_lease_events_sha256":
                          published["worker_lease_events_sha256"]}
        prefixes[label] = {key: binding[key] for key in (
            "published_prefix_sha256", "published_prefix_bytes",
            "published_prefix_rows")}
    for label in ("first", "second", "third"):
        published = protocol.public_json(paths[label])
        require(derived[label] == published and
                published.get("selection_services_exited_zero") is True and
                published.get("selection_worker_locks_free") is True and
                published.get("official_final_tasks_admitted") == 0 and
                published.get("model_attempts") == 0,
                "historical_lease_retained_" + label + "_failure_changed")
    return ({label: sha256(paths[label].read_bytes()).hexdigest()
             for label in paths}, prefixes)
