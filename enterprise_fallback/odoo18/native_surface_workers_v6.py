"""Additive Odoo workers using one owned native surface policy for every actor.

The pinned v2 evaluator, reset, scoring and paid-worker mechanics are loaded in
a separate namespace. Only adapter/evidence binding and truthful dispatch status
handling are changed. No historical proof can admit the new v6 namespace.
"""
from __future__ import annotations

import ast
from dataclasses import asdict
import importlib
from pathlib import Path

from cursibench import native_surface_guard_policy_v1 as policy
from .native_compat_source_loader_v1 import load_source, assert_frozen_v2_sources


_ROOT = Path(__file__).resolve().parents[2]
_SOURCE = "enterprise_fallback/odoo18/native_material_workers_v2.py"
_PIN = "f989273c67f57bcf11101f26395168d33e45f93f7c1f7fc418c102fdbec3c453"


def _function_source(name: str) -> str:
    """Extract an exact function from the already pinned compatibility source."""
    assert_frozen_v2_sources()
    text = (_ROOT / _SOURCE).read_text()
    nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(nodes) != 1:
        raise ValueError("native_surface_frozen_function_changed")
    node = nodes[0]
    return "\n".join(text.splitlines()[node.lineno - 1:node.end_lineno])


_CASE_BIND = "            journal = HoldoutJournal(adapter, page, attempt)"
_CASE_BOUND = _CASE_BIND + "\n            adapter.bind_guard(root=attempt, worker_private=private)"
_OLD_TRACE = '"exact_return_guard_samples":\n                    journal.adapter.frame_guard_samples'
_NEW_TRACE = '"native_surface_policy_sha256": _native_policy_sha256'
_OLD_SELECTION_SINK = '''                def save_native_guard(index, raw):
                    ref = _write_new(task_dir / "frames" / f"guard-{index:04d}.png", raw)
                    return {"path": "frames/" + ref["path"], "sha256": ref["sha256"]}
                adapter.frame_guard_sink = save_native_guard'''
_NEW_SELECTION_SINK = '''                adapter.bind_guard(root=task_dir, worker_private=self.worker_dir / "private")'''
_TEACHER_PRECHECK = '''        if observation is None or self.current_frame_id() != observation.frame_id:
            raise OdooEpisodeError("odoo_current_frame_changed_before_dispatch")'''
_TEACHER_NONEMPTY = '''        if observation is None:
            raise OdooEpisodeError("odoo_observation_missing_before_dispatch")'''
_TEACHER_RETURN = '''        if applied["action"] != checked:
            raise OdooEpisodeError("odoo_dispatch_action_changed")'''
_TEACHER_WITH_RETURN = _TEACHER_RETURN + '''
        self.native_last_action_status = applied["status"]
        return applied'''
_TEACHER_POST_SAMPLE = '''                    if (active.current_frame_id() != observation.frame_id or
                            validate_action(action, observation,
                                            current_frame_id=observation.frame_id)
                            != action or'''
_TEACHER_SYNTAX_SAMPLE = '''                    if (active.adapter.parse_current_action(action) != action or'''
_RECORDER_APPLIED = '''            require(applied.get("action") == normalized and'''
_RECORDER_CHECKED = '''            require((applied.get("status") == "applied" or
                     (applied.get("status") == "finished" and normalized["type"] == "finish")) and
                    applied.get("action") == normalized and'''

_impl = load_source(_SOURCE, "enterprise_fallback.odoo18._native_surface_workers_v6", _PIN, (
    ("odoo_v066_native_material_adapter_v2", "odoo_v066_native_surface_adapter_v6", 4),
    ("OdooV066NativeMaterialAdapter", "OdooV066NativeSurfaceAdapter", 7),
    ("envloop-odoo-v066-native-material", "envloop-odoo-v066-native-surface", 5),
    ('-v2"', '-v6"', 5),
    ("fresh_native_geometry_material_train_flow_verified", "fresh_native_owned_surface_train_flow_verified", 1),
    (_function_source("_native_current_frame_id"),
     'def _native_current_frame_id(adapter, page) -> str:\n    return adapter.current_frame_id()', 1),
    (_function_source("audit_native_contract"),
     'def audit_native_contract(*args, **kwargs):\n    return _surface_audit_native_contract(*args, **kwargs)', 1),
    ('((CASE_IMPORT, NEUTRAL_CASE_IMPORT), (EVALUATOR_STARTUP, NEUTRAL_EVALUATOR_STARTUP)))',
     '((CASE_IMPORT, NEUTRAL_CASE_IMPORT), (EVALUATOR_STARTUP, NEUTRAL_EVALUATOR_STARTUP),\n'
     '         (_surface_case_bind, _surface_case_bound), (_surface_old_trace, _surface_new_trace)))', 1),
    ('    module._native_ensure_ready = _readiness_function(binding)\n    module.EPOCH_CASE_SCHEMA',
     '    module._native_ensure_ready = _readiness_function(binding)\n'
     '    module._native_policy_sha256 = _surface_policy_sha256\n    module.EPOCH_CASE_SCHEMA', 1),
    ('recorder = _isolated_module("tools/record_odoo_v066_train_gui_v1.py", "recorder", binding)',
     'recorder = _isolated_module("tools/record_odoo_v066_train_gui_v1.py", "recorder", binding,\n'
     '                                ((_surface_recorder_applied, _surface_recorder_checked),))', 1),
    (_OLD_SELECTION_SINK, _NEW_SELECTION_SINK, 1),
    ('         (teacher_dispatch, "        checked = self.adapter.parse_current_action(action)"),',
     '         (teacher_dispatch, "        checked = self.adapter.parse_current_action(action)"),\n'
     '         (_surface_teacher_precheck, _surface_teacher_nonempty),\n'
     '         (_surface_teacher_return, _surface_teacher_with_return),\n'
     '         (_surface_teacher_post_sample, _surface_teacher_syntax_sample),\n'
     '         ("                    active.dispatch(action)", "                    native_result = active.dispatch(action)"),\n'
     '         (\'                    if action["type"] == "finish":\',\n'
     '          \'                    if action["type"] == "finish" and native_result["status"] == "finished":\'),\n'
     '         (\'"applied_action_count": len(trace_rows),\',\n'
     '          \'"attempted_turn_count": len(trace_rows),\\n                    "applied_action_count": sum(_native_dispatch_statuses),\'),\n'
     '         ("        teacher_shas: list[str] = []", "        teacher_shas: list[str] = []\\n        _native_dispatch_statuses = []"),\n'
     '         ("                    trace_rows.append(sampled[\\"trace_row\\"])",\n'
     '          "                    _native_dispatch_statuses.append(native_result[\\"status\\"] == \\"applied\\")\\n                    trace_rows.append(sampled[\\"trace_row\\"])"),', 1),
    ('                        "action_type": action["type"], "native_action": action,',
     '                        "action_type": action["type"], "native_action": action, "native_dispatch_status": applied["status"],', 1),
    ('            out_dir = Path(episode_kwargs["out_dir"])',
     '            out_dir = Path(episode_kwargs["out_dir"])\n            worker_private = self.worker_dir / "private"', 1),
    ('                        active.adapter.frame_guard_sink = save_guard',
     '                        active.adapter.bind_guard(root=out_dir, worker_private=worker_private)', 1),
    ('                            original_dispatch(action)', '                            native_result = original_dispatch(action)', 1),
    ('"contract_receipt": active.native_last_contract_receipt,',
     '"contract_receipt": active.native_last_contract_receipt,\n'
     '                                                   "native_dispatch_status": native_result["status"],', 1),
    ('\n                        active.dispatch = retained_dispatch',
     '\n                            return native_result\n\n                        active.dispatch = retained_dispatch', 1),
))

for _name, _value in {
    "_surface_case_bind": _CASE_BIND, "_surface_case_bound": _CASE_BOUND,
    "_surface_old_trace": _OLD_TRACE, "_surface_new_trace": _NEW_TRACE,
    "_surface_policy_sha256": policy.POLICY_SHA,
    "_surface_recorder_applied": _RECORDER_APPLIED, "_surface_recorder_checked": _RECORDER_CHECKED,
    "_surface_teacher_precheck": _TEACHER_PRECHECK, "_surface_teacher_nonempty": _TEACHER_NONEMPTY,
    "_surface_teacher_return": _TEACHER_RETURN, "_surface_teacher_with_return": _TEACHER_WITH_RETURN,
    "_surface_teacher_post_sample": _TEACHER_POST_SAMPLE,
    "_surface_teacher_syntax_sample": _TEACHER_SYNTAX_SAMPLE,
}.items():
    setattr(_impl, _name, _value)

_impl.SOURCE_FILES = tuple(dict.fromkeys(_impl.SOURCE_FILES + (
    "enterprise_fallback/odoo18/native_surface_workers_v6.py",
    "enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py",
    "enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py",
    "enterprise_fallback/odoo18/native_compat_source_loader_v1.py",
    "src/cursibench/native_surface_guard_policy_v1.py",
    "tools/odoo_v066_native_surface_qualification_v6.py",
)))
_base_public_binding = _impl.public_binding


def public_binding() -> dict:
    assert_frozen_v2_sources()
    value = _base_public_binding()
    _impl.require(value["native_adapter_binding"].get("policy_sha256") == policy.POLICY_SHA and
                  value["profile"] == "native-owned-surface-safety-envelope-v6",
                  "native_surface_shared_policy_binding_changed")
    value.pop("binding_sha256")
    value["native_surface_policy_sha256"] = policy.POLICY_SHA
    value["rejected_turns_consume_budget_and_nonce"] = True
    return {**value, "binding_sha256": _impl.digest(_impl.canonical(value))}


def native_ref_bytes(root: Path, ref: dict) -> bytes:
    """Read the plugin's full evidence refs, with exact hashes and private mode."""
    parsed = policy.verify_artifact(root, ref)
    root = Path(root)
    _impl.require(root.stat().st_mode & 0o077 == 0, "native_surface_root_not_private")
    path = root
    for part in Path(parsed.path).parts:
        path = path / part
        _impl.require(path.stat().st_mode & 0o077 == 0, "native_surface_artifact_not_private")
    _impl.require(parsed.size <= 8_000_000, "native_surface_artifact_too_large")
    raw = path.read_bytes()
    _impl.require(len(raw) == parsed.size and _impl.digest(raw) == parsed.sha256,
                  "native_surface_artifact_changed_during_read")
    return raw


def audit_native_contract(contract: dict, action: dict, observed: bytes,
                          step: int, task: dict, root: Path, *,
                          observation_control_refs: list[str]) -> dict:
    adapter = importlib.import_module(_impl.ADAPTER_MODULE)
    _impl.require(type(observation_control_refs) is list and
                  all(type(ref) is str for ref in observation_control_refs) and
                  observation_control_refs == sorted(set(observation_control_refs)) and
                  type(contract) is dict and type(action) is dict and
                  action.get("task_id") == task["task_id"] and
                  action.get("task_binding_sha256") == task["package_sha256"] and
                  action.get("step") == step and type(action.get("step")) is int and
                  contract.get("task_id_sha256") == _impl.digest(task["task_id"].encode()) and
                  contract.get("task_binding_sha256") == task["package_sha256"] and
                  contract.get("step") == step and type(contract.get("step")) is int and
                  contract.get("screenshot", {}).get("sha256") == _impl.digest(observed) and
                  contract.get("screenshot", {}).get("width") == 1440 and
                  contract.get("screenshot", {}).get("height") == 1000 and
                  contract.get("frame_id_sha256") == _impl.digest(action["frame_id"].encode()) and
                  contract.get("action_type") == action.get("type") and
                  contract.get("action_profile") == "scale-action-profile-v0.6.6" and
                  contract.get("native_adapter_profile") == adapter.PROFILE,
                  "native_surface_action_identity_changed")
    capsule = policy.validate_artifact_ref(contract.get("native_surface_guard"), kind="dispatch_receipt")
    try:
        result = adapter.audit_guard(asdict(capsule), observed,
                                     lambda ref: native_ref_bytes(root, ref), action=action)
    except (ValueError, TypeError, KeyError, OSError):
        raise _impl.NativeMaterialWorkerError("native_surface_saved_evidence_invalid") from None
    _impl.require(result.get("status") == "verified" and result.get("profile") == adapter.PROFILE and
                  result.get("raw_observation_images_reopened") == 1 and
                  result.get("raw_predispatch_images_reopened") == 1 and
                  result.get("decision_status") in ("accepted", "rejected") and
                  result.get("dispatch_status") in ("applied", "rejected", "finished") and
                  ((result["decision_status"], result["dispatch_status"]) in
                   (("accepted", "applied"), ("rejected", "rejected"), ("accepted", "finished"))) and
                  (result["dispatch_status"] != "finished" or action.get("type") == "finish"),
                  "native_surface_driver_status_or_evidence_invalid")
    return {**result, "guard_pngs_reopened": 2, "action_sha256": policy.digest(action)}


_impl._surface_audit_native_contract = audit_native_contract
_impl.public_binding = public_binding


def __getattr__(name):
    return getattr(_impl, name)
