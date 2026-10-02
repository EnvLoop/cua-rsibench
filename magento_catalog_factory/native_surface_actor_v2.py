"""Identical original actor body with the exact current uniform source stamp."""
from pathlib import Path
from hashlib import sha256
from types import FunctionType
from . import native_surface_actor_v1 as original
if sha256(Path(original.__file__).read_bytes()).hexdigest()!='e50def6066e7883f8a0423119f47ff6e9d56d579c6a3d444daa7fe0876f6ffaf':
    raise ValueError('Frozen original actor body changed')
method=original.run_task
if method.__code__.co_names.count('native_surface_workers_v1')!=1:raise ValueError('Checked actor source stamp import changed')
code=method.__code__.replace(co_names=tuple('native_surface_workers_v6' if name=='native_surface_workers_v1' else name
    for name in method.__code__.co_names))
run_task=FunctionType(code,dict(method.__globals__),method.__name__,method.__defaults__,method.__closure__)
run_task.__kwdefaults__=method.__kwdefaults__
