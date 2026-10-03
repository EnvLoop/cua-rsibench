"""Uniform additive Writer pointer contract; frozen V48 and input guards remain."""
import argparse,hashlib,json
from pathlib import Path
from types import FunctionType
from . import native_editor_runtime_v48 as base
from . import native_editor_reader_v49 as reader
BASE_SHA='3870959b33ce4b232f560d902fd137acab78a1befeef0d843d93557a9e4a7c18'
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V48 runtime changed')
parent=base.parent
EXTRA=('native_desktop_factory/native_writer_pointer_capability_v49.py','native_desktop_factory/native_editor_reader_v49.py','native_desktop_factory/native_editor_runtime_v49.py','tests/test_native_desktop_writer_pointer_v49.py')
POLICY={'schema':'native-Writer-pointer-contract-v49','scope':'exact_known_build_Writer_paragraph_and_original_document_text_ancestor','strict_zero_child_leaf_required':True,'current_owned_EditMode_and_medium_required':True,'raw_sensitive_and_focus_preserved':True,'keyboard_eligible_only_actual_raw_focused':True,'original_keyboard_focus_and_lease_guards_unchanged':True,'all_seven_roles_uniform':True,'old_results_reclassified':False}

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-Writer-pointer-runtime-source-v49','native_reader_schema':reader.SCHEMA,'source_sha256s':{**old['source_sha256s'],**{n:parent.digest((root/n).read_bytes()) for n in EXTRA}},'writer_pointer_policy':POLICY,'native_qualification_passed':False,'old_results_reclassified':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 fn=base.factory;clone=FunctionType(fn.__code__,{**fn.__globals__,'source_manifest':source_manifest},fn.__name__,fn.__defaults__,fn.__closure__);clone.__kwdefaults__=fn.__kwdefaults__
 result=clone(manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 cls=result.actor_class;original_bootstrap=cls._bootstrap;source_root=Path(source_root or Path(__file__).resolve().parents[1])
 def bootstrap(self):
  original_bootstrap(self)
  files=('native_editor_reader_v49.py','native_writer_pointer_capability_v49.py')
  parent.json_put(self.root,self.out/'writer-source-bootstrap-intent.private.json',{'files':{n:parent.digest((source_root/'native_desktop_factory'/n).read_bytes()) for n in files},'native_guard_changed':False})
  for name in files:self.sandbox.files.write(parent.REMOTE+'/'+name,(source_root/'native_desktop_factory'/name).read_bytes())
 cls._bootstrap=bootstrap
 old=cls.native_probe
 ns={**old.__globals__,'PROBE_SOURCE':Path(reader.__file__),'PROBE_PATH':parent.REMOTE+'/native_editor_reader_v49.py','PROBE_SCHEMA':reader.SCHEMA}
 cls.native_probe=FunctionType(old.__code__,ns,old.__name__,old.__defaults__,old.__closure__)
 original_prepare=cls.prepare
 def prepare(self,**kwargs):
  original_prepare(self,**kwargs)
  self.receipt['parent_declared_native_reader_sha256']=self.receipt.get('native_reader_sha256')
  self.receipt['native_reader_sha256']=parent.digest(Path(reader.__file__).read_bytes());self.receipt['writer_pointer_policy']=POLICY;self.persist()
 cls.prepare=prepare
 return result

control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-Writer-pointer-public-binding-v49','source_manifest_sha256':parent.digest(parent.canonical(manifest)),'writer_pointer_policy':POLICY,'native_policy_sha256':manifest['native_policy_sha256'],'actor_paths':manifest['actor_paths'],'native_reader_schema':reader.SCHEMA,'observation_policy_sha256':manifest['observation_policy_sha256'],'native_qualification_passed':False,'old_results_reclassified':False,'model_calls':0,'tinker_calls':0}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['source','public-binding']);parser.add_argument('--root',type=Path);a=parser.parse_args();print(json.dumps(source_manifest(a.root) if a.mode=='source' else public_binding(a.root),sort_keys=True,separators=(',',':')))
