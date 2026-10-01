"""Fresh V14 workers: one expiry-capped native adapter for every execution role.

V13 worker source is checked and compiled into an independent namespace. Only
its epoch, adapter references and fresh qualification identifiers change. The
same original evaluator, geometry, verifier, reset and 20/20/100 world remain.
"""
from .native_compat_source_loader_v1 import load_source

_PARENT = 'enterprise_fallback/odoo18/native_surface_workers_v13.py'
_PARENT_SHA = '5e6163ff320ef1760ec7753408f2ad0d31f99682120cb61c3e5d1d16e30a926e'
_impl = load_source(_PARENT, 'enterprise_fallback.odoo18._native_surface_workers_v14_parent', _PARENT_SHA, (
    ('_native_surface_workers_v13_wrapper', '_native_surface_workers_v14_wrapper', 1),
    ("(('v6','v13',9),)", "(('v6','v14',9),('odoo_native_surface_evidence_v14.py','odoo_native_surface_evidence_v13.py',1))", 1),
    ("'native':'v13'", "'native':'v14'", 1),
    ('envloop-odoo-native-control-rejection-v13', 'envloop-odoo-native-control-rejection-v14', 1),
))
_impl._impl._impl.SOURCE_FILES = tuple(dict.fromkeys(_impl._impl._impl.SOURCE_FILES + (
    _PARENT,
    'enterprise_fallback/odoo18/native_surface_workers_v14.py',
    'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v13.py',
    'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v14.py',
    'enterprise_fallback/odoo18/odoo_native_surface_evidence_v13.py',
    'tools/odoo_v066_native_surface_qualification_v14.py',
    'enterprise_fallback/odoo18/native_reference_viewport_v3.py',
    'enterprise_fallback/odoo18/native_reference_viewport_v4.py',
    'tools/odoo_v066_scale_recipes_v5.py',
    'tools/odoo_v066_native_reference_qualification_v3.py',
    'tools/odoo_v066_native_reference_qualification_v4.py',
    'enterprise_fallback/odoo18/native_reference_split_finalizer_v3.py',
)))
_base_public_binding = _impl.public_binding


def public_binding():
    value = dict(_base_public_binding())
    value.pop('binding_sha256')
    value['source_epoch'] = {**value['source_epoch'], 'native':'v14',
        'historical_control_credit':0, 'v13_positive_control_credit':0,
        'uniform_expiry_boundary':'odoo-uniform-frame-expiry-v14',
        'viewport_reference_wrapper':'enterprise_fallback.odoo18.native_reference_viewport_v4',
        'fresh_viewport_reference_epoch':'v4', 'old_viewport_reference_control_credit':0,
        'fresh_train_full20_full100_required':True}
    return {**value, 'binding_sha256':_impl.digest(_impl.canonical(value))}


_impl.public_binding = public_binding
_impl._impl.public_binding = public_binding
_impl._impl._impl.public_binding = public_binding


def __getattr__(name):
    return getattr(_impl, name)
