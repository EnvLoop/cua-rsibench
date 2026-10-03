"""Uniform known-Impress focused leaf projection; original input guards unchanged."""
import argparse,hashlib,json
from pathlib import Path
from types import FunctionType
from . import native_editor_runtime_v51 as base
from . import native_editor_reader_v52 as reader
BASE_SHA='7d26bc0abebcad1be864bbae37b7a5e7d00560553fd718aa3ca83f5ca710f89d'
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V51 runtime changed')
parent=base.parent
EXTRA=('native_desktop_factory/native_impress_focus_v52.py','native_desktop_factory/native_editor_reader_v52.py','native_desktop_factory/native_editor_runtime_v52.py','tests/test_native_desktop_impress_focus_v52.py')
POLICY={'schema':'native-known-Impress-focused-leaf-projection-v52','complete_visible_document_scope_required':True,'strict_unique_raw_focused_editable_paragraph_required':True,'other_raw_focused_nodes_must_be_verified_document_ancestors':True,'raw_flags_targets_and_global_incomplete_status_preserved':True,'managed_deferred_unknown_unrelated_or_multiple_leaves_refuse':True,'existing_unique_node_budget_and_depth_unchanged':True,'original_native_input_keyboard_lease_nonce_and_paired_capture_unchanged':True,'all_seven_roles_uniform':True,'old_results_reclassified':False}
def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-Impress-focused-leaf-runtime-source-v52','native_reader_schema':reader.SCHEMA,'source_sha256s':{**old['source_sha256s'],**{n:parent.digest((root/n).read_bytes()) for n in EXTRA}},'Impress_focus_policy':POLICY,'native_qualification_passed':False,'old_results_reclassified':False}
def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 fn=base.factory;clone=FunctionType(fn.__code__,{**fn.__globals__,'source_manifest':source_manifest},fn.__name__,fn.__defaults__,fn.__closure__);clone.__kwdefaults__=fn.__kwdefaults__
 result=clone(manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 cls=result.actor_class;original_bootstrap=cls._bootstrap;source_root=Path(source_root or Path(__file__).resolve().parents[1])
 def bootstrap(self):
  original_bootstrap(self);files=('native_editor_reader_v52.py','native_impress_focus_v52.py')
  parent.json_put(self.root,self.out/'Impress-focus-bootstrap-intent.private.json',{'files':{n:parent.digest((source_root/'native_desktop_factory'/n).read_bytes()) for n in files},'native_guard_changed':False})
  for name in files:self.sandbox.files.write(parent.REMOTE+'/'+name,(source_root/'native_desktop_factory'/name).read_bytes())
 cls._bootstrap=bootstrap
 old=cls.native_probe;ns={**old.__globals__,'PROBE_SOURCE':Path(reader.__file__),'PROBE_PATH':parent.REMOTE+'/native_editor_reader_v52.py','PROBE_SCHEMA':reader.SCHEMA}
 cls.native_probe=FunctionType(old.__code__,ns,old.__name__,old.__defaults__,old.__closure__)
 original_prepare=cls.prepare
 def prepare(self,**kwargs):
  original_prepare(self,**kwargs);self.receipt['native_reader_sha256']=parent.digest(Path(reader.__file__).read_bytes());self.receipt['Impress_focus_policy']=POLICY;self.persist()
 cls.prepare=prepare
 return result
control_driver=base.control_driver
def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-Impress-focused-leaf-public-binding-v52','source_manifest_sha256':parent.digest(parent.canonical(manifest)),'Impress_focus_policy':POLICY,'native_policy_sha256':manifest['native_policy_sha256'],'actor_paths':manifest['actor_paths'],'native_reader_schema':reader.SCHEMA,'native_qualification_passed':False,'old_results_reclassified':False,'model_calls':0,'tinker_calls':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['source','public-binding']);p.add_argument('--root',type=Path);a=p.parse_args();print(json.dumps(source_manifest(a.root) if a.mode=='source' else public_binding(a.root),sort_keys=True,separators=(',',':')))
