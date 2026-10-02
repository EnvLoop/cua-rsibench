"""Private group boundaries for non-admin GitLab actors."""

import unittest

from gitlab_world import factory, operators


class GitLabOperatorPlanTests(unittest.TestCase):
    def test_train_selection_evaluation_groups_are_distinct(self):
        world = factory.build_world("operator-plan-test-private-seed-001")
        reserve = factory.reserve_replacement("operator-plan-test-private-seed-001")
        world["reserve_projects"] = [reserve["project"]]
        plan = operators.plan(world)
        self.assertEqual(len(set(plan["groups"].values())), 3)
        self.assertEqual(plan["expected_role_level"], 50)
        self.assertFalse(plan["expected_is_admin"])
        self.assertEqual(world["projects"][10]["group_path"],
                         plan["groups"]["final_candidate_unsealed"])
        self.assertEqual(reserve["project"]["group_path"],
                         plan["groups"]["final_candidate_unsealed"])


if __name__ == "__main__":
    unittest.main()
