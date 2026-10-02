"""Recovery-ready Tinker primitives; constructing classes performs no API call.

V1/V2 sources and consumed claims stay immutable. Future IDs are persisted
before SDK result polling; account HTTP 402 fails immediately. A separate
explicit authority is required for a fresh model attempt, never an automatic
resubmission of an uncertain forward/backward request.
"""
from __future__ import annotations

from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import re
import time
from types import FunctionType

from . import twenty_task_trial_training_v1 as base

ROOT = Path(__file__).resolve().parents[2]
RESTART_SCHEMA = 'envloop-odoo20-explicit-fresh-tinker-restart-v1'


def _clone(function, changes):
    scoped = FunctionType(function.__code__, {**function.__globals__, **changes},
                          function.__name__, function.__defaults__, function.__closure__)
    scoped.__kwdefaults__ = function.__kwdefaults__
    return scoped


def future_metadata_factory(out, delegate):
    """Capture genuine server future IDs before delegate starts retrieving them."""
    out = Path(out)
    base.require(out.is_dir() and not out.is_symlink() and out.stat().st_mode & 0o077 == 0,
                 'owned_future_metadata_directory_required')
    def tracked(model_cls, holder, untyped_future, *args, **kwargs):
        request_id = getattr(untyped_future, 'request_id', None)
        base.require(type(request_id) is str and bool(request_id), 'actual_server_future_id_required')
        frame = inspect.currentframe().f_back
        try:
            local = frame.f_locals
            counter = local.get('request_id')
            client = local.get('self')
            actual_model = getattr(client, 'model_id', None)
            model_sequence = local.get('model_seq_id')
            caller = frame.f_code.co_name
        finally:
            del frame
        # The integer is read from the exact SDK closure, never inferred from
        # the number of receipts or substituted for the server future UUID.
        sequence = counter+1 if type(counter) is int and counter >= 0 else None
        row = {'schema':'envloop-odoo20-actual-sdk-future-metadata-v1',
            'request_id':request_id, 'session_id':holder.get_session_id(),
            'model_id':actual_model if type(actual_model) is str else None,
            'training_seq_id':sequence,
            'model_seq_id':model_sequence if type(model_sequence) is int else None,
            'request_type':kwargs.get('request_type'), 'model_class':model_cls.__name__,
            'sdk_caller':caller, 'captured_at_unix':time.time(),
            'request_start_time':kwargs.get('request_start_time'),
            'before_sdk_future_result_polling':True, 'mutation_resubmission_authorized':False,
            'actual_cost_usd':None}
        path = out/('sdk-future-'+sha256(request_id.encode()).hexdigest()+'.private.json')
        base.write(path, row)
        return delegate(model_cls, holder, untyped_future, *args, **kwargs)
    return tracked


def recovery_ready_service_class(out):
    """Same real SDK, scoped metadata capture and no billing-pause polling."""
    from tinker.lib.public_interfaces.service_client import ServiceClient
    from tinker.lib.public_interfaces.training_client import TrainingClient
    from tinker.lib.api_future_impl import _APIFuture
    original_service = base.no_retry_service_class()  # verifies SDK 0.30 hashes
    original_holder = original_service._get_session_holder.__globals__['InternalClientHolder']
    class BillingFailFastHolder(original_holder):
        def _should_pause_on_billing(self, status_code, detail):
            return False
    tracked_future = future_metadata_factory(out, _APIFuture)
    training_methods = {name:_clone(getattr(TrainingClient,name), {'_APIFuture':tracked_future})
        for name in ('_run_fwd_bwd','optim_step','save_state','_save_weights_for_sampler_impl','_load_state_impl')}
    scoped_training = type('Odoo20RecoveryOwnedTrainingClient', (TrainingClient,), training_methods)
    methods = {name:_clone(getattr(original_service,name), {'InternalClientHolder':BillingFailFastHolder})
        for name in ('_get_session_holder','_get_rest_holder')}
    methods['_create_lora_training_client_submit'] = _clone(
        ServiceClient._create_lora_training_client_submit, {'_APIFuture':tracked_future})
    def create_lora_training_client(self, *args, **kwargs):
        client = ServiceClient.create_lora_training_client(self, *args, **kwargs)
        # Adopt the actual fresh client locally. Its real model ID, counters,
        # locks and holder are preserved; no model/client creation is replayed.
        owned = object.__new__(scoped_training)
        owned.__dict__.update(client.__dict__)
        return owned
    methods['create_lora_training_client'] = create_lora_training_client
    return type('Odoo20RecoveryOwnedService', (original_service,), methods)


def failed_attempt(root):
    """Read retained identity and known frontier, without claiming live weights."""
    root = Path(root).resolve()
    base.require(root.is_relative_to(ROOT/'work') and root.is_dir(), 'owned_failed_attempt_required')
    request = base.private_json(root/'training-request.private.json', root=root)
    session = base.private_json(root/'session-create-result.private.json', root=root)
    model = base.private_json(root/'lora-create-result.private.json', root=root)
    base.require(session['status'] == model['status'] == 'completed', 'actual_prior_session_and_model_required')
    completed = []
    for path in sorted(root.glob('step-*-optim-result.private.json')):
        row = base.private_json(path, root=root)
        if row['status'] == 'completed':
            completed.append(int(path.name.split('-')[1]))
    uncertain = sorted(path.name for path in root.glob('step-*-forward-backward-deadline.private.json'))
    base.require(uncertain and not (root/'actual-training-result.private.json').exists(),
                 'failed_uncertain_attempt_required')
    return {'dataset_identity':request['dataset_identity'], 'model':request['model'],
        'optimizer_steps_planned':request['fixed_training_settings']['optimizer_steps'],
        'completed_optimizer_step_indices':completed, 'uncertain_forward_backward_deadlines':uncertain,
        'actual_session_id':session['result']['session_id'], 'actual_model_id':model['result']['model_id'],
        'training_request_sha256':base.digest((root/'training-request.private.json').read_bytes()),
        'saved_state_checkpoint_locally_recorded':bool(list(root.glob('*save-state*result.private.json'))),
        'saved_sampler_checkpoint_locally_recorded':(root/'sampler-weights-save-result.private.json').exists(),
        'prior_optimizer_state_recoverable_proved':False}


def readonly_status_queries(prior):
    """Descriptors only; callers must separately authorize/retain real reads."""
    return [('get_training_run',prior['actual_model_id']),
            ('get_session',prior['actual_session_id']),
            ('list_checkpoints',prior['actual_model_id'])]


EXECUTION_SOURCE_FILES = (
    'enterprise_fallback/odoo18/tinker_trial_recovery_v1.py',
    'enterprise_fallback/odoo18/twenty_task_trial_training_restart_v1.py',
    'tools/check_odoo20_tinker_access_v1.py',
)


def check_execution_sources(expected):
    base.require(type(expected) is dict and set(expected) == set(EXECUTION_SOURCE_FILES),
                 'exact_restart_execution_sources_required')
    for name, hashed in expected.items():
        base.require(base.digest((ROOT/name).read_bytes()) == hashed, 'restart_execution_source_changed')


def checked_access(reference, terminal_ref):
    """Same genuine capabilities/terminal derivation as the root recovery gate."""
    def read(ref):
        path = Path(ref['path'])
        base.require(path.is_absolute() and not path.is_symlink(), 'absolute_private_access_reference_required')
        return base.private_json(path, ref['sha256'], root=ROOT/'work')
    access = read(reference); terminal = read(terminal_ref)
    base.require(access.get('schema') == 'envloop-odoo20-tinker-access-restored-v1' and access.get('status') == 'ready' and
        access.get('model') == base.MODEL and access.get('provider_http_status') == 200 and access.get('error_type') is None and
        access.get('actual_provider_call') is True and access.get('checked_after_prior_terminal') is True and
        access.get('prior_terminal_ref') == terminal_ref and
        access.get('supported_model_verified') is access.get('owned_close_returned') is True and
        access.get('owned_close_awaited') is True and
        access.get('checker_source_sha256') == base.digest((ROOT/'tools/check_odoo20_tinker_access_v1.py').read_bytes()) and
        type(access.get('started_at')) in (int, float) and type(access.get('ended_at')) in (int, float) and
        access['started_at'] >= terminal['ended_at'] and access['ended_at'] >= access['started_at'] and
        access.get('checked_at') == access['ended_at'] and
        access.get('training_calls') == access.get('model_sampling_calls') == access.get('automatic_retries') ==
        access.get('formal_large_study_credit') == 0 and access.get('actual_cost_usd') is None and
        access.get('raw_provider_evidence_ref') is not None, 'genuine_access_after_prior_terminal_required')
    raw = read(access['raw_provider_evidence_ref'])
    matching = [row for row in raw.get('supported_models', []) if row.get('model_name') == base.MODEL]
    base.require(len(matching) == 1 and matching[0].get('trainable') is not False and
        matching[0].get('sampleable') is not False, 'actual_capabilities_model_list_required')
    from tools.check_odoo20_tinker_access_v1 import result_receipt
    expected = result_receipt(terminal_ref=terminal_ref, terminal=terminal,
        started_at=access['started_at'], ended_at=access['ended_at'], capabilities=raw,
        status_code=200, error_type=None, close_returned=True,
        raw_provider_evidence_ref=access['raw_provider_evidence_ref'])
    base.require(access == expected, 'actual_root_access_checker_receipt_changed')
    return access


def checked_restart_authority(path, expected_sha, *, inputs, prior_root):
    """Explicit fresh-attempt policy; never delete or bypass the old claim."""
    namespace = Path(inputs.namespace).resolve()
    prior_root = Path(prior_root).resolve()
    prior = failed_attempt(prior_root)
    authority = base.private_json(path, expected_sha, root=namespace)
    required = {'schema','dataset_identity','model','optimizer_steps','prior_training_request_sha256',
                'prior_consumed_claim_ref','retire_prior_attempt','start_from_fresh_base',
                'carry_prior_model_state','automatic_replay_authorized','fresh_restart_authorized',
                'billing_access_receipt_ref','prior_terminal_ref','execution_source_sha256s','new_attempt_nonce','new_output_name'}
    base.require(set(authority) == required and authority['schema'] == RESTART_SCHEMA and
        authority['dataset_identity'] == inputs.identity == prior['dataset_identity'] and
        authority['model'] == inputs.training['model'] == prior['model'] and
        authority['optimizer_steps'] == inputs.training['optimizer_steps'] == prior['optimizer_steps_planned'] == 192 and
        authority['prior_training_request_sha256'] == prior['training_request_sha256'] and
        authority['retire_prior_attempt'] is True and authority['start_from_fresh_base'] is True and
        authority['carry_prior_model_state'] is False and authority['automatic_replay_authorized'] is False and
        authority['fresh_restart_authorized'] is True,
        'explicit_retired_fresh_restart_authority_required')
    check_execution_sources(authority['execution_source_sha256s'])
    terminal_ref = authority['prior_terminal_ref']
    terminal = base.private_json(terminal_ref['path'], terminal_ref['sha256'], root=ROOT/'work')
    base.require(terminal.get('exit_code') == 1 and terminal.get('automatic_restarts') == 0 and
        type(terminal.get('pid')) is int and terminal['pid'] > 0 and
        type(terminal.get('ended_at')) in (int, float), 'prior_failed_worker_terminal_required')
    try:
        os.kill(terminal['pid'], 0)
    except ProcessLookupError:
        pass
    else:
        base.require(False, 'prior_worker_not_proved_dead')
    latest = max((path.stat().st_mtime for pattern in ('*-deadline.private.json','*-error.private.json','owned-provider-close.private.json')
                  for path in prior_root.glob(pattern)), default=0)
    base.require(terminal['ended_at'] >= latest, 'prior_worker_terminal_precedes_late_completion')
    claim_ref = authority['prior_consumed_claim_ref']
    claim_path = base.reference(namespace,claim_ref)
    claim = base.private_json(claim_path,claim_ref['sha256'],root=namespace)
    base.require(claim['dataset_identity'] == inputs.identity and Path(claim['output_root']).resolve() == prior_root and
                 claim['automatic_replay_authorized'] is False, 'prior_failed_claim_not_bound')
    checked_access(authority['billing_access_receipt_ref'], authority['prior_terminal_ref'])
    nonce = authority['new_attempt_nonce']; name = authority['new_output_name']
    base.require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce) and
                 type(name) is str and re.fullmatch(r'[a-zA-Z0-9_-]+\.private',name) and
                 not (namespace/name).exists() and not (namespace/name).is_symlink(),
                 'fresh_restart_namespace_required')
    return {**prior, 'new_output_root':str(namespace/name), 'restart_authority_sha256':expected_sha,
        'restart_claim_identity':base.digest(json.dumps({'dataset':inputs.identity,'authority':expected_sha,'nonce':nonce},
                                                       sort_keys=True).encode()),
        'unknown_prior_forward_backward_resubmitted':False,
        'execution_source_sha256s':authority['execution_source_sha256s']}
