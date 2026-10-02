"""Source-bound all-app scope; preserve the old transport and actor guards."""
import inspect
from pathlib import Path
from types import FunctionType
from . import current_inventory_runtime as current
from . import native_business_reader as reader

BASE_RUNTIME_SHA='ba45d3e29a66d359757d2ded578e48a3186db3d3941706773574eefbc3b88122'
MAX_PROBE_BYTES=524288
EXTRA=('native_desktop_factory/native_business_reader.py','native_desktop_factory/business_native_runtime.py',
 'tests/test_native_desktop_business_runtime.py')
if current.base.parent.digest(Path(current.__file__).read_bytes())!=BASE_RUNTIME_SHA:raise ValueError('Frozen V39 runtime changed')

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=current.source_manifest(root)
 return {**old,'schema':'cua-native-business-current-runtime-source-v40','native_reader_schema':reader.SCHEMA,
  'source_sha256s':{**old['source_sha256s'],**{name:current.base.parent.digest((root/name).read_bytes()) for name in EXTRA}},
  'maximum_typed_probe_bytes':MAX_PROBE_BYTES,'typed_all_app_principal_checked_each_probe':True,
  'old_results_reclassified':False,'native_qualification_passed':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 original=current.factory;namespace={**original.__globals__,'reader':reader,'source_manifest':source_manifest}
 source=inspect.getsource(original)
 peer="'native_terminal_hit_diagnostic_v38.py','native_current_inventory.py'),"
 path="parent.REMOTE+'/native_current_inventory.py'"
 current.base.parent.require(source.count(peer)==1 and source.count(path)==1,'Frozen V39 runtime reader interface changed')
 source=source.replace(peer,"'native_terminal_hit_diagnostic_v38.py','native_current_inventory.py','native_business_reader.py'),")
 source=source.replace(path,"parent.REMOTE+'/native_business_reader.py'")
 exec(compile(source,__file__,'exec'),namespace)
 result=namespace['factory'](manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 original_probe=result.actor_class.native_probe
 current.base.parent.require(original_probe.__code__.co_consts.count(262144)==1,'Frozen typed probe resource limit changed')
 constants=tuple(MAX_PROBE_BYTES if value==262144 else value for value in original_probe.__code__.co_consts)
 scoped=FunctionType(original_probe.__code__.replace(co_consts=constants),original_probe.__globals__,original_probe.__name__,original_probe.__defaults__,original_probe.__closure__)
 scoped.__kwdefaults__=original_probe.__kwdefaults__
 result.actor_class.native_probe=scoped
 return result

control_driver=current.control_driver
