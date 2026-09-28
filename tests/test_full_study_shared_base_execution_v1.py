"""Fake-only durable paid-session checks for one shared-base selection."""

from __future__ import annotations

from pathlib import Path
import base64
import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from cursibench import full_study_shared_base_execution_v1 as execution
from tests import test_full_study_campaign_dispatch_v1 as dispatch_fixture
from tests import test_gitlab_selection_worker_v066 as gitlab_fake
from gitlab_world import selection_worker_v066 as gitlab
from cursibench import full_study_shared_base_selection_v1 as shared
from cursibench import full_study_matrix_v1 as matrix


class SharedBaseSessionTests(unittest.TestCase):
    def setUp(self):
        harness = dispatch_fixture.FullStudyDispatchTests(
            "test_campaign_cannot_start_without_one_shared_base_selection")
        harness.setUp()
        self.addCleanup(harness.tearDown)
        self.harness = harness
        self.study = harness.frozen()
        (Path(self.study.repo_root) / "work").mkdir(mode=0o700,
                                                     exist_ok=True)
        self.session = execution.SharedBaseSession(
            self.study, "powerpoint-web")
        self.task = self.session.started["selection_tasks"][0]

    def tinker_request(self):
        return {"schema": "cua-full-study-selection-sampling-request-v1",
                "cell_id": "powerpoint-web",
                "selection_attempt": self.session.attempt_id,
                "task_id": self.task["task_id"],
                "package_sha256": self.task["package_sha256"],
                "checkpoint_path_sha256": self.session.started[
                    "checkpoint_path_sha256"],
                "frame_sha256": "a" * 64}

    def test_base_view_and_exact_request_are_reserved_before_fake_provider(self):
        started = self.session.started
        self.assertEqual(started["task_count"], 20)
        self.assertTrue(all("-official-" not in row["task_id"]
                            for row in started["selection_tasks"]))
        request = self.tinker_request()
        attempt_id = self.session.attempt_id + "-sample-001"
        def provider(raw):
            self.assertEqual(raw, request)
            budget = self.session.budget.owner_attempts(self.session.owner)
            self.assertEqual(budget[attempt_id]["status"], "dispatched")
            envelope = (self.session.directory / "paid" /
                        (attempt_id + ".request.private.json"))
            self.assertTrue(envelope.exists())
            self.assertEqual(json.loads(envelope.read_bytes())[
                "qwen_runtime"]["runtime_spec_sha256"], "d" * 64)
            return {"status": "completed", "text": '{"type":"finish"}'}
        paid = self.session.dispatch_paid(
            attempt_id=attempt_id, category="tinker",
            work=request, request=request,
            reserve_usd="0.01", resource_reservation={},
            provider=provider)
        self.assertEqual(paid["result"]["status"], "completed")
        env_id = self.session.attempt_id + "-env-batch"
        env_request = {
            "schema": "cua-full-study-selection-environment-request-v1",
            "cell_id": "powerpoint-web",
            "selection_attempt": self.session.attempt_id,
            "selection_identities_sha256": started[
                "selection_identities_sha256"],
            "selection_tasks": started["selection_tasks"],
            "checkpoint_path_sha256": started[
                "checkpoint_path_sha256"],
        }
        self.session.dispatch_paid(
            attempt_id=env_id, category="e2b",
            work=env_request, request=env_request,
            reserve_usd="0.01",
            resource_reservation={"e2b_sandbox_hours": "0.01",
                                  "e2b_peak_concurrency": "1"},
            provider=lambda _: {"status": "active"})
        def reconcile(item):
            return {"actual_usd": "0.005",
                    "invoice_basis": "provider_invoice",
                    "provider_invoice_usd": "0.005",
                    "source_bytes": ("synthetic account usage " +
                                     item["attempt_id"]).encode()}
        refs = self.session.reconcile_all(reconcile)
        self.assertEqual(len(refs), 2)
        owner = self.session.budget.owner_attempts(self.session.owner)
        self.assertEqual({row["status"] for row in owner.values()},
                         {"settled"})
        self.assertEqual({row["category"] for row in owner.values()},
                         {"tinker", "e2b"})

    def test_runtime_refusal_precedes_shared_base_file_reserve_and_provider(self):
        self.harness.runtime_gate_mock.side_effect = (
            execution.qwen_runtime_gate.RuntimeGateError("missing_runtime"))
        attempt_id = self.session.attempt_id + "-sample-001"
        called = []
        with self.assertRaisesRegex(execution.SharedBaseExecutionError,
                                    "qwen_runtime_pre_dispatch_failed"):
            self.session.dispatch_paid(
                attempt_id=attempt_id, category="tinker",
                work=self.tinker_request(), request=self.tinker_request(),
                reserve_usd="0.01", resource_reservation={},
                provider=lambda _: called.append("provider"))
        self.assertEqual(called, [])
        self.assertEqual(self.session.budget.owner_attempts(
            self.session.owner), {})
        self.assertFalse((self.session.directory / "paid" /
                          (attempt_id + ".request.private.json")).exists())
        self.assertFalse((self.session.directory / "paid" /
                          (attempt_id + ".worker-request.private.json")).exists())

    def test_uncertain_callback_keeps_reserve_and_cannot_replay(self):
        request = self.tinker_request()
        attempt_id = self.session.attempt_id + "-sample-001"
        calls = []
        def broken(_request):
            calls.append("called")
            raise RuntimeError("synthetic transport uncertainty")
        with self.assertRaisesRegex(execution.SharedBaseExecutionError,
                                    "uncertain_no_replay"):
            self.session.dispatch_paid(
                attempt_id=attempt_id, category="tinker",
                work=request, request=request,
                reserve_usd="0.01", resource_reservation={},
                provider=broken)
        self.assertEqual(calls, ["called"])
        self.assertEqual(self.session.budget.owner_attempts(
            self.session.owner)[attempt_id]["status"], "uncertain")
        with self.assertRaises(execution.SharedBaseExecutionError):
            self.session.dispatch_paid(
                attempt_id=attempt_id, category="tinker",
                work=request, request=request,
                reserve_usd="0.01", resource_reservation={},
                provider=broken)
        self.assertEqual(calls, ["called"])

    def test_selection_categories_share_one_separate_reserve(self):
        self.session.cell["base_selection_cost_upper_bound_usd"] = "0.015"
        request = self.tinker_request()
        self.session.dispatch_paid(
            attempt_id=self.session.attempt_id + "-sample-001",
            category="tinker", work=request, request=request,
            reserve_usd="0.01", resource_reservation={},
            provider=lambda _: {"status": "completed"})
        calls = []
        with self.assertRaisesRegex(execution.SharedBaseExecutionError,
                                    "selection_separate_reserve_exhausted"):
            self.session.dispatch_paid(
                attempt_id=self.session.attempt_id + "-sample-002",
                category="tinker", work=request, request=request,
                reserve_usd="0.01", resource_reservation={},
                provider=lambda _: calls.append("called"))
        self.assertEqual(calls, [])
        self.assertEqual(len(self.session.budget.owner_attempts(
            self.session.owner)), 1)


class SharedBaseEndToEndTests(unittest.TestCase):
    def setUp(self):
        harness = dispatch_fixture.FullStudyDispatchTests(
            "test_campaign_cannot_start_without_one_shared_base_selection")
        harness.setUp()
        self.addCleanup(harness.tearDown)
        self.study = harness.frozen()
        (Path(self.study.repo_root) / "work").mkdir(mode=0o700,
                                                     exist_ok=True)

    def test_gitlab_twenty_fake_gui_tasks_are_projected_and_admitted(self):
        worker = gitlab.GitLabSelectionWorker()
        worker.backend = gitlab_fake.FakeBackend()
        training = {
            "max_supervised_tokens": 32768,
            "prefill_usd_per_million_tokens": "1",
            "sample_usd_per_million_tokens": "2",
            "billing_multiplier_upper": "1"}
        policy = {"seed": 23, "temperature": 0.0,
                  "max_output_tokens": 64,
                  "max_actions_per_task": 2,
                  "max_wall_seconds_per_task": 720}
        def run_native(session, out_dir):
            def provider(request, _prompt):
                return {
                    "schema": "envloop-gitlab-v066-selection-sampler-result-v1",
                    "status": "completed", "reported_model": gitlab.MODEL,
                    "checkpoint_path_sha256": session.started[
                        "checkpoint_path_sha256"],
                    "text": '{"type":"finish"}',
                    "stop_reason": "stop", "elapsed_seconds": 0.01,
                    "usage": {"input_tokens": request["input_tokens"],
                              "output_tokens": 5,
                              "image_tokens": request["image_tokens"],
                              "prompt_cache_hit_tokens": None,
                              "provider_billed_tokens": None,
                              "basis":
                              "rendered_input_and_returned_output_not_invoice"},
                }
            with patch.object(worker, "_require_frozen",
                              return_value=({}, {})), \
                 patch.object(worker, "_resolve_checkpoint_path",
                              return_value=gitlab.MODEL), \
                 patch.object(worker, "_policy",
                              return_value=(training, policy,
                                            Decimal("0.5"))), \
                 patch.object(worker, "_load_vision",
                              return_value=gitlab_fake.FakeVision()):
                return worker.run_attempt(
                    session=session, started=session.started,
                    out_dir=out_dir, sampler_provider=provider)

        def reconcile(item):
            basis = ("self_hosted_nominal_meter" if
                     item["category"] == "storage_application" else
                     "provider_invoice")
            return {"actual_usd": "0", "invoice_basis": basis,
                    "provider_invoice_usd": (None if basis ==
                     "self_hosted_nominal_meter" else "0"),
                    "source_bytes": ("fake-provider-usage:" +
                                     item["attempt_id"]).encode()}

        admitted = execution.execute_shared_base(
            self.study, "gitlab", run_native, reconcile)
        self.assertEqual(admitted["task_count"], 20)
        self.assertEqual(admitted["wins"], 20)
        self.assertEqual(admitted["paid_attempt_count"], 40)
        self.assertEqual(admitted["researcher_campaigns"], 0)
        self.assertTrue((Path(admitted["receipt_path"]).parent /
                         "accepted.private.json").is_file())
        imported = []
        for researcher_id in matrix.RESEARCHERS:
            campaign = self.study.open_campaign(
                Path(self.study.repo_root) / "work" /
                ("campaign-gitlab-" + researcher_id),
                cell_id="gitlab", researcher_id=researcher_id)
            base = campaign.record_base_selection(
                shared_receipt_path=Path(admitted["receipt_path"]))
            imported.append(base["shared_receipt_sha256"])
        self.assertEqual(imported,
                         [admitted["shared_receipt_sha256"]] * 4)

    def test_odoo_batch_paid_grammar_and_native_projection_are_admitted(self):
        def write(path, value, *, raw=False):
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            data = value if raw else shared._canonical(value)
            path.write_bytes(data)
            path.chmod(0o600)
            return shared._sha(data)

        def run_native(session, out_dir):
            out_dir.mkdir(mode=0o700)
            started = session.started
            local_id = session.attempt_id + "-local-service"
            local_request = {
                "selection_attempt": session.attempt_id,
                "selection_identities_sha256": started[
                    "selection_identities_sha256"],
                "selection_tasks": started["selection_tasks"],
                "checkpoint_path_sha256": started[
                    "checkpoint_path_sha256"]}
            session.dispatch_paid(
                attempt_id=local_id, category="storage_application",
                work=local_request, request=local_request,
                reserve_usd="0.1", resource_reservation={},
                provider=lambda _: {"status":
                    "reserved_before_local_worker_start"})
            setup_id = session.attempt_id + "-tinker-setup"
            setup_request = {
                "selection_attempt": session.attempt_id,
                "selection_identities_sha256": started[
                    "selection_identities_sha256"],
                "checkpoint_path_sha256": started[
                    "checkpoint_path_sha256"],
                "model": "Qwen/Qwen3.8-27B",
                "sampling_kind": "base"}
            session.dispatch_paid(
                attempt_id=setup_id, category="tinker",
                work=setup_request, request=setup_request,
                reserve_usd="0.01", resource_reservation={},
                provider=lambda _: {"status": "ready"})
            rows = []
            result_rows = []
            for ordinal, identity in enumerate(started["selection_tasks"], 1):
                folder = out_dir / "tasks" / f"task-{ordinal:03d}"
                folder.mkdir(mode=0o700, parents=True)
                png = gitlab_fake.png()
                frame_sha = write(folder / "frames" / "step-000.png",
                                  png, raw=True)
                paid_id = session.attempt_id + f"-sample-{ordinal:02d}-000"
                request = {
                    "selection_attempt": session.attempt_id,
                    "task_id": identity["task_id"],
                    "package_sha256": identity["package_sha256"],
                    "checkpoint_path_sha256": started[
                        "checkpoint_path_sha256"],
                    "frame_sha256": frame_sha,
                    "image_base64": base64.b64encode(png).decode(),
                    "sampling_kind": "base"}
                session.dispatch_paid(
                    attempt_id=paid_id, category="tinker",
                    work=request, request=request,
                    reserve_usd="0.01", resource_reservation={},
                    provider=lambda _: {"status": "completed",
                                        "text": '{"type":"finish"}'})
                saved_sha = write(folder / "saved-state.private.json", {
                    "schema": "envloop-odoo-selection-saved-sql-v1",
                    "task_id": identity["task_id"],
                    "business_snapshot": {"business_sha256": "a" * 64},
                    "gui_reload_frame_sha256": frame_sha})
                verifier_sha = write(folder / "verifier.private.json", {
                    "score": 1, "independent_select_only": True})
                semantic = {"business_snapshot": {"business_sha256":
                                                    "b" * 64}}
                baseline_sha = write(
                    folder / "baseline-semantic.private.json", semantic)
                restored_sha = write(
                    folder / "restored-semantic.private.json", semantic)
                reset_sha = write(folder / "reset.private.json", {
                    "pre_database_filestore_exact": True,
                    "post_database_filestore_exact": True,
                    "baseline_semantic_ref": {
                        "path": "baseline-semantic.private.json",
                        "sha256": baseline_sha},
                    "restored_semantic_ref": {
                        "path": "restored-semantic.private.json",
                        "sha256": restored_sha}})
                frames_sha = write(folder / "frames.private.json", [{
                    "path": "frames/step-000.png", "sha256": frame_sha}])
                actions_sha = write(folder / "actions.private.json", [{
                    "step": 0, "frame_sha256": frame_sha,
                    "action_type": "finish"}])
                usage_sha = write(folder / "usage.private.json", {
                    "samples": [{"step": 0, "paid_attempt_id": paid_id,
                                 "model_text_sha256": shared._sha(
                                     b'{"type":"finish"}')}],
                })
                row = {**identity, "score": 1,
                       "saved_state_sha256": saved_sha,
                       "verifier_receipt_sha256": verifier_sha,
                       "reset_receipt_sha256": reset_sha,
                       "baseline_semantic_sha256": baseline_sha,
                       "restored_semantic_sha256": restored_sha,
                       "frames_sha256": frames_sha,
                       "actions_sha256": actions_sha,
                       "usage_sha256": usage_sha,
                       "frame_count": 1, "sample_count": 1,
                       "sample_paid_attempt_ids": [paid_id]}
                rows.append(row)
                result_rows.append({key: row[key] for key in (
                    "task_id", "package_sha256", "score",
                    "saved_state_sha256", "verifier_receipt_sha256",
                    "reset_receipt_sha256")})
            ledger_sha = write(out_dir / "task-ledger.private.json", {
                "selection_attempt": session.attempt_id,
                "checkpoint_sha256": started[
                    "checkpoint_path_sha256"],
                "selection_identities_sha256": started[
                    "selection_identities_sha256"],
                "rows": rows})
            runtime_sha = write(out_dir / "local-runtime.private.json", {
                "services_restored_to_initial_state": True,
                "final_database_snapshot_equal": True,
                "final_physical_filestore_equal": True})
            return {"result": {
                "cell_id": "odoo-community",
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "evaluator_isolated": True, "tasks": result_rows},
                "paid_attempt_ids": list(session.completed_paid),
                "task_ledger_sha256": ledger_sha,
                "local_runtime_receipt_sha256": runtime_sha}

        def reconcile(item):
            basis = ("self_hosted_nominal_meter" if item["category"] ==
                     "storage_application" else "provider_invoice")
            return {"actual_usd": "0", "invoice_basis": basis,
                    "provider_invoice_usd": None if basis ==
                    "self_hosted_nominal_meter" else "0",
                    "source_bytes": ("fake-source:" +
                                     item["attempt_id"]).encode()}

        def worker_factory(**kwargs):
            class FakeOdooWorker:
                cell_id = "odoo-community"
                runtime_sha256 = kwargs["expected_runtime_sha256"]
                verifier_sha256 = kwargs["expected_verifier_sha256"]

                def run_selection(self, *, started, checkpoint_path,
                                  student_config_raw,
                                  student_config_sha256, out_dir,
                                  dispatch_paid, base_mode):
                    self_test = self
                    assert base_mode is True
                    assert checkpoint_path == "Qwen/Qwen3.8-27B"
                    assert started["checkpoint_path_sha256"] == kwargs[
                        "expected_base_checkpoint_sha256"]
                    assert shared._sha(student_config_raw) == \
                        student_config_sha256
                    assert self_test.cell_id == "odoo-community"
                    return run_native(dispatch_paid.__self__, out_dir)
            return FakeOdooWorker()

        admitted = execution.run_odoo_shared_base(
            self.study, reconcile,
            worker_dir=Path(self.study.repo_root) / "fake-odoo-worker",
            local_cost_authority_path=Path(self.study.repo_root) /
                "fake-cost-authority.json",
            local_cost_authority_sha256="a" * 64,
            worker_factory=worker_factory)
        self.assertEqual(admitted["task_count"], 20)
        self.assertEqual(admitted["wins"], 20)
        self.assertEqual(admitted["paid_attempt_count"], 22)


if __name__ == "__main__":
    unittest.main()
