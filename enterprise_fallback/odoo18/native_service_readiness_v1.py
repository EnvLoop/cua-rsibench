"""Shared neutral startup using the accepted bounded v13 DB readiness gate.

Callbacks are scoped to one already leased worker. This helper never restores
data, scores a task, or reads a task/oracle. Failure cleanup uses service
commands and status only, including failures after a partially applied command.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

RECEIPT_SCHEMA = "envloop-odoo-native-service-readiness-v1"
READY_STATUS = "native_services_ready"
FAILED_STATUS = "native_service_startup_failed"
ACCEPTED_READINESS_SOURCE = "tools/odoo_v066_train_attachment_calibration_v13.py"
READINESS_BOUNDS = {
    "timeout_seconds": 60, "probe_timeout_seconds": 5,
    "max_probes": 30, "poll_seconds": 1,
}
_SERVICES = {"db", "web"}


def _policy_matches(value) -> bool:
    return (type(value) is dict and set(value) == set(READINESS_BOUNDS)
            and all(type(value[key]) is int and value[key] == expected
                    for key, expected in READINESS_BOUNDS.items()))


class NativeServiceReadinessError(RuntimeError):
    def __init__(self, receipt: dict):
        super().__init__(FAILED_STATUS)
        self.receipt = deepcopy(receipt)


def _services(value) -> set[str]:
    if type(value) is not set or any(type(item) is not str for item in value):
        raise ValueError("native_service_status_invalid")
    # Match accepted v13's treatment of Compose's blank status lines.
    result = {item.strip() for item in value if item.strip()}
    if not result <= _SERVICES:
        raise ValueError("native_service_status_invalid")
    return result


def _wait_db_ready(worker: Path) -> dict:
    """Call the unchanged accepted gate, without constructing its TRAIN runner."""
    from tools import odoo_v066_train_attachment_calibration_v13 as accepted
    actual = {
        "timeout_seconds": accepted.READINESS_TIMEOUT_S,
        "probe_timeout_seconds": accepted.READINESS_PROBE_TIMEOUT_S,
        "max_probes": accepted.READINESS_MAX_PROBES,
        "poll_seconds": accepted.READINESS_POLL_S,
    }
    if not _policy_matches(actual):
        raise ValueError("native_accepted_readiness_policy_changed")
    return accepted._wait_db_ready(worker)


def _validate_db_ready(value: dict) -> None:
    if (type(value) is not dict or value.get("status") != "postgres_health_and_select_1_ready"
            or value.get("query") != "SELECT 1"
            or type(value.get("probe_count")) is not int
            or not 1 <= value["probe_count"] <= READINESS_BOUNDS["max_probes"]
            or type(value.get("elapsed_milliseconds")) is not int
            or value["elapsed_milliseconds"] < 0):
        raise ValueError("native_accepted_readiness_receipt_invalid")
    rows = value.get("observations")
    if type(rows) is not list or len(rows) != value["probe_count"]:
        raise ValueError("native_accepted_readiness_receipt_invalid")
    for index, row in enumerate(rows, 1):
        if type(row) is not dict or row.get("attempt") != index or type(row.get("attempt")) is not int:
            raise ValueError("native_accepted_readiness_receipt_invalid")
    last = rows[-1]
    if (last.get("services") != ["db"] or type(last.get("compose_ps_exit_code")) is not int
            or last["compose_ps_exit_code"] != 0
            or type(last.get("pg_isready_exit_code")) is not int or last["pg_isready_exit_code"] != 0
            or type(last.get("psql_exit_code")) is not int or last["psql_exit_code"] != 0):
        raise ValueError("native_accepted_readiness_receipt_invalid")


def validate_ready_receipt(receipt: dict) -> dict:
    """Pure verification of policy, native readiness evidence and startup order."""
    fields = {"schema", "status", "worker", "running_before", "running_after",
              "accepted_readiness_source", "readiness_bounds", "db_readiness", "phases",
              "cleanup_attempted", "original_services_restored", "error_type", "receipt_sink_error_type"}
    if (type(receipt) is not dict or set(receipt) != fields or receipt["schema"] != RECEIPT_SCHEMA
            or receipt["status"] != READY_STATUS or type(receipt["worker"]) is not str
            or receipt["accepted_readiness_source"] != ACCEPTED_READINESS_SOURCE
            or not _policy_matches(receipt["readiness_bounds"])
            or receipt["running_after"] != ["db", "web"]
            or receipt["cleanup_attempted"] is not False
            or receipt["original_services_restored"] is not None
            or receipt["error_type"] is not None or receipt["receipt_sink_error_type"] is not None):
        raise ValueError("native_ready_receipt_invalid")
    before = receipt["running_before"]
    if type(before) is not list or any(type(s) is not str for s in before) or before != sorted(_services(set(before))):
        raise ValueError("native_ready_receipt_invalid")
    _validate_db_ready(receipt["db_readiness"])
    expected = ["inspect_before"] + (["stop_web"] if "web" in before else []) + [
        "up_db", "db_readiness", "up_web", "inspect_ready"]
    phases = receipt["phases"]
    if (type(phases) is not list or any(type(row) is not dict for row in phases)
            or [row.get("phase") for row in phases] != expected
            or any(row.get("status") != "completed" for row in phases)
            or phases[0].get("services") != before
            or phases[-1].get("services") != ["db", "web"]):
        raise ValueError("native_ready_receipt_invalid")
    commands = {"stop_web": ["stop", "web"], "up_db": ["up", "-d", "db"],
                "up_web": ["up", "-d", "web"]}
    for row in phases:
        if (row["phase"] in commands and row.get("command") != commands[row["phase"]]) or (
                row["phase"] not in commands and "command" in row):
            raise ValueError("native_ready_receipt_invalid")
    return receipt


def ensure_ready(*, worker, running_before: set[str], compose, running, receipt_sink) -> dict:
    """Stop web, start DB, prove readiness, then start web exactly once.

    ``compose(*args)`` is a worker-scoped closure; ``running()`` returns the
    current service set. ``receipt_sink(dict)`` retains a final receipt and may
    return an artifact reference or None. Failures raise a fixed-label error
    carrying the truthful receipt if its sink could not retain that receipt.
    """
    receipt = {
        "schema": RECEIPT_SCHEMA, "status": "startup_in_progress", "worker": str(worker),
        "running_before": None, "running_after": None,
        "accepted_readiness_source": ACCEPTED_READINESS_SOURCE,
        "readiness_bounds": dict(READINESS_BOUNDS), "db_readiness": None, "phases": [],
        "cleanup_attempted": False, "original_services_restored": None,
        "error_type": None, "receipt_sink_error_type": None,
    }
    before = None
    sink_attempted = False

    def phase(name, callback, *, command=None, status_query=False):
        row = {"phase": name, "status": "started"}
        if command is not None:
            row["command"] = list(command)
        receipt["phases"].append(row)
        try:
            value = callback()
            if status_query:
                value = _services(value)
                row["services"] = sorted(value)
            elif command is not None:
                code = getattr(value, "returncode", None)
                if code is not None and (type(code) is not int or code != 0):
                    raise RuntimeError("native_service_command_failed")
            row["status"] = "completed"
            return value
        except BaseException as error:
            row.update(status="failed", error_type=type(error).__name__)
            raise

    def command(name, *args):
        return phase(name, lambda: compose(*args), command=args)

    def cleanup():
        receipt["cleanup_attempted"] = True
        try:
            current = phase("cleanup_inspect", running, status_query=True)
        except BaseException:
            current = None
        for service in ("web", "db"):
            if service not in before and (current is None or service in current):
                try:
                    command("cleanup_stop_" + service, "stop", service)
                except BaseException:
                    pass
        for service in ("db", "web"):
            if service in before and (current is None or service not in current):
                try:
                    # Web depends on DB in Compose. Recreating a prior web-only
                    # running set must not also bring up an unwanted DB.
                    args = ("up", "-d", "--no-deps", service) if service == "web" and "db" not in before else ("up", "-d", service)
                    command("cleanup_up_" + service, *args)
                except BaseException:
                    pass
        try:
            restored = phase("cleanup_verify", running, status_query=True)
            receipt["running_after"] = sorted(restored)
            receipt["original_services_restored"] = restored == before
        except BaseException:
            receipt["running_after"] = None
            receipt["original_services_restored"] = None

    try:
        if not all(callable(callback) for callback in (compose, running, receipt_sink)):
            raise ValueError("native_service_callbacks_invalid")
        before = _services(running_before)
        receipt["running_before"] = sorted(before)
        current = phase("inspect_before", running, status_query=True)
        if current != before:
            raise ValueError("native_service_start_state_changed")
        if "web" in before:
            command("stop_web", "stop", "web")
        command("up_db", "up", "-d", "db")

        def accepted_gate():
            ready = _wait_db_ready(Path(worker))
            receipt["db_readiness"] = ready if type(ready) is dict else None
            _validate_db_ready(ready)
            return ready

        phase("db_readiness", accepted_gate)
        command("up_web", "up", "-d", "web")
        receipt["running_after"] = sorted(phase("inspect_ready", running, status_query=True))
        if receipt["running_after"] != ["db", "web"]:
            raise ValueError("native_service_final_state_changed")
        receipt["status"] = READY_STATUS
        validate_ready_receipt(receipt)
        sink_attempted = True
        receipt_sink(deepcopy(receipt))
        return receipt
    except BaseException as error:
        receipt.update(status=FAILED_STATUS, error_type=type(error).__name__)
        if sink_attempted:
            receipt["receipt_sink_error_type"] = type(error).__name__
            receipt["phases"].append({"phase": "retain_receipt", "status": "failed",
                                      "error_type": type(error).__name__})
        if before is not None and callable(compose) and callable(running):
            cleanup()
        if not sink_attempted and callable(receipt_sink):
            try:
                receipt_sink(deepcopy(receipt))
            except BaseException as sink_error:
                receipt["receipt_sink_error_type"] = type(sink_error).__name__
        raise NativeServiceReadinessError(receipt) from None


__all__ = ["ensure_ready", "validate_ready_receipt", "NativeServiceReadinessError",
           "RECEIPT_SCHEMA", "READY_STATUS", "FAILED_STATUS", "READINESS_BOUNDS",
           "ACCEPTED_READINESS_SOURCE"]
