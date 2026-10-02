"""Uniform V46 observation pairs; V23–V45 bytes and guard are unchanged."""
import argparse,hashlib,inspect,json,textwrap
from pathlib import Path
from types import FunctionType
from . import native_editor_runtime_v45 as base
from . import semantic_native_transport_v23 as transport

BASE_SHA='d40edbf8643be5cc92f6b4e0f2911289d8b2ff38cda27cea5bcfc826bb906f16'
OBSERVATION_POLICY={'schema':'native-guarded-observation-pairs-v46','scope':'all_seven_actor_paths',
 'observation_captures_per_turn':1,'native_probes_per_observation_capture':2,
 'predispatch_captures_per_turn':1,'native_probes_per_predispatch_capture':2,
 'before_after_metadata_equality_required':True,'old_last_four_readiness_samples_required':False,
 'native_guard_decision_unchanged':True,'lease_nonce_keyboard_readonly_checks_unchanged':True,
 'actor_seconds':720,'maximum_actions':90,'lease_seconds':1200,'enter_resampling_changed':False,
 'old_results_reclassified':False}
EXTRA=('native_desktop_factory/native_guarded_observation_runtime_v46.py','tests/test_native_desktop_guarded_observation_v46.py')
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V45 runtime changed')
parent=base.parent

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-guarded-observation-runtime-source-v46',
  'source_sha256s':{**old['source_sha256s'],**{n:parent.digest((root/n).read_bytes()) for n in EXTRA}},
  'observation_policy':OBSERVATION_POLICY,'observation_policy_sha256':parent.digest(parent.canonical(OBSERVATION_POLICY)),
  'native_qualification_passed':False,'old_results_reclassified':False}

def scoped_observe():
 original=transport.SemanticModelGuest.observe
 source=textwrap.dedent(inspect.getsource(original))
 sampling='for sample,delay in enumerate(SAMPLE_DELAYS_MS if self.pending else (0,)):'
 claim=" if self.pending:require(all(stable_metadata(m)==stable_metadata(captures[-1][1]) for _,m in captures[-4:]),'Native readiness state not stable')\n"
 if source.count(sampling)!=1 or source.count(claim)!=1:raise ValueError('Frozen shared observation method changed')
 source=source.replace(sampling,'for sample,delay in enumerate((0,)):').replace(claim,'')
 source=source.replace("'pixel_equality_required':False}","'pixel_equality_required':False,'observation_policy':'native-guarded-observation-pairs-v46','last_four_samples_claimed':False}")
 namespace={**original.__globals__}
 exec(compile(source,__file__,'exec'),namespace)
 return namespace['observe']

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 original=base.factory;namespace={**original.__globals__,'source_manifest':source_manifest}
 clone=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
 clone.__kwdefaults__=original.__kwdefaults__
 result=clone(manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 result.actor_class.observe=scoped_observe()
 return result

control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-guarded-observation-public-binding-v46',
  'source_manifest_sha256':parent.digest(parent.canonical(manifest)),
  'observation_policy_sha256':manifest['observation_policy_sha256'],'observation_policy':OBSERVATION_POLICY,
  'native_policy_sha256':manifest['native_policy_sha256'],'native_reader_schema':manifest['native_reader_schema'],
  'actor_paths':manifest['actor_paths'],'native_qualification_passed':False,'model_calls':0,'tinker_calls':0,
  'old_results_reclassified':False,'raw_native_flags_preserved':True}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['source','public-binding']);parser.add_argument('--root',type=Path);args=parser.parse_args()
 print(json.dumps(source_manifest(args.root) if args.mode=='source' else public_binding(args.root),sort_keys=True,separators=(',',':')))
