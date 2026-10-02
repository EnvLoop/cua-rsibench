"""Hash-bound, public TRAIN-only Tinker LoRA entrypoint for the Odoo20 pilot.

The input manifest is an operator-owned, mode-0600 file next to the active
trial plan. Pickles require explicit trust and a restricted loader; their
contents are independently rebuilt from paid teacher requests and native
saved/reset evidence. This authority never grants full-study credit.
No dispatch or replay occurs without --execute and --trust-owned-rendered.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError, wait
from dataclasses import fields, is_dataclass, replace
from decimal import Decimal
from hashlib import sha256
import importlib
import io
import json
import os
from pathlib import Path
import pickle
import re
from types import FunctionType, SimpleNamespace

from . import twenty_task_trial_teacher_v1 as trial
from cursibench import scale_action_contract as contract
from cursibench import scale_action_output_v066 as output

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'Qwen/Qwen3.8-27B'
SCHEMA = 'envloop-odoo20-trusted-training-input-v1'
HEX = re.compile(r'[0-9a-f]{64}\Z')
SDK_SHA256S = {
    'tinker.lib.public_interfaces.service_client': 'b8e63b7970ac2ae9461d7fd8d1939d15d64dc5a5d9526acf7d82b217637744f8',
    'tinker.lib.public_interfaces.training_client': '454b20914262776ac868eb3657329be22f83e0aab4d0c38c40f1721f1591a584',
    'tinker.lib.public_interfaces.sampling_client': 'fed9b0bd006925e1fd5eb9cea06c78392418ed7f7aa9b5c9acbb0cdedda80d4a',
    'tinker.lib.internal_client_holder': '78bfe7a113f5b36191fd9e72f715e98b86e8fd74d125fcdf612732109e9d5492',
    'tinker.lib.retry_handler': '8dba752fbf61860c53a76a61aeff950e62ecc0f01fc28b5992347a5785809abf',
}


class TrainingError(ValueError):
    pass


def require(value, label):
    if not value:
        raise TrainingError(label)


def digest(raw):
    return sha256(raw).hexdigest()


def write(path, value):
    """Exclusive durable write, including directory durability before dispatch."""
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_bytes(path, expected=None, *, root, maximum=256_000_000):
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and
            path.resolve().is_relative_to(Path(root).resolve()) and
            path.stat().st_mode & 0o077 == 0 and path.stat().st_size <= maximum,
            'private_owned_input_required')
    # Reject symlinked parent components too, before following ownership paths.
    for parent in path.parents:
        require(not parent.is_symlink(), 'private_input_symlink_parent')
        if parent == Path(root):
            break
    raw = path.read_bytes()
    require(expected is None or (type(expected) is str and HEX.fullmatch(expected)
                                and digest(raw) == expected), 'input_hash_mismatch')
    return raw


def private_json(path, expected=None, *, root):
    value = json.loads(private_bytes(path, expected, root=root, maximum=8_000_000))
    require(type(value) is dict, 'private_json_object_required')
    return value


def reference(root, ref):
    require(type(ref) is dict and set(ref) == {'path', 'sha256'}, 'input_reference_invalid')
    path = Path(ref['path'])
    require(not path.is_absolute() and '..' not in path.parts, 'input_reference_escape')
    return Path(root) / path


def check_sources(manifest):
    expected = manifest['source_sha256s']
    needed = {'enterprise_fallback/odoo18/twenty_task_trial_teacher_v1.py',
              'src/cursibench/full_study_teacher_adapter_v1.py',
              'src/cursibench/scale_vision_proxy.py',
              'src/cursibench/scale_action_output_v066.py',
              'src/cursibench/full_study_campaign_dispatch_v1.py'}
    require(type(expected) is dict and set(expected) == needed, 'training_sources_not_frozen')
    for relative, hashed in expected.items():
        require(digest((ROOT / relative).read_bytes()) == hashed, 'training_source_changed')


def frozen_training(manifest, namespace, plan):
    """New pilot authority; reuse only explicitly bound diagnostic hyperparameters."""
    ref = plan['trial_training_ref']
    path = Path(ref['path'])
    if not path.is_absolute():
        path = namespace / path
    require(path.parent.resolve() == namespace and
            manifest['training_asset_sha256'] == ref['sha256'], 'pilot_training_asset_unbound')
    raw = private_bytes(path, ref['sha256'], root=namespace)
    training = json.loads(raw)
    require(training['schema'] == 'envloop-odoo20-qwen-sft-training-v1' and
            training['model'] == MODEL and training['action_profile'] == 'scale-action-profile-v0.6.6' and
            training['full_study_ratified_training_profile_claim'] is False and
            training['automatic_replay_after_uncertain_call'] is False and
            training['provider_invoice_required_for_cost_claim'] is True,
            'new_pilot_training_authority_required')
    prereg = ROOT / 'runtime/qwen38-vision/real-gui-diagnostic-prereg-v1.json'
    anchor_raw = prereg.read_bytes()
    require(digest(anchor_raw) == training['hyperparameter_reference_sha256'], 'hyperparameter_anchor_changed')
    anchor = json.loads(anchor_raw)
    for name in ('lora_rank', 'batch_size', 'optimizer_steps', 'learning_rate'):
        require(training[name] == anchor[name], 'bound_hyperparameter_changed')
    require(training['seed'] == anchor['model_seed'] and
            training['sampling_temperature'] == 0 and training['sample_max_tokens'] == 512 and
            training['minimum_distinct_training_tasks'] == training['minimum_distinct_workflows'] == 4,
            'pilot_training_bounds_changed')
    for name, maximum in (('lora_rank', 256), ('batch_size', 128), ('optimizer_steps', 10000),
                          ('max_supervised_tokens', 32768), ('max_scheduled_tokens', 4194304)):
        require(type(training[name]) is int and 0 < training[name] <= maximum, 'pilot_training_bound_invalid')
    require(Decimal(training['learning_rate']).is_finite() and Decimal(training['learning_rate']) > 0,
            'pilot_learning_rate_invalid')
    return training, digest(raw)


class RestrictedRenderedUnpickler(pickle.Unpickler):
    """Allow only the concrete data types emitted by the installed renderer."""
    def find_class(self, module, name):
        allowed = {('tinker', n) for n in ('Datum', 'ModelInput', 'EncodedTextChunk', 'TensorData')}
        allowed |= {('tinker.types.image_chunk', 'ImageChunk'),
                    ('numpy', 'dtype'), ('numpy._core.numeric', '_frombuffer')}
        require((module, name) in allowed, 'rendered_pickle_non_datum_global')
        return getattr(importlib.import_module(module), name)

    def persistent_load(self, pid):
        raise TrainingError('rendered_pickle_persistent_reference')


def data_signature(value):
    """A deterministic comparison, independent of pickle/set serialization order."""
    from tinker import types
    def model_input(model):
        require(type(model) is types.ModelInput, 'actual_tinker_model_input_required')
        chunks = []
        for chunk in model.chunks:
            if type(chunk) is types.ImageChunk:
                require(type(chunk.length) is int and chunk.length > 0 and bool(chunk.data),
                        'multimodal_image_unbounded')
                chunks.append(('image', digest(chunk.data), chunk.format, chunk.length))
            elif type(chunk) is types.EncodedTextChunk:
                chunks.append(('text', list(chunk.tokens)))
            else:
                raise TrainingError('unexpected_model_input_chunk')
        require(sum(row[0] == 'image' for row in chunks) == 1, 'exactly_one_actual_image_required')
        return chunks
    if type(value) is types.ModelInput:
        return model_input(value)
    require(type(value) is types.Datum and
            set(value.loss_fn_inputs) == {'target_tokens', 'weights'},
            'actual_cross_entropy_datum_required')
    tensors = {}
    for name, tensor in value.loss_fn_inputs.items():
        require(type(tensor) is types.TensorData, 'actual_tinker_tensor_required')
        array = tensor.to_numpy()
        require(array.ndim == 1 and len(array) == value.model_input.length and
                str(array.dtype) == ('int64' if name == 'target_tokens' else 'float32'),
                'datum_loss_tensor_shape_or_type')
        if name == 'weights':
            require(bool((array >= 0).all()) and bool((array <= 1).all()) and
                    float(array.sum()) > 0, 'positive_assistant_loss_required')
        tensors[name] = (str(array.dtype), list(array.shape), array.tolist())
    return model_input(value.model_input), tensors


def reopen_episode(directory, descriptor, manifest, plan, task, proposal, vision):
    """Reprove the actual provider, GUI, independent save/reset and datum chain."""
    receipt_path = directory / 'rendered-train-receipt.private.json'
    receipt = private_json(receipt_path, descriptor['render_receipt_sha256'], root=directory)
    require(receipt['schema'] == 'envloop-odoo20-real-teacher-render-v1' and
            receipt['task_id'] == task['task_id'] and receipt['source_split'] == 'train' and
            receipt['trial_plan_sha256'] == manifest['trial_plan_sha256'] and
            receipt['proposal_sha256'] == manifest['proposal_ref']['sha256'] and
            receipt['native_saved_state_checked'] is True and
            receipt['formal_large_study_credit'] == 0 and
            receipt['rendered_sha256'] == descriptor['rendered_sha256'],
            'teacher_render_provenance_invalid')
    intent = private_json(directory.parent / (directory.name + '-paid-intent.private.json'), root=directory.parent)
    require(intent['trial_plan_sha256'] == manifest['trial_plan_sha256'] and
            intent['proposal_sha256'] == manifest['proposal_ref']['sha256'] and
            intent['teacher_model'] == plan['models']['teacher'] and intent['task'] == task and
            intent['same_request_replay_authorized'] is False, 'teacher_paid_intent_unbound')
    episode = directory / 'episode.private'
    native_result = private_json(directory / 'native-teacher-result.private.json', root=directory)
    require(native_result['episode_receipt_sha256'] == descriptor['episode_receipt_sha256'],
            'native_episode_hash_unbound')
    native = private_json(episode / 'episode.private.json', descriptor['episode_receipt_sha256'], root=episode)
    _, trace_raw = trial.teacher._reference(episode, native['action_trace_ref'], suffix='.json')
    traces = json.loads(trace_raw)
    require(len(traces) == receipt['teacher_turns'] and traces, 'teacher_trace_count_invalid')
    turns = []
    for index, row in enumerate(traces):
        prefix = f'teacher-call-{index:03d}'
        request = private_json(directory / (prefix + '-request.private.json'), root=directory)
        call_intent = private_json(directory / (prefix + '-intent.private.json'), root=directory)
        provider = private_json(directory / (prefix + '-result.private.json'), row['teacher_result_sha256'], root=directory)
        actual = provider['receipt']
        require(request['model'] == actual.get('reported_model') == plan['models']['teacher'] and
                actual.get('status') == 'completed' and actual.get('response_id') == row['actual_response_id']
                and bool(actual.get('response_id')), 'actual_active_teacher_model_required')
        require(call_intent['before_provider_post'] is True and
                call_intent['same_request_replay_authorized'] is False and
                all(call_intent[k] == row[k] for k in ('step', 'frame_id', 'frame_sha256')) and
                call_intent['task_id'] == task['task_id'], 'teacher_call_intent_mismatch')
        _, frame = trial.teacher._reference(episode, native['frame_refs'][index], suffix='.png')
        require(digest(frame) == row['frame_sha256'] and
                request['image_data_url'] == 'data:image/png;base64,' + base64.b64encode(frame).decode(),
                'teacher_actual_image_changed')
        user = json.loads(request['user_text']); instruction = json.loads(user['instruction'])
        visible = json.loads(user['visible_text'])
        require(instruction['task_instruction'] == task['visible_instruction'] and
                user['researcher_teacher_request'] == proposal['teacher_request'],
                'teacher_public_instruction_or_proposal_changed')
        observation = contract.make_observation(task_id=task['task_id'], task_binding_sha256=task['package_sha256'],
            instruction=instruction['task_instruction'], step=row['step'], screenshot_bytes=frame,
            a11y_text=visible['a11y_text'], dom_text=visible['dom_text'], controls=visible['controls'],
            previous_action_result=instruction['previous_action_result'], memory=instruction['memory'],
            limits=contract.ContractLimits(max_step=plan['actor_limits']['actions']))
        observation = replace(observation, frame_id=row['frame_id'])
        rendered = output.render_for_model(observation)
        require(rendered['instruction'] == user['instruction'] and rendered['visible_text'] == user['visible_text'],
                'teacher_observation_not_exactly_reconstructed')
        action = output.normalize_model_action(provider['text'], observation, current_frame_id=observation.frame_id)
        require(action == row['action'], 'actual_teacher_action_changed')
        turns.append({'observation': observation, 'action': action, 'trace_row': row,
                      'teacher_result_sha256': row['teacher_result_sha256']})
    binding = trial.workers.public_binding()
    require(native['runtime_sha256'] == plan['native_binding_sha256'], 'native_runtime_changed')
    # Adapter is reopened from the source-bound factory module (no native work).
    native_training = trial.workers._model_modules(binding)[0]
    adapter_sha = native_training.adapter_sha256()
    active = SimpleNamespace(runtime_sha256=plan['native_binding_sha256'], adapter_sha256=adapter_sha,
        verifier_sha256=binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'])
    episode_sha = trial.verify_trial_episode(episode, native_result, task, turns, active, plan['models']['teacher'])
    admitted = trial.admissible_training_turns(episode, turns)
    require(len(admitted) == receipt['positive_training_turns'] and
            len(turns) - len(admitted) == receipt['rejected_turns_excluded'], 'native_admitted_turn_count_changed')
    rebuilt = trial.render_trial_turns(task['task_id'], episode_sha, admitted, vision)
    raw = private_bytes(directory / 'trusted-rendered-train.private.pkl', descriptor['rendered_sha256'], root=directory)
    loaded = RestrictedRenderedUnpickler(io.BytesIO(raw)).load()
    require(type(loaded) is dict and set(loaded) == {'datums', 'prompts', 'receipt'} and
            loaded['receipt'] == receipt['renderer_receipt'] == rebuilt.receipt and
            rebuilt.receipt.get('student_inference_prompt_equality_checked') is True and
            len(loaded['datums']) == len(loaded['prompts']) == len(rebuilt.datums),
            'rendered_batch_receipt_or_length_changed')
    for stored, actual in zip(loaded['datums'] + loaded['prompts'], rebuilt.datums + rebuilt.prompts, strict=True):
        require(data_signature(stored) == data_signature(actual), 'rendered_datum_differs_from_actual_trajectory')
    close = private_json(directory / 'teacher-provider-close.private.json', root=directory)
    require(close['real_close_call_returned'] is True and close['owned_callback_completion_proved'] is True,
            'teacher_owned_completion_not_proved')
    # Submit only independently rebuilt values; the pickle never determines data.
    return rebuilt


def checked_train_worker(namespace, ref):
    """The operator manifest binds public TRAIN identity, wherever it resides."""
    require(type(ref) is dict and set(ref) == {'path', 'sha256'} and
            type(ref['path']) is str and type(ref['sha256']) is str and HEX.fullmatch(ref['sha256']),
            'train_worker_reference_invalid')
    worker = Path(ref['path'])
    if not worker.is_absolute():
        require('..' not in worker.parts, 'train_worker_reference_escape')
        worker = Path(namespace) / worker
    require(worker.name == 'train' and worker.is_dir() and not worker.is_symlink(),
            'public_train_worker_only')
    # Directory location is not authority. Both subsequent inputs remain
    # private and hash-bound, and every submitted raw episode is reopened.
    for name in ('task_set_manifest.json', 'partition_cases.json'):
        path = worker / 'private' / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
                'private_train_partition_inputs_required')
    return worker


def load_inputs(*, plan_path, plan_sha, manifest_path, manifest_sha, trust_owned_rendered):
    require(trust_owned_rendered is True, 'explicit_owned_rendered_trust_required')
    plan_path = Path(plan_path).resolve(); namespace = plan_path.parent
    require(namespace.is_relative_to(ROOT / 'work') and Path(manifest_path).parent.resolve() == namespace,
            'same_owned_trial_namespace_required')
    plan = trial.checked_trial(plan_path, plan_sha)
    require(plan['models']['student'] == MODEL and plan['models']['teacher'] == 'gpt-6-sol' and
            plan['models']['initial_researcher'] == 'gpt-6-sol' and
            plan.get('formal_large_study_credit') == 0 and plan.get('unknown_billing_is_null') is True,
            'active_sol6_pilot_epoch_required')
    manifest = private_json(manifest_path, manifest_sha, root=namespace)
    require(manifest['schema'] == SCHEMA and manifest['trial_plan_sha256'] == plan_sha and
            manifest['formal_large_study_credit'] == 0, 'explicit_pilot_training_authority_required')
    check_sources(manifest)
    training, training_sha = frozen_training(manifest, namespace, plan)
    worker = checked_train_worker(namespace, manifest['train_worker_ref'])
    task_set = private_json(worker / 'private/task_set_manifest.json',
                            manifest['train_worker_ref']['sha256'], root=worker)
    rows = task_set['train']
    require(len(rows) == len({r['task_id'] for r in rows}) == 20 and
            not {r['task_id'] for r in rows} & {r['task_id'] for r in plan.get('final_tasks_metadata', [])} and
            all('-HID-' not in r['task_id'] and '-RSV-' not in r['task_id'] for r in rows),
            'exact_twenty_public_train_ids_required')
    world = private_json(worker / 'private/partition_cases.json', manifest['train_cases_sha256'], root=worker)
    cases = {c['id']: c for group in world['cases'].values() for c in group}
    require(set(cases) == {r['task_id'] for r in rows}, 'public_train_world_changed')
    proposal_path = reference(namespace, manifest['proposal_ref'])
    proposal = trial.checked_proposal(proposal_path, manifest['proposal_ref']['sha256'], plan['models']['initial_researcher'])
    require(set(proposal) == {'hypothesis', 'train_task_ids', 'teacher_request'} and
            0 < len(proposal['train_task_ids']) <= 4 and
            len(set(proposal['train_task_ids'])) == len(proposal['train_task_ids']) and
            set(proposal['train_task_ids']) <= set(cases), 'actual_public_train_proposal_required')
    descriptors = manifest['batches']
    require(type(descriptors) is list and 0 < len(descriptors) <= 4 and
            len({b['task_id'] for b in descriptors}) == len(descriptors) and
            {b['task_id'] for b in descriptors} == set(proposal['train_task_ids']), 'complete_proposed_training_batch_required')
    require(len(descriptors) >= training['minimum_distinct_training_tasks'] and
            len({cases[b['task_id']]['family'] for b in descriptors}) >= training['minimum_distinct_workflows'],
            'four_actual_public_training_workflows_required')
    vision = trial.teacher._load_renderer()
    datums, prompts, receipts = [], [], []
    for descriptor in descriptors:
        require(descriptor['task_id'] in cases, 'hidden_or_foreign_training_id')
        relative = Path(descriptor['directory'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'teacher_directory_escape')
        directory = namespace / relative
        require(directory.is_dir() and not directory.is_symlink(), 'owned_teacher_directory_required')
        task_id = descriptor['task_id']
        task = {'task_id': task_id, 'package_sha256': next(r['package_sha256'] for r in rows if r['task_id'] == task_id),
                'visible_instruction': cases[task_id]['prompt']}
        batch = reopen_episode(directory, descriptor, manifest, plan, task, proposal, vision)
        datums.extend(batch.datums); prompts.extend(batch.prompts); receipts.append(batch.receipt)
    indices, scheduled = fixed_schedule(datums, training)
    return SimpleNamespace(plan=plan, manifest=manifest, training=training, training_sha=training_sha,
        namespace=namespace, datums=datums, prompts=prompts, receipts=receipts, indices=indices,
        scheduled_tokens=scheduled, identity=digest(json.dumps({'plan': plan_sha, 'training': training_sha,
           'proposal': manifest['proposal_ref']['sha256'],
           'batches': sorted((b['task_id'], b['episode_receipt_sha256'], b['rendered_sha256'])
                             for b in descriptors)}, sort_keys=True).encode()))


def fixed_schedule(datums, training):
    capacity = training['batch_size'] * training['optimizer_steps']
    require(datums and len(datums) <= capacity, 'pilot_fixed_schedule_capacity_prerequisite')
    lengths = [d.model_input.length for d in datums]
    require(all(type(n) is int and 0 < n <= training['max_supervised_tokens'] for n in lengths),
            'pilot_supervised_token_cap')
    indices = [[(step * training['batch_size'] + offset) % len(datums)
                for offset in range(training['batch_size'])] for step in range(training['optimizer_steps'])]
    require({i for row in indices for i in row} == set(range(len(datums))), 'pilot_fixed_schedule_omits_datum')
    scheduled = sum(lengths[i] for row in indices for i in row)
    require(scheduled <= training['max_scheduled_tokens'], 'pilot_scheduled_token_cap_prerequisite')
    return indices, scheduled


def no_retry_service_class():
    """Tinker 0.30 training retries live on holders, separate from HTTP retries."""
    import tinker
    from tinker.lib.internal_client_holder import InternalClientHolder
    from tinker.lib.public_interfaces.service_client import ServiceClient
    require(tinker.__version__ == '0.30.0', 'inspected_tinker_030_required')
    for name, expected in SDK_SHA256S.items():
        require(digest(Path(importlib.import_module(name).__file__).read_bytes()) == expected,
                'inspected_tinker_sdk_source_changed')
    class OwnedHolder(InternalClientHolder):
        async def execute_with_retries(self, func, *args, **kwargs):
            return await func(*args, **kwargs)
    methods = {}
    for name in ('_get_session_holder', '_get_rest_holder'):
        original = getattr(ServiceClient, name)
        require(original.__globals__['InternalClientHolder'] is InternalClientHolder,
                'tinker_holder_namespace_changed')
        scoped = FunctionType(original.__code__, {**original.__globals__, 'InternalClientHolder': OwnedHolder},
                              original.__name__, original.__defaults__, original.__closure__)
        scoped.__kwdefaults__ = original.__kwdefaults__
        methods[name] = scoped
    return type('Odoo20OwnedNoRetryService', (ServiceClient,), methods)


class OwnedCalls:
    """Each mutation has one durable intent and one retained completion/error."""
    def __init__(self, out, identity):
        self.out, self.identity = out, identity
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='owned-odoo20-tinker')
        self.futures = []

    def call(self, name, request, callback, summarize=lambda x: x, timeout=300):
        write(self.out / (name + '-intent.private.json'), {'schema': 'envloop-odoo20-tinker-operation-intent-v1',
            'dataset_identity': self.identity, 'operation': name, 'request': request,
            'before_provider_call': True, 'automatic_replay_authorized': False, 'actual_cost_usd': None})
        def invoke():
            try:
                result = callback()
                if hasattr(result, 'result'):
                    result = result.result()
                retained = summarize(result)
                write(self.out / (name + '-result.private.json'), {'status': 'completed', 'result': retained,
                    'actual_cost_usd': None, 'formal_large_study_credit': 0})
                return result
            except BaseException as exc:
                write(self.out / (name + '-error.private.json'), {'status': 'uncertain_no_replay',
                    'error_type': type(exc).__name__, 'error': str(exc)[:8000], 'actual_cost_usd': None,
                    'automatic_replay_authorized': False, 'formal_large_study_credit': 0})
                raise
        future = self.pool.submit(invoke); self.futures.append(future)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            write(self.out / (name + '-deadline.private.json'), {'status': 'uncertain_owned_future_retained',
                'automatic_replay_authorized': False, 'actual_cost_usd': None})
            raise TrainingError('provider_completion_uncertain_no_replay') from None

    def settle(self, timeout=30):
        _, pending = wait(self.futures, timeout=timeout)
        self.pool.shutdown(wait=not pending, cancel_futures=False)
        return {'submitted_calls': len(self.futures), 'all_owned_calls_settled': not pending,
                'pending_owned_calls': len(pending)}


def retain_response(value):
    """Retain actual Rust-dataclass and Pydantic SDK outputs, including tensors."""
    import numpy as np
    from tinker import types
    if type(value) is types.TensorData:
        return {'dtype': value.dtype, 'shape': list(value.shape), 'data': value.to_numpy().tolist()}
    if hasattr(value, 'model_dump'):
        return retain_response(value.model_dump(mode='python'))
    if is_dataclass(value):
        return {field.name: retain_response(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, np.ndarray):
        return retain_response(value.tolist())
    if isinstance(value, np.generic):
        return retain_response(value.item())
    if type(value) is dict:
        return {str(key): retain_response(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [retain_response(item) for item in value]
    if type(value) is bytes:
        return {'base64': base64.b64encode(value).decode()}
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        import math
        return value if math.isfinite(value) else {'nonfinite_float': repr(value)}
    raise TrainingError('actual_provider_response_not_serializable')


def train_real(inputs, out):
    import tinker
    from tinker import types
    from tinker.lib.retry_handler import RetryConfig
    service_class = no_retry_service_class()
    calls = OwnedCalls(out, inputs.identity); service = None; status = 'errored'
    result = None
    try:
        service = service_class(max_retries=0, user_metadata={'purpose': 'envloop-odoo20-train-only-v1',
            'dataset_identity': inputs.identity, 'cell_id': 'odoo-community', 'split': 'train'})
        calls.call('session-create', {'model': MODEL, 'max_retries': 0, 'holder_retries': False},
            lambda: service.holder, lambda h: {'session_id': h.get_session_id()})
        client = calls.call('lora-create', {'model': MODEL, 'rank': inputs.training['lora_rank'],
            'seed': inputs.training['seed'], 'optimizer': 'adamw'},
            lambda: service.create_lora_training_client(base_model=MODEL, rank=inputs.training['lora_rank'],
                seed=inputs.training['seed'], optimizer=types.AdamOptimizerConfig()),
            lambda c: {'model_id': str(c.model_id)})
        for step, indices in enumerate(inputs.indices):
            batch = [inputs.datums[i] for i in indices]
            calls.call(f'step-{step:04d}-forward-backward', {'datum_indices': indices, 'loss_fn': 'cross_entropy'},
                lambda batch=batch: client.forward_backward(batch, 'cross_entropy'), retain_response)
            params = types.AdamParams(learning_rate=float(inputs.training['learning_rate']))
            calls.call(f'step-{step:04d}-optim', params.model_dump(mode='json'),
                lambda: client.optim_step(params), retain_response)
        checkpoint = calls.call('sampler-weights-save', {'name': 'odoo20-' + inputs.identity[:24]},
            lambda: client.save_weights_for_sampler('odoo20-' + inputs.identity[:24]), retain_response)
        require(type(checkpoint.path) is str and re.fullmatch(r'tinker://[^\s/]+/sampler_weights/[^\s/]+', checkpoint.path),
                'actual_sampler_checkpoint_required')
        sampler = calls.call('sampler-create', {'model_path': checkpoint.path, 'retry_logic': False},
            lambda: service.create_sampling_client(model_path=checkpoint.path,
                retry_config=RetryConfig(enable_retry_logic=False)), lambda s: {'response_type': type(s).__name__})
        base = calls.call('sampler-base-read', {}, sampler.get_base_model)
        require(base == MODEL, 'actual_checkpoint_base_model_changed')
        sample = calls.call('checkpoint-sample', {'prompt_index': 0, 'max_tokens': inputs.training['sample_max_tokens'],
            'temperature': 0, 'seed': inputs.training['seed']}, lambda: sampler.sample(prompt=inputs.prompts[0], num_samples=1,
                sampling_params=types.SamplingParams(max_tokens=inputs.training['sample_max_tokens'],
                temperature=0, seed=inputs.training['seed'])), retain_response)
        require(len(sample.sequences) == 1 and len(sample.sequences[0].tokens) <= inputs.training['sample_max_tokens'],
                'actual_checkpoint_sample_invalid')
        result = {'schema': 'envloop-odoo20-actual-tinker-training-result-v1', 'checkpoint_path': checkpoint.path,
            'dataset_identity': inputs.identity, 'model': MODEL, 'observed_base_model': base,
            'optimizer_steps_completed': len(inputs.indices), 'scheduled_tokens': inputs.scheduled_tokens,
            'sample_token_count': len(sample.sequences[0].tokens), 'actual_cost_usd': None,
            'formal_large_study_credit': 0, 'full_six_environment_publication_claim': False}
        status = 'success'
    finally:
        close_returned = False
        try:
            if service is not None:
                calls.call('service-close', {'status': status}, lambda: service.close(status), retain_response, timeout=30)
                close_returned = True
        finally:
            lifecycle = calls.settle()
            holders = [] if service is None else [h for h in (service._session_holder, service._rest_holder) if h is not None]
            closed = close_returned and bool(holders) and all(h._closed for h in holders) and lifecycle['all_owned_calls_settled']
            write(out / 'owned-provider-close.private.json', {'real_close_call_returned': close_returned,
                'owned_client_cleanup_proved': closed, 'lifecycle': lifecycle, 'actual_cost_usd': None,
                'formal_large_study_credit': 0, 'provider_model_completion_inferred_from_close': False})
    require(closed, 'owned_provider_cleanup_unproved')
    write(out / 'actual-training-result.private.json', result)
    return result


def run(*, plan_path, plan_sha, manifest_path, manifest_sha, output_root,
        execute=False, trust_owned_rendered=False):
    inputs = load_inputs(plan_path=plan_path, plan_sha=plan_sha, manifest_path=manifest_path,
                         manifest_sha=manifest_sha, trust_owned_rendered=trust_owned_rendered)
    require(execute is True, 'explicit_trial_training_dispatch_required')
    require(bool(os.environ.get('TINKER_API_KEY')), 'tinker_key_required_before_dispatch')
    out = Path(output_root)
    require(not out.is_symlink() and out.parent.resolve() == inputs.namespace and not out.exists(),
            'fresh_owned_training_output_required')
    # A process crash or error consumes this dataset identity across output names.
    claim = inputs.namespace / ('tinker-training-' + inputs.identity + '-consumed.private.json')
    require(not claim.exists(), 'dataset_dispatch_already_consumed_no_replay')
    out.mkdir(mode=0o700)
    write(claim, {'schema': 'envloop-odoo20-training-consumed-v1', 'dataset_identity': inputs.identity,
                 'output_root': str(out.resolve()), 'automatic_replay_authorized': False, 'actual_cost_usd': None})
    write(out / 'training-request.private.json', {'schema': 'envloop-odoo20-tinker-training-request-v1',
        'dataset_identity': inputs.identity, 'trial_plan_sha256': plan_sha, 'manifest_sha256': manifest_sha,
        'training_asset_sha256': inputs.training_sha, 'model': MODEL,
        'teacher_model': inputs.plan['models']['teacher'], 'datum_count': len(inputs.datums),
        'fixed_training_settings': inputs.training, 'scheduled_tokens': inputs.scheduled_tokens,
        'actual_cost_usd': None, 'formal_large_study_credit': 0, 'automatic_replay_authorized': False})
    result = train_real(inputs, out)
    return {'status': 'actual_pilot_training_checkpoint_saved', 'dataset_identity': inputs.identity,
            'checkpoint_path_sha256': digest(result['checkpoint_path'].encode()),
            'optimizer_steps_completed': result['optimizer_steps_completed'], 'actual_cost_usd': None,
            'formal_large_study_credit': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'manifest-path', 'manifest-sha', 'output-root'):
        parser.add_argument('--' + field, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--trust-owned-rendered', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__':
    main()
