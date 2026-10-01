"""Fresh semantic source/qualification contract; never reclassifies old rows."""
from pathlib import Path
import hashlib
from cursibench import native_surface_guard_policy_v1 as policy
from .current_teacher_worker_v22 import source_closure as teacher_sources

SOURCES=('native_desktop_factory/native_accessibility_probe_v23.py','native_desktop_factory/semantic_native_transport_v23.py',
 'native_desktop_factory/semantic_source_load_v23.py','native_desktop_factory/semantic_episode_engine_v23.py',
 'native_desktop_factory/semantic_native_counterparts_v23.py','native_desktop_factory/semantic_native_epoch_v23.py',
 'tests/test_native_desktop_semantic_native_transport_v23.py','tests/test_native_desktop_accessibility_probe_v23.py','tests/test_native_desktop_semantic_episode_engine_v23.py','src/cursibench/native_surface_guard_policy_v1.py')

def proposal(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);sources=teacher_sources(root)
 for name in SOURCES:sources[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
 return {'schema':'cua-native-desktop-semantic-epoch-proposal-v23','source_sha256s':sources,'native_policy_sha256':policy.POLICY_SHA,
  'status':'source_only_not_native_qualified','max_actions':90,'actor_seconds':720,'lease_seconds':1200,
  'actor_paths':['teacher','control','shared-base','astra','sol56','sol6','luna6'],'all_actor_paths_same_source':True,
  'native_metadata_kind':'actual-owned-x11-gi-atspi-state-and-hit-testing','raster_equality_required':False,'pixel_masking':False,
  'task_gold_used_by_guard':False,'raw_observation_and_predispatch_retained':True,'source_epoch_requires_fresh_native_qualification':True,
  'native_qualification_passed':False,'old_results_reclassified':False,'provider_calls':0,'official_model_results':0}

def validate_activation(receipt,*,expected_source_sha256s,independent_raw_auditor=None):
 if receipt.get('schema')!='cua-native-desktop-semantic-native-qualification-v23' or receipt.get('source_sha256s')!=expected_source_sha256s or receipt.get('native_policy_sha256')!=policy.POLICY_SHA:
  raise ValueError('Fresh semantic native qualification source binding required')
 for field in ['actual_native_probe_observed','all_seven_paths_qualified','fresh_control_trios_120_completed','raw_native_metadata_reopened','native_io_receipts_reopened','actual_clock_and_distinct_reset_verified']:
  if receipt.get(field) is not True:raise ValueError('Actual fresh semantic native proofs incomplete')
 if receipt.get('old_results_reclassified') is not False:raise ValueError('Historical rows cannot become semantic qualification')
 if not callable(independent_raw_auditor):raise ValueError('Independent reopening of actual 120 native control/raw IO/reset receipts required')
 result=independent_raw_auditor(receipt)
 if type(result) is not dict or result.get('native_epoch_schema')!='v23' or result.get('raw_native_evidence_reopened') is not True or result.get('completed_current_control_trios')!=120:
  raise ValueError('Actual native evidence auditor has not admitted this new epoch')
 return receipt
