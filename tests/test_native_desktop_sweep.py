"""Check bounded GUI sweep planning without making a provider call."""

from __future__ import annotations

from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import calibrate_sweep, factory_v2, source


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
