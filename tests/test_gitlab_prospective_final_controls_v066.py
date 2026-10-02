"""No-Docker tests for source-bound prospective GitLab final controls."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gitlab_world import prospective_final_controls_v066 as lane


class ProspectiveGitLabControlsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.run_dir = self.root / "source-bound-100"
        self.baseline = self._snapshot([])
        baseline_path = self.root / "baseline-persisted-state.json"
        self._write(baseline_path, self.baseline)
        self.inputs = {
            "private_root": self.root,
            "world": {"tasks": [{"task_id": "task-000", "partition":
                                   "final_candidate_unsealed"}], "reserve_tasks": []},
            "world_sha256": "1" * 64,
            "preflight_private_sha256": "2" * 64,
            "preflight_public_sha256": "3" * 64,
            "baseline_sha256": lane.sha(baseline_path.read_bytes()),
            "baseline_business_sha256": self.baseline["business_sha256"],
            "bootstrap_progress_sha256": "4" * 64,
            "amended_ratification": {"private_sha256": "5" * 64,
                                      "public_sha256": "6" * 64},
            "roster": [{"task_id": f"task-{i:03d}",
                        "package_sha256": lane.sha(f"package:{i}".encode()),
                        "source_family_sha256": lane.sha(f"family:{i // 5}".encode()),
                        "template_group": "cross_record_issue_triage"}
                       for i in range(100)],
        }
        lane.freeze_plan(self.run_dir, self.inputs)
        self.plan, self.plan_sha = lane.validate_plan(self.run_dir, self.inputs)

    def _snapshot(self, labels: list[dict]) -> dict:
        value = {"schema": "envloop-gitlab-persisted-snapshot-v1",
                 "project_ids": [1],
                 "db": {"labels": labels, "issues": []},
                 "git": {"1": {"refs": {}}}}
        value["business_sha256"] = lane.sha(lane.canonical(value))
        return value

    def _write(self, path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        path.chmod(0o600)

    def test_intent_is_durable_before_fake_actor_and_no_replay_after_failure(self) -> None:
        observed = []
        async def fake_actor(plan, plan_sha, index, run_dir, baseline):
            events = lane.read_journal(run_dir, plan_sha)
            self.assertEqual(events[-1]["kind"], "intent")
            self.assertEqual(events[-1]["task_index"], index)
            observed.append(index)
            raise RuntimeError("fake infrastructure interruption")
        with self.assertRaisesRegex(RuntimeError, "no_auto_replay"):
            asyncio.run(lane.run_loop(self.run_dir, self.inputs, max_tasks=1,
                                      execute_one=fake_actor,
                                      readiness=lambda _plan: self.baseline))
        state = lane.journal_state(lane.read_journal(self.run_dir, self.plan_sha),
                                   self.plan)
        self.assertEqual(observed, [0])
        self.assertTrue(state["failed"])
        self.assertEqual(state["next_index"], 0)
        with self.assertRaisesRegex(ValueError, "separate_amendment"):
            asyncio.run(lane.run_loop(self.run_dir, self.inputs, max_tasks=1,
                                      execute_one=fake_actor,
                                      readiness=lambda _plan: self.baseline))
        self.assertEqual(observed, [0])

    def test_success_continues_from_next_id_and_reopens_trio_bytes(self) -> None:
        called = []
        async def fake_actor(plan, plan_sha, index, run_dir, baseline):
            self.assertEqual(lane.read_journal(run_dir, plan_sha)[-1]["kind"], "intent")
            item = plan["task_roster"][index]
            folder = run_dir / "attempts" / f"{index:03d}"
            folder.mkdir(mode=0o700)
            trio = {"schema": lane.TRIO_SCHEMA, "task_id": item["task_id"],
                    "package_sha256": item["package_sha256"],
                    "plan_sha256": plan_sha,
                    "source_bundle_sha256": plan["source_bundle_sha256"]}
            path = folder / "trio-complete.private.json"
            self._write(path, trio)
            called.append(index)
            return {"task_id": item["task_id"],
                    "trio_receipt_sha256": lane.sha(path.read_bytes()),
                    "control_scores": [1.0, 0.0, 1.0],
                    "fresh_cold_resets": 3,
                    "model_calls": 0, "official_final_admitted": 0}
        first = asyncio.run(lane.run_loop(self.run_dir, self.inputs, max_tasks=1,
                                          execute_one=fake_actor,
                                          readiness=lambda _plan: self.baseline))
        second = asyncio.run(lane.run_loop(self.run_dir, self.inputs, max_tasks=1,
                                           execute_one=fake_actor,
                                           readiness=lambda _plan: self.baseline))
        self.assertEqual(called, [0, 1])
        self.assertEqual((first["completed"], second["completed"]), (1, 2))
        self.assertEqual(second["official_final_admitted"], 0)

    def test_journal_rejects_repeated_intent_and_incomplete_intent(self) -> None:
        entries = []
        journal = self.run_dir / "journal.private.jsonl"
        item = self.plan["task_roster"][0]
        intent = {"kind": "intent", "task_index": 0,
                  "task_id": item["task_id"],
                  "package_sha256": item["package_sha256"],
                  "source_bundle_sha256": self.plan["source_bundle_sha256"],
                  "official_final_admitted": 0}
        lane.append_event(journal, self.plan_sha, entries, intent)
        self.assertIsNotNone(lane.journal_state(entries, self.plan)["pending"])
        with self.assertRaisesRegex(ValueError, "separate_amendment"):
            asyncio.run(lane.run_loop(self.run_dir, self.inputs, max_tasks=1,
                                      execute_one=lambda *_args: None,
                                      readiness=lambda _plan: self.baseline))
        lane.append_event(journal, self.plan_sha, entries, intent)
        with self.assertRaisesRegex(ValueError, "replay_or_roster_drift"):
            lane.journal_state(entries, self.plan)

    def test_exact_v06_proofs_need_saved_restore_and_unrelated_probe(self) -> None:
        identity = self.plan["task_roster"][0]
        validated = {
            "trio_receipt_sha256": "a" * 64,
            "unrelated_probe_sha256": "b" * 64,
            "probe_response": {"score": 0.0, "no_regression": False,
                               "persisted_oracle": True},
            "cases": [{"score": score,
                       "mutated_business_sha256": str(i + 1) * 64,
                       "restored_business_sha256": self.baseline["business_sha256"],
                       "case_completion_sha256": str(i + 6) * 64}
                      for i, score in enumerate((1.0, 0.0, 1.0))],
        }
        result = lane.derive_v06_proofs(
            identity, self.baseline["business_sha256"], validated,
            plan_sha256=self.plan_sha,
            source_bundle_sha256=self.plan["source_bundle_sha256"])
        self.assertEqual(result["reset_proof"]["initial_state_sha256"],
                         result["reset_proof"]["restored_state_sha256"])
        self.assertEqual(result["verifier_proof"]["schema"],
                         "cua-task-verifier-proof-v0.6")
        self.assertEqual(result["source_envelope"]["trio_receipt_sha256"], "a" * 64)
        invalid = copy.deepcopy(validated)
        invalid["cases"][1]["restored_business_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "requires_validated"):
            lane.derive_v06_proofs(identity, self.baseline["business_sha256"], invalid,
                                   plan_sha256=self.plan_sha,
                                   source_bundle_sha256=self.plan["source_bundle_sha256"])

    def test_amended_ratification_supersedes_old_digest_and_keeps_gitlab_adapter(self) -> None:
        common = lane.common_source_hashes()
        adapter = lane.sha((lane.ROOT /
                            "gitlab_world/vision_actor_v066_train.py").read_bytes())
        cells = ("powerpoint-web", "excel-web", "desktop-native",
                 "odoo-community", "gitlab", "magento-admin")
        private = {"schema": "cua-six-cell-action-profile-v066-ratification-v1",
                   "status": "ratified_pre_result",
                   "ratified_utc": datetime.now(timezone.utc).isoformat(),
                   "action_profile": "scale-action-profile-v0.6.6",
                   "base_and_selected_identical": True,
                   "hidden_final_model_attempts_before_ratification": 0,
                   "common_source_sha256s": common,
                   "cell_profiles": {
                       cell: {"common_source_sha256s": common,
                              "adapter_sha256": adapter if cell == "gitlab" else "0" * 64}
                       for cell in cells}}
        private_path = self.root / "amended.private.json"
        public_path = self.root / "amended.public.json"
        self._write(private_path, private)
        visible = {
            "schema": "cua-six-cell-v066-caret-code-only-ratification-public-v1",
            "status": "new_source_bytes_frozen_for_evaluator_controls_only",
            "private_ratification_sha256": lane.sha(private_path.read_bytes()),
            "supersedes_old_private_ratification_sha256": "a" * 64,
            "common_source_sha256s": common,
            "cell_adapter_sha256s": {
                cell: private["cell_profiles"][cell]["adapter_sha256"]
                for cell in cells},
            "qualified_final_tasks": 0,
            "researcher_campaigns": 0,
            "official_final_model_results": 0,
        }
        self._write(public_path, visible)
        accepted = lane.amended_ratification(private_path, public_path, "a" * 64)
        self.assertEqual(accepted["gitlab_adapter_sha256"], adapter)
        with self.assertRaisesRegex(ValueError, "amended_v066"):
            lane.amended_ratification(private_path, public_path, "b" * 64)

    def test_raw_auditor_rejects_success_journal_without_case_receipts(self) -> None:
        item = self.plan["task_roster"][0]
        folder = self.run_dir / "attempts" / "000"
        folder.mkdir(mode=0o700)
        trio = {"schema": lane.TRIO_SCHEMA, "task_id": item["task_id"],
                "package_sha256": item["package_sha256"],
                "plan_sha256": self.plan_sha,
                "source_bundle_sha256": self.plan["source_bundle_sha256"],
                "control_scores": [1.0, 0.0, 1.0], "cases": [],
                "model_calls": 0, "official_final_admitted": 0}
        path = folder / "trio-complete.private.json"
        self._write(path, trio)
        entries = []
        journal = self.run_dir / "journal.private.jsonl"
        lane.append_event(journal, self.plan_sha, entries,
                          {"kind": "intent", "task_index": 0,
                           "task_id": item["task_id"],
                           "package_sha256": item["package_sha256"],
                           "source_bundle_sha256": self.plan["source_bundle_sha256"],
                           "official_final_admitted": 0})
        lane.append_event(journal, self.plan_sha, entries,
                          {"kind": "terminal", "task_index": 0,
                           "task_id": item["task_id"],
                           "status": "control_passed", "error_type": None,
                           "wall_seconds": 0.1,
                           "trio_receipt_sha256": lane.sha(path.read_bytes()),
                           "official_final_admitted": 0})
        with self.assertRaisesRegex(ValueError, "prospective_trio_receipt_invalid"):
            lane.audit_controls(self.run_dir, self.inputs,
                                evaluator=lambda *_args, **_kwargs: {})

    def test_raw_auditor_reopens_complete_fake_cases_and_rejects_tamper(self) -> None:
        identity = self.plan["task_roster"][0]
        task_id = identity["task_id"]
        folder = self.run_dir / "attempts" / "000"
        folder.mkdir(mode=0o700)
        refs = []
        saved_positive = None
        for number, (name, _variant, score) in enumerate(
                lane.CASES["cross_record_issue_triage"], 1):
            case = folder / name
            case.mkdir(mode=0o700)
            saved = self._snapshot([{"id": 1, "title": f"case-{number}"}])
            if number == 1:
                saved_positive = saved
            after = case / "after-persisted-state.json"
            restored = case / "after-reset-persisted-state.json"
            self._write(after, saved)
            self._write(restored, self.baseline)
            (case / "policy.png").write_bytes(b"policy")
            (case / "issue-after.png").write_bytes(b"saved issue")
            receipt = {
                "schema": "envloop-gitlab-gui-control-attempt-v1",
                "task_id": task_id, "case": name,
                "fresh_browser_context": True,
                "scoped_non_admin_operator": True,
                "credential_retained_in_receipt": False,
                "raw_har_retained": False, "model_calls": 0,
                "gui": {"policy_rendered": True, "saved_visible": True,
                        "screenshot_sha256": {
                            "policy.png": lane.sha(b"policy"),
                            "issue-after.png": lane.sha(b"saved issue")}},
                "persisted_oracle": {
                    "task_id": task_id, "score": score,
                    "persisted_oracle": True,
                    "no_regression": score == 1.0,
                    "before_business_sha256": self.baseline["business_sha256"],
                    "after_business_sha256": saved["business_sha256"]},
            }
            receipt_path = case / "receipt.json"
            self._write(receipt_path, receipt)
            complete = {
                "schema": lane.CASE_SCHEMA,
                "task_id": task_id, "case": name,
                "expected_score": score,
                "plan_sha256": self.plan_sha,
                "source_bundle_sha256": self.plan["source_bundle_sha256"],
                "raw_receipt_sha256": lane.sha(receipt_path.read_bytes()),
                "after_state_sha256": lane.sha(after.read_bytes()),
                "restored_state_sha256": lane.sha(restored.read_bytes()),
                "all_gui_screenshot_sha256s": {
                    "policy.png": lane.sha(b"policy"),
                    "issue-after.png": lane.sha(b"saved issue")},
                "reset_receipt": {"cold_reset": True,
                                  "same_business_sha256": True,
                                  "container_identity_changed": True,
                                  "generation": number},
                "model_calls": 0, "official_final_admitted": 0,
            }
            complete_path = case / "case-complete.private.json"
            self._write(complete_path, complete)
            refs.append({"case": name,
                         "case_completion_sha256": lane.sha(complete_path.read_bytes())})
        self.assertIsNotNone(saved_positive)
        unrelated = lane._unrelated_perturbation(saved_positive)
        unrelated_path = folder / "unrelated-change-state.private.json"
        self._write(unrelated_path, unrelated)
        positive_path = folder / "positive-1" / "after-persisted-state.json"
        response = {"task_id": task_id, "score": 0.0,
                    "persisted_oracle": True, "no_regression": False,
                    "before_business_sha256": self.baseline["business_sha256"],
                    "after_business_sha256": unrelated["business_sha256"]}
        probe = {"schema": lane.PROBE_SCHEMA, "task_id": task_id,
                 "plan_sha256": self.plan_sha,
                 "positive_state_sha256": lane.sha(positive_path.read_bytes()),
                 "unrelated_state_sha256": lane.sha(unrelated_path.read_bytes()),
                 "mutation": "first_existing_label_title_appended",
                 "verifier_response": response,
                 "model_calls": 0, "official_final_admitted": 0}
        probe_path = folder / "unrelated-probe.private.json"
        self._write(probe_path, probe)
        trio = {"schema": lane.TRIO_SCHEMA, "task_id": task_id,
                "package_sha256": identity["package_sha256"],
                "plan_sha256": self.plan_sha,
                "source_bundle_sha256": self.plan["source_bundle_sha256"],
                "cases": refs, "control_scores": [1.0, 0.0, 1.0],
                "unrelated_probe_sha256": lane.sha(probe_path.read_bytes()),
                "model_calls": 0, "official_final_admitted": 0}
        trio_path = folder / "trio-complete.private.json"
        self._write(trio_path, trio)
        entries = []
        journal = self.run_dir / "journal.private.jsonl"
        lane.append_event(journal, self.plan_sha, entries,
                          {"kind": "intent", "task_index": 0,
                           "task_id": task_id,
                           "package_sha256": identity["package_sha256"],
                           "source_bundle_sha256": self.plan["source_bundle_sha256"],
                           "official_final_admitted": 0})
        lane.append_event(journal, self.plan_sha, entries,
                          {"kind": "terminal", "task_index": 0,
                           "task_id": task_id,
                           "status": "control_passed", "error_type": None,
                           "wall_seconds": 0.1,
                           "trio_receipt_sha256": lane.sha(trio_path.read_bytes()),
                           "official_final_admitted": 0})
        private, public = lane.audit_controls(
            self.run_dir, self.inputs,
            evaluator=lambda *_args, **_kwargs: response)
        self.assertEqual(private["completed_task_count"], 1)
        self.assertEqual(len(private["validated_tasks"][0]["cases"]), 3)
        self.assertFalse(public["all_100_controls_independently_validated"])
        self.assertEqual(public["official_final_admitted"], 0)
        restored = folder / "positive-1" / "after-reset-persisted-state.json"
        restored.write_bytes(b"{}\n")
        with self.assertRaisesRegex(ValueError, "raw_bytes_changed"):
            lane.audit_controls(self.run_dir, self.inputs,
                                evaluator=lambda *_args, **_kwargs: response)


if __name__ == "__main__":
    unittest.main()
