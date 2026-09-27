"""Prospective GitLab recovery must not select replacements from outcomes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gitlab_world import factory, pre_result_recovery as recovery, sweep


SEED = "private-recovery-fixture-seed-2026-09-28"
ORIGINAL = factory.build_world(SEED)
RESERVE = factory.reserve_replacement(SEED)
WORLD = {**ORIGINAL, "reserve_projects": [RESERVE["project"]],
         "reserve_tasks": RESERVE["tasks"]}
EXPOSED = next(row for row in ORIGINAL["tasks"]
               if row["partition"] == "final_candidate_unsealed")
EXCLUDED = {row["task_id"] for row in ORIGINAL["tasks"]
            if row["source_family"] == EXPOSED["source_family"]}
ACTIVE = [row for row in WORLD["tasks"] + WORLD["reserve_tasks"]
          if row["partition"] == "final_candidate_unsealed"
          and row["task_id"] not in EXCLUDED]


def synthetic_catalog():
    rows = factory.source_excerpt()["records"] + json.loads(
        factory.RESERVE_EXCERPT.read_text())["records"]
    out = copy.deepcopy(rows)
    for number in range(1, 41):
        item = copy.deepcopy(rows[number])
        item["cveID"] = f"CVE-2026-{90000 + number}"
        item["vendorProject"] = f"unused-test-vendor-{number}"
        out.append(item)
    return out


def complete_first_attempt_index(failed: dict[str, tuple[str, list[float] | None]]):
    items = {}
    ledger = []
    for row in ACTIVE:
        task_id = row["task_id"]
        if task_id in failed:
            status, scores = failed[task_id]
            digest = factory.sha256("ledger:" + task_id)
            item = {"status": status, "scores": scores,
                    "source_family_sha256": factory.sha256(row["source_family"]),
                    "failure_ledger_entry_sha256": digest}
            ledger.append({"task_id": task_id, "seq": len(ledger) + 1,
                           "status": status, "scores": scores, "attempt_number": 1,
                           "source_family_sha256": item["source_family_sha256"],
                           "entry_sha256": digest})
        else:
            item = {"status": recovery.PASS_STATUS,
                    "scores": [1.0, 0.0, 1.0], "cold_resets": 3,
                    "source_family_sha256": factory.sha256(row["source_family"])}
        items[task_id] = {**item, "attempts": [item.copy()]}
    return {"schema": "envloop-gitlab-development-sweep-v1", "items": items}, ledger


class GitLabProspectiveRecoveryTests(unittest.TestCase):
    def test_queue_is_ordered_disjoint_and_public_commitment_contains_no_gold(self):
        first = recovery.ordered_queue(SEED, WORLD, synthetic_catalog())
        second = recovery.ordered_queue(SEED, WORLD, list(reversed(synthetic_catalog())))
        self.assertEqual(first, second)
        self.assertEqual(len(first["ordered_families"]), 5)
        self.assertEqual(sum(len(row["tasks"]) for row in first["ordered_families"]), 25)
        source_cves = {r["cveID"] for project in WORLD["projects"] + WORLD["reserve_projects"]
                       for r in project["advisories"]}
        chosen = {r["cveID"] for row in first["ordered_families"]
                  for r in row["project"]["advisories"]}
        self.assertEqual(len(chosen), 20)
        self.assertFalse(chosen & source_cves)
        public = recovery.public_commitment(first)
        serialized = json.dumps(public)
        for row in first["ordered_families"]:
            self.assertNotIn(row["project"]["full_path"], serialized)
            self.assertNotIn(row["tasks"][0]["task_id"], serialized)
            self.assertNotIn(row["project"]["advisories"][0]["cveID"], serialized)
        self.assertEqual(public["official_final_admitted"], 0)

    def test_private_queue_is_exclusive_mode_0600_and_drift_rejected(self):
        queue = recovery.ordered_queue(SEED, WORLD, synthetic_catalog())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private" / "queue.json"
            first = recovery.freeze_private_queue(queue, path)
            self.assertEqual(first, recovery.freeze_private_queue(queue, path))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            changed = copy.deepcopy(queue)
            changed["queue_sha256"] = "0" * 64
            with self.assertRaises((RuntimeError, ValueError)):
                recovery.freeze_private_queue(changed, path)

    def test_catalog_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text('{"count": 0, "vulnerabilities": []}')
            with self.assertRaises(ValueError):
                recovery.load_catalog(path)

    def test_completed_first_denominator_classifies_scored_miss_as_deterministic(self):
        deterministic = next(row for row in ACTIVE
                             if row["template_group"] == "release_milestone_coordination")
        infra = next(row for row in ACTIVE
                     if row["template_group"] == "approved_merge_request_merge")
        index, ledger = complete_first_attempt_index({
            deterministic["task_id"]: ("development_gui_trio_failed", [0.0, 0.0, 1.0]),
            infra["task_id"]: ("driver_or_environment_failed", None),
        })
        no_fix = recovery.first_attempt_resolution(
            WORLD, index, ledger, excluded_task_ids=EXCLUDED, generic_fix_evidence={})
        self.assertEqual(no_fix["original_first_attempt_failures"], 2)
        self.assertEqual(no_fix["original_first_attempt_passes"], 98)
        self.assertEqual(no_fix["immediate_whole_family_retirement_task_ids"],
                         [deterministic["task_id"]])
        self.assertEqual(len(no_fix["eligible_one_time_requalifications"]), 1)
        with_fix = recovery.first_attempt_resolution(
            WORLD, index, ledger, excluded_task_ids=EXCLUDED,
            generic_fix_evidence={deterministic["template_group"]: "a" * 64})
        self.assertEqual(len(with_fix["eligible_one_time_requalifications"]), 2)
        self.assertEqual(with_fix["immediate_whole_family_retirement_task_ids"], [])
        self.assertNotIn(deterministic["task_id"],
                         json.dumps(recovery.public_resolution(with_fix)))

    def test_incomplete_or_unreconciled_first_denominator_is_rejected(self):
        index, ledger = complete_first_attempt_index({})
        one_id = next(iter(index["items"]))
        del index["items"][one_id]
        with self.assertRaises(ValueError):
            recovery.first_attempt_resolution(
                WORLD, index, ledger, excluded_task_ids=EXCLUDED, generic_fix_evidence={})
        index, ledger = complete_first_attempt_index({
            one_id: ("development_gui_trio_failed", [1.0, 0.0, 0.0])})
        with self.assertRaises(ValueError):
            recovery.first_attempt_resolution(
                WORLD, index, [], excluded_task_ids=EXCLUDED, generic_fix_evidence={})
        index["items"][one_id]["attempts"].append({"status": "development_gui_trio_failed"})
        with self.assertRaises(ValueError):
            recovery.first_attempt_resolution(
                WORLD, index, ledger, excluded_task_ids=EXCLUDED, generic_fix_evidence={})

    def test_one_time_requalification_then_fifo_whole_family_replacement(self):
        deterministic = next(row for row in ACTIVE
                             if row["template_group"] == "release_milestone_coordination")
        infra = next(row for row in ACTIVE
                     if row["template_group"] == "approved_merge_request_merge"
                     and row["source_family"] != deterministic["source_family"])
        index, ledger = complete_first_attempt_index({
            deterministic["task_id"]: ("development_gui_trio_failed", [0.0, 0.0, 1.0]),
            infra["task_id"]: ("driver_or_environment_failed", None),
        })
        resolution = recovery.first_attempt_resolution(
            WORLD, index, ledger, excluded_task_ids=EXCLUDED,
            generic_fix_evidence={deterministic["template_group"]: "a" * 64})
        eligible = recovery.eligible_requalification_rows(ACTIVE, index, ledger, resolution)
        self.assertEqual({row["task_id"] for row in eligible},
                         {deterministic["task_id"], infra["task_id"]})
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "resolution.json"
            recovery.freeze_private_resolution(resolution, private)
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            self.assertEqual(recovery.read_private_resolution(private), resolution)

        good = {"status": recovery.PASS_STATUS, "scores": [1.0, 0.0, 1.0],
                "cold_resets": 3}
        item = index["items"][deterministic["task_id"]]
        item["attempts"].append(good.copy())
        item.update(good)
        bad = {"status": "development_gui_trio_failed", "scores": [1.0, 0.0, 0.0],
               "failure_ledger_entry_sha256": factory.sha256("second-failure")}
        item = index["items"][infra["task_id"]]
        item["attempts"].append(bad.copy())
        item.update(bad)
        ledger.append({"task_id": infra["task_id"], "seq": 3,
                       "attempt_number": 2, "entry_sha256": bad[
                           "failure_ledger_entry_sha256"]})
        queue = recovery.ordered_queue(SEED, WORLD, synthetic_catalog())
        plan = recovery.prospective_roster_after_requalification(
            WORLD, index, ledger, resolution, queue, excluded_task_ids=EXCLUDED)
        public = recovery.public_roster_plan(plan)
        self.assertEqual(public["retired_whole_source_families"], 1)
        self.assertEqual(public["retired_original_task_ids"], 5)
        self.assertEqual(public["fifo_replacement_source_families"], 1)
        self.assertEqual(public["prospective_candidate_task_count"], 100)
        self.assertEqual(public["replacement_gui_trios_still_required"], 5)
        self.assertNotIn(infra["task_id"], json.dumps(public))
        self.assertNotIn(deterministic["task_id"], json.dumps(public))

    def test_mutated_first_attempt_after_freeze_blocks_retry(self):
        failed = ACTIVE[0]
        index, ledger = complete_first_attempt_index({
            failed["task_id"]: ("driver_or_environment_failed", None)})
        resolution = recovery.first_attempt_resolution(
            WORLD, index, ledger, excluded_task_ids=EXCLUDED, generic_fix_evidence={})
        index["items"][failed["task_id"]]["attempts"][0]["error_type"] = "rewritten"
        with self.assertRaises(ValueError):
            recovery.eligible_requalification_rows(ACTIVE, index, ledger, resolution)


class GitLabRecoverySweepGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_flag_without_frozen_plan_is_rejected_before_gui(self):
        with patch.object(sweep, "_load", return_value={"items": {}}), \
                patch.object(sweep, "reconcile_failure_ledger"), \
                patch.object(sweep.quarantine, "excluded_task_ids", return_value=set()), \
                patch.object(sweep.gui_controls, "run") as gui:
            with self.assertRaises(ValueError):
                await sweep.run(1, retry_failed=True)
            gui.assert_not_called()


if __name__ == "__main__":
    unittest.main()
