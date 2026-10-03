"""Uniform Writer observation inventory, unchanged V49 native input guards."""
import argparse,hashlib,json
from pathlib import Path
from types import FunctionType
from . import native_editor_runtime_v49 as base
from . import native_editor_reader_v50 as reader
BASE_SHA='aa53226dcdc6e99d39072e05889fa300db6db2d72f4b030f5e29c04430f6e8ed'
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V49 runtime changed')
parent=base.parent
EXTRA=('native_desktop_factory/native_writer_inventory_v50.py','native_desktop_factory/native_editor_reader_v50.py','native_desktop_factory/native_editor_runtime_v50.py','tests/test_native_desktop_writer_inventory_v50.py')
POLICY={'schema':'native-bounded-Writer-observation-inventory-v50','known_Writer_document_text_only':True,'direct_visible_owned_zero_child_paragraphs_only':True,'original_child_cap128_forward_cap64_node512_depth32_preserved':True,'action_point_or_text_selector_used':False,'other_managed_roles_deferred_unchanged':True,'original_observed_current_target_equality_required':True,'all_seven_roles_uniform':True,'old_results_reclassified':False}

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-Writer-observation-inventory-source-v50','native_reader_schema':reader.SCHEMA,'source_sha256s':{**old['source_sha256s'],**{n:parent.digest((root/n).read_bytes()) for n in EXTRA}},'writer_observation_inventory_policy':POLICY,'native_qualification_passed':False,'old_results_reclassified':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 fn=base.factory;clone=FunctionType(fn.__code__,{**fn.__globals__,'source_manifest':source_manifest},fn.__name__,fn.__defaults__,fn.__closure__);clone.__kwdefaults__=fn.__kwdefaults__
 result=clone(manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 cls=result.actor_class;original_bootstrap=cls._bootstrap;source_root=Path(source_root or Path(__file__).resolve().parents[1])
 def bootstrap(self):
  original_bootstrap(self)
  files=('native_editor_reader_v50.py','native_writer_inventory_v50.py')
  parent.json_put(self.root,self.out/'writer-inventory-bootstrap-intent.private.json',{'files':{n:parent.digest((source_root/'native_desktop_factory'/n).read_bytes()) for n in files},'native_guard_changed':False})
  for name in files:self.sandbox.files.write(parent.REMOTE+'/'+name,(source_root/'native_desktop_factory'/name).read_bytes())
 cls._bootstrap=bootstrap
 old=cls.native_probe;ns={**old.__globals__,'PROBE_SOURCE':Path(reader.__file__),'PROBE_PATH':parent.REMOTE+'/native_editor_reader_v50.py','PROBE_SCHEMA':reader.SCHEMA}
 cls.native_probe=FunctionType(old.__code__,ns,old.__name__,old.__defaults__,old.__closure__)
 original_prepare=cls.prepare
 def prepare(self,**kwargs):
  original_prepare(self,**kwargs);self.receipt['native_reader_sha256']=parent.digest(Path(reader.__file__).read_bytes());self.receipt['writer_observation_inventory_policy']=POLICY;self.persist()
 cls.prepare=prepare
 return result
control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-Writer-observation-inventory-binding-v50','source_manifest_sha256':parent.digest(parent.canonical(manifest)),'writer_observation_inventory_policy':POLICY,'native_policy_sha256':manifest['native_policy_sha256'],'actor_paths':manifest['actor_paths'],'native_reader_schema':reader.SCHEMA,'native_qualification_passed':False,'old_results_reclassified':False,'model_calls':0,'tinker_calls':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['source','public-binding']);p.add_argument('--root',type=Path);a=p.parse_args();print(json.dumps(source_manifest(a.root) if a.mode=='source' else public_binding(a.root),sort_keys=True,separators=(',',':')))
