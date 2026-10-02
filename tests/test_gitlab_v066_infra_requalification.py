"""No-GUI tests for the one-use GitLab recovery branch."""

from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import signal
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import prospective_final_controls_v066 as lane
from gitlab_world import v066_infra_requalification_v1 as recovery


class RecoveryBranchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.branch = self.private / "branch"
        self.branch.mkdir(mode=0o700)
        (self.branch / "attempts").mkdir(mode=0o700)
        self.supervision = self.branch / "supervision"
        self.supervision.mkdir(mode=0o700)
        self.private_freeze = self.branch / "source-freeze.private.json"
        recovery.one.write_new(self.private_freeze, {"source": "frozen"})
        self.public_freeze = self.root / "source-freeze-public.json"
        self.public_freeze.write_text("{}")
        self.old_sha = "a" * 64
        self.review_sha = "b" * 64
        self.old = {
            "task_roster": [
                {"task_id": f"private-{index:03d}",
                 "package_sha256": f"{index:064x}"}
                for index in range(100)
            ],
            "source_bundle_sha256": "c" * 64,
            "baseline_business_sha256": "d" * 64,
            "max_wall_seconds_per_task": 7200,
        }
        self.context = {
            "old": self.old,
            "old_sha": self.old_sha,
            "bound": {},
            "failed_result_sha256": "e" * 64,
            "journal_terminal_entry_sha256": "f" * 64,
            "journal_full_sha256": "1" * 64,
            "nine_private": {"validated_tasks": [
                {"task_id": row["task_id"]}
                for row in self.old["task_roster"][:9]]},
        }
        self.prefix_audit = {
            "completed_task_count": 9,
            "pending_intent": False,
            "terminal_failure": False,
            "validated_tasks": self.context["nine_private"]["validated_tasks"],
        }
        self.patches = [
            patch.object(recovery, "ROOT", self.root),
            patch.object(recovery, "BRANCH", self.branch),
            patch.object(recovery, "SUPERVISION", self.supervision),
            patch.object(recovery, "PRIVATE_FREEZE", self.private_freeze),
            patch.object(recovery, "PUBLIC_FREEZE", self.public_freeze),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])
        self._write_prefix()

    def _write_prefix(self):
        journal = self.branch / "journal.private.jsonl"
        entries = []
        for index in range(9):
            row = self.old["task_roster"][index]
            lane.append_event(journal, self.old_sha, entries, {
                "kind": "intent", "task_index": index,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "source_bundle_sha256": self.old["source_bundle_sha256"],
                "official_final_admitted": 0,
            })
            lane.append_event(journal, self.old_sha, entries, {
                "kind": "terminal", "task_index": index,
                "task_id": row["task_id"],
                "status": "control_passed", "error_type": None,
                "wall_seconds": 1.0, "trio_receipt_sha256": "f" * 64,
                "official_final_admitted": 0,
            })

    def _patch_run(self, *, child):
        child_patch = (
            patch.object(recovery.one, "supervise_child", side_effect=child)
            if callable(child) else
            patch.object(recovery.one, "supervise_child", return_value=child)
        )
        return [
            patch.object(recovery, "_reviewed_public_digest",
                         return_value=self.review_sha),
            patch.object(recovery, "validate_freeze",
                         return_value=({}, self.context, self.prefix_audit, {})),
            patch.object(recovery.one, "lock_supervisor",
                         side_effect=nullcontext),
            patch.object(recovery, "_lock", side_effect=nullcontext),
            patch.object(recovery.lane, "assert_live_world",
                         return_value={"business_sha256": "d" * 64}),
            patch.object(recovery, "_confirm_child_process_group",
                         side_effect=lambda value: {
                             **value,
                             "process_group_terminated": True,
                             "group_survivor_observed_after_child_wait": False,
                         }),
            child_patch,
        ]

    def test_private_tree_copy_is_exact_and_symlink_fails(self):
        source = self.private / "source"
        source.mkdir(mode=0o700)
        (source / "case").mkdir(mode=0o700)
        (source / "case" / "readback.json").write_text('{"ok":true}\n')
        destination = self.private / "destination"
        expected = recovery._copy_tree(source, destination)
        self.assertEqual(expected, recovery._tree_manifest(destination))
        self.assertEqual((destination / "case" / "readback.json").stat().st_mode & 0o077, 0)
        (source / "case" / "unsafe-link").symlink_to("readback.json")
        with self.assertRaisesRegex(recovery.RecoveryError, "private_tree_symlink"):
            recovery._tree_manifest(source)

    def test_public_freeze_has_no_private_task_identity(self):
        private = {
            "source_bundle_sha256": "a" * 64,
            "superseded_v2_public_freeze_sha256": "3" * 64,
            "superseded_v2_private_freeze_sha256": "4" * 64,
            "original_100_id_plan_sha256": "b" * 64,
            "original_full_failed_journal_sha256": "c" * 64,
            "original_failed_terminal_entry_sha256": "d" * 64,
            "original_failed_batch_receipt_sha256": "e" * 64,
            "original_nine_private_audit_sha256": "f" * 64,
            "branch_nine_prefix_journal_sha256": "1" * 64,
            "requalification_task_id": "private-answer",
        }
        public = recovery._public_freeze(private, "2" * 64)
        self.assertNotIn("private-answer", json.dumps(public))
        self.assertFalse(public["continuation_dispatch_authorized"])
        self.assertEqual(public["same_identity_fresh_clone_requalification_budget"], 1)

    def test_terminalizing_branch_keeps_prefix_and_never_replays(self):
        journal = self.branch / "journal.private.jsonl"
        prefix = journal.read_bytes()
        self.assertTrue(recovery._terminalize_branch(
            self.context, elapsed=12.5, error_type="SupervisedChildNonpassingExit"))
        entries = lane.read_journal(self.branch, self.old_sha)
        state = lane.journal_state(entries, self.old)
        self.assertTrue(state["failed"])
        self.assertIsNone(state["pending"])
        self.assertEqual(state["next_index"], 9)
        self.assertTrue(journal.read_bytes().startswith(prefix))
        self.assertEqual(len(entries), 20)
        self.assertTrue(recovery._terminalize_branch(
            self.context, elapsed=13.0, error_type="SupervisedChildNonpassingExit"))
        self.assertEqual(len(lane.read_journal(self.branch, self.old_sha)), 20)

    def test_existing_intent_refuses_second_dispatch_without_child(self):
        recovery.one.write_new(
            self.supervision / "009-intent.private.json", {"already": "issued"})
        parts = self._patch_run(child=AssertionError("must_not_run_child"))
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with self.assertRaisesRegex(
                recovery.RecoveryError,
                "same_identity_requalification_already_used_or_uncertain"):
            recovery.run_requalification(self.private / "ratification.json",
                                         self.review_sha)

    def test_wrong_public_digest_cannot_create_intent(self):
        with self.assertRaisesRegex(
                recovery.RecoveryError,
                "explicit_reviewed_public_freeze_sha256_required"):
            recovery.run_requalification(
                self.private / "ratification.json", "0" * 64)
        self.assertFalse(
            (self.supervision / "009-intent.private.json").exists())

    def test_direct_child_run_without_supervisor_parent_is_rejected(self):
        fake_intent = {
            "schema": recovery.INTENT_SCHEMA,
            "task_index": 9,
            "supervisor_pid": 1,
            "reviewed_public_freeze_sha256": self.review_sha,
            "original_failed_result_sha256":
                self.context["failed_result_sha256"],
        }
        with patch.object(recovery, "_reviewed_public_digest",
                          return_value=self.review_sha), \
             patch.object(recovery, "validate_freeze",
                          return_value=({}, self.context,
                                        self.prefix_audit, {})), \
             patch.object(recovery, "_read_private",
                          return_value=(fake_intent, "0" * 64)), \
             patch.object(recovery.lane, "run_loop",
                          side_effect=AssertionError("must_not_run_gui")):
            with self.assertRaisesRegex(
                    recovery.RecoveryError,
                    "requalification_child_intent_or_branch_changed"):
                recovery._child_run(
                    self.private / "ratification.json", self.review_sha)

    def test_failed_child_terminalizes_branch_and_never_replays(self):
        parts = self._patch_run(child={
            "child_terminated": True, "timed_out": False,
            "exit_code": 1, "elapsed_seconds": 3.0,
        })
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(recovery.one, "exact_cold_reset",
                          return_value={"cold_reset_exact": True,
                                        "world_healthy": True}):
            result = recovery.run_requalification(
                self.private / "ratification.json", self.review_sha)
        self.assertEqual(
            result["status"], "requalification_terminal_no_replay_exactly_reset")
        self.assertEqual(
            lane.journal_state(
                lane.read_journal(self.branch, self.old_sha),
                self.old)["failed"], True)
        with self.assertRaisesRegex(
                recovery.RecoveryError,
                "same_identity_requalification_already_used_or_uncertain"):
            recovery.run_requalification(
                self.private / "ratification.json", self.review_sha)

    def test_supervision_oserror_cannot_claim_child_terminated_or_reset(self):
        def unknown_supervision_failure(*_args, **_kwargs):
            raise OSError("injected error after possible child spawn")

        parts = self._patch_run(child=unknown_supervision_failure)
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        with patch.object(recovery.one, "exact_cold_reset") as reset:
            result = recovery.run_requalification(
                self.private / "ratification.json", self.review_sha)
        saved = json.loads(
            (self.supervision / "009-result.private.json").read_bytes())
        state = lane.journal_state(
            lane.read_journal(self.branch, self.old_sha), self.old)
        self.assertEqual(result["status"], "manual_review_required_no_replay")
        self.assertFalse(saved["child"]["child_terminated"])
        self.assertTrue(saved["child"]["termination_unconfirmed"])
        self.assertFalse(saved["post_attempt_baseline_exact"])
        self.assertIsNone(state["pending"])
        self.assertFalse(state["failed"])
        self.assertEqual(state["next_index"], 9)
        reset.assert_not_called()
        with self.assertRaisesRegex(
                recovery.RecoveryError,
                "same_identity_requalification_already_used_or_uncertain"):
            recovery.run_requalification(
                self.private / "ratification.json", self.review_sha)

    def test_sigterm_ignoring_grandchild_cannot_fake_group_termination(self):
        code = (
            'import subprocess,sys,time; '
            'p=subprocess.Popen([sys.executable,"-c",'
            '"import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);'
            'time.sleep(30)"]); print(p.pid,flush=True); time.sleep(30)'
        )
        stdout = self.private / "watchdog.stdout.private.log"
        stderr = self.private / "watchdog.stderr.private.log"
        raw = None
        try:
            raw = recovery.one.supervise_child(
                [sys.executable, "-c", code], cwd=self.private,
                env=dict(os.environ), stdout_path=stdout, stderr_path=stderr,
                timeout_seconds=1.0, grace_seconds=0.2)
            self.assertTrue(raw["timed_out"])
            self.assertTrue(raw["child_terminated"])
            with patch.object(recovery, "GROUP_TERM_GRACE_SECONDS", 0.2), \
                 patch.object(recovery, "GROUP_KILL_GRACE_SECONDS", 0.5):
                checked = recovery._confirm_child_process_group(raw)
            self.assertTrue(checked["group_survivor_observed_after_child_wait"])
            self.assertTrue(checked["post_watchdog_sigterm_used"])
            self.assertTrue(checked["post_watchdog_sigkill_used"])
            self.assertTrue(checked["process_group_terminated"] or
                            checked["termination_unconfirmed"])
            if checked["process_group_terminated"]:
                self.assertFalse(recovery._group_exists(raw["child_pid"]))
            else:
                self.assertFalse(checked["child_terminated"])
        finally:
            if raw is not None and raw.get("child_pid"):
                try:
                    os.killpg(raw["child_pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_undispatched_audit_cannot_publish_result(self):
        with patch.object(recovery, "validate_freeze",
                          return_value=({}, self.context, self.prefix_audit, {})):
            result = recovery.audit_requalification(
                self.private / "ratification.json")
            self.assertEqual(
                result["status"],
                "source_frozen_no_requalification_dispatched")
            with self.assertRaisesRegex(
                    recovery.RecoveryError,
                    "cannot_publish_undispatched_requalification"):
                recovery.audit_requalification(
                    self.private / "ratification.json", publish=True)

    def test_independent_result_audit_rejects_raw_digest_tampering(self):
        recovery.one.write_new(
            self.supervision / "009-intent.private.json", {"saved": True})
        recovery.one.write_new(
            self.supervision / "009-result.private.json", {"saved": True})
        full_audit = {
            **self.prefix_audit,
            "completed_task_count": 10,
            "validated_tasks": [
                *self.prefix_audit["validated_tasks"],
                {"task_id": self.old["task_roster"][9]["task_id"]}],
        }
        public_sha = recovery.one.sha(self.public_freeze.read_bytes())
        intent = {
            "schema": recovery.INTENT_SCHEMA,
            "task_index": 9,
            "supervisor_pid": 123,
            "task_id": self.old["task_roster"][9]["task_id"],
            "package_sha256": self.old["task_roster"][9]["package_sha256"],
            "reviewed_public_freeze_sha256": public_sha,
            "original_failed_result_sha256":
                self.context["failed_result_sha256"],
            "source_freeze_sha256":
                recovery.one.sha(self.private_freeze.read_bytes()),
            "same_identity_fresh_clone_attempt_number": 2,
            "automatic_same_id_replay": False,
            "model_calls": 0, "official_final_admitted": 0,
        }
        result = {
            "schema": recovery.RESULT_SCHEMA,
            "status": "same_identity_fresh_clone_requalified",
            "source_freeze_sha256":
                recovery.one.sha(self.private_freeze.read_bytes()),
            "reviewed_public_freeze_sha256": public_sha,
            "original_100_id_plan_sha256": self.old_sha,
            "original_failed_result_sha256":
                self.context["failed_result_sha256"],
            "task_index": 9,
            "task_id": self.old["task_roster"][9]["task_id"],
            "automatic_same_id_replay": False,
            "continuation_dispatch_authorized": False,
            "model_calls": 0, "official_final_admitted": 0,
            "child": {"child_terminated": True, "timed_out": False,
                      "exit_code": 0, "process_group_terminated": True,
                      "group_survivor_observed_after_child_wait": False},
            "post_attempt_baseline_exact": True,
            "raw_audit": {
                "completed_task_count": 10,
                "all_branch_raw_receipts_reopened": True,
                "audit_private_sha256":
                    recovery.one.sha(recovery.one.canonical(full_audit)),
            },
        }

        def read(path):
            if path.name.endswith("-intent.private.json"):
                return intent, "a" * 64
            return result, "b" * 64

        with patch.object(recovery, "validate_freeze",
                          return_value=({}, self.context, full_audit, {})), \
             patch.object(recovery, "_read_private", side_effect=read), \
             patch.object(recovery.lane, "assert_live_world",
                          return_value={"business_sha256": "d" * 64}):
            checked = recovery.audit_requalification(
                self.private / "ratification.json")
            self.assertEqual(checked["branch_completed_controls"], 10)
            self.assertFalse(checked["continuation_dispatch_authorized"])
            result["raw_audit"]["audit_private_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                    recovery.RecoveryError,
                    "fresh_requalification_raw_or_reset_evidence_changed"):
                recovery.audit_requalification(
                    self.private / "ratification.json")

    def test_successful_child_advances_once_and_still_blocks_continuation(self):
        def child(*_args, **_kwargs):
            row = self.old["task_roster"][9]
            entries = lane.read_journal(self.branch, self.old_sha)
            journal = self.branch / "journal.private.jsonl"
            lane.append_event(journal, self.old_sha, entries, {
                "kind": "intent", "task_index": 9,
                "task_id": row["task_id"],
                "package_sha256": row["package_sha256"],
                "source_bundle_sha256": self.old["source_bundle_sha256"],
                "official_final_admitted": 0,
            })
            lane.append_event(journal, self.old_sha, entries, {
                "kind": "terminal", "task_index": 9,
                "task_id": row["task_id"],
                "status": "control_passed", "error_type": None,
                "wall_seconds": 2.0, "trio_receipt_sha256": "f" * 64,
                "official_final_admitted": 0,
            })
            return {
                "child_terminated": True, "timed_out": False,
                "exit_code": 0, "elapsed_seconds": 2.0,
            }

        parts = self._patch_run(child=child)
        for item in parts:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(parts)])
        audited = {
            "completed_task_count": 10,
            "validated_tasks": [
                *self.context["nine_private"]["validated_tasks"],
                {"task_id": self.old["task_roster"][9]["task_id"]}],
        }
        with patch.object(recovery.lane, "audit_controls",
                          return_value=(audited, {})):
            result = recovery.run_requalification(
                self.private / "ratification.json", self.review_sha)
        self.assertEqual(result["status"], "same_identity_fresh_clone_requalified")
        self.assertEqual(result["completed_branch_controls"], 10)
        self.assertFalse(result["continuation_dispatch_authorized"])
        saved = json.loads(
            (self.supervision / "009-result.private.json").read_bytes())
        self.assertEqual(saved["status"], "same_identity_fresh_clone_requalified")
        self.assertFalse(saved["automatic_same_id_replay"])
        with self.assertRaisesRegex(
                recovery.RecoveryError,
                "same_identity_requalification_already_used_or_uncertain"):
            recovery.run_requalification(
                self.private / "ratification.json", self.review_sha)


if __name__ == "__main__":
    unittest.main()
