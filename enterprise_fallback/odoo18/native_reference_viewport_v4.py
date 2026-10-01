"""Fresh Ref4 source binding around the exact frozen Ref3 viewport algorithm."""
from .native_compat_source_loader_v1 import load_source


_PARENT = "enterprise_fallback/odoo18/native_reference_viewport_v3.py"
_impl = load_source(
    _PARENT,
    "enterprise_fallback.odoo18._native_reference_viewport_v4",
    "f3f1ecd1096af2ca1005beefc0132c0fefe8402ffdb1c8d1095864ffe69cd755",
    (
        ("native_surface_workers_v13", "native_surface_workers_v14", 1),
        ("odoo-native-viewport-reference-source-v3", "odoo-native-viewport-reference-source-v4", 1),
        ("same_v13_adapter_actor_scorer_reset", "same_v14_adapter_actor_scorer_reset", 1),
        ("viewport-reference-v3", "viewport-reference-v4", 1),
        ("viewport-case-v3", "viewport-case-v4", 1),
    ),
)
_impl.REFERENCE_FILES = tuple(dict.fromkeys(_impl.REFERENCE_FILES + (
    "enterprise_fallback/odoo18/native_reference_facet_v2.py",
    "enterprise_fallback/odoo18/native_compat_source_loader_v1.py",
    "enterprise_fallback/odoo18/native_reference_viewport_v4.py",
    "tools/odoo_v066_native_reference_qualification_v4.py",
)))


def __getattr__(name):
    return getattr(_impl, name)
