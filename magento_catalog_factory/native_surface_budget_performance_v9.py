"""Original SQL/reset oracle with the exact V3 native process evidence decoder."""
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from . import native_surface_budget_performance_v2 as original

source=Path(original.__file__).read_bytes()
if sha256(source).hexdigest()!='4fba00c2872d6d656433b040e2177d68e6e5eb53a65ad676368cc8f50aa9a749':
    raise ValueError('Frozen queue verdict source changed')
text=source.decode()
for before,after,count in [('native_queue_profile_v2 as profile,native_queue_runtime_v2 as runtime',
    'native_queue_profile_v5 as profile,native_queue_runtime_v9 as runtime',1),
    ('magento_catalog_factory/native_surface_budget_performance_v2.py','magento_catalog_factory/native_surface_budget_performance_v9.py',1),
    ('magento_catalog_factory/native_queue_profile_v2.py','magento_catalog_factory/native_queue_profile_v5.py',1),
    ('magento_catalog_factory/native_queue_runtime_v2.py','magento_catalog_factory/native_queue_runtime_v9.py',1),
    ('magento_catalog_factory.native_surface_budget_performance_v2','magento_catalog_factory.native_surface_budget_performance_v9',1)]:
    if text.count(before)!=count:raise ValueError('Checked native queue verdict counterpart changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_budget_performance_v9')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,str(Path(original.__file__)),'exec'),_impl.__dict__)
from types import FunctionType
_method=_impl.original_audit
if _method.__code__.co_names.count('native_surface_workers_v1')!=1:raise ValueError('Checked original saved auditor source import changed')
_code=_method.__code__.replace(co_names=tuple('native_surface_workers_v9' if name=='native_surface_workers_v1' else name for name in _method.__code__.co_names))
_scoped=FunctionType(_code,dict(_method.__globals__),_method.__name__,_method.__defaults__,_method.__closure__)
_scoped.__kwdefaults__=_method.__kwdefaults__
_impl.original_audit=_scoped

def __getattr__(name):return getattr(_impl,name)
