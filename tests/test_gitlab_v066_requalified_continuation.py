"""Offline contracts for the source-frozen GitLab continuation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import prospective_final_controls_v066 as lane
from gitlab_world import v066_requalified_continuation_v1 as continuation


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs/evidence").mkdir(parents=True)
        self.branch = self.root / "branch"
        self.branch.mkdir(mode=0o700)
        (self.branch / "attempts").mkdir(mode=0o700)
        self.continuation = self.branch / "continuation"
        self.continuation.mkdir(mode=0o700)
        self.supervision = self.continuation / "supervision"
        self.supervision.mkdir(mode=0o700)
        self.batches = self.continuation / "batches"
        self.batches.mkdir(mode=0o700)
        self.private_freeze = self.continuation / "source-freeze.private.json"
        continuation.one.write_new(self.private_freeze, {"frozen": True})
        self.public_freeze = self.root / "public-freeze.json"
        self.public_freeze.write_text("{}")
        self.old_sha = "a" * 64
        self.review_sha = "b" * 64
        self.old = {
            "task_roster": [{"task_id": f"private-{index:03d}",
                             "package_sha256": f"{index:064x}"}
                            for index in range(100)],
            "source_bundle_sha256": "c" * 64,
            "baseline_business_sha256": "d" * 64,
            "max_wall_seconds_per_task": 7200,
        }
        self._write_ten_prefix()
        self.audit = {
            "schema": "envloop-gitlab-v066-control-audit-private-v1",
            "plan_sha256": self.old_sha,
            "source_bundle_sha256": self.old["source_bundle_sha256"],
            "completed_task_count": 10,
            "pending_intent": False,
            "terminal_failure": False,
            "all_100_controls_independently_validated": False,
            "validated_tasks": [
                {"task_id": self.old["task_roster"][index]["task_id"]}
                for index in range(10)],
            "unissued_v06_proof_material": [],
            "proof_files_issued": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
        self.context = {
            "old": self.old, "old_sha": self.old_sha,
            "bound": {}, "audited": self.audit,
            "journal_state": {"next_index": 10, "pending": None,
                              "failed": False},
            "ten_validated_rows_sha256": continuation.one.sha(
                continuation.one.canonical(self.audit["validated_tasks"])),
            "v3_result_sha256": "e" * 64,
        }
        self.patches = [
            patch.object(continuation.one, "ROOT", self.root),
            patch.object(continuation.one, "PRIVATE_ROOT", self.root),
            patch.object(continuation, "ROOT", self.root),
            patch.object(continuation, "BRANCH", self.branch),
            patch.object(continuation, "CONTINUATION", self.continuation),
            patch.object(continuation, "SUPERVISION", self.supervision),
            patch.object(continuation, "BATCHES", self.batches),
            patch.object(continuation, "PRIVATE_FREEZE", self.private_freeze),
            patch.object(continuation, "PUBLIC_FREEZE", self.public_freeze),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    def _write_ten_prefix(self):
        entries = []
        path = self.branch / "journal.private.jsonl"
        for index in range(10):
            item = self.old["task_roster"][index]
            lane.append_event(path, self.old_sha, entries, {
                "kind": "intent", "task_index": index,
                "task_id": item["task_id"],
                "package_sha256": item["package_sha256"],
                "source_bundle_sha256": self.old["source_bundle_sha256"],
                "official_final_admitted": 0,
            })
            lane.append_event(path, self.old_sha, entries, {
                "kind": "terminal", "task_index": index,
                "task_id": item["task_id"],
                "status": "control_passed", "error_type": None,
                "wall_seconds": 1.0, "trio_receipt_sha256": "f" * 64,
                "official_final_admitted": 0,
            })

    def _mock_preflight(self):
        return [
            patch.object(continuation, "_reviewed_public_digest",
                         return_value=self.review_sha),
            patch.object(continuation, "validate_freeze",
                         return_value=({}, self.context, self.audit)),
            patch.object(continuation.lane, "assert_live_world",
                         return_value={"business_sha256": "d" * 64}),
        ]

    def _start_pending_id(self):
        plan_sha = continuation.one.sha(self.private_freeze.read_bytes())
        entries = []
        continuation._append_batch(entries, plan_sha, {
            "kind": "batch_start", "batch_number": 0,
            "start_index": 10, "max_new_ids": 1,
            "source_freeze_sha256": plan_sha,
            "automatic_same_id_replay": False,
        })
        item = self.old["task_roster"][10]
        continuation._append_batch(entries, plan_sha, {
            "kind": "id_intent", "batch_number": 0,
            "task_index": 10, "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "pre_id_raw_audit_sha256": "1" * 64,
            "baseline_business_sha256": "d" * 64,
            "source_freeze_sha256": plan_sha,
        })
        return plan_sha

    def test_public_freeze_omits_private_task_identity(self):
        private = {
            "source_bundle_sha256": "a" * 64,
            "original_100_id_plan_sha256": "b" * 64,
            "original_failed_journal_sha256": "c" * 64,
            "original_failed_attempt_manifest_sha256": "d" * 64,
            "v3_public_outcome_sha256": "e" * 64,
            "v3_private_audit_sha256": "f" * 64,
            "ten_journal_prefix_sha256": "1" * 64,
            "ten_validated_rows_sha256": "2" * 64,
            "private_task_id": "private-secret-answer",
        }
        public = continuation._public_freeze(private, "3" * 64)
        self.assertNotIn("private-secret-answer", json.dumps(public))
        self.assertEqual(public["remaining_original_roster_controls"], 90)
        self.assertEqual(public["max_new_ids_per_batch"], 5)

    def test_terminalize_only_next_identity_and_never_replays(self):
        journal = self.branch / "journal.private.jsonl"
        prefix = journal.read_bytes()
        self.assertTrue(continuation._terminalize_branch(
            self.context, 10, elapsed=3.0,
            error_type="SupervisedChildNonpassingExit"))
        state = lane.journal_state(
            lane.read_journal(self.branch, self.old_sha), self.old)
        self.assertEqual(state["next_index"], 10)
        self.assertTrue(state["failed"])
        self.assertTrue(journal.read_bytes().startswith(prefix))
        self.assertTrue(continuation._terminalize_branch(
            self.context, 10, elapsed=4.0,
            error_type="SupervisedChildNonpassingExit"))
        self.assertEqual(len(lane.read_journal(self.branch, self.old_sha)), 22)

    def test_batch_budget_above_five_rejected_before_dispatch(self):
        with self.assertRaisesRegex(
                continuation.ContinuationError,
                "explicit_bounded_continuation_batch_required"):
            continuation.run_batch(
                self.private_freeze,
                continuation.one.sha(self.public_freeze.read_bytes()),
                                   max_new_ids=6)

    def test_batch_journal_rejects_duplicate_id_intent(self):
        plan_sha = continuation.one.sha(self.private_freeze.read_bytes())
        entries = []
        continuation._append_batch(entries, plan_sha, {
            "kind": "batch_start", "batch_number": 0,
            "start_index": 10, "max_new_ids": 1,
            "source_freeze_sha256": plan_sha,
            "automatic_same_id_replay": False,
        })
        item = self.old["task_roster"][10]
        payload = {
            "kind": "id_intent", "batch_number": 0,
            "task_index": 10, "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "pre_id_raw_audit_sha256": "1" * 64,
            "baseline_business_sha256": "d" * 64,
            "source_freeze_sha256": plan_sha,
        }
        continuation._append_batch(entries, plan_sha, payload)
        continuation._append_batch(entries, plan_sha, payload)
        with self.assertRaisesRegex(
                continuation.ContinuationError,
                "continuation_batch_id_intent_invalid"):
            continuation._batch_journal(plan_sha, self.old)

    def test_pending_id_without_result_never_dispatches_again(self):
        plan_sha = continuation.one.sha(self.private_freeze.read_bytes())
        entries = []
        continuation._append_batch(entries, plan_sha, {
            "kind": "batch_start", "batch_number": 0,
            "start_index": 10, "max_new_ids": 1,
            "source_freeze_sha256": plan_sha,
            "automatic_same_id_replay": False,
        })
        item = self.old["task_roster"][10]
        continuation._append_batch(entries, plan_sha, {
            "kind": "id_intent", "batch_number": 0,
            "task_index": 10, "task_id": item["task_id"],
            "package_sha256": item["package_sha256"],
            "pre_id_raw_audit_sha256": "1" * 64,
            "baseline_business_sha256": "d" * 64,
            "source_freeze_sha256": plan_sha,
        })
        parts = self._mock_preflight()
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(continuation, "_run_one") as run:
            with self.assertRaisesRegex(
                    continuation.ContinuationError,
                    "pending_continuation_id_without_result_manual_review_no_replay"):
                continuation.run_batch(
                    self.private_freeze, self.review_sha,
                    max_new_ids=1, resume_pending=True)
            run.assert_not_called()

    def test_one_bounded_batch_dispatches_once_and_public_is_identity_free(self):
        parts = self._mock_preflight()
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(continuation, "_run_one") as run, \
             patch.object(continuation, "_verify_passed",
                          return_value=("1" * 64, "2" * 64)):
            run.side_effect = lambda *_args: continuation.one.write_new(
                self.supervision / "010-result.private.json", {"saved": True})
            public = continuation.run_batch(
                self.private_freeze, self.review_sha, max_new_ids=1)
            run.assert_called_once()
        self.assertEqual(public["status"], "completed_requested_ids")
        self.assertEqual(public["next_index"], 11)
        self.assertNotIn("private-010", json.dumps(public))
        self.assertFalse(public["official_final_admitted"])
        entries, state = continuation._batch_journal(
            continuation.one.sha(self.private_freeze.read_bytes()), self.old)
        self.assertEqual([row["kind"] for row in entries],
                         ["batch_start", "id_intent", "id_completed",
                          "batch_end"])
        self.assertEqual(state["next_index"], 11)

    def test_failed_id_closes_batch_and_blocks_next_dispatch(self):
        parts = self._mock_preflight()
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(continuation, "_run_one") as run, \
             patch.object(continuation, "_verify_passed",
                          side_effect=continuation.ContinuationError("nonpass")), \
             patch.object(continuation, "_verify_failed",
                          return_value="1" * 64):
            run.side_effect = lambda *_args: continuation.one.write_new(
                self.supervision / "010-result.private.json", {"saved": True})
            public = continuation.run_batch(
                self.private_freeze, self.review_sha, max_new_ids=1)
            self.assertEqual(public["status"],
                             "stopped_on_failed_id_no_replay")
            with self.assertRaisesRegex(
                    continuation.ContinuationError,
                    "continuation_batch_stopped_or_budget_exceeds_roster"):
                continuation.run_batch(
                    self.private_freeze, self.review_sha, max_new_ids=1)
            run.assert_called_once()

    def test_unconfirmed_process_group_blocks_reset_and_same_id_retry(self):
        self._start_pending_id()
        parts = self._mock_preflight()
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        raw = {"child_terminated": True, "child_pid": 12345,
               "timed_out": False, "exit_code": 0,
               "elapsed_seconds": 1.0}
        uncertain = {**raw, "child_terminated": False,
                     "process_group_terminated": False,
                     "termination_unconfirmed": True}
        with patch.object(continuation.one, "supervise_child",
                          return_value=raw), \
             patch.object(continuation.recovery,
                          "_confirm_child_process_group",
                          return_value=uncertain), \
             patch.object(continuation.one, "exact_cold_reset") as reset:
            first = continuation._run_one(
                self.private_freeze, 10, self.review_sha)
            self.assertEqual(first["status"],
                             "manual_review_required_no_replay")
            reset.assert_not_called()
            with self.assertRaisesRegex(
                    continuation.ContinuationError,
                    "continuation_one_id_already_issued_or_uncertain"):
                continuation._run_one(
                    self.private_freeze, 10, self.review_sha)
        saved = json.loads(
            (self.supervision / "010-result.private.json").read_bytes())
        self.assertFalse(saved["post_attempt_baseline_exact"])
        self.assertFalse(saved["child"]["process_group_terminated"])

    def test_direct_child_without_matching_supervisor_parent_is_rejected(self):
        plan_sha = self._start_pending_id()
        continuation.one.write_new(
            self.supervision / "010-intent.private.json", {
                "schema": continuation.SUPERVISOR_INTENT_SCHEMA,
                "task_index": 10,
                "task_id": self.old["task_roster"][10]["task_id"],
                "package_sha256":
                    self.old["task_roster"][10]["package_sha256"],
                "supervisor_pid": 1,
                "source_freeze_sha256": plan_sha,
                "reviewed_public_freeze_sha256": self.review_sha,
                "automatic_same_id_replay": False,
            })
        parts = self._mock_preflight()
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(continuation.lane, "run_loop",
                          side_effect=AssertionError("must_not_run_gui")):
            with self.assertRaisesRegex(
                    continuation.ContinuationError,
                    "continuation_child_intent_or_branch_changed"):
                continuation._child_run(
                    self.private_freeze, 10, self.review_sha)

    def test_saved_result_forbids_direct_child_replay_even_with_parent(self):
        plan_sha = self._start_pending_id()
        item = self.old["task_roster"][10]
        continuation.one.write_new(
            self.supervision / "010-intent.private.json", {
                "schema": continuation.SUPERVISOR_INTENT_SCHEMA,
                "task_index": 10, "task_id": item["task_id"],
                "package_sha256": item["package_sha256"],
                "supervisor_pid": os.getppid(),
                "source_freeze_sha256": plan_sha,
                "reviewed_public_freeze_sha256": self.review_sha,
                "automatic_same_id_replay": False,
            })
        continuation.one.write_new(
            self.supervision / "010-result.private.json", {"saved": True})
        parts = self._mock_preflight()
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(continuation.lane, "run_loop",
                          side_effect=AssertionError("must_not_run_gui")):
            with self.assertRaisesRegex(
                    continuation.ContinuationError,
                    "continuation_child_intent_or_branch_changed"):
                continuation._child_run(
                    self.private_freeze, 10, self.review_sha)


if __name__ == "__main__":
    unittest.main()
