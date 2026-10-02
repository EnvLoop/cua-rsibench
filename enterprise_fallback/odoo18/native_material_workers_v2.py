"""Additive, source-bound Odoo workers sharing one neutral native adapter.

Existing frozen files are never changed or monkeypatched. The three small
adapter imports are replaced in isolated module namespaces; all original
checkpoint, paid dispatch, SQL, filestore, and worker-lease code is retained.
The new binding is a scoped source freeze, not a six-cell promotion receipt.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import importlib
import json
from pathlib import Path
import re
import sys
import time
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_MODULE = "enterprise_fallback.odoo18.odoo_v066_native_material_adapter_v2"
ADAPTER_FILE = "enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py"
BINDING_SCHEMA = "envloop-odoo-v066-native-material-worker-binding-v2"
TRAIN_CONTROL_SCHEMA = "envloop-odoo-v066-native-material-train-control-v2"
TRAIN_CONTROL_STATUS = "fresh_native_geometry_material_train_flow_verified"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
NONCE = re.compile(r"[0-9a-f]{32}\Z")
SOURCE_FILES = (
    "enterprise_fallback/odoo18/native_material_workers_v2.py",
    "enterprise_fallback/odoo18/native_service_readiness_v2.py",
    ADAPTER_FILE,
    "enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py",
    "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "enterprise_fallback/odoo18/odoo_native_adapter.py",
    "enterprise_fallback/odoo18/teacher_episode_worker_v066.py",
    "enterprise_fallback/odoo18/selection_worker_v066.py",
    "enterprise_fallback/odoo18/compose.yaml",
    "enterprise_fallback/odoo18/factory.py",
    "enterprise_fallback/odoo18/partition_factory.py",
    "enterprise_fallback/odoo18/gui_controls.py",
    "enterprise_fallback/odoo18/reset.py",
    "enterprise_fallback/odoo18/verify.py",
    "enterprise_fallback/odoo18/worker_lease.py",
    "enterprise_fallback/odoo18/v066_requalification_pilot.py",
    "tools/odoo_v066_native_material_qualification_v2.py",
    "tools/odoo_v066_current_candidate_case_v5.py",
    "tools/audit_odoo_v066_current_candidate_case_v1.py",
    "tools/odoo_v066_scale_protocol_v1.py",
    "tools/odoo_v066_scale_controller_v1.py",
    "tools/odoo_v066_scale_recipes_v1.py",
    "tools/odoo_v066_scale_audit_v1.py",
    "tools/record_odoo_v066_train_gui_v1.py",
    "tools/odoo_v066_train_attachment_calibration_v13.py",
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_vision_proxy.py",
    "src/cursibench/full_study_selection_environment_v1.py",
    "src/cursibench/full_study_campaign_dispatch_v1.py",
    "src/cursibench/full_study_teacher_adapter_v1.py",
    "native_desktop_factory/v066_final_freeze.py",
)
TRAIN_IMPORT = "from .odoo_v066_train_adapter import OdooV066TrainAdapter, VIEWPORT"
NEUTRAL_TRAIN_IMPORT = (
    "from .odoo_v066_train_adapter import VIEWPORT\n"
    "from .odoo_v066_native_material_adapter_v2 import "
    "OdooV066NativeMaterialAdapter as OdooV066TrainAdapter"
)
CASE_IMPORT = (
    "from enterprise_fallback.odoo18.odoo_v066_scale_parse_border_adapter_v5 import (\n"
    "        OdooV066ScaleParseBorderAdapterV5, PROFILE)"
)
NEUTRAL_CASE_IMPORT = (
    "from enterprise_fallback.odoo18.odoo_v066_native_material_adapter_v2 import (\n"
    "        OdooV066NativeMaterialAdapter as OdooV066ScaleParseBorderAdapterV5, PROFILE)"
)
EVALUATOR_STARTUP = '''        running_before = train_recorder._running(factory.HERE)
        if not {"db", "web"} <= running_before:
            train_recorder._compose(factory.HERE, "up", "-d", "db", "web")'''
NEUTRAL_EVALUATOR_STARTUP = '''        running_before = train_recorder._running(factory.HERE)
        _native_ensure_ready(
            worker=factory.HERE, running_before=running_before,
            compose=lambda *args: train_recorder._compose(factory.HERE, *args),
            running=lambda: train_recorder._running(factory.HERE),
            receipt_sink=lambda value: _save(attempt / "db-readiness.private.json", value))'''
MODEL_STARTUP = '''                if not {"db", "web"} <= running_before:
                    self._compose("up", "-d", "db", "web")'''
NEUTRAL_MODEL_STARTUP = '''                _native_ensure_ready(
                    worker=self.worker_dir, running_before=running_before,
                    compose=self._compose, running=self._running,
                    receipt_sink=self._native_readiness_sink)'''


class NativeMaterialWorkerError(ValueError):
    """Fixed failure labels; no task, oracle, credential, or provider text."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise NativeMaterialWorkerError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def common_adapter_class():
    return importlib.import_module(ADAPTER_MODULE).OdooV066NativeMaterialAdapter


def _native_current_frame_id(adapter, page) -> str:
    """Sampling freshness; the action-specific neutral guards still dispatch."""
    observation = adapter.latest
    if (observation is None or page is not adapter._native_page or
            page.url != adapter.latest_url or time.monotonic() > observation.expires_at):
        return "stale"
    context = adapter._context()
    if context != adapter._observed_context:
        return "stale"
    raw = page.screenshot(type="png")
    if adapter._context() != context or page.url != adapter.latest_url:
        return "stale"
    eligible = (context["rfq_form"] and context["form_count"] == 1 and
                context["modal_count"] == 0 and context["viewer_count"] == 0 and
                (context["focus_in_form"] or context["focus_is_body"]))
    adapter_module = importlib.import_module(ADAPTER_MODULE)
    material = adapter_module.border_material(observation.screenshot_bytes, context["native_geometry"]) if eligible else None
    if material is None:
        return observation.frame_id if raw == observation.screenshot_bytes else "stale"
    physical = adapter_module.border_material(raw, context["native_geometry"])
    return observation.frame_id if physical is not None and physical[
        "canonical_material_sha256"] == material["canonical_material_sha256"] else "stale"


def public_binding() -> dict:
    """Read source files only. Never import a worker or start a provider."""
    adapter = importlib.import_module(ADAPTER_MODULE)
    adapter_binding = adapter.public_binding()
    require(type(adapter_binding) is dict and
            HEX64.fullmatch(str(adapter_binding.get("binding_sha256"))) is not None,
            "native_adapter_binding_invalid")
    value = {
        "schema": BINDING_SCHEMA,
        "profile": adapter.PROFILE,
        "native_adapter_binding": adapter_binding,
        "source_sha256s": {name: digest((ROOT / name).read_bytes())
                           for name in SOURCE_FILES},
        "adapter_substitutions": {
            "teacher": "OdooV066NativeMaterialAdapter",
            "qwen_base": "OdooV066NativeMaterialAdapter",
            "qwen_checkpoint": "OdooV066NativeMaterialAdapter",
            "evaluator": "OdooV066NativeMaterialAdapter",
        },
        "service_readiness_policy": {
            "source": "tools/odoo_v066_train_attachment_calibration_v13.py",
            "timeout_seconds": 60, "probe_timeout_seconds": 5,
            "max_probes": 30, "poll_seconds": 1,
            "query": "SELECT 1", "database_role": "bench_verify",
            "startup_order": ["stop_web_if_present", "up_db", "v13_ready_gate", "up_web"],
            "restore_before_gate": False,
        },
        "old_positive_credit": 0,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }
    return {**value, "binding_sha256": digest(canonical(value))}


def validate_binding(value: object, expected_sha256: str | None = None) -> dict:
    require(type(value) is dict and canonical(value) == canonical(public_binding()),
            "native_worker_whole_binding_changed")
    if expected_sha256 is not None:
        require(expected_sha256 == value["binding_sha256"],
                "native_worker_binding_digest_changed")
    return value


def private_json(path: Path, expected_sha256: str | None = None) -> dict:
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and
            path.stat().st_mode & 0o077 == 0 and
            0 < path.stat().st_size <= 8_000_000,
            "native_private_receipt_unsafe")
    raw = path.read_bytes()
    if expected_sha256 is not None:
        require(digest(raw) == expected_sha256,
                "native_private_receipt_digest_changed")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise NativeMaterialWorkerError("native_private_receipt_invalid") from None
    require(type(result) is dict, "native_private_receipt_invalid")
    return result


def validate_train_control(value: object, binding: dict) -> dict:
    """Accept only a new neutral TRAIN control, never any historical success."""
    validate_binding(binding)
    require(type(value) is dict and
            value.get("schema") == TRAIN_CONTROL_SCHEMA and
            value.get("status") == TRAIN_CONTROL_STATUS and
            value.get("split") == "train" and
            value.get("family") == "purchase" and
            type(value.get("run_nonce_hex")) is str and
            NONCE.fullmatch(str(value.get("run_nonce_hex"))) is not None and
            value.get("run_nonce_sha256") == digest(value["run_nonce_hex"].encode()) and
            value.get("native_adapter_binding_sha256") ==
            binding["native_adapter_binding"]["binding_sha256"] and
            value.get("native_worker_binding_sha256") == binding["binding_sha256"] and
            all(type(value.get(key)) is float and value[key] == expected
                for key, expected in (("independent_baseline_reward", 0.0),
                                      ("independent_positive_reward", 1.0),
                                      ("independent_wrong_object_reward", 0.0))) and
            all(value.get(key) is True for key in (
                "full_pre_web_filestore_reset_exact",
                "protected_post_web_source_bytes_equal",
                "source_attachment_readback", "original_services_restored",
                "source_visual_review_verified", "native_service_readiness_verified")) and
            value.get("source_visual_review_pending") is False and
            all(HEX64.fullmatch(str(value.get(key))) is not None for key in (
                "attempt_sha256", "audit_sha256", "plan_sha256", "source_review_sha256",
                "source_frame_sha256", "source_asset_sha256",
                "native_service_readiness_receipt_sha256")) and
            all(type(value.get(key)) is int and value[key] == 0 for key in (
                "old_positive_credit", "model_attempts", "official_final_tasks_admitted")),
            "fresh_native_train_control_required")
    return value


def _isolated_module(relative: str, tag: str, binding: dict,
                     substitutions: tuple[tuple[str, str], ...] = ()) -> ModuleType:
    validate_binding(binding)
    path = ROOT / relative
    raw = path.read_bytes()
    require(digest(raw) == binding["source_sha256s"][relative],
            "native_reused_source_changed")
    source = raw.decode("utf-8")
    for before, after in substitutions:
        require(source.count(before) == 1,
                "native_adapter_substitution_interface_changed")
        source = source.replace(before, after, 1)
    prefix = "enterprise_fallback.odoo18" if relative.startswith(
        "enterprise_fallback/") else "tools"
    name = prefix + "._native_material_" + tag + "_" + binding["binding_sha256"][:16]
    loaded = sys.modules.get(name)
    if loaded is not None:
        require(getattr(loaded, "_native_whole_binding", None) == binding,
                "native_isolated_module_binding_conflict")
        return loaded
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = prefix
    module._native_whole_binding = binding
    # A separate name is required for dataclasses. Existing module identities
    # and their global aliases are never modified.
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
        validate_binding(binding)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def evaluator_module(binding: dict) -> ModuleType:
    module = _isolated_module(
        "tools/odoo_v066_current_candidate_case_v5.py", "case", binding,
        ((CASE_IMPORT, NEUTRAL_CASE_IMPORT), (EVALUATOR_STARTUP, NEUTRAL_EVALUATOR_STARTUP)))
    module._native_ensure_ready = _readiness_function(binding)
    module.EPOCH_CASE_SCHEMA = "envloop-odoo-v066-native-material-gui-case-v2"
    module.EPOCH_CASE_STATUS = "raw_native_material_gui_positive_negative_reset_complete_review_pending"
    module.INTENT_SCHEMA = "envloop-odoo-v066-native-material-gui-case-intent-v2"
    recorder = _isolated_module("tools/record_odoo_v066_train_gui_v1.py", "recorder", binding)
    recorder.MAX_PRE_INTENT_STALE_OBSERVATIONS = 1

    class SingleAttemptJournal(recorder.ActionJournal):
        def act(self, *args, **kwargs):
            frame = super().act(*args, **kwargs)
            self.sft.clear()
            return frame

    module.HoldoutJournal = SingleAttemptJournal
    return module


def semantic_auditor_module(binding: dict) -> ModuleType:
    module = _isolated_module(
        "tools/audit_odoo_v066_current_candidate_case_v1.py", "audit", binding)
    module.case_path = evaluator_module(binding)
    module.EPOCH_CASE_AUDIT_SCHEMA = "envloop-odoo-v066-native-material-gui-case-audit-v2"
    return module


def _model_modules(binding: dict) -> tuple[ModuleType, ModuleType]:
    current_frame_method = '''        observation = self.adapter.latest
        if (observation is not None and self.page.url == self.adapter.latest_url
                and _hash(self.page.screenshot(type="png")) ==
                observation.screenshot["sha256"] and
                time.monotonic() <= observation.expires_at):
            return observation.frame_id
        return "stale"'''
    teacher_dispatch = '''        checked = validate_action(action, observation,
                                  current_frame_id=observation.frame_id)'''
    selection_parse = '''                        action = output_v066.normalize_model_action(
                            result["text"], observation,
                            current_frame_id=observation.frame_id)'''
    selection_constructor_tail = '''                    instruction=case["prompt"])
                memory = ""'''
    selection_sink = '''                    instruction=case["prompt"])
                def save_native_guard(index, raw):
                    ref = _write_new(task_dir / "frames" / f"guard-{index:04d}.png", raw)
                    return {"path": "frames/" + ref["path"], "sha256": ref["sha256"]}
                adapter.frame_guard_sink = save_native_guard
                memory = ""'''
    teacher = _isolated_module(
        "enterprise_fallback/odoo18/teacher_episode_worker_v066.py", "teacher", binding,
        ((TRAIN_IMPORT, NEUTRAL_TRAIN_IMPORT), (MODEL_STARTUP, NEUTRAL_MODEL_STARTUP),
         (current_frame_method, "        return _native_current_frame_id(self.adapter, self.page)"),
         (teacher_dispatch, "        checked = self.adapter.parse_current_action(action)"),
         ('''        applied = self.adapter.dispatch(checked)
        if applied["action"] != checked:''',
          '''        applied = self.adapter.dispatch(checked)
        self.native_last_contract_receipt = applied["public_contract_receipt"]
        if applied["action"] != checked:''')))
    selection = _isolated_module(
        "enterprise_fallback/odoo18/selection_worker_v066.py", "selection", binding,
        ((TRAIN_IMPORT, NEUTRAL_TRAIN_IMPORT), (MODEL_STARTUP, NEUTRAL_MODEL_STARTUP),
         (selection_parse, '                        action = adapter.parse_current_action(result["text"])'),
         (selection_constructor_tail, selection_sink),
         ('''                        "action_type": action["type"],''',
          '''                        "action_type": action["type"], "native_action": action,
                        "native_observation_control_refs": sorted(c.ref for c in observation.controls if c.visible and c.enabled),''')))
    teacher._native_current_frame_id = _native_current_frame_id
    teacher._native_ensure_ready = _readiness_function(binding)
    selection._native_ensure_ready = teacher._native_ensure_ready
    require(teacher.OdooV066TrainAdapter is common_adapter_class() and
            selection.OdooV066TrainAdapter is common_adapter_class(),
            "native_model_adapter_class_identity_conflict")
    for module in (teacher, selection):
        module.source_hashes = lambda: dict(validate_binding(binding)["source_sha256s"])
        module.runtime_sha256 = lambda: validate_binding(binding)["binding_sha256"]
        module.adapter_sha256 = lambda: validate_binding(binding)["source_sha256s"][ADAPTER_FILE]
    if not hasattr(selection, "_native_original_audit_task_artifacts"):
        selection._native_original_audit_task_artifacts = selection._audit_task_artifacts

        def audit_task(directory, task, row):
            selection._native_original_audit_task_artifacts(directory, task, row)
            actions = private_json_list(Path(directory) / "actions.private.json")
            for step, action in enumerate(actions):
                observed = private_ref_bytes(Path(directory), {
                    "path": f"frames/step-{step:03d}.png",
                    "sha256": action["frame_sha256"],
                })
                audit_native_contract(action["contract_receipt"], action["native_action"],
                                      observed, step, task, Path(directory),
                                      observation_control_refs=action.get("native_observation_control_refs"))

        selection._audit_task_artifacts = audit_task
    return teacher, selection


def _readiness_function(binding: dict):
    def ensure_ready(**kwargs):
        validate_binding(binding)
        module = importlib.import_module("enterprise_fallback.odoo18.native_service_readiness_v2")
        return module.ensure_ready(**kwargs)
    return ensure_ready


def audit_readiness_receipt(path: Path, binding: dict, worker_dir: Path) -> dict:
    validate_binding(binding)
    receipt = private_json(path)
    readiness = importlib.import_module("enterprise_fallback.odoo18.native_service_readiness_v2")
    try:
        readiness.validate_ready_receipt(receipt)
    except (ValueError, TypeError, KeyError):
        raise NativeMaterialWorkerError("native_saved_service_readiness_unverified") from None
    require(receipt["worker"] == str(Path(worker_dir).resolve()),
            "native_saved_service_readiness_worker_changed")
    return {"native_service_readiness_receipt_sha256": digest(Path(path).read_bytes()),
            "native_service_readiness_verified": True}


def private_json_list(path: Path) -> list:
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and
            path.stat().st_mode & 0o077 == 0 and path.stat().st_size <= 8_000_000,
            "native_private_list_unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeDecodeError):
        raise NativeMaterialWorkerError("native_private_list_invalid") from None
    require(type(value) is list, "native_private_list_invalid")
    return value


def private_ref_bytes(root: Path, ref: dict) -> bytes:
    require(type(ref) is dict and set(ref) == {"path", "sha256"} and
            type(ref["path"]) is str and HEX64.fullmatch(str(ref["sha256"])) is not None,
            "native_frame_ref_invalid")
    relative = Path(ref["path"])
    require(not relative.is_absolute() and ".." not in relative.parts and
            relative.parts and relative.parts[0] == "frames" and
            relative.suffix == ".png", "native_frame_ref_outside_frames")
    root = Path(root)
    require(root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o077 == 0,
            "native_frame_root_unsafe")
    current = root
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink() and current.exists() and
                current.stat().st_mode & 0o077 == 0,
                "native_frame_ref_unsafe")
    require(current.is_file() and current.stat().st_size <= 8_000_000,
            "native_frame_ref_unsafe")
    raw = current.read_bytes()
    require(digest(raw) == ref["sha256"], "native_frame_ref_digest_changed")
    return raw


def audit_native_contract(contract: dict, action: dict, observed: bytes,
                          step: int, task: dict, root: Path, *,
                          observation_control_refs: list[str]) -> dict:
    """Reopen both guards and bind them to the durable normalized action."""
    adapter = importlib.import_module(ADAPTER_MODULE)
    require(type(observation_control_refs) is list and
            all(type(ref) is str for ref in observation_control_refs) and
            observation_control_refs == sorted(set(observation_control_refs)),
            "native_durable_observation_control_refs_invalid")
    require(type(action) is dict and type(contract) is dict and
            action.get("task_id") == task["task_id"] and
            action.get("task_binding_sha256") == task["package_sha256"] and
            contract.get("task_id_sha256") == digest(task["task_id"].encode()) and
            contract.get("task_binding_sha256") == task["package_sha256"] and
            type(contract.get("step")) is int and contract["step"] == step and
            contract.get("action_profile") == "scale-action-profile-v0.6.6" and
            contract.get("screenshot", {}).get("sha256") == digest(observed) and
            contract.get("screenshot", {}).get("width") == 1440 and
            contract.get("screenshot", {}).get("height") == 1000 and
            contract.get("error_code") is None and
            contract.get("native_adapter_profile") == adapter.PROFILE,
            "native_action_contract_identity_changed")
    action_sha = digest(json.dumps(action, sort_keys=True, separators=(",", ":"),
                                   allow_nan=False).encode())
    frame_id_sha = digest(action["frame_id"].encode())
    require(contract.get("frame_id_sha256") == frame_id_sha,
            "native_public_contract_frame_id_changed")
    guards = []
    refs = []
    for stage in ("parse", "dispatch"):
        guard = contract.get("native_material_" + stage + "_guard")
        require(type(guard) is dict and guard.get("stage") == stage and
                guard.get("action_sha256") == action_sha and
                guard.get("observed_frame_id_sha256") == frame_id_sha and
                guard.get("observed_control_refs") == observation_control_refs,
                "native_guard_action_frame_or_observed_control_refs_changed")
        try:
            result = adapter.audit_guard(guard, observed,
                                         lambda ref: private_ref_bytes(root, ref), action=action)
        except (ValueError, TypeError, KeyError):
            raise NativeMaterialWorkerError("native_saved_guard_rederivation_failed") from None
        require(result.get("raw_guard_pngs_reopened") == 3 and
                result.get("material_equality_verified") is True and
                all(row.get("step") == step and
                    row.get("observed_frame_sha256") == digest(observed) and
                    row.get("observed_frame_id_sha256") == frame_id_sha
                    for row in guard["sampled_frames"]),
                "native_guard_sample_identity_changed")
        refs.extend(row["sampled_frame_ref"]["path"] for row in guard["sampled_frames"])
        guards.append(guard)
    require(len(set(refs)) == 6 and
            guards[0]["observed_url"] == guards[1]["observed_url"] and
            guards[0]["observed_native_context"] == guards[1]["observed_native_context"] and
            guards[0]["native_context"] == guards[1]["native_context"] and
            guards[0]["native_target_contexts"] == guards[1]["native_target_contexts"],
            "native_parse_dispatch_context_or_raw_samples_changed")
    return {"guard_pngs_reopened": 6, "action_sha256": action_sha}


def _require_live(worker, binding: dict, binding_path: Path,
                  binding_file_sha256: str, train_control_path: Path,
                  train_control_sha256: str) -> None:
    require(worker.enable_live is True and
            worker.expected_runtime_sha256 == binding["binding_sha256"] and
            worker.runtime_sha256 == binding["binding_sha256"] and
            worker.expected_verifier_sha256 == binding["source_sha256s"][
                "enterprise_fallback/odoo18/verify.py"] and
            worker.verifier_sha256 == worker.expected_verifier_sha256 and
            worker.adapter_sha256 == binding["source_sha256s"][ADAPTER_FILE],
            "native_model_live_and_source_bindings_required")
    validate_binding(private_json(binding_path, binding_file_sha256),
                     binding["binding_sha256"])
    validate_train_control(private_json(train_control_path, train_control_sha256), binding)


def _require_campaign_ratification(binding: dict, path: Path | None,
                                   expected_sha256: str | None) -> None:
    require(path is not None and type(expected_sha256) is str and
            HEX64.fullmatch(expected_sha256) is not None,
            "native_model_campaign_ratification_pending")
    private_json(path, expected_sha256)
    from native_desktop_factory.v066_final_freeze import validate_ratification
    try:
        ratification, actual_sha = validate_ratification(path)
    except (OSError, ValueError, TypeError, KeyError):
        raise NativeMaterialWorkerError("native_model_campaign_ratification_not_admitted") from None
    profile = ratification.get("cell_profiles", {}).get("odoo-community", {})
    require(actual_sha == expected_sha256 and
            set(profile) == {"common_source_sha256s", "adapter_sha256"} and
            profile.get("adapter_sha256") == binding["source_sha256s"][ADAPTER_FILE],
            "native_model_campaign_neutral_profile_not_admitted")


def train_worker(*, native_binding_path: Path, native_binding_file_sha256: str,
                 train_control_path: Path, train_control_sha256: str,
                 campaign_ratification_path: Path | None = None,
                 campaign_ratification_sha256: str | None = None,
                 **kwargs):
    """Teacher integration, retaining the existing run_episode API and resets."""
    binding = validate_binding(private_json(native_binding_path, native_binding_file_sha256))
    teacher, _ = _model_modules(binding)

    class NativeTrainWorker(teacher.OdooTrainEpisodeWorker):
        def _require_ratification(self):
            _require_live(self, binding, native_binding_path,
                          native_binding_file_sha256, train_control_path,
                          train_control_sha256)
            _require_campaign_ratification(binding, campaign_ratification_path,
                                            campaign_ratification_sha256)

        def run_episode(self, **episode_kwargs):
            original_backend = self.backend
            out_dir = Path(episode_kwargs["out_dir"])

            class GuardBackend:
                @contextmanager
                def open(self, task):
                    original_backend._native_readiness_sink = lambda value: teacher._artifact(
                        out_dir, "db-readiness.private.json", value)
                    with original_backend.open(task) as active:
                        contracts = out_dir / "artifacts" / "native-contracts"
                        contracts.mkdir(mode=0o700)
                        def save_guard(index, raw):
                            ref = teacher._write_new(out_dir / "frames" / f"guard-{index:04d}.png", raw)
                            return {"path": "frames/" + ref["path"], "sha256": ref["sha256"]}
                        active.adapter.frame_guard_sink = save_guard
                        original_dispatch = active.dispatch

                        def retained_dispatch(action):
                            observation = active.adapter.latest
                            original_dispatch(action)
                            teacher._write_new(contracts / f"step-{observation.step:03d}.private.json",
                                               teacher._canonical({
                                                   "step": observation.step,
                                                   "action": action,
                                                   "frame_sha256": observation.screenshot["sha256"],
                                                   "native_observation_control_refs": sorted(c.ref for c in observation.controls if c.visible and c.enabled),
                                                   "contract_receipt": active.native_last_contract_receipt,
                                               }))

                        active.dispatch = retained_dispatch
                        yield active

            self.backend = GuardBackend()
            try:
                result = super().run_episode(**episode_kwargs)
                audit_readiness_receipt(out_dir / "artifacts" / "db-readiness.private.json", binding,
                                        self.worker_dir)
                task = episode_kwargs["task"]
                trace = private_json_list(out_dir / "actions.private.json")
                for step, row in enumerate(trace):
                    retained = private_json(out_dir / "artifacts" / "native-contracts" /
                                            f"step-{step:03d}.private.json")
                    require(retained.get("step") == step and retained.get("action") == row["action"] and
                            retained.get("frame_sha256") == row["frame_sha256"],
                            "native_teacher_separate_contract_trace_changed")
                    observed = private_ref_bytes(out_dir, {
                        "path": f"frames/step-{step:03d}.png",
                        "sha256": row["frame_sha256"],
                    })
                    audit_native_contract(retained["contract_receipt"], row["action"],
                                          observed, step, task, out_dir,
                                          observation_control_refs=retained.get("native_observation_control_refs"))
                return result
            finally:
                self.backend = original_backend

    require(not ({"ratification_path", "ratification_sha256"} & kwargs.keys()),
            "native_worker_refuses_historical_ratification")
    return NativeTrainWorker(
        ratification_path=campaign_ratification_path,
        ratification_sha256=campaign_ratification_sha256, **kwargs)


def selection_worker(*, native_binding_path: Path, native_binding_file_sha256: str,
                     train_control_path: Path, train_control_sha256: str,
                     campaign_ratification_path: Path | None = None,
                     campaign_ratification_sha256: str | None = None,
                     **kwargs):
    """One neutral worker for the existing explicit Qwen base/checkpoint modes."""
    binding = validate_binding(private_json(native_binding_path, native_binding_file_sha256))
    _, selection = _model_modules(binding)

    class NativeSelectionWorker(selection.OdooSelectionWorker):
        def _require_freeze(self):
            _require_live(self, binding, native_binding_path,
                          native_binding_file_sha256, train_control_path,
                          train_control_sha256)
            _require_campaign_ratification(binding, campaign_ratification_path,
                                            campaign_ratification_sha256)
            require(selection.environment_class.category(self.cell_id) ==
                    self.environment_category,
                    "native_worker_environment_category_changed")
            return selection._cost_authority(self.local_cost_authority_path,
                                             self.local_cost_authority_sha256)

        def run_selection(self, **selection_kwargs):
            out_dir = Path(selection_kwargs["out_dir"])
            self.environment._native_readiness_sink = lambda value: selection._write_json(
                out_dir / "db-readiness.private.json", value)
            result = super().run_selection(**selection_kwargs)
            if result.get("status") == "scored":
                audit_readiness_receipt(out_dir / "db-readiness.private.json", binding, self.worker_dir)
            return result

    require(not ({"ratification_path", "ratification_sha256"} & kwargs.keys()),
            "native_worker_refuses_historical_ratification")
    return NativeSelectionWorker(
        ratification_path=campaign_ratification_path,
        ratification_sha256=campaign_ratification_sha256, **kwargs)
