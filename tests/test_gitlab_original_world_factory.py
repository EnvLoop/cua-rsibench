"""Source, independence, and public-boundary tests for original GitLab world."""

import json
from pathlib import Path
import tempfile
import unittest

from gitlab_world import factory


SEED = "development-fixture-seed-is-private-001"


class GitLabWorldFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = factory.build_world(SEED)

    def test_pinned_cc0_source_and_world_cardinality(self):
        self.assertEqual(len(factory.source_excerpt()["records"]), 120)
        self.assertEqual(len(self.world["projects"]), 30)
        self.assertEqual(len(self.world["tasks"]), 140)
        self.assertEqual(self.world["split_audit"]["task_counts"], {
            "train": 20, "selection": 20, "final_candidate_unsealed": 100})
        self.assertEqual(self.world["split_audit"]["official_final_admitted"], 0)

    def test_project_source_entity_principal_template_sets_are_disjoint(self):
        audit = self.world["split_audit"]
        self.assertTrue(audit["all_cross_partition_disjoint"])
        self.assertEqual(audit["source_record_count"], 120)
        for pair in audit["overlap_counts"].values():
            self.assertEqual(set(pair.values()), {0})
        self.assertEqual(len({task["task_id"] for task in self.world["tasks"]}), 140)
        self.assertEqual(len({task["source_family"] for task in self.world["tasks"]}), 30)

    def test_real_advisory_facts_and_synthetic_overlay_are_labeled(self):
        project = self.world["projects"][10]
        self.assertIn(project["advisories"][0]["cveID"], project["files"]["security/kev-register.csv"])
        self.assertIn("Synthetic internal", project["files"]["README.md"])
        self.assertEqual(len(project["issues"]), 6)
        self.assertEqual(sum(issue["key"] == "historical_duplicate" for issue in project["issues"]), 1)
        self.assertTrue(any(issue["confidential"] for issue in project["issues"]))
        self.assertIn("rules:\n    - when: never", project["files"][".gitlab-ci.yml"])
        self.assertTrue(project["principals"]["incoming"] != project["principals"]["contractor"])
        self.assertEqual(len([task for task in self.world["tasks"]
                              if task["project_family"] == project["full_path"]]), 5)

    def test_private_seed_changes_source_mapping_and_public_receipt_excludes_gold(self):
        other = factory.build_world("development-fixture-seed-is-private-002")
        self.assertNotEqual([row["advisories"][0]["cveID"] for row in self.world["projects"]],
                            [row["advisories"][0]["cveID"] for row in other["projects"]])
        public = factory.public_receipt(self.world)
        serialized = json.dumps(public)
        self.assertNotIn("oracle", serialized)
        self.assertNotIn("prompt", serialized)
        self.assertNotIn("world_seed_sha256", serialized)
        self.assertNotIn(self.world["projects"][10]["advisories"][0]["cveID"], serialized)

    def test_private_write_is_exclusive_and_restrictive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private" / "world.json"
            factory.write_private(path, {"schema": "test"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                factory.write_private(path, {})

    def test_invalid_seed_or_source_row_count_fails_closed(self):
        with self.assertRaises(ValueError):
            factory.build_world("short")
        with self.assertRaises(ValueError):
            factory.build_world(SEED, records=factory.source_excerpt()["records"][:-1])


if __name__ == "__main__":
    unittest.main()
