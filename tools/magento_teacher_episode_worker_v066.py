"""Fail-closed original-Magento v0.6.6 train teacher episode boundary.

The actor loop, current-frame Magento GUI adapter, private trace, independent
saved-state verifier and fresh-clone receipt are concrete. The dedicated
cron-free *training* clone lifecycle is not qualified while the frozen v2
100-case evaluator owns the existing Docker lane. The production backend
therefore refuses before a Docker/model call. A later, separately audited
dedicated lane may implement this module's backend contract; fake tests exercise
the complete teacher interface without touching the live evaluator.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Callable

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import (
    ContractLimits, Observation, make_observation,
)
from cursibench.scale_action_contract_v066 import (
    ACTION_PROFILE_VERSION, validate_action,
)
from magento_catalog_factory import seed, verify
from tools import magento_v066_train_adapter as gui
from tools import magento_dedicated_train_lane_v066 as dedicated


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-magento-v066-train-teacher-worker-v1"
MAX_ACTIONS = 90
WALL_SECONDS = 720
LOCAL_LEASE_SECONDS = 3600
# A dedicated launcher/resetter exists, but a distinct independent train-only
# positive/negative/fresh-reset smoke must be frozen before this gate opens.
# No such receipt is shipped and live execution remains disabled by default.
DEDICATED_BACKEND_IMPLEMENTED = True
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
RUNTIME_FILES = (
    "tools/magento_teacher_episode_worker_v066.py",
    "tools/magento_dedicated_train_lane_v066.py",
    "tools/magento_v066_train_adapter.py",
    "tools/run_magento_model_pilot_v063.py",
    "tools/run_magento_model_pilot_v06.py",
    "tools/start_magento_native_sidecar_clone_v1.py",
    "tools/sweep_magento_original_gui_controls_v1.py",
    "tools/magento_cron_runtime_contract_v1.py",
    "tools/qualify_magento_original_catalog_v1.py",
    "tools/reconcile_magento_unseeded_search_drift_v1.py",
    "magento_catalog_factory/plan.py",
    "magento_catalog_factory/seed.py",
    "magento_catalog_factory/verify.py",
)


class MagentoTeacherWorkerError(RuntimeError):
    """Fixed local subtype; never expose private task/provider text."""


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _private(path: Path, *, directory: bool = False) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _write_new(path: Path, raw: bytes) -> dict[str, str]:
    if (path.exists() or path.is_symlink() or len(raw) > 8_000_000 or
            not _private(path.parent, directory=True)):
        raise MagentoTeacherWorkerError("magento_private_output_unsafe")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": path.name, "sha256": _hash(raw)}


def _write_json(path: Path, value: object) -> dict[str, str]:
    return _write_new(path, _canonical(value))


def source_hashes() -> dict[str, str]:
    return {relative: _hash((ROOT / relative).read_bytes())
            for relative in RUNTIME_FILES}


def runtime_sha256() -> str:
    return _hash(_canonical(source_hashes()))


def adapter_sha256() -> str:
    return _hash(Path(gui.__file__).read_bytes())


def verifier_sha256() -> str:
    return _hash(Path(verify.__file__).read_bytes())


def _money(value: object) -> Decimal:
    if type(value) is not str:
        raise MagentoTeacherWorkerError("magento_local_cost_invalid")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise MagentoTeacherWorkerError("magento_local_cost_invalid") from None
    if (not result.is_finite() or result <= 0 or
            -result.as_tuple().exponent > 9):
        raise MagentoTeacherWorkerError("magento_local_cost_invalid")
    return result


class UnqualifiedMagentoTrainRuntime:
    """The live evaluator lane is intentionally never an implicit fallback."""

    qualified = False

    def reserve_capacity(self, _request: dict) -> dict:
        raise MagentoTeacherWorkerError(
            "dedicated_magento_train_lane_not_qualified")

    @asynccontextmanager
    async def open_case(self, _case: dict, _out_dir: Path):
        raise MagentoTeacherWorkerError(
            "dedicated_magento_train_lane_not_qualified")
        yield  # pragma: no cover


async def _capture(page, task: dict, *, step: int, memory: str,
                   previous: dict | None) -> tuple[Observation, dict, str]:
    host = gui.prior.host
    image = await page.screenshot(type="png", full_page=False,
                                  animations="disabled",
                                  mask=[page.locator(".admin-user")])
    controls, handles = await host._visible_controls(page)
    headings = []
    for item in await page.locator("h1, h2").element_handles():
        try:
            if await item.is_visible():
                headings.append(host._short_text(await item.inner_text(), 200))
        except Exception:
            continue
    observation = make_observation(
        task_id=task["task_id"],
        task_binding_sha256=task["package_sha256"],
        instruction=task["visible_instruction"],
        step=step, screenshot_bytes=image,
        a11y_text="Visible headings: " + "; ".join(headings[:12]),
        dom_text="", controls=controls,
        previous_action_result=previous, memory=memory,
        limits=ContractLimits(max_step=MAX_ACTIONS))
    return observation, handles, page.url


async def _same_frame(page, observation: Observation, frame_url: str) -> bool:
    try:
        await gui._current(page, observation, frame_url)
        return True
    except Exception:
        return False


class MagentoTeacherEpisodeWorker:
    """Cell-owned train worker accepted by collect_train_batch after freeze."""

    cell_id = "magento-admin"
    action_profile = ACTION_PROFILE_VERSION
    original_software_gui = True
    original_surface = "web"
    requires_e2b = False

    def __init__(self, *, plan_path: Path, plan_sha256: str,
                 private_output_root: Path,
                 ratification_path: Path | None = None,
                 ratification_sha256: str | None = None,
                 expected_runtime_sha256: str | None = None,
                 expected_verifier_sha256: str | None = None,
                 dedicated_lane_receipt: Path | None = None,
                 dedicated_lane_sha256: str | None = None,
                 local_cost_authority: Path | None = None,
                 local_cost_authority_sha256: str | None = None,
                 dispatch_local_service: Callable | None = None,
                 enable_live: bool = False):
        original_plan = Path(plan_path)
        self.plan_path_was_symlink = original_plan.is_symlink()
        self.plan_path = original_plan.resolve()
        self.plan_sha256 = plan_sha256
        self.private_output_root = Path(private_output_root).resolve()
        self.ratification_path = (Path(ratification_path) if
                                  ratification_path is not None else None)
        self.ratification_sha256 = ratification_sha256
        self.expected_runtime_sha256 = expected_runtime_sha256
        self.expected_verifier_sha256 = expected_verifier_sha256
        self.dedicated_lane_receipt = (Path(dedicated_lane_receipt) if
                                       dedicated_lane_receipt is not None else
                                       None)
        self.dedicated_lane_sha256 = dedicated_lane_sha256
        self.local_cost_authority = (Path(local_cost_authority) if
                                     local_cost_authority is not None else None)
        self.local_cost_authority_sha256 = local_cost_authority_sha256
        self.dispatch_local_service = dispatch_local_service
        self.enable_live = enable_live
        self.runtime_sha256 = runtime_sha256()
        self.adapter_sha256 = adapter_sha256()
        self.verifier_sha256 = verifier_sha256()
        self.backend = UnqualifiedMagentoTrainRuntime()

    def _require_live(self) -> dict:
        if (DEDICATED_BACKEND_IMPLEMENTED is not True or
                self.enable_live is not True or
                self.runtime_sha256 != runtime_sha256() or
                self.adapter_sha256 != adapter_sha256() or
                self.verifier_sha256 != verifier_sha256() or
                self.expected_runtime_sha256 != self.runtime_sha256 or
                self.expected_verifier_sha256 != self.verifier_sha256 or
                self.ratification_path is None or
                not _private(self.ratification_path) or
                type(self.ratification_sha256) is not str or
                not HEX64.fullmatch(self.ratification_sha256) or
                self.dedicated_lane_receipt is None or
                not _private(self.dedicated_lane_receipt) or
                self.local_cost_authority is None or
                not _private(self.local_cost_authority) or
                not callable(self.dispatch_local_service) or
                not self.dedicated_lane_receipt.resolve().is_relative_to(
                    (ROOT / "work").resolve()) or
                not self.local_cost_authority.resolve().is_relative_to(
                    (ROOT / "work").resolve())):
            raise MagentoTeacherWorkerError(
                "magento_live_teacher_requires_dedicated_frozen_lane")
        from native_desktop_factory.v066_final_freeze import validate_ratification
        try:
            ratification, digest = validate_ratification(
                self.ratification_path)
        except (OSError, ValueError, TypeError, KeyError):
            raise MagentoTeacherWorkerError(
                "magento_six_cell_ratification_invalid") from None
        if (digest != self.ratification_sha256 or
                ratification["cell_profiles"][self.cell_id]
                ["adapter_sha256"] != self.adapter_sha256):
            raise MagentoTeacherWorkerError(
                "magento_v066_adapter_binding_changed")
        lane_raw = self.dedicated_lane_receipt.read_bytes()
        if (self.dedicated_lane_sha256 != _hash(lane_raw) or
                self.dedicated_lane_receipt.resolve() ==
                (ROOT / "work/magento-original/exclusive-worker.lock").resolve()):
            raise MagentoTeacherWorkerError(
                "dedicated_train_lane_receipt_changed")
        lane = json.loads(lane_raw)
        smoke = lane.get("independent_train_smoke")
        if (lane.get("schema") !=
                "envloop-magento-v066-dedicated-train-lane-v1" or
                lane.get("status") !=
                "qualified_after_independent_train_smoke" or
                lane.get("runtime_sha256") != self.runtime_sha256 or
                lane.get("launcher_source_sha256") != _hash(Path(
                    dedicated.__file__).read_bytes()) or
                lane.get("app_name") != dedicated.PAIRS[0][0] or
                lane.get("search_name") != dedicated.PAIRS[0][1] or
                lane.get("app_reset_name") != dedicated.PAIRS[1][0] or
                lane.get("search_reset_name") != dedicated.PAIRS[1][1] or
                lane.get("network") != dedicated.NETWORK or
                lane.get("loopback_ports") != [7820, 7821, 7822, 7823] or
                lane.get("source_search_sha256") !=
                dedicated.evaluator.SEARCH_SHA or
                lane.get("source_commit") !=
                dedicated.evaluator.IMAGE_SOURCE_COMMIT or
                lane.get("app_image_sha256") != seed.IMAGE or
                lane.get("search_image_sha256") !=
                verify.NATIVE_SEARCH_IMAGE or
                lane.get("cron_autostart_disabled") is not True or
                lane.get("no_host_mounts") is not True or
                lane.get("actor_role_bound") is not True or
                lane.get("browser_network_guard_installed") is not True or
                type(smoke) is not dict or
                smoke.get("known_positive_score") != 1 or
                smoke.get("wrong_variant_score") != 0 or
                smoke.get("fresh_clone_reset_passed") is not True or
                smoke.get("original_magento_gui") is not True or
                type(smoke.get("private_receipt_ref")) is not dict or
                type(smoke["private_receipt_ref"].get("path")) is not str or
                type(smoke["private_receipt_ref"].get("sha256")) is not str or
                HEX64.fullmatch(smoke["private_receipt_ref"]["sha256"])
                is None or
                type(lane.get("actor_credentials_ref")) is not dict or
                type(lane["actor_credentials_ref"].get("path")) is not str or
                type(lane["actor_credentials_ref"].get("sha256")) is not str or
                HEX64.fullmatch(lane["actor_credentials_ref"]["sha256"])
                is None):
            raise MagentoTeacherWorkerError(
                "dedicated_train_clone_runtime_not_qualified")
        smoke_path = Path(smoke["private_receipt_ref"]["path"])
        if (not _private(smoke_path) or
                not smoke_path.resolve().is_relative_to(
                    (ROOT / "work").resolve()) or
                _hash(smoke_path.read_bytes()) !=
                smoke["private_receipt_ref"]["sha256"]):
            raise MagentoTeacherWorkerError(
                "independent_train_smoke_receipt_missing_or_changed")
        try:
            control = json.loads(smoke_path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MagentoTeacherWorkerError(
                "independent_train_smoke_receipt_invalid") from None
        if (control.get("schema") !=
                "envloop-magento-v066-dedicated-train-control-v1" or
                control.get("status") != "complete_before_teacher" or
                control.get("evaluator_only") is not True or
                control.get("model_calls") != 0 or
                control.get("known_positive_score") != 1 or
                control.get("wrong_variant_score") != 0 or
                control.get("fresh_clone_reset_passed") is not True or
                control.get("different_app_container_ids") is not True or
                control.get("different_search_container_ids") is not True or
                control.get("both_pairs_removed") is not True or
                control.get("actor_acl_verified") is not True or
                control.get("browser_guard_verified") is not True or
                control.get("cron_never_autostarted") is not True or
                control.get("no_evaluator_container_overlap") is not True or
                control.get("launcher_source_sha256") != _hash(Path(
                    dedicated.__file__).read_bytes()) or
                control.get("verifier_source_sha256") !=
                self.verifier_sha256):
            raise MagentoTeacherWorkerError(
                "independent_train_smoke_does_not_qualify_lane")
        actor_path = Path(lane["actor_credentials_ref"]["path"])
        if (not _private(actor_path) or
                not actor_path.resolve().is_relative_to(
                    (ROOT / "work").resolve()) or
                _hash(actor_path.read_bytes()) !=
                lane["actor_credentials_ref"]["sha256"]):
            raise MagentoTeacherWorkerError(
                "dedicated_actor_credentials_not_source_bound")
        cost_raw = self.local_cost_authority.read_bytes()
        if (self.local_cost_authority_sha256 != _hash(cost_raw)):
            raise MagentoTeacherWorkerError(
                "magento_local_cost_authority_changed")
        cost = json.loads(cost_raw)
        if (cost.get("schema") !=
                "cua-full-study-local-opportunity-cost-authority-v1" or
                cost.get("cell_id") != self.cell_id or
                cost.get("basis") != "nominal_local_opportunity_cost_upper" or
                cost.get("provider_invoice_usd") is not None or
                cost.get("lease_seconds") != LOCAL_LEASE_SECONDS):
            raise MagentoTeacherWorkerError(
                "magento_local_cost_authority_invalid")
        _money(cost.get("hourly_usd_upper"))
        # Overwrite any caller-injected backend with this source-bound real
        # launcher only after the independent smoke and cost gates pass.
        self.backend = dedicated.DedicatedMagentoTrainRuntime(
            lane, self.dedicated_lane_receipt)
        return cost

    def _train_case(self, task: object) -> dict:
        if (type(task) is not dict or set(task) != {
                "task_id", "package_sha256", "visible_instruction"} or
                type(task["task_id"]) is not str or
                TASK_ID.fullmatch(task["task_id"]) is None or
                type(task["package_sha256"]) is not str or
                HEX64.fullmatch(task["package_sha256"]) is None or
                type(task["visible_instruction"]) is not str):
            raise MagentoTeacherWorkerError(
                "magento_train_task_shape_invalid")
        if (self.plan_path_was_symlink or
                not _private(self.plan_path) or
                not self.plan_path.is_relative_to((ROOT / "work").resolve()) or
                type(self.plan_sha256) is not str or
                not HEX64.fullmatch(self.plan_sha256)):
            raise MagentoTeacherWorkerError(
                "magento_private_plan_unbound")
        plan = json.loads(self.plan_path.read_bytes())
        train = plan.get("cases", {}).get("train")
        if (plan.get("schema") != "envloop-magento-catalog-candidates-v1" or
                type(train) is not list or len(train) != 20 or
                len({row["task_id"] for row in train}) != 20 or
                task["task_id"] not in {row["task_id"] for row in train}):
            raise MagentoTeacherWorkerError(
                "magento_train_partition_not_exact_twenty")
        try:
            case = seed.load_case(self.plan_path, self.plan_sha256,
                                  task["task_id"])
        except (ValueError, KeyError, TypeError, OSError):
            raise MagentoTeacherWorkerError(
                "magento_train_case_package_changed") from None
        if (case["split"] != "train" or
                len(case["target_variants"]) != 1 or
                case["package_sha256"] != task["package_sha256"] or
                case["instruction"] != task["visible_instruction"] or
                any(case["task_id"] == row["task_id"] for split, rows in
                    plan["cases"].items() if split != "train" for row in rows)):
            raise MagentoTeacherWorkerError(
                "magento_train_case_cross_split_or_instruction_changed")
        return case

    def _check_output(self, out_dir: Path) -> None:
        if (not _private(self.private_output_root, directory=True) or
                not _private(out_dir, directory=True) or
                not out_dir.resolve().is_relative_to(self.private_output_root)
                or {child.name for child in out_dir.iterdir()} != {"frames"}
                or not _private(out_dir / "frames", directory=True)):
            raise MagentoTeacherWorkerError(
                "magento_episode_private_output_unsafe")

    def _reserve_local_service(self, task: dict, out_dir: Path,
                               cost: dict) -> dict:
        attempt_id = ("magento-teacher-local-" +
                      _hash((str(out_dir) + task["task_id"]).encode())[:20])
        amount = (Decimal(LOCAL_LEASE_SECONDS) / Decimal(3600) *
                  _money(cost["hourly_usd_upper"]))
        reserve = str(amount.quantize(Decimal("0.000000001"),
                                      rounding=ROUND_CEILING))
        request = {
            "schema": "cua-magento-v066-teacher-local-lease-v1",
            "cell_id": self.cell_id,
            "train_task_id": task["task_id"],
            "package_sha256": task["package_sha256"],
            "worker_runtime_sha256": self.runtime_sha256,
            "dedicated_lane_sha256": self.dedicated_lane_sha256,
            "lease_seconds": LOCAL_LEASE_SECONDS,
            "provider_invoice_usd": None,
        }
        paid = self.dispatch_local_service(
            attempt_id=attempt_id, category="storage_application",
            work={"task_id": task["task_id"],
                  "package_sha256": task["package_sha256"],
                  "runtime_sha256": self.runtime_sha256},
            request=request, reserve_usd=reserve,
            resource_reservation={},
            provider=self.backend.reserve_capacity)
        if (type(paid) is not dict or paid.get("attempt_id") != attempt_id or
                type(paid.get("result")) is not dict or
                type(paid.get("result_sha256")) is not str or
                HEX64.fullmatch(paid["result_sha256"]) is None or
                paid.get("billing_state") !=
                "awaiting_provider_usage_reconciliation" or
                paid["result"].get("status") !=
                "reserved_before_original_gui_start"):
            raise MagentoTeacherWorkerError(
                "magento_local_service_reservation_ambiguous")
        return {"paid_attempt_id": attempt_id,
                "paid_result_sha256": paid.get("result_sha256"),
                "planning_upper_usd": reserve,
                "provider_invoice_usd": None}

    async def _drive(self, session, task: dict, out_dir: Path,
                     sample_teacher: Callable) -> tuple[list[dict], list[dict]]:
        page = session.page
        loop = asyncio.get_running_loop()
        frames = []
        turns = []
        memory = ""
        previous = None
        started = time.monotonic()
        for step in range(MAX_ACTIONS):
            if time.monotonic() - started > WALL_SECONDS:
                raise MagentoTeacherWorkerError(
                    "magento_teacher_episode_wall_budget_exhausted")
            obs, handles, frame_url = await _capture(
                page, task, step=step, memory=memory, previous=previous)
            frame_path = out_dir / "frames" / f"step-{step:03d}.png"
            frame_ref = _write_new(frame_path, obs.screenshot_bytes)
            frames.append({"path": "frames/" + frame_ref["path"],
                           "sha256": frame_ref["sha256"]})

            def current_frame_id() -> str:
                future = asyncio.run_coroutine_threadsafe(
                    _same_frame(page, obs, frame_url), loop)
                try:
                    return (obs.frame_id if future.result(timeout=30)
                            else "stale")
                except Exception:
                    future.cancel()
                    return "stale"

            sampled = await asyncio.to_thread(
                sample_teacher, obs, current_frame_id)
            if (type(sampled) is not dict or
                    set(sampled) != {"action", "trace_row",
                                     "teacher_result_sha256"} or
                    type(sampled["action"]) is not dict or
                    type(sampled["trace_row"]) is not dict or
                    type(sampled["teacher_result_sha256"]) is not str or
                    HEX64.fullmatch(sampled["teacher_result_sha256"]) is None
                    or sampled["trace_row"].get("action") !=
                    sampled["action"] or
                    sampled["trace_row"].get("frame_sha256") !=
                    frame_ref["sha256"] or
                    sampled["trace_row"].get("frame_id") != obs.frame_id):
                raise MagentoTeacherWorkerError(
                    "magento_teacher_action_trace_unbound")
            action = sampled["action"]
            if (not await _same_frame(page, obs, frame_url) or
                    validate_action(action, obs,
                                    current_frame_id=obs.frame_id) != action):
                raise MagentoTeacherWorkerError(
                    "magento_teacher_frame_changed_after_paid_call")
            previous = await gui.dispatch_current_action(
                page, action, obs, handles, frame_url)
            if previous != {"status": "applied", "code": "ok"}:
                raise MagentoTeacherWorkerError(
                    "magento_gui_dispatch_not_applied")
            turns.append(sampled["trace_row"])
            memory = action["memory"]
            if action["type"] == "finish":
                return frames, turns
        raise MagentoTeacherWorkerError(
            "magento_teacher_episode_action_budget_exhausted")

    async def _run_async(self, case: dict, task: dict, out_dir: Path,
                         sample_teacher: Callable) -> tuple[dict, dict]:
        session = None
        score = None
        try:
            async with self.backend.open_case(case, out_dir) as active:
                session = active
                if (type(active.baseline_state) is not dict or
                        active.fresh_clone_prepared is not True or
                        active.native_quote_visible is not True):
                    raise MagentoTeacherWorkerError(
                        "magento_original_train_baseline_unverified")
                verify.check_baseline(case, active.baseline_state)
                frames, turns = await self._drive(
                    active, task, out_dir, sample_teacher)
                saved = await active.saved_state()
                if type(saved) is not dict or saved.get("snapshot") is None or\
                        saved.get("native_save_observed") is not True:
                    raise MagentoTeacherWorkerError(
                        "magento_native_saved_state_not_observed")
                score = verify.score_saved_state(
                    case, active.baseline_state, saved["snapshot"])
                if score["passed"] is not True or score["score"] != 1.0:
                    raise MagentoTeacherWorkerError(
                        "magento_independent_train_positive_not_saved")
            if (session is None or type(session.reset_proof) is not dict or
                    session.reset_proof.get("fresh_clone_reset_passed") is not True or
                    session.reset_proof.get("different_app_container_ids") is not True or
                    session.reset_proof.get("different_search_container_ids")
                    is not True or
                    session.reset_proof.get("no_host_mounts") is not True or
                    session.reset_proof.get("both_pairs_removed") is not True):
                raise MagentoTeacherWorkerError(
                    "magento_physical_fresh_clone_reset_unverified")
            restored = session.reset_proof.get("restored_snapshot")
            if type(restored) is not dict:
                raise MagentoTeacherWorkerError(
                    "magento_restored_snapshot_missing")
            allowed_clock = verify.check_material_reset(
                session.baseline_state, restored)
            return ({"frames": frames, "turns": turns,
                     "saved": saved, "score": score},
                    {"reset_proof": session.reset_proof,
                     "allowed_volatile_fields": allowed_clock,
                     "baseline_snapshot": session.baseline_state,
                     "restored_snapshot": restored})
        except Exception:
            raise

    def run_episode(self, *, task, out_dir, sample_teacher,
                    dispatch_e2b) -> dict:
        if not callable(sample_teacher) or not callable(dispatch_e2b):
            raise MagentoTeacherWorkerError(
                "magento_teacher_callbacks_missing")
        cost = self._require_live()
        case = self._train_case(task)
        out_dir = Path(out_dir).absolute()
        self._check_output(out_dir)
        local = None
        lease_started = time.monotonic()
        try:
            local = self._reserve_local_service(task, out_dir, cost)
            gui_result, reset_result = asyncio.run(
                self._run_async(case, task, out_dir, sample_teacher))
            elapsed = time.monotonic() - lease_started
            if elapsed > LOCAL_LEASE_SECONDS:
                raise MagentoTeacherWorkerError(
                    "magento_local_service_lease_exceeded")
            nominal = (Decimal(str(elapsed)) / Decimal(3600) *
                       _money(cost["hourly_usd_upper"]))
            local["metered_wall_seconds"] = elapsed
            local["metered_nominal_usd"] = str(nominal.quantize(
                Decimal("0.000000001"), rounding=ROUND_CEILING))
            local["basis"] = "nominal_local_opportunity_cost_not_invoice"
            artifact_dir = out_dir / "artifacts"
            artifact_dir.mkdir(mode=0o700)
            saved_ref = _write_json(
                artifact_dir / "saved-artifact.private.json",
                gui_result["saved"])
            baseline_semantic = {
                "material_baseline_sha256":
                    verify.canonical_sha(reset_result["baseline_snapshot"]),
                "allowed_volatile_fields": reset_result[
                    "allowed_volatile_fields"],
            }
            baseline_ref = _write_json(
                artifact_dir / "baseline.private.json",
                baseline_semantic)
            restored_ref = _write_json(
                artifact_dir / "restored.private.json",
                baseline_semantic)
            raw_baseline_ref = _write_json(
                artifact_dir / "baseline-raw.private.json",
                reset_result["baseline_snapshot"])
            raw_restored_ref = _write_json(
                artifact_dir / "restored-raw.private.json",
                reset_result["restored_snapshot"])
            local_ref = _write_json(
                artifact_dir / "local-service.private.json", local)
            common = {"cell_id": self.cell_id,
                      "task_id": task["task_id"],
                      "package_sha256": task["package_sha256"]}
            state = {"schema": teacher.STATE_SCHEMA, **common,
                     "independent_of_actor": True,
                     "native_save_observed": True,
                     "target_state_pass": True,
                     "no_regression_pass": True,
                     "saved_artifact_sha256": saved_ref["sha256"],
                     "saved_artifact_ref": {
                         "path": "artifacts/" + saved_ref["path"],
                         "sha256": saved_ref["sha256"]},
                     "verifier_sha256": self.verifier_sha256,
                     "evaluator_result": "pass",
                     "local_service_paid_attempt_id": local[
                         "paid_attempt_id"],
                     "local_service_receipt_ref": {
                         "path": "artifacts/" + local_ref["path"],
                         "sha256": local_ref["sha256"]},
                     "score_receipt": gui_result["score"]}
            reset = {"schema": teacher.RESET_SCHEMA, **common,
                     "independent_of_actor": True,
                     "fresh_environment": True,
                     "state_equivalence_pass": True,
                     "sandbox_terminated": True,
                     "baseline_semantic_sha256": baseline_ref["sha256"],
                     "restored_semantic_sha256": restored_ref["sha256"],
                     "baseline_state_ref": {
                         "path": "artifacts/" + baseline_ref["path"],
                         "sha256": baseline_ref["sha256"]},
                     "restored_state_ref": {
                         "path": "artifacts/" + restored_ref["path"],
                         "sha256": restored_ref["sha256"]},
                     "raw_baseline_state_ref": {
                         "path": "artifacts/" + raw_baseline_ref["path"],
                         "sha256": raw_baseline_ref["sha256"]},
                     "raw_restored_state_ref": {
                         "path": "artifacts/" + raw_restored_ref["path"],
                         "sha256": raw_restored_ref["sha256"]},
                     "physical_fresh_clone_proof": reset_result[
                         "reset_proof"]}
            action_ref = _write_json(out_dir / "actions.private.json",
                                     gui_result["turns"])
            state_ref = _write_json(out_dir / "saved-state.private.json",
                                    state)
            reset_ref = _write_json(out_dir / "reset.private.json",
                                    reset)
            episode = {"schema": teacher.EPISODE_SCHEMA,
                       "status": "admitted", "split": "train", **common,
                       "action_profile": self.action_profile,
                       "teacher_model": teacher.matrix.TEACHER,
                       "original_software_gui": True,
                       "original_surface": self.original_surface,
                       "runtime_sha256": self.runtime_sha256,
                       "adapter_sha256": self.adapter_sha256,
                       "frame_refs": gui_result["frames"],
                       "action_trace_ref": action_ref,
                       "saved_state_ref": state_ref,
                       "reset_ref": reset_ref,
                       "teacher_result_sha256s": [
                           row["teacher_result_sha256"] for row in
                           gui_result["turns"]],
                       "e2b_attempt_ids": []}
            receipt_ref = _write_json(out_dir / "episode.private.json",
                                      episode)
            return {"episode_receipt_path": str(out_dir /
                                                receipt_ref["path"]),
                    "episode_receipt_sha256": receipt_ref["sha256"]}
        except Exception as exc:
            failure = out_dir / "failure.private.json"
            if not failure.exists():
                _write_json(failure, {
                    "schema": "envloop-magento-v066-teacher-failure-v1",
                    "failure_type": type(exc).__name__,
                    "reason": (str(exc) if isinstance(
                        exc, MagentoTeacherWorkerError) else
                        "external_callback_or_runtime_failure"),
                    "local_service_paid_attempt_id": (
                        local["paid_attempt_id"] if local else None),
                    "automatic_replay_authorized": False})
            raise


__all__ = ["MagentoTeacherEpisodeWorker",
           "UnqualifiedMagentoTrainRuntime", "runtime_sha256",
           "adapter_sha256", "verifier_sha256"]
