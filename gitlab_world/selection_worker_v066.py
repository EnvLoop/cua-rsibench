"""Prospective 20-task Qwen v0.6.6 selection worker for original GitLab CE.

Only a frozen campaign's ``start_selection_attempt`` view can enter. This
worker never opens a final package, sends gold to the student, fabricates an
E2B lease for self-hosted GitLab, or replays an uncertain paid call. Live use
defaults off until six-cell ratification and source/cost bindings are frozen.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Callable, Iterator

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench import full_study_matrix_v1 as matrix
from cursibench import scale_action_output_v066 as output_v066
from cursibench.scale_action_contract import ContractError, Observation
from cursibench.scale_action_contract_v066 import (
    ACTION_PROFILE_VERSION, validate_action,
)
from cursibench.scale_vision_proxy import (
    MODEL, PROCESSOR, RENDERER, QwenVisionRenderer, TinkerVisionBackend,
)

from . import (bootstrap, factory, operators, reset, runtime,
               selection_oracle_v066 as oracle,
               teacher_episode_worker_v066 as train, verify,
               vision_actor_v066_train as actor)


ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAMPLER_PATH = re.compile(r"tinker://[^\s/]+/sampler_weights/[^\s/]+\Z")
RESULT_SCHEMA = "cua-full-study-selection-saved-result-v1"
TASK_RECEIPT_SCHEMA = "envloop-gitlab-v066-selection-task-private-v1"
BATCH_RECEIPT_SCHEMA = "envloop-gitlab-v066-selection-batch-private-v1"
RUNTIME_FILES = (
    "gitlab_world/selection_worker_v066.py",
    "gitlab_world/selection_oracle_v066.py",
    "gitlab_world/teacher_episode_worker_v066.py",
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


class GitLabSelectionError(RuntimeError):
    """Fixed failure codes with no private task or provider body."""


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
    return _hash(_canonical({relative: _hash((ROOT / relative).read_bytes())
                             for relative in (
                                 "gitlab_world/verify.py",
                                 "gitlab_world/selection_oracle_v066.py")}))


def adapter_sha256() -> str:
    return train.adapter_sha256()


def _write_new(path: Path, raw: bytes) -> dict[str, str]:
    return train._write_new(path, raw)


def _private_json(path: Path, root: Path) -> tuple[dict, bytes]:
    if (not path.is_file() or path.is_symlink() or
            not path.resolve().is_relative_to(root.resolve()) or
            path.stat().st_mode & 0o077 or path.stat().st_size > 8_000_000):
        raise GitLabSelectionError("private_checkpoint_result_missing_or_unsafe")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GitLabSelectionError("private_checkpoint_result_invalid_json") from None
    if type(value) is not dict:
        raise GitLabSelectionError("private_checkpoint_result_not_object")
    return value, raw


async def _dispatch_gui(page, frame, action: dict) -> dict:
    """Physical current-frame GUI dispatch; no selector, URL or API action."""
    checked = validate_action(action, frame.observation,
                              current_frame_id=frame.observation.frame_id)
    await actor._current(page, frame, checked)
    kind = checked["type"]
    if kind == "finish":
        pass
    elif kind == "wait":
        await page.wait_for_timeout(checked["duration_ms"])
    elif kind in ("click", "double_click"):
        target = checked["target"]
        if "ref" in target:
            handle = frame.handles[target["ref"]]
            if kind == "double_click":
                await handle.dblclick(timeout=15000)
            else:
                await handle.click(timeout=15000)
        elif kind == "double_click":
            await page.mouse.dblclick(target["x"], target["y"])
        else:
            await page.mouse.click(target["x"], target["y"])
    elif kind == "type":
        if "target" not in checked:
            if checked["mode"] != "insert":
                raise ContractError("invalid_action")
            await page.keyboard.insert_text(checked["text"])
        else:
            target = checked["target"]
            if "ref" in target:
                handle = frame.handles[target["ref"]]
                if checked["mode"] == "fill":
                    await handle.fill(checked["text"], timeout=15000)
                else:
                    await handle.focus()
                    await page.keyboard.insert_text(checked["text"])
            else:
                await page.mouse.click(target["x"], target["y"])
                if checked["mode"] == "fill":
                    await page.keyboard.press("ControlOrMeta+A")
                await page.keyboard.insert_text(checked["text"])
    elif kind == "key":
        if "target" in checked:
            target = checked["target"]
            if "ref" in target:
                await frame.handles[target["ref"]].focus()
            else:
                await page.mouse.click(target["x"], target["y"])
        await page.keyboard.press(checked["key"])
    elif kind == "scroll":
        if "target" in checked:
            target = checked["target"]
            if "ref" in target:
                await frame.handles[target["ref"]].hover()
            else:
                await page.mouse.move(target["x"], target["y"])
        await page.mouse.wheel(checked["dx"], checked["dy"])
    elif kind == "drag":
        x1, y1 = await actor.prior._point(page, checked["from"], frame.handles)
        x2, y2 = await actor.prior._point(page, checked["to"], frame.handles)
        await page.mouse.move(x1, y1)
        await page.mouse.down()
        await page.mouse.move(x2, y2, steps=8)
        await page.mouse.up()
    else:
        raise ContractError("invalid_action")
    return {"status": "applied", "code": "ok"}


class _RealSelectionSession(train._RealGitLabSession):
    async def _dispatch(self, action: dict) -> dict:
        return await _dispatch_gui(self.page, self.latest, action)

    def read_saved_state(self) -> dict:
        if not self.loop.call(self._check_scoped()):
            raise GitLabSelectionError("actor_left_scoped_selection_project")
        reload_sha = self.loop.call(self._reload())
        after = verify.state_snapshot()
        score = oracle.evaluate_selection_task(
            self.original_task,
            self.baseline_semantic["business_snapshot"], after)
        return {"business_snapshot": after,
                "independent_score": score,
                "gui_reload_frame_sha256": reload_sha,
                "original_gitlab_ce": True,
                "postgresql_and_git_readback": True,
                "model_finished": self.finished}


class RealGitLabSelectionBackend(train.RealGitLabTrainBackend):
    """One selected task per fresh, non-admin, original-GitLab cold clone."""

    def _load_selection_task(self, identity: dict) -> tuple[dict, dict, dict, dict]:
        private = runtime.PRIVATE
        needed = (bootstrap.WORLD_FILE, bootstrap.PROGRESS_FILE,
                  operators.CREDENTIALS, operators.RECEIPT,
                  private / "baseline-persisted-state.json", reset.STATE_FILE)
        if (not train._mode_private(private, directory=True) or
                any(not train._mode_private(path, directory=False)
                    for path in needed)):
            raise GitLabSelectionError("private_selection_world_missing_or_unsafe")
        world = bootstrap.world()
        selection = [row for row in world["tasks"]
                     if row["partition"] == "selection"]
        other_ids = {row["task_id"] for row in bootstrap.all_tasks(world)
                     if row["partition"] != "selection"}
        matches = [row for row in selection
                   if row["task_id"] == identity["task_id"]]
        if (len(selection) != 20 or
                len({row["task_id"] for row in selection}) != 20 or
                len(matches) != 1 or identity["task_id"] in other_ids or
                identity["package_sha256"] !=
                factory.sha256(factory.canonical(matches[0]))):
            raise GitLabSelectionError("task_not_in_private_selection_partition")
        original = matches[0]
        projects = [row for row in bootstrap.all_projects(world)
                    if row["full_path"] == original["project_family"]]
        if len(projects) != 1 or projects[0]["partition"] != "selection":
            raise GitLabSelectionError("project_not_in_selection_partition")
        roster = json.loads(operators.CREDENTIALS.read_bytes())
        operator = json.loads(operators.RECEIPT.read_bytes())
        progress = json.loads(bootstrap.PROGRESS_FILE.read_bytes())
        own = operator.get("identities", {}).get("selection", {})
        if (set(roster) != set(operators.PARTITIONS) or
                type(roster.get("selection")) is not dict or
                type(roster["selection"].get("username")) is not str or
                type(roster["selection"].get("password")) is not str or
                not roster["selection"]["password"] or
                own.get("group_id") != progress["groups"].get(
                    projects[0]["group_path"]) or
                operator.get("root_admin_is_actor") is not False):
            raise GitLabSelectionError("scoped_selection_operator_invalid")
        task = {"task_id": original["task_id"],
                "package_sha256": identity["package_sha256"],
                "visible_instruction": original["prompt"]}
        return original, projects[0], roster["selection"], task

    @contextmanager
    def open(self, identity: dict) -> Iterator[_RealSelectionSession]:
        original, project, credentials, task = self._load_selection_task(identity)
        actor.assert_shared_stack()
        with self._lease():
            baseline = reset._baseline()
            if baseline["business_sha256"] != reset._state()[
                    "baseline_business_sha256"]:
                raise GitLabSelectionError("frozen_baseline_changed")
            pre_reset = reset.reset()
            if (pre_reset.get("cold_reset") is not True or
                    pre_reset.get("same_business_sha256") is not True):
                raise GitLabSelectionError("pre_selection_cold_reset_failed")
            before = verify.state_snapshot()
            before_proof = runtime.proof(runtime.WORLD)
            if (before != baseline or before_proof["image_id"] != runtime.IMAGE_ID or
                    oracle.evaluate_selection_task(
                        original, before, before)["reward"] != 0.0):
                raise GitLabSelectionError("selection_baseline_not_exact")
            semantic = {"business_snapshot": before,
                        "seed_lowerdirs_sha256": _hash(_canonical(
                            reset._state()["seed_volume_lowerdirs"])),
                        "pinned_image_id": before_proof["image_id"]}
            loop = train._AsyncLoop()
            opened = None
            session = None
            failure = None
            try:
                loop.start()
                opened = loop.call(self._start_browser(project, credentials),
                                   timeout=300)
                session = _RealSelectionSession(
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
                        "pinned_image_id": after_proof["image_id"]}
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
                    raise GitLabSelectionError(
                        "post_selection_cold_reset_failed") from failure


class _RealTinkerSampler:
    """Open the selected sampler only inside a prior paid reservation."""

    def __init__(self, *, checkpoint_path: str,
                 checkpoint_sha256: str, vision: QwenVisionRenderer,
                 seed: int, temperature: float, max_output_tokens: int,
                 campaign_metadata: dict):
        self.checkpoint_path = checkpoint_path
        self.checkpoint_sha256 = checkpoint_sha256
        self.vision = vision
        self.seed = seed
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.campaign_metadata = campaign_metadata
        self.service = None
        self.backend = None
        self.closed = False

    def __call__(self, request: dict, prompt) -> dict:
        if self.closed:
            raise GitLabSelectionError("sampler_after_close")
        if self.backend is None:
            import tinker
            self.service = tinker.ServiceClient(
                user_metadata=self.campaign_metadata)
            self.backend = TinkerVisionBackend.from_service(
                self.service, self.vision,
                checkpoint=self.checkpoint_path, seed=self.seed)
            if self.backend.sampling_client.get_base_model() != MODEL:
                raise GitLabSelectionError("selected_sampler_base_model_changed")
        from tinker import types
        started = time.monotonic()
        response = self.backend.sampling_client.sample(
            prompt=prompt, num_samples=1,
            sampling_params=types.SamplingParams(
                max_tokens=self.max_output_tokens,
                temperature=self.temperature, seed=self.seed,
                stop=self.vision.renderer.get_stop_sequences()))\
            .result(timeout=240)
        if len(response.sequences) != 1:
            raise GitLabSelectionError("selected_sampler_sequence_count_invalid")
        sequence = response.sequences[0]
        tokens = sequence.tokens
        if (not isinstance(tokens, (list, tuple)) or
                any(type(token) is not int or token < 0 for token in tokens) or
                len(tokens) > self.max_output_tokens or
                getattr(sequence, "stop_reason", None) not in
                (None, "stop", "length")):
            raise GitLabSelectionError("selected_sampler_response_invalid")
        cached = getattr(response, "prompt_cache_hit_tokens", None)
        if cached is not None and (type(cached) is not int or
                                   not 0 <= cached <= request["input_tokens"]):
            raise GitLabSelectionError("selected_sampler_cache_usage_invalid")
        text = self.backend.decode(tokens)
        if type(text) is not str or len(text.encode()) > 65_536:
            raise GitLabSelectionError("selected_sampler_decoded_text_invalid")
        return {
            "schema": "envloop-gitlab-v066-selection-sampler-result-v1",
            "status": "completed", "reported_model": MODEL,
            "checkpoint_path_sha256": self.checkpoint_sha256,
            "text": text,
            "stop_reason": getattr(sequence, "stop_reason", None),
            "elapsed_seconds": time.monotonic() - started,
            "usage": {
                "input_tokens": request["input_tokens"],
                "output_tokens": len(tokens),
                "image_tokens": request["image_tokens"],
                "prompt_cache_hit_tokens": cached,
                "provider_billed_tokens": None,
                "basis": "rendered_input_and_returned_output_not_invoice",
            },
        }

    def close(self, *, success: bool) -> None:
        self.closed = True
        if self.service is not None:
            self.service.close("success" if success else "errored").result(
                timeout=30)


class GitLabSelectionWorker:
    """One complete, frozen 20-task selection attempt, never a final run."""

    cell_id = "gitlab"
    action_profile = ACTION_PROFILE_VERSION
    requires_e2b = False
    original_software_gui = True
    original_surface = "web"

    def __init__(self, *, enable_live: bool = False):
        self.enable_live = enable_live
        self.runtime_sha256 = runtime_sha256()
        self.verifier_sha256 = verifier_sha256()
        self.adapter_sha256 = adapter_sha256()
        self.backend = RealGitLabSelectionBackend()

    def _require_frozen(self, session, started: dict) -> tuple[dict, dict]:
        if self.enable_live is not True:
            raise GitLabSelectionError("selection_requires_real_six_cell_freeze")
        try:
            cell_id, ratification = teacher._frozen_session(session)
        except Exception:
            raise GitLabSelectionError("selection_requires_real_six_cell_freeze") from None
        cell = next((row for row in session.study.plan["cells"]
                     if row["cell_id"] == cell_id), None)
        profile = ratification.get("cell_profiles", {}).get(cell_id, {})
        if (cell_id != self.cell_id or cell is None or
                profile.get("adapter_sha256") != self.adapter_sha256 or
                cell["matched_bindings"]["runtime"] != self.runtime_sha256 or
                cell["matched_bindings"]["verifier"] != self.verifier_sha256 or
                self.runtime_sha256 != runtime_sha256() or
                self.verifier_sha256 != verifier_sha256() or
                self.adapter_sha256 != adapter_sha256()):
            raise GitLabSelectionError("selection_source_bindings_not_frozen")
        actor.assert_shared_stack()
        required = {"attempt_id", "checkpoint_path_sha256",
                    "selection_tasks", "selection_identities_sha256",
                    "task_count"}
        if type(started) is not dict or set(started) != required:
            raise GitLabSelectionError("selection_start_result_invalid")
        tasks = started["selection_tasks"]
        expected = session.views["selection"]
        events = [row for row in session._events("selection_started")
                  if row["data"].get("attempt_id") == started["attempt_id"]]
        if (type(tasks) is not list or len(tasks) != 20 or
                any(type(row) is not dict or set(row) !=
                    {"task_id", "package_sha256"} for row in tasks) or
                len({row["task_id"] for row in tasks}) != 20 or
                tasks != expected or started["task_count"] != 20 or
                type(started["attempt_id"]) is not str or
                len(started["attempt_id"]) > 100 or
                type(started["checkpoint_path_sha256"]) is not str or
                not HEX64.fullmatch(started["checkpoint_path_sha256"]) or
                started["selection_identities_sha256"] !=
                _hash(_canonical(tasks)) or
                len(events) != 1 or
                events[0]["data"].get("selection_identities_sha256") !=
                started["selection_identities_sha256"] or
                events[0]["data"].get("checkpoint_path_sha256") !=
                started["checkpoint_path_sha256"]):
            raise GitLabSelectionError("selection_start_or_view_changed")
        return cell, events[0]["data"]

    def _resolve_checkpoint_path(self, session, checkpoint_sha256: str) -> str:
        rows = [row["data"] for row in session._events("tinker_checkpoint")
                if row["data"].get("checkpoint_path_sha256") ==
                checkpoint_sha256]
        if len(rows) != 1:
            raise GitLabSelectionError("selection_checkpoint_not_unique")
        paid_id = rows[0]["paid_attempt_id"]
        path = session.directory / f"{paid_id}.result.private.json"
        result, raw = _private_json(path, session.directory)
        paid = [row["data"] for row in session._events("paid_result")
                if row["data"].get("attempt_id") == paid_id]
        candidate = result.get("checkpoint_path")
        if (len(paid) != 1 or paid[0].get("result_sha256") != _hash(raw) or
                type(candidate) is not str or
                not SAMPLER_PATH.fullmatch(candidate) or
                _hash(candidate.encode()) != checkpoint_sha256 or
                result.get("observed_base_model") != MODEL):
            raise GitLabSelectionError("selection_checkpoint_path_not_bound")
        return candidate

    def _policy(self, session, cell: dict) -> tuple[dict, dict, Decimal]:
        training, _training_sha = session.study.student_training_configuration()
        sampling = cell["sampling"]
        execution = cell["execution"]
        cap = Decimal(session.intent["storage_application_usd_cap"])
        if (training.get("action_profile") != ACTION_PROFILE_VERSION or
                training.get("model") != MODEL or
                type(sampling) is not dict or
                type(execution) is not dict or
                type(sampling.get("seed")) is not int or
                type(sampling.get("max_output_tokens")) is not int or
                not 0 < sampling["max_output_tokens"] <= 4096 or
                type(execution.get("max_actions_per_task")) is not int or
                not 0 < execution["max_actions_per_task"] <= 90 or
                type(execution.get("max_wall_seconds_per_task")) is not int or
                not 0 < execution["max_wall_seconds_per_task"] <= 2880 or
                not cap.is_finite() or cap <= 0):
            raise GitLabSelectionError("selection_frozen_sampling_or_cost_invalid")
        try:
            temperature = Decimal(str(sampling["temperature"]))
        except Exception:
            raise GitLabSelectionError("selection_temperature_invalid") from None
        if not temperature.is_finite() or not 0 <= temperature <= 2:
            raise GitLabSelectionError("selection_temperature_invalid")
        app_quote = (cap / Decimal(20)).quantize(
            Decimal("0.000000001"), rounding=ROUND_DOWN)
        worst_nominal = (cap * Decimal(
            execution["max_wall_seconds_per_task"]) /
            Decimal(matrix.CAMPAIGN_HOURS * 3600)).quantize(
                Decimal("0.000000001"), rounding=ROUND_CEILING)
        if app_quote <= 0 or worst_nominal > app_quote:
            raise GitLabSelectionError("selection_application_cap_cannot_cover_task")
        return training, {**sampling, **execution,
                          "temperature": float(temperature)}, app_quote

    def _check_output(self, session, out_dir: Path) -> None:
        work = Path(session.study.repo_root) / "work"
        if (not work.is_dir() or work.is_symlink() or
                out_dir.exists() or out_dir.is_symlink() or
                not train._mode_private(out_dir.parent, directory=True) or
                not out_dir.resolve().is_relative_to(work.resolve())):
            raise GitLabSelectionError("selection_private_output_new_work_dir_required")

    @staticmethod
    def _model_quote(training: dict, prompt_tokens: int,
                     output_tokens: int) -> str:
        amount = ((Decimal(prompt_tokens) *
                   Decimal(training["prefill_usd_per_million_tokens"]) +
                   Decimal(output_tokens) *
                   Decimal(training["sample_usd_per_million_tokens"])) /
                  Decimal(1_000_000) *
                  Decimal(training["billing_multiplier_upper"]))
        quote = amount.quantize(Decimal("0.000000001"),
                                rounding=ROUND_CEILING)
        if quote <= 0:
            raise GitLabSelectionError("selection_sampler_quote_not_positive")
        return str(quote)

    @staticmethod
    def _render_observation(vision: QwenVisionRenderer,
                            observation: Observation,
                            max_input_tokens: int):
        from PIL import Image
        rendered = output_v066.render_for_model(observation)
        with Image.open(io.BytesIO(rendered["image_bytes"])) as opened:
            image = opened.convert("RGB")
        prompt, info = vision.render(
            image, rendered["instruction"], rendered["visible_text"])
        if (type(info) is not dict or
                type(info.get("input_tokens")) is not int or
                type(info.get("image_tokens")) is not int or
                not 0 < info["image_tokens"] < info["input_tokens"] <=
                max_input_tokens or
                "ImageChunk" not in info.get("chunk_types", ()) or
                prompt.length != info["input_tokens"]):
            raise GitLabSelectionError("selection_qwen_image_render_invalid")
        return prompt, info, rendered

    @staticmethod
    def _load_vision() -> QwenVisionRenderer:
        vision = QwenVisionRenderer.load()
        if (type(vision.identity) is not dict or
                vision.identity.get("model") != MODEL or
                vision.identity.get("renderer") != RENDERER or
                vision.identity.get("image_processor") != PROCESSOR):
            raise GitLabSelectionError("selection_qwen_renderer_identity_changed")
        return vision

    def _sample_action(self, *, session, started: dict, task: dict,
                       ordinal: int, observation: Observation,
                       active: _RealSelectionSession,
                       training: dict, policy: dict,
                       checkpoint_sha256: str, vision: QwenVisionRenderer,
                       provider: Callable[[dict, object], dict]) -> dict:
        if active.current_frame_id() != observation.frame_id:
            raise GitLabSelectionError("selection_frame_changed_before_reservation")
        prompt, info, rendered = self._render_observation(
            vision, observation, training["max_supervised_tokens"])
        request = {
            "schema": "cua-full-study-selection-sampling-request-v1",
            "cell_id": self.cell_id,
            "selection_attempt": started["attempt_id"],
            "task_id": task["task_id"],
            "package_sha256": task["package_sha256"],
            "checkpoint_path_sha256": checkpoint_sha256,
            "step": observation.step,
            "frame_id": observation.frame_id,
            "frame_sha256": _hash(observation.screenshot_bytes),
            "rendered_prompt_sha256": _hash(_canonical({
                "instruction": rendered["instruction"],
                "visible_text": rendered["visible_text"],
                "frame_sha256": _hash(observation.screenshot_bytes)})),
            "input_tokens": info["input_tokens"],
            "image_tokens": info["image_tokens"],
            "max_output_tokens": policy["max_output_tokens"],
            "seed": policy["seed"],
            "temperature": str(policy["temperature"]),
        }
        paid_id = (started["attempt_id"] +
                   f"-sample-{ordinal:03d}-{observation.step:03d}")
        quote = self._model_quote(
            training, info["input_tokens"], policy["max_output_tokens"])
        paid = session.dispatch_paid(
            attempt_id=paid_id, category="tinker",
            work={"selection_attempt": started["attempt_id"],
                  "task_id": task["task_id"],
                  "package_sha256": task["package_sha256"],
                  "step": observation.step,
                  "checkpoint_path_sha256": checkpoint_sha256,
                  "frame_sha256": request["frame_sha256"]},
            request=request, reserve_usd=quote,
            resource_reservation={},
            provider=lambda _request: provider(request, prompt))
        if active.current_frame_id() != observation.frame_id:
            raise GitLabSelectionError("selection_frame_changed_after_paid_sample")
        result = paid["result"]
        usage = result.get("usage") if type(result) is dict else None
        provider_elapsed = (result.get("elapsed_seconds")
                            if type(result) is dict else None)
        if (type(result) is not dict or
                result.get("schema") !=
                "envloop-gitlab-v066-selection-sampler-result-v1" or
                result.get("status") != "completed" or
                result.get("reported_model") != MODEL or
                result.get("checkpoint_path_sha256") != checkpoint_sha256 or
                type(result.get("text")) is not str or
                len(result["text"].encode()) > 65_536 or
                type(usage) is not dict or
                usage.get("input_tokens") != info["input_tokens"] or
                type(usage.get("output_tokens")) is not int or
                not 0 <= usage["output_tokens"] <=
                policy["max_output_tokens"] or
                usage.get("image_tokens") != info["image_tokens"] or
                usage.get("provider_billed_tokens") is not None or
                usage.get("basis") !=
                "rendered_input_and_returned_output_not_invoice" or
                type(provider_elapsed) not in (int, float) or
                not math.isfinite(provider_elapsed) or
                provider_elapsed < 0):
            raise GitLabSelectionError("selection_sampler_model_or_usage_invalid")
        try:
            action = output_v066.normalize_model_action(
                result["text"], observation,
                current_frame_id=active.current_frame_id())
        except ContractError as exc:
            model_code = exc.code
            if exc.code == "stale_frame" and active.current_frame_id() == \
                    observation.frame_id:
                # The physical frame is still current. In this validator a
                # nonexistent advertised ref shares the stale_frame code;
                # classify that invented ref as a model action failure.
                model_code = "invalid_model_ref"
            if model_code not in {"invalid_action_json", "invalid_action",
                                  "invalid_model_ref"}:
                raise GitLabSelectionError("selection_action_frame_or_expiry_invalid") from None
            return {"paid_attempt_id": paid_id,
                    "paid_result_sha256": paid["result_sha256"],
                    "reserve_usd": quote,
                    "usage": usage,
                    "provider_elapsed_seconds": provider_elapsed,
                    "action": None,
                    "model_error_code": model_code,
                    "model_text_sha256": _hash(result["text"].encode())}
        if active.current_frame_id() != observation.frame_id:
            raise GitLabSelectionError("selection_frame_changed_before_gui_dispatch")
        return {"paid_attempt_id": paid_id,
                "paid_result_sha256": paid["result_sha256"],
                "reserve_usd": quote,
                "usage": usage,
                "provider_elapsed_seconds": provider_elapsed,
                "action": action,
                "model_error_code": None,
                "model_text_sha256": _hash(result["text"].encode())}

    def _task_episode(self, *, session, started: dict, identity: dict,
                      ordinal: int, out_dir: Path,
                      training: dict, policy: dict,
                      app_quote: Decimal, vision: QwenVisionRenderer,
                      checkpoint_sha256: str,
                      sampler_provider: Callable[[dict, object], dict]) -> dict:
        out_dir.mkdir(mode=0o700)
        (out_dir / "frames").mkdir(mode=0o700)
        (out_dir / "artifacts").mkdir(mode=0o700)
        app_paid_id = started["attempt_id"] + f"-app-{ordinal:03d}"
        runtime_started = time.monotonic()
        actor_started = None
        actor_elapsed = None
        lease = None
        active = None
        app_paid = None
        paid_ids = []
        sample_rows = []
        trace = []
        frame_refs = []
        saved = None
        outcome = None

        def start_application(_request):
            nonlocal lease, active
            lease = self.backend.open(identity)
            active = lease.__enter__()
            if (active.pre_restore_exact is not True or
                    type(active.baseline_semantic) is not dict):
                raise GitLabSelectionError("selection_baseline_not_exact")
            return {
                "schema": "envloop-gitlab-selection-local-runtime-start-v1",
                "status": "active",
                "baseline_business_sha256": active.baseline_semantic[
                    "business_snapshot"]["business_sha256"],
                "runtime_sha256": self.runtime_sha256,
                "local_runtime_invoice": None,
            }

        app_request = {
            "schema": "cua-full-study-selection-application-runtime-request-v1",
            "selection_attempt": started["attempt_id"],
            "cell_id": self.cell_id,
            "task_id": identity["task_id"],
            "package_sha256": identity["package_sha256"],
            "checkpoint_path_sha256": checkpoint_sha256,
            "runtime_sha256": self.runtime_sha256,
            "max_wall_seconds": policy["max_wall_seconds_per_task"],
            "nominal_upper_usd": str(app_quote),
        }
        failure = None
        try:
            app_paid = session.dispatch_paid(
                attempt_id=app_paid_id, category="storage_application",
                work=app_request, request=app_request,
                reserve_usd=str(app_quote), resource_reservation={},
                provider=start_application)
            paid_ids.append(app_paid_id)
            if (app_paid["result"].get("status") != "active" or
                    active is None):
                raise GitLabSelectionError("selection_application_lease_invalid")
            actor_started = time.monotonic()
            memory = ""
            for step in range(policy["max_actions_per_task"]):
                elapsed = time.monotonic() - actor_started
                if elapsed > policy["max_wall_seconds_per_task"]:
                    outcome = "task_wall_timeout"
                    break
                observation = active.observe(memory=memory)
                if (type(observation) is not Observation or
                        observation.task_id != identity["task_id"] or
                        observation.task_binding_sha256 !=
                        identity["package_sha256"] or
                        observation.step != step):
                    raise GitLabSelectionError("selection_observation_not_bound")
                frame = _write_new(
                    out_dir / "frames" / f"step-{step:03d}.png",
                    observation.screenshot_bytes)
                frame_refs.append({"path": "frames/" + frame["path"],
                                   "sha256": frame["sha256"]})
                intended_sample_id = (
                    started["attempt_id"] +
                    f"-sample-{ordinal:03d}-{observation.step:03d}")
                paid_ids.append(intended_sample_id)
                sampled = self._sample_action(
                    session=session, started=started, task=identity,
                    ordinal=ordinal, observation=observation,
                    active=active, training=training, policy=policy,
                    checkpoint_sha256=checkpoint_sha256, vision=vision,
                    provider=sampler_provider)
                if sampled["paid_attempt_id"] != intended_sample_id:
                    raise GitLabSelectionError(
                        "selection_sampler_paid_identity_changed")
                sample_rows.append(sampled)
                row = {
                    "step": step, "frame_ref": frame_refs[-1],
                    "paid_attempt_id": sampled["paid_attempt_id"],
                    "paid_result_sha256": sampled["paid_result_sha256"],
                    "model_text_sha256": sampled["model_text_sha256"],
                    "usage": sampled["usage"],
                    "provider_elapsed_seconds":
                        sampled["provider_elapsed_seconds"],
                    "model_error_code": sampled["model_error_code"],
                    "action": sampled["action"],
                }
                trace.append(row)
                if sampled["action"] is None:
                    outcome = "model_invalid_action"
                    break
                active.dispatch(sampled["action"])
                memory = sampled["action"]["memory"]
                if sampled["action"]["type"] == "finish":
                    outcome = "finished"
                    break
            else:
                outcome = "action_budget_exhausted"
            saved = active.read_saved_state()
            actor_elapsed = time.monotonic() - actor_started
            if actor_elapsed > policy["max_wall_seconds_per_task"]:
                outcome = "task_wall_timeout"
        except BaseException as exc:
            failure = exc
            try:
                _write_new(out_dir / "actions-partial.private.json",
                           _canonical(trace))
                _write_new(out_dir / "task-failure.private.json",
                           _canonical({
                               "schema":
                                   "envloop-gitlab-v066-selection-task-failure-v1",
                               "task_id": identity["task_id"],
                               "package_sha256": identity["package_sha256"],
                               "checkpoint_sha256": checkpoint_sha256,
                               "observed_frame_refs": frame_refs,
                               "intended_application_paid_attempt_id":
                                   app_paid_id,
                               "attempted_paid_attempt_ids": paid_ids,
                               "failure_type": type(exc).__name__,
                               "automatic_paid_replay_authorized": False,
                               "cold_reset_pending_at_record": True,
                           }))
            except Exception:
                pass
            raise
        finally:
            if lease is not None:
                try:
                    lease.__exit__(type(failure) if failure else None,
                                   failure,
                                   failure.__traceback__ if failure else None)
                except Exception:
                    if not (out_dir / "actions-partial.private.json").exists():
                        try:
                            _write_new(out_dir / "actions-partial.private.json",
                                       _canonical(trace))
                        except Exception:
                            pass
                    raise GitLabSelectionError(
                        "selection_application_cold_reset_failed") from failure

        if (active is None or not active.pre_restore_exact or
                not active.post_restore_exact or
                not active.environment_terminated or
                active.reset_semantic != active.baseline_semantic or
                type(saved) is not dict or
                saved.get("original_gitlab_ce") is not True or
                saved.get("postgresql_and_git_readback") is not True or
                type(saved.get("independent_score")) is not dict or
                saved["independent_score"].get("reward") not in (0.0, 1.0) or
                not HEX64.fullmatch(
                    saved.get("gui_reload_frame_sha256", ""))):
            raise GitLabSelectionError(
                "selection_saved_state_or_exact_reset_missing")
        if not sample_rows:
            raise GitLabSelectionError(
                "selection_task_has_no_tinker_paid_attempt")
        score = int(saved["independent_score"]["reward"] == 1.0 and
                    saved["independent_score"].get("checks_passed") is True)
        elapsed = time.monotonic() - runtime_started
        cap = Decimal(session.intent["storage_application_usd_cap"])
        nominal = (cap * Decimal(str(elapsed)) /
                   Decimal(matrix.CAMPAIGN_HOURS * 3600)).quantize(
                       Decimal("0.000000001"), rounding=ROUND_CEILING)
        if nominal > app_quote:
            raise GitLabSelectionError("selection_application_nominal_overrun")
        saved_ref = train._artifact(
            out_dir, "saved-artifact.private.json", saved)
        baseline_ref = train._artifact(
            out_dir, "baseline.private.json", active.baseline_semantic)
        restored_ref = train._artifact(
            out_dir, "restored.private.json", active.reset_semantic)
        verifier = {
            "schema": "envloop-gitlab-v066-selection-independent-verifier-v1",
            "task_id": identity["task_id"],
            "package_sha256": identity["package_sha256"],
            "score": score, "model_outcome": outcome,
            "persisted_oracle": saved["independent_score"],
            "native_reload_frame_sha256": saved["gui_reload_frame_sha256"],
            "verifier_sha256": self.verifier_sha256,
            "independent_of_actor": True,
        }
        reset_receipt = {
            "schema": "envloop-gitlab-v066-selection-cold-reset-v1",
            "task_id": identity["task_id"],
            "package_sha256": identity["package_sha256"],
            "baseline_state_ref": baseline_ref,
            "restored_state_ref": restored_ref,
            "baseline_semantic_sha256": baseline_ref["sha256"],
            "restored_semantic_sha256": restored_ref["sha256"],
            "fresh_environment": True,
            "state_equivalence_pass": True,
            "used_clone_terminated": True,
        }
        cost = {
            "schema": "envloop-gitlab-v066-selection-cost-v1",
            "application_paid_attempt_id": app_paid_id,
            "application_result_sha256": app_paid["result_sha256"],
            "application_nominal_upper_usd": str(app_quote),
            "application_nominal_metered_usd": str(nominal),
            "application_wall_seconds": elapsed,
            "actor_wall_seconds": actor_elapsed,
            "application_invoice_usd": None,
            "application_usage_basis":
                "frozen_self_hosted_cap_divided_by_16_hour_campaign_not_invoice",
            "tinker_paid_attempt_ids": paid_ids[1:],
            "tinker_reserve_usd": str(sum(
                (Decimal(row["reserve_usd"]) for row in sample_rows),
                Decimal(0))),
            "tinker_invoice_usd": None,
            "tinker_usage_basis":
                "rendered_and_returned_tokens_pending_provider_reconciliation",
            "timeout_subtype": (outcome if outcome in
                                {"task_wall_timeout", "action_budget_exhausted"}
                                else None),
        }
        trace_ref = _write_new(out_dir / "actions.private.json",
                               _canonical(trace))
        state_ref = _write_new(out_dir / "saved-state.private.json",
                               _canonical(saved))
        verifier_ref = _write_new(out_dir / "verifier.private.json",
                                  _canonical(verifier))
        reset_ref = _write_new(out_dir / "reset.private.json",
                               _canonical(reset_receipt))
        cost_ref = _write_new(out_dir / "cost.private.json", _canonical(cost))
        task_receipt = {
            "schema": TASK_RECEIPT_SCHEMA,
            "task_id": identity["task_id"],
            "package_sha256": identity["package_sha256"],
            "checkpoint_path_sha256": checkpoint_sha256,
            "score": score, "model_outcome": outcome,
            "frame_refs": frame_refs,
            "action_trace_ref": trace_ref,
            "saved_artifact_ref": saved_ref,
            "saved_state_ref": state_ref,
            "verifier_ref": verifier_ref,
            "reset_ref": reset_ref,
            "cost_ref": cost_ref,
            "paid_attempt_ids": paid_ids,
            "runtime_sha256": self.runtime_sha256,
            "verifier_sha256": self.verifier_sha256,
        }
        receipt_ref = _write_new(out_dir / "task.private.json",
                                 _canonical(task_receipt))
        return {
            "result_row": {
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "score": score,
                "saved_state_sha256": state_ref["sha256"],
                "verifier_receipt_sha256": verifier_ref["sha256"],
                "reset_receipt_sha256": reset_ref["sha256"],
            },
            "paid_attempt_ids": paid_ids,
            "task_receipt_ref": {"path": out_dir.name + "/" +
                                 receipt_ref["path"],
                                 "sha256": receipt_ref["sha256"]},
        }

    @staticmethod
    def _verify_task_receipt(root: Path, item: dict) -> None:
        reference = item["task_receipt_ref"]
        receipt_path = root / reference["path"]
        receipt, raw = _private_json(receipt_path, root)
        row = item["result_row"]
        if (_hash(raw) != reference["sha256"] or
                receipt.get("schema") != TASK_RECEIPT_SCHEMA or
                receipt.get("task_id") != row["task_id"] or
                receipt.get("package_sha256") != row["package_sha256"] or
                receipt.get("score") != row["score"] or
                receipt.get("paid_attempt_ids") != item["paid_attempt_ids"]):
            raise GitLabSelectionError("selection_task_receipt_changed")
        opened = {}
        for key, row_field in (
                ("saved_state_ref", "saved_state_sha256"),
                ("verifier_ref", "verifier_receipt_sha256"),
                ("reset_ref", "reset_receipt_sha256")):
            ref = receipt.get(key)
            if (type(ref) is not dict or set(ref) != {"path", "sha256"} or
                    ref["sha256"] != row[row_field]):
                raise GitLabSelectionError("selection_task_evidence_ref_changed")
            value, evidence_raw = _private_json(
                receipt_path.parent / ref["path"], receipt_path.parent)
            if _hash(evidence_raw) != ref["sha256"]:
                raise GitLabSelectionError("selection_task_evidence_bytes_changed")
            if key == "verifier_ref" and (
                    value.get("independent_of_actor") is not True or
                    value.get("score") != row["score"]):
                raise GitLabSelectionError("selection_independent_verifier_missing")
            if key == "reset_ref" and (
                    value.get("fresh_environment") is not True or
                    value.get("state_equivalence_pass") is not True or
                    value.get("used_clone_terminated") is not True or
                    value.get("baseline_semantic_sha256") !=
                    value.get("restored_semantic_sha256")):
                raise GitLabSelectionError("selection_exact_reset_missing")
            opened[key] = value
        saved_ref = receipt.get("saved_artifact_ref")
        if (type(saved_ref) is not dict or
                set(saved_ref) != {"path", "sha256"} or
                not saved_ref["path"].startswith("artifacts/")):
            raise GitLabSelectionError("selection_saved_artifact_ref_missing")
        saved, saved_raw = _private_json(
            receipt_path.parent / saved_ref["path"], receipt_path.parent)
        if (_hash(saved_raw) != saved_ref["sha256"] or
                saved != opened["saved_state_ref"] or
                opened["verifier_ref"].get("persisted_oracle") !=
                saved.get("independent_score")):
            raise GitLabSelectionError("selection_saved_artifact_or_oracle_changed")
        reset_value = opened["reset_ref"]
        baseline_ref = reset_value.get("baseline_state_ref")
        restored_ref = reset_value.get("restored_state_ref")
        if (type(baseline_ref) is not dict or
                type(restored_ref) is not dict or
                any(type(ref) is not dict or
                    set(ref) != {"path", "sha256"} or
                    not ref["path"].startswith("artifacts/")
                    for ref in (baseline_ref, restored_ref))):
            raise GitLabSelectionError("selection_reset_source_refs_missing")
        baseline, baseline_raw = _private_json(
            receipt_path.parent / baseline_ref["path"], receipt_path.parent)
        restored, restored_raw = _private_json(
            receipt_path.parent / restored_ref["path"], receipt_path.parent)
        if (baseline != restored or
                _hash(baseline_raw) != baseline_ref["sha256"] or
                _hash(restored_raw) != restored_ref["sha256"] or
                baseline_ref["sha256"] !=
                reset_value["baseline_semantic_sha256"] or
                restored_ref["sha256"] !=
                reset_value["restored_semantic_sha256"]):
            raise GitLabSelectionError("selection_reset_source_bytes_changed")
        cost_ref = receipt.get("cost_ref")
        if type(cost_ref) is not dict or set(cost_ref) != {"path", "sha256"}:
            raise GitLabSelectionError("selection_cost_ref_missing")
        cost, cost_raw = _private_json(
            receipt_path.parent / cost_ref["path"], receipt_path.parent)
        if (_hash(cost_raw) != cost_ref["sha256"] or
                cost.get("application_paid_attempt_id") !=
                item["paid_attempt_ids"][0] or
                cost.get("tinker_paid_attempt_ids") !=
                item["paid_attempt_ids"][1:] or
                cost.get("application_invoice_usd") is not None or
                cost.get("tinker_invoice_usd") is not None):
            raise GitLabSelectionError("selection_cost_or_paid_ids_changed")
        for frame_ref in receipt.get("frame_refs", []):
            if (type(frame_ref) is not dict or
                    set(frame_ref) != {"path", "sha256"} or
                    not frame_ref["path"].startswith("frames/")):
                raise GitLabSelectionError("selection_frame_ref_invalid")
            path = receipt_path.parent / frame_ref["path"]
            if (not path.is_file() or path.is_symlink() or
                    not path.resolve().is_relative_to(
                        receipt_path.parent.resolve()) or
                    path.stat().st_mode & 0o077 or
                    _hash(path.read_bytes()) != frame_ref["sha256"]):
                raise GitLabSelectionError("selection_frame_bytes_changed")
        trace_ref = receipt.get("action_trace_ref")
        if (type(trace_ref) is not dict or
                set(trace_ref) != {"path", "sha256"} or
                trace_ref["path"] != "actions.private.json"):
            raise GitLabSelectionError("selection_action_trace_ref_invalid")
        trace_path = receipt_path.parent / trace_ref["path"]
        if (not trace_path.is_file() or trace_path.is_symlink() or
                trace_path.stat().st_mode & 0o077):
            raise GitLabSelectionError("selection_action_trace_missing")
        trace_raw = trace_path.read_bytes()
        try:
            trace_rows = json.loads(trace_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitLabSelectionError("selection_action_trace_invalid") from None
        if (type(trace_rows) is not list or
                _hash(trace_raw) != trace_ref["sha256"] or
                [row.get("paid_attempt_id") for row in trace_rows] !=
                item["paid_attempt_ids"][1:] or
                [row.get("frame_ref") for row in trace_rows] !=
                receipt["frame_refs"]):
            raise GitLabSelectionError("selection_action_trace_or_paid_changed")

    def run_attempt(self, *, session, started: dict, out_dir: Path,
                    sampler_provider: Callable[[dict, object], dict] | None = None) -> dict:
        """Return exactly 20 saved-state rows and every paid attempt ID.

        The caller records a scored or invalid selection in the campaign
        journal only after separately reviewing this mode-0600 output.
        """
        cell, _start_event = self._require_frozen(session, started)
        out_dir = Path(out_dir).absolute()
        self._check_output(session, out_dir)
        checkpoint_path = self._resolve_checkpoint_path(
            session, started["checkpoint_path_sha256"])
        training, policy, app_quote = self._policy(session, cell)
        vision = self._load_vision()
        if sampler_provider is None:
            if not os.environ.get("TINKER_API_KEY"):
                raise GitLabSelectionError("selection_tinker_key_missing_before_paid")
            sampler = _RealTinkerSampler(
                checkpoint_path=checkpoint_path,
                checkpoint_sha256=started["checkpoint_path_sha256"],
                vision=vision, seed=policy["seed"],
                temperature=policy["temperature"],
                max_output_tokens=policy["max_output_tokens"],
                campaign_metadata={
                    "purpose": "envloop-full-study-selection-v066",
                    "study_id": session.study.plan["study_id"],
                    "cell_id": self.cell_id,
                    "researcher_id": session.intent["researcher_id"],
                    "split": "selection",
                })
            sampler_provider = sampler
        else:
            if not callable(sampler_provider):
                raise GitLabSelectionError("selection_sampler_provider_invalid")
            sampler = None
        out_dir.mkdir(mode=0o700)
        items = []
        paid_ids = []
        completed = False
        try:
            for ordinal, identity in enumerate(
                    started["selection_tasks"], 1):
                item = self._task_episode(
                    session=session, started=started,
                    identity=identity, ordinal=ordinal,
                    out_dir=out_dir / f"task-{ordinal:03d}",
                    training=training, policy=policy,
                    app_quote=app_quote, vision=vision,
                    checkpoint_sha256=started["checkpoint_path_sha256"],
                    sampler_provider=sampler_provider)
                self._verify_task_receipt(out_dir, item)
                items.append(item)
                paid_ids.extend(item["paid_attempt_ids"])
            if (len(items) != matrix.SELECTION_PER_CELL or
                    len(paid_ids) != len(set(paid_ids)) or
                    not any("-sample-" in attempt for attempt in paid_ids) or
                    not any("-app-" in attempt for attempt in paid_ids)):
                raise GitLabSelectionError("selection_twenty_task_or_paid_coverage_missing")
            result = {
                "schema": RESULT_SCHEMA,
                "cell_id": self.cell_id,
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "evaluator_isolated": True,
                "tasks": [item["result_row"] for item in items],
            }
            if [row["task_id"] for row in result["tasks"]] != [
                    row["task_id"] for row in started["selection_tasks"]]:
                raise GitLabSelectionError("selection_result_order_or_roster_changed")
            result_ref = _write_new(out_dir / "selection-result.private.json",
                                    _canonical(result))
            task_ledger = {
                "schema": "envloop-gitlab-v066-selection-paid-task-ledger-v1",
                "cell_id": self.cell_id,
                "selection_attempt": started["attempt_id"],
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "selection_identities_sha256":
                    started["selection_identities_sha256"],
                "task_count": len(items),
                "tasks": [{
                    "task_id": item["result_row"]["task_id"],
                    "package_sha256": item["result_row"]["package_sha256"],
                    "checkpoint_sha256":
                        started["checkpoint_path_sha256"],
                    "saved_state_sha256":
                        item["result_row"]["saved_state_sha256"],
                    "verifier_receipt_sha256":
                        item["result_row"]["verifier_receipt_sha256"],
                    "reset_receipt_sha256":
                        item["result_row"]["reset_receipt_sha256"],
                    "application_paid_attempt_id":
                        item["paid_attempt_ids"][0],
                    "qwen_paid_attempt_ids":
                        item["paid_attempt_ids"][1:],
                    "task_receipt_ref": item["task_receipt_ref"],
                } for item in items],
            }
            if any(not row["qwen_paid_attempt_ids"] for row in
                   task_ledger["tasks"]):
                raise GitLabSelectionError("selection_task_paid_coverage_missing")
            task_ledger_ref = _write_new(
                out_dir / "task-ledger.private.json",
                _canonical(task_ledger))
            batch = {
                "schema": BATCH_RECEIPT_SCHEMA,
                "selection_attempt": started["attempt_id"],
                "selection_identities_sha256":
                    started["selection_identities_sha256"],
                "checkpoint_path_sha256":
                    started["checkpoint_path_sha256"],
                "runtime_sha256": self.runtime_sha256,
                "verifier_sha256": self.verifier_sha256,
                "adapter_sha256": self.adapter_sha256,
                "task_count": len(items),
                "task_receipt_refs": [item["task_receipt_ref"]
                                      for item in items],
                "task_ledger_ref": task_ledger_ref,
                "saved_result_ref": result_ref,
                "paid_attempt_ids": paid_ids,
                "tinker_usage_reconciled": False,
                "self_hosted_nominal_cost_reconciled": False,
                "external_provider_invoice_present": False,
                "official_final_tasks_observed": 0,
            }
            batch_ref = _write_new(out_dir / "batch.private.json",
                                   _canonical(batch))
            completed = True
            return {
                "result": result,
                "paid_attempt_ids": paid_ids,
                "batch_receipt_path": str(out_dir / batch_ref["path"]),
                "batch_receipt_sha256": batch_ref["sha256"],
                "task_ledger_path": str(out_dir /
                                        task_ledger_ref["path"]),
                "task_ledger_sha256": task_ledger_ref["sha256"],
                "saved_result_sha256": result_ref["sha256"],
            }
        except BaseException as exc:
            failure_path = out_dir / "failure.private.json"
            if not failure_path.exists():
                _write_new(failure_path, _canonical({
                    "schema": "envloop-gitlab-v066-selection-failure-v1",
                    "selection_attempt": started["attempt_id"],
                    "completed_distinct_tasks": len(items),
                    "completed_paid_attempt_ids": paid_ids,
                    "failure_type": type(exc).__name__,
                    "reason": str(exc) if isinstance(
                        exc, GitLabSelectionError) else
                        "external_callback_or_runtime_failure",
                    "automatic_paid_replay_authorized": False,
                    "official_final_tasks_observed": 0,
                }))
            raise
        finally:
            if sampler is not None:
                sampler.close(success=completed)


__all__ = ["GitLabSelectionWorker", "RealGitLabSelectionBackend",
           "runtime_sha256", "verifier_sha256", "adapter_sha256"]
