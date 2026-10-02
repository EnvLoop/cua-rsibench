"""Runnable original Magento controls with the source-bound CMS setup repair."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType
from . import native_surface_facade_v1 as ancestor

ROOT=Path(__file__).resolve().parents[1]
PARENT='magento_catalog_factory/native_surface_facade_v1.py'
PARENT_SHA='c9b4706e7e2225755d8c5d41dcef1823abc21bee7d66227999c36afc3b0a331b'
source=(ROOT/PARENT).read_bytes()
if sha256(source).hexdigest()!=PARENT_SHA:raise ValueError('Frozen Magento controls source changed')
text=source.decode()
for before,after in [('from .native_surface_workers_v1 import','from .native_surface_workers_v8 import'),
 ('from .native_queue_runtime_v2 import run_task','from .native_queue_runtime_v8 import run_task'),
 ('from .native_surface_budget_performance_v2 import audit_episode','from .native_surface_budget_performance_v8 import audit_episode')]:
    if text.count(before)!=1:raise ValueError('Checked Magento controls runtime source changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_facade_v8')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,str(ROOT/PARENT),'exec'),_impl.__dict__)
# Reuse the identical original evaluator-only sampler class accepted by the
# frozen actor. Its native mutations and source are unchanged and hash-bound.
_impl.ReferenceSampler=ancestor.ReferenceSampler

def __getattr__(name):return getattr(_impl,name)
if __name__=='__main__':_impl.main()
