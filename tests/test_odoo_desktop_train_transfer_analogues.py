"""Source-bound offline controls for the Odoo and native Desktop train pools."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "enterprise_fallback" / "odoo18"))

from hidden_factory import hidden_candidate_world  # noqa: E402
from partition_factory import candidate_world  # noqa: E402
from train_transfer_analogues import audit as odoo_audit, build as odoo_build  # noqa: E402
from train_transfer_shadow_audit import audit as shadow_audit  # noqa: E402
from native_desktop_factory import factory as base  # noqa: E402
from native_desktop_factory import factory_v2  # noqa: E402
from native_desktop_factory.source import COUNTRIES, EXPECTED_SHA256  # noqa: E402
from native_desktop_factory.train_transfer_analogues import (  # noqa: E402
    audit as desktop_audit, stage as desktop_stage,
)


class OdooTrainTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {
            "train": candidate_world("original-train-" + "a" * 40, "train"),
            "selection": candidate_world("original-train-" + "a" * 40, "selection"),
            "official_hidden": hidden_candidate_world("original-hidden-" + "b" * 40),
        }
        cls.seed = "new-supplemental-training-" + "c" * 40

    def test_two_per_workflow_disjoint_and_shadow_scorer(self):
        staged = odoo_build(self.seed, self.original)
        public = odoo_audit(staged, self.original)
        self.assertEqual(public["case_count"], 8)
        self.assertEqual(public["per_workflow"],
                         {"crm": 2, "inventory": 2, "purchase": 2, "sales": 2})
        self.assertTrue(all(n == 0 for split in public["cross_split_overlap_counts"].values()
                            for n in split.values()))
        shadow = shadow_audit(staged)
        self.assertEqual(shadow["counts"], {"unsolved_baseline": 8,
                         "positive_pass": 8, "near_miss_rejected": 8,
                         "unrelated_change_rejected": 8})
        self.assertEqual(shadow["gui_qualified_count"], 0)

    def test_source_or_gold_tamper_fails_closed(self):
        staged = odoo_build(self.seed, self.original)
        altered = deepcopy(staged)
        altered["world"]["cases"]["inventory"][0]["expected"]["minimum"] += 1
        with self.assertRaises(ValueError):
            odoo_audit(altered, self.original)
        altered = deepcopy(staged)
        first = altered["world"]["cases"]["purchase"][0]["id"]
        altered["source_assets_hex"][first] = "00"
        with self.assertRaises(ValueError):
            odoo_audit(altered, self.original)

    def test_reused_training_entity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlaps"):
            odoo_build("original-train-" + "a" * 40, self.original)


class DesktopTrainTransferTests(unittest.TestCase):
    @staticmethod
    def _boundary(root: Path) -> tuple[Path, Path]:
        mapping = {"schema": "cua-native-wdi-private-map-v1",
                   "train": list(COUNTRIES[:5]),
                   "selection": list(COUNTRIES[5:10]),
                   "final_candidate": list(COUNTRIES[10:]),
                   "variant_salt": "ab" * 32}
        map_path = root / "private-map.json"
        map_path.write_bytes(base.json_bytes(mapping))
        rows = []
        for split in ("train", "selection", "final_candidate"):
            for iso in mapping[split]:
                for workflow in base.WORKFLOWS:
                    rows.append({"task_id": f"old-{split}-{iso}-{workflow}",
                                 "split": split, "workflow": workflow,
                                 "source_groups": [f"wdi-country:{iso}"],
                                 "template_group": factory_v2.TEMPLATES[split][workflow]})
        inventory = {"schema": "cua-native-wdi-candidate-inventory-v1",
                     "design_revision": "v2-distinct-structures",
                     "source_sha256": EXPECTED_SHA256,
                     "private_map_sha256": base.digest(base.json_bytes(mapping)),
                     "counts": base.EXPECTED_COUNTS, "tasks": rows}
        candidate = root / "original-candidates"
        candidate.mkdir()
        (candidate / "candidate-inventory.json").write_bytes(base.json_bytes(inventory))
        return map_path, candidate

    def test_saved_ooxml_controls_and_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mapping, candidate = self._boundary(root)
            out = root / "supplemental"
            staged = desktop_stage(mapping, candidate, out)
            self.assertEqual(len(staged["rows"]), 8)
            public = desktop_audit(mapping, candidate, out)
            self.assertEqual(public["positive_saved_artifact_pass_count"], 8)
            self.assertEqual(public["near_miss_rejected_count"], 8)
            self.assertEqual(public["unrelated_change_rejected_count"], 8)
            self.assertEqual(public["train_source_country_count"], 2)
            self.assertEqual(public["gui_qualified_count"], 0)

    def test_mutated_saved_control_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mapping, candidate = self._boundary(root)
            out = root / "supplemental"
            staged = desktop_stage(mapping, candidate, out)
            row = staged["rows"][0]
            path = out / row["task_id"] / "positive.xlsx"
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "offline saved-artifact controls changed"):
                desktop_audit(mapping, candidate, out)

    def test_partition_overlap_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mapping_path, candidate = self._boundary(root)
            mapping = json.loads(mapping_path.read_bytes())
            mapping["selection"][0] = mapping["train"][0]
            mapping_path.write_bytes(base.json_bytes(mapping))
            with self.assertRaises(ValueError):
                desktop_stage(mapping_path, candidate, root / "supplemental")


if __name__ == "__main__":
    unittest.main()
