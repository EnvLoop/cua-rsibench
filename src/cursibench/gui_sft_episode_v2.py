"""Cell-neutral, fail-closed GUI SFT episode and offline Qwen vision renderer.

The actor sees only a current masked screenshot, visible controls, task text,
previous GUI-action status, and optional self-generated memory. Evaluator
receipts and selection/final manifests stay outside the actor prompt. This
module validates data and constructs datums; it never dispatches GUI or paid
model calls.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import subprocess

from .scale_action_contract import ContractLimits, make_observation, render_for_proxy
from .scale_action_output_v062 import normalize_model_action
from .scale_vision_proxy import MODEL, PROCESSOR, RENDERER, QwenVisionRenderer


SCHEMA = 'gui-sft-episode-v2'
SPLIT_SCHEMA = 'gui-sft-split-manifest-v2'
GATE_SCHEMA = 'gui-sft-gate-receipt-v2'
COOKBOOK_COMMIT = '1e53aa3d1cdd6389b3290c2574641eccc0503242'
ACTION_VERSION = 'scale-computer-use-v0.6'
OUTPUT_VERSION = 'gui-sft-output-v1'
MAX_ACTIONS = 90
MAX_TOKENS = 32_768
CELLS = frozenset({
    'magento_admin', 'gitlab_project', 'odoo_erp',
    'office_excel_web', 'office_powerpoint_web', 'libreoffice_desktop',
})
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}\Z')
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_GATE_KINDS = {
    'positive': ('published_evaluator', 1.0),
    'negative': ('negative_control', 0.0),
    'saved_state': ('independent_readback', None),
    'reset': ('state_equivalence', None),
}

# The GUI action grammar is unchanged from v1. The v2 source/split and oracle
# metadata are outside the model-facing request; the action ceiling is 90.
TRAIN_ACTION_CONTRACT = (
    'Return exactly one JSON object with one GUI action. Types: click {target}, '
    'type {target,text,mode:"fill"|"insert"}, key {key} (optional target), '
    'scroll {dx,dy} (optional target), drag {from,to}, wait {duration_ms}, '
    'finish {}. Memory is optional. A target is exactly {"ref":"visible-ref"} '
    'from current visible controls or integer {"x":0,"y":0} inside the '
    'screenshot. Use only the current screenshot and controls. Do not include '
    'a URL, selector, shell command, application API, file path, frame ID, or '
    'explanatory prose. The host permits at most 90 GUI actions.'
)


class EpisodeGateError(ValueError):
    """A fixed subtype; never include actor or private verifier text."""


def _require(value, code):
    if not value:
        raise EpisodeGateError(code)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _identifier(value) -> bool:
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


def _hash(value) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _tags(value) -> list[str]:
    _require(type(value) is list and value and all(_identifier(item) for item in value),
             'invalid_entity_tags')
    _require(value == sorted(set(value)), 'entity_tags_not_canonical')
    return value


def _safe_relative(root: Path, value: str, prefix: str, suffix: str) -> Path:
    _require(type(value) is str and value.startswith(prefix) and
             value.endswith(suffix) and '/' not in value[len(prefix):] and
             '\\' not in value, 'invalid_relative_path')
    path = root / value
    _require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
             'invalid_relative_path')
    _require(path.is_file(), 'missing_private_artifact')
    return path


def _source(value) -> dict:
    _require(type(value) is dict and
             set(value) == {'name', 'revision', 'dataset_sha256', 'task_id',
                            'template_id', 'task_sha256', 'entity_tags',
                            'observation_task_id'},
             'invalid_source')
    _require(all(_identifier(value[key]) for key in
                 ('name', 'revision', 'task_id', 'template_id',
                  'observation_task_id')) and
             _hash(value['dataset_sha256']) and _hash(value['task_sha256']),
             'invalid_source')
    _tags(value['entity_tags'])
    return value


def _source_binding(source: dict, cell: str) -> str:
    return sha256(json_text({'cell': cell, 'source': source}).encode())


def _manifest(path: Path, *, expected_split: str, cell: str, source: dict) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    manifest = json.loads(raw)
    _require(type(manifest) is dict and manifest.get('schema') == SPLIT_SCHEMA and
             manifest.get('split') == expected_split and
             manifest.get('cell') == cell and
             manifest.get('source_name') == source['name'] and
             manifest.get('source_revision') == source['revision'] and
             manifest.get('source_dataset_sha256') == source['dataset_sha256'] and
             manifest.get('status') in ('provisional', 'frozen') and
             manifest.get('entity_coverage') in ('complete', 'declared_hints_only'),
             'split_manifest_mismatch')
    items = manifest.get('items')
    _require(type(items) is list and items, 'empty_split_manifest')
    for item in items:
        _require(type(item) is dict and set(item) ==
                 {'task_id', 'template_id', 'entity_tags'} and
                 _identifier(item['task_id']) and _identifier(item['template_id']),
                 'invalid_split_item')
        if item['entity_tags']:
            _tags(item['entity_tags'])
        else:
            _require(item['entity_tags'] == [], 'invalid_split_item')
    _require(len({row['task_id'] for row in items}) == len(items),
             'duplicate_split_task')
    return manifest, sha256(raw)


def validate_split_exclusion(source: dict, cell: str,
                             selection_path: Path, final_path: Path) -> dict:
    selection, selection_hash = _manifest(selection_path, expected_split='selection',
                                          cell=cell, source=source)
    final, final_hash = _manifest(final_path, expected_split='final',
                                 cell=cell, source=source)
    rows = selection['items'] + final['items']
    task_ids = {row['task_id'] for row in rows}
    templates = {row['template_id'] for row in rows}
    entities = {tag for row in rows for tag in row['entity_tags']}
    _require(source['task_id'] not in task_ids,
             'train_task_in_evaluation_split')
    _require(source['template_id'] not in templates,
             'train_template_in_evaluation_split')
    _require(not set(source['entity_tags']) & entities,
             'train_entity_in_evaluation_split')
    _require({row['task_id'] for row in selection['items']}.isdisjoint(
        row['task_id'] for row in final['items']), 'selection_final_task_overlap')
    _require({row['template_id'] for row in selection['items']}.isdisjoint(
        row['template_id'] for row in final['items']),
        'selection_final_template_overlap')
    _require({tag for row in selection['items']
              for tag in row['entity_tags']}.isdisjoint(
                  tag for row in final['items']
                  for tag in row['entity_tags']),
             'selection_final_declared_entity_overlap')
    return {
        'selection_sha256': selection_hash, 'final_sha256': final_hash,
        'selection_count': len(selection['items']),
        'final_count': len(final['items']),
        'selection_status': selection['status'],
        'final_status': final['status'],
        'entity_coverage': [selection['entity_coverage'], final['entity_coverage']],
        'train_source_task_template_and_declared_entities_disjoint': True,
        'selection_final_task_template_disjoint': True,
        'selection_final_declared_entities_disjoint': True,
        'official_final_admitted': False if final['status'] == 'provisional' else None,
    }


def _receipt(root: Path, gate: str, reference: dict,
             cell: str, source: dict) -> dict:
    _require(type(reference) is dict and set(reference) == {'path', 'sha256'} and
             _hash(reference['sha256']), 'invalid_gate_reference')
    path = _safe_relative(root, reference['path'], 'receipts/', '.json')
    raw = path.read_bytes()
    _require(sha256(raw) == reference['sha256'], 'gate_receipt_hash_mismatch')
    data = json.loads(raw)
    expected_kind, expected_score = _GATE_KINDS[gate]
    _require(type(data) is dict and data.get('schema') == GATE_SCHEMA and
             data.get('gate') == gate and data.get('cell') == cell and
             data.get('source_binding_sha256') == _source_binding(source, cell) and
             data.get('verifier_kind') == expected_kind and
             data.get('status') == 'pass' and
             data.get('independent_of_actor') is True and
             _hash(data.get('source_artifact_sha256')) and
             type(data.get('source_artifact_path')) is str,
             'gate_provenance_invalid')
    source_artifact = _safe_relative(root, data['source_artifact_path'],
                                     'receipts/source-', '.json')
    _require(sha256(source_artifact.read_bytes()) ==
             data['source_artifact_sha256'],
             'source_artifact_hash_mismatch')
    if expected_score is not None:
        _require(data.get('score') == expected_score,
                 'gate_score_invalid')
    if gate == 'negative':
        _require(_identifier(data.get('control_kind')) and
                 data.get('independent_state_control_pass') is True,
                 'negative_control_not_independent')
    if gate == 'saved_state':
        _require(data.get('target_state_pass') is True and
                 data.get('unintended_state_preserved') is True,
                 'saved_state_not_admitted')
    if gate == 'reset':
        _require(data.get('state_equivalence_pass') is True and
                 data.get('business_state_rows_match_baseline') is True and
                 _hash(data.get('baseline_semantic_sha256')) and
                 data.get('restored_semantic_sha256') ==
                 data.get('baseline_semantic_sha256'),
                 'reset_not_equivalent')
    return data


def _observation(root: Path, step: dict, index: int,
                 source: dict, cell: str):
    _require(type(step) is dict and
             set(step) == {'step', 'screenshot_file', 'screenshot_sha256',
                           'observation', 'action'} and
             step.get('step') == index,
             'nonsequential_steps')
    relative = step.get('screenshot_file')
    _require(relative == f'frames/step-{index:03d}.png', 'frame_name_mismatch')
    image = _safe_relative(root, relative, 'frames/', '.png').read_bytes()
    _require(sha256(image) == step.get('screenshot_sha256'),
             'frame_hash_mismatch')
    row = step.get('observation')
    _require(type(row) is dict and
             set(row) == {'task_id', 'task_binding_sha256', 'instruction',
                          'a11y_text', 'dom_text', 'controls',
                          'previous_action_result', 'memory'} and
             row.get('task_id') == source['observation_task_id'] and
             _hash(row.get('task_binding_sha256')),
             'observation_task_binding_mismatch')
    return make_observation(
        task_id=row['task_id'], task_binding_sha256=row['task_binding_sha256'],
        instruction=row['instruction'], step=index, screenshot_bytes=image,
        a11y_text=row['a11y_text'], dom_text=row['dom_text'],
        controls=row['controls'],
        previous_action_result=row['previous_action_result'],
        memory=row['memory'], limits=ContractLimits(max_step=MAX_ACTIONS))


def validate_episode(episode_dir: Path, *, selection_manifest: Path,
                     final_manifest: Path) -> tuple[dict, list[dict], dict]:
    root = Path(episode_dir).resolve()
    raw = (root / 'episode.json').read_bytes()
    episode = json.loads(raw)
    _require(type(episode) is dict and episode.get('schema') == SCHEMA and
             episode.get('split') == 'train' and episode.get('cell') in CELLS and
             episode.get('action_contract_version') == ACTION_VERSION and
             episode.get('renderer') == {'model': MODEL, 'name': RENDERER,
                                          'image_processor': PROCESSOR},
             'invalid_episode_header')
    cell = episode['cell']
    source = _source(episode.get('source'))
    split = validate_split_exclusion(source, cell, selection_manifest,
                                     final_manifest)
    refs = episode.get('provenance_receipts')
    _require(type(refs) is dict and set(refs) == set(_GATE_KINDS),
             'missing_gate_receipts')
    gates = {name: _receipt(root, name, refs[name], cell, source)
             for name in _GATE_KINDS}
    steps = episode.get('steps')
    _require(type(steps) is list and 1 <= len(steps) <= MAX_ACTIONS,
             'invalid_step_count')
    result = json.loads((root / 'result.json').read_text())
    _require(type(result) is dict and result.get('status') == 'completed' and
             result.get('episode_sha256') == sha256(raw) and
             result.get('action_count') == len(steps) and
             result.get('frame_count') == len(steps) and
             result.get('paid_provider_calls') == 0,
             'episode_result_not_admitted')
    turns = []
    for index, step in enumerate(steps):
        if index > 0:
            old = steps[index - 1]
            expected = old['action'].get('memory', old['observation']['memory'])
            _require(step['observation'].get('memory') == expected,
                     'memory_chain_mismatch')
        observation = _observation(root, step, index, source, cell)
        action = step.get('action')
        _require(type(action) is dict, 'invalid_action')
        normalized = normalize_model_action(json_text(action), observation,
                                            current_frame_id=observation.frame_id)
        _require(normalized['type'] == action['type'], 'action_mismatch')
        if index < len(steps) - 1:
            _require(action['type'] != 'finish', 'premature_finish')
        else:
            _require(action['type'] == 'finish', 'missing_finish')
        turns.append({'observation': observation, 'action': action})
    return episode, turns, {'split': split,
                             'gate_receipt_sha256': {k: refs[k]['sha256']
                                                     for k in _GATE_KINDS},
                             'episode_sha256': sha256(raw),
                             'action_sha256': sha256(json_text(
                                 [step['action'] for step in steps]).encode()),
                             'frame_sha256': sha256(json_text(
                                 [step['screenshot_sha256'] for step in steps]).encode())}


def render_model_turn(observation) -> dict:
    base = render_for_proxy(observation)
    instruction = json_text({
        'output_version': OUTPUT_VERSION,
        'contract': TRAIN_ACTION_CONTRACT,
        'task_instruction': observation.instruction,
        'previous_action_result': observation.previous_action_result,
        'memory': observation.memory,
    })
    _require(len(instruction.encode()) <= 16_384, 'instruction_limit')
    return {'image_bytes': base['image_bytes'], 'instruction': instruction,
            'visible_text': base['visible_text']}


@dataclass(frozen=True)
class OfflineSftResult:
    datums: list
    prompts: list
    receipt: dict


def _pinned_cookbook() -> str:
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
        raise EpisodeGateError('cookbook_revision_unverified') from None
    _require(commit == COOKBOOK_COMMIT and not dirty,
             'cookbook_revision_mismatch')
    return commit


def build_tinker_datums(episode_dir: Path, *, selection_manifest: Path,
                        final_manifest: Path, renderer=None) -> OfflineSftResult:
    """Offline construction only; no ServiceClient or paid call."""
    from PIL import Image
    from tinker_cookbook.renderers import ImagePart, Message, TextPart
    from tinker_cookbook.supervised.data import datum_from_model_input_weights

    episode, turns, proof = validate_episode(
        episode_dir, selection_manifest=selection_manifest,
        final_manifest=final_manifest)
    cookbook_commit = _pinned_cookbook()
    vision = renderer or QwenVisionRenderer.load()
    _require(vision.identity['model'] == MODEL and
             vision.identity['renderer'] == RENDERER and
             vision.identity['image_processor'] == PROCESSOR,
             'renderer_identity_mismatch')
    datums, prompts, counts = [], [], []
    for turn in turns:
        request = render_model_turn(turn['observation'])
        with Image.open(io.BytesIO(request['image_bytes'])) as opened:
            image = opened.convert('RGB')
        user = Message(role='user', content=[
            ImagePart(type='image', image=image),
            TextPart(type='text', text=json_text({
                'instruction': request['instruction'],
                'visible_text': request['visible_text']}))])
        assistant = Message(role='assistant', content=json_text(turn['action']))
        model_input, weights = vision.renderer.build_supervised_example([user, assistant])
        prompt = vision.renderer.build_generation_prompt([user])
        images = [chunk for chunk in model_input.chunks
                  if type(chunk).__name__ == 'ImageChunk']
        prompt_images = [chunk for chunk in prompt.chunks
                         if type(chunk).__name__ == 'ImageChunk']
        weight_sum = float(weights.sum().item())
        _require(len(images) == 1 and len(prompt_images) == 1 and weight_sum > 0 and
                 model_input.length <= MAX_TOKENS and prompt.length < model_input.length,
                 'image_or_assistant_loss_missing')
        datums.append(datum_from_model_input_weights(
            model_input, weights, max_length=MAX_TOKENS, reduction='none'))
        prompts.append(prompt)
        counts.append({'input_tokens': model_input.length,
                       'image_tokens': images[0].length,
                       'assistant_loss_sum': weight_sum})
    return OfflineSftResult(datums, prompts, {
        'schema': 'gui-sft-offline-render-v2',
        'cell': episode['cell'], 'source': episode['source'],
        'model': MODEL, 'renderer': RENDERER, 'image_processor': PROCESSOR,
        'renderer_identity': vision.identity,
        'cookbook_commit': cookbook_commit,
        'tinker_sdk_version': importlib.metadata.version('tinker'),
        'datum_count': len(datums),
        'max_supervised_tokens': max(row['input_tokens'] for row in counts),
        'max_image_tokens': max(row['image_tokens'] for row in counts),
        'minimum_positive_assistant_loss_sum': min(
            row['assistant_loss_sum'] for row in counts),
        'provenance': proof,
        'paid_provider_calls': 0, 'optimizer_steps': 0,
        'trained_improvement_measured': False,
        'official_final_task_count_added': 0,
    })
