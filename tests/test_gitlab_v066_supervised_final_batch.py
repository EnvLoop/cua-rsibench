"""Fake-child tests for immutable GitLab one-ID batching and no replay."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import v066_supervised_final_batch_v1 as batch


class BatchJournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.run = self.private / "run"
        self.run.mkdir(mode=0o700)
        self.supervision = self.run / "supervision"
        self.supervision.mkdir(mode=0o700)
        self.batches = self.run / "batches"
        self.batches.mkdir(mode=0o700)
        (self.root / "docs/evidence").mkdir(parents=True)
        self.old_sha = "a" * 64
        self.plan_sha = "b" * 64
        self.old = {"task_roster": [
            {"task_id": f"private-{index:03d}",
             "package_sha256": f"{index:064x}"}
            for index in range(100)],
            "baseline_business_sha256": "c" * 64}
        self.original_count = 3
        self.failed = False
        self.dispatched = []
        self.patches = [
            patch.object(batch, "ROOT", self.root),
            patch.object(batch, "BATCH_DIR", self.batches),
            patch.object(batch, "PRIVATE_PLAN", self.batches / "source-plan.private.json"),
            patch.object(batch.one, "ROOT", self.root),
            patch.object(batch.one, "PRIVATE_ROOT", self.private),
            patch.object(batch.one, "RUN_DIR", self.run),
            patch.object(batch.one, "SUPERVISION", self.supervision),
            patch.object(batch, "validate_plan", return_value=(
                {}, self.old, {}, self.old_sha)),
            patch.object(batch.lane, "read_journal", side_effect=lambda *_:
                         [None] * self.original_count),
            patch.object(batch.lane, "journal_state", side_effect=self._original_state),
            patch.object(batch.lane, "audit_controls", side_effect=self._raw_audit),
            patch.object(batch.lane, "assert_live_world", side_effect=lambda *_:
                         {"business_sha256": "c" * 64}),
            patch.object(batch.one, "_prior_supervision_complete"),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        batch.one.write_new(batch.PRIVATE_PLAN, {"source": "fake"})

    def _original_state(self, _entries, _plan):
        return {"next_index": self.original_count, "pending": None,
                "failed": self.failed}

    def _raw_audit(self, *_args):
        private = {"schema": "envloop-gitlab-v066-control-audit-private-v1",
                   "status": "source_bound_evaluator_controls_only_not_official_admission",
                   "plan_sha256": self.old_sha,
                   "source_bundle_sha256": "d" * 64,
                   "completed_task_count": self.original_count,
                   "pending_intent": False, "terminal_failure": self.failed,
                   "all_100_controls_independently_validated": False,
                   "unissued_v06_proof_material": [],
                   "proof_files_issued": False,
                   "model_calls": 0, "official_final_admitted": 0,
                   "validated_tasks": [
                       {"task_id": self.old["task_roster"][index]["task_id"]}
                       for index in range(self.original_count)]}
        return private, {}

    def _write_supervisor_result(self, *, failure=False):
        index = self.original_count
        self.dispatched.append(index)
        status = ("one_id_terminal_no_replay_exactly_reset" if failure else
                  "one_id_completed_and_raw_receipts_independently_audited")
        batch.one.write_new(self.supervision /
                            f"{index:03d}-result.private.json", {
            "schema": batch.one.RESULT_SCHEMA,
            "status": status,
            "task_index": index,
            "task_id": self.old["task_roster"][index]["task_id"],
            "original_100_id_plan_sha256": self.old_sha,
            "post_attempt_baseline_exact": True,
            "raw_audit": {"completed_task_count": index + 1,
                          "all_current_raw_receipts_reopened": True}
            if not failure else None,
            "provider_or_gui_replay_authorized": False,
            "official_final_admitted": 0,
            "child": {"child_terminated": True, "timed_out": False,
                      "exit_code": 0 if not failure else 1},
        })
        if failure:
            self.failed = True
        else:
            self.original_count += 1
        return {"status": status}

    def test_two_bounded_batches_advance_once_per_id_and_write_receipts(self):
        with patch.object(batch.one, "run_one", side_effect=lambda *_:
                          self._write_supervisor_result()):
            first = batch.run_batch(self.private / "ratification.json",
                                    max_new_ids=3)
            second = batch.run_batch(self.private / "ratification.json",
                                     max_new_ids=2)
        self.assertEqual(self.dispatched, [3, 4, 5, 6, 7])
        self.assertEqual((first["completed_count"], first["next_index"]), (3, 6))
        self.assertEqual((second["completed_count"], second["next_index"]), (2, 8))
        entries, state = batch._read_journal(
            batch.one.sha(batch.PRIVATE_PLAN.read_bytes()), self.old)
        self.assertEqual(state["next_index"], 8)
        self.assertEqual(len(state["closed_batches"]), 2)
        self.assertEqual(sum(e["kind"] == "id_intent" for e in entries), 5)
        self.assertEqual(sum(e["kind"] == "id_completed" for e in entries), 5)
        for number in (0, 1):
            private, public = batch._receipt_paths(number)
            self.assertTrue(private.exists())
            self.assertTrue(public.exists())
            self.assertEqual(private.stat().st_mode & 0o077, 0)
            self.assertEqual(json.loads(public.read_bytes())["official_final_admitted"], 0)

    def test_crash_after_intent_never_replays_and_only_reconciles_existing_result(self):
        with patch.object(batch.one, "run_one", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                batch.run_batch(self.private / "ratification.json", max_new_ids=2)
        self.assertEqual(self.dispatched, [])
        with patch.object(batch.one, "run_one", side_effect=AssertionError("replay")):
            with self.assertRaisesRegex(batch.BatchError,
                                        "pending_id_without_supervisor_result"):
                batch.run_batch(self.private / "ratification.json",
                                max_new_ids=2, resume_pending=True)
        self._write_supervisor_result()
        with patch.object(batch.one, "run_one", side_effect=lambda *_:
                          self._write_supervisor_result()):
            result = batch.run_batch(self.private / "ratification.json",
                                     max_new_ids=2, resume_pending=True)
        self.assertEqual(self.dispatched, [3, 4])
        self.assertEqual(result["next_index"], 5)
        self.assertEqual(result["completed_count"], 2)

    def test_failed_id_stops_and_cannot_start_another_batch(self):
        with patch.object(batch.one, "run_one", side_effect=lambda *_:
                          self._write_supervisor_result(failure=True)):
            result = batch.run_batch(self.private / "ratification.json",
                                     max_new_ids=3)
        self.assertEqual(self.dispatched, [3])
        self.assertEqual(result["status"], "stopped_on_failed_id_no_replay")
        with self.assertRaisesRegex(batch.BatchError, "prior_batch_failed_id_no_replay"):
            batch.run_batch(self.private / "ratification.json", max_new_ids=1)

    def test_hash_chain_tamper_fails_closed(self):
        with patch.object(batch.one, "run_one", side_effect=lambda *_:
                          self._write_supervisor_result()):
            batch.run_batch(self.private / "ratification.json", max_new_ids=1)
        journal = self.batches / "journal.private.jsonl"
        raw = journal.read_bytes().replace(b'"max_new_ids":1', b'"max_new_ids":2')
        journal.write_bytes(raw)
        with self.assertRaisesRegex(batch.BatchError,
                                    "batch_journal_hash_chain_changed"):
            batch._read_journal(batch.one.sha(batch.PRIVATE_PLAN.read_bytes()),
                                self.old)

    def test_read_only_audit_reopens_saved_supervisor_and_raw_digest(self):
        with patch.object(batch.one, "run_one", side_effect=lambda *_:
                          self._write_supervisor_result()):
            batch.run_batch(self.private / "ratification.json", max_new_ids=1)
        result = batch.audit(self.private / "ratification.json")
        self.assertEqual(result["completed_current_controls"], 4)
        self.assertFalse(result["pending_id"])
        receipt = self.supervision / "003-result.private.json"
        receipt.write_bytes(receipt.read_bytes().replace(
            b'"exit_code":0', b'"exit_code":1'))
        with self.assertRaisesRegex(batch.BatchError,
                                    "batch_audit_supervisor_result_bytes_changed"):
            batch.audit(self.private / "ratification.json")


if __name__ == "__main__":
    unittest.main()
