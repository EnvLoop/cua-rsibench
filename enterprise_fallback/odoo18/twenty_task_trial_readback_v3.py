"""Saved-only typed evidence readback and recovery; never dispatches a model."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import importlib
from . import native_surface_workers_v14 as workers
from . import native_surface_final_worker_v1 as legacy
from cursibench import native_surface_guard_policy_v1 as policy

require, digest, private = legacy.require, legacy.digest, legacy.private
TYPED_FIELDS = {'schema', 'path', 'sha256', 'size', 'kind'}
KINDS_BY_SCHEMA = {'odoo-actual-actor-clock-v1': 'native_observation_envelope',
    'odoo-actual-task-lifecycle-v1': 'native_observation_envelope',
    'odoo-owned-complete-lifecycle-v12': 'native_observation_envelope',
    'odoo-owned-provider-close-v1': 'dispatch_receipt'}


def mirror_bytes(path):
    path = Path(path)
    if path.name == 'journal.lock' and path.stat().st_size == 0:
        require(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0,
                'readback_private_empty_journal_lock_required')
        return b''
    return private(path)


def read_ref(root, reference):
    """Retain every typed field and invoke the original native verifier."""
    require(type(reference) is dict, 'readback_exact_reference_required')
    if set(reference) == TYPED_FIELDS:
        policy.verify_artifact(root, reference)
        raw = workers.native_ref_bytes(Path(root), reference)
        value = json.loads(raw)
        expected_kind = KINDS_BY_SCHEMA.get(value.get('schema')) if type(value) is dict else None
        require(expected_kind is not None and reference['kind'] == expected_kind, 'readback_typed_json_kind_or_schema_changed')
        return value
    require(set(reference) == {'path', 'sha256'}, 'readback_exact_reference_required')
    name = Path(reference['path'])
    require(not name.is_absolute() and '..' not in name.parts and str(name), 'readback_relative_reference_required')
    raw = private(Path(root)/name)
    require(digest(raw) == reference['sha256'], 'readback_simple_reference_changed')
    return json.loads(raw)


def typed_reference(root, relative, kind):
    """Reference existing bytes, explicitly reconstructed rather than rewritten."""
    path = Path(root)/relative
    raw = private(path)
    reference = {'schema': 'native-guard-artifact-ref-v1', 'path': relative,
                 'sha256': digest(raw), 'size': len(raw), 'kind': kind}
    read_ref(root, reference)
    return reference


def reconstruct_row(episode, task):
    """Recover the lost in-memory return only from its preserved raw files."""
    episode = Path(episode)
    names = {'saved_state_sha256': 'saved-state.private.json', 'verifier_receipt_sha256': 'verifier.private.json',
        'reset_receipt_sha256': 'reset.private.json', 'baseline_semantic_sha256': 'baseline-semantic.private.json',
        'restored_semantic_sha256': 'restored-semantic.private.json', 'actions_sha256': 'actions.private.json',
        'usage_sha256': 'usage.private.json', 'frames_sha256': 'frames.private.json'}
    values = {name: json.loads(private(episode/name)) for name in names.values()}
    saved, verdict = values['saved-state.private.json'], values['verifier.private.json']
    usage, frames = values['usage.private.json'], values['frames.private.json']
    require(saved['task_id'] == verdict['task_id'] == usage['task_id'] == task['task_id'] and
        saved['termination'] == verdict['termination'] and type(verdict['score']) is int and verdict['score'] in (0, 1),
        'readback_saved_task_or_score_unbound')
    life_ref = typed_reference(episode, 'actor-clock/complete-lifecycle.private.json', 'native_observation_envelope')
    life = read_ref(episode, life_ref)
    task_ref = typed_reference(episode, 'actor-clock/task-lifecycle.private.json', 'native_observation_envelope')
    require(life['task_id'] == task['task_id'] and life['package_sha256'] == task['package_sha256'],
        'readback_owned_lifecycle_task_changed')
    return {**task, 'score': verdict['score'], **{key: digest(private(episode/name)) for key, name in names.items()},
        'frame_count': len(frames), 'sample_count': len(usage['samples']),
        'sample_paid_attempt_ids': [sample['paid_attempt_id'] for sample in usage['samples']],
        'rendered_input_tokens': usage['rendered_input_tokens'], 'sampled_output_tokens': usage['sampled_output_tokens'],
        'termination': saved['termination'], 'actor_clock_ref': life['actor_clock'], 'task_lifecycle_ref': task_ref,
        'owned_complete_lifecycle_ref': life_ref, 'provider_close_ref': life['provider_close']}


def replay_saved_case(*, plan_path, plan_sha, old_output_root, old_root_review_path, old_root_review_sha,
        old_terminal_path, old_terminal_sha, worker_dir, output_root):
    """Reopen one consumed base episode; no original bytes or provider IDs change.

    The output is a recovery candidate, not admission. A separate explicit root
    review must authorize its import into a fresh remaining19 execution.
    """
    from . import twenty_task_trial_evaluator_v3 as evaluator, twenty_task_trial_selection_v2 as old_selection
    plan, _ = evaluator.checked_trial(plan_path, plan_sha)
    terminal = workers.private_json(old_terminal_path, old_terminal_sha)
    require(terminal['exit_code'] == 1 and terminal['automatic_restarts'] == 0, 'readback_known_terminal_failed_auditor_required')
    try: os.kill(terminal['pid'], 0)
    except ProcessLookupError: pass
    else: require(False, 'readback_original_worker_still_live')
    old = Path(old_output_root).resolve()
    intent = workers.private_json(old/'selection-intent.private.json')
    review = workers.private_json(old_root_review_path, old_root_review_sha)
    source = old_selection.source_binding()
    require(intent['source_binding'] == source and intent['trial_plan_sha256'] == plan_sha and
        intent['root_review_sha256'] == old_root_review_sha and intent['base_mode'] is True and
        review['schema'] == 'envloop-odoo20-selection-root-review-v2' and review['trial_plan_sha256'] == plan_sha and
        review['selection_source_sha256'] == source['binding_sha256'] and review['sampling_kind'] == 'base' and
        review['checkpoint_sha256'] == intent['checkpoint_sha256'] == digest(evaluator.MODEL.encode()) and
        source['native_binding_sha256'] == plan['native_binding_sha256'], 'readback_exact_original_base_source_epoch_required')
    worker = Path(worker_dir).resolve(); require(worker.name == 'selection', 'readback_original_selection_worker_required')
    os.environ['ENVLOOP_ODOO_WORKER_DIR'] = str(worker)
    manifest = workers.private_json(worker/'private/task_set_manifest.json')
    identities = [{key: row[key] for key in ('task_id', 'package_sha256')} for row in manifest['selection']]
    require(identities == intent['identities'] and len(identities) == 20, 'readback_same_full_selection_metadata_required')
    episodes = [path for path in old.iterdir() if path.is_dir() and (path/'task-intent.private.json').is_file()]
    require(len(episodes) == 1, 'readback_one_consumed_first_case_required')
    episode = episodes[0]; task_intent = workers.private_json(episode/'task-intent.private.json')
    task = identities[0]; require(task_intent['task'] == task, 'readback_original_first_task_required')
    failure = workers.private_json(episode/'selection-task-failure.private.json')
    require(failure['task'] == task and failure['error_type'] == 'OdooFinalWorkerError' and
        failure['error_sha256'] == digest(b'trial_exact_reference_required') and
        failure['same_request_replay_authorized'] is False and failure['formal_large_study_credit'] == 0,
        'readback_only_known_post_episode_reference_bug_allowed')
    binding = workers.public_binding()
    _, selection = workers._model_modules(binding)
    row = reconstruct_row(episode, task)
    selection._audit_task_artifacts(episode, task, row)
    setup = workers.private_json(episode/'paid-setup-result.private.json')
    actual = setup['actual_backend_identity']
    require(setup['status'] == 'ready' and actual['sampling_kind'] == 'base' and
        actual['checkpoint_sha256'] == selection.vision_digest(evaluator.MODEL) and actual['seed'] == review['sampling_seed'] and
        actual['temperature'] == 0, 'readback_actual_original_qwen_base_setup_required')
    calls = failure['paid_calls']
    usage = workers.private_json(episode/'usage.private.json')
    require(len(calls) == row['sample_count'] and all(sample['status'] == 'completed' for sample in usage['samples']),
        'readback_original_completed_paid_coverage_required')
    for call in calls:
        retained = read_ref(episode, call['result'])
        require(retained['status'] == 'completed' and retained['request_id'] == call['request_id'] and
            retained['new_dispatch'] is True and retained['reused'] is False, 'readback_original_paid_result_changed')
    # A saved replay does not need a live application's factory namespace.
    # Bind the saved proof directly to the unchanged original private gold and
    # checkpoint context, and use only the original verifier's pure functions.
    proofs = [legacy.final.reference(episode, path) for path in sorted(episode.glob('live-proof-*.private.json'))]
    require(len(proofs) >= 2, 'readback_original_live_saved_proofs_missing')
    context = read_ref(episode, proofs[-1])['context']
    private_root = worker/'private'
    gold_name = {'purchase': 'development_gold.json', 'inventory': 'replenishment_gold.json',
                 'sales': 'sales_gold.json', 'crm': 'crm_gold.json'}[context['family']]
    expected_context = {'family': context['family'], 'target': workers.private_json(private_root/gold_name)[task['task_id']],
        'baseline': workers.private_json(private_root/'baseline_snapshot.json'),
        'frozen_files': workers.private_json(private_root/'baseline-filestore-manifest.json')}
    require(context == expected_context, 'readback_original_saved_proof_gold_or_checkpoint_changed')
    environment = SimpleNamespace(proofs=proofs, proof_context=context, runtime_receipt=failure['runtime_cleanup'])
    pure_verify = importlib.import_module('verify')
    require(Path(pure_verify.__file__).resolve() == legacy.ROOT/'enterprise_fallback/odoo18/verify.py' and
        digest(Path(pure_verify.__file__).read_bytes()) == binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'],
        'readback_original_pure_verifier_source_changed')
    auditor = evaluator.audit_saved_episode
    from types import FunctionType
    proxy = SimpleNamespace(**{**vars(legacy), '_modules': lambda *args: (None, None, None, pure_verify, None)})
    audit = FunctionType(auditor.__code__, {**auditor.__globals__, 'legacy': proxy}, auditor.__name__, auditor.__defaults__, auditor.__closure__)
    audit.__kwdefaults__ = auditor.__kwdefaults__
    checked = audit(episode, task, row, environment, selection, binding, worker, SimpleNamespace(calls=calls))
    out = Path(output_root)
    require(out.is_absolute() and out.resolve().is_relative_to(evaluator.ROOT/'work') and not out.exists(),
        'readback_fresh_recovery_namespace_required')
    out.mkdir(parents=True, mode=0o700)
    # A byte-identical mirror keeps the consumed original directory untouched.
    # Relative native refs remain valid; every original hash is recorded.
    mirror = out/'original-evidence-byte-mirror.private'; mirror.mkdir(mode=0o700)
    originals = []
    for path in sorted(episode.rglob('*')):
        require(not path.is_symlink(), 'readback_original_link_not_allowed')
        relative = path.relative_to(episode)
        target = mirror/relative
        if path.is_dir(): target.mkdir(mode=0o700)
        else:
            raw = mirror_bytes(path); fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            originals.append({'path': str(path), 'mirror_relative_path': str(relative), 'sha256': digest(raw), 'size': len(raw)})
    row_ref = legacy.write(mirror, 'reconstructed-native-row.private.json', row)
    selection._audit_task_artifacts(mirror, task, row)
    for item in originals: require(digest(mirror_bytes(item['path'])) == item['sha256'], 'readback_original_changed_during_recovery')
    result = {'schema': 'envloop-odoo20-saved-selection-case-import-candidate-v3',
        'status': 'saved_original_first_case_independently_replayed', 'trial_plan_sha256': plan_sha,
        'native_binding_sha256': binding['binding_sha256'], 'old_selection_source_binding': source,
        'old_selection_intent_ref': {'path': str(old/'selection-intent.private.json'), 'sha256': digest(private(old/'selection-intent.private.json'))},
        'old_root_review_ref': {'path': str(Path(old_root_review_path).resolve()), 'sha256': old_root_review_sha},
        'old_terminal_ref': {'path': str(Path(old_terminal_path).resolve()), 'sha256': old_terminal_sha},
        'original_episode_root': str(episode), 'original_evidence_byte_mirror': originals,
        'reconstruction_is_explicit_not_an_original_retained_row': True, 'task': task, 'score': checked['score'],
        'entry': {'task': task, 'episode_root': str(mirror), 'native_row': row_ref,
            'paid_setup_result': legacy.final.reference(mirror, mirror/'paid-setup-result.private.json')},
        'sampling_seed': review['sampling_seed'], 'sample_max_tokens': review['sample_max_tokens'], 'base_mode': True,
        'model': evaluator.MODEL, 'completed_original_sample_calls': len(calls), 'new_model_calls': 0,
        'actual_cost_usd': None, 'formal_large_study_credit': 0, 'same_request_replay_authorized': False,
        'checked_saved_evidence': checked}
    legacy.write(out, 'saved-case-import-candidate.private.json', result)
    return result
