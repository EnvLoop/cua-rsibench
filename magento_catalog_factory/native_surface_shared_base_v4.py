"""Reopen actual shared-base results with current V4 source and queue verifier."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'magento_catalog_factory/native_surface_shared_base_v1.py').read_bytes()
if sha256(source).hexdigest()!='6496f5ff5c7661438acb2624852500508293f24d863d0a6d3c52f8bb33664af1':
    raise ValueError('Frozen shared-base bridge changed')
text=source.decode()
for before,after in [('from .native_surface_workers_v1 import','from .native_surface_workers_v6 import'),
    ('from .native_surface_budget_performance_v2 import','from .native_surface_budget_performance_v6 import')]:
    if text.count(before)!=1:raise ValueError('Checked shared-base uniform counterpart changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_shared_base_v4')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,'checked-current-magento-shared-base-bridge-v2','exec'),_impl.__dict__)
def __getattr__(name):return getattr(_impl,name)
