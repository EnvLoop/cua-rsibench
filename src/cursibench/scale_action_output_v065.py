"""Pre-result v0.6.5 cell-neutral minimal GUI output boundary.

This keeps v0.6.4 historical evidence intact. A single top-level ``action``
string is normalized to ``type`` only when ``type`` is absent; every action
field, target, frame, and expiry then goes through the unchanged v0.6.2/full
validator. The same rule applies to base and selected checkpoints in all six
cells. A speculative target-mode rewrite failed a train-only smoke and is not
part of this version. The only prompt change from v0.6.4 removes a literal
dummy control-ref example that the model copied as an action target. It never
converts a missing, stale, or invented control ref to a pixel.
"""

from __future__ import annotations

import json

from .scale_action_contract import ContractError, Observation, render_for_proxy
from .scale_action_output_v064 import MODEL_ACTION_CONTRACT as V064_MODEL_ACTION_CONTRACT
from .scale_action_output_v062 import (
    _parse_one_object, normalize_model_action as _normalize_v062,
)


OUTPUT_VERSION = 'scale-action-output-v0.6.5'
MODEL_ACTION_CONTRACT = V064_MODEL_ACTION_CONTRACT.replace(
    '{"ref":"visible-ref"} from current visible controls',
    'a ref copied verbatim from a visible enabled control in the current controls list (when nonempty)',
)


def render_for_model(observation: Observation) -> dict[str, bytes | str]:
    base = render_for_proxy(observation)
    instruction = json.dumps({
        'output_version': OUTPUT_VERSION,
        'contract': MODEL_ACTION_CONTRACT,
        'max_actions': observation.limits.max_step,
        'task_instruction': observation.instruction,
        'previous_action_result': observation.previous_action_result,
        'memory': observation.memory,
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if len(instruction.encode('utf-8')) > 16_384:
        raise ContractError('invalid_observation')
    return {'image_bytes': base['image_bytes'], 'instruction': instruction,
            'visible_text': base['visible_text']}


def _normalize_one_fence(raw: str) -> str:
    if type(raw) is not str:
        raise ContractError('invalid_action_json')
    candidate = raw.strip()
    if candidate.startswith('```'):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0] == '```' and lines[-1] == '```':
            return '```json\n' + '\n'.join(lines[1:-1]) + '\n```'
    return raw


def normalize_model_action(raw: str, observation: Observation, *,
                           current_frame_id: str) -> dict:
    """Transport-normalize one fence and one unambiguous action-kind alias."""
    payload = _parse_one_object(_normalize_one_fence(raw))
    if 'action' in payload:
        if 'type' in payload or type(payload['action']) is not str:
            raise ContractError('invalid_action')
        payload['type'] = payload.pop('action')
    # Parsing above already rejects duplicate keys, invalid JSON and wrapper
    # prose. Serialize only the parsed object, then use the pinned v0.6.2 path
    # for its exact action schema, target, current frame and expiry checks.
    try:
        normalized = json.dumps(payload, ensure_ascii=False,
                                separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, UnicodeError):
        raise ContractError('invalid_action_json') from None
    return _normalize_v062(normalized, observation,
                           current_frame_id=current_frame_id)
