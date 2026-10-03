"""Reference8 priority autosave; unchanged Native14 and Reference7 save."""
from .native_compat_source_loader_v1 import load_source
from . import native_reference_viewport_v7 as prior
from .native_reference_save_v7 import POLICY as SAVE_POLICY
from .native_reference_autosave_v8 import POLICY as AUTOSAVE_POLICY

_impl=load_source('enterprise_fallback/odoo18/native_reference_viewport_v3.py',
    'enterprise_fallback.odoo18._native_reference_viewport_v8',
    'f3f1ecd1096af2ca1005beefc0132c0fefe8402ffdb1c8d1095864ffe69cd755',(
        ('native_surface_workers_v13','native_surface_workers_v14',1),
        ('odoo-native-viewport-reference-source-v3','odoo-native-viewport-reference-source-v8',1),
        ('same_v13_adapter_actor_scorer_reset','same_v14_adapter_actor_scorer_reset',1),
        ('viewport-reference-v3','viewport-reference-v8',1),('viewport-case-v3','viewport-case-v8',1),
        ('from tools import odoo_v066_scale_recipes_v5 as recipes','from tools import odoo_v066_scale_recipes_v9 as recipes',1)))
_impl.REFERENCE_FILES=tuple(dict.fromkeys((*prior._impl.REFERENCE_FILES,
    'enterprise_fallback/odoo18/native_reference_autosave_v8.py',
    'enterprise_fallback/odoo18/native_reference_viewport_v8.py',
    'enterprise_fallback/odoo18/native_reference_split_finalizer_v8.py',
    'tools/odoo_v066_scale_recipes_v9.py','tools/odoo_v066_native_reference_qualification_v8.py',
    'tests/test_odoo_native_reference_autosave_v8.py','tests/test_odoo_native_reference_epoch_v8.py')))
_base_binding=_impl.reference_binding

def reference_binding():
    value=_base_binding();value.pop('reference_binding_sha256')
    value.update(native_save_policy=SAVE_POLICY,priority_autosave_wait_policy=AUTOSAVE_POLICY,
        unchanged_reference7_save_helper_used=True,dirty_native_save_click_required=True,
        prior_reference4_control_credit=0,prior_reference5_control_credit=0,
        prior_reference6_control_credit=0,prior_reference7_control_credit=0,
        fresh_reference8_train_and_full_splits_required=True)
    return {**value,'reference_binding_sha256':_impl.core.digest(_impl.core.canonical(value))}

_impl.reference_binding=reference_binding
def __getattr__(name):return getattr(_impl,name)
