"""Fresh v7 worker namespace; exact v6 worker mechanics and typed principal."""
from .native_compat_source_loader_v1 import load_source

_impl=load_source('enterprise_fallback/odoo18/native_surface_workers_v6.py',
 'enterprise_fallback.odoo18._native_surface_workers_v7_wrapper',
 '048e90f8d5c8e1a32193671405a29e17584eaaf939e2767d6504fcf8baed696f',(('v6','v7',9),))
_impl._impl.SOURCE_FILES=tuple(dict.fromkeys(_impl._impl.SOURCE_FILES+(
 'enterprise_fallback/odoo18/odoo_native_principal_witness_v7.py',
 'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
 'enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
 'enterprise_fallback/odoo18/native_surface_workers_v6.py',
 'tools/odoo_v066_native_surface_qualification_v6.py',)))


def __getattr__(name):return getattr(_impl,name)
