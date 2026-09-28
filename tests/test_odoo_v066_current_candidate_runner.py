"""Fake one-case current-epoch dispatch ordering and fail-closed gates."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import odoo_v066_current_candidate_one_selection_v1 as runner
from tools import odoo_v066_current_candidate_epoch_v1 as epoch
from tools import odoo_v066_scale_protocol_v1 as protocol


class FakeLease:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @contextmanager
    def exclusive_worker_operation(self, operation: str):
        self.events.append("lease_acquired")
        try:
            yield
        finally:
            self.events.append("lease_released")


class CurrentCandidateRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / "selection"
        self.private = self.worker / "private"
        (self.private / "v066_scale_controls").mkdir(parents=True,
                                                     mode=0o700)
        self.private.chmod(0o700)
        self.plan_path = self.root / "plan.private.json"
        self.public_path = self.root / "plan.public.json"
        self.old_private = self.root / "old.private.json"
        self.old_public = self.root / "old.public.json"
        self.source_freeze = self.root / "source-freeze.json"
        for path in (self.public_path, self.old_private, self.old_public,
                     self.source_freeze):
            path.write_text("{}\n", encoding="utf-8")
            path.chmod(0o600)
        self.plan = {
            "split": "selection",
            "fresh_run_directory_name": "current-candidate-" + "a" * 32,
            "run_nonce_hex": "a" * 32,
            "source_freeze_sha256": "b" * 64,
            "physical_dispatch_profile": protocol.PINNED_BORDER_PROFILE,
            "current_candidate_private_sha256": "c" * 64,
            "historical_ratification_sha256": protocol.RATIFICATION_SHA,
            "tasks": [{
                "task_id": "FAKE-CASE-1", "family": "inventory",
                "package_sha256": "d" * 64,
                "task_binding_sha256": "e" * 64,
                "source_asset_sha256": "f" * 64,
                "split": "selection",
            }],
        }
        protocol.write_new(self.plan_path, self.plan, private=True)
        protocol.write_new(self.private / "partition_cases.json", {
            "cases": {"inventory": [
                {"id": "FAKE-CASE-1", "family": "inventory"},
                {"id": "FAKE-WRONG-2", "family": "inventory"}]},
        }, private=True)
        self.events: list[str] = []

    def _mocks(self):
        gate_value = {
            "status": "no_gui_current_sql_full_filestore_gate_independently_verified",
            "gate_sha256": "9" * 64,
        }
        return (
            patch.object(runner.source, "validate", return_value={}),
            patch.object(runner.source, "FREEZE", self.source_freeze),
            patch.object(runner.gate, "_ac_power", return_value=True),
            patch.object(runner.plan_audit, "audit", return_value={}),
            patch.object(runner.gate_audit, "audit", return_value=gate_value),
            patch.object(runner.protocol, "_worker_split",
                         return_value=self.private),
            patch.object(runner.controller, "_run_lock",
                         return_value=nullcontext()),
            patch.object(runner.controller, "_modules",
                         return_value=(object(), object(), object(),
                                       object(), FakeLease(self.events))),
            patch.dict(os.environ, {"ENVLOOP_ODOO_WORKER_DIR":
                                    str(self.worker.resolve())}),
        )

    def _run(self, **options):
        return runner.run_one(
            worker_dir=self.worker, historical_root=self.root,
            private_plan=self.plan_path, public_plan=self.public_path,
            old_private_plan=self.old_private,
            old_public_plan=self.old_public, **options)

    def test_fake_one_case_positive_negative_reset_and_lease_order(self):
        def execute(**kwargs):
            self.events.append("gui")
            self.assertEqual(kwargs["case"]["id"], "FAKE-CASE-1")
            self.assertEqual(kwargs["wrong"]["id"], "FAKE-WRONG-2")
            self.assertEqual(kwargs["row"]["current_candidate_private_sha256"],
                             "c" * 64)
            attempt = kwargs["run_dir"] / "attempt-000"
            attempt.mkdir(mode=0o700)
            protocol.write_new(attempt / "attempt.private.json", {
                "schema": "fake-saved-positive-negative-reset",
            }, private=True)

        def case_audit(**_kwargs):
            self.events.append("case_audit")
            return {
                "status": "current_candidate_raw_gui_semantics_verified_source_visual_review_pending",
                "independent_baseline_reward": 0.0,
                "independent_positive_reward": 1.0,
                "independent_wrong_object_reward": 0.0,
                "full_pre_web_filestore_reset_exact": True,
                "protected_post_web_source_bytes_equal": True,
                "source_visual_review_pending": True,
                "official_final_tasks_admitted": 0,
            }

        def batch_audit(**_kwargs):
            self.events.append("batch_audit")
            return {
                "status": "one_raw_selection_control_independently_verified_visual_review_pending",
                "independently_verified_raw_selection_controls": 1,
                "official_final_tasks_admitted": 0,
            }

        with self._mocks()[0], self._mocks()[1], self._mocks()[2], \
                self._mocks()[3], self._mocks()[4], self._mocks()[5], \
                self._mocks()[6], self._mocks()[7], self._mocks()[8]:
            result = self._run(execute=True, case_executor=execute,
                               case_auditor=case_audit,
                               batch_auditor=batch_audit)
        self.assertEqual(self.events,
                         ["lease_acquired", "gui", "lease_released",
                          "case_audit", "batch_audit"])
        self.assertEqual(result["independently_audited_raw_cases"], 1)
        self.assertEqual(result["official_final_tasks_admitted"], 0)
        self.assertEqual(result["model_attempts"], 0)

    def test_missing_execute_or_ac_never_creates_run(self):
        with self.assertRaisesRegex(runner.CurrentControlError,
                                    "explicit_execute"):
            self._run(execute=False)
        with patch.object(runner.gate, "_ac_power", return_value=False):
            with self.assertRaisesRegex(runner.CurrentControlError,
                                        "verified_ac_power"):
                self._run(execute=True)
        self.assertFalse((self.private / "v066_scale_controls" /
                          self.plan["fresh_run_directory_name"]).exists())

    def test_existing_same_nonce_run_is_terminal_no_replay(self):
        run_dir = (self.private / "v066_scale_controls" /
                   self.plan["fresh_run_directory_name"])
        run_dir.mkdir(mode=0o700)
        mocks = self._mocks()
        from contextlib import ExitStack
        with ExitStack() as stack:
            for context in mocks:
                stack.enter_context(context)
            with self.assertRaisesRegex(runner.CurrentControlError,
                                        "fresh_run_already_exists"):
                self._run(execute=True)
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
