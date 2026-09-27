"""No-Docker, fake-provider checks for the 20-task GitLab selection worker."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager, nullcontext
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_selection_paid_coverage_v1 as paid_coverage
from cursibench.scale_action_contract import make_observation
from gitlab_world import (bootstrap, factory, operators, reset, runtime,
                          selection_worker_v066 as selection)
from tests.test_gitlab_v066_train_adapter import FakePage, frame as browser_frame


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def png(color: str = "white") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (128, 96), color).save(output, "PNG")
    return output.getvalue()


class FakeVision:
    identity = {"model": selection.MODEL,
                "renderer": selection.RENDERER,
                "image_processor": selection.PROCESSOR}

    def render(self, image, instruction, visible_text):
        assert image.size == (128, 96)
        assert "scale-action-output-v0.6.6" in instruction
        assert visible_text
        return SimpleNamespace(length=40), {
            "input_tokens": 40, "image_tokens": 12,
            "chunk_types": ["TextChunk", "ImageChunk"]}

    def decode(self, _tokens):
        return '{"type":"finish"}'


class FakeSelectionSession:
    def __init__(self, identity):
        self.identity = identity
        self.task = {**identity,
                     "visible_instruction": "Complete this selection record."}
        self.baseline_semantic = {
            "business_snapshot": {"business_sha256": "a" * 64},
            "seed_lowerdirs_sha256": "b" * 64}
        self.reset_semantic = None
        self.pre_restore_exact = True
        self.post_restore_exact = False
        self.environment_terminated = False
        self.step = 0
        self.latest = None
        self.finished = False
        self.stale_after_sample = False
        self.dispatches = []
        self.reward = 1.0

    def observe(self, *, memory):
        self.latest = make_observation(
            task_id=self.identity["task_id"],
            task_binding_sha256=self.identity["package_sha256"],
            instruction=self.task["visible_instruction"],
            step=self.step, screenshot_bytes=png(), memory=memory,
            previous_action_result=(None if self.step == 0 else
                                    {"status": "applied", "code": "ok"}))
        return self.latest

    def current_frame_id(self):
        return (self.latest.frame_id if self.latest is not None and
                not self.stale_after_sample else "stale")

    def dispatch(self, action):
        if self.current_frame_id() != self.latest.frame_id:
            raise AssertionError("stale frame physically dispatched")
        self.dispatches.append(action["type"])
        self.step += 1
        if action["type"] == "finish":
            self.finished = True

    def read_saved_state(self):
        return {
            "business_snapshot": {"business_sha256": "c" * 64},
            "independent_score": {
                "reward": self.reward,
                "checks_passed": self.reward == 1.0,
                "difference_codes": [] if self.reward == 1.0 else
                                    ["target_or_no_regression_mismatch"]},
            "gui_reload_frame_sha256": sha(png()),
            "original_gitlab_ce": True,
            "postgresql_and_git_readback": True,
            "model_finished": self.finished,
        }


class FakeBackend:
    def __init__(self):
        self.sessions = []
        self.fail_reset_on = None

    @contextmanager
    def open(self, identity):
        active = FakeSelectionSession(identity)
        self.sessions.append(active)
        try:
            yield active
        finally:
            active.reset_semantic = dict(active.baseline_semantic)
            active.post_restore_exact = (
                self.fail_reset_on != len(self.sessions))
            active.environment_terminated = True


class FakeCampaign:
    def __init__(self, root: Path, tasks: list[dict], started: dict):
        self.study = SimpleNamespace(
            repo_root=root, plan={"study_id": "synthetic-full-study"})
        self.intent = {"cell_id": "gitlab", "researcher_id": "astra",
                       "storage_application_usd_cap": "10"}
        self.views = {"selection": tasks}
        self.started = started
        self.calls = []

    def dispatch_paid(self, *, attempt_id, category, work, request,
                      reserve_usd, resource_reservation, provider):
        self.calls.append({"attempt_id": attempt_id, "category": category,
                           "work": work, "request": request,
                           "reserve_usd": reserve_usd,
                           "resource_reservation": resource_reservation})
        result = provider(request)
        return {"result": result,
                "result_sha256": sha(selection._canonical(result)),
                "billing_state": "awaiting_provider_usage_reconciliation"}


class SelectionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gitlab-selection-fake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        self.out = self.work / "selection-001"
        self.tasks = [
            {"task_id": f"synthetic-selection-{index:03d}",
             "package_sha256": f"{index:064x}"}
            for index in range(1, 21)]
        self.started = {
            "attempt_id": "selection-001",
            "checkpoint_path_sha256": "a" * 64,
            "selection_tasks": self.tasks,
            "selection_identities_sha256": sha(
                selection._canonical(self.tasks)),
            "task_count": 20,
        }
        self.session = FakeCampaign(self.root, self.tasks, self.started)
        self.worker = selection.GitLabSelectionWorker()
        self.backend = FakeBackend()
        self.worker.backend = self.backend
        self.policy = {"seed": 23, "temperature": 0.0,
                       "max_output_tokens": 64,
                       "max_actions_per_task": 2,
                       "max_wall_seconds_per_task": 720}
        self.training = {
            "max_supervised_tokens": 32768,
            "prefill_usd_per_million_tokens": "1",
            "sample_usd_per_million_tokens": "2",
            "billing_multiplier_upper": "1"}
        self.model_text = '{"type":"finish"}'

    def provider(self, request, _prompt):
        return {
            "schema": "envloop-gitlab-v066-selection-sampler-result-v1",
            "status": "completed",
            "reported_model": selection.MODEL,
            "checkpoint_path_sha256": self.started[
                "checkpoint_path_sha256"],
            "text": self.model_text,
            "stop_reason": "stop",
            "elapsed_seconds": 0.01,
            "usage": {"input_tokens": request["input_tokens"],
                      "output_tokens": 5,
                      "image_tokens": request["image_tokens"],
                      "prompt_cache_hit_tokens": None,
                      "provider_billed_tokens": None,
                      "basis":
                      "rendered_input_and_returned_output_not_invoice"},
        }

    def run_fake(self, provider=None):
        with patch.object(self.worker, "_require_frozen",
                          return_value=({}, {})), \
             patch.object(self.worker, "_resolve_checkpoint_path",
                          return_value="tinker://fake/sampler_weights/selected"), \
             patch.object(self.worker, "_policy",
                          return_value=(self.training, self.policy,
                                        Decimal("0.5"))), \
             patch.object(self.worker, "_load_vision",
                          return_value=FakeVision()):
            return self.worker.run_attempt(
                session=self.session, started=self.started,
                out_dir=self.out,
                sampler_provider=provider or self.provider)

    def test_default_refuses_before_output_paid_call_or_browser(self):
        with self.assertRaisesRegex(selection.GitLabSelectionError,
                                    "requires_real_six_cell_freeze"):
            self.worker.run_attempt(
                session=self.session, started=self.started,
                out_dir=self.out, sampler_provider=self.provider)
        self.assertEqual(self.session.calls, [])
        self.assertEqual(self.backend.sessions, [])
        self.assertFalse(self.out.exists())

    def test_complete_twenty_task_fake_selection_matches_dispatcher_schema(self):
        result = self.run_fake()
        rows = result["result"]["tasks"]
        self.assertEqual(len(rows), 20)
        self.assertEqual([row["task_id"] for row in rows],
                         [task["task_id"] for task in self.tasks])
        self.assertEqual(sum(row["score"] for row in rows), 20)
        self.assertEqual(len(result["paid_attempt_ids"]), 40)
        paid_projection = paid_coverage.validate(
            cell_id="gitlab", attempt_id=self.started["attempt_id"],
            checkpoint_sha256=self.started["checkpoint_path_sha256"],
            selection_tasks=self.started["selection_tasks"],
            selection_identities_sha256=self.started[
                "selection_identities_sha256"],
            paid_calls=[{
                "attempt_id": call["attempt_id"],
                "category": call["category"],
                "request": call["request"],
                "result_present": True,
            } for call in self.session.calls],
            related_paid_attempt_ids=set(result["paid_attempt_ids"]))
        self.assertEqual(paid_projection["sample_paid_attempt_count"], 20)
        self.assertEqual({row["category"] for row in self.session.calls},
                         {"tinker", "storage_application"})
        self.assertEqual(sum(row["category"] == "storage_application"
                             for row in self.session.calls), 20)
        self.assertTrue(all(row["resource_reservation"] == {}
                            for row in self.session.calls))
        by_id = {row["task_id"]: row["package_sha256"]
                 for row in self.tasks}
        for paid in self.session.calls:
            for field in ("work", "request"):
                bound = paid[field]
                self.assertEqual(bound["package_sha256"],
                                 by_id[bound["task_id"]])
                self.assertEqual(bound["checkpoint_path_sha256"],
                                 self.started["checkpoint_path_sha256"])
        for index in range(1, 21):
            receipt = json.loads((self.out / f"task-{index:03d}" /
                                  "task.private.json").read_text())
            self.assertEqual(len(receipt["paid_attempt_ids"]), 2)
            self.assertIn("-app-", receipt["paid_attempt_ids"][0])
            self.assertIn("-sample-", receipt["paid_attempt_ids"][1])
        dummy = SimpleNamespace(intent={"cell_id": "gitlab"},
                                views={"selection": self.tasks})
        validated = campaign.CampaignSession._selection_result(
            dummy, result["result"],
            checkpoint_sha256=self.started["checkpoint_path_sha256"])
        self.assertEqual(sum(validated.values()), 20)
        self.assertTrue(all(row.stat().st_mode & 0o077 == 0
                            for row in self.out.rglob("*.json")))
        batch = json.loads(Path(result["batch_receipt_path"]).read_text())
        self.assertFalse(batch["tinker_usage_reconciled"])
        self.assertFalse(batch["external_provider_invoice_present"])
        ledger_path = Path(result["task_ledger_path"])
        self.assertEqual(sha(ledger_path.read_bytes()),
                         result["task_ledger_sha256"])
        ledger = json.loads(ledger_path.read_text())
        self.assertEqual(ledger["schema"],
                         "envloop-gitlab-v066-selection-paid-task-ledger-v1")
        self.assertEqual(ledger["task_count"], 20)
        self.assertEqual([row["task_id"] for row in ledger["tasks"]],
                         [row["task_id"] for row in self.tasks])
        self.assertTrue(all(len(row["qwen_paid_attempt_ids"]) == 1
                            for row in ledger["tasks"]))
        self.assertEqual(batch["task_ledger_ref"],
                         {"path": ledger_path.name,
                          "sha256": result["task_ledger_sha256"]})

    def test_invalid_model_output_scores_zero_with_saved_state_and_reset(self):
        self.model_text = "not JSON"
        def unsolved_provider(request, prompt):
            self.backend.sessions[-1].reward = 0.0
            return self.provider(request, prompt)
        result = self.run_fake(provider=unsolved_provider)
        self.assertTrue(all(row["score"] == 0
                            for row in result["result"]["tasks"]))
        self.assertEqual(len(result["paid_attempt_ids"]), 40)
        trace = json.loads((self.out / "task-001" /
                            "actions.private.json").read_text())
        self.assertEqual(trace[0]["model_error_code"], "invalid_action_json")
        self.assertTrue(self.backend.sessions[0].post_restore_exact)

    def test_tampered_private_verifier_cannot_pass_task_readback(self):
        result = self.run_fake()
        ledger = json.loads(Path(result["task_ledger_path"]).read_text())
        first = ledger["tasks"][0]
        item = {"result_row": result["result"]["tasks"][0],
                "paid_attempt_ids": [first["application_paid_attempt_id"],
                                     *first["qwen_paid_attempt_ids"]],
                "task_receipt_ref": first["task_receipt_ref"]}
        verifier = self.out / "task-001" / "verifier.private.json"
        verifier.write_bytes(verifier.read_bytes() + b"\n")
        with self.assertRaisesRegex(selection.GitLabSelectionError,
                                    "evidence_bytes_changed"):
            self.worker._verify_task_receipt(self.out, item)

    def test_actor_wall_timeout_scores_zero_after_real_sample(self):
        import time
        self.policy["max_wall_seconds_per_task"] = 0.005
        def slow_provider(request, prompt):
            self.backend.sessions[-1].reward = 0.0
            time.sleep(0.02)
            return self.provider(request, prompt)
        result = self.run_fake(provider=slow_provider)
        self.assertTrue(all(row["score"] == 0
                            for row in result["result"]["tasks"]))
        cost = json.loads((self.out / "task-001" /
                           "cost.private.json").read_text())
        self.assertEqual(cost["timeout_subtype"], "task_wall_timeout")
        self.assertEqual(len(result["paid_attempt_ids"]), 40)

    def test_persisted_success_is_scored_even_without_finish_signal(self):
        self.model_text = "not JSON"
        result = self.run_fake()
        self.assertTrue(all(row["score"] == 1
                            for row in result["result"]["tasks"]))
        trace = json.loads((self.out / "task-001" /
                            "actions.private.json").read_text())
        self.assertEqual(trace[0]["model_error_code"], "invalid_action_json")
        verifier = json.loads((self.out / "task-001" /
                               "verifier.private.json").read_text())
        self.assertEqual(verifier["model_outcome"], "model_invalid_action")
        self.assertEqual(verifier["score"], 1)

    def test_invented_ref_is_model_failure_when_physical_frame_is_current(self):
        self.model_text = '{"type":"click","target":{"ref":"invented"}}'
        def unsolved_provider(request, prompt):
            self.backend.sessions[-1].reward = 0.0
            return self.provider(request, prompt)
        result = self.run_fake(provider=unsolved_provider)
        self.assertTrue(all(row["score"] == 0
                            for row in result["result"]["tasks"]))
        trace = json.loads((self.out / "task-001" /
                            "actions.private.json").read_text())
        self.assertEqual(trace[0]["model_error_code"], "invalid_model_ref")
        self.assertEqual(self.backend.sessions[0].dispatches, [])

    def test_no_tinker_sample_for_a_task_invalidates_whole_attempt(self):
        self.policy["max_wall_seconds_per_task"] = 1e-12
        with self.assertRaisesRegex(selection.GitLabSelectionError,
                                    "no_tinker_paid_attempt"):
            self.run_fake()
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue((self.out / "failure.private.json").exists())
        self.assertTrue(self.backend.sessions[0].post_restore_exact)

    def test_stale_after_paid_call_preserves_failure_without_scored_result(self):
        original = self.provider
        def stale_provider(request, prompt):
            self.backend.sessions[-1].stale_after_sample = True
            return original(request, prompt)
        with patch.object(self.worker, "_require_frozen",
                          return_value=({}, {})), \
             patch.object(self.worker, "_resolve_checkpoint_path",
                          return_value="tinker://fake/sampler_weights/selected"), \
             patch.object(self.worker, "_policy",
                          return_value=(self.training, self.policy,
                                        Decimal("0.5"))), \
             patch.object(self.worker, "_load_vision",
                          return_value=FakeVision()):
            with self.assertRaisesRegex(selection.GitLabSelectionError,
                                        "frame_changed_after_paid_sample"):
                self.worker.run_attempt(
                    session=self.session, started=self.started,
                    out_dir=self.out, sampler_provider=stale_provider)
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue((self.out / "failure.private.json").exists())
        self.assertTrue(self.backend.sessions[0].post_restore_exact)
        partial = self.out / "task-001" / "task-failure.private.json"
        self.assertTrue(partial.exists())
        attempt = json.loads(partial.read_text())
        self.assertEqual(len(attempt["attempted_paid_attempt_ids"]), 2)
        self.assertFalse(attempt["automatic_paid_replay_authorized"])

    def test_failed_cold_reset_rejects_whole_selection(self):
        self.backend.fail_reset_on = 1
        with self.assertRaisesRegex(selection.GitLabSelectionError,
                                    "saved_state_or_exact_reset_missing"):
            self.run_fake()
        self.assertFalse((self.out / "selection-result.private.json").exists())
        self.assertTrue((self.out / "failure.private.json").exists())

    def test_private_checkpoint_path_tamper_is_rejected(self):
        self.session.directory = self.work
        checkpoint_path = "tinker://fake/sampler_weights/selected"
        self.started["checkpoint_path_sha256"] = sha(
            checkpoint_path.encode())
        paid = {"checkpoint_path": checkpoint_path,
                "observed_base_model": selection.MODEL}
        path = self.work / "tinker-001.result.private.json"
        path.write_bytes(selection._canonical(paid))
        path.chmod(0o600)
        events = {
            "tinker_checkpoint": [{"data": {
                "paid_attempt_id": "tinker-001",
                "checkpoint_path_sha256":
                    self.started["checkpoint_path_sha256"]}}],
            "paid_result": [{"data": {
                "attempt_id": "tinker-001",
                "result_sha256": sha(path.read_bytes())}}],
        }
        self.session._events = lambda kind: events.get(kind, [])
        resolved = self.worker._resolve_checkpoint_path(
            self.session, self.started["checkpoint_path_sha256"])
        self.assertEqual(resolved, checkpoint_path)
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaises(selection.GitLabSelectionError):
            self.worker._resolve_checkpoint_path(
                self.session, self.started["checkpoint_path_sha256"])

    def test_current_frame_selection_double_click_and_stale_reject(self):
        page = FakePage()
        observed = browser_frame()
        action = selection.output_v066.normalize_model_action(
            '{"type":"double_click","target":{"x":5,"y":6}}',
            observed.observation,
            current_frame_id=observed.observation.frame_id)
        asyncio.run(selection._dispatch_gui(page, observed, action))
        self.assertEqual(page.events, [("dblclick", 5, 6)])
        page.events.clear()
        page.frame = png("black")
        with self.assertRaisesRegex(selection.ContractError, "stale_frame"):
            asyncio.run(selection._dispatch_gui(page, observed, action))
        self.assertEqual(page.events, [])

    def test_frozen_selection_view_rejects_changed_or_duplicate_ids(self):
        self.worker.enable_live = True
        self.session.study.plan["cells"] = [{
            "cell_id": "gitlab", "matched_bindings": {
                "runtime": self.worker.runtime_sha256,
                "verifier": self.worker.verifier_sha256}}]
        self.session._events = lambda kind: ([{"data": {
            "attempt_id": self.started["attempt_id"],
            "selection_identities_sha256":
                self.started["selection_identities_sha256"],
            "checkpoint_path_sha256":
                self.started["checkpoint_path_sha256"]}}]
            if kind == "selection_started" else [])
        ratification = {"cell_profiles": {"gitlab": {
            "adapter_sha256": self.worker.adapter_sha256}}}
        with patch.object(selection.teacher, "_frozen_session",
                          return_value=("gitlab", ratification)):
            cell, _ = self.worker._require_frozen(
                self.session, self.started)
            self.assertEqual(cell["cell_id"], "gitlab")
            altered = {**self.started,
                       "selection_tasks": [*self.tasks[:-1], self.tasks[0]]}
            with self.assertRaisesRegex(selection.GitLabSelectionError,
                                        "selection_start_or_view_changed"):
                self.worker._require_frozen(self.session, altered)

    def test_real_backend_requires_exact_private_selection_identity(self):
        private = self.root / "gitlab-private"
        private.mkdir(mode=0o700)
        def write(name, value):
            path = private / name
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            return path
        world = factory.build_world("private-development-fixture-seed-001")
        project = next(row for row in world["projects"]
                       if row["partition"] == "selection")
        original = next(row for row in world["tasks"]
                        if row["project_family"] == project["full_path"])
        bound = {"task_id": original["task_id"],
                 "package_sha256": factory.sha256(factory.canonical(original))}
        manifest = write("world-private.json", {"schema": factory.SCHEMA})
        progress = write("bootstrap-progress.json", {
            "groups": {project["group_path"]: 17}})
        credentials = write("operator-credentials-private.json", {
            partition: {"username": "synthetic", "password": "synthetic"}
            for partition in ("train", "selection",
                              "final_candidate_unsealed")})
        receipt = write("operator-bootstrap-private.json", {
            "identities": {"selection": {"group_id": 17}},
            "root_admin_is_actor": False})
        write("baseline-persisted-state.json", {})
        state = write("cow-reset-state.json", {})
        backend = selection.RealGitLabSelectionBackend()
        with patch.object(runtime, "PRIVATE", private), \
             patch.object(bootstrap, "WORLD_FILE", manifest), \
             patch.object(bootstrap, "PROGRESS_FILE", progress), \
             patch.object(operators, "CREDENTIALS", credentials), \
             patch.object(operators, "RECEIPT", receipt), \
             patch.object(reset, "STATE_FILE", state), \
             patch.object(bootstrap, "world", return_value=world):
            task, source, actor, view = backend._load_selection_task(bound)
            self.assertEqual((task["partition"], source["partition"]),
                             ("selection", "selection"))
            self.assertEqual(view["visible_instruction"], original["prompt"])
            self.assertEqual(actor["username"], "synthetic")
            wrong_train = next(row for row in world["tasks"]
                               if row["partition"] == "train")
            for wrong in (
                    {**bound, "package_sha256": "0" * 64},
                    {"task_id": wrong_train["task_id"],
                     "package_sha256":
                        factory.sha256(factory.canonical(wrong_train))}):
                with self.assertRaisesRegex(selection.GitLabSelectionError,
                                            "not_in_private_selection"):
                    backend._load_selection_task(wrong)

    def test_real_backend_two_exact_resets_without_docker(self):
        class FakeLoop:
            def start(self): pass
            def call(self, coroutine, **_kwargs):
                return asyncio.run(coroutine)
            def close(self): pass
        baseline = {"business_sha256": "a" * 64}
        state = {"baseline_business_sha256": "a" * 64,
                 "seed_volume_lowerdirs": {"data": "/frozen/data"}}
        cold = {"cold_reset": True, "same_business_sha256": True}
        proof_before = {"image_id": runtime.IMAGE_ID,
                        "container_id_sha256": "1" * 64}
        proof_after = {"image_id": runtime.IMAGE_ID,
                       "container_id_sha256": "2" * 64}
        backend = selection.RealGitLabSelectionBackend()
        with patch.object(backend, "_load_selection_task",
                          return_value=({}, {"full_path": "train/project"},
                                        {}, {"task_id": "synthetic",
                                             "package_sha256": "a" * 64,
                                             "visible_instruction": "Edit."})), \
             patch.object(backend, "_lease", return_value=nullcontext()), \
             patch.object(reset, "_baseline", return_value=baseline), \
             patch.object(reset, "_state", return_value=state), \
             patch.object(reset, "reset", side_effect=[cold, cold]) as resets, \
             patch.object(selection.verify, "state_snapshot",
                          return_value=baseline), \
             patch.object(runtime, "proof",
                          side_effect=[proof_before, proof_after]), \
             patch.object(selection.oracle, "evaluate_selection_task",
                          return_value={"reward": 0.0}), \
             patch.object(selection.train, "_AsyncLoop", FakeLoop), \
             patch.object(backend, "_start_browser",
                          new=AsyncMock(return_value=(None, None, None,
                                                      FakePage()))), \
             patch.object(backend, "_stop_browser", new=AsyncMock()):
            with backend.open({"task_id": "synthetic",
                               "package_sha256": "a" * 64}) as active:
                self.assertTrue(active.pre_restore_exact)
            self.assertTrue(active.post_restore_exact)
            self.assertTrue(active.environment_terminated)
            self.assertEqual(resets.call_count, 2)

    def test_selected_tinker_sdk_path_is_fake_and_checkpoint_bound(self):
        import tinker
        class FakeFuture:
            def __init__(self, value): self.value = value
            def result(self, timeout):
                assert timeout in (30, 240)
                return self.value
        class FakeSamplingClient:
            def get_base_model(self): return selection.MODEL
            def sample(self, *, prompt, num_samples, sampling_params):
                self.prompt = prompt
                self.params = sampling_params
                self.samples = num_samples
                return FakeFuture(SimpleNamespace(
                    sequences=[SimpleNamespace(tokens=[1, 2],
                                               stop_reason="stop")],
                    prompt_cache_hit_tokens=None))
        class FakeService:
            def __init__(self): self.client = FakeSamplingClient()
            def create_sampling_client(self, *, model_path):
                self.path = model_path
                return self.client
            def close(self, status):
                self.status = status
                return FakeFuture(None)
        service = FakeService()
        vision = FakeVision()
        vision.renderer = SimpleNamespace(get_stop_sequences=lambda: [])
        checkpoint = "tinker://fake/sampler_weights/selected"
        sampler = selection._RealTinkerSampler(
            checkpoint_path=checkpoint,
            checkpoint_sha256=sha(checkpoint.encode()),
            vision=vision, seed=23, temperature=0.0,
            max_output_tokens=64,
            campaign_metadata={"purpose": "synthetic"})
        request = {"input_tokens": 40, "image_tokens": 12}
        with patch.object(tinker, "ServiceClient", return_value=service):
            output = sampler(request, SimpleNamespace(length=40))
            sampler.close(success=True)
        self.assertEqual(service.path, checkpoint)
        self.assertEqual(service.client.samples, 1)
        self.assertEqual(output["text"], '{"type":"finish"}')
        self.assertEqual(output["usage"]["provider_billed_tokens"], None)
        self.assertEqual(service.status, "success")


if __name__ == "__main__":
    unittest.main()
