"""Original LibreOffice Desktop train-only GUI teacher episode worker.

The full-study adapter owns all paid teacher and E2B reservations. This worker
opens only one frozen WDI *train* package, samples the teacher from actual
1280x800 screenshots, dispatches only v0.6.6 GUI actions, independently reads
the saved OOXML, and checks reset in a distinct E2B guest. An injected fake
backend is allowed only for offline tests and cannot enable live dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import time
from typing import Callable

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import Observation
from cursibench.scale_action_contract_v066 import (
    ACTION_PROFILE_VERSION, validate_action,
)
from cursibench.scale_final_v06 import validate_splits

from . import admit, profile_canonical, qwen_v066_adapter, runtime_fingerprint_probe
from .gui_control_shell import wait_for_document_ready
from .official_saved_verifier import verify_official
from .official_scorer_freeze import scorer_bundle
from .source import EXPECTED_SHA256
from .v066_final_freeze import digest, validate_ratification
from .verify import (docx_content, pptx_layout, pptx_shape_structure,
                     pptx_slide_shapes, xlsx_cells, formula_key)


ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MAX_ACTIONS = 90
LEASE_SECONDS = 600
# Ceiling includes both sequential server leases; the shared campaign account
# must reserve each lease separately at its own frozen allocated hourly rate.
E2B_RESERVE_USD_PER_LEASE = "0.166666667"
EPISODE_WALL_SECONDS = 1_350
MAX_EPISODE_PRIVATE_BYTES = 96 * 1024 * 1024
MIN_HOST_FREE_BYTES = 8 * 1024 * 1024 * 1024
SOURCE_FILES = (
    "native_desktop_factory/teacher_episode_worker_v066.py",
    "native_desktop_factory/admit.py",
    "native_desktop_factory/factory.py",
    "native_desktop_factory/factory_v2.py",
    "native_desktop_factory/source.py",
    "native_desktop_factory/gui_control_shell.py",
    "native_desktop_factory/qwen_v064_adapter.py",
    "native_desktop_factory/qwen_v066_adapter.py",
    "native_desktop_factory/runtime_fingerprint_probe.py",
    "native_desktop_factory/profile_canonical.py",
    "native_desktop_factory/v066_final_freeze.py",
    "native_desktop_factory/verify.py",
    "native_desktop_factory/official_scorer_freeze.py",
    "native_desktop_factory/official_saved_verifier.py",
    "native_desktop_factory/target_text_semantics.py",
    "native_desktop_factory/formula_semantics.py",
)


class DesktopEpisodeError(RuntimeError):
    """Fixed failure code: never format task gold or provider response text."""


def _canonical(value: object) -> bytes:
    return teacher._canonical(value)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def runtime_sha256() -> str:
    hashes = {relative: _sha((ROOT / relative).read_bytes())
              for relative in SOURCE_FILES}
    return _sha(_canonical(hashes))


def verifier_sha256() -> str:
    return scorer_bundle()[0]


def adapter_sha256() -> str:
    return _sha(Path(qwen_v066_adapter.__file__).read_bytes())


def _private(path: Path, *, directory: bool) -> bool:
    return (not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            path.stat().st_mode & 0o077 == 0)


def _write_new(path: Path, raw: bytes, *, maximum: int = 20_000_000) -> dict:
    if (not raw or len(raw) > maximum or path.exists() or path.is_symlink()
            or not _private(path.parent, directory=True)):
        raise DesktopEpisodeError("desktop_private_episode_path_unsafe")
    episode = (path.parent.parent if path.parent.name in {"frames", "artifacts"}
               else path.parent)
    used = sum(item.stat().st_size for item in episode.rglob("*")
               if item.is_file())
    if (used + len(raw) > MAX_EPISODE_PRIVATE_BYTES or
            shutil.disk_usage(episode).free - len(raw) < MIN_HOST_FREE_BYTES):
        raise DesktopEpisodeError("desktop_episode_evidence_or_host_space_exhausted")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": path.name, "sha256": _sha(raw)}


def _artifact(out_dir: Path, name: str, raw: bytes) -> dict:
    ref = _write_new(out_dir / "artifacts" / name, raw)
    return {"path": "artifacts/" + name, "sha256": ref["sha256"]}


def _read_ref(out_dir: Path, reference: dict) -> bytes:
    if (type(reference) is not dict or
            set(reference) != {"path", "sha256"} or
            type(reference["path"]) is not str or
            Path(reference["path"]).is_absolute() or
            ".." in Path(reference["path"]).parts):
        raise DesktopEpisodeError("desktop_private_evidence_reference_invalid")
    path = (out_dir / reference["path"]).resolve()
    if (not path.is_relative_to(out_dir.resolve()) or
            not _private(path, directory=False)):
        raise DesktopEpisodeError("desktop_private_evidence_reference_missing")
    raw = path.read_bytes()
    if _sha(raw) != reference["sha256"]:
        raise DesktopEpisodeError("desktop_private_evidence_hash_changed")
    return raw


def audit_episode_private(out_dir: Path) -> dict:
    """Independently re-open both raw frame streams before admission."""
    out_dir = Path(out_dir).resolve()
    receipt_path = out_dir / "episode.private.json"
    if not _private(receipt_path, directory=False):
        raise DesktopEpisodeError("desktop_episode_receipt_missing")
    receipt = json.loads(receipt_path.read_bytes())
    state = json.loads(_read_ref(out_dir, receipt["saved_state_ref"]))
    evidence = json.loads(_read_ref(out_dir, state["frame_evidence_ref"]))
    observations = receipt["frame_refs"]
    predispatch = evidence["predispatch_frame_refs"]
    if (receipt.get("split") != "train" or
            len(observations) != len(predispatch) or
            len(observations) != len(receipt["teacher_result_sha256s"]) or
            len(evidence["guest_sandbox_id_sha256s"]) != 2 or
            len(set(evidence["guest_sandbox_id_sha256s"])) != 2 or
            evidence.get("both_provider_shapes_attested") is not True or
            evidence.get("both_profiles_absent_before_neutral_open") is not True or
            type(evidence.get("neutral_profile_sha256")) is not str or
            HEX64.fullmatch(evidence["neutral_profile_sha256"]) is None or
            type(evidence.get("scoped_guest_content_sha256")) is not str or
            HEX64.fullmatch(evidence["scoped_guest_content_sha256"]) is None):
        raise DesktopEpisodeError("desktop_raw_frame_or_fresh_guest_count_invalid")
    for step, (observed_ref, pre_ref) in enumerate(
            zip(observations, predispatch)):
        if (observed_ref.get("path") != f"frames/step-{step:03d}.png" or
                pre_ref.get("path") != f"frames/predispatch-{step:03d}.png"):
            raise DesktopEpisodeError("desktop_raw_frame_order_invalid")
        observed = _read_ref(out_dir, observed_ref)
        before_action = _read_ref(out_dir, pre_ref)
        if (qwen_v066_adapter.prior.application_frame_digest(observed) !=
                qwen_v066_adapter.prior.application_frame_digest(before_action)):
            raise DesktopEpisodeError("desktop_predispatch_application_frame_changed")
    return {"raw_observation_frames": len(observations),
            "raw_predispatch_frames": len(predispatch),
            "distinct_guest_sandboxes": 2}


def _validate_task(task: object) -> dict:
    if (type(task) is not dict or
            set(task) != {"task_id", "package_sha256", "visible_instruction"} or
            type(task["task_id"]) is not str or
            TASK_ID.fullmatch(task["task_id"]) is None or
            type(task["package_sha256"]) is not str or
            HEX64.fullmatch(task["package_sha256"]) is None or
            type(task["visible_instruction"]) is not str or
            not 1 <= len(task["visible_instruction"].encode()) <= 16_384):
        raise DesktopEpisodeError("desktop_train_task_binding_invalid")
    return dict(task)


def _semantic_input(raw: bytes, suffix: str) -> dict:
    if suffix == ".xlsx":
        # LibreOffice may recalculate a formula cache during the trusted
        # neutral save. Preserve the formula itself and every source constant;
        # a cache is evaluator output, not an independent WDI observation.
        normalized = {}
        for sheet, cells in xlsx_cells(raw).items():
            normalized[sheet] = {}
            for address, cell in cells.items():
                formula = cell["formula"]
                if formula is not None:
                    normalized[sheet][address] = {"formula": formula_key(formula)}
                    continue
                value = cell["value"]
                if value is not None:
                    try:
                        value = str(Decimal(value).normalize())
                    except (InvalidOperation, TypeError, ValueError):
                        pass
                normalized[sheet][address] = {"value": value}
        return {"kind": "Calc", "cells": normalized}
    if suffix == ".pptx":
        return {"kind": "Impress", "shapes": pptx_slide_shapes(raw),
                "drawable_structure": pptx_shape_structure(raw)}
    if suffix == ".docx":
        return {"kind": "Writer", "content": docx_content(raw)}
    raise DesktopEpisodeError("desktop_train_artifact_type_invalid")


def _impress_geometry_valid(raw: bytes) -> bool:
    canvas, slides = pptx_layout(raw)
    return bool(slides) and all(
        0 <= x < canvas[0] and 0 <= y < canvas[1] and
        0 < width <= canvas[0] and 0 < height <= canvas[1] and
        x + width <= canvas[0] and y + height <= canvas[1]
        for slide in slides for x, y, width, height in slide)


def _package(candidate_root: Path, task: dict) -> tuple[dict, bytes, dict, str]:
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    rows = inventory.get("tasks")
    if (inventory.get("schema") != "cua-native-wdi-candidate-inventory-v1"
            or inventory.get("design_revision") != "v2-distinct-structures"
            or inventory.get("source_sha256") != EXPECTED_SHA256
            or type(rows) is not list or len(rows) != 140
            or sum(row.get("split") == "train" for row in rows) != 20
            or sum(row.get("split") == "selection" for row in rows) != 20
            or sum(row.get("split") == "final_candidate" for row in rows) != 100):
        raise DesktopEpisodeError("desktop_train_inventory_not_frozen")
    try:
        task_sets = {name: [] for name in ("train", "selection", "official")}
        for row in rows:
            split = ("official" if row["split"] == "final_candidate"
                     else row["split"])
            task_sets[split].append({key: row[key] for key in (
                "task_id", "package_sha256", "source_groups",
                "template_group", "instance_group")})
        if len(validate_splits(task_sets)) != 100:
            raise ValueError("Incomplete split")
    except (ValueError, KeyError, TypeError):
        raise DesktopEpisodeError(
            "desktop_train_selection_final_groups_overlap") from None
    matches = [row for row in rows if row.get("task_id") == task["task_id"]]
    if (len(matches) != 1 or matches[0].get("split") != "train"
            or matches[0].get("package_sha256") != task["package_sha256"]):
        raise DesktopEpisodeError("desktop_source_not_train_only")
    row = matches[0]
    try:
        directory, baseline, oracle = admit._package(candidate_root, row)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise DesktopEpisodeError("desktop_train_package_bytes_changed") from None
    files = [*directory.glob("*.xlsx"), *directory.glob("*.pptx"),
             *directory.glob("*.docx")]
    if (len(files) != 1 or oracle.get("split") != "train"
            or oracle.get("source_sha256") != EXPECTED_SHA256
            or (directory / "actor_task.txt").read_text() !=
                task["visible_instruction"]):
        raise DesktopEpisodeError("desktop_train_package_not_bound")
    return row, baseline, oracle, files[0].name


@dataclass
class DesktopGuest:
    """Narrow GUI/session interface implemented by real and fake guests."""

    sandbox_id: str
    guest_content_sha256: str | None = None
    profile_sha256: str | None = None
    neutral_input: bytes | None = None
    raw_input_sha256: str | None = None
    provider_shape_attested: bool = False
    fresh_profile_absent: bool = False
    killed: bool = False
    _latest: Observation | None = None
    _last_screenshot: bytes | None = None

    def prepare(self, *, source: bytes, filename: str, oracle: dict,
                guest_identity: dict) -> None:
        raise NotImplementedError

    def observe(self, *, task: dict, step: int, previous: dict | None,
                memory: str) -> Observation:
        raise NotImplementedError

    def current_frame_id(self) -> str:
        raise NotImplementedError

    def predispatch_frame(self) -> bytes:
        raise NotImplementedError

    def dispatch(self, action: dict) -> None:
        raise NotImplementedError

    def read_saved(self) -> bytes:
        raise NotImplementedError

    def close(self) -> bool:
        raise NotImplementedError


class RealDesktopGuest(DesktopGuest):
    def __init__(self, sandbox, *, phase: str):
        super().__init__(sandbox_id=sandbox.sandbox_id)
        self.sandbox = sandbox
        self.phase = phase
        self.remote = None

    def _screenshot(self) -> bytes:
        self._last_screenshot = bytes(self.sandbox.screenshot())
        return self._last_screenshot

    def prepare(self, *, source: bytes, filename: str, oracle: dict,
                guest_identity: dict) -> None:
        info = self.sandbox.get_info(request_timeout=12)
        if (info.template_id != guest_identity["provider_template_id"] or
                info.envd_version != guest_identity["provider_envd_version"] or
                info.cpu_count != guest_identity["provider_shape"]["vcpu"] or
                info.memory_mb != guest_identity["provider_shape"]["memory_mb"]):
            raise DesktopEpisodeError("desktop_guest_provider_shape_drift")
        self.provider_shape_attested = True
        probe = runtime_fingerprint_probe.GUEST_CONTENT_PROBE
        self.sandbox.files.write("/tmp/native-guest-content-probe-teacher.py",
                                 probe.encode())
        result = self.sandbox.commands.run(
            "sudo -n python3 /tmp/native-guest-content-probe-teacher.py",
            timeout=450, request_timeout=480)
        if result.exit_code != 0:
            raise DesktopEpisodeError("desktop_guest_content_probe_failed")
        guest = json.loads(result.stdout)
        if (guest.get("content_tree_sha256") !=
                guest_identity["static_content_sha256"] or
                guest.get("counts") != guest_identity["static_content_counts"] or
                guest.get("kernel") != guest_identity["kernel_identity"] or
                guest.get("excluded_paths") !=
                guest_identity["static_content_excluded_paths"]):
            raise DesktopEpisodeError("desktop_guest_content_drift")
        self.guest_content_sha256 = guest["content_tree_sha256"]
        absent = self.sandbox.commands.run(
            "test ! -e /home/user/.config/libreoffice/4/user")
        if absent.exit_code != 0:
            raise DesktopEpisodeError("desktop_guest_profile_not_fresh")
        self.fresh_profile_absent = True
        self.remote = "/home/user/" + filename
        self.sandbox.files.write(self.remote, source)
        if bytes(self.sandbox.files.read(self.remote, format="bytes")) != source:
            raise DesktopEpisodeError("desktop_staged_train_input_changed")
        self.raw_input_sha256 = _sha(source)
        self.sandbox.open(self.remote)
        wait_for_document_ready(self.sandbox, filename)
        time.sleep(7)
        self.sandbox.press("esc")
        time.sleep(1)
        # Trusted normalization runs before any teacher observation. It edits
        # no target and is checked against independent OOXML semantic content.
        self.sandbox.press(["ctrl", "s"])
        time.sleep(2)
        title = self.sandbox.commands.run(
            "xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()
        if title == "Confirm File Format":
            self.sandbox.left_click(790, 519)
            time.sleep(2)
        neutral = bytes(self.sandbox.files.read(self.remote, format="bytes"))
        suffix = Path(filename).suffix
        if suffix == ".pptx" and neutral == source:
            raise DesktopEpisodeError("desktop_impress_native_normalization_missing")
        if suffix == ".pptx" and not _impress_geometry_valid(neutral):
            raise DesktopEpisodeError("desktop_impress_native_geometry_invalid")
        if _semantic_input(neutral, suffix) != _semantic_input(source, suffix):
            raise DesktopEpisodeError("desktop_neutral_save_changed_source_semantics")
        self.neutral_input = neutral
        self.sandbox.files.write("/tmp/native-profile-file-probe-teacher.py",
                                 runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())

        def profile() -> str:
            run = self.sandbox.commands.run(
                "python3 /tmp/native-profile-file-probe-teacher.py")
            if run.exit_code != 0:
                raise DesktopEpisodeError("desktop_profile_probe_failed")
            registry = bytes(self.sandbox.files.read(
                "/home/user/.config/libreoffice/4/user/registrymodifications.xcu",
                format="bytes"))
            return profile_canonical.canonical_profile_tree(
                json.loads(run.stdout), registry)

        first = profile()
        time.sleep(1)
        second = profile()
        if first != second:
            raise DesktopEpisodeError("desktop_neutral_profile_unstable")
        self.profile_sha256 = first

    def observe(self, *, task: dict, step: int, previous: dict | None,
                memory: str) -> Observation:
        class _Camera:
            def __init__(self, guest):
                self.guest = guest
            def screenshot(self):
                return self.guest._screenshot()
        frame = qwen_v066_adapter.observe(
            _Camera(self), task_id=task["task_id"],
            task_binding_sha256=task["package_sha256"],
            instruction=task["visible_instruction"], step=step,
            previous_action_result=previous, memory=memory,
            max_actions=MAX_ACTIONS)
        self._latest = frame
        return frame

    def current_frame_id(self) -> str:
        frame = self._latest
        if frame is None or time.monotonic() > frame.expires_at:
            return "stale"
        try:
            current = self._screenshot()
            if (qwen_v066_adapter.prior.application_frame_digest(current) ==
                    qwen_v066_adapter.prior.application_frame_digest(
                        frame.screenshot_bytes)):
                return frame.frame_id
        except Exception:
            return "stale"
        return "stale"

    def predispatch_frame(self) -> bytes:
        if self._last_screenshot is None:
            raise DesktopEpisodeError("desktop_predispatch_frame_missing")
        return self._last_screenshot

    def dispatch(self, action: dict) -> None:
        if self._latest is None:
            raise DesktopEpisodeError("desktop_current_frame_missing_before_dispatch")
        checked = validate_action(
            action, self._latest, current_frame_id=self._latest.frame_id)
        if checked != action or qwen_v066_adapter.dispatch(
                self.sandbox, checked) != action["type"]:
            raise DesktopEpisodeError("desktop_gui_action_not_applied")

    def read_saved(self) -> bytes:
        if self.remote is None:
            raise DesktopEpisodeError("desktop_remote_train_document_missing")
        return bytes(self.sandbox.files.read(self.remote, format="bytes"))

    def close(self) -> bool:
        if self.killed:
            return True
        try:
            killed = bool(self.sandbox.kill())
            running = bool(self.sandbox.is_running(request_timeout=12))
        except Exception:
            return False
        self.killed = killed and not running
        return self.killed


class RealDesktopTrainBackend:
    """Only this backend has SDK access; provider callback reserves first."""

    is_fake = False

    def create(self, phase: str, lease_seconds: int) -> RealDesktopGuest:
        if not os.environ.get("E2B_API_KEY"):
            raise DesktopEpisodeError("desktop_private_e2b_credential_missing")
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(
            template="desktop", resolution=(1280, 800),
            timeout=lease_seconds, allow_internet_access=False,
            metadata={"envloop_purpose": "teacher-native-wdi-train-" + phase})
        return RealDesktopGuest(sandbox, phase=phase)


class DesktopTrainEpisodeWorker:
    """Concrete train-only native Office worker for collect_train_batch."""

    cell_id = "desktop-native"
    action_profile = ACTION_PROFILE_VERSION
    original_software_gui = True
    original_surface = "native"
    requires_e2b = True
    requires_fresh_e2b_reset = True

    def __init__(self, *, candidate_root: Path, private_map: Path,
                 guest_identity_public: Path, private_output_root: Path,
                 ratification_path: Path | None = None,
                 ratification_sha256: str | None = None,
                 expected_runtime_sha256: str | None = None,
                 expected_verifier_sha256: str | None = None,
                 expected_inventory_sha256: str | None = None,
                 expected_guest_identity_sha256: str | None = None,
                 enable_live: bool = False,
                 backend: object | None = None):
        self.candidate_root = Path(candidate_root).resolve()
        self.private_map = Path(private_map).resolve()
        self.guest_identity_public = Path(guest_identity_public).resolve()
        self.private_output_root = Path(private_output_root).resolve()
        self.ratification_path = Path(ratification_path) if ratification_path else None
        self.ratification_sha256 = ratification_sha256
        self.runtime_sha256 = runtime_sha256()
        self.verifier_sha256 = verifier_sha256()
        self.adapter_sha256 = adapter_sha256()
        self.expected_runtime_sha256 = expected_runtime_sha256
        self.expected_verifier_sha256 = expected_verifier_sha256
        self.expected_inventory_sha256 = expected_inventory_sha256
        self.expected_guest_identity_sha256 = expected_guest_identity_sha256
        self.enable_live = enable_live
        if backend is not None and enable_live:
            raise DesktopEpisodeError("desktop_fake_backend_cannot_enable_live")
        self.backend = backend if backend is not None else RealDesktopTrainBackend()

    def _require_live_freeze(self) -> None:
        if getattr(self.backend, "is_fake", False):
            raise DesktopEpisodeError("desktop_fake_backend_cannot_admit_training")
        if (self.enable_live is not True or self.ratification_path is None or
                not _private(self.ratification_path, directory=False) or
                self.runtime_sha256 != runtime_sha256() or
                self.verifier_sha256 != verifier_sha256() or
                self.adapter_sha256 != adapter_sha256() or
                self.expected_runtime_sha256 != self.runtime_sha256 or
                self.expected_verifier_sha256 != self.verifier_sha256 or
                type(self.expected_inventory_sha256) is not str or
                HEX64.fullmatch(self.expected_inventory_sha256) is None or
                type(self.expected_guest_identity_sha256) is not str or
                HEX64.fullmatch(self.expected_guest_identity_sha256) is None or
                type(self.ratification_sha256) is not str or
                HEX64.fullmatch(self.ratification_sha256) is None):
            raise DesktopEpisodeError("desktop_live_episode_requires_frozen_bindings")
        try:
            ratified, sha = validate_ratification(self.ratification_path)
        except (OSError, ValueError, TypeError, KeyError):
            raise DesktopEpisodeError("desktop_six_cell_ratification_invalid") from None
        if (sha != self.ratification_sha256 or
                ratified["cell_profiles"][self.cell_id]["adapter_sha256"] !=
                self.adapter_sha256):
            raise DesktopEpisodeError("desktop_six_cell_adapter_binding_changed")

    def _preflight(self, task: dict, out_dir: Path) -> tuple[dict, bytes, dict, str, dict, str]:
        self._require_live_freeze()
        if (not _private(self.private_output_root, directory=True) or
                not _private(out_dir, directory=True) or
                not out_dir.resolve().is_relative_to(self.private_output_root) or
                not _private(out_dir / "frames", directory=True) or
                set(child.name for child in out_dir.iterdir()) != {"frames"}):
            raise DesktopEpisodeError("desktop_episode_private_output_unsafe")
        row, source, oracle, filename = _package(self.candidate_root, task)
        inventory_raw = (self.candidate_root / "candidate-inventory.json").read_bytes()
        if (self.expected_inventory_sha256 is not None and
                _sha(inventory_raw) != self.expected_inventory_sha256):
            raise DesktopEpisodeError("desktop_train_inventory_binding_changed")
        if not _private(self.private_map, directory=False):
            raise DesktopEpisodeError("desktop_private_oracle_map_unsafe")
        map_raw = self.private_map.read_bytes()
        mapping = json.loads(map_raw)
        inventory = json.loads(
            (self.candidate_root / "candidate-inventory.json").read_bytes())
        if (type(mapping.get("variant_salt")) is not str or
                len(mapping["variant_salt"]) < 32 or
                inventory.get("private_map_sha256") != _sha(map_raw) or
                not self.guest_identity_public.is_file() or
                self.guest_identity_public.is_symlink() or
                not self.guest_identity_public.is_relative_to(ROOT)):
            raise DesktopEpisodeError("desktop_guest_or_scorer_binding_missing")
        guest_raw = self.guest_identity_public.read_bytes()
        if (self.expected_guest_identity_sha256 is not None and
                _sha(guest_raw) != self.expected_guest_identity_sha256):
            raise DesktopEpisodeError("desktop_guest_identity_binding_changed")
        guest = json.loads(guest_raw)
        if (guest.get("schema") !=
                "cua-native-wdi-guest-content-identity-public-v1" or
                guest.get("scoped_guest_content_identity_passed") is not True or
                guest.get("guest_content_probe_script_sha256") !=
                _sha(runtime_fingerprint_probe.GUEST_CONTENT_PROBE.encode())):
            raise DesktopEpisodeError("desktop_guest_identity_unbound")
        return row, source, oracle, filename, guest, mapping["variant_salt"]

    def run_episode(self, *, task, out_dir, sample_teacher,
                    dispatch_e2b) -> dict:
        task = _validate_task(task)
        if not callable(sample_teacher) or not callable(dispatch_e2b):
            raise DesktopEpisodeError("desktop_teacher_callbacks_missing")
        out_dir = Path(out_dir).absolute()
        row, source, oracle, filename, guest_ref, private_salt = self._preflight(
            task, out_dir)
        suffix = Path(filename).suffix
        artifacts_dir = out_dir / "artifacts"
        artifacts_dir.mkdir(mode=0o700)
        frame_refs: list[dict] = []
        trace_rows: list[dict] = []
        teacher_shas: list[str] = []
        predispatch_refs: list[dict] = []
        guests: list[DesktopGuest] = []
        e2b_attempt_ids: list[str] = []
        actor: DesktopGuest | None = None
        reset_guest: DesktopGuest | None = None
        saved: bytes | None = None
        score: dict | None = None
        started = time.monotonic()

        def require_time() -> None:
            if time.monotonic() - started > EPISODE_WALL_SECONDS:
                raise DesktopEpisodeError("desktop_episode_wall_clock_exhausted")

        def create_guest(phase: str) -> DesktopGuest:
            allocated: DesktopGuest | None = None

            def provider(_request: dict) -> dict:
                nonlocal allocated
                allocated = self.backend.create(phase, LEASE_SECONDS)
                guests.append(allocated)
                return {"schema": teacher.E2B_RESULT_SCHEMA,
                        "sandbox_id": allocated.sandbox_id,
                        "lease_seconds": LEASE_SECONDS,
                        "created": True}

            paid = dispatch_e2b(
                phase=phase, lease_seconds=LEASE_SECONDS,
                reserve_usd=E2B_RESERVE_USD_PER_LEASE, provider=provider)
            if (allocated is None or type(paid) is not dict or
                    paid.get("result", {}).get("sandbox_id") != allocated.sandbox_id or
                    type(paid.get("attempt_id")) is not str):
                raise DesktopEpisodeError("desktop_e2b_lease_result_ambiguous")
            e2b_attempt_ids.append(paid["attempt_id"])
            return allocated

        try:
            actor = create_guest("actor")
            actor.prepare(source=source, filename=filename, oracle=oracle,
                          guest_identity=guest_ref)
            if (actor.guest_content_sha256 != guest_ref["static_content_sha256"] or
                    actor.provider_shape_attested is not True or
                    actor.fresh_profile_absent is not True or
                    type(actor.profile_sha256) is not str or
                    HEX64.fullmatch(actor.profile_sha256) is None or
                    type(actor.neutral_input) is not bytes or
                    _semantic_input(actor.neutral_input, suffix) !=
                    _semantic_input(source, suffix) or
                    actor.raw_input_sha256 != _sha(source)):
                raise DesktopEpisodeError("desktop_actor_guest_profile_or_neutral_baseline_invalid")
            effective_oracle = {**oracle, "input_sha256": _sha(actor.neutral_input)}
            baseline_result = verify_official(
                actor.neutral_input, actor.neutral_input, effective_oracle,
                private_salt=private_salt)
            if baseline_result.get("passed") is not False:
                raise DesktopEpisodeError("desktop_train_baseline_already_solved")
            memory = ""
            previous = None
            for step in range(MAX_ACTIONS):
                require_time()
                observation = actor.observe(
                    task=task, step=step, previous=previous, memory=memory)
                if (type(observation) is not Observation or
                        observation.task_id != task["task_id"] or
                        observation.task_binding_sha256 != task["package_sha256"] or
                        observation.instruction != task["visible_instruction"] or
                        observation.step != step):
                    raise DesktopEpisodeError("desktop_observation_not_bound_to_train")
                frame_ref = _write_new(
                    out_dir / "frames" / f"step-{step:03d}.png",
                    observation.screenshot_bytes, maximum=4_000_000)
                frame_refs.append({"path": "frames/" + frame_ref["path"],
                                   "sha256": frame_ref["sha256"]})
                sampled = sample_teacher(observation, actor.current_frame_id)
                if (type(sampled) is not dict or
                        set(sampled) != {"action", "trace_row",
                                         "teacher_result_sha256"} or
                        type(sampled["action"]) is not dict or
                        type(sampled["trace_row"]) is not dict or
                        type(sampled["teacher_result_sha256"]) is not str or
                        HEX64.fullmatch(sampled["teacher_result_sha256"]) is None):
                    raise DesktopEpisodeError("desktop_teacher_sample_invalid")
                action = sampled["action"]
                # The paid adapter already checked the frame after sampling;
                # this separate physical check is immediately before dispatch.
                if (actor.current_frame_id() != observation.frame_id or
                        validate_action(action, observation,
                                        current_frame_id=observation.frame_id) != action or
                        sampled["trace_row"].get("step") != step or
                        sampled["trace_row"].get("frame_id") != observation.frame_id or
                        sampled["trace_row"].get("frame_sha256") != frame_ref["sha256"] or
                        sampled["trace_row"].get("action") != action or
                        sampled["trace_row"].get("teacher_result_sha256") !=
                        sampled["teacher_result_sha256"]):
                    raise DesktopEpisodeError("desktop_paid_action_or_frame_changed")
                predispatch = actor.predispatch_frame()
                if (type(predispatch) is not bytes or
                        qwen_v066_adapter.prior.application_frame_digest(
                            predispatch) !=
                        qwen_v066_adapter.prior.application_frame_digest(
                            observation.screenshot_bytes)):
                    raise DesktopEpisodeError("desktop_predispatch_frame_changed")
                pre_ref = _write_new(
                    out_dir / "frames" / f"predispatch-{step:03d}.png",
                    predispatch, maximum=4_000_000)
                predispatch_refs.append({
                    "path": "frames/" + pre_ref["path"],
                    "sha256": pre_ref["sha256"]})
                actor.dispatch(action)
                trace_rows.append(sampled["trace_row"])
                teacher_shas.append(sampled["teacher_result_sha256"])
                memory = action["memory"]
                if action["type"] == "finish":
                    saved = actor.read_saved()
                    score = verify_official(
                        actor.neutral_input, saved, effective_oracle,
                        private_salt=private_salt)
                    break
                previous = {"status": "applied", "code": "ok"}
            else:
                raise DesktopEpisodeError("desktop_teacher_action_budget_exhausted")
            if (saved is None or score is None or score.get("passed") is not True or
                    score.get("errors") != []):
                raise DesktopEpisodeError("desktop_actor_saved_ooxml_not_positive")
            if actor.close() is not True:
                raise DesktopEpisodeError("desktop_actor_sandbox_cleanup_unverified")
            require_time()
            reset_guest = create_guest("reset")
            if reset_guest.sandbox_id == actor.sandbox_id:
                raise DesktopEpisodeError("desktop_fresh_reset_reused_actor_sandbox")
            reset_guest.prepare(source=source, filename=filename, oracle=oracle,
                                guest_identity=guest_ref)
            require_time()
            if (reset_guest.guest_content_sha256 != actor.guest_content_sha256 or
                    reset_guest.provider_shape_attested is not True or
                    reset_guest.fresh_profile_absent is not True or
                    reset_guest.profile_sha256 != actor.profile_sha256 or
                    reset_guest.raw_input_sha256 != actor.raw_input_sha256 or
                    type(reset_guest.neutral_input) is not bytes or
                    _semantic_input(reset_guest.neutral_input, suffix) !=
                    _semantic_input(actor.neutral_input, suffix) or
                    _sha(reset_guest.read_saved()) !=
                    _sha(reset_guest.neutral_input)):
                raise DesktopEpisodeError("desktop_fresh_guest_profile_or_baseline_changed")
            baseline_semantic = {
                "task_binding_sha256": task["package_sha256"],
                "source_input_sha256": _sha(source),
                "neutral_content": _semantic_input(actor.neutral_input, suffix),
                "neutral_profile_sha256": actor.profile_sha256,
                "scoped_guest_content_sha256": actor.guest_content_sha256,
            }
            restored_semantic = {
                "task_binding_sha256": task["package_sha256"],
                "source_input_sha256": _sha(source),
                "neutral_content": _semantic_input(reset_guest.neutral_input, suffix),
                "neutral_profile_sha256": reset_guest.profile_sha256,
                "scoped_guest_content_sha256": reset_guest.guest_content_sha256,
            }
            if (baseline_semantic != restored_semantic or
                    reset_guest.close() is not True):
                raise DesktopEpisodeError("desktop_fresh_reset_or_teardown_failed")
            require_time()
            frame_evidence_ref = _artifact(
                out_dir, "frame-evidence.private.json",
                _canonical({"predispatch_frame_refs": predispatch_refs,
                            "guest_sandbox_id_sha256s": [
                                _sha(guest.sandbox_id.encode()) for guest in guests],
                            "scoped_guest_content_sha256":
                            actor.guest_content_sha256,
                            "neutral_profile_sha256": actor.profile_sha256,
                            "both_provider_shapes_attested": True,
                            "both_profiles_absent_before_neutral_open": True,
                            "source_input_sha256": _sha(source),
                            "actor_neutral_input_sha256": _sha(actor.neutral_input),
                            "reset_neutral_input_sha256":
                            _sha(reset_guest.neutral_input)}))
            saved_ref = _artifact(out_dir, "saved" + suffix, saved)
            baseline_ref = _artifact(out_dir, "baseline.private.json",
                                     _canonical(baseline_semantic))
            restored_ref = _artifact(out_dir, "restored.private.json",
                                     _canonical(restored_semantic))
            common = {"cell_id": self.cell_id, "task_id": task["task_id"],
                      "package_sha256": task["package_sha256"]}
            state = {
                "schema": teacher.STATE_SCHEMA, **common,
                "independent_of_actor": True,
                "native_save_observed": True,
                "target_state_pass": True,
                "no_regression_pass": True,
                "saved_artifact_sha256": saved_ref["sha256"],
                "saved_artifact_ref": saved_ref,
                "frame_evidence_ref": frame_evidence_ref,
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
                                    _canonical(trace_rows))
            state_ref = _write_new(out_dir / "saved-state.private.json",
                                   _canonical(state))
            reset_ref = _write_new(out_dir / "reset.private.json",
                                   _canonical(reset))
            episode = {
                "schema": teacher.EPISODE_SCHEMA,
                "status": "admitted", "split": "train", **common,
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
                "e2b_attempt_ids": e2b_attempt_ids,
            }
            receipt_ref = _write_new(out_dir / "episode.private.json",
                                     _canonical(episode))
            audit_episode_private(out_dir)
            return {"episode_receipt_path": str(out_dir / receipt_ref["path"]),
                    "episode_receipt_sha256": receipt_ref["sha256"]}
        except BaseException as exc:
            if not (out_dir / "failure.private.json").exists():
                _write_new(out_dir / "failure.private.json",
                           _canonical({
                               "schema": "cua-native-wdi-v066-teacher-failure-v1",
                               "failure_type": type(exc).__name__,
                               "reason": str(exc) if isinstance(exc, DesktopEpisodeError)
                               else "provider_callback_or_runtime_failure",
                               "observed_frame_count": len(frame_refs),
                               "applied_action_count": len(trace_rows),
                               "known_sandbox_count": len(guests),
                               "provider_replay_authorized": False,
                           }))
            raise
        finally:
            for guest in guests:
                if not guest.killed:
                    guest.close()


__all__ = ["DesktopTrainEpisodeWorker", "RealDesktopTrainBackend",
           "runtime_sha256", "verifier_sha256", "adapter_sha256",
           "audit_episode_private"]
