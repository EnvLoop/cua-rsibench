"""Frozen20 pilot controls on the unchanged sealed Odoo100/native57 world.

This is an explicit subset authority, not a full100 or six-cell admission.
Each case calls the original reference-v3 runner and saved independent auditor.
Raw controls remain pending until a separate source-frame review is supplied.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import secrets
from . import twenty_task_trial_evaluator_v1 as evaluator
from . import native_surface_workers_v13 as workers
from . import native_reference_viewport_v3 as reference
from . import native_reference_split_finalizer_v3 as finalizer
from .partition_factory import source_asset
from tools import odoo_v066_native_reference_qualification_v3 as qualification
from tools import odoo_v066_scale_controller_v1 as controller

require, digest, private, write = evaluator.require, evaluator.digest, evaluator.private, evaluator.write
SCHEMA = 'envloop-odoo20-native-control-plan-v1'
PENDING = 'twenty_saved_controls_pending_independent_source_visual_review'
VERIFIED = 'twenty_saved_controls_and_independent_source_visual_review_verified'
FIELDS = {'schema', 'trial_plan_ref', 'source_binding', 'native_core_plan', 'reference_binding',
          'frozen_twenty_metadata', 'fresh_run_directory_name', 'model_calls', 'formal_large_study_credit',
          'official_final_tasks_admitted', 'automatic_replay_authorized'}


def source_binding():
    value = {'schema': 'envloop-odoo20-native-control-source-v1',
        'native_binding_sha256': workers.public_binding()['binding_sha256'],
        'reference_binding_sha256': reference.reference_binding()['reference_binding_sha256'],
        'source_sha256s': {'enterprise_fallback/odoo18/twenty_task_trial_controls_v1.py': digest(Path(__file__).read_bytes()),
            'enterprise_fallback/odoo18/twenty_task_trial_evaluator_v1.py': digest(Path(evaluator.__file__).read_bytes()),
            'enterprise_fallback/odoo18/native_reference_split_finalizer_v3.py': digest(Path(finalizer.__file__).read_bytes())},
        'original_world_count': 100, 'pilot_control_count': 20, 'formal_admission_permitted': False}
    return {**value, 'binding_sha256': digest(workers.canonical(value))}


def prepare(*, trial_plan_path, trial_plan_sha):
    """Source/metadata only. No worker bodies, native calls or model requests."""
    trial, _ = evaluator.checked_trial(trial_plan_path, trial_plan_sha)
    original = evaluator.read_ref(trial['original_candidate_plan_ref'])
    core = copy.deepcopy(original['native_core_plan'])
    nonce = secrets.token_hex(16)
    core.update(run_nonce_hex=nonce, run_nonce_sha256=digest(nonce.encode()), fresh_run_directory_name='native-v13-'+nonce)
    qualification.validate_plan({**original, 'native_core_plan': core})
    plan = {'schema': SCHEMA, 'trial_plan_ref': {'path': str(Path(trial_plan_path).resolve()), 'sha256': trial_plan_sha},
        'source_binding': source_binding(), 'native_core_plan': core, 'reference_binding': original['reference_binding'],
        'frozen_twenty_metadata': trial['final_tasks_metadata'], 'fresh_run_directory_name': 'odoo20-controls-'+nonce,
        'model_calls': 0, 'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0, 'automatic_replay_authorized': False}
    return plan, {'schema': SCHEMA, 'status': 'source_metadata_prepared_no_native_calls', 'control_count': 20,
        'original_world_count': 100, 'private_plan_sha256': digest(workers.canonical(plan)),
        'native_binding_sha256': core['native_worker_binding_sha256'], 'formal_large_study_credit': 0,
        'official_final_tasks_admitted': 0, 'model_calls': 0}


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == FIELDS and plan['schema'] == SCHEMA and
        plan['source_binding'] == source_binding() and plan['automatic_replay_authorized'] is False and
        all(type(plan[key]) is int and plan[key] == 0 for key in ('model_calls', 'formal_large_study_credit', 'official_final_tasks_admitted')),
        'explicit_unqualified_twenty_control_authority_required')
    trial, candidates = evaluator.checked_trial(plan['trial_plan_ref']['path'], plan['trial_plan_ref']['sha256'])
    core = plan['native_core_plan']
    require(plan['frozen_twenty_metadata'] == trial['final_tasks_metadata'] and core['tasks'] == candidates and
        core['split'] == 'official_hidden' and core['task_count'] == 100 and
        plan['reference_binding'] == reference.reference_binding() and
        core['native_worker_binding_sha256'] == trial['native_binding_sha256'] and
        plan['fresh_run_directory_name'] == 'odoo20-controls-'+core['run_nonce_hex'],
        'trial_control_twenty_projection_or_hundred_source_changed')
    original = evaluator.read_ref(trial['original_candidate_plan_ref'])
    require(core['run_nonce_hex'] != original['native_core_plan']['run_nonce_hex'], 'trial_controls_fresh_nonce_required')
    expected = copy.deepcopy(original['native_core_plan'])
    expected.update(run_nonce_hex=core['run_nonce_hex'], run_nonce_sha256=digest(core['run_nonce_hex'].encode()),
                    fresh_run_directory_name='native-v13-'+core['run_nonce_hex'])
    require(core == expected, 'trial_original_hundred_core_binding_changed')
    qualification.validate_plan({**original, 'native_core_plan': core})
    return plan


def _load(plan_path, plan_sha):
    raw = private(plan_path)
    require(digest(raw) == plan_sha and raw == workers.canonical(json.loads(raw)), 'trial_control_canonical_plan_required')
    return validate_plan(json.loads(raw))


def _case_audit(facade, plan, metadata, attempt, worker_private, prerequisite_sha):
    row = facade._case_row(plan['native_core_plan'], metadata, prerequisite_sha)
    audit = facade.audit_case(plan=plan['native_core_plan'], row=row, attempt=attempt, worker_private=worker_private)
    require([audit.get(key) for key in ('independent_baseline_reward', 'independent_positive_reward',
        'independent_wrong_object_reward')] == [0.0, 1.0, 0.0] and
        audit.get('original_services_restored') is True and audit.get('full_pre_web_filestore_reset_exact') is True and
        audit.get('protected_post_web_source_bytes_equal') is True and audit.get('source_attachment_gui_frame_retained') is True and
        audit.get('protected_source_files_checked') == 3*(plan['native_core_plan']['task_count']//4)+1 and audit.get('model_attempts') == 0 and
        audit.get('official_final_tasks_admitted') == 0, 'trial_original_saved_control_score_reset_or_source_unproved')
    reader = finalizer.SavedReader()
    receipt, _ = reader.value(attempt/'attempt.private.json')
    provenance = finalizer._v3_action_provenance(reader, attempt, receipt, audit, plan['reference_binding'])
    reader.unchanged()
    return audit, provenance


def run(*, plan_path, plan_sha, worker_dir, run_dir, train_control_path, train_control_sha,
        root_review_path, root_review_sha, execute=False):
    require(execute is True, 'trial_control_explicit_native_dispatch_required')
    plan = _load(plan_path, plan_sha)
    review = workers.private_json(root_review_path, root_review_sha)
    require(review == {'schema': 'envloop-odoo20-native-controls-root-review-v1', 'control_plan_sha256': plan_sha,
        'trial_plan_sha256': plan['trial_plan_ref']['sha256'], 'source_binding_sha256': plan['source_binding']['binding_sha256'],
        'train_control_sha256': train_control_sha, 'twenty_subset_controls_authorized': True,
        'formal_hundred_or_six_cell_admission_authorized': False, 'automatic_retry_authorized': False},
        'trial_control_exact_subset_root_review_required')
    core, binding = plan['native_core_plan'], plan['native_core_plan']['native_worker_binding']
    train = workers.validate_train_control(workers.private_json(train_control_path, train_control_sha), binding)
    require(train['run_nonce_sha256'] != core['run_nonce_sha256'], 'trial_control_train_nonce_reused')
    worker, out = Path(worker_dir).resolve(), Path(run_dir)
    require(worker.name == 'official_hidden' and out.is_absolute() and
        out.parent.resolve() == worker/'private/v066_twenty_task_controls_v1' and
        out.name == plan['fresh_run_directory_name'] and not out.exists() and not out.is_symlink(),
        'trial_controls_owned_fresh_namespace_required')
    os.environ['ENVLOOP_ODOO_WORKER_DIR'] = str(worker)
    facade = qualification._facade(plan['reference_binding'])
    # This unchanged preflight validates the complete100 source/checkpoint
    # world. It does not shrink a partition or grant100 control credit.
    world, worker_private = facade._live_preflight(core, worker)
    modules = controller._modules(worker)
    if not out.parent.exists(): out.parent.mkdir(mode=0o700)
    require(out.parent.stat().st_mode & 0o077 == 0 and not out.parent.is_symlink(), 'trial_control_private_parent_required')
    with controller._run_lock(out.parent):
        out.mkdir(mode=0o700)
        write(out, 'control-intent.private.json', {'schema': 'envloop-odoo20-native-controls-intent-v1',
            'control_plan_sha256': plan_sha, 'trial_plan_sha256': plan['trial_plan_ref']['sha256'],
            'source_binding_sha256': plan['source_binding']['binding_sha256'], 'fresh_train_control_sha256': train_control_sha,
            'root_review_sha256': root_review_sha, 'native_binding_sha256': binding['binding_sha256'],
            'original_world_count': 100, 'expected_case_count': 20, 'model_calls': 0,
            'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0, 'automatic_replay_authorized': False})
        runner = reference.candidate_module(binding, plan['reference_binding'])
        cases = {case['id']: (family, case) for family, group in world['cases'].items() for case in group}
        entries = []
        for ordinal, metadata in enumerate(plan['frozen_twenty_metadata']):
            _load(plan_path, plan_sha)
            require(digest(private(root_review_path)) == root_review_sha and
                digest(private(train_control_path)) == train_control_sha, 'trial_control_authority_changed_before_dispatch')
            row = facade._case_row(core, metadata, train_control_sha)
            family, case = cases[metadata['task_id']]
            wrong = next(item for item in world['cases'][family] if item['id'] != case['id'])
            try:
                with modules[-1].exclusive_worker_operation(controller.LEASE_OPERATION):
                    runner.execute_case(run_dir=out, ordinal=ordinal, row=row, case=case, wrong=wrong, family=family, modules=modules)
                attempt = out/f'attempt-{ordinal:03d}'
                audit, provenance = _case_audit(facade, plan, metadata, attempt, worker_private, train_control_sha)
                audit_ref = write(attempt, 'independent-audit.private.json', audit)
                provenance_ref = write(attempt, 'reference-provenance.private.json', provenance)
                entries.append({'metadata': metadata, 'attempt': evaluator.legacy.final.reference(out, attempt/'attempt.private.json'),
                    'audit': {'path': f'attempt-{ordinal:03d}/'+audit_ref['path'], 'sha256': audit_ref['sha256']},
                    'reference_provenance': {'path': f'attempt-{ordinal:03d}/'+provenance_ref['path'], 'sha256': provenance_ref['sha256']}})
            except BaseException as error:
                write(out, 'failed.private.json', {'schema': 'envloop-odoo20-native-controls-failure-v1', 'ordinal': ordinal,
                    'completed_controls': len(entries), 'error_type': type(error).__name__, 'error_sha256': digest(str(error).encode()),
                    'model_calls': 0, 'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0,
                    'automatic_replay_authorized': False})
                raise
        result = {'schema': 'envloop-odoo20-native-controls-result-v1', 'status': PENDING,
            'control_plan_sha256': plan_sha, 'trial_plan_sha256': plan['trial_plan_ref']['sha256'],
            'native_binding_sha256': binding['binding_sha256'], 'reference_binding_sha256': plan['reference_binding']['reference_binding_sha256'],
            'original_world_count': 100, 'saved_control_count': 20, 'source_visual_review_pending': True,
            'entries': entries, 'model_calls': 0, 'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0}
        write(out, 'controls-result.private.json', result)
        return {key: value for key, value in result.items() if key != 'entries'}


def audit(*, plan_path, plan_sha, worker_dir, run_dir, source_review_path=None, source_review_sha=None):
    """Saved-only replay. Separate reviewer supplies all20 native/source QA."""
    plan = _load(plan_path, plan_sha)
    require((source_review_path is None and source_review_sha is None) or
        (source_review_path is not None and type(source_review_sha) is str and workers.HEX64.fullmatch(source_review_sha) is not None),
        'trial_source_review_hash_bound_reference_required')
    worker, out = Path(worker_dir).resolve(), Path(run_dir).resolve()
    require(worker.name == 'official_hidden' and out.parent == worker/'private/v066_twenty_task_controls_v1' and
        out.name == plan['fresh_run_directory_name'], 'trial_control_saved_namespace_changed')
    result = workers.private_json(out/'controls-result.private.json')
    intent = workers.private_json(out/'control-intent.private.json')
    require(result.get('schema') == 'envloop-odoo20-native-controls-result-v1' and result.get('status') == PENDING and
        result.get('control_plan_sha256') == plan_sha and result.get('trial_plan_sha256') == plan['trial_plan_ref']['sha256'] and
        result.get('native_binding_sha256') == plan['native_core_plan']['native_worker_binding_sha256'] and
        result.get('reference_binding_sha256') == plan['reference_binding']['reference_binding_sha256'] and
        result.get('saved_control_count') == 20 and result.get('original_world_count') == 100 and
        result.get('model_calls') == result.get('formal_large_study_credit') == result.get('official_final_tasks_admitted') == 0 and
        len(result.get('entries', [])) == 20 and intent.get('control_plan_sha256') == plan_sha and
        intent.get('source_binding_sha256') == plan['source_binding']['binding_sha256'] and
        intent.get('original_world_count') == 100 and intent.get('expected_case_count') == 20 and
        intent.get('model_calls') == intent.get('formal_large_study_credit') == intent.get('official_final_tasks_admitted') == 0 and
        intent.get('automatic_replay_authorized') is False,
        'trial_twenty_saved_control_result_required')
    review = None
    if source_review_path is not None:
        review = workers.private_json(source_review_path, source_review_sha)
        require(review.get('schema') == 'envloop-odoo20-native-controls-source-review-v1' and
            review.get('control_plan_sha256') == plan_sha and review.get('reviewer_independent_of_actor') is True and
            review.get('controls_result_sha256') == digest(private(out/'controls-result.private.json')) and
            type(review.get('rows')) is list and len(review['rows']) == 20, 'trial_independent_full_twenty_source_review_required')
    os.environ['ENVLOOP_ODOO_WORKER_DIR'] = str(worker)
    facade = qualification._facade(plan['reference_binding'])
    world, worker_private = facade._live_preflight(plan['native_core_plan'], worker)
    cases = {case['id']: case for group in world['cases'].values() for case in group}
    read = finalizer.SavedReader()
    rows = []
    for ordinal, (metadata, entry) in enumerate(zip(plan['frozen_twenty_metadata'], result['entries'], strict=True)):
        require(entry.get('metadata') == metadata and entry['attempt']['path'] == f'attempt-{ordinal:03d}/attempt.private.json' and
            entry['audit']['path'] == f'attempt-{ordinal:03d}/independent-audit.private.json' and
            entry['reference_provenance']['path'] == f'attempt-{ordinal:03d}/reference-provenance.private.json',
            'trial_saved_controls_exact_roster_or_path_changed')
        attempt = out/f'attempt-{ordinal:03d}'
        receipt_path, receipt_raw = read.ref(entry['attempt'], out)
        _, audit_raw = read.ref(entry['audit'], out)
        _, provenance_raw = read.ref(entry['reference_provenance'], out)
        saved_audit, provenance = _case_audit(facade, plan, metadata, attempt, worker_private, intent['fresh_train_control_sha256'])
        require(json.loads(audit_raw) == saved_audit and json.loads(provenance_raw) == provenance,
            'trial_saved_control_independent_replay_changed')
        receipt = json.loads(receipt_raw)
        row = {'task_id': metadata['task_id'], 'package_sha256': metadata['package_sha256'], 'family': metadata['family'],
            'independent_scores': [0, 1, 0], 'attempt_sha256': digest(receipt_raw), 'audit_sha256': digest(audit_raw),
            'source_frame_sha256': receipt['refs']['source_frame']['sha256'], 'source_visual_review_verified': False}
        if review is not None:
            approved = review['rows'][ordinal]
            require(approved.get('task_id') == metadata['task_id'] and approved.get('package_sha256') == metadata['package_sha256'] and
                approved.get('source_frame_sha256') == row['source_frame_sha256'] and
                approved.get('source_attachment_readable') is True and approved.get('source_matches_package') is True,
                'trial_source_review_identity_or_readability_unproved')
            _, frame = read.ref(receipt['refs']['source_frame'], attempt)
            _, native_copy = read.ref(approved['native_frame_copy'])
            _, asset_copy = read.ref(approved['exact_source_asset_copy'])
            pair_path, _ = read.ref(approved['side_by_side_qa'])
            require(frame == native_copy and asset_copy == source_asset(cases[metadata['task_id']], world) and
                digest(asset_copy) == metadata['source_asset_sha256'], 'trial_reviewed_source_or_native_pixels_changed')
            from PIL import Image
            import io
            with Image.open(io.BytesIO(frame)) as native, Image.open(pair_path) as pair:
                x, y = approved['native_crop_origin']
                require(pair.crop((x, y, x+native.width, y+native.height)).convert('RGB').tobytes() == native.convert('RGB').tobytes(),
                    'trial_reviewed_qa_native_panel_changed')
            require(finalizer._stamp(approved['reviewed_at_utc']) >= finalizer._stamp(receipt['finished_at_utc']),
                'trial_visual_review_predates_control')
            row['source_visual_review_verified'] = True
        rows.append(row)
    read.unchanged()
    return {'schema': 'envloop-odoo20-native-controls-audit-v1', 'status': VERIFIED if review else PENDING,
        'control_plan_sha256': plan_sha, 'trial_plan_sha256': plan['trial_plan_ref']['sha256'],
        'native_binding_sha256': plan['native_core_plan']['native_worker_binding_sha256'],
        'reference_binding_sha256': plan['reference_binding']['reference_binding_sha256'],
        'control_count': 20, 'original_world_count': 100, 'rows': rows, 'source_visual_review_pending': review is None,
        'source_review_sha256': source_review_sha, 'model_calls': 0, 'formal_large_study_credit': 0, 'official_final_tasks_admitted': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--trial-plan-path', required=True); prep.add_argument('--trial-plan-sha', required=True)
    prep.add_argument('--output-path', required=True)
    live = sub.add_parser('run')
    for field in ('plan-path', 'plan-sha', 'worker-dir', 'run-dir', 'train-control-path', 'train-control-sha',
                  'root-review-path', 'root-review-sha'): live.add_argument('--'+field, required=True)
    live.add_argument('--execute', action='store_true')
    check = sub.add_parser('audit')
    for field in ('plan-path', 'plan-sha', 'worker-dir', 'run-dir'): check.add_argument('--'+field, required=True)
    check.add_argument('--source-review-path'); check.add_argument('--source-review-sha')
    args = vars(parser.parse_args()); command = args.pop('command')
    if command == 'prepare':
        path = Path(args.pop('output_path')); plan, result = prepare(**args)
        write(path.parent, path.name, plan)
    elif command == 'run': result = run(**args)
    else: result = audit(**args)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
