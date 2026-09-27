"""Train-only, saved-state-gated GUI teacher collection for a frozen campaign.

This module never opens a selection/final package. A cell-owned worker drives
the original GUI and independently verifies its saved artifact and reset. The
adapter owns the teacher's multimodal paid calls, current-frame action check,
private evidence binding, and v0.6.6 Qwen rendering. A worker claim is not a
substitute for the separately frozen cell qualification and code audit.
"""

from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Callable

from . import full_study_matrix_v1 as matrix
from . import scale_action_output_v066 as output_v066
from .scale_action_contract import Observation
from .scale_action_contract_v066 import ACTION_PROFILE_VERSION, validate_action
from .scale_vision_proxy import MODEL, PROCESSOR, RENDERER, QwenVisionRenderer


DATASET_SCHEMA = 'cua-full-study-rendered-train-batch-v1'
RENDER_SCHEMA = 'cua-full-study-qwen-render-v066-v1'
EPISODE_SCHEMA = 'cua-full-study-teacher-gui-episode-v1'
STATE_SCHEMA = 'cua-full-study-teacher-saved-state-v1'
RESET_SCHEMA = 'cua-full-study-teacher-reset-v1'
TEACHER_REQUEST_SCHEMA = 'cua-full-study-teacher-rollout-request-v1'
E2B_REQUEST_SCHEMA = 'cua-full-study-teacher-e2b-lease-v1'
E2B_RESULT_SCHEMA = 'cua-full-study-teacher-e2b-lease-result-v1'
HARNESS_SCHEMA = 'cua-full-study-teacher-multimodal-harness-v1'
RATE_SCHEMA = 'cua-agentrouterhub-rate-upper-v1'
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_MAX_JSON_BYTES = 8_000_000


class TeacherAdapterError(ValueError):
    """Fixed local failure labels; never include private task/provider text."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TeacherAdapterError(code)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_hash(value: object) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _private_file(path: Path, root: Path, label: str) -> tuple[dict, bytes]:
    target = Path(path)
    _require(not target.is_symlink() and target.is_file() and
             target.resolve().is_relative_to(root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             target.stat().st_size <= _MAX_JSON_BYTES,
             label + '_private_file_missing_or_unsafe')
    raw = target.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TeacherAdapterError(label + '_invalid_json') from None
    _require(type(value) is dict, label + '_object_required')
    return value, raw


def _reference(directory: Path, reference: object, *, suffix: str) -> tuple[Path, bytes]:
    _require(type(reference) is dict and set(reference) == {'path', 'sha256'} and
             _is_hash(reference['sha256']) and type(reference['path']) is str,
             'episode_reference_invalid')
    relative = Path(reference['path'])
    _require(not relative.is_absolute() and '..' not in relative.parts and
             relative.suffix == suffix and len(relative.parts) <= 2,
             'episode_reference_unsafe')
    target = directory / relative
    _require(not target.is_symlink() and target.is_file() and
             target.resolve().is_relative_to(directory.resolve()) and
             target.stat().st_mode & 0o077 == 0,
             'episode_reference_missing_or_public')
    raw = target.read_bytes()
    _require(_sha(raw) == reference['sha256'], 'episode_reference_hash_mismatch')
    return target, raw


def _json_ref(directory: Path, reference: object) -> dict:
    _, raw = _reference(directory, reference, suffix='.json')
    _require(len(raw) <= _MAX_JSON_BYTES, 'episode_reference_too_large')
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TeacherAdapterError('episode_reference_invalid_json') from None
    _require(type(result) is dict, 'episode_reference_object_required')
    return result


def _frozen_session(session: object) -> tuple[str, dict]:
    """Recheck the real six-cell ratification before any provider reservation."""
    study = getattr(session, 'study', None)
    intent = getattr(session, 'intent', None)
    views = getattr(session, 'views', None)
    _require(type(intent) is dict and type(views) is dict and
             set(views) == {'train', 'selection'} and
             callable(getattr(session, 'dispatch_paid', None)) and
             callable(getattr(session, '_train_context', None)) and
             callable(getattr(session, '_events', None)) and
             callable(getattr(session, '_check_time', None)) and
             study is not None, 'frozen_campaign_session_required')
    cell_id = intent.get('cell_id')
    _require(cell_id in matrix.CELLS and
             len(views['selection']) == matrix.SELECTION_PER_CELL and
             bool(views['train']), 'campaign_task_views_invalid')
    plan = getattr(study, 'plan', None)
    _require(type(plan) is dict and plan.get('campaign_count') == 24 and
             plan.get('distinct_official_task_identities') == 600 and
             plan.get('cell_ids') == list(matrix.CELLS) and
             _is_hash(getattr(study, 'public_witness_sha256', None)) and
             _is_hash(getattr(study, 'ratification_sha256', None)),
             'real_six_cell_freeze_missing')
    from native_desktop_factory.v066_final_freeze import validate_ratification
    path = getattr(study, 'ratification_path', None)
    _require(path is not None and Path(path).is_file() and
             not Path(path).is_symlink() and
             Path(path).stat().st_mode & 0o077 == 0,
             'real_six_cell_ratification_missing')
    try:
        ratification, digest = validate_ratification(Path(path))
    except (TypeError, OSError, ValueError, KeyError, json.JSONDecodeError):
        raise TeacherAdapterError('real_six_cell_ratification_missing') from None
    _require(digest == study.ratification_sha256 and
             ratification == getattr(study, 'ratification', None),
             'real_six_cell_ratification_changed')
    session._check_time()
    return cell_id, ratification


def _proposal_and_train(session: object, round_index: int,
                        train_context_path: Path) -> tuple[dict, list[dict], str]:
    _require(type(round_index) is int and round_index > 0 and
             round_index <= 999, 'teacher_round_invalid')
    proposal_path = session.directory / f'proposal-{round_index:03d}.private.json'
    proposal, raw = _private_file(proposal_path, session.directory,
                                  'researcher_proposal')
    matching = [row for row in session._events('researcher_proposal')
                if row['data'].get('round_index') == round_index]
    _require(len(matching) == 1 and
             matching[0]['data'].get('proposal_sha256') == _sha(raw) and
             proposal.get('schema') == 'cua-full-study-researcher-proposal-v1' and
             set(proposal) == {'schema', 'hypothesis', 'train_task_ids',
                               'teacher_request'} and
             type(proposal.get('hypothesis')) is str and
             1 <= len(proposal['hypothesis'].encode()) <= 8192 and
             matching[0]['data'].get('hypothesis_sha256') ==
             _sha(proposal['hypothesis'].encode()) and
             type(proposal.get('train_task_ids')) is list and
             bool(proposal['train_task_ids']) and
             len(proposal['train_task_ids']) == len(set(proposal['train_task_ids'])) and
             type(proposal.get('teacher_request')) is str and
             1 <= len(proposal['teacher_request'].encode()) <= 8192,
             'researcher_proposal_not_frozen_or_train_only')
    tasks, context_sha = session._train_context(Path(train_context_path))
    _require(matching[0]['data'].get('train_context_sha256') == context_sha,
             'researcher_proposal_context_changed')
    by_id = {row['task_id']: row for row in tasks}
    view = {row['task_id']: row['package_sha256']
            for row in session.views['train']}
    selected = proposal['train_task_ids']
    _require(set(selected) <= set(by_id) == set(view) and
             all(by_id[task_id]['package_sha256'] == view[task_id]
                 for task_id in selected) and
             not set(selected) & {row['task_id']
                                  for row in session.views['selection']},
             'teacher_source_not_train_only')
    return proposal, [by_id[task_id] for task_id in selected], context_sha


def _teacher_configuration(session: object) -> tuple[dict, dict, dict, str]:
    _require(callable(getattr(session.study, 'teacher_configuration', None)),
             'frozen_teacher_configuration_missing')
    config = session.study.teacher_configuration()
    _require(type(config) is dict and config.get('model') == matrix.TEACHER and
             _is_hash(config.get('config_sha256')) and
             type(config.get('assets')) is dict and
             type(config.get('settings')) is dict,
             'frozen_teacher_configuration_invalid')
    try:
        harness = json.loads(config['assets']['harness'])
        rate = json.loads(config['assets']['provider_route'])
        tool_grammar = config['assets']['tool_grammar'].decode()
        system_prompt = config['assets']['prompt'].decode()
    except (KeyError, AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        raise TeacherAdapterError('frozen_teacher_multimodal_assets_invalid') from None
    needed = {'schema', 'transport', 'image_detail', 'max_frame_bytes',
              'max_frame_pixels', 'max_actions_per_episode',
              'max_input_tokens_per_call', 'request_timeout_seconds'}
    _require(type(harness) is dict and set(harness) == needed and
             harness['schema'] == HARNESS_SCHEMA and
             harness['transport'] == 'agentrouterhub-responses-image-v1' and
             harness['image_detail'] in {'high', 'low'} and
             type(harness['max_frame_bytes']) is int and
             0 < harness['max_frame_bytes'] <= 4_000_000 and
             type(harness['max_frame_pixels']) is int and
             0 < harness['max_frame_pixels'] <= 4_194_304 and
             type(harness['max_actions_per_episode']) is int and
             0 < harness['max_actions_per_episode'] <= 90 and
             type(harness['max_input_tokens_per_call']) is int and
             0 < harness['max_input_tokens_per_call'] <= 65_536 and
             type(harness['request_timeout_seconds']) is int and
             0 < harness['request_timeout_seconds'] <= 900 and
             tool_grammar == output_v066.MODEL_ACTION_CONTRACT and
             1 <= len(system_prompt.encode()) <= 8192,
             'frozen_teacher_multimodal_harness_invalid')
    rate_fields = {'schema', 'model', 'base_url',
                   'input_usd_per_million_tokens',
                   'output_usd_per_million_tokens', 'fixed_usd_per_call',
                   'billing_multiplier_upper'}
    _require(type(rate) is dict and set(rate) == rate_fields and
             rate['schema'] == RATE_SCHEMA and rate['model'] == matrix.TEACHER and
             rate['base_url'] == 'https://sub2api.agentrouterhub.com' and
             os.environ.get('OPENAI_BASE_URL', rate['base_url']).rstrip('/') ==
             rate['base_url'], 'frozen_teacher_route_invalid')
    for name in rate_fields - {'schema', 'model', 'base_url'}:
        _require(type(rate[name]) is str,
                 'frozen_teacher_rate_invalid')
        try:
            value = Decimal(rate[name])
        except Exception:
            raise TeacherAdapterError('frozen_teacher_rate_invalid') from None
        _require(value.is_finite() and value >= 0 and
                 (name == 'fixed_usd_per_call' or value > 0) and
                 (name != 'billing_multiplier_upper' or value >= 1),
                 'frozen_teacher_rate_invalid')
    settings = config['settings']
    _require(type(settings.get('max_output_tokens')) is int and
             0 < settings['max_output_tokens'] <= 4096 and
             settings.get('reasoning_effort') in
             {'low', 'medium', 'high', 'xhigh', 'max'} and
             settings.get('reasoning_mode') in {'standard', 'pro'},
             'frozen_teacher_settings_invalid')
    return config, harness, rate, system_prompt


def _teacher_quote(rate: dict, harness: dict, output_tokens: int) -> str:
    input_usd = Decimal(rate['input_usd_per_million_tokens'])
    output_usd = Decimal(rate['output_usd_per_million_tokens'])
    fixed = Decimal(rate['fixed_usd_per_call'])
    multiplier = Decimal(rate['billing_multiplier_upper'])
    worst = ((input_usd * harness['max_input_tokens_per_call'] +
              output_usd * output_tokens) / Decimal(1_000_000) + fixed) * multiplier
    return str(worst.quantize(Decimal('0.000000001'), rounding=ROUND_CEILING))


def _real_teacher_provider(request: dict, timeout_seconds: int) -> dict:
    """Responses image request; no text-only fallback or retry after POST."""
    from .http_transport import post_json
    key = os.environ.get('OPENAI_API_KEY')
    _require(bool(key), 'teacher_api_key_missing')
    reasoning = {'effort': request['reasoning_effort']}
    if request['reasoning_mode'] == 'pro':
        reasoning['mode'] = 'pro'
    payload = {
        'model': request['model'], 'store': False,
        'max_output_tokens': request['max_output_tokens'],
        'reasoning': reasoning,
        'input': [
            {'role': 'developer', 'content': request['system_prompt']},
            {'role': 'user', 'content': [
                {'type': 'input_text', 'text': request['user_text']},
                {'type': 'input_image',
                 'image_url': request['image_data_url'],
                 'detail': request['image_detail']},
            ]},
        ],
    }
    body = post_json('https://sub2api.agentrouterhub.com/v1/responses',
                     payload, {'Authorization': 'Bearer ' + key,
                               'Content-Type': 'application/json',
                               'User-Agent': 'cua-rsibench/full-study-teacher-v1'},
                     timeout_seconds)
    _require(type(body) is dict, 'teacher_response_invalid')
    text = '\n'.join(part['text'] for item in body.get('output', [])
                     if type(item) is dict and item.get('type') == 'message'
                     for part in item.get('content', [])
                     if type(part) is dict and part.get('type') == 'output_text'
                     and type(part.get('text')) is str)
    return {'text': text,
            'receipt': {'reported_model': body.get('model'),
                        'status': body.get('status'),
                        'response_id': body.get('id'),
                        'usage': body.get('usage'),
                        'transport': body.get('__cua_transport')}}


@dataclass(frozen=True)
class RenderedTrainBatch:
    datums: list
    prompts: list
    receipt: dict


@dataclass(frozen=True)
class CollectedTrainBatch:
    dataset_manifest_path: Path
    rendered_batch: RenderedTrainBatch
    episode_receipt_sha256s: list[str]


def _load_renderer():
    # Import the training data path now, so a missing pinned dependency cannot
    # waste any teacher/E2B reservation before datum construction.
    from tinker_cookbook.supervised.data import datum_from_model_input_weights  # noqa: F401
    vision = QwenVisionRenderer.load()
    _require(type(vision.identity) is dict and
             vision.identity.get('model') == MODEL and
             vision.identity.get('renderer') == RENDERER and
             vision.identity.get('image_processor') == PROCESSOR,
             'qwen_vision_renderer_identity_invalid')
    return vision


def _render_turns(cell_id: str, task_ids: list[str],
                  episode_shas: list[str], turns: list[dict],
                  vision) -> RenderedTrainBatch:
    from PIL import Image
    from tinker_cookbook.renderers import ImagePart, Message, TextPart
    from tinker_cookbook.supervised.data import datum_from_model_input_weights

    datums, prompts, datum_lengths, prompt_lengths = [], [], [], []
    for turn in turns:
        observation = turn['observation']
        rendered = output_v066.render_for_model(observation)
        with Image.open(io.BytesIO(rendered['image_bytes'])) as opened:
            image = opened.convert('RGB')
        user = Message(role='user', content=[
            ImagePart(type='image', image=image),
            TextPart(type='text', text=json.dumps({
                'instruction': rendered['instruction'],
                'visible_text': rendered['visible_text']},
                ensure_ascii=False, sort_keys=True, separators=(',', ':')))])
        action = {key: value for key, value in turn['action'].items()
                  if key not in {'version', 'task_id', 'task_binding_sha256',
                                 'step', 'frame_id'}}
        assistant = Message(role='assistant', content=_canonical(action).decode().strip())
        model_input, weights = vision.renderer.build_supervised_example([user, assistant])
        prompt = vision.renderer.build_generation_prompt([user])
        image_chunks = [chunk for chunk in model_input.chunks
                        if type(chunk).__name__ == 'ImageChunk']
        _require(len(image_chunks) == 1 and float(weights.sum().item()) > 0 and
                 type(model_input.length) is int and
                 type(prompt.length) is int and
                 0 < prompt.length < model_input.length <= 32768,
                 'qwen_render_missing_image_or_assistant_loss')
        datum = datum_from_model_input_weights(
            model_input, weights, max_length=32768, reduction='none')
        actual_length = getattr(getattr(datum, 'model_input', None),
                                'length', None)
        _require(type(actual_length) is int and
                 prompt.length < actual_length <= model_input.length and
                 any(type(chunk).__name__ == 'ImageChunk'
                     for chunk in datum.model_input.chunks),
                 'qwen_shifted_datum_length_or_image_invalid')
        datums.append(datum)
        prompts.append(prompt)
        datum_lengths.append(actual_length)
        prompt_lengths.append(prompt.length)
    receipt = {'schema': RENDER_SCHEMA, 'cell_id': cell_id,
               'action_profile': ACTION_PROFILE_VERSION, 'model': MODEL,
               'train_task_ids': task_ids,
               'episode_receipt_sha256s': episode_shas,
               'datum_token_lengths': datum_lengths,
               'prompt_token_lengths': prompt_lengths}
    return RenderedTrainBatch(datums, prompts, receipt)


def _verify_episode(directory: Path, result: object, *, cell_id: str,
                    task: dict, runtime_sha: str, adapter_sha: str,
                    verifier_sha: str,
                    turns: list[dict], e2b_attempt_ids: list[str],
                    requires_e2b: bool) -> str:
    _require(type(result) is dict and set(result) ==
             {'episode_receipt_path', 'episode_receipt_sha256'},
             'worker_episode_result_invalid')
    receipt_path = Path(result['episode_receipt_path'])
    _require(receipt_path == directory / 'episode.private.json' and
             _is_hash(result['episode_receipt_sha256']),
             'worker_episode_receipt_path_invalid')
    receipt, raw = _private_file(receipt_path, directory, 'episode')
    _require(_sha(raw) == result['episode_receipt_sha256'],
             'worker_episode_receipt_hash_mismatch')
    fields = {'schema', 'status', 'split', 'cell_id', 'task_id',
              'package_sha256', 'action_profile', 'teacher_model',
              'original_software_gui', 'original_surface', 'runtime_sha256',
              'adapter_sha256', 'frame_refs', 'action_trace_ref',
              'saved_state_ref', 'reset_ref', 'teacher_result_sha256s',
              'e2b_attempt_ids'}
    _require(set(receipt) == fields and receipt['schema'] == EPISODE_SCHEMA and
             receipt['status'] == 'admitted' and receipt['split'] == 'train' and
             receipt['cell_id'] == cell_id and
             receipt['task_id'] == task['task_id'] and
             receipt['package_sha256'] == task['package_sha256'] and
             receipt['action_profile'] == ACTION_PROFILE_VERSION and
             receipt['teacher_model'] == matrix.TEACHER and
             receipt['original_software_gui'] is True and
             receipt['original_surface'] in {'native', 'web'} and
             receipt['runtime_sha256'] == runtime_sha and
             receipt['adapter_sha256'] == adapter_sha and
             receipt['e2b_attempt_ids'] == e2b_attempt_ids and
             bool(e2b_attempt_ids) == requires_e2b and
             type(receipt['frame_refs']) is list and
             len(receipt['frame_refs']) == len(turns) and turns and
             receipt['teacher_result_sha256s'] ==
             [turn['teacher_result_sha256'] for turn in turns],
             'worker_episode_identity_or_split_invalid')
    for index, (reference, turn) in enumerate(zip(receipt['frame_refs'], turns)):
        _require(type(reference) is dict and
                 reference.get('path') == f'frames/step-{index:03d}.png',
                 'episode_frame_order_invalid')
        _, image = _reference(directory, reference, suffix='.png')
        _require(image == turn['observation'].screenshot_bytes,
                 'episode_frame_differs_from_paid_observation')
    trace_path, trace_raw = _reference(directory, receipt['action_trace_ref'],
                                       suffix='.json')
    _require(trace_path.name == 'actions.private.json',
             'episode_trace_path_invalid')
    expected_trace = [turn['trace_row'] for turn in turns]
    _require(trace_raw == _canonical(expected_trace),
             'episode_trace_differs_from_paid_actions')
    state = _json_ref(directory, receipt['saved_state_ref'])
    reset = _json_ref(directory, receipt['reset_ref'])
    common = {'cell_id': cell_id, 'task_id': task['task_id'],
              'package_sha256': task['package_sha256']}
    _require(state.get('schema') == STATE_SCHEMA and
             all(state.get(key) == value for key, value in common.items()) and
             state.get('independent_of_actor') is True and
             state.get('native_save_observed') is True and
             state.get('target_state_pass') is True and
             state.get('no_regression_pass') is True and
             _is_hash(state.get('saved_artifact_sha256')) and
             state.get('verifier_sha256') == verifier_sha and
             state.get('evaluator_result') == 'pass',
             'episode_independent_saved_state_missing')
    saved_ref = state.get('saved_artifact_ref')
    _require(type(saved_ref) is dict and
             type(saved_ref.get('path')) is str and
             saved_ref['path'].startswith('artifacts/'),
             'episode_saved_artifact_reference_missing')
    _, saved_bytes = _reference(directory, saved_ref,
                                suffix=Path(saved_ref['path']).suffix)
    _require(_sha(saved_bytes) == state['saved_artifact_sha256'] and
             bool(saved_bytes), 'episode_saved_artifact_changed')
    _require(reset.get('schema') == RESET_SCHEMA and
             all(reset.get(key) == value for key, value in common.items()) and
             reset.get('independent_of_actor') is True and
             reset.get('fresh_environment') is True and
             reset.get('state_equivalence_pass') is True and
             _is_hash(reset.get('baseline_semantic_sha256')) and
             reset.get('restored_semantic_sha256') ==
             reset.get('baseline_semantic_sha256') and
             reset.get('sandbox_terminated') is True,
             'episode_fresh_reset_missing')
    for name, digest_field in (('baseline_state_ref', 'baseline_semantic_sha256'),
                               ('restored_state_ref', 'restored_semantic_sha256')):
        reference = reset.get(name)
        _require(type(reference) is dict and
                 type(reference.get('path')) is str and
                 reference['path'].startswith('artifacts/'),
                 'episode_reset_artifact_reference_missing')
        _, raw_state = _reference(directory, reference, suffix='.json')
        _require(bool(raw_state) and _sha(raw_state) == reset[digest_field],
                 'episode_reset_artifact_changed')
    _require(turns[-1]['action']['type'] == 'finish' and
             all(turn['action']['type'] != 'finish' for turn in turns[:-1]),
             'episode_finish_missing_or_premature')
    return _sha(raw)


def collect_train_batch(session, round_index, train_context_path, out_dir,
                        cell_worker, *, teacher_provider=None) -> CollectedTrainBatch:
    """Collect and render only a hash-bound researcher's train proposal.

    ``cell_worker.run_episode`` must accept ``task``, ``out_dir``,
    ``sample_teacher``, and ``dispatch_e2b`` keyword arguments. It must drive
    the original GUI, write private frame/trace/state/reset files, and return
    the episode receipt reference. It never receives a selection/final view.
    """
    cell_id, ratification = _frozen_session(session)
    proposal, tasks, context_sha = _proposal_and_train(
        session, round_index, Path(train_context_path))
    config, harness, rate, system_prompt = _teacher_configuration(session)
    _require(teacher_provider is None or callable(teacher_provider),
             'teacher_provider_invalid')
    if teacher_provider is None:
        _require(bool(os.environ.get('OPENAI_API_KEY')),
                 'teacher_api_key_missing_before_paid_call')
    _require(getattr(cell_worker, 'cell_id', None) == cell_id and
             getattr(cell_worker, 'action_profile', None) == ACTION_PROFILE_VERSION and
             getattr(cell_worker, 'original_software_gui', None) is True and
             getattr(cell_worker, 'original_surface', None) in {'native', 'web'} and
             type(getattr(cell_worker, 'requires_e2b', None)) is bool and
             callable(getattr(cell_worker, 'run_episode', None)) and
             getattr(cell_worker, 'adapter_sha256', None) ==
             ratification['cell_profiles'][cell_id]['adapter_sha256'],
             'original_gui_cell_worker_unbound')
    selected_count = len(tasks)
    _require(selected_count <= 999, 'teacher_episode_count_limit')
    root = Path(session.study.repo_root) / 'work'
    destination = Path(out_dir).absolute()
    _require(not root.is_symlink() and not destination.is_symlink() and
             destination.resolve().is_relative_to(root.resolve()) and
             not destination.exists(), 'teacher_output_private_new_directory_required')
    cell_plan = next(row for row in session.study.plan['cells']
                     if row['cell_id'] == cell_id)
    runtime_sha = cell_plan['matched_bindings']['runtime']
    verifier_sha = cell_plan['matched_bindings']['verifier']
    _require(_is_hash(runtime_sha) and _is_hash(verifier_sha),
             'frozen_cell_runtime_or_verifier_missing')
    training, _ = session.study.student_training_configuration()
    _require(training['action_profile'] == ACTION_PROFILE_VERSION and
             training['model'] == MODEL and
             type(training.get('batch_size')) is int and
             type(training.get('optimizer_steps')) is int and
             type(training.get('max_supervised_tokens')) is int and
             type(training.get('max_scheduled_tokens')) is int and
             0 < training['batch_size'] * training['optimizer_steps'] and
             len(tasks) <= training['batch_size'] * training['optimizer_steps'],
             'frozen_qwen_training_profile_mismatch')
    vision = _load_renderer()
    reserve_usd = _teacher_quote(
        rate, harness, config['settings']['max_output_tokens'])
    _require(Decimal(reserve_usd) > 0,
             'teacher_worst_case_quote_not_positive')
    destination.mkdir(parents=True, mode=0o700)
    destination.chmod(0o700)
    result_shas: list[str] = []
    all_turns: list[dict] = []
    for episode_index, task in enumerate(tasks, 1):
        episode_dir = destination / f'episode-{episode_index:03d}'
        episode_dir.mkdir(mode=0o700)
        (episode_dir / 'frames').mkdir(mode=0o700)
        turns: list[dict] = []
        e2b_attempt_ids: list[str] = []

        def sample_teacher(observation: Observation,
                           current_frame_id: Callable[[], str]) -> dict:
            step = len(turns)
            _require(type(observation) is Observation and
                     callable(current_frame_id) and
                     current_frame_id() == observation.frame_id and
                     observation.task_id == task['task_id'] and
                     observation.task_binding_sha256 == task['package_sha256'] and
                     observation.instruction == task['visible_instruction'] and
                     observation.step == step and
                     step < harness['max_actions_per_episode'] and
                     len(observation.screenshot_bytes) <=
                     harness['max_frame_bytes'] and
                     observation.screenshot['pixels'] <=
                     harness['max_frame_pixels'],
                     'teacher_observation_not_current_train_frame')
            if cell_worker.requires_e2b:
                _require(e2b_attempt_ids,
                         'e2b_lease_must_be_reserved_before_gui_observation')
            rendered = output_v066.render_for_model(observation)
            mime = ('image/png' if observation.screenshot['format'] == 'png'
                    else 'image/jpeg')
            request = {
                'schema': TEACHER_REQUEST_SCHEMA,
                'model': matrix.TEACHER,
                'cell_id': cell_id,
                'train_task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'round_index': round_index,
                'episode_index': episode_index,
                'step': step,
                'frame_id': observation.frame_id,
                'frame_sha256': _sha(observation.screenshot_bytes),
                'image_data_url': 'data:' + mime + ';base64,' +
                                  base64.b64encode(observation.screenshot_bytes).decode(),
                'image_detail': harness['image_detail'],
                'system_prompt': system_prompt,
                'user_text': _canonical({
                    'task_instruction': task['visible_instruction'],
                    'researcher_teacher_request': proposal['teacher_request'],
                    'model_instruction': rendered['instruction'],
                    'visible_text': rendered['visible_text'],
                }).decode(),
                'reasoning_effort': config['settings']['reasoning_effort'],
                'reasoning_mode': config['settings']['reasoning_mode'],
                'max_output_tokens': config['settings']['max_output_tokens'],
                'max_input_tokens': harness['max_input_tokens_per_call'],
                'teacher_config_sha256': config['config_sha256'],
                'train_context_sha256': context_sha,
            }
            _require(len(_canonical(request)) <= _MAX_JSON_BYTES,
                     'teacher_multimodal_request_too_large')
            attempt_id = (f'teacher-r{round_index:03d}-e{episode_index:03d}-'
                          f's{step:03d}')

            def call(paid_request: dict) -> dict:
                response = (teacher_provider(paid_request) if teacher_provider
                            is not None else _real_teacher_provider(
                                paid_request, harness['request_timeout_seconds']))
                _require(type(response) is dict and
                         set(response) == {'text', 'receipt'} and
                         type(response['text']) is str and
                         0 < len(response['text'].encode()) <= 65_536 and
                         type(response['receipt']) is dict,
                         'teacher_response_body_invalid')
                receipt = response['receipt']
                usage = receipt.get('usage')
                _require(receipt.get('reported_model') == matrix.TEACHER and
                         receipt.get('status') == 'completed' and
                         type(receipt.get('response_id')) is str and
                         bool(receipt['response_id']) and
                         type(usage) is dict and
                         type(usage.get('input_tokens')) is int and
                         type(usage.get('output_tokens')) is int and
                         0 < usage['input_tokens'] <=
                         harness['max_input_tokens_per_call'] and
                         0 < usage['output_tokens'] <=
                         config['settings']['max_output_tokens'],
                         'teacher_model_status_or_usage_ambiguous')
                return response

            paid = session.dispatch_paid(
                attempt_id=attempt_id, category='teacher_rollout',
                work={'round_index': round_index,
                      'episode_index': episode_index,
                      'train_task_id': task['task_id'],
                      'package_sha256': task['package_sha256'],
                      'step': step, 'frame_sha256': request['frame_sha256']},
                request=request, reserve_usd=reserve_usd,
                resource_reservation={
                    'teacher_rollout_calls': '1',
                    'teacher_rollout_tokens': str(
                        harness['max_input_tokens_per_call'] +
                        config['settings']['max_output_tokens'])},
                provider=call)
            _require(current_frame_id() == observation.frame_id,
                     'teacher_frame_changed_after_paid_call')
            action = output_v066.normalize_model_action(
                paid['result']['text'], observation,
                current_frame_id=current_frame_id())
            # The worker must recheck this frame again immediately before the
            # physical GUI action; the adapter cannot perform that dispatch.
            validate_action(action, observation,
                            current_frame_id=current_frame_id())
            trace_row = {
                'step': step, 'frame_id': observation.frame_id,
                'frame_sha256': request['frame_sha256'],
                'observation': {
                    'task_id': observation.task_id,
                    'task_binding_sha256': observation.task_binding_sha256,
                    'instruction': observation.instruction,
                    'a11y_text': observation.a11y_text,
                    'dom_text': observation.dom_text,
                    'controls': [vars(control) for control in observation.controls],
                    'previous_action_result': observation.previous_action_result,
                    'memory': observation.memory,
                    'issued_at': observation.issued_at,
                },
                'action': action,
                'teacher_result_sha256': paid['result_sha256'],
            }
            turns.append({'observation': observation,
                          'action': copy.deepcopy(action),
                          'trace_row': copy.deepcopy(trace_row),
                          'teacher_result_sha256': paid['result_sha256']})
            return {'action': copy.deepcopy(action),
                    'trace_row': copy.deepcopy(trace_row),
                    'teacher_result_sha256': paid['result_sha256']}

        def dispatch_e2b(*, lease_seconds: int, reserve_usd: str,
                         provider: Callable[[dict], dict]) -> dict:
            _require(cell_worker.requires_e2b and not e2b_attempt_ids and
                     not turns and type(lease_seconds) is int and
                     0 < lease_seconds <= 3600 and
                     callable(provider),
                     'e2b_lease_contract_invalid')
            try:
                amount = Decimal(reserve_usd)
            except Exception:
                raise TeacherAdapterError('e2b_reserve_invalid') from None
            _require(amount.is_finite() and amount > 0 and
                     -amount.as_tuple().exponent <= 9,
                     'e2b_reserve_invalid')
            hours = (Decimal(lease_seconds) / Decimal(3600)).quantize(
                Decimal('0.000000001'), rounding=ROUND_CEILING)
            try:
                allocated_hourly = (Decimal(session.intent['e2b_usd_cap']) /
                                    Decimal(session.intent['e2b_sandbox_hours_cap']))
            except (KeyError, ArithmeticError, ValueError, TypeError):
                raise TeacherAdapterError('frozen_e2b_rate_allocation_missing') from None
            _require(allocated_hourly.is_finite() and allocated_hourly > 0 and
                     amount >= (hours * allocated_hourly).quantize(
                         Decimal('0.000000001'), rounding=ROUND_CEILING),
                     'e2b_full_lease_reservation_underallocated')
            request = {'schema': E2B_REQUEST_SCHEMA, 'cell_id': cell_id,
                       'train_task_id': task['task_id'],
                       'package_sha256': task['package_sha256'],
                       'round_index': round_index,
                       'episode_index': episode_index,
                       'lease_seconds': lease_seconds,
                       'purpose': 'teacher_original_gui_train'}
            attempt_id = f'e2b-teacher-r{round_index:03d}-e{episode_index:03d}'

            def create(paid_request: dict) -> dict:
                result = provider(paid_request)
                _require(type(result) is dict and
                         set(result) == {'schema', 'sandbox_id',
                                         'lease_seconds', 'created'} and
                         result['schema'] == E2B_RESULT_SCHEMA and
                         type(result['sandbox_id']) is str and
                         re.fullmatch(r'[A-Za-z0-9._:-]{1,160}',
                                      result['sandbox_id']) is not None and
                         result['lease_seconds'] == lease_seconds and
                         result['created'] is True,
                         'e2b_provider_creation_ambiguous')
                return result

            paid = session.dispatch_paid(
                attempt_id=attempt_id, category='e2b',
                work=request, request=request, reserve_usd=reserve_usd,
                resource_reservation={
                    'e2b_sandbox_hours': str(hours),
                    'e2b_peak_concurrency': '1'}, provider=create)
            e2b_attempt_ids.append(attempt_id)
            return paid

        result = cell_worker.run_episode(
            task=dict(task), out_dir=episode_dir,
            sample_teacher=sample_teacher, dispatch_e2b=dispatch_e2b)
        receipt_sha = _verify_episode(
            episode_dir, result, cell_id=cell_id, task=task,
            runtime_sha=runtime_sha,
            adapter_sha=cell_worker.adapter_sha256,
            verifier_sha=verifier_sha,
            turns=turns, e2b_attempt_ids=e2b_attempt_ids,
            requires_e2b=cell_worker.requires_e2b)
        result_shas.append(receipt_sha)
        all_turns.extend(turns)
        _require(len(all_turns) <=
                 training['batch_size'] * training['optimizer_steps'],
                 'teacher_episode_exceeds_frozen_training_capacity')
    rendered_batch = _render_turns(cell_id, [task['task_id'] for task in tasks],
                                   result_shas, all_turns, vision)
    lengths = rendered_batch.receipt['datum_token_lengths']
    scheduled_tokens = sum(
        lengths[(step * training['batch_size'] + offset) % len(lengths)]
        for step in range(training['optimizer_steps'])
        for offset in range(training['batch_size']))
    _require(max(lengths) <= training['max_supervised_tokens'] and
             scheduled_tokens <= training['max_scheduled_tokens'],
             'teacher_batch_exceeds_frozen_qwen_token_capacity')
    manifest = {
        'schema': DATASET_SCHEMA, 'cell_id': cell_id,
        'action_profile': ACTION_PROFILE_VERSION, 'model': MODEL,
        'train_task_ids': [task['task_id'] for task in tasks],
        'train_package_sha256_by_id': {
            task['task_id']: task['package_sha256'] for task in tasks},
        'episode_receipt_sha256s': result_shas,
        'rendered_batch_sha256': _sha(_canonical(rendered_batch.receipt)),
        'admitted_train_only': True,
        'selection_task_count': 0, 'final_task_count': 0,
    }
    dataset_path = destination / 'dataset.private.json'
    descriptor = os.open(dataset_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(_canonical(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    return CollectedTrainBatch(dataset_path, rendered_batch, result_shas)
