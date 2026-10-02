"""Reuse the frozen V38 common launcher with one checked current reader."""
from pathlib import Path
from types import FunctionType
from . import terminal_owned_runtime as base
from . import native_current_inventory as reader

BASE_RUNTIME_SHA='7f5fbea2df11a926fd3d06edda45d57072e3dfe954eef5171fe84fa7a202f3ca'
if base.parent.digest(Path(base.__file__).read_bytes())!=BASE_RUNTIME_SHA:raise ValueError('Frozen V38 runtime source changed')

EXTRA=('native_desktop_factory/native_current_inventory.py','native_desktop_factory/current_inventory_runtime.py',
 'tests/test_native_desktop_current_inventory.py')

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-current-inventory-runtime-source-v39','native_reader_schema':reader.SCHEMA,
  'source_sha256s':{**old['source_sha256s'],**{name:base.parent.digest((root/name).read_bytes()) for name in EXTRA}},
  'native_inventory_order':'bounded_breadth_first','application_cache_policy':'same_owned_process_and_bus_NONE','old_results_reclassified':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 original=base.factory
 namespace={**original.__globals__,'SCHEMA':reader.SCHEMA,'SOURCE':Path(reader.__file__),'source_manifest':source_manifest}
 source=__import__('inspect').getsource(original)
 needle="'PEERS':(*parent.PEERS,'native_hit_identity_diagnostic_v33.py','native_forward_owned_probe_v37.py','native_terminal_hit_diagnostic_v38.py'),"
 base.parent.require(source.count(needle)==1,'Frozen V38 factory scope changed')
 source=source.replace(needle,"'PEERS':(*parent.PEERS,'native_hit_identity_diagnostic_v33.py','native_forward_owned_probe_v37.py','native_terminal_hit_diagnostic_v38.py','native_current_inventory.py'),")
 source=source.replace("'PROBE_PATH':parent.REMOTE+'/native_terminal_hit_diagnostic_v38.py'","'PROBE_PATH':parent.REMOTE+'/native_current_inventory.py'")
 exec(compile(source,__file__,'exec'),namespace)
 return namespace['factory'](manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)

control_driver=base.control_driver
