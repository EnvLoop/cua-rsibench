"""No-Docker/fake-provider GitLab teacher worker and train oracle tests."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import copy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import make_observation
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action
from gitlab_world import (factory, teacher_episode_worker_v066 as gitlab,
                          train_teacher_oracle_v066 as oracle, verify)
from tests.test_gitlab_v066_train_adapter import FakePage, frame as fake_frame


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (160, 120), (80, 100, 125)).save(output, "PNG")
    return output.getvalue()


class FakeSession(gitlab.EpisodeSession):
    def __init__(self, task: dict):
        super().__init__(baseline_semantic={"postgresql_git": "baseline",
                                            "overlay_seed": "frozen"},
                         pre_restore_exact=True)
        self.task = task
        self.step = 0
        self.latest = None
        self.finished = False
        self.stale_after_sample = False
        self.reward = 1.0
        self.dispatches = []

    def observe(self, *, memory: str):
        self.latest = make_observation(
            task_id=self.task["task_id"],
            task_binding_sha256=self.task["package_sha256"],
            instruction=self.task["visible_instruction"],
            step=self.step, screenshot_bytes=png(), memory=memory,
            controls=[{"ref": "c001", "role": "button", "label": "Save",
                       "visible": True, "enabled": True}],
            previous_action_result=(None if self.step == 0 else
                                    {"status": "applied", "code": "ok"}))
        return self.latest

    def current_frame_id(self):
        return (self.latest.frame_id if self.latest is not None and
                not self.stale_after_sample else "stale")

    def dispatch(self, action):
        validate_action(action, self.latest,
                        current_frame_id=self.current_frame_id())
        self.dispatches.append(action["type"])
        self.step += 1
        if action["type"] == "finish":
            self.finished = True

    def read_saved_state(self):
        if not self.finished:
            raise AssertionError("independent scorer called before finish")
        return {
            "business_snapshot": {"postgresql_git": "saved"},
            "independent_score": {
                "reward": self.reward,
                "checks_passed": self.reward == 1.0,
                "difference_codes": [] if self.reward == 1.0 else
                                    ["target_or_no_regression_mismatch"],
            },
            "gui_reload_frame_sha256": digest(png()),
            "original_gitlab_ce": True,
            "postgresql_and_git_readback": True,
        }


class FakeBackend:
    def __init__(self):
        self.open_calls = 0
        self.session = None
        self.fail_pre = False
        self.fail_post = False

    @contextmanager
    def open(self, task):
        self.open_calls += 1
        self.session = FakeSession(task)
        self.session.pre_restore_exact = not self.fail_pre
        try:
            yield self.session
        finally:
            self.session.reset_semantic = dict(self.session.baseline_semantic)
            self.session.post_restore_exact = not self.fail_post
            self.session.environment_terminated = True


class GitLabTeacherEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gitlab-teacher-fake-")
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
        self.worker = gitlab.GitLabTrainEpisodeWorker(
            private_output_root=self.work)
        self.turns = []
        self.e2b_calls = 0

    def sample(self, observation, current_frame_id):
        self.assertEqual(current_frame_id(), observation.frame_id)
        self.assertEqual((self.episode / "frames" /
                          f"step-{observation.step:03d}.png").read_bytes(),
                         observation.screenshot_bytes)
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
        raise AssertionError("Self-hosted GitLab must not reserve E2B")

    def run_fake(self):
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            return self.worker.run_episode(
                task=self.task, out_dir=self.episode,
                sample_teacher=self.sample, dispatch_e2b=self.e2b)

    def test_live_default_refuses_before_environment_or_provider(self):
        with patch.object(self.worker.backend, "open",
                          side_effect=AssertionError("Docker reached")):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "requires_frozen_bindings"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=self.sample, dispatch_e2b=self.e2b)
        self.assertEqual(self.backend.open_calls, 0)
        self.assertEqual(self.e2b_calls, 0)
        self.assertEqual(list(self.episode.iterdir()),
                         [self.episode / "frames"])

    def test_changed_runtime_binding_refuses_before_environment(self):
        marker = self.root / "synthetic-ratification.private.json"
        marker.write_text("{}")
        marker.chmod(0o600)
        self.worker.enable_live = True
        self.worker.ratification_path = marker
        self.worker.ratification_sha256 = "a" * 64
        self.worker.expected_runtime_sha256 = "0" * 64
        self.worker.expected_verifier_sha256 = self.worker.verifier_sha256
        with patch.object(self.worker.backend, "open",
                          side_effect=AssertionError("Docker reached")):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "requires_frozen_bindings"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=self.sample, dispatch_e2b=self.e2b)

    def test_successful_fake_teacher_episode_satisfies_real_receipt_validator(self):
        result = self.run_fake()
        episode_sha = teacher._verify_episode(
            self.episode, result, cell_id="gitlab", task=self.task,
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

    def test_uncertain_save_or_regression_cannot_admit(self):
        def unsuccessful(observation, current_frame_id):
            result = self.sample(observation, current_frame_id)
            self.backend.session.reward = 0.0
            return result
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "saved_state_or_fresh_reset"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=unsuccessful, dispatch_e2b=self.e2b)
        self.assertFalse((self.episode / "episode.private.json").exists())
        self.assertTrue((self.episode / "failure.private.json").exists())

    def test_inexact_baseline_stops_before_teacher_callback(self):
        self.backend.fail_pre = True
        calls = []
        def forbidden(observation, current_frame_id):
            calls.append(observation)
            return self.sample(observation, current_frame_id)
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "baseline_not_exact"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=forbidden, dispatch_e2b=self.e2b)
        self.assertEqual(calls, [])
        self.assertTrue(self.backend.session.post_restore_exact)

    def test_changed_frame_after_teacher_call_does_not_dispatch(self):
        def stale(observation, current_frame_id):
            result = self.sample(observation, current_frame_id)
            self.backend.session.stale_after_sample = True
            return result
        with patch.object(self.worker, "_require_ratification"), \
             patch.object(self.worker.backend, "open",
                          side_effect=self.backend.open):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "action_or_frame_changed"):
                self.worker.run_episode(
                    task=self.task, out_dir=self.episode,
                    sample_teacher=stale, dispatch_e2b=self.e2b)
        self.assertEqual(self.backend.session.dispatches, [])
        self.assertFalse((self.episode / "episode.private.json").exists())

    def test_failed_physical_reset_does_not_admit(self):
        self.backend.fail_post = True
        with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                    "saved_state_or_fresh_reset"):
            self.run_fake()
        self.assertFalse((self.episode / "episode.private.json").exists())

    def test_task_and_private_output_boundaries(self):
        with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                    "train_task_binding_invalid"):
            gitlab._validate_task({**self.task, "hidden_gold": "x"})
        external = self.root / "public"
        external.mkdir()
        (external / "frames").mkdir(mode=0o700)
        with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                    "private_output_unsafe"):
            self.worker._check_output(external)

    def test_real_session_rechecks_current_physical_pixels(self):
        class FakeLoop:
            @staticmethod
            def call(coroutine, **_kwargs):
                import asyncio
                return asyncio.run(coroutine)
        page = FakePage()
        observed = fake_frame()
        session = gitlab._RealGitLabSession(
            loop=FakeLoop(), page=page, task=self.task,
            original_task={"partition": "train"},
            project_path="train/project", baseline_semantic={})
        session.latest = observed
        action = normalize_model_action(
            '{"type":"double_click","target":{"x":5,"y":6}}',
            observed.observation,
            current_frame_id=observed.observation.frame_id)
        page.frame = png()
        with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                    "current_frame_changed_before_dispatch"):
            session.dispatch(action)
        self.assertEqual(page.events, [])

    def test_real_session_uses_v066_current_frame_gui_dispatch(self):
        class FakeLoop:
            @staticmethod
            def call(coroutine, **_kwargs):
                import asyncio
                return asyncio.run(coroutine)
        page = FakePage()
        observed = fake_frame()
        session = gitlab._RealGitLabSession(
            loop=FakeLoop(), page=page, task=self.task,
            original_task={"partition": "train"},
            project_path="train/project", baseline_semantic={})
        session.latest = observed
        action = normalize_model_action(
            '{"type":"double_click","target":{"x":5,"y":6}}',
            observed.observation,
            current_frame_id=observed.observation.frame_id)
        session.dispatch(action)
        self.assertEqual(page.events, [("dblclick", 5, 6)])
        self.assertEqual(session.step, 1)

    def test_real_session_never_samples_another_project(self):
        class FakeLoop:
            @staticmethod
            def call(coroutine, **_kwargs):
                import asyncio
                return asyncio.run(coroutine)
        page = FakePage()
        session = gitlab._RealGitLabSession(
            loop=FakeLoop(), page=page, task=self.task,
            original_task={"partition": "train"},
            project_path="train/project", baseline_semantic={})
        session.latest = fake_frame()
        page.url = "http://127.0.0.1:8014/another-train/project"
        self.assertEqual(session.current_frame_id(), "stale")
        with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                    "left_scoped_train_project"):
            session.observe(memory="")
        self.assertEqual(page.events, [])

    def test_navigation_during_capture_cannot_return_other_project_frame(self):
        class FakeLoop:
            @staticmethod
            def call(coroutine, **_kwargs):
                import asyncio
                return asyncio.run(coroutine)
        page = FakePage()
        session = gitlab._RealGitLabSession(
            loop=FakeLoop(), page=page, task=self.task,
            original_task={"partition": "train"},
            project_path="train/project", baseline_semantic={})
        async def redirect_capture(*_args, **_kwargs):
            page.url = "http://127.0.0.1:8014/another-train/project"
            return fake_frame()
        with patch.object(gitlab.actor, "capture",
                          side_effect=redirect_capture):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "left_scoped_train_project"):
                session.observe(memory="")

    def test_real_backend_requires_exact_private_train_identity(self):
        private = self.root / "gitlab-private"
        private.mkdir(mode=0o700)
        def write(name, value):
            path = private / name
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            return path
        manifest = write("world-private.json", {"schema": factory.SCHEMA})
        progress = write("bootstrap-progress.json", {
            "groups": {PROJECT["group_path"]: 17}})
        credentials = write("operator-credentials-private.json", {
            partition: {"username": "synthetic", "password": "synthetic"}
            for partition in ("train", "selection",
                              "final_candidate_unsealed")})
        receipt = write("operator-bootstrap-private.json", {
            "identities": {"train": {"group_id": 17}},
            "root_admin_is_actor": False})
        write("baseline-persisted-state.json", {})
        state = write("cow-reset-state.json", {})
        original = TASKS[0]
        bound = {"task_id": original["task_id"],
                 "package_sha256": factory.sha256(factory.canonical(original)),
                 "visible_instruction": original["prompt"]}
        backend = gitlab.RealGitLabTrainBackend()
        with patch.object(gitlab.runtime, "PRIVATE", private), \
             patch.object(gitlab.bootstrap, "WORLD_FILE", manifest), \
             patch.object(gitlab.bootstrap, "PROGRESS_FILE", progress), \
             patch.object(gitlab.operators, "CREDENTIALS", credentials), \
             patch.object(gitlab.operators, "RECEIPT", receipt), \
             patch.object(gitlab.reset, "STATE_FILE", state), \
             patch.object(gitlab.bootstrap, "world", return_value=WORLD):
            task, project, actor = backend._load_train_task(bound)
            self.assertEqual((task["partition"], project["partition"]),
                             ("train", "train"))
            self.assertEqual(actor["username"], "synthetic")
            for wrong in ({**bound, "package_sha256": "0" * 64},
                          {**bound, "visible_instruction": "Changed."},
                          {**bound, "task_id": next(row["task_id"]
                              for row in WORLD["tasks"]
                              if row["partition"] == "selection")}):
                with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                            "not_in_private_train_partition"):
                    backend._load_train_task(wrong)

    def test_real_backend_calls_two_exact_cold_resets_without_docker(self):
        class FakeLoop:
            def start(self): pass
            def call(self, coroutine, **_kwargs):
                import asyncio
                return asyncio.run(coroutine)
            def close(self): pass
        baseline = {"business_sha256": "a" * 64}
        state = {"baseline_business_sha256": "a" * 64,
                 "seed_volume_lowerdirs": {"data": "/frozen/data"}}
        pre = {"cold_reset": True, "same_business_sha256": True}
        proof_before = {"image_id": gitlab.runtime.IMAGE_ID,
                        "container_id_sha256": "1" * 64}
        proof_after = {"image_id": gitlab.runtime.IMAGE_ID,
                       "container_id_sha256": "2" * 64}
        backend = gitlab.RealGitLabTrainBackend()
        with patch.object(backend, "_load_train_task",
                          return_value=(TASKS[0], PROJECT, {})), \
             patch.object(backend, "_lease", return_value=nullcontext()), \
             patch.object(gitlab.reset, "_baseline", return_value=baseline), \
             patch.object(gitlab.reset, "_state", return_value=state), \
             patch.object(gitlab.reset, "reset", side_effect=[pre, pre]) as cold, \
             patch.object(gitlab.verify, "state_snapshot",
                          return_value=baseline), \
             patch.object(gitlab.runtime, "proof",
                          side_effect=[proof_before, proof_after]), \
             patch.object(gitlab.oracle, "evaluate_train_task",
                          return_value={"reward": 0.0}), \
             patch.object(gitlab, "_AsyncLoop", FakeLoop), \
             patch.object(backend, "_start_browser",
                          new=AsyncMock(return_value=(None, None, None,
                                                      FakePage()))), \
             patch.object(backend, "_stop_browser", new=AsyncMock()):
            with backend.open(self.task) as session:
                self.assertTrue(session.pre_restore_exact)
            self.assertTrue(session.post_restore_exact)
            self.assertTrue(session.environment_terminated)
            self.assertEqual(cold.call_count, 2)

    def test_background_loop_keeps_async_browser_calls_on_one_thread(self):
        import asyncio
        import threading
        loop = gitlab._AsyncLoop()
        loop.start()
        try:
            async def thread_id():
                return threading.get_ident()
            self.assertNotEqual(loop.call(thread_id()),
                                threading.get_ident())
            self.assertEqual(loop.call(thread_id()),
                             loop.call(thread_id()))
        finally:
            loop.close()

    def test_real_backend_rejects_reused_clone_identity_after_reset(self):
        class FakeLoop:
            def start(self): pass
            def call(self, coroutine, **_kwargs):
                import asyncio
                return asyncio.run(coroutine)
            def close(self): pass
        baseline = {"business_sha256": "a" * 64}
        state = {"baseline_business_sha256": "a" * 64,
                 "seed_volume_lowerdirs": {"data": "/frozen/data"}}
        cold = {"cold_reset": True, "same_business_sha256": True}
        proof = {"image_id": gitlab.runtime.IMAGE_ID,
                 "container_id_sha256": "1" * 64}
        backend = gitlab.RealGitLabTrainBackend()
        with patch.object(backend, "_load_train_task",
                          return_value=(TASKS[0], PROJECT, {})), \
             patch.object(backend, "_lease", return_value=nullcontext()), \
             patch.object(gitlab.reset, "_baseline", return_value=baseline), \
             patch.object(gitlab.reset, "_state", return_value=state), \
             patch.object(gitlab.reset, "reset", side_effect=[cold, cold]), \
             patch.object(gitlab.verify, "state_snapshot",
                          return_value=baseline), \
             patch.object(gitlab.runtime, "proof",
                          side_effect=[proof, proof]), \
             patch.object(gitlab.oracle, "evaluate_train_task",
                          return_value={"reward": 0.0}), \
             patch.object(gitlab, "_AsyncLoop", FakeLoop), \
             patch.object(backend, "_start_browser",
                          new=AsyncMock(return_value=(None, None, None,
                                                      FakePage()))), \
             patch.object(backend, "_stop_browser", new=AsyncMock()):
            with self.assertRaisesRegex(gitlab.GitLabEpisodeError,
                                        "post_episode_cold_reset_failed"):
                with backend.open(self.task):
                    pass


WORLD = factory.build_world("private-development-fixture-seed-001")
PROJECT = next(row for row in WORLD["projects"] if row["partition"] == "train")
TASKS = [row for row in WORLD["tasks"]
         if row["project_family"] == PROJECT["full_path"]]
PROGRESS = {"project_id": 17,
            "issue_iids": {"active": 1},
            "user_ids": {"incoming": 103}}


def snapshot():
    return {
        "schema": verify.SCHEMA, "project_ids": [17, 18],
        "business_sha256": "before",
        "db": {
            "projects": [{"id": 17}, {"id": 18}],
            "issues": [
                {"id": 201, "project_id": 17, "iid": 1,
                 "title": "active", "due_date": None},
                {"id": 301, "project_id": 18, "iid": 1,
                 "title": "unrelated", "due_date": None}],
            "issue_assignees": [],
            "labels": [{"id": 51, "project_id": 17,
                        "title": TASKS[0]["oracle"]["expected_priority"]}],
            "issue_label_links": [],
            "milestones": [], "members": [], "merge_requests": [],
        },
        "git": {"17": {"refs": {"refs/heads/main": "a" * 40},
                       "main_blobs_sha256": {"README.md": "r"}},
                "18": {"refs": {"refs/heads/main": "b" * 40},
                       "main_blobs_sha256": {"README.md": "s"}}},
    }


class GitLabTrainOracleTests(unittest.TestCase):
    def test_four_original_train_workflows_and_no_regression(self):
        for task in TASKS:
            with self.subTest(family=task["template_group"]):
                before = snapshot()
                after = copy.deepcopy(before)
                after["business_sha256"] = "after"
                family = task["template_group"]
                if family == "issue_label_from_alert":
                    after["db"]["issue_label_links"].append(
                        {"id": 701, "target_id": 201, "label_id": 51})
                elif family == "issue_due_from_register":
                    after["db"]["issues"][0]["due_date"] = (
                        PROJECT["policy"]["issue_due"])
                elif family == "milestone_window_from_policy":
                    policy = PROJECT["policy"]
                    after["db"]["milestones"].append({
                        "id": 401, "project_id": 17,
                        "title": policy["milestone_title"],
                        "start_date": policy["milestone_start"],
                        "due_date": policy["milestone_due"]})
                elif family == "guest_member_from_roster":
                    after["db"]["members"].append({
                        "id": 601, "source_id": 17, "user_id": 103,
                        "access_level": 10, "expires_at": None})
                with patch.object(verify, "_context",
                                  return_value=(PROJECT, PROGRESS)):
                    good = oracle.evaluate_train_task(task, before, after)
                    self.assertEqual((good["reward"], good["checks_passed"]),
                                     (1.0, True))
                    after["db"]["issues"][1]["title"] = "collateral"
                    bad = oracle.evaluate_train_task(task, before, after)
                    self.assertEqual((bad["reward"], bad["checks_passed"]),
                                     (0.0, False))

    def test_nontrain_task_and_incomplete_saved_state_rejected(self):
        before = snapshot()
        task = TASKS[0]
        with patch.object(verify, "_context",
                          return_value=(PROJECT, PROGRESS)):
            self.assertEqual(oracle.evaluate_train_task(
                task, before, before)["reward"], 0.0)
        with self.assertRaisesRegex(ValueError, "train_only"):
            oracle.evaluate_train_task(
                {**task, "partition": "final_candidate_unsealed"},
                before, before)


if __name__ == "__main__":
    unittest.main()
