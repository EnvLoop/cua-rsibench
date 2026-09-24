"""v0.6.3 minimal GUI output with bounded, explicit stale-frame resampling.

Output schema and strict validation are exactly the pinned v0.6.2 boundary.
The new version communicates the execution budget and permits the trusted
runner to discard a completed sample only when its observed frame has drifted.
No model-provided field can select a replay or bypass the action validator.
"""
from __future__ import annotations

import json

from .scale_action_contract import ContractError, Observation, render_for_proxy
from .scale_action_output_v062 import normalize_model_action

OUTPUT_VERSION = 'scale-action-output-v0.6.3'
MODEL_ACTION_CONTRACT = (
    'Return exactly one JSON object with type and only the fields for that GUI '
    'action. Use click {target}, type {target,text,mode:"fill"|"insert"}, '
    'key {key} (optional target), scroll {dx,dy} (optional target), '
    'drag {from,to}, wait {duration_ms}, or finish with no extra fields. '
    'Memory is optional; if omitted, the trusted runner carries current bounded '
    'memory forward. A target is exactly {"ref":"visible-ref"} from current '
    'visible controls or integer {"x":0,"y":0} inside the screenshot. '
    'Use one GUI action per turn; finish when done. The pilot permits at most '
    'five applied GUI actions. A changed page frame may cause the trusted runner '
    'to discard a sample and request a new action from a fresh observation; '
    'at most seven samples and two such discards are allowed. '
    'Do not include version, task ID, hash, step, frame ID, selector, URL, '
    'shell command, application API, file path, or explanatory prose. '
    'Plain JSON is preferred; one exact ```json code fence is also accepted.'
)


def render_for_model(observation: Observation) -> dict[str, bytes | str]:
    """Current screenshot/visible controls, task instruction, and prior action only."""
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
