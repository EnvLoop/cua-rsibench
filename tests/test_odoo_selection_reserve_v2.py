"""V2 must retain three-line reading burden and exclude V1 development data."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_odoo_selection_reserve_v1 import _old_row, _write
from tools import audit_odoo_selection_reserve_v2 as independent
from tools import odoo_selection_reserve_v1 as v1
from tools import odoo_selection_reserve_v2 as v2


class DifficultyMatchedReserveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "task-manifest.json"
        self.correlation = self.root / "correlation.json"
        self.train_world = self.root / "train-world.json"
        self.selection_world = self.root / "selection-world.json"
        self.v1_private = self.root / "work" / "v1-freeze.private.json"
        self.v1_public = self.root / "v1-freeze.public.json"
        self.v1_cohort = self.root / "work" / "v1-cohort"
        self.v2_private = self.root / "work" / "v2-freeze.private.json"
        self.v2_public = self.root / "v2-freeze.public.json"
        self.v2_cohort = self.root / "work" / "v2-cohort"
        task_sets = {"train": [_old_row("train", index) for index in range(20)],
                     "selection": [_old_row("selection", index) for index in range(20)],
                     "official": [_old_row("official", index) for index in range(100)]}
        _write(self.manifest, task_sets)
        _write(self.correlation, {"source_family": "purchase",
                                  "case_identities": task_sets["selection"][:5],
                                  "all_five_live_clicked_under_v6": False})
        for split, path in (("train", self.train_world),
                            ("selection", self.selection_world)):
            _write(path, {"split": split, "vendors": [f"{split} vendor"],
                          "customers": [f"{split} customer"],
                          "products": [{"sku": f"{split} sku"}],
                          "salespeople": [f"{split} salesperson"]})
        with patch.object(v1.secrets, "token_hex", return_value="1a" * 32):
            v1.freeze(manifest_path=self.manifest, correlation_path=self.correlation,
                      train_world_path=self.train_world,
                      selection_world_path=self.selection_world,
                      private_path=self.v1_private, public_path=self.v1_public)
        v1.materialize(manifest_path=self.manifest, correlation_path=self.correlation,
                       train_world_path=self.train_world,
                       selection_world_path=self.selection_world,
                       private_freeze_path=self.v1_private,
                       public_freeze_path=self.v1_public,
                       cohort_dir=self.v1_cohort)

    def _freeze_v2(self) -> None:
        with patch.object(v2.secrets, "token_hex", return_value="2b" * 32):
            v2.freeze(manifest_path=self.manifest, correlation_path=self.correlation,
                      train_world_path=self.train_world,
                      selection_world_path=self.selection_world,
                      prior_v1_cohort_dir=self.v1_cohort,
                      private_path=self.v2_private, public_path=self.v2_public)

    def _materialize_v2(self) -> None:
        v2.materialize(manifest_path=self.manifest, correlation_path=self.correlation,
                       train_world_path=self.train_world,
                       selection_world_path=self.selection_world,
                       prior_v1_cohort_dir=self.v1_cohort,
                       private_freeze_path=self.v2_private,
                       public_freeze_path=self.v2_public,
                       cohort_dir=self.v2_cohort)

    def _audit_v2(self) -> dict:
        return independent.audit(manifest_path=self.manifest,
                                 correlation_path=self.correlation,
                                 train_world_path=self.train_world,
                                 selection_world_path=self.selection_world,
                                 generator_path=Path(v2.__file__),
                                 base_generator_path=Path(v1.__file__),
                                 prior_v1_cohort_dir=self.v1_cohort,
                                 private_freeze_path=self.v2_private,
                                 public_freeze_path=self.v2_public,
                                 cohort_dir=self.v2_cohort)

    def test_v2_three_source_rows_are_required_before_audit_passes(self) -> None:
        self._freeze_v2()
        self.assertFalse(self.v2_cohort.exists())
        self._materialize_v2()
        result = self._audit_v2()
        self.assertEqual(result["source_rows_checked_per_case"], 3)
        self.assertEqual(result["private_source_scalar_fields_checked"], 45)
        self.assertEqual(result["prior_v1_development_identity_source_template_entity_overlap"], 0)
        self.assertEqual(result["offline_positive_controls"], 5)
        self.assertEqual(result["selection_denominator_unchanged"], 20)
        self.assertEqual(result["selection_admissions"], 0)
        v1_cases = json.loads((self.v1_cohort / "cases.private.json").read_text())
        v2_cases = json.loads((self.v2_cohort / "cases.private.json").read_text())
        self.assertFalse({case["id"] for case in v1_cases} & {case["id"] for case in v2_cases})
        self.assertTrue(all("Compare all three authorized source lines" in case["prompt"]
                            for case in v2_cases))
        with self.assertRaises(FileExistsError):
            self._materialize_v2()

    def test_v2_prior_development_drift_fails_closed(self) -> None:
        self._freeze_v2()
        prior_cases = self.v1_cohort / "cases.private.json"
        prior_cases.write_text(prior_cases.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "V2 frozen input drift"):
            self._materialize_v2()


if __name__ == "__main__":
    unittest.main()
