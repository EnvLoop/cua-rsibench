"""Fake-provider twenty-task Odoo selection; no Docker or model dispatch."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_selection_paid_coverage_v1 as paid_coverage
from cursibench import scale_final_v06 as final
from cursibench.scale_action_contract import make_observation
from enterprise_fallback.odoo18 import selection_worker_v066 as selection


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def private_json(path: Path, value: object) -> str:
    raw = selection._canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)
    return digest(raw)


class FakeSampler:
    def __init__(self, events):
        self.events = events
        self.calls = 0
        self.fail_at_task = None

    def __enter__(self):
        self.events.append("fake_sampler_open")
        return self

    def __exit__(self, *_args):
        self.events.append("fake_sampler_close")

    def sample(self, observation, *, task_index, step, task_dir):
        self.calls += 1
        self.events.append("fake_tinker_sample")
        if self.fail_at_task == task_index:
            return {"status": "error", "text": None,
                    "request_id": f"fake-{task_index}-{step}",
                    "new_dispatch": True, "reused": False,
                    "error_subtype": "provider_timeout_uncertain",
                    "usage": {"input_tokens": 100,
                              "output_tokens": None}}
        return {"status": "completed", "text": '{"type":"finish"}',
                "request_id": f"fake-{task_index}-{step}",
                "new_dispatch": True, "reused": False,
                "usage": {"input_tokens": 100, "output_tokens": 10}}


class FakeEnvironment:
    def __init__(self, events):
        self.events = events
        self.runtime_receipt = None
        self.fail_reset = False
        self.tamper_artifact_at = None
        self.cases = []

    def validate_tasks(self, tasks):
        self.events.append("private_selection_manifest_checked")
        assert len(tasks) == 20

    def reserve_local_capacity(self, request):
        self.events.append("local_capacity_reserved")
        assert request["lease_seconds"] == selection.LOCAL_LEASE_SECONDS
        return {"status": "reserved_before_local_worker_start",
                "provider_invoice_usd": None}

    @contextmanager
    def batch(self):
        self.events.append("local_batch_open")
        try:
            yield self
        finally:
            self.events.append("local_batch_closed_and_reset")
            self.runtime_receipt = {
                "services_restored_to_initial_state": not self.fail_reset,
                "final_database_snapshot_equal": not self.fail_reset,
                "final_physical_filestore_equal": not self.fail_reset,
                "elapsed_seconds": 60.0,
                "provider_invoice_usd": None,
            }

    def run_case(self, task, index, sampler, directory):
        self.cases.append(task["task_id"])
        frame_dir = directory / "frames"
        frame_dir.mkdir(mode=0o700)
        png = io.BytesIO()
        Image.new("RGB", (64, 48), (80, 100, 120)).save(png, "PNG")
        frame_path = frame_dir / "step-000.png"
        frame_path.write_bytes(png.getvalue())
        frame_path.chmod(0o600)
        frame_sha = digest(png.getvalue())
        observation = make_observation(
            task_id=task["task_id"],
            task_binding_sha256=task["package_sha256"],
            instruction="Repair the visible synthetic selection record.",
            step=0, screenshot_bytes=png.getvalue())
        sampled = sampler.sample(observation, task_index=index, step=0,
                                 task_dir=directory)
        assert sampled["status"] == "completed"
        frames = private_json(directory / "frames.private.json", [{
            "path": "frames/step-000.png", "sha256": frame_sha,
        }])
        saved = private_json(directory / "saved-state.private.json", {
            "schema": "envloop-odoo-selection-saved-sql-v1",
            "task_id": task["task_id"],
            "business_snapshot": {"synthetic_saved": index % 2 == 0},
            "gui_reload_frame_sha256": frame_sha,
            "termination": "model_finish",
        })
        verified = private_json(directory / "verifier.private.json", {
            "schema": "envloop-odoo-selection-verifier-v1",
            "task_id": task["task_id"],
            "independent_select_only": True,
            "verifier_source_sha256": selection.verifier_sha256(),
            "score": int(index % 2 == 0),
        })
        reset = private_json(directory / "reset.private.json", {
            "schema": "envloop-odoo-selection-reset-v1",
            "task_id": task["task_id"],
            "pre_database_filestore_exact": True,
            "post_database_filestore_exact": True,
            "baseline_semantic_sha256": "a" * 64,
            "restored_semantic_sha256": "a" * 64,
        })
        journal = directory / "sampling-journal" / "requests.sqlite3"
        journal.parent.mkdir(mode=0o700)
        journal.write_bytes(b"fake durable sampler journal")
        journal.chmod(0o600)
        usage = private_json(directory / "usage.private.json", {
            "schema": "envloop-odoo-selection-task-usage-v1",
            "task_id": task["task_id"],
            "samples": [{"usage": sampled["rendered_usage"],
                         "paid_attempt_id": sampled["paid_attempt_id"]}],
            "rendered_input_tokens": 100, "sampled_output_tokens": 10,
            "provider_billed_usd": None,
            "sampling_journal_sha256": digest(journal.read_bytes()),
        })
        actions = private_json(directory / "actions.private.json", [{
            "synthetic_action": "finish", "frame_sha256": frame_sha}])
        if self.tamper_artifact_at == index:
            (directory / "saved-state.private.json").write_bytes(b"tampered")
        return {"task_id": task["task_id"],
                "package_sha256": task["package_sha256"],
                "score": int(index % 2 == 0),
                "saved_state_sha256": saved,
                "verifier_receipt_sha256": verified,
                "reset_receipt_sha256": reset,
                "actions_sha256": actions,
                "frames_sha256": frames,
                "frame_count": 1,
                "usage_sha256": usage,
                "sample_count": 1,
                "sample_paid_attempt_ids": [sampled["paid_attempt_id"]],
                "rendered_input_tokens": 100,
                "sampled_output_tokens": 10,
                "termination": "model_finish"}


class FakePaidDispatch:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def __call__(self, *, attempt_id, category, work, request,
                 reserve_usd, resource_reservation, provider):
        self.calls.append({"attempt_id": attempt_id, "category": category,
                           "reserve_usd": reserve_usd,
                           "resources": resource_reservation,
                           "request": request})
        self.events.append("paid_" + category + "_reserved")
        try:
            result = provider(request)
        except Exception:
            self.events.append("paid_" + category + "_uncertain")
            raise campaign.DispatchError(
                "paid_response_uncertain_reconcile_before_retry") from None
        self.calls[-1]["result"] = result
        return {"attempt_id": attempt_id, "result": result,
                "result_sha256": digest(selection._canonical(result)),
                "billing_state": "awaiting_provider_usage_reconciliation"}


class SelectionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="odoo-selection-fake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        self.out = self.work / "selection-attempt-001"
        self.checkpoint = "tinker://fake/sampler_weights/ckpt-1"
        tasks = [{"task_id": f"selection-synthetic-{index:03d}",
                  "package_sha256": digest(f"package-{index}".encode())}
                 for index in range(1, 21)]
        self.started = {
            "attempt_id": "odoo-selection-001",
            "checkpoint_path_sha256": digest(self.checkpoint.encode()),
            "selection_tasks": tasks,
            "selection_identities_sha256": digest(selection._canonical(tasks)),
            "task_count": 20,
        }
        self.student = {
            "schema": "cua-full-study-qwen-sft-training-v1",
            "model": "Qwen/Qwen3.8-27B",
            "action_profile": "scale-action-profile-v0.6.6",
            "sample_max_tokens": 48, "seed": 23,
            "prefill_usd_per_million_tokens": "0.50",
            "sample_usd_per_million_tokens": "1.00",
            "billing_multiplier_upper": "2.0",
        }
        self.student_raw = final.json_bytes(self.student)
        self.student_sha = digest(self.student_raw)
        self.events = []
        self.environment = FakeEnvironment(self.events)
        self.paid = FakePaidDispatch(self.events)
        self.sampler = FakeSampler(self.events)
        self.worker = selection.OdooSelectionWorker(
            worker_dir=self.root / "selection",
            private_output_root=self.work)

    def run_fake(self):
        with patch.object(self.worker, "_require_freeze", return_value={
                "hourly_usd_upper": "1.00"}), \
             patch.object(self.worker, "_preflight_renderer"), \
             patch.object(self.worker, "environment", self.environment), \
             patch.object(self.worker, "_make_sampler",
                          return_value=self.sampler):
            return self.worker.run_selection(
                started=self.started, checkpoint_path=self.checkpoint,
                student_config_raw=self.student_raw,
                student_config_sha256=self.student_sha,
                out_dir=self.out, dispatch_paid=self.paid)

    def test_default_refuses_before_any_cost_or_environment(self):
        with self.assertRaisesRegex(selection.SelectionWorkerError,
                                    "requires_real_six_cell_freeze"):
            self.worker.run_selection(
                started=self.started, checkpoint_path=self.checkpoint,
                student_config_raw=self.student_raw,
                student_config_sha256=self.student_sha,
                out_dir=self.out, dispatch_paid=self.paid)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.paid.calls, [])
        self.assertEqual(self.events, [])

    def test_exact_twenty_results_and_per_sample_paid_attempts(self):
        outcome = self.run_fake()
        self.assertEqual(outcome["status"], "scored")
        self.assertEqual([call["category"] for call in self.paid.calls],
                         ["storage_application"] + ["tinker"] * 21)
        self.assertEqual([call["resources"] for call in self.paid.calls],
                         [{}] * 22)
        self.assertTrue(all(call["result"].get("usage") ==
                            {"provider_billed_tokens": None}
                            for call in self.paid.calls[1:]))
        self.assertEqual([call["result"].get("rendered_usage", {}).get(
            "input_tokens") for call in self.paid.calls[2:]], [100] * 20)
        self.assertEqual(self.events[:6], [
            "private_selection_manifest_checked",
            "paid_storage_application_reserved", "local_capacity_reserved",
            "paid_tinker_reserved", "fake_sampler_open",
            "local_batch_open",
        ])
        self.assertEqual(len(self.environment.cases), 20)
        self.assertEqual(self.sampler.calls, 20)
        self.assertEqual(len(outcome["paid_attempt_ids"]), 22)
        paid_projection = paid_coverage.validate(
            cell_id="odoo-community",
            attempt_id=self.started["attempt_id"],
            checkpoint_sha256=self.started["checkpoint_path_sha256"],
            selection_tasks=self.started["selection_tasks"],
            selection_identities_sha256=self.started[
                "selection_identities_sha256"],
            paid_calls=[{
                "attempt_id": call["attempt_id"],
                "category": call["category"],
                "request": call["request"],
                "result_present": "result" in call,
                "result_status": call.get("result", {}).get("status"),
            } for call in self.paid.calls],
            related_paid_attempt_ids=set(outcome["paid_attempt_ids"]))
        self.assertEqual(paid_projection["sample_paid_attempt_count"], 20)
        self.assertEqual(outcome["task_ledger_path"], str(self.out /
                         "task-ledger.private.json"))
        self.assertEqual(outcome["task_ledger_sha256"], digest((self.out /
                         "task-ledger.private.json").read_bytes()))
        ledger = json.loads((self.out /
                             "task-ledger.private.json").read_bytes())
        self.assertEqual(len(ledger["rows"]), 20)
        self.assertTrue(all(row["checkpoint_sha256"] ==
                            self.started["checkpoint_path_sha256"]
                            for row in ledger["rows"]))
        self.assertTrue(all(len(row["sample_paid_attempt_ids"]) == 1
                            for row in ledger["rows"]))
        self.assertEqual(ledger["paid_attempt_ids"],
                         outcome["paid_attempt_ids"])
        self.assertIsNone(outcome["provider_invoice_usd"])
        result = outcome["result"]
        self.assertEqual(set(result), {"schema", "cell_id",
                                        "checkpoint_sha256",
                                        "evaluator_isolated", "tasks"})
        self.assertEqual([row["task_id"] for row in result["tasks"]],
                         [row["task_id"] for row in
                          self.started["selection_tasks"]])
        self.assertEqual(sum(row["score"] for row in result["tasks"]), 10)
        fake_session = type("SelectionView", (), {
            "intent": {"cell_id": "odoo-community"},
            "views": {"selection": tuple(self.started["selection_tasks"])}
        })()
        scores = campaign.CampaignSession._selection_result(
            fake_session, result,
            checkpoint_sha256=self.started["checkpoint_path_sha256"])
        self.assertEqual(sum(scores.values()), 10)
        usage = json.loads((self.out / "usage.private.json").read_text())
        self.assertEqual(usage["rendered_input_tokens"], 2000)
        self.assertEqual(usage["sampled_output_tokens"], 200)
        self.assertIsNone(usage["tinker_provider_billed_usd"])
        self.assertIsNone(usage["local_provider_invoice_usd"])
        timeouts = json.loads((self.out / "timeouts.private.json").read_text())
        self.assertEqual(timeouts["timeout_or_uncertain_count"], 0)
        self.assertEqual((self.out / "selection-result.private.json")
                         .stat().st_mode & 0o077, 0)

    def test_uncertain_sample_is_invalid_not_model_zero(self):
        self.sampler.fail_at_task = 3
        outcome = self.run_fake()
        self.assertEqual(outcome["status"], "invalid")
        self.assertEqual(outcome["failure_type"], "provider")
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue((self.out / "invalid.private.json").exists())
        self.assertEqual(len(self.environment.cases), 3)
        receipt = json.loads((self.out / "timeouts.private.json").read_text())
        self.assertEqual(receipt["timeout_or_uncertain_count"], 1)
        self.assertTrue((self.out / "local-runtime.private.json").is_file())
        invalid = json.loads((self.out / "invalid.private.json").read_text())
        self.assertFalse(invalid["automatic_replay_authorized"])
        self.assertEqual(invalid["paid_attempt_ids_declared"], [
            "odoo-selection-001-local-service",
            "odoo-selection-001-tinker-setup",
            "odoo-selection-001-sample-01-000",
            "odoo-selection-001-sample-02-000",
            "odoo-selection-001-sample-03-000"])

    def test_uncertain_local_reset_is_environment_invalid(self):
        self.environment.fail_reset = True
        outcome = self.run_fake()
        self.assertEqual(outcome["status"], "invalid")
        self.assertEqual(outcome["failure_type"], "environment")
        self.assertFalse((self.out / "selection-result.private.json").exists())

    def test_changed_saved_state_is_invalid_before_result_projection(self):
        self.environment.tamper_artifact_at = 2
        outcome = self.run_fake()
        self.assertEqual(outcome["status"], "invalid")
        self.assertEqual(outcome["failure_type"], "environment")
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue((self.out / "invalid.private.json").is_file())

    def test_real_backend_manifest_is_selection_only_without_docker(self):
        private = self.root / "selection" / "private"
        private.mkdir(parents=True, mode=0o700)
        tasks = self.started["selection_tasks"]
        private_json(private / "task_set_manifest.json", {
            "train": [{"task_id": "train-synthetic-001",
                       "package_sha256": "a" * 64}],
            "selection": tasks,
            "official": [{"task_id": "hidden-synthetic-001",
                          "package_sha256": "b" * 64}],
        })
        families = ("purchase", "inventory", "sales", "crm")
        cases = {family: [] for family in families}
        for index, task in enumerate(tasks):
            cases[families[index % 4]].append({
                "id": task["task_id"], "prompt": "Synthetic selection."})
        private_json(private / "partition_cases.json", {"cases": cases})
        private_json(private / "actor_credentials.json", {
            "synthetic": True})
        with patch.object(self.worker.environment, "_module_boundary",
                          return_value=(SimpleNamespace(PRIVATE=private),
                                        None, None, None, None)):
            self.worker.environment.validate_tasks(tasks)
            self.assertEqual(len(self.worker.environment._cases), 20)
            changed = [dict(row) for row in tasks]
            changed[0]["package_sha256"] = "f" * 64
            with self.assertRaisesRegex(selection.SelectionWorkerError,
                                        "selection_private_manifest_mismatch"):
                self.worker.environment.validate_tasks(changed)

    def test_real_case_evaluator_path_uses_rendered_not_billed_usage(self):
        task = self.started["selection_tasks"][0]
        private = self.root / "selection" / "private"
        private.mkdir(parents=True, mode=0o700)
        private_json(private / "checkpoint_receipt.json", {
            "db_sha256": "a" * 64, "filestore_sha256": "b" * 64})
        private_json(private / "actor_credentials.json", {
            "login": "synthetic-actor", "password": "synthetic-only"})
        calls = {"score": 0, "snapshot": 0, "restore": 0}

        def score(_case):
            calls["score"] += 1
            return ({"reward": 0.0, "checks_passed": False,
                     "difference_codes": ["target_missing"]}
                    if calls["score"] == 1 else
                    {"reward": 1.0, "checks_passed": True,
                     "difference_codes": []})

        def snapshot():
            calls["snapshot"] += 1
            return ({"state": "saved"} if calls["snapshot"] == 2
                    else {"state": "baseline"})

        def restore():
            calls["restore"] += 1
            return {"business_snapshot_equal": True,
                    "physical_filestore_equal_before_web_restart": True}

        png = io.BytesIO()
        Image.new("RGB", (160, 120), (80, 100, 120)).save(png, "PNG")

        class Page:
            url = "http://127.0.0.1:8093/odoo/purchase"
            viewport_size = selection.VIEWPORT
            def goto(self, url): self.url = url
            def locator(self, _selector):
                return SimpleNamespace(wait_for=lambda: None)
            def screenshot(self, **_kwargs): return png.getvalue()
            def reload(self, **_kwargs): return None

        class Browser:
            def __init__(self): self.page = Page()
            def new_page(self, **_kwargs): return self.page
            def close(self): return None

        class Playwright:
            def __enter__(self):
                self.chromium = SimpleNamespace(
                    launch=lambda **_kwargs: Browser())
                return self
            def __exit__(self, *_args): return False

        class Adapter:
            def __init__(self, page, **_kwargs):
                self.finished = False
            def observe_for_model(self, *, memory):
                observation = make_observation(
                    task_id=task["task_id"],
                    task_binding_sha256=task["package_sha256"],
                    instruction="Synthetic selection.", step=0,
                    screenshot_bytes=png.getvalue(), memory=memory)
                return observation, selection.output_v066.render_for_model(
                    observation)
            def dispatch(self, action):
                self.finished = action["type"] == "finish"
                return {"finished": self.finished,
                        "public_contract_receipt": {"type": "finish"}}

        class Sampler:
            def sample(self, _observation, *, task_index, step, task_dir):
                journal = task_dir / "sampling-journal" / "requests.sqlite3"
                journal.parent.mkdir(mode=0o700)
                journal.write_bytes(b"synthetic journal")
                journal.chmod(0o600)
                return {"status": "completed", "text": '{"type":"finish"}',
                        "rendered_usage": {"input_tokens": 100,
                                           "output_tokens": 10},
                        "usage": {"provider_billed_tokens": None},
                        "paid_attempt_id": "odoo-selection-001-sample-01-000",
                        "request_id": "synthetic-request",
                        "error_subtype": None}

        factory = SimpleNamespace(PRIVATE=private,
                                  local_config=lambda: {"ODOO_PORT": "8093"})
        gui = SimpleNamespace(browser_login=lambda *_args: None)
        reset = SimpleNamespace(restore=restore)
        verify = SimpleNamespace(score=score, snapshot=snapshot)
        self.worker.environment._cases = {
            task["task_id"]: ("purchase", {"id": task["task_id"],
                                            "prompt": "Synthetic selection."})}
        self.worker.environment._package_by_id = {
            task["task_id"]: task["package_sha256"]}
        task_dir = self.work / "task-001"
        task_dir.mkdir(mode=0o700)
        with patch.object(self.worker.environment, "_module_boundary",
                          return_value=(factory, gui, reset, verify, None)), \
             patch("playwright.sync_api.sync_playwright",
                   return_value=Playwright()), \
             patch.object(selection, "OdooV066TrainAdapter", Adapter):
            row = self.worker.environment.run_case(
                task, 1, Sampler(), task_dir)
        selection._audit_task_artifacts(task_dir, task, row)
        self.assertEqual(row["score"], 1)
        self.assertEqual(row["rendered_input_tokens"], 100)
        self.assertEqual(row["sampled_output_tokens"], 10)
        self.assertEqual(row["sample_paid_attempt_ids"],
                         ["odoo-selection-001-sample-01-000"])
        self.assertEqual(calls, {"score": 2, "snapshot": 3,
                                 "restore": 2})

    def test_checkpoint_task_and_training_config_tamper_precede_paid_work(self):
        for started, checkpoint, raw, sha in (
            (self.started, self.checkpoint + "-other",
             self.student_raw, self.student_sha),
            ({**self.started, "selection_tasks":
              self.started["selection_tasks"][:-1]},
             self.checkpoint, self.student_raw, self.student_sha),
            (self.started, self.checkpoint,
             self.student_raw.replace(b'"seed": 23', b'"seed": 24'),
             self.student_sha),
        ):
            with self.subTest(checkpoint=checkpoint, count=len(started[
                    "selection_tasks"]), changed=raw != self.student_raw):
                with self.assertRaises(selection.SelectionWorkerError):
                    self.worker.run_selection(
                        started=started, checkpoint_path=checkpoint,
                        student_config_raw=raw,
                        student_config_sha256=sha,
                        out_dir=self.out, dispatch_paid=self.paid)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.paid.calls, [])

    def test_nominal_local_authority_never_claims_invoice(self):
        authority = {
            "schema": selection.LOCAL_COST_SCHEMA,
            "cell_id": "odoo-community",
            "basis": "nominal_local_opportunity_cost_upper",
            "hourly_usd_upper": "1.00",
            "provider_invoice_usd": None,
            "lease_seconds": selection.LOCAL_LEASE_SECONDS,
        }
        path = self.work / "cost-authority.private.json"
        authority_sha = private_json(path, authority)
        parsed = selection._cost_authority(path, authority_sha)
        self.assertEqual(parsed, authority)
        self.assertEqual(selection.local_upper_reserve_usd(parsed),
                         "4.500000000")
        self.assertGreater(float(selection.tinker_upper_reserve_usd(
            self.student)), 0)
        path.chmod(0o644)
        with self.assertRaisesRegex(selection.SelectionWorkerError,
                                    "local_cost_authority_missing"):
            selection._cost_authority(path, authority_sha)


if __name__ == "__main__":
    unittest.main()
