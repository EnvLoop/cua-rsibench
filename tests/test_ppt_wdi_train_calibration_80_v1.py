"""Training-analogue shape and blind held-out source gate tests."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools import build_ppt_wdi_train_calibration_80_v1 as cal


class CalibrationPoolTests(unittest.TestCase):
    def test_eighty_tasks_cover_ten_workflows_across_eight_sources(self):
        source = wdi.load()
        codes = sorted(wdi.COUNTRIES)[:8]
        extras = {}
        for iso in codes[5:]:
            extras[iso] = (
                wdi.country_facts(source, iso),
                {"download_date": "2026-09-27", "data_last_updated": "2026-09-01"},
                b"private synthetic ZIP", b"private synthetic snapshot",
                b"private synthetic provenance")
        rows = cal.make_rows(b"x" * 32, codes[:5], extras)
        self.assertEqual(len(rows), 80)
        self.assertEqual(len({row["task_id"] for row in rows}), 80)
        self.assertTrue(all(row["split"] == "train_policy_development" and
                            row["development_source_split"] == "train" and
                            row["official_final_credit"] == 0 and
                            len(row["target_keys"]) == 4 for row in rows))
        for workflow in ppt.WORKFLOWS:
            sample = [row for row in rows if row["workflow"] == workflow]
            self.assertEqual(len(sample), 8)
            self.assertEqual(len({row["source_group"] for row in sample}), 8)
        self.assertEqual(len({row["source_group"] for row in rows
                              if row.get("source_scope") ==
                              "private_wdi_country_csv_reserve_v1"}), 3)

    def test_blind_check_returns_only_counts_never_hidden_id_or_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            heldout = root / "heldout.json"
            queue_path = root / "queue.json"
            plan = {"schema": ppt.SCHEMA,
                    "sets": {"selection": [{"source_group": "BBB",
                                            "task_id": "private-selection-id",
                                            "correct": "private-selection-answer"}],
                             "final_candidate": [{"source_group": "CCC",
                                                  "task_id": "private-final-id",
                                                  "correct": "private-final-answer"}]}}
            heldout.write_bytes(ppt.canonical(plan))
            plan_hash = ppt.sha(heldout.read_bytes())
            queue = {"schema": "envloop-ppt-future-reserve-queue-private-v1",
                     "current_plan_sha256": plan_hash,
                     "ordered_future_country_iso": ["DDD"]}
            queue_path.write_bytes(ppt.canonical(queue))
            with patch.object(cal, "PLAN_SHA", plan_hash), patch.object(
                    cal, "QUEUE_SHA", ppt.sha(queue_path.read_bytes())):
                result = cal.blind_heldout_collision(heldout, queue_path,
                                                     {"AAA", "BBB", "DDD"})
            self.assertEqual(result["heldout_source_collision_count"], 1)
            self.assertEqual(result["future_reserve_collision_count"], 1)
            self.assertTrue(result["any_collision"])
            public = json.dumps(result)
            self.assertNotIn("private-final-id", public)
            self.assertNotIn("private-selection-answer", public)
            self.assertNotIn("BBB", public)


if __name__ == "__main__":
    unittest.main()
