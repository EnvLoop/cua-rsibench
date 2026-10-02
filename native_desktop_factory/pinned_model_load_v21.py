"""Load exact legacy worker bodies into a separate reviewed v21 namespace."""
from hashlib import sha256
from pathlib import Path
import sys
from types import ModuleType

PINS={
 'prospective_model_worker_v11.py':'03b87428d0730ef62d95b1820810eb09b8094f700e0f983a5794327b36c1efe5',
 'train_weak_base_pilot_v11.py':'690cc091064926a5f343076ec39ffb3092e3f35c32c63067b4e66accd869702e',
 'model_transport_integration_v11.py':'2bfd65e07e4b86f2a224d7e7d5456ec8fc63379fc75c3ed76cdcf97634d8cc0b',
 'shared_base_model_execution_v11.py':'a8ed414cb713049d54368a6942490c9ee8e7d0268fa301df539927f4f4a7c1fc',
}


def load(filename,name,replacements=()):
    file=Path(__file__).with_name(filename);raw=file.read_bytes()
    if sha256(raw).hexdigest()!=PINS[filename]:raise ValueError('v21_pinned_legacy_source_changed')
    source=raw.decode()
    for before,after in replacements:
        if source.count(before)!=1:raise ValueError('v21_pinned_patch_not_exactly_once')
        source=source.replace(before,after)
    module=ModuleType(name);module.__package__='native_desktop_factory';module.__file__=str(file)
    sys.modules[name]=module
    try:exec(compile(source,name,'exec'),module.__dict__)
    except BaseException:sys.modules.pop(name,None);raise
    return module
