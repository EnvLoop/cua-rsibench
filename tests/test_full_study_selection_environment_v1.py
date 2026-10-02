"""All six original-software selection cost classes stay explicit."""

from __future__ import annotations

import unittest

from cursibench.full_study_matrix_v1 import CELLS
from cursibench import full_study_selection_environment_v1 as environment


class SelectionEnvironmentTests(unittest.TestCase):
    def test_all_six_cells_have_exact_pre_result_environment_class(self):
        expected = {
            "powerpoint-web": "e2b", "excel-web": "e2b",
            "desktop-native": "e2b",
            "odoo-community": "storage_application",
            "gitlab": "storage_application",
            "magento-admin": "storage_application",
        }
        self.assertEqual(set(environment.BY_CELL), set(CELLS))
        self.assertEqual(environment.BY_CELL, expected)
        self.assertRegex(environment.binding_sha256(), r"^[0-9a-f]{64}$")
        for cell, category in expected.items():
            with self.subTest(cell=cell):
                self.assertEqual(environment.category(cell), category)
                self.assertTrue(environment.paid_categories_valid(
                    cell, {"tinker", category}))
                other = ({"tinker", "storage_application"} if category ==
                         "e2b" else {"tinker", "e2b"})
                self.assertFalse(environment.paid_categories_valid(cell, other))
                self.assertFalse(environment.paid_categories_valid(
                    cell, {category}))

    def test_self_hosted_cannot_claim_e2b_as_extra_environment(self):
        for cell in ("odoo-community", "gitlab", "magento-admin"):
            with self.subTest(cell=cell):
                self.assertFalse(environment.paid_categories_valid(
                    cell, {"tinker", "storage_application", "e2b"}))


if __name__ == "__main__":
    unittest.main()
