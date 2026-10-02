"""v0.6.4 cell-neutral minimal GUI output for the full study.

Only a single whole-response unlabeled JSON fence is additionally normalized
to the pinned v0.6.2 minimal-action validator. The older v0.6.2/v0.6.3
interfaces retain their historical parsing behavior and evidence hashes.
"""

from __future__ import annotations

import json

from .scale_action_contract import ContractError, Observation, render_for_proxy
from .scale_action_output_v062 import normalize_model_action as _normalize_v062


OUTPUT_VERSION = 'scale-action-output-v0.6.4'
MODEL_ACTION_CONTRACT = (
    'Return exactly one JSON object with type and only the fields for that GUI '
    'action. Use click {target}, type {target,text,mode:"fill"|"insert"}, '
    'key {key} (optional target), scroll {dx,dy} (optional target), '
    'drag {from,to}, wait {duration_ms}, or finish with no extra fields. '
    'Memory is optional; if omitted, the trusted runner carries current bounded '
    'memory forward. A target is exactly {"ref":"visible-ref"} from current '
    'visible controls or integer {"x":0,"y":0} inside the screenshot. '
    'Use one GUI action per turn and finish when done. '
    'Do not include version, task ID, hash, step, frame ID, selector, URL, '
    'shell command, application API, file path, or explanatory prose. '
    'Plain JSON is preferred. Exactly one whole-response ```json or unlabeled '
    '``` code fence is also accepted; no surrounding prose or second block.'
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


def normalize_model_action(raw: str, observation: Observation, *,
                           current_frame_id: str) -> dict:
    """Normalize only one unlabeled fence, then reuse the strict v0.6.2 path."""
    if type(raw) is not str:
        raise ContractError('invalid_action_json')
    candidate = raw.strip()
    if candidate.startswith('```'):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0] == '```' and lines[-1] == '```':
            raw = '```json\n' + '\n'.join(lines[1:-1]) + '\n```'
    return _normalize_v062(raw, observation,
                           current_frame_id=current_frame_id)
