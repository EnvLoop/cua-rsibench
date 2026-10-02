"""Retain the v2 worker API with a new common source binding and fresh v3 proof."""
from .native_compat_source_loader_v1 import load_source, assert_frozen_v2_sources

_impl = load_source('enterprise_fallback/odoo18/native_material_workers_v2.py',
    'enterprise_fallback.odoo18._native_material_workers_v3',
    'f989273c67f57bcf11101f26395168d33e45f93f7c1f7fc418c102fdbec3c453', (
        ('odoo_v066_native_material_adapter_v2', 'odoo_v066_native_material_adapter_v3', 4),
        ('-v2"', '-v3"', 5),
    ))
_impl.SOURCE_FILES = tuple(dict.fromkeys(_impl.SOURCE_FILES + (
    'enterprise_fallback/odoo18/native_material_workers_v3.py',
    'enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py',
    'enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v3.py',
    'enterprise_fallback/odoo18/odoo_native_geometry_material_v3.py',
    'enterprise_fallback/odoo18/native_compat_source_loader_v1.py',
    'tools/odoo_v066_native_material_qualification_v3.py',
)))


_base_public_binding = _impl.public_binding


def public_binding():
    assert_frozen_v2_sources()
    return _base_public_binding()


# Only this new isolated namespace changes; original v2 modules stay intact.
_impl.public_binding = public_binding


def __getattr__(name):
    return getattr(_impl, name)
