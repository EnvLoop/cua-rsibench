"""Offline shared-base gate tests; all task/provider evidence is synthetic."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from cursibench import full_study_budget_v1 as budget_module
from cursibench import full_study_matrix_v1 as matrix
from cursibench import full_study_shared_base_selection_v1 as shared
from tests import shared_base_selection_fixture as fixture
from tests import test_full_study_campaign_dispatch_v1 as dispatch_fixture


class SharedBaseSelectionGateTests(unittest.TestCase):
    def setUp(self):
        harness = dispatch_fixture.FullStudyDispatchTests(
            "test_campaign_cannot_start_without_one_shared_base_selection")
        harness.setUp()
        self.addCleanup(harness.tearDown)
        self.harness = harness
        self.study = harness.frozen()
        self.cell_id = matrix.CELLS[0]
        work = Path(self.study.repo_root) / "work"
        work.mkdir(mode=0o700, exist_ok=True)
        self.budget = budget_module.StudyBudgetLedger(
            work / "full-study-budget.jsonl", self.study.plan)
        self.path = fixture.build(self.study, self.budget, self.cell_id)

    def test_twenty_private_original_gui_scores_and_shared_paid_budget(self):
        result, digest = shared.verify_receipt(
            self.study, self.budget, self.cell_id, self.path,
            require_registry=False)
        self.assertEqual(len(result["tasks"]), 20)
        admitted = shared.admit_receipt(
            self.study, self.budget, self.cell_id, self.path)
        self.assertEqual(admitted["shared_receipt_sha256"], digest)
        self.assertEqual(admitted["wins"], 0)
        reopened, current = shared.verify_receipt(
            self.study, self.budget, self.cell_id, self.path)
        self.assertEqual(reopened, result)
        self.assertEqual(current, digest)
        paid = self.budget.owner_attempts(self.cell_id + ":shared-base")
        self.assertEqual(len(paid), 40)
        self.assertEqual({row["status"] for row in paid.values()},
                         {"settled"})

    def test_missing_or_tampered_gui_and_saved_state_cannot_be_admitted(self):
        trace = self.path.parent / "task-001" / "gui-trace.json"
        original = trace.read_bytes()
        try:
            trace.write_bytes(original + b" ")
            with self.assertRaises(shared.SharedBaseSelectionError):
                shared.admit_receipt(
                    self.study, self.budget, self.cell_id, self.path)
        finally:
            trace.write_bytes(original)
        saved = self.path.parent / "task-001" / "saved.json"
        original = saved.read_bytes()
        try:
            saved.write_bytes(original + b" ")
            with self.assertRaises(shared.SharedBaseSelectionError):
                shared.admit_receipt(
                    self.study, self.budget, self.cell_id, self.path)
        finally:
            saved.write_bytes(original)
        self.assertFalse((self.path.parent / "accepted.private.json").exists())

    def test_wrong_environment_or_extra_unreconciled_paid_attempt_fails(self):
        original = self.path.read_bytes()
        try:
            value = json.loads(original)
            value["paid_attempt_refs"][1]["category"] = "storage_application"
            self.path.write_bytes(shared._canonical(value))
            with self.assertRaises(shared.SharedBaseSelectionError):
                shared.verify_receipt(
                    self.study, self.budget, self.cell_id, self.path,
                    require_registry=False)
        finally:
            self.path.write_bytes(original)
        self.budget.reserve("unreferenced-shared-base-tinker",
                            self.cell_id + ":shared-base", "tinker",
                            "0.01", shared._sha(b"unreferenced work"))
        with self.assertRaisesRegex(shared.SharedBaseSelectionError,
                                    "paid_budget_attempts_unmatched"):
            shared.verify_receipt(
                self.study, self.budget, self.cell_id, self.path,
                require_registry=False)

    def test_registered_bytes_cannot_change_between_four_campaigns(self):
        admitted = shared.admit_receipt(
            self.study, self.budget, self.cell_id, self.path)
        original = self.path.read_bytes()
        try:
            self.path.write_bytes(original + b" ")
            with self.assertRaisesRegex(shared.SharedBaseSelectionError,
                                        "registry_changed"):
                shared.verify_receipt(
                    self.study, self.budget, self.cell_id, self.path)
        finally:
            self.path.write_bytes(original)
        self.assertEqual(shared.verify_receipt(
            self.study, self.budget, self.cell_id, self.path)[1],
            admitted["shared_receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
