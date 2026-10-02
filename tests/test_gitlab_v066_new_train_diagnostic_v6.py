"""Offline contracts for the new TRAIN identity GitLab GUI diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from gitlab_world import v066_new_train_diagnostic_v6 as diagnostic


class TrainDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs/evidence").mkdir(parents=True)
        self.private_root = self.root / "private"
        self.private_root.mkdir(mode=0o700)
        self.run = self.private_root / "run"
        self.run.mkdir(mode=0o700)
        self.cases = self.run / "cases"
        self.plan = self.run / "source.private.json"
        self.public = self.root / "docs/evidence/source.json"
        self.ratification = self.private_root / "ratification.private.json"
        self.ratification.write_text("{}")
        self.ratification.chmod(0o600)
        self.baseline = self.private_root / "baseline-persisted-state.json"
        self.baseline.write_text(json.dumps({"business_sha256": "a" * 64}))
        self.baseline.chmod(0o600)
        self.world = self.private_root / "world-private.json"
        self.world.write_text("{}")
        self.world.chmod(0o600)
        self.patches = [
            patch.object(diagnostic, "ROOT", self.root),
            patch.object(diagnostic.one, "ROOT", self.root),
            patch.object(diagnostic.one, "PRIVATE_ROOT", self.private_root),
            patch.object(diagnostic, "PRIVATE_ROOT", self.private_root),
            patch.object(diagnostic, "RUN", self.run),
            patch.object(diagnostic, "CASES_DIR", self.cases),
            patch.object(diagnostic, "PLAN", self.plan),
            patch.object(diagnostic, "PUBLIC_PLAN", self.public),
            patch.object(diagnostic, "INTENT", self.run / "intent.private.json"),
            patch.object(diagnostic, "CHILD_RESULT", self.run / "child.private.json"),
            patch.object(diagnostic, "SUPERVISOR_RESULT",
                         self.run / "supervisor.private.json"),
            patch.object(diagnostic, "PUBLIC_RESULT",
                         self.root / "docs/evidence/result.json"),
            patch.object(diagnostic.bootstrap, "WORLD_FILE", self.world),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    def _task(self):
        return {"task_id": "private-new-train-id", "partition": "train",
                "template_group": "issue_label_from_alert",
                "source_family": "private-train-source",
                "oracle": {"expected_priority": "priority::p1"},
                "prompt": "private task instruction"}

    def test_saved_train_score_targets_active_or_controlled_wrong_issue(self):
        task = self._task()
        progress = {"project_id": 10,
                    "issue_iids": {"active": 1, "historical_duplicate": 2}}
        before = {"business_sha256": "a" * 64}
        after = {"business_sha256": "b" * 64}
        for negative, expected_issue, reward in ((False, 101, 1.0),
                                                 (True, 102, 0.0)):
            with self.subTest(negative=negative), \
                 patch.object(diagnostic.oracle, "evaluate_train_task",
                              return_value={"reward": reward}), \
                 patch.object(diagnostic.verify, "_context",
                              return_value=({"partition": "train"}, progress)), \
                 patch.object(diagnostic.verify, "_unchanged_tables"), \
                 patch.object(diagnostic.verify, "_unchanged_other_git"), \
                 patch.object(diagnostic.verify, "_issue",
                              side_effect=lambda _b, _p, iid: {"id": 100 + iid}), \
                 patch.object(diagnostic.verify, "_project_label_id",
                              return_value=7), \
                 patch.object(diagnostic.verify, "_added_label_link") as added:
                score = diagnostic.score_saved_case(
                    task, before, after, negative=negative)
                self.assertEqual(score["score"], reward)
                added.assert_called_once_with(before, after, expected_issue, 7)

    def test_wrong_object_is_not_accepted_as_positive(self):
        with patch.object(diagnostic.oracle, "evaluate_train_task",
                          return_value={"reward": 1.0}):
            with self.assertRaisesRegex(
                    diagnostic.DiagnosticError,
                    "train_saved_state_oracle_score_changed"):
                diagnostic.score_saved_case(self._task(), {}, {}, negative=True)

    def test_private_selector_uses_third_unused_train_identity(self):
        label_tasks = [
            {"task_id": f"train-{index}", "partition": "train",
             "template_group": "issue_label_from_alert",
             "project_family": f"project-{index}",
             "source_family": f"source-{index}",
             "oracle": {"expected_priority": "priority::p1"}}
            for index in range(5)]
        other_tasks = [
            {"task_id": f"other-{index}", "partition": "train",
             "template_group": "issue_due_from_register"}
            for index in range(15)]
        self.world.write_text(json.dumps({"tasks": label_tasks + other_tasks}))
        self.world.chmod(0o600)
        self.baseline.write_text(json.dumps({
            "business_sha256": "a" * 64,
            "db": {"issue_label_links": []}}))
        self.baseline.chmod(0o600)
        v4_plan = self.private_root / "v4.private.json"
        diagnostic.one.write_new(v4_plan, {
            "candidate_roster": [{"task_id": "final-only",
                                  "source_family_sha256": "f" * 64}]})
        progress = {"project_id": 1,
                    "issue_iids": {"active": 1, "historical_duplicate": 2}}
        with patch.object(diagnostic.replacement, "PRIVATE_PLAN", v4_plan), \
             patch.object(diagnostic.first_train, "_train_task",
                          return_value=(label_tasks[0], {})), \
             patch.object(diagnostic.second_train, "second_train_task",
                          return_value=(label_tasks[1], {})), \
             patch.object(diagnostic.verify, "_context",
                          return_value=({"partition": "train"}, progress)), \
             patch.object(diagnostic.verify, "_project_label_id",
                          return_value=7), \
             patch.object(diagnostic.verify, "_issue",
                          side_effect=lambda _b, _p, iid: {"id": 100 + iid}):
            selected, package_sha = diagnostic.select_train_task()
            self.assertEqual(selected["task_id"], "train-2")
            self.assertEqual(len(package_sha), 64)

    def test_public_plan_omits_train_identity_prompt_and_gold(self):
        private = {
            "source_bundle_sha256": "a" * 64,
            "parent_boot_independent_audit_sha256": "b" * 64,
            "intent_nonce_sha256": "c" * 64,
            "train_task_id": "private-new-train-id",
            "task_prompt": "private task instruction",
            "gold_label": "priority::p1",
        }
        public = diagnostic._public_plan(private, "d" * 64)
        encoded = json.dumps(public)
        self.assertNotIn("private-new-train-id", encoded)
        self.assertNotIn("private task instruction", encoded)
        self.assertNotIn("priority::p1", encoded)
        self.assertEqual(public["selection_or_final_tasks_dispatched"], 0)
        self.assertFalse(public["same_failed_final_identity_replay_authorized"])

    def test_third_case_missing_raw_logs_cannot_pass_trio(self):
        rows = [
            {"error_type": None, "restored_exact": True,
             "gui": {"saved_visible_after_reload": True},
             "score": {"score": score}, "expected_score": score,
             "forensics": {"raw_startup_logs_saved": True,
                           "state_only_inspect_saved": True}}
            for score in (1.0, 0.0, 1.0)]
        self.assertTrue(diagnostic.completed_case_trio(rows))
        rows[2]["forensics"]["raw_startup_logs_saved"] = False
        self.assertFalse(diagnostic.completed_case_trio(rows))

    def test_offline_freeze_audit_and_nonce_hide(self):
        task = self._task()
        with patch.object(diagnostic, "_parent_binding", return_value={}), \
             patch.object(diagnostic, "select_train_task",
                          return_value=(task, "e" * 64)), \
             patch.object(diagnostic.first_train,
                          "_acl_and_split_evidence",
                          return_value={"train_operator_non_admin": True}), \
             patch.object(diagnostic, "_source_hashes",
                          return_value={"source.py": "f" * 64}), \
             patch.object(diagnostic, "PARENT_BOOT_AUDIT", self.world), \
             patch.object(diagnostic.secrets, "token_hex",
                          return_value="ab" * 32), \
             patch.object(diagnostic.lane, "assert_live_world") as live:
            public = diagnostic.freeze(self.ratification)
            audited = diagnostic.audit(self.ratification)
        self.assertEqual(public, audited)
        self.assertNotIn("ab" * 32, json.dumps(public))
        self.assertEqual(public["official_final_admitted"], 0)
        self.assertFalse(diagnostic.INTENT.exists())
        self.assertEqual(self.plan.stat().st_mode & 0o077, 0)
        live.assert_not_called()

    def test_duplicate_intent_rejects_before_live_world(self):
        self.public.write_text("{}")
        diagnostic.INTENT.write_text("{}")
        private = {"intent_nonce": "ab" * 32,
                   "intent_nonce_sha256": "c" * 64,
                   "train_task_package_sha256": "e" * 64}
        with patch.object(diagnostic, "validate_freeze",
                          return_value=(private, "a" * 64, self._task())), \
             patch.object(diagnostic.lane, "assert_live_world") as live, \
             patch.object(diagnostic.one, "supervise_child") as supervise:
            with self.assertRaisesRegex(
                    diagnostic.DiagnosticError,
                    "new_train_intent_already_dispatched_no_replay"):
                diagnostic.run_diagnostic(
                    self.ratification,
                    diagnostic.one.sha(self.public.read_bytes()))
        live.assert_not_called()
        supervise.assert_not_called()

    def test_artifact_manifest_binds_cases_and_supervisor_fallback(self):
        self.cases.mkdir(mode=0o700)
        case = self.cases / "00-positive-1"
        case.mkdir(mode=0o700)
        (case / "receipt.json").write_text("{}")
        (case / "receipt.json").chmod(0o600)
        fallback = self.run / "supervisor-fallback"
        fallback.mkdir(mode=0o700)
        (fallback / "docker-logs.stdout.private.log").write_bytes(b"raw")
        (fallback / "docker-logs.stdout.private.log").chmod(0o600)
        manifest = diagnostic._artifact_tree_manifest()
        self.assertEqual({row["path"] for row in manifest},
                         {"cases/00-positive-1/receipt.json",
                          "supervisor-fallback/docker-logs.stdout.private.log"})

    def test_one_case_preserves_reset_and_forensics_on_gui_failure(self):
        self.cases.mkdir(mode=0o700)
        baseline = {"business_sha256": "a" * 64}
        after = {"business_sha256": "b" * 64}
        self.baseline.write_text(json.dumps(baseline))
        self.baseline.chmod(0o600)
        order = []

        async def failing_gui(_browser, _task, _issue, _folder):
            order.append("gui")
            raise RuntimeError("GUI failed")

        def reset():
            order.append("reset")
            return {"cold_reset": True, "container_identity_changed": True,
                    "same_business_sha256": True}

        def capture(_folder):
            order.append("capture")
            return {"raw_startup_logs_saved": True,
                    "state_only_inspect_saved": True}

        with patch.object(diagnostic.verify, "state_snapshot",
                          side_effect=[baseline, baseline]), \
             patch.object(diagnostic, "_gui_label", side_effect=failing_gui), \
             patch.object(diagnostic.reset, "reset", side_effect=reset), \
             patch.object(diagnostic.lane, "assert_live_world",
                          return_value=baseline), \
             patch.object(diagnostic.boot, "capture_startup_forensics",
                          side_effect=capture):
            record = asyncio.run(diagnostic._one_case(
                object(), self._task(), {"baseline_business_sha256": "a" * 64},
                0, "positive-1", "active", 1.0))
        self.assertEqual(order, ["gui", "reset", "capture"])
        self.assertEqual(record["error_type"], "RuntimeError")
        self.assertTrue(record["restored_exact"])
        self.assertTrue((self.cases / "00-positive-1" /
                         "case-receipt.private.json").is_file())

    def test_supervisor_failure_captures_before_exact_cleanup(self):
        self.public.write_text("{}")
        reviewed = diagnostic.one.sha(self.public.read_bytes())
        nonce = "ab" * 32
        task = self._task()
        plan = {"intent_nonce": nonce,
                "intent_nonce_sha256": diagnostic.one.sha(nonce.encode()),
                "train_task_package_sha256": "e" * 64}
        child = {"child_terminated": True,
                 "process_group_terminated": True,
                 "exit_code": 1, "timed_out": False}
        forensic = {"raw_file_sha256s": {"docker_logs_stdout": "f" * 64}}
        order = []

        def capture(folder):
            order.append("capture")
            self.assertEqual(folder.name, "supervisor-fallback")
            return forensic

        def cleanup():
            order.append("cleanup")
            return {"cold_reset_exact": True}

        with patch.object(diagnostic, "validate_freeze",
                          return_value=(plan, "a" * 64, task)), \
             patch.object(diagnostic.terminal, "validate_freeze",
                          return_value=({}, {"old": {}}, {})), \
             patch.object(diagnostic.lane, "assert_live_world", return_value={}), \
             patch.object(diagnostic.one, "supervise_child", return_value=child), \
             patch.object(diagnostic.recovery, "_confirm_child_process_group",
                          side_effect=lambda row: row), \
             patch.object(diagnostic.boot, "capture_startup_forensics",
                          side_effect=capture), \
             patch.object(diagnostic.one, "exact_cold_reset",
                          side_effect=cleanup):
            result = diagnostic.run_diagnostic(self.ratification, reviewed)
        self.assertEqual(order, ["capture", "cleanup"])
        self.assertEqual(result["status"],
                         "terminal_train_diagnostic_failed_exactly_reset_no_replay")
        self.assertTrue(result["post_attempt_exact_baseline"])
        self.assertEqual(result["completed_gui_cases"], 0)
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["selection_or_final_tasks_dispatched"], 0)
        self.assertNotIn(task["task_id"], json.dumps(result))


if __name__ == "__main__":
    unittest.main()
