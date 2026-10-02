"""GitLab source partitions satisfy the shared GUI SFT split gate."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cursibench import gui_sft_episode_v2 as shared
from gitlab_world import factory, sft_binding


class GitLabSftSplitTests(unittest.TestCase):
    def test_selection_final_and_train_source_are_entity_template_disjoint(self):
        world = factory.build_world("gitlab-sft-split-test-private-seed-001")
        reserve = factory.reserve_replacement("gitlab-sft-split-test-private-seed-001")
        world["reserve_projects"] = [reserve["project"]]
        world["reserve_tasks"] = reserve["tasks"]
        final = [row for row in world["tasks"]
                 if row["partition"] == "final_candidate_unsealed"]
        with patch.object(sft_binding.sweep, "candidates", return_value=final):
            selection, exam, source = sft_binding.manifests(world)
        self.assertEqual((len(selection["items"]), len(exam["items"])), (20, 100))
        with tempfile.TemporaryDirectory() as tmp:
            select_path = Path(tmp) / "selection.json"
            final_path = Path(tmp) / "final.json"
            select_path.write_text(json.dumps(selection))
            final_path.write_text(json.dumps(exam))
            receipt = shared.validate_split_exclusion(
                source, "gitlab_project", select_path, final_path)
            self.assertTrue(receipt["selection_final_task_template_disjoint"])
            self.assertTrue(receipt["selection_final_declared_entities_disjoint"])
            self.assertTrue(receipt["train_source_task_template_and_declared_entities_disjoint"])
            source["entity_tags"] = exam["items"][0]["entity_tags"]
            with self.assertRaises(shared.EpisodeGateError):
                shared.validate_split_exclusion(
                    source, "gitlab_project", select_path, final_path)


if __name__ == "__main__":
    unittest.main()
