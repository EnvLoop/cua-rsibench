"""Same paid teacher contract, current uniform runtime and saved verifier."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'magento_catalog_factory/native_surface_teacher_v1.py').read_bytes()
if sha256(source).hexdigest()!='a1481de18a590552538fe4fd929cfbd3d0b72012add8afab2ab2853049c42992':
    raise ValueError('Frozen teacher bridge changed')
text=source.decode()
for before,after in [('from .native_surface_workers_v1 import','from .native_surface_workers_v4 import'),
    ('from .native_queue_runtime_v2 import','from .native_queue_runtime_v4 import'),
    ('from .native_surface_budget_performance_v2 import','from .native_surface_budget_performance_v4 import')]:
    if text.count(before)!=1:raise ValueError('Checked teacher uniform counterpart changed')
    text=text.replace(before,after)
_impl=ModuleType('magento_catalog_factory._native_surface_teacher_v2')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,'checked-current-magento-teacher-bridge-v2','exec'),_impl.__dict__)
def __getattr__(name):return getattr(_impl,name)
