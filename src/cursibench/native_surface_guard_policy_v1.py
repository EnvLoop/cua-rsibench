"""Immutable native safety envelope; independent of task correctness and pixels.

This module makes decisions only. The evaluator must save both raw images and
native envelopes, bind a real lease check, consume the nonce durably, and write
an exclusive intent before invoking an application driver. It never retargets
an action or treats a decision as proof that a driver applied it.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import time
from types import MappingProxyType
from typing import Any


VERSION = "native-surface-guard-v1"
FEEDBACK_VERSION = "native-surface-rejection-feedback-v1"
REJECTION_REASONS = frozenset({
    "invalid_action", "native_binding_changed", "stale_nonce_or_task", "expired_observation",
    "native_context_changed", "target_not_current_and_safe", "editable_focus_changed_or_unsafe",
})
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
ACTION_TYPES = ("click", "double_click", "type", "key", "scroll", "drag", "wait", "finish")
ARTIFACT_KINDS = (
    "raw_observation_image", "raw_predispatch_image",
    "native_observation_envelope", "native_predispatch_envelope",
    "lease_evidence", "lease_check", "action_intent", "dispatch_receipt",
    "driver_result",
)
POLICY = MappingProxyType({
    "version": VERSION,
    "all_model_slots": ("base", "selected-1", "selected-2", "selected-3", "selected-4", "teacher", "control"),
    "primary_gate": "owned_native_surface_and_current_safe_target",
    "coordinate_target_resolution": "most_specific_native_target_unambiguous_or_reject",
    "targeted_keyboard": "safe_editable_target_then_native_focus_recheck_before_keyboard_io",
    "raster_equality_required": False,
    "raw_observation_and_predispatch_evidence_required": True,
    "lease_check": "fresh_trusted_callback_with_bound_durable_evidence",
    "bindings": ("lease", "task", "package", "step", "one_use_nonce", "ttl"),
    "hard_stop": ("ownership_or_lease_loss", "outside_workspace", "policy_drift", "invalid_evidence"),
    "recovery": "consume_turn_and_nonce_then_new_observation_and_new_sample",
    "retarget_action": False,
    "use_task_answers_or_current_values": False,
    "applied_requires_actual_driver_success": True,
    "nonce_consumption_and_exclusive_intent_before_driver": True,
})


class GuardError(ValueError):
    """A fixed error code; never include private native payloads in errors."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise GuardError("invalid_canonical_data")
        return {key: _plain(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [_plain(item) for item in value]
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise GuardError("invalid_canonical_data")


def canonical(value: Any) -> bytes:
    """Canonical UTF-8 JSON, including frozen policy and validated records."""
    try:
        return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, TypeError):
        raise GuardError("invalid_canonical_data") from None


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


POLICY_SHA = digest(POLICY)


def _row(value: Any, keys: tuple[str, ...], code: str) -> dict:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if type(value) is not dict or set(value) != set(keys):
        raise GuardError(code)
    return value


def _id(value: Any, code: str) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise GuardError(code)
    return value


def _sha(value: Any, code: str) -> str:
    if type(value) is not str or not _SHA.fullmatch(value):
        raise GuardError(code)
    return value


def _number(value: Any, code: str) -> float:
    if type(value) not in (int, float):
        raise GuardError(code)
    try:
        if not math.isfinite(value) or value < 0:
            raise GuardError(code)
    except OverflowError:
        raise GuardError(code) from None
    return float(value)


def _ids(value: Any, code: str) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or not 0 < len(value) <= 512:
        raise GuardError(code)
    result = tuple(_id(item, code) for item in value)
    if len(set(result)) != len(result):
        raise GuardError(code)
    return result


@dataclass(frozen=True)
class ArtifactRef:
    schema: str
    path: str
    sha256: str
    size: int
    kind: str


def validate_artifact_ref(value: Any, *, kind: str | None = None) -> ArtifactRef:
    row = _row(value, ("schema", "path", "sha256", "size", "kind"), "invalid_artifact_ref")
    path = row["path"]
    if (row["schema"] != "native-guard-artifact-ref-v1" or type(path) is not str
            or not path or len(path) > 1024 or "\\" in path or "\x00" in path
            or PurePosixPath(path).is_absolute() or any(part in (".", "..", "") for part in path.split("/"))
            or type(row["size"]) is not int or row["size"] <= 0
            or row["kind"] not in ARTIFACT_KINDS or (kind is not None and row["kind"] != kind)):
        raise GuardError("invalid_artifact_ref")
    _sha(row["sha256"], "invalid_artifact_ref")
    return ArtifactRef(**row)


def verify_artifact(root: Path | str, value: Any) -> ArtifactRef:
    """Reopen evidence without allowing links or paths outside its root."""
    ref = validate_artifact_ref(value)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise GuardError("invalid_artifact_root")
    path = root
    for part in PurePosixPath(ref.path).parts:
        path = path / part
        if path.is_symlink():
            raise GuardError("invalid_artifact_path")
    try:
        if not path.is_file() or path.stat().st_size != ref.size:
            raise GuardError("artifact_mismatch")
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        if sha.hexdigest() != ref.sha256:
            raise GuardError("artifact_mismatch")
    except OSError:
        raise GuardError("artifact_unavailable") from None
    return ref


@dataclass(frozen=True)
class NativeLease:
    schema: str
    lease_id: str
    cell_id: str
    account_sha256: str
    workspace_sha256: str
    window_sha256: str
    owner_sha256: str
    issued_at: float
    expires_at: float
    evidence: ArtifactRef


def validate_lease(value: Any) -> NativeLease:
    row = _row(value, tuple(NativeLease.__dataclass_fields__), "invalid_lease")
    if row["schema"] != "native-surface-lease-v1":
        raise GuardError("invalid_lease")
    for key in ("lease_id", "cell_id"):
        _id(row[key], "invalid_lease")
    for key in ("account_sha256", "workspace_sha256", "window_sha256", "owner_sha256"):
        _sha(row[key], "invalid_lease")
    issued = _number(row["issued_at"], "invalid_lease")
    expires = _number(row["expires_at"], "invalid_lease")
    if expires <= issued:
        raise GuardError("invalid_lease")
    return NativeLease(**{**row, "issued_at": issued, "expires_at": expires,
                          "evidence": validate_artifact_ref(row["evidence"], kind="lease_evidence")})


@dataclass(frozen=True)
class NativeTarget:
    ref: str
    bounds: tuple[int, int, int, int]
    visible: bool
    enabled: bool
    obscured: bool
    keyboard: bool
    actions: tuple[str, ...]


@dataclass(frozen=True)
class NativeEnvelope:
    schema: str
    policy_sha256: str
    phase: str
    lease: NativeLease
    task_id: str
    task_binding_sha256: str
    frame_id: str
    step: int
    captured_at: float
    expires_at: float
    viewport: tuple[int, int]
    view_id: str
    modal_id: str
    focus_id: str
    allowed_views: tuple[str, ...]
    allowed_modals: tuple[str, ...]
    allowed_focus: tuple[str, ...]
    owned_surface: bool
    targets: tuple[NativeTarget, ...]
    raw_image: ArtifactRef
    raw_envelope: ArtifactRef


def validate_envelope(value: Any) -> NativeEnvelope:
    row = _row(value, tuple(NativeEnvelope.__dataclass_fields__), "invalid_envelope")
    if (row["schema"] != "native-surface-envelope-v1" or row["policy_sha256"] != POLICY_SHA
            or row["phase"] not in ("observation", "predispatch")):
        raise GuardError("invalid_envelope")
    for key in ("task_id", "frame_id", "view_id", "modal_id", "focus_id"):
        _id(row[key], "invalid_envelope")
    _sha(row["task_binding_sha256"], "invalid_envelope")
    if type(row["step"]) is not int or row["step"] < 0 or type(row["owned_surface"]) is not bool:
        raise GuardError("invalid_envelope")
    viewport = row["viewport"]
    if (type(viewport) not in (list, tuple) or len(viewport) != 2
            or any(type(item) is not int or not 0 < item <= 32768 for item in viewport)):
        raise GuardError("invalid_envelope")
    captured = _number(row["captured_at"], "invalid_envelope")
    expires = _number(row["expires_at"], "invalid_envelope")
    if expires <= captured:
        raise GuardError("invalid_envelope")
    targets = row["targets"]
    if type(targets) not in (list, tuple) or len(targets) > 512:
        raise GuardError("invalid_envelope")
    checked = []
    for target in targets:
        target = _row(target, tuple(NativeTarget.__dataclass_fields__), "invalid_target")
        _id(target["ref"], "invalid_target")
        bounds = target["bounds"]
        if (type(bounds) not in (list, tuple) or len(bounds) != 4
                or any(type(item) is not int for item in bounds)
                or bounds[0] < 0 or bounds[1] < 0 or bounds[2] <= 0 or bounds[3] <= 0
                or bounds[0] + bounds[2] > viewport[0] or bounds[1] + bounds[3] > viewport[1]
                or any(type(target[key]) is not bool for key in ("visible", "enabled", "obscured", "keyboard"))):
            raise GuardError("invalid_target")
        actions = _ids(target["actions"], "invalid_target")
        if any(action not in ACTION_TYPES for action in actions):
            raise GuardError("invalid_target")
        checked.append(NativeTarget(**{**target, "bounds": tuple(bounds), "actions": actions}))
    if len({target.ref for target in checked}) != len(checked):
        raise GuardError("invalid_target")
    phase = row["phase"]
    lease = validate_lease(row["lease"])
    if not lease.issued_at <= captured < expires <= lease.expires_at:
        raise GuardError("invalid_envelope")
    return NativeEnvelope(**{
        **row, "lease": lease, "viewport": tuple(viewport),
        "captured_at": captured, "expires_at": expires, "targets": tuple(checked),
        "allowed_views": _ids(row["allowed_views"], "invalid_envelope"),
        "allowed_modals": _ids(row["allowed_modals"], "invalid_envelope"),
        "allowed_focus": _ids(row["allowed_focus"], "invalid_envelope"),
        "raw_image": validate_artifact_ref(row["raw_image"], kind=f"raw_{phase}_image"),
        "raw_envelope": validate_artifact_ref(row["raw_envelope"], kind=f"native_{phase}_envelope"),
    })


def validate_lease_check(value: Any, lease: NativeLease) -> dict:
    row = _row(value, ("schema", "lease_sha256", "status", "checked_at", "expires_at", "evidence"), "invalid_lease_check")
    if (row["schema"] != "native-surface-lease-check-v1" or row["lease_sha256"] != digest(lease)
            or row["status"] not in ("active", "inactive")):
        raise GuardError("invalid_lease_check")
    checked = _number(row["checked_at"], "invalid_lease_check")
    expires = _number(row["expires_at"], "invalid_lease_check")
    if expires <= checked or expires > lease.expires_at:
        raise GuardError("invalid_lease_check")
    return {**row, "checked_at": checked, "expires_at": expires,
            "evidence": validate_artifact_ref(row["evidence"], kind="lease_check")}


def _safe_target(target: Any, envelope: NativeEnvelope, kind: str, *, keyboard: bool = False) -> bool:
    if type(target) is not dict:
        return False
    matches = []
    if set(target) == {"ref"} and type(target["ref"]) is str:
        matches = [item for item in envelope.targets if item.ref == target["ref"]]
    elif set(target) == {"x", "y"} and all(type(target[key]) is int for key in ("x", "y")):
        x, y = target["x"], target["y"]
        matches = [item for item in envelope.targets if item.bounds[0] <= x < item.bounds[0] + item.bounds[2]
                   and item.bounds[1] <= y < item.bounds[1] + item.bounds[3]]
        if matches:
            # An owned canvas must not override a disabled or obscured smaller
            # native control. Ambiguous equally specific hit targets fail shut.
            area = min(item.bounds[2] * item.bounds[3] for item in matches)
            matches = [item for item in matches if item.bounds[2] * item.bounds[3] == area]
            if len(matches) != 1:
                return False
    return any(item.visible and item.enabled and not item.obscured and kind in item.actions
               and (not keyboard or item.keyboard) for item in matches)


def decision(observed: Any, current: Any, action: dict, *,
             lease_check: Callable[[NativeLease], dict], now: float | None = None) -> dict:
    """Decide safety for an already syntax-validated, unchanged model action.

    The mandatory callback must inspect the real evaluator-owned lease and save
    its receipt. A bool or an echoed self-declared active field is not accepted.
    A decision cannot prove one-use consumption; the executor owns that ledger.
    """
    obs = validate_envelope(observed)
    cur = validate_envelope(current)
    evidence = {"observation_image": asdict(obs.raw_image), "predispatch_image": asdict(cur.raw_image),
                "observation_envelope": asdict(obs.raw_envelope), "predispatch_envelope": asdict(cur.raw_envelope)}

    def result(status: str, reason: str, check: dict | None = None) -> dict:
        return {"schema": "native-surface-decision-v1", "policy_sha256": POLICY_SHA,
                "status": status, "reason": reason, "observation_sha256": digest(obs),
                "predispatch_sha256": digest(cur), "action_sha256": digest(action),
                "evidence": evidence, "lease_check": _plain(check),
                "consume_turn": True, "invalidate_nonce": True, "driver_called": False}

    if obs.phase != "observation" or cur.phase != "predispatch":
        return result("hard_stop", "invalid_evidence_phase")
    if obs.raw_image.path == cur.raw_image.path or obs.raw_envelope.path == cur.raw_envelope.path:
        return result("hard_stop", "evidence_path_reused")
    if (digest(obs.lease) != digest(cur.lease) or not obs.owned_surface or not cur.owned_surface):
        return result("hard_stop", "ownership_changed")
    if (obs.viewport, obs.allowed_views, obs.allowed_modals, obs.allowed_focus) != (
            cur.viewport, cur.allowed_views, cur.allowed_modals, cur.allowed_focus):
        return result("hard_stop", "policy_scope_changed")
    if not callable(lease_check):
        return result("hard_stop", "invalid_lease_check")
    try:
        check = validate_lease_check(lease_check(cur.lease), cur.lease)
    except Exception:
        return result("hard_stop", "invalid_lease_check")
    tick = _number(time.monotonic() if now is None else now, "invalid_clock")
    if (check["status"] != "active" or not cur.lease.issued_at <= tick <= cur.lease.expires_at
            or not cur.captured_at <= check["checked_at"] <= tick <= check["expires_at"]):
        return result("hard_stop", "lease_inactive_or_stale", check)
    if (cur.view_id not in cur.allowed_views or cur.modal_id not in cur.allowed_modals
            or obs.view_id not in obs.allowed_views or obs.modal_id not in obs.allowed_modals):
        return result("hard_stop", "outside_allowed_surface", check)
    if type(action) is not dict or any(key not in action for key in ("task_id", "task_binding_sha256", "frame_id", "step", "type")):
        return result("rejected", "invalid_action", check)
    if (obs.task_id, obs.task_binding_sha256, obs.frame_id, obs.step) != (
            cur.task_id, cur.task_binding_sha256, cur.frame_id, cur.step):
        return result("rejected", "native_binding_changed", check)
    if (type(action["step"]) is not int or (action["task_id"], action["task_binding_sha256"], action["frame_id"], action["step"]) != (
            obs.task_id, obs.task_binding_sha256, obs.frame_id, obs.step)):
        return result("rejected", "stale_nonce_or_task", check)
    if not obs.captured_at <= cur.captured_at <= tick <= min(obs.expires_at, cur.expires_at):
        return result("rejected", "expired_observation", check)
    if (obs.view_id, obs.modal_id) != (cur.view_id, cur.modal_id):
        return result("rejected", "native_context_changed", check)
    kind = action["type"]
    if type(kind) is not str or kind not in ACTION_TYPES:
        return result("rejected", "invalid_action", check)
    targets = [action[key] for key in ("target", "from", "to") if key in action]
    if ((kind in ("click", "double_click") and "target" not in action)
            or (kind == "drag" and not {"from", "to"} <= set(action))):
        return result("rejected", "invalid_action", check)
    for target in targets:
        if (not _safe_target(target, obs, kind, keyboard=kind in ("type", "key"))
                or not _safe_target(target, cur, kind, keyboard=kind in ("type", "key"))):
            return result("rejected", "target_not_current_and_safe", check)
    if kind in ("type", "key") and "target" not in action:
        if (obs.focus_id != cur.focus_id or cur.focus_id not in cur.allowed_focus
                or not any(item.ref == cur.focus_id and item.keyboard and item.visible and item.enabled
                           and not item.obscured and kind in item.actions for item in cur.targets)):
            return result("rejected", "editable_focus_changed_or_unsafe", check)
    return result("accepted", "owned_surface_and_safe_target", check)


def validate_receipt(value: Any) -> dict:
    """Validate durable execution semantics, never infer success from intent."""
    keys = ("schema", "policy_sha256", "decision_sha256", "action_sha256", "frame_id", "step",
            "status", "reason", "turn_consumed", "nonce_invalidated", "intent", "driver_result", "driver_evidence")
    row = _row(value, keys, "invalid_receipt")
    if (row["schema"] != "native-surface-dispatch-receipt-v1" or row["policy_sha256"] != POLICY_SHA
            or row["status"] not in ("accepted", "rejected", "hard_stop", "applied", "failed")
            or row["turn_consumed"] is not True or row["nonce_invalidated"] is not True
            or type(row["step"]) is not int or row["step"] < 0):
        raise GuardError("invalid_receipt")
    _id(row["frame_id"], "invalid_receipt")
    _id(row["reason"], "invalid_receipt")
    for key in ("decision_sha256", "action_sha256"):
        _sha(row[key], "invalid_receipt")
    intent = None if row["intent"] is None else validate_artifact_ref(row["intent"], kind="action_intent")
    driver = None if row["driver_evidence"] is None else validate_artifact_ref(row["driver_evidence"], kind="driver_result")
    expected = {"accepted": ("not_attempted",), "rejected": ("not_attempted",),
                "hard_stop": ("not_attempted",), "applied": ("succeeded",), "failed": ("failed", "unknown")}
    if row["driver_result"] not in expected[row["status"]] or (
            row["status"] in ("accepted", "applied", "failed") and intent is None):
        raise GuardError("invalid_receipt")
    if row["status"] in ("rejected", "hard_stop") and intent is not None:
        raise GuardError("invalid_receipt")
    if (row["status"] in ("applied", "failed")) != (driver is not None):
        raise GuardError("invalid_receipt")
    return {**row, "intent": intent, "driver_evidence": driver}


def rejection_feedback(value: dict) -> dict[str, str]:
    """Truthful versioned actor feedback for a recoverable rejected decision.

    Legacy Observation construction may need its unchanged enum projection
    first. Replace only that constructed observation's previous result with
    this record before rendering. Hard stops never enter the recovery loop.
    """
    if (type(value) is not dict or value.get("schema") != "native-surface-decision-v1"
            or value.get("policy_sha256") != POLICY_SHA or value.get("status") != "rejected"
            or value.get("reason") not in REJECTION_REASONS or value.get("driver_called") is not False
            or value.get("consume_turn") is not True or value.get("invalidate_nonce") is not True):
        raise GuardError("invalid_rejection_feedback")
    return {"version": FEEDBACK_VERSION, "status": "rejected", "code": value["reason"]}
