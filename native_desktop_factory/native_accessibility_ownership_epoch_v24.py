"""Source-bound ownership correction; actual Calc facts only, no activation."""
from pathlib import Path
import hashlib,json
from .native_accessibility_probe_v24 import PIN,ATTESTED_EXE_SHA

SOURCES=('native_desktop_factory/native_accessibility_probe_v23.py','native_desktop_factory/native_accessibility_probe_v24.py',
 'native_desktop_factory/native_accessibility_ownership_epoch_v24.py','tests/test_native_desktop_accessibility_probe_v24.py',
 'docs/evidence/native-accessibility-ownership-observed-2026-10-01.json')

def proposal(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCES}
 facts=json.loads((root/SOURCES[-1]).read_bytes())
 if sources[SOURCES[0]]!=PIN or facts['process_executable_sha256']!=ATTESTED_EXE_SHA or facts['native_wm_class']!='libreoffice-calc' or facts['native_uid']!=facts['probe_uid']:
  raise ValueError('Actual ownership diagnostic/frozen source binding changed')
 return {'schema':'cua-native-accessibility-ownership-source-epoch-v24','source_sha256s':sources,'native_observed_application_kinds':['calc'],
  'unobserved_application_kinds':['impress','writer'],'unobserved_types_active':False,'uid_equality_required':True,'exact_wm_class_required':True,
  'attested_executable_bytes_required':True,'gi_native_observed':False,'new_native_probe_required':True,'native_qualification_passed':False,
  'old_rejections_reclassified':False,'provider_dispatch_enabled_by_proposal':False,'official_model_results':0}
