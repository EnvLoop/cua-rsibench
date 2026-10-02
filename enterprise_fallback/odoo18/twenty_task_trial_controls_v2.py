"""Fresh frozen20 controls under unchanged V14 source and Ref4 recipes.

This checked wrapper preserves V1 evidence and grants zero full-study credit.
"""
from pathlib import Path
from .native_compat_source_loader_v1 import load_source

_PARENT = 'enterprise_fallback/odoo18/twenty_task_trial_controls_v1.py'
_PARENT_SHA = '8424f358add0dc7bea2dd61a79ec96e25838563f72d0d1a91b8de92e35c57ddb'
_impl = load_source(_PARENT, 'enterprise_fallback.odoo18._twenty_task_trial_controls_v2', _PARENT_SHA,
    (('twenty_task_trial_evaluator_v1', 'twenty_task_trial_evaluator_v2', 2),
     ('native_surface_workers_v13', 'native_surface_workers_v14', 1),
     ('native_reference_viewport_v3', 'native_reference_viewport_v4', 1),
     ('native_reference_split_finalizer_v3', 'native_reference_split_finalizer_v4', 2),
     ('native_reference_qualification_v3', 'native_reference_qualification_v4', 1),
     ('_v3_action_provenance', '_v4_action_provenance', 1),
     ('native-v13-', 'native-v14-', 2),
     ('v066_twenty_task_controls_v1', 'v066_twenty_task_controls_v2', 2),
     ('twenty_task_trial_controls_v1.py', 'twenty_task_trial_controls_v2.py', 1),
     ('envloop-odoo20-native-controls-result-v1', 'envloop-odoo20-native-controls-result-v2', 2),
     *tuple(('envloop-odoo20-'+name+'-v1', 'envloop-odoo20-'+name+'-v2', 1) for name in
        ('native-control-plan', 'native-control-source', 'native-controls-audit', 'native-controls-failure',
         'native-controls-intent', 'native-controls-root-review', 'native-controls-source-review'))))
_impl.__file__ = str(Path(__file__).resolve())
_source_binding = _impl.source_binding


def source_binding():
    value = _source_binding()
    value.pop('binding_sha256')
    value['source_sha256s'][_PARENT] = _impl.digest((_impl.evaluator.ROOT/_PARENT).read_bytes())
    return {**value, 'binding_sha256': _impl.digest(_impl.workers.canonical(value))}


_impl.source_binding = source_binding


def __getattr__(name): return getattr(_impl, name)


if __name__ == '__main__': _impl.main()
