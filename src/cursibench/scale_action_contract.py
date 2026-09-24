"""v0.6 computer-use observation and action boundary.

The trusted application adapter constructs observations and owns the current
frame ID. Model output is data: this module validates it but never dispatches a
browser, desktop, shell, API, or filesystem operation. A caller must recheck the
current frame ID at dispatch time, including after sampling has completed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import secrets
import time
from typing import Any, Callable


VERSION = 'scale-computer-use-v0.6'
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
_REF = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z')
_ALLOWED_KEYS = frozenset({
    'Enter', 'Tab', 'Shift+Tab', 'Escape', 'Backspace', 'Delete', 'Space',
    'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End',
    'PageUp', 'PageDown', 'Control+A', 'Meta+A', 'Control+S', 'Meta+S',
})
_RESULT_CODES = {
    'applied': frozenset({'ok'}),
    'rejected': frozenset({'target_not_found', 'target_disabled', 'target_obscured',
                           'invalid_action'}),
    'failed': frozenset({'action_timeout', 'environment_error'}),
}
_PUBLIC_ERRORS = frozenset({
    'invalid_observation', 'invalid_image', 'invalid_action_json',
    'invalid_action', 'stale_frame', 'expired_frame', 'sampling_failed',
})

ACTION_CONTRACT = (
    'Return exactly one JSON object with version, task_id, task_binding_sha256, step, frame_id, '
    'type, memory and the fields for that type. Types: click {target}, '
    'type {target,text,mode:"fill"|"insert"}, key {key} (optional target), '
    'scroll {dx,dy} (optional target), drag {from,to}, wait {duration_ms}, '
    'finish {}. A target is exactly {"ref":"visible-ref"} or integer '
    '{"x":0,"y":0} within the current screenshot. Use only current visible '
    'enabled refs. One action per turn. No selectors, URLs, shell commands, '
    'application APIs, or file operations. Preserve concise working memory.'
)


class ContractError(ValueError):
    """Fixed error code safe to expose; do not include private input."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _digest(value: bytes | str) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _text(value: Any, maximum: int, *, required: bool = False,
          code: str = 'invalid_observation') -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise ContractError(code)
    try:
        if len(value.encode('utf-8')) > maximum:
            raise ContractError(code)
    except UnicodeError:
        raise ContractError(code) from None
    return value


def _exact_dict(value: Any, keys: set[str], *, code: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ContractError(code)
    return value


def _identifier(value: Any, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ContractError('invalid_observation')
    return value


def _finite(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class ContractLimits:
    instruction_bytes: int = 8192
    visible_text_bytes: int = 65536
    a11y_text_bytes: int = 16384
    dom_text_bytes: int = 32768
    memory_bytes: int = 4096
    typed_text_bytes: int = 8192
    max_controls: int = 128
    max_step: int = 90
    frame_ttl_seconds: int = 270
    max_wait_ms: int = 2000
    max_scroll_pixels: int = 2000

    def __post_init__(self):
        ceilings = {
            'instruction_bytes': 16384, 'visible_text_bytes': 65536,
            'a11y_text_bytes': 32768, 'dom_text_bytes': 65536,
            'memory_bytes': 6000, 'typed_text_bytes': 16384,
            'max_controls': 512, 'max_step': 10000,
            'frame_ttl_seconds': 300, 'max_wait_ms': 10000,
            'max_scroll_pixels': 10000,
        }
        for name, ceiling in ceilings.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= ceiling:
                raise ContractError('invalid_observation')


@dataclass(frozen=True)
class Control:
    ref: str
    role: str
    label: str
    visible: bool
    enabled: bool

    @classmethod
    def parse(cls, value: Any) -> 'Control':
        row = _exact_dict(value, {'ref', 'role', 'label', 'visible', 'enabled'}, code='invalid_observation')
        ref = _identifier(row['ref'], _REF)
        role = _text(row['role'], 80, required=True)
        label = _text(row['label'], 256)
        if type(row['visible']) is not bool or row['visible'] is not True or type(row['enabled']) is not bool:
            raise ContractError('invalid_observation')
        return cls(ref, role, label, row['visible'], row['enabled'])


@dataclass(frozen=True)
class Observation:
    task_id: str
    task_binding_sha256: str
    instruction: str
    step: int
    screenshot_bytes: bytes = field(repr=False)
    screenshot: dict[str, Any]
    a11y_text: str = field(repr=False)
    dom_text: str = field(repr=False)
    controls: tuple[Control, ...]
    previous_action_result: dict[str, str] | None
    memory: str = field(repr=False)
    frame_id: str
    issued_at: float
    expires_at: float
    limits: ContractLimits = field(repr=False)

    @property
    def modalities(self) -> tuple[str, ...]:
        return ('screenshot',) + (('a11y',) if self.a11y_text else ()) + (('dom',) if self.dom_text else ())


def make_observation(*, task_id: str, task_binding_sha256: str,
                     instruction: str, step: int, screenshot_bytes: bytes,
                     a11y_text: str = '', dom_text: str = '',
                     controls: list[dict] | tuple[dict, ...] = (),
                     previous_action_result: dict[str, str] | None = None,
                     memory: str = '', issued_at: float | None = None,
                     limits: ContractLimits | None = None) -> Observation:
    """Build a task-bound frame from trusted, current UI evidence.

    Screenshot metadata uses the same validator as the image sampling proxy so
    coordinate limits and rendered image bounds agree. The random frame ID
    rotates even when two screenshots happen to have identical pixels.
    """
    limits = limits or ContractLimits()
    _identifier(task_id, _ID)
    if not isinstance(task_binding_sha256, str) or not _HEX64.fullmatch(task_binding_sha256):
        raise ContractError('invalid_observation')
    instruction = _text(instruction, limits.instruction_bytes, required=True)
    a11y_text = _text(a11y_text, limits.a11y_text_bytes)
    dom_text = _text(dom_text, limits.dom_text_bytes)
    memory = _text(memory, limits.memory_bytes)
    if type(step) is not int or not 0 <= step <= limits.max_step:
        raise ContractError('invalid_observation')
    if type(controls) not in (list, tuple) or len(controls) > limits.max_controls:
        raise ContractError('invalid_observation')
    parsed_controls = tuple(Control.parse(row) for row in controls)
    if len({row.ref for row in parsed_controls}) != len(parsed_controls):
        raise ContractError('invalid_observation')
    if step == 0 and previous_action_result is not None:
        raise ContractError('invalid_observation')
    if step > 0:
        result = _exact_dict(previous_action_result, {'status', 'code'}, code='invalid_observation')
        if (type(result['status']) is not str or type(result['code']) is not str
                or result['status'] not in _RESULT_CODES
                or result['code'] not in _RESULT_CODES[result['status']]):
            raise ContractError('invalid_observation')
        previous_action_result = dict(result)
    if issued_at is None:
        issued_at = time.monotonic()
    if not _finite(issued_at) or issued_at < 0:
        raise ContractError('invalid_observation')
    from .scale_vision_proxy import Limits as VisionLimits, ProxyError, image_from_bytes
    try:
        _, screenshot = image_from_bytes(screenshot_bytes, VisionLimits())
    except ProxyError:
        raise ContractError('invalid_image') from None
    observation = Observation(
        task_id=task_id, task_binding_sha256=task_binding_sha256,
        instruction=instruction, step=step, screenshot_bytes=screenshot_bytes,
        screenshot=screenshot, a11y_text=a11y_text, dom_text=dom_text,
        controls=parsed_controls, previous_action_result=previous_action_result,
        memory=memory, frame_id=secrets.token_hex(16), issued_at=float(issued_at),
        expires_at=float(issued_at) + limits.frame_ttl_seconds, limits=limits,
    )
    # Fail at frame construction, before any provider call, if the image/text
    # proxy would reject the serialized turn context.
    render_for_proxy(observation)
    return observation


def render_for_proxy(observation: Observation) -> dict[str, bytes | str]:
    """One stable image-plus-text representation for training and evaluation."""
    if type(observation) is not Observation:
        raise ContractError('invalid_observation')
    instruction = _json_bytes({
        'version': VERSION, 'contract': ACTION_CONTRACT,
        'task_id': observation.task_id,
        'task_binding_sha256': observation.task_binding_sha256,
        'instruction': observation.instruction, 'step': observation.step,
        'frame_id': observation.frame_id,
        'previous_action_result': observation.previous_action_result,
        'memory': observation.memory,
    }).decode('utf-8')
    visible_text = _json_bytes({
        'a11y_text': observation.a11y_text, 'dom_text': observation.dom_text,
        'controls': [vars(control) for control in observation.controls],
        'screenshot': observation.screenshot,
    }).decode('utf-8')
    if (len(instruction.encode('utf-8')) > 16384
            or len(visible_text.encode('utf-8')) > observation.limits.visible_text_bytes):
        raise ContractError('invalid_observation')
    return {'image_bytes': observation.screenshot_bytes,
            'instruction': instruction, 'visible_text': visible_text}


def _strict_json(raw: str | dict) -> dict:
    if type(raw) is dict:
        return raw
    if type(raw) is not str or len(raw.encode('utf-8', errors='ignore')) > 65536:
        raise ContractError('invalid_action_json')

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ContractError('invalid_action_json')
            value[key] = item
        return value

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ContractError('invalid_action_json')))
    except (ValueError, UnicodeError, TypeError):
        raise ContractError('invalid_action_json') from None
    if type(parsed) is not dict:
        raise ContractError('invalid_action_json')
    return parsed


def _target(value: Any, observation: Observation) -> dict:
    if type(value) is not dict:
        raise ContractError('invalid_action')
    if set(value) == {'ref'}:
        ref = value['ref']
        if not isinstance(ref, str):
            raise ContractError('invalid_action')
        control = next((row for row in observation.controls if row.ref == ref), None)
        if control is None or not control.enabled:
            raise ContractError('stale_frame')
        return {'ref': ref}
    if set(value) == {'x', 'y'}:
        x, y = value['x'], value['y']
        if (type(x) is not int or type(y) is not int
                or not 0 <= x < observation.screenshot['width']
                or not 0 <= y < observation.screenshot['height']):
            raise ContractError('invalid_action')
        return {'x': x, 'y': y}
    raise ContractError('invalid_action')


def validate_action(raw: str | dict, observation: Observation, *,
                    current_frame_id: str, now: float | None = None) -> dict:
    """Return a validated action only while this precise frame is still current."""
    if type(observation) is not Observation or type(current_frame_id) is not str:
        raise ContractError('invalid_action')
    now = time.monotonic() if now is None else now
    if not _finite(now):
        raise ContractError('invalid_action')
    if current_frame_id != observation.frame_id:
        raise ContractError('stale_frame')
    if now < observation.issued_at or now > observation.expires_at:
        raise ContractError('expired_frame')
    action = _strict_json(raw)
    common = {'version', 'task_id', 'task_binding_sha256', 'step', 'frame_id', 'type', 'memory'}
    kind = action.get('type')
    extras = {
        'click': {'target'}, 'type': {'target', 'text', 'mode'},
        'key': {'key'}, 'scroll': {'dx', 'dy'},
        'drag': {'from', 'to'}, 'wait': {'duration_ms'}, 'finish': set(),
    }
    if type(kind) is not str or kind not in extras:
        raise ContractError('invalid_action')
    permitted = common | extras[kind] | ({'target'} if kind in ('key', 'scroll') else set())
    required = common | extras[kind]
    if not required <= set(action) or not set(action) <= permitted:
        raise ContractError('invalid_action')
    if (action['version'] != VERSION or action['task_id'] != observation.task_id
            or action['task_binding_sha256'] != observation.task_binding_sha256
            or type(action['step']) is not int or action['step'] != observation.step
            or action['frame_id'] != observation.frame_id):
        raise ContractError('stale_frame')
    _text(action['memory'], observation.limits.memory_bytes, code='invalid_action')
    if kind in ('click', 'type', 'key', 'scroll') and 'target' in action:
        _target(action['target'], observation)
    if kind == 'type':
        if action['mode'] not in ('fill', 'insert'):
            raise ContractError('invalid_action')
        if not isinstance(action['text'], str) or not action['text']:
            raise ContractError('invalid_action')
        try:
            if len(action['text'].encode('utf-8')) > observation.limits.typed_text_bytes:
                raise ContractError('invalid_action')
        except UnicodeError:
            raise ContractError('invalid_action') from None
    elif kind == 'key':
        if type(action['key']) is not str or action['key'] not in _ALLOWED_KEYS:
            raise ContractError('invalid_action')
    elif kind == 'scroll':
        dx, dy = action['dx'], action['dy']
        bound = observation.limits.max_scroll_pixels
        if (type(dx) is not int or type(dy) is not int or not -bound <= dx <= bound
                or not -bound <= dy <= bound or dx == dy == 0):
            raise ContractError('invalid_action')
    elif kind == 'drag':
        _target(action['from'], observation)
        _target(action['to'], observation)
        if action['from'] == action['to']:
            raise ContractError('invalid_action')
    elif kind == 'wait':
        duration = action['duration_ms']
        if type(duration) is not int or not 1 <= duration <= observation.limits.max_wait_ms:
            raise ContractError('invalid_action')
    return action


def sample_and_validate_action(adapter: Any, observation: Observation, *,
                               request_id: str,
                               current_frame_id: Callable[[], str]) -> tuple[dict, dict]:
    """Bridge the vision proxy and this contract without dispatching actions.

    The trusted runner supplies a live frame-ID getter. It must rotate that ID
    whenever its current UI state changes, then recheck it again immediately
    before any actual UI dispatch.
    """
    if not callable(current_frame_id):
        raise ContractError('invalid_action')
    if current_frame_id() != observation.frame_id:
        raise ContractError('stale_frame')
    if time.monotonic() > observation.expires_at:
        raise ContractError('expired_frame')
    request = render_for_proxy(observation)
    result = adapter.sample(request_id=request_id, **request)
    if type(result) is not dict or result.get('status') != 'completed' or type(result.get('text')) is not str:
        raise ContractError('sampling_failed')
    action = validate_action(result['text'], observation, current_frame_id=current_frame_id())
    return action, result


def public_receipt(observation: Observation, *, action: dict | None = None,
                   error: ContractError | None = None) -> dict:
    """An allowlisted log record; excludes instruction, UI text and typed data."""
    if type(observation) is not Observation:
        raise ContractError('invalid_observation')
    if action is not None:
        action = validate_action(action, observation, current_frame_id=observation.frame_id,
                                 now=observation.issued_at)
    if error is not None and (type(error) is not ContractError or error.code not in _PUBLIC_ERRORS):
        raise ContractError('invalid_action')
    return {
        'version': VERSION, 'task_binding_sha256': observation.task_binding_sha256,
        'task_id_sha256': _digest(observation.task_id), 'step': observation.step,
        'frame_id_sha256': _digest(observation.frame_id),
        'modalities': list(observation.modalities),
        'screenshot': dict(observation.screenshot),
        'a11y_sha256': _digest(observation.a11y_text),
        'dom_sha256': _digest(observation.dom_text),
        'memory_sha256': _digest(observation.memory),
        'control_count': len(observation.controls),
        'previous_action_status': (observation.previous_action_result or {}).get('status'),
        'action_type': action['type'] if action else None,
        'error_code': error.code if error else None,
    }
