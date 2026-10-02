"""Fresh native14/Ref4 saved replay; historical V13/Ref3 bytes stay intact."""
from .native_compat_source_loader_v1 import load_source
_impl = load_source(
    'enterprise_fallback/odoo18/native_reference_split_finalizer_v3.py',
    'enterprise_fallback.odoo18._native_reference_split_finalizer_v4',
    '93732b4d4185352a9f92b439a4857323f6a45c5a636dd6607456f6c1210f9d49',
    (('v13', 'v14', 3), ('v3', 'v4', 33)))
_impl.__file__ = __file__
def __getattr__(name): return getattr(_impl, name)
if __name__ == '__main__': _impl.main()
