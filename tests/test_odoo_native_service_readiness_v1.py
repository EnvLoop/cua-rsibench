"""Fake-only startup, accepted readiness and exact failure service cleanup."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import native_service_readiness_v1 as startup


def ready():
    return {"status": "postgres_health_and_select_1_ready", "query": "SELECT 1",
            "probe_count": 1, "elapsed_milliseconds": 20,
            "observations": [{"attempt": 1, "services": ["db"], "compose_ps_exit_code": 0,
                              "pg_isready_exit_code": 0, "psql_exit_code": 0}]}


class FakeServices:
    def __init__(self, before=()):
        self.services = set(before)
        self.calls = []
        self.receipts = []
        self.fail_command = None
        self.status_failure_after = None
        self.status_calls = 0

    def compose(self, *args):
        self.calls.append(args)
        if args[0] == "up":
            self.services.add(args[-1])
        elif args[0] == "stop":
            self.services.discard(args[-1])
        else:
            raise AssertionError("Only native service commands allowed")
        if args == self.fail_command:
            self.fail_command = None
            raise subprocess.CalledProcessError(1, list(args), output="private details")
        return subprocess.CompletedProcess(list(args), 0)

    def running(self):
        self.status_calls += 1
        if self.status_failure_after is not None and self.status_calls >= self.status_failure_after:
            raise OSError("status unavailable")
        return set(self.services)

    def sink(self, receipt):
        self.receipts.append(deepcopy(receipt))

    def ensure(self, before=None):
        return startup.ensure_ready(worker=Path("/fake/worker"),
                                    running_before=set(self.services) if before is None else before,
                                    compose=self.compose, running=self.running, receipt_sink=self.sink)


class ServiceReadinessTests(unittest.TestCase):
    def test_cold_start_readiness_precedes_web_and_receipt_rederives(self):
        fake = FakeServices()

        def gate(worker):
            self.assertEqual(worker, Path("/fake/worker"))
            self.assertEqual(fake.services, {"db"})
            self.assertEqual(fake.calls, [("up", "-d", "db")])
            return ready()

        with patch.object(startup, "_wait_db_ready", side_effect=gate):
            receipt = fake.ensure()
        self.assertEqual(fake.calls, [("up", "-d", "db"), ("up", "-d", "web")])
        self.assertEqual(fake.services, {"db", "web"})
        self.assertEqual(fake.receipts, [receipt])
        self.assertEqual(startup.validate_ready_receipt(receipt), receipt)

    def test_warm_both_stops_web_before_accepted_db_only_probe(self):
        fake = FakeServices({"db", "web"})

        def gate(_worker):
            self.assertEqual(fake.services, {"db"})
            return ready()

        with patch.object(startup, "_wait_db_ready", side_effect=gate):
            receipt = fake.ensure()
        self.assertEqual(fake.calls, [("stop", "web"), ("up", "-d", "db"), ("up", "-d", "web")])
        self.assertEqual(receipt["running_before"], ["db", "web"])
        startup.validate_ready_receipt(receipt)

    def test_readiness_failure_stops_new_db_without_reset_or_web_start(self):
        fake = FakeServices()
        with patch.object(startup, "_wait_db_ready", side_effect=TimeoutError):
            with self.assertRaisesRegex(startup.NativeServiceReadinessError, startup.FAILED_STATUS) as caught:
                fake.ensure()
        receipt = caught.exception.receipt
        self.assertEqual(fake.calls, [("up", "-d", "db"), ("stop", "db")])
        self.assertEqual(fake.services, set())
        self.assertIs(receipt["original_services_restored"], True)
        self.assertEqual(receipt["running_after"], [])
        self.assertEqual(fake.receipts, [receipt])
        self.assertEqual(receipt["error_type"], "TimeoutError")

    def test_partial_up_db_failure_still_restores_cold_state(self):
        fake = FakeServices()
        fake.fail_command = ("up", "-d", "db")
        with patch.object(startup, "_wait_db_ready", side_effect=AssertionError("no readiness call")) as gate:
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                fake.ensure()
        gate.assert_not_called()
        self.assertEqual(fake.calls, [("up", "-d", "db"), ("stop", "db")])
        self.assertEqual(fake.services, set())
        self.assertIs(caught.exception.receipt["original_services_restored"], True)

    def test_failed_gate_restores_original_db_and_web_set(self):
        fake = FakeServices({"db", "web"})
        with patch.object(startup, "_wait_db_ready", side_effect=TimeoutError):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                fake.ensure()
        self.assertEqual(fake.calls, [("stop", "web"), ("up", "-d", "db"), ("up", "-d", "web")])
        self.assertEqual(fake.services, {"db", "web"})
        self.assertIs(caught.exception.receipt["original_services_restored"], True)

    def test_partial_web_up_failure_restores_original_db_only(self):
        fake = FakeServices({"db"})
        fake.fail_command = ("up", "-d", "web")
        with patch.object(startup, "_wait_db_ready", return_value=ready()):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                fake.ensure()
        self.assertEqual(fake.calls, [("up", "-d", "db"), ("up", "-d", "web"), ("stop", "web")])
        self.assertEqual(fake.services, {"db"})
        self.assertIs(caught.exception.receipt["original_services_restored"], True)

    def test_failed_gate_restores_web_only_without_starting_dependency(self):
        fake = FakeServices({"web"})
        original = fake.compose

        def compose(*args):
            reply = original(*args)
            if args[0] == "up" and args[-1] == "web" and "--no-deps" not in args:
                fake.services.add("db")
            return reply

        with patch.object(startup, "_wait_db_ready", side_effect=TimeoutError):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                startup.ensure_ready(worker=Path("/fake/worker"), running_before={"web"},
                                     compose=compose, running=fake.running, receipt_sink=fake.sink)
        self.assertEqual(fake.services, {"web"})
        self.assertEqual(fake.calls[-1], ("up", "-d", "--no-deps", "web"))
        self.assertIs(caught.exception.receipt["original_services_restored"], True)

    def test_invalid_ready_evidence_is_failed_gate_and_never_starts_web(self):
        fake = FakeServices()
        invalid = ready()
        invalid["observations"][-1]["psql_exit_code"] = 1
        with patch.object(startup, "_wait_db_ready", return_value=invalid):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                fake.ensure()
        self.assertEqual(fake.calls, [("up", "-d", "db"), ("stop", "db")])
        self.assertEqual(caught.exception.receipt["phases"][2]["status"], "failed")
        self.assertEqual(caught.exception.receipt["db_readiness"], invalid)

    def test_cleanup_status_failure_preserves_unknown_claim(self):
        fake = FakeServices()
        fake.status_failure_after = 2
        with patch.object(startup, "_wait_db_ready", side_effect=TimeoutError):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                fake.ensure()
        self.assertIsNone(caught.exception.receipt["original_services_restored"])
        self.assertIsNone(caught.exception.receipt["running_after"])
        self.assertEqual(fake.calls, [("up", "-d", "db"), ("stop", "web"), ("stop", "db")])

    def test_cleanup_command_failure_reports_mismatch_truthfully(self):
        fake = FakeServices()
        original = fake.compose

        def compose(*args):
            if args == ("stop", "db"):
                fake.calls.append(args)
                raise OSError("stop failed before effect")
            return original(*args)

        with patch.object(startup, "_wait_db_ready", side_effect=TimeoutError):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                startup.ensure_ready(worker=Path("/fake/worker"), running_before=set(),
                                     compose=compose, running=fake.running, receipt_sink=fake.sink)
        self.assertIs(caught.exception.receipt["original_services_restored"], False)
        self.assertEqual(caught.exception.receipt["running_after"], ["db"])

    def test_sink_failure_cleans_services_and_keeps_receipt_on_fixed_error(self):
        fake = FakeServices()
        with patch.object(startup, "_wait_db_ready", return_value=ready()):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                startup.ensure_ready(worker=Path("/fake/worker"), running_before=set(),
                                     compose=fake.compose, running=fake.running,
                                     receipt_sink=lambda _receipt: (_ for _ in ()).throw(OSError("private path")))
        self.assertEqual(fake.services, set())
        self.assertEqual(caught.exception.receipt["receipt_sink_error_type"], "OSError")
        self.assertIs(caught.exception.receipt["original_services_restored"], True)
        self.assertNotIn("private path", str(caught.exception))

    def test_nonzero_compose_result_is_not_success(self):
        fake = FakeServices()

        def compose(*args):
            reply = fake.compose(*args)
            return subprocess.CompletedProcess(args, 1) if args == ("up", "-d", "db") else reply

        with patch.object(startup, "_wait_db_ready", side_effect=AssertionError("no readiness call")):
            with self.assertRaises(startup.NativeServiceReadinessError) as caught:
                startup.ensure_ready(worker=Path("/fake/worker"), running_before=set(),
                                     compose=compose, running=fake.running, receipt_sink=fake.sink)
        self.assertIs(caught.exception.receipt["original_services_restored"], True)
        self.assertEqual(fake.services, set())

    def test_validator_rejects_weakened_policy_query_order_and_bool_codes(self):
        fake = FakeServices()
        with patch.object(startup, "_wait_db_ready", return_value=ready()):
            receipt = fake.ensure()
        for change in ("bounds", "bounds_type", "query", "order", "command", "services", "bool"):
            bad = deepcopy(receipt)
            if change == "bounds":bad["readiness_bounds"]["timeout_seconds"] = 90
            elif change == "bounds_type":bad["readiness_bounds"]["poll_seconds"] = True
            elif change == "query":bad["db_readiness"]["query"] = "SELECT 2"
            elif change == "order":bad["phases"][1], bad["phases"][2] = bad["phases"][2], bad["phases"][1]
            elif change == "command":bad["phases"][1]["command"] = ["exec", "db", "psql"]
            elif change == "services":bad["running_after"] = ["db"]
            else:bad["db_readiness"]["observations"][-1]["psql_exit_code"] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                startup.validate_ready_receipt(bad)

    def test_accepted_dependency_is_called_without_running_native_probe(self):
        from tools import odoo_v066_train_attachment_calibration_v13 as accepted
        with patch.object(accepted, "_wait_db_ready", return_value=ready()) as gate:
            self.assertEqual(startup._wait_db_ready(Path("/fake/worker")), ready())
        gate.assert_called_once_with(Path("/fake/worker"))
        with patch.object(accepted, "READINESS_TIMEOUT_S", 90), patch.object(accepted, "_wait_db_ready") as gate:
            with self.assertRaisesRegex(ValueError, "policy_changed"):
                startup._wait_db_ready(Path("/fake/worker"))
        gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
