"""Uniform pre-open format preference; V47 native input and source stay frozen."""
import argparse,hashlib,inspect,json,textwrap
from pathlib import Path
from types import FunctionType,MethodType
from . import native_editor_runtime_v47 as base
from . import uniform_model_transport_v11 as legacy
from . import native_format_startup_preset_v48 as preset
from . import native_format_profile_guard_v48 as profile
BASE_SHA='6da0d49515a63b58dd71b4dd47c7b525d4dd2c7c1fc0680589a0b033d22c0693'
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V47 runtime changed')
parent=base.parent
EXTRA=('native_desktop_factory/native_format_startup_preset_v48.py','native_desktop_factory/native_format_profile_guard_v48.py','native_desktop_factory/native_editor_runtime_v48.py','tests/test_native_desktop_format_startup_v48.py')

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-format-startup-runtime-source-v48','source_sha256s':{**old['source_sha256s'],**{n:parent.digest((root/n).read_bytes()) for n in EXTRA}},'declared_startup_preference':preset.POLICY,'parent_profile_comparison':'mandatory_false_preference_plus_all_remaining_original_profile_properties','native_qualification_passed':False,'old_results_reclassified':False}

def startup_prepare():
 fn=legacy.ModelGuest.prepare;source=textwrap.dedent(inspect.getsource(fn));marker=" self.receipt['fresh_profile_absent']=True\n"
 if source.count(marker)!=1:raise ValueError('Original pre-open profile boundary changed')
 namespace={**fn.__globals__,'profile':profile,'preset':preset}
 exec(compile(source.replace(marker,marker+' preset.setup(self)\n'),__file__,'exec'),namespace)
 return namespace['prepare']

StartupGuest=type('StartupPreferenceGuest48',(legacy.ModelGuest,),{'prepare':startup_prepare()})

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 fn=base.factory;clone=FunctionType(fn.__code__,{**fn.__globals__,'source_manifest':source_manifest},fn.__name__,fn.__defaults__,fn.__closure__);clone.__kwdefaults__=fn.__kwdefaults__
 result=clone(manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 # C3 places this setup method before the unchanged legacy prepare; zero-arg
 # super calls in the existing native classes retain their original owners.
 guest=type('UniformFormatStartupGuest48',(result.actor_class,StartupGuest),{})
 result.actor_class=guest
 fn=result.wrap_owned_guest.__func__;scope={**fn.__globals__,'CommonNativeModelGuest':guest}
 wrapped=FunctionType(fn.__code__,scope,fn.__name__,fn.__defaults__,fn.__closure__);wrapped.__kwdefaults__=fn.__kwdefaults__
 result.wrap_owned_guest=MethodType(wrapped,result)
 return result

control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-format-startup-public-binding-v48','source_manifest_sha256':parent.digest(parent.canonical(manifest)),'declared_startup_preference':preset.POLICY,'native_policy_sha256':manifest['native_policy_sha256'],'native_reader_schema':manifest['native_reader_schema'],'actor_paths':manifest['actor_paths'],'observation_policy_sha256':manifest['observation_policy_sha256'],'native_qualification_passed':False,'old_results_reclassified':False,'model_calls':0,'tinker_calls':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['source','public-binding']);parser.add_argument('--root',type=Path);args=parser.parse_args();print(json.dumps(source_manifest(args.root) if args.mode=='source' else public_binding(args.root),sort_keys=True,separators=(',',':')))
