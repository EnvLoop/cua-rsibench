"""Odoo20 V2 training: literal V13/V14 origins, with V14 target execution.

Only independently saved/reset public TRAIN teacher episodes enter SFT. The
explicit pre-result schedule amendment provides 384 slots for four bounded
90-action trajectories. V13 evidence is audited as V13 and never relabelled.
The immutable V1 implementation owns actual Tinker/no-retry/close operations.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import importlib
import json
from pathlib import Path
from types import FunctionType, SimpleNamespace

from . import twenty_task_trial_training_v1 as base
from . import twenty_task_trial_teacher_v1 as original_trial
from . import native_surface_workers_v13 as workers13
from . import native_surface_workers_v14 as workers14

ROOT = Path(__file__).resolve().parents[2]
MODEL = base.MODEL
SCHEMA = 'envloop-odoo20-trusted-training-input-v2'
ANCESTOR_PLAN_SHA = '126dfcdd9b270a489d0e7a34a64538a546738c81a04179bd089e454f6633436e'
ANCESTOR_NATIVE_BINDING_SHA = '56b3e77c254c5dd38d6bbaebf4661d3d71a7d053de44c942e055f0adf89842f4'
PREVIOUS_TRAINING_ASSET_SHA = '599287bd38a7d673e29031d2554862df47251fd7fe9ace9c8eb9a02b267feb20'
BASE_SOURCE_SHA = '7443544d93d7fb02bbecb44c33a6d301fded072b0e875233ffd42fa9c1ff86c5'
TrainingError, require, digest = base.TrainingError, base.require, base.digest
private_json, private_bytes, write = base.private_json, base.private_bytes, base.write
fixed_schedule = base.fixed_schedule


def scoped_origin_trial(origin):
    """Fresh function globals select origin workers without changing V1 globals."""
    namespace = SimpleNamespace(**vars(original_trial))
    namespace.workers = origin.workers
    for name in ('checked_trial', 'checked_proposal', 'verify_trial_episode',
                 'admissible_training_turns', 'render_trial_turns'):
        function = getattr(original_trial, name)
        scoped = FunctionType(function.__code__, {**function.__globals__, 'workers': origin.workers},
                              function.__name__, function.__defaults__, function.__closure__)
        scoped.__kwdefaults__ = function.__kwdefaults__
        setattr(namespace, name, scoped)
    return namespace


def checked_lineage(plan_path, plan_sha):
    """Bind one exact pre-result V13 ancestor and the current V14 authority."""
    require(digest(Path(base.__file__).read_bytes()) == BASE_SOURCE_SHA, 'immutable_v1_training_source_changed')
    plan_path = Path(plan_path)
    require(not plan_path.is_symlink() and plan_path.resolve().is_relative_to(ROOT/'work'),
            'owned_target_plan_required')
    plan_path = plan_path.resolve()
    plan = private_json(plan_path, plan_sha, root=ROOT/'work')
    target = SimpleNamespace(plan=plan, plan_path=plan_path, plan_sha256=plan_sha,
                             native_binding_sha256=plan['native_binding_sha256'],
                             native_epoch='v14', workers=workers14)
    require(plan.get('runtime_epoch') == 'v14', 'target_execution_v14_required')
    require(scoped_origin_trial(target).checked_trial(plan_path, plan_sha) == plan and
            plan.get('formal_large_study_credit') == 0 and plan.get('unknown_billing_is_null') is True and
            plan.get('sampling_uses_model_outcomes') is False and
            plan.get('original_verifier_and_reset_required') is True,
            'target_plan_authority_changed')
    refs = plan.get('teacher_data_plan_refs')
    require(type(refs) is list and len(refs) == 1, 'exact_declared_v13_ancestor_required')
    ref = refs[0]
    require(type(ref) is dict and set(ref) == {'path', 'sha256', 'native_binding_sha256', 'native_epoch'} and
            ref['sha256'] == ANCESTOR_PLAN_SHA and ref['native_epoch'] == 'v13' and
            ref['native_binding_sha256'] == ANCESTOR_NATIVE_BINDING_SHA,
            'unapproved_teacher_data_ancestor')
    path = Path(ref['path'])
    if not path.is_absolute():
        require('..' not in path.parts, 'ancestor_plan_path_escape')
        path = plan_path.parent/path
    ancestor = private_json(path, ref['sha256'], root=ROOT/'work')
    require(ancestor['native_binding_sha256'] == ref['native_binding_sha256'], 'ancestor_native_binding_mismatch')
    origin = SimpleNamespace(plan=ancestor, plan_path=path.resolve(), plan_sha256=ref['sha256'],
        native_binding_sha256=ref['native_binding_sha256'], native_epoch='v13', workers=workers13)
    require(scoped_origin_trial(origin).checked_trial(path, ref['sha256']) == ancestor,
            'ancestor_plan_authority_changed')
    same = ('schema', 'cell_id', 'study_type', 'models', 'sampling_seed', 'final_tasks_metadata',
            'family_counts', 'final_task_count', 'selection_task_count', 'train_task_count',
            'actor_limits', 'original_candidate_count', 'sampling_uses_model_outcomes',
            'original_verifier_and_reset_required', 'base_and_selected_checkpoint_same_final_tasks_required',
            'checkpoint_selection_before_final_outcomes_required', 'formal_large_study_credit',
            'full_six_environment_publication_claim', 'unknown_billing_is_null')
    require(all(plan.get(field) == ancestor.get(field) for field in same),
            'teacher_data_lineage_changes_frozen_task_or_model_contract')
    require(plan['models'] == {'student': MODEL, 'teacher': 'gpt-6-sol', 'initial_researcher': 'gpt-6-sol'} and
            plan['actor_limits']['actions'] == 90 and plan['actor_limits']['seconds'] == 720 and
            plan['original_candidate_count'] == 100,
            'lineage_model_or_actor_limits_changed')
    return plan, {plan_sha: target, origin.plan_sha256: origin}


def frozen_training(manifest, namespace, plan):
    """The new bound schedule, not the old 64-step/full-study configuration."""
    ref = plan['trial_training_ref']; path = Path(ref['path'])
    if not path.is_absolute():
        path = Path(namespace)/path
    require(path.parent.resolve() == Path(namespace).resolve() and
            manifest['training_asset_sha256'] == ref['sha256'], 'v2_training_asset_unbound')
    raw = private_bytes(path, ref['sha256'], root=namespace)
    training = json.loads(raw)
    require(training['schema'] == 'envloop-odoo20-qwen-sft-training-v1' and training['model'] == MODEL and
            training['action_profile'] == 'scale-action-profile-v0.6.6' and
            training['full_study_ratified_training_profile_claim'] is False and
            training['automatic_replay_after_uncertain_call'] is False and
            training['provider_invoice_required_for_cost_claim'] is True and
            training.get('pre_result_schedule_amendment') is True and
            training.get('previous_training_asset_sha256') == PREVIOUS_TRAINING_ASSET_SHA and
            type(training.get('coverage_policy')) is str and bool(training['coverage_policy']) and
            training['optimizer_steps'] == 192 and training['batch_size'] == 2 and
            training['max_scheduled_tokens'] == 12_582_912 and training['max_supervised_tokens'] == 32768,
            'explicit_pre_result_192_step_schedule_required')
    anchor_raw = (ROOT/'runtime/qwen38-vision/real-gui-diagnostic-prereg-v1.json').read_bytes()
    require(digest(anchor_raw) == training['hyperparameter_reference_sha256'], 'hyperparameter_anchor_changed')
    anchor = json.loads(anchor_raw)
    require(all(training[field] == anchor[field] for field in ('lora_rank', 'batch_size', 'learning_rate')) and
            training['seed'] == anchor['model_seed'] and training['sampling_temperature'] == 0 and
            training['sample_max_tokens'] == 512 and
            training['minimum_distinct_training_tasks'] == training['minimum_distinct_workflows'] == 4 and
            training['batch_size']*training['optimizer_steps'] >= 4*plan['actor_limits']['actions'],
            'v2_schedule_or_fixed_hyperparameters_changed')
    for field in ('optimizer_steps', 'batch_size', 'max_scheduled_tokens', 'max_supervised_tokens',
                  'lora_rank', 'seed', 'sample_max_tokens'):
        require(type(training[field]) is int, 'v2_training_integer_required')
    require(type(training['learning_rate']) is str and Decimal(training['learning_rate']).is_finite() and
            Decimal(training['learning_rate']) > 0, 'v2_learning_rate_invalid')
    return training, digest(raw)


def check_sources(manifest):
    needed = {'enterprise_fallback/odoo18/twenty_task_trial_teacher_v1.py',
              'enterprise_fallback/odoo18/twenty_task_trial_teacher_v2.py',
              'enterprise_fallback/odoo18/twenty_task_trial_training_v1.py',
              'enterprise_fallback/odoo18/twenty_task_trial_training_v2.py',
              'src/cursibench/full_study_teacher_adapter_v1.py',
              'src/cursibench/scale_vision_proxy.py', 'src/cursibench/scale_action_output_v066.py',
              'src/cursibench/full_study_campaign_dispatch_v1.py'}
    expected = manifest['source_sha256s']
    require(type(expected) is dict and set(expected) == needed, 'v2_training_sources_not_frozen')
    for relative, hashed in expected.items():
        require(digest((ROOT/relative).read_bytes()) == hashed, 'v2_training_source_changed')


def reopen_episode(directory, descriptor, manifest, plan, task, proposal, vision, *, origins):
    """V1's full native/provider/datum proof, executed with the literal origin."""
    sha = descriptor['origin_trial_plan_sha256']
    require(sha in origins, 'teacher_episode_origin_not_declared')
    origin = origins[sha]
    require(descriptor['origin_native_epoch'] == origin.native_epoch and
            descriptor['origin_native_binding_sha256'] == origin.native_binding_sha256 and
            origin.plan['native_binding_sha256'] == origin.native_binding_sha256,
            'teacher_episode_origin_epoch_or_binding_mismatch')
    directory = Path(directory)
    require(not directory.is_symlink() and directory.resolve().is_relative_to(origin.plan_path.parent),
            'teacher_episode_outside_declared_origin_namespace')
    outer = private_json(directory/'rendered-train-receipt.private.json',
                         descriptor['render_receipt_sha256'], root=directory)
    require(type(outer['teacher_turns']) is int and 0 < outer['teacher_turns'] <= origin.plan['actor_limits']['actions'],
            'teacher_episode_exceeds_declared_action_cap')
    effective = {**manifest, 'trial_plan_sha256': origin.plan_sha256}
    facade = scoped_origin_trial(origin)
    function = base.reopen_episode
    scoped = FunctionType(function.__code__, {**function.__globals__, 'trial': facade},
                          function.__name__, function.__defaults__, function.__closure__)
    scoped.__kwdefaults__ = function.__kwdefaults__
    batch = scoped(directory, descriptor, effective, origin.plan, task, proposal, vision)
    # Keep the actual renderer receipt byte-for-byte in its original epoch.
    return SimpleNamespace(datums=batch.datums, prompts=batch.prompts, receipt=batch.receipt,
        origin_metadata={'origin_trial_plan_sha256': origin.plan_sha256,
                         'origin_native_binding_sha256': origin.native_binding_sha256,
                         'origin_native_epoch': origin.native_epoch,
                         'target_execution_native_epoch': 'v14',
                         'task_id': task['task_id'], 'teacher_model': origin.plan['models']['teacher'],
                         'rendered_sha256': descriptor['rendered_sha256'],
                         'episode_receipt_sha256': descriptor['episode_receipt_sha256'],
                         'formal_large_study_credit': 0})


def load_inputs(*, plan_path, plan_sha, manifest_path, manifest_sha, trust_owned_rendered):
    require(trust_owned_rendered is True, 'explicit_owned_rendered_trust_required')
    plan, origins = checked_lineage(plan_path, plan_sha)
    namespace = Path(plan_path).resolve().parent
    require(Path(manifest_path).parent.resolve() == namespace, 'same_owned_trial_namespace_required')
    manifest = private_json(manifest_path, manifest_sha, root=namespace)
    require(manifest['schema'] == SCHEMA and manifest['trial_plan_sha256'] == plan_sha and
            manifest['formal_large_study_credit'] == 0 and manifest.get('target_execution_native_epoch') == 'v14',
            'explicit_v2_origin_training_authority_required')
    check_sources(manifest)
    training, training_sha = frozen_training(manifest, namespace, plan)
    worker = base.checked_train_worker(namespace, manifest['train_worker_ref'])
    task_set = private_json(worker/'private/task_set_manifest.json', manifest['train_worker_ref']['sha256'], root=worker)
    rows = task_set['train']; final_ids = {row['task_id'] for row in plan['final_tasks_metadata']}
    require(len(rows) == len({row['task_id'] for row in rows}) == 20 and
            not {row['task_id'] for row in rows} & final_ids and
            all('-HID-' not in row['task_id'] and '-RSV-' not in row['task_id'] for row in rows),
            'exact_twenty_public_train_ids_required')
    world = private_json(worker/'private/partition_cases.json', manifest['train_cases_sha256'], root=worker)
    cases = {case['id']:case for group in world['cases'].values() for case in group}
    require(set(cases) == {row['task_id'] for row in rows}, 'public_train_world_changed')
    proposal_path = base.reference(namespace, manifest['proposal_ref'])
    # Both allowed plans declare the same actual Sol6/public TRAIN contract.
    # The old checked raw researcher return may continue into the V14 episode.
    proposal = original_trial.checked_proposal(proposal_path, manifest['proposal_ref']['sha256'], 'gpt-6-sol')
    require(set(proposal) == {'hypothesis', 'train_task_ids', 'teacher_request'} and
            len(proposal['train_task_ids']) == len(set(proposal['train_task_ids'])) == 4 and
            set(proposal['train_task_ids']) <= set(cases), 'actual_four_public_train_proposal_required')
    descriptors = manifest['batches']
    require(type(descriptors) is list and len(descriptors) == len({row['task_id'] for row in descriptors}) == 4 and
            {row['task_id'] for row in descriptors} == set(proposal['train_task_ids']) and
            {cases[row['task_id']]['family'] for row in descriptors} == {'purchase', 'inventory', 'sales', 'crm'},
            'four_actual_public_training_workflows_required')
    vision = original_trial.teacher._load_renderer()
    datums, prompts, receipts, provenance = [], [], [], []
    for descriptor in descriptors:
        require(descriptor['origin_trial_plan_sha256'] in origins, 'teacher_episode_origin_not_declared')
        origin = origins[descriptor['origin_trial_plan_sha256']]
        relative = Path(descriptor['directory'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'teacher_directory_escape')
        directory = origin.plan_path.parent/relative
        task_id = descriptor['task_id']
        task = {'task_id':task_id, 'package_sha256':next(row['package_sha256'] for row in rows if row['task_id'] == task_id),
                'visible_instruction':cases[task_id]['prompt']}
        batch = reopen_episode(directory, descriptor, manifest, plan, task, proposal, vision, origins=origins)
        datums.extend(batch.datums); prompts.extend(batch.prompts); receipts.append(batch.receipt)
        provenance.append(batch.origin_metadata)
    require(any(row['origin_native_epoch'] == 'v14' for row in provenance), 'fresh_v14_teacher_origin_required')
    indices, scheduled = fixed_schedule(datums, training)
    identity = digest(json.dumps({'target_plan':plan_sha, 'training_asset':training_sha,
        'proposal':manifest['proposal_ref']['sha256'], 'origins':sorted(
            (row['task_id'],row['origin_trial_plan_sha256'],row['origin_native_binding_sha256'],
             row['episode_receipt_sha256'],row['rendered_sha256']) for row in provenance)},sort_keys=True).encode())
    return SimpleNamespace(plan=plan, manifest=manifest, training=training, training_sha=training_sha,
        namespace=namespace, datums=datums, prompts=prompts, receipts=receipts, indices=indices,
        scheduled_tokens=scheduled, identity=identity, origin_metadata=provenance,
        execution_native_epoch='v14', execution_native_binding_sha256=plan['native_binding_sha256'])


def train_real(inputs, out):
    require(inputs.execution_native_epoch == 'v14', 'target_execution_v14_required')
    write(Path(out)/'training-data-lineage.private.json', {
        'schema':'envloop-odoo20-native-origin-training-lineage-v2', 'dataset_identity':inputs.identity,
        'target_execution_native_epoch':'v14',
        'target_execution_native_binding_sha256':inputs.execution_native_binding_sha256,
        'teacher_episode_origins':inputs.origin_metadata, 'actual_cost_usd':None, 'formal_large_study_credit':0,
        'v13_data_relabelled_v14':False, 'v13_qualification_credit':0})
    # Actual SDK source pins, every intent/result/error, max_retries=0,
    # RetryConfig(False), pending-call retention and owned close are unchanged.
    return base.train_real(inputs, out)


def run(**kwargs):
    function = base.run
    scoped = FunctionType(function.__code__, {**function.__globals__, 'load_inputs':load_inputs, 'train_real':train_real},
                          function.__name__, function.__defaults__, function.__closure__)
    scoped.__kwdefaults__ = function.__kwdefaults__
    return {**scoped(**kwargs), 'training_entrypoint_schema':'envloop-odoo20-training-v2',
            'target_execution_native_epoch':'v14', 'v13_data_relabelled_v14':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path','plan-sha','manifest-path','manifest-sha','output-root'):
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--trust-owned-rendered',action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())),sort_keys=True))


if __name__=='__main__':
    main()
