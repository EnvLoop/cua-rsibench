"""Uniform owned V41 factory and offline source/public-binding entrypoints."""
import argparse,hashlib,inspect,json
from pathlib import Path
from types import FunctionType,SimpleNamespace
from . import business_native_runtime as base
from . import native_window_current_reader as reader
from . import native_atspi_warning_policy_v32 as warning

BASE_SHA='878dde4529190bcbf38af9b22160c11a7b5f8021e15ad763d8b7019e67bcff1d'
EXTRA=('native_desktop_factory/native_window_current_reader.py','native_desktop_factory/native_window_current_runtime.py',
 'native_desktop_factory/native_client_coordinate_probe.py','native_desktop_factory/native_coordinate_probe.py',
 'tests/test_native_desktop_window_current.py','tests/test_native_desktop_client_coordinates.py','tests/test_native_desktop_coordinate_probe.py')
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V40 runtime changed')

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-window-current-runtime-source-v41','native_reader_schema':reader.SCHEMA,
  'source_sha256s':{**old['source_sha256s'],**{name:base.current.base.parent.digest((root/name).read_bytes()) for name in EXTRA}},
  'native_coordinate_api':'WINDOW_plus_verified_absolute_X11_client_origin',
  'editable_container_requires_original_native_record':True,'physical_pixels_retargeted':False,'old_results_reclassified':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 original=base.factory;ns={**original.__globals__,'reader':reader,'source_manifest':source_manifest}
 source=inspect.getsource(original)
 peers="'native_current_inventory.py','native_business_reader.py'),"
 path="parent.REMOTE+'/native_business_reader.py'"
 base.current.base.parent.require(source.count(peers)==1 and source.count(path)==1,'Frozen V40 reader integration changed')
 source=source.replace(peers,"'native_current_inventory.py','native_business_reader.py','native_window_current_reader.py','native_client_coordinate_probe.py'),")
 source=source.replace(path,"parent.REMOTE+'/native_window_current_reader.py'")
 exec(compile(source,__file__,'exec'),ns)
 result=ns['factory'](manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 classify=warning.classify
 scoped=FunctionType(classify.__code__,{**classify.__globals__,'FILES':warning.FILES|{'native_window_current_reader.py'}},classify.__name__,classify.__defaults__,classify.__closure__)
 result.actor_class.native_probe.__globals__['warning_policy']=SimpleNamespace(classify=scoped)
 return result

control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root);parent=base.current.base.parent
 return {'schema':'cua-native-window-current-public-binding-v41','source_manifest_sha256':parent.digest(parent.canonical(manifest)),
  'native_policy_sha256':manifest['native_policy_sha256'],'native_reader_schema':manifest['native_reader_schema'],
  'actor_paths':manifest['actor_paths'],'app_kinds':['calc','writer','impress'],'native_qualification_passed':False,
  'model_calls':0,'tinker_calls':0,'old_results_reclassified':False,'provider_dispatch_performed':False}

def source_registration(*,root,native_epoch_sha256):
 from cursibench.full_study_native_counterparts_v22 import register
 sources=source_manifest(root)['source_sha256s']
 return register(root,cell_id='desktop-native',native_source_sha256s=sources,
  actor_clock_source_sha256=sources['native_desktop_factory/actor_deadline_future_v21.py'],native_epoch_sha256=native_epoch_sha256,qualified=False)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['source','public-binding']);parser.add_argument('--root',type=Path);args=parser.parse_args()
 print(json.dumps(source_manifest(args.root) if args.mode=='source' else public_binding(args.root),sort_keys=True,separators=(',',':')))
