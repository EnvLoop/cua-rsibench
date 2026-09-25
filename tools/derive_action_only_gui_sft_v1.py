"""Derive action-only training inputs from an immutable admitted GUI trace.

The deterministic teacher supplied host memory between actions, but its
executed assistant JSON omitted that optional field. This derivation removes
host memory from model-facing observations. It does not alter action bytes,
masked frame bytes, action order, evaluator evidence, or saved-state checks.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

from cursibench.gui_sft_data_v1 import (
    SCHEMA, TRAIN_TASK_ID, TRAIN_TEMPLATE_ID, validate_episode,
)


ROOT = Path(__file__).resolve().parents[1]
PINNED_ORIGINAL_EPISODE_SHA256 = '1105c4cd44fdb0bf2a5cc6c1e21211c215f0eae4a2e10f30cecd09684598abfe'
PINNED_ORIGINAL_RESULT_SHA256 = 'e29456cfc5ddcb97e4e001271024bde9a40d31de59eac68aad92d26fcf191657'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')
    path.chmod(0o600)


def derive(source: Path, out: Path) -> dict:
    source, out = Path(source).resolve(), Path(out).resolve()
    if not source.is_relative_to(ROOT / 'work') or \
            not out.is_relative_to(ROOT / 'work') or out.exists():
        raise ValueError('private_source_and_fresh_output_required')
    original_bytes = (source / 'episode.json').read_bytes()
    result_bytes = (source / 'result.json').read_bytes()
    if sha(original_bytes) != PINNED_ORIGINAL_EPISODE_SHA256 or \
            sha(result_bytes) != PINNED_ORIGINAL_RESULT_SHA256:
        raise ValueError('pinned_admitted_original_changed')
    original = json.loads(original_bytes)
    result = json.loads(result_bytes)
    if (original.get('schema') != SCHEMA or original.get('task_id') != TRAIN_TASK_ID or
            original.get('intent_template_id') != TRAIN_TEMPLATE_ID or
            result.get('status') != 'completed' or
            result.get('episode_admitted') is not True or
            result.get('official_score') != 1.0 or
            result.get('independent_saved_state_pass') is not True or
            result.get('final_reset_verified') is not True or
            result.get('paid_provider_calls') != 0 or
            result.get('episode_sha256') != PINNED_ORIGINAL_EPISODE_SHA256 or
            len(original.get('steps', [])) != 36):
        raise ValueError('original_admission_not_verified')
    out.mkdir(mode=0o700, parents=True)
    (out / 'frames').mkdir(mode=0o700)
    derived = copy.deepcopy(original)
    for index, (old, new) in enumerate(zip(original['steps'], derived['steps'])):
        if old.get('step') != index or old.get('action') != new.get('action') or \
                'memory' in old['action']:
            raise ValueError('executed_action_changed')
        relative = old['screenshot_file']
        if relative != f'frames/step-{index:03d}.png':
            raise ValueError('unexpected_frame_path')
        image = (source / relative).read_bytes()
        if sha(image) != old['screenshot_sha256']:
            raise ValueError('original_frame_hash_mismatch')
        path = out / relative
        shutil.copyfile(source / relative, path)
        path.chmod(0o600)
        new['observation']['memory'] = ''
    derived['derivation'] = {
        'kind': 'action_only_host_memory_removed',
        'original_episode_sha256': PINNED_ORIGINAL_EPISODE_SHA256,
        'original_result_sha256': PINNED_ORIGINAL_RESULT_SHA256,
        'executed_actions_and_masked_frames_unchanged': True,
        'host_memory_used_as_assistant_target': False,
    }
    write_new(out / 'episode.json', derived)
    new_result = copy.deepcopy(result)
    new_result['episode_sha256'] = sha((out / 'episode.json').read_bytes())
    new_result['derivation'] = derived['derivation']
    write_new(out / 'result.json', new_result)
    _, turns = validate_episode(out)
    if [turn['action'] for turn in turns] != [step['action'] for step in original['steps']]:
        raise ValueError('validated_actions_changed')
    return {'schema': 'gui-sft-action-only-derivation-v1',
            'source_episode_sha256': PINNED_ORIGINAL_EPISODE_SHA256,
            'derived_episode_sha256': new_result['episode_sha256'],
            'validated_turns': len(turns),
            'masked_frames_unchanged': True,
            'executed_actions_unchanged': True,
            'host_memory_omitted': True,
            'paid_provider_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.source, args.out), sort_keys=True))
