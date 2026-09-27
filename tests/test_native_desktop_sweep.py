"""Check bounded GUI sweep planning without making a provider call."""

from __future__ import annotations

from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import (budget_ledger, calibrate_sweep,
                                    factory_v2, reconcile_single_noid, source)


class SweepBudgetTests(unittest.TestCase):
    def test_worst_case_lease_reservation_and_concurrency(self):
        reserve = calibrate_sweep.validate_budget(
            lease_seconds=300, max_new_sandboxes=30,
            max_estimated_usd=Decimal("3.00"),
            usd_per_hour_upper=Decimal("1.00"), concurrency=2)
        self.assertEqual(reserve, Decimal("2.5"))
        with self.assertRaisesRegex(ValueError, "USD ceiling"):
            calibrate_sweep.validate_budget(
                lease_seconds=300, max_new_sandboxes=30,
                max_estimated_usd=Decimal("2.00"),
                usd_per_hour_upper=Decimal("1.00"), concurrency=2)
        with self.assertRaisesRegex(ValueError, "published"):
            calibrate_sweep.validate_budget(
                lease_seconds=300, max_new_sandboxes=30,
                max_estimated_usd=Decimal("3.00"),
                usd_per_hour_upper=Decimal("0.35"), concurrency=2)
        with self.assertRaisesRegex(ValueError, "concurrency"):
            calibrate_sweep.validate_budget(
                lease_seconds=300, max_new_sandboxes=30,
                max_estimated_usd=Decimal("2"),
                usd_per_hour_upper=Decimal("1.00"), concurrency=4)

    def test_lane_ledger_counts_diagnostics_and_each_health_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, seconds in (("batch-001", 300), ("batch-002", 1000)):
                path = root / "final-v2-normalization" / name / "batch-receipt.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"schema": "cua-native-impress-batch-normalization-v1",
                                            "status": "finished", "lease_seconds": seconds,
                                            "sandbox_id_sha256": name}))
            diagnostic = root / "gui-diagnostics" / "sample" / "positive" / "receipt.json"
            diagnostic.parent.mkdir(parents=True)
            diagnostic.write_text(json.dumps({"schema": "cua-native-wdi-gui-development-attempt-v1",
                                              "status": "control_passed", "sandbox_timeout_seconds": 180,
                                              "sandbox_id_sha256": "diagnostic"}))
            for name in ("outage", "later"):
                path = root / "sweep-runs" / name / "health-probe.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"schema": "cua-native-wdi-e2b-recovery-health-probe-v1",
                                            "status": "healthy_and_terminated", "lease_seconds": 120,
                                            "sandbox_id_sha256": name}))
            diagnostic_probe = root / "gui-diagnostics" / "health-probe-later.json"
            diagnostic_probe.write_text(json.dumps({
                "schema": "cua-native-wdi-e2b-recovery-health-probe-v1",
                "status": "healthy_and_terminated", "lease_seconds": 120,
                "sandbox_id_sha256": "diagnostic-health",
            }))
            result = budget_ledger.audit(root, proposed_new_sandboxes=2,
                                         proposed_lease_seconds=300,
                                         max_lane_reserved_usd=Decimal("40"))
            self.assertEqual(result["past_by_kind"], {"gui_attempt": 1,
                                                        "health_probe": 3,
                                                        "neutral_batch": 2})
            self.assertEqual(result["past_full_server_lease_seconds"], 1840)
            self.assertTrue(result["within_cap"])

    def test_noid_transport_waits_for_full_lease_and_health_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary) / "attempt"
            attempt.mkdir()
            (attempt / "receipt.json").write_text(json.dumps({
                "status": "error", "error_type": "ConnectError",
                "sandbox_id_sha256": None, "staged_sha256": None,
                "actor_actions": [], "sandbox_timeout_seconds": 300,
            }))
            birth = attempt.stat().st_birthtime
            with patch.object(reconcile_single_noid.time, "time", return_value=birth + 389), \
                 patch.object(reconcile_single_noid, "active_hashes", return_value=(set(), 0)):
                early = reconcile_single_noid.reconcile(attempt, grace_seconds=90, query_provider=True)
            self.assertFalse(early["ready_for_separate_health_probe"])
            with patch.object(reconcile_single_noid.time, "time", return_value=birth + 391), \
                 patch.object(reconcile_single_noid, "active_hashes", return_value=(set(), 0)):
                final = reconcile_single_noid.reconcile(attempt, grace_seconds=90, query_provider=True)
            self.assertTrue(final["ready_for_separate_health_probe"])


@unittest.skipUnless(all(importlib.util.find_spec(x) for x in ("openpyxl", "pptx", "docx")),
                     "Office document builders unavailable")
class SweepPlanTests(unittest.TestCase):
    def test_scripts_are_gui_only_and_existing_failure_is_not_replayed(self):
        countries = list(source.COUNTRIES)
        mapping = {"schema": "cua-native-wdi-private-map-v1", "train": countries[:5],
                   "selection": countries[5:10], "final_candidate": countries[10:],
                   "variant_salt": "d" * 64}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            factory_v2.generate(candidate, mapping)
            inventory = json.loads((candidate / "candidate-inventory.json").read_bytes())
            for workflow in ("calc-growth", "impress-deck", "writer-brief"):
                row = next(r for r in inventory["tasks"] if r["split"] == "final_candidate"
                           and r["workflow"] == workflow)
                package_dir = candidate / "final_candidate" / row["task_id"]
                oracle = json.loads((package_dir / "oracle.json").read_bytes())
                positive = calibrate_sweep.actor_script(package_dir, oracle, "positive")
                near = calibrate_sweep.actor_script(package_dir, oracle, "near-miss")
                self.assertNotEqual(positive, near)
                self.assertIn("press ctrl,s", positive)
                self.assertIn("readback\nstop", positive)
                self.assertNotIn("commands.run", positive)
                self.assertNotIn("files.write", positive)
                if workflow == "writer-brief":
                    self.assertIn("press ctrl,h", positive)
                    self.assertIn("assert_window Find and Replace", positive)
                    self.assertIn("assert_window LibreOffice Writer", positive)
                    self.assertNotIn("press ctrl,f", positive)
                self.assertEqual(calibrate_sweep.actor_script(package_dir, oracle, "cold-reset"), "stop\n")
            attempts = root / "attempts"
            selected, _ = calibrate_sweep.plan(candidate, attempts,
                                               max_tasks=1, max_new_sandboxes=3)
            self.assertEqual(len(selected), 1)
            failed = attempts / selected[0]["row"]["task_id"] / "positive"
            failed.mkdir(parents=True)
            (failed / "receipt.json").write_text(json.dumps({"status": "error"}))
            selected_again, deferred = calibrate_sweep.plan(candidate, attempts,
                                                              max_tasks=1, max_new_sandboxes=3)
            self.assertNotEqual(selected_again[0]["row"]["task_id"], selected[0]["row"]["task_id"])
            self.assertTrue(any(x["reason"] == "existing_attempt_failed_or_uncertain" for x in deferred))

            def fake_transport_failure(_candidate, _attempts, item, _lease, *, dry_run,
                                       expected_template_id=None):
                return {"task_id": item["row"]["task_id"],
                        "status": "stopped_after_failed_or_uncertain_attempt",
                        "attempts": [{"attempt": "positive", "status": "failed",
                                      "child_error_type": "ConnectError",
                                      "sandbox_id_observed": False}]}

            with patch.object(calibrate_sweep, "_run_task", side_effect=fake_transport_failure):
                result = calibrate_sweep.execute(
                    candidate, root / "fresh-attempts", root / "circuit-receipt",
                    max_tasks=5, max_new_sandboxes=15, lease_seconds=300,
                    max_estimated_usd=Decimal("1.25"),
                    usd_per_hour_upper=Decimal("1"), concurrency=1,
                    max_wall_seconds=600, dry_run=True,
                    max_infrastructure_create_errors=2)
            self.assertEqual(len(result["results"]), 2)
            self.assertEqual(result["circuit_breaker"]["reason"], "E2B_ConnectError_threshold")
            self.assertEqual(result["unstarted_due_circuit_breaker"], 3)


if __name__ == "__main__":
    unittest.main()
