"""Bounded continuation cannot create a provider lease in offline plan mode."""

from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_day_rollover_continuation_v2 as control


class ContinuationTests(unittest.TestCase):
    def test_offline_plan_skips_two_quarantined_ids_and_never_calls_provider(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            attempts = root / "v066-final-gui"
            rows = [{"task_id": f"train-final-{index}"}
                    for index in range(100)]
            paths = {"attempts_root": attempts,
                     "old_original_root": root / "old/v066-final-gui",
                     "old_caret_root": root / "caret/v066-final-gui",
                     "old_failed_scoped_root": root / "scoped/v066-final-gui"}
            progress = {"independently_accepted_complete_trios": 7}
            with (patch.object(control, "validate_live",
                               return_value=({}, progress, paths, rows)),
                  patch.object(control, "combined_budget",
                               return_value={"combined_full_lease_intents": 53}),
                  patch.object(control, "active_hashes",
                               side_effect=AssertionError("No provider query")),
                  patch.object(control, "_run_one_task",
                               side_effect=AssertionError("No sandbox"))):
                result = control.run_batch(
                    freeze_path=root / "freeze.private.json",
                    run_dir=root / "unused", max_new_ids=2,
                    execute=False)
                self.assertEqual(result["new_ids_selected"], 2)
                self.assertEqual(result["status"],
                                 "offline_bounded_continuation_plan")
                self.assertFalse(attempts.exists())
                with self.assertRaisesRegex(ValueError, "One or two"):
                    control.run_batch(
                        freeze_path=root / "freeze.private.json",
                        run_dir=root / "unused", max_new_ids=3,
                        execute=False)

    def test_one_root_owned_batch_has_terminal_journal_without_real_provider(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            attempts = root / "work/v066-final-gui"
            run_dir = root / "work/v066-continuation-runs/batch-0001"
            rows = [{"task_id": f"train-final-{index}"}
                    for index in range(100)]
            paths = {key: root / key for key in (
                "bridge_path", "old_original_root", "old_caret_root",
                "old_failed_scoped_root",
                "public_day_audit", "private_day_audit", "reference_path",
                "runtime_freeze", "failed_private_stop",
                "failed_public_interruption", "candidate_root",
                "private_map", "profile_private", "guest_public",
                "fair_public", "action_ratification", "reservation")}
            paths["attempts_root"] = attempts
            before = {"independently_accepted_complete_trios": 7}
            after = {"independently_accepted_complete_trios": 8}
            freeze = root / "freeze.private.json"
            freeze.write_text("frozen")
            with (patch.object(control, "validate_live", side_effect=[
                    ({}, before, paths, rows),
                    ({}, after, paths, rows)]),
                  patch.dict(control.os.environ, {"E2B_API_KEY": "test"}),
                  patch.object(control, "combined_budget",
                               return_value={"combined_full_lease_intents": 53}),
                  patch.object(control, "active_hashes",
                               side_effect=[(set(), 0), (set(), 0)]),
                  patch.object(control, "_run_one_task", return_value={
                      "status": "provisional_trio_complete"}) as child):
                result = control.run_batch(
                    freeze_path=freeze, run_dir=run_dir,
                    max_new_ids=1, execute=True)
            self.assertEqual(result["status"],
                             "bounded_completed_and_audited")
            self.assertEqual(result["new_complete_trios"], 1)
            self.assertEqual(child.call_count, 1)
            journal = json.loads((run_dir / "run-receipt.json").read_bytes())
            self.assertEqual(journal["status"],
                             "bounded_completed_and_audited")
            self.assertEqual(journal["official_final_admissions"], 0)

    def test_missing_dedicated_credential_refuses_before_intent(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            attempts = root / "work/v066-final-gui"
            run_dir = root / "work/v066-continuation-runs/batch-0001"
            rows = [{"task_id": f"train-final-{index}"}
                    for index in range(100)]
            paths = {"attempts_root": attempts,
                     "old_original_root": root / "old/v066-final-gui",
                     "old_caret_root": root / "caret/v066-final-gui",
                     "old_failed_scoped_root": root / "scoped/v066-final-gui"}
            with (patch.object(control, "validate_live", return_value=(
                    {}, {"independently_accepted_complete_trios": 7},
                    paths, rows)),
                  patch.object(control, "combined_budget", return_value={}),
                  patch.dict(control.os.environ, {"E2B_API_KEY": ""}),
                  patch.object(control, "active_hashes",
                               side_effect=AssertionError("No provider query")),
                  patch.object(control, "_run_one_task",
                               side_effect=AssertionError("No child"))):
                with self.assertRaisesRegex(ValueError, "credential absent"):
                    control.run_batch(
                        freeze_path=root / "freeze.private.json",
                        run_dir=run_dir, max_new_ids=1, execute=True)
            self.assertFalse(run_dir.exists())


if __name__ == "__main__":
    unittest.main()
