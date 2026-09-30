"""Offline no-replay, screenshot, and supervisor contracts for v7."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from gitlab_world import v066_new_train_diagnostic_v7 as v7


PNG = b"\x89PNG\r\n\x1a\nprivate-image-bytes"


class TrainDiagnosticV7Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs/evidence").mkdir(parents=True)
        self.private_root = self.root / "private"
        self.private_root.mkdir(mode=0o700)
        self.run = self.private_root / "v7"
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
        self.forensic = self.private_root / "v6-forensic.json"
        self.forensic.write_text(json.dumps({"one_use_intent_sha256": "1" * 64}))
        self.forensic.chmod(0o600)
        self.patches = [
            patch.object(v7, "ROOT", self.root),
            patch.object(v7.one, "ROOT", self.root),
            patch.object(v7.one, "PRIVATE_ROOT", self.private_root),
            patch.object(v7, "PRIVATE_ROOT", self.private_root),
            patch.object(v7, "RUN", self.run),
            patch.object(v7, "CASES_DIR", self.cases),
            patch.object(v7, "PLAN", self.plan),
            patch.object(v7, "PUBLIC_PLAN", self.public),
            patch.object(v7, "INTENT", self.run / "intent.private.json"),
            patch.object(v7, "CHILD_RESULT", self.run / "child.private.json"),
            patch.object(v7, "SUPERVISOR_RESULT", self.run / "supervisor.private.json"),
            patch.object(v7, "PUBLIC_RESULT", self.root / "docs/evidence/result.json"),
            patch.object(v7, "PARENT_FORENSIC", self.forensic),
            patch.object(v7.bootstrap, "WORLD_FILE", self.world),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    @staticmethod
    def task():
        return {"task_id": "private-train-ordinal-3", "partition": "train",
                "template_group": "issue_label_from_alert",
                "project_family": "private-train-project-3",
                "source_family": "private-train-source-3",
                "oracle": {"expected_priority": "priority::p1"},
                "prompt": "private task instruction"}

    def test_png_is_atomic_owner_only_and_cannot_overwrite(self):
        folder = self.run / "screenshot"
        folder.mkdir(mode=0o700)
        digest = v7._write_private_png(folder, "policy.png", PNG)
        target = folder / "policy.png"
        self.assertEqual(target.read_bytes(), PNG)
        self.assertEqual(target.stat().st_mode & 0o077, 0)
        self.assertEqual(digest, v7.one.sha(PNG))
        self.assertEqual(list(folder.glob("*.tmp")), [])
        with self.assertRaisesRegex(v7.DiagnosticV7Error,
                                    "v7_screenshot_destination_must_be_new"):
            v7._write_private_png(folder, "policy.png", PNG + b"changed")
        self.assertEqual(target.read_bytes(), PNG)

    def test_playwright_bytes_are_saved_without_path_argument(self):
        folder = self.run / "screenshot"
        folder.mkdir(mode=0o700)
        page = type("Page", (), {})()
        page.screenshot = AsyncMock(return_value=PNG)
        digest = asyncio.run(v7._secure_screenshot(page, folder, "issue-before.png"))
        page.screenshot.assert_awaited_once_with(type="png", full_page=True)
        self.assertEqual(digest, v7.one.sha(PNG))
        self.assertEqual((folder / "issue-before.png").stat().st_mode & 0o077, 0)

    def test_artifact_review_records_permissive_png_without_throwing(self):
        self.cases.mkdir(mode=0o700)
        folder = self.cases / "00-positive-1"
        folder.mkdir(mode=0o700)
        screenshot = folder / "policy.png"
        screenshot.write_bytes(PNG)
        screenshot.chmod(0o644)
        review = v7._artifact_review()
        self.assertFalse(review["permission_gate_passed"])
        self.assertIn("artifact_permission", review["issue_codes"])
        self.assertEqual(review["files"][0]["mode"], 0o644)
        self.assertEqual(review["files"][0]["sha256"], v7.one.sha(PNG))

    def test_scoped_v6_case_runner_restores_globals_on_error(self):
        original_dir, original_gui = v7.previous.CASES_DIR, v7.previous._gui_label
        with self.assertRaisesRegex(RuntimeError, "stop"):
            with v7._scoped_v6_case_runner():
                self.assertEqual(v7.previous.CASES_DIR, self.cases)
                self.assertIs(v7.previous._gui_label, v7._secure_gui_label)
                raise RuntimeError("stop")
        self.assertEqual(v7.previous.CASES_DIR, original_dir)
        self.assertIs(v7.previous._gui_label, original_gui)

    def test_selector_uses_fourth_unused_train_identity(self):
        labels = [
            {"task_id": f"train-{index}", "partition": "train",
             "template_group": "issue_label_from_alert",
             "project_family": f"project-{index}",
             "source_family": f"source-{index}",
             "oracle": {"expected_priority": "priority::p1"}}
            for index in range(5)]
        others = [{"task_id": f"other-{index}", "partition": "train",
                   "template_group": "issue_due_from_register"}
                  for index in range(15)]
        self.world.write_text(json.dumps({"tasks": labels + others}))
        self.world.chmod(0o600)
        self.baseline.write_text(json.dumps({
            "business_sha256": "a" * 64,
            "db": {"issue_label_links": []}}))
        self.baseline.chmod(0o600)
        v4 = self.private_root / "v4.private.json"
        v7.one.write_new(v4, {"candidate_roster": [
            {"task_id": "final-only", "source_family_sha256": "f" * 64}]})
        progress = {"project_id": 1,
                    "issue_iids": {"active": 1, "historical_duplicate": 2}}
        with patch.object(v7.replacement, "PRIVATE_PLAN", v4), \
             patch.object(v7.first_train, "_train_task",
                          return_value=(labels[0], {})), \
             patch.object(v7.second_train, "second_train_task",
                          return_value=(labels[1], {})), \
             patch.object(v7.previous, "select_train_task",
                          return_value=(labels[2], "a" * 64)), \
             patch.object(v7.verify, "_context",
                          return_value=({"partition": "train"}, progress)), \
             patch.object(v7.verify, "_project_label_id", return_value=7), \
             patch.object(v7.verify, "_issue",
                          side_effect=lambda _b, _p, iid: {"id": 100 + iid}):
            task, package = v7.select_train_task()
        self.assertEqual(task["task_id"], "train-3")
        self.assertEqual(len(package), 64)

    def _freeze_offline(self):
        with patch.object(v7, "_v6_forensic_boundary", return_value={}), \
             patch.object(v7, "select_train_task",
                          return_value=(self.task(), "e" * 64)), \
             patch.object(v7.first_train, "_acl_and_split_evidence",
                          return_value={"train_operator_non_admin": True}), \
             patch.object(v7, "_source_hashes",
                          return_value={"source.py": "f" * 64}), \
             patch.object(v7.secrets, "token_hex", return_value="ab" * 32), \
             patch.object(v7.lane, "assert_live_world") as live:
            public = v7.freeze(self.ratification)
            audited = v7.audit(self.ratification)
        live.assert_not_called()
        return public, audited

    def test_offline_freeze_audit_and_public_privacy(self):
        public, audited = self._freeze_offline()
        self.assertEqual(public, audited)
        encoded = json.dumps(public)
        self.assertNotIn(self.task()["task_id"], encoded)
        self.assertNotIn(self.task()["prompt"], encoded)
        self.assertNotIn("ab" * 32, encoded)
        self.assertFalse(v7.INTENT.exists())
        self.assertEqual(self.plan.stat().st_mode & 0o077, 0)
        self.assertEqual(public["official_final_admitted"], 0)

    def test_duplicate_intent_rejected_before_world_dispatch(self):
        self.public.write_text("{}")
        v7.INTENT.write_text("{}")
        plan = {"intent_nonce": "ab" * 32,
                "intent_nonce_sha256": "c" * 64,
                "train_task_package_sha256": "e" * 64}
        with patch.object(v7, "validate_freeze",
                          return_value=(plan, "a" * 64, self.task())), \
             patch.object(v7.lane, "assert_live_world") as world, \
             patch.object(v7.one, "supervise_child") as supervise:
            with self.assertRaisesRegex(v7.DiagnosticV7Error,
                                        "v7_intent_already_dispatched_no_replay"):
                v7.run_diagnostic(self.ratification,
                                  v7.one.sha(self.public.read_bytes()))
        world.assert_not_called()
        supervise.assert_not_called()

    def _supervisor_fixture(self, *, review_error: bool):
        self.public.write_text("{}")
        reviewed = v7.one.sha(self.public.read_bytes())
        nonce = "ab" * 32
        plan = {"intent_nonce": nonce,
                "intent_nonce_sha256": v7.one.sha(nonce.encode()),
                "train_task_package_sha256": "e" * 64}
        task = self.task()
        child_status = "three_train_gui_cases_saved_pending_supervisor_review"

        def child_process(*_args, **_kwargs):
            intent_sha = v7.one.sha(v7.INTENT.read_bytes())
            v7.one.write_new(v7.CHILD_RESULT, {
                "schema": v7.CHILD_SCHEMA,
                "status": child_status,
                "source_freeze_sha256": "a" * 64,
                "intent_sha256": intent_sha,
                "intent_nonce_sha256": plan["intent_nonce_sha256"],
                "train_task_package_sha256": "e" * 64,
                "completed_cases": 3,
                "case_receipt_sha256s": ["f" * 64] * 3,
                "scores": [1.0, 0.0, 1.0],
                "provider_calls": 0,
                "selection_or_final_tasks_dispatched": 0,
                "official_final_admitted": 0,
            })
            return {"child_terminated": True,
                    "process_group_terminated": True,
                    "exit_code": 0, "timed_out": False}

        review = {"files": [{"path": "cases/00/policy.png", "mode": 0o644,
                              "sha256": "f" * 64, "bytes": 12}],
                  "issue_codes": ["artifact_permission"],
                  "permission_gate_passed": False}
        with patch.object(v7, "validate_freeze",
                          return_value=(plan, "a" * 64, task)), \
             patch.object(v7.terminal, "validate_freeze",
                          return_value=({}, {"old": {}}, {})), \
             patch.object(v7.lane, "assert_live_world", return_value={}), \
             patch.object(v7.one, "supervise_child", side_effect=child_process), \
             patch.object(v7.recovery, "_confirm_child_process_group",
                          side_effect=lambda row: row), \
             patch.object(v7, "_artifact_review",
                          side_effect=PermissionError if review_error else None,
                          return_value=review):
            outcome = v7.run_diagnostic(self.ratification, reviewed)
            if not review_error:
                audited = v7.audit(self.ratification)
                self.assertEqual(audited, outcome)
        return outcome

    def test_permission_failure_writes_terminal_receipt_not_success(self):
        outcome = self._supervisor_fixture(review_error=False)
        self.assertEqual(outcome["status"],
                         "terminal_evidence_permission_failure_no_replay")
        self.assertFalse(outcome["success_claim_authorized"])
        self.assertFalse(outcome["artifact_permission_gate_passed"])
        self.assertEqual(outcome["saved_state_scores"], [])
        self.assertTrue(v7.SUPERVISOR_RESULT.is_file())
        self.assertTrue(v7.PUBLIC_RESULT.is_file())

    def test_clean_supervisor_gate_still_requires_separate_audit(self):
        self.public.write_text("{}")
        supervisor = {
            "status": "three_train_gui_cases_independently_reviewable",
            "intent_nonce_sha256": "a" * 64,
            "completed_gui_cases": 3,
            "saved_state_scores": [1.0, 0.0, 1.0],
            "artifact_review": {"files": [], "issue_codes": [],
                                "permission_gate_passed": True},
            "child_process_group_terminated": True,
            "post_attempt_exact_baseline": True,
        }
        public = v7._public_result(supervisor, "b" * 64)
        self.assertTrue(public["supervisor_evidence_gate_passed"])
        self.assertTrue(public["independent_postrun_audit_required"])
        self.assertFalse(public["success_claim_authorized"])
        self.assertEqual(public["official_final_admitted"], 0)

    def test_artifact_review_exception_still_writes_non_success_receipt(self):
        outcome = self._supervisor_fixture(review_error=True)
        self.assertEqual(outcome["status"],
                         "terminal_evidence_permission_failure_no_replay")
        self.assertFalse(outcome["success_claim_authorized"])
        self.assertTrue(v7.SUPERVISOR_RESULT.is_file())
        self.assertTrue(v7.PUBLIC_RESULT.is_file())


if __name__ == "__main__":
    unittest.main()
