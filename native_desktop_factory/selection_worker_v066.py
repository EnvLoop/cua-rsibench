"""Frozen 20-task native LibreOffice v0.6.6 Qwen selection worker.

The campaign owns every paid intent. This worker only accepts the exact
selection view returned by start_selection_attempt, binds one checkpoint,
and operates original LibreOffice Calc/Impress/Writer through E2B GUI methods.
Each task has a separately reserved actor guest, at least one Tinker sample,
independent actor-saved OOXML scoring, and a separately reserved fresh reset
guest. Scores are not returned until the campaign's paid-coverage auditor
accepts all 20 tasks and every related paid intent.

Live dispatch is disabled by default. Fake-provider tests use committed WDI
development files in a synthetic selection roster; they create no sandbox or
model call. No frozen v0.6.6 action/renderer/controller file is modified here.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import time
from typing import Callable

from cursibench import (full_study_campaign_dispatch_v1 as campaign,
                        full_study_selection_paid_coverage_v1 as paid_coverage,
                        scale_action_output_v066 as output_v066)
from cursibench.scale_action_contract import ContractError, Observation
from cursibench.scale_action_contract_v066 import ACTION_PROFILE_VERSION
from cursibench.scale_final_v06 import validate_splits
from cursibench.scale_vision_proxy import MODEL, PROCESSOR, RENDERER

from . import admit, factory_v2, qwen_v066_adapter
from .official_saved_verifier import verify_official
from .source import EXPECTED_SHA256
from .teacher_episode_worker_v066 import (
    DesktopGuest, RealDesktopGuest, _semantic_input,
    adapter_sha256, verifier_sha256,
)
from .v066_final_freeze import digest
from .verify import docx_content, pptx_slide_shapes, xlsx_cells


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cua-native-wdi-v066-selection-worker-v1"
RESULT_SCHEMA = "cua-full-study-selection-saved-result-v1"
TASK_SCHEMA = "cua-native-wdi-v066-selection-task-receipt-v1"
LEDGER_SCHEMA = "cua-native-wdi-v066-selection-paid-task-ledger-v1"
MAX_TASKS = 20
MAX_ACTIONS = 90
ACTOR_LEASE_SECONDS = 900
RESET_LEASE_SECONDS = 600
ACTOR_LEASE_RESERVE_USD = "0.250000000"
RESET_LEASE_RESERVE_USD = "0.166666667"
MAX_FRAME_BYTES = 4_000_000
MAX_INPUT_TOKENS = 32_768
MAX_OUTPUT_TOKENS = 4096
MAX_TASK_WALL_SECONDS = 1_600
MAX_BATCH_WALL_SECONDS = 16 * 3600
MAX_PRIVATE_EVIDENCE_BYTES = 2 * 1024 ** 3
MIN_HOST_FREE_BYTES = 8 * 1024 ** 3
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAMPLER_PATH = campaign.TINKER_PATH
SOURCE_FILES = (
    "native_desktop_factory/selection_worker_v066.py",
    "native_desktop_factory/teacher_episode_worker_v066.py",
    "native_desktop_factory/qwen_v064_adapter.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "native_desktop_factory/official_saved_verifier.py",
    "native_desktop_factory/formula_semantics.py",
    "native_desktop_factory/target_text_semantics.py",
    "native_desktop_factory/verify.py",
    "native_desktop_factory/admit.py",
    "native_desktop_factory/factory_v2.py",
    "native_desktop_factory/source.py",
    "src/cursibench/full_study_selection_paid_coverage_v1.py",
    "src/cursibench/full_study_selection_environment_v1.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_vision_proxy.py",
)


class DesktopSelectionError(RuntimeError):
    """Fixed private failure code; never include raw task or model text."""


class DesktopSelectionUncertain(DesktopSelectionError):
    """Provider/transport/cleanup ambiguity cannot be scored as task zero."""


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def source_hashes() -> dict[str, str]:
    return {relative: _sha((ROOT / relative).read_bytes())
            for relative in SOURCE_FILES}


def runtime_sha256() -> str:
    return _sha(_canonical(source_hashes()))


def _private(path: Path, *, directory: bool) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _write_new(path: Path, raw: bytes, *, limit: int = 20_000_000) -> dict:
    if (not raw or len(raw) > limit or path.exists() or path.is_symlink() or
            not _private(path.parent, directory=True)):
        raise DesktopSelectionError("selection_private_artifact_path_unsafe")
    if shutil.disk_usage(path.parent).free - len(raw) < MIN_HOST_FREE_BYTES:
        raise DesktopSelectionError("selection_host_free_space_floor_reached")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": path.name, "sha256": _sha(raw)}


def _read_bound(path: Path, sha: str) -> bytes:
    if (not _private(path, directory=False) or
            type(sha) is not str or HEX64.fullmatch(sha) is None):
        raise DesktopSelectionError("selection_private_artifact_missing")
    raw = path.read_bytes()
    if _sha(raw) != sha:
        raise DesktopSelectionError("selection_private_artifact_hash_changed")
    return raw


def _money(raw: object, *, positive: bool = True) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise DesktopSelectionError("selection_cost_decimal_invalid") from None
    if (not value.is_finite() or -value.as_tuple().exponent > 9 or
            (positive and value <= 0) or (not positive and value < 0)):
        raise DesktopSelectionError("selection_cost_decimal_invalid")
    return value


def _quote_sample(training: dict, max_output: int) -> str:
    price = ((Decimal(MAX_INPUT_TOKENS) *
              _money(training["prefill_usd_per_million_tokens"]) +
              Decimal(max_output) *
              _money(training["sample_usd_per_million_tokens"])) /
             Decimal(1_000_000) *
             _money(training["billing_multiplier_upper"]))
    return str(price.quantize(Decimal("0.000000001"),
                              rounding=ROUND_CEILING))


def _runtime_dependencies() -> None:
    """Production Desktop extra; report venv is deliberately insufficient."""
    from importlib.metadata import version
    try:
        observed = {name: version(name) for name in
                    ("e2b-desktop", "e2b", "Pillow", "tinker")}
    except Exception:
        raise DesktopSelectionError(
            "selection_pinned_desktop_extra_missing") from None
    if observed != {"e2b-desktop": "2.2.0", "e2b": "2.51.0",
                    "Pillow": "11.3.0", "tinker": "0.30.0"}:
        raise DesktopSelectionError("selection_pinned_desktop_extra_missing")


@dataclass(frozen=True)
class SelectionPackage:
    identity: dict
    source: bytes
    oracle: dict
    filename: str
    instruction: str
    source_inventory_sha256: str


def _source_attribution_present(raw: bytes, suffix: str) -> bool:
    if suffix == ".xlsx":
        values = [str(cell["value"]) for sheet in xlsx_cells(raw).values()
                  for cell in sheet.values() if cell["value"] is not None]
    elif suffix == ".pptx":
        values = [text for slide in pptx_slide_shapes(raw) for text in slide]
    elif suffix == ".docx":
        content = docx_content(raw)
        values = [*content["paragraphs"],
                  *(text for table in content["tables"]
                    for row in table for text in row)]
    else:
        return False
    text = " ".join(values).lower()
    return all(phrase in text for phrase in
               ("world bank", "cc by 4.0", "envloop"))


def _load_selection_packages(candidate_root: Path, private_map: Path,
                             identities: list[dict],
                             expected_inventory_sha256: str) -> list[SelectionPackage]:
    """Open all 20 selection packages before any paid/model operation."""
    if (not candidate_root.is_dir() or candidate_root.is_symlink() or
            not _private(private_map, directory=False) or
            type(expected_inventory_sha256) is not str or
            HEX64.fullmatch(expected_inventory_sha256) is None):
        raise DesktopSelectionError("selection_private_source_missing")
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    map_raw = private_map.read_bytes()
    rows = inventory.get("tasks")
    if (digest(inventory_raw) != expected_inventory_sha256 or
            inventory.get("schema") != "cua-native-wdi-candidate-inventory-v1" or
            inventory.get("design_revision") != "v2-distinct-structures" or
            inventory.get("source_sha256") != EXPECTED_SHA256 or
            inventory.get("private_map_sha256") != digest(map_raw) or
            type(rows) is not list or len(rows) != 140):
        raise DesktopSelectionError("selection_inventory_or_source_binding_changed")
    try:
        task_sets = {name: [] for name in ("train", "selection", "official")}
        for row in rows:
            split = ("official" if row["split"] == "final_candidate"
                     else row["split"])
            task_sets[split].append({key: row[key] for key in (
                "task_id", "package_sha256", "source_groups",
                "template_group", "instance_group")})
        if len(validate_splits(task_sets)) != 100:
            raise ValueError("incomplete source split")
    except (ValueError, KeyError, TypeError):
        raise DesktopSelectionError("selection_source_template_split_overlap") from None
    selected = {row["task_id"]: row for row in rows
                if row.get("split") == "selection"}
    if (len(selected) != MAX_TASKS or len(identities) != MAX_TASKS or
            set(selected) != {row["task_id"] for row in identities}):
        raise DesktopSelectionError("selection_roster_not_exact_source_split")
    train_and_final = {row["task_id"] for row in rows
                       if row.get("split") != "selection"}
    if train_and_final & set(selected):
        raise DesktopSelectionError("selection_source_id_leaked_across_splits")
    packages = []
    for identity in identities:
        row = selected[identity["task_id"]]
        if (type(identity) is not dict or
                set(identity) != {"task_id", "package_sha256"} or
                row.get("package_sha256") != identity["package_sha256"] or
                row.get("split") != "selection"):
            raise DesktopSelectionError("selection_package_identity_changed")
        try:
            package_dir, source, oracle = admit._package(candidate_root, row)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise DesktopSelectionError("selection_ooxml_package_changed") from None
        files = [*package_dir.glob("*.xlsx"), *package_dir.glob("*.pptx"),
                 *package_dir.glob("*.docx")]
        if (len(files) != 1 or oracle.get("split") != "selection" or
                oracle.get("source_sha256") != EXPECTED_SHA256 or
                oracle.get("design_revision") != "v2-distinct-structures" or
                oracle.get("edits") != 2 or
                len(oracle.get("targets", {})) != 2 or
                row.get("template_group") !=
                factory_v2.TEMPLATES["selection"].get(row.get("workflow"))):
            raise DesktopSelectionError("selection_original_office_source_missing")
        workflow = row["workflow"]
        signature = oracle.get("structure_signature")
        if workflow.startswith("calc-"):
            expected_signature = {"sheets": 3, "targets": ["B5", "B6"],
                                  "policy_sheet": False}
            structure_passed = len(xlsx_cells(source)) == 3
        elif workflow == "impress-deck":
            expected_signature = {"slides": 5, "targets": 2}
            structure_passed = (len(pptx_slide_shapes(source)) == 5 and
                                oracle.get("target_slide") == 4)
        elif workflow == "writer-brief":
            expected_signature = {"tables": 1, "source_years": 3,
                                  "targets": 2}
            structure_passed = len(docx_content(source)["tables"]) == 1
        else:
            raise DesktopSelectionError("selection_office_workflow_unknown")
        if signature != expected_signature or not structure_passed:
            raise DesktopSelectionError("selection_v2_structure_not_authentic")
        if not _source_attribution_present(source, files[0].suffix):
            raise DesktopSelectionError("selection_wdi_attribution_missing")
        instruction = (package_dir / "actor_task.txt").read_text()
        packages.append(SelectionPackage(
            identity=dict(identity), source=source, oracle=oracle,
            filename=files[0].name, instruction=instruction,
            source_inventory_sha256=digest(inventory_raw)))
    return packages


def _load_selection_profiles(path: Path | None,
                             expected_sha256: str | None,
                             inventory_sha256: str,
                             guest_identity_public_sha256: str,
                             expected_guest_content_sha256: str,
                             identities: object) -> dict[str, dict]:
    """Bind a premeasured neutral LibreOffice profile to each of 20 IDs."""
    if (path is None or not _private(path, directory=False) or
            type(expected_sha256) is not str or
            HEX64.fullmatch(expected_sha256) is None or
            digest(path.read_bytes()) != expected_sha256):
        raise DesktopSelectionError("selection_per_id_profile_reference_missing")
    try:
        profiles = json.loads(path.read_bytes())
        accepted = profiles["accepted"]
        by_id = {row["task_id"]: row for row in accepted}
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        raise DesktopSelectionError(
            "selection_per_id_profile_reference_invalid") from None
    if (type(identities) is not list or len(identities) != MAX_TASKS or
            any(type(row) is not dict or
                set(row) != {"task_id", "package_sha256"}
                for row in identities) or
            type(accepted) is not list or len(accepted) != MAX_TASKS or
            len(by_id) != MAX_TASKS or
            profiles.get("schema") !=
            "cua-native-wdi-v066-selection-profile-baselines-private-v1" or
            profiles.get("candidate_inventory_sha256") !=
            inventory_sha256 or
            profiles.get("guest_identity_public_sha256") !=
            guest_identity_public_sha256 or
            profiles.get("distinct_sandbox_count") != MAX_TASKS or
            profiles.get("model_calls") != 0 or
            profiles.get("provider_invoice_usd") is not None):
        raise DesktopSelectionError("selection_per_id_profile_reference_invalid")
    expected = {row["task_id"]: row["package_sha256"]
                for row in identities}
    if (len(expected) != MAX_TASKS or set(expected) != set(by_id) or
            any(type(row) is not dict or
                set(row) != {"task_id", "package_sha256",
                             "canonical_profile_sha256",
                             "receipt_path", "receipt_sha256"} or
                row["package_sha256"] != expected[row["task_id"]] or
                type(row["canonical_profile_sha256"]) is not str or
                HEX64.fullmatch(row["canonical_profile_sha256"]) is None or
                type(row["receipt_sha256"]) is not str or
                HEX64.fullmatch(row["receipt_sha256"]) is None
                for row in accepted)):
        raise DesktopSelectionError("selection_per_id_profile_reference_invalid")
    result = {}
    sandbox_ids = set()
    for task_id, row in by_id.items():
        relative = Path(row["receipt_path"])
        receipt_path = path.parent / relative
        if (relative.is_absolute() or ".." in relative.parts or
                not receipt_path.resolve().is_relative_to(
                    path.parent.resolve()) or
                not _private(receipt_path, directory=False)):
            raise DesktopSelectionError("selection_per_id_profile_receipt_unsafe")
        raw = receipt_path.read_bytes()
        if _sha(raw) != row["receipt_sha256"]:
            raise DesktopSelectionError("selection_per_id_profile_receipt_changed")
        try:
            receipt = json.loads(raw)
            screenshots = list(receipt_path.parent.glob("neutral-open.png"))
            neutral_files = list(receipt_path.parent.glob("neutral-baseline.*"))
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            raise DesktopSelectionError("selection_per_id_profile_receipt_invalid") from None
        if (receipt.get("schema") !=
                "cua-native-wdi-v066-selection-profile-baseline-v1" or
                receipt.get("status") != "profile_baseline_passed" or
                receipt.get("split") != "selection" or
                receipt.get("task_id") != task_id or
                receipt.get("package_sha256") != expected[task_id] or
                receipt.get("canonical_profile_sha256") !=
                row["canonical_profile_sha256"] or
                receipt.get("profile_snapshot_sha256s") !=
                [row["canonical_profile_sha256"]] * 2 or
                receipt.get("guest_content_sha256") !=
                expected_guest_content_sha256 or
                receipt.get("provider_kind") != "e2b_desktop" or
                receipt.get("sdk_version") != "2.2.0" or
                receipt.get("provider_shape_attested") is not True or
                receipt.get("fresh_profile_absent") is not True or
                receipt.get("source_semantics_equal_after_neutral_save")
                is not True or
                receipt.get("kill_returned") is not True or
                receipt.get("is_running_after_kill") is not False or
                receipt.get("model_calls") != 0 or
                receipt.get("provider_invoice_usd") is not None or
                receipt.get("lease_seconds") != 600 or
                receipt.get("full_lease_reserved_usd") != "0.166666667" or
                type(receipt.get("input_sha256")) is not str or
                HEX64.fullmatch(receipt["input_sha256"]) is None or
                type(receipt.get("neutral_input_sha256")) is not str or
                HEX64.fullmatch(receipt["neutral_input_sha256"]) is None or
                len(screenshots) != 1 or len(neutral_files) != 1 or
                not _private(screenshots[0], directory=False) or
                not _private(neutral_files[0], directory=False) or
                _sha(screenshots[0].read_bytes()) !=
                receipt.get("neutral_open_screenshot_sha256") or
                _sha(neutral_files[0].read_bytes()) !=
                receipt["neutral_input_sha256"] or
                receipt.get("sandbox_id_sha256") in sandbox_ids):
            raise DesktopSelectionError("selection_per_id_profile_receipt_invalid")
        sandbox_ids.add(receipt["sandbox_id_sha256"])
        result[task_id] = {
            "canonical_profile_sha256": row["canonical_profile_sha256"],
            "input_sha256": receipt["input_sha256"],
            "receipt_sha256": row["receipt_sha256"],
        }
    return result


class RealDesktopSelectionBackend:
    is_fake = False

    def create(self, phase: str, lease_seconds: int,
               package: SelectionPackage) -> "RealDesktopSelectionGuest":
        if not os.environ.get("E2B_API_KEY"):
            raise DesktopSelectionError("selection_e2b_key_missing_before_create")
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(
            template="desktop", resolution=(1280, 800),
            timeout=lease_seconds, allow_internet_access=False,
            metadata={"envloop_purpose": "native-wdi-v066-selection-" + phase,
                      "envloop_package_sha12":
                      package.identity["package_sha256"][:12]})
        return RealDesktopSelectionGuest(sandbox, phase=phase)


class RealDesktopSelectionGuest(RealDesktopGuest):
    """Render the exact frozen selection action limit in each observation."""

    def observe(self, *, task: dict, step: int, previous: dict | None,
                memory: str, max_actions: int) -> Observation:
        class _Camera:
            def __init__(self, guest):
                self.guest = guest

            def screenshot(self):
                return self.guest._screenshot()

        frame = qwen_v066_adapter.observe(
            _Camera(self), task_id=task["task_id"],
            task_binding_sha256=task["package_sha256"],
            instruction=task["visible_instruction"],
            step=step, previous_action_result=previous,
            memory=memory, max_actions=max_actions)
        self._latest = frame
        return frame


class RealTinkerSelectionSampler:
    """Pinned checkpoint sampler; its setup and each sample have paid intents."""

    is_fake = False

    def __init__(self):
        self.service = None
        self.backend = None
        self.renderer = None
        self.adapters = {}
        self.checkpoint_sha256 = None
        self.config = None

    def start(self, *, checkpoint_path: str, checkpoint_sha256: str,
              config: dict, out_dir: Path, attempt_id: str) -> dict:
        from cursibench.scale_vision_proxy import (
            QwenVisionRenderer, TinkerVisionBackend, campaign_metadata,
        )
        import tinker
        try:
            self.renderer = QwenVisionRenderer.load()
            if (self.renderer.identity.get("model") != MODEL or
                    self.renderer.identity.get("renderer") != RENDERER or
                    self.renderer.identity.get("image_processor") != PROCESSOR):
                raise DesktopSelectionError("selection_qwen_renderer_drift")
            self.service = tinker.ServiceClient(user_metadata=campaign_metadata(
                "desktop-selection-" + _sha(attempt_id.encode())[:12]))
            self.backend = TinkerVisionBackend.from_service(
                self.service, self.renderer, checkpoint=checkpoint_path,
                seed=config["seed"])
            identity = self.backend.identity
            if (identity.get("sampling_kind") != "checkpoint" or
                    identity.get("checkpoint_sha256") != checkpoint_sha256 or
                    self.backend.sampling_client.get_base_model() != MODEL):
                raise DesktopSelectionError("selection_sampler_checkpoint_drift")
        except Exception:
            try:
                self.close(success=False)
            except Exception:
                pass
            raise DesktopSelectionUncertain(
                "selection_sampler_setup_uncertain") from None
        self.checkpoint_sha256 = checkpoint_sha256
        self.config = config
        self.out_dir = out_dir
        self.attempt_id = attempt_id
        return {"schema": "cua-native-wdi-v066-sampler-setup-v1",
                "status": "ready", "checkpoint_path_sha256": checkpoint_sha256,
                "provider_invoice_usd": None}

    def sample(self, *, observation: Observation,
               ordinal: int, step: int, task_dir: Path) -> dict:
        from cursibench.scale_vision_proxy import Limits, VisionSamplingAdapter
        adapter = self.adapters.get(ordinal)
        if adapter is None:
            adapter = VisionSamplingAdapter(
                self.backend, task_dir / "sampling-journal",
                limits=Limits(max_actions=self.config["max_actions"],
                              input_tokens=MAX_INPUT_TOKENS,
                              output_tokens=self.config["max_output_tokens"],
                              request_timeout_seconds=120))
            self.adapters[ordinal] = adapter
        rendered = output_v066.render_for_model(observation)
        request_id = ("desktop-sel-" +
                      _sha(self.attempt_id.encode())[:12] +
                      f"-{ordinal:02d}-{step:03d}")
        result = adapter.sample(request_id=request_id, **rendered)
        if result.get("reused") or result.get("new_dispatch") is not True:
            raise DesktopSelectionUncertain("selection_sampler_replay_or_no_dispatch")
        return result

    def close(self, *, success: bool) -> None:
        if self.service is None:
            return
        try:
            self.service.close("success" if success else "errored").result(
                timeout=30)
        except Exception:
            raise DesktopSelectionUncertain(
                "selection_sampler_close_uncertain") from None
        finally:
            self.service = None


class DesktopSelectionWorker:
    """One saved-state-gated 20-task original-Desktop selection attempt."""

    cell_id = "desktop-native"
    action_profile = ACTION_PROFILE_VERSION
    requires_e2b = True
    original_software_gui = True
    original_surface = "native"

    def __init__(self, *, candidate_root: Path,
                 private_map: Path, guest_identity_public: Path,
                 expected_inventory_sha256: str,
                 expected_guest_identity_sha256: str,
                 profile_private_manifest: Path | None = None,
                 expected_profile_manifest_sha256: str | None = None,
                 enable_live: bool = False,
                 backend: object | None = None,
                 sampler: object | None = None):
        self.candidate_root = Path(candidate_root).resolve()
        self.private_map = Path(private_map).resolve()
        self.guest_identity_public = Path(guest_identity_public).resolve()
        self.expected_inventory_sha256 = expected_inventory_sha256
        self.expected_guest_identity_sha256 = expected_guest_identity_sha256
        self.profile_private_manifest = (Path(profile_private_manifest).resolve()
                                         if profile_private_manifest else None)
        self.expected_profile_manifest_sha256 = (
            expected_profile_manifest_sha256)
        self._profiles: dict[str, str] = {}
        self.enable_live = enable_live
        self.runtime_sha256 = runtime_sha256()
        self.verifier_sha256 = verifier_sha256()
        self.adapter_sha256 = adapter_sha256()
        if enable_live and (backend is not None or sampler is not None):
            raise DesktopSelectionError("selection_fake_provider_cannot_enable_live")
        self.backend = backend if backend is not None else RealDesktopSelectionBackend()
        self.sampler = sampler if sampler is not None else RealTinkerSelectionSampler()
        self._evidence_bytes = 0

    def _require_frozen(self, session, started: dict) -> tuple[dict, dict]:
        if (self.enable_live is not True or
                getattr(self.backend, "is_fake", False) or
                getattr(self.sampler, "is_fake", False)):
            raise DesktopSelectionError("selection_requires_real_six_cell_freeze")
        try:
            from cursibench import full_study_teacher_adapter_v1 as teacher
            cell_id, ratification = teacher._frozen_session(session)
        except Exception:
            raise DesktopSelectionError("selection_requires_real_six_cell_freeze") from None
        cell = next((row for row in session.study.plan["cells"]
                     if row["cell_id"] == cell_id), None)
        if (cell_id != self.cell_id or cell is None or
                ratification["cell_profiles"][cell_id]["adapter_sha256"] !=
                self.adapter_sha256 or
                cell["matched_bindings"]["runtime"] != self.runtime_sha256 or
                cell["matched_bindings"]["verifier"] != self.verifier_sha256 or
                self.runtime_sha256 != runtime_sha256() or
                self.verifier_sha256 != verifier_sha256() or
                self.adapter_sha256 != adapter_sha256()):
            raise DesktopSelectionError("selection_runtime_or_action_binding_changed")
        if (type(self.expected_inventory_sha256) is not str or
                HEX64.fullmatch(self.expected_inventory_sha256) is None or
                type(self.expected_guest_identity_sha256) is not str or
                HEX64.fullmatch(self.expected_guest_identity_sha256) is None or
                not self.guest_identity_public.is_file() or
                self.guest_identity_public.is_symlink() or
                digest(self.guest_identity_public.read_bytes()) !=
                self.expected_guest_identity_sha256):
            raise DesktopSelectionError("selection_source_or_guest_reference_unbound")
        self._profiles = _load_selection_profiles(
            self.profile_private_manifest,
            self.expected_profile_manifest_sha256,
            self.expected_inventory_sha256,
            self.expected_guest_identity_sha256,
            json.loads(self.guest_identity_public.read_bytes())["static_content_sha256"],
            started.get("selection_tasks") if type(started) is dict else None)
        _runtime_dependencies()
        required = {"attempt_id", "checkpoint_path_sha256",
                    "selection_tasks", "selection_identities_sha256",
                    "task_count"}
        if type(started) is not dict or set(started) != required:
            raise DesktopSelectionError("selection_started_view_invalid")
        tasks = started["selection_tasks"]
        events = [row for row in session._events("selection_started")
                  if row["data"].get("attempt_id") == started["attempt_id"]]
        if (type(tasks) is not list or len(tasks) != MAX_TASKS or
                any(type(row) is not dict or set(row) !=
                    {"task_id", "package_sha256"} or
                    type(row["task_id"]) is not str or
                    type(row["package_sha256"]) is not str or
                    HEX64.fullmatch(row["package_sha256"]) is None
                    for row in tasks) or
                len({row["task_id"] for row in tasks}) != MAX_TASKS or
                tasks != list(session.views["selection"]) or
                started["task_count"] != MAX_TASKS or
                type(started["attempt_id"]) is not str or
                campaign.dollars.ATTEMPT.fullmatch(
                    started["attempt_id"]) is None or
                type(started["checkpoint_path_sha256"]) is not str or
                HEX64.fullmatch(started["checkpoint_path_sha256"]) is None or
                started["selection_identities_sha256"] !=
                _sha(_canonical(tasks)) or len(events) != 1 or
                events[0]["data"].get("selection_identities_sha256") !=
                started["selection_identities_sha256"] or
                events[0]["data"].get("checkpoint_path_sha256") !=
                started["checkpoint_path_sha256"]):
            raise DesktopSelectionError("selection_attempt_not_frozen_exactly")
        return cell, events[0]["data"]

    def _resolve_checkpoint(self, session, checkpoint_sha256: str) -> str:
        rows = [row["data"] for row in session._events("tinker_checkpoint")
                if row["data"].get("checkpoint_path_sha256") ==
                checkpoint_sha256]
        if len(rows) != 1:
            raise DesktopSelectionError("selection_checkpoint_not_unique")
        paid_id = rows[0]["paid_attempt_id"]
        path = session.directory / f"{paid_id}.result.private.json"
        raw = _read_bound(path, next(
            (row["data"]["result_sha256"] for row in
             session._events("paid_result") if
             row["data"].get("attempt_id") == paid_id), ""))
        receipt = json.loads(raw)
        checkpoint = receipt.get("checkpoint_path")
        if (type(checkpoint) is not str or
                SAMPLER_PATH.fullmatch(checkpoint) is None or
                _sha(checkpoint.encode()) != checkpoint_sha256 or
                receipt.get("observed_base_model") != MODEL):
            raise DesktopSelectionError("selection_checkpoint_result_not_bound")
        return checkpoint

    def _policy(self, session, cell: dict) -> tuple[dict, dict]:
        training, training_sha = session.study.student_training_configuration()
        sampling, execution = cell["sampling"], cell["execution"]
        if (training.get("model") != MODEL or
                training.get("action_profile") != ACTION_PROFILE_VERSION or
                type(sampling.get("seed")) is not int or
                type(sampling.get("max_output_tokens")) is not int or
                not 0 < sampling["max_output_tokens"] <=
                training["sample_max_tokens"] <= MAX_OUTPUT_TOKENS or
                type(execution.get("max_actions_per_task")) is not int or
                not 0 < execution["max_actions_per_task"] <= MAX_ACTIONS or
                type(execution.get("max_wall_seconds_per_task")) is not int or
                not 0 < execution["max_wall_seconds_per_task"] <=
                ACTOR_LEASE_SECONDS - 120 or
                training["max_supervised_tokens"] > MAX_INPUT_TOKENS):
            raise DesktopSelectionError("selection_frozen_qwen_or_wall_policy_invalid")
        try:
            temperature = Decimal(str(sampling["temperature"]))
        except (InvalidOperation, ValueError, TypeError):
            raise DesktopSelectionError("selection_temperature_invalid") from None
        if not temperature.is_finite() or not 0 <= temperature <= 2:
            raise DesktopSelectionError("selection_temperature_invalid")
        for key in ("prefill_usd_per_million_tokens",
                    "sample_usd_per_million_tokens",
                    "billing_multiplier_upper"):
            _money(training[key])
        if _money(training["billing_multiplier_upper"]) < 1:
            raise DesktopSelectionError("selection_tinker_multiplier_below_one")
        actor_hours = (Decimal(ACTOR_LEASE_SECONDS) /
                       Decimal(3600)).quantize(
                           Decimal("0.000000001"),
                           rounding=ROUND_CEILING)
        reset_hours = (Decimal(RESET_LEASE_SECONDS) /
                       Decimal(3600)).quantize(
                           Decimal("0.000000001"),
                           rounding=ROUND_CEILING)
        required_hours = Decimal(MAX_TASKS) * (actor_hours + reset_hours)
        required_usd = (Decimal(MAX_TASKS) *
                        (Decimal(ACTOR_LEASE_RESERVE_USD) +
                         Decimal(RESET_LEASE_RESERVE_USD)))
        quote = _quote_sample(training, sampling["max_output_tokens"])
        if (_money(session.intent.get("e2b_sandbox_hours_cap")) <
                required_hours or
                _money(session.intent.get("e2b_usd_cap")) < required_usd or
                _money(quote) <= 0):
            raise DesktopSelectionError("selection_e2b_or_tinker_budget_insufficient")
        return training, {"max_actions": execution["max_actions_per_task"],
                          "actor_wall_seconds": execution["max_wall_seconds_per_task"],
                          "max_output_tokens": sampling["max_output_tokens"],
                          "seed": sampling["seed"],
                          "temperature": float(temperature),
                          "training_sha256": training_sha}

    def _check_output(self, session, out_dir: Path) -> None:
        work = Path(session.study.repo_root) / "work"
        if (not work.is_dir() or work.is_symlink() or
                out_dir.exists() or out_dir.is_symlink() or
                not _private(out_dir.parent, directory=True) or
                not out_dir.resolve().is_relative_to(work.resolve()) or
                shutil.disk_usage(work).free < MIN_HOST_FREE_BYTES):
            raise DesktopSelectionError("selection_private_output_or_host_space_unsafe")

    def _save(self, batch_dir: Path, path: Path, raw: bytes,
              *, limit: int = 20_000_000) -> dict:
        if (self._evidence_bytes + len(raw) > MAX_PRIVATE_EVIDENCE_BYTES or
                shutil.disk_usage(batch_dir).free - len(raw) <
                MIN_HOST_FREE_BYTES):
            raise DesktopSelectionError("selection_private_evidence_budget_exhausted")
        ref = _write_new(path, raw, limit=limit)
        self._evidence_bytes += len(raw)
        return ref

    @staticmethod
    def _storage_check(batch_dir: Path) -> None:
        total = sum(path.stat().st_size for path in batch_dir.rglob("*")
                    if path.is_file() and not path.is_symlink())
        if (total > MAX_PRIVATE_EVIDENCE_BYTES or
                shutil.disk_usage(batch_dir).free < MIN_HOST_FREE_BYTES):
            raise DesktopSelectionError(
                "selection_private_evidence_or_host_space_exhausted")

    def _reserve_sampler_setup(self, *, session, started: dict,
                               checkpoint_path: str, policy: dict,
                               out_dir: Path, paid_ids: list[str],
                               declared_ids: list[str]) -> None:
        paid_id = started["attempt_id"] + "-tinker-setup"
        declared_ids.append(paid_id)
        request = {
            "schema": "cua-full-study-selection-sampling-request-v1",
            "kind": "checkpoint_sampler_setup",
            "cell_id": self.cell_id,
            "selection_attempt": started["attempt_id"],
            "selection_identities_sha256":
                started["selection_identities_sha256"],
            "checkpoint_path_sha256": started["checkpoint_path_sha256"],
            "worker_runtime_sha256": self.runtime_sha256,
            "model": MODEL,
            "provider_invoice_usd": None,
        }

        def provider(paid_request: dict) -> dict:
            if paid_request != request:
                raise DesktopSelectionError("selection_sampler_setup_request_changed")
            return self.sampler.start(
                checkpoint_path=checkpoint_path,
                checkpoint_sha256=started["checkpoint_path_sha256"],
                config=policy, out_dir=out_dir,
                attempt_id=started["attempt_id"])

        result = session.dispatch_paid(
            attempt_id=paid_id, category="tinker",
            work={"selection_attempt": started["attempt_id"],
                  "kind": "checkpoint_sampler_setup",
                  "checkpoint_path_sha256":
                  started["checkpoint_path_sha256"]},
            request=request, reserve_usd=policy["sample_quote_usd"],
            resource_reservation={}, provider=provider)
        if (type(result) is not dict or
                result.get("attempt_id") != paid_id or
                type(result.get("result_sha256")) is not str or
                HEX64.fullmatch(result["result_sha256"]) is None or
                result.get("result", {}).get("status") != "ready" or
                result["result"].get("checkpoint_path_sha256") !=
                started["checkpoint_path_sha256"]):
            raise DesktopSelectionUncertain("selection_sampler_setup_ambiguous")
        paid_ids.append(paid_id)

    def _reserve_guest(self, *, session, started: dict,
                       package: SelectionPackage, ordinal: int,
                       phase: str, paid_ids: list[str],
                       declared_ids: list[str]) -> DesktopGuest:
        if phase not in ("actor", "reset"):
            raise DesktopSelectionError("selection_guest_phase_invalid")
        lease = (ACTOR_LEASE_SECONDS if phase == "actor" else
                 RESET_LEASE_SECONDS)
        reserve = (ACTOR_LEASE_RESERVE_USD if phase == "actor" else
                   RESET_LEASE_RESERVE_USD)
        paid_id = (started["attempt_id"] +
                   f"-e2b-{ordinal:03d}-{phase}")
        declared_ids.append(paid_id)
        request = {
            "schema": "cua-full-study-selection-e2b-desktop-lease-v1",
            "selection_attempt": started["attempt_id"],
            "cell_id": self.cell_id,
            "task_id": package.identity["task_id"],
            "package_sha256": package.identity["package_sha256"],
            "checkpoint_path_sha256": started["checkpoint_path_sha256"],
            "phase": phase, "lease_seconds": lease,
            "worker_runtime_sha256": self.runtime_sha256,
            "provider_invoice_usd": None,
        }
        guest: DesktopGuest | None = None

        def provider(paid_request: dict) -> dict:
            nonlocal guest
            if paid_request != request:
                raise DesktopSelectionError("selection_guest_lease_request_changed")
            guest = self.backend.create(phase, lease, package)
            return {"schema": "cua-full-study-selection-e2b-desktop-result-v1",
                    "status": "active", "sandbox_id": guest.sandbox_id,
                    "lease_seconds": lease, "provider_invoice_usd": None}

        try:
            paid = session.dispatch_paid(
                attempt_id=paid_id, category="e2b",
                work=request, request=request,
                reserve_usd=reserve,
                resource_reservation={
                    "e2b_sandbox_hours": str((Decimal(lease) /
                                              Decimal(3600)).quantize(
                        Decimal("0.000000001"),
                        rounding=ROUND_CEILING)),
                    "e2b_peak_concurrency": "1"},
                provider=provider)
        except Exception:
            if guest is not None:
                guest.close()
            raise DesktopSelectionUncertain("selection_e2b_create_or_ack_uncertain") from None
        if (guest is None or type(paid) is not dict or
                paid.get("attempt_id") != paid_id or
                type(paid.get("result_sha256")) is not str or
                HEX64.fullmatch(paid["result_sha256"]) is None or
                paid.get("result", {}).get("status") != "active" or
                paid["result"].get("sandbox_id") != guest.sandbox_id):
            if guest is not None:
                guest.close()
            raise DesktopSelectionUncertain("selection_e2b_result_ambiguous")
        paid_ids.append(paid_id)
        return guest

    def _sample_action(self, *, session, started: dict,
                       package: SelectionPackage, ordinal: int,
                       observation: Observation, guest: DesktopGuest,
                       policy: dict, task_dir: Path,
                       paid_ids: list[str],
                       declared_ids: list[str]) -> dict:
        if guest.current_frame_id() != observation.frame_id:
            raise DesktopSelectionError("selection_frame_stale_before_paid_sample")
        rendered = output_v066.render_for_model(observation)
        frame_sha = _sha(observation.screenshot_bytes)
        paid_id = (started["attempt_id"] +
                   f"-sample-{ordinal:03d}-{observation.step:03d}")
        declared_ids.append(paid_id)
        request = {
            "schema": "cua-full-study-selection-sampling-request-v1",
            "cell_id": self.cell_id,
            "selection_attempt": started["attempt_id"],
            "task_id": package.identity["task_id"],
            "package_sha256": package.identity["package_sha256"],
            "checkpoint_path_sha256": started["checkpoint_path_sha256"],
            "step": observation.step,
            "frame_id": observation.frame_id,
            "frame_sha256": frame_sha,
            "image_base64": base64.b64encode(
                observation.screenshot_bytes).decode(),
            "instruction": rendered["instruction"],
            "visible_text": rendered["visible_text"],
            "max_input_tokens": MAX_INPUT_TOKENS,
            "max_output_tokens": policy["max_output_tokens"],
            "seed": policy["seed"],
            "temperature": str(policy["temperature"]),
        }

        def provider(paid_request: dict) -> dict:
            if (paid_request != request or
                    _sha(base64.b64decode(
                        paid_request["image_base64"], validate=True)) !=
                    frame_sha):
                raise DesktopSelectionError("selection_paid_frame_request_changed")
            result = self.sampler.sample(
                observation=observation, ordinal=ordinal,
                step=observation.step, task_dir=task_dir)
            usage = result.get("usage") if type(result) is dict else None
            if (type(result) is not dict or
                    result.get("status") != "completed" or
                    result.get("new_dispatch") is not True or
                    result.get("reused") is True or
                    type(result.get("text")) is not str or
                    not 0 < len(result["text"].encode()) <= 65_536 or
                    type(usage) is not dict or
                    type(usage.get("input_tokens")) is not int or
                    not 0 < usage["input_tokens"] <= MAX_INPUT_TOKENS or
                    type(usage.get("output_tokens")) is not int or
                    not 0 <= usage["output_tokens"] <=
                    policy["max_output_tokens"] or
                    type(usage.get("image_tokens")) is not int or
                    not 0 < usage["image_tokens"] <=
                    usage["input_tokens"]):
                raise DesktopSelectionUncertain("selection_tinker_sample_or_usage_uncertain")
            return {"schema": "cua-native-wdi-v066-paid-qwen-sample-v1",
                    "status": "completed", "reported_model": MODEL,
                    "checkpoint_path_sha256":
                    started["checkpoint_path_sha256"],
                    "text": result["text"],
                    "usage": {**usage, "provider_billed_tokens": None},
                    "new_dispatch": True, "reused": False,
                    "provider_invoice_usd": None}

        try:
            paid = session.dispatch_paid(
                attempt_id=paid_id, category="tinker",
                work={"selection_attempt": started["attempt_id"],
                      "task_id": package.identity["task_id"],
                      "package_sha256": package.identity["package_sha256"],
                      "checkpoint_path_sha256":
                      started["checkpoint_path_sha256"],
                      "step": observation.step,
                      "frame_sha256": frame_sha},
                request=request,
                reserve_usd=policy["sample_quote_usd"],
                resource_reservation={}, provider=provider)
        except Exception:
            raise DesktopSelectionUncertain(
                "selection_tinker_paid_attempt_uncertain") from None
        result = paid.get("result") if type(paid) is dict else None
        if (type(paid) is not dict or paid.get("attempt_id") != paid_id or
                type(paid.get("result_sha256")) is not str or
                HEX64.fullmatch(paid["result_sha256"]) is None or
                type(result) is not dict or
                result.get("status") != "completed" or
                result.get("reported_model") != MODEL or
                result.get("checkpoint_path_sha256") !=
                started["checkpoint_path_sha256"]):
            raise DesktopSelectionUncertain("selection_tinker_result_ambiguous")
        paid_ids.append(paid_id)
        if guest.current_frame_id() != observation.frame_id:
            raise DesktopSelectionError("selection_frame_drift_after_paid_sample")
        try:
            action = output_v066.normalize_model_action(
                result["text"], observation,
                current_frame_id=observation.frame_id)
        except ContractError as exc:
            if guest.current_frame_id() != observation.frame_id:
                raise DesktopSelectionError(
                    "selection_frame_drift_during_action_parse") from None
            model_error = ("invalid_model_ref" if exc.code == "stale_frame" else
                           exc.code)
            if model_error not in {"invalid_action", "invalid_action_json",
                                   "invalid_model_ref"}:
                raise DesktopSelectionError(
                    "selection_action_frame_or_expiry_invalid") from None
            action = None
        else:
            model_error = None
        return {"paid_attempt_id": paid_id,
                "paid_result_sha256": paid.get("result_sha256"),
                "frame_sha256": frame_sha,
                "model_text_sha256": _sha(result["text"].encode()),
                "action": action, "model_error_code": model_error,
                "usage": result["usage"],
                "reserve_usd": policy["sample_quote_usd"]}

    def _task_episode(self, *, session, started: dict,
                      package: SelectionPackage, ordinal: int,
                      batch_dir: Path, policy: dict,
                      guest_ref: dict,
                      private_salt: str,
                      paid_ids: list[str],
                      declared_ids: list[str]) -> dict:
        identity = package.identity
        task_dir = batch_dir / "tasks" / f"task-{ordinal:03d}"
        task_dir.mkdir(mode=0o700)
        (task_dir / "frames").mkdir(mode=0o700)
        (task_dir / "artifacts").mkdir(mode=0o700)
        actor = None
        reset = None
        trace: list[dict] = []
        frame_refs: list[dict] = []
        predispatch_refs: list[dict] = []
        task_paid_ids: list[str] = []
        task_started = time.monotonic()
        actor_started = None
        outcome = None
        saved = None
        verifier = None
        suffix = Path(package.filename).suffix
        model_task = {**identity,
                      "visible_instruction": package.instruction}
        try:
            actor = self._reserve_guest(
                session=session, started=started, package=package,
                ordinal=ordinal, phase="actor", paid_ids=paid_ids,
                declared_ids=declared_ids)
            task_paid_ids.append(paid_ids[-1])
            actor.prepare(source=package.source, filename=package.filename,
                          oracle=package.oracle,
                          guest_identity=guest_ref)
            if (actor.guest_content_sha256 !=
                    guest_ref["static_content_sha256"] or
                    actor.provider_shape_attested is not True or
                    actor.fresh_profile_absent is not True or
                    type(actor.profile_sha256) is not str or
                    HEX64.fullmatch(actor.profile_sha256) is None or
                    type(actor.neutral_input) is not bytes or
                    actor.raw_input_sha256 != _sha(package.source) or
                    _semantic_input(actor.neutral_input, suffix) !=
                    _semantic_input(package.source, suffix)):
                raise DesktopSelectionError(
                    "selection_actor_guest_or_neutral_source_invalid")
            if (self.enable_live and
                    (actor.profile_sha256 !=
                     self._profiles.get(identity["task_id"], {}).get(
                         "canonical_profile_sha256") or
                     _sha(package.source) !=
                     self._profiles.get(identity["task_id"], {}).get(
                         "input_sha256"))):
                raise DesktopSelectionError(
                    "selection_task_bound_profile_reference_changed")
            effective_oracle = {
                **package.oracle,
                "input_sha256": _sha(actor.neutral_input),
            }
            initial = verify_official(
                actor.neutral_input, actor.neutral_input,
                effective_oracle, private_salt=private_salt)
            if initial.get("passed") is not False:
                raise DesktopSelectionError("selection_baseline_already_solved")
            previous = None
            memory = ""
            actor_started = time.monotonic()
            for step in range(policy["max_actions"]):
                if time.monotonic() - actor_started > policy["actor_wall_seconds"]:
                    outcome = "task_wall_budget"
                    break
                observation = actor.observe(
                    task=model_task, step=step,
                    previous=previous, memory=memory,
                    max_actions=policy["max_actions"])
                if (type(observation) is not Observation or
                        observation.task_id != identity["task_id"] or
                        observation.task_binding_sha256 !=
                        identity["package_sha256"] or
                        observation.instruction != package.instruction or
                        observation.step != step or
                        observation.limits.max_step != policy["max_actions"] or
                        len(observation.screenshot_bytes) > MAX_FRAME_BYTES):
                    raise DesktopSelectionError(
                        "selection_current_native_observation_unbound")
                frame = self._save(
                    batch_dir,
                    task_dir / "frames" / f"step-{step:03d}.png",
                    observation.screenshot_bytes,
                    limit=MAX_FRAME_BYTES)
                frame_ref = {"path": "frames/" + frame["path"],
                             "sha256": frame["sha256"]}
                frame_refs.append(frame_ref)
                intended = (started["attempt_id"] +
                            f"-sample-{ordinal:03d}-{step:03d}")
                sampled = self._sample_action(
                    session=session, started=started,
                    package=package, ordinal=ordinal,
                    observation=observation, guest=actor,
                    policy=policy, task_dir=task_dir,
                    paid_ids=paid_ids,
                    declared_ids=declared_ids)
                self._storage_check(batch_dir)
                if sampled["paid_attempt_id"] != intended:
                    raise DesktopSelectionError(
                        "selection_qwen_paid_attempt_identity_changed")
                task_paid_ids.append(intended)
                trace_row = {
                    "step": step, "frame_ref": frame_ref,
                    "paid_attempt_id": intended,
                    "paid_result_sha256": sampled["paid_result_sha256"],
                    "model_text_sha256": sampled["model_text_sha256"],
                    "usage": sampled["usage"],
                    "model_error_code": sampled["model_error_code"],
                    "action": sampled["action"],
                    "predispatch_frame_ref": None,
                }
                trace.append(trace_row)
                if sampled["action"] is None:
                    outcome = "model_invalid_action"
                    break
                if actor.current_frame_id() != observation.frame_id:
                    raise DesktopSelectionError(
                        "selection_physical_frame_changed_before_dispatch")
                predispatch = actor.predispatch_frame()
                if (type(predispatch) is not bytes or
                        qwen_v066_adapter.prior.application_frame_digest(
                            predispatch) !=
                        qwen_v066_adapter.prior.application_frame_digest(
                            observation.screenshot_bytes)):
                    raise DesktopSelectionError(
                        "selection_raw_predispatch_frame_changed")
                pre_ref = self._save(
                    batch_dir,
                    task_dir / "frames" /
                    f"predispatch-{step:03d}.png",
                    predispatch, limit=MAX_FRAME_BYTES)
                trace_row["predispatch_frame_ref"] = {
                    "path": "frames/" + pre_ref["path"],
                    "sha256": pre_ref["sha256"]}
                predispatch_refs.append(trace_row["predispatch_frame_ref"])
                actor.dispatch(sampled["action"])
                memory = sampled["action"]["memory"]
                if sampled["action"]["type"] == "finish":
                    outcome = "finished"
                    break
                previous = {"status": "applied", "code": "ok"}
            else:
                outcome = "task_action_budget"
            saved = actor.read_saved()
            verifier = verify_official(
                actor.neutral_input, saved,
                effective_oracle, private_salt=private_salt)
            if (type(verifier) is not dict or
                    verifier.get("schema") !=
                    "cua-native-wdi-saved-verifier-v2" or
                    type(verifier.get("passed")) is not bool or
                    type(verifier.get("errors")) is not list):
                raise DesktopSelectionError(
                    "selection_independent_ooxml_verifier_invalid")
            actor_neutral = actor.neutral_input
            actor_profile = actor.profile_sha256
            actor_guest_sha = actor.guest_content_sha256
            actor_id = actor.sandbox_id
            if actor.close() is not True:
                raise DesktopSelectionUncertain(
                    "selection_actor_teardown_uncertain")
            reset = self._reserve_guest(
                session=session, started=started,
                package=package, ordinal=ordinal,
                phase="reset", paid_ids=paid_ids,
                declared_ids=declared_ids)
            task_paid_ids.append(paid_ids[-1])
            if reset.sandbox_id == actor_id:
                raise DesktopSelectionError("selection_fresh_guest_reused")
            reset.prepare(source=package.source,
                          filename=package.filename,
                          oracle=package.oracle,
                          guest_identity=guest_ref)
            if (reset.guest_content_sha256 != actor_guest_sha or
                    reset.provider_shape_attested is not True or
                    reset.fresh_profile_absent is not True or
                    reset.profile_sha256 != actor_profile or
                    reset.raw_input_sha256 != _sha(package.source) or
                    type(reset.neutral_input) is not bytes or
                    _semantic_input(reset.neutral_input, suffix) !=
                    _semantic_input(actor_neutral, suffix) or
                    reset.read_saved() != reset.neutral_input):
                raise DesktopSelectionError(
                    "selection_fresh_guest_or_profile_reset_changed")
            reset_frame = reset._screenshot() if isinstance(
                reset, RealDesktopGuest) else reset.predispatch_frame()
            reset_frame_ref = self._save(
                batch_dir,
                task_dir / "frames/reset-neutral.png",
                reset_frame, limit=MAX_FRAME_BYTES)
            if reset.close() is not True:
                raise DesktopSelectionUncertain(
                    "selection_reset_teardown_uncertain")
            cleanup_ref = self._save(
                batch_dir, task_dir / "cleanup.private.json",
                _canonical({
                    "schema": "cua-native-wdi-v066-selection-cleanup-v1",
                    "actor_sandbox_id_sha256": _sha(actor_id.encode()),
                    "reset_sandbox_id_sha256":
                        _sha(reset.sandbox_id.encode()),
                    "actor_terminated": actor.killed is True,
                    "reset_terminated": reset.killed is True,
                    "provider_invoice_usd": None,
                }))
            baseline_semantic = {
                "source_sha256": _sha(package.source),
                "neutral_content": _semantic_input(actor_neutral, suffix),
                "neutral_profile_sha256": actor_profile,
                "scoped_guest_content_sha256": actor_guest_sha,
            }
            restored_semantic = {
                "source_sha256": _sha(package.source),
                "neutral_content": _semantic_input(reset.neutral_input, suffix),
                "neutral_profile_sha256": reset.profile_sha256,
                "scoped_guest_content_sha256": reset.guest_content_sha256,
            }
            if baseline_semantic != restored_semantic:
                raise DesktopSelectionError("selection_fresh_reset_semantics_differ")
            score = int(outcome == "finished" and verifier["passed"] is True)
            neutral_ref = self._save(
                batch_dir, task_dir / "artifacts" /
                ("neutral-baseline" + suffix), actor_neutral)
            saved_ref = self._save(
                batch_dir, task_dir / "artifacts" / ("saved" + suffix),
                saved)
            baseline_ref = self._save(
                batch_dir, task_dir / "artifacts/baseline.private.json",
                _canonical(baseline_semantic))
            restored_ref = self._save(
                batch_dir, task_dir / "artifacts/restored.private.json",
                _canonical(restored_semantic))
            verifier_receipt = {
                "schema": "cua-native-wdi-v066-selection-verifier-v1",
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "saved_artifact_sha256": saved_ref["sha256"],
                "fair_verifier_bundle_sha256": self.verifier_sha256,
                "fair_result": verifier,
                "model_outcome": outcome,
                "score": score,
                "independent_of_actor": True,
            }
            reset_receipt = {
                "schema": "cua-native-wdi-v066-selection-cold-reset-v1",
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "actor_sandbox_id_sha256": _sha(actor_id.encode()),
                "reset_sandbox_id_sha256": _sha(reset.sandbox_id.encode()),
                "actor_guest_content_sha256": actor_guest_sha,
                "reset_guest_content_sha256": reset.guest_content_sha256,
                "actor_profile_sha256": actor_profile,
                "reset_profile_sha256": reset.profile_sha256,
                "neutral_reset_frame_ref": {
                    "path": "frames/" + reset_frame_ref["path"],
                    "sha256": reset_frame_ref["sha256"]},
                "baseline_state_ref": {"path": "artifacts/" +
                                       baseline_ref["path"],
                                       "sha256": baseline_ref["sha256"]},
                "restored_state_ref": {"path": "artifacts/" +
                                       restored_ref["path"],
                                       "sha256": restored_ref["sha256"]},
                "fresh_environment": True,
                "state_equivalence_pass": True,
                "both_sandboxes_terminated": True,
            }
            trace_ref = self._save(
                batch_dir, task_dir / "actions.private.json",
                _canonical(trace))
            saved_state = {
                "schema": "cua-native-wdi-v066-selection-saved-state-v1",
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "source_input_sha256": _sha(package.source),
                "neutral_input_sha256": _sha(actor_neutral),
                "neutral_input_ref": {"path": "artifacts/" +
                                      neutral_ref["path"],
                                      "sha256": neutral_ref["sha256"]},
                "saved_artifact_ref": {"path": "artifacts/" +
                                       saved_ref["path"],
                                       "sha256": saved_ref["sha256"]},
                "native_save_readback": True,
                "actor_sandbox_terminated": True,
            }
            state_ref = self._save(
                batch_dir, task_dir / "saved-state.private.json",
                _canonical(saved_state))
            verify_ref = self._save(
                batch_dir, task_dir / "verifier.private.json",
                _canonical(verifier_receipt))
            reset_ref = self._save(
                batch_dir, task_dir / "reset.private.json",
                _canonical(reset_receipt))
            paid_task_ids = list(task_paid_ids)
            if (len(paid_task_ids) < 3 or
                    len([x for x in paid_task_ids if "-sample-" in x]) < 1 or
                    len({x for x in paid_task_ids if "-e2b-" in x}) != 2 or
                    len(paid_task_ids) != len(set(paid_task_ids))):
                raise DesktopSelectionError(
                    "selection_task_paid_sample_or_dual_guest_missing")
            task_receipt = {
                "schema": TASK_SCHEMA,
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "source_inventory_sha256": package.source_inventory_sha256,
                "saved_state_sha256": state_ref["sha256"],
                "verifier_receipt_sha256": verify_ref["sha256"],
                "reset_receipt_sha256": reset_ref["sha256"],
                "action_trace_ref": {"path": trace_ref["path"],
                                     "sha256": trace_ref["sha256"]},
                "frame_refs": frame_refs,
                "predispatch_frame_refs": predispatch_refs,
                "paid_attempt_ids": paid_task_ids,
                "cleanup_ref": cleanup_ref,
                "sample_count": len([x for x in paid_task_ids
                                     if "-sample-" in x]),
                "score": score,
                "model_outcome": outcome,
                "actual_provider_billed_usd": None,
            }
            task_ref = self._save(
                batch_dir, task_dir / "task.private.json",
                _canonical(task_receipt))
            return {
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "score": score,
                "saved_state_sha256": state_ref["sha256"],
                "verifier_receipt_sha256": verify_ref["sha256"],
                "reset_receipt_sha256": reset_ref["sha256"],
                "task_receipt_sha256": task_ref["sha256"],
                "paid_attempt_ids": paid_task_ids,
                "sample_count": task_receipt["sample_count"],
                "model_outcome": outcome,
                "elapsed_seconds": round(time.monotonic() - task_started, 3),
            }
        except BaseException as exc:
            failure = {
                "schema": "cua-native-wdi-v066-selection-task-invalid-v1",
                "task_id": identity["task_id"],
                "package_sha256": identity["package_sha256"],
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "exception_type": type(exc).__name__,
                "observed_frame_refs": frame_refs,
                "attempted_paid_attempt_ids": declared_ids,
                "completed_paid_attempt_ids": paid_ids,
                "automatic_replay_authorized": False,
                "model_score_inferred": False,
            }
            if not (task_dir / "task-invalid.private.json").exists():
                try:
                    self._save(batch_dir,
                               task_dir / "task-invalid.private.json",
                               _canonical(failure))
                except Exception:
                    pass
            raise
        finally:
            for guest in (actor, reset):
                if guest is not None and not guest.killed:
                    guest.close()
            if not (task_dir / "task.private.json").exists() and not (
                    task_dir / "cleanup-partial.private.json").exists():
                try:
                    self._save(
                        batch_dir,
                        task_dir / "cleanup-partial.private.json",
                        _canonical({
                            "schema":
                                "cua-native-wdi-v066-selection-partial-cleanup-v1",
                            "actor_sandbox_id_sha256": (
                                _sha(actor.sandbox_id.encode())
                                if actor is not None else None),
                            "reset_sandbox_id_sha256": (
                                _sha(reset.sandbox_id.encode())
                                if reset is not None else None),
                            "actor_terminated": (actor.killed if actor else None),
                            "reset_terminated": (reset.killed if reset else None),
                            "automatic_replay_authorized": False,
                        }))
                except Exception:
                    pass

    def _audit_task(self, *, batch_dir: Path,
                    package: SelectionPackage,
                    ordinal: int, row: dict,
                    private_salt: str) -> None:
        """Re-open raw files and rerun the fair scorer before next task."""
        task_dir = batch_dir / "tasks" / f"task-{ordinal:03d}"
        task = json.loads(_read_bound(
            task_dir / "task.private.json",
            row["task_receipt_sha256"]))
        if (task.get("schema") != TASK_SCHEMA or
                task.get("task_id") != package.identity["task_id"] or
                task.get("package_sha256") !=
                package.identity["package_sha256"] or
                task.get("score") != row["score"] or
                task.get("paid_attempt_ids") != row["paid_attempt_ids"] or
                task.get("saved_state_sha256") !=
                row["saved_state_sha256"] or
                task.get("verifier_receipt_sha256") !=
                row["verifier_receipt_sha256"] or
                task.get("reset_receipt_sha256") !=
                row["reset_receipt_sha256"]):
            raise DesktopSelectionError("selection_task_receipt_binding_changed")
        trace = json.loads(_read_bound(
            task_dir / "actions.private.json",
            task["action_trace_ref"]["sha256"]))
        if (type(trace) is not list or len(trace) != len(task["frame_refs"]) or
                len(trace) != task["sample_count"] or
                len(task["predispatch_frame_refs"]) !=
                sum(item["predispatch_frame_ref"] is not None
                    for item in trace)):
            raise DesktopSelectionError("selection_frame_trace_or_sample_count_changed")
        for step, item in enumerate(trace):
            observation_ref = task["frame_refs"][step]
            if (item["step"] != step or
                    item["frame_ref"] != observation_ref or
                    item["paid_attempt_id"] not in task["paid_attempt_ids"]):
                raise DesktopSelectionError("selection_frame_paid_trace_changed")
            observed = _read_bound(
                task_dir / observation_ref["path"],
                observation_ref["sha256"])
            pre_ref = item["predispatch_frame_ref"]
            if pre_ref is not None:
                pre = _read_bound(task_dir / pre_ref["path"],
                                  pre_ref["sha256"])
                if (qwen_v066_adapter.prior.application_frame_digest(observed) !=
                        qwen_v066_adapter.prior.application_frame_digest(pre)):
                    raise DesktopSelectionError(
                        "selection_raw_predispatch_frame_changed")
        saved_state = json.loads(_read_bound(
            task_dir / "saved-state.private.json",
            row["saved_state_sha256"]))
        neutral_ref = saved_state["neutral_input_ref"]
        saved_ref = saved_state["saved_artifact_ref"]
        neutral = _read_bound(task_dir / neutral_ref["path"],
                              neutral_ref["sha256"])
        saved = _read_bound(task_dir / saved_ref["path"],
                            saved_ref["sha256"])
        effective_oracle = {**package.oracle,
                            "input_sha256": _sha(neutral)}
        independent = verify_official(
            neutral, saved, effective_oracle,
            private_salt=private_salt)
        verification = json.loads(_read_bound(
            task_dir / "verifier.private.json",
            row["verifier_receipt_sha256"]))
        if (verification.get("schema") !=
                "cua-native-wdi-v066-selection-verifier-v1" or
                verification.get("fair_result") != independent or
                verification.get("fair_verifier_bundle_sha256") !=
                self.verifier_sha256 or
                verification.get("score") !=
                int(task["model_outcome"] == "finished" and
                    independent["passed"] is True) or
                verification.get("score") != row["score"]):
            raise DesktopSelectionError("selection_independent_fair_score_changed")
        reset = json.loads(_read_bound(
            task_dir / "reset.private.json",
            row["reset_receipt_sha256"]))
        baseline_ref = reset["baseline_state_ref"]
        restored_ref = reset["restored_state_ref"]
        baseline = _read_bound(task_dir / baseline_ref["path"],
                               baseline_ref["sha256"])
        restored = _read_bound(task_dir / restored_ref["path"],
                               restored_ref["sha256"])
        frame = reset["neutral_reset_frame_ref"]
        _read_bound(task_dir / frame["path"], frame["sha256"])
        cleanup = json.loads(_read_bound(
            task_dir / task["cleanup_ref"]["path"],
            task["cleanup_ref"]["sha256"]))
        if (reset.get("fresh_environment") is not True or
                reset.get("state_equivalence_pass") is not True or
                reset.get("both_sandboxes_terminated") is not True or
                reset["actor_sandbox_id_sha256"] ==
                reset["reset_sandbox_id_sha256"] or
                reset["actor_guest_content_sha256"] !=
                reset["reset_guest_content_sha256"] or
                reset["actor_profile_sha256"] !=
                reset["reset_profile_sha256"] or
                cleanup.get("actor_terminated") is not True or
                cleanup.get("reset_terminated") is not True or
                cleanup.get("actor_sandbox_id_sha256") !=
                reset["actor_sandbox_id_sha256"] or
                cleanup.get("reset_sandbox_id_sha256") !=
                reset["reset_sandbox_id_sha256"] or
                baseline != restored):
            raise DesktopSelectionError("selection_fresh_reset_evidence_changed")

    def run_selection(self, *, session, started: dict,
                      checkpoint_path: str, out_dir: Path) -> dict:
        """Return a result only after 20 per-ID and paid-coverage audits."""
        cell, _start = self._require_frozen(session, started)
        out_dir = Path(out_dir).absolute()
        self._check_output(session, out_dir)
        selected_checkpoint = self._resolve_checkpoint(
            session, started["checkpoint_path_sha256"])
        if checkpoint_path != selected_checkpoint:
            raise DesktopSelectionError("selection_checkpoint_path_changed")
        training, policy = self._policy(session, cell)
        policy["sample_quote_usd"] = _quote_sample(
            training, policy["max_output_tokens"])
        if _money(policy["sample_quote_usd"]) <= 0:
            raise DesktopSelectionError("selection_tinker_quote_missing")
        packages = _load_selection_packages(
            self.candidate_root, self.private_map,
            started["selection_tasks"],
            self.expected_inventory_sha256)
        guest_raw = self.guest_identity_public.read_bytes()
        guest_ref = json.loads(guest_raw)
        if (guest_ref.get("schema") !=
                "cua-native-wdi-guest-content-identity-public-v1" or
                guest_ref.get("scoped_guest_content_identity_passed") is not True or
                guest_ref.get("provider_shape") !=
                {"vcpu": 8, "memory_mb": 8192}):
            raise DesktopSelectionError("selection_guest_content_reference_invalid")
        map_raw = self.private_map.read_bytes()
        private_salt = json.loads(map_raw).get("variant_salt")
        if type(private_salt) is not str or len(private_salt) < 32:
            raise DesktopSelectionError("selection_private_fair_salt_missing")
        out_dir.mkdir(mode=0o700)
        (out_dir / "tasks").mkdir(mode=0o700)
        self._evidence_bytes = 0
        paid_ids: list[str] = []
        declared_ids: list[str] = []
        rows: list[dict] = []
        current_stage = "tinker_setup"
        sampler_open = False
        batch_started = time.monotonic()
        try:
            self._reserve_sampler_setup(
                session=session, started=started,
                checkpoint_path=checkpoint_path,
                policy=policy, out_dir=out_dir,
                paid_ids=paid_ids, declared_ids=declared_ids)
            sampler_open = True
            for ordinal, package in enumerate(packages, 1):
                if time.monotonic() - batch_started > MAX_BATCH_WALL_SECONDS:
                    raise DesktopSelectionError("selection_batch_wall_cap_exhausted")
                current_stage = "task" + str(ordinal)
                row = self._task_episode(
                    session=session, started=started,
                    package=package, ordinal=ordinal,
                    batch_dir=out_dir, policy=policy,
                    guest_ref=guest_ref, private_salt=private_salt,
                    paid_ids=paid_ids, declared_ids=declared_ids)
                if row["elapsed_seconds"] > MAX_TASK_WALL_SECONDS:
                    raise DesktopSelectionError("selection_task_wall_cap_exhausted")
                self._audit_task(
                    batch_dir=out_dir, package=package,
                    ordinal=ordinal, row=row,
                    private_salt=private_salt)
                self._storage_check(out_dir)
                rows.append(row)
            if len(rows) != MAX_TASKS or len(paid_ids) != len(set(paid_ids)):
                raise DesktopSelectionError("selection_twenty_task_paid_coverage_missing")
            self._storage_check(out_dir)
            current_stage = "sampler_close"
            sampler_open = False
            self.sampler.close(success=True)
            current_stage = "paid_coverage"
            coverage = session._selection_paid_coverage(
                attempt_id=started["attempt_id"],
                checkpoint_sha256=started["checkpoint_path_sha256"],
                paid_attempt_ids=paid_ids)
            if (coverage.get("schema") != paid_coverage.SCHEMA or
                    coverage.get("task_count") != MAX_TASKS or
                    coverage.get("all_task_ids_have_sample_and_environment")
                    is not True or
                    coverage.get("sample_paid_attempt_count", 0) < MAX_TASKS or
                    coverage.get("environment_paid_attempt_count", 0) <
                    2 * MAX_TASKS or
                    coverage.get("total_paid_attempt_count") != len(paid_ids)):
                raise DesktopSelectionError("selection_paid_coverage_audit_failed")
            coverage_ref = self._save(
                out_dir, out_dir / "paid-coverage.private.json",
                _canonical(coverage))
            task_ledger = {
                "schema": LEDGER_SCHEMA,
                "cell_id": self.cell_id,
                "selection_attempt": started["attempt_id"],
                "checkpoint_sha256": started["checkpoint_path_sha256"],
                "selection_identities_sha256":
                    started["selection_identities_sha256"],
                "source_inventory_sha256": self.expected_inventory_sha256,
                "guest_identity_public_sha256":
                    self.expected_guest_identity_sha256,
                "profile_private_manifest_sha256":
                    self.expected_profile_manifest_sha256,
                "runtime_sha256": self.runtime_sha256,
                "verifier_sha256": self.verifier_sha256,
                "adapter_sha256": self.adapter_sha256,
                "paid_attempt_ids": paid_ids,
                "paid_coverage_ref": coverage_ref,
                "tasks": [{
                    "task_id": row["task_id"],
                    "package_sha256": row["package_sha256"],
                    "checkpoint_sha256":
                        started["checkpoint_path_sha256"],
                    "saved_state_sha256": row["saved_state_sha256"],
                    "verifier_receipt_sha256":
                        row["verifier_receipt_sha256"],
                    "reset_receipt_sha256": row["reset_receipt_sha256"],
                    "task_receipt_sha256": row["task_receipt_sha256"],
                    "qwen_paid_attempt_ids": [attempt for attempt in
                                              row["paid_attempt_ids"] if
                                              "-sample-" in attempt],
                    "e2b_paid_attempt_ids": [attempt for attempt in
                                            row["paid_attempt_ids"] if
                                            "-e2b-" in attempt],
                } for row in rows],
            }
            if ([row["task_id"] for row in task_ledger["tasks"]] !=
                    [row["task_id"] for row in started["selection_tasks"]] or
                    any(len(row["qwen_paid_attempt_ids"]) < 1 or
                        len(row["e2b_paid_attempt_ids"]) != 2
                        for row in task_ledger["tasks"])):
                raise DesktopSelectionError("selection_task_paid_ledger_incomplete")
            ledger_ref = self._save(
                out_dir, out_dir / "task-ledger.private.json",
                _canonical(task_ledger))
            result = {
                "schema": RESULT_SCHEMA,
                "cell_id": self.cell_id,
                "checkpoint_sha256":
                    started["checkpoint_path_sha256"],
                "evaluator_isolated": True,
                "tasks": [{key: row[key] for key in (
                    "task_id", "package_sha256", "score",
                    "saved_state_sha256", "verifier_receipt_sha256",
                    "reset_receipt_sha256")}
                    for row in rows],
            }
            if session._selection_result(
                    result, checkpoint_sha256=
                    started["checkpoint_path_sha256"]) != {
                        row["task_id"]: row["score"] for row in rows}:
                raise DesktopSelectionError("selection_campaign_score_schema_mismatch")
            result_ref = self._save(
                out_dir, out_dir / "selection-result.private.json",
                _canonical(result))
            summary = {"schema": SCHEMA,
                       "status": "scored_after_paid_coverage",
                       "selection_attempt": started["attempt_id"],
                       "checkpoint_sha256":
                       started["checkpoint_path_sha256"],
                       "task_count": MAX_TASKS,
                       "paid_coverage_sha256": coverage_ref["sha256"],
                       "task_ledger_sha256": ledger_ref["sha256"],
                       "result_sha256": result_ref["sha256"],
                       "paid_attempt_ids": paid_ids,
                       "raw_private_evidence_bytes": self._evidence_bytes,
                       "provider_invoice_usd": None,
                       "official_final_model_attempts": 0}
            summary_ref = self._save(
                out_dir, out_dir / "batch.private.json",
                _canonical(summary))
            return {"status": "scored", "result": result,
                    "result_sha256": result_ref["sha256"],
                    "paid_attempt_ids": paid_ids,
                    "task_ledger_path": str(out_dir /
                                            "task-ledger.private.json"),
                    "task_ledger_sha256": ledger_ref["sha256"],
                    "paid_coverage_path": str(out_dir /
                                              "paid-coverage.private.json"),
                    "paid_coverage_sha256": coverage_ref["sha256"],
                    "batch_receipt_path": str(out_dir /
                                              "batch.private.json"),
                    "batch_receipt_sha256": summary_ref["sha256"],
                    "provider_invoice_usd": None}
        except Exception as exc:
            if sampler_open:
                try:
                    self.sampler.close(success=False)
                except Exception:
                    pass
            failure = {"schema": "cua-native-wdi-v066-selection-invalid-v1",
                       "selection_attempt": started["attempt_id"],
                       "failure_type": ("provider" if isinstance(
                           exc, DesktopSelectionUncertain) else
                           "environment"),
                       "failure_stage": current_stage,
                       "exception_type": type(exc).__name__,
                       "completed_task_count": len(rows),
                       "declared_paid_attempt_ids": declared_ids,
                       "completed_paid_attempt_ids": paid_ids,
                       "automatic_paid_replay_authorized": False,
                       "model_score_inferred_for_failed_task": False,
                       "provider_invoice_usd": None}
            invalid_ref = self._save(
                out_dir, out_dir / "invalid.private.json",
                _canonical(failure))
            return {"status": "invalid",
                    "failure_type": failure["failure_type"],
                    "evaluator_receipt_sha256": invalid_ref["sha256"],
                    "invalid_receipt_path": str(out_dir /
                                                "invalid.private.json"),
                    "paid_attempt_ids": paid_ids}
