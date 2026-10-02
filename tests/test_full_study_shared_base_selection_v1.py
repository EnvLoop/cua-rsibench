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

    def test_self_hosted_batch_lease_and_sampler_setup_cover_same_twenty(self):
        cell_id = "odoo-community"
        source = fixture.build(
            self.study, self.budget, cell_id,
            environment_batch=True, tinker_setup=True)
        result, digest = shared.verify_receipt(
            self.study, self.budget, cell_id, source,
            require_registry=False)
        self.assertEqual(len(result["tasks"]), 20)
        self.assertEqual(shared.admit_receipt(
            self.study, self.budget, cell_id, source)[
            "shared_receipt_sha256"], digest)
        paid = self.budget.owner_attempts(cell_id + ":shared-base")
        self.assertEqual(len(paid), 22)
        self.assertEqual(sum(row["category"] == "storage_application"
                             for row in paid.values()), 1)
        self.assertEqual(sum(row["category"] == "tinker"
                             for row in paid.values()), 21)

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

    def test_hash_audited_tinker_result_must_say_completed(self):
        receipt = json.loads(self.path.read_bytes())
        first = receipt["paid_attempt_refs"][0]
        self.assertEqual(first["category"], "tinker")
        result_path = self.path.parent / first["result_ref"]["path"]
        value = json.loads(result_path.read_bytes())
        value["status"] = "failed"
        raw = shared._canonical(value)
        result_path.write_bytes(raw)
        first["result_ref"]["sha256"] = shared._sha(raw)
        self.path.write_bytes(shared._canonical(receipt))
        with self.assertRaisesRegex(shared.SharedBaseSelectionError,
                                    "paid_result_not_completed"):
            shared.verify_receipt(
                self.study, self.budget, self.cell_id, self.path,
                require_registry=False)

    def test_gitlab_raw_provider_model_must_match_frozen_base(self):
        cell_id = "gitlab"
        source = fixture.build(self.study, self.budget, cell_id)
        receipt = json.loads(source.read_bytes())
        paid = next(item for item in receipt["paid_attempt_refs"]
                    if item["category"] == "tinker")
        result_path = source.parent / paid["result_ref"]["path"]
        result = json.loads(result_path.read_bytes())
        worker_path = source.parent / result["worker_result_ref"]["path"]
        worker_result = json.loads(worker_path.read_bytes())
        worker_result["reported_model"] = "wrong-model"
        raw = shared._canonical(worker_result)
        worker_path.write_bytes(raw)
        result["worker_result_ref"]["sha256"] = shared._sha(raw)
        raw = shared._canonical(result)
        result_path.write_bytes(raw)
        paid["result_ref"]["sha256"] = shared._sha(raw)
        source.write_bytes(shared._canonical(receipt))
        with self.assertRaisesRegex(shared.SharedBaseSelectionError,
                                    "gitlab_provider_model_changed"):
            shared.verify_receipt(self.study, self.budget, cell_id, source,
                                  require_registry=False)

    def test_odoo_raw_sampler_kind_must_be_base(self):
        cell_id = "odoo-community"
        source = fixture.build(
            self.study, self.budget, cell_id,
            environment_batch=True, tinker_setup=True)
        receipt = json.loads(source.read_bytes())
        paid = next(item for item in receipt["paid_attempt_refs"]
                    if item["category"] == "tinker")
        request_path = source.parent / paid["request_ref"]["path"]
        request = json.loads(request_path.read_bytes())
        worker_path = source.parent / request["worker_request_ref"]["path"]
        worker = json.loads(worker_path.read_bytes())
        worker["sampling_kind"] = "checkpoint"
        raw = shared._canonical(worker)
        worker_path.write_bytes(raw)
        request["worker_request_ref"]["sha256"] = shared._sha(raw)
        raw = shared._canonical(request)
        request_path.write_bytes(raw)
        paid["request_ref"]["sha256"] = shared._sha(raw)
        source.write_bytes(shared._canonical(receipt))
        with self.assertRaisesRegex(shared.SharedBaseSelectionError,
                                    "odoo_base_sampler_changed"):
            shared.verify_receipt(self.study, self.budget, cell_id, source,
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
