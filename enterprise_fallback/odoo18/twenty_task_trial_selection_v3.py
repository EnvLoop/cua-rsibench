"""V3 readback repair and explicit immutable first-case import; no replay."""
from pathlib import Path
from types import FunctionType
import inspect
from .native_compat_source_loader_v1 import load_source
from . import twenty_task_trial_readback_v3 as recovery
from . import twenty_task_trial_selection_v1 as historical

_PARENT = 'enterprise_fallback/odoo18/twenty_task_trial_selection_v2.py'
_PARENT_SHA = '2116aa24a4e71652ed13c77b45e0055f3012cba8f9847724c0e4299822e08e40'
_outer = load_source(_PARENT, 'enterprise_fallback.odoo18._trial_selection_v3_outer', _PARENT_SHA,
    (('_twenty_task_trial_selection_v2', '_twenty_task_trial_selection_v3', 1),
     ('twenty_task_trial_selection_v2.py', 'twenty_task_trial_selection_v3.py', 1),
     ('twenty_task_trial_evaluator_v2', 'twenty_task_trial_evaluator_v3', 1),
     ("+'-v2', 1)", "+'-v3', 1)", 1),
     ('envloop-odoo20-selection-checkpoint-freeze-v2', 'envloop-odoo20-selection-checkpoint-freeze-v3', 1),
     ('envloop-odoo20-selection-complete-v2', 'envloop-odoo20-selection-complete-v3', 1)))
_impl = _outer._impl
_outer.__file__ = _impl.__file__ = str(Path(__file__).resolve())
_base_source = _impl.source_binding


def source_binding():
    value = _base_source(); value.pop('binding_sha256')
    value['source_sha256s'][_PARENT] = _impl.digest((_impl.ROOT/_PARENT).read_bytes())
    value['source_sha256s']['enterprise_fallback/odoo18/twenty_task_trial_readback_v3.py'] = \
        _impl.digest(Path(recovery.__file__).read_bytes())
    value['readback_only_migration'] = True
    return {**value, 'binding_sha256': _impl.digest(_impl.legacy.final.canonical(value))}


_impl.source_binding = source_binding


def _import(path, expected, review_path, review_sha, identities, plan_sha, base_mode, checkpoint, seed, max_tokens):
    value = _impl.evaluator.read_ref({'path': str(Path(path).resolve()), 'sha256': expected})
    review = _impl.workers.private_json(review_path, review_sha)
    require = _impl.require
    native = _impl.workers.public_binding()
    require(review == {'schema': 'envloop-odoo20-saved-case-import-root-review-v3', 'trial_plan_sha256': plan_sha,
        'candidate_sha256': expected, 'native_binding_sha256': native['binding_sha256'],
        'same_actor_sampler_scorer_reset_verified': True, 'readback_reference_fix_only': True,
        'original_model_request_replay_authorized': False, 'original_first_case_import_authorized': True},
        'v3_explicit_saved_case_import_review_required')
    require(value['schema'] == 'envloop-odoo20-saved-selection-case-import-candidate-v3' and
        value['status'] == 'saved_original_first_case_independently_replayed' and value['trial_plan_sha256'] == plan_sha and
        value['native_binding_sha256'] == native['binding_sha256'] and value['task'] == identities[0] and
        base_mode is value['base_mode'] is True and checkpoint == value['model'] == _impl.MODEL and
        value['sampling_seed'] == seed and value['sample_max_tokens'] == max_tokens and
        value['new_model_calls'] == value['formal_large_study_credit'] == 0 and value['same_request_replay_authorized'] is False,
        'v3_same_original_first_case_model_metadata_budget_required')
    old_source = value['old_selection_source_binding']
    from . import twenty_task_trial_selection_v2 as original_selector
    require(old_source['native_binding_sha256'] == native['binding_sha256'] and
        old_source == original_selector.source_binding() and
        all(old_source['source_sha256s'].get(name) == sha for name, sha in native['source_sha256s'].items()),
        'v3_original_native_actor_scorer_reset_source_changed')
    original_intent = _impl.evaluator.read_ref(value['old_selection_intent_ref'])
    original_review = _impl.evaluator.read_ref(value['old_root_review_ref'])
    original_terminal = _impl.evaluator.read_ref(value['old_terminal_ref'])
    require(original_intent['trial_plan_sha256'] == plan_sha and original_intent['source_binding'] == old_source and
        original_review['sampling_seed'] == seed and original_review['sample_max_tokens'] == max_tokens and
        original_terminal['exit_code'] == 1 and original_terminal['automatic_restarts'] == 0,
        'v3_original_consumed_command_or_terminal_changed')
    required = {'saved-state.private.json', 'verifier.private.json', 'reset.private.json', 'baseline-semantic.private.json',
        'restored-semantic.private.json', 'actions.private.json', 'usage.private.json', 'frames.private.json',
        'sampling-journal/requests.sqlite3', 'paid-setup-result.private.json', 'actor-clock/end.private.json',
        'actor-clock/complete-lifecycle.private.json', 'actor-clock/provider-close.private.json'}
    require(required <= {row['mirror_relative_path'] for row in value['original_evidence_byte_mirror']},
        'v3_complete_original_evidence_byte_mirror_required')
    for artifact in value['original_evidence_byte_mirror']:
        require(_impl.digest(recovery.mirror_bytes(artifact['path'])) == artifact['sha256'] and
            _impl.digest(recovery.mirror_bytes(Path(value['entry']['episode_root'])/artifact['mirror_relative_path'])) == artifact['sha256'],
            'v3_original_or_mirrored_paid_evidence_changed')
    _, selector = _impl.workers._model_modules(native)
    # Reopen this single row with the production auditor, without manufacturing
    # a20-row packet. Full-coverage validation occurs only after remaining19.
    root = Path(value['entry']['episode_root'])
    row = recovery.read_ref(root, value['entry']['native_row'])
    selector._audit_task_artifacts(root, identities[0], row)
    require(row['score'] == value['score'], 'v3_imported_saved_score_changed')
    clock, life, close = (recovery.read_ref(root, row[key]) for key in
        ('actor_clock_ref', 'owned_complete_lifecycle_ref', 'provider_close_ref'))
    require(clock['native_actions_after_deadline'] == 0 and 0 <= clock['actor_elapsed_seconds'] <= 720 and
        life['saved_readback_reset_and_provider_close_complete'] is True and 0 <= life['ended_monotonic']-life['started_monotonic'] <= 1200 and
        close['status'] == 'acknowledged' and close['real_close_call_returned'] is True and
        life['actor_clock'] == row['actor_clock_ref'] and life['provider_close'] == row['provider_close_ref'],
        'v3_actual_original_lifecycle_typed_refs_unproved')
    return [value['entry']], [{'task': value['task'], 'score': value['score']}]


def run(*, saved_case_import_path=None, saved_case_import_sha=None, saved_case_review_path=None, saved_case_review_sha=None, **kwargs):
    require = _impl.require
    require((saved_case_import_path is None and saved_case_import_sha is None and saved_case_review_path is None and saved_case_review_sha is None) or
        all(value is not None for value in (saved_case_import_path, saved_case_import_sha, saved_case_review_path, saved_case_review_sha)),
        'v3_exact_optional_saved_case_import_references_required')
    source = inspect.getsource(historical.run)
    import re
    for schema in sorted(set(re.findall(r"['\"](envloop-odoo20-[a-z-]+-v1)['\"]", source))):
        source = source.replace(schema, schema[:-1]+'3')
    before = "'selection_twenty_authorized': True"
    require(source.count(before) == 1, 'v3_checked_root_review_interface_changed')
    source = source.replace(before, "'saved_prior_case_import_sha256': _import_sha, "+before)
    require(source.count('entries, scores = [], []') == 1, 'v3_checked_selection_accumulator_changed')
    source = source.replace('entries, scores = [], []', 'entries, scores = _prior(identities, plan_sha, base_mode, checkpoint_path, sampling_seed, sample_max_tokens)')
    before = 'for ordinal, task in enumerate(identities):'
    require(source.count(before) == 1, 'v3_checked_selection_loop_changed')
    source = source.replace(before, before+'\n        if ordinal < _import_count: continue')
    def prior(*args):
        if saved_case_import_path is None: return [], []
        return _import(saved_case_import_path, saved_case_import_sha, saved_case_review_path, saved_case_review_sha, *args)
    namespace = {**_impl.__dict__, '_prior': prior, '_import_sha': saved_case_import_sha,
                 '_import_count': 0 if saved_case_import_path is None else 1}
    exec(compile(source, 'checked-native14-selection-v3-readback-and-saved-import', 'exec'), namespace)
    return namespace['run'](**kwargs)


def __getattr__(name):
    try: return getattr(_outer, name)
    except AttributeError: return getattr(_impl, name)


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'native-binding-path', 'native-binding-sha', 'train-control-path',
        'train-control-sha', 'selection-control-path', 'selection-control-sha', 'local-cost-authority-path',
        'local-cost-authority-sha', 'worker-dir', 'checkpoint-path', 'output-root', 'root-review-path', 'root-review-sha'):
        parser.add_argument('--'+field, required=True)
    for field in ('saved-case-import-path', 'saved-case-import-sha', 'saved-case-review-path', 'saved-case-review-sha'):
        parser.add_argument('--'+field)
    parser.add_argument('--sampling-seed', type=int, default=0); parser.add_argument('--sample-max-tokens', type=int, default=4096)
    parser.add_argument('--base-mode', action='store_true'); parser.add_argument('--execute', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__': main()
