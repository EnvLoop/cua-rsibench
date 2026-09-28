"""Synthetic source-boundary tests; no evaluator country list or gold is loaded."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools import ppt_wdi_calibration_rebase_20260929 as rebase


class CalibrationRebaseTests(unittest.TestCase):
    def test_each_source_registry_category_is_a_fail_closed_collision(self):
        proposed = {f"AA{chr(65+i)}" for i in range(8)}
        categories = ("original_35", "active_v13_train", "active_v13_selection",
                      "active_v13_final", "future_reserve", "historical_final",
                      "new_transfer_pair")
        empty = {name: set() for name in categories}
        self.assertEqual(rebase.overlap_counts(proposed, empty),
                         {name: 0 for name in sorted(categories)})
        for name in categories:
            with self.subTest(name=name):
                source_sets = {key: set(value) for key, value in empty.items()}
                source_sets[name].add("AAA")
                with self.assertRaisesRegex(ValueError, "overlaps_frozen"):
                    rebase.overlap_counts(proposed, source_sets)
        with self.assertRaisesRegex(ValueError, "incomplete_source_overlap"):
            rebase.overlap_counts(proposed, {"original_35": set()})

    def test_fixed_priority_rejects_posthoc_country_swap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ordered = [f"AA{chr(65+i)}" for i in range(10)]
            priority = {"schema": rebase.SOURCE_PRIORITY_SCHEMA,
                        "policy":
                        "fixed_priority_first_eight_complete_csv_outside_frozen_source_unions",
                        "candidate_iso3": ordered}
            priority_path = root / "priority.private.json"
            priority_path.write_bytes(ppt.canonical(priority))
            chosen = ordered[1:9]
            selection = {"schema": rebase.SOURCE_SELECTION_SCHEMA,
                         "selected_iso3": chosen,
                         "rejected_candidates": [{"iso3": ordered[0],
                                                  "reason_type": "ValueError",
                                                  "reason": "missing observation"}],
                         "candidate_priority_sha256": ppt.sha(priority_path.read_bytes()),
                         "required_count": 8}
            selection_path = root / "selection.private.json"
            selection_path.write_bytes(ppt.canonical(selection))
            result = rebase.selection_audit(priority_path, selection_path, set(chosen))
            self.assertEqual(result[2], 1)
            selection["selected_iso3"] = chosen[:-1] + [ordered[9]]
            selection_path.write_bytes(ppt.canonical(selection))
            with self.assertRaisesRegex(ValueError, "does_not_follow_frozen_priority"):
                rebase.selection_audit(priority_path, selection_path,
                                       set(selection["selected_iso3"]))

    def test_new_seed_builds_eighty_unbuilt_specs_without_public_source_leak(self):
        source = wdi.load()
        codes = sorted(wdi.COUNTRIES)[:8]  # Public fixture values only.
        facts = {iso: wdi.country_facts(source, iso) for iso in codes}
        source_rows = [{"iso3": iso,
                        "zip_sha256": ppt.sha((iso + "-zip").encode()),
                        "snapshot_sha256": ppt.sha((iso + "-snapshot").encode()),
                        "provenance_sha256": ppt.sha((iso + "-provenance").encode()),
                        "download_date": rebase.DATE,
                        "data_last_updated": "2026-07-13",
                        "numeric_observation_count": 30} for iso in codes]
        category_names = ("original_35", "active_v13_train",
                          "active_v13_selection", "active_v13_final",
                          "future_reserve", "historical_final", "new_transfer_pair")
        synthetic_anchors = {
            "sets": {name: set() for name in category_names},
            "historical_plan_hashes": [{"revision": f"test-{i}",
                                       "plan_sha256": ppt.sha(str(i).encode())}
                                      for i in range(12)],
            "transfer_source_packages": [{"iso3": "ZZZ"}, {"iso3": "YYY"}],
            "old_public_receipt_sha256": ppt.sha(b"historical-public")}
        with patch.object(rebase, "anchors", return_value=synthetic_anchors), \
             patch.object(rebase, "packages", return_value=(source_rows, facts)), \
             patch.object(rebase, "selection_audit",
                          return_value=(ppt.sha(b"priority"),
                                        ppt.sha(b"selection"), 1)):
            manifest, returned_facts = rebase.source_manifest(
                b"a" * 32, b"b" * 32, *([Path("unused")] * 8))
        plan = rebase.spec_plan(b"a" * 32, manifest, returned_facts)
        public = rebase.public_receipt(manifest, plan)
        self.assertEqual(len(plan["rows"]), 80)
        self.assertEqual(len({row["task_id"] for row in plan["rows"]}), 80)
        self.assertEqual({row["workflow"] for row in plan["rows"]},
                         set(ppt.WORKFLOWS))
        self.assertTrue(all(len(row["target_keys"]) == 4 and
                            row["calibration_role"] ==
                            "nonfinal_withheld_rebase_20260929_source_only"
                            for row in plan["rows"]))
        self.assertEqual(public["new_planned_calibration_specs"], 80)
        self.assertEqual(public["new_decks_built"], 0)
        self.assertFalse(public["historical_80_private_provenance_available"])
        self.assertIsNone(public["historical_80_source_overlap_count"])
        public_text = json.dumps(public)
        self.assertNotIn(plan["rows"][0]["task_id"], public_text)
        self.assertTrue(all(iso not in public_text for iso in codes))

    def test_pinned_manifest_rejects_byte_change_or_false_old_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.private.json"
            names = ("original_35", "active_v13_train",
                     "active_v13_selection", "active_v13_final",
                     "future_reserve", "historical_final", "new_transfer_pair")
            manifest = {"schema": rebase.SCHEMA,
                        "boundary_date": rebase.DATE,
                        "status": "source_checked_spec_plan_only_no_decks",
                        "historical_80_private_provenance_status":
                        "unavailable_not_reconstructed",
                        "historical_80_published_private_manifest_sha256":
                        rebase.OLD_PRIVATE_MANIFEST_SHA,
                        "active_v13_plan_sha256": rebase.PLAN_SHA,
                        "future_reserve_queue_sha256": rebase.QUEUE_SHA,
                        "historical_80_source_overlap_count": None,
                        "historical_plan_hashes": [{} for _ in range(12)],
                        "transfer_source_packages": [{}, {}],
                        "source_overlap_counts": {name: 0 for name in names},
                        "source_families": [{"iso3": f"AA{chr(65+i)}",
                                             "zip_sha256": "a" * 64,
                                             "snapshot_sha256": "b" * 64,
                                             "provenance_sha256": "c" * 64,
                                             "numeric_observation_count": 30}
                                            for i in range(8)],
                        "built_decks": 0, "office_web_gui_admitted": 0,
                        "official_final_admitted": 0}
            path.write_bytes(ppt.canonical(manifest))
            original_sha = ppt.sha(path.read_bytes())
            self.assertEqual(len(rebase.validate_rebased_boundary(path, original_sha)), 8)
            manifest["historical_80_private_provenance_status"] = "reopened"
            path.write_bytes(ppt.canonical(manifest))
            with self.assertRaisesRegex(ValueError, "missing_or_changed"):
                rebase.validate_rebased_boundary(path, ppt.sha(path.read_bytes()))
            with self.assertRaisesRegex(ValueError, "missing_or_changed"):
                rebase.validate_rebased_boundary(path, original_sha)


if __name__ == "__main__":
    unittest.main()
