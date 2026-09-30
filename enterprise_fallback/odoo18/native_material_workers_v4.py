"""Retain the v2 worker API with a new common source binding and fresh v4 proof."""
from .native_compat_source_loader_v1 import load_source, assert_frozen_v2_sources

_impl = load_source('enterprise_fallback/odoo18/native_material_workers_v2.py',
    'enterprise_fallback.odoo18._native_material_workers_v4',
    'f989273c67f57bcf11101f26395168d33e45f93f7c1f7fc418c102fdbec3c453', (
        ('odoo_v066_native_material_adapter_v2', 'odoo_v066_native_material_adapter_v4', 4),
        ('-v2"', '-v4"', 5),
        ('eligible = (context["rfq_form"] and context["form_count"] == 1 and\n'
         '                context["modal_count"] == 0 and context["viewer_count"] == 0 and\n'
         '                (context["focus_in_form"] or context["focus_is_body"]))\n'
         '    adapter_module = importlib.import_module(ADAPTER_MODULE)',
         'adapter_module = importlib.import_module(ADAPTER_MODULE)\n'
         '    eligible = adapter_module.material_eligible(context, {"type": "wait"})',1),
        ('adapter_module.border_material(observation.screenshot_bytes, context["native_geometry"])',
         'adapter_module.border_material(observation.screenshot_bytes, context)',1),
        ('adapter_module.border_material(raw, context["native_geometry"])',
         'adapter_module.border_material(raw, context)',1),
    ))
_impl.SOURCE_FILES = tuple(dict.fromkeys(_impl.SOURCE_FILES + (
    'enterprise_fallback/odoo18/native_material_workers_v4.py',
    'enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py',
    'enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v4.py',
    'enterprise_fallback/odoo18/odoo_native_geometry_material_v3.py',
    'enterprise_fallback/odoo18/odoo_native_search_material_v4.py',
    'enterprise_fallback/odoo18/native_compat_source_loader_v1.py',
    'tools/odoo_v066_native_material_qualification_v4.py',
)))


_base_public_binding = _impl.public_binding


def public_binding():
    assert_frozen_v2_sources()
    return _base_public_binding()


# Only this new isolated namespace changes; original v2 modules stay intact.
_impl.public_binding = public_binding


def __getattr__(name):
    return getattr(_impl, name)
