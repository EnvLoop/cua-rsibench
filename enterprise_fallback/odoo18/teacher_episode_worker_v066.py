"""Frozen-profile Odoo Community train episode worker for the GUI teacher.

The campaign teacher adapter owns paid model reservations and calls this
worker only after validating the six-cell freeze. This module additionally
requires an exact ratification/source binding and an explicit live switch.
Odoo is self-hosted, so ``requires_e2b`` is false and no E2B callback is used.
The actor receives screenshots and visible controls, never SQL, gold, files,
credentials, RPC, or a selector/action API outside the shared GUI grammar.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, Iterator

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import Observation
from cursibench.scale_action_contract_v066 import (
    ACTION_PROFILE_VERSION, validate_action,
)
from .odoo_v066_train_adapter import OdooV066TrainAdapter, VIEWPORT


ROOT = Path(__file__).resolve().parents[2]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MAX_ACTIONS = 90
WALL_SECONDS = 720
RUNTIME_FILES = (
    "enterprise_fallback/odoo18/teacher_episode_worker_v066.py",
    "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "enterprise_fallback/odoo18/compose.yaml",
    "enterprise_fallback/odoo18/factory.py",
    "enterprise_fallback/odoo18/partition_factory.py",
    "enterprise_fallback/odoo18/gui_controls.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/worker_lease.py",
)


class OdooEpisodeError(RuntimeError):
    """Fixed local failure labels; private source and provider text stay out."""


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def source_hashes() -> dict[str, str]:
    return {relative: _hash((ROOT / relative).read_bytes())
            for relative in RUNTIME_FILES}


def runtime_sha256() -> str:
    return _hash(_canonical(source_hashes()))


def verifier_sha256() -> str:
    return _hash((ROOT / "enterprise_fallback/odoo18/verify.py").read_bytes())


def adapter_sha256() -> str:
    return _hash((ROOT / "enterprise_fallback/odoo18/odoo_v066_train_adapter.py").read_bytes())


def _mode_private(path: Path, *, directory: bool) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _write_new(path: Path, raw: bytes) -> dict[str, str]:
    if (path.exists() or path.is_symlink() or len(raw) > 8_000_000 or
            not _mode_private(path.parent, directory=True)):
        raise OdooEpisodeError("private_episode_path_unsafe")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path.name), "sha256": _hash(raw)}


def _artifact(out_dir: Path, name: str, value: object) -> dict[str, str]:
    path = out_dir / "artifacts" / name
    ref = _write_new(path, _canonical(value))
    return {"path": "artifacts/" + ref["path"], "sha256": ref["sha256"]}


def _validate_task(task: object) -> dict:
    if (type(task) is not dict or
            set(task) != {"task_id", "package_sha256", "visible_instruction"} or
            type(task["task_id"]) is not str or
            not TASK_ID.fullmatch(task["task_id"]) or
            type(task["package_sha256"]) is not str or
            not HEX64.fullmatch(task["package_sha256"]) or
            type(task["visible_instruction"]) is not str or
            not 1 <= len(task["visible_instruction"].encode()) <= 16_384):
        raise OdooEpisodeError("train_task_binding_invalid")
    return dict(task)


@dataclass
class EpisodeSession:
    """Minimal private boundary used by both the real and fake backends."""

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


class _RealOdooSession(EpisodeSession):
    def __init__(self, *, page, adapter: OdooV066TrainAdapter,
                 case_id: str, baseline_semantic: dict,
                 score: Callable, snapshot: Callable,
                 frozen_filestore_manifest_sha256: str):
        super().__init__(baseline_semantic=baseline_semantic,
                         pre_restore_exact=True)
        self.page = page
        self.adapter = adapter
        self.case_id = case_id
        self._score = score
        self._snapshot = snapshot
        self._filestore_sha = frozen_filestore_manifest_sha256

    def observe(self, *, memory: str) -> Observation:
        observation, _ = self.adapter.observe_for_model(memory=memory)
        return observation

    def current_frame_id(self) -> str:
        observation = self.adapter.latest
        if (observation is not None and self.page.url == self.adapter.latest_url
                and _hash(self.page.screenshot(type="png")) ==
                observation.screenshot["sha256"] and
                time.monotonic() <= observation.expires_at):
            return observation.frame_id
        return "stale"

    def dispatch(self, action: dict) -> None:
        observation = self.adapter.latest
        if observation is None or self.current_frame_id() != observation.frame_id:
            raise OdooEpisodeError("odoo_current_frame_changed_before_dispatch")
        checked = validate_action(action, observation,
                                  current_frame_id=observation.frame_id)
        applied = self.adapter.dispatch(checked)
        if applied["action"] != checked:
            raise OdooEpisodeError("odoo_dispatch_action_changed")

    def read_saved_state(self) -> dict:
        if not self.adapter.finished:
            raise OdooEpisodeError("teacher_finish_action_missing")
        # Read-only browser reload proves that any editor/autosave survived a
        # new page load. SQL scoring remains a separate SELECT-only evaluator.
        self.page.reload(wait_until="domcontentloaded")
        self.page.locator("body").wait_for()
        reloaded_frame_sha = _hash(self.page.screenshot(type="png"))
        score = self._score(self.case_id)
        semantic = self._snapshot()
        return {
            "business_snapshot": semantic,
            "independent_score": score,
            "gui_reload_frame_sha256": reloaded_frame_sha,
            "frozen_filestore_manifest_sha256": self._filestore_sha,
        }


class RealOdooTrainBackend:
    """Own one isolated, pinned Odoo train worker and its complete restore."""

    ROUTES = {
        "purchase": "/odoo/purchase",
        "inventory": "/odoo/inventory",
        "sales": "/odoo/sales",
        "crm": "/odoo/crm",
    }

    def __init__(self, worker_dir: Path):
        self.worker_dir = Path(worker_dir).resolve()

    def _load_train_case(self, task: dict, private: Path) -> tuple[str, dict]:
        if (not _mode_private(private, directory=True) or
                any(not _mode_private(private / name, directory=False)
                    for name in ("partition_cases.json",
                                 "task_set_manifest.json"))):
            raise OdooEpisodeError("odoo_private_train_manifest_unsafe")
        world = json.loads((private / "partition_cases.json").read_bytes())
        task_sets = json.loads((private / "task_set_manifest.json").read_bytes())
        train = task_sets["train"]
        other_ids = {row["task_id"] for split, rows in task_sets.items()
                     if split != "train" for row in rows}
        if (len(train) != 20 or len({row["task_id"] for row in train}) != 20
                or other_ids & {row["task_id"] for row in train}):
            raise OdooEpisodeError("odoo_train_split_manifest_invalid")
        matches = [row for row in train if row["task_id"] == task["task_id"]]
        cases = [(family, case) for family, rows in world["cases"].items()
                 if family in self.ROUTES for case in rows
                 if case["id"] == task["task_id"]]
        if (len(matches) != 1 or len(cases) != 1 or
                matches[0]["package_sha256"] != task["package_sha256"] or
                cases[0][1]["prompt"] != task["visible_instruction"]):
            raise OdooEpisodeError("odoo_train_task_not_in_private_partition")
        return cases[0]

    def _compose(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["docker", "compose", "--env-file", ".env", *args],
                              cwd=self.worker_dir, capture_output=True,
                              text=True, check=True)

    def _running(self) -> set[str]:
        return set(self._compose("ps", "--status", "running",
                                 "--services").stdout.splitlines())

    @contextmanager
    def open(self, task: dict) -> Iterator[_RealOdooSession]:
        # The Odoo modules read ENVLOOP_ODOO_WORKER_DIR on first import. A
        # process with a different previously imported factory fails closed.
        # Existing Odoo modules import one another as top-level modules.
        # Import them through that same identity: a package-qualified second
        # worker_lease module would hold a different in-process lease registry
        # and native browser_login would reject a legitimately held lease.
        import factory
        import gui_controls
        import reset
        import verify
        import worker_lease
        private_expected = self.worker_dir / "private"
        if (self.worker_dir.name != "train" or
                factory.HERE != self.worker_dir or
                factory.PRIVATE != private_expected or
                reset.HERE != self.worker_dir or
                verify.PRIVATE != private_expected or
                gui_controls.PRIVATE != private_expected or
                worker_lease.PRIVATE != private_expected or
                not _mode_private(self.worker_dir / ".env", directory=False) or
                factory.local_config().get("ODOO_PARTITION") != "train" or
                _hash((self.worker_dir / "compose.yaml").read_bytes()) !=
                source_hashes()["enterprise_fallback/odoo18/compose.yaml"]):
            raise OdooEpisodeError("odoo_original_train_worker_not_bound")
        private = factory.PRIVATE
        family, case = self._load_train_case(task, private)
        if not _mode_private(private / "actor_credentials.json",
                             directory=False):
            raise OdooEpisodeError("odoo_private_actor_credentials_unsafe")
        credentials = json.loads((private / "actor_credentials.json").read_bytes())
        with worker_lease.exclusive_worker_operation("teacher_odoo_v066_train"):
            running_before = self._running()
            browser = None
            session = None
            started = False
            failure = None
            try:
                if not {"db", "web"} <= running_before:
                    self._compose("up", "-d", "db", "web")
                started = True
                before = reset.restore()
                if (before["business_snapshot_equal"] is not True or
                        before["physical_filestore_equal_before_web_restart"]
                        is not True):
                    raise OdooEpisodeError("odoo_pre_episode_full_restore_failed")
                baseline = verify.snapshot()
                if verify.score(case["id"])["reward"] != 0.0:
                    raise OdooEpisodeError("odoo_train_baseline_already_solved")
                checkpoint = json.loads((private / "checkpoint_receipt.json").read_bytes())
                frozen_fs = _hash((private / "baseline-filestore-manifest.json").read_bytes())
                baseline_semantic = {
                    "business_snapshot": baseline,
                    "frozen_filestore_manifest_sha256": frozen_fs,
                    "checkpoint_db_sha256": checkpoint["db_sha256"],
                    "checkpoint_filestore_sha256": checkpoint["filestore_sha256"],
                }
                from playwright.sync_api import sync_playwright
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    page = browser.new_page(viewport=VIEWPORT)
                    gui_controls.browser_login(
                        page, int(factory.local_config()["ODOO_PORT"]),
                        credentials["password"], credentials["login"])
                    page.goto("http://127.0.0.1:" +
                              factory.local_config()["ODOO_PORT"] +
                              self.ROUTES[family])
                    page.locator("body").wait_for()
                    adapter = OdooV066TrainAdapter(
                        page, task_id=task["task_id"],
                        task_binding_sha256=task["package_sha256"],
                        instruction=task["visible_instruction"])
                    session = _RealOdooSession(
                        page=page, adapter=adapter, case_id=case["id"],
                        baseline_semantic=baseline_semantic,
                        score=verify.score, snapshot=verify.snapshot,
                        frozen_filestore_manifest_sha256=frozen_fs)
                    yield session
                    browser.close()
                    browser = None
            except BaseException as exc:
                failure = exc
                raise
            finally:
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        failure = OdooEpisodeError("odoo_browser_close_failed")
                reset_error = None
                if started:
                    try:
                        after = reset.restore()
                        if (after["business_snapshot_equal"] is not True or
                                after["physical_filestore_equal_before_web_restart"]
                                is not True):
                            raise OdooEpisodeError("odoo_post_episode_full_restore_failed")
                        if session is not None:
                            restored = verify.snapshot()
                            session.reset_semantic = {
                                **session.baseline_semantic,
                                "business_snapshot": restored,
                            }
                            session.post_restore_exact = (
                                session.reset_semantic ==
                                session.baseline_semantic)
                    except Exception:
                        reset_error = OdooEpisodeError("odoo_post_episode_full_restore_failed")
                try:
                    if "web" not in running_before:
                        self._compose("stop", "web")
                    if "db" not in running_before:
                        self._compose("stop", "db")
                    services_restored = self._running() == running_before
                except Exception:
                    services_restored = False
                if session is not None:
                    session.environment_terminated = bool(
                        services_restored and reset_error is None and
                        session.post_restore_exact)
                if reset_error is not None or not services_restored:
                    raise OdooEpisodeError("odoo_episode_reset_or_worker_stop_failed") from failure


class OdooTrainEpisodeWorker:
    """Concrete original-Odoo cell worker for collect_train_batch."""

    cell_id = "odoo-community"
    action_profile = ACTION_PROFILE_VERSION
    original_software_gui = True
    original_surface = "web"
    requires_e2b = False

    def __init__(self, *, worker_dir: Path, private_output_root: Path,
                 ratification_path: Path | None = None,
                 ratification_sha256: str | None = None,
                 expected_runtime_sha256: str | None = None,
                 expected_verifier_sha256: str | None = None,
                 enable_live: bool = False):
        self.worker_dir = Path(worker_dir).resolve()
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
        self.backend = RealOdooTrainBackend(self.worker_dir)

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
            raise OdooEpisodeError("odoo_live_episode_requires_frozen_bindings")
        from native_desktop_factory.v066_final_freeze import validate_ratification
        try:
            ratification, digest = validate_ratification(
                self.ratification_path)
        except (OSError, ValueError, TypeError, KeyError):
            raise OdooEpisodeError("odoo_six_cell_ratification_invalid") from None
        profile = ratification.get("cell_profiles", {}).get(self.cell_id, {})
        if (digest != self.ratification_sha256 or
                profile.get("adapter_sha256") != self.adapter_sha256):
            raise OdooEpisodeError("odoo_six_cell_adapter_binding_changed")

    def _check_output(self, out_dir: Path) -> None:
        if (not _mode_private(self.private_output_root, directory=True) or
                not _mode_private(out_dir, directory=True) or
                not out_dir.resolve().is_relative_to(
                    self.private_output_root) or
                not _mode_private(out_dir / "frames", directory=True) or
                any(out_dir.iterdir()) and
                set(child.name for child in out_dir.iterdir()) != {"frames"}):
            raise OdooEpisodeError("odoo_episode_private_output_unsafe")

    def run_episode(self, *, task, out_dir, sample_teacher,
                    dispatch_e2b) -> dict:
        task = _validate_task(task)
        if not callable(sample_teacher) or not callable(dispatch_e2b):
            raise OdooEpisodeError("odoo_teacher_callbacks_missing")
        self._require_ratification()
        out_dir = Path(out_dir).absolute()
        self._check_output(out_dir)
        artifacts = out_dir / "artifacts"
        artifacts.mkdir(mode=0o700)
        frame_refs: list[dict] = []
        trace_rows: list[dict] = []
        teacher_shas: list[str] = []
        memory = ""
        session = None
        saved = None
        try:
            with self.backend.open(task) as active:
                session = active
                if (active.pre_restore_exact is not True or
                        type(active.baseline_semantic) is not dict):
                    raise OdooEpisodeError("odoo_baseline_not_exact_before_teacher_call")
                for step in range(MAX_ACTIONS):
                    observation = active.observe(memory=memory)
                    if (type(observation) is not Observation or
                            observation.step != step or
                            observation.task_id != task["task_id"] or
                            observation.task_binding_sha256 !=
                            task["package_sha256"] or
                            observation.instruction != task["visible_instruction"]):
                        raise OdooEpisodeError("odoo_observation_not_bound_to_train_task")
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
                        raise OdooEpisodeError("odoo_teacher_callback_result_invalid")
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
                        raise OdooEpisodeError("odoo_teacher_action_or_frame_changed")
                    active.dispatch(action)
                    trace_rows.append(sampled["trace_row"])
                    teacher_shas.append(sampled["teacher_result_sha256"])
                    memory = action["memory"]
                    if action["type"] == "finish":
                        saved = active.read_saved_state()
                        break
                else:
                    raise OdooEpisodeError("odoo_teacher_action_budget_exhausted")
            if (session is None or not session.pre_restore_exact or
                    not session.post_restore_exact or
                    not session.environment_terminated or
                    session.reset_semantic != session.baseline_semantic or
                    type(saved) is not dict or
                    type(saved.get("independent_score")) is not dict or
                    saved["independent_score"].get("reward") != 1.0 or
                    saved["independent_score"].get("checks_passed") is not True or
                    saved["independent_score"].get("difference_codes") != [] or
                    not HEX64.fullmatch(
                        saved.get("gui_reload_frame_sha256", ""))):
                raise OdooEpisodeError("odoo_saved_state_or_fresh_reset_not_verified")
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
            reset = {
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
                                    teacher._canonical(trace_rows))
            state_ref = _write_new(out_dir / "saved-state.private.json",
                                   teacher._canonical(state))
            reset_ref = _write_new(out_dir / "reset.private.json",
                                   teacher._canonical(reset))
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
                                     teacher._canonical(episode))
            return {"episode_receipt_path": str(out_dir / receipt_ref["path"]),
                    "episode_receipt_sha256": receipt_ref["sha256"]}
        except BaseException as exc:
            # Retain the first failure and all pre-dispatch frames. The
            # backend context has already attempted its exact cold restore.
            failure = out_dir / "failure.private.json"
            if not failure.exists():
                _write_new(failure, _canonical({
                    "schema": "envloop-odoo-v066-teacher-failure-v1",
                    "failure_type": type(exc).__name__,
                    "reason": str(exc) if isinstance(exc, OdooEpisodeError)
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


__all__ = ["OdooTrainEpisodeWorker", "RealOdooTrainBackend",
           "runtime_sha256", "verifier_sha256", "adapter_sha256"]
