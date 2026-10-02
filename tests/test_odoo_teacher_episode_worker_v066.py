"""Fake-provider Odoo episode tests; no Docker, model, or hidden task is opened."""

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

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import make_observation
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action
from enterprise_fallback.odoo18 import teacher_episode_worker_v066 as odoo
from native_desktop_factory.v066_final_freeze import source_hashes as common_source_hashes
from tests.test_full_study_teacher_adapter_v1 import (
    FakeSession as FakeCampaignSession, write_private,
)
from tests.test_shared_v066_train_adapters import FakeOdooPage, image


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def frame() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (160, 120), (80, 100, 125)).save(stream, "PNG")
    return stream.getvalue()


class FakeSession(odoo.EpisodeSession):
    def __init__(self, task: dict):
        super().__init__(baseline_semantic={"business": "baseline",
                                            "filestore": "baseline"},
                         pre_restore_exact=True)
        self.task = task
        self.step = 0
        self.latest = None
        self.finished = False
        self.stale_after_sample = False
        self.reward = 1.0
        self.dispatches = []
        self.events = []

    def observe(self, *, memory: str):
        self.latest = make_observation(
            task_id=self.task["task_id"],
            task_binding_sha256=self.task["package_sha256"],
            instruction=self.task["visible_instruction"],
            step=self.step, screenshot_bytes=frame(), memory=memory,
            controls=[{"ref": "c001", "role": "button", "label": "Save",
                       "visible": True, "enabled": True}],
            previous_action_result=(None if self.step == 0 else
                                    {"status": "applied", "code": "ok"}))
        return self.latest

    def current_frame_id(self):
        if self.stale_after_sample:
            return "stale"
        return self.latest.frame_id if self.latest is not None else "stale"

    def dispatch(self, action):
        validate_action(action, self.latest,
                        current_frame_id=self.current_frame_id())
        self.dispatches.append(action["type"])
        self.events.append("physical_gui_dispatch")
        self.step += 1
        if action["type"] == "finish":
            self.finished = True

    def read_saved_state(self):
        if not self.finished:
            raise AssertionError("A fake episode cannot score before finish")
        return {
            "business_snapshot": {"business": "saved"},
            "independent_score": {
                "reward": self.reward,
                "checks_passed": self.reward == 1.0,
                "difference_codes": [] if self.reward == 1.0 else
                                    ["target_not_saved"],
            },
            "gui_reload_frame_sha256": digest(frame()),
            "frozen_filestore_manifest_sha256": "a" * 64,
        }


class FakeBackend:
    def __init__(self):
        self.open_calls = 0
        self.session = None
        self.force_pre_restore_failure = False
        self.force_reset_failure = False

    @contextmanager
    def open(self, task):
        self.open_calls += 1
        self.session = FakeSession(task)
        self.session.pre_restore_exact = not self.force_pre_restore_failure
        try:
            yield self.session
        finally:
            self.session.reset_semantic = dict(self.session.baseline_semantic)
            self.session.post_restore_exact = not self.force_reset_failure
            self.session.environment_terminated = True


class OdooEpisodeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="odoo-teacher-fake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        self.episode = self.work / "episode-001"
        self.episode.mkdir(mode=0o700)
        (self.episode / "frames").mkdir(mode=0o700)
        self.task = {"task_id": "train-synthetic-001",
                     "package_sha256": "b" * 64,
                     "visible_instruction": "Save the visible training record."}
        self.backend = FakeBackend()
        self.worker = odoo.OdooTrainEpisodeWorker(
            worker_dir=self.root / "train", private_output_root=self.work)
        self.turns = []
        self.e2b_calls = 0

    def sample(self, observation, current_frame_id):
        self.assertEqual(current_frame_id(), observation.frame_id)
        raw = ('{"type":"click","target":{"ref":"c001"}}'
               if observation.step == 0 else '{"type":"finish"}')
        action = normalize_model_action(raw, observation,
                                        current_frame_id=current_frame_id())
        result_sha = digest(f"fake-teacher-{observation.step}".encode())
        trace = {
            "step": observation.step,
            "frame_id": observation.frame_id,
            "frame_sha256": digest(observation.screenshot_bytes),
            "observation": {
                "task_id": observation.task_id,
                "task_binding_sha256": observation.task_binding_sha256,
                "instruction": observation.instruction,
                "a11y_text": observation.a11y_text,
                "dom_text": observation.dom_text,
                "controls": [vars(control) for control in observation.controls],
                "previous_action_result": observation.previous_action_result,
                "memory": observation.memory,
                "issued_at": observation.issued_at,
            },
            "action": action,
            "teacher_result_sha256": result_sha,
        }
        self.turns.append({"observation": observation, "action": action,
                           "trace_row": trace,
                           "teacher_result_sha256": result_sha})
        return {"action": action, "trace_row": trace,
                "teacher_result_sha256": result_sha}

    def e2b(self, **_kwargs):
        self.e2b_calls += 1
        raise AssertionError("Self-hosted Odoo must not reserve an E2B lease")

    def run_fake(self):
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            return self.worker.run_episode(
                task=self.task, out_dir=self.episode,
                sample_teacher=self.sample, dispatch_e2b=self.e2b)

    def test_live_path_fails_before_backend_without_actual_freeze(self):
        with patch.object(self.worker.backend, "open",
                          side_effect=AssertionError("backend reached")):
            with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                        "requires_frozen_bindings"):
                self.worker.run_episode(task=self.task, out_dir=self.episode,
                                        sample_teacher=self.sample,
                                        dispatch_e2b=self.e2b)
        self.assertEqual(self.backend.open_calls, 0)
        self.assertEqual(self.e2b_calls, 0)
        self.assertEqual(list(self.episode.iterdir()),
                         [self.episode / "frames"])

    def test_changed_runtime_binding_fails_before_backend(self):
        marker = self.root / "synthetic-ratification.private.json"
        marker.write_text("{}")
        marker.chmod(0o600)
        self.worker.enable_live = True
        self.worker.ratification_path = marker
        self.worker.ratification_sha256 = "a" * 64
        self.worker.expected_runtime_sha256 = "0" * 64
        self.worker.expected_verifier_sha256 = self.worker.verifier_sha256
        with patch.object(self.worker.backend, "open",
                          side_effect=AssertionError("backend reached")):
            with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                        "requires_frozen_bindings"):
                self.worker.run_episode(task=self.task,
                                        out_dir=self.episode,
                                        sample_teacher=self.sample,
                                        dispatch_e2b=self.e2b)

    def test_successful_fake_teacher_episode_satisfies_real_receipt_validator(self):
        result = self.run_fake()
        episode_sha = teacher._verify_episode(
            self.episode, result, cell_id="odoo-community", task=self.task,
            runtime_sha=self.worker.runtime_sha256,
            adapter_sha=self.worker.adapter_sha256,
            verifier_sha=self.worker.verifier_sha256,
            turns=self.turns, e2b_attempt_ids=[], requires_e2b=False)
        self.assertEqual(episode_sha, result["episode_receipt_sha256"])
        self.assertEqual(self.backend.session.dispatches, ["click", "finish"])
        self.assertEqual(self.e2b_calls, 0)
        self.assertTrue(self.backend.session.post_restore_exact)
        self.assertEqual(json.loads((self.episode / "episode.private.json")
                                    .read_text())["split"], "train")

    def test_uncertain_saved_state_retains_failure_and_never_admits(self):
        def failed_sample(observation, current_frame_id):
            result = self.sample(observation, current_frame_id)
            self.backend.session.reward = 0.0
            return result
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                        "saved_state_or_fresh_reset"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=failed_sample, dispatch_e2b=self.e2b)
        self.assertFalse((self.episode / "episode.private.json").exists())
        self.assertTrue((self.episode / "failure.private.json").exists())
        self.assertTrue(self.backend.session.post_restore_exact)

    def test_inexact_baseline_stops_before_fake_teacher_reservation(self):
        self.backend.force_pre_restore_failure = True
        teacher_calls = []
        def forbidden_sample(observation, current_frame_id):
            teacher_calls.append(observation)
            return self.sample(observation, current_frame_id)
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                        "baseline_not_exact"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=forbidden_sample, dispatch_e2b=self.e2b)
        self.assertEqual(teacher_calls, [])
        self.assertEqual(self.backend.session.dispatches, [])
        self.assertTrue(self.backend.session.post_restore_exact)

    def test_changed_frame_after_fake_teacher_call_is_not_dispatched(self):
        def stale_sample(observation, current_frame_id):
            result = self.sample(observation, current_frame_id)
            self.backend.session.stale_after_sample = True
            return result
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                        "action_or_frame_changed"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=stale_sample, dispatch_e2b=self.e2b)
        self.assertEqual(self.backend.session.dispatches, [])
        self.assertTrue(self.backend.session.post_restore_exact)
        self.assertEqual(self.e2b_calls, 0)

    def test_failed_physical_reset_cannot_emit_admitted_episode(self):
        self.backend.force_reset_failure = True
        with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                    "saved_state_or_fresh_reset"):
            self.run_fake()
        self.assertFalse((self.episode / "episode.private.json").exists())
        self.assertTrue((self.episode / "failure.private.json").exists())

    def test_task_and_output_boundaries(self):
        with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                    "train_task_binding_invalid"):
            odoo._validate_task({**self.task, "hidden_gold": "x"})
        external = self.root / "public"
        external.mkdir()
        (external / "frames").mkdir(mode=0o700)
        with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                    "private_output_unsafe"):
            self.worker._check_output(external)

    def test_real_backend_train_manifest_gate_without_starting_docker(self):
        private = self.root / "train" / "private"
        private.mkdir(parents=True, mode=0o700)
        train_rows = [{"task_id": self.task["task_id"],
                       "package_sha256": self.task["package_sha256"]}]
        train_rows += [{"task_id": f"train-synthetic-{index:03d}",
                        "package_sha256": "c" * 64}
                       for index in range(2, 21)]
        write_private(private / "task_set_manifest.json", {
            "train": train_rows,
            "selection": [{"task_id": "selection-synthetic-001",
                           "package_sha256": "d" * 64}],
        })
        write_private(private / "partition_cases.json", {
            "cases": {"purchase": [{"id": self.task["task_id"],
                                    "prompt": self.task["visible_instruction"]}]},
        })
        family, case = self.worker.backend._load_train_case(self.task, private)
        self.assertEqual(family, "purchase")
        self.assertEqual(case["id"], self.task["task_id"])
        with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                    "not_in_private_partition"):
            self.worker.backend._load_train_case(
                {**self.task, "task_id": "selection-synthetic-001"}, private)
        with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                    "not_in_private_partition"):
            self.worker.backend._load_train_case(
                {**self.task, "visible_instruction": "Changed."}, private)

    def test_unbound_worker_and_duplicate_lease_identity_stop_before_docker(self):
        with patch.object(self.worker.backend, "_compose",
                          side_effect=AssertionError("Docker reached")):
            with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                        "original_train_worker_not_bound"):
                with self.worker.backend.open(self.task):
                    self.fail("Unbound worker unexpectedly opened")
        import gui_controls
        import reset
        import verify
        import worker_lease
        self.assertIs(gui_controls.require_worker_lease,
                      worker_lease.require_worker_lease)
        self.assertIs(reset.exclusive_worker_operation,
                      worker_lease.exclusive_worker_operation)
        self.assertIs(verify.exclusive_worker_operation,
                      worker_lease.exclusive_worker_operation)

    def test_real_session_rechecks_physical_pixels_before_dispatch(self):
        page = FakeOdooPage()
        adapter = odoo.OdooV066TrainAdapter(
            page, task_id=self.task["task_id"],
            task_binding_sha256=self.task["package_sha256"],
            instruction=self.task["visible_instruction"])
        session = odoo._RealOdooSession(
            page=page, adapter=adapter, case_id=self.task["task_id"],
            baseline_semantic={}, score=lambda _: {}, snapshot=lambda: {},
            frozen_filestore_manifest_sha256="a" * 64)
        observation = session.observe(memory="")
        action = normalize_model_action(
            '{"type":"double_click","target":{"x":5,"y":6}}',
            observation, current_frame_id=observation.frame_id)
        page.frame = image("black")
        with self.assertRaisesRegex(odoo.OdooEpisodeError,
                                    "current_frame_changed_before_dispatch"):
            session.dispatch(action)
        self.assertEqual([event for event in page.calls
                          if event[0] != "wait"], [])

    def test_frozen_campaign_adapter_reserves_fake_teacher_before_odoo_dispatch(self):
        common = common_source_hashes()
        profiles = {cell_id: {
            "common_source_sha256s": common,
            "adapter_sha256": (self.worker.adapter_sha256
                               if cell_id == "odoo-community" else "e" * 64),
        } for cell_id in teacher.matrix.CELLS}
        from native_desktop_factory import qwen_v066_adapter
        profiles["desktop-native"]["adapter_sha256"] = digest(
            Path(qwen_v066_adapter.__file__).read_bytes())
        from datetime import datetime, timezone
        ratification = {
            "schema": "cua-six-cell-action-profile-v066-ratification-v1",
            "status": "ratified_pre_result",
            "ratified_utc": datetime.now(timezone.utc).isoformat(),
            "action_profile": teacher.ACTION_PROFILE_VERSION,
            "common_source_sha256s": common,
            "cell_profiles": profiles,
            "base_and_selected_identical": True,
            "hidden_final_model_attempts_before_ratification": 0,
        }
        ratification_path = self.root / "synthetic-ratification.private.json"
        ratification_sha = write_private(ratification_path, ratification)
        session = FakeCampaignSession(self.root, ratification_path,
                                      ratification)
        session.intent["cell_id"] = "odoo-community"
        odoo_plan = next(row for row in session.study.plan["cells"]
                         if row["cell_id"] == "odoo-community")
        odoo_plan["matched_bindings"] = {
            "runtime": self.worker.runtime_sha256,
            "verifier": self.worker.verifier_sha256,
        }
        # The task is an invented train fixture, never a live Odoo identity.
        session.views["train"] = ({"task_id": self.task["task_id"],
                                   "package_sha256": self.task["package_sha256"]},)
        session.proposal["train_task_ids"] = [self.task["task_id"]]
        session.proposal_sha = write_private(session.proposal_path,
                                             session.proposal)
        context = self.work / "synthetic-context.private.json"
        write_private(context, {
            "schema": "cua-full-study-researcher-train-view-v1",
            "cell_id": "odoo-community", "tasks": [self.task],
        })
        session.context_sha = digest(context.read_bytes())
        self.worker.enable_live = True
        self.worker.ratification_path = ratification_path
        self.worker.ratification_sha256 = ratification_sha
        self.worker.expected_runtime_sha256 = self.worker.runtime_sha256
        self.worker.expected_verifier_sha256 = self.worker.verifier_sha256
        paid_requests = []

        def provider(request):
            paid_requests.append(request)
            self.backend.session.events.append("fake_paid_teacher_response")
            action = ('{"type":"click","target":{"ref":"c001"}}'
                      if request["step"] == 0 else '{"type":"finish"}')
            return {"text": action, "receipt": {
                "reported_model": teacher.matrix.TEACHER,
                "status": "completed",
                "response_id": "synthetic-response-" + str(len(paid_requests)),
                "usage": {"input_tokens": 100, "output_tokens": 10},
            }}

        def fake_render(cell_id, task_ids, episode_shas, turns, _vision):
            self.assertEqual(cell_id, "odoo-community")
            self.assertEqual(task_ids, [self.task["task_id"]])
            self.assertEqual(len(episode_shas), 1)
            self.assertEqual(len(turns), 2)
            receipt = {"schema": teacher.RENDER_SCHEMA,
                       "cell_id": cell_id,
                       "action_profile": teacher.ACTION_PROFILE_VERSION,
                       "model": teacher.MODEL,
                       "train_task_ids": task_ids,
                       "episode_receipt_sha256s": episode_shas,
                       "datum_token_lengths": [20, 20],
                       "prompt_token_lengths": [10, 10]}
            return teacher.RenderedTrainBatch(
                [SimpleNamespace(model_input=SimpleNamespace(length=20))
                 for _ in turns],
                [SimpleNamespace(length=10) for _ in turns], receipt)

        with patch.object(teacher, "_load_renderer", return_value=object()), \
             patch.object(teacher, "_render_turns", side_effect=fake_render), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            result = teacher.collect_train_batch(
                session, 1, context, self.work / "teacher-round-001",
                self.worker, teacher_provider=provider)
        self.assertEqual(len(paid_requests), 2)
        self.assertEqual([row["category"] for row in session.calls],
                         ["teacher_rollout", "teacher_rollout"])
        self.assertTrue(all(float(row["reserve_usd"]) > 0
                            for row in session.calls))
        self.assertEqual(self.backend.session.dispatches,
                         ["click", "finish"])
        self.assertEqual(self.backend.session.events, [
            "fake_paid_teacher_response", "physical_gui_dispatch",
            "fake_paid_teacher_response", "physical_gui_dispatch",
        ])
        self.assertEqual(self.e2b_calls, 0)
        self.assertTrue(result.dataset_manifest_path.is_file())
        self.assertEqual(json.loads(result.dataset_manifest_path.read_text())[
            "final_task_count"], 0)


if __name__ == "__main__":
    unittest.main()
