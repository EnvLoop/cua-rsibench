"""Saved-only Odoo selection prefix recovery and explicit continuation contract.

This module never constructs a sampler, starts a browser, or dispatches a task.
V3/native sources remain immutable. One incomplete infrastructure attempt is
excluded without a score; replacing the whole task requires separate review
and genuine post-terminal provider access evidence.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sqlite3
from types import FunctionType, SimpleNamespace

from . import native_surface_workers_v14 as workers
from . import native_surface_final_worker_v1 as legacy
from . import twenty_task_trial_evaluator_v3 as evaluator
from . import twenty_task_trial_readback_v3 as readback
from . import twenty_task_trial_selection_v3 as original

ROOT, MODEL = evaluator.ROOT, evaluator.MODEL
require, digest, private, write = legacy.require, legacy.digest, legacy.private, legacy.write
SCHEMA = 'envloop-odoo20-saved-selection-prefix-candidate-v4'
STATUS = 'three_saved_cases_reaudited_one_infrastructure_attempt_excluded'
LIMITS = {'actions': 90, 'actor_seconds': 720, 'owned_lifecycle_seconds': 1200}


def source_binding():
    parent = original.source_binding()
    value = {'schema': 'envloop-odoo20-prefix-recovery-source-v4',
        'original_selection_source_binding': parent,
        'native_binding_sha256': workers.public_binding()['binding_sha256'],
        'source_sha256': digest(Path(__file__).read_bytes()),
        'provider_access_checker_sha256': digest((ROOT/'tools/check_odoo20_tinker_access_v1.py').read_bytes()),
        'orchestration_only': True, 'actor_sampler_scorer_reset_changed': False,
        'per_task_limits': LIMITS, 'provider_calls': 0, 'native_calls': 0}
    return {**value, 'binding_sha256': digest(legacy.final.canonical(value))}


def absolute_ref(path, expected=None):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink(), 'prefix_absolute_private_reference_required')
    raw = private(path)
    require(expected is None or digest(raw) == expected, 'prefix_absolute_reference_changed')
    return {'path': str(path), 'sha256': digest(raw)}


def _dead_terminal(path, expected):
    value = workers.private_json(path, expected)
    require(value['exit_code'] == 1 and value['automatic_restarts'] == 0 and
        type(value['pid']) is int and value['pid'] > 0 and value['ended_at'] >= value['started_at'],
        'prefix_failed_terminal_required')
    try:
        os.kill(value['pid'], 0)
    except ProcessLookupError:
        return value
    require(False, 'prefix_original_worker_still_live')


def _journal(episode):
    """Read SQLite in immutable read-only mode; never repair or mutate a journal."""
    path = Path(episode)/'sampling-journal/requests.sqlite3'
    private(path)
    require(not path.with_name(path.name+'-wal').exists(), 'prefix_unsettled_sqlite_wal_forbidden')
    connection = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        values = connection.execute('SELECT id, state, result FROM requests ORDER BY rowid').fetchall()
        return [(key, state, json.loads(result)) for key, state, result in values]
    finally:
        connection.close()


def _cleanup(value):
    require(type(value) is dict and value.get('schema') == 'envloop-odoo-v066-selection-local-runtime-v1' and
        value.get('final_database_snapshot_equal') is True and value.get('final_physical_filestore_equal') is True and
        value.get('services_restored_to_initial_state') is True and value.get('provider_invoice_usd') is None,
        'prefix_actual_outer_reset_and_services_unproved')


def _audit_saved(episode, task, packet, worker, binding, selector, review):
    row = workers.private_json(episode/'native-row.private.json')
    require(packet['schema'] == 'envloop-odoo20-selection-task-result-v3' and packet['task'] == task and
        packet['native_row'] == row and packet['trial_plan_sha256'] == review['trial_plan_sha256'] and
        packet['checkpoint_sha256'] == digest(MODEL.encode()) and packet['formal_large_study_credit'] == 0 and
        packet['actual_cost_usd'] is packet['provider_invoice_sha256'] is None,
        'prefix_exact_original_completed_packet_required')
    selector._audit_task_artifacts(episode, task, row)
    setup = workers.private_json(episode/'paid-setup-result.private.json')
    identity = setup['actual_backend_identity']
    require(setup['status'] == 'ready' and identity['model'] == MODEL and identity['sampling_kind'] == 'base' and
        identity['checkpoint_sha256'] == selector.vision_digest(MODEL) and identity['seed'] == review['sampling_seed'] and
        identity['temperature'] == 0, 'prefix_same_actual_base_sampler_required')
    calls = packet['provider_calls']
    require(len(calls) == row['sample_count'] and bool(calls), 'prefix_actual_completed_call_coverage_required')
    journal = _journal(episode)
    require(len(journal) == len(calls), 'prefix_original_journal_call_count_changed')
    for call, (request_id, state, result) in zip(calls, journal, strict=True):
        intent = readback.read_ref(episode, call['intent'])
        retained = readback.read_ref(episode, call['result'])
        require(state == 'complete' and retained == result and retained['status'] == 'completed' and
            retained['request_id'] == request_id == call['request_id'] == intent['request_id'] and
            retained['new_dispatch'] is True and retained['reused'] is False and
            intent['task_id'] == task['task_id'] and intent['package_sha256'] == task['package_sha256'] and
            intent['same_request_replay_authorized'] is False and
            call['paid_attempt_id'] == intent['paid_attempt_id'], 'prefix_original_completed_call_changed')
    proofs = [legacy.final.reference(episode, path) for path in sorted(episode.glob('live-proof-*.private.json'))]
    require(len(proofs) >= 2, 'prefix_independent_saved_proofs_required')
    context = readback.read_ref(episode, proofs[-1])['context']
    gold = {'purchase': 'development_gold.json', 'inventory': 'replenishment_gold.json',
        'sales': 'sales_gold.json', 'crm': 'crm_gold.json'}[context['family']]
    expected = {'family': context['family'], 'target': workers.private_json(worker/'private'/gold)[task['task_id']],
        'baseline': workers.private_json(worker/'private/baseline_snapshot.json'),
        'frozen_files': workers.private_json(worker/'private/baseline-filestore-manifest.json')}
    require(context == expected, 'prefix_original_gold_baseline_context_changed')
    verify = importlib.import_module('verify')
    require(Path(verify.__file__).resolve() == ROOT/'enterprise_fallback/odoo18/verify.py' and
        digest(Path(verify.__file__).read_bytes()) == binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'],
        'prefix_original_independent_verifier_changed')
    _cleanup(packet['runtime_cleanup'])
    environment = SimpleNamespace(proofs=proofs, proof_context=context, runtime_receipt=packet['runtime_cleanup'])
    auditor = evaluator.audit_saved_episode
    proxy = SimpleNamespace(**{**vars(legacy), '_modules': lambda *args: (None, None, None, verify, None)})
    audit = FunctionType(auditor.__code__, {**auditor.__globals__, 'legacy': proxy},
        auditor.__name__, auditor.__defaults__, auditor.__closure__)
    audit.__kwdefaults__ = auditor.__kwdefaults__
    actual = audit(episode, task, row, environment, selector, binding, worker, SimpleNamespace(calls=calls))
    require(actual == {key: packet[key] for key in actual}, 'prefix_saved_packet_independent_recomputation_changed')
    return {'task': task, 'episode_root': str(episode),
        'native_row': legacy.final.reference(episode, episode/'native-row.private.json'),
        'paid_setup_result': legacy.final.reference(episode, episode/'paid-setup-result.private.json')}, row['score']


def _audit_exclusion(episode, task):
    """Incomplete provider fault is never a failure score or model deadline."""
    failure = workers.private_json(episode/'selection-task-failure.private.json')
    require(failure['schema'] == 'envloop-odoo20-selection-task-failure-v3' and failure['task'] == task and
        failure['same_request_replay_authorized'] is False and failure['formal_large_study_credit'] == 0 and
        failure['actual_cost_usd'] is None, 'prefix_infrastructure_failure_identity_changed')
    require(all(not (episode/name).exists() for name in ('selection-task-result.private.json', 'native-row.private.json',
        'saved-state.private.json', 'verifier.private.json', 'actor-clock/end.private.json',
        'actor-clock/complete-lifecycle.private.json')), 'prefix_incomplete_attempt_cannot_have_model_outcome')
    _cleanup(failure['runtime_cleanup'])
    close = workers.private_json(episode/'actor-clock/provider-close.private.json')
    require(close['status'] == 'acknowledged' and close['real_close_call_returned'] is True and
        close['new_model_requests'] == close['automatic_model_retries'] == 0,
        'prefix_failed_provider_close_unproved')
    calls, journal = failure['paid_calls'], _journal(episode)
    require(len(calls) == len(journal) >= 2, 'prefix_failed_call_journal_coverage_required')
    completed = []
    for index, (call, (request_id, state, result)) in enumerate(zip(calls, journal, strict=True)):
        intent = readback.read_ref(episode, call['intent'])
        require(state == 'complete' and intent['request_id'] == call['request_id'] == request_id == result['request_id'] and
            intent['task_id'] == task['task_id'] and intent['package_sha256'] == task['package_sha256'] and
            call['paid_attempt_id'] == intent['paid_attempt_id'] and intent['same_request_replay_authorized'] is False and
            result['new_dispatch'] is True and result['reused'] is False, 'prefix_failed_original_request_changed')
        if index < len(calls)-1:
            require(result['status'] == 'completed' and readback.read_ref(episode, call['result']) == result,
                'prefix_failed_attempt_completed_prefix_changed')
            completed.append(request_id)
        else:
            require(call['result'] is None and result['status'] == 'error' and
                result['error_subtype'] == 'provider_timeout_uncertain' and
                result['dispatch_may_have_occurred'] is True and result['elapsed_seconds'] >= 120,
                'prefix_last_request_must_remain_uncertain')
            last = result
    return {'ordinal': 3, 'task': task, 'classification': 'provider_infrastructure_uncertain_no_model_score',
        'model_score': None, 'original_attempt_id': calls[-1]['paid_attempt_id'],
        'completed_sample_calls': len(completed), 'uncertain_request_ids': [last['request_id']],
        'completed_request_ids': completed, 'original_request_replay_authorized': False,
        'original_attempt_resume_authorized': False, 'whole_task_replacement_requires_separate_authority': True,
        'outer_runtime_cleanup': failure['runtime_cleanup'], 'provider_close_acknowledged': True,
        'failure_ref': absolute_ref(episode/'selection-task-failure.private.json'),
        'journal_ref': absolute_ref(episode/'sampling-journal/requests.sqlite3'),
        'provider_close_ref': absolute_ref(episode/'actor-clock/provider-close.private.json'),
        'original_episode_root': str(episode), 'actual_cost_usd': None}


def inspect_prefix(*, plan_path, plan_sha, old_output_root, old_root_review_path, old_root_review_sha,
        old_terminal_path, old_terminal_sha, first_case_import_path, first_case_import_sha,
        first_case_review_path, first_case_review_sha, worker_dir):
    """Return a verified in-memory candidate without writing or dispatching."""
    plan, _ = evaluator.checked_trial(plan_path, plan_sha)
    terminal = _dead_terminal(old_terminal_path, old_terminal_sha)
    old, worker = Path(old_output_root).resolve(), Path(worker_dir).resolve()
    require(worker.name == 'selection', 'prefix_original_selection_partition_required')
    manifest = workers.private_json(worker/'private/task_set_manifest.json')
    identities = [{key: row[key] for key in ('task_id', 'package_sha256')} for row in manifest['selection']]
    require(len(identities) == len({row['task_id'] for row in identities}) == 20 and
        not {row['task_id'] for row in identities} & {row['task_id'] for row in plan['final_tasks_metadata']},
        'prefix_same_disjoint_twenty_metadata_required')
    intent = workers.private_json(old/'selection-intent.private.json')
    review = workers.private_json(old_root_review_path, old_root_review_sha)
    source, binding = original.source_binding(), workers.public_binding()
    require(intent['schema'] == 'envloop-odoo20-selection-intent-v3' and intent['source_binding'] == source and
        intent['trial_plan_sha256'] == plan_sha and intent['identities'] == identities and
        intent['root_review_sha256'] == old_root_review_sha and intent['base_mode'] is True and
        intent['checkpoint_sha256'] == digest(MODEL.encode()) and intent['same_request_replay_authorized'] is False and
        intent['formal_large_study_credit'] == 0, 'prefix_exact_original_v3_intent_required')
    require(review == {'schema': 'envloop-odoo20-selection-root-review-v3', 'trial_plan_sha256': plan_sha,
        'selection_source_sha256': source['binding_sha256'],
        'native_selection_control_sha256': review['native_selection_control_sha256'],
        'checkpoint_sha256': digest(MODEL.encode()), 'sampling_seed': 0, 'sample_max_tokens': 4096,
        'sampling_kind': 'base', 'saved_prior_case_import_sha256': first_case_import_sha,
        'selection_twenty_authorized': True, 'formal_admission_authorized': False, 'automatic_retry_authorized': False} and
        binding['binding_sha256'] == plan['native_binding_sha256'] == source['native_binding_sha256'],
        'prefix_same_root_review_model_settings_source_required')
    entries, scores = original._import(first_case_import_path, first_case_import_sha,
        first_case_review_path, first_case_review_sha, identities, plan_sha, True, MODEL, 0, 4096)
    episodes = sorted(path for path in old.iterdir() if path.is_dir() and (path/'task-intent.private.json').is_file())
    require(len(episodes) == 3, 'prefix_exact_two_completed_then_one_failed_attempt_required')
    _, selector = workers._model_modules(binding)
    for ordinal, episode in enumerate(episodes, start=1):
        task_intent = workers.private_json(episode/'task-intent.private.json')
        require(task_intent == {'task': identities[ordinal], 'attempt_id': episode.name,
            'checkpoint_sha256': digest(MODEL.encode()), 'same_request_replay_authorized': False,
            'formal_large_study_credit': 0, 'actual_cost_usd': None} and episode.name.endswith(f'-{ordinal:02d}'),
            'prefix_original_ordinal_attempt_identity_changed')
        if ordinal < 3:
            require(not (episode/'selection-task-failure.private.json').exists(), 'prefix_completed_case_failure_marker')
            packet = workers.private_json(episode/'selection-task-result.private.json')
            entry, score = _audit_saved(episode, identities[ordinal], packet, worker, binding, selector, review)
            entries.append(entry); scores.append({'task': identities[ordinal], 'score': score})
        else:
            exclusion = _audit_exclusion(episode, identities[ordinal])
    return {'schema': SCHEMA, 'status': STATUS, 'trial_plan_sha256': plan_sha, 'source_binding': source_binding(),
        'trial_plan_ref': absolute_ref(plan_path, plan_sha), 'worker_dir': str(worker),
        'original_output_root': str(old),
        'original_intent_ref': absolute_ref(old/'selection-intent.private.json'),
        'original_root_review_ref': absolute_ref(old_root_review_path, old_root_review_sha),
        'original_terminal_ref': absolute_ref(old_terminal_path, old_terminal_sha),
        'original_terminal_ended_at': terminal['ended_at'],
        'first_case_import_ref': absolute_ref(first_case_import_path, first_case_import_sha),
        'first_case_review_ref': absolute_ref(first_case_review_path, first_case_review_sha),
        'identities': identities, 'model': MODEL, 'base_mode': True, 'sampling_seed': 0, 'sample_max_tokens': 4096,
        'selection_control_sha256': review['native_selection_control_sha256'],
        'selection_tasks': entries, 'scores': scores, 'completed_ordinals': [0, 1, 2],
        'infrastructure_exclusion': exclusion, 'unattempted_ordinals': list(range(4, 20)),
        'new_model_calls': 0, 'provider_calls': 0, 'native_calls': 0, 'actual_cost_usd': None,
        'same_request_replay_authorized': False, 'formal_large_study_credit': 0,
        'hidden_final_outcomes_used': False, 'continuation_authorized': False}


def _mirror(episode, destination):
    destination.mkdir(mode=0o700)
    files = []
    for path in sorted(episode.rglob('*')):
        require(not path.is_symlink(), 'prefix_original_evidence_link_forbidden')
        relative = path.relative_to(episode); target = destination/relative
        if path.is_dir():
            target.mkdir(mode=0o700)
        else:
            raw = readback.mirror_bytes(path)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            files.append({'original_path': str(path), 'mirror_relative_path': str(relative),
                'sha256': digest(raw), 'size': len(raw)})
    for item in files:
        require(digest(readback.mirror_bytes(item['original_path'])) == item['sha256'], 'prefix_original_changed_during_mirror')
    return files


def build_prefix(*, output_root, **kwargs):
    value = inspect_prefix(**kwargs)
    out = Path(output_root)
    require(out.is_absolute() and out.resolve().is_relative_to(ROOT/'work') and not out.exists() and not out.is_symlink(),
        'prefix_fresh_private_recovery_namespace_required')
    out.mkdir(parents=True, mode=0o700)
    value['evidence_mirrors'] = []
    for ordinal in (1, 2):
        entry = value['selection_tasks'][ordinal]; episode = Path(entry['episode_root']); mirror = out/f'ordinal-{ordinal:02d}.private'
        files = _mirror(episode, mirror)
        value['evidence_mirrors'].append({'ordinal': ordinal, 'original_episode_root': str(episode),
            'mirror_root': str(mirror), 'files': files})
        entry['episode_root'] = str(mirror)
    failed = value['infrastructure_exclusion']; mirror = out/'excluded-ordinal-03.private'
    value['evidence_mirrors'].append({'ordinal': 3, 'original_episode_root': failed['original_episode_root'],
        'mirror_root': str(mirror), 'files': _mirror(Path(failed['original_episode_root']), mirror)})
    write(out, 'saved-prefix-candidate.private.json', value)
    return value


def checked_candidate(path, expected):
    """Reaudit provenance and every completed row; summary hashes are insufficient."""
    value = evaluator.read_ref(absolute_ref(path, expected))
    require(value['schema'] == SCHEMA and value['status'] == STATUS and value['source_binding'] == source_binding(),
        'prefix_verified_candidate_required')
    ref = lambda key, part: value[key][part]
    original_value = inspect_prefix(plan_path=ref('trial_plan_ref', 'path'), plan_sha=ref('trial_plan_ref', 'sha256'),
        old_output_root=value['original_output_root'], old_root_review_path=ref('original_root_review_ref', 'path'),
        old_root_review_sha=ref('original_root_review_ref', 'sha256'), old_terminal_path=ref('original_terminal_ref', 'path'),
        old_terminal_sha=ref('original_terminal_ref', 'sha256'), first_case_import_path=ref('first_case_import_ref', 'path'),
        first_case_import_sha=ref('first_case_import_ref', 'sha256'), first_case_review_path=ref('first_case_review_ref', 'path'),
        first_case_review_sha=ref('first_case_review_ref', 'sha256'), worker_dir=value['worker_dir'])
    mirrors = value['evidence_mirrors']
    require([mirror['ordinal'] for mirror in mirrors] == [1, 2, 3], 'prefix_complete_mirror_coverage_required')
    normalized = json.loads(json.dumps(value)); normalized.pop('evidence_mirrors')
    for mirror in mirrors:
        episode = Path(mirror['original_episode_root']); destination = Path(mirror['mirror_root'])
        require(destination.is_absolute() and destination.is_dir() and not destination.is_symlink() and
            destination.stat().st_mode & 0o077 == 0, 'prefix_private_mirror_required')
        files = [p for p in sorted(episode.rglob('*')) if p.is_file()]
        require([str(path) for path in files] == [item['original_path'] for item in mirror['files']],
            'prefix_all_original_bytes_must_remain_mirrored')
        for item in mirror['files']:
            original_path = Path(item['original_path'])
            require(original_path.relative_to(episode).as_posix() == item['mirror_relative_path'] and
                original_path.stat().st_size == item['size'] and
                digest(readback.mirror_bytes(original_path)) == item['sha256'] and
                digest(readback.mirror_bytes(destination/item['mirror_relative_path'])) == item['sha256'],
                'prefix_retained_original_or_mirror_changed')
        ordinal = mirror['ordinal']
        if ordinal < 3:
            require(value['selection_tasks'][ordinal]['episode_root'] == str(destination) and
                original_value['selection_tasks'][ordinal]['episode_root'] == str(episode),
                'prefix_mirror_entry_root_changed')
            normalized['selection_tasks'][ordinal]['episode_root'] = str(episode)
        else:
            require(value['infrastructure_exclusion']['original_episode_root'] == str(episode),
                'prefix_exclusion_mirror_root_changed')
    require(normalized == original_value, 'prefix_candidate_does_not_match_reaudited_originals')
    return value


def continuation_review(candidate_ref):
    """Exact review form; filling it does not itself dispatch anything."""
    return {'schema': 'envloop-odoo20-prefix-continuation-root-review-v4',
        'candidate_sha256': candidate_ref['sha256'], 'prefix_source_sha256': source_binding()['binding_sha256'],
        'saved_prefix_import_authorized': True, 'one_fresh_whole_task_replacement_authorized': True,
        'replacement_ordinal': 3, 'unattempted_ordinals': list(range(4, 20)),
        'original_request_replay_authorized': False, 'original_attempt_resume_authorized': False,
        'automatic_retry_authorized': False, 'formal_admission_authorized': False,
        'actor_sampler_scorer_reset_unchanged': True, 'per_task_limits': LIMITS}


def checked_access(reference, candidate):
    """Require the actual root capabilities checker, raw model list and close."""
    access = evaluator.read_ref(reference)
    require(access.get('schema') == 'envloop-odoo20-tinker-access-restored-v1' and access.get('status') == 'ready' and
        access.get('model') == MODEL and access.get('provider_http_status') == 200 and access.get('error_type') is None and
        access.get('actual_provider_call') is True and access.get('checked_after_prior_terminal') is True and
        access.get('prior_terminal_ref') == candidate['original_terminal_ref'] and
        access.get('supported_model_verified') is access.get('owned_close_returned') is True and
        access.get('owned_close_awaited') is True and
        access.get('checker_source_sha256') == digest((ROOT/'tools/check_odoo20_tinker_access_v1.py').read_bytes()) and
        type(access.get('started_at')) in (int, float) and type(access.get('ended_at')) in (int, float) and
        access['started_at'] >= candidate['original_terminal_ended_at'] and access['ended_at'] >= access['started_at'] and
        access.get('checked_at') == access['ended_at'] and
        access.get('training_calls') == access.get('model_sampling_calls') == access.get('automatic_retries') ==
        access.get('formal_large_study_credit') == 0 and access.get('actual_cost_usd') is None and
        access.get('raw_provider_evidence_ref') is not None, 'prefix_live_provider_access_after_terminal_required')
    raw = evaluator.read_ref(access['raw_provider_evidence_ref'])
    matching = [row for row in raw.get('supported_models', []) if row.get('model_name') == MODEL]
    require(len(matching) == 1 and matching[0].get('trainable') is not False and
        matching[0].get('sampleable') is not False, 'prefix_actual_capabilities_model_list_required')
    from tools.check_odoo20_tinker_access_v1 import result_receipt
    terminal = evaluator.read_ref(candidate['original_terminal_ref'])
    expected = result_receipt(terminal_ref=candidate['original_terminal_ref'], terminal=terminal,
        started_at=access['started_at'], ended_at=access['ended_at'], capabilities=raw,
        status_code=200, error_type=None, close_returned=True,
        raw_provider_evidence_ref=access['raw_provider_evidence_ref'])
    require(access == expected, 'prefix_actual_root_access_checker_receipt_changed')
    return access


def authorize_continuation(*, candidate_path, candidate_sha, review_path, review_sha,
        provider_access_path, provider_access_sha, output_path):
    """Validate reviewer/provider evidence and write a non-dispatch authority."""
    value = checked_candidate(candidate_path, candidate_sha)
    require(value['schema'] == SCHEMA and value['status'] == STATUS and value['source_binding'] == source_binding() and
        value['completed_ordinals'] == [0, 1, 2] and value['unattempted_ordinals'] == list(range(4, 20)) and
        value['same_request_replay_authorized'] is False and value['new_model_calls'] == 0 and
        value['continuation_authorized'] is False and value['formal_large_study_credit'] == 0,
        'prefix_verified_candidate_required')
    review = evaluator.read_ref(absolute_ref(review_path, review_sha))
    require(review == continuation_review({'sha256': candidate_sha}), 'prefix_exact_separate_continuation_review_required')
    checked_access(absolute_ref(provider_access_path, provider_access_sha), value)
    for mirror in value['evidence_mirrors']:
        for item in mirror['files']:
            require(digest(readback.mirror_bytes(item['original_path'])) == item['sha256'] and
                digest(readback.mirror_bytes(Path(mirror['mirror_root'])/item['mirror_relative_path'])) == item['sha256'],
                'prefix_retained_original_or_mirror_changed')
    exclusion = value['infrastructure_exclusion']
    require(exclusion['ordinal'] == 3 and exclusion['model_score'] is None and
        exclusion['original_request_replay_authorized'] is False and exclusion['original_attempt_resume_authorized'] is False,
        'prefix_infrastructure_exclusion_changed')
    result = {'schema': 'envloop-odoo20-selection-continuation-authority-v4',
        'candidate_ref': absolute_ref(candidate_path, candidate_sha), 'root_review_ref': absolute_ref(review_path, review_sha),
        'provider_access_ref': absolute_ref(provider_access_path, provider_access_sha),
        'trial_plan_sha256': value['trial_plan_sha256'], 'source_binding': value['source_binding'],
        'import_ordinals': [0, 1, 2], 'fresh_dispatch_ordinals': list(range(3, 20)),
        'replacement': {'ordinal': 3, 'task': value['identities'][3], 'max_fresh_whole_task_attempts': 1,
            'superseded_attempt_id': exclusion['original_attempt_id'], 'original_attempt_resumed': False,
            'forbidden_request_ids': exclusion['completed_request_ids'] + exclusion['uncertain_request_ids']},
        'dispatch_count': 17, 'model': MODEL, 'base_mode': True, 'sampling_seed': 0, 'sample_max_tokens': 4096,
        'automatic_retry_authorized': False, 'original_request_replay_authorized': False,
        'actor_sampler_scorer_reset_changed': False, 'per_task_limits': LIMITS,
        'provider_calls_by_this_module': 0, 'native_calls_by_this_module': 0, 'actual_cost_usd': None,
        'formal_large_study_credit': 0, 'hidden_final_outcomes_used': False}
    target = Path(output_path)
    require(target.is_absolute() and target.resolve().is_relative_to(ROOT/'work') and not target.exists(),
        'prefix_fresh_private_authority_path_required')
    write(target.parent, target.name, result)
    return result
