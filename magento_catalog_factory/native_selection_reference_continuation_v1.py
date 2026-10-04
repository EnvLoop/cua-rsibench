"""Additive, separately reviewed continuation of interrupted original controls.

Review and saved audit are evidence-only. The original native execution and
verification modules are unchanged; this module changes only provenance joining
and runs the nine remaining whole trios after an explicit new review.
"""
import argparse
import asyncio
import json
import os
import time
from hashlib import sha256
from pathlib import Path

from . import native_selection_reference_controls_v1 as original

require, private, write = original.require, original.private, original.write
REUSED_TRIOS = 11
TOTAL_TRIOS = 20
MODES = original.MODES


def _sha(path):
    return original._sha(path)


def _ref(path, digest=None):
    return original._ref(path, digest or _sha(path))


def _same(left, right):
    return original.workers.final.canonical(left) == original.workers.final.canonical(right)


def _safe_output(path):
    path = Path(path).absolute()
    require(not any(parent.is_symlink() for parent in (path, *path.parents)),
            'continuation_output_symlink_ancestry')
    return path.resolve()


def source_binding():
    root = Path(__file__).resolve().parents[1]
    names = ('magento_catalog_factory/native_selection_reference_continuation_v1.py',
             'magento_catalog_factory/native_reference_host_supervisor_v1.py')
    value = {'schema': 'magento-selection20-continuation-source-v1',
             'original_reference_binding': original.source_binding(),
             'source_sha256s': {name: _sha(root/name) for name in names},
             'native_actor_sampler_scorer_guard_reset_changed': False,
             'model_calls': 0, 'tinker_calls': 0}
    return {**value, 'binding_sha256': sha256(original.workers.final.canonical(value)).hexdigest()}


def _audit_trio(inputs, ordinal, task, root, fresh_owner=None):
    identity = inputs.roster['splits']['selection'][ordinal]
    require({key: task.get(key) for key in identity} == identity,
            'continuation_original_identity_changed')
    require(type(task.get('ordinal')) is int and task['ordinal'] == ordinal and
            set(task.get('trio', {})) == {mode for mode, _ in MODES},
            'continuation_whole_original_ordinal_trio_required')
    actions = frames = actor_ms = lifecycle_ms = 0
    for mode, score in MODES:
        proof = task['trio'][mode]
        folder = Path(root)/f'attempt-{ordinal:03d}'/mode
        require(Path(proof['episode_root']).absolute() == folder.absolute() and
                Path(proof['episode_root']).resolve() == folder.resolve() and
                not any(parent.is_symlink() for parent in (folder, *folder.parents)),
                'continuation_original_episode_path_changed')
        row = private(folder/'native-row.private.json', proof['native_row_sha256'])
        if fresh_owner is not None:
            held = private(folder/'guard/held-lease.private.json')
            require(held['owned_operation']['pid'] == fresh_owner['pid'] and
                    held['owned_operation']['started_monotonic'] >= fresh_owner['started_monotonic'],
                    'continuation_copied_old_episode_cannot_be_fresh')
        require({key: row.get(key) for key in identity} == identity and
                row.get('native_source_binding_sha256') == inputs.binding['binding_sha256'] and
                type(row.get('score')) is int and type(proof.get('score')) is int and
                row['score'] == proof['score'] == score,
                'continuation_original_row_identity_source_score_changed')
        require(type(row.get('samples')) is list and all(
            sample.get('paid_attempt_id') is None and sample.get('status') == 'control_action' and
            sample.get('raw_result', {}).get('model_call_performed') is False
            for sample in row['samples']), 'continuation_reference_only_samples_required')
        saved = original.audit.audit_episode(folder, row, provider_close_required=False)
        require(type(saved.get('score')) is int and saved['score'] == score,
                'continuation_independent_score_changed')
        actions += len(saved['actions']); frames += len(saved['frames'])
        actor_ms += row.get('actor_wall_time_ms', 0)
        lifecycle_ms += row.get('lifecycle_wall_time_ms', 0)
    return {'actions': actions, 'frames': frames, 'actor_wall_time_ms': actor_ms,
            'lifecycle_wall_time_ms': lifecycle_ms}


def _original_task(inputs, root, ordinal):
    trio = {}
    for mode, _ in MODES:
        folder = Path(root)/f'attempt-{ordinal:03d}'/mode
        row_path = folder/'native-row.private.json'
        row = private(row_path)
        trio[mode] = {'score': row['score'], 'episode_root': str(folder.resolve()),
                      'native_row_sha256': _sha(row_path)}
    task = {**inputs.roster['splits']['selection'][ordinal], 'ordinal': ordinal,
            'origin': 'original_completed_whole_trio', 'trio': trio}
    _audit_trio(inputs, ordinal, task, root)
    return task


def _preserved_original(root, historical):
    reference = historical['references']['original-artifact-preservation-manifest.private.json']
    manifest = private(reference['path'], reference['sha256'])
    source = Path(manifest['source_root'])
    require(source.resolve() == Path(root).parent.resolve() and
            manifest['file_count'] == historical['preserved_files'] and
            manifest['total_bytes'] == historical['preserved_bytes'] and not manifest['symlinks'],
            'continuation_original_preservation_scope_changed')
    names = set(); total = 0
    for row in manifest['rows']:
        relative = Path(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts and
                row['path'] not in names, 'continuation_preserved_path_unsafe')
        path = source/relative
        require(path.resolve().is_relative_to(source.resolve()) and
                path.stat().st_size == row['bytes'] and _sha(path) == row['sha256'],
                'continuation_original_artifact_changed')
        names.add(row['path']); total += row['bytes']
    actual = {str(path.relative_to(source)) for path in source.rglob('*') if path.is_file()}
    require(actual == names and len(names) == manifest['file_count'] and total == manifest['total_bytes'],
            'continuation_original_preservation_incomplete')
    return reference


def _prepare(*, original_arguments_path, original_arguments_sha256,
             original_review_path, original_review_sha256,
             interruption_audit_path, interruption_audit_sha256,
             cleanup_result_path, cleanup_result_sha256, output):
    arguments = private(original_arguments_path, original_arguments_sha256)
    inputs, base = original._prepare(**arguments)
    require(_same(private(original_review_path, original_review_sha256), base),
            'continuation_exact_original_review_required')
    require(len(inputs.roster['splits']['selection']) == TOTAL_TRIOS and
            len({row['task_id'] for row in inputs.roster['splits']['selection']}) == TOTAL_TRIOS,
            'continuation_exact_original_twenty_required')
    old_root = Path(arguments['output']).resolve()
    require(not (old_root/'controls.private.json').exists(),
            'continuation_interrupted_original_namespace_required')
    claim = old_root.parent/f'selection-reference-{original_review_sha256}-consumed.private.json'
    require(private(claim).get('root_review_sha256') == original_review_sha256,
            'continuation_original_one_use_launch_required')
    historical = private(interruption_audit_path, interruption_audit_sha256)
    cleanup = private(cleanup_result_path, cleanup_result_sha256)
    require(historical.get('schema') == 'magento-interrupted-selection20-audit-final-v1' and
            historical.get('completed_whole_trios') == REUSED_TRIOS and
            historical.get('whole_trio_attempt_ordinals') == list(range(REUSED_TRIOS)) and
            historical.get('completed_native_modes') == 34 and
            historical.get('original_artifacts_verified_unchanged') is True and
            historical.get('full_selection20_complete') is False,
            'continuation_exact_interruption_audit_required')
    preservation_ref = _preserved_original(old_root, historical)
    require(cleanup.get('schema') == 'magento-exact-owned-interruption-cleanup-result-v1' and
            all(cleanup.get(key) is True for key in ('exact_container_ids_and_names_absent',
                'exact_network_id_and_name_absent', 'original_artifacts_unchanged',
                'original_host_pid_absent')) and
            all(type(cleanup.get(key)) is int and cleanup[key] == 0 for key in ('uncertain_commands', 'automatic_replays',
                'old_partial_mode_credit', 'cohort_runs', 'model_calls', 'tinker_calls')) and
            cleanup.get('formal_native_reset_or_close_receipt_recreated') is False,
            'continuation_exact_owned_resource_cleanup_required')
    partial_root = old_root/'attempt-011/positive'
    partial_held = private(partial_root/'guard/held-lease.private.json')
    targets = cleanup.get('exact_targets', {})
    containers = targets.get('containers', [])
    require(targets.get('context') == 'colima-cua-scale' and len(containers) == 2 and
            all(sha256(container['id'].encode()).hexdigest() == partial_held[kind+'_id_sha256'] and
                container['image'] == partial_held[kind+'_image_sha256']
                for kind, container in zip(('app', 'search'), containers)) and
            cleanup.get('preserved_files') == historical.get('preserved_files') and
            cleanup.get('preserved_bytes') == historical.get('preserved_bytes'),
            'continuation_cleanup_must_bind_original_partial_resources')
    output = _safe_output(output)
    preserved_root = old_root.parent
    require(output != preserved_root and not output.is_relative_to(preserved_root) and
            not preserved_root.is_relative_to(output), 'continuation_fresh_separate_namespace_required')
    prefix = [_original_task(inputs, old_root, ordinal) for ordinal in range(REUSED_TRIOS)]
    ignored = old_root/'attempt-011/baseline/native-row.private.json'
    ignored_row = private(ignored)
    require({key: ignored_row[key] for key in ('task_id', 'package_sha256')} ==
            inputs.roster['splits']['selection'][REUSED_TRIOS],
            'continuation_preserved_partial_identity_changed')
    contract = {'schema': 'magento-selection20-continuation-root-review-v1',
        'source_binding': source_binding(), 'original_reference_review': base,
        'original_arguments_ref': _ref(original_arguments_path, original_arguments_sha256),
        'original_review_ref': _ref(original_review_path, original_review_sha256),
        'interruption_audit_ref': _ref(interruption_audit_path, interruption_audit_sha256),
        'original_preservation_manifest_ref': preservation_ref,
        'cleanup_result_ref': _ref(cleanup_result_path, cleanup_result_sha256),
        'original_output_root': str(old_root), 'output_root': str(output),
        'selection_tasks': inputs.roster['splits']['selection'],
        'reused_whole_trios': prefix, 'fresh_original_ordinals': list(range(REUSED_TRIOS, TOTAL_TRIOS)),
        'fresh_mode_count': (TOTAL_TRIOS-REUSED_TRIOS)*len(MODES), 'accepted_mode_count': 60,
        'modes': [mode for mode, _ in MODES], 'task_count': TOTAL_TRIOS,
        'discarded_partial_baseline_ref': _ref(ignored),
        'historical_completed_native_modes': 34, 'historical_accepted_native_modes': 33,
        'old_partial_mode_credit': 0, 'failure_costs_preserved_separately': True,
        'actor_turn_limit': 90, 'actor_seconds_limit': 720, 'owned_lifecycle_seconds_limit': 1200,
        'native_actor_sampler_scorer_guard_reset_changed': False,
        'automatic_restart_authorized': False, 'formal_registration_authorized': False,
        'model_lane_admission_claimed': False, 'model_calls': 0, 'tinker_calls': 0}
    return inputs, contract, arguments


def review_contract(**kwargs):
    """Reopen original saved evidence only; no new task load or runtime."""
    return _prepare(**kwargs)[1]


def _authority_root():
    return Path(__file__).resolve().parents[1]/'work/magento-continuation-authority.private'


def aggregate_saved_audit(inputs, contract, manifest_path, manifest_sha256):
    """Strict saved verification of all twenty ordered tasks and sixty modes."""
    manifest = private(manifest_path, manifest_sha256)
    expected_keys = {'schema', 'continuation_binding_sha256', 'selection_identities', 'task_count',
                     'mode_count', 'tasks', 'model_calls', 'tinker_calls', 'old_partial_mode_credit',
                     'formal_registration_performed', 'fresh_run_owner_ref'}
    require(set(manifest) == expected_keys and
            manifest['schema'] == 'magento-selection20-continuation-controls-v1' and
            manifest['continuation_binding_sha256'] == contract['source_binding']['binding_sha256'] and
            manifest['selection_identities'] == contract['selection_tasks'] and
            type(manifest['task_count']) is int and manifest['task_count'] == TOTAL_TRIOS and
            type(manifest['mode_count']) is int and manifest['mode_count'] == 60 and
            all(type(manifest[key]) is int and manifest[key] == 0
                for key in ('model_calls', 'tinker_calls', 'old_partial_mode_credit')) and
            manifest['formal_registration_performed'] is False and len(manifest['tasks']) == TOTAL_TRIOS,
            'continuation_strict_full_twenty_manifest_required')
    owner_path = Path(contract['output_root'])/'continuation-run-owner.private.json'
    require(manifest['fresh_run_owner_ref'] == _ref(owner_path), 'continuation_run_owner_changed')
    owner = private(owner_path, manifest['fresh_run_owner_ref']['sha256'])
    require(owner.get('schema') == 'magento-continuation-owned-host-run-v1' and
            type(owner.get('pid')) is int and owner['pid'] > 0 and
            type(owner.get('started_monotonic')) in (int, float) and
            owner.get('continuation_binding_sha256') == contract['source_binding']['binding_sha256'] and
            owner.get('automatic_restart_authorized') is False,
            'continuation_actual_host_run_owner_required')
    totals = {'actions': 0, 'frames': 0, 'actor_wall_time_ms': 0, 'lifecycle_wall_time_ms': 0}
    for ordinal, task in enumerate(manifest['tasks']):
        if ordinal < REUSED_TRIOS:
            require(task == contract['reused_whole_trios'][ordinal],
                    'continuation_original_whole_trio_provenance_changed')
            root = contract['original_output_root']
        else:
            require(task.get('origin') == 'fresh_remaining_whole_trio',
                    'continuation_fresh_partial_task_cannot_be_promoted')
            root = Path(contract['output_root'])/'fresh-controls.private'
        checked = _audit_trio(inputs, ordinal, task, root, None if ordinal < REUSED_TRIOS else owner)
        for key in totals: totals[key] += checked[key]
    return {'controls_ref': _ref(manifest_path, manifest_sha256), 'task_count': TOTAL_TRIOS,
            'mode_count': 60, 'reused_complete_trios': REUSED_TRIOS,
            'fresh_complete_trios': TOTAL_TRIOS-REUSED_TRIOS, 'saved_state_reset_rederived': True,
            'original_order_and_identities_rederived': True, **totals}


def run(*, root_review_path, root_review_sha256, execute=False, **kwargs):
    require(execute is True, 'explicit_new_reviewed_continuation_execution_required')
    inputs, expected, arguments = _prepare(**kwargs)
    require(_same(private(root_review_path, root_review_sha256), expected),
            'continuation_exact_current_root_review_required')
    output = _safe_output(expected['output_root'])
    require(not output.exists(), 'continuation_fresh_output_required')
    # A fixed repository-owned claim prevents reuse even after output deletion.
    authority = _safe_output(_authority_root())
    authority.mkdir(mode=0o700, exist_ok=True)
    require(authority.stat().st_mode & 0o077 == 0 and not authority.is_symlink(),
            'continuation_private_authority_required')
    write(authority, root_review_sha256+'-consumed.private.json',
          {'root_review_sha256': root_review_sha256, 'pid': os.getpid(),
           'automatic_replay_authorized': False, 'model_calls': 0, 'tinker_calls': 0})
    output.mkdir(mode=0o700, parents=True)
    owner = {'schema': 'magento-continuation-owned-host-run-v1', 'pid': os.getpid(),
             'started_monotonic': time.monotonic(),
             'continuation_binding_sha256': expected['source_binding']['binding_sha256'],
             'root_review_ref': _ref(root_review_path, root_review_sha256),
             'automatic_restart_authorized': False}
    write(output, 'continuation-run-owner.private.json', owner)
    tasks = list(expected['reused_whole_trios'])
    try:
        for ordinal in expected['fresh_original_ordinals']:
            require(_prepare(**kwargs)[1] == expected, 'continuation_prerequisites_changed')
            identity = inputs.roster['splits']['selection'][ordinal]
            case = inputs.load(identity, 'selection'); trio = {}
            for mode, score in MODES:
                require(source_binding() == expected['source_binding'], 'continuation_source_changed')
                folder = output/'fresh-controls.private'/f'attempt-{ordinal:03d}'/mode
                folder.mkdir(mode=0o700, parents=True)
                sampler = original.facade.ReferenceSampler(case, mode)
                row = asyncio.run(original.facade.run_task(case=case, task=identity, output=folder,
                    runtime=inputs.runtime(), sampler=sampler, username=inputs.username(),
                    attempt_id=f'continuation-control-{ordinal:03d}-{mode}', paid_attempt_id=None))
                write(folder, 'native-row.private.json', row)
                proof = {'score': row['score'], 'episode_root': str(folder.resolve()),
                         'native_row_sha256': _sha(folder/'native-row.private.json')}
                # Validate each mode immediately; never dispatch the next mode after a failure.
                require(row['score'] == score and type(row['score']) is int,
                        'continuation_reference_mode_score_failed')
                require(all(sample.get('paid_attempt_id') is None and
                            sample.get('status') == 'control_action' and
                            sample.get('raw_result', {}).get('model_call_performed') is False
                            for sample in row['samples']), 'continuation_reference_only_samples_required')
                original.audit.audit_episode(folder, row, provider_close_required=False)
                trio[mode] = proof
            task = {**identity, 'ordinal': ordinal, 'origin': 'fresh_remaining_whole_trio', 'trio': trio}
            _audit_trio(inputs, ordinal, task, output/'fresh-controls.private', owner)
            tasks.append(task); write(output, f'completed-trio-{ordinal:03d}.private.json', task)
        require(_prepare(**kwargs)[1] == expected, 'continuation_final_prerequisites_changed')
        manifest = {'schema': 'magento-selection20-continuation-controls-v1',
            'continuation_binding_sha256': expected['source_binding']['binding_sha256'],
            'selection_identities': expected['selection_tasks'], 'task_count': TOTAL_TRIOS,
            'mode_count': 60, 'tasks': tasks, 'model_calls': 0, 'tinker_calls': 0,
            'fresh_run_owner_ref': _ref(output/'continuation-run-owner.private.json'),
            'old_partial_mode_credit': 0, 'formal_registration_performed': False}
        write(output, 'aggregate-controls.private.json', manifest)
        checked = aggregate_saved_audit(inputs, expected, output/'aggregate-controls.private.json',
                                        _sha(output/'aggregate-controls.private.json'))
        require(source_binding() == expected['source_binding'], 'continuation_source_changed')
        result = {'schema': 'magento-selection20-continuation-result-v1',
            'root_review_ref': _ref(root_review_path, root_review_sha256),
            'source_binding': expected['source_binding'], 'saved_audit': checked,
            'interruption_audit_ref': expected['interruption_audit_ref'],
            'discarded_partial_baseline_ref': expected['discarded_partial_baseline_ref'],
            'failure_costs_preserved_separately': True, 'old_partial_mode_credit': 0,
            'source_visual_qualification_complete': False, 'formal_registration_performed': False,
            'model_lane_admission_claimed': False, 'model_calls': 0, 'tinker_calls': 0}
        write(output, 'continuation-result.private.json', result)
        return result
    except BaseException as error:
        write(output, 'failure.private.json', {'schema': 'magento-selection20-continuation-failure-v1',
            'error_type': type(error).__name__, 'completed_whole_trios': len(tasks)-REUSED_TRIOS,
            'automatic_replay_authorized': False, 'old_partial_mode_credit': 0,
            'model_calls': 0, 'tinker_calls': 0, 'formal_registration_performed': False})
        raise


def saved_audit(*, root_review_path, root_review_sha256, **kwargs):
    inputs, expected, _ = _prepare(**kwargs)
    require(_same(private(root_review_path, root_review_sha256), expected),
            'continuation_exact_current_root_review_required')
    output = Path(expected['output_root'])
    require(not (output/'failure.private.json').exists(), 'failed_continuation_not_complete')
    result = private(output/'continuation-result.private.json')
    checked = aggregate_saved_audit(inputs, expected, output/'aggregate-controls.private.json',
                                    result['saved_audit']['controls_ref']['sha256'])
    require(_same(result, {'schema': 'magento-selection20-continuation-result-v1',
        'root_review_ref': _ref(root_review_path, root_review_sha256),
        'source_binding': expected['source_binding'], 'saved_audit': checked,
        'interruption_audit_ref': expected['interruption_audit_ref'],
        'discarded_partial_baseline_ref': expected['discarded_partial_baseline_ref'],
        'failure_costs_preserved_separately': True, 'old_partial_mode_credit': 0,
        'source_visual_qualification_complete': False, 'formal_registration_performed': False,
        'model_lane_admission_claimed': False, 'model_calls': 0, 'tinker_calls': 0}),
        'continuation_saved_result_changed')
    owner = private(output/'continuation-run-owner.private.json')
    require(owner.get('root_review_ref') == result['root_review_ref'],
            'continuation_saved_owner_review_changed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('review', 'run', 'audit'))
    for name in ('original-arguments-path', 'original-arguments-sha256', 'original-review-path',
                 'original-review-sha256', 'interruption-audit-path', 'interruption-audit-sha256',
                 'cleanup-result-path', 'cleanup-result-sha256', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--root-review-path'); parser.add_argument('--root-review-sha256')
    parser.add_argument('--review-output'); parser.add_argument('--execute', action='store_true')
    args = vars(parser.parse_args()); command = args.pop('command'); destination = args.pop('review_output')
    if command == 'review':
        args.pop('root_review_path'); args.pop('root_review_sha256'); args.pop('execute')
        require(destination is not None, 'continuation_private_review_output_required')
        value = review_contract(**args); path = Path(destination)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True); write(path.parent, path.name, value)
    else:
        if command == 'audit': args.pop('execute')
        (run if command == 'run' else saved_audit)(**args)
    print(json.dumps({'status': 'continuation_'+command+'_complete', 'cohort_launch_from_review': False,
                      'model_calls': 0, 'tinker_calls': 0, 'formal_registration_performed': False}))


if __name__ == '__main__': main()
