"""Train-only original GitLab CE teacher episode worker for the full study.

The campaign adapter owns teacher reservations. This worker owns a scoped
non-admin browser, current-frame GUI dispatch, evaluator-only PostgreSQL/Git
scoring, and physical overlayfs cold reset. Live execution defaults off and
requires the private six-cell ratification. It never selects a task or calls
a model or E2B itself.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Callable, Iterator
from urllib.parse import urlsplit

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import ContractError, Observation
from cursibench.scale_action_contract_v066 import (
    ACTION_PROFILE_VERSION, validate_action,
)
from cursibench.scale_action_output_v066 import normalize_model_action

from . import (bootstrap, factory, operators, reset, runtime,
               train_teacher_oracle_v066 as oracle, verify,
               vision_actor_v066_train as actor)


ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MAX_ACTIONS = 90
WALL_SECONDS = 1800
VIEWPORT = {"width": 1440, "height": 1000}
RUNTIME_FILES = (
    "gitlab_world/teacher_episode_worker_v066.py",
    "gitlab_world/train_teacher_oracle_v066.py",
    "gitlab_world/vision_actor_v066_train.py",
    "gitlab_world/vision_actor.py",
    "gitlab_world/bootstrap.py",
    "gitlab_world/factory.py",
    "gitlab_world/operators.py",
    "gitlab_world/reset.py",
    "gitlab_world/runtime.py",
    "gitlab_world/verify.py",
    "gitlab_world/data/kev_excerpt.json",
    "gitlab_world/data/kev_reserve_excerpt.json",
)


class GitLabEpisodeError(RuntimeError):
    """Fixed private failure labels; never include task, gold or credentials."""


def _canonical(value: object) -> bytes:
    return teacher._canonical(value)


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def source_hashes() -> dict[str, str]:
    return {relative: _hash((ROOT / relative).read_bytes())
            for relative in RUNTIME_FILES}


def runtime_sha256() -> str:
    return _hash(_canonical(source_hashes()))


def verifier_sha256() -> str:
    return _hash(_canonical({
        relative: _hash((ROOT / relative).read_bytes())
        for relative in ("gitlab_world/verify.py",
                         "gitlab_world/train_teacher_oracle_v066.py")
    }))


def adapter_sha256() -> str:
    return _hash((ROOT / "gitlab_world/vision_actor_v066_train.py").read_bytes())


def _mode_private(path: Path, *, directory: bool) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _write_new(path: Path, raw: bytes) -> dict[str, str]:
    if (path.exists() or path.is_symlink() or len(raw) > 8_000_000 or
            not _mode_private(path.parent, directory=True)):
        raise GitLabEpisodeError("private_episode_path_unsafe")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": path.name, "sha256": _hash(raw)}


def _artifact(out_dir: Path, name: str, value: object) -> dict[str, str]:
    reference = _write_new(out_dir / "artifacts" / name,
                           _canonical(value))
    return {"path": "artifacts/" + reference["path"],
            "sha256": reference["sha256"]}


def _validate_task(task: object) -> dict:
    if (type(task) is not dict or
            set(task) != {"task_id", "package_sha256", "visible_instruction"} or
            type(task["task_id"]) is not str or
            not TASK_ID.fullmatch(task["task_id"]) or
            type(task["package_sha256"]) is not str or
            not HEX64.fullmatch(task["package_sha256"]) or
            type(task["visible_instruction"]) is not str or
            not 1 <= len(task["visible_instruction"].encode()) <= 16_384):
        raise GitLabEpisodeError("train_task_binding_invalid")
    return dict(task)


class _AsyncLoop:
    """Keep every Playwright object on one loop while the paid callback is sync."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name="gitlab-teacher-browser")

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True))
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.loop.close()

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(10):
            raise GitLabEpisodeError("browser_event_loop_start_failed")

    def call(self, coroutine, *, timeout: int = 120):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        try:
            return future.result(timeout)
        except TimeoutError:
            future.cancel()
            raise GitLabEpisodeError("browser_operation_timeout") from None

    def close(self) -> None:
        if self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(30)
            if self.thread.is_alive():
                raise GitLabEpisodeError("browser_event_loop_stop_failed")


@dataclass
class EpisodeSession:
    baseline_semantic: dict
    reset_semantic: dict | None = None
    pre_restore_exact: bool = False
    post_restore_exact: bool = False
    environment_terminated: bool = False

    def observe(self, *, memory: str) -> Observation:
        raise NotImplementedError

    def current_frame_id(self) -> str:
        raise NotImplementedError

    def dispatch(self, action: dict) -> None:
        raise NotImplementedError

    def read_saved_state(self) -> dict:
        raise NotImplementedError


class _RealGitLabSession(EpisodeSession):
    def __init__(self, *, loop: _AsyncLoop, page, task: dict,
                 original_task: dict, project_path: str,
                 baseline_semantic: dict):
        super().__init__(baseline_semantic=baseline_semantic,
                         pre_restore_exact=True)
        self.loop = loop
        self.page = page
        self.task = task
        self.original_task = original_task
        self.project_path = "/" + project_path
        self.latest = None
        self.step = 0
        self.previous = None
        self.finished = False

    async def _capture(self, memory: str):
        if not self._scoped_url():
            raise GitLabEpisodeError("gitlab_actor_left_scoped_train_project")
        frame = await actor.capture(
            self.page, task_id=self.task["task_id"],
            binding_sha256=self.task["package_sha256"],
            instruction=self.task["visible_instruction"],
            step=self.step, memory=memory, previous=self.previous)
        if not self._scoped_url() or frame.page_url != self.page.url:
            raise GitLabEpisodeError("gitlab_actor_left_scoped_train_project")
        return frame

    def _scoped_url(self) -> bool:
        path = urlsplit(self.page.url).path.rstrip("/")
        return (actor.local_origin(self.page.url) and
                (path == self.project_path or
                 path.startswith(self.project_path + "/")))

    async def _check_scoped(self) -> bool:
        return self._scoped_url()

    def observe(self, *, memory: str) -> Observation:
        if self.finished:
            raise GitLabEpisodeError("observation_after_finish")
        self.latest = self.loop.call(self._capture(memory))
        return self.latest.observation

    async def _current_frame(self) -> str:
        if (self.latest is None or not self._scoped_url() or
                time.monotonic() > self.latest.observation.expires_at):
            return "stale"
        try:
            await actor._current(self.page, self.latest, {"type": "wait"})
        except ContractError:
            return "stale"
        return self.latest.observation.frame_id

    def current_frame_id(self) -> str:
        return self.loop.call(self._current_frame())

    async def _dispatch(self, action: dict) -> dict:
        observation = self.latest.observation
        minimal = {key: value for key, value in action.items()
                   if key not in {"version", "task_id", "task_binding_sha256",
                                  "step", "frame_id"}}
        raw = _canonical(minimal).decode()
        reconstructed = normalize_model_action(
            raw, observation, current_frame_id=observation.frame_id)
        if reconstructed != action:
            raise GitLabEpisodeError("teacher_action_reconstruction_changed")
        result, _receipt = await actor.validate_and_dispatch(
            self.page, raw, self.latest, task_partition="train")
        return result

    def dispatch(self, action: dict) -> None:
        if self.latest is None or self.current_frame_id() != self.latest.observation.frame_id:
            raise GitLabEpisodeError("current_frame_changed_before_dispatch")
        checked = validate_action(
            action, self.latest.observation,
            current_frame_id=self.latest.observation.frame_id)
        result = self.loop.call(self._dispatch(checked))
        if result != {"status": "applied", "code": "ok"}:
            raise GitLabEpisodeError("gui_dispatch_not_applied")
        self.step += 1
        self.previous = result
        self.latest = None
        if action["type"] == "finish":
            self.finished = True

    async def _reload(self) -> str:
        await self.page.reload(wait_until="domcontentloaded", timeout=90000)
        await self.page.locator("body").wait_for(timeout=30000)
        if not self._scoped_url():
            raise GitLabEpisodeError("gitlab_actor_left_scoped_train_project")
        screenshot = await self.page.screenshot(
            type="png", full_page=False, animations="disabled",
            mask=[self.page.locator('input[type="password"]')])
        return _hash(screenshot)

    def read_saved_state(self) -> dict:
        if not self.finished:
            raise GitLabEpisodeError("teacher_finish_action_missing")
        if not self.loop.call(self._check_scoped()):
            raise GitLabEpisodeError("gitlab_actor_left_scoped_train_project")
        reload_sha = self.loop.call(self._reload())
        after = verify.state_snapshot()
        score = oracle.evaluate_train_task(
            self.original_task,
            self.baseline_semantic["business_snapshot"], after)
        return {"business_snapshot": after,
                "independent_score": score,
                "gui_reload_frame_sha256": reload_sha,
                "original_gitlab_ce": True,
                "postgresql_and_git_readback": True}


class RealGitLabTrainBackend:
    """One scoped GitLab train project and two exact overlayfs cold resets."""

    def _load_train_task(self, task: dict) -> tuple[dict, dict, dict]:
        private = runtime.PRIVATE
        needed = (bootstrap.WORLD_FILE, bootstrap.PROGRESS_FILE,
                  operators.CREDENTIALS, operators.RECEIPT,
                  private / "baseline-persisted-state.json", reset.STATE_FILE)
        if (not _mode_private(private, directory=True) or
                any(not _mode_private(path, directory=False)
                    for path in needed)):
            raise GitLabEpisodeError("gitlab_private_train_world_missing_or_unsafe")
        world = bootstrap.world()
        train = [row for row in world["tasks"]
                 if row["partition"] == "train"]
        other_ids = {row["task_id"] for row in bootstrap.all_tasks(world)
                     if row["partition"] != "train"}
        matches = [row for row in train if row["task_id"] == task["task_id"]]
        if (len(train) != 20 or len({row["task_id"] for row in train}) != 20 or
                len(matches) != 1 or task["task_id"] in other_ids or
                task["package_sha256"] !=
                factory.sha256(factory.canonical(matches[0])) or
                task["visible_instruction"] != matches[0]["prompt"]):
            raise GitLabEpisodeError("gitlab_task_not_in_private_train_partition")
        original = matches[0]
        projects = [row for row in bootstrap.all_projects(world)
                    if row["full_path"] == original["project_family"]]
        if len(projects) != 1 or projects[0]["partition"] != "train":
            raise GitLabEpisodeError("gitlab_project_not_in_train_partition")
        roster = json.loads(operators.CREDENTIALS.read_bytes())
        operator = json.loads(operators.RECEIPT.read_bytes())
        progress = json.loads(bootstrap.PROGRESS_FILE.read_bytes())
        group_path = projects[0]["group_path"]
        own = operator.get("identities", {}).get("train", {})
        if (set(roster) != set(operators.PARTITIONS) or
                type(roster.get("train")) is not dict or
                type(roster["train"].get("username")) is not str or
                type(roster["train"].get("password")) is not str or
                not roster["train"]["password"] or
                own.get("group_id") != progress["groups"].get(group_path) or
                operator.get("root_admin_is_actor") is not False):
            raise GitLabEpisodeError("gitlab_scoped_train_operator_invalid")
        return original, projects[0], roster["train"]

    @contextmanager
    def _lease(self) -> Iterator[None]:
        path = runtime.PRIVATE / "teacher-episode-exclusive.lock"
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if not _mode_private(path, directory=False):
                raise GitLabEpisodeError("gitlab_episode_lease_unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise GitLabEpisodeError("gitlab_episode_lease_busy") from None
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    async def _start_browser(self, project: dict, credentials: dict):
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        browser = context = None
        try:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(viewport=VIEWPORT)
            await actor.install_local_guard(context)
            page = await context.new_page()
            if await context.cookies():
                raise GitLabEpisodeError("gitlab_actor_context_not_fresh")
            await page.goto(runtime.BASE + "/users/sign_in",
                            wait_until="domcontentloaded", timeout=90000)
            await page.locator("#user_login").fill(credentials["username"])
            await page.locator("#user_password").fill(credentials["password"])
            await page.get_by_role("button", name="Sign in").click()
            await page.wait_for_url(lambda value: "users/sign_in" not in value,
                                    timeout=90000)
            await page.goto(runtime.BASE + "/" + project["full_path"],
                            wait_until="domcontentloaded", timeout=90000)
            await page.get_by_text(project["display_name"],
                                   exact=False).first.wait_for(timeout=30000)
            if not actor.local_origin(page.url):
                raise GitLabEpisodeError("gitlab_actor_left_local_origin")
            return playwright, browser, context, page
        except BaseException:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
            await playwright.stop()
            raise

    async def _stop_browser(self, opened) -> None:
        playwright, browser, context, _page = opened
        try:
            await context.close()
        finally:
            try:
                await browser.close()
            finally:
                await playwright.stop()

    @contextmanager
    def open(self, task: dict) -> Iterator[_RealGitLabSession]:
        original, project, credentials = self._load_train_task(task)
        actor.assert_shared_stack()
        with self._lease():
            baseline = reset._baseline()
            if (baseline["business_sha256"] !=
                    reset._state()["baseline_business_sha256"]):
                raise GitLabEpisodeError("gitlab_frozen_baseline_changed")
            pre_reset = reset.reset()
            if (pre_reset.get("cold_reset") is not True or
                    pre_reset.get("same_business_sha256") is not True):
                raise GitLabEpisodeError("gitlab_pre_episode_cold_reset_failed")
            before = verify.state_snapshot()
            before_proof = runtime.proof(runtime.WORLD)
            if (before != baseline or before_proof["image_id"] != runtime.IMAGE_ID or
                    oracle.evaluate_train_task(original, before, before)["reward"] != 0.0):
                raise GitLabEpisodeError("gitlab_train_baseline_not_exact")
            semantic = {
                "business_snapshot": before,
                "seed_lowerdirs_sha256": _hash(_canonical(
                    reset._state()["seed_volume_lowerdirs"])),
                "pinned_image_id": before_proof["image_id"],
            }
            loop = _AsyncLoop()
            opened = None
            session = None
            failure = None
            try:
                loop.start()
                opened = loop.call(self._start_browser(project, credentials),
                                   timeout=300)
                session = _RealGitLabSession(
                    loop=loop, page=opened[3], task=task,
                    original_task=original, project_path=project["full_path"],
                    baseline_semantic=semantic)
                yield session
            except BaseException as exc:
                failure = exc
                raise
            finally:
                browser_closed = False
                try:
                    if opened is not None:
                        loop.call(self._stop_browser(opened), timeout=120)
                    browser_closed = True
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    browser_closed = False
                reset_ok = False
                try:
                    post_reset = reset.reset()
                    restored = verify.state_snapshot()
                    after_proof = runtime.proof(runtime.WORLD)
                    reset_semantic = {
                        "business_snapshot": restored,
                        "seed_lowerdirs_sha256": _hash(_canonical(
                            reset._state()["seed_volume_lowerdirs"])),
                        "pinned_image_id": after_proof["image_id"],
                    }
                    reset_ok = (
                        post_reset.get("cold_reset") is True and
                        post_reset.get("same_business_sha256") is True and
                        restored == baseline and
                        after_proof["container_id_sha256"] !=
                        before_proof["container_id_sha256"] and
                        reset_semantic == semantic)
                    if session is not None:
                        session.reset_semantic = reset_semantic
                        session.post_restore_exact = reset_ok
                        session.environment_terminated = (
                            reset_ok and browser_closed)
                except Exception:
                    reset_ok = False
                if not reset_ok or not browser_closed:
                    raise GitLabEpisodeError(
                        "gitlab_post_episode_cold_reset_failed") from failure


class GitLabTrainEpisodeWorker:
    """Concrete self-hosted GitLab cell worker for ``collect_train_batch``."""

    cell_id = "gitlab"
    action_profile = ACTION_PROFILE_VERSION
    original_software_gui = True
    original_surface = "web"
    requires_e2b = False

    def __init__(self, *, private_output_root: Path,
                 ratification_path: Path | None = None,
                 ratification_sha256: str | None = None,
                 expected_runtime_sha256: str | None = None,
                 expected_verifier_sha256: str | None = None,
                 enable_live: bool = False):
        self.private_output_root = Path(private_output_root).resolve()
        self.ratification_path = (Path(ratification_path)
                                  if ratification_path is not None else None)
        self.ratification_sha256 = ratification_sha256
        self.runtime_sha256 = runtime_sha256()
        self.verifier_sha256 = verifier_sha256()
        self.adapter_sha256 = adapter_sha256()
        self.expected_runtime_sha256 = expected_runtime_sha256
        self.expected_verifier_sha256 = expected_verifier_sha256
        self.enable_live = enable_live
        self.backend = RealGitLabTrainBackend()

    def _require_ratification(self) -> None:
        if (self.enable_live is not True or
                self.ratification_path is None or
                not _mode_private(self.ratification_path, directory=False) or
                type(self.ratification_sha256) is not str or
                not HEX64.fullmatch(self.ratification_sha256) or
                self.expected_runtime_sha256 != self.runtime_sha256 or
                self.expected_verifier_sha256 != self.verifier_sha256 or
                self.runtime_sha256 != runtime_sha256() or
                self.verifier_sha256 != verifier_sha256() or
                self.adapter_sha256 != adapter_sha256()):
            raise GitLabEpisodeError("gitlab_live_episode_requires_frozen_bindings")
        from native_desktop_factory.v066_final_freeze import validate_ratification
        try:
            ratification, digest = validate_ratification(
                self.ratification_path)
        except (OSError, ValueError, TypeError, KeyError):
            raise GitLabEpisodeError("gitlab_six_cell_ratification_invalid") from None
        profile = ratification.get("cell_profiles", {}).get(self.cell_id, {})
        if (digest != self.ratification_sha256 or
                profile.get("adapter_sha256") != self.adapter_sha256):
            raise GitLabEpisodeError("gitlab_six_cell_adapter_binding_changed")

    def _check_output(self, out_dir: Path) -> None:
        if (not _mode_private(self.private_output_root, directory=True) or
                not _mode_private(out_dir, directory=True) or
                not out_dir.resolve().is_relative_to(
                    self.private_output_root) or
                not _mode_private(out_dir / "frames", directory=True) or
                {child.name for child in out_dir.iterdir()} != {"frames"}):
            raise GitLabEpisodeError("gitlab_episode_private_output_unsafe")

    def run_episode(self, *, task, out_dir, sample_teacher,
                    dispatch_e2b) -> dict:
        task = _validate_task(task)
        if not callable(sample_teacher) or not callable(dispatch_e2b):
            raise GitLabEpisodeError("gitlab_teacher_callbacks_missing")
        self._require_ratification()
        out_dir = Path(out_dir).absolute()
        self._check_output(out_dir)
        (out_dir / "artifacts").mkdir(mode=0o700)
        frame_refs: list[dict] = []
        trace_rows: list[dict] = []
        teacher_shas: list[str] = []
        memory = ""
        session = None
        saved = None
        started = time.monotonic()
        try:
            with self.backend.open(task) as active:
                session = active
                if (active.pre_restore_exact is not True or
                        type(active.baseline_semantic) is not dict):
                    raise GitLabEpisodeError(
                        "gitlab_baseline_not_exact_before_teacher_call")
                for step in range(MAX_ACTIONS):
                    if time.monotonic() - started > WALL_SECONDS:
                        raise GitLabEpisodeError("gitlab_teacher_episode_time_exhausted")
                    observation = active.observe(memory=memory)
                    if (type(observation) is not Observation or
                            observation.step != step or
                            observation.task_id != task["task_id"] or
                            observation.task_binding_sha256 !=
                            task["package_sha256"] or
                            observation.instruction != task["visible_instruction"]):
                        raise GitLabEpisodeError(
                            "gitlab_observation_not_bound_to_train_task")
                    frame = out_dir / "frames" / f"step-{step:03d}.png"
                    ref = _write_new(frame, observation.screenshot_bytes)
                    frame_refs.append({"path": "frames/" + ref["path"],
                                       "sha256": ref["sha256"]})
                    sampled = sample_teacher(observation,
                                             active.current_frame_id)
                    if (type(sampled) is not dict or
                            set(sampled) != {"action", "trace_row",
                                             "teacher_result_sha256"} or
                            type(sampled["action"]) is not dict or
                            type(sampled["trace_row"]) is not dict or
                            type(sampled["teacher_result_sha256"]) is not str or
                            not HEX64.fullmatch(
                                sampled["teacher_result_sha256"])):
                        raise GitLabEpisodeError(
                            "gitlab_teacher_callback_result_invalid")
                    action = sampled["action"]
                    if (active.current_frame_id() != observation.frame_id or
                            validate_action(action, observation,
                                            current_frame_id=observation.frame_id)
                            != action or
                            sampled["trace_row"].get("action") != action or
                            sampled["trace_row"].get("step") != step or
                            sampled["trace_row"].get("frame_id") !=
                            observation.frame_id or
                            sampled["trace_row"].get("frame_sha256") !=
                            ref["sha256"] or
                            sampled["trace_row"].get(
                                "teacher_result_sha256") !=
                            sampled["teacher_result_sha256"]):
                        raise GitLabEpisodeError(
                            "gitlab_teacher_action_or_frame_changed")
                    active.dispatch(action)
                    trace_rows.append(sampled["trace_row"])
                    teacher_shas.append(sampled["teacher_result_sha256"])
                    memory = action["memory"]
                    if action["type"] == "finish":
                        saved = active.read_saved_state()
                        break
                else:
                    raise GitLabEpisodeError(
                        "gitlab_teacher_action_budget_exhausted")
            if (session is None or not session.pre_restore_exact or
                    not session.post_restore_exact or
                    not session.environment_terminated or
                    session.reset_semantic != session.baseline_semantic or
                    type(saved) is not dict or
                    saved.get("original_gitlab_ce") is not True or
                    saved.get("postgresql_and_git_readback") is not True or
                    type(saved.get("independent_score")) is not dict or
                    saved["independent_score"].get("reward") != 1.0 or
                    saved["independent_score"].get("checks_passed") is not True or
                    saved["independent_score"].get("difference_codes") != [] or
                    not HEX64.fullmatch(
                        saved.get("gui_reload_frame_sha256", ""))):
                raise GitLabEpisodeError(
                    "gitlab_saved_state_or_fresh_reset_not_verified")
            saved_ref = _artifact(out_dir, "saved-artifact.private.json", saved)
            baseline_ref = _artifact(out_dir, "baseline.private.json",
                                     session.baseline_semantic)
            restored_ref = _artifact(out_dir, "restored.private.json",
                                     session.reset_semantic)
            common = {"cell_id": self.cell_id,
                      "task_id": task["task_id"],
                      "package_sha256": task["package_sha256"]}
            state = {
                "schema": teacher.STATE_SCHEMA, **common,
                "independent_of_actor": True,
                "native_save_observed": True,
                "target_state_pass": True,
                "no_regression_pass": True,
                "saved_artifact_sha256": saved_ref["sha256"],
                "saved_artifact_ref": saved_ref,
                "verifier_sha256": self.verifier_sha256,
                "evaluator_result": "pass",
            }
            reset_receipt = {
                "schema": teacher.RESET_SCHEMA, **common,
                "independent_of_actor": True,
                "fresh_environment": True,
                "state_equivalence_pass": True,
                "sandbox_terminated": True,
                "baseline_semantic_sha256": baseline_ref["sha256"],
                "restored_semantic_sha256": restored_ref["sha256"],
                "baseline_state_ref": baseline_ref,
                "restored_state_ref": restored_ref,
            }
            action_ref = _write_new(out_dir / "actions.private.json",
                                    _canonical(trace_rows))
            state_ref = _write_new(out_dir / "saved-state.private.json",
                                   _canonical(state))
            reset_ref = _write_new(out_dir / "reset.private.json",
                                   _canonical(reset_receipt))
            episode = {
                "schema": teacher.EPISODE_SCHEMA, "status": "admitted",
                "split": "train", **common,
                "action_profile": self.action_profile,
                "teacher_model": teacher.matrix.TEACHER,
                "original_software_gui": True,
                "original_surface": self.original_surface,
                "runtime_sha256": self.runtime_sha256,
                "adapter_sha256": self.adapter_sha256,
                "frame_refs": frame_refs,
                "action_trace_ref": action_ref,
                "saved_state_ref": state_ref,
                "reset_ref": reset_ref,
                "teacher_result_sha256s": teacher_shas,
                "e2b_attempt_ids": [],
            }
            receipt_ref = _write_new(out_dir / "episode.private.json",
                                     _canonical(episode))
            return {"episode_receipt_path": str(out_dir / receipt_ref["path"]),
                    "episode_receipt_sha256": receipt_ref["sha256"]}
        except BaseException as exc:
            failure = out_dir / "failure.private.json"
            if not failure.exists():
                _write_new(failure, _canonical({
                    "schema": "envloop-gitlab-v066-teacher-failure-v1",
                    "failure_type": type(exc).__name__,
                    "reason": str(exc) if isinstance(exc, GitLabEpisodeError)
                    else "external_callback_or_runtime_failure",
                    "observed_frame_count": len(frame_refs),
                    "applied_action_count": len(trace_rows),
                    "post_restore_exact": (session.post_restore_exact
                                           if session is not None else None),
                    "environment_terminated": (
                        session.environment_terminated if session is not None
                        else None),
                    "provider_or_e2b_replay_authorized": False,
                }))
            raise


__all__ = ["GitLabTrainEpisodeWorker", "RealGitLabTrainBackend",
           "runtime_sha256", "verifier_sha256", "adapter_sha256"]
