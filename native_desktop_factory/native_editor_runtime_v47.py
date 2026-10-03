"""Uniform V47 proof producer; V46 observation policy and guards preserved."""
import argparse, hashlib, inspect, json
from pathlib import Path
from types import FunctionType
from . import native_editor_runtime_v45 as editor45
from . import native_guarded_observation_runtime_v46 as base
from . import native_editor_reader_v47 as reader
from . import native_editor_evidence_v47 as evidence
BASE_SHA='20ea87b3b7664ba18360c548266dff35cad4d2fcfcaa2ae01d5fce954997e650'
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V46 runtime changed')
parent=base.parent
EXTRA=('native_desktop_factory/native_editor_evidence_v47.py','native_desktop_factory/native_editor_reader_v47.py','native_desktop_factory/native_editor_runtime_v47.py','tests/test_native_desktop_expiry_rounding_v47.py')
EXPIRY_POLICY={'schema':'native-editor-conservative-expiry-v47','maximum_proof_lifetime_seconds':10,'producer':'math.nextafter(observed_at+10,negative_infinity)','validator_unchanged':True,'lifetime_extended':False,'actor_seconds':720,'maximum_actions':90,'lease_seconds':1200,'native_flags_and_guards_unchanged':True}

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-editor-conservative-expiry-runtime-source-v47','native_reader_schema':reader.SCHEMA,
  'source_sha256s':{**old['source_sha256s'],**{n:parent.digest((root/n).read_bytes()) for n in EXTRA}},
  'proof_expiry_policy':EXPIRY_POLICY,'native_qualification_passed':False,'old_results_reclassified':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 original=editor45.factory;scope={**original.__globals__,'reader':reader,'evidence':evidence,'source_manifest':source_manifest}
 source=inspect.getsource(original)
 peers="'native_editor_evidence_v45.py','native_virtual_cell_identity_v44.py'),"
 path="parent.REMOTE+'/native_editor_reader_v45.py'"
 script="parent.REMOTE+'/native_editor_evidence_v45.py'"
 for expected in (peers,path,script):
  if source.count(expected)!=1:raise ValueError('Frozen editor integration changed')
 source=source.replace(peers,"'native_editor_evidence_v45.py','native_virtual_cell_identity_v44.py','native_editor_reader_v47.py','native_editor_evidence_v47.py'),")
 source=source.replace(path,"parent.REMOTE+'/native_editor_reader_v47.py'").replace(script,"parent.REMOTE+'/native_editor_evidence_v47.py'")
 exec(compile(source,__file__,'exec'),scope)
 result=scope['factory'](manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 result.actor_class.observe=base.scoped_observe()
 return result

control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-editor-conservative-expiry-public-binding-v47','source_manifest_sha256':parent.digest(parent.canonical(manifest)),
  'proof_expiry_policy':EXPIRY_POLICY,'observation_policy_sha256':manifest['observation_policy_sha256'],'observation_policy':manifest['observation_policy'],
  'native_policy_sha256':manifest['native_policy_sha256'],'native_reader_schema':manifest['native_reader_schema'],'actor_paths':manifest['actor_paths'],
  'native_qualification_passed':False,'old_results_reclassified':False,'model_calls':0,'tinker_calls':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['source','public-binding']);parser.add_argument('--root',type=Path);args=parser.parse_args()
 print(json.dumps(source_manifest(args.root) if args.mode=='source' else public_binding(args.root),sort_keys=True,separators=(',',':')))
