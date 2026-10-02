"""Calibrate potential numeric/role scoring against paraphrases and traps."""

from __future__ import annotations

import unittest

from native_desktop_factory.target_text_semantics import semantically_correct


class TargetTextSemanticTests(unittest.TestCase):
    def test_valid_wdi_statement_paraphrases(self):
        self.assertTrue(semantically_correct(
            "GDP increased 6.560% in 2024 from 2023.",
            "GDP finding: nominal output grew 6.56% from 2023 to 2024."))
        self.assertTrue(semantically_correct(
            "Inflation changed by -0.790 percentage points in 2024 vs 2023.",
            "Price finding: inflation changed by -0.79 percentage points from 2023 to 2024."))
        self.assertTrue(semantically_correct(
            "The 2024 unemployment rate was 11.4 percent.",
            "Labor finding: 2024 unemployment was 11.40%."))

    def test_wrong_value_period_unit_or_ambiguous_number_rejected(self):
        truth = "2024 inflation acceleration: -0.79 pp"
        for wrong in ("2024 inflation acceleration: -0.29 pp",
                      "2023 inflation acceleration: -0.79 pp",
                      "2024 inflation acceleration: -0.79%",
                      "2024 inflation acceleration: -0.79 pp (draft -2.29 pp)",
                      "2024 GDP growth: -0.79 pp"):
            with self.subTest(wrong=wrong):
                self.assertFalse(semantically_correct(wrong, truth))


if __name__ == "__main__":
    unittest.main()
