"""Twenty-task original Odoo Community v0.6.6 Qwen selection worker.

The only task view accepted here is the exact return value from
``CampaignSession.start_selection_attempt``. It contains no train or final
instructions. The selected checkpoint path is private and its SHA-256 must
match that start receipt. A frozen campaign supplies ``dispatch_paid``: one
local-application reservation, one sampler-setup reservation, and a distinct
paid attempt per SDK sample are durable before their work. Local runtime and
rendered token counts are kept separate from provider invoices.

This worker is disabled for live execution until a six-cell ratification,
source bindings, and a private local cost authority are present. It has no
public CLI. Fake-provider tests never start Docker or a Tinker service.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, Iterator

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_selection_environment_v1 as environment_class
from cursibench import scale_action_output_v066 as output_v066
from cursibench.scale_action_contract import ContractError, Observation
from cursibench.scale_action_contract_v066 import ACTION_PROFILE_VERSION
from .odoo_v066_train_adapter import OdooV066TrainAdapter, VIEWPORT
from .teacher_episode_worker_v066 import (
    OdooEpisodeError, ROOT, _canonical, _hash, _mode_private, _write_new,
    adapter_sha256, verifier_sha256,
)


SCHEMA = "envloop-odoo-v066-selection-worker-v1"
RESULT_SCHEMA = "cua-full-study-selection-saved-result-v1"
LOCAL_LEASE_SCHEMA = "cua-full-study-original-software-local-lease-v1"
LOCAL_COST_SCHEMA = "cua-full-study-local-opportunity-cost-authority-v1"
USAGE_SCHEMA = "envloop-odoo-v066-selection-usage-v1"
TIMEOUT_SCHEMA = "envloop-odoo-v066-selection-timeouts-v1"
MAX_TASKS = 20
MAX_ACTIONS = 90
WALL_SECONDS_PER_TASK = 720
LOCAL_LEASE_SECONDS = 16_200
MAX_INPUT_TOKENS = 32_768
MAX_OUTPUT_TOKENS = 4096
SAMPLE_TIMEOUT_SECONDS = 120
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
SOURCE_FILES = (
    "enterprise_fallback/odoo18/selection_worker_v066.py",
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
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_vision_proxy.py",
    "src/cursibench/full_study_selection_environment_v1.py",
)


class SelectionWorkerError(OdooEpisodeError):
    """Safe fixed subtype, never a raw model/source/provider message."""


class SelectionProviderUncertain(SelectionWorkerError):
    pass


def source_hashes() -> dict[str, str]:
    return {relative: _hash((ROOT / relative).read_bytes())
            for relative in SOURCE_FILES}


def runtime_sha256() -> str:
    return _hash(_canonical(source_hashes()))


def _money(value: object, *, positive: bool = True) -> Decimal:
    if type(value) is not str:
        raise SelectionWorkerError("selection_decimal_string_required")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise SelectionWorkerError("selection_decimal_invalid") from None
    if (not amount.is_finite() or (positive and amount <= 0) or
            (not positive and amount < 0) or
            -amount.as_tuple().exponent > 9):
        raise SelectionWorkerError("selection_decimal_invalid")
    return amount


def _start_view(started: object, checkpoint_path: str) -> dict:
    if (type(started) is not dict or set(started) != {
            "attempt_id", "checkpoint_path_sha256", "selection_tasks",
            "selection_identities_sha256", "task_count"} or
            type(started["attempt_id"]) is not str or
            campaign.dollars.ATTEMPT.fullmatch(started["attempt_id"]) is None or
            len(started["attempt_id"]) > 100 or
            type(checkpoint_path) is not str or
            campaign.TINKER_PATH.fullmatch(checkpoint_path) is None or
            _hash(checkpoint_path.encode()) != started["checkpoint_path_sha256"] or
            type(started["selection_tasks"]) is not list or
            len(started["selection_tasks"]) != MAX_TASKS or
            type(started["task_count"]) is not int or
            started["task_count"] != MAX_TASKS or
            type(started["selection_identities_sha256"]) is not str or
            started["selection_identities_sha256"] !=
            _hash(_canonical(started["selection_tasks"]))):
        raise SelectionWorkerError("selection_start_or_checkpoint_unbound")
    seen = set()
    for task in started["selection_tasks"]:
        if (type(task) is not dict or set(task) != {"task_id", "package_sha256"}
                or type(task["task_id"]) is not str or
                TASK_ID.fullmatch(task["task_id"]) is None or
                task["task_id"] in seen or
                type(task["package_sha256"]) is not str or
                HEX64.fullmatch(task["package_sha256"]) is None):
            raise SelectionWorkerError("selection_task_identity_invalid")
        seen.add(task["task_id"])
    return dict(started)


def _student_sampling_config(raw: object, config_sha: str) -> dict:
    if (type(raw) is not bytes or not 0 < len(raw) <= 1_000_000 or
            type(config_sha) is not str or
            not HEX64.fullmatch(config_sha) or _hash(raw) != config_sha):
        raise SelectionWorkerError("selection_student_sampling_config_unbound")
    try:
        config = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SelectionWorkerError("selection_student_sampling_config_unbound") from None
    needed = {"model", "action_profile", "sample_max_tokens", "seed",
              "prefill_usd_per_million_tokens",
              "sample_usd_per_million_tokens", "billing_multiplier_upper"}
    if (type(config) is not dict or not needed <= set(config) or
            config["model"] != "Qwen/Qwen3.8-27B" or
            config["action_profile"] != ACTION_PROFILE_VERSION or
            type(config["sample_max_tokens"]) is not int or
            not 1 <= config["sample_max_tokens"] <= MAX_OUTPUT_TOKENS or
            type(config["seed"]) is not int or
            not 0 <= config["seed"] < 2**31):
        raise SelectionWorkerError("selection_student_sampling_config_unbound")
    for name in ("prefill_usd_per_million_tokens",
                 "sample_usd_per_million_tokens",
                 "billing_multiplier_upper"):
        _money(config[name])
    if _money(config["billing_multiplier_upper"]) < 1:
        raise SelectionWorkerError("selection_sampling_multiplier_below_one")
    return config


def tinker_upper_reserve_usd(config: dict) -> str:
    return str(_money(tinker_sample_reserve_usd(config)) *
               Decimal(MAX_TASKS * MAX_ACTIONS + 1))


def tinker_sample_reserve_usd(config: dict) -> str:
    tokens_usd = (
        Decimal(MAX_INPUT_TOKENS) *
        _money(config["prefill_usd_per_million_tokens"]) +
        Decimal(config["sample_max_tokens"]) *
        _money(config["sample_usd_per_million_tokens"])) / Decimal(1_000_000)
    return str((tokens_usd * _money(config["billing_multiplier_upper"]))
               .quantize(Decimal("0.000000001"), rounding=ROUND_CEILING))


def _cost_authority(path: Path, expected_sha: str) -> dict:
    if (not _mode_private(path, directory=False) or
            type(expected_sha) is not str or
            not HEX64.fullmatch(expected_sha) or
            _hash(path.read_bytes()) != expected_sha):
        raise SelectionWorkerError("local_cost_authority_missing_or_changed")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SelectionWorkerError("local_cost_authority_invalid") from None
    if (type(value) is not dict or set(value) != {
            "schema", "cell_id", "basis", "hourly_usd_upper",
            "provider_invoice_usd", "lease_seconds"} or
            value["schema"] != LOCAL_COST_SCHEMA or
            value["cell_id"] != "odoo-community" or
            value["basis"] != "nominal_local_opportunity_cost_upper" or
            value["provider_invoice_usd"] is not None or
            value["lease_seconds"] != LOCAL_LEASE_SECONDS):
        raise SelectionWorkerError("local_cost_authority_invalid")
    _money(value["hourly_usd_upper"])
    return value


def local_upper_reserve_usd(authority: dict) -> str:
    hours = Decimal(LOCAL_LEASE_SECONDS) / Decimal(3600)
    return str((hours * _money(authority["hourly_usd_upper"]))
               .quantize(Decimal("0.000000001"), rounding=ROUND_CEILING))


def _write_json(path: Path, value: object) -> str:
    return _write_new(path, _canonical(value))["sha256"]


def _audit_task_artifacts(directory: Path, task: dict, row: dict) -> None:
    files = {
        "saved_state_sha256": "saved-state.private.json",
        "verifier_receipt_sha256": "verifier.private.json",
        "reset_receipt_sha256": "reset.private.json",
        "actions_sha256": "actions.private.json",
        "usage_sha256": "usage.private.json",
        "frames_sha256": "frames.private.json",
    }
    loaded = {}
    for key, name in files.items():
        path = directory / name
        if (not _mode_private(path, directory=False) or
                type(row.get(key)) is not str or
                row[key] != _hash(path.read_bytes())):
            raise SelectionWorkerError("selection_task_artifact_hash_or_mode_invalid")
        try:
            loaded[key] = json.loads(path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SelectionWorkerError("selection_task_artifact_json_invalid") from None
    saved = loaded["saved_state_sha256"]
    verifier = loaded["verifier_receipt_sha256"]
    reset = loaded["reset_receipt_sha256"]
    actions = loaded["actions_sha256"]
    usage = loaded["usage_sha256"]
    frames = loaded["frames_sha256"]
    if (type(saved) is not dict or
            saved.get("schema") != "envloop-odoo-selection-saved-sql-v1" or
            saved.get("task_id") != task["task_id"] or
            type(saved.get("business_snapshot")) is not dict or
            type(saved.get("gui_reload_frame_sha256")) is not str or
            HEX64.fullmatch(saved["gui_reload_frame_sha256"]) is None or
            type(verifier) is not dict or
            verifier.get("schema") != "envloop-odoo-selection-verifier-v1" or
            verifier.get("task_id") != task["task_id"] or
            verifier.get("independent_select_only") is not True or
            verifier.get("verifier_source_sha256") != verifier_sha256() or
            verifier.get("score") != row["score"] or
            type(reset) is not dict or
            reset.get("schema") != "envloop-odoo-selection-reset-v1" or
            reset.get("task_id") != task["task_id"] or
            reset.get("pre_database_filestore_exact") is not True or
            reset.get("post_database_filestore_exact") is not True or
            reset.get("baseline_semantic_sha256") !=
            reset.get("restored_semantic_sha256") or
            type(actions) is not list or len(actions) > MAX_ACTIONS or
            type(usage) is not dict or
            usage.get("schema") != "envloop-odoo-selection-task-usage-v1" or
            usage.get("task_id") != task["task_id"] or
            usage.get("provider_billed_usd") is not None or
            usage.get("rendered_input_tokens") != row.get(
                "rendered_input_tokens") or
            usage.get("sampled_output_tokens") != row.get(
                "sampled_output_tokens") or
            len(usage.get("samples", [])) != row.get("sample_count") or
            type(row.get("sample_paid_attempt_ids")) is not list or
            len(row["sample_paid_attempt_ids"]) != row.get("sample_count") or
            [sample.get("paid_attempt_id") for sample in usage["samples"]]
            != row["sample_paid_attempt_ids"] or
            type(frames) is not list or
            len(frames) != row.get("frame_count") or not frames):
        raise SelectionWorkerError("selection_task_independent_evidence_invalid")
    frame_hashes = set()
    for step, frame in enumerate(frames):
        if (type(frame) is not dict or
                frame.get("path") != f"frames/step-{step:03d}.png" or
                type(frame.get("sha256")) is not str):
            raise SelectionWorkerError("selection_task_frame_manifest_invalid")
        path = directory / frame["path"]
        if (not _mode_private(path, directory=False) or
                frame["sha256"] != _hash(path.read_bytes())):
            raise SelectionWorkerError("selection_task_frame_changed")
        frame_hashes.add(frame["sha256"])
    if any(type(action) is not dict or
           action.get("frame_sha256") not in frame_hashes
           for action in actions):
        raise SelectionWorkerError("selection_action_frame_unbound")
    journal = directory / "sampling-journal" / "requests.sqlite3"
    if (row.get("sample_count", 0) < 1 or
            not _mode_private(journal, directory=False) or
            usage.get("sampling_journal_sha256") !=
            _hash(journal.read_bytes())):
        raise SelectionWorkerError("selection_sampler_journal_missing")


class RealTinkerSelectionSampler:
    """One pinned checkpoint service; one durable sample journal per task."""

    def __init__(self, checkpoint_path: str, config: dict,
                 output_root: Path, attempt_id: str):
        self.checkpoint_path = checkpoint_path
        self.config = config
        self.output_root = output_root
        self.attempt_id = attempt_id
        self.service = None
        self.backend = None
        self.renderer = None
        self.adapters = {}
        self.success = False

    def __enter__(self):
        from cursibench.scale_vision_proxy import (
            QwenVisionRenderer, TinkerVisionBackend, campaign_metadata,
        )
        import tinker
        self.renderer = QwenVisionRenderer.load()
        self.service = tinker.ServiceClient(user_metadata=campaign_metadata(
            "odoo-selection-" + _hash(self.attempt_id.encode())[:12]))
        try:
            self.backend = TinkerVisionBackend.from_service(
                self.service, self.renderer, checkpoint=self.checkpoint_path,
                seed=self.config["seed"])
            if self.backend.identity.get("checkpoint_sha256") != _hash(
                    self.checkpoint_path.encode()):
                raise SelectionWorkerError(
                    "selection_sampler_checkpoint_changed")
        except Exception:
            try:
                self.service.close("errored").result(timeout=30)
            except Exception:
                pass
            self.service = None
            raise SelectionProviderUncertain(
                "selection_sampler_initialization_uncertain") from None
        return self

    def sample(self, observation: Observation, *, task_index: int,
               step: int, task_dir: Path) -> dict:
        from cursibench.scale_vision_proxy import Limits, VisionSamplingAdapter
        adapter = self.adapters.get(task_index)
        if adapter is None:
            adapter = VisionSamplingAdapter(
                self.backend, task_dir / "sampling-journal",
                limits=Limits(max_actions=MAX_ACTIONS,
                              input_tokens=MAX_INPUT_TOKENS,
                              output_tokens=self.config["sample_max_tokens"],
                              request_timeout_seconds=SAMPLE_TIMEOUT_SECONDS))
            self.adapters[task_index] = adapter
        rendered = output_v066.render_for_model(observation)
        request_id = ("odoo-sel-" +
                      _hash(self.attempt_id.encode())[:10] +
                      f"-{task_index:02d}-{step:03d}")
        result = adapter.sample(request_id=request_id, **rendered)
        if result.get("reused") or result.get("new_dispatch") is not True:
            raise SelectionProviderUncertain("selection_sampler_replay_or_no_dispatch")
        return result

    def __exit__(self, exc_type, _exc, _tb):
        if self.service is not None:
            try:
                self.service.close("success" if exc_type is None else
                                   "errored").result(timeout=30)
            except Exception:
                raise SelectionProviderUncertain(
                    "selection_sampler_close_uncertain") from None


class _PaidSelectionSampler:
    """Reserve one exact, frame-bound Tinker attempt before each SDK sample."""

    def __init__(self, *, delegate, dispatch_paid: Callable, start: dict,
                 config: dict, config_sha256: str, runtime_sha256: str,
                 paid_attempt_ids: list[str], declared_attempt_ids: list[str],
                 timeout_rows: list[dict]):
        self.delegate = delegate
        self.dispatch_paid = dispatch_paid
        self.start = start
        self.config = config
        self.config_sha256 = config_sha256
        self.runtime_sha256 = runtime_sha256
        self.paid_attempt_ids = paid_attempt_ids
        self.declared_attempt_ids = declared_attempt_ids
        self.timeout_rows = timeout_rows

    def sample(self, observation: Observation, *, task_index: int,
               step: int, task_dir: Path) -> dict:
        if (type(observation) is not Observation or
                not 1 <= task_index <= MAX_TASKS or
                not 0 <= step < MAX_ACTIONS or
                len(observation.screenshot_bytes) > 4_000_000 or
                observation.task_id != self.start[
                    "selection_tasks"][task_index - 1]["task_id"] or
                observation.task_binding_sha256 != self.start[
                    "selection_tasks"][task_index - 1]["package_sha256"]):
            raise SelectionWorkerError("selection_paid_sample_frame_unbound")
        rendered = output_v066.render_for_model(observation)
        paid_id = (self.start["attempt_id"] +
                   f"-sample-{task_index:02d}-{step:03d}")
        self.declared_attempt_ids.append(paid_id)
        frame_sha = _hash(observation.screenshot_bytes)
        request = {
            "schema": "cua-full-study-selection-sampling-request-v1",
            "cell_id": "odoo-community",
            "selection_attempt": self.start["attempt_id"],
            "selection_identities_sha256": self.start[
                "selection_identities_sha256"],
            "checkpoint_path_sha256": self.start[
                "checkpoint_path_sha256"],
            "student_config_sha256": self.config_sha256,
            "worker_runtime_sha256": self.runtime_sha256,
            "task_id": observation.task_id,
            "package_sha256": observation.task_binding_sha256,
            "task_index": task_index,
            "step": step,
            "frame_id": observation.frame_id,
            "frame_sha256": frame_sha,
            "image_base64": base64.b64encode(
                observation.screenshot_bytes).decode(),
            "instruction": rendered["instruction"],
            "visible_text": rendered["visible_text"],
            "max_input_tokens": MAX_INPUT_TOKENS,
            "max_output_tokens": self.config["sample_max_tokens"],
        }

        def call(paid_request: dict) -> dict:
            if (paid_request != request or
                    _hash(base64.b64decode(
                        paid_request["image_base64"], validate=True)) !=
                    frame_sha):
                raise SelectionWorkerError("selection_paid_frame_request_changed")
            result = self.delegate.sample(
                observation, task_index=task_index, step=step,
                task_dir=task_dir)
            if (type(result) is not dict or
                    result.get("status") != "completed" or
                    result.get("new_dispatch") is not True or
                    result.get("reused") is True):
                self.timeout_rows.append({
                    "task_index": task_index, "step": step,
                    "paid_attempt_id": paid_id,
                    "failure_class": "provider_or_timeout_uncertain",
                    "subtype": (result.get("error_subtype") if
                                type(result) is dict else
                                "provider_result_invalid"),
                })
                raise SelectionProviderUncertain(
                    "selection_tinker_sample_uncertain")
            usage = result.get("usage")
            if (type(result.get("text")) is not str or
                    type(usage) is not dict or
                    type(usage.get("input_tokens")) is not int or
                    type(usage.get("output_tokens")) is not int or
                    usage["input_tokens"] <= 0 or
                    usage["output_tokens"] < 0):
                self.timeout_rows.append({
                    "task_index": task_index, "step": step,
                    "paid_attempt_id": paid_id,
                    "failure_class": "provider_usage_ambiguous",
                    "subtype": "completed_without_bounded_usage",
                })
                raise SelectionProviderUncertain(
                    "selection_tinker_usage_ambiguous")
            return {
                "schema": "envloop-odoo-v066-paid-sample-result-v1",
                "status": "completed", "text": result["text"],
                "request_id": result.get("request_id"),
                "error_subtype": None,
                "new_dispatch": True, "reused": False,
                "rendered_usage": usage,
                "usage": {"provider_billed_tokens": None},
                "sampler_result_sha256": _hash(_canonical(result)),
            }

        try:
            paid = self.dispatch_paid(
                attempt_id=paid_id, category="tinker",
                work={"selection_attempt": self.start["attempt_id"],
                      "task_id": observation.task_id,
                      "package_sha256": observation.task_binding_sha256,
                      "checkpoint_path_sha256": self.start[
                          "checkpoint_path_sha256"],
                      "task_index": task_index, "step": step,
                      "frame_sha256": frame_sha},
                request=request,
                reserve_usd=tinker_sample_reserve_usd(self.config),
                resource_reservation={}, provider=call)
        except Exception:
            if not any(row.get("paid_attempt_id") == paid_id for row in
                       self.timeout_rows):
                self.timeout_rows.append({
                    "task_index": task_index, "step": step,
                    "paid_attempt_id": paid_id,
                    "failure_class": "reservation_or_provider_uncertain",
                    "subtype": "paid_attempt_not_replayable",
                })
            raise SelectionProviderUncertain(
                "selection_tinker_paid_attempt_uncertain") from None
        result = paid.get("result") if type(paid) is dict else None
        if (type(paid) is not dict or
                paid.get("attempt_id") != paid_id or
                type(result) is not dict or
                result.get("status") != "completed" or
                type(result.get("text")) is not str):
            self.timeout_rows.append({
                "task_index": task_index, "step": step,
                "paid_attempt_id": paid_id,
                "failure_class": "paid_result_ambiguous",
                "subtype": "paid_response_cannot_be_scored",
            })
            raise SelectionProviderUncertain(
                "selection_tinker_paid_result_ambiguous")
        self.paid_attempt_ids.append(paid_id)
        return {**result, "paid_attempt_id": paid_id}


class RealOdooSelectionEnvironment:
    """Selection-only pinned Odoo worker; each case gets a full cold reset."""

    ROUTES = {
        "purchase": "/odoo/purchase", "inventory": "/odoo/inventory",
        "sales": "/odoo/sales", "crm": "/odoo/crm",
    }

    def __init__(self, worker_dir: Path):
        self.worker_dir = Path(worker_dir).resolve()
        self._cases = None
        self._package_by_id = None
        self.runtime_receipt = None

    def _module_boundary(self):
        # All historical Odoo modules share the *top-level* worker_lease
        # registry. Package-qualified imports would silently duplicate it.
        import factory
        import gui_controls
        import reset
        import verify
        import worker_lease
        private = self.worker_dir / "private"
        if (self.worker_dir.name != "selection" or
                factory.HERE != self.worker_dir or
                factory.PRIVATE != private or
                reset.HERE != self.worker_dir or
                verify.PRIVATE != private or
                gui_controls.PRIVATE != private or
                worker_lease.PRIVATE != private or
                not _mode_private(self.worker_dir / ".env", directory=False) or
                not _mode_private(private, directory=True) or
                factory.local_config().get("ODOO_PARTITION") != "selection" or
                _hash((self.worker_dir / "compose.yaml").read_bytes()) !=
                source_hashes()["enterprise_fallback/odoo18/compose.yaml"]):
            raise SelectionWorkerError("original_odoo_selection_worker_unbound")
        return factory, gui_controls, reset, verify, worker_lease

    def validate_tasks(self, tasks: list[dict]) -> None:
        factory, _, _, _, _ = self._module_boundary()
        private = factory.PRIVATE
        for name in ("partition_cases.json", "task_set_manifest.json",
                     "actor_credentials.json"):
            if not _mode_private(private / name, directory=False):
                raise SelectionWorkerError("private_selection_package_unsafe")
        world = json.loads((private / "partition_cases.json").read_bytes())
        manifest = json.loads((private / "task_set_manifest.json").read_bytes())
        selected = manifest.get("selection")
        if (type(selected) is not list or len(selected) != MAX_TASKS or
                len({row["task_id"] for row in selected}) != MAX_TASKS or
                {row["task_id"] for row in selected} !=
                {row["task_id"] for row in tasks} or
                {row["task_id"]: row["package_sha256"] for row in selected}
                != {row["task_id"]: row["package_sha256"] for row in tasks}):
            raise SelectionWorkerError("selection_private_manifest_mismatch")
        other_ids = {row["task_id"] for split, rows in manifest.items()
                     if split != "selection" and type(rows) is list
                     for row in rows}
        if other_ids & {row["task_id"] for row in selected}:
            raise SelectionWorkerError("selection_split_identity_overlap")
        cases = [(family, case) for family, rows in world["cases"].items()
                 if family in self.ROUTES for case in rows]
        if (len(cases) != MAX_TASKS or
                {case["id"] for _, case in cases} !=
                {row["task_id"] for row in selected}):
            raise SelectionWorkerError("selection_private_case_coverage_invalid")
        self._cases = {case["id"]: (family, case) for family, case in cases}
        self._package_by_id = {row["task_id"]: row["package_sha256"]
                               for row in selected}

    def reserve_local_capacity(self, request: dict) -> dict:
        self.validate_tasks(request["selection_tasks"])
        return {"schema": LOCAL_LEASE_SCHEMA,
                "status": "reserved_before_local_worker_start",
                "worker_runtime_sha256": request["worker_runtime_sha256"],
                "selection_identities_sha256": request[
                    "selection_identities_sha256"],
                "lease_seconds": LOCAL_LEASE_SECONDS,
                "provider_invoice_usd": None,
                "cost_basis": "nominal_local_opportunity_cost_upper"}

    def _compose(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["docker", "compose", "--env-file", ".env", *args],
                              cwd=self.worker_dir, capture_output=True,
                              text=True, check=True)

    def _running(self) -> set[str]:
        return set(self._compose("ps", "--status", "running",
                                 "--services").stdout.splitlines())

    @contextmanager
    def batch(self) -> Iterator["RealOdooSelectionEnvironment"]:
        factory, _, reset, _, worker_lease = self._module_boundary()
        if self._cases is None or self._package_by_id is None:
            raise SelectionWorkerError("selection_cases_not_preflighted")
        started_at = time.monotonic()
        with worker_lease.exclusive_worker_operation("selection_odoo_v066"):
            running_before = self._running()
            started = False
            try:
                if not {"db", "web"} <= running_before:
                    self._compose("up", "-d", "db", "web")
                started = True
                yield self
            finally:
                final_reset = None
                if started:
                    try:
                        final_reset = reset.restore()
                    except Exception:
                        final_reset = None
                try:
                    if "web" not in running_before:
                        self._compose("stop", "web")
                    if "db" not in running_before:
                        self._compose("stop", "db")
                    services_restored = self._running() == running_before
                except Exception:
                    services_restored = False
                elapsed = time.monotonic() - started_at
                self.runtime_receipt = {
                    "schema": "envloop-odoo-v066-selection-local-runtime-v1",
                    "elapsed_seconds": elapsed,
                    "lease_seconds": LOCAL_LEASE_SECONDS,
                    "final_database_snapshot_equal": bool(final_reset and
                        final_reset["business_snapshot_equal"]),
                    "final_physical_filestore_equal": bool(final_reset and
                        final_reset["physical_filestore_equal_before_web_restart"]),
                    "services_restored_to_initial_state": services_restored,
                    "provider_invoice_usd": None,
                    "cost_basis": "nominal_local_opportunity_cost_upper",
                }
                if (elapsed > LOCAL_LEASE_SECONDS or not services_restored or
                        not self.runtime_receipt["final_database_snapshot_equal"]
                        or not self.runtime_receipt[
                            "final_physical_filestore_equal"]):
                    raise SelectionWorkerError(
                        "selection_local_lease_or_final_reset_failed")

    def run_case(self, task: dict, index: int, sampler,
                 task_dir: Path) -> dict:
        factory, gui_controls, reset, verify, _ = self._module_boundary()
        if (self._cases is None or task["task_id"] not in self._cases or
                self._package_by_id[task["task_id"]] != task["package_sha256"]):
            raise SelectionWorkerError("selection_case_not_preflighted")
        family, case = self._cases[task["task_id"]]
        before = reset.restore()
        if (before["business_snapshot_equal"] is not True or
                before["physical_filestore_equal_before_web_restart"]
                is not True or verify.score(case["id"])["reward"] != 0.0):
            raise SelectionWorkerError("selection_case_baseline_not_exact")
        baseline = verify.snapshot()
        checkpoint = json.loads((factory.PRIVATE /
                                 "checkpoint_receipt.json").read_bytes())
        baseline_semantic = {"business_snapshot": baseline,
                             "db_checkpoint_sha256": checkpoint["db_sha256"],
                             "filestore_checkpoint_sha256": checkpoint[
                                 "filestore_sha256"]}
        (task_dir / "frames").mkdir(mode=0o700)
        frames = []
        actions = []
        samples = []
        termination = "unknown"
        saved = None
        score = None
        browser = None
        started = time.monotonic()
        try:
            from playwright.sync_api import sync_playwright
            credentials = json.loads((factory.PRIVATE /
                                      "actor_credentials.json").read_bytes())
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
                    instruction=case["prompt"])
                memory = ""
                for step in range(MAX_ACTIONS):
                    if time.monotonic() - started > WALL_SECONDS_PER_TASK:
                        termination = "task_wall_budget"
                        break
                    observation, rendered = adapter.observe_for_model(
                        memory=memory)
                    frame_raw = observation.screenshot_bytes
                    frame_path = task_dir / "frames" / f"step-{step:03d}.png"
                    _write_new(frame_path, frame_raw)
                    frames.append({"path": "frames/" + frame_path.name,
                                   "sha256": _hash(frame_raw),
                                   "frame_id_sha256": _hash(
                                       observation.frame_id.encode()),
                                   "rendered_instruction_sha256": _hash(
                                       rendered["instruction"].encode()),
                                   "visible_text_sha256": _hash(
                                       rendered["visible_text"].encode())})
                    result = sampler.sample(observation, task_index=index,
                                            step=step, task_dir=task_dir)
                    samples.append({
                        "step": step, "status": result.get("status"),
                        "error_subtype": result.get("error_subtype"),
                        "usage": result.get("rendered_usage"),
                        "request_id_sha256": _hash(str(result.get(
                            "request_id", "")).encode()),
                        "paid_attempt_id": result.get("paid_attempt_id"),
                        "model_text_sha256": (_hash(result["text"].encode())
                                              if type(result.get("text")) is str
                                              else None),
                    })
                    if result.get("status") != "completed":
                        raise SelectionProviderUncertain(
                            "selection_tinker_sample_uncertain")
                    usage = result.get("rendered_usage")
                    if (type(usage) is not dict or
                            type(usage.get("input_tokens")) is not int or
                            type(usage.get("output_tokens")) is not int or
                            usage["input_tokens"] <= 0 or
                            usage["output_tokens"] < 0):
                        raise SelectionProviderUncertain(
                            "selection_tinker_usage_ambiguous")
                    try:
                        action = output_v066.normalize_model_action(
                            result["text"], observation,
                            current_frame_id=observation.frame_id)
                    except ContractError:
                        termination = "model_action_invalid"
                        break
                    try:
                        applied = adapter.dispatch(action)
                    except ContractError as exc:
                        if (exc.code == "expired_frame" and
                                time.monotonic() - started >
                                WALL_SECONDS_PER_TASK):
                            termination = "task_wall_budget"
                            break
                        raise
                    actions.append({
                        "step": step, "frame_sha256": _hash(frame_raw),
                        "action_type": action["type"],
                        "contract_receipt": applied[
                            "public_contract_receipt"],
                        "sample_text_sha256": _hash(result["text"].encode()),
                    })
                    memory = action["memory"]
                    if applied["finished"]:
                        termination = "model_finish"
                        break
                else:
                    termination = "task_action_budget"
                # Browser reload is evaluator-owned readback, after actor work.
                page.reload(wait_until="domcontentloaded")
                page.locator("body").wait_for()
                reloaded_frame_sha = _hash(page.screenshot(type="png"))
                score = verify.score(case["id"])
                saved = {"schema": "envloop-odoo-selection-saved-sql-v1",
                         "task_id": task["task_id"],
                         "business_snapshot": verify.snapshot(),
                         "gui_reload_frame_sha256": reloaded_frame_sha,
                         "termination": termination}
                browser.close()
                browser = None
        finally:
            if browser is not None:
                browser.close()
            after = reset.restore()
            restored = verify.snapshot()
            reset_exact = bool(after["business_snapshot_equal"] and
                               after[
                                   "physical_filestore_equal_before_web_restart"]
                               and restored == baseline)
            reset_receipt = {
                "schema": "envloop-odoo-selection-reset-v1",
                "task_id": task["task_id"],
                "pre_database_filestore_exact": True,
                "post_database_filestore_exact": reset_exact,
                "baseline_semantic_sha256": _hash(_canonical(
                    baseline_semantic)),
                "restored_semantic_sha256": _hash(_canonical({
                    **baseline_semantic,
                    "business_snapshot": restored})),
            }
            _write_json(task_dir / "reset.private.json", reset_receipt)
            if not reset_exact:
                raise SelectionWorkerError("selection_case_reset_failed")
        if saved is None or score is None:
            raise SelectionWorkerError("selection_case_saved_state_missing")
        task_score = int(score["reward"] == 1.0 and
                         score["checks_passed"] is True and
                         score["difference_codes"] == [])
        verifier = {"schema": "envloop-odoo-selection-verifier-v1",
                    "task_id": task["task_id"],
                    "independent_select_only": True,
                    "verifier_source_sha256": verifier_sha256(),
                    "score": task_score,
                    "reward": score["reward"],
                    "checks_passed": score["checks_passed"],
                    "difference_codes": score["difference_codes"],
                    "no_regression_pass": bool(task_score),
                    "termination": termination}
        saved_sha = _write_json(task_dir / "saved-state.private.json", saved)
        verifier_sha = _write_json(task_dir / "verifier.private.json", verifier)
        actions_sha = _write_json(task_dir / "actions.private.json", actions)
        frames_sha = _write_json(task_dir / "frames.private.json", frames)
        rendered_input = sum(row["usage"]["input_tokens"] for row in samples)
        sampled_output = sum(row["usage"]["output_tokens"] for row in samples)
        usage_sha = _write_json(task_dir / "usage.private.json", {
            "schema": "envloop-odoo-selection-task-usage-v1",
            "task_id": task["task_id"], "samples": samples,
            "rendered_input_tokens": rendered_input,
            "sampled_output_tokens": sampled_output,
            "sampling_journal_sha256": (_hash((task_dir / "sampling-journal" /
                "requests.sqlite3").read_bytes()) if
                (task_dir / "sampling-journal" /
                 "requests.sqlite3").is_file() else None),
            "provider_billed_usd": None,
        })
        return {"task_id": task["task_id"],
                "package_sha256": task["package_sha256"],
                "score": task_score,
                "saved_state_sha256": saved_sha,
                "verifier_receipt_sha256": verifier_sha,
                "reset_receipt_sha256": _hash((task_dir /
                                                "reset.private.json").read_bytes()),
                "actions_sha256": actions_sha,
                "frames_sha256": frames_sha,
                "frame_count": len(frames),
                "usage_sha256": usage_sha,
                "sample_count": len(samples),
                "sample_paid_attempt_ids": [row["paid_attempt_id"]
                                            for row in samples],
                "rendered_input_tokens": rendered_input,
                "sampled_output_tokens": sampled_output,
                "termination": termination}


class OdooSelectionWorker:
    """Source-bound selection worker; only the 20 started task IDs enter it."""

    cell_id = "odoo-community"
    action_profile = ACTION_PROFILE_VERSION
    original_software_gui = True
    original_surface = "web"
    environment_category = "storage_application"

    def __init__(self, *, worker_dir: Path, private_output_root: Path,
                 ratification_path: Path | None = None,
                 ratification_sha256: str | None = None,
                 expected_runtime_sha256: str | None = None,
                 expected_verifier_sha256: str | None = None,
                 local_cost_authority_path: Path | None = None,
                 local_cost_authority_sha256: str | None = None,
                 enable_live: bool = False):
        self.worker_dir = Path(worker_dir).resolve()
        self.private_output_root = Path(private_output_root).resolve()
        self.ratification_path = (Path(ratification_path) if
                                  ratification_path is not None else None)
        self.ratification_sha256 = ratification_sha256
        self.expected_runtime_sha256 = expected_runtime_sha256
        self.expected_verifier_sha256 = expected_verifier_sha256
        self.local_cost_authority_path = (Path(local_cost_authority_path)
                                          if local_cost_authority_path is not None
                                          else None)
        self.local_cost_authority_sha256 = local_cost_authority_sha256
        self.enable_live = enable_live
        self.runtime_sha256 = runtime_sha256()
        self.verifier_sha256 = verifier_sha256()
        self.adapter_sha256 = adapter_sha256()
        self.environment = RealOdooSelectionEnvironment(self.worker_dir)

    def _require_freeze(self) -> dict:
        if (self.enable_live is not True or
                self.ratification_path is None or
                not _mode_private(self.ratification_path, directory=False) or
                type(self.ratification_sha256) is not str or
                not HEX64.fullmatch(self.ratification_sha256) or
                self.expected_runtime_sha256 != self.runtime_sha256 or
                self.expected_verifier_sha256 != self.verifier_sha256 or
                self.runtime_sha256 != runtime_sha256() or
                self.verifier_sha256 != verifier_sha256() or
                self.adapter_sha256 != adapter_sha256() or
                self.local_cost_authority_path is None or
                environment_class.category(self.cell_id) !=
                self.environment_category):
            raise SelectionWorkerError("selection_requires_real_six_cell_freeze")
        from native_desktop_factory.v066_final_freeze import validate_ratification
        try:
            value, digest = validate_ratification(self.ratification_path)
        except (OSError, ValueError, TypeError, KeyError):
            raise SelectionWorkerError("selection_ratification_invalid") from None
        profile = value.get("cell_profiles", {}).get(self.cell_id, {})
        if (digest != self.ratification_sha256 or
                profile.get("adapter_sha256") != self.adapter_sha256):
            raise SelectionWorkerError("selection_adapter_binding_changed")
        return _cost_authority(self.local_cost_authority_path,
                               self.local_cost_authority_sha256)

    def _check_output(self, out_dir: Path) -> None:
        if (not _mode_private(self.private_output_root, directory=True) or
                out_dir.exists() or out_dir.is_symlink() or
                not out_dir.resolve().is_relative_to(self.private_output_root)):
            raise SelectionWorkerError("selection_private_output_must_be_new")

    def _make_sampler(self, checkpoint_path: str, config: dict,
                      out_dir: Path, attempt_id: str):
        return RealTinkerSelectionSampler(checkpoint_path, config, out_dir,
                                          attempt_id)

    def _preflight_renderer(self) -> None:
        # Fail before any local-service or Tinker dollar reservation if the
        # pinned multimodal renderer cannot construct a Qwen image prompt.
        from cursibench.scale_vision_proxy import (
            MODEL, PROCESSOR, RENDERER, QwenVisionRenderer,
        )
        identity = QwenVisionRenderer.load().identity
        if (type(identity) is not dict or identity.get("model") != MODEL or
                identity.get("renderer") != RENDERER or
                identity.get("image_processor") != PROCESSOR):
            raise SelectionWorkerError("selection_qwen_renderer_unavailable")

    def run_selection(self, *, started: dict, checkpoint_path: str,
                      student_config_raw: bytes, student_config_sha256: str,
                      out_dir: Path, dispatch_paid: Callable) -> dict:
        """Return exact 20-task result plus paid IDs/usage evidence for caller.

        The caller records the returned result through
        ``session.record_selection_scored``. Invalid attempts return a private
        evaluator receipt for ``session.record_selection_invalid`` instead.
        """
        start = _start_view(started, checkpoint_path)
        config = _student_sampling_config(student_config_raw,
                                          student_config_sha256)
        if not callable(dispatch_paid):
            raise SelectionWorkerError("selection_paid_dispatch_missing")
        authority = self._require_freeze()
        out_dir = Path(out_dir).absolute()
        self._check_output(out_dir)
        out_dir.mkdir(mode=0o700)
        (out_dir / "tasks").mkdir(mode=0o700)
        paid_attempt_ids = []
        declared_paid_attempt_ids = []
        current_stage = "local_preflight"
        task_rows = []
        timeout_rows = []
        environment_failure = False
        sampler_holder = None
        sampler_open = False
        try:
            self._preflight_renderer()
            self.environment.validate_tasks(start["selection_tasks"])
            local_id = start["attempt_id"] + "-local-service"
            declared_paid_attempt_ids.append(local_id)
            local_request = {
                "schema": LOCAL_LEASE_SCHEMA,
                "cell_id": self.cell_id,
                "selection_attempt": start["attempt_id"],
                "selection_identities_sha256": start[
                    "selection_identities_sha256"],
                "selection_tasks": start["selection_tasks"],
                "worker_runtime_sha256": self.runtime_sha256,
                "local_cost_authority_sha256":
                    self.local_cost_authority_sha256,
                "lease_seconds": LOCAL_LEASE_SECONDS,
                "provider_invoice_usd": None,
            }
            current_stage = "local_service_reservation"
            local_paid = dispatch_paid(
                attempt_id=local_id, category="storage_application",
                work={"selection_attempt": start["attempt_id"],
                      "kind": "original_local_application_lease",
                      "identities_sha256": start[
                          "selection_identities_sha256"]},
                request=local_request,
                reserve_usd=local_upper_reserve_usd(authority),
                resource_reservation={},
                provider=self.environment.reserve_local_capacity)
            if (type(local_paid) is not dict or
                    local_paid.get("attempt_id") != local_id or
                    local_paid.get("result", {}).get("status") !=
                    "reserved_before_local_worker_start"):
                raise SelectionWorkerError(
                    "selection_local_service_reservation_ambiguous")
            paid_attempt_ids.append(local_id)
            setup_id = start["attempt_id"] + "-tinker-setup"
            declared_paid_attempt_ids.append(setup_id)
            setup_request = {
                "schema": "cua-full-study-selection-sampling-request-v1",
                "kind": "checkpoint_sampler_setup",
                "cell_id": self.cell_id,
                "selection_attempt": start["attempt_id"],
                "selection_identities_sha256": start[
                    "selection_identities_sha256"],
                "checkpoint_path_sha256": start[
                    "checkpoint_path_sha256"],
                "student_config_sha256": student_config_sha256,
                "worker_runtime_sha256": self.runtime_sha256,
                "model": "Qwen/Qwen3.8-27B",
                "provider_invoice_usd": None,
            }
            sampler_holder = self._make_sampler(
                checkpoint_path, config, out_dir, start["attempt_id"])

            def setup_sampler(_request: dict) -> dict:
                nonlocal sampler_open
                sampler_holder.__enter__()
                sampler_open = True
                return {"schema": "envloop-odoo-v066-sampler-setup-v1",
                        "status": "ready",
                        "checkpoint_path_sha256": start[
                            "checkpoint_path_sha256"],
                        "usage": {"provider_billed_tokens": None},
                        "provider_invoice_usd": None}

            current_stage = "tinker_setup_reservation"
            setup_paid = dispatch_paid(
                attempt_id=setup_id, category="tinker",
                work={"selection_attempt": start["attempt_id"],
                      "kind": "checkpoint_sampler_setup",
                      "checkpoint_path_sha256": start[
                          "checkpoint_path_sha256"]},
                request=setup_request,
                reserve_usd=tinker_sample_reserve_usd(config),
                resource_reservation={}, provider=setup_sampler)
            if (type(setup_paid) is not dict or
                    setup_paid.get("attempt_id") != setup_id or
                    setup_paid.get("result", {}).get("status") != "ready"):
                raise SelectionProviderUncertain(
                    "selection_sampler_setup_result_ambiguous")
            paid_attempt_ids.append(setup_id)
            paid_sampler = _PaidSelectionSampler(
                delegate=sampler_holder, dispatch_paid=dispatch_paid,
                start=start, config=config,
                config_sha256=student_config_sha256,
                runtime_sha256=self.runtime_sha256,
                paid_attempt_ids=paid_attempt_ids,
                declared_attempt_ids=declared_paid_attempt_ids,
                timeout_rows=timeout_rows)
            current_stage = "per_sample_tinker_and_odoo_gui"
            try:
                with self.environment.batch() as active:
                    for index, task in enumerate(
                            start["selection_tasks"], 1):
                        directory = (out_dir / "tasks" /
                                     f"task-{index:03d}")
                        directory.mkdir(mode=0o700)
                        row = active.run_case(task, index, paid_sampler,
                                              directory)
                        if (type(row) is not dict or
                                row.get("task_id") != task["task_id"] or
                                row.get("package_sha256") !=
                                task["package_sha256"] or
                                row.get("score") not in (0, 1) or
                                any(type(row.get(key)) is not str or
                                    HEX64.fullmatch(row[key]) is None
                                    for key in ("saved_state_sha256",
                                                "verifier_receipt_sha256",
                                                "reset_receipt_sha256"))):
                            raise SelectionWorkerError(
                                "selection_task_result_unbound")
                        _audit_task_artifacts(directory, task, row)
                        task_rows.append({
                            **row,
                            "checkpoint_sha256": start[
                                "checkpoint_path_sha256"],
                        })
            except SelectionProviderUncertain:
                raise
            except Exception:
                environment_failure = True
                raise
            finally:
                if sampler_open:
                    try:
                        sampler_holder.__exit__(None, None, None)
                    finally:
                        sampler_open = False
            runtime = self.environment.runtime_receipt
            if (type(runtime) is not dict or
                    runtime.get("services_restored_to_initial_state")
                    is not True or
                    runtime.get("final_database_snapshot_equal") is not True or
                    runtime.get("final_physical_filestore_equal") is not True or
                    runtime.get("elapsed_seconds", LOCAL_LEASE_SECONDS + 1)
                    > LOCAL_LEASE_SECONDS):
                environment_failure = True
                raise SelectionWorkerError("selection_batch_reset_unverified")
            runtime_sha = _write_json(
                out_dir / "local-runtime.private.json", runtime)
            task_ledger_sha = _write_json(
                out_dir / "task-ledger.private.json", {
                    "schema": "envloop-odoo-v066-selection-task-ledger-v1",
                    "selection_attempt": start["attempt_id"],
                    "checkpoint_sha256": start[
                        "checkpoint_path_sha256"],
                    "selection_identities_sha256": start[
                        "selection_identities_sha256"],
                    "worker_runtime_sha256": self.runtime_sha256,
                    "verifier_sha256": self.verifier_sha256,
                    "adapter_sha256": self.adapter_sha256,
                    "environment_mapping_sha256":
                        environment_class.binding_sha256(),
                    "paid_attempt_ids": paid_attempt_ids,
                    "rows": task_rows,
                })
            result = {
                "schema": RESULT_SCHEMA,
                "cell_id": self.cell_id,
                "checkpoint_sha256": start["checkpoint_path_sha256"],
                "evaluator_isolated": True,
                "tasks": [{key: row[key] for key in (
                    "task_id", "package_sha256", "score",
                    "saved_state_sha256", "verifier_receipt_sha256",
                    "reset_receipt_sha256")}
                    for row in task_rows],
            }
            if len(result["tasks"]) != MAX_TASKS:
                raise SelectionWorkerError(
                    "selection_task_coverage_incomplete")
            result_sha = _write_json(
                out_dir / "selection-result.private.json", result)
            usage = {"schema": USAGE_SCHEMA,
                     "selection_attempt": start["attempt_id"],
                     "checkpoint_sha256": start[
                         "checkpoint_path_sha256"],
                     "task_count": MAX_TASKS,
                     "sample_calls": sum(row["sample_count"] for row in
                                         task_rows),
                     "rendered_input_tokens": sum(row[
                         "rendered_input_tokens"] for row in task_rows),
                     "sampled_output_tokens": sum(row[
                         "sampled_output_tokens"] for row in task_rows),
                     "task_usage_sha256s": [row["usage_sha256"] for
                                             row in task_rows],
                     "paid_attempt_ids": paid_attempt_ids,
                     "task_ledger_sha256": task_ledger_sha,
                     "local_runtime_receipt_sha256": runtime_sha,
                     "tinker_provider_billed_usd": None,
                     "local_provider_invoice_usd": None,
                     "basis":
                         "per_sample_rendered_tokens_and_local_wall_not_invoice"}
            usage_sha = _write_json(out_dir / "usage.private.json", usage)
            timeout_sha = _write_json(out_dir / "timeouts.private.json", {
                "schema": TIMEOUT_SCHEMA,
                "selection_attempt": start["attempt_id"],
                "timeout_or_uncertain_count": len(timeout_rows),
                "rows": timeout_rows,
                "task_budget_termination_count": sum(
                    row["termination"] in {"task_wall_budget",
                                           "task_action_budget"}
                    for row in task_rows),
                "task_budget_rows": [
                    {"task_index": index,
                     "termination": row["termination"]}
                    for index, row in enumerate(task_rows, 1)
                    if row["termination"] in {"task_wall_budget",
                                              "task_action_budget"}],
            })
            result_raw = (out_dir /
                          "selection-result.private.json").read_bytes()
            if (result_sha != _hash(result_raw) or
                    [row["task_id"] for row in result["tasks"]] !=
                    [row["task_id"] for row in start["selection_tasks"]] or
                    [row["package_sha256"] for row in result["tasks"]] !=
                    [row["package_sha256"] for row in
                     start["selection_tasks"]]):
                raise SelectionWorkerError("selection_saved_result_changed")
            return {"status": "scored", "result": result,
                    "result_sha256": result_sha,
                    "paid_attempt_ids": paid_attempt_ids,
                    "task_ledger_path": str(out_dir /
                                            "task-ledger.private.json"),
                    "task_ledger_sha256": task_ledger_sha,
                    "usage_receipt_path": str(out_dir /
                                              "usage.private.json"),
                    "usage_receipt_sha256": usage_sha,
                    "timeout_receipt_path": str(out_dir /
                                                "timeouts.private.json"),
                    "timeout_receipt_sha256": timeout_sha,
                    "local_runtime_receipt_path": str(out_dir /
                        "local-runtime.private.json"),
                    "local_runtime_receipt_sha256": runtime_sha,
                    "provider_invoice_usd": None}
        except Exception as exc:
            if sampler_open and sampler_holder is not None:
                try:
                    sampler_holder.__exit__(type(exc), exc,
                                            exc.__traceback__)
                except Exception:
                    pass
            failure_type = ("environment" if environment_failure or
                            current_stage in {"local_preflight",
                                              "local_service_reservation"}
                            else "provider")
            failure = {"schema": "envloop-odoo-v066-selection-invalid-v1",
                       "selection_attempt": start["attempt_id"],
                       "failure_type": failure_type,
                       "failure_stage": current_stage,
                       "exception_type": type(exc).__name__,
                       "completed_task_count": len(task_rows),
                       "paid_attempt_ids_observed": paid_attempt_ids,
                       "paid_attempt_ids_declared":
                           declared_paid_attempt_ids,
                       "provider_invoice_usd": None,
                       "automatic_replay_authorized": False}
            receipt_sha = _write_json(out_dir / "invalid.private.json",
                                      failure)
            runtime = self.environment.runtime_receipt
            if (type(runtime) is dict and not
                    (out_dir / "local-runtime.private.json").exists()):
                _write_json(out_dir / "local-runtime.private.json", runtime)
            if not (out_dir / "timeouts.private.json").exists():
                _write_json(out_dir / "timeouts.private.json", {
                    "schema": TIMEOUT_SCHEMA,
                    "selection_attempt": start["attempt_id"],
                    "timeout_or_uncertain_count": len(timeout_rows),
                    "rows": timeout_rows,
                    "task_budget_termination_count": sum(
                        row["termination"] in {"task_wall_budget",
                                               "task_action_budget"}
                        for row in task_rows),
                    "task_budget_rows": [
                        {"task_index": index,
                         "termination": row["termination"]}
                        for index, row in enumerate(task_rows, 1)
                        if row["termination"] in {"task_wall_budget",
                                                  "task_action_budget"}],
                })
            return {"status": "invalid", "failure_type": failure_type,
                    "evaluator_receipt_sha256": receipt_sha,
                    "invalid_receipt_path": str(out_dir /
                                                "invalid.private.json"),
                    "timeout_receipt_path": str(out_dir /
                                                "timeouts.private.json"),
                    "local_runtime_receipt_path": (
                        str(out_dir / "local-runtime.private.json") if
                        (out_dir / "local-runtime.private.json").is_file()
                        else None),
                    "paid_attempt_ids": paid_attempt_ids,
                    "paid_attempt_ids_declared":
                        declared_paid_attempt_ids,
                    "provider_invoice_usd": None}


__all__ = ["OdooSelectionWorker", "RealOdooSelectionEnvironment",
           "RealTinkerSelectionSampler", "runtime_sha256",
           "tinker_upper_reserve_usd", "local_upper_reserve_usd"]
