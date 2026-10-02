"""Prospective GitLab recovery must not select replacements from outcomes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gitlab_world import (factory, gui_controls, gui_workflows,
                          pre_result_recovery as recovery, sweep)


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


def make_valid_train_receipt(tmp: str, workflow: str):
    root = Path(tmp) / "private"
    baseline_sha = "b" * 64
    factory.write_private(root / "baseline-persisted-state.json",
                          {"business_sha256": baseline_sha})
    shape = recovery.TRAIN_RECEIPT_SHAPES[workflow]
    folder = root / shape["directory"] / "run-test"
    folder.parent.mkdir(mode=0o700)
    folder.mkdir(mode=0o700)
    case_refs = {}
    for index, (label, score) in enumerate(zip(shape["labels"], (1.0, 0.0, 1.0))):
        path = folder / label / "receipt.json"
        path.parent.mkdir(mode=0o700)
        factory.write_private(path, {"label": label, "score": score,
                                     "before_business_sha256": baseline_sha,
                                     "after_business_sha256": chr(ord("c") + index) * 64,
                                     "post_reset_business_sha256": baseline_sha,
                                     "cold_reset_verified": True,
                                     "visible_reload_verified": True,
                                     "independent_saved_state_checked": True,
                                     "no_regression_checked": True})
        case_refs[label] = {"path": label + "/receipt.json",
                            "sha256": factory.sha256(path.read_bytes())}
    operator = gui_controls if shape["operator_module"] == "gui_controls" else gui_workflows
    script = Path(recovery.__file__).resolve().parents[1] / "tools" / shape["probe_script"]
    train_project = next(p for p in WORLD["projects"] if p["partition"] == "train")
    summary = {"schema": shape["schema"], "workflow": workflow,
               "partition": "train", "project_path": train_project["full_path"],
               "scores": [1.0, 0.0, 1.0], "cold_resets": [True] * 3,
               "case_receipts": case_refs, "baseline_business_sha256": baseline_sha,
               "generic_operator_sha256": factory.sha256(Path(operator.__file__).read_bytes()),
               "probe_script_sha256": factory.sha256(script.read_bytes()),
               "visible_reload_verified_all": True,
               "independent_saved_state_checked": True,
               "no_regression_checked": True, "passed": True,
               "model_calls": 0, "official_final_admitted": 0}
    summary_path = folder / "summary-private.json"
    factory.write_private(summary_path, summary)
    ref = {"path": str(summary_path.relative_to(root)),
           "sha256": factory.sha256(summary_path.read_bytes())}
    return root, ref, summary_path


class GitLabProspectiveRecoveryTests(unittest.TestCase):
    def test_both_deterministic_workflows_require_real_train_receipt_files(self):
        for workflow in recovery.TRAIN_RECEIPT_SHAPES:
            with self.subTest(workflow=workflow), tempfile.TemporaryDirectory() as tmp:
                root, ref, _ = make_valid_train_receipt(tmp, workflow)
                self.assertEqual(recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: ref}, private_root=root),
                    {workflow: ref["sha256"]})
                with self.assertRaises(ValueError):
                    recovery.validate_generic_fix_evidence(
                        WORLD, {workflow: "a" * 64}, private_root=root)

    def test_train_receipt_drift_wrong_partition_and_source_hash_fail_closed(self):
        workflow = "release_milestone_coordination"
        with tempfile.TemporaryDirectory() as tmp:
            root, ref, summary_path = make_valid_train_receipt(tmp, workflow)
            corrupted = copy.deepcopy(ref)
            corrupted["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: corrupted}, private_root=root)
            summary = json.loads(summary_path.read_text())
            summary["partition"] = "final_candidate_unsealed"
            summary_path.write_text(json.dumps(summary, sort_keys=True))
            ref["sha256"] = factory.sha256(summary_path.read_bytes())
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: ref}, private_root=root)
            summary["partition"] = "train"
            summary["generic_operator_sha256"] = "0" * 64
            summary_path.write_text(json.dumps(summary, sort_keys=True))
            ref["sha256"] = factory.sha256(summary_path.read_bytes())
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: ref}, private_root=root)

    def test_legacy_probe_schema_and_permissive_private_root_rejected(self):
        workflow = "release_milestone_coordination"
        with tempfile.TemporaryDirectory() as tmp:
            root, ref, summary_path = make_valid_train_receipt(tmp, workflow)
            summary = json.loads(summary_path.read_text())
            summary["schema"] = "envloop-gitlab-train-milestone-save-probe-v1"
            summary_path.write_text(json.dumps(summary, sort_keys=True))
            ref["sha256"] = factory.sha256(summary_path.read_bytes())
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: ref}, private_root=root)
            summary["schema"] = recovery.TRAIN_RECEIPT_SHAPES[workflow]["schema"]
            summary_path.write_text(json.dumps(summary, sort_keys=True))
            ref["sha256"] = factory.sha256(summary_path.read_bytes())
            root.chmod(0o755)
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: ref}, private_root=root)

    def test_train_case_reset_or_no_regression_drift_blocks_freeze(self):
        workflow = "cross_record_issue_triage"
        with tempfile.TemporaryDirectory() as tmp:
            root, ref, summary_path = make_valid_train_receipt(tmp, workflow)
            summary = json.loads(summary_path.read_text())
            case_path = summary_path.parent / "positive-2" / "receipt.json"
            case = json.loads(case_path.read_text())
            case["post_reset_business_sha256"] = "0" * 64
            case["no_regression_checked"] = False
            case_path.write_text(json.dumps(case, sort_keys=True))
            summary["case_receipts"]["positive-2"]["sha256"] = factory.sha256(
                case_path.read_bytes())
            summary_path.write_text(json.dumps(summary, sort_keys=True))
            ref["sha256"] = factory.sha256(summary_path.read_bytes())
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: ref}, private_root=root)

    def test_train_receipt_symlink_and_path_escape_are_rejected(self):
        workflow = "release_milestone_coordination"
        with tempfile.TemporaryDirectory() as tmp:
            root, ref, summary_path = make_valid_train_receipt(tmp, workflow)
            link = root / "train-milestone-save-probe" / "run-link" / "summary-private.json"
            link.parent.mkdir(mode=0o700)
            link.symlink_to(summary_path)
            linked = {"path": str(link.relative_to(root)),
                      "sha256": factory.sha256(summary_path.read_bytes())}
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: linked}, private_root=root)
            escaped = {"path": "../" + ref["path"], "sha256": ref["sha256"]}
            with self.assertRaises(ValueError):
                recovery.validate_generic_fix_evidence(
                    WORLD, {workflow: escaped}, private_root=root)

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
        with tempfile.TemporaryDirectory() as tmp:
            root, ref, _ = make_valid_train_receipt(
                tmp, deterministic["template_group"])
            with_fix = recovery.first_attempt_resolution(
                WORLD, index, ledger, excluded_task_ids=EXCLUDED,
                generic_fix_evidence={deterministic["template_group"]: ref},
                private_root=root)
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
        with tempfile.TemporaryDirectory() as tmp:
            root, ref, _ = make_valid_train_receipt(
                tmp, deterministic["template_group"])
            resolution = recovery.first_attempt_resolution(
                WORLD, index, ledger, excluded_task_ids=EXCLUDED,
                generic_fix_evidence={deterministic["template_group"]: ref},
                private_root=root)
            eligible = recovery.eligible_requalification_rows(
                ACTIVE, index, ledger, resolution, world=WORLD, private_root=root)
            self.assertEqual({row["task_id"] for row in eligible},
                             {deterministic["task_id"], infra["task_id"]})
            private = Path(tmp) / "resolution.json"
            recovery.freeze_private_resolution(resolution, private)
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            self.assertEqual(recovery.read_private_resolution(
                private, private_root=Path(tmp)), resolution)

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
            recovery.eligible_requalification_rows(
                ACTIVE, index, ledger, resolution, world=WORLD)


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
