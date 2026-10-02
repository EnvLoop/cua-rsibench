"""Native14 Sol6 teacher endpoint; original V13 collector stays unchanged."""
from .native_compat_source_loader_v1 import load_source
_impl = load_source(
    'enterprise_fallback/odoo18/twenty_task_trial_teacher_v1.py',
    'enterprise_fallback.odoo18._twenty_task_trial_teacher_v2',
    '8f65162fecd11dc66678d1e469d0a8cc7845d39bbf729a88844ec6bd687164a5',
    (('native_surface_workers_v13', 'native_surface_workers_v14', 1),))
_impl.TEACHER_SYSTEM_PROMPT += (
    '\nThis native browser runs on macOS. For select-all inside a focused editor, '
    'use Meta+A (Command+A). Control+A moves the caret to the beginning and does '
    'not select the existing text here. After activating a real editor, replace '
    'its value with Meta+A followed by a separate targetless insert action, or '
    'use fill on an actual editable textbox ref. Verify the displayed value '
    'matches the source exactly; do not append another copy of a reference. '
    'For this teacher collection, never emit a fill action. Edit using an '
    'observed click to activate the field, a fresh Meta+A action, then a '
    'separate targetless insert action. Table-cell refs are not editable '
    'textbox refs even when they display a number. Observe between each step.')
def __getattr__(name): return getattr(_impl, name)
if __name__ == '__main__': _impl.main()
