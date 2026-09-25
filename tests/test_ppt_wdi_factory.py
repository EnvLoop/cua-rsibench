"""Meaningful source, split, and independent OOXML control checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from ppt_wdi_factory import plan, qa, verify
from ppt_wdi_factory.build import DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON, DEFAULT_SKILL, prepare_builder, run


def finalized_package(private: Path, row: dict) -> Path:
    package = private / "packages" / "final_candidate" / row["task_id"]
    package.mkdir(parents=True)
    spec = package / "task.private.json"
    spec.write_bytes(plan.canonical(row))
    builder = prepare_builder(private, DEFAULT_MODULES)
    environment = {**os.environ, "PRESENTATIONS_SKILL_DIR": str(DEFAULT_SKILL),
                   "RUNTIME_PYTHON": str(DEFAULT_PYTHON), "RUNTIME_NODE": str(DEFAULT_NODE),
                   "RUNTIME_NODE_MODULES": str(DEFAULT_MODULES)}
    subprocess.run([str(DEFAULT_NODE), str(builder), str(spec), str(package / "draft.pptx")],
                   check=True, capture_output=True, env=environment)
    subprocess.run([str(DEFAULT_NODE), str(Path("ppt_wdi_factory/finalize_deck.mjs").resolve()),
                    str(package / "draft.pptx"), str(package / "source.pptx")],
                   check=True, capture_output=True, env=environment)
    return package


class PptWdiFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = plan.build(bytes.fromhex("f0" * 32))

    def test_140_country_disjoint_candidates_with_distinct_causal_workflows(self):
        sets = self.candidates["sets"]
        self.assertEqual({key: len(rows) for key, rows in sets.items()}, plan.COUNTS)
        countries = {key: {r["source_group"] for r in rows} for key, rows in sets.items()}
        self.assertEqual({key: len(value) for key, value in countries.items()},
                         {"train": 5, "selection": 5, "final_candidate": 25})
        self.assertFalse(countries["train"] & countries["selection"])
        self.assertFalse(countries["train"] & countries["final_candidate"])
        self.assertFalse(countries["selection"] & countries["final_candidate"])
        final = sets["final_candidate"]
        self.assertTrue(all(r["target_keys"] == ["summary", "ledger", "interpretation"]
                            for r in sets["selection"]))
        self.assertEqual({r["workflow"] for r in final}, set(plan.WORKFLOWS))
        self.assertEqual({workflow: sum(r["workflow"] == workflow for r in final)
                          for workflow in plan.WORKFLOWS}, {workflow: 10 for workflow in plan.WORKFLOWS})
        self.assertEqual(len({r["task_id"] for r in final}), 100)
        self.assertTrue(all(r["target_keys"] == verify.FINAL_TARGETS.get(
            r["workflow"], verify.DEFAULT_FINAL_TARGETS) for r in final))
        self.assertTrue(all(r["calculation"]["value"] != r["calculation"]["wrong_value"]
                            for r in final))
        self.assertTrue(all(r["calculation"]["formula"] != r["calculation"]["wrong_formula"]
                            for r in final))

    def test_public_receipt_has_no_gold_or_country_map(self):
        receipt = plan.public_receipt(self.candidates, "0" * 64)
        data = json.dumps(receipt)
        self.assertEqual(receipt["admission"]["official_final_tasks"], 0)
        self.assertNotIn("correct", data)
        self.assertNotIn("actor_task", data)
        for country in plan.COUNTRIES:
            self.assertNotIn(f'"{country}"', data)

    def test_existing_wdi_partition_can_be_shared_across_cells(self):
        seed = bytes.fromhex("f0" * 32)
        original = plan.source_split(seed)
        aligned = {"schema": "cua-native-wdi-private-map-v1", **original}
        rerun = plan.build(bytes.fromhex("e1" * 32), aligned)
        for split in plan.COUNTS:
            self.assertEqual({r["source_group"] for r in rerun["sets"][split]},
                             set(original[split]))
        self.assertEqual(rerun["country_partition_alignment"],
                         "shared_wdi_desktop_private_partition")

    @unittest.skipUnless(DEFAULT_NODE.is_file() and DEFAULT_MODULES.is_dir(),
                         "bundled presentation runtime is unavailable")
    def test_positive_partial_collateral_and_chart_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            (private / "candidate-plan.private.json").write_bytes(plan.canonical(self.candidates))
            run(private, DEFAULT_NODE, DEFAULT_MODULES, limit=1)
            row = self.candidates["sets"]["train"][0]
            package = private / "packages" / "train" / row["task_id"]
            with ZipFile(package / "source.pptx") as archive:
                self.assertEqual(sum(name.endswith(".xlsx") for name in archive.namelist()), 1)
            self.assertEqual(qa.audit(private, limit=1)["chart_workbook_contract_pass"], 1)
            report = verify.calibrate(package)
            self.assertTrue(report["offline_controls_pass"])
            receipt = json.loads((package / "calibration.private.json").read_text())
            self.assertEqual(receipt["checks"]["positive"]["score"], 1)
            self.assertEqual(receipt["checks"]["near_miss"]["score"], 0)
            self.assertFalse(receipt["checks"]["collateral"]["preservation_pass"])
            self.assertFalse(receipt["checks"]["wrong_chart"]["preservation_pass"])

    @unittest.skipUnless(DEFAULT_NODE.is_file() and DEFAULT_MODULES.is_dir(),
                         "bundled presentation runtime is unavailable")
    def test_final_four_dependent_targets_and_near_miss(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            row = self.candidates["sets"]["final_candidate"][0]
            package = finalized_package(private, row)
            self.assertTrue(verify.calibrate(package)["offline_controls_pass"])
            receipt = json.loads((package / "calibration.private.json").read_text())
            self.assertEqual(len(receipt["checks"]["positive"]["per_target"]), 4)
            near = receipt["checks"]["near_miss"]
            self.assertEqual(sum(x["correct"] for x in near["per_target"].values()), 1)
            self.assertTrue(near["preservation_pass"])
            source = package / "source.pptx"
            destroyed = package / "deleted-target.pptx"
            with ZipFile(source) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            root = ET.fromstring(members["ppt/slides/slide1.xml"])
            names = [node for node in root.iter(verify.P + "cNvPr")
                     if node.get("name") == "target__summary"]
            self.assertEqual(len(names), 1)
            names[0].set("name", "deleted-target")
            members["ppt/slides/slide1.xml"] = ET.tostring(root)
            with ZipFile(destroyed, "w", compression=ZIP_DEFLATED) as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            oracle = json.loads((package / "oracle.private.json").read_text())
            result = verify.verify(source, destroyed, oracle)
            self.assertEqual(result["status"], "scored")
            self.assertEqual(result["score"], 0)
            self.assertFalse(result["preservation_pass"])

    @unittest.skipUnless(DEFAULT_NODE.is_file() and DEFAULT_MODULES.is_dir(),
                         "bundled presentation runtime is unavailable")
    def test_provenance_and_chart_legend_workflows(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            for workflow in ("source_year_reconciliation", "chart_series_relabel"):
                row = next(r for r in self.candidates["sets"]["final_candidate"]
                           if r["workflow"] == workflow)
                package = finalized_package(private, row)
                self.assertTrue(verify.calibrate(package)["offline_controls_pass"])
                receipt = json.loads((package / "calibration.private.json").read_text())
                self.assertEqual(len(receipt["checks"]["positive"]["per_target"]), 4)
                if workflow == "source_year_reconciliation":
                    self.assertIn("attribution", row["target_keys"])
                else:
                    self.assertEqual(receipt["checks"]["legend_desync"]["score"], 0)
                    self.assertTrue(receipt["checks"]["legend_desync"]["preservation_pass"])


if __name__ == "__main__":
    unittest.main()
