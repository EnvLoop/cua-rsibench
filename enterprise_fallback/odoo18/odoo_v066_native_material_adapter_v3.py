"""Small isolated compatibility layer over the exact preserved v2 adapter."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from .native_compat_source_loader_v1 import load_source, assert_frozen_v2_sources

_impl = load_source('enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py',
    'enterprise_fallback.odoo18._native_material_adapter_v3',
    'df736235bdc584677a6762d9c65134d3a4177372bf4c35cada30cdf306fda3c3', (
        ('odoo_native_geometry_material_v2', 'odoo_native_geometry_material_v3', 2),
        ('native-observed-context-geometry-finite-material-v2', 'native-observed-context-geometry-finite-material-v3', 1),
    ))
OdooV066NativeMaterialAdapter = _impl.OdooV066NativeMaterialAdapter
PROFILE, VIEWPORT = _impl.PROFILE, _impl.VIEWPORT
NATIVE_CONTEXT_JS, VISIBLE_CONTROLS_JS = _impl.NATIVE_CONTEXT_JS, _impl.VISIBLE_CONTROLS_JS
valid_context, audit_guard, border_material = _impl.valid_context, _impl.audit_guard, _impl.border_material


def public_binding():
    assert_frozen_v2_sources()
    root = Path(__file__).resolve().parents[2]
    value = _impl.public_binding()
    extra = ('enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v3.py',
             'enterprise_fallback/odoo18/odoo_native_geometry_material_v3.py',
             'enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py',
             'enterprise_fallback/odoo18/native_compat_source_loader_v1.py')
    bindings = {**value['bindings_sha256'], **{name: sha256((root/name).read_bytes()).hexdigest() for name in extra}}
    return {**value, 'schema': 'envloop-odoo-native-material-common-binding-v3',
            'geometry_projection': 'finite_native_css_phases_unambiguous_nearest_device_pixel',
            'bindings_sha256': bindings,
            'binding_sha256': sha256(json.dumps(bindings,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}


def __getattr__(name):
    return getattr(_impl, name)
