"""Explicit Odoo20 development evaluation; no full-study admission authority.

The original sealed 100-task source remains intact. Only the deterministic
20-task projection is dispatchable, after a selection-only checkpoint freeze.
Preflight reads metadata only; hidden bodies open inside the existing evaluator
after the per-task intent has consumed a fresh attempt. No automatic retries.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import importlib
from . import native_surface_final_worker_v1 as legacy
from . import native_surface_workers_v13 as workers
from . import native_reference_viewport_v3 as reference
from .native_public_train_pilot_v22 import read_ref
from .native_surface_final_worker_v22 import MeteredSampler
from .odoo_actor_model_modules_v1 import run_owned_task
from .odoo_no_retry_sampler_v22 import sampler_class

ROOT = legacy.ROOT
require, digest, private, write = legacy.require, legacy.digest, legacy.private, legacy.write
CELL = 'odoo-community'
MODEL = 'Qwen/Qwen3.8-27B'
FAMILIES = ('purchase', 'inventory', 'sales', 'crm')
META_FIELDS = {'task_id', 'package_sha256', 'family', 'source_asset_sha256',
               'source_label', 'task_binding_sha256', 'visible_instruction_sha256'}
FILES = ('enterprise_fallback/odoo18/twenty_task_trial_evaluator_v1.py',
         'enterprise_fallback/odoo18/native_public_train_pilot_v22.py',
         'enterprise_fallback/odoo18/native_surface_final_worker_v22.py',
         'enterprise_fallback/odoo18/odoo_no_retry_sampler_v22.py',
         'src/cursibench/scale_vision_proxy.py')


def source_binding():
    native = workers.public_binding()
    value = {'schema': 'envloop-odoo20-evaluator-source-v1',
             'native_binding_sha256': native['binding_sha256'],
             'reference_binding_sha256': reference.reference_binding()['reference_binding_sha256'],
             'source_sha256s': {**native['source_sha256s'],
                                **{name: digest((ROOT/name).read_bytes()) for name in FILES}},
             'formal_large_study_credit': 0, 'formal_admission_permitted': False,
             'actor_limits': {'actions': 90, 'seconds': 720, 'owned_lifecycle_seconds': 1200}}
    return {**value, 'binding_sha256': digest(legacy.final.canonical(value))}


def _metadata(rows, count, per_family):
    require(type(rows) is list and len(rows) == count, 'trial_metadata_count_invalid')
    for row in rows:
        require(type(row) is dict and set(row) == META_FIELDS and
                type(row['task_id']) is str and row['task_id'] and
                row['family'] in FAMILIES and type(row['source_label']) is str and row['source_label'] and
                all(re.fullmatch(r'[0-9a-f]{64}', str(row[key])) is not None for key in
                    ('package_sha256', 'source_asset_sha256', 'task_binding_sha256', 'visible_instruction_sha256')),
                'trial_metadata_identity_invalid')
    require(len({row['task_id'] for row in rows}) == count and
            Counter(row['family'] for row in rows) == Counter({family: per_family for family in FAMILIES}),
            'trial_metadata_roster_invalid')


def checked_trial(plan_path, plan_sha):
    """Read hash-bound source/roster metadata without opening task bodies."""
    plan = workers.private_json(plan_path, plan_sha)
    current = source_binding()
    models = plan.get('models', {})
    require(plan.get('schema') == 'envloop-single-environment-twenty-task-trial-v1' and
            plan.get('cell_id') == CELL and plan.get('study_type') == 'single_environment_development_trial' and
            plan.get('original_candidate_count') == 100 and plan.get('final_task_count') == 20 and
            plan.get('selection_task_count') == plan.get('train_task_count') == 20 and
            set(models) == {'initial_researcher', 'teacher', 'student'} and models['student'] == MODEL and
            models['teacher'] == models['initial_researcher'] and models['teacher'] in ('gpt-6-sol', 'gpt-6-astra', 'gpt-6.1-sol') and
            plan.get('actor_limits') == current['actor_limits'] and
            plan.get('native_binding_sha256') == current['native_binding_sha256'] and
            plan.get('reference_binding_sha256') == current['reference_binding_sha256'] and
            plan.get('formal_large_study_credit') == 0 and plan.get('full_six_environment_publication_claim') is False and
            plan.get('sampling_uses_model_outcomes') is False and plan.get('unknown_billing_is_null') is True and
            plan.get('original_verifier_and_reset_required') is True and
            plan.get('base_and_selected_checkpoint_same_final_tasks_required') is True and
            plan.get('checkpoint_selection_before_final_outcomes_required') is True,
            'explicit_odoo20_development_authority_required')
    original = read_ref(plan['original_candidate_plan_ref'])
    core = original.get('native_core_plan', {})
    require(original.get('schema') == 'odoo-native-reference-qualification-plan-v3' and
            core.get('split') == 'official_hidden' and core.get('task_count') == 100 and
            core.get('native_worker_binding_sha256') == current['native_binding_sha256'] and
            original.get('reference_binding') == reference.reference_binding(),
            'trial_original_hundred_source_required')
    candidates = core.get('tasks')
    _metadata(candidates, 100, 25)
    rows = plan.get('final_tasks_metadata')
    _metadata(rows, 20, 5)
    require(type(plan.get('sampling_seed')) is str and bool(plan['sampling_seed']), 'trial_sampling_seed_required')
    expected = []
    for family in FAMILIES:
        ranked = sorted((row for row in candidates if row['family'] == family), key=lambda row:
                        digest((plan['sampling_seed']+'\0'+row['task_id']+'\0'+row['package_sha256']).encode()))
        expected.extend(ranked[:5])
    require(rows == expected and plan.get('family_counts') == {family: 5 for family in FAMILIES},
            'trial_frozen_deterministic_twenty_changed')
    return plan, candidates


class TrialSampler(MeteredSampler):
    """Use the real no-retry sampler and preserve both setup and sample calls."""
    def __enter__(self):
        write(self.episode, 'paid-setup-intent.private.json', {
            'schema': 'envloop-odoo20-paid-setup-intent-v1', 'attempt_id': self.command['attempt_id'],
            'model': MODEL, 'sampling_kind': 'base' if self.delegate.base_mode else 'checkpoint',
            'checkpoint_sha256': digest(self.delegate.checkpoint_path.encode()), 'actual_cost_usd': None,
            'http_max_retries': 0, 'sampling_retry_enabled': False, 'same_request_replay_authorized': False})
        returned = super().__enter__()
        try:
            write(self.episode, 'paid-setup-result.private.json', {
                'schema': 'envloop-odoo20-paid-setup-result-v1', 'status': 'ready',
                'actual_backend_identity': self.delegate.backend.identity, 'actual_cost_usd': None})
        except BaseException:
            import sys
            self.delegate.__exit__(*sys.exc_info())
            raise
        return returned


def _ref(root, reference_value):
    require(type(reference_value) is dict and set(reference_value) == {'path', 'sha256'}, 'trial_exact_reference_required')
    name = Path(reference_value['path'])
    require(not name.is_absolute() and '..' not in name.parts, 'trial_relative_reference_required')
    path = Path(root)/name
    raw = private(path)
    require(digest(raw) == reference_value['sha256'], 'trial_evidence_reference_changed')
    return json.loads(raw)


def checked_selection_freeze(freeze_ref, *, plan_sha, source_sha, selection_manifest, selection):
    """Require independently audited selection20, not a typed checkpoint name.

    The root creates this immutable receipt only after reviewing actual selection
    task rows. Per-task paid setup receipts bind the returned sampler identity.
    The final evaluator's fresh output is created after this receipt is read.
    """
    freeze = read_ref(freeze_ref)
    fields = {'schema', 'trial_plan_sha256', 'evaluator_source_sha256', 'checkpoint_path',
              'checkpoint_sha256', 'model', 'selection_split', 'selection_tasks',
              'checkpoint_frozen_before_final_outcomes', 'hidden_final_outcomes_used',
              'formal_large_study_credit'}
    require(type(freeze) is dict and set(freeze) == fields and
            freeze['schema'] == 'envloop-odoo20-selection-checkpoint-freeze-v1' and
            freeze['trial_plan_sha256'] == plan_sha and freeze['evaluator_source_sha256'] == source_sha and
            freeze['model'] == MODEL and freeze['selection_split'] == 'selection' and
            freeze['checkpoint_frozen_before_final_outcomes'] is True and freeze['hidden_final_outcomes_used'] is False and
            freeze['formal_large_study_credit'] == 0 and type(freeze['checkpoint_path']) is str and
            selection.campaign.TINKER_PATH.fullmatch(freeze['checkpoint_path']) is not None and
            digest(freeze['checkpoint_path'].encode()) == freeze['checkpoint_sha256'],
            'trial_selection_frozen_checkpoint_required')
    expected = {row['task_id']: row['package_sha256'] for row in selection_manifest}
    rows = freeze['selection_tasks']
    require(len(selection_manifest) == len(expected) == 20 and type(rows) is list and len(rows) == 20,
            'trial_selection_full_twenty_required')
    seen = set()
    for entry in rows:
        require(type(entry) is dict and set(entry) == {'task', 'episode_root', 'native_row', 'paid_setup_result'} and
                type(entry['task']) is dict and set(entry['task']) == {'task_id', 'package_sha256'} and
                entry['task']['task_id'] in expected and entry['task']['task_id'] not in seen and
                expected[entry['task']['task_id']] == entry['task']['package_sha256'],
                'trial_selection_identity_changed')
        seen.add(entry['task']['task_id'])
        episode = Path(entry['episode_root'])
        require(episode.is_absolute() and episode.is_dir() and not episode.is_symlink() and
                episode.stat().st_mode & 0o077 == 0, 'trial_selection_private_episode_required')
        row = _ref(episode, entry['native_row'])
        require(row.get('task_id') == entry['task']['task_id'] and row.get('package_sha256') == entry['task']['package_sha256'],
                'trial_selection_native_row_changed')
        selection._audit_task_artifacts(episode, entry['task'], row)
        setup = _ref(episode, entry['paid_setup_result'])
        require(setup.get('status') == 'ready' and setup.get('actual_backend_identity', {}).get('sampling_kind') == 'checkpoint' and
                setup['actual_backend_identity'].get('checkpoint_sha256') == selection.vision_digest(freeze['checkpoint_path']),
                'trial_selection_actual_checkpoint_setup_required')
        clock = _ref(episode, row['actor_clock_ref'])
        require(clock.get('native_actions_after_deadline') == 0 and clock.get('evaluation_outside_actor_clock') is True and
                0 <= clock['actor_elapsed_seconds'] <= 720, 'trial_selection_actor_clock_unproved')
        for field, code in (('owned_complete_lifecycle_ref', 'trial_selection_lifecycle_unproved'),
                            ('provider_close_ref', 'trial_selection_provider_close_unproved')):
            value = _ref(episode, row[field])
            if field == 'owned_complete_lifecycle_ref':
                require(value.get('saved_readback_reset_and_provider_close_complete') is True and
                        0 <= value['ended_monotonic']-value['started_monotonic'] <= 1200, code)
            else:
                require(value.get('status') == 'acknowledged' and value.get('real_close_call_returned') is True, code)
    return freeze


def audit_saved_episode(episode, task, row, environment, selection, binding, worker, metered):
    selection._audit_task_artifacts(episode, task, row)
    workers.audit_readiness_receipt(Path(episode)/'db-readiness.private.json', binding, worker)
    read = lambda name: json.loads(private(Path(episode)/name))
    saved, reset = read('saved-state.private.json'), read('reset.private.json')
    baseline, restored = read('baseline-semantic.private.json'), read('restored-semantic.private.json')
    require(reset['pre_database_filestore_exact'] is True and reset['post_database_filestore_exact'] is True and
            baseline == restored and len(environment.proofs) >= 2, 'trial_exact_reset_and_live_proof_required')
    proof = _ref(episode, environment.proofs[-1])
    require(proof['observed'] == saved['business_snapshot'] and proof['context'] == environment.proof_context,
            'trial_saved_readback_changed')
    verify = legacy._modules(worker, binding)[3]
    context = proof['context']
    verdict = legacy._evaluate(context['family'], task['task_id'], context['target'], context['baseline'],
                               saved['business_snapshot'], proof['physical_files'], context['frozen_files'],
                               proof['attachment_paths'], verify)
    score = int(verdict['reward'] == 1.0 and verdict['checks_passed'] is True and not verdict['difference_codes'])
    require(verdict == proof['verdict'] and score == row['score'], 'trial_independent_saved_score_changed')
    clock, life, close = (_ref(episode, row[key]) for key in
                          ('actor_clock_ref', 'owned_complete_lifecycle_ref', 'provider_close_ref'))
    require(clock['native_actions_after_deadline'] == 0 and clock['evaluation_outside_actor_clock'] is True and
            0 <= clock['actor_elapsed_seconds'] <= 720 and life['saved_readback_reset_and_provider_close_complete'] is True and
            0 <= life['ended_monotonic']-life['started_monotonic'] <= 1200 and
            close['status'] == 'acknowledged' and close['real_close_call_returned'] is True,
            'trial_actual_actor_lifecycle_close_unproved')
    usage = read('usage.private.json')
    require(len(usage['samples']) == len(metered.calls) and bool(metered.calls), 'trial_actual_paid_sample_coverage_required')
    return {'score': score, 'difference_codes': verdict['difference_codes'], 'native_row': row,
            'provider_calls': metered.calls, 'authentic_usage': usage, 'runtime_cleanup': environment.runtime_receipt,
            'actual_cost_usd': None, 'provider_invoice_sha256': None, 'formal_large_study_credit': 0}


def run(*, plan_path, plan_sha, native_binding_path, native_binding_sha,
        selection_freeze_path, selection_freeze_sha, worker_dir, output_root,
        root_review_path, root_review_sha, sampling_seed=0, sample_max_tokens=4096, execute=False):
    require(execute is True, 'trial_explicit_live_development_dispatch_required')
    plan, candidates = checked_trial(plan_path, plan_sha)
    source = source_binding()
    binding = workers.validate_binding(workers.private_json(native_binding_path, native_binding_sha))
    require(binding['binding_sha256'] == plan['native_binding_sha256'], 'trial_native_binding_changed')
    review = workers.private_json(root_review_path, root_review_sha)
    require(review == {'schema': 'envloop-odoo20-final-development-root-review-v1', 'trial_plan_sha256': plan_sha,
                       'evaluator_source_sha256': source['binding_sha256'], 'selection_freeze_sha256': selection_freeze_sha,
                       'development_twenty_pair_authorized': True, 'formal_admission_authorized': False,
                       'native_final_controls_status': 'pending_genuine_controls', 'automatic_retry_authorized': False},
            'trial_exact_development_root_review_required')
    require(type(sampling_seed) is int and 0 <= sampling_seed < 2**31 and
            type(sample_max_tokens) is int and 0 < sample_max_tokens <= 4096, 'trial_frozen_sampling_invalid')
    worker = Path(worker_dir).resolve()
    # Original module boundary validates partition/compose/private credentials;
    # this metadata-only read does not open partition_cases.json or any gold.
    manifest = workers.private_json(worker/'private/task_set_manifest.json')
    expected = {row['task_id']: row['package_sha256'] for row in candidates}
    require(worker.name == 'official_hidden' and
            {row['task_id']: row['package_sha256'] for row in manifest['official']} == expected and
            len(manifest['official']) == 100 and not expected.keys() &
            {row['task_id'] for split, rows in manifest.items() if split != 'official' for row in rows},
            'trial_original_sealed_roster_changed')
    _, selection = workers._model_modules(binding)
    freeze = checked_selection_freeze({'path': str(Path(selection_freeze_path).resolve()), 'sha256': selection_freeze_sha},
                                     plan_sha=plan_sha, source_sha=source['binding_sha256'],
                                     selection_manifest=manifest['selection'], selection=selection)
    require(not {row['task']['task_id'] for row in freeze['selection_tasks']} & set(expected), 'trial_selection_final_overlap')
    out = Path(output_root)
    require(out.is_absolute() and not out.exists() and not out.is_symlink() and
            out.resolve().is_relative_to(ROOT/'work'), 'trial_fresh_owned_pair_namespace_required')
    # Renderer preflight precedes paid setup and native work.
    from cursibench.scale_vision_proxy import QwenVisionRenderer
    QwenVisionRenderer.load()
    require(bool(os.environ.get('TINKER_API_KEY')), 'trial_tinker_key_missing')
    out.mkdir(parents=True, mode=0o700)
    write(out, 'pair-intent.private.json', {'schema': 'envloop-odoo20-final-development-intent-v1',
        'trial_plan_sha256': plan_sha, 'source_binding': source, 'selection_freeze_sha256': selection_freeze_sha,
        'root_review_sha256': root_review_sha, 'sampling_seed': sampling_seed, 'sample_max_tokens': sample_max_tokens,
        'formal_large_study_credit': 0, 'formal_final_tasks_admitted': 0, 'same_request_replay_authorized': False})
    identities = [{key: row[key] for key in ('task_id', 'package_sha256')} for row in candidates]
    outcomes = []
    for lane in ('baseline', 'selected_checkpoint'):
        for ordinal, metadata in enumerate(plan['final_tasks_metadata']):
            require(source_binding() == source, 'trial_source_changed_before_dispatch')
            checked_trial(plan_path, plan_sha)
            require(digest(private(selection_freeze_path)) == selection_freeze_sha and
                    digest(private(root_review_path)) == root_review_sha, 'trial_frozen_authority_changed')
            checkpoint = MODEL if lane == 'baseline' else freeze['checkpoint_path']
            task = {key: metadata[key] for key in ('task_id', 'package_sha256')}
            attempt = f'odoo20-{lane}-{ordinal:02d}-{digest(str(out.resolve()).encode())[:12]}'
            episode = out/attempt
            episode.mkdir(mode=0o700)
            write(episode, 'task-intent.private.json', {'task': task, 'lane': lane, 'attempt_id': attempt,
                'checkpoint_sha256': digest(checkpoint.encode()), 'selection_freeze_sha256': selection_freeze_sha,
                'actual_cost_usd': None, 'same_request_replay_authorized': False, 'formal_large_study_credit': 0})
            environment = legacy.environment_factory(selection, worker, identities, binding)
            environment._native_readiness_sink = lambda value: write(episode, 'db-readiness.private.json', value)
            metered = None
            try:
                # Only the evaluator sees hidden source/gold. Sampler receives
                # the unchanged native loop's visible instruction/current frame.
                environment.load_command_task(task, episode)
                case = environment._cases[task['task_id']][1]
                require(digest(case['prompt'].encode()) == metadata['visible_instruction_sha256'],
                        'trial_hidden_visible_instruction_changed')
                package_factory = importlib.import_module('partition_factory')
                require(Path(package_factory.__file__).resolve() == ROOT/'enterprise_fallback/odoo18/partition_factory.py',
                        'trial_original_package_factory_changed')
                factory = legacy._modules(worker, binding)[0]
                world = json.loads(private(factory.PRIVATE/'partition_cases.json'))
                asset = package_factory.source_asset(case, world)
                require(digest(asset) == metadata['source_asset_sha256'] and case.get('family') == metadata['family'],
                        'trial_hidden_source_asset_changed')
                config = {'model': MODEL, 'seed': sampling_seed, 'sample_max_tokens': sample_max_tokens}
                actual = sampler_class(selection)(checkpoint_path=checkpoint, config=config, output_root=episode,
                    attempt_id=attempt, base_mode=lane == 'baseline',
                    expected_base_checkpoint_sha256=digest(MODEL.encode()) if lane == 'baseline' else None)
                metered = TrialSampler(actual, episode, {'attempt_id': attempt})
                metered.parent_paid_attempt_id = attempt
                row = run_owned_task(environment=environment, task=task, index=0, sampler=metered,
                                     task_dir=episode, attempt_id=attempt)
                result = audit_saved_episode(episode, task, row, environment, selection, binding, worker, metered)
                write(episode, 'trial-task-result.private.json', {'schema': 'envloop-odoo20-final-development-result-v1',
                    'lane': lane, 'task': task, 'status': 'independently_saved_scored_reset_and_closed', **result})
                outcomes.append({'lane': lane, 'task': task, 'score': result['score'],
                                 'result': legacy.final.reference(out, episode/'trial-task-result.private.json')})
            except BaseException as error:
                write(episode, 'trial-task-failure.private.json', {'schema': 'envloop-odoo20-final-development-failure-v1',
                    'lane': lane, 'task': task, 'error_type': type(error).__name__, 'error_sha256': digest(str(error).encode()),
                    'runtime_cleanup': getattr(environment, 'runtime_receipt', None), 'paid_calls': [] if metered is None else metered.calls,
                    'actual_cost_usd': None, 'same_request_replay_authorized': False, 'formal_large_study_credit': 0})
                raise
    write(out, 'pair-result.private.json', {'schema': 'envloop-odoo20-final-development-pair-result-v1',
        'status': 'forty_native_outcomes_audited', 'trial_plan_sha256': plan_sha, 'selection_freeze_sha256': selection_freeze_sha,
        'tasks_per_lane': 20, 'outcomes': outcomes, 'formal_large_study_credit': 0, 'formal_final_tasks_admitted': 0})
    return {'status': 'forty_native_outcomes_audited', 'tasks_per_lane': 20, 'formal_large_study_credit': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'native-binding-path', 'native-binding-sha',
                  'selection-freeze-path', 'selection-freeze-sha', 'worker-dir', 'output-root',
                  'root-review-path', 'root-review-sha'):
        parser.add_argument('--'+field, required=True)
    parser.add_argument('--sampling-seed', type=int, default=0)
    parser.add_argument('--sample-max-tokens', type=int, default=4096)
    parser.add_argument('--execute', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__':
    main()
