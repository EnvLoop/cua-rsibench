"""V14 final20 evaluator: current source, selected checkpoint and all20 controls.

V1 remains immutable. Before any paid/native final dispatch this wrapper
replays all20 genuine controls and their independent source QA. Pilot control
qualification never grants full100/six-cell study admission.
"""
from pathlib import Path
from types import FunctionType
from .native_compat_source_loader_v1 import load_source

_PARENT = 'enterprise_fallback/odoo18/twenty_task_trial_evaluator_v1.py'
_PARENT_SHA = 'e8b4b1d06ecb2dd44c585c0817a6156bde9add80222b1c419dff53a9315fc44f'
_SCHEMAS = ('evaluator-source', 'final-development-failure', 'final-development-intent',
    'final-development-pair-result', 'final-development-result', 'final-development-root-review',
    'paid-setup-intent', 'paid-setup-result', 'selection-checkpoint-freeze')
_impl = load_source(_PARENT, 'enterprise_fallback.odoo18._twenty_task_trial_evaluator_v2', _PARENT_SHA,
    (('native_surface_workers_v13', 'native_surface_workers_v14', 1),
     ('native_reference_viewport_v3', 'native_reference_viewport_v4', 1),
     ('odoo-native-reference-qualification-plan-v3', 'odoo-native-reference-qualification-plan-v4', 1),
     ('twenty_task_trial_evaluator_v1.py', 'twenty_task_trial_evaluator_v2.py', 1),
     ("'native_final_controls_status': 'pending_genuine_controls'",
      "'native_final_controls_status': 'all_twenty_controls_and_source_qa_verified', 'final_controls_descriptor_sha256': _current_controls_sha()", 1),
     *tuple(('envloop-odoo20-'+name+'-v1', 'envloop-odoo20-'+name+'-v2', 1) for name in _SCHEMAS)))
_impl.__file__ = str(Path(__file__).resolve())
_impl.FILES = tuple(dict.fromkeys((*_impl.FILES, _PARENT,
    'enterprise_fallback/odoo18/twenty_task_trial_controls_v2.py',
    'enterprise_fallback/odoo18/twenty_task_trial_controls_v1.py',
    'enterprise_fallback/odoo18/native_reference_split_finalizer_v4.py')))

_checked_trial = _impl.checked_trial


def checked_trial(plan_path, plan_sha):
    plan, candidates = _checked_trial(plan_path, plan_sha)
    _impl.require(plan['models'] == {'initial_researcher': 'gpt-6-sol', 'teacher': 'gpt-6-sol',
                                   'student': 'Qwen/Qwen3.8-27B'}, 'v14_exact_sol6_qwen38_epoch_required')
    return plan, candidates


_impl.checked_trial = checked_trial


def checked_final_controls(descriptor_ref, *, plan_path, plan_sha, worker_dir):
    """Reopen the original controls; a typed 'verified' summary cannot qualify."""
    from . import twenty_task_trial_controls_v2 as controls
    plan, _ = checked_trial(plan_path, plan_sha)
    descriptor = _impl.read_ref(descriptor_ref)
    fields = {'schema', 'trial_plan_sha256', 'control_plan_ref', 'control_audit_ref',
              'source_review_ref', 'worker_dir', 'run_dir', 'formal_large_study_credit'}
    _impl.require(type(descriptor) is dict and set(descriptor) == fields and
        descriptor['schema'] == 'envloop-odoo20-final-controls-descriptor-v2' and
        descriptor['trial_plan_sha256'] == plan_sha and descriptor['formal_large_study_credit'] == 0 and
        Path(descriptor['worker_dir']).resolve() == Path(worker_dir).resolve(), 'v14_exact_final_control_descriptor_required')
    control_plan = _impl.read_ref(descriptor['control_plan_ref'])
    recorded = _impl.read_ref(descriptor['control_audit_ref'])
    _impl.read_ref(descriptor['source_review_ref'])
    _impl.require(control_plan['trial_plan_ref'] == {'path': str(Path(plan_path).resolve()), 'sha256': plan_sha} and
        control_plan['frozen_twenty_metadata'] == plan['final_tasks_metadata'], 'v14_control_trial_epoch_or_roster_changed')
    controls.validate_plan(control_plan)
    derived = controls.audit(plan_path=descriptor['control_plan_ref']['path'], plan_sha=descriptor['control_plan_ref']['sha256'],
        worker_dir=descriptor['worker_dir'], run_dir=descriptor['run_dir'],
        source_review_path=descriptor['source_review_ref']['path'], source_review_sha=descriptor['source_review_ref']['sha256'])
    _impl.require(recorded == derived and derived['status'] == controls.VERIFIED and
        derived['trial_plan_sha256'] == plan_sha and derived['native_binding_sha256'] == plan['native_binding_sha256'] and
        derived['reference_binding_sha256'] == plan['reference_binding_sha256'] and
        derived['control_count'] == 20 and derived['original_world_count'] == 100 and
        derived['source_visual_review_pending'] is False and len(derived['rows']) == 20 and
        all(derived[key] == 0 for key in ('model_calls', 'formal_large_study_credit', 'official_final_tasks_admitted')) and
        [(row['task_id'], row['package_sha256'], row['family']) for row in derived['rows']] ==
        [(row['task_id'], row['package_sha256'], row['family']) for row in plan['final_tasks_metadata']] and
        all(row['independent_scores'] == [0, 1, 0] and row['source_visual_review_verified'] is True for row in derived['rows']),
        'v14_all_twenty_actual_controls_and_independent_source_qa_required')
    return descriptor


def run(*, final_controls_descriptor_path, final_controls_descriptor_sha, **kwargs):
    _impl.require(kwargs.get('execute') is True, 'v14_explicit_final_pair_dispatch_required')
    descriptor_ref = {'path': str(Path(final_controls_descriptor_path).resolve()), 'sha256': final_controls_descriptor_sha}
    descriptor = checked_final_controls(descriptor_ref, plan_path=kwargs['plan_path'], plan_sha=kwargs['plan_sha'],
                                        worker_dir=kwargs['worker_dir'])
    def guarded_trial(path, expected):
        # The full replay above occurs once before any final paid/native work;
        # immutable descriptor/plan/audit/review bytes are checked every task.
        _impl.read_ref(descriptor_ref)
        for field in ('control_plan_ref', 'control_audit_ref', 'source_review_ref'): _impl.read_ref(descriptor[field])
        return checked_trial(path, expected)
    original = _impl.run
    method = FunctionType(original.__code__, {**original.__globals__, 'checked_trial': guarded_trial,
        '_current_controls_sha': lambda: final_controls_descriptor_sha}, original.__name__, original.__defaults__, original.__closure__)
    method.__kwdefaults__ = original.__kwdefaults__
    return method(**kwargs)


def __getattr__(name): return getattr(_impl, name)


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path', 'plan-sha', 'native-binding-path', 'native-binding-sha', 'selection-freeze-path',
        'selection-freeze-sha', 'worker-dir', 'output-root', 'root-review-path', 'root-review-sha',
        'final-controls-descriptor-path', 'final-controls-descriptor-sha'):
        parser.add_argument('--'+field, required=True)
    parser.add_argument('--sampling-seed', type=int, default=0)
    parser.add_argument('--sample-max-tokens', type=int, default=4096)
    parser.add_argument('--execute', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), sort_keys=True))


if __name__ == '__main__': main()
