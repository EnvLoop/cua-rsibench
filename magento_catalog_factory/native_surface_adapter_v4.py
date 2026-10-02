"""Same bounded native reads with current-document rendered principal evidence."""
from types import FunctionType
from . import native_surface_adapter_v3 as original
from . import native_surface_adapter_v2 as reads
from .native_principal_header_v2 import NATIVE_JS

_base=reads._meta_current
_meta=FunctionType(_base.__code__,{**_base.__globals__,'NATIVE_JS':NATIVE_JS},_base.__name__,_base.__defaults__,_base.__closure__)
_meta.__kwdefaults__=_base.__kwdefaults__
_base=original.NativeAdapter.meta
_current=FunctionType(_base.__code__,{**_base.__globals__,'_meta_current':_meta},_base.__name__,_base.__defaults__,_base.__closure__)
_current.__kwdefaults__=_base.__kwdefaults__

class NativeAdapter(original.NativeAdapter):
    meta=_current
