"""Refusal and namespace tests for terminal-only interruption reconciliation."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from tools import reconcile_gitlab_v7_train_interruption_20260930 as tool


class InterruptionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.run = self.repo / tool.RUN_RELATIVE
        self.run.mkdir(parents=True, mode=0o700)
        self.ratification = self.repo / "ratification.private.json"
        self.ratification.write_text("{}")

    def test_atomic_receipt_write_never_overwrites(self):
        target = self.run / "new.private.json"
        tool.write_new(target, b"original\n", 0o600)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, "receipt_path_not_new"):
            tool.write_new(target, b"replacement\n", 0o600)
        self.assertEqual(target.read_bytes(), b"original\n")
        self.assertEqual(list(self.run.glob(".v7-reconcile-*")), [])

    def test_manifest_rejects_permissive_artifact(self):
        target = self.run / "evidence.png"
        target.write_bytes(b"image")
        target.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "v7_artifact_mode_not_exact"):
            tool.manifest(self.run)

    def test_manifest_rejects_symlink_and_binds_bytes(self):
        target = self.run / "evidence.private.json"
        tool.write_new(target, b"original", 0o600)
        before = tool.manifest(self.run)
        target.write_bytes(b"changed")
        self.assertNotEqual(before, tool.manifest(self.run))
        link = self.run / "linked.private.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "v7_artifact_symlink"):
            tool.manifest(self.run)

    def _reviewed(self):
        report = {"live_original_postgres_git_exact_baseline": True}
        path = self.repo / "reviewed-audit.json"
        raw = tool.canonical(report) + b"\n"
        path.write_bytes(raw)
        return report, path, tool.digest(raw)

    def _finalize(self, path, audit_sha, tool_sha=None):
        return tool.finalize(
            repo=self.repo, ratification=self.ratification,
            reviewed_tool_sha256=tool_sha or tool.digest(Path(tool.__file__).read_bytes()),
            reviewed_audit=path, reviewed_audit_sha256=audit_sha)

    def test_wrong_reviewed_tool_refuses_before_audit(self):
        _, path, audit_sha = self._reviewed()
        with patch.object(tool, "audit") as audit:
            with self.assertRaisesRegex(ValueError, "reviewed_reconciliation_tool_sha256_required"):
                self._finalize(path, audit_sha, "0" * 64)
        audit.assert_not_called()
        self.assertEqual(list(self.run.iterdir()), [])

    def test_changed_reviewed_audit_refuses_before_audit(self):
        _, path, _ = self._reviewed()
        with patch.object(tool, "audit") as audit:
            with self.assertRaisesRegex(ValueError, "reviewed_interruption_audit_sha256_required"):
                self._finalize(path, "0" * 64)
        audit.assert_not_called()

    def test_current_evidence_disagreement_refuses_before_write(self):
        _, path, audit_sha = self._reviewed()
        with patch.object(tool, "audit", return_value={"changed": True}), \
             patch.object(tool, "existing_diagnostic_lock"):
            with self.assertRaisesRegex(ValueError, "reviewed_interruption_audit_no_longer_current"):
                self._finalize(path, audit_sha)
        self.assertEqual(list(self.run.iterdir()), [])

    def test_finalize_creates_only_distinct_non_success_receipt(self):
        report, path, audit_sha = self._reviewed()
        with patch.object(tool, "audit", return_value=report) as audit, \
             patch.object(tool, "no_matching_processes"), \
             patch.object(tool, "existing_diagnostic_lock"):
            result = self._finalize(path, audit_sha)
        audit.assert_called_once_with(repo=self.repo, ratification=self.ratification,
                                      check_live=True)
        target = self.run / "interruption-reconciliation.private.json"
        receipt = json.loads(target.read_bytes())
        self.assertEqual(list(self.run.iterdir()), [target])
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertFalse(receipt["original_supervisor_evidence_reconstructed"])
        self.assertIsNone(receipt["original_supervisor_exit_code"])
        self.assertIsNone(receipt["original_watchdog_timed_out"])
        self.assertFalse(receipt["original_process_group_termination_receipt_available"])
        self.assertFalse(receipt["success_claim_authorized"])
        self.assertFalse(receipt["same_intent_replay_authorized"])
        self.assertEqual(receipt["gui_or_task_dispatches"], 0)
        self.assertEqual(result["official_final_admitted"], 0)
        self.assertFalse((self.run / "supervisor-result.private.json").exists())
        self.assertFalse((self.repo / tool.PUBLIC_RESULT_RELATIVE).exists())
        with patch.object(tool, "audit", return_value=report), \
             patch.object(tool, "no_matching_processes"), \
             patch.object(tool, "existing_diagnostic_lock"):
            with self.assertRaisesRegex(ValueError, "receipt_path_not_new"):
                self._finalize(path, audit_sha)

    def test_existing_lock_excludes_other_finalizer_without_modifying_bytes(self):
        path = self.run / ".diagnostic.lock"
        tool.write_new(path, b"existing-original-lock", 0o600)
        before = tool.manifest(self.run)
        with tool.existing_diagnostic_lock(self.run):
            with self.assertRaises(BlockingIOError):
                with tool.existing_diagnostic_lock(self.run):
                    self.fail("second finalizer entered locked diagnostic")
        self.assertEqual(tool.manifest(self.run), before)


if __name__ == "__main__":
    unittest.main()
