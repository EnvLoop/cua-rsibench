"""Offline no-replay and whole-family contracts for the GitLab v4 plan."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import v066_infra_recovery_v4 as v4


WORKFLOWS = tuple(sorted(v4.lane.CASES))


def original_roster() -> list[dict]:
    return [
        {"task_id": f"original-{index:03d}",
         "package_sha256": f"{index + 1:064x}",
         "source_family_sha256": f"{index // 5 + 1:064x}",
         "template_group": WORKFLOWS[index % 5]}
        for index in range(100)
    ]


def first_reserve() -> dict:
    return {
        "ordinal": 1,
        "tasks": [
            {"task_id": f"reserve-{index:03d}",
             "template_group": workflow,
             "source_family": "new-disjoint-family",
             "partition": "final_candidate_unsealed",
             "prompt": "private task text"}
            for index, workflow in enumerate(WORKFLOWS)
        ],
    }


class RecoveryV4Tests(unittest.TestCase):
    def test_retirement_replaces_whole_family_with_first_fifo_family(self):
        old = original_roster()
        result = v4.replacement_roster(old, first_reserve())
        candidate = result["candidate_roster"]
        self.assertEqual(len(candidate), 100)
        self.assertEqual(result["retired_family_original_indices"],
                         [10, 11, 12, 13, 14])
        self.assertEqual(result["retired_completed_controls"], 3)
        self.assertEqual(result["retained_historical_passing_controls"], 10)
        self.assertEqual([x["task_id"] for x in candidate[:10]],
                         [x["task_id"] for x in old[:10]])
        self.assertEqual({x["task_id"] for x in candidate[10:15]},
                         {x["task_id"] for x in first_reserve()["tasks"]})
        self.assertEqual([x["task_id"] for x in candidate[15:]],
                         [x["task_id"] for x in old[15:]])
        self.assertFalse({x["task_id"] for x in old[10:15]} &
                         {x["task_id"] for x in candidate})
        self.assertEqual(result["diagnostic_task_id"], old[15]["task_id"])
        self.assertNotIn(old[15]["task_id"],
                         {x["task_id"] for x in first_reserve()["tasks"]})

    def test_single_task_swap_is_rejected(self):
        reserve = first_reserve()
        reserve["tasks"].pop()
        with self.assertRaisesRegex(
                v4.RecoveryPlanError,
                "first_fifo_reserve_family_missing"):
            v4.replacement_roster(original_roster(), reserve)

    def test_reserve_id_overlap_is_rejected(self):
        reserve = first_reserve()
        reserve["tasks"][0]["task_id"] = original_roster()[13]["task_id"]
        with self.assertRaisesRegex(
                v4.RecoveryPlanError,
                "reserve_source_or_task_identity_overlaps_original_roster"):
            v4.replacement_roster(original_roster(), reserve)

    def test_next_original_id_in_failed_family_is_rejected(self):
        old = original_roster()
        old[15]["source_family_sha256"] = old[13]["source_family_sha256"]
        with self.assertRaisesRegex(
                v4.RecoveryPlanError,
                "failed_correlated_family_or_distinct_diagnostic_changed"):
            v4.replacement_roster(old, first_reserve())

    def test_public_plan_never_exposes_private_identity_or_prompt(self):
        roster = v4.replacement_roster(original_roster(), first_reserve())
        private = {
            "epoch_sha256": "a" * 64,
            "source_bundle_sha256": "b" * 64,
            "terminal_public_sha256": "c" * 64,
            "fifo_public_commitment_sha256": "d" * 64,
            "fifo_queue_sha256": "e" * 64,
            "candidate_roster_sha256": "f" * 64,
            **roster,
        }
        public = v4.public_plan_payload(private, "1" * 64)
        encoded = json.dumps(public)
        self.assertNotIn("original-013", encoded)
        self.assertNotIn("reserve-000", encoded)
        self.assertNotIn("private task text", encoded)
        self.assertFalse(public["one_id_gui_dispatch_authorized"])
        self.assertFalse(public["same_identity_replay_authorized"])
        self.assertTrue(
            public["diagnostic_result_not_counted_as_final_roster_control"])

    def test_offline_freeze_writes_only_plan_files(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_dir = root / "private"
            public_plan = root / "docs/evidence/public.json"
            public_plan.parent.mkdir(parents=True)
            private = {
                "schema": v4.PRIVATE_SCHEMA,
                "status": "prospective_new_id_epoch_plan_only_no_dispatch",
                "epoch_sha256": "a" * 64,
                "source_bundle_sha256": "b" * 64,
                "terminal_public_sha256": "c" * 64,
                "fifo_public_commitment_sha256": "d" * 64,
                "fifo_queue_sha256": "e" * 64,
                "candidate_roster_sha256": "f" * 64,
                "one_id_gui_dispatch_authorized": False,
            }
            with patch.object(v4, "ROOT", root), \
                 patch.object(v4.one, "ROOT", root), \
                 patch.object(v4, "PRIVATE_DIR", private_dir), \
                 patch.object(v4, "PRIVATE_PLAN", private_dir / "plan.json"), \
                 patch.object(v4, "PUBLIC_PLAN", public_plan), \
                 patch.object(v4, "build", return_value=(private, {})), \
                 patch.object(v4.terminal, "audit") as prior_audit, \
                 patch.object(v4.reserve, "ordered_queue") as queue_build:
                result = v4.freeze(root / "ratification.private.json")
                self.assertFalse(result["one_id_gui_dispatch_authorized"])
                self.assertTrue((private_dir / "plan.json").is_file())
                self.assertTrue(public_plan.is_file())
                self.assertEqual((private_dir / "plan.json").stat().st_mode & 0o077,
                                 0)
                prior_audit.assert_not_called()
                queue_build.assert_not_called()

    def test_saved_plan_drift_fails_read_only_audit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_dir = root / "private"
            private_dir.mkdir(mode=0o700)
            private_plan = private_dir / "plan.json"
            public_plan = root / "public.json"
            v4.one.write_new(private_plan, {"schema": v4.PRIVATE_SCHEMA,
                                            "epoch_sha256": "a" * 64})
            public_plan.write_text("{}")
            with patch.object(v4.one, "PRIVATE_ROOT", root), \
                 patch.object(v4, "PRIVATE_PLAN", private_plan), \
                 patch.object(v4, "PUBLIC_PLAN", public_plan), \
                 patch.object(v4, "build", return_value=(
                     {"schema": v4.PRIVATE_SCHEMA,
                      "epoch_sha256": "b" * 64}, {})):
                with self.assertRaisesRegex(
                        v4.RecoveryPlanError,
                        "new_epoch_source_or_candidate_roster_changed"):
                    v4.audit(root / "ratification.private.json")


if __name__ == "__main__":
    unittest.main()
