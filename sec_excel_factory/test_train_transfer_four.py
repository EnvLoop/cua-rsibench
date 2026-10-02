"""Public synthetic contract tests for the TRAIN-only SEC OOXML scorer."""

from __future__ import annotations

import unittest

from sec_excel_factory.verify_train_transfer_four import (
    CASH, CASH_TARGETS, INTEREST, INTEREST_TARGETS,
    _close, _counterfactuals, expected_values,
)


def _facts(**amounts: float) -> dict:
    return {key: {"value": value} for key, value in amounts.items()}


def _cash_case() -> dict:
    return {
        "profile": CASH,
        "scenario": {"operating_change": -0.1,
                     "extra_investing_share": 0.05,
                     "fx_share_change": 0.01},
        "periods": [
            {"facts": _facts(operating=100, investing=-20, financing=-10,
                             fx=0, net_change=70, beginning=50, ending=120,
                             cash=100, restricted=20)},
            {"facts": _facts(operating=120, investing=-30, financing=-20,
                             fx=-5, net_change=65, beginning=120, ending=185,
                             cash=150, restricted=35)},
        ],
    }


def _interest_case(control: str) -> dict:
    prior = _facts(operating_income=150, interest_expense_abs=10,
                   cash_from_operations=100, debt_component_1=50,
                   debt_component_2=50)
    current = _facts(operating_income=180, interest_expense_abs=12,
                     cash_from_operations=120, debt_component_1=60,
                     debt_component_2=70)
    if control == "direct_principal":
        prior["debt_principal_direct"] = {"value": 100}
        current["debt_principal_direct"] = {"value": 130}
    else:
        prior["debt_carrying"] = {"value": 97}
        prior["unamortized_cost"] = {"value": 3}
        current["debt_carrying"] = {"value": 126}
        current["unamortized_cost"] = {"value": 4}
    return {"profile": INTEREST, "source": {"debt_control_kind": control},
            "scenario": {"rate_change": 0.02,
                         "income_change": -0.1,
                         "cash_flow_change": -0.05},
            "periods": [{"facts": prior, "component_count": 2},
                        {"facts": current, "component_count": 2}]}


class TrainTransferCounterfactualTests(unittest.TestCase):
    def _assert_all_targets_dynamic(self, case: dict, targets: set) -> None:
        base = expected_values(case)
        self.assertEqual(set(base), targets)
        witnessed = set()
        for source, drivers in _counterfactuals(case):
            changed = expected_values(case, source_changes=source,
                                      driver_changes=drivers)
            witnessed.update(key for key in targets
                             if not _close(base[key], changed[key]))
        self.assertEqual(witnessed, targets)

    def test_cash_profile_each_target_has_a_dependency_witness(self) -> None:
        self._assert_all_targets_dynamic(_cash_case(), CASH_TARGETS)

    def test_direct_principal_each_target_has_a_dependency_witness(self) -> None:
        self._assert_all_targets_dynamic(_interest_case("direct_principal"), INTEREST_TARGETS)

    def test_carrying_bridge_each_target_has_a_dependency_witness(self) -> None:
        self._assert_all_targets_dynamic(_interest_case("carrying_plus_unamortized_cost"),
                                         INTEREST_TARGETS)


if __name__ == "__main__":
    unittest.main()
