"""Enforce substantive split-template changes and fail-closed final admission."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from native_desktop_factory import (admit, factory, factory_v2,
                                    formula_semantics, source,
                                    target_text_semantics, verify)


DEPENDENCIES = all(importlib.util.find_spec(name) is not None for name in
                   ("openpyxl", "pptx", "docx"))


@unittest.skipUnless(DEPENDENCIES, "Office document builders unavailable")
class DistinctDesktopTemplateTests(unittest.TestCase):
    def test_deterministic_140_and_real_structure_separation(self):
        countries = list(source.COUNTRIES)
        mapping = {"schema": "cua-native-wdi-private-map-v1", "train": countries[:5],
                   "selection": countries[5:10], "final_candidate": countries[10:],
                   "variant_salt": "c" * 64}
        with tempfile.TemporaryDirectory() as temp:
            one, two = Path(temp) / "one", Path(temp) / "two"
            first = factory_v2.generate(one, mapping)
            second = factory_v2.generate(two, mapping)
            self.assertEqual(first, second)
            self.assertEqual(first["counts"], factory.EXPECTED_COUNTS)
            self.assertEqual(len({r["task_id"] for r in first["tasks"]}), 140)
            families = {split: {tuple(r["source_groups"]) for r in first["tasks"] if r["split"] == split}
                        for split in factory.EXPECTED_COUNTS}
            self.assertEqual({key: len(value) for key, value in families.items()},
                             {"train": 5, "selection": 5, "final_candidate": 25})
            for a in families:
                for b in families:
                    if a != b:
                        self.assertFalse(families[a] & families[b])
            templates = {split: {r["template_group"] for r in first["tasks"] if r["split"] == split}
                         for split in factory.EXPECTED_COUNTS}
            self.assertEqual({key: len(value) for key, value in templates.items()},
                             {"train": 4, "selection": 4, "final_candidate": 4})
            self.assertFalse(templates["train"] & templates["selection"])
            self.assertFalse(templates["train"] & templates["final_candidate"])
            self.assertFalse(templates["selection"] & templates["final_candidate"])

            shapes = {}
            for split in factory.EXPECTED_COUNTS:
                iso = mapping[split][0]
                task_id = (f"wdi-native-{iso.lower()}-" if split == "train" else
                           f"wdi-native-v2-{iso.lower()}-")
                for workflow, ext in (("calc-growth", ".xlsx"),
                                      ("impress-deck", ".pptx"),
                                      ("writer-brief", ".docx")):
                    path = one / split / (task_id + workflow) / (task_id + workflow + ext)
                    raw = path.read_bytes()
                    if ext == ".xlsx":
                        shape = len(verify.xlsx_cells(raw))
                    elif ext == ".pptx":
                        shape = len(verify.pptx_slide_shapes(raw))
                    else:
                        document = verify.docx_content(raw)
                        shape = (len(document["tables"]), len(document["tables"][0]))
                    shapes[(split, workflow)] = shape
            self.assertEqual([shapes[(s, "calc-growth")] for s in factory.EXPECTED_COUNTS], [2, 3, 4])
            self.assertEqual([shapes[(s, "impress-deck")] for s in factory.EXPECTED_COUNTS], [4, 5, 7])
            self.assertEqual([shapes[(s, "writer-brief")][0] for s in factory.EXPECTED_COUNTS], [1, 1, 2])
            self.assertEqual([shapes[(s, "writer-brief")][1] for s in factory.EXPECTED_COUNTS], [7, 4, 7])

            for row in first["tasks"]:
                if row["split"] != "final_candidate":
                    continue
                oracle = json.loads((one / row["split"] / row["task_id"] / "oracle.json").read_bytes())
                self.assertEqual(len(oracle["targets"]), 3)
                for wrong, expected in oracle["targets"].items():
                    if isinstance(expected, str):
                        self.assertNotEqual(wrong, expected)
                        self.assertTrue(target_text_semantics.semantically_correct(expected, expected))
                        self.assertFalse(target_text_semantics.semantically_correct(wrong, expected))
                if row["workflow"].startswith("calc-"):
                    directory = one / row["split"] / row["task_id"]
                    cells = verify.xlsx_cells(next(directory.glob("*.xlsx")).read_bytes())
                    for address, rule in oracle["targets"].items():
                        sheet, cell = address.split("!", 1)
                        baseline_formula = "=" + cells[sheet][cell]["formula"]
                        self.assertTrue(formula_semantics.semantically_equivalent(
                            rule["formula"], rule["formula"], cells,
                            private_salt="test-only-counterfactual-salt"))
                        self.assertFalse(formula_semantics.semantically_equivalent(
                            baseline_formula, rule["formula"], cells,
                            private_salt="test-only-counterfactual-salt"))
            gate = admit.audit(one, Path(temp) / "missing-gui")
            self.assertEqual((gate["qualified_final_count"], gate["missing_receipt_count"],
                              gate["status"]), (0, 100, "incomplete"))
            partial = Path(temp) / "partial-gui"
            (partial / next(r["task_id"] for r in first["tasks"] if r["split"] == "final_candidate") / "positive").mkdir(parents=True)
            partial_gate = admit.audit(one, partial)
            self.assertEqual((partial_gate["missing_receipt_count"],
                              partial_gate["invalid_receipt_count"]), (100, 0))


if __name__ == "__main__":
    unittest.main()
