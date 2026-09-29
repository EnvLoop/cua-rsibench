"""Offline, outcome-independent reserve commitment and verifier controls."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import audit_odoo_selection_reserve_v1 as independent
from tools import odoo_selection_reserve_v1 as reserve


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _old_row(split: str, index: int) -> dict:
    family = ("ELPO", "ELRP", "ELSQ", "ELCRM")[index // (5 if split != "official" else 25)]
    ordinal = 1 + index % (5 if split != "official" else 25)
    prefix = {"train": "TRN", "selection": "SEL", "official": "HID"}[split]
    return {"task_id": f"{family}-{prefix}-{ordinal:04d}",
            "package_sha256": f"old-package-{split}-{index}",
            "source_groups": [f"old-source-{split}-{index}"],
            "template_group": f"old-template-{split}-{index // 5}",
            "instance_group": f"old-instance-{split}-{index}"}


class ReserveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "work" / "reserve"
        self.manifest = self.root / "task-manifest.json"
        self.correlation = self.root / "correlation.json"
        self.train_world = self.root / "train-world.json"
        self.selection_world = self.root / "selection-world.json"
        self.private_freeze = self.private / "freeze.private.json"
        self.public_freeze = self.root / "freeze.public.json"
        self.cohort = self.private / "cohort"
        task_sets = {"train": [_old_row("train", index) for index in range(20)],
                     "selection": [_old_row("selection", index) for index in range(20)],
                     "official": [_old_row("official", index) for index in range(100)]}
        retired = task_sets["selection"][:5]
        self.ids = [row["task_id"] for row in retired]
        _write(self.manifest, task_sets)
        _write(self.correlation, {"case_identities": retired, "source_family": "purchase",
                                  "all_five_live_clicked_under_v6": False})
        _write(self.train_world, {"split": "train", "vendors": ["TRN Supplier"],
                                  "customers": ["TRN Customer"],
                                  "products": [{"sku": "EL-TRN-001"}],
                                  "salespeople": ["TRN Sales"]})
        _write(self.selection_world, {"split": "selection", "vendors": ["SEL Supplier"],
                                      "customers": ["SEL Customer"],
                                      "products": [{"sku": "EL-SEL-001"}],
                                      "salespeople": ["SEL Sales"]})

    def _freeze(self) -> dict:
        with patch.object(reserve.secrets, "token_hex", return_value="7a" * 32):
            return reserve.freeze(manifest_path=self.manifest,
                                  correlation_path=self.correlation,
                                  train_world_path=self.train_world,
                                  selection_world_path=self.selection_world,
                                  private_path=self.private_freeze,
                                  public_path=self.public_freeze)

    def _materialize(self) -> dict:
        return reserve.materialize(manifest_path=self.manifest,
                                   correlation_path=self.correlation,
                                   train_world_path=self.train_world,
                                   selection_world_path=self.selection_world,
                                   private_freeze_path=self.private_freeze,
                                   public_freeze_path=self.public_freeze,
                                   cohort_dir=self.cohort)

    def test_prospective_freeze_precedes_exactly_five_offline_packages(self) -> None:
        freeze = self._freeze()
        self.assertFalse(self.cohort.exists())
        self.assertEqual(freeze["rule"]["selection_denominator"], 20)
        self.assertFalse(freeze["rule"]["redraw_after_failure"])
        receipt = self._materialize()
        self.assertEqual(receipt["cohort_count"], 5)
        cases = json.loads((self.cohort / "cases.private.json").read_text())
        self.assertEqual(len({case["id"] for case in cases}), 5)
        self.assertEqual(len({case["vendor"] for case in cases}), 5)
        self.assertEqual(len({case["source_kind"] for case in cases}), 5)
        self.assertEqual(len({case["template_group"] for case in cases}), 5)
        self.assertTrue(all(case["partition"] == "selection" for case in cases))
        self.assertTrue(all(case["id"] not in self.ids for case in cases))
        inventory = json.loads((self.cohort / "prospective-inventory.private.json").read_text())
        self.assertEqual(len(inventory["retained_selection"]), 15)
        self.assertEqual(len(inventory["new_selection"]), 5)
        self.assertFalse(inventory["campaign_dispatch_authorized"])
        with self.assertRaises(FileExistsError):
            self._materialize()

    def test_independent_audit_and_negative_controls(self) -> None:
        self._freeze()
        self._materialize()
        report = independent.audit(manifest_path=self.manifest,
                                   correlation_path=self.correlation,
                                   train_world_path=self.train_world,
                                   selection_world_path=self.selection_world,
                                   generator_path=Path(reserve.__file__),
                                   private_freeze_path=self.private_freeze,
                                   public_freeze_path=self.public_freeze,
                                   cohort_dir=self.cohort)
        self.assertEqual(report["source_documents_checked"], 5)
        self.assertEqual(report["offline_positive_controls"], 5)
        self.assertEqual(report["offline_wrong_object_negative_controls"], 5)
        self.assertEqual(report["offline_reset_controls"], 5)
        self.assertEqual(report["native_gui_controls"], 0)
        self.assertEqual(report["selection_admissions"], 0)
        public_text = json.dumps(report)
        self.assertNotIn("7a" * 32, public_text)
        self.assertTrue(all(task_id not in public_text for task_id in self.ids))
        cases = json.loads((self.cohort / "cases.private.json").read_text())
        baseline = json.loads((self.cohort / "baseline-state.private.json").read_text())
        case = cases[0]
        positive = copy.deepcopy(baseline)
        idx = case["target_line_index"]
        positive["orders"][case["id"]]["lines"][idx]["qty"] = (
            case["lines"][idx]["expected"]["qty"])
        positive["orders"][case["id"]]["lines"][idx]["price"] = (
            case["lines"][idx]["expected"]["price"])
        self.assertTrue(all(independent.saved_state_score(case, baseline, positive).values()))
        wrong_source = copy.deepcopy(positive)
        wrong_source["orders"][case["id"]]["attachment_sha256"] = "tampered"
        self.assertFalse(independent.saved_state_score(case, baseline, wrong_source)["source_exact"])
        wrong_date = copy.deepcopy(positive)
        wrong_date["orders"][case["id"]]["lines"][idx]["date"] = "2030-01-01"
        self.assertFalse(independent.saved_state_score(case, baseline, wrong_date)["protected_exact"])

    def test_frozen_source_and_input_drift_fail_closed(self) -> None:
        self._freeze()
        self.selection_world.write_text(self.selection_world.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "Frozen input drift"):
            self._materialize()
        self.selection_world.write_text(self.selection_world.read_text()[:-1])
        public = json.loads(self.public_freeze.read_text())
        public["generator_sha256"] = "0" * 64
        self.public_freeze.write_text(json.dumps(public))
        with self.assertRaisesRegex(ValueError, "Frozen generator source drift"):
            self._materialize()


if __name__ == "__main__":
    unittest.main()
