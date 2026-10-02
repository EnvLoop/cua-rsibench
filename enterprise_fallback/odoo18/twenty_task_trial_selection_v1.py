"""Native public selection20 for the explicit Odoo20 development trial.

The historical six-cell authority remains unchanged. Each task has a fresh
owned native lease, saved scorer proof, no-retry sampler and real provider close.
No hidden final bodies are opened by this module. Unknown billing stays null.
"""
from __future__ import annotations
import argparse
import importlib
import inspect
import json
import os
from pathlib import Path
from types import FunctionType, SimpleNamespace
from . import twenty_task_trial_evaluator_v1 as evaluator
from . import native_surface_workers_v13 as workers
from . import native_surface_final_worker_v1 as legacy
from . import native_reference_split_finalizer_v3 as controls
from .odoo_actor_model_modules_v1 import run_owned_task
from .odoo_no_retry_sampler_v22 import sampler_class

ROOT, MODEL = evaluator.ROOT, evaluator.MODEL
require, digest, private, write = evaluator.require, evaluator.digest, evaluator.private, evaluator.write


def source_binding():
    native = workers.public_binding()
    value = {'schema': 'envloop-odoo20-selection-source-v1', 'native_binding_sha256': native['binding_sha256'],
        'evaluator_source_sha256': evaluator.source_binding()['binding_sha256'],
        'source_sha256s': {**native['source_sha256s'],
            'enterprise_fallback/odoo18/twenty_task_trial_selection_v1.py': digest(Path(__file__).read_bytes())},
        'formal_large_study_credit': 0, 'formal_registration_permitted': False,
        'per_task_limits': {'actions': 90, 'actor_seconds': 720, 'owned_lifecycle_seconds': 1200}}
    return {**value, 'binding_sha256': digest(legacy.final.canonical(value))}


def checked_control(path, expected, plan, identities):
    value = workers.private_json(path, expected)
    require(value.get('schema') == controls.SCHEMA and value.get('status') == controls.STATUS and
        value.get('split') == 'selection' and value.get('qualified_control_case_count') == 20 and
        value.get('native_worker_binding_sha256') == plan['native_binding_sha256'] and
        value.get('reference_binding_sha256') == plan['reference_binding_sha256'] and
        value.get('finalizer_source_sha256') == digest(Path(controls.__file__).read_bytes()) and
        value.get('all_saved_audits_independently_rederived') is True and
        value.get('all_source_and_packages_equivalent') is True and value.get('originals_preserved') is True and
        value.get('formal_task_registration_count') == 0 and value.get('formal_registration_performed') is False and
        value.get('model_calls') == value.get('provider_calls') == value.get('native_calls') == 0,
        'trial_actual_native_selection_twenty_control_required')
    rows = value.get('rows')
    require(type(rows) is list and len(rows) == 20 and
        [(row['task_id'], row['package_sha256']) for row in rows] ==
        [(row['task_id'], row['package_sha256']) for row in identities] and
        all(row.get('independent_scores') == [0.0, 1.0, 0.0] and row.get('source_visual_review_verified') is True and
            row.get('source_attachment_readback') is True for row in rows),
        'trial_native_selection_controls_identity_or_saved_score_changed')
    return value


def modules(worker, binding):
    """Preserve the original selection module boundary and credential checks."""
    code = ROOT/'enterprise_fallback/odoo18'
    os.environ['ENVLOOP_ODOO_WORKER_DIR'] = str(worker)
    import sys
    if str(code) not in sys.path: sys.path.insert(0, str(code))
    result = []
    for name in ('factory', 'gui_controls', 'reset', 'verify', 'worker_lease'):
        loaded = sys.modules.get(name)
        require(loaded is None or Path(loaded.__file__).resolve() == code/(name+'.py'), 'trial_selection_module_conflict')
        result.append(importlib.import_module(name))
    factory, gui, reset, verify, lease = result
    require(worker.name == 'selection' and factory.HERE == worker and factory.PRIVATE == worker/'private' and
        reset.HERE == worker and gui.PRIVATE == verify.PRIVATE == lease.PRIVATE == factory.PRIVATE and
        factory.local_config().get('ODOO_PARTITION') == 'selection' and
        digest((worker/'compose.yaml').read_bytes()) == binding['source_sha256s']['enterprise_fallback/odoo18/compose.yaml'] and
        not (worker/'compose.yaml').is_symlink(), 'trial_original_selection_worker_required')
    private(worker/'.env')
    return result


def selection_environment(selection, worker, identities, binding):
    """An exact checked partition bridge; actor/scorer/reset sources stay native57."""
    source = inspect.getsource(legacy.environment_factory)
    substitutions = (("rows=manifest.get('official')", "rows=manifest.get('selection')"),
        ('len(rows)==100', 'len(rows)==20'), ('len(all_cases)==100', 'len(all_cases)==20'),
        ('==25 for family', '==5 for family'), ('})==100', '})==20'),
        ("split!='official'", "split!='selection'"))
    for before, after in substitutions:
        require(source.count(before) == 1, 'trial_checked_selection_partition_bridge_changed')
        source = source.replace(before, after)
    namespace = {**legacy.environment_factory.__globals__, '_modules': modules}
    exec(compile(source, 'checked-odoo20-selection-partition-bridge-v1', 'exec'), namespace)
    return namespace['environment_factory'](selection, worker, identities, binding)


def scoped_worker(*, plan_path, plan_sha, binding, **kwargs):
    original = workers.selection_worker
    def trial_authority(current, path, expected):
        require(Path(path).resolve() == Path(plan_path).resolve() and expected == plan_sha,
                'trial_selection_authority_reference_changed')
        plan, _ = evaluator.checked_trial(path, expected)
        require(current['binding_sha256'] == binding['binding_sha256'] == plan['native_binding_sha256'],
                'trial_selection_authority_native_source_changed')
    namespace = {**original.__globals__, '_require_campaign_ratification': trial_authority}
    factory = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    factory.__kwdefaults__ = original.__kwdefaults__
    return factory(campaign_ratification_path=Path(plan_path), campaign_ratification_sha256=plan_sha, **kwargs)


def run(*, plan_path, plan_sha, native_binding_path, native_binding_sha, train_control_path, train_control_sha,
        selection_control_path, selection_control_sha, local_cost_authority_path, local_cost_authority_sha,
        worker_dir, checkpoint_path, output_root, root_review_path, root_review_sha,
        sampling_seed=0, sample_max_tokens=4096, base_mode=False, execute=False):
    require(execute is True, 'trial_explicit_selection_dispatch_required')
    plan, _ = evaluator.checked_trial(plan_path, plan_sha)
    binding = workers.validate_binding(workers.private_json(native_binding_path, native_binding_sha))
    require(binding['binding_sha256'] == plan['native_binding_sha256'], 'trial_selection_native_binding_changed')
    source = source_binding()
    worker, out = Path(worker_dir).resolve(), Path(output_root)
    manifest = workers.private_json(worker/'private/task_set_manifest.json')
    raw_identities = manifest['selection']
    identities = [{key: row[key] for key in ('task_id', 'package_sha256')} for row in raw_identities]
    require(worker.name == 'selection' and len(identities) == len({row['task_id'] for row in identities}) == 20 and
        not {row['task_id'] for row in identities} & {row['task_id'] for row in plan['final_tasks_metadata']},
        'trial_exact_disjoint_selection_twenty_required')
    checked_control(selection_control_path, selection_control_sha, plan, identities)
    _, selection = workers._model_modules(binding)
    require(type(base_mode) is bool and ((base_mode and checkpoint_path == MODEL) or
        (not base_mode and type(checkpoint_path) is str and selection.campaign.TINKER_PATH.fullmatch(checkpoint_path))),
        'trial_selection_checkpoint_mode_changed')
    require(type(sampling_seed) is int and 0 <= sampling_seed < 2**31 and
        type(sample_max_tokens) is int and 0 < sample_max_tokens <= 4096, 'trial_selection_sampling_invalid')
    review = workers.private_json(root_review_path, root_review_sha)
    require(review == {'schema': 'envloop-odoo20-selection-root-review-v1', 'trial_plan_sha256': plan_sha,
        'selection_source_sha256': source['binding_sha256'], 'native_selection_control_sha256': selection_control_sha,
        'checkpoint_sha256': digest(checkpoint_path.encode()), 'sampling_seed': sampling_seed,
        'sample_max_tokens': sample_max_tokens, 'sampling_kind': 'base' if base_mode else 'checkpoint',
        'selection_twenty_authorized': True, 'formal_admission_authorized': False, 'automatic_retry_authorized': False},
        'trial_exact_selection_root_review_required')
    active = scoped_worker(plan_path=plan_path, plan_sha=plan_sha, binding=binding,
        native_binding_path=Path(native_binding_path), native_binding_file_sha256=native_binding_sha,
        train_control_path=Path(train_control_path), train_control_sha256=train_control_sha,
        worker_dir=worker, private_output_root=out.parent,
        expected_runtime_sha256=binding['binding_sha256'],
        expected_verifier_sha256=binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'],
        local_cost_authority_path=Path(local_cost_authority_path), local_cost_authority_sha256=local_cost_authority_sha,
        allow_base_model=base_mode, expected_base_checkpoint_sha256=digest(MODEL.encode()) if base_mode else None,
        enable_live=True)
    # This invokes the original live/TRAIN/source/cost checks, with only the
    # separately named campaign authority selected for this explicit trial.
    active._require_freeze()
    from cursibench.scale_vision_proxy import QwenVisionRenderer
    QwenVisionRenderer.load()
    require(bool(os.environ.get('TINKER_API_KEY')), 'trial_selection_tinker_key_missing')
    require(out.is_absolute() and out.resolve().is_relative_to(ROOT/'work') and not out.exists() and not out.is_symlink(),
        'trial_selection_fresh_owned_namespace_required')
    out.mkdir(mode=0o700, parents=True)
    write(out, 'selection-intent.private.json', {'schema': 'envloop-odoo20-selection-intent-v1',
        'trial_plan_sha256': plan_sha, 'source_binding': source, 'root_review_sha256': root_review_sha,
        'checkpoint_sha256': digest(checkpoint_path.encode()), 'base_mode': base_mode,
        'identities': identities, 'same_request_replay_authorized': False, 'formal_large_study_credit': 0,
        'actual_cost_usd': None})
    entries, scores = [], []
    for ordinal, task in enumerate(identities):
        require(source_binding() == source and digest(private(root_review_path)) == root_review_sha,
                'trial_selection_source_or_review_changed_before_dispatch')
        active._require_freeze()
        checked_control(selection_control_path, selection_control_sha, plan, identities)
        attempt = f'odoo20-selection-{"base" if base_mode else "checkpoint"}-{digest(str(out).encode())[:10]}-{ordinal:02d}'
        episode = out/attempt
        episode.mkdir(mode=0o700)
        write(episode, 'task-intent.private.json', {'task': task, 'attempt_id': attempt,
            'checkpoint_sha256': digest(checkpoint_path.encode()), 'same_request_replay_authorized': False,
            'formal_large_study_credit': 0, 'actual_cost_usd': None})
        environment = selection_environment(selection, worker, identities, binding)
        environment._native_readiness_sink = lambda value: write(episode, 'db-readiness.private.json', value)
        metered = None
        try:
            environment.load_command_task(task, episode)
            config = {'model': MODEL, 'seed': sampling_seed, 'sample_max_tokens': sample_max_tokens}
            actual = sampler_class(selection)(checkpoint_path=checkpoint_path, config=config, output_root=episode,
                attempt_id=attempt, base_mode=base_mode, expected_base_checkpoint_sha256=digest(MODEL.encode()) if base_mode else None)
            metered = evaluator.TrialSampler(actual, episode, {'attempt_id': attempt})
            metered.parent_paid_attempt_id = attempt
            row = run_owned_task(environment=environment, task=task, index=0, sampler=metered,
                task_dir=episode, attempt_id=attempt)
            # Reuse the exact independent saved readback/verifier/reset/close
            # auditor; its only module boundary is this selection partition.
            audit = evaluator.audit_saved_episode
            proxy = SimpleNamespace(**{**vars(legacy), '_modules': modules})
            local = FunctionType(audit.__code__, {**audit.__globals__, 'legacy': proxy},
                audit.__name__, audit.__defaults__, audit.__closure__)
            local.__kwdefaults__ = audit.__kwdefaults__
            result = local(episode, task, row, environment, selection, binding, worker, metered)
            native_row = write(episode, 'native-row.private.json', row)
            setup = legacy.final.reference(episode, episode/'paid-setup-result.private.json')
            write(episode, 'selection-task-result.private.json', {'schema': 'envloop-odoo20-selection-task-result-v1',
                'task': task, 'trial_plan_sha256': plan_sha, 'checkpoint_sha256': digest(checkpoint_path.encode()), **result})
            entries.append({'task': task, 'episode_root': str(episode), 'native_row': native_row, 'paid_setup_result': setup})
            scores.append({'task': task, 'score': result['score']})
        except BaseException as error:
            write(episode, 'selection-task-failure.private.json', {'schema': 'envloop-odoo20-selection-task-failure-v1',
                'task': task, 'error_type': type(error).__name__, 'error_sha256': digest(str(error).encode()),
                'runtime_cleanup': getattr(environment, 'runtime_receipt', None),
                'paid_calls': [] if metered is None else metered.calls, 'actual_cost_usd': None,
                'same_request_replay_authorized': False, 'formal_large_study_credit': 0})
            raise
    result = {'schema': 'envloop-odoo20-selection-complete-v1', 'status': 'twenty_saved_scores_reset_and_closed',
        'trial_plan_sha256': plan_sha, 'source_binding': source, 'selection_control_sha256': selection_control_sha,
        'selection_control_ref': {'path': str(Path(selection_control_path).resolve()), 'sha256': selection_control_sha},
        'model': MODEL, 'checkpoint_path': checkpoint_path, 'checkpoint_sha256': digest(checkpoint_path.encode()),
        'base_mode': base_mode, 'selection_tasks': entries, 'scores': scores, 'actual_cost_usd': None,
        'formal_large_study_credit': 0, 'hidden_final_outcomes_used': False}
    write(out, 'selection-result.private.json', result)
    return result


def audit_selection_result(result, selection):
    """Reopen score/identity/setup/clock/reset/close evidence before promotion."""
    entries, scores = result.get('selection_tasks'), result.get('scores')
    require(type(entries) is list and type(scores) is list and len(entries) == len(scores) == 20,
            'trial_selection_result_full_twenty_required')
    seen = set()
    for entry, score in zip(entries, scores, strict=True):
        require(type(entry) is dict and set(entry) == {'task', 'episode_root', 'native_row', 'paid_setup_result'} and
                type(entry['task']) is dict and set(entry['task']) == {'task_id', 'package_sha256'} and
                type(score) is dict and set(score) == {'task', 'score'} and score['task'] == entry['task'] and
                type(score['score']) is int and score['score'] in (0, 1) and entry['task']['task_id'] not in seen,
                'trial_selection_result_identity_or_score_changed')
        seen.add(entry['task']['task_id'])
        episode = Path(entry['episode_root'])
        require(episode.is_absolute() and episode.is_dir() and not episode.is_symlink() and episode.stat().st_mode & 0o077 == 0,
                'trial_selection_private_episode_required')
        row = evaluator._ref(episode, entry['native_row'])
        require(row.get('task_id') == entry['task']['task_id'] and row.get('package_sha256') == entry['task']['package_sha256'] and
                row.get('score') == score['score'], 'trial_selection_raw_score_changed')
        selection._audit_task_artifacts(episode, entry['task'], row)
        setup = evaluator._ref(episode, entry['paid_setup_result'])
        identity = setup.get('actual_backend_identity', {})
        require(setup.get('status') == 'ready' and identity.get('sampling_kind') == ('base' if result['base_mode'] else 'checkpoint') and
                identity.get('checkpoint_sha256') == selection.vision_digest(result['checkpoint_path']),
                'trial_selection_raw_setup_changed')
        clock, life, close = (evaluator._ref(episode, row[key]) for key in
            ('actor_clock_ref', 'owned_complete_lifecycle_ref', 'provider_close_ref'))
        require(clock.get('native_actions_after_deadline') == 0 and clock.get('evaluation_outside_actor_clock') is True and
                0 <= clock['actor_elapsed_seconds'] <= 720 and life.get('saved_readback_reset_and_provider_close_complete') is True and
                0 <= life['ended_monotonic']-life['started_monotonic'] <= 1200 and close.get('status') == 'acknowledged' and
                close.get('real_close_call_returned') is True, 'trial_selection_raw_lifecycle_unproved')


def freeze_checkpoint(*, plan_path, plan_sha, baseline_result_ref, selected_result_ref, output_path):
    """Construct the exact final-evaluator receipt from reviewed selection only.

    Call before creating any final pair namespace. Final results are never an
    input. A checkpoint must preserve every base selection success to promote.
    """
    plan, _ = evaluator.checked_trial(plan_path, plan_sha)
    baseline, selected = evaluator.read_ref(baseline_result_ref), evaluator.read_ref(selected_result_ref)
    source = source_binding()
    binding = workers.public_binding()
    _, selection = workers._model_modules(binding)
    for result, base in ((baseline, True), (selected, False)):
        require(result.get('schema') == 'envloop-odoo20-selection-complete-v1' and
            result.get('status') == 'twenty_saved_scores_reset_and_closed' and result.get('base_mode') is base and
            result.get('trial_plan_sha256') == plan_sha and result.get('source_binding') == source and
            result.get('hidden_final_outcomes_used') is False and result.get('formal_large_study_credit') == 0 and
            result.get('model') == MODEL and len(result.get('scores', [])) == 20 and
            digest(result['checkpoint_path'].encode()) == result['checkpoint_sha256'] and
            ((base and result['checkpoint_path'] == MODEL) or
             (not base and selection.campaign.TINKER_PATH.fullmatch(result['checkpoint_path']) is not None)),
            'trial_actual_matched_selection_pair_required')
        audit_selection_result(result, selection)
    require(baseline['selection_control_ref'] == selected['selection_control_ref'] and
            baseline['selection_control_sha256'] == selected['selection_control_sha256'] == selected['selection_control_ref']['sha256'] and
            [row['task'] for row in baseline['selection_tasks']] == [row['task'] for row in selected['selection_tasks']],
            'trial_matched_selection_source_roster_required')
    checked_control(selected['selection_control_ref']['path'], selected['selection_control_ref']['sha256'],
                    plan, [row['task'] for row in selected['selection_tasks']])
    base_scores = {row['task']['task_id']: row['score'] for row in baseline['scores']}
    new_scores = {row['task']['task_id']: row['score'] for row in selected['scores']}
    require(len(base_scores) == len(new_scores) == 20 and set(base_scores) == set(new_scores) and
        all(type(score) is int and score in (0, 1) for score in (*base_scores.values(), *new_scores.values())) and
        all(new_scores[name] >= score for name, score in base_scores.items()), 'trial_selection_no_regression_required')
    value = {'schema': 'envloop-odoo20-selection-checkpoint-freeze-v1', 'trial_plan_sha256': plan_sha,
        'evaluator_source_sha256': source['evaluator_source_sha256'], 'checkpoint_path': selected['checkpoint_path'],
        'checkpoint_sha256': selected['checkpoint_sha256'], 'model': MODEL, 'selection_split': 'selection',
        'selection_tasks': selected['selection_tasks'], 'checkpoint_frozen_before_final_outcomes': True,
        'hidden_final_outcomes_used': False, 'formal_large_study_credit': 0}
    # Reopen every selected raw artifact and actual sampler setup; a result
    # summary or a typed Tinker path alone is insufficient for this freeze.
    manifest = [row['task'] for row in selected['selection_tasks']]
    parent = Path(output_path).parent
    require(parent.is_dir() and parent.stat().st_mode & 0o077 == 0 and not Path(output_path).exists(),
        'trial_checkpoint_freeze_fresh_private_path_required')
    # checked_selection_freeze reads immutable bytes. Validate before writing
    # the promotion artifact via a private one-use temporary validation file.
    validation = parent/(Path(output_path).name+'.validation.private.json')
    write(parent, validation.name, value)
    evaluator.checked_selection_freeze({'path': str(validation.resolve()), 'sha256': digest(validation.read_bytes())},
        plan_sha=plan_sha, source_sha=source['evaluator_source_sha256'], selection_manifest=manifest, selection=selection)
    write(parent, Path(output_path).name, value)
    write(parent, Path(output_path).name+'.selection-lineage.private.json', {'baseline_result': baseline_result_ref,
        'selected_result': selected_result_ref, 'freeze_sha256': digest(private(output_path)),
        'trial_plan_sha256': plan_sha, 'no_regression_checked': True, 'formal_large_study_credit': 0})
    return {'path': str(Path(output_path).resolve()), 'sha256': digest(private(output_path))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'native-binding-path', 'native-binding-sha', 'train-control-path',
        'train-control-sha', 'selection-control-path', 'selection-control-sha', 'local-cost-authority-path',
        'local-cost-authority-sha', 'worker-dir', 'checkpoint-path', 'output-root', 'root-review-path', 'root-review-sha'):
        parser.add_argument('--'+field, required=True)
    parser.add_argument('--sampling-seed', type=int, default=0)
    parser.add_argument('--sample-max-tokens', type=int, default=4096)
    parser.add_argument('--base-mode', action='store_true')
    parser.add_argument('--execute', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__': main()
