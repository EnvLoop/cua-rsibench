"""Synthetic-only contract tests for the TRAIN tax-position oracle and gate."""

from __future__ import annotations

import copy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from sec_excel_factory.audit_tax_train_transfer_two import _require_frozen_case_exact
from sec_excel_factory.verify_tax_train_transfer_two import (
    TARGETS, _case_scope, _close, _counterfactuals, expected_values,
)
from tools.sec_tax_train_prepare_v1 import CARD_SIGNATURE, GRAPH, _fact, _make_case


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

    def test_balanced_fact_tamper_cannot_match_frozen_review(self) -> None:
        fixture = _case()
        plan = {"issuer_cik": 999999, "accession": "0000999999-25-000001",
                "form": "10-K", "primary_document": "synthetic-10k.html",
                "final_graph_reservation": GRAPH,
                "skill_signature_sha256": CARD_SIGNATURE}
        card = {"minimum_target_edits": 9, "independent_skill_review": True,
                "causal_skill_atoms": ["synthetic causal step"],
                "dependency_edges": []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source-00"
            root.mkdir()
            raw = {}
            for name in ("10k.html", "companyfacts.json"):
                data = f"synthetic fixture {name}".encode()
                (root / name).write_bytes(data)
                raw[name] = sha256(data).hexdigest()
            periods = []
            for i, period in enumerate(fixture["periods"]):
                projection = {}
                for key, fact in period["fields"].items():
                    projected = "net_interest_expense" if key == "interest_flow" else key
                    source = None if fact["presence"] == "not_separately_reported" else {
                        "companyfacts_same_accession_match": True,
                        "document": "10k.html", "ixbrl_tag": "synthetic:Fact",
                        "ixbrl_context_ref": f"synthetic-context-{i}-{key}",
                        "context_period": {"instant": period["period_end"]},
                        "filed_musd": abs(fact["value"]),
                    }
                    projection[projected] = {
                        "status": fact["presence"],
                        "signed_value_musd": fact["value"],
                        "source_field": source}
                projection["combined_interest_penalties_expense_benefit"] = {
                    "status": "not_separately_reported",
                    "signed_value_musd": None, "source_field": None}
                periods.append({"period_end": period["period_end"],
                                "period_start": "synthetic-period-start",
                                "bridge_arithmetic_delta_musd": 0,
                                "template_fields": projection})
            reviewed = {"source_index": 0, "identity": plan,
                        "semantic_source_review": "pass",
                        "official_final_case_admitted": False,
                        "excel_web_admitted": False,
                        "raw_sha256": raw,
                        "bridge_location": {"document": "10k.html"},
                        "periods": periods}
            exact = _make_case(0, reviewed, plan, Path(temp),
                               "synthetic-review-sha", card)
            _require_frozen_case_exact(exact, exact)
            changed = copy.deepcopy(exact)
            current = changed["periods"][1]["fields"]
            current["current_year_additions"]["value"] += 1
            current["prior_year_reductions"]["value"] -= 1
            _case_scope(changed)  # The signed arithmetic still balances.
            with self.assertRaisesRegex(ValueError,
                                        "private_case_fields_differ_from_frozen_semantic_review"):
                _require_frozen_case_exact(changed, exact)


if __name__ == "__main__":
    unittest.main()
