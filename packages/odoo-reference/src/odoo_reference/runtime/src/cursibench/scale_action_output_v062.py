"""v0.6.2 model-output boundary with optional bounded memory.

The model returns one minimal GUI action. If it omits memory, the trusted host
copies the current Observation memory (empty on the first turn), then injects
task/frame identity and uses the unchanged strict v0.6 validator. Extra fields,
prose, multiple objects/fences, and non-GUI action paths remain invalid.
"""
from __future__ import annotations

import json
import re

from .scale_action_contract import (
    ContractError, Observation, VERSION as TRUSTED_ACTION_VERSION,
    render_for_proxy, validate_action,
)

OUTPUT_VERSION = 'scale-action-output-v0.6.2'
MODEL_ACTION_CONTRACT = (
    'Return exactly one JSON object with type and only the fields for that GUI '
    'action. Use click {target}, type {target,text,mode:"fill"|"insert"}, '
    'key {key} (optional target), scroll {dx,dy} (optional target), '
    'drag {from,to}, wait {duration_ms}, or finish with no extra fields. '
    'The memory field is optional: if omitted, the trusted runner carries the '
    'current bounded memory forward. A target is exactly {"ref":"visible-ref"} '
    'from current visible controls or integer {"x":0,"y":0} inside the screenshot. '
    'Use one GUI action per turn; finish when done. You have at most five turns. '
    'Do not include version, task ID, hash, step, frame ID, selector, URL, '
    'shell command, application API, file path, or explanatory prose. '
    'Plain JSON is preferred; one exact ```json code fence is also accepted.'
)

_FENCE = re.compile(r'```json\r?\n(?P<body>[\s\S]*?)\r?\n```\Z')
_KIND_FIELDS = {
    'click': frozenset({'target'}),
    'type': frozenset({'target', 'text', 'mode'}),
    'key': frozenset({'key'}),
    'scroll': frozenset({'dx', 'dy'}),
    'drag': frozenset({'from', 'to'}),
    'wait': frozenset({'duration_ms'}),
    'finish': frozenset(),
}


def render_for_model(observation: Observation) -> dict[str, bytes | str]:
    """Keep image/current visible UI; remove identifiers the model needn't copy."""
    base = render_for_proxy(observation)
    instruction = json.dumps({
        'output_version': OUTPUT_VERSION,
        'contract': MODEL_ACTION_CONTRACT,
        'task_instruction': observation.instruction,
        'previous_action_result': observation.previous_action_result,
        'memory': observation.memory,
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if len(instruction.encode('utf-8')) > 16_384:
        raise ContractError('invalid_observation')
    return {'image_bytes': base['image_bytes'], 'instruction': instruction,
            'visible_text': base['visible_text']}


def _parse_one_object(raw: str) -> dict:
    if type(raw) is not str:
        raise ContractError('invalid_action_json')
    try:
        if len(raw.encode('utf-8')) > 65_536:
            raise ContractError('invalid_action_json')
    except UnicodeError:
        raise ContractError('invalid_action_json') from None
    body = raw.strip()
    if body.startswith('```'):
        match = _FENCE.fullmatch(body)
        if match is None:
            raise ContractError('invalid_action_json')
        body = match.group('body')
        if '```' in body:
            raise ContractError('invalid_action_json')
    elif '```' in body:
        raise ContractError('invalid_action_json')

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError('invalid_action_json')
            result[key] = value
        return result

    try:
        parsed = json.loads(body, object_pairs_hook=unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ContractError('invalid_action_json')))
    except (ValueError, TypeError, UnicodeError):
        raise ContractError('invalid_action_json') from None
    if type(parsed) is not dict:
        raise ContractError('invalid_action_json')
    return parsed


def normalize_model_action(raw: str, observation: Observation, *,
                           current_frame_id: str) -> dict:
    """Fill only missing memory and metadata, then validate every action field."""
    payload = _parse_one_object(raw)
    kind = payload.get('type')
    if type(kind) is not str or kind not in _KIND_FIELDS:
        raise ContractError('invalid_action')
    required = {'type'} | _KIND_FIELDS[kind]
    permitted = required | {'memory'} | ({'target'} if kind in ('key', 'scroll') else set())
    if not required <= set(payload) or not set(payload) <= permitted:
        raise ContractError('invalid_action')
    full = {
        'version': TRUSTED_ACTION_VERSION,
        'task_id': observation.task_id,
        'task_binding_sha256': observation.task_binding_sha256,
        'step': observation.step,
        'frame_id': observation.frame_id,
        'memory': observation.memory,
        **payload,
    }
    return validate_action(full, observation, current_frame_id=current_frame_id)
