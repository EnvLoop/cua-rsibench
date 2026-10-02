"""Bounded Odoo DB readiness, fail-stop cleanup, and v4 receipt checks."""

from __future__ import annotations

from contextlib import ExitStack, nullcontext
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import audit_odoo_v066_battery_authorized_batch_v4 as batch
from tools import audit_odoo_v066_current_candidate_no_gui_gate_v4 as audit
from tools import odoo_v066_current_candidate_no_gui_gate_v4 as gate
from tools import odoo_v066_current_candidate_one_selection_v4 as runner
from tools import odoo_v066_db_readiness_source_v4 as source
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_battery_authorized_power_v2 as power


def result(code: int, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], code, stdout, "")


def power_sample(second: int) -> dict:
    raw = ("Now drawing from 'Battery Power'\n"
           " -InternalBattery-0 (id=12345) 35%; discharging; 1:30 remaining\n")
    return {
        "schema": power.POWER_SCHEMA,
        "captured_at_utc": f"2026-09-29T00:00:{second:02d}+00:00",
        "source": "Battery Power", "battery_percent": 35,
        "raw_pmset_stdout": raw,
        "raw_pmset_stdout_sha256": sha256(raw.encode()).hexdigest(),
        "battery_operation_authorized_by_user_on": "2026-09-29",
    }


class ReadinessTests(unittest.TestCase):
    def test_delayed_postgres_then_select_one(self) -> None:
        clock_value = [0.0]
        stages = iter((
            ("ps", result(0, "\n")),
            ("ps", result(0, "db\n")),
            ("pg_isready", result(1)),
            ("ps", result(0, "db\n")),
            ("pg_isready", result(0)),
            ("psql", result(1)),
            ("ps", result(0, "db\n")),
            ("pg_isready", result(0)),
            ("psql", result(0, "1\n")),
        ))

        def probe(_worker, *args, timeout_s):
            expected, reply = next(stages)
            self.assertIn(expected, args)
            self.assertGreater(timeout_s, 0)
            self.assertLessEqual(timeout_s, gate.READINESS_PROBE_TIMEOUT_S)
            if expected == "psql":
                self.assertEqual(args[-1], "SELECT 1")
            return reply

        def sleep(seconds):
            clock_value[0] += seconds

        ready = gate._wait_db_ready(
            Path("/unused"), clock=lambda: clock_value[0],
            sleeper=sleep, probe=probe)
        self.assertEqual(ready["probe_count"], 4)
        self.assertEqual(ready["elapsed_milliseconds"], 3000)
        self.assertEqual(ready["observations"][-1]["psql_exit_code"], 0)
        audit._readiness(ready)
        with self.assertRaisesRegex(audit.GateAuditError, "select_1_unverified"):
            audit._readiness({**ready, "observations":
                              [*ready["observations"][:-1],
                               {**ready["observations"][-1],
                                "psql_stdout_sha256": "0" * 64}]})

    def test_timeout_never_returns_baseline_or_receipt(self) -> None:
        clock_value = [0.0]

        def sleep(seconds):
            clock_value[0] += seconds

        with self.assertRaisesRegex(gate.NoGuiGateError, "readiness_timeout"):
            gate._wait_db_ready(
                Path("/unused"), clock=lambda: clock_value[0],
                sleeper=sleep, probe=lambda *_args, **_kwargs:
                result(0, "\n"))
        self.assertEqual(clock_value[0], gate.READINESS_MAX_PROBES)

    def test_unexpected_web_service_fails_closed(self) -> None:
        with self.assertRaisesRegex(gate.NoGuiGateError,
                                    "unexpected_service_started"):
            gate._wait_db_ready(
                Path("/unused"),
                probe=lambda *_args, **_kwargs: result(0, "db\nweb\n"))

    def test_readiness_failure_stops_db_without_sql_or_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            worker = Path(raw) / "selection"
            private = worker / "private"
            private.mkdir(parents=True)
            calls = []

            def compose(_worker, *args):
                calls.append(args)
                return result(0)

            verify = SimpleNamespace(snapshot=Mock())
            reset = SimpleNamespace(filestore_manifest=Mock())
            lease = SimpleNamespace(exclusive_worker_operation=lambda _: nullcontext())
            with (patch.object(gate.protocol, "_worker_split", return_value=private),
                  patch.object(gate.controller, "_modules",
                               return_value=(object(), object(), reset, verify, lease)),
                  patch.object(gate.controller, "_run_lock",
                               return_value=nullcontext()),
                  patch.object(gate.controller,
                               "_running_services_without_compose_blank",
                               side_effect=[set(), set()]),
                  patch.object(gate.train_recorder, "_compose",
                               side_effect=compose),
                  patch.object(gate, "_wait_db_ready",
                               side_effect=gate.NoGuiGateError("not_ready"))):
                with self.assertRaisesRegex(gate.NoGuiGateError,
                                            "not_ready"):
                    gate._collect_live_baseline(worker)
            self.assertEqual(calls, [("up", "-d", "db"), ("stop", "db")])
            verify.snapshot.assert_not_called()
            reset.filestore_manifest.assert_not_called()


class ReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        self.epoch = self.private / "v066_current_candidate_epoch"
        self.epoch.mkdir(parents=True, mode=0o700)
        self.private.chmod(0o700)
        self.plan = self.epoch / "plan.private.json"
        self.public = self.root / "plan-public.json"
        self.old_private = self.root / "old-private.json"
        self.old_public = self.root / "old-public.json"
        self.freeze = self.root / "v4-freeze.json"
        for path in (self.public, self.old_private, self.old_public,
                     self.freeze):
            path.write_text("{}\n")
        self.failures = {label: char * 64 for label, char in
                         (("first", "1"), ("second", "2"), ("third", "3"))}
        self.prefixes = {"second": {"published_prefix_sha256": "a" * 64},
                         "third": {"published_prefix_sha256": "b" * 64}}
        protocol.write_new(self.plan, {
            "run_nonce_hex": "a" * 32,
            "fresh_run_directory_name": "current-candidate-" + "a" * 32,
            "current_candidate_private_sha256": "b" * 64,
            "source_freeze_sha256": "c" * 64,
            "retained_terminal_failure_public_sha256s": self.failures,
        }, private=True)
        self.sql = {"baseline": "saved state"}
        self.files = {"filestore/a": "d" * 64}
        protocol.write_new(self.private / "baseline_snapshot.json",
                           self.sql, private=True)
        protocol.write_new(self.private / "baseline-filestore-manifest.json",
                           self.files, private=True)
        rows = [
            {"event": "acquired", "operation": gate.GATE_OPERATION,
             "pid": 123, "at_utc": "2026-09-29T00:00:00+00:00"},
            {"event": "released", "operation": gate.GATE_OPERATION,
             "pid": 123, "at_utc": "2026-09-29T00:00:01+00:00"},
        ]
        self.events = self.private / "worker-lease-events.jsonl"
        self.events.write_bytes(("\n".join(json.dumps(r) for r in rows)
                                 + "\n").encode())
        self.events.chmod(0o600)
        self.readiness = {
            "status": "postgres_health_and_select_1_ready",
            "timeout_seconds": gate.READINESS_TIMEOUT_S,
            "probe_timeout_seconds": gate.READINESS_PROBE_TIMEOUT_S,
            "probe_count": 1, "elapsed_milliseconds": 1000,
            "observations": [{
                "attempt": 1, "services": ["db"],
                "compose_ps_exit_code": 0,
                "pg_isready_exit_code": 0, "psql_exit_code": 0,
                "psql_stdout_sha256": sha256(b"1\n").hexdigest(),
            }], "query": "SELECT 1",
        }

    def kwargs(self) -> dict:
        return dict(worker_dir=self.worker, historical_root=self.root,
                    private_plan=self.plan, public_plan=self.public,
                    old_private_plan=self.old_private,
                    old_public_plan=self.old_public)

    def test_v4_gate_and_independent_audit_bind_readiness(self) -> None:
        with ExitStack() as stack:
            for context in (
                patch.object(source, "validate", return_value={}),
                patch.object(source, "FREEZE", self.freeze),
                patch.object(gate.power, "capture",
                             side_effect=[power_sample(0), power_sample(1)]),
                patch.object(gate.plan_audit, "audit", return_value={}),
                patch.object(gate.protocol, "_worker_split",
                             return_value=self.private),
                patch.object(gate.retained, "reaudit_retained",
                             return_value=(self.failures, self.prefixes)),
                patch.object(gate, "_collect_live_baseline", return_value=(
                    self.sql, self.files,
                    sha256(self.events.read_bytes()).hexdigest(),
                    self.events.stat().st_size, True, self.readiness)),
                patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                        str(self.worker.resolve())}),
            ):
                stack.enter_context(context)
            result = gate.prepare(**self.kwargs(), execute_baseline_check=True)
            receipt_path = self.epoch / gate.GATE_FILE
            self.assertEqual(result["schema"], gate.GATE_SCHEMA)
            verified = audit.audit(**self.kwargs())
            self.assertEqual(verified["gate_sha256"], result["gate_sha256"])
            self.assertEqual(verified["db_readiness_probe_count"], 1)
            receipt = protocol.private_json(receipt_path)
            receipt["db_readiness"]["observations"][-1]["psql_exit_code"] = 1
            receipt_path.write_bytes(protocol.canonical(receipt))
            with self.assertRaisesRegex(audit.GateAuditError,
                                        "select_1_unverified"):
                audit.audit(**self.kwargs())

    def test_prior_v3_outputs_reject_before_service_call(self) -> None:
        (self.epoch / gate.prior_gate.GATE_FILE).write_text("{}\n")
        with ExitStack() as stack:
            for context in (
                patch.object(source, "validate", return_value={}),
                patch.object(gate.power, "capture",
                             return_value=power_sample(0)),
                patch.object(gate.plan_audit, "audit", return_value={}),
                patch.object(gate.protocol, "_worker_split",
                             return_value=self.private),
                patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                        str(self.worker.resolve())}),
            ):
                stack.enter_context(context)
            with patch.object(gate, "_collect_live_baseline") as live:
                with self.assertRaisesRegex(gate.NoGuiGateError,
                                            "prior_v3_output_present"):
                    gate.prepare(**self.kwargs(),
                                 execute_baseline_check=True)
                live.assert_not_called()

    def test_timeout_at_live_gate_writes_no_result_files(self) -> None:
        with ExitStack() as stack:
            for context in (
                patch.object(source, "validate", return_value={}),
                patch.object(gate.power, "capture",
                             return_value=power_sample(0)),
                patch.object(gate.plan_audit, "audit", return_value={}),
                patch.object(gate.protocol, "_worker_split",
                             return_value=self.private),
                patch.object(gate.retained, "reaudit_retained",
                             return_value=(self.failures, self.prefixes)),
                patch.object(gate, "_collect_live_baseline",
                             side_effect=gate.NoGuiGateError(
                                 "no_gui_gate_db_readiness_timeout_no_receipt")),
                patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                        str(self.worker.resolve())}),
            ):
                stack.enter_context(context)
            with self.assertRaisesRegex(gate.NoGuiGateError,
                                        "readiness_timeout_no_receipt"):
                gate.prepare(**self.kwargs(), execute_baseline_check=True)
        self.assertFalse(any((self.epoch / name).exists()
                             for name in (gate.GATE_FILE, gate.SQL_FILE,
                                          gate.FILES_FILE)))

    def test_v4_runner_and_batch_use_v4_gate(self) -> None:
        self.assertEqual(source.validate()["schema"], source.SCHEMA)
        self.assertIs(runner.gate_audit, audit)
        self.assertIs(batch.gate_audit, audit)
        self.assertIs(runner.source, source)
        self.assertIs(batch.source, source)
        self.assertEqual(audit.PUBLIC_AUDIT.parent,
                         protocol.ROOT / "docs/evidence")


if __name__ == "__main__":
    unittest.main()
