"""Reference5 native save repair; original Native14 actors remain immutable."""
from .native_compat_source_loader_v1 import load_source
from .native_reference_save_v5 import POLICY

_impl=load_source('enterprise_fallback/odoo18/native_reference_viewport_v3.py',
    'enterprise_fallback.odoo18._native_reference_viewport_v5',
    'f3f1ecd1096af2ca1005beefc0132c0fefe8402ffdb1c8d1095864ffe69cd755',(
        ('native_surface_workers_v13','native_surface_workers_v14',1),
        ('odoo-native-viewport-reference-source-v3','odoo-native-viewport-reference-source-v5',1),
        ('same_v13_adapter_actor_scorer_reset','same_v14_adapter_actor_scorer_reset',1),
        ('viewport-reference-v3','viewport-reference-v5',1),('viewport-case-v3','viewport-case-v5',1),
        ('from tools import odoo_v066_scale_recipes_v5 as recipes','from tools import odoo_v066_scale_recipes_v6 as recipes',1)))
_impl.REFERENCE_FILES=tuple(dict.fromkeys((*_impl.REFERENCE_FILES,
    'enterprise_fallback/odoo18/native_reference_viewport_v4.py',
    'enterprise_fallback/odoo18/native_compat_source_loader_v1.py',
    'enterprise_fallback/odoo18/native_reference_facet_v2.py',
    'tools/odoo_v066_native_reference_qualification_v4.py',
    'enterprise_fallback/odoo18/native_reference_save_v5.py',
    'enterprise_fallback/odoo18/native_reference_viewport_v5.py',
    'tools/odoo_v066_scale_recipes_v6.py','tools/odoo_v066_native_reference_qualification_v5.py',
    'enterprise_fallback/odoo18/native_reference_split_finalizer_v5.py',
    'tests/test_odoo_native_reference_save_v5.py','tests/test_odoo_native_reference_epoch_v5.py')))
_base_binding=_impl.reference_binding

def reference_binding():
    value=_base_binding();value.pop('reference_binding_sha256')
    value.update(native_save_policy=POLICY,manual_native_save_click_required=True,
        prior_reference4_control_credit=0,fresh_reference5_train_and_full_splits_required=True)
    return {**value,'reference_binding_sha256':_impl.core.digest(_impl.core.canonical(value))}

_impl.reference_binding=reference_binding
def __getattr__(name):return getattr(_impl,name)
