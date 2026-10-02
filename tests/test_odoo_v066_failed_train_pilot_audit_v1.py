"""Offline checks for the preserved failed train pilot auditor.

Set the three ODOO_FAILED_PILOT_* variables for the real evidence checks.
No test dispatches a GUI action or changes the original attempt.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import audit_odoo_v066_failed_train_pilot_v1 as auditor


ROOT = Path(__file__).resolve().parents[1]


class PureVerifierTests(unittest.TestCase):
    def test_only_selected_functions_execute(self):
        source = b"""
raise RuntimeError('module import would be unsafe')
def keyed(rows): return rows
def global_identity_differences(a, b): return []
def evaluate(*args): return {'reward': 1.0}
def protected_source_file_differences(*args): return []
def protected_source_store_path_differences(*args): return []
"""
        functions = auditor.pure_old_verifier(source)
        self.assertEqual(functions["evaluate"]()["reward"], 1.0)


class PreservedAttemptTests(unittest.TestCase):
    def setUp(self):
        paths = [os.environ.get(name) for name in (
            "ODOO_FAILED_PILOT_ATTEMPT",
            "ODOO_FAILED_PILOT_BINDING",
            "ODOO_FAILED_PILOT_PRIVATE_PLAN",
        )]
        if not all(paths):
            self.skipTest("private preserved-attempt paths not supplied")
        self.attempt, self.binding, self.private_plan = map(Path, paths)
        self.args = {
            "attempt": self.attempt,
            "train_private": self.attempt.parent.parent,
            "binding_path": self.binding,
            "private_plan_path": self.private_plan,
            "public_plan_path": ROOT / "docs/evidence/odoo-v066-prospective-gui-requalification-post-restart-2026-09-28.json",
            "freeze_path": ROOT / "docs/evidence/odoo-v066-train-recorder-code-freeze-post-restart-2026-09-28.json",
            "repo": ROOT,
        }

    def test_real_saved_chain_and_public_redaction(self):
        receipt = auditor.audit(**self.args)
        self.assertEqual(receipt["status"],
                         "source_bound_failed_train_pilot_pre_intent")
        self.assertEqual(receipt["matched_intent_result_steps"], 16)
        self.assertEqual(receipt["captured_frames"], 17)
        self.assertFalse(receipt["specific_contract_error_code_verified"])
        self.assertEqual(receipt["positive_pure_verifier_reward"], 1.0)
        self.assertTrue(receipt["post_reset_sql_equals_frozen_baseline"])
        public_text = json.dumps(receipt)
        for private_text in (str(self.attempt), str(self.binding),
                             str(self.private_plan), "password", "stale_frame"):
            self.assertNotIn(private_text, public_text)
        task_id = json.loads((self.attempt / "actions" /
                              "step-000-intent.private.json").read_bytes())["task_id"]
        self.assertNotIn(task_id, public_text)

    def test_tampered_dispatch_result_rejected_without_writing_original(self):
        target = self.attempt / "actions" / "step-005-result.private.json"
        original = auditor.raw_file

        def changed(path):
            raw = original(path)
            if Path(path) == target:
                value = json.loads(raw)
                value["intent_sha256"] = "0" * 64
                return auditor.canonical(value)
            return raw

        with patch.object(auditor, "raw_file", side_effect=changed):
            with self.assertRaisesRegex(
                    auditor.AuditError, "intent_result_or_trace_chain_invalid"):
                auditor.audit(**self.args)

    def test_old_source_freeze_mismatch_rejected(self):
        original = auditor.git_blob

        def changed(repo, revision, relative):
            raw = original(repo, revision, relative)
            return raw + b"\n" if relative == auditor.OLD_RECORDER else raw

        with patch.object(auditor, "git_blob", side_effect=changed):
            with self.assertRaisesRegex(auditor.AuditError,
                                        "old_code_freeze_unbound"):
                auditor.audit(**self.args)


if __name__ == "__main__":
    unittest.main()
