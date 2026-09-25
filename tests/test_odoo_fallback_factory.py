"""Offline invariants for the original Odoo Community fallback prototypes."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ODDO_DIR = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18"
sys.path.insert(0, str(ODDO_DIR))
from factory import (  # noqa: E402
    SOURCE, candidates, catalog, confirmation, replenishment_candidates,
    proposed_clustered_split, sha256_bytes, split_audit, train_world_candidates,
)
from verify import evaluate, evaluate_replenishment  # noqa: E402


class OdooFixtureTests(unittest.TestCase):
    def test_seeded_candidate_shape_and_provenance(self):
        rfqs = candidates()
        rules = replenishment_candidates()
        self.assertEqual(len(rfqs), 120)
        self.assertEqual(len(rules), 20)
        self.assertEqual(len(catalog()), 48)
        self.assertEqual(len({r["id"] for r in rfqs}), 120)
        self.assertEqual(len({r["sku"] for r in rules}), 20)
        self.assertEqual(sum(r["partition"] == "selection_candidate" for r in rfqs), 20)
        self.assertEqual(sum(r["partition"] == "unsealed_scale_candidate" for r in rfqs), 100)
        self.assertEqual(set(Counter(r["pattern"] for r in rfqs).values()), {15})
        for case in rfqs:
            self.assertEqual(len(case["lines"]), 3)
            self.assertEqual(len({line["sku"] for line in case["lines"]}), 3)
            self.assertTrue(any(line["initial"] != line["expected"] for line in case["lines"]))
        for case in rules:
            self.assertNotEqual(case["initial"], case["expected"])
            self.assertIn("four-week demand", case["source_note"])
        source = SOURCE.read_bytes()
        self.assertEqual(len(json.loads(source)["records"]), 112)
        self.assertEqual(sha256_bytes(source), "df9f56387b2c30bc521d8a4eb13c6e437a065d3b921ed4ae3a5fab1e1f20f64a")

    def test_train_world_entities_are_disjoint_and_reproducible(self):
        first = train_world_candidates(20260925)
        self.assertEqual(first, train_world_candidates(20260925))
        self.assertNotEqual(first, train_world_candidates(20260926))
        self.assertEqual(len(first), 40)
        evaluated = candidates()
        self.assertFalse({c["id"] for c in first} & {c["id"] for c in evaluated})
        self.assertFalse({c["vendor"] for c in first} & {c["vendor"] for c in evaluated})
        self.assertFalse({l["sku"] for c in first for l in c["lines"]} &
                         {l["sku"] for c in evaluated for l in c["lines"]})
        audit = split_audit()
        self.assertEqual(audit["train_selection_overlap"]["vendors"], 0)
        self.assertEqual(audit["train_scale_overlap"]["skus"], 0)
        self.assertEqual(audit["selection_scale_overlap"],
                         {"ids": 0, "vendors": 20, "skus": 36, "patterns": 8})
        self.assertFalse(audit["official_entity_and_pattern_disjoint_gate"])

    def test_proposed_clustered_split_is_entity_disjoint_but_same_template(self):
        plan = proposed_clustered_split(20260925)
        self.assertEqual({part: len(rows) for part, rows in plan.items()},
                         {"train": 40, "selection": 20, "evaluation_candidate_unsealed": 100})
        self.assertEqual(plan, proposed_clustered_split(20260925))
        pools = {}
        for part, rows in plan.items():
            pools[part] = {
                "ids": {row["id"] for row in rows},
                "vendors": {row["vendor"] for row in rows},
                "skus": {line["sku"] for row in rows for line in row["lines"]},
                "patterns": {row["pattern"] for row in rows},
            }
            self.assertTrue(all(count == 5 for count in Counter(row["vendor"] for row in rows).values()))
        parts = list(pools)
        for index, left in enumerate(parts):
            for right in parts[index + 1:]:
                for field in ("ids", "vendors", "skus"):
                    self.assertFalse(pools[left][field] & pools[right][field])
                self.assertEqual(len(pools[left]["patterns"] & pools[right]["patterns"]), 8)

    @unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"),
                         "PDF report dependencies not installed")
    def test_confirmation_is_readable_single_page_pdf(self):
        from io import BytesIO
        from pypdf import PdfReader

        case = candidates()[4]
        data = confirmation(case)
        reader = PdfReader(BytesIO(data))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn(case["id"], text)
        self.assertIn("SYNTHETIC BENCHMARK DOCUMENT", text)
        for line in case["lines"]:
            self.assertIn(line["sku"], text)
            self.assertIn(f"{line['expected']['price']:.2f}", text)


class IndependentEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "orders": [{"id": 1, "name": "ELPO-0001"}],
            "lines": [
                {"id": 1, "order_id": 1, "product_id": 10, "name": "target", "qty": "2", "price": "12.00", "date": "2025-01-01"},
                {"id": 2, "order_id": 2, "product_id": 20, "name": "other", "qty": "3", "price": "15.00", "date": "2025-01-02"},
            ],
            "attachments": [{"id": 1, "checksum": "abc"}],
            "vendors": [{"id": 1, "name": "Vendor"}],
            "products": [{"id": 10, "description_purchase": "source"}],
            "orderpoints": [
                {"id": 1, "product_id": 10, "location_id": 8, "warehouse_id": 1,
                 "company_id": 1, "minimum": "15", "maximum": "19", "multiple": "1", "trigger": "manual"},
                {"id": 2, "product_id": 20, "location_id": 8, "warehouse_id": 1,
                 "company_id": 1, "minimum": "8", "maximum": "12", "multiple": "1", "trigger": "manual"},
            ],
        }

    def test_purchase_positive_and_wrong_object_negative(self):
        target = {"lines": [{"line_id": 1, "product_id": 10,
                             "expected": {"qty": 2, "price": 10.0, "date": "2025-01-01"}}]}
        observed = copy.deepcopy(self.baseline)
        observed["lines"][0]["price"] = "10.00"
        self.assertEqual(evaluate("ELPO-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["lines"][1]["qty"] = "4"
        self.assertIn("unrelated_order_line_changed",
                      evaluate("ELPO-0001", target, self.baseline, observed)["difference_codes"])
        observed = copy.deepcopy(self.baseline)
        observed["attachments"][0]["checksum"] = "tampered"
        self.assertIn("attachments_changed_or_missing",
                      evaluate("ELPO-0001", target, self.baseline, observed)["difference_codes"])

    def test_replenishment_positive_and_wrong_rule_negative(self):
        target = {"rule_id": 1, "expected": {"minimum": 13, "maximum": 21}}
        observed = copy.deepcopy(self.baseline)
        observed["orderpoints"][0]["minimum"] = "13"
        observed["orderpoints"][0]["maximum"] = "21"
        self.assertEqual(evaluate_replenishment("ELRP-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["orderpoints"][1]["minimum"] = "9"
        self.assertIn("unrelated_replenishment_rule_changed",
                      evaluate_replenishment("ELRP-0001", target, self.baseline, observed)["difference_codes"])


if __name__ == "__main__":
    unittest.main()
