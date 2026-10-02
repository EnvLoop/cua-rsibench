"""Additive selection orchestration: prefix import and one reviewed replacement.

Native14 actor/sampler/scorer/reset and evaluatorV3 stay unchanged. V3 result
and freeze formats remain compatible, with explicit V4 orchestration source
and original V3 row provenance retained. No failed sample is replayed.
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import re
from types import FunctionType

from . import twenty_task_trial_selection_v3 as original
from . import twenty_task_trial_selection_v1 as historical
from . import twenty_task_trial_prefix_recovery_v4 as recovery

_impl = original._impl
require, digest, private, write = _impl.require, _impl.digest, _impl.private, _impl.write


def source_binding():
    parent = original.source_binding()
    value = {**parent}; value.pop('binding_sha256')
    value['schema'] = 'envloop-odoo20-selection-source-v4'
    value['original_selection_source_binding'] = parent
    value['prefix_recovery_source_binding'] = recovery.source_binding()
    value['source_sha256s'] = {**parent['source_sha256s'],
        'enterprise_fallback/odoo18/twenty_task_trial_selection_v4.py': digest(Path(__file__).read_bytes()),
        'enterprise_fallback/odoo18/twenty_task_trial_prefix_recovery_v4.py': digest(Path(recovery.__file__).read_bytes())}
    value.update(orchestration_only_amendment=True, actor_sampler_scorer_reset_changed=False,
        imported_rows_retain_original_source=True, infrastructure_faults_are_not_model_scores=True)
    return {**value, 'binding_sha256': digest(_impl.legacy.final.canonical(value))}


def _authority(path, expected, identities, plan_sha, checkpoint, seed, tokens):
    value = _impl.evaluator.read_ref(recovery.absolute_ref(path, expected))
    candidate_ref = value['candidate_ref']
    candidate = recovery.checked_candidate(candidate_ref['path'], candidate_ref['sha256'])
    review = _impl.evaluator.read_ref(value['root_review_ref'])
    require(review == recovery.continuation_review(candidate_ref), 'v4_continuation_root_review_changed')
    require(value['schema'] == 'envloop-odoo20-selection-continuation-authority-v4' and
        value['source_binding'] == recovery.source_binding() and value['trial_plan_sha256'] == plan_sha and
        candidate['identities'] == identities and candidate['trial_plan_sha256'] == plan_sha and
        value['model'] == checkpoint == _impl.MODEL and value['base_mode'] is True and
        value['sampling_seed'] == seed == 0 and value['sample_max_tokens'] == tokens == 4096 and
        value['import_ordinals'] == [0, 1, 2] and value['fresh_dispatch_ordinals'] == list(range(3, 20)) and
        value['dispatch_count'] == 17 and value['original_request_replay_authorized'] is False and
        value['automatic_retry_authorized'] is False and value['formal_large_study_credit'] == 0 and
        value['actor_sampler_scorer_reset_changed'] is False and value['per_task_limits'] == recovery.LIMITS and
        value['replacement'] == {'ordinal': 3, 'task': identities[3], 'max_fresh_whole_task_attempts': 1,
            'superseded_attempt_id': candidate['infrastructure_exclusion']['original_attempt_id'],
            'original_attempt_resumed': False, 'forbidden_request_ids':
            candidate['infrastructure_exclusion']['completed_request_ids'] +
            candidate['infrastructure_exclusion']['uncertain_request_ids']}, 'v4_exact_continuation_authority_required')
    recovery.checked_access(value['provider_access_ref'], candidate)
    return value, candidate


def orchestration_source():
    """Build the checked orchestration patch without loading a model or UI."""
    source = inspect.getsource(historical.run)
    for schema in sorted(set(re.findall(r"['\"](envloop-odoo20-[a-z-]+-v1)['\"]", source))):
        source = source.replace(schema, schema[:-1]+'3')
    substitutions = (
        ("'selection_twenty_authorized': True", "'continuation_authority_sha256': _authority_sha, 'selection_twenty_authorized': True"),
        ('entries, scores = [], []', 'entries, scores = _prior(identities, plan_sha, checkpoint_path, sampling_seed, sample_max_tokens)'),
        ('for ordinal, task in enumerate(identities):', 'for ordinal, task in enumerate(identities):\n        if ordinal < _import_count: continue'),
        ("'actual_cost_usd': None})\n    entries", "'actual_cost_usd': None, 'orchestration_epoch': 'v4', 'continuation_authority_sha256': _authority_sha})\n    entries"),
        ("'hidden_final_outcomes_used': False}", "'hidden_final_outcomes_used': False, 'orchestration_epoch': 'v4',\n        'continuation_authority_ref': _authority_ref, 'imported_row_source_binding': _imported_source,\n        'infrastructure_exclusion': _exclusion}"),
    )
    for before, after in substitutions:
        require(source.count(before) == 1, 'v4_checked_orchestration_interface_changed')
        source = source.replace(before, after)
    return source


def run(*, continuation_authority_path=None, continuation_authority_sha=None, **kwargs):
    require(kwargs.get('execute') is True, 'v4_explicit_selection_dispatch_required')
    base_mode = kwargs.get('base_mode', False)
    require((base_mode and continuation_authority_path is not None and continuation_authority_sha is not None) or
        (base_mode is False and continuation_authority_path is continuation_authority_sha is None),
        'v4_base_requires_reviewed_prefix_authority_checkpoint_requires_fresh_twenty')
    source = orchestration_source()
    forbidden = set()
    def prior(identities, plan_sha, checkpoint, seed, tokens):
        if not base_mode:
            return [], []
        authority, candidate = _authority(continuation_authority_path, continuation_authority_sha,
            identities, plan_sha, checkpoint, seed, tokens)
        # One-use claim prevents uncertain repeat launch under another output.
        owner = Path(continuation_authority_path).parent
        write(owner, f'continuation-{continuation_authority_sha}-consumed.private.json',
            {'schema': 'envloop-odoo20-continuation-consumed-v4', 'authority_sha256': continuation_authority_sha,
             'output_root': str(Path(kwargs['output_root']).resolve()), 'same_request_replay_authorized': False,
             'automatic_restarts': 0, 'actual_cost_usd': None})
        forbidden.update(authority['replacement']['forbidden_request_ids'])
        namespace['_imported_source'] = candidate['source_binding']['original_selection_source_binding']
        namespace['_exclusion'] = candidate['infrastructure_exclusion']
        return candidate['selection_tasks'], candidate['scores']
    original_owned_task = _impl.run_owned_task
    def guarded_owned_task(**task_kwargs):
        attempt = task_kwargs['attempt_id']
        prospective = {'odoo-sel-'+digest(attempt.encode())[:10]+f'-00-{step:03d}' for step in range(90)}
        require(not prospective & forbidden, 'v4_original_provider_request_ids_must_never_be_reused')
        if base_mode:
            recovery.absolute_ref(continuation_authority_path, continuation_authority_sha)
        return original_owned_task(**task_kwargs)
    namespace = {**_impl.__dict__, 'source_binding': source_binding, '_prior': prior,
        'run_owned_task': guarded_owned_task,
        '_import_count': 3 if base_mode else 0, '_authority_sha': continuation_authority_sha,
        '_authority_ref': None if not base_mode else recovery.absolute_ref(continuation_authority_path, continuation_authority_sha),
        '_imported_source': None, '_exclusion': None}
    exec(compile(source, 'checked-native14-selection-v4-prefix-orchestration-only', 'exec'), namespace)
    return namespace['run'](**kwargs)


def freeze_checkpoint(**kwargs):
    """Reuse the exact V3 no-regression gate with this facade's source binding."""
    baseline = _impl.evaluator.read_ref(kwargs['baseline_result_ref'])
    selected = _impl.evaluator.read_ref(kwargs['selected_result_ref'])
    require(baseline.get('orchestration_epoch') == selected.get('orchestration_epoch') == 'v4' and
        selected.get('continuation_authority_ref') is selected.get('infrastructure_exclusion') is None and
        selected.get('imported_row_source_binding') is None, 'v4_actual_continuation_and_fresh_checkpoint_lanes_required')
    authority_ref = baseline['continuation_authority_ref']
    authority, candidate = _authority(authority_ref['path'], authority_ref['sha256'],
        [row['task'] for row in baseline['selection_tasks']], kwargs['plan_sha'], _impl.MODEL, 0, 4096)
    require(baseline['infrastructure_exclusion'] == candidate['infrastructure_exclusion'] and
        baseline['imported_row_source_binding'] == candidate['source_binding']['original_selection_source_binding'] and
        baseline['selection_tasks'][:3] == candidate['selection_tasks'] and baseline['scores'][:3] == candidate['scores'],
        'v4_original_imported_row_and_exclusion_lineage_changed')
    method = original.freeze_checkpoint
    scoped = FunctionType(method.__code__, {**method.__globals__, 'source_binding': source_binding},
        method.__name__, method.__defaults__, method.__closure__)
    scoped.__kwdefaults__ = method.__kwdefaults__
    return scoped(**kwargs)


def __getattr__(name):
    return getattr(original, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'native-binding-path', 'native-binding-sha', 'train-control-path',
        'train-control-sha', 'selection-control-path', 'selection-control-sha', 'local-cost-authority-path',
        'local-cost-authority-sha', 'worker-dir', 'checkpoint-path', 'output-root', 'root-review-path', 'root-review-sha'):
        parser.add_argument('--'+field, required=True)
    for field in ('continuation-authority-path', 'continuation-authority-sha'):
        parser.add_argument('--'+field)
    parser.add_argument('--sampling-seed', type=int, default=0)
    parser.add_argument('--sample-max-tokens', type=int, default=4096)
    parser.add_argument('--base-mode', action='store_true'); parser.add_argument('--execute', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__':
    main()
