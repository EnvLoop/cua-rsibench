"""Additive V3 typed-reference readback; V14 actor/scorer/budget unchanged."""
from pathlib import Path
from .native_compat_source_loader_v1 import load_source
from .twenty_task_trial_readback_v3 import read_ref as read_relative_typed_ref

_PARENT = 'enterprise_fallback/odoo18/twenty_task_trial_evaluator_v2.py'
_PARENT_SHA = '3f88b18e9d79bdf7debf0eba0bdec71d56c1c0f9c34b8a0d75fdc62507077c46'
_outer = load_source(_PARENT, 'enterprise_fallback.odoo18._trial_evaluator_v3_outer', _PARENT_SHA,
    (('_twenty_task_trial_evaluator_v2', '_twenty_task_trial_evaluator_v3', 1),
     ('twenty_task_trial_evaluator_v2.py', 'twenty_task_trial_evaluator_v3.py', 1),
     ("+'-v2', 1)", "+'-v3', 1)", 1)))
_outer.__file__ = str(Path(__file__).resolve())
_impl = _outer._impl
_impl.__file__ = str(Path(__file__).resolve())
_impl._ref = read_relative_typed_ref
_impl.FILES = tuple(dict.fromkeys((*_impl.FILES, _PARENT,
    'enterprise_fallback/odoo18/twenty_task_trial_readback_v3.py')))


def __getattr__(name):
    try: return getattr(_outer, name)
    except AttributeError: return getattr(_impl, name)


if __name__ == '__main__': _outer.main()
