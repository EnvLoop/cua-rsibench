"""A GitLab project, not each correlated task, is one analysis family."""

import unittest
from unittest.mock import patch

from gitlab_world import analysis_binding, factory


class GitLabAnalysisBindingTests(unittest.TestCase):
    def test_exact_100_task_20_project_mapping(self):
        world = factory.build_world("analysis-binding-test-private-seed-001")
        rows = [row for row in world["tasks"]
                if row["partition"] == "final_candidate_unsealed"]
        with patch.object(analysis_binding.sweep, "candidates", return_value=rows):
            result = analysis_binding.manifest()
            self.assertEqual(result["schema"], "cua-cell-analysis-families-v1")
            self.assertEqual(result["cell_id"], "gitlab")
            self.assertEqual(len(result["family_by_task"]), 100)
            self.assertEqual(len(set(result["family_by_task"].values())), 20)
        with patch.object(analysis_binding.sweep, "candidates", return_value=rows[:-1]):
            with self.assertRaises(ValueError):
                analysis_binding.manifest()


if __name__ == "__main__":
    unittest.main()
