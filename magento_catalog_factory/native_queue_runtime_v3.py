"""Same queue/reset semantics, exact guest process ownership and CMS readiness."""
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from . import native_queue_runtime_v2 as original
from .native_quote_navigation_v2 import Runtime as NavigationRuntime

source=Path(original.__file__).read_bytes()
if sha256(source).hexdigest()!='bf84b15bf20d31243d23f91ddbc739610910b06879dc118774a388175ed55f0f':
    raise ValueError('Frozen native queue runtime changed')
text=source.decode();before='from . import native_queue_profile_v2 as profile'
if text.count(before)!=1:raise ValueError('Checked native queue profile import changed')
_impl=ModuleType('magento_catalog_factory._native_queue_runtime_v3')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text.replace(before,'from . import native_queue_profile_v3 as profile'),
    str(Path(original.__file__)),'exec'),_impl.__dict__)

class Runtime(_impl.Runtime,NavigationRuntime):
    """The V2 queue superclass now enters the isolated navigation setup bridge."""
    pass

run_task=_impl.run_task
queue_verdict=_impl.queue_verdict
NativeQueue=_impl.NativeQueue
