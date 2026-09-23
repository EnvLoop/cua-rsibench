"""Resolve explicit base/checkpoint inputs without historical workspace files."""
import json
from pathlib import Path

DEFAULT_MODEL='Qwen/Qwen3.5-4B'

def model_input(training_path=None,base=False,model=None):
    training=json.loads(Path(training_path).read_text()) if training_path else None
    if training and model and model!=training['model']:raise ValueError('model does not match training manifest')
    selected=model or (training['model'] if training else DEFAULT_MODEL)
    if base:return {'model':selected,'checkpoint':selected,'inference_kind':'base'}
    if not training:raise ValueError('--training is required for checkpoint evaluation')
    if not training.get('verified_training_and_sampling') or not training.get('checkpoint'):
        raise ValueError('verified training and checkpoint sampling required')
    return dict(training,inference_kind='checkpoint')
