"""Independent arithmetic equivalence and counterfactual hardcoding checks."""

from __future__ import annotations

import unittest

from native_desktop_factory.formula_semantics import semantically_equivalent


CELLS = {
    "Evidence ledger": {
        "B7": {"formula": None, "value": "90"},
        "B8": {"formula": None, "value": "100"},
        "B9": {"formula": None, "value": "110"},
        "C4": {"formula": None, "value": "80"},
        "C9": {"formula": None, "value": "100"},
        "D9": {"formula": None, "value": "7.5"},
    },
    "Risk policy": {"B4": {"formula": None, "value": "5"}},
}


class FormulaSemanticTests(unittest.TestCase):
    def test_equivalent_growth_and_cagr_formulas_pass(self):
        self.assertTrue(semantically_equivalent(
            "=('Evidence ledger'!B9-'Evidence ledger'!B8)/'Evidence ledger'!B8*100",
            "=('Evidence ledger'!B9/'Evidence ledger'!B8-1)*100",
            CELLS, private_salt="private-test-salt"))
        self.assertTrue(semantically_equivalent(
            "=100*(('Evidence ledger'!C9/'Evidence ledger'!C4)^(0.2)-1)",
            "=(('Evidence ledger'!C9/'Evidence ledger'!C4)^(1/5)-1)*100",
            CELLS, private_salt="private-test-salt"))

    def test_wrong_year_constant_and_hardcoded_policy_fail(self):
        truth = "=('Evidence ledger'!B9/'Evidence ledger'!B8-1)*100"
        self.assertFalse(semantically_equivalent(
            "=('Evidence ledger'!B9/'Evidence ledger'!B7-1)*100", truth,
            CELLS, private_salt="private-test-salt"))
        self.assertFalse(semantically_equivalent("=10", truth, CELLS,
                                                 private_salt="private-test-salt"))
        self.assertFalse(semantically_equivalent(
            "='Evidence ledger'!D9-5",
            "='Evidence ledger'!D9-'Risk policy'!B4",
            CELLS, private_salt="private-test-salt"))

    def test_unsafe_syntax_is_rejected(self):
        truth = "=('Evidence ledger'!B9/'Evidence ledger'!B8-1)*100"
        for attempted in ("=__import__('os').system('echo x')", "=1/0",
                          "='[external.xlsx]Sheet1'!A1", "=A1", "=SUM(A1:A10)"):
            with self.subTest(formula=attempted):
                self.assertFalse(semantically_equivalent(attempted, truth, CELLS,
                                                         private_salt="private-test-salt"))


if __name__ == "__main__":
    unittest.main()
