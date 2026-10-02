"""Current-candidate Odoo saved-state semantics and old-attempt rejection."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from tests import test_odoo_v066_scale_controls as legacy
from tools import audit_odoo_v066_current_candidate_case_v1 as audit
from tools import odoo_v066_current_candidate_case_v1 as actor
from tools import odoo_v066_scale_protocol_v1 as protocol


class CurrentCandidateCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        # Reuse the older auditor's independent synthetic SQL/filestore setup,
        # then change only the new epoch identity. Its positive, wrong-object
        # negative, and reset states remain separate saved artifacts.
        legacy.IndependentSavedStateTests.setUp(self)
        self.plan["current_candidate_private_sha256"] = "d" * 64
        self.plan["historical_ratification_sha256"] = protocol.RATIFICATION_SHA
        self.row.update({
            "epoch_source_freeze_sha256": "e" * 64,
            "no_gui_gate_sha256": "f" * 64,
            "run_nonce_sha256": "1" * 64,
        })
        self.receipt["schema"] = actor.EPOCH_CASE_SCHEMA
        self.receipt["status"] = actor.EPOCH_CASE_STATUS
        self.receipt.pop("ratification_sha256")
        self.receipt.update({
            "plan_sha256": protocol.digest(protocol.canonical(self.plan)),
            "current_candidate_private_sha256":
                self.plan["current_candidate_private_sha256"],
            "historical_ratification_sha256": protocol.RATIFICATION_SHA,
            "epoch_source_freeze_sha256":
                self.row["epoch_source_freeze_sha256"],
            "no_gui_gate_sha256": self.row["no_gui_gate_sha256"],
            "run_nonce_sha256": self.row["run_nonce_sha256"],
        })
        legacy.write(self.attempt / "attempt.private.json", self.receipt)
        legacy.write(self.attempt / "intent.private.json", {
            "schema": actor.INTENT_SCHEMA,
            "task_id": self.row["task_id"],
            "package_sha256": self.row["package_sha256"],
            "current_candidate_private_sha256":
                self.plan["current_candidate_private_sha256"],
            "epoch_source_freeze_sha256":
                self.row["epoch_source_freeze_sha256"],
            "no_gui_gate_sha256": self.row["no_gui_gate_sha256"],
            "run_nonce_sha256": self.row["run_nonce_sha256"],
        })

    def test_fake_positive_wrong_object_and_full_reset_are_rederived(self) -> None:
        result = audit.audit_current_case(
            plan=self.plan, row=self.row, attempt=self.attempt,
            worker_private=self.private)
        self.assertEqual(result["independent_baseline_reward"], 0.0)
        self.assertEqual(result["independent_positive_reward"], 1.0)
        self.assertEqual(result["independent_wrong_object_reward"], 0.0)
        self.assertTrue(result["full_pre_web_filestore_reset_exact"])
        self.assertTrue(result["protected_post_web_source_bytes_equal"])
        self.assertEqual(result["official_final_tasks_admitted"], 0)

    def test_old_receipt_cannot_be_laundered_into_current_candidate(self) -> None:
        self.receipt["schema"] = protocol.CASE_SCHEMA
        self.receipt["status"] = "raw_gui_positive_negative_reset_complete_source_review_pending"
        self.receipt["ratification_sha256"] = protocol.RATIFICATION_SHA
        legacy.write(self.attempt / "attempt.private.json", self.receipt)
        with self.assertRaisesRegex(ValueError,
                                    "scale_case_receipt_identity_or_refs_invalid"):
            audit.audit_current_case(
                plan=self.plan, row=self.row, attempt=self.attempt,
                worker_private=self.private)

    def test_rehashed_wrong_object_state_still_fails_independent_score(self) -> None:
        positive = json.loads((self.attempt / "positive_sql.json").read_bytes())
        path = self.attempt / "negative_sql.json"
        legacy.write(path, positive)
        self.receipt["refs"]["negative_sql"]["sha256"] = protocol.digest(
            path.read_bytes())
        legacy.write(self.attempt / "attempt.private.json", self.receipt)
        with self.assertRaisesRegex(ValueError,
                                    "scale_case_independent_saved_state_or_negative_invalid"):
            audit.audit_current_case(
                plan=self.plan, row=self.row, attempt=self.attempt,
                worker_private=self.private)


if __name__ == "__main__":
    unittest.main()
