"""Train-only, real-screen GUI examples for the Qwen3.8 computer-use student.

An episode is private local evidence. No datum is returned until the recorded
GUI save, independent state check, official evaluator and reset all agree.
This module never calls a model service or dispatches a browser action.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess

from .scale_action_contract import ContractLimits, make_observation
from .scale_action_output_v062 import normalize_model_action
from .scale_action_contract import render_for_proxy
from .scale_vision_proxy import MODEL, PROCESSOR, RENDERER, QwenVisionRenderer


SCHEMA = 'gui-sft-episode-v1'
SOURCE_COMMIT = '6473f72db5dcefc97b5725b59e734504edc28a21'
SOURCE_DATA_SHA256 = 'd65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30'
TRAIN_TASK_ID = 777
TRAIN_TEMPLATE_ID = 742
EXPOSED_FAILED_TASK_IDS = (486, 538)
MAX_ACTIONS = 40
MAX_TOKENS = 32_768
COOKBOOK_COMMIT = '1e53aa3d1cdd6389b3290c2574641eccc0503242'

TRAIN_ACTION_CONTRACT = (
    'Return exactly one JSON object with one GUI action. Types: click {target}, '
    'type {target,text,mode:"fill"|"insert"}, key {key} (optional target), '
    'scroll {dx,dy} (optional target), drag {from,to}, wait {duration_ms}, '
    'finish {}. Memory is optional. A target is exactly {"ref":"visible-ref"} '
    'from current visible controls or integer {"x":0,"y":0} inside the '
    'screenshot. Use only the current screenshot and controls. Do not include '
    'a URL, selector, shell command, application API, file path, frame ID, or '
    'explanatory prose. The host permits at most 40 GUI actions.'
)


class DataGateError(ValueError):
    """A fixed subtype safe for the public receipt."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def train_exclusion_manifest() -> dict:
    return {
        'schema': 'gui-sft-train-exclusion-v1',
        'source': 'WebArena-Verified',
        'source_commit': SOURCE_COMMIT,
        'source_dataset_sha256': SOURCE_DATA_SHA256,
        'site': 'shopping_admin',
        'train_only_task_ids': [TRAIN_TASK_ID],
        'train_only_intent_template_ids': [TRAIN_TEMPLATE_ID],
        'train_only_entity_tags': [f'magento:product:{entity_id}'
                                   for entity_id in (111, 114, 117, 120, 123)],
        'other_exposed_unadmitted_task_ids': list(EXPOSED_FAILED_TASK_IDS),
        'rule': 'Quarantine task 777, full template 742 and overlapping products from final. Pre-training task 777 diagnostics are historical and never a post-training held-out score.',
    }


def _check_episode(episode: dict) -> None:
    if (type(episode) is not dict or episode.get('schema') != SCHEMA or
            episode.get('split') != 'train' or episode.get('source_commit') != SOURCE_COMMIT or
            episode.get('source_dataset_sha256') != SOURCE_DATA_SHA256 or
            episode.get('task_id') != TRAIN_TASK_ID or
            episode.get('intent_template_id') != TRAIN_TEMPLATE_ID or
            episode.get('site') != 'shopping_admin' or
            episode.get('entity_tags') != [f'magento:product:{entity_id}'
                                           for entity_id in (111, 114, 117, 120, 123)]):
        raise DataGateError('invalid_train_source')
    evidence = episode.get('admission')
    if (type(evidence) is not dict or evidence.get('published_evaluator_score') != 1.0 or
            evidence.get('independent_saved_state_pass') is not True or
            evidence.get('reset_verified') is not True or
            evidence.get('search_index_reset_verified') is not True or
            evidence.get('native_save_count') != 5 or
            evidence.get('raw_and_sanitized_evaluator_equal') is not True):
        raise DataGateError('state_or_evaluator_not_admitted')
    steps = episode.get('steps')
    if type(steps) is not list or not 1 <= len(steps) <= MAX_ACTIONS:
        raise DataGateError('invalid_step_count')
    if any(type(step) is not dict or step.get('step') != index
           for index, step in enumerate(steps)):
        raise DataGateError('nonsequential_steps')
    if any(step.get('action', {}).get('type') == 'finish' for step in steps[:-1]):
        raise DataGateError('premature_finish')
    if steps[-1].get('action', {}).get('type') != 'finish':
        raise DataGateError('missing_terminal_action')


def _frame_path(root: Path, relative: str) -> Path:
    if (type(relative) is not str or not relative.startswith('frames/step-') or
            not relative.endswith('.png') or '/' in relative[len('frames/'):]):
        raise DataGateError('invalid_frame_path')
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise DataGateError('invalid_frame_path')
    return path


def validate_episode(episode_dir: Path) -> tuple[dict, list[dict]]:
    """Rebuild current-frame observations and validate every normalized action."""
    root = Path(episode_dir).resolve()
    episode_bytes = (root / 'episode.json').read_bytes()
    episode = json.loads(episode_bytes)
    _check_episode(episode)
    result = json.loads((root / 'result.json').read_text())
    if (type(result) is not dict or result.get('status') != 'completed' or
            result.get('episode_admitted') is not True or
            result.get('final_reset_verified') is not True or
            result.get('independent_saved_state_pass') is not True or
            result.get('reset_verified') is not True or
            result.get('official_score') != 1.0 or
            result.get('paid_provider_calls') != 0 or
            result.get('episode_sha256') != sha256(episode_bytes) or
            result.get('task_id') != TRAIN_TASK_ID or
            result.get('intent_template_id') != TRAIN_TEMPLATE_ID or
            result.get('action_count') != len(episode['steps']) or
            result.get('screenshot_count') != len(episode['steps']) or
            result.get('source', {}).get('git_commit') != SOURCE_COMMIT):
        raise DataGateError('recorder_result_not_admitted')
    validated = []
    for index, step in enumerate(episode['steps']):
        image = _frame_path(root, step.get('screenshot_file')).read_bytes()
        if sha256(image) != step.get('screenshot_sha256'):
            raise DataGateError('screenshot_hash_mismatch')
        observation_data = step.get('observation')
        if type(observation_data) is not dict:
            raise DataGateError('invalid_observation')
        if observation_data.get('task_id') != 'webarena.shopping_admin.777':
            raise DataGateError('task_binding_mismatch')
        if index > 0:
            prior = episode['steps'][index - 1]
            expected_memory = prior['action'].get(
                'memory', prior['observation']['memory'])
            if observation_data.get('memory') != expected_memory:
                raise DataGateError('memory_chain_mismatch')
        observation = make_observation(
            task_id=observation_data['task_id'],
            task_binding_sha256=observation_data['task_binding_sha256'],
            instruction=observation_data['instruction'], step=index,
            screenshot_bytes=image, a11y_text=observation_data['a11y_text'],
            dom_text=observation_data['dom_text'], controls=observation_data['controls'],
            previous_action_result=observation_data['previous_action_result'],
            memory=observation_data['memory'], limits=ContractLimits(max_step=MAX_ACTIONS),
        )
        minimal = step.get('action')
        if type(minimal) is not dict:
            raise DataGateError('invalid_action')
        raw = json_text(minimal)
        normalized = normalize_model_action(raw, observation,
                                             current_frame_id=observation.frame_id)
        allowed = {'type', 'memory', 'target', 'text', 'mode', 'key', 'dx', 'dy',
                   'from', 'to', 'duration_ms'}
        if not set(minimal) <= allowed:
            raise DataGateError('private_action_fields')
        if normalized['type'] != minimal['type']:
            raise DataGateError('action_mismatch')
        validated.append({'observation': observation, 'action': minimal,
                          'normalized': normalized})
    return episode, validated


def render_model_turn(observation) -> dict:
    """Use the deployed image/text envelope and its strict minimal action type."""
    base = render_for_proxy(observation)
    instruction = json_text({
        'output_version': 'gui-sft-output-v1',
        'contract': TRAIN_ACTION_CONTRACT,
        'task_instruction': observation.instruction,
        'previous_action_result': observation.previous_action_result,
        'memory': observation.memory,
    })
    if len(instruction.encode()) > 16_384:
        raise DataGateError('instruction_limit')
    return {'image_bytes': base['image_bytes'], 'instruction': instruction,
            'visible_text': base['visible_text']}


@dataclass(frozen=True)
class OfflineSftResult:
    datums: list
    prompts: list
    receipt: dict
    stop_sequences: list
    supervised_token_lengths: list[int]
    prompt_token_lengths: list[int]


def pinned_cookbook_commit() -> str:
    import tinker_cookbook
    source = Path(tinker_cookbook.__file__).resolve().parents[1]
    try:
        commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, check=True,
                                timeout=10).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(source), 'status', '--porcelain',
                                '--', 'tinker_cookbook'],
                               capture_output=True, text=True, check=True,
                               timeout=10).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        raise DataGateError('cookbook_revision_unverified') from None
    if commit != COOKBOOK_COMMIT or dirty:
        raise DataGateError('cookbook_revision_mismatch')
    return commit


def build_tinker_datums(episode_dir: Path, *, renderer=None) -> OfflineSftResult:
    """Construct real GUI image+action datums locally; no provider calls."""
    from PIL import Image
    from tinker_cookbook.renderers import ImagePart, Message, TextPart
    from tinker_cookbook.supervised.data import datum_from_model_input_weights
    import io

    episode, turns = validate_episode(episode_dir)
    cookbook_commit = pinned_cookbook_commit()
    vision = renderer or QwenVisionRenderer.load()
    if vision.identity['model'] != MODEL or vision.identity['renderer'] != RENDERER or \
            vision.identity['image_processor'] != PROCESSOR:
        raise DataGateError('renderer_identity_mismatch')
    datums, prompts, counts = [], [], []
    for turn in turns:
        request = render_model_turn(turn['observation'])
        with Image.open(io.BytesIO(request['image_bytes'])) as raw_image:
            image = raw_image.convert('RGB')
        user = Message(role='user', content=[
            ImagePart(type='image', image=image),
            TextPart(type='text', text=json_text({
                'instruction': request['instruction'],
                'visible_text': request['visible_text']}))])
        assistant = Message(role='assistant', content=json_text(turn['action']))
        model_input, weights = vision.renderer.build_supervised_example([user, assistant])
        prompt = vision.renderer.build_generation_prompt([user])
        images = [chunk for chunk in model_input.chunks if type(chunk).__name__ == 'ImageChunk']
        prompt_images = [chunk for chunk in prompt.chunks if type(chunk).__name__ == 'ImageChunk']
        weight_sum = float(weights.sum().item())
        if len(images) != 1 or len(prompt_images) != 1 or weight_sum <= 0:
            raise DataGateError('missing_image_or_assistant_loss')
        if model_input.length > MAX_TOKENS or prompt.length >= model_input.length:
            raise DataGateError('rendered_token_limit')
        datum = datum_from_model_input_weights(model_input, weights,
                                               max_length=MAX_TOKENS, reduction='none')
        datums.append(datum)
        prompts.append(prompt)
        counts.append({'input_tokens': model_input.length,
                       'image_tokens': images[0].length,
                       'assistant_loss_weight_sum': weight_sum})
    receipt = {
        'schema': 'gui-sft-offline-render-v1', 'model': MODEL,
        'renderer': RENDERER, 'image_processor': PROCESSOR,
        'renderer_identity': vision.identity,
        'cookbook_commit': cookbook_commit,
        'tinker_sdk_version': importlib.metadata.version('tinker'),
        'source_commit': SOURCE_COMMIT, 'source_dataset_sha256': SOURCE_DATA_SHA256,
        'train_task_id': TRAIN_TASK_ID, 'train_template_id': TRAIN_TEMPLATE_ID,
        'train_only': True, 'episode_sha256': sha256((Path(episode_dir) / 'episode.json').read_bytes()),
        'step_count': len(turns), 'datum_count': len(datums),
        'min_assistant_loss_weight_sum': min(row['assistant_loss_weight_sum'] for row in counts),
        'max_supervised_tokens': max(row['input_tokens'] for row in counts),
        'max_image_tokens': max(row['image_tokens'] for row in counts),
        'first_supervised_tokens': counts[0]['input_tokens'],
        'first_prompt_tokens': prompts[0].length,
        'paid_provider_calls': 0, 'checkpoint_trained': False,
        'student_improvement_claimed': False,
    }
    return OfflineSftResult(datums, prompts, receipt,
                            list(vision.renderer.get_stop_sequences()),
                            [row['input_tokens'] for row in counts],
                            [prompt.length for prompt in prompts])
