"""Synthetic-only contract tests for the TRAIN tax-position oracle and gate."""

from __future__ import annotations

import unittest

from sec_excel_factory.verify_tax_train_transfer_two import (
    TARGETS, _case_scope, _close, _counterfactuals, expected_values,
)
from tools.sec_tax_train_prepare_v1 import _fact


def _item(value, presence="reported") -> dict:
    return {"presence": presence, "value": value,
            "document": "synthetic.html" if presence != "not_separately_reported" else None,
            "ixbrl_tag": "synthetic:Fact" if presence != "not_separately_reported" else None,
            "ixbrl_context_ref": "synthetic-context" if presence != "not_separately_reported" else None}


def _case() -> dict:
    prior = {"opening": _item(100), "current_year_additions": _item(20),
             "prior_year_additions": _item(3), "prior_year_reductions": _item(-5),
             "settlements": _item(-8), "lapse": _item(None, "not_separately_reported"),
             "translation": _item(None, "not_separately_reported"),
             "other": _item(None, "not_separately_reported"), "closing": _item(110),
             "accrued_interest_penalties": _item(4), "interest_flow": _item(2)}
    current = {"opening": _item(110), "current_year_additions": _item(30),
               "prior_year_additions": _item(5), "prior_year_reductions": _item(-4),
               "settlements": _item(-2), "lapse": _item(-1),
               "translation": _item(None, "not_separately_reported"),
               "other": _item(None, "not_separately_reported"), "closing": _item(138),
               "accrued_interest_penalties": _item(6), "interest_flow": _item(-1)}
    return {"schema": "envloop.sec_tax_train_analogue_case.private.v1",
            "scope": "TRAIN-only offline analogue; no final workbook or GUI admission",
            "source": {"raw_sha256": {"synthetic.html": "fixture-only"},
                       "interest_flow_label": "Net interest expense"},
            "skill": {"signature_sha256":
                      "ff413ae00b002631deefbccab6a6392405c63e6f31a968efbb5ef67aaa5506e8"},
            "scenario": {"additions": 7, "settlements": -3, "accrual_change": 0.1},
            "periods": [{"period_end": "2024-12-31", "fields": prior},
                        {"period_end": "2025-12-31", "fields": current}]}


class TaxTrainTransferSyntheticTests(unittest.TestCase):
    def test_signed_bridge_and_separate_interest_scope(self) -> None:
        case = _case()
        _case_scope(case)
        actual = expected_values(case)
        self.assertEqual(set(actual), TARGETS)
        self.assertEqual(actual[("Gross bridge", "C13")], 28)
        self.assertEqual(actual[("Gross bridge", "C14")], 138)
        self.assertEqual(actual[("Gross bridge", "C16")], 0)
        self.assertEqual(actual[("Interest scope", "C5")], 6)
        self.assertAlmostEqual(actual[("Tax summary", "B8")], 148.6)

    def test_each_target_has_counterfactual_witness(self) -> None:
        case = _case()
        baseline = expected_values(case)
        witnessed = set()
        for source, drivers in _counterfactuals(case):
            changed = expected_values(case, source_changes=source,
                                      driver_changes=drivers)
            witnessed.update(key for key in TARGETS
                             if not _close(changed[key], baseline[key]))
        self.assertEqual(witnessed, TARGETS)
        self.assertEqual(len(_counterfactuals(case)), 11)

    def test_joint_replay_rejects_additive_interaction_impostor(self) -> None:
        case = _case()
        base_accrued = case["periods"][1]["fields"]["accrued_interest_penalties"]["value"]
        base_rate = case["scenario"]["accrual_change"]
        gross = case["periods"][1]["fields"]["closing"]["value"] + 7 - 3

        def impostor(accrued: float, rate: float) -> float:
            return gross + accrued * (1 + base_rate) + base_accrued * (rate - base_rate)

        self.assertAlmostEqual(impostor(base_accrued, base_rate),
                               expected_values(case)[("Tax summary", "B8")])
        self.assertAlmostEqual(impostor(base_accrued + 4, base_rate),
                               expected_values(case, source_changes={
                                   (1, "accrued_interest_penalties"): base_accrued + 4
                               })[("Tax summary", "B8")])
        self.assertAlmostEqual(impostor(base_accrued, base_rate + 0.02),
                               expected_values(case, driver_changes={
                                   "accrual_change": base_rate + 0.02
                               })[("Tax summary", "B8")])
        joint = expected_values(case, source_changes={
            (1, "accrued_interest_penalties"): base_accrued + 4},
            driver_changes={"accrual_change": base_rate + 0.02})[("Tax summary", "B8")]
        self.assertNotAlmostEqual(impostor(base_accrued + 4, base_rate + 0.02), joint)

    def test_absent_category_cannot_be_filed_zero(self) -> None:
        case = _case()
        case["periods"][1]["fields"]["translation"]["value"] = 0
        with self.assertRaisesRegex(ValueError,
                                    "unreported_category_misrepresented_as_filed_zero"):
            _case_scope(case)
        with self.assertRaisesRegex(ValueError,
                                    "unreported_category_misrepresented_as_filed_fact"):
            _fact({"status": "not_separately_reported", "signed_value_musd": 0,
                   "source_field": None}, "translation", mandatory=False)


if __name__ == "__main__":
    unittest.main()
