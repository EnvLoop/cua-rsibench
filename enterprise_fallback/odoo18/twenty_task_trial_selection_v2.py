"""Source-pinned V14/Ref4 selection20, preserving actual V1 mechanisms."""
from pathlib import Path
from .native_compat_source_loader_v1 import load_source

_PARENT = 'enterprise_fallback/odoo18/twenty_task_trial_selection_v1.py'
_PARENT_SHA = '86437dc818e38e626b0754e0ec8d04153652b748a19358731068cc0492b943f9'
_impl = load_source(_PARENT, 'enterprise_fallback.odoo18._twenty_task_trial_selection_v2', _PARENT_SHA,
    (('twenty_task_trial_evaluator_v1', 'twenty_task_trial_evaluator_v2', 1),
     ('native_surface_workers_v13', 'native_surface_workers_v14', 1),
     ('native_reference_split_finalizer_v3', 'native_reference_split_finalizer_v4', 1),
     ('twenty_task_trial_selection_v1.py', 'twenty_task_trial_selection_v2.py', 1),
     ('envloop-odoo20-selection-checkpoint-freeze-v1', 'envloop-odoo20-selection-checkpoint-freeze-v2', 1),
     ('envloop-odoo20-selection-complete-v1', 'envloop-odoo20-selection-complete-v2', 2),
     *tuple(('envloop-odoo20-'+name+'-v1', 'envloop-odoo20-'+name+'-v2', 1) for name in
        ('selection-intent', 'selection-root-review', 'selection-source', 'selection-task-failure', 'selection-task-result'))))
_impl.__file__ = str(Path(__file__).resolve())
_source_binding = _impl.source_binding


def source_binding():
    value = _source_binding()
    value.pop('binding_sha256')
    value['source_sha256s'][_PARENT] = _impl.digest((_impl.ROOT/_PARENT).read_bytes())
    value['source_sha256s']['enterprise_fallback/odoo18/native_reference_split_finalizer_v4.py'] = \
        _impl.digest(Path(_impl.controls.__file__).read_bytes())
    return {**value, 'binding_sha256': _impl.digest(_impl.legacy.final.canonical(value))}


_impl.source_binding = source_binding


def __getattr__(name): return getattr(_impl, name)


if __name__ == '__main__': _impl.main()
