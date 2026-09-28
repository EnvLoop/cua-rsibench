"""Fail-closed checks for the read-only GitLab admission preflight."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import audit_gitlab_final_candidate_preflight_v1 as preflight


class GitLabFinalCandidatePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.baseline = self._snapshot({"issues": []})
        self.saved = self._snapshot({"issues": [{"id": 1, "label": "fixed"}]})
        self.case = self.root / "gui-controls" / "task" / "trio-123" / "positive-1"
        self.case.mkdir(parents=True)
        (self.root / "gui-controls").chmod(0o700)
        (self.case / "policy.png").write_bytes(b"visible policy screenshot")
        (self.case / "issue-after.png").write_bytes(b"saved issue screenshot")
        self._write(self.case / "after-persisted-state.json", self.saved)
        self.attempt = {
            "schema": "envloop-gitlab-gui-control-attempt-v1",
            "task_id": "task", "case": "positive-1",
            "fresh_browser_context": True, "scoped_non_admin_operator": True,
            "credential_retained_in_receipt": False, "raw_har_retained": False,
            "model_calls": 0,
            "gui": {"policy_rendered": True, "saved_visible": True,
                    "screenshot_sha256": {
                        "policy.png": preflight.sha(b"visible policy screenshot"),
                        "issue-after.png": preflight.sha(b"saved issue screenshot")}},
            "persisted_oracle": {
                "task_id": "task", "score": 1.0,
                "persisted_oracle": True, "no_regression": True,
                "before_business_sha256": self.baseline["business_sha256"],
                "after_business_sha256": self.saved["business_sha256"]},
            "cold_reset": {"cold_reset": True, "same_business_sha256": True,
                           "container_identity_changed": True, "generation": 7},
        }
        receipt = copy.deepcopy(self.attempt)
        receipt.pop("cold_reset")
        self._write(self.case / "receipt.json", receipt)

    def _snapshot(self, db: dict) -> dict:
        value = {"schema": "envloop-gitlab-persisted-snapshot-v1",
                 "project_ids": [1], "db": db, "git": {"1": {"refs": {}}}}
        value["business_sha256"] = preflight.sha(preflight.canonical(value))
        return value

    def _write(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        path.chmod(0o600)

    def test_valid_case_rehashes_original_receipt_state_and_screens(self) -> None:
        result = preflight.verify_case(
            self.root, self.case, self.attempt, task_id="task",
            baseline=self.baseline, expected_score=1.0)
        self.assertEqual(result["reset_generation"], 7)
        self.assertEqual(result["mutated_business_sha256"],
                         self.saved["business_sha256"])
        self.assertEqual(set(result["screenshot_sha256s"]),
                         {"policy.png", "issue-after.png"})

    def test_changed_screenshot_is_rejected(self) -> None:
        (self.case / "issue-after.png").write_bytes(b"wrong pixels")
        with self.assertRaisesRegex(ValueError, "case_screen_bytes_changed"):
            preflight.verify_case(self.root, self.case, self.attempt,
                                  task_id="task", baseline=self.baseline,
                                  expected_score=1.0)

    def test_changed_persisted_snapshot_is_rejected(self) -> None:
        wrong = copy.deepcopy(self.saved)
        wrong["db"]["issues"][0]["label"] = "wrong"
        self._write(self.case / "after-persisted-state.json", wrong)
        with self.assertRaisesRegex(ValueError, "persisted_state_readback_changed"):
            preflight.verify_case(self.root, self.case, self.attempt,
                                  task_id="task", baseline=self.baseline,
                                  expected_score=1.0)

    def test_missing_reset_and_fake_negative_are_rejected(self) -> None:
        missing = copy.deepcopy(self.attempt)
        missing["cold_reset"]["same_business_sha256"] = False
        with self.assertRaisesRegex(ValueError, "case_fresh_reset_receipt_changed"):
            preflight.verify_case(self.root, self.case, missing,
                                  task_id="task", baseline=self.baseline,
                                  expected_score=1.0)
        negative = copy.deepcopy(self.attempt)
        negative["persisted_oracle"]["score"] = 0.0
        mirrored = copy.deepcopy(negative)
        mirrored.pop("cold_reset")
        self._write(self.case / "receipt.json", mirrored)
        with self.assertRaisesRegex(ValueError, "case_oracle_or_no_regression_changed"):
            preflight.verify_case(self.root, self.case, negative,
                                  task_id="task", baseline=self.baseline,
                                  expected_score=0.0)

    def test_private_file_symlink_is_rejected(self) -> None:
        link = self.root / "linked.json"
        link.symlink_to(self.case / "receipt.json")
        with self.assertRaisesRegex(ValueError, "private_evidence_symlink"):
            preflight.read_file(link, self.root)

    def test_private_ledger_write_is_exclusive_and_restrictive(self) -> None:
        self.assertIn("v066_live_student_observation_and_sampling_not_qualified",
                      preflight.BLOCKERS)
        self.assertIn("per_task_v06_reset_and_verifier_proofs_not_issued",
                      preflight.BLOCKERS)
        path = self.root / "ledger.private.json"
        digest = preflight.write_new(path, {"official_final_admitted": 0}, 0o600)
        self.assertEqual(preflight.sha(path.read_bytes()), digest)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            preflight.write_new(path, {"official_final_admitted": 100}, 0o600)
        self.assertEqual(json.loads(path.read_bytes())["official_final_admitted"], 0)


if __name__ == "__main__":
    unittest.main()
