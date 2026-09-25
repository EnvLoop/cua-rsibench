"""The cross-cell matrix must not turn public candidate IDs into final tasks."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_saas_admission_matrix_v06 as matrix  # noqa: E402
import plan_gitlab_final_candidates_v06 as gitlab  # noqa: E402
from tests.test_plan_gitlab_final_candidates_v06 import fake_rows  # noqa: E402


class SaaSMatrixTests(unittest.TestCase):
    def test_mutation_retrieval_navigation_require_distinct_oracles(self):
        for kind, requirement in (
            ("mutate", "persisted_saved_state_readback"),
            ("retrieve", "browsing_and_answer_provenance"),
            ("navigate", "rendered_final_destination_readback"),
        ):
            pending = matrix.pending_for({"task_type": kind})
            self.assertIn(requirement, pending)
            self.assertIn("reset_to_exact_monitored_baseline", pending)
            self.assertIn("evaluator_owned_unpublished_variant_and_answer_seal", pending)

    def test_source_plan_remains_provisional_even_with_100_candidates(self):
        manifest = gitlab.manifest(fake_rows(), set())
        cell = matrix.make_cell("gitlab", manifest)
        self.assertEqual(cell["provisional_final_count"], 100)
        self.assertEqual(cell["official_final_admitted_count"], 0)
        self.assertEqual(len(cell["candidate_gate_queue"]), 100)
        self.assertTrue(all(item["admission_status"] == "offline_candidate_unverified"
                            for item in cell["candidate_gate_queue"]))

    def test_forged_admission_claim_fails_closed(self):
        manifest = gitlab.manifest(fake_rows(), set())
        modified = copy.deepcopy(manifest)
        modified["counts"]["provisional_final_officially_admitted"] = 1
        with self.assertRaisesRegex(ValueError, "cannot admit official final"):
            matrix.make_cell("gitlab", modified)
        modified = copy.deepcopy(manifest)
        modified["task_sets"]["provisional_final"][0]["admission_status"] = "official_final"
        with self.assertRaisesRegex(ValueError, "unsupported admission claim"):
            matrix.make_cell("gitlab", modified)


if __name__ == "__main__":
    unittest.main()
